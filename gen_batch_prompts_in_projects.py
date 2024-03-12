# EXTRACT THE PROMPT FROM IMAGES METADATA DESCRIPTION 
# searches for folders with project files in it , extract the image metadata prompts , and create combined prompts and scripts for each project
# randomly combines prompt text , balance loras , generating permutations 
import os
import glob
import re
import datetime
import random
import json
from tqdm import tqdm
from pathlib import Path
from sdparsers import ParserManager

#PROJECT_ROOT_FOLDERPATH = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOLDERPATH = 'D:/CODE/STABLEDIFFUSION_AUTO/PROJECTS/'
API_PATH = 'D:/CODE/SD_PROJECT_BATCH_TOOLS/'
API_PY = 'sd_batch_image_gen_auto1111_webui.py'
WORD_LIMIT = 7000  # Word limit for the word_limiter function 
PROMPT_STRENGTH = 0.3
PROMPT_RANDOM_TOTAL = 400
ERROR_LOG_FILE = 'sd_batch_image_gen_auto1111_webui_error_log.txt'

# Add a function to read JSON configuration from a project file
def read_project_config(project_file):
    try:
        with open(project_file, 'r') as file:
            return json.load(file)
    except json.JSONDecodeError as e:
        log_error(f"Error reading JSON from {project_file}: {e}")
        return {}
    
def log_error(error_message): # log errors
    with open(ERROR_LOG_FILE, 'a') as log_file:
        log_file.write(error_message + '\n')

def safe_run(func): # Decorator for safe execution and error logging
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_message = f"Error in {func.__name__}: {e}"
            print(error_message)
            log_error(error_message)
            return None
    return wrapper

# STRING UTILS=========================================================================
@safe_run
def string_replace_fix_multiline(input_string):
    replacements = ['\n', 'BREAK', ',', '  ']
    for r in replacements:
        input_string = input_string.replace(r, " , ")
    return re.sub(r',\s+,', " , ", input_string).strip()

@safe_run
def string_replace_fix_slashes(input_string):
    return input_string.replace('\\', '/').replace('//', '/')

@safe_run
def word_limiter(input_string):
    return " ".join(input_string.strip().split(" ")[:WORD_LIMIT])

@safe_run
def get_image_files(directory, extensions):
    return [item for ext in extensions for item in glob.glob(f'{directory}/*.{ext}')]

# PARSE EXTRACT PROMPT STRINGS
def parse_sd_file(image_input_parse): 
    # Parse prompts from image metadata and return a tuple of (positive prompt, negative prompt).
    try:
        parser_manager = ParserManager()
        prompt_data = parser_manager.parse(image_input_parse)
        if prompt_data and prompt_data.prompts:
            return [(prompt.value, negative_prompt.value) if prompt and negative_prompt else (None, None) for prompt, negative_prompt in prompt_data.prompts][0]  # Ensure a tuple is always returned
    except Exception as e:
        print(f"Error parsing file {image_input_parse}: {e}")
    return (None, None)  # Return a tuple with two None values in case of an error or no data

@safe_run
def extract_prompts_from_files(target_directory):
    print(f"EXTRACTING IMAGE PROMPTS FROM ... {target_directory}")
    directory_input = Path(target_directory) / 'selected'
    file_list = get_image_files(directory_input, ['jpeg', 'jpg', 'png'])

    output_project_name = Path(target_directory).name
    output_filename_pos = f'prompt_list_{output_project_name}.txt'
    output_filename_neg = f'negative_prompt_list_{output_project_name}.txt'

    output_file_pos = Path(target_directory) / output_filename_pos
    output_file_neg = Path(target_directory) / output_filename_neg

    multi_text_prompt = set()
    multi_text_negative_prompt = set()

    for current_image in file_list:
        prompt, prompt_neg = parse_sd_file(current_image)
        if prompt:
            current_prompt = string_replace_fix_multiline(prompt)
            multi_text_prompt.add(current_prompt)
        if prompt_neg:
            current_neg_prompt = string_replace_fix_multiline(prompt_neg)
            multi_text_negative_prompt.add(current_neg_prompt)

    limited_prompts = [word_limiter(re.sub(r' {2,}', ' ', prompt)) for prompt in multi_text_prompt]
    limited_neg_prompts = [word_limiter(re.sub(r' {2,}', ' ', prompt)) for prompt in multi_text_negative_prompt]

    with open(output_file_pos, 'w', encoding='utf8') as textfile_output_final:
        textfile_output_final.write('\n'.join(limited_prompts))

    with open(output_file_neg, 'w', encoding='utf8') as textfile_output_neg_final:
        textfile_output_neg_final.write('\n'.join(limited_neg_prompts))

@safe_run
def extract_prompts_from_txt(target_directory):
    output_project_name = Path(target_directory).name
    output_filename = f'prompt_list_txt_{output_project_name}.txt'
    output_file = os.path.join(target_directory, output_filename)

    file_list = glob.glob(os.path.join(target_directory, '*.txt'))
    excluded_files = {f"prompt_list_random_{output_project_name}", f"python_random_{output_project_name}"}

    multi_text_prompt = set()
    for current_txt in file_list:
        if Path(current_txt).stem not in excluded_files:
            with open(current_txt, 'r', encoding='utf8') as textfile_input:
                multi_text_prompt.update([line.strip() for line in textfile_input if line.strip() and "python script" not in line])

    limited_prompts = [word_limiter(re.sub(r' {2,}', ' ', prompt)) for prompt in multi_text_prompt]

    with open(output_file, 'w', encoding='utf8') as textfile_output_final:
        textfile_output_final.write('\n'.join(limited_prompts))

#// RANDOM COMBINE FROM TXT ===================================
@safe_run
def get_file_list(directory, exclude_files):
    file_list = glob.glob(str(directory / '*.txt'))
    return [file for file in file_list if Path(file).name not in exclude_files]

@safe_run
def read_lines_from_file(file):
    with open(file, 'r', encoding='utf8') as file_handle:
        return [line.strip() for line in file_handle if line.strip()]

@safe_run
def combine_prompts(file_list):
    combined_lines = []
    for file in file_list:
        lines = read_lines_from_file(file)
        for line in lines:
            if "python script" not in line and line not in combined_lines:
                combined_lines.append(line)
    return combined_lines

@safe_run
def create_random_prompts(combined_lines, total_prompts):
    prompt_list_final_words = []
    for prompt in combined_lines:
        words = prompt.split(", ")
        prompt_list_final_words.extend([word.strip() for word in words if word.strip() not in prompt_list_final_words])

    combined_prompts = prompt_list_final_words + combined_lines
    output_lines = []
    for _ in range(total_prompts):
        random.shuffle(combined_prompts)
        current_combo_word = ', '.join(combined_prompts[:8])
        output_lines.append(word_limiter(current_combo_word))
    return output_lines

@safe_run
def random_combine_from_txt(target_directory, random_prompt_total):
    directory_input = Path(target_directory)
    output_project_name = directory_input.name

    # Separate output filenames for positive and negative prompts
    output_filename_pos = f'random_prompt_list_{output_project_name}.txt'
    output_filename_neg = f'random_negative_prompt_list_{output_project_name}.txt'
    output_file_pos = directory_input / output_filename_pos
    output_file_neg = directory_input / output_filename_neg

    # Define exclude files for positive and negative prompts
    exclude_files_pos = [f'negative_prompt_list_{output_project_name}.txt', output_filename_pos, output_filename_neg,output_filename_neg, output_filename_pos]
    exclude_files_neg = [f'prompt_list_{output_project_name}.txt', output_filename_neg, output_filename_pos]
    #exclude_both = exclude_files_pos + exclude_files_neg

    # Get file lists for positive and negative prompts
    file_list_pos = get_file_list(directory_input, exclude_files_pos)
    print("PSOIVIE = " + str(file_list_pos))
    file_list_neg = get_file_list(directory_input, exclude_files_neg)

    # Combine lines from positive and negative prompt files
    combined_lines_pos = combine_prompts(file_list_pos)
    combined_lines_neg = combine_prompts(file_list_neg)

    # Create random prompts for positive and negative
    output_lines_pos = create_random_prompts(combined_lines_pos, random_prompt_total)
    output_lines_neg = create_random_prompts(combined_lines_neg, random_prompt_total)

    # Write positive and negative random prompts to separate files
    with open(output_file_pos, 'w', encoding='utf8') as file_handle_pos:
        file_handle_pos.write('\n'.join(output_lines_pos))
    with open(output_file_neg, 'w', encoding='utf8') as file_handle_neg:
        file_handle_neg.write('\n'.join(output_lines_neg))

@safe_run
def create_script_per_init(target_directory, prompt_strength): # creates Python scripts per init image , multiple text lines of the bat shell to be gathered by the project manager 
    print("CREATING PYTHON SCRIPTS ... " + str(target_directory))
    directory_input = Path(target_directory)
    current_datetime = datetime.datetime.now()
    current_timeseed_string = current_datetime.strftime("%Y%m%d")
    output_dir_string_datetime = 'output/' + current_timeseed_string
    output_directory = directory_input / output_dir_string_datetime
    output_project_name = directory_input.name

    output_filename = 'python_random_' + output_project_name + '.txt'
    output_file = directory_input / output_filename

    random_filename = 'prompt_list_random_' + output_project_name + '.txt'
    random_file = directory_input / random_filename

    init_images_group = glob.glob(str(directory_input / '*.jpeg')) + glob.glob(str(directory_input / '*.jpg')) + glob.glob(str(directory_input / '*.png'))

    script_lines = []
    for current_image in init_images_group:
        python_script = f'''python scripts/img2img.py --init-img "{current_image}" --strength {prompt_strength} --ddim_steps 200 --scale 19 --skip_grid --seed -1 --n_samples 1 --from-file "{random_file}" --outdir "{output_directory}"'''
        script_lines.append(python_script)

    python_txt2img_script = f'''python scripts/txt2img.py --W 512 --H 512 --scale 19 --plms --skip_grid --seed -1 --n_samples 1 --from-file "{random_file}" --outdir "{output_directory}"'''
    script_lines.append(python_txt2img_script)

    if len(init_images_group) > 1:
        python_batch_script = f'''python scripts/img2img_batch.py --init-img-folder "{directory_input}" --init_random --ddim_steps 200 --scale 19 --skip_grid --seed -1 --n_samples 1 --from-file "{random_file}" --outdir "{output_directory}"'''
        script_lines.append(python_batch_script)

    with open(output_file, 'w', encoding='utf8') as textfile_output_final:
        textfile_output_final.write('\n'.join(script_lines))

#// EXTRACT PYTHON FROM TXT ===================================
@safe_run
def extract_python_from_txt(folderpath_python_txt_input):
    print("EXTRACTING PYTHON FROM TXT ...")
    file_list = glob.glob(os.path.join(folderpath_python_txt_input, '**', 'python_*.txt'), recursive=True)
    print("PYTHON FILE LIST = " + str(len(file_list)))
    output_filename = 'python_scripts_all.txt'
    output_file = os.path.join(folderpath_python_txt_input, output_filename)

    multi_text_prompt = set()
    for current_txt in file_list:
        print("EXTRACTING METADATA FROM == " + current_txt)
        with open(current_txt, 'r', encoding='utf8') as textfile_input:
            lines = [line.strip() for line in textfile_input if line.strip()]
            multi_text_prompt.update(lines)

    print("LINE COUNT = " + str(len(multi_text_prompt)))
    with open(output_file, 'w', encoding='utf8') as textfile_output_final:
        for current_multiword in multi_text_prompt:
            textfile_output_final.write(current_multiword + '\n')

    print("WORD COUNT = " + str(len(multi_text_prompt)))
    print("+++++++++++ COMPLETE +++++++++++++")

#// GENERATE LOCAL BATCH FILE FOR IMG  ===================================
@safe_run
def generate_bat_img2img(target_directory, API_PATH, API_PY):
    print("GENERATING BAT IMG2IMG ... " + str(target_directory))
    directory_input = Path(target_directory)
    current_datetime = datetime.datetime.now().strftime("%Y%m%d")
    output_dir = (directory_input / ('output/' + current_datetime)).as_posix()
    output_project_name = directory_input.name

    output_filename = '00_' + output_project_name + '.bat'
    output_file = directory_input / output_filename

    bat_commands = []
    random_prompt_filepath = (directory_input / ('random_prompt_list_' + output_project_name + '.txt')).as_posix()
    random_negative_prompt_filepath = (directory_input / ('random_negative_prompt_list_' + output_project_name + '.txt')).as_posix()
    prompt_txt_filepath = (directory_input / ('prompt_list_' + output_project_name + '.txt')).as_posix()
    promptneg_txt_filepath = (directory_input / ('negative_prompt_list_' + output_project_name + '.txt')).as_posix()

    python_batch_final_output = f'''python {API_PATH}{API_PY} --init-img-folder "{directory_input.as_posix()}" --prompttxt "{prompt_txt_filepath}" --promptnegtxt "{promptneg_txt_filepath}" --outdir "{output_dir}" --width=1024 --height=1024'''
    bat_commands.append(python_batch_final_output)
    bat_commands.append('pause')

    with open(output_file, 'w', encoding='utf8') as textfile_output_final:
        textfile_output_final.write('\n'.join(bat_commands))

#//=================================================================================================================
#// PROJECT LIST GENERATE ============================================
def main():
    rootdir = PROJECT_ROOT_FOLDERPATH
    project_file_list = glob.glob(os.path.join(rootdir, '**', '*.project'), recursive=True)

    project_folder_dict = {}
    for current_project in tqdm(project_file_list, desc="Processing projects"):
        current_project_folder = Path(current_project).parent
        current_project_modified = os.path.getmtime(current_project) 
        project_folder_dict[current_project_folder] = current_project_modified

        
        # Read the JSON configuration from the project file
        project_config = read_project_config(current_project)
        # Override parameters with values from the project configuration
        prompt_strength = project_config.get('prompt_strength', PROMPT_STRENGTH)
        prompt_random_total = project_config.get('prompt_random_total', PROMPT_RANDOM_TOTAL)
        # Add more overrides as needed based on your project configuration

    project_folder_list_sorted = sorted(project_folder_dict, key=project_folder_dict.get, reverse=True)

    for project_folder_current in tqdm(project_folder_list_sorted, desc="Running batch operations"):
        print(str(extract_prompts_from_files))
        extract_prompts_from_files(project_folder_current) # PARSE IMAGES IN SELECTED GET THEIR PROMPT AND NEGATIVE PROMPT
        #extract_prompts_from_txt(project_folder_current) # PARSE TXT IN SELECTED GET THEIR PROMPT AND NEGATIVE PROMPT
        random_combine_from_txt(project_folder_current, PROMPT_RANDOM_TOTAL) # FROM THE COMBINED FOUND PROMPTS RANDOMLY MIX THEM
        create_script_per_init(project_folder_current, PROMPT_STRENGTH) # GENERATE A LINE OF SHELL FOR EACH INIT IMAGE WITH SETTINGS TO BE COLLECTED BY THE PROJECT MANAGER
        generate_bat_img2img(project_folder_current, API_PATH, API_PY) # GENERATE A LOCAL BAT WITH SETTINGS WITHIN EACH PROJECT FOLDER
    
    extract_python_from_txt(PROJECT_ROOT_FOLDERPATH) # FINALLY GET ALL PYTHON TXT FILES FROM SUBFOLDER AND APPEND TO SINGULAR MAIN BAT FILE

if __name__ == "__main__":
    main()