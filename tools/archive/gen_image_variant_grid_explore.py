"""
GENERATE IMAGE VARIANT GRID EXPLORER 
a prompt mutator for use with auto1111 stable diffusion webui
variants of lora strengths are aligned along axis 
"""

#// GEN IMAGE VAIRANT GRID EXPLORER
#//=======================================================================================
import os
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QGridLayout, QWidget, QPushButton, QTextEdit ,QComboBox
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QMetaObject, Q_ARG, Qt, pyqtSlot
import requests
import base64
from PIL import Image, PngImagePlugin
import io
import re
import itertools
from sdparsers import ParserManager
import qdarkstyle
import threading
import time
from tqdm import tqdm

MAX_COMBINATIONS = 100  # Set a limit to the number of combinations

LORA_STRENGTH_TOTAL = 2.0
LORA_STRENGTH_INDIVIDUAL = 0.8
LORA_STRENGTH_STEP = 0.1

GENERATION_MODE_GLOBAL = "txt2img"
OUTPUT_PATH = "./output"

#//=======================================================================================
def read_png_metadata(file_path):
    print("LOG: reading metadata sd parser")
    # Use sdparsers to extract metadata
    parser_manager = ParserManager()
    prompt_data = parser_manager.parse(file_path)
    if prompt_data:
        # Extract the first prompt and its corresponding negative prompt, if available
        prompt, negative_prompt = prompt_data.prompts[0] if prompt_data.prompts else (None, None)
        metadata = {
            "prompt": prompt[0] if prompt else "",
            "negative_prompt": negative_prompt[0] if negative_prompt else "",
            "model": prompt_data.models[0].name if prompt_data.models else "",
            #"model_hash": prompt_data.models[0].model_hash if prompt_data.models else "",
            "seed": prompt_data.samplers[0].parameters.get('seed', '') if prompt_data.samplers else "",
            "steps": prompt_data.samplers[0].parameters.get('steps', '') if prompt_data.samplers else "",
            "cfg_scale": prompt_data.samplers[0].parameters.get('cfg_scale', '') if prompt_data.samplers else "",
            "size": prompt_data.metadata.get('size', ''),
            #"vae_hash": prompt_data.metadata.get('vae_hash', ''),
            "vae": prompt_data.metadata.get('vae', ''),
            #"skip_factor": prompt_data.metadata.get('\\"skip_factor\\"', ''),
            #"backbone_factor": prompt_data.metadata.get('{\\"backbone_factor\\"', ''),
            #"freeu_schedule": prompt_data.metadata.get('freeu_schedule', ''),
            #"freeu_version": prompt_data.metadata.get('freeu_version', ''),
            "wildcard_prompt": prompt_data.metadata.get('wildcard_prompt', ''),
        }
        return metadata
    return {}

def generate_image(image_path, prompt, negative_prompt, width, height):
    print("LOG: generating image")
    # Encode the image as base64
    encoded = base64.b64encode(open(image_path, "rb").read())
    encoded_string = str(encoded, encoding='utf-8')
    init_image_encoded = 'data:image/png;base64,' + encoded_string

    # Set up the payload for the API request
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "n_iter": 1,
        "seed": -1,  # Random seed
        "steps": 50,
        "cfg_scale": 7,
        "width": int(width),
        "height": int(height),
        "sampler_index": "Euler a",
        "denoising_strength": 0.7,
        "alwayson_scripts": {
            "Asymmetric tiling": {"args": [False, True, True, 0, -1]},
            "ADetailer": {"args": [True, {"ad_denoising_strength": 0.4}]}
        }
    }
    if GENERATION_MODE_GLOBAL == "img2img":
        payload["init_images"] = [init_image_encoded]
    print(payload)

    # Make the API request
    api_url_start = 'http://127.0.0.1:7860/sdapi/v1/'
    api_url = api_url_start + GENERATION_MODE_GLOBAL
    print(api_url)
    response = requests.post(api_url, json=payload)
    print(response)
    if response.status_code == 200:
        result = response.json()
        if 'images' in result and len(result['images']) > 0:
            image_data = base64.b64decode(result['images'][0].split(",", 1)[0])
            image = Image.open(io.BytesIO(image_data))
            output_path = os.path.join(OUTPUT_PATH, f"variant_{time.time()}.png")
            image.save(output_path)
            # Wait for the file to be written
            while not os.path.exists(output_path):
                time.sleep(2.0)
            return output_path
            
    return None

#//=======================================================================================
def extract_loras_from_text(text):
    #"""Extracts all LORAs (Low Order Rank Adaptation) from the text"""
    print("LOG: extract_loras_from_text ")
    lora_pattern = r"<lora:([^:>]+):([\d\.]+)>" # regex <lora:name:0.3> 
    loras_extracted = re.findall(lora_pattern, text)
    return loras_extracted

def generate_strength_combinations(number_of_loras, total_strength, max_individual_strength):
    #"""Generates all possible combinations of LORA strengths with a limit """
    print("LOG: Generating strength combinations...")
    strength_steps = [i * LORA_STRENGTH_STEP for i in range(int(max_individual_strength / LORA_STRENGTH_STEP) + 1)]
    total_combinations = len(strength_steps) ** number_of_loras
    estimated_combinations = min(total_combinations, MAX_COMBINATIONS)
    
    print(f"LOG: Estimated number of combinations: {estimated_combinations} (limited to {MAX_COMBINATIONS})")

    valid_combinations = []
    for combo in tqdm(itertools.product(strength_steps, repeat=number_of_loras), total=estimated_combinations, desc="Generating combinations"):
        if sum(combo) <= total_strength:
            valid_combinations.append(combo)
        if len(valid_combinations) >= MAX_COMBINATIONS:
            break  # Stop if the limit is reached

    return valid_combinations

def replace_lora_strength(text, lora_name, new_strength):
    #"""Replaces a single LORA's strength in the text"""
    lora_to_replace = f"<lora:{lora_name}:[\\d\\.]+>"
    new_lora_tag = f"<lora:{lora_name}:{new_strength:.1f}>"
    return re.sub(lora_to_replace, new_lora_tag, text, count=1)

def create_permutations(text, loras, combinations):
    #"""Creates permutations of the text with each combination of LORA strengths."""
    print("LOG: create_permutations ")
    permutations = []
    for combo in combinations:
        modified_text = text
        for lora_info, strength in zip(loras, combo):
            lora_name = lora_info[0]
            modified_text = replace_lora_strength(modified_text, lora_name, strength)
        permutations.append(modified_text)

    return permutations

def generate_lora_variants(text, strength_total=LORA_STRENGTH_TOTAL, max_individual=LORA_STRENGTH_INDIVIDUAL):
    #"""Generates all LORA variants based on strength combinations."""
    print("LOG: generate_lora_variants ")
    loras = extract_loras_from_text(text)  # Extract LORAs
    combinations = generate_strength_combinations(len(loras), strength_total, max_individual)  # Generate strength combinations
    final_permutations = create_permutations(text, loras, combinations)  # Create permutations
    return final_permutations

#//=======================================================================================
# UI
class ImageGrid(QMainWindow):
    def __init__(self):
        super().__init__()
        self.processing_pixmap = QPixmap(256, 256)  # Placeholder pixmap for processing images
        self.processing_pixmap.fill(Qt.gray)  # Fill the pixmap with gray color
        self.variant_images = []  # List to store variant images
        self.generation_mode = GENERATION_MODE_GLOBAL  # Default generation mode
        self.output_dir = "output"  # Directory to save generated images
        os.makedirs(self.output_dir, exist_ok=True)  # Create the directory if it doesn't exist
        self.initUI()


    def initUI(self):
        self.setWindowTitle('Image Variant Explorer')
        self.showMaximized()
        self.setStyleSheet("background-color: black; color: white;")  #  background=black  text=white

        # GRID
        self.central_widget = QWidget(self)
        self.central_widget.setStyleSheet("background-color: black;")  #  background   black
        self.setCentralWidget(self.central_widget)
        self.grid_layout = QGridLayout(self.central_widget)

        # Generation Mode Switch (ComboBox)
        self.mode_combobox = QComboBox(self)
        self.mode_combobox.addItems(["img2img", "txt2img"])
        self.mode_combobox.currentTextChanged.connect(self.change_generation_mode)
        self.grid_layout.addWidget(self.mode_combobox, 2, 3)

        # BLANK IMAGES
        self.image_labels = [[QLabel(self) for _ in range(3)] for _ in range(3)]
        for i in range(3):
            for j in range(3):
                self.image_labels[i][j].setAlignment(Qt.AlignCenter)
                self.image_labels[i][j].setStyleSheet("border: 1px solid white;")  #  border  white
                self.grid_layout.addWidget(self.image_labels[i][j], i, j)
                self.image_labels[i][j].mousePressEvent = self.make_on_click_handler(i, j)
                if (i, j) != (1, 1):  # Set placeholder for unprocessed variants
                    self.image_labels[i][j].setPixmap(self.processing_pixmap)

        self.prompt_textbox = QTextEdit(self)
        self.prompt_textbox.setReadOnly(True)
        self.grid_layout.addWidget(self.prompt_textbox, 0, 3, 1, 1)

        # GENERATE BUTTON
        self.generate_button = QPushButton('Generate Variants', self)
        self.generate_button.setStyleSheet("background-color: #333333; color: white;")  # Set button style to dark
        self.generate_button.clicked.connect(self.generate_variants)
        self.grid_layout.addWidget(self.generate_button, 1, 3)

        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            self.load_center_image(file_path)
            break  # Load only the first image

    def make_on_click_handler(self, row, col):
        def on_click(event):
            # Ignore clicks on the center image
            if (row, col) == (1, 1):
                return
            self.on_variant_clicked(row, col)
        return on_click

    def on_variant_clicked(self, row, col):
        # Get the file path of the clicked variant
        variant_path = self.image_labels[row][col].property("file_path")
        if variant_path:
            self.load_center_image(variant_path)
            self.generate_variants()

    def load_center_image(self, file_path):
        print("LOG: load_center_image")
        # Load the center image and update the UI
        self.center_image_path = file_path
        pixmap = QPixmap(file_path)
        self.image_labels[1][1].setPixmap(pixmap.scaled(256, 256, Qt.KeepAspectRatio))

        # Read metadata and generate variants
        self.generate_variants()

    def change_generation_mode(self, mode):
        self.generation_mode = mode
        print(f"LOG: Generation mode changed to {self.generation_mode}")

    @pyqtSlot(int, int, str)
    def update_image_label(self, row, col, image_path):
        pixmap = QPixmap(image_path)
        self.image_labels[row][col].setPixmap(pixmap.scaled(256, 256, Qt.KeepAspectRatio))

#//=======================================================================================
    def generate_variants(self):
        print("LOG: generating variants")
        # Read metadata from the center image
        metadata = read_png_metadata(self.center_image_path)
        prompt = metadata.get('prompt', '')
        negative_prompt = metadata.get('prompt_neg', '')
        width, height = metadata.get('size', '512x512').split('x')

        # Generate LoRA variants of the prompt
        lora_variant_prompts = generate_lora_variants(prompt)

        # Start a new thread to generate and update variants
        threading.Thread(target=self.generate_and_update_variants, args=(lora_variant_prompts, width, height, negative_prompt)).start()

    def generate_and_update_variants(self, prompts, width, height, negative_prompt):
        print("LOG: generate_and_update_variants")
        for i, variant_prompt in enumerate(prompts):
            variant_path = generate_image(self.center_image_path, variant_prompt, negative_prompt, width, height)
            if variant_path:
                # Update the UI with the new variant
                row, col = divmod(i, 3)
                if (row, col) != (1, 1):  # Skip the center image
                    QMetaObject.invokeMethod(self, "update_image_label", Qt.QueuedConnection, 
                                             Q_ARG(int, row), Q_ARG(int, col), Q_ARG(str, variant_path))

            time.sleep(2)  # Adjust the sleep time as needed

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ImageGrid()
    ex.show()
    sys.exit(app.exec_())

# TODO

# add a switch in the ui have a checkpoint variant explorer switch , that instead of lora's shows different checkpoints , from an array of checkpoints or by pointing to a directory
# separate the ui from everythign else , read_png_metadata , generate_image , generate_and_update_variants , generate_variants shoudl exist outside of the ui class , make sure they're written to be modular and async

# add a switch to lock the input img2img , useful for when doing texture synthesis and looking for lora vairants  .
# add safe text output filename handler
# add the text labels to the variants the text should be white and aligned based on the orientation of the the variant suqare of the grid that it is in , such that the text is closest to the center squeare , for example the upper left square text is aligned to the lower right , and the lower right suqare text is alignedo to the upper left of it square , making the text of each surrounding image closest to the center square . 