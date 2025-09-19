"""
VIDEO ADD AUDIO
quickly add audio to a video file using secondary audio or video 
requires ffmpeg and ffprobe
"""

import sys
import os
import subprocess
import argparse
from PyQt5 import QtWidgets, QtCore, QtGui

FFMPEG_PATH = r'C:\TOOLS\ffprobe.exe'
# ---------------------------------------------------------------
# Utility function to run ffmpeg command with logging

def run_ffmpeg(cmd, log_func=None):
    if log_func:
        log_func(f"Running: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
    if log_func:
        log_func(stdout)
        log_func(stderr)
    return process.returncode, stdout, stderr

# ---------------------------------------------------------------
# ffprobe helpers

def get_ffprobe_path(ffmpeg_path):
    # Replace ffmpeg.exe with ffprobe.exe if possible, else use default
    if ffmpeg_path and ffmpeg_path.lower().endswith('ffmpeg.exe'):
        ffprobe_path = ffmpeg_path[:-10] + 'ffprobe.exe'
        if os.path.isfile(ffprobe_path):
            return ffprobe_path
    return FFMPEG_PATH

def get_video_duration_ffprobe(video_path, ffprobe_path, log_func=None):
    cmd = [ffprobe_path, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
    try:
        if log_func:
            log_func(f"Running ffprobe for duration: {' '.join(cmd)}")
        output = subprocess.check_output(cmd, universal_newlines=True).strip()
        duration = float(output)
        if log_func:
            log_func(f"Video duration (ffprobe): {duration}s")
        return duration
    except Exception as e:
        if log_func:
            log_func(f"Failed to get video duration with ffprobe: {e}")
        return None

def get_video_codec_ffprobe(video_path, ffprobe_path, log_func=None):
    cmd = [ffprobe_path, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
    try:
        if log_func:
            log_func(f"Running ffprobe for codec: {' '.join(cmd)}")
        output = subprocess.check_output(cmd, universal_newlines=True).strip()
        if log_func:
            log_func(f"Video codec (ffprobe): {output}")
        return output.lower()
    except Exception as e:
        if log_func:
            log_func(f"Failed to get video codec with ffprobe: {e}")
        return None

# ---------------------------------------------------------------
# Core modular logic

def add_audio_to_video(base_video, audio_source, output_file, ffmpeg_path=None, ffprobe_path=None, log_func=print):
    if not ffmpeg_path:
        ffmpeg_path = r"C:/TOOLS/ffmpeg.exe"
    if not ffprobe_path:
        ffprobe_path = get_ffprobe_path(ffmpeg_path)
    # Check ffmpeg/ffprobe existence
    try:
        subprocess.check_output([ffmpeg_path, "-version"], stderr=subprocess.STDOUT)
        subprocess.check_output([ffprobe_path, "-version"], stderr=subprocess.STDOUT)
    except Exception as e:
        log_func("FFmpeg/ffprobe not found! Please specify the correct ffmpeg.exe path or add to your PATH.")
        log_func(f"FFmpeg/ffprobe not found or not working: {e}")
        return False
    if not base_video or not os.path.isfile(base_video):
        log_func("Please provide a valid base video file.")
        return False
    if not audio_source or not os.path.isfile(audio_source):
        log_func("Please provide a valid audio or video file.")
        return False
    if not output_file:
        base, ext = os.path.splitext(base_video)
        output_file = base + "_with_audio" + ext
        log_func(f"Output file not specified, using: {output_file}")
    # Get base video duration (ffprobe)
    duration = get_video_duration_ffprobe(base_video, ffprobe_path, log_func)
    if duration is None:
        log_func("Failed to get video duration (ffprobe). See log.")
        return False
    # Detect base video codec (ffprobe)
    codec = get_video_codec_ffprobe(base_video, ffprobe_path, log_func)
    # Map codec to ffmpeg encoder and best quality
    codec_map = {
        "h264": ("libx264", ["-crf", "16", "-preset", "slow"]),
        "hevc": ("libx265", ["-crf", "20", "-preset", "slow"]),
        "prores": ("prores_ks", ["-profile:v", "3"]),
        "mpeg4": ("mpeg4", ["-q:v", "2"]),
        "vp9": ("libvpx-vp9", ["-b:v", "0", "-crf", "30"]),
        # Add more as needed
    }
    if codec in codec_map:
        vcodec, vopts = codec_map[codec]
        log_func(f"Using video codec: {vcodec} with options: {vopts}")
    else:
        vcodec, vopts = "libx264", ["-crf", "16", "-preset", "slow"]
        log_func(f"Unknown codec, defaulting to libx264")
    # Compose ffmpeg command
    ffmpeg_cmd = [
        ffmpeg_path, "-y",
        "-i", base_video,
        "-i", audio_source,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-c:a", "aac",
    ]
    if vcodec == "copy":
        ffmpeg_cmd += ["-c:v", "copy"]
    else:
        ffmpeg_cmd += ["-c:v", vcodec] + vopts
    ffmpeg_cmd.append(output_file)
    log_func("Processing...")
    code, out, err = run_ffmpeg(ffmpeg_cmd, log_func)
    if code == 0:
        log_func(f"Done! Output: {output_file}")
        return True
    else:
        log_func(f"FFmpeg error: {err}")
        return False

# ---------------------------------------------------------------
# Main PyQt5 Application

class DropLineEdit(QtWidgets.QLineEdit):
    fileChanged = QtCore.pyqtSignal(str)
    def __init__(self, filetypes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.filetypes = filetypes
        self.setPlaceholderText(f"Drag and drop a {filetypes} file here or click to browse...")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and any([str(url.toLocalFile()).lower().endswith(self.filetypes) for url in urls]):
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = str(urls[0].toLocalFile())
            if file_path.lower().endswith(self.filetypes):
                self.setText(file_path)
                self.fileChanged.emit(file_path)

    def mousePressEvent(self, event):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, f"Select {self.filetypes} file", "", f"*{self.filetypes}")
        if fname:
            self.setText(fname)
            self.fileChanged.emit(fname)

class VideoAddAudioApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Add Audio")
        self.setMinimumWidth(600)
        self.setStyleSheet(self.dark_stylesheet())
        layout = QtWidgets.QVBoxLayout()

        self.base_video_edit = DropLineEdit((".mp4", ".mov", ".avi", ".mkv"))
        self.base_video_edit.fileChanged.connect(self.on_base_video_changed)
        self.audio_edit = DropLineEdit((".mp3", ".wav", ".aac", ".ogg", ".flac", ".m4a", ".mp4", ".mov", ".avi", ".mkv"))
        self.output_edit = QtWidgets.QLineEdit()
        self.output_edit.setPlaceholderText("Output file (auto-filled)")
        self.status_label = QtWidgets.QLabel("")
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.run_button = QtWidgets.QPushButton("Add Audio to Video")
        self.run_button.clicked.connect(self.process)

        # Add widgets to layout (ffmpeg at the bottom)
        layout.addWidget(QtWidgets.QLabel("Base Video:"))
        layout.addWidget(self.base_video_edit)
        layout.addWidget(QtWidgets.QLabel("Audio or Video Source:"))
        layout.addWidget(self.audio_edit)
        layout.addWidget(QtWidgets.QLabel("Output File:"))
        layout.addWidget(self.output_edit)
        layout.addWidget(self.run_button)
        layout.addWidget(self.status_label)
        layout.addWidget(QtWidgets.QLabel("Log:"))
        layout.addWidget(self.log_box)
        # FFmpeg input at the bottom
        self.ffmpeg_path_edit = QtWidgets.QLineEdit("C:/TOOLS/ffmpeg.exe")
        self.ffmpeg_path_edit.setPlaceholderText("Path to ffmpeg.exe (default: C:/TOOLS/ffmpeg.exe)")
        self.ffmpeg_path_browse = QtWidgets.QPushButton("Browse")
        self.ffmpeg_path_browse.clicked.connect(self.browse_ffmpeg_path)
        ffmpeg_path_layout = QtWidgets.QHBoxLayout()
        ffmpeg_path_layout.addWidget(self.ffmpeg_path_edit)
        ffmpeg_path_layout.addWidget(self.ffmpeg_path_browse)
        layout.addWidget(QtWidgets.QLabel("FFmpeg Executable:"))
        layout.addLayout(ffmpeg_path_layout)
        self.setLayout(layout)

    def log(self, msg):
        self.log_box.appendPlainText(str(msg))
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def browse_ffmpeg_path(self):
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select ffmpeg executable", "", "ffmpeg.exe (ffmpeg.exe);;All Files (*)")
        if fname:
            self.ffmpeg_path_edit.setText(fname)

    def on_base_video_changed(self, path):
        if path:
            base, ext = os.path.splitext(path)
            self.output_edit.setText(base + "_with_audio" + ext)

    def process(self):
        base_video = self.base_video_edit.text().strip()
        audio_source = self.audio_edit.text().strip()
        output_file = self.output_edit.text().strip()
        ffmpeg_path = self.ffmpeg_path_edit.text().strip() or "C:/TOOLS/ffmpeg.exe"
        ffprobe_path = get_ffprobe_path(ffmpeg_path)
        ok = add_audio_to_video(base_video, audio_source, output_file, ffmpeg_path, ffprobe_path, self.log)
        if ok:
            self.status_label.setText(f"Done! Output: {output_file}")
        else:
            self.status_label.setText("Failed. See log.")

    def dark_stylesheet(self):
        return """
        QWidget { background: #232629; color: #F0F0F0; }
        QLineEdit, QPlainTextEdit { background: #31363b; color: #F0F0F0; border: 1px solid #555; }
        QPushButton { background: #31363b; color: #F0F0F0; border: 1px solid #555; padding: 5px; }
        QLabel { color: #F0F0F0; }
        QScrollBar:vertical { background: #232629; width: 12px; }
        QScrollBar::handle:vertical { background: #555; min-height: 20px; }
        """

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add audio to a video file using ffmpeg/ffprobe. If no arguments are given, launches GUI.")
    parser.add_argument('--video', help='Input video file')
    parser.add_argument('--audio', help='Input audio (or video) file')
    parser.add_argument('--output', help='Output file (optional)')
    parser.add_argument('--ffmpeg', help='Path to ffmpeg.exe (optional)')
    parser.add_argument('--ffprobe', help='Path to ffprobe.exe (optional)')
    args = parser.parse_args()

    if args.video and args.audio:
        add_audio_to_video(
            base_video=args.video,
            audio_source=args.audio,
            output_file=args.output,
            ffmpeg_path=args.ffmpeg,
            ffprobe_path=args.ffprobe,
            log_func=print
        )
    else:
        app = QtWidgets.QApplication(sys.argv)
        window = VideoAddAudioApp()
        window.show()
        sys.exit(app.exec_())
