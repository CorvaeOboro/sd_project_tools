#!/usr/bin/env python3
"""
Parameter-based File Sorter with Robust Associated File Matching and Debug Logging

This script scans for files (with specific extensions) in a selected folder (non-recursively)
and checks for an associated info file whose name is based on the primary file's base name.
It expects the info file to contain JSON data with a "model" dictionary that includes
two boolean parameters: "nsfw" and "poi".

For example:
    Primary file: berry(1).safetensors
    Associated info file: berry(1).civitai.info

Files flagged as:
    - nsfw: true   -> will be copied to a subfolder named "nsfw"
    - poi: true    -> will be copied to a subfolder named "poi"

After a successful copy (verified via hash and filesize), the originals are removed.
"""

import os
import json
import re
import glob
import shutil
import hashlib
import time
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog

# --------------------------
# Debug Flag and Helper Function
# --------------------------
DEBUG = True

def debug_print(message):
    if DEBUG:
        print(message)

# --------------------------
# Configuration Constants
# --------------------------
# Extensions for files to be sorted (add any as needed)
NEURALNETS_EXTENSIONS = ['.safetensors', '.pt', '.ckpt']

# The extension for the associated info file.
# (Set to ".civitai.info" so that e.g. "berry(1).safetensors" will be matched with "berry(1).civitai.info")
INFO_EXTENSION = ".civitai.info"

# Optional preview file extension (if such files exist alongside your primary files)
PREVIEW_EXTENSION = ".preview.png"

# Delay (in seconds) after copying a file (helps to avoid potential race conditions)
TRANSFER_DELAY = 1

# --------------------------
# Helper Functions
# --------------------------
def get_file_hash(filepath):
    """Return the SHA256 hash of the file at the given path."""
    with open(filepath, 'rb') as f:
        file_bytes = f.read()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        debug_print(f"Calculated hash for {filepath}: {file_hash}")
        return file_hash

def safe_copy_file(src, dest):
    """
    Copy a file from src to dest while verifying the copy.
    If a file with the same name already exists, a new name is generated.
    Returns the destination file path on success.
    """
    debug_print(f"Starting to copy file from {src} to {dest}")
    original_dest = dest
    base, ext = os.path.splitext(dest)
    counter = 1

    # If a file with the same name exists, iterate the filename until a unique one is found.
    while os.path.exists(original_dest):
        # If the existing file is exactly the same, skip the copy.
        if (get_file_hash(src) == get_file_hash(original_dest) and
                os.path.getsize(src) == os.path.getsize(original_dest)):
            debug_print(f"Destination file {original_dest} already exists and is identical.")
            return original_dest
        else:
            original_dest = f"{base}_{counter}{ext}"
            counter += 1
            debug_print(f"File exists. Trying new destination: {original_dest}")

    # Copy the file and wait briefly.
    shutil.copy2(src, original_dest)
    debug_print(f"Copied file from {src} to {original_dest}. Waiting for {TRANSFER_DELAY} second(s)...")
    time.sleep(TRANSFER_DELAY)

    # Verify the copy by comparing the hash and file size.
    if (get_file_hash(src) == get_file_hash(original_dest) and
            os.path.getsize(src) == os.path.getsize(original_dest)):
        debug_print(f"File copy verified: {src} -> {original_dest}")
        return original_dest
    else:
        debug_print(f"Failed to verify copy of {src} to {original_dest}.")
        os.remove(original_dest)
        raise Exception("File copy verification failed")

def load_json_safely(filepath):
    """
    Load JSON from a file, attempting to fix common formatting issues such as trailing commas.
    Raises an error if parsing still fails.
    """
    debug_print(f"Attempting to load JSON from {filepath}")
    with open(filepath, 'r') as f:
        try:
            data = json.load(f)
            debug_print(f"Successfully loaded JSON from {filepath}")
            return data
        except json.JSONDecodeError as e:
            debug_print(f"JSON decode error in {filepath}: {e}. Trying to fix common issues.")
            f.seek(0)
            content = f.read()
            # Remove trailing commas before closing braces or brackets.
            content_fixed = re.sub(r',\s*([}\]])', r'\1', content)
            try:
                data = json.loads(content_fixed)
                debug_print(f"Successfully loaded fixed JSON from {filepath}")
                return data
            except Exception as e2:
                raise ValueError(f"Failed to parse JSON file {filepath} even after fixing: {e2}")

def find_associated_file(file_path, suffix):
    """
    Attempt to locate an associated file for the given file_path that ends with the provided suffix.
    First, it constructs the candidate filename using os.path.splitext and appending the suffix.
    If that candidate does not exist, it uses glob to search for files starting with the base name and ending with the suffix.
    Returns the full path of the associated file if found; otherwise, returns None.
    """
    base = os.path.splitext(file_path)[0]  # e.g. "berry(1)" from "berry(1).safetensors"
    candidate = base + suffix            # e.g. "berry(1).civitai.info"
    if os.path.exists(candidate):
        debug_print(f"Found associated file (direct match): {candidate}")
        return candidate
    else:
        pattern = base + "*" + suffix
        matches = glob.glob(pattern)
        if matches:
            debug_print(f"Found associated file via glob: {matches[0]} (pattern used: {pattern})")
            return matches[0]
        else:
            debug_print(f"No associated file found for {file_path} with suffix '{suffix}' (pattern: {pattern})")
            return None

def sort_files_by_parameters(base_dir, extensions, info_suffix, preview_suffix):
    """
    Sort files in the base_dir (non-recursively) based on parameters found in the associated info file.
    If the info file indicates that "nsfw" or "poi" is true in the "model" section, the files are
    copied to corresponding subfolders ("nsfw" and/or "poi"). After successful copies, the originals are removed.
    """
    debug_print(f"Scanning directory: {base_dir}")

    # List only files (not directories) with one of the target extensions in the base folder.
    files = [
        f for f in os.listdir(base_dir)
        if os.path.isfile(os.path.join(base_dir, f)) and os.path.splitext(f)[1].lower() in extensions
    ]
    
    debug_print(f"Found {len(files)} file(s) with the specified extensions in {base_dir}.")
    
    for file in tqdm(files, desc="Sorting files"):
        file_path = os.path.join(base_dir, file)
        debug_print(f"Processing file: {file_path}")

        # Locate the associated info file robustly.
        info_path = find_associated_file(file_path, info_suffix)
        if not info_path:
            debug_print(f"No associated info file found for {file_path}. Skipping.")
            continue

        # Locate the associated preview file (if it exists); this is optional.
        preview_path = find_associated_file(file_path, preview_suffix)

        try:
            info = load_json_safely(info_path)
        except Exception as e:
            debug_print(f"Error loading/parsing info file {info_path}: {e}. Skipping file.")
            continue

        # Extract flags; default to False if not present.
        nsfw_flag = info.get("model", {}).get("nsfw", False)
        poi_flag = info.get("model", {}).get("poi", False)
        debug_print(f"Extracted parameters for {file_path}: nsfw={nsfw_flag}, poi={poi_flag}")

        # Determine destination folders based on the flags.
        destinations = []
        if nsfw_flag:
            destinations.append(os.path.join(base_dir, "nsfw"))
        if poi_flag:
            destinations.append(os.path.join(base_dir, "poi"))
        
        # If neither flag is true, skip the file.
        if not destinations:
            debug_print(f"File {file_path} does not meet any criteria (nsfw or poi true). Skipping.")
            continue

        # Attempt to copy the file (and its associated info/preview) to each destination.
        copy_success = True
        for dest in destinations:
            os.makedirs(dest, exist_ok=True)
            debug_print(f"Destination directory ensured: {dest}")

            dest_file = os.path.join(dest, os.path.basename(file_path))
            dest_info = os.path.join(dest, os.path.basename(info_path))
            dest_preview = preview_path and os.path.join(dest, os.path.basename(preview_path))

            try:
                debug_print(f"Copying {file_path} to {dest_file}")
                safe_copy_file(file_path, dest_file)
                debug_print(f"Copying {info_path} to {dest_info}")
                safe_copy_file(info_path, dest_info)
                if preview_path and os.path.exists(preview_path):
                    debug_print(f"Copying {preview_path} to {dest_preview}")
                    safe_copy_file(preview_path, dest_preview)
            except Exception as e:
                debug_print(f"Error copying files for {file_path} to {dest}: {e}")
                copy_success = False
                break

        # If all copies succeeded, remove the original file(s).
        if copy_success:
            debug_print(f"All copies successful for {file_path}. Removing original files.")
            try:
                os.remove(file_path)
                os.remove(info_path)
                if preview_path and os.path.exists(preview_path):
                    os.remove(preview_path)
            except Exception as e:
                debug_print(f"Error removing original files for {file_path}: {e}")
        else:
            debug_print(f"Skipping removal of original files for {file_path} due to copy errors.")

# --------------------------
# GUI Code for User Interaction
# --------------------------
def select_directory(entry_widget):
    """Open a directory selection dialog and insert the chosen directory into the entry widget."""
    directory = filedialog.askdirectory()
    if directory:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, directory)
        debug_print(f"Directory selected: {directory}")

def main():
    """Set up the tkinter GUI and start the sorter."""
    root = tk.Tk()
    root.title('Parameter-based File Organizer (Debug Mode)')
    root.configure(bg='#333333')

    # Entry field: Shows the target directory (default empty)
    entry = tk.Entry(root, width=60, bg='#666666', fg='white')
    entry.pack(padx=10, pady=10)

    # Frame for the buttons
    frame_buttons = tk.Frame(root, bg='#333333')
    frame_buttons.pack(pady=5)

    # Button to select directory
    select_button = tk.Button(
        frame_buttons,
        text='Select Directory',
        command=lambda: select_directory(entry),
        bg='#555555',
        fg='white'
    )
    select_button.grid(row=0, column=0, padx=5)

    # Button to start sorting the files
    sort_button = tk.Button(
        frame_buttons,
        text='Sort Files',
        command=lambda: sort_files_by_parameters(
            entry.get(), NEURALNETS_EXTENSIONS, INFO_EXTENSION, PREVIEW_EXTENSION
        ),
        bg='#555555',
        fg='white'
    )
    sort_button.grid(row=0, column=1, padx=5)

    root.mainloop()

if __name__ == '__main__':
    main()
