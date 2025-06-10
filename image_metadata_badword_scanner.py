"""
IMAGE METADATA BAD WORD SCANNER
review image data 
Batch and single-image tool for scanning Stable Diffusion image metadata for bad word list matches
uses bad_words.txt by default
"""

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QListWidget, QCheckBox,
    QMainWindow, QFileDialog, QTextEdit, QWidget
)
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt

import qdarkstyle
import json
from PIL import Image
try:
    from sd_parsers import parse_image
except ImportError:
    parse_image = None

def debug_print(msg):
    print(f"[ImageMetadataScanner] {msg}")

class ImageMetadataScanner:
    """
    Core logic for extracting and parsing Stable Diffusion metadata from images, supporting
    Automatic1111, ComfyUI, and generic PNG/JPG workflows. Includes debug output.
    """
    def __init__(self, bad_words=None):
        self.bad_words = set(bad_words) if bad_words else set()

    def set_bad_words(self, bad_words):
        self.bad_words = set(bad_words)

    def extract_metadata_text(self, file_path):
        debug_print(f"Opening file: {file_path}")
        ext = os.path.splitext(file_path)[1].lower()
        all_text = []
        try:
            if parse_image:
                debug_print("Trying sd-parsers parse_image...")
                result = parse_image(file_path)
                if result:
                    for k, v in result.items():
                        debug_print(f"sd-parsers: {k} -> {str(v)[:60]}...")
                        all_text.append(f"[sd-parsers:{k}]: {v}")
        except Exception as e:
            debug_print(f"sd-parsers failed: {e}")
        # Fallback: Pillow direct read
        try:
            img = Image.open(file_path)
            if ext == '.png':
                debug_print("Trying PNG text chunks...")
                text_chunks = getattr(img, 'text', {})
                for k, v in text_chunks.items():
                    debug_print(f"PNG text chunk: {k} -> {v[:60]}...")
                    all_text.append(f"[{k}]: {v}")
                for k, v in img.info.items():
                    if k not in text_chunks:
                        debug_print(f"PNG info field: {k} -> {str(v)[:60]}...")
                        all_text.append(f"[info:{k}]: {v}")
                exif = img.info.get('exif')
                if exif:
                    debug_print("EXIF data found in PNG.")
                    all_text.append(f"[EXIF]: {exif}")
            elif ext in ['.jpg', '.jpeg', '.bmp']:
                debug_print("Trying JPEG/BMP info...")
                for k, v in img.info.items():
                    debug_print(f"JPEG/BMP info field: {k} -> {str(v)[:60]}...")
                    if isinstance(v, bytes):
                        try:
                            v = v.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
                    all_text.append(f"[info:{k}]: {v}")
                exif = img.info.get('exif')
                if exif:
                    debug_print("EXIF data found in JPEG/BMP.")
                    all_text.append(f"[EXIF]: {exif}")
            elif ext == '.webp':
                debug_print("Trying WEBP info...")
                for k, v in img.info.items():
                    debug_print(f"WEBP info field: {k} -> {str(v)[:60]}...")
                    if isinstance(v, bytes):
                        try:
                            v = v.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
                    all_text.append(f"[info:{k}]: {v}")
                xmp = img.info.get('xmp')
                if xmp:
                    debug_print("XMP data found in WEBP.")
                    if isinstance(xmp, bytes):
                        try:
                            xmp = xmp.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
                    all_text.append(f"[XMP]: {xmp}")
        except Exception as e:
            debug_print(f"Pillow fallback failed: {e}")
        if not all_text:
            debug_print("No metadata found.")
            return ''
        return '\n'.join(all_text)

    def find_badword_matches(self, text):
        if not self.bad_words or not text:
            return []
        text_lower = text.lower()
        matches = []
        for word in self.bad_words:
            if word in text_lower:
                # Find all occurrences and their positions
                positions = []
                start = 0
                while True:
                    idx = text_lower.find(word, start)
                    if idx == -1:
                        break
                    positions.append(idx)
                    start = idx + 1
                debug_print(f"Bad word '{word}' found {len(positions)} times at positions: {positions}")
                matches.append((word, positions))
        debug_print(f"Bad word matches: {[w for w, _ in matches]}")
        return matches


class BadWordScanner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stable Diffusion Metadata Bad Word Scanner")
        self.setAcceptDrops(True)
        self.scanner = ImageMetadataScanner()
        self.last_scanned_file = None
        self.last_metadata = None
        self.last_badwords = None

        # UI Elements
        self._init_ui()

        self.load_bad_words()

    def _init_ui(self):
        layout = QVBoxLayout()

        self.drop_label = QLabel("<font size=6 color=white>DRAG & DROP IMAGE HERE</font>")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setFixedHeight(200)
        self.drop_label.setStyleSheet("border: 2px dashed #aaa; text-align: center; background-color: #222;")
        layout.addWidget(self.drop_label)

        # Main horizontal area: left = preview/metadata, right = badwords
        main_hbox = QHBoxLayout()

        # Left column: image and metadata
        left_vbox = QVBoxLayout()
        self.image_preview = QLabel()
        self.image_preview.setFixedHeight(180)
        left_vbox.addWidget(self.image_preview)
        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        left_vbox.addWidget(self.metadata_text)
        main_hbox.addLayout(left_vbox, 2)

        # Right column: bad words label (vertically stretchable)
        right_vbox = QVBoxLayout()
        self.badwords_label = QLabel()
        self.badwords_label.setStyleSheet("color: red; font-size: 20px;")
        self.badwords_label.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.badwords_label.setWordWrap(True)
        right_vbox.addWidget(self.badwords_label, stretch=1)
        main_hbox.addLayout(right_vbox, 1)

        layout.addLayout(main_hbox)

        self.add_word_input = QLineEdit()
        self.add_word_input.setPlaceholderText("Add new bad word...")
        add_word_btn = QPushButton("Add Bad Word")
        add_word_btn.clicked.connect(self.add_bad_word)
        layout.addWidget(self.add_word_input)
        layout.addWidget(add_word_btn)

        # Bad word list status label
        self.badword_label = QLabel("No bad word list loaded")
        self.badword_label.setStyleSheet("color: #ccc;")
        layout.addWidget(self.badword_label)

        # Checkbox for output mode
        self.suffix_checkbox = QCheckBox("Add '_cleaned' suffix to output file (otherwise overwrite original)")
        self.suffix_checkbox.setChecked(True)
        layout.addWidget(self.suffix_checkbox)

        # Results area (for batch)
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("color: #eee; background-color: #222;")
        layout.addWidget(self.results_list)

        # Remove Bad Words Button
        self.remove_button = QPushButton("Remove Bad Words from Last Image")
        self.remove_button.clicked.connect(self.remove_bad_words_from_last_image)
        layout.addWidget(self.remove_button)

        # Batch scan/clean buttons
        batch_btn_layout = QHBoxLayout()
        self.batch_scan_button = QPushButton("Batch Scan Folder")
        self.batch_scan_button.clicked.connect(self.batch_scan_folder_dialog)
        batch_btn_layout.addWidget(self.batch_scan_button)
        self.batch_clean_button = QPushButton("Batch Clean Folder")
        self.batch_clean_button.clicked.connect(self.batch_clean_folder_dialog)
        batch_btn_layout.addWidget(self.batch_clean_button)
        layout.addLayout(batch_btn_layout)

        self.setLayout(layout)

    def load_bad_words(self):
        # Always load from default bad_words.txt in the same directory as this script
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bad_words.txt")
        if os.path.isfile(default_path):
            with open(default_path, "r", encoding="utf-8") as f:
                bad_words = set(line.strip().lower() for line in f if line.strip())
            self.scanner.set_bad_words(bad_words)
            self.badword_label.setText(f"Loaded: bad_words.txt ({len(bad_words)} words)")
            print(f"[UI] Loaded bad word list from default location: {default_path} with {len(bad_words)} words.")
        else:
            self.badword_label.setText("No bad word list loaded")
            print("[UI] No bad_words.txt found in default location.")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        file_path = event.mimeData().urls()[0].toLocalFile()
        if file_path.lower().endswith((".jpg", ".jpeg", ".bmp", ".png", ".webp")):
            self.scan_image(file_path)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.scan_folder(folder)

    def load_badword_list(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Bad Word List", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, "r", encoding="utf-8") as f:
                bad_words = set(line.strip().lower() for line in f if line.strip())
            self.scanner.set_bad_words(bad_words)
            self.badword_label.setText(f"Loaded: {os.path.basename(file_name)} ({len(bad_words)} words)")
            print(f"[UI] Loaded bad word list: {file_name} with {len(bad_words)} words.")
        else:
            self.badword_label.setText("No bad word list loaded")

    def load_default_badword_list(self):
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bad_words.txt")
        if os.path.isfile(default_path):
            with open(default_path, "r", encoding="utf-8") as f:
                bad_words = set(line.strip().lower() for line in f if line.strip())
            self.scanner.set_bad_words(bad_words)
            self.badword_label.setText(f"Loaded: bad_words.txt ({len(bad_words)} words)")
            print(f"[UI] Loaded default bad_words.txt with {len(bad_words)} words.")
        else:
            self.badword_label.setText("No bad word list loaded")
            print("[UI] No default bad_words.txt found.")

    def add_bad_word(self):
        word = self.add_word_input.text().strip().lower()
        if word:
            self.scanner.bad_words.add(word)
            self.add_word_input.clear()
            self.badword_label.setText(f"Added: {word} (Total: {len(self.scanner.bad_words)})")
            print(f"[UI] Added bad word: {word}")

    def scan_folder(self, folder):
        self.results_list.clear()
        image_files = [os.path.join(folder, f) for f in os.listdir(folder)
                       if f.lower().endswith((".jpg", ".jpeg", ".bmp", ".png", ".webp"))]
        if not image_files:
            self.results_list.addItem("No image files found in folder.")
            return
        print(f"[UI] Scanning folder: {folder} with {len(image_files)} images.")
        for img_path in image_files:
            self.scan_image(img_path, batch=True)

    def batch_clean_folder(self, folder):
        self.results_list.clear()
        image_files = [os.path.join(folder, f) for f in os.listdir(folder)
                       if f.lower().endswith((".jpg", ".jpeg", ".bmp", ".png", ".webp"))]
        if not image_files:
            self.results_list.addItem("No image files found in folder.")
            return
        for file_path in image_files:
            print(f"[BATCH CLEAN] Cleaning: {file_path}")
            self.last_scanned_file = file_path
            self.remove_bad_words_from_last_image()

    def batch_scan_folder(self, folder):
        self.results_list.clear()
        image_files = [os.path.join(folder, f) for f in os.listdir(folder)
                       if f.lower().endswith((".jpg", ".jpeg", ".bmp", ".png", ".webp"))]
        if not image_files:
            self.results_list.addItem("No image files found in folder.")
            return
        for file_path in image_files:
            self.scan_image(file_path, batch=True)

    def batch_scan_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.batch_scan_folder(folder)

    def batch_clean_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.batch_clean_folder(folder)

    def scan_image(self, file_path, batch=False):
        print(f"[UI] Scanning image: {file_path}")
        meta_text = self.scanner.extract_metadata_text(file_path)
        # Show image in preview
        if os.path.isfile(file_path):
            pixmap = QPixmap(file_path)
            self.drop_label.setPixmap(pixmap.scaled(self.drop_label.width(), self.drop_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # Show metadata
        self.metadata_text.setPlainText(meta_text or "<No metadata found>")
        # Show bad words in big red label with details (word and count only)
        matches = self.scanner.find_badword_matches(meta_text)
        if matches:
            badword_details = []
            for word, positions in matches:
                detail = f"{word} (count: {len(positions)})"
                badword_details.append(detail)
            self.badwords_label.setText("Bad Words:\n" + "\n".join(badword_details))
        else:
            self.badwords_label.setText("")
        # Results area for batch or single
        if not meta_text:
            if not batch:
                self.results_list.addItem(f"{os.path.basename(file_path)}: No metadata found.")
            print(f"[UI] No metadata found for {file_path}")
            self.last_scanned_file = file_path if not batch else self.last_scanned_file
            self.last_metadata = meta_text
            self.last_badwords = matches
            return
        if matches:
            for word, positions in matches:
                self.results_list.addItem(f"{os.path.basename(file_path)}: '{word}' found {len(positions)} times")
            print(f"[UI] Found bad words in {file_path}: {[(w, len(p)) for w, p in matches]}")
            # Also append details to metadata area
            self.metadata_text.append("\n--- Bad Word Occurrences ---")
            for word, positions in matches:
                self.metadata_text.append(f"'{word}' found {len(positions)} times")
        elif not batch:
            self.results_list.addItem(f"{os.path.basename(file_path)}: No bad words found.")
            print(f"[UI] No bad words found in {file_path}")
        # Track last scanned file and metadata for cleaning
        if not batch:
            self.last_scanned_file = file_path
            self.last_metadata = meta_text
            self.last_badwords = matches

    def remove_bad_words_from_last_image(self):
        file_path = self.last_scanned_file
        if not file_path:
            msg = "No image has been scanned yet."
            print(f"[CLEAN] {msg}")
            self.results_list.addItem(msg)
            return
        ext = os.path.splitext(file_path)[1].lower()
        meta_text = self.scanner.extract_metadata_text(file_path)
        if not meta_text:
            msg = "No metadata found in image."
            print(f"[CLEAN] {msg}")
            self.results_list.addItem(msg)
            return
        matches = self.scanner.find_badword_matches(meta_text)
        if not matches:
            msg = "No bad words found in the last scanned image."
            print(f"[CLEAN] {msg}")
            self.results_list.addItem(msg)
            return
        # Remove all bad words (case-insensitive, all instances) from every text-based metadata field
        import re
        try:
            if ext == ".png":
                img = Image.open(file_path)
                from PIL.PngImagePlugin import PngInfo
                pnginfo = PngInfo()
                text_chunks = getattr(img, 'text', {})
                cleaned_fields = {}
                # Clean all text chunks
                for k, v in text_chunks.items():
                    orig_v = v
                    cleaned_v = v
                    for word, _ in matches:
                        pattern = re.compile(re.escape(word), re.IGNORECASE)
                        cleaned_v, count = pattern.subn("", cleaned_v)
                        if count > 0:
                            print(f"[CLEAN][PNG] Field '{k}': Removed '{word}' ({count} instances)")
                    cleaned_fields[k] = cleaned_v
                    pnginfo.add_text(k, cleaned_v)
                # Clean all extra info fields (if string type)
                for k, v in img.info.items():
                    if k not in cleaned_fields and isinstance(v, str):
                        orig_v = v
                        cleaned_v = v
                        for word, _ in matches:
                            pattern = re.compile(re.escape(word), re.IGNORECASE)
                            cleaned_v, count = pattern.subn("", cleaned_v)
                            if count > 0:
                                print(f"[CLEAN][PNG-info] Field '{k}': Removed '{word}' ({count} instances)")
                        pnginfo.add_text(k, cleaned_v)
                # Determine output path based on checkbox
                if hasattr(self, 'suffix_checkbox') and not self.suffix_checkbox.isChecked():
                    out_path = file_path
                else:
                    out_path = os.path.splitext(file_path)[0] + "_cleaned.png"
                img.save(out_path, "PNG", pnginfo=pnginfo)
                msg = f"Bad words removed from all metadata fields and saved as: {out_path}"
                print(f"[CLEAN] {msg}")
                self.results_list.addItem(msg)
            elif ext in ['.jpg', '.jpeg', '.bmp']:
                img = Image.open(file_path)
                info = img.info.copy()
                # Clean all string/bytes fields in info
                for k, v in info.items():
                    if isinstance(v, (str, bytes)):
                        if isinstance(v, bytes):
                            try:
                                v = v.decode('utf-8', errors='ignore')
                            except Exception:
                                continue
                        orig_v = v
                        cleaned_v = v
                        for word, _ in matches:
                            pattern = re.compile(re.escape(word), re.IGNORECASE)
                            cleaned_v, count = pattern.subn("", cleaned_v)
                            if count > 0:
                                print(f"[CLEAN][JPEG-info] Field '{k}': Removed '{word}' ({count} instances)")
                        info[k] = cleaned_v.encode('utf-8')
                # Determine output path based on checkbox
                if hasattr(self, 'suffix_checkbox') and not self.suffix_checkbox.isChecked():
                    out_path = file_path
                else:
                    out_path = os.path.splitext(file_path)[0] + "_cleaned.jpg"
                img.save(out_path, "JPEG", **info)
                msg = f"Bad words removed from all metadata fields and saved as: {out_path}"
                print(f"[CLEAN] {msg}")
                self.results_list.addItem(msg)
            elif ext == ".webp":
                img = Image.open(file_path)
                info = img.info.copy()
                # Clean all string/bytes fields in info (including XMP if present)
                for k, v in info.items():
                    if isinstance(v, (str, bytes)):
                        if isinstance(v, bytes):
                            try:
                                v = v.decode('utf-8', errors='ignore')
                            except Exception:
                                continue
                        orig_v = v
                        cleaned_v = v
                        for word, _ in matches:
                            pattern = re.compile(re.escape(word), re.IGNORECASE)
                            cleaned_v, count = pattern.subn("", cleaned_v)
                            if count > 0:
                                print(f"[CLEAN][WEBP-info] Field '{k}': Removed '{word}' ({count} instances)")
                        info[k] = cleaned_v.encode('utf-8')
                # Determine output path based on checkbox
                if hasattr(self, 'suffix_checkbox') and not self.suffix_checkbox.isChecked():
                    out_path = file_path
                else:
                    out_path = os.path.splitext(file_path)[0] + "_cleaned.webp"
                img.save(out_path, "WEBP", **info)
                msg = f"Bad words removed from all metadata fields and saved as: {out_path}"
                print(f"[CLEAN] {msg}")
                self.results_list.addItem(msg)
            else:
                msg = "Only PNG, JPEG/BMP, and WEBP are supported for cleaning."
                print(f"[CLEAN] {msg}")
                self.results_list.addItem(msg)
        except Exception as e:
            msg = f"Failed to clean and save image: {e}"
            print(f"[CLEAN] {msg}")
            self.results_list.addItem(msg)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    window = BadWordScanner()
    window.show()
    sys.exit(app.exec_())
