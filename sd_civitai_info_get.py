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

# For Tkinter GUI (if available)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except ImportError:
    tk = None

# Constants
VAE_SUFFIX = '.vae'
MODEL_EXTENSIONS = ['.ckpt', '.safetensors', '.sft', '.pt']
CIVITAI_API_URL = 'https://civitai.com/api/v1/model-versions/by-hash/'

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

def download_image(url, save_path):
    """Download an image from a URL."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            with open(save_path, 'wb') as f, tqdm(
                total=total_size, unit='B', unit_scale=True,
                desc=f"Downloading {os.path.basename(save_path)}", leave=False
            ) as pbar:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
    except requests.RequestException as e:
        print(f"Request error while downloading image from {url}: {e}")

def get_full_size_image_url(image_url, width):
    """Modify the image URL to request the full-size image."""
    return re.sub(r'/width=\d+/', f'/width={width}/', image_url)

def is_valid_png(filepath):
    """Check if the file is a valid PNG by comparing its header."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
            return header == PNG_SIGNATURE
    except Exception:
        return False

def is_valid_mp4(filepath):
    """Check if the file is a valid MP4 by looking for the 'ftyp' box."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(12)
            if len(header) < 12:
                return False
            # In MP4, bytes 4-8 are usually 'ftyp'
            return header[4:8] == b'ftyp'
    except Exception:
        return False

def is_valid_webm(filepath):
    """Check if the file is a valid WebM by checking for the EBML header."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(4)
            return header == b'\x1A\x45\xDF\xA3'
    except Exception:
        return False

def validate_preview_file(base):
    """
    Validate the downloaded preview file.

    If the file saved as <base>.preview.png is not a valid PNG, try renaming it
    to <base>.preview.mp4 and test for a minimal MP4 signature. (You can also try
    a WebM check if desired.)
    """
    png_file = base + '.preview.png'
    if os.path.exists(png_file):
        if is_valid_png(png_file):
            print(f"Valid PNG preview image: {png_file}")
            return
        else:
            print(f"Invalid PNG file detected: {png_file}. Attempting to rename and validate as MP4.")
            mp4_file = base + '.preview.mp4'
            if os.path.exists(mp4_file):
                os.remove(mp4_file)
            os.rename(png_file, mp4_file)
            if is_valid_mp4(mp4_file):
                print(f"Valid MP4 preview video: {mp4_file}")
                return
            else:
                print("File is not a valid MP4. Attempting to rename and validate as WebM.")
                webm_file = base + '.preview.webm'
                if os.path.exists(webm_file):
                    os.remove(webm_file)
                os.rename(mp4_file, webm_file)
                if is_valid_webm(webm_file):
                    print(f"Valid WebM preview video: {webm_file}")
                    return
                else:
                    print(f"Downloaded file is not a valid PNG, MP4, or WebM: {webm_file}")

def get_preview_image(base, model_info, max_size_preview=False, skip_nsfw_preview=False):
    """Download the preview image for a model and validate its format."""
    preview_image_file = base + '.preview.png'
    if os.path.exists(preview_image_file):
        print(f"Preview image already exists: {preview_image_file}")
        return
    if 'images' in model_info:
        for image_info in model_info['images']:
            if skip_nsfw_preview and image_info.get('nsfw'):
                print("Skipping NSFW image")
                continue
            image_url = image_info.get('url')
            if image_url:
                if max_size_preview and 'width' in image_info:
                    width = image_info['width']
                    image_url = get_full_size_image_url(image_url, width)
                print(f"Downloading preview image from {image_url}")
                download_image(image_url, preview_image_file)
                print(f"Saved preview image to {preview_image_file}")
                # Validate the downloaded file (and possibly rename if needed)
                validate_preview_file(base)
                # Only download the first valid image
                break
    else:
        print("No images found in model info.")

def scan_models(model_dir, model_extensions, max_size_preview=False, skip_nsfw_preview=False):
    """Scan model directory and process each model file."""
    total_models = sum(len(files) for _, _, files in os.walk(model_dir))
    with tqdm(total=total_models, desc="Processing models") as pbar:
        for root, _, files in os.walk(model_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                base, ext = os.path.splitext(filepath)
                if ext.lower() in model_extensions:
                    # Skip VAE files
                    if base.lower().endswith(VAE_SUFFIX):
                        print(f"Skipping VAE file: {filepath}")
                        pbar.update(1)
                        continue

                    # Check if '.civitai.info' exists already
                    info_file = base + '.civitai.info'
                    if os.path.exists(info_file):
                        with open(info_file, 'r', encoding='utf-8') as f:
                            model_info = json.load(f)
                    else:
                        # Compute SHA256 hash
                        print(f"Computing SHA256 for {filepath}")
                        sha256_hash = compute_sha256(filepath)
                        if not sha256_hash:
                            print(f"Failed to compute SHA256 for {filepath}")
                            pbar.update(1)
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
                            pbar.update(1)
                            continue  # Skip to next file

                    # Check if preview image already exists
                    preview_image_file = base + '.preview.png'
                    if not os.path.exists(preview_image_file):
                        get_preview_image(base, model_info, max_size_preview, skip_nsfw_preview)

                    # Respect rate limiting
                    time.sleep(0.5)
                pbar.update(1)
    print("Scanning complete.")

def run_gui():
    """Launch a simple Tkinter GUI for scanning models."""
    if tk is None:
        print("Tkinter is not available on this system.")
        return

    root = tk.Tk()
    root.title("Civitai Model Scanner")

    # Folder path label and entry
    folder_label = tk.Label(root, text="Model Directory:")
    folder_label.grid(row=0, column=0, padx=5, pady=5)

    folder_entry = tk.Entry(root, width=50)
    folder_entry.grid(row=0, column=1, padx=5, pady=5)

    def browse_folder():
        folder_selected = filedialog.askdirectory()
        folder_entry.delete(0, tk.END)
        folder_entry.insert(0, folder_selected)

    browse_button = tk.Button(root, text="Browse", command=browse_folder)
    browse_button.grid(row=0, column=2, padx=5, pady=5)

    def start_scanning():
        model_dir = folder_entry.get()
        if not model_dir or not os.path.isdir(model_dir):
            messagebox.showerror("Error", "Please specify a valid model directory.")
            return
        # Run the scan in a separate thread so the UI stays responsive
        threading.Thread(
            target=scan_models, args=(model_dir, MODEL_EXTENSIONS, False, False),
            daemon=True
        ).start()

    start_button = tk.Button(root, text="Start Scanning", command=start_scanning)
    start_button.grid(row=1, column=1, padx=5, pady=10)

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

        args = parser.parse_args()
        scan_models(args.model_dir, args.extensions, args.max_size_preview, args.skip_nsfw_preview)
    else:
        run_gui()
