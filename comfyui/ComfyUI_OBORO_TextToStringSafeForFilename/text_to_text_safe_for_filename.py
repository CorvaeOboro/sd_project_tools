import re
import string
import unicodedata

class OBOROTextToTextSafeForFilename:
    """
    This node converts a text input into a filename-safe variant by:
      - Replacing or removing invalid characters
      - Handling Windows-reserved filenames
      - Optionally normalizing Unicode
      - Collapsing underscores
      - Truncating length if needed
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "string_in": ("STRING",),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "process_string"
    CATEGORY = "OBORO"
    DESCRIPTION = "Converts a text input into a filename-safe variant."

    # ---- CONFIGURATIONS ----
    # Characters to replace with underscore
    direct_replacements = {
        " ": "_",
        "\n": "_",
        "\r": "_",
        "(": "_",
        ")": "_",
        ":": "_",
        "<": "_",
        ">": "_",  
        "\\": "_",
        "/": "_",
        "*": "_",
        "?": "_",
        "\"": "_",
        "|": "_",
        "-": "_",
        # ... add more if needed
    }

    # Characters to remove outright
    remove_characters = [
        ",",
        # If you want to remove additional punctuation, do so here
    ]

    # Reserved Windows filenames
    reserved_names = {
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5",
        "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5",
        "lpt6", "lpt7", "lpt8", "lpt9",
    }

    # Maximum length for safety
    MAX_LENGTH = 150  # you can set to 255 or other desired limit

    def process_string(self, string_in):

        # (Optional) Normalize Unicode to decompose accents, etc.
        string_in = unicodedata.normalize("NFKD", string_in)
        
        # Step A: Direct replacements
        for original_char, replacement_char in self.direct_replacements.items():
            string_in = string_in.replace(original_char, replacement_char)

        # Step B: Remove specifically designated characters
        for char_to_remove in self.remove_characters:
            string_in = string_in.replace(char_to_remove, "")

        # Step C: Remove any leftover control characters or punctuation that we do not want. We'll keep underscore though.
        # 1) Remove control chars (ASCII 0-31 and 127)
        control_chars = ''.join(chr(c) for c in range(32)) + chr(127)
        for cc in control_chars:
            string_in = string_in.replace(cc, "")

        # 2) Remove all punctuation except underscore
        punctuation_without_underscore = "".join(
            ch for ch in string.punctuation if ch != "_"
        )
        string_in = re.sub(f"[{re.escape(punctuation_without_underscore)}]+", "", string_in)

        # Step D: Collapse multiple underscores
        string_in = re.sub(r"_{2,}", "_", string_in)

        # Step E: Remove trailing/leading periods/spaces/underscores if needed
        # Windows doesn't handle trailing spaces or periods well:
        string_in = string_in.strip(" ._")

        # Step F: If the entire cleaned string is one of the reserved Windows filenames, suffix  to avoid conflicts.
        if string_in.lower() in self.reserved_names:
            string_in = string_in + "_0"

        # Step G: Enforce maximum length
        if len(string_in) > self.MAX_LENGTH:
            string_in = string_in[:self.MAX_LENGTH]

        # If after everything it's empty, give it a default name
        if not string_in:
            string_in = "error_empty_string"

        return (string_in,)


# Register the node
NODE_CLASS_MAPPINGS = {
    "OBOROTextToTextSafeForFilename": OBOROTextToTextSafeForFilename,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OBOROTextToTextSafeForFilename": "Text To Filename Safe Text",
}
