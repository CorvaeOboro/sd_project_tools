# SORT CIVITAI FILES
# sort the safetensors based on the civitai.info (created by auto1111 extension - civitai helper)
# sorts existing structure of folders into basemodel and type subfolders
# Checkpoints, LORA, LoCon, TextualInversion, separated by parent BaseModelType (SD 1.5, SDXL)
import os
import json
import shutil
import glob
import hashlib
import tkinter as tk
from tkinter import filedialog
# from threading import Thread # avoiding threading due to file copy incomplete errors
import time
from tqdm import tqdm


# TYPE info example = "model": {"name": "3DModelTestA", "type": "Checkpoint"}
TYPE_FOLDERNAME = {  # Directory for each type
    'Checkpoint': 'Checkpoint',
    'LORA': 'LORA',
    'LoCon': 'LoCon',
    'TextualInversion': 'TextualInversion',
}

LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))  # Directory of the Python file
TARGET_DIR = "./test"  # Directory of the neural network files to sort
NEURALNETS_EXTENSIONS = ['.safetensors', '.pt', '.ckpt']  # Extensions to sort
INFO_EXTENSION = '.civitai.info'  # Info file extension
PREVIEW_EXTENSION = '.preview.png'  # Preview file extension
TRANSFER_DELAY = 1  # Delay between transfers in seconds

#//=========================================================================================================


# File operations
def get_file_hash(filepath):
    with open(filepath, 'rb') as file:
        return hashlib.sha256(file.read()).hexdigest()

# Safely move files , by doing a copy , then checking hash compare  
def safe_move_file(src, dest):
    original_dest = dest
    base, ext = os.path.splitext(dest)
    counter = 1

    # if existing file with same name , then iterate filename 
    while os.path.exists(original_dest):
        #if the existing files is the exact same hash and file size then remove the source
        if get_file_hash(src) == get_file_hash(original_dest) and os.path.getsize(src) == os.path.getsize(original_dest):
            os.remove(src)  # Only remove the source file if the copy is verified
            return
        else:
            dest = f"{base}_{counter}{ext}"
            counter += 1

    # Perform the file copy
    shutil.copy2(src, dest)
    time.sleep(TRANSFER_DELAY)  # Wait to ensure the copy is not rushed

    # Verify the copy , compare hash and filesize
    if get_file_hash(src) == get_file_hash(dest) and os.path.getsize(src) == os.path.getsize(dest):
        os.remove(src)  # Only remove the source file if the copy is verified
    else:
        print(f"Failed to verify the copy of {src}. Original remains in place.")
        os.remove(dest) # removing failed copy

def move_files_to_model_dir(file, info_file, preview_file, base_dir, model_type, type_dirs, preview_ext):
    if model_type in type_dirs:
        dest_dir = base_dir
        os.makedirs(dest_dir, exist_ok=True)

        dest_file = os.path.join(dest_dir, os.path.basename(file))
        dest_info_file = os.path.join(dest_dir, os.path.basename(info_file))
        dest_preview_file = file.rsplit(".", 1)[0] + preview_ext

        safe_move_file(file, dest_file)
        safe_move_file(info_file, dest_info_file)
        if os.path.exists(preview_file):
            safe_move_file(preview_file, dest_preview_file)

# Main sorting function
def sort_files(base_dir, extensions, info_ext, preview_ext, type_dirs):
    print("Starting file sorting...")
    for ext in tqdm(extensions, desc="Processing extensions"):
        for file in glob.glob(f'{base_dir}/**/*{ext}', recursive=True):
            info_file = file.rsplit(".", 1)[0] + info_ext
            preview_file = file.rsplit(".", 1)[0] + preview_ext
            if os.path.exists(info_file):
                with open(info_file, 'r') as f:
                    info = json.load(f)
                model_type = info.get('model', {}).get('type', '')
                base_model_type = info.get('baseModel', '')
                final_dir = os.path.join(base_dir, base_model_type, model_type)
                os.makedirs(final_dir, exist_ok=True)
                move_files_to_model_dir(file, info_file, preview_file, final_dir, model_type, type_dirs, preview_ext)

# UI and interaction
def select_directory():
    directory = filedialog.askdirectory()
    entry.delete(0, tk.END)
    entry.insert(0, directory)

# UI ========================================
if __name__ == "__main__":
    root = tk.Tk()
    root.title('Civitai File Organizer')
    root.configure(bg='#333333')

    entry = tk.Entry(root, width=50, bg='#666666', fg='white')
    entry.insert(0, LOCAL_DIR)
    entry.pack(padx=10, pady=10)

    frame_buttons = tk.Frame(root, bg='#333333')
    frame_buttons.pack(pady=5)

    select_button = tk.Button(frame_buttons, text='Select Directory', command=select_directory, bg='#555555', fg='white')
    select_button.grid(row=0, column=0, padx=5)

    sort_button = tk.Button(frame_buttons, text='Sort Files', command=lambda: sort_files(entry.get(), NEURALNETS_EXTENSIONS, INFO_EXTENSION, PREVIEW_EXTENSION, TYPE_FOLDERNAME), bg='#555555', fg='white')
    sort_button.grid(row=0, column=1, padx=5)

    root.mainloop()