#// BATCH IMAGE GEN using STABLEDIFFUSION AUTO111 WEBUI API
#// for each image , and prompt lists in a project folder , synthesize img2img with multiple checkpoints   
#// using auto1111 api with extensions asymmetric tiling ( seamless texture ) and adetailer ( faces ) and controlnet ( canny + depth ) 
import json
import requests
import io
import base64
from PIL import Image, PngImagePlugin
import random
import datetime
import time
import glob
import os
import argparse
from random import shuffle
from PIL import Image
from PIL.ExifTags import TAGS
import pathlib
import re
from collections import defaultdict

#//========================================================================================
# DEFAULTS - can be ovveriden by args parse
SHUFFLE_PROMPTS = True
CONTROLNET_STRENGTH = 0.01
TILING_SETTING = False
DENOISE_STRENGTH = 0.99
API_URL = "http://127.0.0.1:7860"
CHECKPOINTS_ARRAY  = ["neurogenV10_v10.safetensors","juggernaut_v19.safetensors"]

#//========================================================================================

def generate_img2img_set(image_filename,prompt_input,prompt_negative,sd_model,seed_start,num_images,output_dir,input_width,input_height):
    #//========================================================================================
    init_image_filepath  =image_filename
    encoded = base64.b64encode(open(init_image_filepath, "rb").read()) 
    encodedString=str(encoded, encoding='utf-8')
    init_image_encoded ='data:image/png;base64,' + encodedString

    prompt =  prompt_input
    negative_prompt = prompt_negative
    #// SET MODEL
    sd_model_checkpoint = sd_model # currently filename only , previously was filename+hash
    sdwebapi_options = requests.get(url= str(API_URL) + '/sdapi/v1/options')
    sdwebapi_options_json = sdwebapi_options.json()
    sdwebapi_options_json['sd_model_checkpoint'] = sd_model_checkpoint
    requests.post(url= str(API_URL) + '/sdapi/v1/options', json=sdwebapi_options_json)

    #//========================================================================================
    payload = {
        "alwayson_scripts":{
            "Asymmetric tiling":{"args":[TILING_SETTING,True,True,0,-1]}, # tiling X and Y 
            "ControlNet": {"args": [
                {"batch_images": "", "control_mode": "Balanced", "enabled": True, "image": { "image" :init_image_encoded,"mask" :None, }, "input_mode": "simple", "model": "control_v11f1p_sd15_depth [cfd03158]", "module": "depth_midas", "output_dir": "", "processor_res": 512, "resize_mode": "Crop and Resize", "threshold_a": -1, "threshold_b": -1, "weight": CONTROLNET_STRENGTH},
                {"batch_images": "", "control_mode": "Balanced", "enabled": True, "image": { "image" :init_image_encoded,"mask" :None, }, "input_mode": "simple", "model": "control_v11p_sd15_canny [d14c016b]", "module": "canny", "output_dir": "", "processor_res": 512, "resize_mode": "Crop and Resize", "threshold_a": 100, "threshold_b": 200, "weight": CONTROLNET_STRENGTH},
                ]},
            "AnimateDiff" : {"args" : [{"enable" : False, }]}, # this extension gives warning errors if not set to false 
            "Conditioning Highres.fix (for sd-v1-5-inpainting)" :{"args" :[0]},  # this extension gives warning errors if not set to 0 args
            "ADetailer": {"args": [True,{"ad_cfg_scale": 7, "ad_checkpoint": "Use same checkpoint", "ad_confidence": 0.3, "ad_controlnet_weight": 1, "ad_denoising_strength": 0.4, "ad_dilate_erode": 4, "ad_inpaint_height": 512, "ad_inpaint_only_masked_padding": 32, "ad_inpaint_width": 512, "ad_mask_blur": 4, "ad_model": "face_yolov8n.pt", "ad_negative_prompt": "", "ad_noise_multiplier": 1, "ad_prompt": "", "ad_sampler": "Euler a", "ad_steps": 28,}]},
            },
        "init_images": [
                init_image_encoded
                ]  ,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "n_iter": 1,  # FORCING 1 iteration here , so the results are saved itertively , num iteration handled by exterior for loop
        "seed": seed_start,
        "steps": 70,
        "cfg_scale": 8,
        "width": input_width,"height": input_height,
        "sampler_index": "DPM++ 2M Karras",
        #//=============================================================
        "denoising_strength": DENOISE_STRENGTH,
        "sd_model_checkpoint": sd_model_checkpoint,
        "override_settings_restore_afterwards": False,
        "override_settings" :{"sd_model_checkpoint" :sd_model_checkpoint}, 
        #//========================= HI RES FIX
        "conditioning_highres_fix": 0,
        "enable_hr" :False,
        "hr_negative_prompt" : negative_prompt,
        "hr_prompt" :prompt,
        "hr_resize_x" :0,
        "hr_resize_y" :0,
        "hr_scale" :2,
        "hr_second_pass_steps" :15,
        "hr_upscaler" :"Latent",
    }
    override_settings = {}
    
    override_settings["sd_model_checkpoint"] = sd_model_checkpoint
    override_payload = {
                    "override_settings": override_settings
                }
    payload.update(override_payload)

    #//========================================================================================
    #response = requests.post(url=f'{url}/sdapi/v1/txt2img', json=payload)
    response = requests.post(url=str(API_URL) + '/sdapi/v1/img2img', json=payload)
    r = response.json()
    #//========================================================================================

    prompt_short = string_replace_safe_filename(prompt)

    #//========================================================================================
    image_count = 0
    for i in r['images']:
        image = Image.open(io.BytesIO(base64.b64decode(i.split(",",1)[0])))

        png_payload = {
            "image": "data:image/png;base64," + i
        }
        response2 = requests.post(url= str(API_URL) + '/sdapi/v1/png-info', json=png_payload)

        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("parameters", response2.json().get("info"))

        now = datetime.datetime.now()
        timebased_seed = int(now.strftime("%Y%m%d%H%M%S"))
        imagename = output_dir + "/" + str(timebased_seed) + "_" + prompt_short + "_" + str(image_count) + ".png"
        image_count +=1


        os.makedirs(output_dir, exist_ok=True)
        print("SAVING IMAGE == " + imagename)
        if ( image_count == 1 ): # FIRST IMAGE ONLY NOT CONTROLNET , disable for debug to get the controlnet images
            image.save(imagename, pnginfo=pnginfo)

def string_replace_safe_filename(input_string):
    modified_string = re.sub(r"<lora:", "_", input_string) # Remove specific syntax "<lora:" and replace it with "_"
    modified_string = re.sub(r"<lyco:", "_", input_string) # Remove specific syntax "<lyco:" and replace it with "_"
    modified_string = re.sub("'", "", modified_string)# apostrophe is collapsed , all possesive plurals are collapsed 
    modified_string = re.sub("-", "", modified_string)# hyphen is collapsed , all combo-words are collapsed into combowords
    modified_string = re.sub(r"[^a-zA-Z]", "_", input_string) # Replace all non-letters with underscores
    modified_string = re.sub(r"_+", "_", modified_string)# Ensure no consecutive underscores
    modified_string = modified_string[:150]
    return modified_string

def generate_from_folder(target_directory):
    # for each file in folder
    image_set = glob.glob(os.path.join(target_directory, "*.jpg")) + glob.glob(os.path.join(target_directory, "*.png"))+ glob.glob(os.path.join(target_directory, "*.bmp"))
    for current_image in image_set:
        return

    # get image parameters
    # generate new image from parameters with adetailer or other modified options
    return

def load_image(file_path):
    image = Image.open(file_path)

    if pathlib.Path(file_path).suffix == ".jpg":
        exif_data = image._getexif()
        if exif_data:
            exif_text = ""
            for tag_id in exif_data:
                tag = TAGS.get(tag_id, tag_id)
                value = exif_data.get(tag_id)
                if isinstance(value, bytes):
                    value = value.decode("utf-8", "ignore")
                exif_text += f"{tag}: {value}\n"
            #self.textbox.setPlainText(exif_text)
        else:
            return
            #self.textbox.setPlainText("No EXIF data found")
    if pathlib.Path(file_path).suffix == ".png":
        print("PNG IMAGE")
        with open(file_path, 'rb') as f:
            png_raw = f.read(10000).decode('windows-1252', errors='ignore')
            #png_raw =  f.read(1000)
            #print(str(png_raw))

        parameter_dict = {
            "prompt": """tEXtparameters([\S\s]*)Negative prompt:""",
            "prompt_neg": """Negative prompt:([\S\s]*)Steps: """,
            "modelhash": """Model hash: ([\S\s]*),""",
            "modelname": """Model: ([\S\s]*),""",
            "seed": """Seed: ([\S\s]*),""",
            "size": """Size: ([\S\s]*),""",
            "cfg_scale": """CFG scale: ([\S\s]*),""",
            "sampler": """Sampler: ([\S\s]*),""",
            "steps": """Steps: ([\S\s]*),""",
        }
        output_dict = {}
        for key, value in parameter_dict.items():
            regex_current = value
            matches_current = re.search(regex_current, str(png_raw), re.DOTALL)
            if matches_current:
                extracted_text_current = matches_current.group(1)
                extracted_text_current = extracted_text_current.strip()
                extracted_text_current = extracted_text_current.replace(",","")
            output_dict[key] = extracted_text_current


#//========================================================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--init-img-folder", type=str,nargs="?", help="folderpath to the image guides img2img ", default="./input")
    parser.add_argument("--promptfolder", type=str,nargs="?", help="folderpath to where prompt and negative prompt txt is kept , depreceated", default="./input")
    parser.add_argument("--prompttxt", type=str,nargs="?", help="filepath to txt prompts", default="./input/prompt.txt")
    parser.add_argument("--promptnegtxt", type=str,nargs="?", help="fileath to negative txt prompts", default="./input/negative_prompt.txt")
    parser.add_argument("--outdir", type=str,nargs="?", help="folderpath to save output images", default="./input/output")
    parser.add_argument("--num", type=int,nargs="?", help="number of images to generate per initimage / sdmodel set", default=4)
    parser.add_argument("--width", type=int,nargs="?", help="image width", default=512)
    parser.add_argument("--height", type=int,nargs="?", help="image hieght", default=512)
    parser.add_argument("--models", nargs='+', help="List of model string arrays", default=CHECKPOINTS_ARRAY)
    parser.add_argument("--denoise_strength", type=float, help="Denoising strength for the image generation", default=DENOISE_STRENGTH)
    parser.add_argument("--tiling_setting", type=bool, help="Tiling setting (True/False)", default=TILING_SETTING)
    parser.add_argument("--controlnet_strength", type=float, help="ControlNet strength", default=CONTROLNET_STRENGTH)

    args_parsed = parser.parse_args()
    #//========================================================================================

    target_directory = args_parsed.init_img_folder
    print("IMAGES = " + target_directory)
    image_set = glob.glob(os.path.join(target_directory, "*.jpg")) + glob.glob(os.path.join(target_directory, "*.png"))+ glob.glob(os.path.join(target_directory, "*.bmp"))
    shuffle(image_set)
    #print("IMAGES = " + image_set)
    out_directory = args_parsed.outdir
    num_images = args_parsed.num
    width = args_parsed.width
    height = args_parsed.height
    sd_model_list = args_parsed.models
    denoise_strength = args_parsed.denoise_strength
    tiling_setting = args_parsed.tiling_setting
    controlnet_strength = args_parsed.controlnet_strength
    #sd_model_list = ["neurogenV10_v10.safetensors","juggernaut_v19.safetensors"]
    

    #//=================================================
    #PROMPTS
    #prompt_directory = args_parsed.promptfolder
    #prompt_txtfile = prompt_directory + "/" + "prompt.txt"
    prompt_txtfile = args_parsed.prompttxt
    print("PROMPTS = " + prompt_txtfile)
    prompt_list = []
    prompt_list_text = open(prompt_txtfile,'r')
    prompt_list_text_list = prompt_list_text.readlines()
    for prompt_current in prompt_list_text_list:
        prompt_final = prompt_current.strip()
        if prompt_final != "" :
            prompt_list.append(prompt_final)

    #//=================================================
    #NEGATIVE PROMPTS
    prompt_neg_list = []
    prompt_negative = ""
    
    #prompt_neg_directory = args_parsed.promptfolder
    #prompt_neg_txtfile = prompt_neg_directory + "/" + "prompt_negative.txt"
    prompt_neg_txtfile = args_parsed.promptnegtxt
    prompt_neg_list = []
    prompt_neg_list_text = open(prompt_neg_txtfile,'r')
    prompt_neg_list_text_list = prompt_neg_list_text.readlines()
    for prompt_neg_current in prompt_neg_list_text_list:
        prompt_neg_final = prompt_neg_current.strip()
        if prompt_neg_final != "" :
            prompt_neg_list.append(prompt_neg_final)
    
    if SHUFFLE_PROMPTS:
        shuffle(prompt_list)
        shuffle(prompt_neg_list)

    for current_sd_model in sd_model_list:
        for current_image in image_set:
            prompt_count = 0
            for current_prompt in prompt_list:

                image_filename  = str(current_image)
                prompt_input =  current_prompt
                if prompt_neg_list:
                    prompt_negative_number_modulo = int(( prompt_count%len(prompt_neg_list) ) * 1)
                    print("prompt_negative_number_modulo = " + str(prompt_negative_number_modulo))
                    prompt_negative = str(prompt_neg_list[prompt_negative_number_modulo]) # change to each
                sd_model = current_sd_model
                seed_start=-1
                num_images=2
                for current_iteration in range(num_images):
                    print( "GEN IMG2IMG == " + image_filename + "  ==  " + sd_model)
                    print( "PROMPT == " + current_prompt )
                    generate_img2img_set(image_filename,prompt_input,prompt_negative,sd_model,seed_start,1,out_directory,width,height)
                prompt_count += 1


#//========================================================================================
if __name__ == "__main__":
    main()