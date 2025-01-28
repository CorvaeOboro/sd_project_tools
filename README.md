# sd_project_tools
stable diffusion project tools , focused on batch processing image generation variants . a collection of tools for interacting with image synthesis projects , organizing , reviewing , and generating . 

# install
- install python 3.10
- [download sd_project_tools](https://github.com/CorvaeOboro/sd_project_tools/archive/refs/heads/master.zip)
- pip install -r [requirements.txt](https://github.com/CorvaeOboro/sd_project_tools/blob/main/requirements.txt)

# Review and Ranking tools
- [image_review_and_rank.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_review_and_rank.py) = image viewer from a folderpath , quickly rank images into subfolders using 1,2, or 3 . navigate with arrows . view as tiled texture with T 
- [image_review_and_rank_multi_project.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_review_and_rank_multi_project.py) = project image reviewer , quickly rank images into subfolders using left click = 1 and right click = 2 , colorizes by amount 

# ComfyUI custom nodes
- [Load Image FilePath Out](/comfyui/ComfyUI_OBORO_LoadImageFilePathOut/load_image_filepath_out.py) = Similar to the load image node, additionaly outputs the filepath and folderpath of the loaded image to strings
- [Load Text File Graceful](/comfyui/ComfyUI_OBORO_LoadTextFileGraceful/load_text_file_graceful.py) = Loads text as string , handling invalid files gracefully without crashing
- [LoRA Strength Variants](/comfyui/ComfyUI_OBORO_LoraStrengthVariants/lora_strength_variants.py) = Processes LoRA strings with options to randomize Strength or highlight random LoRAs , within a maximum total and individual strength limits
- [Save Image Extended FolderPath](/comfyui/ComfyUI_OBORO_SaveImageExtendedFolderPath/save_image_extended_folderpath.py) = Save image of external folder path
- [String To String Safe For Filename](/comfyui/ComfyUI_OBORO_StringToStringSafeForFilename/string_safe_for_filename.py) = Converts text into filename-safe text by replacing invalid and unfavored characters.

# model info
- [sd_civitai_info_get.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_civitai_info_get.py) = gets info and preview for model checkpoints and LoRAs , similar to webui civitai helper but standalone
- [sd_sort_civitai_files.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_sort_civitai_files.py) = sorts model checkpoints and LoRAs based on the info from corresponding civitai info , models by base model , then by type .

# project tools
- [gen_batch_prompts_in_projects.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_batch_prompts_in_projects.py) = searchs folders recursively for .project files , for each project gathers the metadata image prompts and generates the local and project-wide batch files for image generation ,  prompt variants . 
- [gen_project_files_from_images.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_project_files_from_images.py) = given a folder of images create named folders and project files for each . 
- [sd_batch_image_gen_auto1111_webui.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_batch_image_gen_auto1111_webui.py) = a basic controller of stable diffusion auto1111 webui api , includes specific arguments to cycle through each prompt/negative pair , each target img2img , each checkpoint . 
- [gen_image_variant_grid_explore.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_image_variant_grid_explore.py) = a user interface to view generated images with randomized lora strength variants arranged as 3x3 grid , selecting a variant then becomes the center and new variants are generated , in this way navigating spatially toward lora strength settings

# image prompt tools
- [image_text_prompt_tools.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_text_prompt_tools.py) = drag drop image to view prompt and negative . copy prompts to work area to merge multiple prompts together without duplicates . options to simplify strengths ( removing all parathesis ) , and scale lora strengths relative to a target maximum . 
- [lora_variants.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/lora_variants.py) = input a prompt with loras and generate all permutations of strengths , within a range of total lora strength and per lora strengths . the output can then be used for x/y plot or as wildcard . 


# auto1111 webui project workflow
each "project" is a folder with a source image ( target img2img ) , a .project file ( settings overrides ) , and a 'selected' subfolder containing synthesized images . the python tools included help to generate such a structure and to then batch process multiple projects . 

example for texture synthesis = a low resolution source images of a stone brick pattern , the 'selected' folder contains multiple images of different stone textures synthesized using stable diffusion containing the prompt/negative in their metadata . gen_batch_prompts_in_projects.py gathers the prompt/negative pairs from 'selected' and randomly combines into a new list of variants , a local and project-wide .bat is generated that will use the auto1111 webui api to run img2img with controlnet for all the prompt variants , across multiple checkpoints , saving the variants into each projects 'output' subfolder . 

requires [auto1111 webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) with --api for image synthesis

# LICENSE
- free to all , [creative commons zero CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) , free to re-distribute , attribution not required