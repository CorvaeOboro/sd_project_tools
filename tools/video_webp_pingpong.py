import sys
import os
import imageio

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QCheckBox, QProgressBar, QFileDialog
)
from PyQt5.QtCore import (
    Qt, QThreadPool, QRunnable, pyqtSignal, QObject, QEvent
)
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

# ----------------------------
# Worker signal definitions
# ----------------------------
class WorkerSignals(QObject):
    progress = pyqtSignal(int, int, str)  # current_index, total_count, message
    error = pyqtSignal(str)               # error message
    finished = pyqtSignal()              # no data, just a completion signal


# ----------------------------
# Worker that does conversion
# ----------------------------
class PingPongWorker(QRunnable):
    """
    A worker that processes a list of WebP files asynchronously.
    """
    def __init__(self, file_list, save_to_subfolder=False):
        super().__init__()
        self.file_list = file_list
        self.save_to_subfolder = save_to_subfolder
        self.signals = WorkerSignals()

    def run(self):
        total = len(self.file_list)

        for i, file_path in enumerate(self.file_list, start=1):
            # Emit a signal to update progress / show current file name
            self.signals.progress.emit(i, total, f"Processing {os.path.basename(file_path)}...")

            try:
                self.convert_to_pingpong(file_path, self.save_to_subfolder)
            except Exception as e:
                err_msg = f"ERROR converting {os.path.basename(file_path)}:\n{str(e)}"
                self.signals.error.emit(err_msg)

            # Emit a signal that we finished a file
            self.signals.progress.emit(i, total, f"Finished {os.path.basename(file_path)}")

        # When done, emit finished signal
        self.signals.finished.emit()

    @staticmethod
    def convert_to_pingpong(file_path, save_to_subfolder):
        """
        Reads the animated WebP file, builds forward+reverse frames,
        and saves a new WebP. Uses high or lossless quality based on source.
        """
        # Step 1: Open the file with imageio
        print(f"Reading frames from '{file_path}'...")
        reader = imageio.get_reader(file_path, format='WEBP')

        frames = []
        durations = []
        meta = reader.get_meta_data()

        loop = meta.get('loop', 0)  # 0 => infinite
        original_lossless = meta.get('lossless', False)
        original_quality = meta.get('quality', None)
        overall_fps = meta.get('fps', None)
        overall_duration = meta.get('duration', None)

        # Step 2: Read frames + attempt per-frame durations
        for idx, frame in enumerate(reader):
            frames.append(frame)
            # Attempt to get per-frame duration
            try:
                frame_meta = reader.get_meta_data(index=idx)
                durations.append(frame_meta.get('duration', 0.1))
            except:
                durations.append(0.1)

        reader.close()

        if len(frames) < 2:
            # Not truly animated or only 1 frame
            print(f"Skipping '{file_path}': only one frame found.")
            return

        # Attempt to unify durations if they are all identical and we have a single fps
        if all(abs(d - durations[0]) < 1e-9 for d in durations):
            if overall_fps:
                # Convert fps => uniform duration
                uniform_dur = 1.0 / overall_fps
                durations = [uniform_dur] * len(frames)
            elif overall_duration and isinstance(overall_duration, (int, float)):
                durations = [overall_duration] * len(frames)

        # Step 3: Build pingpong frames + durations
        # (Exclude the very last frame to avoid doubling it: forward + reverse)
        # However, to ensure *all* frames appear in reverse, we do frames[-2::-1],
        # which iterates from second-to-last down to index 0.
        pingpong_frames = frames + frames[-2::-1]
        pingpong_durations = durations + durations[-2::-1]

        # Step 4: Determine output path
        base, ext = os.path.splitext(file_path)
        base_name = os.path.basename(base)
        directory = os.path.dirname(file_path)

        if save_to_subfolder:
            out_dir = os.path.join(directory, "pingpong")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, base_name + "_pingpong" + ext)
        else:
            out_path = base + "_pingpong" + ext

        # Step 5: Decide final encoding settings
        # If original was lossless, keep it that way
        # otherwise use quality=100, method=6 for best possible quality
        lossless = original_lossless
        if lossless:
            quality = 100
        else:
            quality = 100

        print(f"Writing pingpong to '{out_path}' (lossless={lossless}, quality={quality})...")

        # Step 6: Write the file with imageio
        try:
            imageio.mimwrite(
                out_path,
                pingpong_frames,
                format='webp',
                duration=pingpong_durations,
                loop=loop,
                lossless=lossless,
                quality=quality,
                method=6  # Some Pillow builds support method=6 (best compression).
            )
        except TypeError:
            # method=6 not supported on older Pillow
            imageio.mimwrite(
                out_path,
                pingpong_frames,
                format='webp',
                duration=pingpong_durations,
                loop=loop,
                lossless=lossless,
                quality=quality
            )

        print(f"Done. Created pingpong file: {out_path}")


# ----------------------------
# The main GUI widget
# ----------------------------
class DragDropWebPConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebP PingPong Converter (Async)")
        self.setAcceptDrops(True)
        self.resize(600, 300)

        # Apply dark theme and component styles
        self.setup_dark_theme()

        # For async tasks
        self.threadpool = QThreadPool()

        # --- Layout ---
        layout = QVBoxLayout(self)

        # 1) Label for drag-drop instructions
        self.label = QLabel(
            "Drag & drop an animated WebP here to convert a single file.\n"
            "Or use the batch processing controls below."
        )
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFrameStyle(QLabel.StyledPanel | QLabel.Raised)
        self.label.setMinimumHeight(60)
        layout.addWidget(self.label)

        # 2) Batch group
        #    - line edit + browse
        #    - checkbox subfolder
        #    - process button + progress bar
        batch_layout = QVBoxLayout()

        # --- Folder selection ---
        folder_hbox = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select or type a folder path...")
        btn_browse = QPushButton("Browse...")
        btn_browse.setObjectName("browseButton")
        btn_browse.clicked.connect(self.browse_folder)
        folder_hbox.addWidget(self.folder_input)
        folder_hbox.addWidget(btn_browse)

        # --- Subfolder checkbox ---
        self.subfolder_checkbox = QCheckBox("Save outputs to a 'pingpong' subfolder")
        self.subfolder_checkbox.setChecked(False)

        # --- Process + progress bar ---
        process_hbox = QHBoxLayout()
        self.process_button = QPushButton("Process Folder")
        self.process_button.setObjectName("processButton")
        self.process_button.clicked.connect(self.process_folder)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)  # We'll adjust range dynamically

        process_hbox.addWidget(self.process_button)
        process_hbox.addWidget(self.progress_bar)

        # Status label for inline feedback (replaces message boxes)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignLeft)

        batch_layout.addLayout(folder_hbox)
        batch_layout.addWidget(self.subfolder_checkbox)
        batch_layout.addLayout(process_hbox)
        batch_layout.addWidget(self.status_label)

        layout.addLayout(batch_layout)
        layout.addStretch()

    def setup_dark_theme(self):
        """Apply a consistent dark mode palette and muted, varied button colors."""
        # Global dark palette
        dark_styles = """
            QWidget {
                background-color: #121212;
                color: #E0E0E0;
                font-size: 12pt;
            }
            QLabel#statusLabel {
                color: #A0A0A0;
                padding: 6px 4px;
            }
            QLabel {
                background-color: #1E1E1E;
                border: 1px solid #2A2A2A;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit {
                background-color: #1A1A1A;
                color: #E0E0E0;
                border: 1px solid #2C2C2C;
                border-radius: 6px;
                padding: 6px 8px;
                selection-background-color: #2E3A4A;
                selection-color: #FFFFFF;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #3A3A3A;
                background: #1A1A1A;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #3A3A3A;
                background: #395B64; /* muted teal */
            }
            QProgressBar {
                background-color: #1A1A1A;
                border: 1px solid #2C2C2C;
                border-radius: 6px;
                text-align: center;
                color: #B0B0B0;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #446688; /* muted steel blue */
                border-radius: 6px;
            }
            QPushButton {
                background-color: #262626;
                color: #E0E0E0;
                border: 1px solid #3A3A3A;
                padding: 6px 12px;
                border-radius: 8px;
            }
            QPushButton:hover {
                filter: brightness(1.1);
            }
            QPushButton:pressed {
                filter: brightness(0.9);
            }
            /* Muted, varied button colors */
            QPushButton#browseButton {
                background-color: #2D3B45; /* muted blue-gray */
                border-color: #3E4F59;
            }
            QPushButton#browseButton:hover { background-color: #334451; }
            QPushButton#browseButton:pressed { background-color: #293842; }

            QPushButton#processButton {
                background-color: #3A4336; /* muted olive */
                border-color: #4A5546;
            }
            QPushButton#processButton:hover { background-color: #414B3D; }
            QPushButton#processButton:pressed { background-color: #353F33; }
        """
        self.setStyleSheet(dark_styles)

    def show_status(self, message: str, level: str = "info"):
        """Inline status updates with subtle color cues; also prints to console."""
        colors = {
            "info": "#A0A0A0",
            "warn": "#C9A227",
            "error": "#D96B6B",
            "ok": "#7CB342",
        }
        color = colors.get(level, colors["info"])
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")
        print(message)

    # -------------------
    #   Drag & Drop
    # -------------------
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        webp_files = []
        for url in urls:
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".webp"):
                webp_files.append(file_path)
            else:
                print(f"Skipping non-WebP file: {file_path}")

        if not webp_files:
            return

        # Convert all dropped WebPs in an async worker
        # Typically, you might drop just 1 file, but let's handle multiples
        worker = PingPongWorker(file_list=webp_files, save_to_subfolder=False)
        worker.signals.progress.connect(self.on_worker_progress)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.finished.connect(self.on_worker_finished_single)

        # No progress bar for single-file? We'll still show minimal updates
        self.progress_bar.setRange(0, len(webp_files))
        self.progress_bar.setValue(0)

        self.threadpool.start(worker)

    # -------------------
    #   Folder Batch
    # -------------------
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)

    def process_folder(self):
        folder_path = self.folder_input.text().strip()
        if not folder_path or not os.path.isdir(folder_path):
            self.show_status("Invalid folder: Please select a valid folder path.", level="warn")
            return

        # Gather all .webp files
        all_files = sorted(os.listdir(folder_path))
        webp_files = [os.path.join(folder_path, f) for f in all_files if f.lower().endswith(".webp")]

        if not webp_files:
            self.show_status("No .webp files found in the selected folder.", level="warn")
            return

        # Prepare progress bar
        self.progress_bar.setRange(0, len(webp_files))
        self.progress_bar.setValue(0)

        # Create + start the worker
        save_to_subfolder = self.subfolder_checkbox.isChecked()
        worker = PingPongWorker(webp_files, save_to_subfolder)
        worker.signals.progress.connect(self.on_worker_progress)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.finished.connect(self.on_worker_finished_batch)

        self.threadpool.start(worker)
        self.show_status(f"Started batch processing of {len(webp_files)} files in '{folder_path}'...", level="info")

    # -------------------
    #   Worker Slots
    # -------------------
    def on_worker_progress(self, current, total, message):
        """Signal from the worker to indicate progress and log messages."""
        # Update progress bar and print the current message
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        print(message)

    def on_worker_error(self, error_msg):
        """Handle errors from the worker."""
        self.show_status(error_msg, level="error")

    def on_worker_finished_batch(self):
        """Called when the batch worker finishes all files."""
        self.show_status("Batch processing complete.", level="ok")
        self.progress_bar.setValue(self.progress_bar.maximum())

    def on_worker_finished_single(self):
        """Called when the worker finishes single-file or drag-drop job."""
        self.show_status("Single-file conversion(s) complete.", level="ok")
        self.progress_bar.setValue(self.progress_bar.maximum())


def main():
    app = QApplication(sys.argv)
    window = DragDropWebPConverter()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
