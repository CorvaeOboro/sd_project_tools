"""
OBORO Checkpoint Loader By String Dirty - a ComfyUI Custom Node

This node loads a Stable Diffusion checkpoint by matching a string input to available checkpoint files.
It is robust to different input formats, supporting both full/relative paths and just filenames.

Features:
- Accepts a checkpoint name or relative path as input 
- Searches for a compatible checkpoint file in the ComfyUI checkpoints directory.
- Matching tries exact filename, base name (without extension), and partial filename matches.
- Outputs the loaded model, CLIP, VAE, and the resolved checkpoint filename.

Inputs:
    ckpt_name: The name or path of the checkpoint to load (string).
    DEBUG_MODE: Enable verbose debug output 

Outputs:
    model: The loaded model object.
    clip: The loaded CLIP object.
    vae: The loaded VAE object.
    ckpt_filename: The resolved checkpoint filename (string).

"""
import os
import folder_paths
import nodes
import os


class OBOROCheckpointLoaderByStringDirty:
    @staticmethod
    def debug_message(msg, DEBUG_MODE):
        if DEBUG_MODE:
            print(f"[OBOROCheckpointLoaderByStringDirty][DEBUG] {msg}")

    @staticmethod
    def _get_all_checkpoints_recursive(base_dir, exts=(".ckpt", ".safetensors", ".sft")):
        """
        Recursively collect all checkpoint files under base_dir, returning relative paths.
        """
        files = []
        for root, dirs, filenames in os.walk(base_dir):
            for f in filenames:
                if any(f.endswith(ext) for ext in exts):
                    rel_path = os.path.relpath(os.path.join(root, f), base_dir)
                    # Normalize to use forward slashes for matching
                    files.append(rel_path.replace("\\", "/"))
        return files

    @classmethod
    def find_matching_filename(cls, input_string, filenames, DEBUG_MODE=False):
        cls.debug_message(f"Searching for checkpoint: input_string='{input_string}'", DEBUG_MODE)
        cls.debug_message(f"Available filenames: {filenames}", DEBUG_MODE)

        # Normalize input: support both full/relative paths and just filenames
        input_filename = os.path.basename(input_string)
        input_base, input_ext = os.path.splitext(input_filename)
        input_string_norm = input_string.replace("\\", "/")
        cls.debug_message(f"Normalized input filename: {input_filename}", DEBUG_MODE)
        cls.debug_message(f"Normalized input string for path: {input_string_norm}", DEBUG_MODE)

        # Try exact relative path match
        for filename in filenames:
            if input_string_norm == filename:
                cls.debug_message(f"Exact relative path match found: {filename}", DEBUG_MODE)
                return filename

        # Try exact filename match
        for filename in filenames:
            if input_filename == os.path.basename(filename):
                cls.debug_message(f"Exact filename match found: {filename}", DEBUG_MODE)
                return filename

        # Try matching base name (without extension)
        for filename in filenames:
            filename_base, filename_ext = os.path.splitext(os.path.basename(filename))
            if input_base == filename_base:
                cls.debug_message(f"Base name match found: {filename}", DEBUG_MODE)
                return filename

        # Try partial filename match
        for filename in filenames:
            if input_filename in filename:
                cls.debug_message(f"Partial filename match found: {filename}", DEBUG_MODE)
                return filename

        cls.debug_message(f"No match found for '{input_string}'", DEBUG_MODE)
        raise FileNotFoundError(f"File '{input_string}' not found in checkpoint directory.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"ckpt_name": ("STRING", {"default": ""})},
            "optional": {"DEBUG_MODE": ("BOOLEAN", {"default": False})}
        }

    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "ckpt_filename")
    FUNCTION = "load_checkpoint"
    CATEGORY = "OBORO"

    def load_checkpoint(self, ckpt_name, output_vae=True, output_clip=True, DEBUG_MODE=False):
        self.debug_message(f"load_checkpoint called with ckpt_name='{ckpt_name}', output_vae={output_vae}, output_clip={output_clip}, DEBUG_MODE={DEBUG_MODE}", DEBUG_MODE)
        # Recursively collect all checkpoint files (relative paths)
        checkpoints_dir = folder_paths.get_folder_paths("checkpoints")[0]
        filenames = self._get_all_checkpoints_recursive(checkpoints_dir)
        self.debug_message(f"Found {len(filenames)} checkpoint files in search path (recursive).", DEBUG_MODE)
        ckpt_name_full = self.find_matching_filename(ckpt_name, filenames, DEBUG_MODE)
        self.debug_message(f"Resolved checkpoint filename: {ckpt_name_full}", DEBUG_MODE)
        loader = nodes.CheckpointLoaderSimple()
        # Pass the full path to the loader
        full_ckpt_path = os.path.join(checkpoints_dir, ckpt_name_full)
        model, clip, vae = loader.load_checkpoint(full_ckpt_path)
        self.debug_message(f"Checkpoint loaded: model={type(model)}, clip={type(clip)}, vae={type(vae)}", DEBUG_MODE)
        return model, clip, vae, ckpt_name_full

NODE_CLASS_MAPPINGS = {
    'OBOROCheckpointLoaderByStringDirty': OBOROCheckpointLoaderByStringDirty,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'OBOROCheckpointLoaderByStringDirty': 'Checkpoint Loader By String Dirty',
}
