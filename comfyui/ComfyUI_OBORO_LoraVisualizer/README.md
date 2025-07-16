# ComfyUI LORA Strength Visualizer

A ComfyUI custom node that creates a visual representation of LORA strengths in your prompt. The node generates an image where each LORA is displayed with its name and strength value, with the text size and brightness scaled according to the LORA's strength.

## Features

- Extracts LORA names and strengths from prompt text
- Sorts LORAs by strength (strongest first)
- Visualizes each LORA with:
  - Text size scaled by strength (larger = stronger)
  - Text brightness scaled by strength (brighter = stronger)
  - Strength value shown next to LORA name
- Configurable output image dimensions
- Black background for optimal contrast

## Installation

1. Create a `ComfyUI_OBORO_LoraVisualizer` folder in your ComfyUI custom nodes directory
2. Copy all files into the folder
3. Restart ComfyUI

## Usage

1. Add the "LORA Strength Visualizer" node to your workflow
2. Connect a text prompt containing LORA tags (in the format `<lora:name:strength>`)
3. Optionally adjust the output image dimensions
4. The node will output an image showing all LORAs sorted by strength

## Example

Input prompt:
```
a photo of a cat <lora:cat_v1:0.8> with realistic fur <lora:furDetails:0.5> in anime style <lora:animeStyle:0.3>
```

This will create an image with:
- "cat_v1 (0.80)" - largest and brightest
- "furDetails (0.50)" - medium size and brightness
- "animeStyle (0.30)" - smallest and most faded

## Requirements

- PIL (Python Imaging Library)
- numpy
- torch (PyTorch)
- A TrueType font file (automatically searches common system font locations)
