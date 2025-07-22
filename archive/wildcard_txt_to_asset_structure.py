#!/usr/bin/env python3
"""
Wildcard TXT to Asset Structure Tool

Usage:
    python wildcard_txt_to_asset_structure.py --input wildcard.txt --prefix item_potion_

- Each line in the input .txt file should start with a title ending with a comma, followed by the rest of the prompt text.
- The script will create a folder for each line, named as <prefix><filesafe_title>, with a subfolder 'prompt', and save the original line as 'prompt/prompt_sdxl.md'.

Example input line:
    Witch's Bog-Brew , purple bottle
Resulting structure:
    item_potion_witchs_bog_brew/prompt/prompt_sdxl.md
    item_potion_witchs_bog_brew/target/example.png
    item_potion_witchs_bog_brew/item_potion_witchs_bog_brew.png
    item_potion_witchs_bog_brew/item_potion_witchs_bog_brew.psd

"""
import os
import argparse
import re
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image

# Global defaults
DEFAULT_INPUT = ''
DEFAULT_PREFIX = 'item_potion_'
DEFAULT_OUTPUT = ''
# List of directories to search for default prompt templates
DEFAULT_PROMPT_TEMPLATE_DIRS = [str(Path(__file__).parent / 'prompt')]
# Directory to search for default target image templates
DEFAULT_TARGET_TEMPLATE_DIR = str(Path(__file__).parent / 'target')

def filesafe_title(title: str) -> str:
    # Lowercase, replace non-alphanum with underscores, collapse multiple underscores
    title = title.lower()
    # Replace all non-word characters (except underscore) with underscores
    title = re.sub(r"[^a-z0-9]+", "_", title)
    # Remove leading/trailing underscores
    title = title.strip('_')
    # Truncate to max 50 characters
    return title[:50]

def parse_line_and_folder(line: str, prefix: str, output_dir: Path):
    """
    Parse a wildcard line and return (title, folder_name, folder_path).
    """
    if ',' not in line:
        return None
    title, rest = line.split(',', 1)
    title = title.strip()
    folder_name = prefix + filesafe_title(title)
    folder_path = Path(output_dir) / folder_name / 'prompt'
    return title, folder_name, folder_path

def create_prompt_files(line: str, folder_path: Path, prompt_templates):
    """
    Create prompt .md files in the asset's prompt folder.
    """
    folder_path.mkdir(parents=True, exist_ok=True)
    for tmpl in prompt_templates:
        out_md = folder_path / tmpl.name
        if out_md.exists():
            print(f"Exists, skipped: {out_md}")
            continue
        with open(tmpl, 'r', encoding='utf-8') as tfile:
            tmpl_content = tfile.read()
        # Only prepend for non-negative prompts
        if not tmpl.name.endswith('_negative.md'):
            content = line + '\n' + tmpl_content
        else:
            content = tmpl_content
        with open(out_md, 'w', encoding='utf-8') as md_file:
            md_file.write(content)
        print(f"Created: {out_md}")

def copy_target_images(folder_path: Path):
    """
    Copy default target images from the template dir to the asset's target folder.
    """
    target_template_dir = Path(DEFAULT_TARGET_TEMPLATE_DIR)
    asset_target_dir = folder_path.parent / 'target'
    if target_template_dir.exists() and target_template_dir.is_dir():
        asset_target_dir.mkdir(parents=True, exist_ok=True)
        for img in target_template_dir.iterdir():
            if img.is_file():
                dest_img = asset_target_dir / img.name
                if dest_img.exists():
                    print(f"Exists, skipped: {dest_img}")
                    continue
                with open(img, 'rb') as fsrc, open(dest_img, 'wb') as fdst:
                    fdst.write(fsrc.read())
                print(f"Copied: {dest_img}")

def create_asset_images(folder_path: Path):
    """
    Create a 1024x1024 black PNG and PSD named after the asset folder.
    """
    asset_root = folder_path.parent
    base_name = asset_root.name
    png_path = asset_root / f"{base_name}.png"
    psd_path = asset_root / f"{base_name}.psd"
    if not png_path.exists():
        img = Image.new('RGB', (1024, 1024), color='black')
        img.save(png_path)
        print(f"Created: {png_path}")
    else:
        print(f"Exists, skipped: {png_path}")
    if not psd_path.exists():
        # Copy the PNG as a placeholder for the PSD
        with open(png_path, 'rb') as fsrc, open(psd_path, 'wb') as fdst:
            fdst.write(fsrc.read())
        print(f"Created: {psd_path}")
    else:
        print(f"Exists, skipped: {psd_path}")

def process_wildcard_txt(input_path: str, prefix: str, output_dir: str = None):
    """
    Main function to process the wildcard .txt file and generate asset structure.
    Steps:
    1. Find all prompt templates
    2. For each line, parse and create asset folders/files
    3. Create prompt files
    4. Copy target images
    5. Create black PNG/PSD images
    """
    input_path = Path(input_path)
    # Step 1: Find all prompt_*.md templates in the specified template dirs
    prompt_templates = []
    for tdir in DEFAULT_PROMPT_TEMPLATE_DIRS:
        tdir_path = Path(tdir)
        prompt_templates.extend(tdir_path.glob('prompt_*.md'))
    if output_dir is None:
        output_dir = input_path.parent
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Step 2: Parse line and get folder path
            parsed = parse_line_and_folder(line, prefix, output_dir)
            if not parsed:
                print(f"Skipping line (no comma found): {line}")
                continue
            title, folder_name, folder_path = parsed
            # Step 3: Create prompt files
            create_prompt_files(line, folder_path, prompt_templates)
            # Step 4: Copy target images
            copy_target_images(folder_path)
            # Step 5: Create black PNG and PSD
            create_asset_images(folder_path)

def launch_gui():
    def browse_input():
        file_path = filedialog.askopenfilename(title='Select Wildcard .txt File', filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')])
        if file_path:
            input_var.set(file_path)
    def browse_output():
        dir_path = filedialog.askdirectory(title='Select Output Directory')
        if dir_path:
            output_var.set(dir_path)
    def run_process():
        input_path = input_var.get()
        prefix = prefix_var.get()
        output_dir = output_var.get() or None
        if not input_path or not prefix:
            messagebox.showerror('Missing Parameters', 'Input file and prefix are required.')
            return
        try:
            process_wildcard_txt(input_path, prefix, output_dir)
            messagebox.showinfo('Success', 'Processing complete!')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    root = tk.Tk()
    root.title('Wildcard TXT to Asset Structure')
    tk.Label(root, text='Input .txt File:').grid(row=0, column=0, sticky='e')
    input_var = tk.StringVar(value=DEFAULT_INPUT)
    tk.Entry(root, textvariable=input_var, width=50).grid(row=0, column=1)
    tk.Button(root, text='Browse', command=browse_input).grid(row=0, column=2)

    tk.Label(root, text='Prefix:').grid(row=1, column=0, sticky='e')
    prefix_var = tk.StringVar(value=DEFAULT_PREFIX)
    tk.Entry(root, textvariable=prefix_var, width=50).grid(row=1, column=1)

    tk.Label(root, text='Output Directory:').grid(row=2, column=0, sticky='e')
    output_var = tk.StringVar(value=DEFAULT_OUTPUT)
    tk.Entry(root, textvariable=output_var, width=50).grid(row=2, column=1)
    tk.Button(root, text='Browse', command=browse_output).grid(row=2, column=2)

    tk.Button(root, text='Run', command=run_process, width=20).grid(row=3, column=0, columnspan=3, pady=10)
    root.mainloop()

def main():
    import sys
    if len(sys.argv) == 1:
        launch_gui()
        return
    parser = argparse.ArgumentParser(description='Convert wildcard .txt to asset structure.')
    parser.add_argument('--input', '-i', required=True, help='Path to wildcard .txt file')
    parser.add_argument('--prefix', '-p', required=True, help='Prefix for folder names (e.g., item_potion_)')
    parser.add_argument('--output', '-o', default=None, help='Optional output directory (default: input file directory)')
    args = parser.parse_args()
    process_wildcard_txt(args.input, args.prefix, args.output)

if __name__ == '__main__':
    main()
