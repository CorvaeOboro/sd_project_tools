import os
import re
import sys
from typing import Dict

# Insert your ComfyUI path so Comfy can find its necessary modules, if needed:
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'comfy'))

class OBOROLoraStringMultiplierNode:
    """
    A ComfyUI node that applies a multiplier to LoRA strengths and optionally enforces hard caps on:
        - Individual LoRA strengths.
        - The total combined strength of all LoRAs.
    
    Workflow:
        1. Parse the input text to extract LoRAs in the format <lora:name:strength>.
        2. Multiply each LoRA's strength by the provided multiplier.
        3. If individual cap enforcement is enabled, cap each strength to the specified maximum.
        4. If total cap enforcement is enabled, and the sum of strengths exceeds the maximum,
           scale all strengths proportionally so that the total matches the cap.
        5. Reassemble the modified LoRA tags into a single string for output.
    """

    def __init__(self):
        pass  # No preset defaults; all values are provided via node inputs.

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True}),
                "multiplier": ("FLOAT", {"default": 1.0}),
                "individual_cap_enabled": ("BOOLEAN", {"default": False}),
                "individual_cap": ("FLOAT", {"default": 1.0}),
                "total_cap_enabled": ("BOOLEAN", {"default": False}),
                "total_cap": ("FLOAT", {"default": 1.0}),
            },
            "optional": {},
            "hidden": {},
        }

    RETURN_TYPES = ("STRING",)  # The node returns a single modified string.
    RETURN_NAMES = ("modified_text",)
    FUNCTION = "process"
    CATEGORY = "OBORO"
    OUTPUT_NODE = False

    def parse_lora_syntax(self, text: str) -> Dict[str, float]:
        """
        Parse LoRA strings from the input text.
        Expected LoRA syntax format: <lora:name:strength>
        Returns a dictionary mapping each LoRA name to its strength.
        """
        lora_pattern = r"<lora:([^:<>]+):([0-9]*\.?[0-9]+)>"
        matches = re.findall(lora_pattern, text)
        parsed_loras = {name.strip(): float(strength) for name, strength in matches}
        print("Parsed LoRA syntax:", parsed_loras)
        return parsed_loras

    def format_lora_syntax(self, loras: Dict[str, float]) -> str:
        """
        Convert the dictionary of LoRAs back into a formatted string.
        """
        if not loras:
            print("No LoRAs to format. Returning empty string.")
            return ""
        formatted = " ".join(f"<lora:{name}:{strength:.2f}>" for name, strength in loras.items())
        print("Formatted LoRA syntax:", formatted)
        return formatted

    def process(
        self,
        text: str,
        multiplier: float,
        individual_cap_enabled: bool,
        individual_cap: float,
        total_cap_enabled: bool,
        total_cap: float,
        *args,
        **kwargs,
    ) -> tuple:
        """
        Process the input text by applying the multiplier and enforcing the specified caps.
        """
        print("Input Text:", text)
        loras = self.parse_lora_syntax(text)

        # Apply the multiplier to each LoRA strength.
        multiplied_loras = {}
        for name, strength in loras.items():
            new_strength = strength * multiplier
            multiplied_loras[name] = new_strength
        print("After applying multiplier:", multiplied_loras)

        # Enforce individual strength cap if enabled.
        if individual_cap_enabled:
            for name in multiplied_loras:
                original = multiplied_loras[name]
                multiplied_loras[name] = min(original, individual_cap)
            print("After enforcing individual cap:", multiplied_loras)

        # Enforce total strength cap if enabled.
        if total_cap_enabled:
            total_strength = sum(multiplied_loras.values())
            if total_strength > total_cap and total_strength > 0:
                scale_factor = total_cap / total_strength
                for name in multiplied_loras:
                    multiplied_loras[name] *= scale_factor
                print("After enforcing total cap, scale factor applied:", scale_factor)
                print("LoRAs after total cap enforcement:", multiplied_loras)
            else:
                print("Total strength within cap, no scaling needed:", total_strength)

        final_text = self.format_lora_syntax(multiplied_loras)
        print("Final output text:", final_text)
        return (final_text,)

# ComfyUI needs to know which classes to load when scanning your .py file.
NODE_CLASS_MAPPINGS = {
    "OBOROLoraStringMultiplierNode": OBOROLoraStringMultiplierNode,
}

# (Optional) Provide a human-readable display name for your node.
NODE_DISPLAY_NAME_MAPPINGS = {
    "OBOROLoraStringMultiplierNode": "LoRA Strength Multiplier on Text ",
}
