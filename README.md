<p align="center">
  <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/sd_project_tools_header_long.png?raw=true" height="120" /> 
</p>

# diffusion_project_tools
- a collection of tools for interacting with image synthesis projects , organizing , reviewing , and generating . 

| review | comfy | prompt | video | audio | 
| :---: | :---: | :---: | :---: | :---: |
| <a href="https://github.com/CorvaeOboro/sd_project_tools#review-and-rank"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/thumb_image.png?raw=true" width="140" height="140" /> </a>| <a href="https://github.com/CorvaeOboro/sd_project_tools#comfyui-custom-nodes"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/thumb_comfy.png?raw=true" width="140" height="140" />  </a>  |  <a href="https://github.com/CorvaeOboro/sd_project_tools#prompt-entry"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/thumb_prompt.png?raw=true" width="140" height="140" />  </a>  | <a href="https://github.com/CorvaeOboro/sd_project_tools#video-tools"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/thumb_video.png?raw=true" width="140" height="140" />  </a>  | <a href="https://github.com/CorvaeOboro/sd_project_tools#voice-action-tools"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/thumb_voice.png?raw=true" width="140" height="140" /> </a>|

# install
- install python 3.10
- [download diffusion_project_tools](https://github.com/CorvaeOboro/sd_project_tools/archive/refs/heads/master.zip) and extract to a folder
- quick install using [00_install_and_launch.bat](https://github.com/CorvaeOboro/sd_project_tools/blob/main/00_install_and_launch.bat) = it creates an isolated local Python virtual environment and installs the [requirements.txt](https://github.com/CorvaeOboro/sd_project_tools/blob/main/requirements.txt) into it , then runs launcher tool ui to  launch any of the project tools shown below .

or manually install:
- create a virtual environment: `python -m venv venv`
- activate the virtual environment:
    - Windows: `venv\Scripts\activate`
    - macOS/Linux: `source venv/bin/activate`
- install requirements: `pip install -r requirements.txt`
- run [launch_tools.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/launch_tools.py)

# Launcher
<img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/launch_tools.png?raw=true" />

- [launch_tools.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/launch_tools.py) = Central launcher UI for all project tools 

# Review and Rank
- [image_review_and_rank_multi_project.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_review_and_rank_multi_project.py) = project image reviewer , quickly rank images into subfolders using left click = 1 and right click = 2 , colorizes by amount 
 <a href="https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_review_and_rank_multi_project.py"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main//docs/image_review_and_rank_multi_project.png?raw=true" height="200" /> </a>
- [image_review_and_rank.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_review_and_rank.py) = simpler image viewer from a folderpath , quickly rank fullscreen singular images into subfolders using 1,2, or 3 . navigate with arrows . view as tiled texture with T 

# ComfyUI custom nodes
located in /comfyui/ folder , copy into comfyui custom_nodes  to install
<img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main//docs/diffusion_project_tools_comfy_workflow.png?raw=true" height="200" />

- [Checkpoint Loader By String Dirty](/comfyui/ComfyUI_OBORO_CheckpointLoaderByStringDirty/checkpoint_loader_by_string_dirty.py) = Loads a Diffusion checkpoint by matching a string input (full path, relative path, or filename) to any registered checkpoint.
- [Checkpoint Random Selector](/comfyui/ComfyUI_OBORO_RandomCheckpointSelector/random_checkpoint_selector.py) = Randomly selects a checkpoint from a category/folder at a set interval 
- [Image Contrast Limited Adaptive Histogram Equalization](/comfyui/ComfyUI_OBORO_ImageContrastLimitedAdaptiveHistogramEqualization/image_CLAHE.py) = Image contrast using CLAHE , localized relativistic histogram equalization
- [Image Multi Scale Retinex Color Restoration](/comfyui/ComfyUI_OBORO_ImageMultiScaleRetinexColorRestoration/image_MSRCR.py) = Image contrast using Multi-Scale Retinex Color Restoration
- [Load Image FilePath Out](/comfyui/ComfyUI_OBORO_LoadImageFilePathOut/load_image_filepath_out.py) = Load image node, with additional outputs for the filepath and folderpath of the loaded image 
- [Load Image Random Variants](/comfyui/ComfyUI_OBORO_LoadImageRandomVariants/load_image_random_variant.py) = Loads a image from a filepath with optional random variants , like suffixs or subfolders of multiple renders 
- [Load Text File Graceful](/comfyui/ComfyUI_OBORO_LoadTextFileGraceful/load_text_file_graceful.py) = Loads text as string , handling missing or invalid files gracefully without crashing
- [Lora Strength Multiplier](/comfyui/ComfyUI_OBORO_LoraStrengthMultiplier/lora_strength_multiplier.py) = Multiplies and caps LoRA string strengths, with options for total and individual caps.
- [LoRA Strength Variants](/comfyui/ComfyUI_OBORO_LoraStrengthVariants/lora_strength_variants.py) = Processes LoRA strings with options to randomize Strength or highlight random LoRAs , within a maximum total and individual strength limits
- [Save Image Extended FolderPath](/comfyui/ComfyUI_OBORO_SaveImageExtendedFolderPath/save_image_extended_folderpath.py) = Save image to external folder path ( requires editing comfy ui folder_paths.py )
- [Text Strength Multiplier](/comfyui/ComfyUI_OBORO_TextStrengthMultiplier/text_strength_multiplier.py) = Multiplies and caps text strengths, with options for total and individual caps.
- [Text To String Safe For Filename](/comfyui/ComfyUI_OBORO_TextToStringSafeForFilename/text_to_string_safe_for_filename.py) = Converts text into filename-safe text by replacing invalid and unfavored characters and truncating to 150 characters
- [Text Token Count](/comfyui/ComfyUI_OBORO_TextTokenCount/text_token_count.py) = Counts the number of tokens in a string using CLIP 

- [comfyui_workflow_color_edit.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/comfyui_workflow_color_edit.py) = helper script to batch-edit colors/values within saved ComfyUI workflow JSONs

# Tensor Info and Sorting
<img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main//docs/tensor_tools_all.png?raw=true" height="200" /> 

- [tensor_tools_all.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/tensor_tools_all.py) = gets info from civitai , sorts by info by model type and category , removes duplicates by hash

# Prompt Entry
<a href="https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/gen_project_prompt_entry.py"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main//docs/gen_project_prompt_entry.png?raw=true" height="200" /> </a>

- [gen_project_prompt_entry.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/gen_project_prompt_entry.py) = GUI dashboard for managing multiple item prompts , support for SDXL and SD1.5 positive/negative prompts and FLUX and VIDEO prompts
- [project_status_dashboard.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/project_status_dashboard.py) = dashboard to visualize and track project generation status and outputs

# Image Tools
- [image_editor_layered.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_editor_layered.py) = basic GUI tool to edit an image with multiple layers
- [image_text_prompt_tools.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_text_prompt_tools.py) = GUI tool to drag drop image and for prompt management. merge multiple prompts without duplicates, balance prompt strengths, simplify prompt structure (remove parentheses), scale LoRA strengths to target maximum, 
- [lora_variants.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/lora_variants.py) = input a prompt with loras and generate all permutations of strengths , within a range of total lora strength and per lora strengths . the output can then be used for x/y plot or as wildcard
- [lora_previews_to_list.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/lora_previews_to_list.py) = given a folder of lora previews creates a list
 - [image_icon_generator.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_icon_generator.py) = generate app icons/thumbnails from images with safe padding and backgrounds
 - [image_inspect_bmp.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_inspect_bmp.py) = inspect BMP headers and pixel data for debugging/validation
 - [image_metadata_badword_scanner.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_metadata_badword_scanner.py) = scan image metadata/captions for bad words and produce a cleaned report
 - [image_psd_reconstruct.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_psd_reconstruct.py) = reconstruct images from PSD layers for analysis or export

- # Video Tools
- [video_clip_marker.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_clip_marker.py) = tool for marking and processing video clips
- <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/video_clip_marker.png?raw=true" height="200" />
- [video_combine.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_combine.py) = GUI tool for combining videos, adjusting speed, removing first frames, and batch processing video folders. Uses ffmpeg
- [video_add_audio.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_add_audio.py) = quick Add audio to a video file using ffmpeg and ffprobe. Supports both GUI and CLI modes. Drag-and-drop interface.
- [video_place_in_image_composite.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_place_in_image_composite.py) = GUI tool to composite a video into a region of an image using template matching and homography. 
- [video_webp_pingpong.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_webp_pingpong.py) = creates ping-pong WebP animations from video files
- [video_psd_to_timelapse_anim.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_psd_to_timelapse_anim.py) = Converts PSD layers to timelapse animations, UI and CLI, exports to video gif or webp or webm. updated to use [image_psd_to_timelapse_export.jsx](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/image_psd_to_timelapse_export.jsx) a photoshop javascript to do the exporting faster 
<img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/image_psd_to_timelapse_anim.png?raw=true" height="200" />

- [video_editor_word_rating.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_editor_word_rating.py) = GUI tool to rate video frames using words 
- [video_review_and_rank_multi_project.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_review_and_rank_multi_project.py) =UI for reviewing and ranking video files
 - [VIDEO_cursor_removal.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/VIDEO_cursor_removal.py) = detect and remove mouse cursor overlays from screen recordings
 - [VIDEO_image_sequence_to_webp.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/VIDEO_image_sequence_to_webp.py) = convert folders of image sequences into optimized animated WebP
 - [video_audio_batch_processor.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_audio_batch_processor.py) = batch operations for extracting, replacing, or adjusting audio across many videos
 - [video_interlacing_fix.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_interlacing_fix.py) = deinterlace and repair interlaced footage using ffmpeg filters
 - [video_to_gif_cropper.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_to_gif_cropper.py) = crop and convert video clips into GIFs with loop-friendly settings
  - [video_music_sync.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/video_music_sync.py) = align audio to music video timing via waveform analysis , useful for syncing stage show to record audio
  <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/video_music_sync.png?raw=true" height="200" />

# Voice Action Tools
- [voice_action_organizer.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/voice_action_organizer.py) = GUI tool for offline speech recognition (using Vosk) to trigger hotkeys or move selected files in Windows Explorer using spoken commands. JSON action management. Requires the [Vosk speech model](https://alphacephei.com/vosk/models)
- <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/voice_action_organizer.png?raw=true" height="200" />

# Audio Tools
- [audio_timing_beat.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/audio_timing_beat.py) = analyze audio beat timing and markers for synchronization tasks

# auto1111 project workflow
- archived tools built around the previous auto1111 workflow are in [/tools/archive/](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tools/archive/) folder 
- this workflow is now recreated in comfyui using the projects [custom nodes](https://github.com/CorvaeOboro/sd_project_tools/blob/main/comfyui/)

# LICENSE
- free to all , [creative commons zero CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) , free to re-distribute , attribution not required