# IMAGE TEXT PROMPT TOOLS - image metadata parser with tools to analyze, combine, balance, and simplify prompts
# Drag an image into the working area, use "copy to work area" button to copy prompt, drag in another image and repeat
# BALANCE: working area text is merged, duplicate prompts removed, prompt strength is balanced, duplicate LORAs removed
# SIMPLIFY: removes all strength modifiers on prompt groups, removes group parentheses
# LORA SCALE: relatively scale the strength of all LORAs to fit a maximum and multiply by adjustable scaler
# =================================================================================

# UI Libraries
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QTextEdit, QAction, QFileDialog,
    QPushButton, QMessageBox
)
from PyQt5.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PyQt5.QtCore import Qt

# Image Libraries
from PIL import Image
from PIL.PngImagePlugin import PngInfo

# Utilities
import sys
import os
import re
from collections import defaultdict
import pyperclip

import qdarkstyle

ERROR_LOG_FILE = "image_text_prompt_tools_error_log.txt"
ROUNDING_DECIMAL_PLACE = 2
REPLACE_UNDERSCORES = True


class MainWindow(QMainWindow):
    # =======================================================================================
    # UI Initialization
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IMAGE PROMPT UTILITIES")
        self.setGeometry(200, 30, 1100, 1200)  # Increased height to accommodate new fields
        self._init_ui()

    def _init_ui(self):
        # Image Display Area
        self.label = QLabel(self)
        self.label.setGeometry(10, 20, 490, 490)
        self.display_img_label1 = QLabel("<font size=6 color=white>DRAG DROP IMAGE</font>", self)
        self.display_img_label1.move(100, 100)
        self.display_img_label1.resize(200, 300)
        self.display_img_filepath = QTextEdit(self)
        self.display_img_filepath.setGeometry(10, 500, 490, 100)

        # Metadata Text Areas
        self.textbox = QTextEdit(self)
        self.textbox.setGeometry(520, 20, 270, 300)
        self.textbox.setReadOnly(True)
        self.textbox.setStyleSheet("color: rgb(200, 200, 200);")  # Adjusted color for dark mode

        self.textbox_neg = QTextEdit(self)
        self.textbox_neg.setGeometry(520, 320, 270, 200)
        self.textbox_neg.setReadOnly(True)
        self.textbox_neg.setStyleSheet("color: rgb(200, 200, 200);")  # Adjusted color for dark mode

        # Editable Prompt Areas
        self._init_editable_prompts()
        self._init_buttons()
        self._init_menu()

    def _init_editable_prompts(self):
        # Prompt Edit
        self.textbox_prompt = QTextEdit(self)
        self.textbox_prompt.setGeometry(10, 610, 760, 100)
        self.textbox_prompt.setStyleSheet("color: rgb(200, 200, 200);")
        self.label1 = QLabel("<font size=4 color=white>PROMPT EDIT</font>", self)
        self.label1.move(10, 595)
        self.label1.resize(500, 20)

        # Prompt Output
        self.textbox_prompt_output = QTextEdit(self)
        self.textbox_prompt_output.setGeometry(10, 720, 760, 100)
        self.textbox_prompt_output.setStyleSheet("color: rgb(200, 200, 200);")
        self.label2 = QLabel("<font size=4 color=white>PROMPT OUTPUT</font>", self)
        self.label2.move(10, 705)
        self.label2.resize(500, 20)

        # Negative Prompt Edit
        self.textbox_prompt_neg = QTextEdit(self)
        self.textbox_prompt_neg.setGeometry(10, 830, 760, 100)
        self.textbox_prompt_neg.setStyleSheet("color: rgb(200, 200, 200);")
        self.label1_neg = QLabel("<font size=4 color=white>NEGATIVE EDIT</font>", self)
        self.label1_neg.move(10, 815)
        self.label1_neg.resize(500, 20)

        # Negative Prompt Output
        self.textbox_prompt_output_neg = QTextEdit(self)
        self.textbox_prompt_output_neg.setGeometry(10, 940, 760, 100)
        self.textbox_prompt_output_neg.setStyleSheet("color: rgb(200, 200, 200);")
        self.label2_neg = QLabel("<font size=4 color=white>NEGATIVE OUTPUT</font>", self)
        self.label2_neg.move(10, 925)
        self.label2_neg.resize(500, 20)

        # Lora Hashes Edit
        self.textbox_lora_hashes = QTextEdit(self)
        self.textbox_lora_hashes.setGeometry(800, 610, 270, 100)
        self.textbox_lora_hashes.setStyleSheet("color: rgb(200, 200, 200);")
        self.label_lora_hashes = QLabel("<font size=4 color=white>LORA HASHES EDIT</font>", self)
        self.label_lora_hashes.move(800, 595)
        self.label_lora_hashes.resize(500, 20)

        # TI Hashes Edit
        self.textbox_ti_hashes = QTextEdit(self)
        self.textbox_ti_hashes.setGeometry(800, 830, 270, 100)
        self.textbox_ti_hashes.setStyleSheet("color: rgb(200, 200, 200);")
        self.label_ti_hashes = QLabel("<font size=4 color=white>TI HASHES EDIT</font>", self)
        self.label_ti_hashes.move(800, 815)
        self.label_ti_hashes.resize(500, 20)

    def _init_buttons(self):
        # Functional Buttons
        self.convert_button = QPushButton('CONVERT', self)
        self.convert_button.resize(100, 25)
        self.convert_button.move(10, 570)
        self.convert_button.clicked.connect(self.CONVERT_jpg_to_png)

        self.simple_button = QPushButton('SIMPLE', self)
        self.simple_button.resize(100, 25)
        self.simple_button.move(250, 570)
        self.simple_button.clicked.connect(self.button_simplify)

        self.balance_button = QPushButton('BALANCE', self)
        self.balance_button.resize(100, 25)
        self.balance_button.move(450, 570)
        self.balance_button.clicked.connect(self.button_balance)

        self.copy_to_area_button = QPushButton('COPY TO AREA', self)
        self.copy_to_area_button.resize(100, 25)
        self.copy_to_area_button.move(700, 570)
        self.copy_to_area_button.clicked.connect(self.COPY_TO_AREA)

        # Copy and Clear Buttons for Prompt Output
        self.copy_button = QPushButton('COPY', self)
        self.copy_button.resize(50, 20)
        self.copy_button.move(770, 730)
        self.copy_button.clicked.connect(self.copyToClipboard)

        self.clear_button = QPushButton('CLEAR', self)
        self.clear_button.resize(50, 20)
        self.clear_button.move(770, 760)
        self.clear_button.clicked.connect(self.clear_prompts)

        # Copy and Clear Buttons for Negative Prompt Output
        self.copy_button_neg = QPushButton('COPY', self)
        self.copy_button_neg.resize(50, 20)
        self.copy_button_neg.move(770, 950)
        self.copy_button_neg.clicked.connect(self.copyToClipboard_neg)

        self.clear_button_neg = QPushButton('CLEAR', self)
        self.clear_button_neg.resize(50, 20)
        self.clear_button_neg.move(770, 980)
        self.clear_button_neg.clicked.connect(self.clear_negative_prompts)

        # Save Metadata Button
        self.save_metadata_button = QPushButton('SAVE METADATA', self)
        self.save_metadata_button.resize(100, 25)
        self.save_metadata_button.move(700, 600)
        self.save_metadata_button.clicked.connect(self.save_metadata)

    def _init_menu(self):
        open_file_action = QAction("Open", self)
        open_file_action.setShortcut("Ctrl+O")
        open_file_action.triggered.connect(self.open_file)
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(open_file_action)

    # =======================================================================================
    # Event Handlers
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        file_path = event.mimeData().urls()[0].toLocalFile()
        if file_path.lower().endswith(('.jpg', '.jpeg', '.bmp', '.png')):
            self.load_image(file_path)

    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Image Files (*.jpg *.png *.jpeg *.bmp)"
        )
        if file_name:
            self.load_image(file_name)

    # =======================================================================================
    # Image Loading and Metadata Handling
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
        if file_path.lower().endswith(".jpg"):
            self._handle_jpg_metadata(file_path)
        elif file_path.lower().endswith(".png"):
            self._handle_png_metadata(file_path)

    def _handle_jpg_metadata(self, file_path):
        # Implement JPEG metadata handling if needed
        pass

    def _handle_png_metadata(self, file_path):
        try:
            # Read the 'parameters' text from the image metadata
            img = Image.open(file_path)
            parameters = img.text.get('parameters', '')
            if parameters:
                self.textbox.setPlainText(parameters)
                prompt, negative_prompt, lora_hashes, ti_hashes = self.parse_parameters(parameters)
                self.textbox_prompt.setPlainText(prompt)
                self.textbox_prompt_neg.setPlainText(negative_prompt)
                self.textbox_lora_hashes.setPlainText(lora_hashes)
                self.textbox_ti_hashes.setPlainText(ti_hashes)
            else:
                self.textbox.setPlainText("No parameters found")
        except Exception as e:
            print(f"Error reading PNG metadata: {e}")
            self.textbox.setPlainText("Error reading metadata")

    # =======================================================================================
    # Button Functions
    def COPY_TO_AREA(self):
        existing_text = self.textbox_prompt.toPlainText()
        prompt_text = self.textbox.toPlainText()
        combined_text = f"{existing_text} , {prompt_text}"
        self.textbox_prompt.setPlainText(combined_text)

        existing_text_neg = self.textbox_prompt_neg.toPlainText()
        prompt_text_neg = self.textbox_neg.toPlainText()
        combined_text_neg = f"{existing_text_neg} , {prompt_text_neg}"
        self.textbox_prompt_neg.setPlainText(combined_text_neg)

    def clear_prompts(self):
        self.textbox_prompt_output.clear()

    def clear_negative_prompts(self):
        self.textbox_prompt_output_neg.clear()

    def CONVERT_jpg_to_png(self):
        # Implement conversion if needed
        pass

    def button_simplify(self):
        prompt_text = self.textbox_prompt.toPlainText()
        prompt_simplified = self.simplify_prompt(prompt_text)
        self.textbox_prompt_output.setPlainText(prompt_simplified)

    def button_balance(self):
        prompt_text = self.textbox_prompt.toPlainText()
        prompt_balanced = self.balance_text_prompt(prompt_text)
        self.textbox_prompt_output.setPlainText(prompt_balanced)

    def copyToClipboard(self):
        text = self.textbox_prompt_output.toPlainText()
        if text:
            pyperclip.copy(text)

    def copyToClipboard_neg(self):
        text = self.textbox_prompt_output_neg.toPlainText()
        if text:
            pyperclip.copy(text)

    # =======================================================================================
    # Metadata Editing and Saving
    def save_metadata(self):
        current_image = self.display_img_filepath.toPlainText()
        if os.path.isfile(current_image) and current_image.lower().endswith('.png'):
            try:
                img = Image.open(current_image)
                info = img.info
                parameters = info.get('parameters', '')

                new_prompt = self.textbox_prompt.toPlainText()
                new_negative_prompt = self.textbox_prompt_neg.toPlainText()
                new_lora_hashes = self.textbox_lora_hashes.toPlainText()
                new_ti_hashes = self.textbox_ti_hashes.toPlainText()

                if parameters:
                    # Reconstruct parameters
                    new_parameters = self.reconstruct_parameters(
                        parameters, new_prompt, new_negative_prompt, new_lora_hashes, new_ti_hashes
                    )
                else:
                    # If no existing parameters, create a new one
                    new_parameters = (
                        f'{new_prompt}\nNegative prompt: {new_negative_prompt}\n'
                        f'Lora hashes: {new_lora_hashes}\nTI hashes: {new_ti_hashes}'
                    )

                pnginfo = PngInfo()
                for key, value in info.items():
                    if key != 'parameters':
                        pnginfo.add_text(key, value)
                pnginfo.add_text('parameters', new_parameters)

                base, ext = os.path.splitext(current_image)
                new_image_path = base + '_edited' + ext
                img.save(new_image_path, 'PNG', pnginfo=pnginfo)
                QMessageBox.information(self, 'Success', f'Image saved to {new_image_path}')
            except Exception as e:
                QMessageBox.warning(self, 'Error', f'Error saving metadata: {e}')
        else:
            QMessageBox.warning(self, 'Error', 'No PNG image loaded.')

    # =======================================================================================
    # Prompt Manipulation Functions
    def parse_parameters(self, parameters_str):
        # Remove any null characters
        parameters_str = parameters_str.replace('\x00', '')

        # Extract the positive prompt
        prompt_match = re.search(r'^(.*?)(?=\nNegative prompt:|$)', parameters_str, re.DOTALL)
        prompt = prompt_match.group(1).strip() if prompt_match else parameters_str.strip()

        # Extract the negative prompt
        negative_prompt_match = re.search(r'Negative prompt:\s*(.*?)(?=\n[A-Za-z ]+:|$)', parameters_str, re.DOTALL)
        negative_prompt = negative_prompt_match.group(1).strip() if negative_prompt_match else ''

        # Extract Lora hashes
        lora_hashes_match = re.search(r'Lora hashes:\s*(.*?)(?=\n[A-Za-z ]+:|$)', parameters_str, re.DOTALL)
        lora_hashes = lora_hashes_match.group(1).strip() if lora_hashes_match else ''

        # Extract TI hashes
        ti_hashes_match = re.search(r'TI hashes:\s*(.*?)(?=\n[A-Za-z ]+:|$)', parameters_str, re.DOTALL)
        ti_hashes = ti_hashes_match.group(1).strip() if ti_hashes_match else ''

        return prompt, negative_prompt, lora_hashes, ti_hashes

    def reconstruct_parameters(self, parameters_str, new_prompt, new_negative_prompt, new_lora_hashes, new_ti_hashes):
        # Remove any null characters
        parameters_str = parameters_str.replace('\x00', '')

        # Replace the positive prompt
        if 'Negative prompt:' in parameters_str:
            parameters_str = re.sub(
                r'^(.*?)(?=\nNegative prompt:)',
                f'{new_prompt}',
                parameters_str,
                flags=re.DOTALL
            )
        else:
            # If no negative prompt, replace up to next metadata field or end of string
            parameters_str = re.sub(
                r'^(.*?)(?=\n[A-Za-z ]+:|$)',
                f'{new_prompt}',
                parameters_str,
                flags=re.DOTALL
            )

        # Replace the negative prompt
        if 'Negative prompt:' in parameters_str:
            parameters_str = re.sub(
                r'(Negative prompt:\s*)(.*?)(?=\n[A-Za-z ]+:|$)',
                f'\\1{new_negative_prompt}',
                parameters_str,
                flags=re.DOTALL
            )
        else:
            # If 'Negative prompt:' not found, append it
            parameters_str += f'\nNegative prompt: {new_negative_prompt}'

        # Replace Lora hashes
        if 'Lora hashes:' in parameters_str:
            parameters_str = re.sub(
                r'(Lora hashes:\s*)(.*?)(?=\n[A-Za-z ]+:|$)',
                f'\\1{new_lora_hashes}',
                parameters_str,
                flags=re.DOTALL
            )
        else:
            # If 'Lora hashes:' not found, append it
            parameters_str += f'\nLora hashes: {new_lora_hashes}'

        # Replace TI hashes
        if 'TI hashes:' in parameters_str:
            parameters_str = re.sub(
                r'(TI hashes:\s*)(.*?)(?=\n[A-Za-z ]+:|$)',
                f'\\1{new_ti_hashes}',
                parameters_str,
                flags=re.DOTALL
            )
        else:
            # If 'TI hashes:' not found, append it
            parameters_str += f'\nTI hashes: {new_ti_hashes}'

        return parameters_str

    def balance_text_prompt(self, input_text):
        # Implement balance logic
        return input_text  # Placeholder

    def simplify_prompt(self, input_text):
        # Implement simplify logic
        return input_text  # Placeholder

    # =======================================================================================
    # Error Logging
    def _write_error_log(self, message):
        with open(ERROR_LOG_FILE, "a") as file:
            file.write(message + "\n")


# =======================================================================================
# Main Execution
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    window = MainWindow()
    window.setAcceptDrops(True)
    window.show()
    sys.exit(app.exec_())
