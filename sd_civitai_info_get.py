import os
import requests
import hashlib
import json
import time
import re
import argparse
from tqdm import tqdm

# Constants
VAE_SUFFIX = '.vae'
MODEL_EXTENSIONS = ['.ckpt', '.safetensors']
CIVITAI_API_URL = 'https://civitai.com/api/v1/model-versions/by-hash/'

def compute_sha256(file_path):
    """Compute the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    total_size = os.path.getsize(file_path)
    with open(file_path, "rb") as f, tqdm(
        total=total_size, unit='B', unit_scale=True, desc=f"Hashing {os.path.basename(file_path)}", leave=False
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
                total=total_size, unit='B', unit_scale=True, desc=f"Downloading {os.path.basename(save_path)}", leave=False
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

def get_preview_image(base, model_info, max_size_preview=False, skip_nsfw_preview=False):
    """Download the preview image for a model."""
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

                    # Initialize flags
                    info_file_exists = False
                    preview_image_exists = False

                    # Check if '.civitai.info' exists
                    info_file = base + '.civitai.info'
                    if os.path.exists(info_file):
                        info_file_exists = True
                        # Load model_info from existing .civitai.info file
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
                            # Save model info
                            with open(info_file, 'w', encoding='utf-8') as f:
                                json.dump(model_info, f, indent=4)
                            print(f"Saved model info to {info_file}")
                        else:
                            print(f"No matching model found on Civitai for {filepath}")
                            pbar.update(1)
                            continue  # Skip to next file

                    # Check if '.preview.png' exists
                    preview_image_file = base + '.preview.png'
                    if os.path.exists(preview_image_file):
                        preview_image_exists = True

                    # If preview image does not exist, attempt to download it
                    if not preview_image_exists:
                        get_preview_image(base, model_info, max_size_preview, skip_nsfw_preview)

                    # Respect rate limit
                    time.sleep(0.5)
                pbar.update(1)
    print("Scanning complete.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scan models and get info from Civitai.')
    parser.add_argument('--model_dir', type=str, required=True, help='Directory containing models to scan')
    parser.add_argument('--extensions', nargs='+', default=['.ckpt', '.safetensors'], help='List of model file extensions to scan')
    parser.add_argument('--max_size_preview', action='store_true', help='Download max size preview images')
    parser.add_argument('--skip_nsfw_preview', action='store_true', help='Skip downloading NSFW preview images')

    args = parser.parse_args()

    model_dir = args.model_dir

    scan_models(model_dir, args.extensions, args.max_size_preview, args.skip_nsfw_preview)
