"""
TENSOR TOOLS MULTI 
multiple tools for interacting with the tensor diffusion models 
GET INFO , SORT , REMOVE DUPLICATES

Features:

GET INFO 
- for each tensor file gets hash then queries CivitAI API downloading info and preview image
- stores info in a NAME.civitai.info file
- downloads preview image or video , like NAME.preview.png or NAME.preview.mp4

SORT TENSOR FILES by CIVITAI INFO into BASEMODEL and TYPE subfolders
- sort the safetensors based on the civitai.info ( from GET INFO or other external tools like "auto1111 civitai helper")
- BASEMODEL like SDXL or FLUX D
- TYPE like Checkpoint or LORA or LoCon or TextualInversion

SORT TENSOR FILES by CIVITAI INFO into NSFW and POI subfolders
- sort the safetensors based on the civitai.info ( from GET INFO or other external tools like "auto1111 civitai helper")
- NSFW not safe for work
- POI person of interest 

REMOVE DUPLICATES 
- compare files by size and hash
- store computed hashes to a cache file to avoid rehashing , in the target folder's locaiton 
- remove duplicates favoring the oldest file without "(1)" suffix

"""
#//===========================================================================
import os
import sys
import hashlib
import tkinter as tk
from tkinter import filedialog, ttk , scrolledtext
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
import json
import threading
import requests
import time
import re
import shutil
import glob
import io

#//===========================================================================
# Data Classes
@dataclass
class FileStats:
    total_files: int = 0
    unique_sizes: int = 0
    potential_duplicates: int = 0
    bytes_saved: int = 0
    files_deleted: int = 0

#//===========================================================================
# Civitai Constants
VAE_SUFFIX = '.vae'
MODEL_EXTENSIONS = ['.ckpt', '.safetensors', '.sft', '.pt']
CIVITAI_API_URL = 'https://civitai.com/api/v1/model-versions/by-hash/'
CIVITAI_SETTINGS_FILE = "sd_civitai_info_get_settings.json"
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

# Sorting Constants
TYPE_FOLDERNAME = {
    'Checkpoint': 'Checkpoint',
    'LORA': 'LORA',
    'LoCon': 'LoCon',
    'TextualInversion': 'TextualInversion',
}
NEURALNETS_EXTENSIONS = ['.safetensors', '.pt', '.ckpt']
INFO_EXTENSION = '.civitai.info'
TRANSFER_DELAY = 1

# Category Sorting Constants
PREVIEW_EXTENSIONS = [
    '.preview.png',
    '.preview.jpg',
    '.preview.jpeg',
    '.preview.webp',
    '.preview.gif',
    '.preview.webm',
    '.preview.mp4'
]


# ============================================================================
# CIVITAI INFO GET
# ============================================================================

def compute_sha256_civitai(file_path, progress_cb=None):
    """Compute the SHA256 hash of a file for Civitai lookup."""
    sha256_hash = hashlib.sha256()
    total_size = os.path.getsize(file_path)
    
    with open(file_path, "rb") as f:
        bytes_read = 0
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
            bytes_read += len(byte_block)
            if progress_cb:
                progress_cb('Hashing file', bytes_read, total_size)
    return sha256_hash.hexdigest()

def get_model_info_by_hash(hash_value):
    """Query the Civitai API using the hash to get model information."""
    url = CIVITAI_API_URL + hash_value
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"Model not found on Civitai for hash: {hash_value}")
            return None
        else:
            print(f"Error {response.status_code} while querying Civitai for hash {hash_value}")
            return None
    except requests.RequestException as e:
        print(f"Request error while querying Civitai for hash {hash_value}: {e}")
        return None

def get_extension_from_url(url):
    """Extract the file extension from URL, considering query parameters."""
    path = url.split('?')[0]  # Remove query parameters
    ext = os.path.splitext(path)[1].lower()
    return ext if ext else None

def get_extension_from_content_type(content_type):
    """Map content-type to file extension."""
    content_type = content_type.lower()
    content_type_map = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp',
        'video/mp4': '.mp4',
        'video/webm': '.webm'
    }
    return content_type_map.get(content_type.split(';')[0])

def is_valid_image_header(filepath):
    """Check if the file starts with known image format headers."""
    headers = {
        b'\xFF\xD8\xFF': '.jpg',  # JPEG
        b'\x89PNG\r\n\x1a\n': '.png',  # PNG
        b'GIF87a': '.gif',  # GIF87a
        b'GIF89a': '.gif',  # GIF89a
        b'RIFF': '.webp',  # WEBP
        b'\x1A\x45\xDF\xA3': '.webm',  # WEBM
        b'\x00\x00\x00': '.mp4'  # MP4 (simplified check)
    }
    
    try:
        with open(filepath, 'rb') as f:
            # Read enough bytes for the longest header
            header = f.read(8)
            
            for magic, ext in headers.items():
                if header.startswith(magic):
                    return ext
    except Exception as e:
        print(f"Error checking file header: {e}")
    
    return None

def download_image(url, save_path, progress_cb=None):
    """Download an image from a URL and determine its correct extension."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    temp_path = save_path + '.tmp'  # Define temp_path at the start
    
    try:
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            
            # Try to determine the correct extension
            content_type = r.headers.get('content-type', '').lower()
            url_ext = get_extension_from_url(url)
            content_type_ext = get_extension_from_content_type(content_type)
            
            # Save the file with a temporary extension
            total_size = int(r.headers.get('content-length', 0))
            
            with open(temp_path, 'wb') as f:
                bytes_downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_cb:
                            progress_cb('Downloading preview', bytes_downloaded, total_size)
            
            # Check the file header
            header_ext = is_valid_image_header(temp_path)
            
            # Determine final extension (prioritize header check > content-type > url extension)
            final_ext = header_ext or content_type_ext or url_ext or '.png'
            final_path = os.path.splitext(save_path)[0] + final_ext
            
            # Remove any existing file with the same name
            if os.path.exists(final_path):
                os.remove(final_path)
            
            # Rename to final path
            os.rename(temp_path, final_path)
            print(f"Saved preview as {os.path.basename(final_path)}")
            return final_path
            
    except requests.RequestException as e:
        print(f"Error downloading from {url}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None
    except Exception as e:
        print(f"Error processing download: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def get_full_size_image_url(image_url, width):
    """Modify the image URL to request the full-size image."""
    return re.sub(r'/width=\d+/', f'/width={width}/', image_url)

def get_preview_image(base, model_info, max_size_preview=False, skip_nsfw_preview=False):
    """Download the preview image for a model."""
    if 'images' not in model_info:
        print("No images found in model info.")
        return
        
    for image_info in model_info['images']:
        if skip_nsfw_preview and image_info.get('nsfw'):
            print("Skipping NSFW image")
            continue
            
        image_url = image_info.get('url')
        if not image_url:
            continue
            
        if max_size_preview and 'width' in image_info:
            width = image_info['width']
            image_url = get_full_size_image_url(image_url, width)
            
        print(f"Downloading preview from {image_url}")
        preview_path = base + '.preview.png'  # Initial extension will be changed by download_image
        
        if download_image(image_url, preview_path):
            # Successfully downloaded and processed
            break
        else:
            print("Failed to download preview, trying next image if available")
            continue

def scan_civitai_models(model_dir, model_extensions=None, max_size_preview=False, skip_nsfw_preview=False, progress_cb=None):
    """Scan model directory and process each model file for Civitai info."""
    if model_extensions is None:
        model_extensions = MODEL_EXTENSIONS
    
    # Count total files first
    total_models = 0
    for root, _, files in os.walk(model_dir):
        for filename in files:
            _, ext = os.path.splitext(filename)
            if ext.lower() in model_extensions:
                base = os.path.splitext(os.path.join(root, filename))[0]
                if not base.lower().endswith(VAE_SUFFIX):
                    total_models += 1
    
    processed = 0
    if progress_cb:
        progress_cb('Scanning models', 0, total_models)
    
    for root, _, files in os.walk(model_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            base, ext = os.path.splitext(filepath)
            if ext.lower() in model_extensions:
                # Skip VAE files
                if base.lower().endswith(VAE_SUFFIX):
                    print(f"Skipping VAE file: {filepath}")
                    continue

                # Check if '.civitai.info' exists already
                info_file = base + '.civitai.info'
                if os.path.exists(info_file):
                    with open(info_file, 'r', encoding='utf-8') as f:
                        model_info = json.load(f)
                else:
                    # Compute SHA256 hash
                    print(f"Computing SHA256 for {filepath}")
                    sha256_hash = compute_sha256_civitai(filepath, progress_cb)
                    if not sha256_hash:
                        print(f"Failed to compute SHA256 for {filepath}")
                        processed += 1
                        if progress_cb:
                            progress_cb('Scanning models', processed, total_models)
                        continue
                    
                    # Query Civitai API
                    print(f"Querying Civitai API for hash {sha256_hash}")
                    model_info = get_model_info_by_hash(sha256_hash)
                    if model_info:
                        with open(info_file, 'w', encoding='utf-8') as f:
                            json.dump(model_info, f, indent=4)
                        print(f"Saved model info to {info_file}")
                    else:
                        print(f"No matching model found on Civitai for {filepath}")
                        processed += 1
                        if progress_cb:
                            progress_cb('Scanning models', processed, total_models)
                        continue  # Skip to next file

                # Check if preview image already exists
                preview_files = [base + ext for ext in ['.preview.png', '.preview.jpg', '.preview.gif', '.preview.webp']]
                preview_exists = any(os.path.exists(f) for f in preview_files)
                
                if not preview_exists:
                    get_preview_image(base, model_info, max_size_preview, skip_nsfw_preview)

                # Respect rate limiting
                time.sleep(0.5)
                
            processed += 1
            if progress_cb:
                progress_cb('Scanning models', processed, total_models)
    
    print("Civitai scanning complete.")
    return processed

# ============================================================================
# SORTING TENSORS BY INFO
# ============================================================================

def get_file_hash_sorting(filepath):
    """Compute SHA256 hash for file verification during sorting."""
    with open(filepath, 'rb') as file:
        return hashlib.sha256(file.read()).hexdigest()

def safe_move_file(src, dest, progress_cb=None):
    """Safely move files by copying and verifying before deleting the source."""
    original_dest = dest
    base, ext = os.path.splitext(dest)
    counter = 1

    # If a file with the same name exists, iterate the filename
    while os.path.exists(original_dest):
        # If the existing file is exactly the same, remove the source
        if get_file_hash_sorting(src) == get_file_hash_sorting(original_dest) and os.path.getsize(src) == os.path.getsize(original_dest):
            print(f"Duplicate file found, removing source: {src}")
            os.remove(src)  # Only remove the source file if the copy is verified
            return
        else:
            original_dest = f"{base}_{counter}{ext}"
            counter += 1

    # Perform the file copy
    print(f"Moving {os.path.basename(src)} to {os.path.dirname(original_dest)}")
    shutil.copy2(src, original_dest)
    time.sleep(TRANSFER_DELAY)  # Wait to ensure the copy is not rushed

    # Verify the copy by comparing hash and filesize
    if get_file_hash_sorting(src) == get_file_hash_sorting(original_dest) and os.path.getsize(src) == os.path.getsize(original_dest):
        os.remove(src)  # Only remove the source file if the copy is verified
        print(f"Successfully moved: {os.path.basename(src)}")
    else:
        print(f"Failed to verify the copy of {src}. Original remains in place.")
        os.remove(original_dest)  # Remove failed copy

def move_files_to_model_dir(file, info_file, preview_files, base_dir, model_type, type_dirs, progress_cb=None):
    """Move model files to appropriate directory structure."""
    if model_type in type_dirs:
        dest_dir = base_dir
        os.makedirs(dest_dir, exist_ok=True)

        dest_file = os.path.join(dest_dir, os.path.basename(file))
        dest_info_file = os.path.join(dest_dir, os.path.basename(info_file))

        # Move main file and info file
        safe_move_file(file, dest_file, progress_cb)
        safe_move_file(info_file, dest_info_file, progress_cb)
        
        # Move all preview files
        for preview_file in preview_files:
            if os.path.exists(preview_file):
                dest_preview_file = os.path.join(dest_dir, os.path.basename(preview_file))
                safe_move_file(preview_file, dest_preview_file, progress_cb)

def find_all_preview_files(base_filename):
    """Find all preview files for a given base filename with any supported extension."""
    preview_files = []
    for ext in PREVIEW_EXTENSIONS:
        preview_path = base_filename + ext
        if os.path.exists(preview_path):
            preview_files.append(preview_path)
    return preview_files

def sort_civitai_files(base_dir, extensions=None, info_ext=None, type_dirs=None, progress_cb=None):
    """Main sorting function to organize files based on Civitai info."""
    if extensions is None:
        extensions = NEURALNETS_EXTENSIONS
    if info_ext is None:
        info_ext = INFO_EXTENSION
    if type_dirs is None:
        type_dirs = TYPE_FOLDERNAME
    
    print(f"Starting file sorting in: {base_dir}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Collect all files with the given extensions
    all_files = []
    for ext in extensions:
        found_files = glob.glob(os.path.join(base_dir, '**', f'*{ext}'), recursive=True)
        all_files.extend(found_files)

    total_files = len(all_files)
    processed = 0
    moved_files = 0
    
    if total_files == 0:
        print("No files found to sort.")
        return 0
    
    print(f"Found {total_files} files to process")
    
    if progress_cb:
        progress_cb('Sorting files', 0, total_files)

    for file in all_files:
        base_filename = os.path.splitext(file)[0]
        info_file = base_filename + info_ext
        preview_files = find_all_preview_files(base_filename)
        
        if os.path.exists(info_file):
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                model_type = info.get('model', {}).get('type', '')
                base_model_type = info.get('baseModel', '')
                
                if model_type and base_model_type:
                    final_dir = os.path.join(base_dir, base_model_type, model_type)
                    print(f"Processing: {os.path.basename(file)} -> {base_model_type}/{model_type}")
                    if preview_files:
                        print(f"  Found {len(preview_files)} preview file(s): {[os.path.basename(p) for p in preview_files]}")
                    move_files_to_model_dir(file, info_file, preview_files, final_dir, model_type, type_dirs, progress_cb)
                    moved_files += 1
                else:
                    print(f"Skipping {os.path.basename(file)}: Missing model type or base model info")
            except Exception as e:
                print(f"Error processing {file}: {e}")
        else:
            print(f"Skipping {os.path.basename(file)}: No .civitai.info file found")
        
        processed += 1
        if progress_cb:
            progress_cb('Sorting files', processed, total_files)
    
    print(f"\nSorting completed!")
    print(f"- Files processed: {processed}")
    print(f"- Files moved: {moved_files}")
    
    return moved_files

# ============================================================================
# CATEGORY SORTING BY NSFW/POI
# ============================================================================

def get_file_hash_category(filepath: str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash for file verification during category sorting."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error calculating hash for {filepath}: {e}")
        raise

def safe_copy_file_category(src: str, dest: str) -> str:
    """Safely copy file with verification and duplicate handling."""
    print(f"Copying: {os.path.basename(src)} -> {dest}")
    original_dest = dest
    base, ext = os.path.splitext(dest)
    counter = 1
    
    # Handle existing files
    while os.path.exists(original_dest):
        try:
            if (get_file_hash_category(src) == get_file_hash_category(original_dest) and
                    os.path.getsize(src) == os.path.getsize(original_dest)):
                print(f"Destination file {original_dest} already exists and is identical.")
                return original_dest
        except Exception as e:
            print(f"Warning: Error comparing files {src} and {original_dest}: {e}")
            
        original_dest = f"{base}_{counter}{ext}"
        counter += 1
    
    # Copy and verify
    try:
        shutil.copy2(src, original_dest)
        time.sleep(TRANSFER_DELAY)
        
        # Verify copy
        if (get_file_hash_category(src) == get_file_hash_category(original_dest) and
                os.path.getsize(src) == os.path.getsize(original_dest)):
            print(f"Successfully copied and verified: {os.path.basename(original_dest)}")
            return original_dest
        else:
            os.remove(original_dest)
            raise Exception("Copy verification failed")
    except Exception as e:
        print(f"Error copying {src} to {original_dest}: {e}")
        raise

def load_json_safely_category(filepath: str) -> dict:
    """Load JSON from civitai.info file with error handling."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                raise ValueError("File is empty")
            return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"JSON decode error in {filepath}: {e}")
        raise
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        raise

def find_associated_file_category(file_path: str, suffixes) -> str:
    """Find associated file with given suffix(es)."""
    if isinstance(suffixes, str):
        suffixes = [suffixes]
    
    base_name = os.path.splitext(file_path)[0]
    
    for suffix in suffixes:
        candidate = base_name + suffix
        if os.path.exists(candidate):
            return candidate
    return None

def sort_files_by_category(base_dir: str, extensions=None, info_ext=None, preview_exts=None, progress_cb=None):
    """Sort files into NSFW and POI categories based on civitai.info metadata."""
    if extensions is None:
        extensions = NEURALNETS_EXTENSIONS
    if info_ext is None:
        info_ext = INFO_EXTENSION
    if preview_exts is None:
        preview_exts = PREVIEW_EXTENSIONS
    
    print(f"\n[Starting category sorting in: {base_dir}]")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(base_dir):
        print(f"Error: Directory does not exist: {base_dir}")
        return 0
    
    # Find files to process
    files = [
        f for f in os.listdir(base_dir)
        if os.path.isfile(os.path.join(base_dir, f)) and 
        os.path.splitext(f)[1].lower() in extensions
    ]
    
    if not files:
        print(f"No files found with extensions {extensions} in {base_dir}")
        return 0
    
    print(f"Found {len(files)} file(s) to process")
    total_files = len(files)
    processed = 0
    moved_files = 0
    
    for file in files:
        file_path = os.path.join(base_dir, file)
        print(f"\nProcessing: {file}")
        
        # Find associated info file
        info_path = find_associated_file_category(file_path, info_ext)
        if not info_path:
            print(f"No info file found for {file}. Skipping.")
            processed += 1
            if progress_cb:
                progress_cb('Processing files', processed, total_files)
            continue
        
        # Find preview file
        preview_path = find_associated_file_category(file_path, preview_exts)
        if preview_path:
            print(f"Found preview: {os.path.basename(preview_path)}")
        
        try:
            # Load and parse info file
            info = load_json_safely_category(info_path)
            model_info = info.get("model", {})
            nsfw_flag = model_info.get("nsfw", False)
            poi_flag = model_info.get("poi", False)
            
            print(f"Flags: nsfw={nsfw_flag}, poi={poi_flag}")
            
            # Determine destinations
            destinations = []
            if nsfw_flag:
                destinations.append(os.path.join(base_dir, "nsfw"))
            if poi_flag:
                destinations.append(os.path.join(base_dir, "poi"))
            
            if not destinations:
                print(f"File {file} does not meet any category criteria. Skipping.")
                processed += 1
                if progress_cb:
                    progress_cb('Processing files', processed, total_files)
                continue
            
            # Copy to each destination
            copy_success = True
            for dest_dir in destinations:
                os.makedirs(dest_dir, exist_ok=True)
                print(f"Copying files to: {dest_dir}")
                
                try:
                    # Copy main file
                    dest_file = os.path.join(dest_dir, os.path.basename(file_path))
                    safe_copy_file_category(file_path, dest_file)
                    
                    # Copy info file
                    dest_info = os.path.join(dest_dir, os.path.basename(info_path))
                    safe_copy_file_category(info_path, dest_info)
                    
                    # Copy preview if exists
                    if preview_path:
                        dest_preview = os.path.join(dest_dir, os.path.basename(preview_path))
                        safe_copy_file_category(preview_path, dest_preview)
                    
                except Exception as e:
                    print(f"Error copying files to {dest_dir}: {e}")
                    copy_success = False
                    break
            
            # Remove originals if all copies succeeded
            if copy_success:
                print("Removing original files...")
                try:
                    os.remove(file_path)
                    os.remove(info_path)
                    if preview_path:
                        os.remove(preview_path)
                    print("Original files removed successfully")
                    moved_files += 1
                except Exception as e:
                    print(f"Error removing original files: {e}")
            else:
                print("Skipping removal of originals due to copy errors")
        
        except Exception as e:
            print(f"Error processing {file}: {e}")
        
        processed += 1
        if progress_cb:
            progress_cb('Processing files', processed, total_files)
    
    print(f"\nCategory sorting completed!")
    print(f"- Files processed: {processed}")
    print(f"- Files moved: {moved_files}")
    
    return moved_files

class TextRedirector:
    def __init__(self, widget):
        self.widget = widget
    def write(self, s):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, s)
        self.widget.see(tk.END)
        self.widget.configure(state='disabled')
    def flush(self):
        pass

class OutputMultiplexer:
    """
     stream multiplexer that redirects output to multiple destinations.
    
    This class allows simultaneous output to multiple streams (e.g., GUI widget and file buffer)
    while maintaining proper error handling and stream interface compatibility.
    
    Args:
        *streams: Variable number of output streams that implement write() and flush() methods
    
    Example:
        multiplexer = OutputMultiplexer(gui_redirector, file_buffer)
        sys.stdout = multiplexer  # Now all print() goes to both destinations
    """
    
    def __init__(self, *streams):
        if not streams:
            raise ValueError("At least one output stream must be provided")
        self.streams = streams
        self._validate_streams()
    
    def _validate_streams(self):
        """Validate that all streams have required methods."""
        for i, stream in enumerate(self.streams):
            if not hasattr(stream, 'write'):
                raise TypeError(f"Stream {i} does not have a write() method")
            if not hasattr(stream, 'flush'):
                raise TypeError(f"Stream {i} does not have a flush() method")
    
    def write(self, text):
        """Write text to all configured streams."""
        if not isinstance(text, str):
            text = str(text)
        
        for stream in self.streams:
            try:
                stream.write(text)
            except Exception as e:
                # Continue writing to other streams even if one fails
                print(f"Warning: Failed to write to stream {stream}: {e}", file=sys.__stderr__)
    
    def flush(self):
        """Flush all configured streams."""
        for stream in self.streams:
            try:
                stream.flush()
            except Exception as e:
                # Continue flushing other streams even if one fails
                print(f"Warning: Failed to flush stream {stream}: {e}", file=sys.__stderr__)

# ============================================================================
# REMOVE DUPLICATES 
# ============================================================================
def group_files_by_size(files: List[str], progress_cb=None) -> Dict[int, List[str]]:
    """
    First pass: Group files by size to identify potential duplicates.
    """
    size_dict: Dict[int, List[str]] = {}
    print("\n[1/4] Analyzing file sizes...")
    total = len(files)
    for idx, file in enumerate(files):
        try:
            size = os.path.getsize(file)
            size_dict.setdefault(size, []).append(file)
        except OSError as e:
            print(f"Error accessing file {file}: {e}")
        if progress_cb:
            progress_cb('Scanning files', idx+1, total)
    return size_dict

def filter_potential_duplicates(size_dict: Dict[int, List[str]]) -> Tuple[Dict[int, List[str]], FileStats]:
    """
    Filter out unique file sizes and collect statistics.
    """
    stats = FileStats(total_files=sum(len(files) for files in size_dict.values()))
    stats.unique_sizes = len(size_dict)
    
    # Only keep sizes with multiple files
    duplicate_sizes = {size: files for size, files in size_dict.items() if len(files) > 1}
    stats.potential_duplicates = sum(len(files) for files in duplicate_sizes.values())
    
    print(f"\nFile Analysis Summary:")
    print(f"- Total files scanned: {stats.total_files}")
    print(f"- Unique file sizes: {stats.unique_sizes}")
    print(f"- Files needing hash comparison: {stats.potential_duplicates}")
    
    return duplicate_sizes, stats

def load_hash_cache(cache_path: str) -> dict:
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load hash cache: {e}")
    return {}

def save_hash_cache(cache_path: str, cache: dict):
    try:
        with open(cache_path, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"Failed to save hash cache: {e}")

def get_file_hash(file_path: str, hash_cache: dict = None) -> str:
    """
    Computes the SHA-256 hash of a file, using a cache if provided.
    """
    try:
        stat = os.stat(file_path)
        cache_key = f"{file_path}|{stat.st_size}|{stat.st_mtime}"
        if hash_cache is not None:
            cached = hash_cache.get(cache_key)
            if cached:
                return cached
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if hash_cache is not None:
            hash_cache[cache_key] = digest
        return digest
    except Exception as e:
        print(f"Error hashing file {file_path}: {e}")
        return ""

def find_duplicate_files(size_dict: Dict[int, List[str]], hash_cache: dict, cache_path: str, progress_cb=None) -> Tuple[Dict[str, List[List[str]]], FileStats]:
    """
    Second pass: Identify duplicate files by comparing hashes of files with same size.
    Uses a persistent hash cache to avoid unnecessary rehashing.
    """
    print("\n[2/4] Comparing file contents...")
    duplicates: Dict[str, List[List[str]]] = {}
    stats = FileStats()
    updated = False

    total_groups = len(size_dict)
    for idx, (size, files) in enumerate(size_dict.items()):
        hash_dict: Dict[str, List[str]] = {}
        for file in files:
            file_hash = get_file_hash(file, hash_cache)
            if file_hash:
                hash_dict.setdefault(file_hash, []).append(file)
                updated = True
        for file_hash, file_list in hash_dict.items():
            if len(file_list) > 1:
                dir_path = os.path.dirname(file_list[0])
                duplicates.setdefault(dir_path, []).append(file_list)
                stats.bytes_saved += os.path.getsize(file_list[0]) * (len(file_list) - 1)
        if progress_cb:
            progress_cb('Comparing files', idx+1, total_groups)

    if updated:
        save_hash_cache(cache_path, hash_cache)

    if duplicates:
        print(f"\nDuplicate Files Found:")
        print(f"- Potential space savings: {stats.bytes_saved / (1024*1024):.2f} MB")
    else:
        print("\nNo duplicate files found!")
    
    return duplicates, stats

def get_file_priority(file_path: str) -> Tuple[float, bool, int]:
    """
    Determines which file to keep based on modification time and name.
    """
    try:
        mtime = os.path.getmtime(file_path)
        basename = os.path.basename(file_path)
        has_suffix = any(f"({i})" in basename for i in range(1, 10))
        name_length = len(basename)
        return (mtime, has_suffix, name_length)
    except Exception as e:
        print(f"Error getting priority for file {file_path}: {e}")
        return (float('inf'), True, float('inf'))

def delete_duplicate_files(duplicates: Dict[str, List[List[str]]], hash_cache: dict, progress_cb=None) -> int:
    """
    Final pass: Delete duplicate files while keeping one copy. Logs full details to the log window.
    """
    print("\n[3/4] Removing duplicate files...")
    total_deleted = 0
    total_groups = sum(len(groups) for groups in duplicates.values())
    processed = 0
    for dir_path, file_groups in duplicates.items():
        for file_list in file_groups:
            # Prepare detailed info for this duplicate group
            hashes = [(f, get_file_hash(f, hash_cache)) for f in file_list]
            sizes = [(f, os.path.getsize(f)) for f in file_list]
            print(f"\nDuplicate group in directory: {dir_path}")
            for f, h in hashes:
                print(f"  File: {f}")
                print(f"    Size: {os.path.getsize(f)} bytes, Hash: {h}")
            file_list.sort(key=get_file_priority)
            file_to_keep = file_list[0]
            print(f"-> Keeping: {file_to_keep} (oldest, no '(1)' suffix if possible)")
            files_to_delete = file_list[1:]
            for file_path in files_to_delete:
                try:
                    # Get hash before deleting the file
                    file_hash = get_file_hash(file_path, hash_cache)
                    os.remove(file_path)
                    print(f"-> Deleted: {file_path} (duplicate of {file_to_keep})")
                    print(f"   Reason: Same hash as kept file ({file_hash})")
                    total_deleted += 1
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
            processed += 1
            if progress_cb:
                progress_cb('Removing duplicates', processed, total_groups)
    return total_deleted

def remove_duplicate_files(folder_path: str, progress_cb=None) -> Tuple[int, FileStats]:
    """
    Main function to remove duplicate files in a folder. Uses a persistent hash cache.
    """
    print(f"\n[Starting duplicate file removal in: {folder_path}]")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Prepare hash cache path
    cache_path = os.path.join(folder_path, ".duplicate_hash_cache.json")
    hash_cache = load_hash_cache(cache_path)

    # Get all files recursively
    all_files = [os.path.join(dp, f) for dp, dn, fn in os.walk(folder_path) for f in fn]
    if not all_files:
        print("No files found in the specified directory!")
        return 0, FileStats()
    
    # First pass: Group by size
    size_dict = group_files_by_size(all_files, progress_cb)
    
    # Filter and get statistics
    duplicate_sizes, stats = filter_potential_duplicates(size_dict)
    if not duplicate_sizes:
        return 0, stats
    
    # Second pass: Find actual duplicates (with cache)
    duplicates, stats = find_duplicate_files(duplicate_sizes, hash_cache, cache_path, progress_cb)
    if not duplicates:
        return 0, stats
    
    # Final pass: Delete duplicates (detailed log)
    stats.files_deleted = delete_duplicate_files(duplicates, hash_cache, progress_cb)
    
    print(f"\n[4/4] Operation completed successfully!")
    print(f"- Total files deleted: {stats.files_deleted}")
    print(f"- Space saved: {stats.bytes_saved / (1024*1024):.2f} MB")
    
    return stats.files_deleted, stats

# ============================================================================
# USER INTERFACE
# ============================================================================
class TensorToolsUI:
    def __init__(self):
        self.root = None
        self.folder_entry = None
        self.progressbar = None
        self.progress_label = None
        self.log_text = None
        self.start_btn = None
        self.civitai_btn = None
        self.sort_btn = None
        self.category_btn = None
        self.setup_ui()
    
    def setup_ui(self):
        """Initialize the main UI components."""
        self.root = tk.Tk()
        self.root.title("Tensor Tools - Get Info , Sort by Model and Category , Remove Duplicates")
        self.root.geometry("700x600")
        self.root.configure(bg='#23272e')

        style_args = {
            'bg': '#23272e',
            'fg': '#e6e6e6',
            'insertbackground': '#e6e6e6',
            'highlightbackground': '#444',
            'highlightcolor': '#444',
            'selectbackground': '#444',
            'selectforeground': '#e6e6e6',
        }

        # Folder selection frame
        frame = tk.Frame(self.root, bg='#23272e', padx=10, pady=10)
        frame.pack(expand=False, fill='x')
        
        # Configure grid columns - middle column (entry) expands
        frame.columnconfigure(0, weight=0)  # Label column - fixed width
        frame.columnconfigure(1, weight=1)  # Entry column - expands
        frame.columnconfigure(2, weight=0)  # Browse button column - fixed width

        label = tk.Label(frame, text="Folder Path:", bg='#23272e', fg='#e6e6e6')
        label.grid(row=0, column=0, sticky='w', padx=(0, 5))

        self.folder_entry = tk.Entry(frame, **style_args)
        self.folder_entry.grid(row=0, column=1, sticky='ew', padx=(0, 5))

        browse_btn = tk.Button(frame, text="Browse", command=self.browse_folder, bg='#444', fg='#e6e6e6', activebackground='#666', activeforeground='#fff')
        browse_btn.grid(row=0, column=2, sticky='w')

        # Tool selection buttons
        tools_frame = tk.Frame(self.root, bg='#23272e', padx=10, pady=5)
        tools_frame.pack(expand=False, fill='x')
        
        tools_label = tk.Label(tools_frame, text="Select Tool:", bg='#23272e', fg='#e6e6e6', font=('Arial', 10, 'bold'))
        tools_label.pack(anchor='w')
        
        buttons_frame = tk.Frame(tools_frame, bg='#23272e')
        buttons_frame.pack(fill='x', pady=(5, 0))
        
        # Configure grid columns to expand equally
        for i in range(4):
            buttons_frame.columnconfigure(i, weight=1, uniform="button")
        
        self.civitai_btn = tk.Button(buttons_frame, text="Get Info from Civitai", command=self.start_civitai_scan, bg='#388e3c', fg='#ffffff', activebackground='#2e7d32', activeforeground='#fff')
        self.civitai_btn.grid(row=0, column=0, sticky='ew', padx=(0, 3))
        
        self.sort_btn = tk.Button(buttons_frame, text="Sort by Model Type", command=self.start_sorting, bg='#1976d2', fg='#ffffff', activebackground='#1565c0', activeforeground='#fff')
        self.sort_btn.grid(row=0, column=1, sticky='ew', padx=(3, 3))
        
        self.category_btn = tk.Button(buttons_frame, text="Sort by Category", command=self.start_category_sorting, bg='#1976d2', fg='#ffffff', activebackground='#1565c0', activeforeground='#fff')
        self.category_btn.grid(row=0, column=2, sticky='ew', padx=(3, 3))

        self.start_btn = tk.Button(buttons_frame, text="Remove Duplicates", command=self.start_removal, bg='#d32f2f', fg='#ffffff', activebackground='#b71c1c', activeforeground='#fff')
        self.start_btn.grid(row=0, column=3, sticky='ew', padx=(3, 0))

        # Progress bar
        self.progressbar = ttk.Progressbar(self.root, orient='horizontal', length=500, mode='determinate')
        self.progressbar.pack(pady=(10, 0))
        self.progress_label = tk.Label(self.root, text="", bg='#23272e', fg='#e6e6e6')
        self.progress_label.pack()

        # Log area
        log_label = tk.Label(self.root, text="Log:", bg='#23272e', fg='#e6e6e6')
        log_label.pack(anchor='w', padx=22)

        self.log_text = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=20, width=70, font=("Consolas", 10),
                                                bg='#181a1b', fg='#e6e6e6', insertbackground='#e6e6e6',
                                                selectbackground='#444', selectforeground='#fff')
        self.log_text.pack(expand=True, fill='both', padx=20, pady=(0, 20))
        self.log_text.configure(state='disabled')
    
    def browse_folder(self):
        """Browse and select a folder."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_path)
            print(f"Selected folder: {folder_path}")
        else:
            print("No folder selected.")
    
    def update_progress_ui(self, stage, current, total):
        """Update progress bar and label."""
        def _update():
            progress = (current / total) * 100 if total > 0 else 0
            self.progressbar['value'] = progress
            self.progress_label.config(text=f"{stage}: {current}/{total} ({progress:.1f}%)")
        self.root.after(0, _update)
    
    def _prepare_ui_for_operation(self):
        """Prepare UI for starting an operation."""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        self.progressbar['value'] = 0
        self.progress_label.config(text="")
    
    def _setup_logging(self):
        """Setup logging redirection for operations."""
        old_stdout = sys.stdout
        log_capture = io.StringIO()
        sys.stdout = OutputMultiplexer(TextRedirector(self.log_text), log_capture)
        return old_stdout, log_capture
    
    def _save_report(self, folder_path, log_content, report_prefix):
        """Save operation report to file."""
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        report_path = os.path.join(folder_path, f"{report_prefix}_{timestamp}.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(log_content)
        return report_path
    
    def start_civitai_scan(self):
        """Start Civitai scanning process."""
        folder_path = self.folder_entry.get()
        if not folder_path or not os.path.isdir(folder_path):
            print("Error: Please enter a valid folder path.")
            return
        
        self._prepare_ui_for_operation()
        self.civitai_btn.config(state='disabled')
        
        # Start the operation in a separate thread
        threading.Thread(target=self._run_civitai_scan, args=(folder_path,), daemon=True).start()
    
    def _run_civitai_scan(self, folder_path):
        """Execute Civitai scanning operation."""
        old_stdout, log_capture = self._setup_logging()
        try:
            processed = scan_civitai_models(folder_path, progress_cb=self.update_progress_ui)
            self._save_report(folder_path, log_capture.getvalue(), "00_civitai_scan_report")
            self._show_civitai_completion(processed, folder_path)
        finally:
            os.sys.stdout = old_stdout
    
    def _show_civitai_completion(self, processed, folder_path):
        """Show completion message for Civitai scan."""
        def show_done():
            print("\n[Civitai scan completed]")
            print(f"Models processed: {processed}")
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            report_path = os.path.join(folder_path, f"00_civitai_scan_report_{timestamp}.txt")
            print(f"Report saved to: {report_path}")
            self.civitai_btn.config(state='normal')
            self.progress_label.config(text="Done.")
        self.root.after(0, show_done)
    
    def start_sorting(self):
        """Start sorting process."""
        folder_path = self.folder_entry.get()
        if not folder_path or not os.path.isdir(folder_path):
            print("Error: Please enter a valid folder path.")
            return
        
        self._prepare_ui_for_operation()
        self.sort_btn.config(state='disabled')
        
        # Start the operation in a separate thread
        threading.Thread(target=self._run_sorting, args=(folder_path,), daemon=True).start()
    
    def _run_sorting(self, folder_path):
        """Execute sorting operation."""
        old_stdout, log_capture = self._setup_logging()
        try:
            moved_files = sort_civitai_files(folder_path, progress_cb=self.update_progress_ui)
            self._save_report(folder_path, log_capture.getvalue(), "00_sorting_report")
            self._show_sorting_completion(moved_files, folder_path)
        finally:
            os.sys.stdout = old_stdout
    
    def _show_sorting_completion(self, moved_files, folder_path):
        """Show completion message for sorting."""
        def show_done():
            print("\n[Sorting completed]")
            print(f"Files moved: {moved_files}")
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            report_path = os.path.join(folder_path, f"00_sorting_report_{timestamp}.txt")
            print(f"Report saved to: {report_path}")
            self.sort_btn.config(state='normal')
            self.progress_label.config(text="Done.")
        self.root.after(0, show_done)
    
    def start_removal(self):
        """Start duplicate removal process."""
        folder_path = self.folder_entry.get()
        if not folder_path or not os.path.isdir(folder_path):
            print("Error: Please enter a valid folder path.")
            return
        
        self._prepare_ui_for_operation()
        self.start_btn.config(state='disabled')
        
        # Start the operation in a separate thread
        threading.Thread(target=self._run_removal, args=(folder_path,), daemon=True).start()
    
    def _run_removal(self, folder_path):
        """Execute duplicate removal operation."""
        old_stdout, log_capture = self._setup_logging()
        try:
            total_deleted, stats = remove_duplicate_files(folder_path, progress_cb=self.update_progress_ui)
            self._save_report(folder_path, log_capture.getvalue(), "00_duplicate_removal_report")
            self._show_removal_completion(stats, folder_path)
        finally:
            os.sys.stdout = old_stdout
    
    def _show_removal_completion(self, stats, folder_path):
        """Show completion message for duplicate removal."""
        def show_done():
            print("\n[Process completed]")
            print(f"Files analyzed: {stats.total_files}")
            print(f"Files deleted: {stats.files_deleted}")
            print(f"Space saved: {stats.bytes_saved / (1024*1024):.2f} MB")
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            report_path = os.path.join(folder_path, f"00_duplicate_removal_report_{timestamp}.txt")
            print(f"Report saved to: {report_path}")
            self.start_btn.config(state='normal')
            self.progress_label.config(text="Done.")
        self.root.after(0, show_done)
    
    def start_category_sorting(self):
        """Start the category sorting process."""
        folder_path = self.folder_entry.get().strip()
        if not folder_path:
            print("Warning: Please select a folder first.")
            return
        
        if not os.path.exists(folder_path):
            print("Error: Selected folder does not exist.")
            return
        
        self._prepare_ui_for_operation()
        
        # Start category sorting in a separate thread
        thread = threading.Thread(target=self._run_category_sorting, args=(folder_path,))
        thread.daemon = True
        thread.start()
    
    def _run_category_sorting(self, folder_path):
        """Run category sorting in a separate thread."""
        old_stdout, log_capture = self._setup_logging()
        
        try:
            moved_files = sort_files_by_category(
                folder_path,
                progress_cb=self.update_progress_ui
            )
            
            self._show_category_completion(moved_files, folder_path, log_capture)
            
        except Exception as e:
            print(f"Error during category sorting: {e}")
            print(f"Category sorting failed: {e}")
        finally:
            sys.stdout = old_stdout
    
    def _show_category_completion(self, moved_files, folder_path, log_capture):
        """Show completion message and save report for category sorting."""
        def show_done():
            print("\n[Category Sorting Complete]")
            print(f"Category sorting completed!")
            print(f"Files moved: {moved_files}")
            print(f"Files have been sorted into 'nsfw' and 'poi' subfolders based on their Civitai metadata.")
            
            # Save detailed report
            report_path = self._save_report(folder_path, log_capture.getvalue(), "00_category_sorting")
            print(f"Report saved to: {report_path}")
            self.start_btn.config(state='normal')
            self.progress_label.config(text="Done.")
        self.root.after(0, show_done)
    
    def run(self):
        """Start the main UI loop."""
        self.root.mainloop()

if __name__ == "__main__":
    app = TensorToolsUI()
    app.run()
