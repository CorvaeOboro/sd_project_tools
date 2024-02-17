
# for each image create folder with name
import os
import glob
from pathlib import Path
import pathlib
import shutil

rootdir = os.path.dirname(os.path.abspath(__file__))

directory_input = rootdir
file_list = glob.glob(directory_input + '/' + '*.jpeg') + glob.glob(directory_input + '/' + '*.jpg')+ glob.glob(directory_input + '/' + '*.png')+ glob.glob(directory_input + '/' + '*.bmp')

for current_image in file_list:
    current_image_name = pathlib.PurePath(str(current_image)).stem
    current_image_name_full = pathlib.PurePath(str(current_image)).name
    project_dir = str(directory_input) + "/" + current_image_name 
    print("PROJECT DIRECTORY = " + project_dir)
    os.mkdir(project_dir)
    selected_dir = str(directory_input) + "/" + current_image_name + "/selected"
    print("SELECTED DIRECTORY = " + selected_dir)
    os.mkdir(selected_dir)

    # COPY IMAGES TO PROJECT FOLDERS
    project_image = project_dir + "/" + current_image_name_full
    print("PROJECT IMAGE PATH = " + project_image)
    shutil.copyfile(current_image, project_image)
    selected_image = selected_dir + "/" + current_image_name_full
    print("SELECTED IMAGE PATH = " + selected_image)
    shutil.copyfile(current_image, selected_image)

    project_text_path = project_dir + "/project.project"
    with open(project_text_path, 'w') as textfile_output_final:
        textfile_output_final.write('')
        textfile_output_final.close


