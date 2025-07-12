import os

class OBOROLoadTextFileGraceful:
    """
    A ComfyUI node that loads text from a file. 
    Non-comment lines (lines that do not start with '#') are:
      - joined into a single output string, and 
      - also stored in a dictionary under the user-specified key.

    If the file path is invalid or the file cannot be read, an empty 
    string and empty list are returned gracefully (no crash).
    """

    def __init__(self):
        """
        Node initialization can hold default values or references 
        to external modules if necessary.
        """
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "file_path": ("STRING", {"default": "", "multiline": False}),
                "dictionary_name": ("STRING", {"default": "[filename]", "multiline": False}),
            },
            # If you want to handle optional or hidden inputs, add them here:
            "optional": {},
            "hidden": {},
        }

    # ComfyUI expects certain class variables that define how the node behaves
    RETURN_TYPES = ("STRING", "DICT")  # We return a text string plus a dictionary
    FUNCTION = "load_file"            # The method in this class that is called
    CATEGORY = "OBORO"                 # Category name for where this node appears
    OUTPUT_NODE = False               # Whether this node can terminate a workflow

    def load_file(self, 
                  file_path="", 
                  dictionary_name="[filename]",
                  *args, 
                  **kwargs):
        """
        Main logic to load a text file:

        1. If dictionary_name is "[filename]", we use the base filename (no extension).
        2. If file_path does not exist, return an empty string and empty dictionary.
        3. Skip any line that starts with '#'.
        4. Return a single string (joined with newlines) and a dict {dictionary_key: [list_of_lines]}.
        """

        # Derive the dictionary key if user left the default "[filename]"
        if dictionary_name == "[filename]":
            dictionary_name = os.path.splitext(os.path.basename(file_path))[0]

        # Check for file existence
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            print(f"[LoadTextFileGraceful] Warning: File not found: {file_path}")
            return "", {dictionary_name: []}

        # Attempt to read file lines, skipping comments
        lines = []
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                for line in f:
                    if not line.strip().startswith('#'):
                        lines.append(line.strip())
        except Exception as e:
            print(f"[LoadTextFileGraceful] Error reading file {file_path}: {e}")
            return "", {dictionary_name: []}

        # Join non-comment lines into a single string
        text_output = "\n".join(lines)

        # Return the text plus a dictionary keyed by dictionary_name
        return text_output, {dictionary_name: lines}


# ComfyUI needs to know which classes to load when scanning your .py file
NODE_CLASS_MAPPINGS = {
    "OBOROLoadTextFileGraceful": OBOROLoadTextFileGraceful,
}

# Provide a human-readable display name for your node
NODE_DISPLAY_NAME_MAPPINGS = {
    "OBOROLoadTextFileGraceful": "Load Text File Graceful",
}
