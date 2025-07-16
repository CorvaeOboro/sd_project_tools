"""
Dynamic project-level __init__.py for ComfyUI custom nodes
--------------------------------------------------------
This file automatically scans all subfolders with an __init__.py and merges their
NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS.
No need to edit this file by hand or regenerate it when adding/removing nodes.
"""
import os
import importlib

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

base = os.path.dirname(__file__)

for name in os.listdir(base):
    subdir = os.path.join(base, name)
    if (
        os.path.isdir(subdir)
        and not name.startswith("__")
        and os.path.isfile(os.path.join(subdir, "__init__.py"))
    ):
        try:
            mod = importlib.import_module(f".{name}", package=__package__)
            NODE_CLASS_MAPPINGS.update(getattr(mod, "NODE_CLASS_MAPPINGS", {}))
            NODE_DISPLAY_NAME_MAPPINGS.update(getattr(mod, "NODE_DISPLAY_NAME_MAPPINGS", {}))
        except Exception as e:
            print(f"Could not import node module {name}: {e}")