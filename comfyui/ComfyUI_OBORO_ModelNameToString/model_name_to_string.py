import os

class OBOROModelNameToString:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "get_model_name"
    CATEGORY = "OBORO"

    @staticmethod
    def remove_file_extension(value):
        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val.endswith(".safetensors"):
                value = value[:-12]
            elif lower_val.endswith(".ckpt"):
                value = value[:-5]
            elif lower_val.endswith(".srt"):
                value = value[:-4]
            elif lower_val.endswith(".pt"):
                value = value[:-3]
        return value

    def get_model_name(self, model):
        """
        In ComfyUI, the MODEL type is often passed around as a dictionary, e.g.:
        {
            'model_name': 'your_checkpoint_name.ckpt',
            'model': <some internal model object>,
            'vae':  <some vae object>,
            ...
        }

        This function attempts to extract the 'model_name' key from that dictionary.
        If the input isn't a dictionary, or doesn't have model_name, it falls back 
        to other attribute checks (if you have a custom model object).
        """

        model_name = "Unknown Model"

        # 1) Check if the model is a dictionary (typical for ComfyUI).
        if isinstance(model, dict):
            # ComfyUI typically stores the checkpoint name in the 'model_name' key:
            if "model_name" in model:
                model_name = model["model_name"]
            elif "name" in model:  # Some custom nodes might pass 'name'
                model_name = model["name"]
            elif "filename" in model:  # Or 'filename'
                model_name = os.path.basename(model["filename"])

        # 2) If it's not a dict, see if we have an object with one of these attributes:
        else:
            if hasattr(model, 'ckpt_name'):
                model_name = model.ckpt_name
            elif hasattr(model, 'name'):
                model_name = model.name
            elif hasattr(model, 'filename'):
                model_name = os.path.basename(model.filename)
            elif hasattr(model, 'ckpt_path'):
                model_name = os.path.basename(model.ckpt_path)

        # Remove file extension if we got any sort of path/string
        model_name = self.remove_file_extension(model_name)
        return (model_name,)


# Register the node
NODE_CLASS_MAPPINGS = {
    "OBOROModelNameToString": OBOROModelNameToString,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OBOROModelNameToString": "Model Name To String",
}
