<p align="center">
  <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/sd_project_tools_header_long.png?raw=true" height="120" /> 
</p>

# diffusion_project_tools
- a collection of tools for interacting with image synthesis projects , organizing , reviewing , and generating . 

| review | comfy | sort| prompt | video | audio | 

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
- [launch_tools.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/launch_tools.py) = Central launcher UI for all project tools 

# Review and Ranking tools
- [image_review_and_rank_multi_project.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_review_and_rank_multi_project.py) = project image reviewer , quickly rank images into subfolders using left click = 1 and right click = 2 , colorizes by amount 
 <a href="https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_review_and_rank_multi_project.py"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main//docs/image_review_and_rank_multi_project.png?raw=true" height="200" /> </a>
- [image_review_and_rank.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_review_and_rank.py) = simple image viewer from a folderpath , quickly rank images into subfolders using 1,2, or 3 . navigate with arrows . view as tiled texture with T 
- [image_review_and_rank_multi.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_review_and_rank_multi.py) = multi-folder image reviewer with basic ranking functionality

# ComfyUI custom nodes
located in /comfyui/ folder , copy into comfyui custom_nodes  to install
- [LoRA Strength Variants](/comfyui/ComfyUI_OBORO_LoraStrengthVariants/lora_strength_variants.py) = Processes LoRA strings with options to randomize Strength or highlight random LoRAs , within a maximum total and individual strength limits
- [Save Image Extended FolderPath](/comfyui/ComfyUI_OBORO_SaveImageExtendedFolderPath/save_image_extended_folderpath.py) = Save image of external folder path ( requires editing comfy ui folder_paths.py )
- [String To String Safe For Filename](/comfyui/ComfyUI_OBORO_StringToStringSafeForFilename/string_safe_for_filename.py) = Converts text into filename-safe text by replacing invalid and unfavored characters.
- [Load Image FilePath Out](/comfyui/ComfyUI_OBORO_LoadImageFilePathOut/load_image_filepath_out.py) = Similar to the load image node, additionaly outputs the filepath and folderpath of the loaded image to strings
- [Load Text File Graceful](/comfyui/ComfyUI_OBORO_LoadTextFileGraceful/load_text_file_graceful.py) = Loads text as string , handling invalid files gracefully without crashing

# tensor info and sorting
- [tensor_sort_civitai_files.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_sort_civitai_files.py) = sorts model checkpoints and LoRAs based on the info from corresponding civitai info , models by base model , then by type
- [tensor_info_civitai_get.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tensor_info_civitai_get.py) = sorts model checkpoints and LoRAs based on the civitai info, models by base model, then by type such as LoRA
- [tensor_sort_civitai_by_category.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/tensor_sort_civitai_by_category.py) = sorts model checkpoints and LoRAs based on the category "nsfw" and "poi" in corresponding civitai info

# project tools
- [gen_project_prompt_entry.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_project_prompt_entry.py) = GUI dashboard for managing multiple item prompts , support for SDXL and SD1.5 positive/negative prompts and FLUX and VIDEO prompts
- <a href="https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_project_prompt_entry.py"> <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main//docs/gen_project_prompt_entry.png?raw=true" height="200" /> </a>

# image prompt tools
- [image_text_prompt_tools.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_text_prompt_tools.py) = GUI tool to drag drop image and for prompt management. merge multiple prompts without duplicates, balance prompt strengths, simplify prompt structure (remove parentheses), scale LoRA strengths to target maximum, 
- [lora_variants.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/lora_variants.py) = input a prompt with loras and generate all permutations of strengths , within a range of total lora strength and per lora strengths . the output can then be used for x/y plot or as wildcard
- [lora_previews_to_list.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/lora_previews_to_list.py) = given a folder of lora previews creates a list

# image tools
- [image_editor_layered.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_editor_layered.py) = basic GUI tool to edit an image with multiple layers

# video tools
- [video_clip_marker.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_clip_marker.py) = tool for marking and processing video clips
- [video_combine.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_combine.py) = GUI tool for combining videos, adjusting speed, removing first frames, and batch processing video folders. Uses ffmpeg
- [video_add_audio.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_add_audio.py) = quick Add audio to a video file using ffmpeg and ffprobe. Supports both GUI and CLI modes. Drag-and-drop interface.
- [video_place_in_image_composite.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_place_in_image_composite.py) = GUI tool to composite a video into a region of an image using template matching and homography. 
- [video_webp_pingpong.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_webp_pingpong.py) = creates ping-pong WebP animations from video files
- [video_to_image_composite.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_to_image_composite.py) = converts video frames to composite images
- [image_psd_to_timelapse_anim.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_psd_to_timelapse_anim.py) = Converts PSD layers to timelapse animations, UI and CLI, exports to video gif or webp or webm. updated to use [image_psd_to_timelapse_export.jsx](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_psd_to_timelapse_export.jsx) a photoshop javascript to do the exporting faster 
- <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/image_psd_to_timelapse_anim.png?raw=true" height="120" />
- [video_editor_word_rating.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_editor_word_rating.py) = GUI tool to rate video frames using words 
- [video_review_and_rank_multi_project.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/video_review_and_rank_multi_project.py) =UI for reviewing and ranking video files

# audio tools
- [voice_action_organizer.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/voice_action_organizer.py) = GUI tool for offline speech recognition (using Vosk) to trigger hotkeys or move selected files in Windows Explorer using spoken commands. JSON action management. Requires the [Vosk speech model](https://alphacephei.com/vosk/models)
- <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/voice_action_organizer.png?raw=true" height="120" />

# auto1111 webui project workflow
earlier versions of this project utilized the auto1111 webui , these are examples of that workflow:
- requires [auto1111 webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) with --api for image synthesis
- each "project" is a folder with a source image ( target img2img ) , a .project file ( settings overrides ) , and a 'selected' subfolder containing synthesized images . the python tools included help to generate such a structure and to then batch process multiple projects . 
- [gen_project_files_from_images.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_project_files_from_images.py)  > [gen_batch_prompts_in_projects.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_batch_prompts_in_projects.py) > [sd_batch_image_gen_auto1111_webui.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_batch_image_gen_auto1111_webui.py)
- [gen_batch_prompts_in_projects.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_batch_prompts_in_projects.py) = searchs folders recursively for .project files , for each project gathers the metadata image prompts and generates the local and project-wide batch files for image generation ,  prompt variants
- [gen_image_variant_grid_explore.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_image_variant_grid_explore.py) = a user interface to view generated images with randomized lora strength variants arranged as 3x3 grid , selecting a variant then becomes the center and new variants are generated , in this way navigating spatially toward lora strength settings
- [projects_from_civitai_info.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/projects_from_civitai_info.py) = creates project structures from Civitai model information
- [projects_from_images.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/projects_from_images.py) = creates project structures from a folder of images
- [gen_project_files_from_images.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_project_files_from_images.py) = given a folder of images create named folders and project files for each
- [sd_batch_image_gen_auto1111_webui.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_batch_image_gen_auto1111_webui.py) = a basic controller of stable diffusion auto1111 webui api , includes specific arguments to cycle through each prompt/negative pair , each target img2img , each checkpoint

example for texture synthesis = a low resolution source images of a stone brick pattern , the 'selected' folder contains multiple images of different stone textures synthesized using stable diffusion containing the prompt/negative in their metadata . [gen_batch_prompts_in_projects.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_batch_prompts_in_projects.py) gathers the prompt/negative pairs from 'selected' and randomly combines into a new list of variants , a local and project-wide .bat is generated that will use the auto1111 webui api via [sd_batch_image_gen_auto1111_webui.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_batch_image_gen_auto1111_webui.py) to run img2img with controlnet for all the prompt variants , across multiple checkpoints , saving the variants into each projects 'output' subfolder . 

this workflow is now recreated in comfyui using the projects [custom nodes](https://github.com/CorvaeOboro/sd_project_tools/blob/main/comfyui/)

# LICENSE
- free to all , [creative commons zero CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) , free to re-distribute , attribution not required