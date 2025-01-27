import os
import re
import sys
import random
from typing import Dict

# Insert your ComfyUI path so Comfy can find its necessary modules, if needed:
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), 'comfy'))

class LoraRandomizerNode:
    """
    A ComfyUI node that parses LoRA strings, randomizes their strengths, highlights a single LoRA, or passes through unmodified.

    Modes:
        - Randomize: Randomize strengths while adhering to max total and individual strengths.
        - Highlight: Highlight a single LoRA, setting others to a low strength.
        - Pass-through: Leave the input unchanged if both modes are off.
    """

    def __init__(self):
        """
        Initialize node with default strength limits.
        """
        self.total_strength = 1.5
        self.max_individual_strength = 0.9

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True}),
                "randomize": ("BOOLEAN", {"default": False}),
                "highlight": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": 0}),
            },
            "optional": {},
            "hidden": {},
        }

    # ComfyUI expects certain class variables that define how the node behaves
    RETURN_TYPES = ("STRING",)  # We return a single modified string
    RETURN_NAMES = ("modified_text",) # Name for the output
    FUNCTION = "process"       # The method in this class that is called
    CATEGORY = "OBORO"          # Category name for where this node appears
    OUTPUT_NODE = False         # Whether this node can terminate a workflow

    def parse_lora_syntax(self, text: str) -> Dict[str, float]:
        """
        Parse LoRA strings into a dictionary of {lora_name: strength}.
        """
        lora_pattern = r"<lora:([^:<>]+):([0-9]*\.?[0-9]+)>"
        matches = re.findall(lora_pattern, text)
        parsed_loras = {name.strip(): float(strength) for name, strength in matches}
        print("Parsed LoRA syntax:", parsed_loras)
        return parsed_loras

    def format_lora_syntax(self, loras: Dict[str, float]) -> str:
        """
        Format a dictionary of {lora_name: strength} back into LoRA syntax.
        Ensure proper formatting even if the dictionary is empty.
        """
        if not loras:
            print("No LoRAs to format. Returning empty string.")
            return ""

        formatted = " ".join(f"<lora:{name}:{strength:.2f}>" for name, strength in loras.items())
        print("Formatted LoRA syntax:", formatted)
        return formatted

    def randomize_strengths(self, loras: Dict[str, float], seed: int) -> Dict[str, float]:
        """
        Randomize the strengths of LoRAs while keeping total under total_strength.
        Connect the random seed to the main seed for reproducibility.
        """
        if seed != 0:
            random.seed(seed)

        total_available = self.total_strength
        randomized_loras = {}
        for name in loras.keys():
            strength = min(random.uniform(0, self.max_individual_strength), total_available)
            randomized_loras[name] = strength
            total_available -= strength
            if total_available <= 0:
                break

        # Fill remaining LoRAs with 0 strength
        for name in loras.keys():
            if name not in randomized_loras:
                randomized_loras[name] = 0.0

        print("Randomized LoRA strengths:", randomized_loras)
        return randomized_loras

    def highlight_random_lora(self, loras: Dict[str, float], seed: int) -> Dict[str, float]:
        """
        Highlight a single LoRA by setting it to a high strength and others to a low strength.
        Connect the random seed to the main seed for reproducibility.
        """
        if seed != 0:
            random.seed(seed)

        if not loras:
            print("No LoRAs to highlight. Returning empty dictionary.")
            return {}

        chosen_lora = random.choice(list(loras.keys()))
        highlighted_loras = {name: 0.01 for name in loras.keys()}
        highlighted_loras[chosen_lora] = 0.9
        print(f"Highlighted LoRA: {chosen_lora}", highlighted_loras)
        return highlighted_loras

    def process(self, text: str, randomize: bool = False, highlight: bool = False, seed: int = 0, *args, **kwargs) -> tuple:
        """
        Process the input text based on the selected modes.
        """
        print("Input Text:", text)

        if not randomize and not highlight:
            print("Pass-through mode: No changes made.")
            return (text,)  # Pass through if both modes are off

        loras = self.parse_lora_syntax(text)

        if randomize:
            loras = self.randomize_strengths(loras, seed)

        if highlight:
            loras = self.highlight_random_lora(loras, seed)

        final_loras = self.format_lora_syntax(loras)

        if not isinstance(final_loras, str):
            print("Error: Final output is not a string.")
            final_loras = ""

        print(f"FINAL LoRA Output: {final_loras}")
        return (final_loras,)  # Return as a tuple

# ComfyUI needs to know which classes to load when scanning your .py file
NODE_CLASS_MAPPINGS = {
    "LoraRandomizerNode": LoraRandomizerNode,
}

# (Optional) Provide a human-readable display name for your node
NODE_DISPLAY_NAME_MAPPINGS = {
    "LoraRandomizerNode": "LoRA Randomizer Node",
}
