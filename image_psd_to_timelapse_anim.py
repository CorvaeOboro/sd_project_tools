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
#//==============================================================================

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True, help='Path to the PSD file or directory containing PSD files')
    parser.add_argument('--max_size', type=int, default=1000, help='Maximum width or height of the image, keeping aspect ratio')
    parser.add_argument('--export_layered', action='store_true', default=True, help='Export images for each layer change')
    parser.add_argument('--make_gif', action='store_true', default=True, help='Generate a GIF showing the layer composition over time')
    parser.add_argument('--make_webm', action='store_true', default=True, help='Generate a WEBM video showing the layer composition over time')
    parser.add_argument('--loop_backward', action='store_true', help='Play the animation forwards then backwards')
    return parser.parse_args()

#//==============================================================================
    # Start up Photoshop application or get reference to already running Photoshop instance
    # this is unfortunately neccesary as psd_tools has no resize functions that keep the layers intact
from photoshop import Session
from photoshop.api import constants
#constants.ResampleMethod.BICUBIC
from photoshop.api.enumerations import ResampleMethod


def resize_psd_via_photoshop(psd_path, maximum_dimension):
    try:
        resized_psd_filename = f"PSDTEMP_{os.path.basename(psd_path)}"
        print("resized_psd_filename " + resized_psd_filename)
        resized_psd_path = os.path.join(os.path.dirname(psd_path), resized_psd_filename)
        print("resized_psd_path " + resized_psd_path)
        with Session(auto_close=False) as ps:
            doc = ps.app.open(psd_path)
            width = doc.width
            height = doc.height
            aspect_ratio = width / height
            if width > height:
                new_width = maximum_dimension
                new_height = maximum_dimension / aspect_ratio
            else:
                new_height = maximum_dimension
                new_width = maximum_dimension * aspect_ratio
            print(f"Calculated new dimensions: {new_width}x{new_height}")
            # Convert new dimensions to strings with units
            #new_width_str = f"{new_width}px"
            #new_height_str = f"{new_height}px"
            new_width_int = int(new_width)
            new_height_int = int(new_height)
            # Access ResampleMethod via ps.app.enum
            #resample_method = ps.app.enum.ResampleMethod.BICUBIC
            #doc.ResizeImage(new_width_str, new_height_str, resolution=72, resampleMethod=resample_method)
            doc.ResizeImage(new_width_int, new_height_int)
            print(f"Resized image within Photoshop.")
            options = ps.PhotoshopSaveOptions()
            doc.SaveAs(resized_psd_path, options)
            print(f"Attempting to save resized PSD to: {resized_psd_path}")
            doc.Close()
            print(f"Closed Photoshop document.")
            if not os.path.exists(resized_psd_path):
                print(f"ERROR: Resized PSD file not found at expected location: {resized_psd_path}")
                return None
            print(f"Resized PSD file saved successfully at: {resized_psd_path}")
            return resized_psd_path
    except Exception as e:
        print(f"An error occurred while resizing the PSD: {e}")
        return None





def extract_visible_layers(layer, layer_list):
    if layer.is_visible():
        if layer.is_group():
            for sublayer in layer:
                extract_visible_layers(sublayer, layer_list)
        else:
            layer_list.append(layer)

def psd_to_layered_images(input_psd_path):
    """ the PSD is saved to composite images that includes the layers visible in stacked order to show the progression of the PSD """
    input_psd_path = Path(input_psd_path)  # Ensure the path is a Path object
    psd = PSDImage.open(input_psd_path)
    visible_layers = []
    start_time = time.time()
    for layer in psd.descendants():
        extract_visible_layers(layer, visible_layers)
    print(f"Extracting layers took {time.time() - start_time:.2f}s")

    start_time = time.time()
    for layer in visible_layers:
        layer.visible = False

    # Custom tqdm setup with dynamic width and enhanced formatting
    dynamic_tqdm = tqdm(visible_layers, desc="Processing layers", ncols=get_dynamic_tqdm_width(),
                        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]")
    for idx, layer in enumerate(dynamic_tqdm):
        start_time = time.time()
        for j in range(idx + 1):
            visible_layers[j].visible = True
        image = psd.composite(force=True)
        # image = resize_image(psd.composite(force=True), max_size) resize is no longer done here it is done to the temp PSD once for speed
        image.save(input_psd_path.parent / f'psdtemp_{idx:05}.png')
        gc.collect()
        dynamic_tqdm.set_postfix_str(f"Layer {idx} processed in {time.time() - start_time:.2f}s")

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



def make_animation(input_path, original_name, file_extension, loop_backward):
    input_path = Path(input_path)  # Ensure input_path is a Path object
    images = sorted(glob.glob(str(input_path.parent / "psdtemp_*.png")))
    images_unique = unique_images_only(images)  # returns paths of images that are uniquely different than previous frame using MSE threshold

    # Load images and convert them to Pillow RGB format
    frames = [Image.open(img).convert("RGB").copy() for img in images_unique]

    # Extend the first frame to hold longer at the start of the animation
    frames_padded = [frames[0]] * FIRST_FRAME_HOLD_TIME
    frames_padded += frames
    frames_padded += [frames[-1]] * LAST_FRAME_HOLD_TIME  # Extend last frame for ending pause

    if loop_backward:
        # Creates a "ping-pong" effect: forward then reverse animation without repeating the last frame
        frames_padded += frames_padded[-2:0:-1]

    # Create the video clip from frames (Pillow images are accepted directly)
    fps = WEBM_FRAME_RATE if file_extension == 'webm' else GIF_SPEED
    clip = ImageSequenceClip(frames_padded, fps=fps)

    # WEBM video quality settings
    # bitrate = optional constraint on bandwidth (in kbps), overrides CRF if specified
    #     - If set, it fixes the output size but might sacrifice quality
    #     - If left None, CRF handles the quality alone
    bitrate = None
    quality = "high"
    if file_extension == 'webm':
        if quality == "high":
            bitrate = '5000k'
        elif quality == "medium":
            bitrate = '3000k'
        elif quality == "low":
            bitrate = '1000k'

    # codec = "libvpx" tells ffmpeg to use Google's VP8 codec for .webm format
    codec = "libvpx"  # Google's VP8 codec for .webm output
    # CRF = Lower is good quality Range: 4 (visually lossless) , high quality = 10-15 ,  low quality = 63 
    crf = 10          # High-quality constant rate factor

    # Save the clip based on the desired file type
    output_path = str(input_path.parent / f"{original_name.stem}.{file_extension}")
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

    # remove all temporary images
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

def process_psd_files(input_maximum_dimension, input_make_webm, input_make_gif, input_loop_backward, input_export_layered):
    psd_files = [p for p in Path(args.input).rglob("*.psd") if "backup" not in p.parts] if Path(args.input).is_dir() else [Path(args.input)]
    dynamic_progress_bar = tqdm(psd_files, desc="Processing PSD files", ncols=get_dynamic_tqdm_width(),
                        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]")

    print("Photoshop application is now visible.")
    # Iterate through the PSD files
    for psd_file_path in dynamic_progress_bar:
        try:
            # Determine the file type based on user input
            file_type = "webm" if input_make_webm else "gif"
            webm_file_path = psd_file_path.parent / f"{psd_file_path.stem}.{file_type}"
            if should_process_psd_file(psd_file_path, webm_file_path, input_make_webm):
                print(f"Processing PSD file: {psd_file_path}")
                # Resize the PSD file using a Photoshop COM interface function
                resized_psd_path = resize_psd_via_photoshop( str(psd_file_path), input_maximum_dimension)
                print(f"Resized PSD file saved at: {resized_psd_path}")
                time.sleep(5)  # Wait for the file save
                # Process the resized PSD file to extract and save layer images
                if input_export_layered:
                    psd_to_layered_images(resized_psd_path)  # Assume this function extracts and saves layers
                    os.remove(resized_psd_path)  # Remove the temporary resized PSD file
                    print(f"Layer images extracted and temporary PSD file removed.")
                # Generate GIF or WEBM if requested
                if input_make_gif or input_make_webm:
                    make_animation(resized_psd_path, psd_file_path, file_type, input_loop_backward)
                    print(f"Animation created for file: {psd_file_path.name}")
                dynamic_progress_bar.set_postfix_str(f"Processed {psd_file_path.name}")
        except Exception as e:
            print(f"An error occurred while processing {psd_file_path.name}: {e}")
            continue
    psd_files = [p for p in Path(args.input).rglob("*.psd") if "backup" not in p.parts] if Path(args.input).is_dir() else [Path(args.input)]
    dynamic_tqdm = tqdm(psd_files, desc="Processing PSD files", ncols=get_dynamic_tqdm_width(), bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]")

def get_dynamic_tqdm_width():
    # Function to get dynamic width for the tqdm progress bar
    terminal_width = shutil.get_terminal_size().columns
    return max(30, terminal_width - 20)  # Ensure a minimum width of 30 and adjust to fit terminal

#//==============================================================================
if __name__ == "__main__":
    # args from CLI 
    args = parse_args()
    input_path = Path(args.input)

    input_arg_max_size = args.max_size
    input_arg_make_webm = args.make_webm
    input_arg_make_gif = args.make_gif
    input_arg_loop_backward = args.loop_backward
    input_arg_export_layered = args.export_layered

    process_psd_files(input_arg_max_size, input_arg_make_webm, input_arg_make_gif, input_arg_loop_backward, input_arg_export_layered)
    print("---------COMPLETE--------")

