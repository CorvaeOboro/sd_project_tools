"""
OBORO Image Load Random Variant - a ComfyUI custom_node

Load image from a folderpath , with options to load one of its variants
variants may be in a subfolder or have a suffix , possibly many variants
if no variants found just load the input "fallback" image

Example
D:\GAMES\EVERQUEST\MODDING\EXPORT\oasis_obj\drymud2.png
D:\GAMES\EVERQUEST\MODDING\EXPORT\oasis_obj\drymud2\drymud2_CAM_ORTHO_PROJ_1.png
D:\GAMES\EVERQUEST\MODDING\EXPORT\oasis_obj\drymud2\drymud2_CAM_ORTHO_PROJ_2.png

the base image is drymud2.png
the variants are in a subfolder based on the image name , with suffix input
there may be an unknown amount of variants with suffix number increasing from 1
there should be a boolean whether look for variants or not
if variants are not found , just load the fallback image
TODO: 
variants are typically a render from a camera of a texture ( on the 3d mesh ) and therefore we would want to disable tiling 
"""

import os
import random
from pathlib import Path
import numpy as np
import torch
from PIL import Image, ImageOps
import folder_paths


class OBOROLoadImageRandomVariant:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "folder": ("STRING", {"default": r"C:/a/images"}),
            "base_filename": ("STRING", {"default": "image.png"}),
            "variant_suffixes": ("STRING", {"default": "_CAM_ORTHO_PROJ_"}),
            "search_variants": ("BOOLEAN", {"default": True}),
            "fallback": ("STRING", {"default": r"C:/a/fallback.png"}),
            "debug_mode": ("BOOLEAN", {"default": False})
        }}

    def debug_print(self, debug_mode, *args, **kwargs):
        """Print only if debug_mode is True."""
        if debug_mode:
            print(*args, **kwargs)


    CATEGORY = "OBORO"
    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "STRING")
    RETURN_NAMES = ("image", "MASK", "file name", "folder path")
    FUNCTION = "load_image"

    def load_image(self, folder, base_filename, variant_suffixes, search_variants, fallback, debug_mode):
        self.debug_print(debug_mode, "[load_image] Called with:")
        self.debug_print(debug_mode, "  folder:", folder)
        self.debug_print(debug_mode, "  base_filename:", base_filename)
        self.debug_print(debug_mode, "  variant_suffixes:", variant_suffixes)
        self.debug_print(debug_mode, "  search_variants:", search_variants)
        self.debug_print(debug_mode, "  fallback:", fallback)

        folder = Path(folder)
        base = folder / base_filename
        stem, ext = os.path.splitext(base_filename)
        self.debug_print(debug_mode, "  base path:", base)
        self.debug_print(debug_mode, "  stem:", stem, "ext:", ext)

        suffixes = [s.strip() for s in variant_suffixes.split(",") if s.strip()]
        self.debug_print(debug_mode, "  suffixes:", suffixes)
        variants = []
        if search_variants:
            variant_folder = folder / stem
            self.debug_print(debug_mode, "  Looking for variants in folder:", variant_folder)
            if variant_folder.exists() and variant_folder.is_dir():
                for suffix in suffixes:
                    i = 1
                    while True:
                        candidate = variant_folder / f"{stem}{suffix}{i}{ext}"
                        if candidate.exists():
                            self.debug_print(debug_mode, f"    Found variant: {candidate}")
                            variants.append(candidate)
                            i += 1
                        else:
                            break
            else:
                self.debug_print(debug_mode, "    Variant folder does not exist or is not a directory.")
        self.debug_print(debug_mode, "  Variants found:", [str(v) for v in variants])
        # Pick a variant or fallback
        if variants:
            chosen = random.choice(variants)
            self.debug_print(debug_mode, f"  Chose random variant: {chosen}")
        elif base.exists():
            chosen = base
            self.debug_print(debug_mode, f"  No variants found. Using base image: {chosen}")
        else:
            chosen = Path(fallback)
            self.debug_print(debug_mode, f"  Base image not found. Using fallback: {chosen}")
        i = Image.open(chosen)
        self.debug_print(debug_mode, f"  Opened image: {chosen}")
        i = ImageOps.exif_transpose(i)
        image = i.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        if 'A' in i.getbands():
            self.debug_print(debug_mode, "  Image has alpha channel. Generating mask from alpha.")
            mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        else:
            self.debug_print(debug_mode, "  No alpha channel. Using default mask.")
            mask = torch.zeros((64,64), dtype=torch.float32, device="cpu")
        dirname, basename = os.path.split(str(chosen))
        file_name = get_file_name_without_extension(str(chosen))
        folder_path = dirname
        self.debug_print(debug_mode, f"  Output file_name: {file_name}, folder_path: {folder_path}")
        return (image, mask, file_name, folder_path)


    @staticmethod
    def get_file_name_without_extension(file_path):
        file_name_with_extension = os.path.basename(file_path)
        file_name, _ = os.path.splitext(file_name_with_extension)
        return file_name

    @staticmethod
    def _resolve_path(image) -> Path:
        image_path = Path(folder_paths.get_annotated_filepath(image))
        return image_path

    @classmethod
    def IS_CHANGED(cls, image):
        import hashlib
        image_path = cls._resolve_path(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        # If image is an output of another node, it will be None during validation
        if image is None:
            return True

        image_path = cls._resolve_path(image)
        if not image_path.exists():
            return f"Invalid image path: {image_path}"

        return True

NODE_CLASS_MAPPINGS = {
    'OBOROLoadImageRandomVariant': OBOROLoadImageRandomVariant,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'OBOROLoadImageRandomVariant': 'Load Image Random Variant',
}
