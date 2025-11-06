"""
VIDEO REVIEW AND RANK
Browse folders of videos, move videos into ranked folders with mouse clicks
Project-scale review and ranking for stable diffusion video projects

temp cacheing: Only visible videos in the UI are temp-copied and loaded for playback. Originals are never locked.

VERSION::20251002
"""
# ===========================================================================================
import os
import sys
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout,
                             QWidget, QGridLayout, QScrollArea, QPushButton, QHBoxLayout,
                             QLineEdit, QFileDialog)

from PyQt5.QtCore import (Qt, QThreadPool, QRunnable, pyqtSignal, QObject,
                           QEvent, QUrl)
import qdarkstyle
import cv2
from PIL import Image
from PyQt5.QtGui import QPixmap


try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
    from PyQt5.QtMultimediaWidgets import QVideoWidget
    QT_MULTIMEDIA_AVAILABLE = True
except ImportError:
    QT_MULTIMEDIA_AVAILABLE = False

# ===========================================================================================
def resolve_ffmpeg_path(project_dir: str) -> str:
    """
    Attempt to resolve a usable ffmpeg executable path with clear debug output.
    Priority:
    1) Env var FFMPEG_PATH if valid
    2) Common project-local folders (tools/ffmpeg, ffmpeg/bin)
    3) Common system locations (C:\\ffmpeg\\bin, Program Files)
    4) Fallback to just 'ffmpeg' (PATH)
    Returns the path string (may be just 'ffmpeg').
    """
    candidates = []
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        candidates.append(env_path)

    if project_dir:
        candidates.extend([
            os.path.join(project_dir, "tools", "ffmpeg", "ffmpeg.exe"),
            os.path.join(project_dir, "tools", "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(project_dir, "ffmpeg", "bin", "ffmpeg.exe"),
        ])

    candidates.extend([
        r"C:\\ffmpeg\\bin\\ffmpeg.exe",
        r"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
        r"C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
    ])

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for c in candidates:
        if c and c not in seen:
            uniq.append(c)
            seen.add(c)

    print("[DEBUG] Attempting to resolve ffmpeg path. Candidates:")
    for c in uniq:
        print(f"[DEBUG]  - {c}")

    for c in uniq:
        if os.path.isfile(c):
            print(f"[DEBUG] Using ffmpeg at: {c}")
            return c

    print("[DEBUG] Falling back to 'ffmpeg' from PATH.")
    return "ffmpeg"

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class VideoLoader(QRunnable):
    """
    Loads video paths and creates temp proxies and thumbnails for only those needed (visible in UI).
    """
    # Ensure only one ffmpeg runs at a time across all workers
    _ffmpeg_lock = threading.Lock()

    def __init__(self, video_paths, temp_dir, ffmpeg_path: str):
        super().__init__()
        self.video_paths = video_paths
        self.temp_dir = temp_dir
        self.signals = WorkerSignals()
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"

    def run(self):
        loaded = []
        for path in self.video_paths:
            try:
                temp_path = self.create_temp_proxy(path)
                thumb_path = self.create_thumbnail(path)
                loaded.append((path, temp_path, thumb_path))
            except Exception as e:
                self.signals.error.emit((e, path))
        self.signals.result.emit(loaded)
        self.signals.finished.emit()

    def create_temp_proxy(self, video_path):
        import subprocess
        base = os.path.splitext(os.path.basename(video_path))[0]
        temp_path = os.path.join(self.temp_dir, base + "_proxy.mpg")
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print(f"[DEBUG] Proxy exists, skipping: {temp_path}")
            return temp_path
        # Convert to MPEG-1 + MP2 using ffmpeg for maximum compatibility
        if os.path.basename(self.ffmpeg_path).lower() == "ffmpeg" and os.path.sep not in self.ffmpeg_path:
            print("[DEBUG] ffmpeg will be resolved via PATH: 'ffmpeg'")
        else:
            print(f"[DEBUG] Using explicit ffmpeg path: {self.ffmpeg_path}")
        if not (os.path.sep not in self.ffmpeg_path) and not os.path.isfile(self.ffmpeg_path):
            print(f"[ERROR] ffmpeg path not found: {self.ffmpeg_path}")
            raise FileNotFoundError(f"ffmpeg not found at {self.ffmpeg_path}")

        ffmpeg_cmd = [
            self.ffmpeg_path, "-y", "-i", video_path,
            "-c:v", "mpeg1video", "-c:a", "mp2",
            "-b:v", "2M", "-b:a", "192k",
            "-vf", "scale=960:720:force_original_aspect_ratio=decrease",
            temp_path
        ]
        print(f"[DEBUG] Running ffmpeg for proxy: {' '.join(ffmpeg_cmd)}")
        try:
            # Serialize all ffmpeg invocations
            with VideoLoader._ffmpeg_lock:
                result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print(f"[DEBUG] ffmpeg stdout: {result.stdout.decode('utf-8', errors='ignore')}")
            print(f"[DEBUG] ffmpeg stderr: {result.stderr.decode('utf-8', errors='ignore')}")
            # Verify output exists and is non-empty
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                raise RuntimeError(f"ffmpeg reported success but output not found or empty: {temp_path}")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] ffmpeg failed for {video_path}: {e.stderr.decode('utf-8', errors='ignore')}")
            raise
        except FileNotFoundError as e:
            print(f"[ERROR] ffmpeg executable not found: {self.ffmpeg_path}. Error: {e}")
            raise
        return temp_path

    def create_thumbnail(self, video_path):
        base = os.path.splitext(os.path.basename(video_path))[0]
        thumb_path = os.path.join(self.temp_dir, base + "_thumb.jpg")
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            print(f"[DEBUG] Thumbnail exists, skipping: {thumb_path}")
            return thumb_path
        try:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img)
                # Compute scale to fit 864x648 while keeping aspect ratio
                target_w, target_h = 864, 648
                src_w, src_h = pil_img.size
                scale = min(target_w / src_w, target_h / src_h)
                new_w = int(src_w * scale)
                new_h = int(src_h * scale)
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                thumb = Image.new("RGB", (target_w, target_h), (0, 0, 0))
                thumb.paste(pil_img, ((target_w - new_w) // 2, (target_h - new_h) // 2))
                thumb.save(thumb_path, "JPEG")
                return thumb_path
        except Exception as e:
            print(f"[ERROR] Failed to create thumbnail for {video_path}: {e}")
        return None

# ===========================================================================================
class VideoWidget(QWidget):
    """
    Widget that shows a thumbnail by default and plays a video from a temp proxy on hover (QMediaPlayer/QVideoWidget, MPEG-1/MP2).
    """
    def __init__(self, orig_path, temp_path, thumb_path, parent=None):
        super().__init__(parent)
        self.orig_path = orig_path
        self.temp_path = temp_path
        self.thumb_path = thumb_path
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.thumbnail_label = QLabel(self)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        if self.thumb_path and os.path.exists(self.thumb_path):
            pixmap = QPixmap(self.thumb_path)
            pixmap = pixmap.scaled(864, 648, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(pixmap)
        else:
            self.thumbnail_label.setText("No thumbnail")
        self.layout.addWidget(self.thumbnail_label)

        self.video_widget = None
        self.player = None
        self.setFixedSize(864, 648)
        self.setMouseTracking(True)

    def enterEvent(self, event):
        print(f"[DEBUG] enterEvent for {self.orig_path}")
        print(f"[DEBUG] Temp proxy: {self.temp_path}")
        if not os.path.exists(self.temp_path):
            print(f"[ERROR] Temp video file does not exist: {self.temp_path}")
        else:
            print(f"[DEBUG] Temp video file exists, size: {os.path.getsize(self.temp_path)} bytes")
        if QT_MULTIMEDIA_AVAILABLE and os.path.exists(self.temp_path):
            if not self.video_widget:
                print(f"[DEBUG] Creating QVideoWidget and QMediaPlayer for {self.temp_path}")
                self.video_widget = QVideoWidget(self)
                self.layout.addWidget(self.video_widget)
                self.player = QMediaPlayer(self)
                self.player.setVideoOutput(self.video_widget)
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(self.temp_path)))
                self.player.setVolume(100)
                self.player.error.connect(self._on_player_error)
                self.player.stateChanged.connect(self._on_player_state_changed)
                self.player.mediaStatusChanged.connect(self._on_media_status_changed)
            self.thumbnail_label.hide()
            self.video_widget.show()
            print(f"[DEBUG] Calling player.play() for {self.temp_path}")
            self.player.play()

    def _on_player_error(self, error):
        print(f"[PLAYER ERROR] {self.player.errorString()} (code: {error}) for file: {self.temp_path}")

    def _on_player_state_changed(self, state):
        print(f"[PLAYER STATE] State changed to {state} for file: {self.temp_path}")

    def _on_media_status_changed(self, status):
        # Loop video if at end
        if status == QMediaPlayer.EndOfMedia:
            print(f"[DEBUG] Looping video for {self.temp_path}")
            self.player.setPosition(0)
            self.player.play()

    def leaveEvent(self, event):
        if self.player and self.video_widget:
            self.player.pause()
            self.video_widget.hide()
            self.thumbnail_label.show()

    def cleanup(self):
        if self.player:
            self.player.stop()
        try:
            os.remove(self.temp_path)
        except Exception:
            pass
        if self.thumb_path and os.path.exists(self.thumb_path):
            try:
                os.remove(self.thumb_path)
            except Exception:
                pass

# ===========================================================================================
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_folder = os.getcwd()
        self.video_width = 864
        self.video_height = 648
        self.videos = []
        self.video_widgets = []
        self.temp_proxies = {}  # orig_path -> temp_path
        self.threadpool = QThreadPool()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Video Review and Rank --- LEFT CLICK = 1 --- RIGHT CLICK = 2")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: black;")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(2)

        # Project folder selection
        self.top_widget = QWidget()
        self.top_layout = QHBoxLayout(self.top_widget)
        self.project_line_edit = QLineEdit()
        self.project_line_edit.setPlaceholderText("Enter PROJECT folder path")
        self.project_line_edit.setText(self.project_folder)
        self.project_line_edit.returnPressed.connect(self.project_folder_changed)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_project_folder)
        self.top_layout.addWidget(self.project_line_edit)
        self.top_layout.addWidget(self.browse_button)
        self.main_layout.addWidget(self.top_widget)

        # ffmpeg path selection
        self.ffmpeg_row = QHBoxLayout()
        self.ffmpeg_line_edit = QLineEdit()
        self.ffmpeg_line_edit.setPlaceholderText("Path to ffmpeg.exe (optional)")
        # Pre-resolve default
        try:
            default_ffmpeg = resolve_ffmpeg_path(self.project_folder)
        except Exception:
            default_ffmpeg = "ffmpeg"
        self.ffmpeg_line_edit.setText(default_ffmpeg)
        self.ffmpeg_browse_btn = QPushButton("FFmpeg...")
        self.ffmpeg_browse_btn.clicked.connect(self.browse_ffmpeg_exe)
        self.ffmpeg_row.addWidget(QLabel("ffmpeg:"))
        self.ffmpeg_row.addWidget(self.ffmpeg_line_edit)
        self.ffmpeg_row.addWidget(self.ffmpeg_browse_btn)
        self.main_layout.addLayout(self.ffmpeg_row)

        # Videos grid
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.scroll_area.setWidget(self.grid_widget)
        self.main_layout.addWidget(self.scroll_area)

        # Filename hover label
        filename_row = QHBoxLayout()
        filename_row.addStretch(1)
        self.filename_hover_label = QLabel("")
        self.filename_hover_label.setStyleSheet("color: #A0A0A0; background: transparent; font-size: 12px;")
        filename_row.addWidget(self.filename_hover_label)
        self.main_layout.addLayout(filename_row)

        # Connect scroll to lazy load
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.lazy_load_visible_videos)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.lazy_load_visible_videos)

        # Initial load
        self.load_videos(self.project_folder)

    def project_folder_changed(self):
        self.project_folder = self.project_line_edit.text()
        if os.path.exists(self.project_folder):
            self.load_videos(self.project_folder)

    def browse_project_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select PROJECT Directory")
        if folder:
            self.project_folder = folder
            self.project_line_edit.setText(self.project_folder)
            self.load_videos(self.project_folder)

    def browse_ffmpeg_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select ffmpeg.exe", self.project_folder, "Executable (ffmpeg.exe)")
        if path:
            self.ffmpeg_line_edit.setText(path)

    def load_videos(self, folder_path):
        self.videos = [os.path.join(folder_path, file) for file in os.listdir(folder_path)
                      if file.lower().endswith('.mp4')]
        # Use a persistent temp/ folder in the project directory
        self.temp_dir = os.path.join(folder_path, 'temp')
        os.makedirs(self.temp_dir, exist_ok=True)
        self.temp_proxies.clear()
        self.display_videos_async()

    def display_videos_async(self):
        visible_paths = self.get_visible_video_paths()
        ffmpeg_path = (self.ffmpeg_line_edit.text().strip() if hasattr(self, 'ffmpeg_line_edit') else "") or resolve_ffmpeg_path(self.project_folder)
        print(f"[DEBUG] display_videos_async using ffmpeg: {ffmpeg_path}")
        loader = VideoLoader(visible_paths, self.temp_dir, ffmpeg_path)
        loader.signals.result.connect(self.on_videos_loaded)
        self.threadpool.start(loader)

    def get_visible_video_paths(self):
        # For now, just return all videos; optimize later for viewport
        return self.videos

    def on_videos_loaded(self, loaded):
        # Clean up old widgets and temp files
        for widget in getattr(self, 'video_widgets', []):
            widget.cleanup()
            widget.setParent(None)
        self.video_widgets = []
        self.temp_proxies = {orig: temp for orig, temp, thumb in loaded}
        for i, (orig_path, temp_path, thumb_path) in enumerate(loaded):
            widget = VideoWidget(orig_path, temp_path, thumb_path)
            widget.installEventFilter(self)
            self.grid_layout.addWidget(widget, i // 2, i % 2)
            self.video_widgets.append(widget)

    def lazy_load_visible_videos(self):
        # Placeholder for future: only load/copy visible videos
        pass

    def eventFilter(self, source, event):
        if isinstance(source, VideoWidget):
            if event.type() == QEvent.Enter:
                self.filename_hover_label.setText(os.path.basename(source.orig_path))
            elif event.type() == QEvent.Leave:
                self.filename_hover_label.setText("")
            elif event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.move_video_to_subfolder(source.orig_path, "01")
                elif event.button() == Qt.RightButton:
                    self.move_video_to_subfolder(source.orig_path, "02")
        return super().eventFilter(source, event)

    def move_video_to_subfolder(self, orig_path, subfolder):
        subfolder_path = os.path.join(self.project_folder, subfolder)
        os.makedirs(subfolder_path, exist_ok=True)
        new_path = os.path.join(subfolder_path, os.path.basename(orig_path))
        try:
            # Remove temp proxy before moving
            if orig_path in self.temp_proxies:
                try:
                    os.remove(self.temp_proxies[orig_path])
                except Exception:
                    pass
            os.rename(orig_path, new_path)
            # Remove video and widget from lists/grid
            if orig_path in self.videos:
                idx = self.videos.index(orig_path)
                self.videos.pop(idx)
                widget = self.video_widgets.pop(idx)
                self.grid_layout.removeWidget(widget)
                widget.cleanup()
                widget.deleteLater()
                self.refresh_grid()
        except OSError as e:
            print(f"Error moving file: {e}")

    def refresh_grid(self):
        # Remove all widgets from grid
        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.itemAt(i).widget().setParent(None)
        # Re-add widgets in order
        for i, widget in enumerate(self.video_widgets):
            self.grid_layout.addWidget(widget, i // 2, i % 2)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    app.exec_()
