#// TEXT PROMPT HELPER - image metadata parser with tools to analyze , combine , balance , and simplify prompts 
#// drag an image into working area , use "copy to work area" button to copy prompt , drag in other image and repeat 
#// BALANCE = working area text is merged , duplicate prompts removed , prompt strength is balanced , duplicate loras removed
#// SIMPLIFY = removes all strength modifiers on prompt groups , removes group parenthesis 
#// LORA SCALE = relatively scale the strength of all loras to fit a maximum and multiply by scaler   
#//=================================================================================
# UI
import PyQt5.QtWidgets 
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QTextEdit, QAction, QFileDialog, QPushButton
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QCursor
from PyQt5.QtCore import Qt
import qdarkstyle
# IMAGE LIBRARIES
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS
# UTIL
import sys
import pathlib
import re
from collections import defaultdict
import os
import win32clipboard
import pyperclip
import chardet
from pathlib import Path

ERROR_LOG_FILE = "text_prompt_helper_error_log.txt"
ROUNDING_DECIMAL_PLACE = 2
REPLACE_UNDERSCORES = True

class MainWindow(QMainWindow):
    #//=======================================================================================
    #// UI
    def __init__(self):
        super().__init__()

        self.setWindowTitle("IMAGE PROMPT UTILITIES")
        self.setGeometry(200, 30, 1100, 1000)

        #// IMAGE AREA
        self.label = QLabel(self)
        self.label.setGeometry(10, 20, 490, 490)
        self.display_img_label1 = QLabel(self)
        self.display_img_label1.setText("<font size=6 color=black>DRAG DROP IMAGE</font>")
        self.display_img_label1.move(100, 100)  
        self.display_img_label1.setWordWrap(True)
        self.display_img_label1.adjustSize() 
        self.display_img_label1.resize(200, 300)
        self.display_img_filepath = QTextEdit(self)
        self.display_img_filepath.setGeometry(10, 500, 490, 100)

        #// TEXT METADATA INFO
        self.textbox = QTextEdit(self)
        self.textbox.setGeometry(520, 20, 270, 300)
        self.textbox.setAcceptDrops(False)
        self.textbox.setReadOnly(True)
        self.textbox.setStyleSheet("color: rgb(100, 100, 100);")
        #// TEXT METADATA INFO NEGATIVE PROMPT
        self.textbox_neg = QTextEdit(self)
        self.textbox_neg.setGeometry(520, 320, 270, 200)
        self.textbox_neg.setAcceptDrops(False)
        self.textbox_neg.setReadOnly(True)
        self.textbox_neg.setStyleSheet("color: rgb(100, 100, 100);")

        #// EDITABLE TEXT AREA PROMPT
        self.textbox_prompt = QTextEdit(self)
        self.textbox_prompt.setGeometry(10, 560, 760, 100)
        self.textbox_prompt.setStyleSheet("color: rgb(100, 100, 200);")
        self.label1 = QLabel(self)
        self.label1.setText("<font size=4 color=black>PROMPT EDIT</font>")
        self.label1.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.label1.move(10, 545)
        self.label1.resize(500, 20)  
        #self.label1.adjustSize() 
        #// EDITABLE TEXT OUPUT AREA
        self.textbox_prompt_output = QTextEdit(self)
        self.textbox_prompt_output.setGeometry(10, 670, 760, 100)
        self.textbox_prompt_output.setStyleSheet("color: rgb(100, 200, 100);")
        self.label2 = QLabel(self)
        self.label2.setText("<font size=4 color=black>PROMPT OUTPUT</font>")
        self.label2.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.label2.move(10, 655)  
        self.label2.resize(500, 20) 
        #self.label2.adjustSize() 

        #// EDITABLE TEXT AREA PROMPT
        self.textbox_prompt_neg = QTextEdit(self)
        self.textbox_prompt_neg.setGeometry(10, 780, 760, 100)
        self.textbox_prompt_neg.setStyleSheet("color: rgb(100, 100, 200);")
        self.label1_neg = QLabel(self)
        self.label1_neg.setText("<font size=4 color=black>NEGATIVE EDIT</font>")
        self.label1_neg.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.label1_neg.move(10, 765)
        self.label1_neg.resize(500, 20)  
        #self.label1_neg.adjustSize() 
        #// EDITABLE TEXT OUPUT AREA
        self.textbox_prompt_output_neg = QTextEdit(self)
        self.textbox_prompt_output_neg.setGeometry(10, 890, 760, 100)
        self.textbox_prompt_output_neg.setStyleSheet("color: rgb(100, 200, 100);")
        self.label2_neg = QLabel(self)
        self.label2_neg.setText("<font size=4 color=black>NEGATIVE OUTPUT</font>")
        self.label2_neg.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.label2_neg.move(10, 875)  
        self.label2_neg.resize(500, 20) 
        #self.label2_neg.adjustSize() 

        #// BUTTONS
        self.convert_button = QPushButton('CONVERT', self)
        self.convert_button.resize(100,25)
        self.convert_button.move(10, 520)        
        self.convert_button.clicked.connect(self.CONVERT_jpg_to_png)

        self.simple_button = QPushButton('SIMPLE', self)
        self.simple_button.resize(100,25)
        self.simple_button.move(250, 520)        
        self.simple_button.clicked.connect(self.button_simplify)

        self.balance_button = QPushButton('BALANCE', self)
        self.balance_button.resize(100,25)
        self.balance_button.move(450, 520)        
        self.balance_button.clicked.connect(self.button_balance)

        self.convert_button = QPushButton('COPY TO AREA', self)
        self.convert_button.resize(100,25)
        self.convert_button.move(700, 520)        
        self.convert_button.clicked.connect(self.COPY_TO_AREA)

        # BUTTONS SPECIFIC TO AREA
        self.copy_button = QPushButton('COPY', self)
        self.copy_button .resize(50,20)
        self.copy_button .move(770, 680)     
        self.copy_button.clicked.connect(self.copyToClipboard) 

        self.clear_button = QPushButton('CLEAR', self)
        self.clear_button .resize(50,20)
        self.clear_button .move(770, 710)     
        self.clear_button.clicked.connect(self.CLEAR) 
        # BUTTONS SPECIFIC TO NEGATIVE AREA
        self.copy_button_neg = QPushButton('COPY', self)
        self.copy_button_neg .resize(50,20)
        self.copy_button_neg .move(770, 900)     
        self.copy_button_neg.clicked.connect(self.copyToClipboard_neg) 

        self.clear_button_neg = QPushButton('CLEAR', self)
        self.clear_button_neg .resize(50,20)
        self.clear_button_neg .move(770, 930)     
        self.clear_button_neg.clicked.connect(self.CLEAR) 

        # MENU FUNCTONS
        open_file_action = QAction("Open", self)
        open_file_action.setShortcut("Ctrl+O")
        open_file_action.triggered.connect(self.open_file)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(open_file_action)

        #// LORA SCALING EDITABLE TEXT AREA PROMPT
        self.textbox_lora_scale = QTextEdit(self)
        self.textbox_lora_scale.setGeometry(1000, 780, 50, 20)
        self.textbox_lora_scale.setStyleSheet("color: rgb(100, 100, 200);")
        self.label1_lora_scale = QLabel(self)
        self.label1_lora_scale.setText("<font size=4 color=black>LORA SCALE</font>")
        self.label1_lora_scale.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.label1_lora_scale.move(1000, 765)
        self.label1_lora_scale.resize(500, 20)  
        # MULTIPLY
        self.convert_button = QPushButton('MULTIPLY LORA', self)
        self.convert_button.resize(100,25)
        self.convert_button.move(1000, 700)        
        self.convert_button.clicked.connect(self.button_LORA_MULTIPLY)
        # TOTAL 
        self.textbox_lora_total = QTextEdit(self)
        self.textbox_lora_total.setGeometry(900, 780, 50, 20)
        self.textbox_lora_total.setStyleSheet("color: rgb(100, 100, 200);")
        self.label1_lora_total = QLabel(self)
        self.label1_lora_total.setText("<font size=4 color=black>LORA SCALE</font>")
        self.label1_lora_total.setStyleSheet("background-color: rgba(255, 255, 255, 0);")
        self.label1_lora_total.move(900, 770)
        self.label1_lora_total.resize(500, 20)  

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        file_path = event.mimeData().urls()[0].toLocalFile()
        if file_path.endswith(('.jpg', '.jpeg', '.bmp', '.png')):
            self.load_image(file_path)

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.jpg *.png *.jpeg *.bmp)")
        if file_name:
            self.load_image(file_name)

    #//================================================= LOAD IMAGE
    def load_image(self, file_path):
        self._display_image(file_path)
        self._handle_image_metadata(file_path)

    def _display_image(self, file_path):
        pixmap = QPixmap(file_path)
        self.label.setPixmap(pixmap)
        self.label.setScaledContents(True)
        self.display_img_label1.setHidden(True)
        self.display_img_filepath.setPlainText(file_path)

    def _handle_image_metadata(self, file_path):
        file_suffix = Path(file_path).suffix
        if file_suffix == ".jpg":
            self._handle_jpg_metadata(file_path)
        elif file_suffix == ".png":
            self._handle_png_metadata(file_path)

    def _handle_jpg_metadata(self, file_path):
        try:
            image = Image.open(file_path)
            exif_data = image._getexif()
            exif_text = self._format_exif_data(exif_data)
            self.textbox.setPlainText(exif_text if exif_text else "No EXIF data found")
        except Exception as e:
            print(f"Error reading JPG metadata: {e}")
            self.textbox.setPlainText("Error reading metadata")

    def _format_exif_data(self, exif_data):
        if not exif_data:
            return None
        exif_text = ""
        for tag_id, value in exif_data.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if isinstance(value, bytes):
                value = value.decode("utf-8", "ignore")
            exif_text += f"{tag}: {value}\n"
        return exif_text

    def _handle_png_metadata(self, file_path):
        try:
            png_info = self._extract_png_metadata(file_path)
            self.textbox.setPlainText(png_info if png_info else "No PNG metadata found")
            png_info_neg = self._extract_png_metadata_neg(file_path)
            self.textbox_neg.setPlainText(png_info_neg if png_info_neg else "No PNG negative metadata found")
        except Exception as e:
            print(f"Error reading PNG metadata: {e}")
            self.textbox.setPlainText("Error reading metadata")

    def _extract_png_metadata(self, file_path):
        with open(file_path, 'rb') as file:
            raw_data = file.read(10000)
            detected = chardet.detect(raw_data)
            png_raw = raw_data.decode(detected['encoding'], errors='ignore')
            regex = r"tparameters([\S\s]*)Negative prompt:"
            matches = re.search(regex, png_raw, re.DOTALL)
            return matches.group(1) if matches else None

    def _extract_png_metadata_neg(self, file_path):
        with open(file_path, 'rb') as file:
            raw_data = file.read(10000)
            png_raw = raw_data.decode('UTF-8', errors='ignore')
            regex_neg = r"Negative prompt:([\S\s]*)Steps: "
            matches_neg = re.search(regex_neg, png_raw, re.DOTALL)
            return matches_neg.group(1) if matches_neg else None

    #//=======================================================================================
    #// SIMPLE UI FUNCTIONS

    def COPY_TO_AREA(self):
        print("COPY_TO_AREA")
        #prompt
        existing_text = str(self.textbox_prompt.toPlainText())
        prompt_text = str(self.textbox.toPlainText())
        combined_text = existing_text + " , " + prompt_text
        self.textbox_prompt.setPlainText(combined_text)
        #negative
        existing_text_neg = str(self.textbox_prompt_neg.toPlainText())
        prompt_text_neg = str(self.textbox_neg.toPlainText())
        combined_text_neg = existing_text_neg + " , " + prompt_text_neg
        self.textbox_prompt_neg.setPlainText(combined_text_neg)
    
    def CLEAR(self):
        print("clear")
    
    def CONVERT_jpg_to_png(self):
        current_image = self.display_img_filepath.toPlainText()
        if os.path.isfile(current_image):
            file_path = str(current_image)

            # Open the JPEG image and extract the EXIF data
            jpeg_img = Image.open(file_path)
            exif_data = jpeg_img.getexif()

            # Extract the description from the EXIF data, if it exists
            description = exif_data.get(270)

            if description is not None:
                # Open the previous PNG image and extract the PNGInfo
                path_file = pathlib.Path(file_path)
                parent_folder = path_file.parents[0]
                filename_only = pathlib.Path(file_path).stem

                png_info = {'Description': description}

                # Convert the JPEG image to PNG with the updated PNGInfo
                png_img = jpeg_img.convert('RGBA')
                final_output_png_path = parent_folder + "/" + filename_only + ".png"
                png_img.save(final_output_png_path, format='PNG', pnginfo=png_info)

    def button_simplify(self):
        prompt_text = str(self.textbox_prompt.toPlainText())    
        prompt_simplified = self.simplify_prompt(prompt_text)
        print("BUTTON RECEIVED === " + prompt_simplified)
        self.textbox_prompt_output.setPlainText(prompt_simplified)

    def button_balance(self):
        prompt_text = str(self.textbox_prompt.toPlainText())    
        prompt_simplified = self.balance_text_prompt(prompt_text)
        print("BUTTON RECEIVED === " + prompt_simplified)
        self.textbox_prompt_output.setPlainText(prompt_simplified)
    
    def button_LORA_MULTIPLY(self):
        prompt_text = str(self.textbox_prompt.toPlainText())   
        lora_multiplier = str(self.textbox_lora_scale.toPlainText())    
        prompt_lora_scaled = self.scale_lora_only(prompt_text,lora_multiplier)
        print("BUTTON LORA_MULTIPLY === " + prompt_lora_scaled)
        self.textbox_prompt_output.setPlainText(prompt_lora_scaled)

    def copyToClipboard(self):
        # Retrieve the text from the textbox
        text = self.textbox_prompt_output.toPlainText()
        print("CLIPBOARD TEXT = " + str(text))
        if text is not None:
            self.addToClipBoard(str(text))

    def copyToClipboard_neg(self):
        # Retrieve the text from the textbox
        text = self.textbox_prompt_output_neg.toPlainText()
        print("CLIPBOARD TEXT = " + str(text))
        if text is not None:
            self.addToClipBoard(str(text))

    def addToClipBoard(self,text):
        double_quote = '''"'''
        clean_text = text.replace('\x00','')
        clean_text = clean_text.replace('\n','')
        clean_text = clean_text.rstrip()
        print(clean_text)
        pyperclip.copy(str(clean_text))

    #//=======================================================================================
    #// PROMPT MANIP FUNCTIONS

    def _write_error_log(self, message):
        with open(ERROR_LOG_FILE, "a") as file:
            file.write(message + "\n")

    def _additive_lora_dictionary(self, lora_matches):
        lora_dict = defaultdict(float)
        for match in lora_matches:
            try:
                words = match.split(':')
                key = f"{words[0].strip()}:{words[1].strip()}"
                value = float(words[2])
                lora_dict[key] += value
            except Exception as e:
                self._write_error_log(f"Error in _additive_lora_dictionary: {e}, match: {match}")
        return lora_dict

    def _additive_dictionary(self, matches):
        word_dict = defaultdict(float)
        for words, value in matches:
            try:
                for word in words.split(','):
                    word = word.strip().replace('_', ' ') if REPLACE_UNDERSCORES else word.strip()
                    value = float(value)
                    word_dict[word] = word_dict[word] * value if word_dict[word] >= 1.0 else value
            except Exception as e:
                self._write_error_log(f"Error in _additive_dictionary: {e}, words: {words}, value: {value}")
        return word_dict

    def _scale_dict_values(self, input_dict, max_val):
        try:
            if not input_dict:
                return input_dict
            max_dict_val = max(input_dict.values())
            factor = max_val / max_dict_val
            return {k: v * factor for k, v in input_dict.items()}
        except Exception as e:
            self._write_error_log(f"Error in _scale_dict_values: {e}")
            return {}

    def _round_dict_values(self, input_dict):
        try:
            return {k: round(v, ROUNDING_DECIMAL_PLACE) for k, v in input_dict.items()}
        except Exception as e:
            self._write_error_log(f"Error in _round_dict_values: {e}")
            return {}

    def _floor_dict_values(self, input_dict, input_min):
        try:
            return {k: max(v, input_min) for k, v in input_dict.items()}
        except Exception as e:
            self._write_error_log(f"Error in _floor_dict_values: {e}")
            return {}

    def balance_text_prompt(self, input_text):
        try:
            if not isinstance(input_text, str):
                raise ValueError("Input text must be a string")

            lora_matches = re.findall(r'<([^>]+)>', input_text)
            lora_dict = self._additive_lora_dictionary(lora_matches)

            matches = re.findall(r'\(([\w\s,]+):([\d.]+)\)', input_text)
            word_dict = self._additive_dictionary(matches)

            text_without_specials = re.sub(r'<[^>]+>|\([^()]*\)', '', input_text)
            for word in text_without_specials.split(','):
                word = word.strip().replace('_', ' ') if REPLACE_UNDERSCORES else word.strip()
                if word:
                    word_dict[word] = word_dict[word] + 0.1 if word_dict[word] > 0.01 else 1.0

            scaled_lora_dict = self._scale_dict_values(lora_dict, 0.9)
            scaled_word_dict = self._scale_dict_values(word_dict, 1.5)

            rounded_lora_dict = self._round_dict_values(scaled_lora_dict)
            rounded_word_dict = self._round_dict_values(scaled_word_dict)

            floored_word_dict = self._floor_dict_values(rounded_word_dict, 1.0)

            lora_str = ' , '.join(f'<{k}:{v}>' for k, v in rounded_lora_dict.items())
            words_str = ' , '.join(f'({k}:{v})' for k, v in floored_word_dict.items())
            final_str = f'{lora_str} , {words_str}'

            return re.sub(r'\(([\w\s]+):1\.0(?![0-9])\)', r'\1', final_str)
        except Exception as e:
            self._write_error_log(f"Error in balance_text_prompt: {e}")
            return ""

    def simplify_prompt(self, input_text):
        try:
            if not isinstance(input_text, str):
                raise ValueError("Input text must be a string")

            lora_matches = re.findall(r'<([^>]+)>', input_text)
            lora_set = set(f'<{match}>' for match in lora_matches)

            matches = re.findall(r'\(([\w\s,]+):([\d.]+)\)', input_text)
            words_set = set(word.strip() for words, _ in matches for word in words.split(','))

            text_without_specials = re.sub(r'<[^>]+>|\([^()]*\)', '', input_text)
            words_set.update(word.strip() for word in text_without_specials.split(','))

            return ' , '.join(sorted(lora_set.union(words_set)))
        except Exception as e:
            self._write_error_log(f"Error in simplify_prompt: {e}")
            return ""

    def scale_lora_only(self, input_text, multiplier):
        try:
            if not isinstance(input_text, str):
                raise ValueError("Input text must be a string")

            lora_matches = re.findall(r'<([^>]+)>', input_text)
            lora_dict = self._additive_lora_dictionary(lora_matches)
            scaled_lora_dict = self._scale_dict_values(lora_dict, float(multiplier))
            rounded_lora_dict = self._round_dict_values(scaled_lora_dict)
            return ' , '.join(f'<{k}:{v}>' for k, v in rounded_lora_dict.items())
        except Exception as e:
            self._write_error_log(f"Error in scale_lora_only: {e}")
            return ""
        
#//=======================================================================================
#// MAIN 
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setAcceptDrops(True)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    window.show()
    sys.exit(app.exec_())