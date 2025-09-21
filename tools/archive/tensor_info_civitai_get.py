"""
Diffusion Tensor Artifact Civitai Info Get
for each tensor file gets hash then queries using civitai API downloading info and preview image
opens a GUI or can be run as command line if args are provided
CLI example: python sd_civitai_info_get.py --model_dir "models/" --skip_nsfw_preview
"""
import os
import sys
import requests
import hashlib
import json
import time
import re
import argparse
from tqdm import tqdm
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

# Constants
VAE_SUFFIX = '.vae'
MODEL_EXTENSIONS = ['.ckpt', '.safetensors', '.sft', '.pt']
CIVITAI_API_URL = 'https://civitai.com/api/v1/model-versions/by-hash/'
SETTINGS_FILE = "sd_civitai_info_get_settings.json"

# PNG file signature (first 8 bytes)
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

def compute_sha256(file_path):
    """Compute the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    total_size = os.path.getsize(file_path)
    with open(file_path, "rb") as f, tqdm(
        total=total_size, unit='B', unit_scale=True,
        desc=f"Hashing {os.path.basename(file_path)}", leave=False
    ) as pbar:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
            pbar.update(len(byte_block))
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

def download_image(url, save_path):
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
            
            with open(temp_path, 'wb') as f, tqdm(
                total=total_size, unit='B', unit_scale=True,
                desc=f"Downloading preview", leave=False
            ) as pbar:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
            
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

def scan_models(model_dir, model_extensions, max_size_preview=False, skip_nsfw_preview=False, progress_callback=None, log_callback=None):
    """Scan model directory and process each model file. Calls progress_callback and log_callback if provided."""
    total_models = sum(len(files) for _, _, files in os.walk(model_dir))
    processed = 0
    if progress_callback:
        progress_callback(0, total_models)
    with tqdm(total=total_models, desc="Processing models", disable=True) as pbar:
        for root, _, files in os.walk(model_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                base, ext = os.path.splitext(filepath)
                if ext.lower() in model_extensions:
                    # Skip VAE files
                    if base.lower().endswith(VAE_SUFFIX):
                        if log_callback:
                            log_callback(f"Skipping VAE file: {filepath}")
                        pbar.update(1)
                        processed += 1
                        if progress_callback:
                            progress_callback(processed, total_models)
                        continue

                    # Check if '.civitai.info' exists already
                    info_file = base + '.civitai.info'
                    if os.path.exists(info_file):
                        with open(info_file, 'r', encoding='utf-8') as f:
                            model_info = json.load(f)
                    else:
                        # Compute SHA256 hash
                        if log_callback:
                            log_callback(f"Computing SHA256 for {filepath}")
                        sha256_hash = compute_sha256(filepath)
                        if not sha256_hash:
                            if log_callback:
                                log_callback(f"Failed to compute SHA256 for {filepath}")
                            pbar.update(1)
                            processed += 1
                            if progress_callback:
                                progress_callback(processed, total_models)
                            continue
                        # Query Civitai API
                        if log_callback:
                            log_callback(f"Querying Civitai API for hash {sha256_hash}")
                        model_info = get_model_info_by_hash(sha256_hash)
                        if model_info:
                            with open(info_file, 'w', encoding='utf-8') as f:
                                json.dump(model_info, f, indent=4)
                            if log_callback:
                                log_callback(f"Saved model info to {info_file}")
                        else:
                            if log_callback:
                                log_callback(f"No matching model found on Civitai for {filepath}")
                            pbar.update(1)
                            processed += 1
                            if progress_callback:
                                progress_callback(processed, total_models)
                            continue  # Skip to next file

                    # Check if preview image already exists
                    preview_image_file = base + '.preview.png'
                    if not os.path.exists(preview_image_file):
                        get_preview_image(base, model_info, max_size_preview, skip_nsfw_preview)

                    # Respect rate limiting
                    time.sleep(0.5)
                pbar.update(1)
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_models)
    if log_callback:
        log_callback("Scanning complete.")

def run_gui():
    """Launch a dark mode Tkinter GUI for scanning models, with progress bar and log."""
    if tk is None:
        print("Tkinter is not available on this system.")
        return

    # Load settings
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}

    # Dark mode colors
    bg_color = "#23272e"
    fg_color = "#f0f0f0"
    entry_bg = "#23272e"
    entry_fg = "#f0f0f0"
    btn_bg = "#2c313c"
    btn_fg = "#f0f0f0"
    log_bg = "#181A1B"
    log_fg = "#b0b0b0"
    prog_bg = "#333"

    root = tk.Tk()
    root.title("Civitai Model Scanner")
    root.configure(bg=bg_color)

    # Folder path label and entry
    folder_label = tk.Label(root, text="Model Directory:", bg=bg_color, fg=fg_color)
    folder_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

    folder_entry = tk.Entry(root, width=50, bg=entry_bg, fg=entry_fg, insertbackground=fg_color)
    folder_entry.grid(row=0, column=1, padx=5, pady=5)
    if settings.get("last_model_dir"):
        folder_entry.insert(0, settings["last_model_dir"])

    def browse_folder():
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            folder_entry.delete(0, tk.END)
            folder_entry.insert(0, folder_selected)

    browse_button = tk.Button(root, text="Browse", command=browse_folder, bg=btn_bg, fg=btn_fg, activebackground=prog_bg, activeforeground=fg_color)
    browse_button.grid(row=0, column=2, padx=5, pady=5)

    # Progress bar
    progress_var = tk.DoubleVar()
    progress_bar = tk.Scale(root, variable=progress_var, from_=0, to=100, orient="horizontal", showvalue=False, length=400, bg=bg_color, troughcolor=prog_bg, highlightthickness=0)
    progress_bar.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    # Log area (single line)
    log_var = tk.StringVar()
    log_label = tk.Label(root, textvariable=log_var, bg=log_bg, fg=log_fg, anchor="w", font=("Consolas", 9))
    log_label.grid(row=2, column=1, padx=5, pady=(0, 10), sticky="ew")

    # Thread communication queue
    gui_queue = queue.Queue()

    def gui_progress_callback(current, total):
        percent = (current / total) * 100 if total else 0
        gui_queue.put(("progress", percent))

    def gui_log_callback(msg):
        gui_queue.put(("log", msg))

    def process_gui_queue():
        try:
            while True:
                item = gui_queue.get_nowait()
                if item[0] == "progress":
                    progress_var.set(item[1])
                elif item[0] == "log":
                    log_var.set(item[1])
        except queue.Empty:
            pass
        root.after(100, process_gui_queue)

    process_gui_queue()

    def start_scanning():
        model_dir = folder_entry.get()
        if not model_dir or not os.path.isdir(model_dir):
            messagebox.showerror("Error", "Please specify a valid model directory.")
            return
        # Save last input to settings
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"last_model_dir": model_dir}, f, indent=2)
        except Exception:
            pass
        # Reset progress/log
        progress_var.set(0)
        log_var.set("")
        # Run the scan in a separate thread so the UI stays responsive
        threading.Thread(
            target=scan_models, args=(model_dir, MODEL_EXTENSIONS, False, False, gui_progress_callback, gui_log_callback),
            daemon=True
        ).start()

    start_button = tk.Button(root, text="Start Scanning", command=start_scanning, bg=btn_bg, fg=btn_fg, activebackground=prog_bg, activeforeground=fg_color)
    start_button.grid(row=3, column=1, padx=5, pady=10)

    root.mainloop()

if __name__ == '__main__':
    # If command-line arguments are provided, run in CLI mode.
    # Otherwise, open the GUI.
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='Scan models and get info from Civitai.')
        parser.add_argument('--model_dir', type=str, required=True, help='Directory containing models to scan')
        parser.add_argument('--extensions', nargs='+', default=['.ckpt', '.safetensors'], help='List of model file extensions to scan')
        parser.add_argument('--max_size_preview', action='store_true', help='Download max size preview images')
        parser.add_argument('--skip_nsfw_preview', action='store_true', help='Skip downloading NSFW preview images')
        # example command showing all args =
        # python sd_civitai_info_get.py --model_dir "models/" --extensions ".ckpt" ".safetensors" --max_size_preview --skip_nsfw_preview

        args = parser.parse_args()
        scan_models(args.model_dir, args.extensions, args.max_size_preview, args.skip_nsfw_preview)
    else:
        run_gui()
