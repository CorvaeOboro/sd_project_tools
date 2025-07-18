<p align="center">
  <img src="https://github.com/CorvaeOboro/sd_project_tools/blob/main/docs/sd_project_tools_header_long.png?raw=true" height="120" /> 
</p>

# ComfyUI - Custom Nodes - Oboro

A collection of custom nodes for ComfyUI, focused on project strutures and variations.
- for example loading random files by string , randomizing lora string strength 
- and additions to load and save nodes for extra folderpath and filename outputs 
- each node is self-contained and could be installed separately if prefer 

# install 
- install through the manager or download as  into the ComfyUI `custom_nodes` directory 
- or install individual copying a node folder into the ComfyUI `custom_nodes` directory 

---


<table>
  <thead>
    <tr>
      <th>Checkpoint</th>
      <th>LoRA</th>
      <th>Load</th>
      <th>Image</th>
      <th>Text</th>
      <th>Save</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <ul style="list-style-type: disc; padding-left: 1.2em;">
          <li><a href="./ComfyUI_OBORO_CheckpointLoaderByStringDirty/checkpoint_loader_by_string_dirty.py">Checkpoint Loader By String Dirty</a></li>
          <li><a href="./ComfyUI_OBORO_RandomCheckpointSelector/random_checkpoint_selector.py">Random Checkpoint Selector</a></li>
          <li><a href="./ComfyUI_OBORO_ModelNameToString/model_name_to_string.py">Model Name To String</a></li>
        </ul>
      </td>
      <td>
        <ul style="list-style-type: disc; padding-left: 1.2em;">
          <li><a href="./ComfyUI_OBORO_LoraStrengthVariants/lora_strength_variants.py">LoRA Strength Variants</a></li>
          <li><a href="./ComfyUI_OBORO_LoraStrengthMultiplier/lora_strength_multiplier.py">LoRA Strength Multiplier</a></li>
          <li><a href="./ComfyUI_OBORO_LoraVisualizer/lora_visualizer.py">LoRA Visualizer</a></li>
        </ul>
      </td>
      <td>
        <ul style="list-style-type: disc; padding-left: 1.2em;">
          <li><a href="./ComfyUI_OBORO_LoadImageFilePathOut/load_image_filepath_out.py">Load Image FilePath Out</a></li>
          <li><a href="./ComfyUI_OBORO_LoadImageRandomVariants/load_image_random_variant.py">Load Image Random Variants</a></li>
          <li><a href="./ComfyUI_OBORO_BatchLoadSubfolder/batch_load_subfolders.py">Batch Load Subfolder</a></li>
          <li><a href="./ComfyUI_OBORO_LoadTextFileGraceful/load_text_file_graceful.py">Load Text File Graceful</a></li>
        </ul>
      </td>
      <td>
        <ul style="list-style-type: disc; padding-left: 1.2em;">
          <li><a href="./ComfyUI_OBORO_ImageContrastLimitedAdaptiveHistogramEqualization/image_CLAHE.py">Image CLAHE</a></li>
          <li><a href="./ComfyUI_OBORO_ImageMultiScaleRetinexColorRestoration/image_MSRCR.py">Image Multi-Scale Retinex Color Restoration</a></li>
          <li><a href="./ComfyUI_OBORO_VideoResizeMatte/image_resize_matte_video.py">Video Resize Matte</a></li>
          <li><a href="./ComfyUI_OBORO_FluxKontextImageScaleOptions/flux_kontext_image_scale_options.py">Flux Kontext Image Scale Options</a></li>
        </ul>
      </td>
      <td>
        <ul style="list-style-type: disc; padding-left: 1.2em;">
          <li><a href="./ComfyUI_OBORO_StringToStringSafeForFilename/text_to_text_safe_for_filename.py">Text To Filename Safe Text</a></li>
          <li><a href="./ComfyUI_OBORO_StringTokenCount/text_token_count.py">Text Token Count</a></li>
          <li><a href="./ComfyUI_OBORO_TextStrengthMultiplier/text_strength_multiplier.py">Text Strength Multiplier</a></li>
        </ul>
      </td>
      <td>
        <ul style="list-style-type: disc; padding-left: 1.2em;">
          <li><a href="./ComfyUI_OBORO_SaveImageExtendedFolderPath/save_image_extended_folderpath.py">Save Image Extended FolderPath</a></li>
          <li><a href="./ComfyUI_OBORO_SaveAnimatedWebPExtendedFolderPath/save_animated_webp_extended_folderpath.py">Save Animated WebP Extended FolderPath</a></li>
        </ul>
      </td>
    </tr>
  </tbody>
</table>

---

## Checkpoint & Model Utilities
- **[Checkpoint Loader By String Dirty](./ComfyUI_OBORO_CheckpointLoaderByStringDirty/checkpoint_loader_by_string_dirty.py)**  
  Loads a Stable Diffusion checkpoint by matching a string input (full path, relative path, or filename) to any registered checkpoint.
- **[Random Checkpoint Selector](./ComfyUI_OBORO_RandomCheckpointSelector/random_checkpoint_selector.py)**  
  Randomly selects a checkpoint from a category/folder at a set interval for reproducible model rotation.
- **[Model Name To String](./ComfyUI_OBORO_ModelNameToString/model_name_to_string.py)**  
  Converts a model object to its name as a string for workflow use.

## LoRA Utilities
- **[LoRA Strength Variants](./ComfyUI_OBORO_LoraStrengthVariants/lora_strength_variants.py)**  
  Parses LoRA strings and randomizes or highlights strengths within specified limits.
- **[LoRA Strength Multiplier](./ComfyUI_OBORO_LoraStrengthMultiplier/lora_strength_multiplier.py)**  
  Multiplies and caps LoRA strengths, with options for total and individual caps.
- **[LoRA Visualizer](./ComfyUI_OBORO_LoraVisualizer/lora_visualizer.py)**  
  Visualizes LoRA strengths in prompt text as a word plot image.

## Load
- **[Load Image FilePath Out](./ComfyUI_OBORO_LoadImageFilePathOut/load_image_filepath_out.py)**  
  Loads an image from a file path and outputs the image, mask, file name, and folder path.
- **[Load Image Random Variants](./ComfyUI_OBORO_LoadImageRandomVariants/load_image_random_variant.py)**  
  Loads a random variant of an image from a folder, with debug and suffix options.
- **[Batch Load Subfolder](./ComfyUI_OBORO_BatchLoadSubfolder/batch_load_subfolders.py)**  
  Loads all images from a subfolder as a batch, with options for limits and indexing.
- **[Load Text File Graceful](./ComfyUI_OBORO_LoadTextFileGraceful/load_text_file_graceful.py)**  
  Loads text from a file, gracefully handling missing/invalid files.

## Image Processing
- **[Image CLAHE (Contrast Limited Adaptive Histogram Equalization)](./ComfyUI_OBORO_ImageContrastLimitedAdaptiveHistogramEqualization/image_CLAHE.py)**  
  Enhances local image contrast using CLAHE.
- **[Image Multi-Scale Retinex Color Restoration](./ComfyUI_OBORO_ImageMultiScaleRetinexColorRestoration/image_MSRCR.py)**  
  Applies Multi-Scale Retinex with Color Restoration for advanced dynamic range and color enhancement.
- **[Video Resize Matte](./ComfyUI_OBORO_VideoResizeMatte/image_resize_matte_video.py)**  
  Resizes video frames with matte options for compositing.
- **[Flux Kontext Image Scale Options](./ComfyUI_OBORO_FluxKontextImageScaleOptions/flux_kontext_image_scale_options.py)**  
  Resizes images for optimal Flux Kontext input, with cropping/stretching options.

## Text & Prompt Utilities
- **[String To String Safe For Filename](./ComfyUI_OBORO_StringToStringSafeForFilename/string_safe_for_filename.py)**  
  Converts text into a filename-safe string.
- **[String Token Count](./ComfyUI_OBORO_StringTokenCount/string_token_count.py)**  
  Counts tokens in a string (useful for prompt engineering).
- **[Text Strength Multiplier](./ComfyUI_OBORO_TextStrengthMultiplier/text_strength_multiplier.py)**  
  Multiplies the strength of text prompt components.

## Save
- **[Save Image Extended FolderPath](./ComfyUI_OBORO_SaveImageExtendedFolderPath/save_image_extended_folderpath.py)**  
  Saves images to an external folder path, supporting custom folder and filename formats.
- **[Save Animated WebP Extended FolderPath](./ComfyUI_OBORO_SaveAnimatedWebPExtendedFolderPath/save_animated_webp_extended_folderpath.py)**  
  Saves animated WebP images to a user-specified folder.

---
