"""
IMAGE METADATA BAD WORD SCANNER
review image frontmatter data and workflows for badwords 
Batch and single-image tool for scanning Stable Diffusion image metadata for bad word list matches
using local bad_words.txt by default , set and edit your own good and bad words 

User Workflow Overview:
-----------------------
1. **Load Bad/Good Word Lists:**
   - On startup, the tool loads `bad_words.txt` (and optionally `good_words.txt`) from the script directory or user-specified locations.
   - The user can load or update these lists at any time via the UI buttons "Load Bad Words List" or "Load Good Words List".

2. **Add Words Manually:**
   - Users may manually add new bad or good words using the input fields and "Add Bad Word"/"Add Good Word" buttons. These are immediately saved to the appropriate file and update the in-memory lists.

3. **Load and Scan Files:**
   - Users load an image or JSON file using "Load File (Image/JSON)". The tool extracts metadata and scans for matches against the loaded bad/good word lists.
   - Scan results are displayed in three columns: Bad Words Found, Good Words Found, Unknown Words Found.

4. **Interact with Results:**
   - Users can double-click bad/unknown words in the lists to move them between categories, updating the relevant word list files and triggering a re-scan.
   - double clicking Unknown words added to Bad words list
   - Right-clicking Unknown words allows adding them to the good words list.

5. **Batch Operations:**
   - The tool supports batch scanning and cleaning of folders, using the current word lists for all operations.

6. **Saving and Cleaning:**
   - Cleaned JSON or images can be saved, with the option to overwrite or add a suffix, using the current state of the word lists.

All word list management (loading, saving, updating) is handled by the core logic for consistency, while the UI provides an interactive and immediate way to manage and update these lists and review scan results.

TODO: 
long good words should protect against small bad word removal 
"""
#//========================================================================================
import sys
import os
import re
from enum import Enum
from typing import Set, Tuple, Optional

from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QListWidget, QCheckBox,
    QMainWindow, QFileDialog, QTextEdit, QWidget, QSizePolicy
)
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt

import qdarkstyle
import json
from PIL import Image
from PIL.PngImagePlugin import PngInfo

try:
    from sd_parsers import parse_image
except ImportError:
    parse_image = None

class WordListType(Enum):
    """Enumeration for different types of word lists."""
    BAD_WORDS = "bad"
    GOOD_WORDS = "good"

#//========================================================================================

def debug_print(msg): #33
    print(f"[ImageMetadataScanner] {msg}")

class ImageMetadataScanner:
    """
    Core logic for extracting and parsing Stable Diffusion metadata from images, supporting
    Automatic1111, ComfyUI, and generic PNG/JPG workflows. Includes debug output.
    """
    def __init__(self, bad_words=None): #41
        self.bad_words = set(bad_words) if bad_words else set()

    def set_bad_words(self, bad_words): #44
        self.bad_words = set(bad_words)

    def extract_metadata_text(self, file_path): #47
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

    def find_badword_matches(self, text): #118
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

class BadWordScannerCore:
    """
    High-level core logic for scanning and cleaning images and JSON files for bad/good/unknown words.
    Handles word list management, batch processing, and delegates low-level metadata extraction to ImageMetadataScanner.
    """
    def __init__(self):
        self.scanner = ImageMetadataScanner()
        self.good_words = set()
        self.bad_words = set()
        self.last_scanned_file = None
        self.last_metadata = None
        self.last_badwords = None
        self.last_json_file = None
        self.last_json_data = None
        self.last_json_badwords = None
        self.last_json_badword_locations = None
        self.cleaned_json_data = None
        # File paths for word lists
        self.badword_file = None
        self.goodword_file = None
    
    def _get_word_list_properties(self, word_list_type: WordListType) -> Tuple[Set[str], str, str]:
        """
        Get the appropriate word set, file path attribute, and default filename for a word list type.
        Returns: (word_set, file_path_attr_name, default_filename)
        """
        if word_list_type == WordListType.BAD_WORDS:
            return self.bad_words, 'badword_file', 'bad_words.txt'
        elif word_list_type == WordListType.GOOD_WORDS:
            return self.good_words, 'goodword_file', 'good_words.txt'
        else:
            raise ValueError(f"Unknown word list type: {word_list_type}")
    
    def load_word_list_from_file(self, word_list_type: WordListType, file_path: Optional[str] = None) -> Tuple[Set[str], Optional[str]]:
        """
        Load words from a file for the specified word list type.
        Returns: (set of words, actual file path used)
        """
        word_set, file_attr_name, default_filename = self._get_word_list_properties(word_list_type)
        
        # Determine search paths
        paths = []
        if file_path:
            paths.append(file_path)
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            paths.append(os.path.join(script_dir, default_filename))
            paths.append(os.path.join(os.getcwd(), default_filename))
        
        # Try to load from each path
        for path in paths:
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        words = set(line.strip().lower() for line in f if line.strip())
                    
                    # Update the appropriate instance variables
                    if word_list_type == WordListType.BAD_WORDS:
                        self.bad_words = words
                        self.badword_file = path
                    else:
                        self.good_words = words
                        self.goodword_file = path
                    
                    return words, path
                except Exception as e:
                    print(f"[Core] Error loading {word_list_type.value} words from {path}: {e}")
                    continue
        
        # No file found, reset to empty
        if word_list_type == WordListType.BAD_WORDS:
            self.bad_words = set()
            self.badword_file = None
        else:
            self.good_words = set()
            self.goodword_file = None
        
        return set(), None
    
    def add_word_to_list_file(self, word: str, word_list_type: WordListType) -> Tuple[bool, str]:
        """
        Add a word to the specified word list file and update the in-memory set.
        Returns: (success, message)
        """
        word = word.strip().lower()
        if not word:
            return False, "No word provided."
        
        word_set, file_attr_name, default_filename = self._get_word_list_properties(word_list_type)
        file_path = getattr(self, file_attr_name)
        
        # Check if word already exists
        if word in word_set:
            return False, f"'{word}' is already in {word_list_type.value} word list."
        
        # Ensure file path exists
        if not file_path:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, default_filename)
            setattr(self, file_attr_name, file_path)
            
            # Create the file if it doesn't exist
            if not os.path.isfile(file_path):
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        pass
                except Exception as e:
                    return False, f"Failed to create {word_list_type.value} words file: {e}"
        
        # Add word to file
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(word + "\n")
            
            # Reload the word list to update in-memory set
            self.load_word_list_from_file(word_list_type, file_path)
            return True, f"Added '{word}' to {word_list_type.value} word list."
            
        except Exception as e:
            return False, f"Failed to add '{word}' to {word_list_type.value} words: {e}"
    
    def remove_word_from_list_file(self, word: str, word_list_type: WordListType) -> Tuple[bool, str]:
        """
        Remove a word from the specified word list file and update the in-memory set.
        Returns: (success, message)
        """
        word = word.strip().lower()
        if not word:
            return False, "No word provided."
        
        word_set, file_attr_name, default_filename = self._get_word_list_properties(word_list_type)
        file_path = getattr(self, file_attr_name)
        
        if not file_path or not os.path.isfile(file_path):
            return False, f"No {word_list_type.value} word list file loaded."
        
        try:
            # Read all lines except the word to remove
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.rstrip() for line in f if line.strip().lower() != word]
            
            # Write back the filtered lines
            with open(file_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
            
            # Reload the word list to update in-memory set
            self.load_word_list_from_file(word_list_type, file_path)
            return True, f"Removed '{word}' from {word_list_type.value} word list."
            
        except Exception as e:
            return False, f"Failed to remove '{word}' from {word_list_type.value} words: {e}"
    
    def move_word_between_lists(self, word: str, from_list: WordListType, to_list: WordListType) -> Tuple[bool, str]:
        """
        Move a word from one word list to another, updating both files.
        Returns: (success, message)
        """
        # Remove from source list
        success_remove, msg_remove = self.remove_word_from_list_file(word, from_list)
        if not success_remove:
            return False, msg_remove
        
        # Add to destination list
        success_add, msg_add = self.add_word_to_list_file(word, to_list)
        if success_add:
            return True, f"Moved '{word}' from {from_list.value} to {to_list.value} word list."
        else:
            # Try to restore to original list if adding failed
            self.add_word_to_list_file(word, from_list)
            return False, f"Failed to move '{word}': {msg_add}"
    
    def scan_image(self, file_path):
        """
        Scan an image file for metadata and find bad, good, and unknown words.
        Returns a dict with keys: metadata_text, badwords, goodwords, unknownwords.
        """
        metadata_text = self.scanner.extract_metadata_text(file_path)
        if not metadata_text:
            return {'metadata_text': None, 'badwords': [], 'goodwords': [], 'unknownwords': []}
        import re
        # For unknown word calculation, replace newlines with spaces and underscores with spaces
        cleaned_text = metadata_text.replace('\n', ' ').replace('_', ' ')
        words_in_text = set(re.findall(r'\b\w+\b', cleaned_text.lower()))
        badwords_found = set()
        goodwords_found = set()
        for word in self.bad_words:
            if word in words_in_text:
                badwords_found.add(word)
        for word in self.good_words:
            if word in words_in_text:
                goodwords_found.add(word)
        # Unknown words: exclude any that are purely numeric
        unknownwords_found = set(w for w in (words_in_text - self.bad_words - self.good_words) if not w.isnumeric())
        return {
            'metadata_text': metadata_text,
            'badwords': sorted(badwords_found),
            'goodwords': sorted(goodwords_found),
            'unknownwords': sorted(unknownwords_found),
        }

    def remove_bad_words_from_file(self, file_path):
        """
        Remove bad words from a file (image or JSON). Returns (removed_count, message).
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.json':
            cleaned_data, removed = self.clean_json_file(file_path)
            msg = f"[Core] Cleaned JSON: {file_path}, removed {removed} bad words."
            return removed, msg
        else:
            cleaned, removed = self.remove_bad_words_from_image(file_path)
            msg = f"[Core] Cleaned image: {file_path}, removed {removed} bad words."
            return removed, msg

    def scan_json(self, file_path):
        """
        Scan a JSON file for bad words. Returns (badwords, badword_locations).
        """
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        self.last_json_file = file_path
        self.last_json_data = json_data
        badwords, badword_locations = self.find_words_in_json_data(json_data, WordListType.BAD_WORDS, track_locations=True)
        self.last_json_badwords = badwords
        self.last_json_badword_locations = badword_locations
        return badwords, badword_locations

    def find_words_in_json_data(self, json_data, word_list_type: WordListType, track_locations: bool = False):
        """
        Find words of the specified type in JSON data.
        
        Args:
            json_data: The JSON data to search through
            word_list_type: Type of words to search for (good or bad)
            track_locations: Whether to track word locations by key
            
        Returns:
            If track_locations=False: List of (key, value, word) tuples
            If track_locations=True: Tuple of (word_list, locations_dict)
        """
        word_set, _, _ = self._get_word_list_properties(word_list_type)
        
        found_words = []
        word_locations = {} if track_locations else None
        
        for key, value in json_data.items():
            if isinstance(value, str):
                for word in word_set:
                    if word in value.lower():
                        found_words.append((key, value, word))
                        
                        # Track locations if requested
                        if track_locations:
                            if key not in word_locations:
                                word_locations[key] = []
                            word_locations[key].append(word)
        
        if track_locations:
            return found_words, word_locations
        else:
            return found_words
    
    def save_cleaned_json(self, file_path):
        """
        Save the cleaned JSON data to a file. Returns True if successful, False otherwise.
        """
        if self.cleaned_json_data:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.cleaned_json_data, f, indent=4)
            return True
        return False

    def clean_json(self, json_data):
        """
        Remove all bad words from JSON data. Returns the cleaned data.
        """
        cleaned_data = json_data.copy()
        for k, v in json_data.items():
            if isinstance(v, str):
                for word in self.bad_words:
                    v = v.replace(word, "")
                cleaned_data[k] = v
        self.cleaned_json_data = cleaned_data
        return cleaned_data

    def remove_bad_words_from_image(self, file_path):
        """
        Remove bad words from image metadata and save the cleaned image.
        Returns (success: bool, removed_count: int).
        """
        try:
            # Extract original metadata
            original_metadata = self.scanner.extract_metadata_text(file_path)
            if not original_metadata:
                return True, 0  # No metadata to clean
            
            # Count and remove bad words from metadata
            cleaned_metadata = original_metadata
            removed_count = 0
            # Sort bad words by length (longest first) to avoid partial matches interfering with longer words
            sorted_bad_words = sorted(self.bad_words, key=len, reverse=True)
            for bad_word in sorted_bad_words:
                if bad_word in cleaned_metadata.lower():
                    # Count occurrences (case-insensitive)
                    import re
                    matches = re.findall(re.escape(bad_word), cleaned_metadata, re.IGNORECASE)
                    removed_count += len(matches)
                    # Remove all occurrences (case-insensitive)
                    cleaned_metadata = re.sub(re.escape(bad_word), "", cleaned_metadata, flags=re.IGNORECASE)
            
            if removed_count == 0:
                return True, 0  # No bad words found
            
            # Clean up extra whitespace
            cleaned_metadata = re.sub(r'\s+', ' ', cleaned_metadata).strip()
            
            # Save the cleaned image with new metadata
            img = Image.open(file_path)
            
            # Create backup filename
            base_name, ext = os.path.splitext(file_path)
            backup_path = f"{base_name}_backup{ext}"
            
            # Save backup of original
            img.save(backup_path)
            print(f"[Core] Created backup: {backup_path}")
            
            # For PNG files, update the metadata
            if ext.lower() == '.png':
                # Create new PngInfo with cleaned metadata
                pnginfo = PngInfo()
                
                # Process ALL text metadata fields, not just specific keys
                # This ensures we clean bad words from any text field while preserving image data
                try:
                    original_info = img.text or {}
                    total_field_removals = 0
                    
                    for key, value in original_info.items():
                        # Only process string values (text metadata)
                        if isinstance(value, str):
                            cleaned_value = value
                            field_removals = 0
                            
                            # Remove bad words from this field
                            # Sort bad words by length (longest first) to avoid partial matches interfering with longer words
                            sorted_bad_words = sorted(self.bad_words, key=len, reverse=True)
                            for bad_word in sorted_bad_words:
                                if bad_word in cleaned_value.lower():
                                    # Create a word boundary pattern that includes underscores and other separators
                                    # This pattern matches the bad word when it's:
                                    # - At the start/end of string
                                    # - Surrounded by spaces, underscores, hyphens, or other non-alphanumeric chars
                                    word_pattern = r'(?<![a-zA-Z0-9])' + re.escape(bad_word) + r'(?![a-zA-Z0-9])'
                                    
                                    # Count occurrences in this field
                                    matches = re.findall(word_pattern, cleaned_value, re.IGNORECASE)
                                    field_removals += len(matches)
                                    # Remove all occurrences (case-insensitive)
                                    cleaned_value = re.sub(word_pattern, "", cleaned_value, flags=re.IGNORECASE)
                            
                            # Clean up extra whitespace in this field
                            cleaned_value = re.sub(r'\s+', ' ', cleaned_value).strip()
                            
                            # Add the cleaned field to the new metadata
                            pnginfo.add_text(key, cleaned_value)
                            
                            if field_removals > 0:
                                total_field_removals += field_removals
                                print(f"[Core] Cleaned {field_removals} bad word(s) from metadata field '{key}'")
                        else:
                            # Preserve non-string metadata as-is (shouldn't contain bad words anyway)
                            pnginfo.add_text(key, str(value))
                    
                    print(f"[Core] Total bad words removed from all metadata fields: {total_field_removals}")
                    
                except Exception as e:
                    print(f"[Core] Warning: Could not process all metadata fields: {e}")
                    # Fallback: just add cleaned parameters if available
                    if 'parameters' in (img.text or {}):
                        pnginfo.add_text("parameters", cleaned_metadata)
                    else:
                        print(f"[Core] No fallback metadata to preserve")
                
                # Save the cleaned image
                img.save(file_path, pnginfo=pnginfo)
                print(f"[Core] Saved cleaned image with updated metadata")
            else:
                # For non-PNG files, we can't easily modify metadata, so just report what would be removed
                print(f"[Core] Warning: Cannot modify metadata for {ext} files. Backup created but original unchanged.")
            
            return True, removed_count
            
        except Exception as e:
            print(f"[Core] Error cleaning image {file_path}: {e}")
            return False, 0

class BadWordScannerUI(QWidget):
    """
    BadWordScannerUI handles the UI for the BadWordScannerCore.
    """
    def __init__(self):
        super().__init__()
        print("[DEBUG] BadWordScannerUI __init__ starting...")
        self.setWindowTitle("Stable Diffusion Metadata Bad Word Scanner")
        self.setAcceptDrops(True)
        self.core = BadWordScannerCore()
        print("[DEBUG] BadWordScannerCore instantiated.")
        self.badword_label = QLabel("No bad word list loaded")
        self.badword_label.setStyleSheet("color: #ccc;")
        self.goodword_label = QLabel("No good word list loaded")
        self.goodword_label.setStyleSheet("color: #ccc;")

        # UI Elements
        self.UI_init_ui()
        print("[DEBUG] UI_init_ui() called.")

        # Always load bad words from default locations on startup
        bad_words, bad_path = self.core.load_word_list_from_file(WordListType.BAD_WORDS)
        #print(f"[DEBUG] UI __init__: bad_words={bad_words}, bad_path={bad_path}")
        if bad_words:
            #print(f"[UI] Loaded {len(bad_words)} bad words from: {bad_path}")
            print(f"[UI] Loaded {len(bad_words)} bad words ")
        else:
            print(f"[UI] No bad_words.txt found in script or working directory!")

        # Always load good words from default locations on startup
        good_words, good_path = self.core.load_word_list_from_file(WordListType.GOOD_WORDS)
        self.goodword_file = good_path
        if self.core.good_words:
            print(f"[UI] Loaded {len(self.core.good_words)} good words from: {good_path}")
        else:
            print(f"[UI] No good_words.txt found in script or working directory!")
        self.goodword_label.setText(
            f"Loaded: {len(self.core.good_words)} good words from {os.path.basename(good_path) if good_path else 'N/A'}"
        )
        # Now that widgets exist, update UI lists/labels
        self.UI_update_word_lists()
        print("[DEBUG] UI_update_word_lists() called.")
        self.UI_update_badword_label()
        print("[DEBUG] UI_update_badword_label() called.")
        print("[DEBUG] UI __init__ complete, window should be visible.")

    def UI_init_ui(self): #
        print("[DEBUG] UI_init_ui() starting...")
        layout = QVBoxLayout()

        # --- Drag-and-drop instructions ---
        drag_label = QLabel("Drag and drop an image file anywhere in this window to scan its metadata.")
        drag_label.setStyleSheet("color: #9cf; font-size: 12pt; font-weight: bold; padding: 8px;")
        layout.addWidget(drag_label)
        print("[DEBUG] Drag-and-drop instructions added.")

        # --- First row: load/scan/batch/clean buttons ---
        top_btn_layout = QHBoxLayout()
        self.load_file_button = QPushButton("Load File (Image/JSON)")
        self.load_file_button.clicked.connect(self.UI_load_file_dialog)
        top_btn_layout.addWidget(self.load_file_button)
        self.json_scan_button = QPushButton("Scan JSON File")
        self.json_scan_button.clicked.connect(self.UI_scan_json_dialog)
        top_btn_layout.addWidget(self.json_scan_button)
        self.batch_scan_button = QPushButton("Batch Scan Folder")
        self.batch_scan_button.clicked.connect(self.UI_batch_scan_folder_dialog)
        self.batch_scan_button.setStyleSheet("background-color: #624e6e; color: #fff; border-radius: 6px; padding: 6px; font-weight: bold;")
        top_btn_layout.addWidget(self.batch_scan_button)
        self.batch_clean_button = QPushButton("Batch Clean Folder")
        self.batch_clean_button.clicked.connect(self.UI_batch_clean_folder_dialog)
        self.batch_clean_button.setStyleSheet("background-color: #624e6e; color: #fff; border-radius: 6px; padding: 6px; font-weight: bold;")
        top_btn_layout.addWidget(self.batch_clean_button)
        layout.addLayout(top_btn_layout)

        # --- Second row: two columns, bad word controls (left), good word controls (right) ---
        bw_gw_columns = QHBoxLayout()

        # Bad word controls (left)
        bad_col = QVBoxLayout()
        self.load_badwords_button = QPushButton("Load Bad Words List")
        self.load_badwords_button.clicked.connect(self.UI_load_badword_list_dialog)
        bad_col.addWidget(self.load_badwords_button)
        bad_col.addWidget(self.badword_label)
        self.add_word_input = QLineEdit()
        self.add_word_input.setPlaceholderText("Add new bad word...")
        bad_col.addWidget(self.add_word_input)
        add_word_btn = QPushButton("Add Bad Word")
        add_word_btn.clicked.connect(self.on_click_add_bad_word)
        bad_col.addWidget(add_word_btn)
        self.remove_button = QPushButton("Remove Bad Words from Last Image")
        self.remove_button.clicked.connect(self.on_click_remove_bad_words_from_last_image)
        self.remove_button.setStyleSheet("background-color: #4e6e4e; color: #fff; border-radius: 6px; padding: 6px; font-weight: bold;")
        bad_col.addWidget(self.remove_button)
        bw_gw_columns.addLayout(bad_col)

        # Good word controls (right)
        good_col = QVBoxLayout()
        self.load_goodwords_button = QPushButton("Load Good Words List")
        self.load_goodwords_button.clicked.connect(self.UI_load_goodword_list_dialog)
        good_col.addWidget(self.load_goodwords_button)
        good_col.addWidget(self.goodword_label)
        self.add_goodword_input = QLineEdit()
        self.add_goodword_input.setPlaceholderText("Add new good word...")
        good_col.addWidget(self.add_goodword_input)
        add_goodword_btn = QPushButton("Add Good Word")
        add_goodword_btn.clicked.connect(self.on_click_add_good_word)
        good_col.addWidget(add_goodword_btn)
        self.json_clean_button = QPushButton("Save Cleaned JSON")
        self.json_clean_button.clicked.connect(self.UI_save_cleaned_json)
        self.json_clean_button.setEnabled(False)
        self.json_clean_button.setStyleSheet("background-color: #3b5876; color: #fff; border-radius: 6px; padding: 6px; font-weight: bold;")
        good_col.addWidget(self.json_clean_button)
        bw_gw_columns.addLayout(good_col)

        layout.addLayout(bw_gw_columns)

        # --- Word Lists (Bad/Good/Unknown) ---
        word_lists_hbox = QHBoxLayout()
        # Bad words
        bad_vbox = QVBoxLayout()
        bad_label = QLabel("Bad Words Found")
        bad_label.setStyleSheet("color: #c33; font-weight: bold;")
        bad_vbox.addWidget(bad_label)
        self.badwords_list = QListWidget()
        self.badwords_list.setStyleSheet("color: #c33; background-color: #222;")
        self.badwords_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.badwords_list.itemDoubleClicked.connect(self.UI_on_bad_word_double_clicked)
        bad_vbox.addWidget(self.badwords_list)
        word_lists_hbox.addLayout(bad_vbox, 1)
        # Good words
        good_vbox = QVBoxLayout()
        good_label = QLabel("Good Words Found")
        good_label.setStyleSheet("color: #3c3; font-weight: bold;")
        good_vbox.addWidget(good_label)
        self.goodword_count_label = QLabel()
        self.goodword_count_label.setStyleSheet("color: #9f6; font-size: 10pt;")
        good_vbox.addWidget(self.goodword_count_label)
        self.goodwords_list = QListWidget()
        self.goodwords_list.setStyleSheet("color: #3c3; background-color: #222;")
        self.goodwords_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        good_vbox.addWidget(self.goodwords_list)
        word_lists_hbox.addLayout(good_vbox, 1)
        # Unknown words
        unknown_vbox = QVBoxLayout()
        unknown_label = QLabel("Unknown Words Found")
        unknown_label.setStyleSheet("color: #cc3; font-weight: bold;")
        unknown_vbox.addWidget(unknown_label)
        self.unknownwords_list = QListWidget()
        self.unknownwords_list.setStyleSheet("color: #cc3; background-color: #222;")
        self.unknownwords_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.unknownwords_list.itemDoubleClicked.connect(self.UI_on_unknown_word_double_clicked)
        self.unknownwords_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.unknownwords_list.customContextMenuRequested.connect(self.UI_on_unknown_word_right_click)
        unknown_vbox.addWidget(self.unknownwords_list)
        word_lists_hbox.addLayout(unknown_vbox, 1)
        layout.addLayout(word_lists_hbox, 1)

        # Bad/good word status


        # Add current file label for scan status
        self.current_file_label = QLabel("No file scanned yet")
        self.current_file_label.setStyleSheet("color: #ccc;")
        layout.addWidget(self.current_file_label)
        # Ensure widgets/layouts are visible
        self.setLayout(layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and url.toLocalFile().lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
                    file_path = url.toLocalFile()
                    print(f"[UI] Dropped image file: {file_path}")
                    self.UI_scan_image(file_path)
                    return
        event.ignore()

    def UI_scan_image(self, file_path):
        print(f"[UI] Scanning image: {file_path}")
        self.core.last_scanned_file = file_path
        scan_result = self.core.scan_image(file_path)
        self.last_metadata = scan_result['metadata_text']
        found_badwords = scan_result['badwords']
        found_goodwords = scan_result['goodwords']
        found_unknownwords = scan_result['unknownwords']
        if not scan_result['metadata_text']:
            self.current_file_label.setText(f"Scanned: {os.path.basename(file_path)} (no metadata found)")
            print(f"[UI] No metadata found in image: {file_path}")
            self.UI_update_word_lists([], [], [])
            return
        self.current_file_label.setText(f"Scanned: {os.path.basename(file_path)} (found {len(found_badwords)} bad, {len(found_goodwords)} good, {len(found_unknownwords)} unknown)")
        print(f"[UI] Scanned image: {file_path}, found {len(found_badwords)} bad, {len(found_goodwords)} good, {len(found_unknownwords)} unknown words.")
        self.UI_update_word_lists(found_badwords, found_goodwords, found_unknownwords)

    def UI_scan_json(self, file_path):
        """UI method to scan a JSON file and update the interface with results."""
        print(f"[UI] Scanning JSON file: {file_path}")
        self.core.last_scanned_file = file_path
        try:
            # Load and analyze the JSON file
            with open(file_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
            
            # Extract all text from JSON for word analysis
            all_text_parts = []
            total_words_in_json = 0
            
            def extract_text_from_json(obj, path=""):
                nonlocal total_words_in_json
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        extract_text_from_json(value, f"{path}.{key}" if path else key)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        extract_text_from_json(item, f"{path}[{i}]")
                elif isinstance(obj, str):
                    all_text_parts.append(obj)
                    # Count words in this text
                    import re
                    words = re.findall(r'\b\w+\b', obj.lower())
                    total_words_in_json += len(words)
            
            extract_text_from_json(json_data)
            
            # Combine all text for analysis
            combined_text = ' '.join(all_text_parts)
            cleaned_text = combined_text.replace('\n', ' ').replace('_', ' ')
            
            # Find all unique words in the JSON
            import re
            words_in_json = set(re.findall(r'\b\w+\b', cleaned_text.lower()))
            
            # Find bad words
            found_badwords = set()
            for word in self.core.bad_words:
                if word in words_in_json:
                    found_badwords.add(word)
            
            # Find good words
            found_goodwords = set()
            for word in self.core.good_words:
                if word in words_in_json:
                    found_goodwords.add(word)
            
            # Find unknown words (exclude numeric words)
            found_unknownwords = set(w for w in (words_in_json - self.core.bad_words - self.core.good_words) if not w.isnumeric())
            
            # Update UI with comprehensive results
            unique_words_count = len(words_in_json)
            self.current_file_label.setText(
                f"Scanned: {os.path.basename(file_path)} "
                f"(Total: {total_words_in_json} words, {unique_words_count} unique | "
                f"Bad: {len(found_badwords)}, Good: {len(found_goodwords)}, Unknown: {len(found_unknownwords)})"
            )
            
            print(f"[UI] JSON scan complete: {file_path}")
            print(f"[UI] Total words in JSON: {total_words_in_json}, Unique words: {unique_words_count}")
            print(f"[UI] Found - Bad: {len(found_badwords)}, Good: {len(found_goodwords)}, Unknown: {len(found_unknownwords)}")
            
            self.UI_update_word_lists(sorted(found_badwords), sorted(found_goodwords), sorted(found_unknownwords))
            
        except Exception as e:
            print(f"[UI] Error scanning JSON file {file_path}: {e}")
            self.current_file_label.setText(f"Error scanning: {os.path.basename(file_path)}")
            self.UI_update_word_lists(set(), set(), set())

    def UI_scan_json_dialog(self):
        """Open file dialog to select and scan a JSON file."""
        file_name, _ = QFileDialog.getOpenFileName(self, "Open JSON File", "", "JSON Files (*.json)")
        if file_name:
            self.UI_scan_json(file_name)

    def UI_batch_clean_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Batch Clean")
        if folder:
            results = self.core.batch_clean_folder(folder)
            print(f"[UI] Batch cleaned folder: {folder}. Cleaned {len(results)} files.")
        else:
            print("[UI] No folder selected for batch clean.")

    def UI_batch_scan_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Batch Scan")
        if folder:
            results = self.core.batch_scan_folder(folder)
            print(f"[UI] Batch scanned folder: {folder}. Found bad words in {len(results)} files.")
        else:
            print("[UI] No folder selected for batch scan.")

    def UI_save_cleaned_json(self):
        if not hasattr(self, 'last_scanned_file') or not self.last_scanned_file:
            print("[UI] No file has been scanned yet.")
            return
        file_path = self.last_scanned_file
        ext = os.path.splitext(file_path)[1].lower()
        if ext != '.json':
            print(f"[UI] Last scanned file is not a JSON: {file_path}")
            return
        cleaned_data, removed = self.core.clean_json_file(file_path)
        if cleaned_data is not None:
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Cleaned JSON", file_path, "JSON Files (*.json)")
            if save_path:
                with open(save_path, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
                print(f"[UI] Saved cleaned JSON to: {save_path} (removed {removed} bad words)")
        else:
            print(f"[UI] Cleaning failed for: {file_path}")

    def on_click_remove_bad_words_from_last_image(self):
        if not hasattr(self.core, 'last_scanned_file') or not self.core.last_scanned_file:
            print("[UI] No file has been scanned yet.")
            return
        file_path = self.core.last_scanned_file
        removed, msg = self.core.remove_bad_words_from_file(file_path)
        print(msg)
        # Re-scan the file to update the UI with the cleaned results
        self.UI_scan_image(file_path)

    def on_click_add_good_word(self):
        word = self.add_goodword_input.text().strip().lower()
        if word:
            success, message = self.core.add_word_to_list_file(word, WordListType.GOOD_WORDS)
            if success:
                self.add_goodword_input.clear()
                self.UI_update_word_lists()
                print(f"[UI] {message}")
            else:
                print(f"[UI] {message}")
        else:
            print("[UI] No word entered to add to good word list.")

    def on_click_add_bad_word(self):
        word = self.add_word_input.text().strip().lower()
        if word:
            success, message = self.core.add_word_to_list_file(word, WordListType.BAD_WORDS)
            if success:
                self.add_word_input.clear()
                self.UI_update_word_lists()
                self.UI_update_badword_label()
                print(f"[UI] {message}")
            else:
                print(f"[UI] {message}")
        else:
            print("[UI] No word entered to add to bad word list.")

    def UI_scan_json_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open JSON File", "", "JSON Files (*.json)")
        if file_name:
            badwords, badword_locations = self.core.scan_json(file_name)
            self.current_file_label.setText(f"Scanned: {os.path.basename(file_name)} (JSON)")
            self.last_scanned_file = file_name
            self.last_badwords = badwords
            self.UI_update_word_lists([w for w,_,_ in badwords])
            print(f"[UI] Scanned JSON: {file_name}, found {len(badwords)} bad words.")

    def UI_update_badword_label(self):
        file_path = getattr(self.core, 'badword_file', None)
        count = len(self.core.bad_words) if hasattr(self.core, 'bad_words') else 0
        if file_path:
            self.badword_label.setText(f"Loaded: {count} bad words from {os.path.basename(file_path)}")
        else:
            self.badword_label.setText(f"No bad word list loaded")
        print(f"[UI] Bad words file label updated: {file_path} ({count} words)")

    def UI_rescan_last_file(self):
        """Helper method to rescan the last scanned file with the appropriate method based on file type."""
        if not self.core.last_scanned_file:
            return
        
        file_path = self.core.last_scanned_file
        if file_path.lower().endswith('.json'):
            self.UI_scan_json(file_path)
        else:
            self.UI_scan_image(file_path)

    def UI_on_unknown_word_double_clicked(self, item):
        word = item.text().strip().lower()
        success, message = self.core.add_word_to_list_file(word, WordListType.BAD_WORDS)
        print(f"[UI] {message}")
        # Rescan last file for immediate feedback
        self.UI_rescan_last_file()

    def UI_on_bad_word_double_clicked(self, item):
        # Move word from bad to good, update files, and re-scan current file
        word = item.text().split(' (count:')[0].strip().lower()  # Remove count if present
        success, message = self.core.move_word_between_lists(word, WordListType.BAD_WORDS, WordListType.GOOD_WORDS)
        print(f"[UI] {message}")
        # Rescan last file for immediate feedback
        self.UI_rescan_last_file()

    def UI_on_unknown_word_right_click(self, pos):
        item = self.unknownwords_list.itemAt(pos)
        if item:
            word = item.text().strip().lower()
            success, message = self.core.add_word_to_list_file(word, WordListType.GOOD_WORDS)
            print(f"[UI] {message}")
            # Rescan last file for immediate feedback
            self.UI_rescan_last_file()

    def UI_save_good_word_to_file(self, word): #
        file_path = getattr(self, 'goodword_file', None)
        if not file_path:
            # Default to good_words.txt in script dir
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "good_words.txt")
            self.goodword_file = file_path
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(word + "\n")
            print(f"[UI] Added '{word}' to good words and saved to: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"[UI] Failed to save good word to file: {e}")

    def UI_update_word_lists(self, found_badwords=None, found_goodwords=None, found_unknownwords=None):
        # Repopulate only the UI lists, not the underlying sets
        self.badwords_list.clear()
        self.goodwords_list.clear()
        self.unknownwords_list.clear()
        if found_badwords:
            for word in sorted(found_badwords):
                self.badwords_list.addItem(word)
        if found_goodwords:
            for word in sorted(found_goodwords):
                self.goodwords_list.addItem(word)
        if found_unknownwords:
            for word in sorted(found_unknownwords):
                self.unknownwords_list.addItem(word)
        self.UI_update_goodword_count_label()

    def UI_update_goodword_count_label(self): #
        count = len(self.core.good_words) if hasattr(self.core, 'good_words') else 0
        file_path = getattr(self, 'goodword_file', None)
        if not file_path:
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "good_words.txt")
        self.goodword_label.setText(f"Loaded: {count} good words from {os.path.basename(file_path)}")
        print(f"[UI] Good words file label updated: {file_path} ({count} words)")

    def UI_reload_good_words_from_file(self):
        good_words, file_path = self.core.reload_good_words_from_file()
        self.good_words = good_words
        self.goodword_file = file_path
        self.goodword_label.setText(f"Loaded: {len(self.good_words)} good words from {os.path.basename(file_path)}")
        print(f"[UI] Good words file label updated: {file_path} ({len(self.good_words)} words)")
        self.UI_update_word_lists()

    def UI_load_file_dialog(self): #
        file_name, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Images/JSON (*.jpg *.jpeg *.bmp *.png *.webp *.json)")
        if file_name:
            if file_name.lower().endswith((".jpg", ".jpeg", ".bmp", ".png", ".webp")):
                self.scan_image(file_name)
            elif file_name.lower().endswith(".json"):
                self.UI_scan_json(file_name)

    def UI_load_badword_list_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Bad Word List", "", "Text Files (*.txt)")
        if file_name:
            bad_words, file_path = self.core.load_word_list_from_file(WordListType.BAD_WORDS, file_name)
            self.badword_file = file_path
            self.UI_update_word_lists()
            self.UI_update_badword_label()
            print(f"[UI] Loaded bad words from: {file_path} ({len(self.core.bad_words)} words)")

    def UI_load_goodword_list_dialog(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Good Word List", "", "Text Files (*.txt)")
        if file_name:
            good_words, file_path = self.core.load_word_list_from_file(WordListType.GOOD_WORDS, file_name)
            self.good_words = good_words
            self.goodword_file = file_path
            self.goodword_label.setText(f"Loaded: {os.path.basename(file_path)} ({len(good_words)} good words)")
            self.UI_update_word_lists()
            print(f"[UI] Loaded good words from: {file_path} ({len(good_words)} words)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    window = BadWordScannerUI()
    window.show()
    sys.exit(app.exec_())
