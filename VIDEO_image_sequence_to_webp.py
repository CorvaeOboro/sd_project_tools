"""
VIDEO image sequence to animated webp converter 

drag drop images and specify delay per frame , export to an animated webp a higher quality looping gif 

VERSION::20250913
"""

import sys
import os
from typing import List

import imageio
from PIL import Image

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QProgressBar, QFileDialog, QSpinBox,
    QCheckBox
)
from PyQt5.QtCore import (
    Qt, QThreadPool, QRunnable, pyqtSignal, QObject
)
from PyQt5.QtGui import QDragEnterEvent, QDropEvent


# ====================  Helper utilities =============================
VALID_IMG_EXT = (
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"
)


def natural_key(s: str):
    """Key function for natural file sorting (numbers in names).
    Example: img2 < img10 while still lexicographically reasonable.
    """
    import re
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def list_images_in_folder(folder: str) -> List[str]:
    if not os.path.isdir(folder):
        return []
    files = [os.path.join(folder, f) for f in os.listdir(folder)]
    imgs = [f for f in files if os.path.splitext(f)[1].lower() in VALID_IMG_EXT and os.path.isfile(f)]
    imgs.sort(key=lambda p: natural_key(os.path.basename(p)))
    return imgs


# ====================  Worker signal definitions =============================
class WorkerSignals(QObject):
    progress = pyqtSignal(int, int, str)  # current, total, message
    error = pyqtSignal(str)               # error text
    finished = pyqtSignal(str)            # output path on completion


# ====================  Worker that builds animated WebP =============================
class BuildWebPWorker(QRunnable):
    def __init__(self, image_paths: List[str], out_path: str, delay_ms: int, quality: int, lossless: bool):
        super().__init__()
        self.image_paths = image_paths
        self.out_path = out_path
        self.delay_ms = max(1, int(delay_ms))
        self.quality = max(1, min(100, int(quality)))
        self.lossless = bool(lossless)
        self.signals = WorkerSignals()

    def run(self):
        try:
            self._build_webp()
            self.signals.finished.emit(self.out_path)
        except Exception as e:
            self.signals.error.emit(str(e))

    def _build_webp(self):
        total = len(self.image_paths)
        if total == 0:
            raise ValueError("No images to process.")

        frames = []
        for i, p in enumerate(self.image_paths, start=1):
            self.signals.progress.emit(i, total, f"Reading {os.path.basename(p)} ({i}/{total})")
            img = Image.open(p).convert("RGBA")
            frames.append(img)

        durations = [self.delay_ms for _ in frames]

        # Prefer Pillow save for full control, fallback to imageio if needed
        out_dir = os.path.dirname(self.out_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Try Pillow first (generally better for animated webp control)
        try:
            frames[0].save(
                self.out_path,
                format="WEBP",
                save_all=True,
                append_images=frames[1:],
                loop=0,                    # infinite
                duration=durations,
                method=6,
                lossless=self.lossless,
                quality=self.quality,
            )
        except Exception:
            # Fallback to imageio if some Pillow builds lack expected args
            arrs = [imageio.v3.imread(p) for p in self.image_paths]
            try:
                imageio.mimwrite(
                    self.out_path,
                    arrs,
                    format='webp',
                    duration=[d/1000.0 for d in durations],  # seconds
                    loop=0,
                    lossless=self.lossless,
                    quality=self.quality,
                    method=6,
                )
            except TypeError:
                imageio.mimwrite(
                    self.out_path,
                    arrs,
                    format='webp',
                    duration=[d/1000.0 for d in durations],
                    loop=0,
                    lossless=self.lossless,
                    quality=self.quality,
                )


# ====================  The main GUI widget =============================
class ImageSequenceToWebP(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Sequence → Animated WebP")
        self.setAcceptDrops(True)
        self.resize(720, 360)

        self.setup_dark_theme()

        self.threadpool = QThreadPool()

        # --- Layout ---
        layout = QVBoxLayout(self)

        # Instructions label / drop target
        self.label = QLabel(
            "Drag & drop images or a folder here.\n"
            "You can also pick images via the 'Add Images' button.\n"
            "All frames will be sorted naturally and used in order."
        )
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFrameStyle(QLabel.StyledPanel | QLabel.Raised)
        self.label.setMinimumHeight(80)
        layout.addWidget(self.label)

        # Selected images summary
        self.summary_label = QLabel("No images selected.")
        layout.addWidget(self.summary_label)

        # Controls row
        controls = QHBoxLayout()

        self.btn_add = QPushButton("Add Images…")
        self.btn_add.setObjectName("addButton")
        self.btn_add.clicked.connect(self.add_images)
        controls.addWidget(self.btn_add)

        self.btn_add_folder = QPushButton("Add Folder…")
        self.btn_add_folder.setObjectName("addFolderButton")
        self.btn_add_folder.clicked.connect(self.add_folder)
        controls.addWidget(self.btn_add_folder)

        controls.addSpacing(12)

        # Delay per frame
        controls.addWidget(QLabel("Delay (ms) per frame:"))
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(1, 60000)
        self.spin_delay.setValue(100)
        controls.addWidget(self.spin_delay)

        controls.addSpacing(12)

        # Quality and lossless
        controls.addWidget(QLabel("Quality:"))
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(1, 100)
        self.spin_quality.setValue(100)
        controls.addWidget(self.spin_quality)

        self.chk_lossless = QCheckBox("Lossless")
        self.chk_lossless.setChecked(True)
        controls.addWidget(self.chk_lossless)

        layout.addLayout(controls)

        # Output row
        out_row = QHBoxLayout()
        self.out_path_edit = QLineEdit()
        self.out_path_edit.setPlaceholderText("Output .webp path (leave empty to choose on export)…")
        out_browse = QPushButton("Browse…")
        out_browse.setObjectName("outBrowseButton")
        out_browse.clicked.connect(self.browse_out)
        out_row.addWidget(self.out_path_edit)
        out_row.addWidget(out_browse)
        layout.addLayout(out_row)

        # Export + progress
        bottom = QHBoxLayout()
        self.btn_export = QPushButton("Build Animated WebP")
        self.btn_export.setObjectName("exportButton")
        self.btn_export.clicked.connect(self.export_webp)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        bottom.addWidget(self.btn_export)
        bottom.addWidget(self.progress_bar)
        layout.addLayout(bottom)

        # Inline status label for subtle feedback
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        # State
        self.image_paths: List[str] = []

    def setup_dark_theme(self):
        """Apply a consistent dark mode palette and muted, varied button colors."""
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
            QSpinBox {
                background-color: #1A1A1A;
                color: #E0E0E0;
                border: 1px solid #2C2C2C;
                border-radius: 6px;
                padding: 4px 6px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #222;
                border: 1px solid #2C2C2C;
                width: 16px;
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
            QPushButton#addButton {
                background-color: #2D3B45; /* muted blue-gray */
                border-color: #3E4F59;
            }
            QPushButton#addButton:hover { background-color: #334451; }
            QPushButton#addButton:pressed { background-color: #293842; }

            QPushButton#addFolderButton {
                background-color: #343145; /* muted indigo */
                border-color: #45415A;
            }
            QPushButton#addFolderButton:hover { background-color: #3A3750; }
            QPushButton#addFolderButton:pressed { background-color: #2E2B41; }

            QPushButton#outBrowseButton {
                background-color: #3A4336; /* muted olive */
                border-color: #4A5546;
            }
            QPushButton#outBrowseButton:hover { background-color: #414B3D; }
            QPushButton#outBrowseButton:pressed { background-color: #353F33; }

            QPushButton#exportButton {
                background-color: #3E2F2F; /* muted maroon */
                border-color: #4E3E3E;
            }
            QPushButton#exportButton:hover { background-color: #453535; }
            QPushButton#exportButton:pressed { background-color: #372A2A; }
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

    # ====================  Drag & Drop =============================
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        added = 0
        for url in urls:
            p = url.toLocalFile()
            if os.path.isdir(p):
                imgs = list_images_in_folder(p)
                self.image_paths.extend(imgs)
                added += len(imgs)
            elif os.path.isfile(p) and os.path.splitext(p)[1].lower() in VALID_IMG_EXT:
                self.image_paths.append(p)
                added += 1
            else:
                print(f"Skipping unsupported item: {p}")
        self._dedupe_and_sort()
        print(f"Added {added} items via drag & drop.")
        self._update_summary()

    # ====================  Buttons / Actions =============================
    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select images", "", 
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;All files (*.*)")
        if not files:
            return
        self.image_paths.extend(files)
        self._dedupe_and_sort()
        print(f"Added {len(files)} images.")
        self._update_summary()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder with images")
        if not folder:
            return
        imgs = list_images_in_folder(folder)
        self.image_paths.extend(imgs)
        self._dedupe_and_sort()
        print(f"Added {len(imgs)} images from folder.")
        self._update_summary()

    def browse_out(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save as", "", "WebP (*.webp)")
        if not path:
            return
        if not path.lower().endswith('.webp'):
            path += '.webp'
        self.out_path_edit.setText(path)

    def export_webp(self):
        if not self.image_paths:
            self.show_status("No images selected. Add files or drop a folder.", level="warn")
            return

        out_path = self.out_path_edit.text().strip()
        if not out_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Animated WebP", "", "WebP (*.webp)")
            if not path:
                return
            if not path.lower().endswith('.webp'):
                path += '.webp'
            out_path = path
            self.out_path_edit.setText(out_path)

        delay_ms = int(self.spin_delay.value())
        quality = int(self.spin_quality.value())
        lossless = bool(self.chk_lossless.isChecked())

        worker = BuildWebPWorker(self.image_paths, out_path, delay_ms, quality, lossless)
        worker.signals.progress.connect(self.on_worker_progress)
        worker.signals.error.connect(self.on_worker_error)
        worker.signals.finished.connect(self.on_worker_finished)

        # Prepare progress bar
        self.progress_bar.setRange(0, len(self.image_paths))
        self.progress_bar.setValue(0)

        self.show_status(f"Starting build: {len(self.image_paths)} frames → {out_path} | delay={delay_ms}ms quality={quality} lossless={lossless}", level="info")
        self.threadpool.start(worker)

    # ====================  Worker slots =============================
    def on_worker_progress(self, current: int, total: int, message: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        if message:
            self.show_status(message, level="info")

    def on_worker_error(self, error_msg: str):
        self.show_status(f"ERROR: {error_msg}", level="error")

    def on_worker_finished(self, out_path: str):
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.show_status(f"Done. Created animated WebP: {out_path}", level="ok")

    # ====================  Helpers =============================
    def _dedupe_and_sort(self):
        # Remove duplicates, keep insertion order then sort naturally by basename
        unique = []
        seen = set()
        for p in self.image_paths:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        unique.sort(key=lambda p: natural_key(os.path.basename(p)))
        self.image_paths = unique

    def _update_summary(self):
        n = len(self.image_paths)
        if n == 0:
            self.summary_label.setText("No images selected.")
            return
        preview = ", ".join(os.path.basename(p) for p in self.image_paths[:3])
        if n > 3:
            preview += f" … (+{n-3} more)"
        self.summary_label.setText(f"Selected {n} images. Order: {preview}")


def main():
    app = QApplication(sys.argv)
    window = ImageSequenceToWebP()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
