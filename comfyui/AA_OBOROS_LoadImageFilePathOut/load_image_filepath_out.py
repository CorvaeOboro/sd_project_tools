import os
import re
import sys
import json
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import numpy as np
import locale
from datetime import datetime
from pathlib import Path
import os
import torch
from PIL import ImageOps
import comfy
import folder_paths
import base64
from io import BytesIO
import torch
import hashlib
from pathlib import Path
from typing import Iterable
from PIL import Image, ImageOps
import numpy as np

class LoadImageFilePathOut:
    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                    {"image": ("STRING", {"default": r"C:/a/image.png [output]"})},
                }

    CATEGORY = "image"

    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "STRING")
    RETURN_NAMES = ("image","MASK","file name","folder path")
    FUNCTION = "load_image"
    def load_image(self, image):
        image_path = LoadImageFilePathOut._resolve_path(image)

        i = Image.open(image_path)
        i = ImageOps.exif_transpose(i)
        image = i.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        if 'A' in i.getbands():
            mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        else:
            mask = torch.zeros((64,64), dtype=torch.float32, device="cpu")
            
        dirname, basename = os.path.split(image_path)
        file_name =  get_file_name_without_extension(image_path)
        folder_path = dirname
        return (image, mask, file_name, folder_path)

    def _resolve_path(image) -> Path:
        image_path = Path(folder_paths.get_annotated_filepath(image))
        return image_path

    @classmethod
    def IS_CHANGED(s, image):
        image_path = LoadImageFilePathOut._resolve_path(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(s, image):
        # If image is an output of another node, it will be None during validation
        if image is None:
            return True

        image_path = LoadImageFilePathOut._resolve_path(image)
        if not image_path.exists():
            return "Invalid image path: {}".format(image_path)

        return True


def get_file_name_without_extension(file_path):
    file_name_with_extension = os.path.basename(file_path)
    file_name, _ = os.path.splitext(file_name_with_extension)
    return file_name

NODE_CLASS_MAPPINGS = {
    'LoadImageFilePathOut': LoadImageFilePathOut,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'LoadImageFilePathOut': 'Load Image FilePath Out',
}
