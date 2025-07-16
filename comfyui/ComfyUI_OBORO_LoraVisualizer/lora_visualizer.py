import os
import re
from typing import List, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch

class OBOROLoraVisualizerWordPlotNode:
    """
    A ComfyUI node that analyzes a prompt text and creates a visual representation
    of LORA strengths, displaying them as text with varying sizes and brightness
    based on their strength values.
    """
    
    def __init__(self):
        self.output_width = 512
        self.output_height = 512
        self.bg_color = (0, 0, 0)
        self.text_color = (255, 255, 255)
        
        # Try to find a suitable font
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ]
        self.font_path = next((p for p in font_paths if os.path.exists(p)), None)
        if not self.font_path:
            print("Warning: No default font found. Text rendering may fail.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True}),
                "width": ("INT", {"default": 512, "min": 64, "max": 2048}),
                "height": ("INT", {"default": 512, "min": 64, "max": 2048}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "process"
    CATEGORY = "OBORO"
    OUTPUT_NODE = True

    def extract_loras(self, text: str) -> List[Tuple[str, float]]:
        """Extract LORA names and their strengths from the prompt."""
        lora_pattern = re.compile(r'<lora:([^:]+):([^>]+)>')
        matches = lora_pattern.findall(text)
        
        # Convert strengths to floats and sort by strength descending
        loras = [(name, float(strength)) for name, strength in matches]
        return sorted(loras, key=lambda x: x[1], reverse=True)

    def create_visualization(self, loras: List[Tuple[str, float]], width: int, height: int) -> Image.Image:
        """Create a visual representation of LORA strengths."""
        img = Image.new('RGB', (width, height), self.bg_color)
        draw = ImageDraw.Draw(img)

        if not loras:
            # Draw "No LORAs found" message
            font = ImageFont.truetype(self.font_path, size=36)
            text = "No LORAs found"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            draw.text((x, y), text, fill=self.text_color, font=font)
            return img

        # Find max and min strengths for normalization
        max_strength = max(strength for _, strength in loras)
        min_strength = min(strength for _, strength in loras)
        strength_range = max_strength - min_strength

        # Calculate layout
        y_pos = height * 0.1  # Start from 10% from top
        available_height = height * 0.8  # Use 80% of height
        spacing = available_height / len(loras)

        for i, (name, strength) in enumerate(loras):
            # Normalize strength for font size (40-120px) and opacity
            if strength_range > 0:
                norm_strength = (strength - min_strength) / strength_range
            else:
                norm_strength = 1.0
                
            font_size = int(40 + norm_strength * 80)
            opacity = int(128 + norm_strength * 127)  # 128-255 range
            
            # Create font and calculate text position
            font = ImageFont.truetype(self.font_path, size=font_size)
            text = f"{name} ({strength:.2f})"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (width - text_width) // 2
            y = int(y_pos + i * spacing)
            
            # Draw text with calculated opacity
            text_color = (255, 255, 255, opacity)
            draw.text((x, y), text, fill=text_color, font=font)

        return img

    def process(self, text: str, width: int, height: int) -> tuple:
        """Process the input text and create a visualization of LORA strengths."""
        # Extract and sort LORAs
        loras = self.extract_loras(text)
        
        # Create visualization
        img = self.create_visualization(loras, width, height)
        
        # Convert to tensor format expected by ComfyUI
        img_tensor = torch.from_numpy(np.array(img).astype(np.float32) / 255.0)
        img_tensor = img_tensor.unsqueeze(0)
        
        return (img_tensor,)

# ComfyUI node registration
NODE_CLASS_MAPPINGS = {
    "OBOROLoraVisualizerWordPlotNode": OBOROLoraVisualizerWordPlotNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OBOROLoraVisualizerWordPlotNode": "LORA Strength Visualizer WordPlot",
}
