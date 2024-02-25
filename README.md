# sd_project_tools
stable diffusion project tools , focused on batch processing image generation variants . 

a collection of tools for large scale asset synthesis . each "project" is a folder with a source image ( target img2img ) , a .project file ( settings overrides ) , and a 'selected' subfolder containing synthesized images . the python tools included help to generate such a structure and to then batch process multiple projects . 

example for texture synthesis = a low resolution source images of a stone brick pattern , the 'selected' folder contains multiple images of different stone textures synthesized using stable diffusion containing the prompt/neg in their metadata . gen_batch_prompts_in_projects.py gathers the prompt/neg pairs from 'selected' and randomly combines into a new list of variants , a local and project-wide .bat is generated that will use the auto1111 webui api to run img2img with controlnet for all the prompt variants , across multiple checkpoints , saving the variants into each projects 'output' subfolder . 

requires [auto1111 webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) with --api for image synthesis

# install
- install python 3.10
- pip install -r requirements.txt

# project tools
- [gen_batch_prompts_in_projects.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_batch_prompts_in_projects.py) = searchs folders recursively for .project files , for each project gathers the metadata image prompts and generates the local and project-wide batch files for image generation ,  prompt variants . 
- [gen_project_files_from_images.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/gen_project_files_from_images.py) = given a folder of images create named folders and project files for each . 
- [sd_batch_image_gen_auto1111_webui.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/sd_batch_image_gen_auto1111_webui.py) = a basic controller of stable diffusion auto1111 webui api , includes specific arguments to cycle through each prompt/neg pair , each target img2img , each checkpoint . 

# image prompt tools
- [image_text_prompt_tools.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_text_prompt_tools.py) = drag drop image to view prompt and negative prompt . copy prompts to work area and easily merge multiple prompts together without duplicate prompt words . simplify strengths ( removing all parathesis ) , and scale lora strengths relative to a target maximum . 
- [lora_variants.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/lora_variants.py) = input a prompt with loras and generate all permutations of strengths , up to a target total strength and a local maximum . the output can then be used for x/y plot or as wildcard . 

# review
- [image_review_and_rank.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/image_review_and_rank.py) = image viewer from a folderpath , quickly rank images into subfolders using 1,2, or 3 . navigate with arrows . view as tiled texture with T 