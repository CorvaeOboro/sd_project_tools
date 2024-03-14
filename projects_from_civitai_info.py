# PROJECTS FROM CIVITAI INFO
# recursive search for .info files , for each create a project folder matching the existing organized subfolder structure 
# creates .project and downloads all of the image examples into the projects 'selected' folder for replicatoion
import os
import json
import requests
import time
from pathlib import Path
from tqdm import tqdm

INFO_DIRECTORY = 'D:/CODE/STABLEDIFFUSION_AUTO/models/Lora'
PROJECT_DIRECTORY = 'D:/CODE/STABLEDIFFUSION_AUTO/PROJECTS/LORA'
DOWNLOAD_DELAY = 5  # seconds

#//============================================================================================
def download_image(url, save_path):
    if not save_path.exists():
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(save_path, 'wb') as file:
                file.write(response.content)
            time.sleep(DOWNLOAD_DELAY)  # Wait before the next download
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {url}: {e}")

def process_info_file(info_file_path):
    relative_path = info_file_path.relative_to(INFO_DIRECTORY).parent
    folder_name = info_file_path.stem  # Removes the '.civitai.info' extension
    new_folder_path = Path(PROJECT_DIRECTORY) / relative_path / folder_name
    new_folder_path.mkdir(parents=True, exist_ok=True)

    with open(info_file_path, 'r') as file:
        data = json.load(file)

    # Copy the .info file to the new folder
    new_info_file_path = new_folder_path / f'{folder_name}.civitai.info'
    with open(new_info_file_path, 'w') as new_file:
        json.dump(data, new_file, indent=4)

    # Create a "project.project" file in the new folder
    project_file_path = new_folder_path / 'project.project'
    project_file_path.touch()

    # Download images to a "selected" subfolder
    selected_folder_path = new_folder_path / 'selected'
    selected_folder_path.mkdir(exist_ok=True)

    for image in tqdm(data.get('images', []), desc=f'Downloading images for {folder_name}'):
        url = image.get('url')
        if url:
            image_name = Path(url).name
            save_path = selected_folder_path / image_name
            if not save_path.exists():
                download_image(url, save_path)

#//===========================================================================================
def main():
    info_files = [Path(root) / file for root, dirs, files in os.walk(INFO_DIRECTORY) for file in files if file.endswith('.civitai.info')]
    for info_file_path in tqdm(info_files, desc='Processing .civitai.info files'):
        process_info_file(info_file_path)

if __name__ == '__main__':
    main()
