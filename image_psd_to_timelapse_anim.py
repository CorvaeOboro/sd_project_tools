# IMAGE PSD TO TIMELAPSE BATCH FOLDER
# make a timelapse video from PSD by layers 
# for each PSD found create a temp resized version , then for each layer save a list of the visibility , hide all the layers then make visible one at compounding the layer stack 
# EXAMPLE: python IMAGE_PSD_TO_GIF_FOLDER.py --input="D:\CODE\IMAGE_PSD_TO_GIF\TEST" --export_layered --make_gif
# current speed for 1000 pixel height psd of 600 layers is 1.5hour , 867 is 4hour , each layer iteration makes the process take longer ( starting at 3s per layer to 30s )
#//==============================================================================
import os # filepaths
#import numpy as np # math
import argparse # process args for running from CLI 
from pathlib import Path # file path , filename stems 
from PIL import Image # save images 
import glob # get all files of types with glob wildcards
import shutil

from tqdm import tqdm # progress bar 
from psd_tools import PSDImage # used to save out from psd , unfortunately cant do resizing so we are opening a photoshop instance via app 
# from moviepy.editor import ImageSequenceClip # make webm
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip # removed numpy dependecy

from win32com.client import Dispatch, GetActiveObject, constants # used for phtoshop instance via app for resizing 
import time # sleeping between saving temps
import gc
import psutil
import tkinter as tk
from tkinter import filedialog, messagebox
import sys
import io
import numpy as np

class TkinterConsole(io.StringIO):
    def __init__(self, log_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_callback = log_callback
    def write(self, s):
        if s.strip():
            self.log_callback(s)
        super().write(s)
    def flush(self):
        pass

def print_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    print(f"Memory Usage: {mem_info.rss / 1024 ** 2:.2f} MB")

#//==============================================================================
FIRST_FRAME_HOLD_TIME = 9
LAST_FRAME_HOLD_TIME = 35
GIF_SPEED = 130
WEBM_FRAME_RATE = 5 # average layer totals around 300-600 , 450/ 10 = 45 seconds , targeting 20 second timeplapse 
# framerate of 6 = 865 layers in 30 seconds
SIMILARITY_THRESHOLD = 1 # how different each layer needs to be , skipping empty or low impact layers 
EXCLUSION_FOLDERS = ["00_backup","backup"]
PHOTOSHOP_EXPORT_JSX = "image_psd_to_timelapse_export.jsx"
#//==============================================================================

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True, help='Path to the PSD file or directory containing PSD files')
    parser.add_argument('--max_size', type=int, default=1000, help='Maximum width or height of the image, keeping aspect ratio')
    parser.add_argument('--export_layered', action='store_true', default=True, help='Export images for each layer change')
    parser.add_argument('--make_gif', action='store_true', default=True, help='Generate a GIF showing the layer composition over time')
    parser.add_argument('--make_webm', action='store_true', default=True, help='Generate a WEBM video showing the layer composition over time')
    parser.add_argument('--loop_backward', action='store_true', help='Play the animation forwards then backwards')
    parser.add_argument('--frames_to_video', action='store_true', help='Process exported PNG frames to video/gif')
    parser.add_argument('--output_name', type=str, help='Name of the output file (without extension)')
    parser.add_argument('--file_type', type=str, default='webm', help='File type for frames_to_video mode')
    parser.add_argument('--export_layered_only', action='store_true', help='Only export layered images from PSDs, skipping animation/video phase')
    return parser.parse_args()

def extract_visible_layers(layer, layer_list):
    if layer.is_visible():
        if layer.is_group():
            for sublayer in layer:
                extract_visible_layers(sublayer, layer_list)
        else:
            layer_list.append(layer)

def psd_to_layered_images(input_psd_path, log_callback=print):
    """
    Enhanced: Recursively traverse all groups/subgroups, collecting visible pixel layers at any depth.
    Handles grouped layers and subgroups robustly.
    Adds detailed logging for debugging.
    """
    input_psd_path = Path(input_psd_path)
    log_callback(f"[psd_to_layered_images] Opening PSD: {input_psd_path}")
    psd = PSDImage.open(input_psd_path)
    log_callback(f"[psd_to_layered_images][DEBUG] PSD type: {type(psd)}")
    log_callback(f"[psd_to_layered_images][DEBUG] PSD dir: {dir(psd)}")
    log_callback(f"[psd_to_layered_images][DEBUG] PSD has {len(psd)} top-level layers.")

    all_layers = []
    def collect_layers(layer, parents_visible=True, parent_names=None, depth=0):
        if parent_names is None:
            parent_names = []
        name = getattr(layer, 'name', 'unnamed')
        visible = getattr(layer, 'visible', False)
        combined_visible = parents_visible and visible
        layer_type = type(layer).__name__
        # Robust pixel layer check
        has_pixels = False
        try:
            if hasattr(layer, 'has_pixels') and callable(layer.has_pixels):
                has_pixels = layer.has_pixels()
            # Also check kind == 'pixel' or composite() returns an image
            if not has_pixels and hasattr(layer, 'kind') and getattr(layer, 'kind', None) == 'pixel':
                has_pixels = True
            if not has_pixels:
                # Try composite()
                try:
                    img = layer.composite()
                    if img is not None and img.getbbox() is not None:
                        has_pixels = True
                except Exception:
                    pass
        except Exception:
            pass
        log_callback(f"[psd_to_layered_images] {'  '*depth}Layer: {'/'.join(parent_names + [name])} | Type: {layer_type} | Visible: {combined_visible} | Has Pixels: {has_pixels} | Keys: {list(layer.__dict__.keys()) if hasattr(layer, '__dict__') else 'N/A'}")
        if hasattr(layer, 'layers') and len(layer.layers) > 0:
            log_callback(f"[psd_to_layered_images] {'  '*depth}Group/Folder: {name} contains {len(layer.layers)} sublayers")
            for sub in layer.layers:
                collect_layers(sub, combined_visible, parent_names + [name], depth=depth+1)
        else:
            all_layers.append((layer, combined_visible, parent_names + [name], layer_type, has_pixels))
    # Instead of starting traversal at the root PSDImage, traverse its direct children (actual top-level layers)
    for layer in psd._layers:
        collect_layers(layer)
    log_callback(f"[psd_to_layered_images][DEBUG] All layers collected: {len(all_layers)}")
    for lyr, combined_visible, parent_names, layer_type, has_pixels in all_layers:
        log_callback(f"[psd_to_layered_images][SUMMARY] {'/'.join(parent_names)} | Type: {layer_type} | Visible: {combined_visible} | Has Pixels: {has_pixels}")
    # Only consider visible, pixel layers at any depth
    pixel_layers = []
    for lyr, combined_visible, parent_names, layer_type, has_pixels in all_layers:
        if combined_visible and has_pixels:
            pixel_layers.append((lyr, parent_names, layer_type))
    out_dir = input_psd_path.parent
    total = len(pixel_layers)
    size = psd.size
    mode = 'RGBA'
    log_callback(f"[psd_to_layered_images] Total exportable layers: {total}")
    if total == 0:
        log_callback("[psd_to_layered_images] No visible pixel layers found. Nothing to export.")
        return
    from PIL import Image
    for i in range(total):
        composite = Image.new(mode, size, (0, 0, 0, 0))
        log_callback(f"[psd_to_layered_images] Compositing frame {i}: layers {i} to {total-1}")
        for lyr, parent_names, layer_type in pixel_layers[i:]:
            try:
                img = lyr.composite()
                if img is not None and img.getbbox() is not None:
                    offset = getattr(lyr, 'offset', (0, 0))
                    composite.alpha_composite(img, dest=offset)
                    log_callback(f"  + Added layer: {'/'.join(parent_names)} [{layer_type}] at offset {offset}")
                else:
                    log_callback(f"  - Skipped blank or non-composite layer: {'/'.join(parent_names)} [{layer_type}]")
            except Exception as e:
                log_callback(f"  ! Error compositing layer {'/'.join(parent_names)} [{layer_type}]: {e}")
        out_path = out_dir / f'psdtemp_{i:05}.png'
        composite.save(out_path)
        log_callback(f"[psd_to_layered_images] Saved frame: {out_path}")

def images_are_similar(img1_data, img2_data, threshold=1):
    # Ensure both images have the same size
    if img1_data.size != img2_data.size:
        return False

    # Calculate mean squared error (MSE) manually
    width, height = img1_data.size
    pixels1 = img1_data.load()
    pixels2 = img2_data.load()

    total_diff = 0
    for x in range(width):
        for y in range(height):
            r1, g1, b1 = pixels1[x, y][:3]
            r2, g2, b2 = pixels2[x, y][:3]
            total_diff += (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2

    mse = total_diff / (width * height * 3)
    return mse < threshold


def unique_images_only(images, threshold=1):
    unique_images = []
    previous_image_data = None
    for img_path in images:
        with Image.open(img_path).convert('RGB') as current_image:
            if previous_image_data is None or not images_are_similar(previous_image_data, current_image, threshold):
                unique_images.append(img_path)
            previous_image_data = current_image.copy()
    return unique_images



def make_animation(input_path, original_name, file_extension, loop_backward, reverse_order=False, delete_frames=False, resize=False, max_size=1000):
    from PIL import Image  # Ensure Image is always imported
    input_path = Path(input_path)  # Ensure input_path is a Path object
    images = sorted(glob.glob(str(input_path / "psdtemp_*.png")))
    images += sorted(glob.glob(str(input_path / "psdtemp_?????.png")))
    images = sorted(list(set(images)))
    if reverse_order:
        images = list(reversed(images))
    if not images:
        print(f"[ERROR] No PNG frames found in {input_path}. Aborting animation.")
        return
    # If only one image, skip unique filtering
    if len(images) == 1:
        images_unique = images
    else:
        images_unique = unique_images_only(images)
    import numpy as np
    # Optionally resize frames
    def resize_frame_np(np_img, max_size):
        pil_img = Image.fromarray(np_img)
        w, h = pil_img.size
        if max(w, h) > max_size:
            if w >= h:
                new_w, new_h = max_size, int(h * max_size / w)
            else:
                new_w, new_h = int(w * max_size / h), max_size
            pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
        return np.array(pil_img)
    frames = [np.array(Image.open(img).convert("RGB")) for img in images_unique]
    if resize:
        frames = [resize_frame_np(f, max_size) for f in frames]
    if not frames:
        print(f"[ERROR] No valid PNG frames found in {input_path}. Aborting animation.")
        return
    output_path = str(input_path / f"{original_name}.{file_extension}")
    if file_extension == "webp":
        # Special handling for webp: duplicate first and last frames for hold duration
        fps = WEBM_FRAME_RATE
        pil_frames = []
        durations = []
        # Hold first frame
        for _ in range(FIRST_FRAME_HOLD_TIME):
            pil_frames.append(Image.fromarray(frames[0]))
            durations.append(int(250.0/fps))
        # Middle frames
        for frame in frames:
            pil_frames.append(Image.fromarray(frame))
            durations.append(int(250.0/fps))
        # Hold last frame
        for _ in range(LAST_FRAME_HOLD_TIME):
            pil_frames.append(Image.fromarray(frames[-1]))
            durations.append(int(250.0/fps))
        if loop_backward:
            # Add ping-pong effect (excluding last frame to avoid double hold)
            for frame in frames[-2:0:-1]:
                pil_frames.append(Image.fromarray(frame))
                durations.append(int(250.0/fps))
        pil_frames[0].save(
            output_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=durations,
            loop=0,
            format="WEBP",
            quality=90,
            method=6
        )
    else:
        # Build padded frames for all formats (start/end hold)
        frames_padded = [frames[0]] * FIRST_FRAME_HOLD_TIME
        frames_padded += frames
        frames_padded += [frames[-1]] * LAST_FRAME_HOLD_TIME
        if loop_backward:
            frames_padded += frames_padded[-2:0:-1]
        from moviepy.editor import ImageSequenceClip
        fps = WEBM_FRAME_RATE if file_extension == 'webm' else GIF_SPEED
        clip = ImageSequenceClip(frames_padded, fps=fps)
        bitrate = None
        quality = "high"
        if file_extension == 'webm':
            if quality == "high":
                bitrate = '5000k'
            elif quality == "medium":
                bitrate = '3000k'
            elif quality == "low":
                bitrate = '1000k'
        codec = "libvpx"  # Google's VP8 codec for .webm output
        crf = 10          # High-quality constant rate factor
        if file_extension == "gif":
            clip.write_gif(output_path, fps=GIF_SPEED)
        elif file_extension == "webm":
            clip.write_videofile(
                output_path,
                codec=codec,
                ffmpeg_params=["-crf", str(crf)],
                bitrate=bitrate,
                fps=fps
            )
    print(f"Animation saved as {output_path}")
    if delete_frames:
        for img in images:
            os.remove(img)

def should_process_psd_file(psd_file_path, webm_file_path, input_arg_make_webm):
    # Skip files within "backup" folders
    if "backup" in psd_file_path.parts:
        return False
    # Skip if the file name starts with 'PSDTEMP_'
    if psd_file_path.stem.startswith("PSDTEMP_"):
        return False
    # Get date modified of PSD file
    date_modified_psd = os.path.getmtime(psd_file_path)
    # Check if the animation file exists and get its date modified
    if webm_file_path.exists():
        date_modified_webm = os.path.getmtime(webm_file_path)
    else:
        date_modified_webm = 0  # If file does not exist, force processing
    # Only process if PSD file is newer than the existing WEBM/GIF
    return date_modified_psd > date_modified_webm

def check_photoshop_available(verbose=False, log_callback=None):
    try:
        from win32com.client import Dispatch
        if verbose and log_callback:
            log_callback("Attempting to Dispatch('Photoshop.Application')...")
        app = Dispatch('Photoshop.Application')
        if verbose and log_callback:
            log_callback(f"Photoshop.Application COM object acquired: version={getattr(app, 'Version', 'unknown')}, exe={getattr(app, 'Path', 'unknown')}")
        return True
    except Exception as e:
        msg = f"Photoshop COM automation not available: {e}\n"
        import traceback
        msg += traceback.format_exc()
        if verbose and log_callback:
            log_callback(msg)
        print(msg)
        return False

def resize_psd_via_photoshop(psd_path, maximum_dimension, log_callback=None):
    try:
        from photoshop import Session
        from photoshop.api import constants
        from photoshop.api.enumerations import ResampleMethod
        import traceback
        resized_psd_filename = f"PSDTEMP_{os.path.basename(psd_path)}"
        print("resized_psd_filename " + resized_psd_filename)
        resized_psd_path = os.path.join(os.path.dirname(psd_path), resized_psd_filename)
        print("resized_psd_path " + resized_psd_path)
        if log_callback:
            log_callback(f"[COM] Attempting to open Photoshop and resize {psd_path}")
        with Session(auto_close=False) as ps:
            doc = ps.app.open(psd_path)
            width = doc.width
            height = doc.height
            aspect_ratio = width / height
            if log_callback:
                log_callback(f"Opened PSD: {psd_path} (width={width}, height={height})")
            if width > height:
                new_width = maximum_dimension
                new_height = maximum_dimension / aspect_ratio
            else:
                new_height = maximum_dimension
                new_width = maximum_dimension * aspect_ratio
            print(f"Calculated new dimensions: {new_width}x{new_height}")
            new_width_int = int(new_width)
            new_height_int = int(new_height)
            doc.ResizeImage(new_width_int, new_height_int)
            print(f"Resized image within Photoshop.")
            options = ps.PhotoshopSaveOptions()
            doc.SaveAs(resized_psd_path, options)
            print(f"Attempting to save resized PSD to: {resized_psd_path}")
            doc.Close()
            print(f"Closed Photoshop document.")
            if not os.path.exists(resized_psd_path):
                print(f"ERROR: Resized PSD file not found at expected location: {resized_psd_path}")
                if log_callback:
                    log_callback(f"[ERROR] Resized PSD file not found at expected location: {resized_psd_path}")
                return None
            print(f"Resized PSD file saved successfully at: {resized_psd_path}")
            return resized_psd_path
    except Exception as e:
        msg = f"An error occurred while resizing the PSD: {e}\n"
        msg += traceback.format_exc()
        if log_callback:
            log_callback(msg)
        print(msg)
        # Additional diagnostics
        try:
            import win32com
            import win32com.client
            msg2 = f"win32com.client module loaded.\n"
            # List running COM objects
            from win32com.client import GetActiveObject
            try:
                active_ps = GetActiveObject('Photoshop.Application')
                msg2 += f"GetActiveObject found Photoshop.Application: version={getattr(active_ps, 'Version', 'unknown')}, exe={getattr(active_ps, 'Path', 'unknown')}\n"
            except Exception as e2:
                msg2 += f"GetActiveObject failed: {e2}\n"
            if log_callback:
                log_callback(msg2)
            print(msg2)
        except Exception as e3:
            msg3 = f"win32com diagnostics failed: {e3}\n"
            if log_callback:
                log_callback(msg3)
            print(msg3)
        return None

def export_layers_with_photoshop_jsx(psd_path, jsx_path, output_dir, log_callback=print):
    """
    Use Photoshop and the provided JSX script to export PSD layers.
    Args:
        psd_path: Path to the PSD file or directory
        jsx_path: Path to the JSX script (should be absolute)
        output_dir: Directory to output exported layers
        log_callback: Optional logger
    """
    import sys
    import time
    from pathlib import Path
    import os
    import pythoncom
    pythoncom.CoInitialize()
    psd_path = Path(psd_path)
    output_dir = Path(output_dir)
    jsx_script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), PHOTOSHOP_EXPORT_JSX))
    # If psd_path is a directory, find the first PSD file inside
    if psd_path.is_dir():
        log_callback(f"[Photoshop JSX Export][DEBUG] Input is a directory. Searching for PSD file in {psd_path}")
        psd_files = list(psd_path.glob('*.psd'))
        if not psd_files:
            log_callback(f"[Photoshop JSX Export][ERROR] No PSD file found in directory: {psd_path}")
            pythoncom.CoUninitialize()
            return
        psd_file = psd_files[0]
        log_callback(f"[Photoshop JSX Export] Using PSD file: {psd_file}")
    else:
        psd_file = psd_path
        log_callback(f"[Photoshop JSX Export] Using PSD file: {psd_file}")
    log_callback(f"[Photoshop JSX Export] Starting export for {psd_file} using {jsx_script_path}")
    try:
        import win32com.client
        app = win32com.client.Dispatch("Photoshop.Application")
        app.Visible = True
        log_callback(f"[Photoshop JSX Export] Waiting for Photoshop to load...")
        time.sleep(3)
        log_callback(f"[Photoshop JSX Export] Opening PSD in Photoshop: {psd_file}")
        try:
            doc = app.Open(str(psd_file))
            log_callback(f"[Photoshop JSX Export] PSD opened successfully.")
            log_callback(f"[Photoshop JSX Export] Waiting for PSD to finish loading...")
            time.sleep(2)
        except Exception as e:
            log_callback(f"[Photoshop JSX Export][ERROR] Failed to open PSD: {e}")
            return
        # Optional: Add a delay here if resizing via Photoshop is required
        # log_callback(f"[Photoshop JSX Export] Waiting after resize (if applicable)...")
        # time.sleep(2)
        log_callback(f"[Photoshop JSX Export] Running JSX: {jsx_script_path}")
        app.DoJavaScriptFile(str(jsx_script_path))
        log_callback(f"[Photoshop JSX Export] Waiting for export to complete...")
        for i in range(60):
            if any(output_dir.glob("*.png")):
                break
            time.sleep(1)
        log_callback(f"[Photoshop JSX Export] Export completed. Check {output_dir}")
    except Exception as e:
        log_callback(f"[Photoshop JSX Export][ERROR] Failed to run JSX: {e}")
    finally:
        pythoncom.CoUninitialize()

def process_psd_files(input_maximum_dimension, input_make_webm, input_make_gif, input_loop_backward, input_export_layered, input_path, progress_callback=None, log_callback=None):
    # Modularized to accept input_path and callbacks for GUI/CLI
    psd_files = [p for p in Path(input_path).rglob("*.psd") if "backup" not in p.parts] if Path(input_path).is_dir() else [Path(input_path)]
    total_files = len(psd_files)
    if log_callback:
        log_callback(f"Found {total_files} PSD files to process.")
    for idx, psd_file_path in enumerate(psd_files):
        try:
            if log_callback:
                log_callback(f"Processing {psd_file_path.name}")
            if progress_callback:
                progress_callback(idx, total_files)
            # Debug: show all args
            if log_callback:
                log_callback(f"Args: max_dim={input_maximum_dimension}, webm={input_make_webm}, gif={input_make_gif}, loop={input_loop_backward}, layered={input_export_layered}")
            file_type = "webm" if input_make_webm else "gif"
            webm_file_path = psd_file_path / f"{psd_file_path.stem}.{file_type}"
            if should_process_psd_file(psd_file_path, webm_file_path, input_make_webm):
                print(f"Processing PSD file: {psd_file_path}")
                resized_psd_path = resize_psd_via_photoshop(str(psd_file_path), input_maximum_dimension, log_callback=log_callback)
                if not resized_psd_path or not os.path.exists(resized_psd_path):
                    print(f"[ERROR] Could not resize {psd_file_path}. Skipping this file. (Check if Photoshop is installed and accessible)")
                    if log_callback:
                        log_callback(f"[ERROR] Could not resize {psd_file_path}. Skipping this file. (Check if Photoshop is installed and accessible)")
                    continue
                print(f"Resized PSD file saved at: {resized_psd_path}")
                time.sleep(2)  # Wait for the file save
                if input_export_layered:
                    psd_to_layered_images(resized_psd_path, log_callback=log_callback)
                    os.remove(resized_psd_path)
                    print(f"Layer images extracted and temporary PSD file removed.")
                if input_make_gif or input_make_webm:
                    make_animation(resized_psd_path, psd_file_path, file_type, input_loop_backward)
                    print(f"Animation created for file: {psd_file_path.name}")
            else:
                print(f"Skipping {psd_file_path} (up to date or in backup folder)")
        except Exception as e:
            if log_callback:
                log_callback(f"Error: {e}")
            print(f"An error occurred while processing {psd_file_path.name}: {e}")
            continue
    if progress_callback:
        progress_callback(total_files, total_files)
    if log_callback:
        log_callback("All files processed.")

def process_frames_to_video(input_folder, output_name, file_type="webm", loop_backward=False, log_callback=None, reverse_order=False, delete_frames=False, resize=False, max_size=1000):
    """
    Recursively search for exported PNG frames (psdtemp_*.png) in input_folder and subfolders, and process each set into a video/gif/webp.
    The output will be saved in the same folder as the PNG frames, with the given output_name and file_type.
    Args:
        input_folder: Folder containing exported PNG frames (e.g., psdtemp_*.png)
        output_name: Name of the output file (without extension)
        file_type: 'webm', 'gif', or 'webp'
        loop_backward: Whether to ping-pong the animation
        log_callback: Optional logging callback
        reverse_order: Whether to reverse the order of the frames
        delete_frames: Whether to delete the frames after processing
        resize: Whether to resize the frames
        max_size: Maximum size for resizing
    """
    import glob
    from pathlib import Path
    input_folder = str(input_folder)
    found_any = False
    for dirpath, dirnames, filenames in os.walk(input_folder):
        pngs = sorted(glob.glob(str(Path(dirpath) / "psdtemp_*.png")))
        pngs += sorted(glob.glob(str(Path(dirpath) / "psdtemp_?????.png")))
        pngs = sorted(list(set(pngs)))
        if pngs:
            found_any = True
            if reverse_order:
                pngs = list(reversed(pngs))
            output_path = Path(dirpath) / f"{output_name}.{file_type}"
            if log_callback:
                log_callback(f"[INFO] Found {len(pngs)} PNG frames in {dirpath}. Creating {output_path.name} (reverse={reverse_order})...")
            else:
                print(f"[INFO] Found {len(pngs)} PNG frames in {dirpath}. Creating {output_path.name} (reverse={reverse_order})...")
            make_animation(Path(dirpath), output_path.stem, file_type, loop_backward, reverse_order=reverse_order, delete_frames=delete_frames, resize=resize, max_size=max_size)
            msg = f"[INFO] Animation processing complete: {output_path}"
            if log_callback:
                log_callback(msg)
            print(msg)
    if not found_any:
        err = f"[ERROR] No PNG frames found recursively in {input_folder}. Nothing to convert to {file_type.upper()}."
        if log_callback:
            log_callback(err)
        else:
            print(err)

def export_layered_images_only(input_path, max_dimension=1000, log_callback=None):
    """
    Only export layered images from PSDs, skipping animation/video phase.
    Args:
        input_path: PSD file or folder
        max_dimension: Resize max dimension (if needed)
        log_callback: Optional logging callback
    """
    from pathlib import Path
    import shutil
    psd_files = [p for p in Path(input_path).rglob("*.psd") if "backup" not in p.parts] if Path(input_path).is_dir() else [Path(input_path)]
    for psd_file_path in psd_files:
        print(f"Exporting layered images for {psd_file_path}")
        # If resizing is requested, use Photoshop. If not, just duplicate the file.
        # This function should only be called when resize is OFF, so just duplicate.
        resized_psd_path = psd_file_path.parent / f"PSDTEMP_{psd_file_path.name}"
        shutil.copy2(psd_file_path, resized_psd_path)
        print(f"[INFO] Duplicated PSD to {resized_psd_path}")
        if log_callback:
            log_callback(f"[INFO] Duplicated PSD to {resized_psd_path}")
        psd_to_layered_images(resized_psd_path, log_callback=log_callback)
        os.remove(resized_psd_path)
        print(f"Layer images exported and temp PSD removed for {psd_file_path}")
        if log_callback:
            log_callback(f"Layer images exported for {psd_file_path}")

def run_gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError:
        print("[ERROR] Tkinter is not installed. Please install it to use the GUI.")
        sys.exit(1)
    root = tk.Tk()
    root.title("PSD to Timelapse Anim")
    root.geometry("650x420")
    # Style
    bg = "#23272e"; fg = "#f0f0f0"; btn_bg = "#2c313c"; btn_fg = fg
    root.configure(bg=bg)

    # Folder path
    tk.Label(root, text="PSD Folder or File:", bg=bg, fg=fg).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    path_var = tk.StringVar()
    tk.Entry(root, textvariable=path_var, width=40, bg=bg, fg=fg, insertbackground=fg).grid(row=0, column=1, padx=5, pady=5)
    def browse():
        sel = filedialog.askdirectory()
        if sel:
            path_var.set(sel)
    tk.Button(root, text="Browse", command=browse, bg=btn_bg, fg=btn_fg).grid(row=0, column=2, padx=5, pady=5)

    # Args options
    max_size_var = tk.IntVar(value=1000)
    resize_var = tk.BooleanVar(value=False)
    export_layered_var = tk.BooleanVar(value=False)
    make_gif_var = tk.BooleanVar(value=False)
    make_webm_var = tk.BooleanVar(value=False)
    make_webp_var = tk.BooleanVar(value=True)
    loop_backward_var = tk.BooleanVar(value=False)
    reverse_order_var = tk.BooleanVar(value=True)
    delete_frames_var = tk.BooleanVar(value=False)
    use_photoshop_jsx_var = tk.BooleanVar(value=False)

    # --- UI Layout ---
    # Row 1: Export Layered | Resize | Max Size label | Max Size input
    tk.Checkbutton(root, text="Export Layered", variable=export_layered_var, bg=bg, fg=fg, selectcolor=bg).grid(row=1, column=0, sticky="w")
    tk.Checkbutton(root, text="Resize", variable=resize_var, bg=bg, fg=fg, selectcolor=bg).grid(row=1, column=1, sticky="w")
    tk.Label(root, text="Max Size:", bg=bg, fg=fg).grid(row=1, column=2, padx=5, pady=5, sticky="e")
    tk.Entry(root, textvariable=max_size_var, width=8, bg=bg, fg=fg, insertbackground=fg).grid(row=1, column=3, sticky="w")

    # Row 2: Animation output checkboxes (WEBP, GIF, WEBM)
    tk.Checkbutton(root, text="Make WEBP", variable=make_webp_var, bg=bg, fg=fg, selectcolor=bg).grid(row=2, column=0, sticky="w")
    tk.Checkbutton(root, text="Make GIF", variable=make_gif_var, bg=bg, fg=fg, selectcolor=bg).grid(row=2, column=1, sticky="w")
    tk.Checkbutton(root, text="Make WEBM", variable=make_webm_var, bg=bg, fg=fg, selectcolor=bg).grid(row=2, column=2, sticky="w")

    # Row 3: Animated options (Reverse Order, Loop Backward, Delete Frames After)
    tk.Checkbutton(root, text="Reverse Order", variable=reverse_order_var, bg=bg, fg=fg, selectcolor=bg).grid(row=3, column=0, sticky="w")
    tk.Checkbutton(root, text="Loop Backward", variable=loop_backward_var, bg=bg, fg=fg, selectcolor=bg).grid(row=3, column=1, sticky="w")
    tk.Checkbutton(root, text="Delete Frames After", variable=delete_frames_var, bg=bg, fg=fg, selectcolor=bg).grid(row=3, column=2, sticky="w")

    # Row 4: Use Photoshop JSX export
    tk.Checkbutton(root, text="Use Photoshop JSX Export", variable=use_photoshop_jsx_var, bg=bg, fg=fg, selectcolor=bg).grid(row=4, column=0, sticky="w")

    # Progress and log
    progress_var = tk.DoubleVar()
    progress_bar = tk.Scale(root, variable=progress_var, from_=0, to=100, orient="horizontal", showvalue=False, length=400, bg=bg)
    progress_bar.grid(row=5, column=0, columnspan=4, padx=5, pady=10)
    log_text = tk.Text(root, height=8, bg="#181A1B", fg="#b0b0b0", wrap="word")
    log_text.grid(row=6, column=0, columnspan=4, sticky="ew", padx=5)
    log_text.config(state="disabled")

    def append_log(msg):
        log_text.config(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.config(state="disabled")

    def gui_progress_callback(current, total):
        percent = (current / total) * 100 if total else 0
        progress_var.set(percent)
    def gui_log_callback(msg):
        append_log(msg)

    def start():
        import os
        folder = path_var.get()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Error", "Please specify a valid PSD file or folder.")
            return
        # Detect if psdtemp_*.png frames exist (support both file and folder input)
        import glob
        input_path = folder
        is_file = os.path.isfile(input_path)
        frames_dir = os.path.dirname(input_path) if is_file else input_path
        frames_exist = bool(glob.glob(os.path.join(frames_dir, "psdtemp_*.png")))
        export_layered = export_layered_var.get()
        make_webm = make_webm_var.get()
        make_gif = make_gif_var.get()
        make_webp = make_webp_var.get()
        loop_backward = loop_backward_var.get()
        reverse_order = reverse_order_var.get()
        delete_frames = delete_frames_var.get()
        resize = resize_var.get()
        max_size = max_size_var.get()
        use_photoshop_jsx = use_photoshop_jsx_var.get()
        # Log all current UI states
        append_log("[UI] Start button pressed with the following settings:")
        append_log(f"[UI]   Path: {folder}")
        append_log(f"[UI]   Export Layered: {export_layered}")
        append_log(f"[UI]   Resize: {resize}")
        append_log(f"[UI]   Max Size: {max_size}")
        append_log(f"[UI]   Make WEBP: {make_webp}")
        append_log(f"[UI]   Make GIF: {make_gif}")
        append_log(f"[UI]   Make WEBM: {make_webm}")
        append_log(f"[UI]   Reverse Order: {reverse_order}")
        append_log(f"[UI]   Loop Backward: {loop_backward}")
        append_log(f"[UI]   Delete Frames After: {delete_frames}")
        append_log(f"[UI]   Use Photoshop JSX Export: {use_photoshop_jsx}")
        append_log(f"[UI]   Exported frames exist: {frames_exist} (dir checked: {frames_dir})")
        # Redirect stdout/stderr to GUI log
        sys.stdout = TkinterConsole(append_log)
        sys.stderr = TkinterConsole(append_log)
        # Disable UI
        for child in root.winfo_children():
            child.configure(state="disabled")
        # Run
        if (not export_layered):
            if frames_exist and (make_webm or make_gif or make_webp):
                append_log(f"[INFO] Detected exported frames in {frames_dir}. Skipping Photoshop and processing frames directly.")
                if make_webm:
                    process_frames_to_video(frames_dir, "timelapse", file_type="webm", loop_backward=loop_backward, log_callback=append_log, reverse_order=reverse_order, delete_frames=delete_frames, resize=resize, max_size=max_size)
                if make_gif:
                    process_frames_to_video(frames_dir, "timelapse", file_type="gif", loop_backward=loop_backward, log_callback=append_log, reverse_order=reverse_order, delete_frames=delete_frames, resize=resize, max_size=max_size)
                if make_webp:
                    process_frames_to_video(frames_dir, "timelapse", file_type="webp", loop_backward=loop_backward, log_callback=append_log, reverse_order=reverse_order, delete_frames=delete_frames, resize=resize, max_size=max_size)
            else:
                append_log("[ERROR] No exported frames found (psdtemp_*.png) in the selected folder. Please export frames first or enable 'Export Layered'.")
        else:
            if use_photoshop_jsx:
                append_log("[INFO] Exporting using Photoshop JSX script...")
                jsx_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_psd_to_timelapse_export.jsx")
                export_layers_with_photoshop_jsx(input_path, jsx_path, input_path, log_callback=append_log)
            else:
                append_log("[INFO] Exporting layered images using psd-tools (no Photoshop dependency)...")
                export_layered_images_only(
                    folder,
                    max_dimension=max_size,
                    log_callback=append_log
                )
            if make_webm or make_gif or make_webp:
                # After export, process frames
                if make_webm:
                    process_frames_to_video(folder, "timelapse", file_type="webm", loop_backward=loop_backward, log_callback=append_log, reverse_order=reverse_order, delete_frames=delete_frames, resize=resize, max_size=max_size)
                if make_gif:
                    process_frames_to_video(folder, "timelapse", file_type="gif", loop_backward=loop_backward, log_callback=append_log, reverse_order=reverse_order, delete_frames=delete_frames, resize=resize, max_size=max_size)
                if make_webp:
                    process_frames_to_video(folder, "timelapse", file_type="webp", loop_backward=loop_backward, log_callback=append_log, reverse_order=reverse_order, delete_frames=delete_frames, resize=resize, max_size=max_size)
        for child in root.winfo_children():
            child.configure(state="normal")
    tk.Button(root, text="Start", command=start, bg=btn_bg, fg=btn_fg).grid(row=7, column=1, pady=10)
    root.mainloop()

def get_dynamic_tqdm_width():
    # Function to get dynamic width for the tqdm progress bar
    terminal_width = shutil.get_terminal_size().columns
    return max(30, terminal_width - 20)  # Ensure a minimum width of 30 and adjust to fit terminal

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        args = parse_args()
        # Add CLI switches for new modes
        if hasattr(args, "frames_to_video") and args.frames_to_video:
            # Example usage: --frames_to_video --input path/to/frames --output_name mytimelapse --file_type webm
            process_frames_to_video(
                args.input,
                getattr(args, "output_name", "timelapse"),
                getattr(args, "file_type", "webm"),
                getattr(args, "loop_backward", False)
            )
        elif hasattr(args, "export_layered_only") and args.export_layered_only:
            export_layered_images_only(args.input, args.max_size)
        else:
            process_psd_files(
                args.max_size,
                args.make_webm,
                args.make_gif,
                args.loop_backward,
                args.export_layered,
                args.input
            )
        print("---------COMPLETE--------")
    else:
        run_gui()
