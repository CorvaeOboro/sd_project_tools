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
    Associated preview: berry(1).preview.png or berry(1).preview.webm, etc.

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
import logging
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional, Tuple

# --------------------------
# Logging Configuration
# --------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('file_sorter.log')
    ]
)

# --------------------------
# Configuration Constants
# --------------------------
# Extensions for files to be sorted (add any as needed)
NEURALNETS_EXTENSIONS = ['.safetensors', '.pt', '.ckpt']

# The extension for the associated info file
INFO_EXTENSION = ".civitai.info"

# List of possible preview file extensions
PREVIEW_EXTENSIONS = [
    ".preview.png",
    ".preview.jpg",
    ".preview.jpeg",
    ".preview.webp",
    ".preview.gif",
    ".preview.webm",
    ".preview.mp4"
]

# Delay (in seconds) after copying a file (helps to avoid potential race conditions)
TRANSFER_DELAY = 0.5  # Reduced from 1 to 0.5 to speed up processing

# Maximum file size for progress reporting (in bytes)
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB

# --------------------------
# Helper Functions
# --------------------------
def get_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """
    Return the SHA256 hash of the file at the given path.
    Uses chunked reading for large files to avoid memory issues.
    """
    sha256_hash = hashlib.sha256()
    file_size = os.path.getsize(filepath)
    
    try:
        with open(filepath, 'rb') as f:
            if file_size > LARGE_FILE_THRESHOLD:
                with tqdm(total=file_size, unit='B', unit_scale=True, desc=f"Hashing {os.path.basename(filepath)}") as pbar:
                    for chunk in iter(lambda: f.read(chunk_size), b''):
                        sha256_hash.update(chunk)
                        pbar.update(len(chunk))
            else:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    sha256_hash.update(chunk)
        
        file_hash = sha256_hash.hexdigest()
        logging.debug(f"Calculated hash for {filepath}: {file_hash}")
        return file_hash
    except Exception as e:
        logging.error(f"Error calculating hash for {filepath}: {e}")
        raise

def safe_copy_file(src: str, dest: str) -> str:
    """
    Copy a file from src to dest while verifying the copy.
    Uses chunked copying for large files to avoid memory issues.
    Returns the destination file path on success.
    """
    logging.info(f"Starting to copy file from {src} to {dest}")
    original_dest = dest
    base, ext = os.path.splitext(dest)
    counter = 1
    
    while os.path.exists(original_dest):
        try:
            if (get_file_hash(src) == get_file_hash(original_dest) and
                    os.path.getsize(src) == os.path.getsize(original_dest)):
                logging.info(f"Destination file {original_dest} already exists and is identical.")
                return original_dest
        except Exception as e:
            logging.warning(f"Error comparing files {src} and {original_dest}: {e}")
            
        original_dest = f"{base}_{counter}{ext}"
        counter += 1
        logging.debug(f"File exists. Trying new destination: {original_dest}")

    try:
        # Use chunked copying for large files
        file_size = os.path.getsize(src)
        if file_size > LARGE_FILE_THRESHOLD:
            with open(src, 'rb') as fsrc, open(original_dest, 'wb') as fdst:
                with tqdm(total=file_size, unit='B', unit_scale=True, 
                         desc=f"Copying {os.path.basename(src)}") as pbar:
                    while True:
                        chunk = fsrc.read(8192)
                        if not chunk:
                            break
                        fdst.write(chunk)
                        pbar.update(len(chunk))
            # Copy metadata separately
            shutil.copystat(src, original_dest)
        else:
            shutil.copy2(src, original_dest)
            
        logging.debug(f"Copied file. Waiting {TRANSFER_DELAY} second(s)...")
        time.sleep(TRANSFER_DELAY)

        # Verify the copy
        if (get_file_hash(src) == get_file_hash(original_dest) and
                os.path.getsize(src) == os.path.getsize(original_dest)):
            logging.info(f"File copy verified: {src} -> {original_dest}")
            return original_dest
        else:
            logging.error(f"Failed to verify copy of {src} to {original_dest}")
            os.remove(original_dest)
            raise Exception("File copy verification failed")
    except Exception as e:
        logging.error(f"Error during file copy {src} to {original_dest}: {e}")
        if os.path.exists(original_dest):
            os.remove(original_dest)
        raise

def load_json_safely(filepath: str) -> dict:
    """
    Load JSON from a file, attempting to fix common formatting issues.
    Raises an error if parsing fails.
    """
    logging.debug(f"Attempting to load JSON from {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                logging.debug(f"Successfully loaded JSON from {filepath}")
                return data
            except json.JSONDecodeError as e:
                logging.warning(f"JSON decode error in {filepath}: {e}. Trying to fix common issues.")
                f.seek(0)
                content = f.read()
                # Remove trailing commas before closing braces or brackets
                content_fixed = re.sub(r',\s*([}\]])', r'\1', content)
                try:
                    data = json.loads(content_fixed)
                    logging.info(f"Successfully loaded fixed JSON from {filepath}")
                    return data
                except Exception as e2:
                    logging.error(f"Failed to parse JSON file {filepath} even after fixing: {e2}")
                    raise ValueError(f"Failed to parse JSON file {filepath} even after fixing: {e2}")
    except Exception as e:
        logging.error(f"Error reading file {filepath}: {e}")
        raise

def find_associated_file(file_path: str, suffixes: str | List[str]) -> Optional[str]:
    """
    Attempt to locate an associated file that matches any of the provided suffixes.
    Returns the full path of the first matching file found, or None if no matches.
    """
    if isinstance(suffixes, str):
        suffixes = [suffixes]
        
    base = os.path.splitext(file_path)[0]
    logging.debug(f"Searching for associated files for {base} with suffixes: {suffixes}")
    
    for suffix in suffixes:
        # Try direct match first
        candidate = base + suffix
        if os.path.exists(candidate):
            logging.debug(f"Found associated file (direct match): {candidate}")
            return candidate
            
        # Try glob pattern if direct match fails
        pattern = base + "*" + suffix
        matches = glob.glob(pattern)
        if matches:
            logging.debug(f"Found associated file via glob: {matches[0]} (pattern: {pattern})")
            return matches[0]
            
    logging.debug(f"No associated file found for {file_path} with any of the suffixes: {suffixes}")
    return None

def sort_files_by_parameters(base_dir: str, extensions: List[str], info_suffix: str, preview_suffixes: List[str]) -> None:
    """
    Sort files based on parameters in the associated info file.
    Handles multiple preview file types and provides detailed progress information.
    """
    logging.info(f"Starting file sort in directory: {base_dir}")
    
    if not os.path.exists(base_dir):
        msg = f"Directory does not exist: {base_dir}"
        logging.error(msg)
        messagebox.showerror("Error", msg)
        return

    # List target files
    files = [
        f for f in os.listdir(base_dir)
        if os.path.isfile(os.path.join(base_dir, f)) and 
        os.path.splitext(f)[1].lower() in extensions
    ]
    
    if not files:
        msg = f"No files found with extensions {extensions} in {base_dir}"
        logging.warning(msg)
        messagebox.showwarning("Warning", msg)
        return
        
    logging.info(f"Found {len(files)} file(s) to process")
    
    for file in tqdm(files, desc="Processing files"):
        file_path = os.path.join(base_dir, file)
        logging.info(f"\nProcessing file: {file_path}")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > LARGE_FILE_THRESHOLD:
            logging.info(f"Large file detected ({file_size/1024/1024:.2f} MB): {file}")

        # Find associated files
        info_path = find_associated_file(file_path, info_suffix)
        if not info_path:
            logging.warning(f"No info file found for {file_path}. Skipping.")
            continue

        preview_path = find_associated_file(file_path, preview_suffixes)
        if preview_path:
            logging.info(f"Found preview file: {preview_path}")
        else:
            logging.debug(f"No preview file found for {file_path}")

        try:
            info = load_json_safely(info_path)
            nsfw_flag = info.get("model", {}).get("nsfw", False)
            poi_flag = info.get("model", {}).get("poi", False)
            logging.info(f"Parameters: nsfw={nsfw_flag}, poi={poi_flag}")

            destinations = []
            if nsfw_flag:
                destinations.append(os.path.join(base_dir, "nsfw"))
            if poi_flag:
                destinations.append(os.path.join(base_dir, "poi"))

            if not destinations:
                logging.debug(f"File {file_path} does not meet any criteria. Skipping.")
                continue

            # Process each destination
            copy_success = True
            for dest in destinations:
                os.makedirs(dest, exist_ok=True)
                logging.info(f"Copying files to: {dest}")

                try:
                    # Copy main file
                    dest_file = os.path.join(dest, os.path.basename(file_path))
                    safe_copy_file(file_path, dest_file)

                    # Copy info file
                    dest_info = os.path.join(dest, os.path.basename(info_path))
                    safe_copy_file(info_path, dest_info)

                    # Copy preview if it exists
                    if preview_path:
                        dest_preview = os.path.join(dest, os.path.basename(preview_path))
                        safe_copy_file(preview_path, dest_preview)

                except Exception as e:
                    logging.error(f"Error copying files to {dest}: {e}")
                    copy_success = False
                    break

            # Remove originals if all copies succeeded
            if copy_success:
                logging.info("Removing original files...")
                try:
                    os.remove(file_path)
                    os.remove(info_path)
                    if preview_path:
                        os.remove(preview_path)
                    logging.info("Original files removed successfully")
                except Exception as e:
                    logging.error(f"Error removing original files: {e}")
            else:
                logging.warning("Skipping removal of originals due to copy errors")

        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")
            continue

# --------------------------
# GUI Code
# --------------------------
class FileOrganizerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Parameter-based File Organizer')
        self.root.configure(bg='#333333')
        self.setup_ui()

    def setup_ui(self):
        # Directory entry
        self.entry = tk.Entry(self.root, width=60, bg='#666666', fg='white')
        self.entry.pack(padx=10, pady=10)

        # Buttons frame
        frame_buttons = tk.Frame(self.root, bg='#333333')
        frame_buttons.pack(pady=5)

        # Select directory button
        tk.Button(
            frame_buttons,
            text='Select Directory',
            command=self.select_directory,
            bg='#555555',
            fg='white'
        ).grid(row=0, column=0, padx=5)

        # Sort files button
        tk.Button(
            frame_buttons,
            text='Sort Files',
            command=self.start_sorting,
            bg='#555555',
            fg='white'
        ).grid(row=0, column=1, padx=5)

    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, directory)
            logging.info(f"Selected directory: {directory}")

    def start_sorting(self):
        directory = self.entry.get()
        if not directory:
            messagebox.showwarning("Warning", "Please select a directory first")
            return
            
        try:
            sort_files_by_parameters(
                directory,
                NEURALNETS_EXTENSIONS,
                INFO_EXTENSION,
                PREVIEW_EXTENSIONS
            )
            messagebox.showinfo("Success", "File sorting completed")
        except Exception as e:
            logging.error(f"Error during sorting: {e}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

    def run(self):
        self.root.mainloop()

def main():
    logging.info("Starting application")
    app = FileOrganizerGUI()
    app.run()

if __name__ == '__main__':
    main()
