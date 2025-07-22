
# ARCHIVE
the archive contains previous singular tools that have been combined and the previous auto1111 project workflow and tools , that has now been replaced by the comfyui custom nodes and workflow .

# archived tensor tools
- [tensor_info_civitai_get.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/archive/tensor_info_civitai_get.py) = gets info from civitai 
- [tensor_sort_civitai_files.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/archive/tensor_sort_civitai_files.py) = sorts by info by model type 
- [tensor_remove_duplicate.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/archive/tensor_remove_duplicate.py) = removes duplicates by hash
- [tensor_sort_civitai_by_category.py](https://github.com/CorvaeOboro/sd_project_tools/blob/main/archive/tensor_sort_civitai_by_category.py) = sorts by info into NSFW and POI category subfolder

# Auto1111 WebUI Project Workflow
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