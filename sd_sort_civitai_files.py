# SORT CIVITAI FILES
# sort the safetensors based on the civitai.info ( created by auto1111 extension - civitai helper )  
# sorts existing structure of folders into basemodel and type subfolders
# Checkpoints , LORA , LoCon , TextualInversion , separated by parent BaseModelType ( SD 1.5 , SDXL )
import os
import json
import shutil
import glob
import hashlib
import tkinter as tk
from tkinter import filedialog
from threading import Thread

# TYPE info example =    "model": {"name": "3DModelTestA","type": "Checkpoint"}
TYPE_FOLDERNAME = {  # Directory for each type
    'Checkpoint': 'Checkpoint',
    'LORA': 'LORA',
    'LoCon': 'LoCon',
    'TextualInversion': 'TextualInversion',
}

LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))  # Directory of the Python file
TARGET_DIR = "./test" # Directory of the neuralnetwork files to sort 
NEURALNETS_EXTENSIONS = ['.safetensors', '.pt', '.ckpt']  # Extensions to sort
INFO_EXTENSION = '.civitai.info'  # Info file extension
PREVIEW_EXTENSION = '.preview.png'  # Preview file extension

#//=========================================================================================================
def get_file_hash(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def move_file(src, dest_file):
    def move():
        if os.path.exists(dest_file):
            if get_file_hash(src) == get_file_hash(dest_file):
                os.remove(src)
                return
            else:
                base, ext = os.path.splitext(dest_file)
                i = 1
                while os.path.exists(dest_file):
                    dest = f"{base}_{i}{ext}"
                    i += 1
        try:
            dest = dest_file
            shutil.copy2(src, dest)
            os.remove(src)
        except Exception as e:
            print(f"Error moving file {src} to {dest}: {e}")

    Thread(target=move).start()

def move_files_to_model_dir(file, info_file, preview_file, base_dir, model_type, type_dirs, preview_ext):
    if model_type in type_dirs:
        #dest_dir = os.path.join(base_dir, type_dirs[model_type])
        dest_dir = base_dir
        os.makedirs(dest_dir, exist_ok=True)

        dest_file = os.path.join(dest_dir, os.path.basename(file))
        dest_info_file = os.path.join(dest_dir, os.path.basename(info_file))
        dest_preview_file = file.rsplit(".", 1)[0] + preview_ext

        move_file(file, dest_file)
        move_file(info_file, dest_info_file)
        if os.path.exists(preview_file):
            move_file(preview_file, dest_preview_file)

def sort_files(base_dir, extensions, info_ext, preview_ext, type_dirs):
    print("SORT = " + str(base_dir) + "     ext=  " + str(extensions))

    for ext in extensions:
        globbedfiles = glob.glob(f'{base_dir}/**/*{ext}', recursive=True)
        print("files = " + str(globbedfiles))
        for file in glob.glob(f'{base_dir}/**/*{ext}', recursive=True):
            info_file = file.rsplit(".", 1)[0] + info_ext
            preview_file = file.rsplit(".", 1)[0] + preview_ext
            print(f"FILE = {file}       ||info file = {info_file}      ||preview png = {preview_file}")
            if os.path.exists(info_file):
                try:
                    with open(info_file, 'r') as f:
                        info = json.load(f)
                        model_type = info.get('model', {}).get('type', '')
                        base_model_type = info.get('baseModel', '')
                        print("INFO = " + str(info_file) + "  ||type =  " + str(model_type) + "   ||basemodel =   " + str(base_model_type))
                        base_model_dir = os.path.join(base_dir, base_model_type)
                        sub_dir = os.path.relpath(os.path.dirname(file), base_dir)
                        final_type_dirt =  os.path.join(base_model_dir, model_type)
                        final_dir = os.path.join(final_type_dirt, sub_dir)
                        os.makedirs(final_dir, exist_ok=True)
                        move_files_to_model_dir(file, info_file, preview_file, final_dir, model_type, type_dirs, preview_ext)
                        print(f"MOVE = {file} {info_file} {preview_file} {final_dir} {model_type} {type_dirs} {preview_ext}")
                except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                    print(f"Error processing {file}: {e}")

def remove_files_with_extension(base_dir, file_ext):
    for file in glob.glob(f'{base_dir}/**/*{file_ext}', recursive=True):
        try:
            os.remove(file)
            print(f'Removed {file}')
        except OSError as e:
            print(f"Error removing {file}: {e}")

def remove_duplicates(base_dir, extensions):
    file_hashes = {}
    for ext in extensions:
        for file in glob.glob(f'{base_dir}/**/*{ext}', recursive=True):
            try:
                file_hash = get_file_hash(file)
                if file_hash in file_hashes:
                    os.remove(file)
                    print(f'Removed duplicate {file}')
                else:
                    file_hashes[file_hash] = file
            except OSError as e:
                print(f"Error processing {file}: {e}")

def select_directory():
    directory = filedialog.askdirectory()
    entry.delete(0, tk.END)
    entry.insert(0, directory)

#//===========================================================================================================
#// UI
if __name__ == "__main__":
    root = tk.Tk()
    root.title('Civitai File Organizer')
    root.configure(bg='#333333')

    entry = tk.Entry(root, width=50, bg='#666666', fg='white')
    entry.pack(padx=10, pady=10)

    select_button = tk.Button(root, text='Select Directory', command=select_directory, bg='#555555', fg='white')
    select_button.pack(pady=5)

    sort_button = tk.Button(root, text='Sort Files', command=lambda: sort_files(entry.get(), NEURALNETS_EXTENSIONS, INFO_EXTENSION, PREVIEW_EXTENSION, TYPE_FOLDERNAME), bg='#555555', fg='white')
    sort_button.pack(pady=5)

    delete_info_button = tk.Button(root, text='Delete Info Files', command=lambda: remove_files_with_extension(entry.get(), INFO_EXTENSION), bg='#555555', fg='white')
    delete_info_button.pack(pady=5)

    delete_preview_button = tk.Button(root, text='Delete Preview Files', command=lambda: remove_files_with_extension(entry.get(), PREVIEW_EXTENSION), bg='#555555', fg='white')
    delete_preview_button.pack(pady=5)

    remove_duplicates_button = tk.Button(root, text='Remove Duplicates', command=lambda: remove_duplicates(entry.get(), NEURALNETS_EXTENSIONS), bg='#555555', fg='white')
    remove_duplicates_button.pack(pady=5)

    root.mainloop()

#// TODO ===========================================================
# add hash checking to double check if a file copy transfer was good
# add a delay between transfers 
# make the remove duplicates prioritize by multiple parameters , first keep the oldest version , if the same date keep the file with the shortest name to disfavor copies "(1)" suffixs
# make sure to not copy if existing with same hash ( dont iterate filename for exact copy )
# set default directory path text entry 
# color buttons , separate the buttons to two sides 
