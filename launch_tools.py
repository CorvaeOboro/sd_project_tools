"""
LAUNCH TOOLS
A GUI to display and launch tools from the diffusion project venv.
Arranges and prioritizes common tools.

Diffusion Project Python Tools :
// REVIEW--------------------------
- image_review_and_rank_multi_project.py
- image_review_and_rank.py
- image_review_and_rank_multi.py

// EDITOR--------------------------
- image_editor_layered.py

// PROMPT--------------------------
- gen_project_prompt_entry.py
- gen_image_variant_grid_explore.py
- gen_batch_prompts_in_projects.py

// VOICE--------------------------
- voice_action_organizer.py

// TENSORS (Unified)--------------------------
- tensor_tools_all.py

- image_metadata_badword_scanner.py
- image_text_prompt_tools.py
- projects_from_images.py
- projects_from_civitai_info.py
- lora_variants.py
- lora_previews_to_list.py

// VIDEO--------------------------
- video_clip_marker.py
- video_add_audio.py
- video_audio_batch_processor.py
- video_place_in_image_composite.py
- video_editor_word_rating.py
- video_interlacing_fix.py
- video_to_gif_cropper.py
- VIDEO_image_sequence_to_webp.py
- VIDEO_cursor_removal.py
- video_combine.py
- video_review_and_rank_multi_project.py
- video_webp_pingpong.py
- video_psd_to_timelapse_anim.py

// OLD WEBUI based project--------------------------
- sd_batch_image_gen_auto1111_webui.py

// WIP--------------------------
- wildcard_txt_to_asset_structure.py

TODO:
add project dashboard
add image and json badword scanner

VERSION::20250913
"""

import os
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import traceback
import math

#//========================================================================================================
DEBUG_MODE = True

def debug_print(*args, **kwargs):
    if DEBUG_MODE:
        print(*args, **kwargs)

# --- Tool Configuration ---
TOOL_CONFIG = {
    "Image Review": { 
        "color": "#7a5f7a", 
        "tools": [
            {"file": "image_review_and_rank_multi_project.py", "label": "Review & Rank Multi Project", "icon": "image_review_and_rank_multi_project.png", "color": "#9f809f", "size_priority": 1},
            {"file": "image_review_and_rank.py", "label": "Review & Rank", "icon": "image_review_and_rank.png", "color": "#6b4f6b", "size_priority": 0},
        ]
    },
    "Prompt": { 
        "color": "#4a785f", 
        "tools": [
            {"file": "gen_project_prompt_entry.py", "label": "Gen Project Entry", "icon": "gen_project_prompt_entry.png", "color": "#6aaa8f", "size_priority": 1},
            {"file": "image_text_prompt_tools.py", "label": "Image Text Prompt Tools", "icon": "image_text_prompt_tools.png", "color": "#3f6651", "size_priority": 0},
        ]
    },
    "Image Tools": { 
        "color": "#4a785f", 
        "tools": [
            {"file": "image_editor_layered.py", "label": "Image Editor Layered", "icon": "image_editor_layered.png", "color": "#6aaa8f", "size_priority": 1},
            {"file": "image_icon_generator.py", "label": "Icon Generator", "icon": "image_icon_generator.png", "color": "#5aa88a", "size_priority": 0},
            {"file": "image_inspect_bmp.py", "label": "Inspect BMP", "icon": "image_inspect_bmp.png", "color": "#5aa88a", "size_priority": 0},
            {"file": "image_metadata_badword_scanner.py", "label": "Metadata Badword Scanner", "icon": "image_metadata_badword_scanner.png", "color": "#5aa88a", "size_priority": 0},
            {"file": "image_psd_reconstruct.py", "label": "PSD Reconstruct", "icon": "image_psd_reconstruct.png", "color": "#5aa88a", "size_priority": 0},
            {"file": "comfyui_workflow_color_edit.py", "label": "ComfyUI Workflow Color Edit", "icon": "comfyui_workflow_color_edit.png", "color": "#5aa88a", "size_priority": 0},
        ]
    },
    "Sort": { 
        "color": "#4a7f7f", 
        "tools": [
            {"file": "tensor_tools_all.py", "label": "Tensor Info Sort Clean", "icon": "tensor_tools_all.png", "color": "#3f6b6b", "size_priority": 0},
            {"file": "voice_action_organizer.py", "label": "Voice Action Organize", "icon": "voice_action_organizer.png", "color": "#bf8f80", "size_priority": 1}
        ]
    },
    "Video": { 
        "color": "#6a5f8f", 
        "tools": [
            {"file": "video_combine.py", "label": "Video Combine", "icon": "video_combine.png", "color": "#5a4f7a", "size_priority": 0},
            {"file": "video_clip_marker.py", "label": "Clip Marker", "icon": "video_clip_marker.png", "color": "#8f80bf", "size_priority": 1}, 
            {"file": "video_place_in_image_composite.py", "label": "Place in Composite", "icon": "video_place_in_image_composite.png", "color": "#7a6fb0", "size_priority": 0},
            {"file": "video_webp_pingpong.py", "label": "WebP PingPong", "icon": "video_webp_pingpong.png", "color": "#4a3f6a", "size_priority": 0},
            {"file": "video_review_and_rank_multi_project.py", "label": "Video Review & Rank Multi Project", "icon": "video_review_and_rank_multi_project.png", "color": "#6a5f8f", "size_priority": 1},
            {"file": "video_psd_to_timelapse_anim.py", "label": "PSD to Timelapse Anim", "icon": "video_psd_to_timelapse_anim.png", "color": "#4a6a8a", "size_priority": 1},
            {"file": "video_add_audio.py", "label": "Add Audio", "icon": "video_add_audio.png", "color": "#4a6a8a", "size_priority": 1},
            {"file": "video_editor_word_rating.py", "label": "Video Word Editor", "icon": "video_editor_word_rating.png", "color": "#4a6a8a", "size_priority": 1},
            {"file": "VIDEO_cursor_removal.py", "label": "Cursor Removal", "icon": "VIDEO_cursor_removal.png", "color": "#4a3f6a", "size_priority": 0},
            {"file": "VIDEO_image_sequence_to_webp.py", "label": "Image Sequence to WebP", "icon": "VIDEO_image_sequence_to_webp.png", "color": "#4a3f6a", "size_priority": 0},
            {"file": "video_audio_batch_processor.py", "label": "Audio Batch Processor", "icon": "video_audio_batch_processor.png", "color": "#4a3f6a", "size_priority": 0},
            {"file": "video_interlacing_fix.py", "label": "Interlacing Fix", "icon": "video_interlacing_fix.png", "color": "#4a3f6a", "size_priority": 0},
            {"file": "video_to_gif_cropper.py", "label": "GIF Cropper", "icon": "video_to_gif_cropper.png", "color": "#4a3f6a", "size_priority": 0},
            {"file": "audio_timing_beat.py", "label": "Audio Timing Beat", "icon": "audio_timing_beat.png", "color": "#4a3f6a", "size_priority": 0},
        ]
    },
    "SD webui Project ": { 
        "color": "#5f5f8f", 
        "tools": [
            {"file": "sd_batch_image_gen_auto1111_webui.py", "label": "Batch Gen WebUI", "icon": "sd_batch_image_gen_auto1111_webui.png", "color": "#8080bf", "size_priority": 1},
            {"file": "projects_from_civitai_info.py", "label": "Projects from Info", "icon": "projects_from_civitai_info.png", "color": "#4f4f7a", "size_priority": 0},
            {"file": "projects_from_images.py", "label": "Projects from Images", "icon": "projects_from_images.png", "color": "#7070b0", "size_priority": 0},
            {"file": "lora_variants.py", "label": "LoRA Variants", "icon": "lora_variants.png", "color": "#60609f", "size_priority": 0},
            {"file": "gen_batch_prompts_in_projects.py", "label": "Batch Prompts", "icon": "gen_batch_prompts_in_projects.png", "color": "#45456a", "size_priority": 0},
            {"file": "gen_image_variant_grid_explore.py", "label": "Variant Grid Explore", "icon": "gen_image_variant_grid_explore.png", "color": "#55558f", "size_priority": 0},
            {"file": "lora_previews_to_list.py", "label": "LoRA Previews to List", "icon": "lora_previews_to_list.png", "color": "#55558f", "size_priority": 0},
            {"file": "tensor_lora_check_compatible_checkpoint.py", "label": "Check LoRA vs Checkpoint", "icon": "tensor_lora_check_compatible_checkpoint.png", "color": "#55558f", "size_priority": 0},
            {"file": "project_status_dashboard.py", "label": "Project Status Dashboard", "icon": "project_status_dashboard.png", "color": "#55558f", "size_priority": 0},
        ]
    }
    ,
    "Dev Tools": {
        "color": "#444444",
        "tools": [
            {"file": "dev_python_imports_to_top.py", "label": "Fix Imports to Top", "icon": "dev_python_imports_to_top.png", "color": "#666666", "size_priority": 0},
            {"file": "dev_python_requirements_env.py", "label": "Requirements & Env", "icon": "dev_python_requirements_env.png", "color": "#666666", "size_priority": 0},
            {"file": "test_safetensors.py", "label": "Test Safetensors", "icon": "test_safetensors.png", "color": "#666666", "size_priority": 0}
        ]
    }
}

# --- GLOBAL SIZING CONSTANTS ---
HEADER_HEIGHT_PX = 12
HEADER_HEIGHT = 24
MIN_CARD_HEIGHT = 68  # Tighter: ~48px icon + ~18-20px text
MAX_CARD_HEIGHT = 140
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 13
MIN_ICON_SIZE = 8
MAX_ICON_SIZE = 32
MIN_BUTTON_WIDTH = 60
BUTTON_PADDING = 0
GROUP_PADDING = 0
CARD_PADDING = 0
MAX_BUTTON_WIDTH = 200

# --- WINDOW DEFAULTS ---
DEFAULT_WINDOW_WIDTH = 400
DEFAULT_WINDOW_HEIGHT = 500

# --- UI ---
ICON_FOLDER = 'icons'
DARK_BG = '#121212'
DARK_CARD = '#1C1C1C'
DARK_TEXT = '#D8D8D8'
DARK_HEADER = '#171717'
CATEGORY_TEXT = '#9aa0a6'  # medium grey for headers

def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb):
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"

def blend_colors(base_hex: str, tint_hex: str, alpha: float) -> str:
    """Blend tint into base by alpha [0..1]."""
    br, bg, bb = _hex_to_rgb(base_hex)
    tr, tg, tb = _hex_to_rgb(tint_hex)
    nr = int(br * (1 - alpha) + tr * alpha)
    ng = int(bg * (1 - alpha) + tg * alpha)
    nb = int(bb * (1 - alpha) + tb * alpha)
    return _rgb_to_hex((nr, ng, nb))

#//========================================================================================================
# --- Utility Functions ---
def get_icon(tool_file, preferred_icon):
    base_dir = Path(__file__).parent
    def _trim_transparent(img: Image.Image) -> Image.Image:
        # Trim fully transparent borders to remove built-in padding
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        bbox = img.split()[-1].getbbox()
        if bbox:
            return img.crop(bbox)
        return img
    # 1) Try explicitly provided icon filename
    if isinstance(preferred_icon, str) and preferred_icon:
        icon_path = base_dir / ICON_FOLDER / preferred_icon
        debug_print(f"get_icon: Trying preferred icon for '{tool_file}': {icon_path}")
        if icon_path.exists():
            try:
                img = Image.open(str(icon_path))
                img = _trim_transparent(img)
                img = img.resize((48, 48), Image.LANCZOS)
                debug_print(f"get_icon: Loaded preferred icon: {icon_path}")
                return ImageTk.PhotoImage(img)
            except Exception:
                debug_print(f"get_icon: Error loading preferred icon '{icon_path}': {traceback.format_exc()}")
        else:
            debug_print(f"get_icon: Preferred icon not found: {icon_path}")
    # 2) Fallback to <tool_base>.png
    fallback_name = os.path.splitext(os.path.basename(tool_file))[0] + '.png'
    fallback_path = base_dir / ICON_FOLDER / fallback_name
    debug_print(f"get_icon: Trying fallback icon for '{tool_file}': {fallback_path}")
    if fallback_path.exists():
        try:
            img = Image.open(str(fallback_path))
            img = _trim_transparent(img)
            img = img.resize((48, 48), Image.LANCZOS)
            debug_print(f"get_icon: Loaded fallback icon: {fallback_path}")
            return ImageTk.PhotoImage(img)
        except Exception:
            debug_print(f"get_icon: Error loading fallback icon '{fallback_path}': {traceback.format_exc()}")
    else:
        debug_print(f"get_icon: Fallback icon not found: {fallback_path}")
    return None

def find_tools():
    py_files = [f for f in os.listdir('.') if f.endswith('.py') and f != 'launch_tools.py']
    debug_print("Python tools in directory:", py_files)
    return TOOL_CONFIG

def shade_color(color, factor):
    r = int(int(color[1:3], 16) * factor)
    g = int(int(color[3:5], 16) * factor)
    b = int(int(color[5:7], 16) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"

class GroupHeader(tk.Frame):
    def __init__(self, parent, text, color, **kwargs):
        super().__init__(parent, bg=DARK_HEADER, **kwargs)
        debug_print(f"GroupHeader.__init__: Creating header '{text}'")
        self.label = tk.Label(
            self,
            text=text,
            bg=DARK_HEADER,
            fg=CATEGORY_TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor='center'
        )
        self.label.pack(expand=True, fill='x', padx=0, pady=0)
        self.group_name = text

class ToolCard(tk.Frame):
    """A custom widget for tool buttons (static icon + text) with dark tinted backgrounds"""
    MIN_HEIGHT = 50

    def __init__(self, parent, launcher_instance, group_name, tool_name, tool_file, icon_imgtk, color, size_priority):
        debug_print(f"TOOLCARD INIT: {tool_name} ({tool_file})")
        debug_print(f"ToolCard.__init__: Creating card '{tool_name}' ({tool_file}) in group '{group_name}'")
        super().__init__(parent, bg=DARK_CARD, bd=0, relief='flat', highlightthickness=0)
        self.launcher = launcher_instance
        self.tool_file = tool_file
        self.tool_name = tool_name # Store for resize debugging
        self.group_name = group_name
        self.color = color
        self.size_priority = size_priority
        # Slightly tint the dark card by the tool color (darker overall)
        self.tile_color = blend_colors(DARK_CARD, color, 0.02)

        self.content = tk.Frame(self, bg=self.tile_color)
        self.content.pack(expand=True, fill='both', padx=0, pady=0)
        # Layout: icon (top), text (bottom) with minimal vertical slack
        # Exact fit for 48px icon; text row minsize will be updated after render
        self.content.grid_rowconfigure(0, weight=0, minsize=48)
        self.content.grid_rowconfigure(1, weight=0, minsize=0)
        self.content.grid_columnconfigure(0, weight=1)

        # Icon
        if isinstance(icon_imgtk, ImageTk.PhotoImage):
            self.icon_label = tk.Label(self.content, image=icon_imgtk, bg=self.tile_color, borderwidth=0, highlightthickness=0)
            self.icon_image_tk = icon_imgtk
            self.icon_label.grid(row=0, column=0, sticky='n', padx=0, pady=(0, 0))
        else:
            self.icon_label = tk.Label(self.content, text=' ', bg=self.tile_color)
            self.icon_label.grid(row=0, column=0, sticky='n', padx=0, pady=(0, 0))

        # Text label rendered with black glow to improve contrast
        self.text_color = blend_colors(DARK_TEXT, color, 0.15)
        self.text_label_imgtk = self._render_text_with_glow(tool_name, 11, self.text_color)
        self.text_label = tk.Label(self.content, image=self.text_label_imgtk, bg=self.tile_color, borderwidth=0, highlightthickness=0)
        # Add a small bottom padding to avoid clipping
        self.text_label.grid(row=1, column=0, sticky='n', padx=0, pady=(0, 2))
        # Set text row minsize to actual image height to avoid extra gap above/below
        try:
            text_h = self.text_label_imgtk.height()
            # Add a few pixels to minsize to ensure no clipping
            self.content.grid_rowconfigure(1, minsize=text_h + 2)
        except Exception:
            pass

        # Bind events
        widgets_to_bind = [self, self.content, self.icon_label, self.text_label]
        for widget in widgets_to_bind:
            if widget is not None:
                widget.bind('<Button-1>', lambda e, t=self.tool_file: self.launcher.run_tool(t))
                widget.bind('<Enter>', lambda e: self._on_enter(self.tile_color))
                widget.bind('<Leave>', lambda e: self._on_leave(self.tile_color))
        debug_print(f"DONE TOOLCARD: {tool_name}")

    def _on_enter(self, base_tile_color):
        new_color = shade_color(base_tile_color, 0.95)
        widgets = [self, self.content, self.icon_label, self.text_label]
        # Remove duplicates and None
        seen = set()
        widgets = [w for w in widgets if w is not None and id(w) not in seen and not seen.add(id(w))]
        for widget in widgets:
            widget.configure(bg=new_color)

    def _on_leave(self, base_tile_color):
        widgets = [self, self.content, self.icon_label, self.text_label]
        seen = set()
        widgets = [w for w in widgets if w is not None and id(w) not in seen and not seen.add(id(w))]
        for widget in widgets:
            widget.configure(bg=base_tile_color)

    def resize(self, card_height, card_width):
        debug_print(f"ToolCard.resize ({self.tool_name}): Target Height={card_height}, Width={card_width}")
        card_height = max(MIN_CARD_HEIGHT, int(card_height))
        card_width = max(MIN_BUTTON_WIDTH, int(card_width))
        debug_print(f"ToolCard.resize ({self.tool_name}): Clamped Height={card_height}, Width={card_width}")
        # Re-render text image with appropriate font size and glow
        font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, int(card_height * 0.14)))
        # Ensure text fits available space under the 48px icon row with a small margin
        available_text_h = max(8, card_height - 48 - 4)
        # Roughly map font size to height; keep some headroom
        font_size = min(font_size, int(available_text_h * 0.90))
        img = self._render_text_with_glow(self.tool_name, font_size, self.text_color)
        self.text_label_imgtk = img
        self.text_label.configure(image=self.text_label_imgtk)
        # Update row minsize to the new text image height for tight fit
        try:
            text_h = self.text_label_imgtk.height()
            self.content.grid_rowconfigure(1, minsize=text_h + 2)
        except Exception:
            pass

    def _render_text_with_glow(self, text: str, font_size: int, fg_hex: str):
        # Load a font
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        # Measure text
        dummy = Image.new('RGBA', (1, 1))
        d = ImageDraw.Draw(dummy)
        bbox = d.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        # Slightly larger padding to avoid glyph descender clipping
        pad = 2
        img = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw black glow by multiple offsets
        glow_color = (0, 0, 0, 180)
        x0, y0 = pad, pad
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x0 + dx, y0 + dy), text, font=font, fill=glow_color)

        # Draw main text
        r, g, b = _hex_to_rgb(fg_hex)
        draw.text((x0, y0), text, font=font, fill=(r, g, b, 255))

        return ImageTk.PhotoImage(img)

class ToolLauncher(tk.Tk):
    def __init__(self, *args, **kwargs):
        debug_print("ToolLauncher.__init__: Start")
        super().__init__(*args, **kwargs)
        self.title("Diffusion Project Tool Launcher")
        self.geometry(f'{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}') # Set initial size
        self.minsize(300, 400) # Enforce minimum size (Lowered values)
        self.configure(bg=DARK_BG)

        # State variables
        self._resize_in_progress = False
        self._initial_layout_done = False # Ensure layout runs at least once
        self._last_width = 0
        self._last_height = 0
        self._resize_after_id = None # For debouncing resize events
        self.last_group_cols = {} # 
        self._resize_job = None # 

        self._build_ui()

        # Populate the UI with tool cards
        self._populate_widgets()

        self.bind('<Configure>', self._on_resize)

    def _build_ui(self):
        self.inner_frame = tk.Frame(self, bg=DARK_BG)
        self.inner_frame.pack(expand=True, fill='both', padx=0, pady=0)

        self.tool_cards = [] 
        self.group_headers = []
        self.icon_images = {} 

    def _populate_widgets(self):
        for widget in self.inner_frame.winfo_children():
            widget.destroy()
            
        self.tool_cards.clear()
        self.group_headers.clear()
        self.icon_images.clear() # Clear stored icon images
        
        tool_config = TOOL_CONFIG # Use the constant directly
        debug_print(f"ToolLauncher._populate_widgets: Processing TOOL_CONFIG with {len(tool_config)} groups.")

        for group, group_info in tool_config.items():
            tools = group_info.get("tools", [])
            if not tools:
                debug_print(f"ToolLauncher._populate_widgets: Skipping empty group '{group}'")
                continue
                
            header = GroupHeader(self.inner_frame, group, group_info["color"])
            self.group_headers.append(header)
            
            for tool in tools:
                debug_print(f"ToolLauncher._populate_widgets: Getting icon for {tool['file']}")
                icon = get_icon(tool["file"], tool.get("icon", " ")) 
                if isinstance(icon, ImageTk.PhotoImage):
                    self.icon_images[tool["file"]] = icon
                    
                debug_print(f"ToolLauncher._populate_widgets: Creating card for '{tool['label']}'")
                card = ToolCard(
                    self.inner_frame,
                    self, # PASS self (the ToolLauncher instance) HERE
                    group,
                    tool["label"],
                    tool["file"],
                    icon,
                    tool.get("color", group_info["color"]), # Use specific tool color if defined
                    tool.get("size_priority", 0)
                )
                self.tool_cards.append(card)

        debug_print("ToolLauncher._populate_widgets: Finished creating widgets")
        debug_print(f"_populate_widgets: Populated {len(self.group_headers)} headers and {len(self.tool_cards)} cards.")

    def run_tool(self, tool_file):
        """Runs the selected tool script in a new persistent console window,
           attempting to use a local 'venv' if present."""
        launcher_dir = Path(__file__).parent
        # Resolve possible locations for the tool: root, tools/, and tools/<basename>
        candidates = []
        p_in = Path(tool_file)
        if p_in.is_absolute():
            candidates.append(p_in)
        else:
            candidates.append(launcher_dir / p_in)
            candidates.append(launcher_dir / 'tools' / p_in)
            candidates.append(launcher_dir / 'tools' / p_in.name)

        tool_path = None
        for cand in candidates:
            if cand.exists():
                tool_path = cand
                break

        if tool_path is None:
            print(f"ERROR: Tool script not found in expected locations for '{tool_file}'.")
            for idx, cand in enumerate(candidates, 1):
                debug_print(f"  Candidate {idx}: {cand}")
            return

        # --- Determine Python Executable (Check for Venv) ---
        venv_python_path = launcher_dir / "venv" / "Scripts" / "python.exe"
        python_executable = None

        if venv_python_path.exists():
            python_executable = str(venv_python_path)
            debug_print(f"Found venv Python executable: {python_executable}")
        else:
            print(f"WARNING: Local venv not found at '{venv_python_path}'.")
            print(f"         Attempting to launch '{tool_path.name}' using the launcher's Python: {sys.executable}")
            python_executable = sys.executable # Fallback
            debug_print(f"Using fallback Python executable: {python_executable}")


        debug_print(f"Attempting to run tool: {tool_path}")
        debug_print(f"  Using Python: {python_executable}")

        # Simplified command: start cmd /k python_path tool_path
        launch_command_list = ['cmd', '/c', 'start', 'cmd', '/k', python_executable, str(tool_path)] # Use raw paths

        debug_print(f"  Launching with command list: {launch_command_list}")
        # Note: ' '.join might not accurately represent final quoting if paths have spaces
        debug_print(f"  Approximate shell command: {' '.join(launch_command_list)}")

        # --- Execution ---
        try:
            process = subprocess.Popen(launch_command_list, shell=False) # shell=False is safer
            debug_print(f"  Launched process (PID: {process.pid if process else 'N/A'})")
        except FileNotFoundError:
            print(f"ERROR: Could not execute 'cmd' or Python executable '{python_executable}'. Check PATH or the executable path.")
            debug_print(f"ERROR: 'cmd' or Python not found ('{python_executable}'), cannot launch tool.")
        except Exception as e:
            print(f"Launch Error: Failed to launch tool '{tool_file}' using '{python_executable}': {e}")
            debug_print(f"ERROR: Failed to launch tool '{tool_file}' using '{python_executable}': {e}\n{traceback.format_exc()}")


    # --- Layout Calculation --- #
    def _calculate_group_layouts(self, width):
        debug_print(f"ToolLauncher._calculate_group_layouts: Start for width {width}")
        if width <= 0:
            debug_print(f"ToolLauncher._calculate_group_layouts: ERROR - Invalid width ({width})")
            return []

        layouts = []
        for header_widget in self.group_headers:
            group_name = header_widget.group_name
            group_tools = [card for card in self.tool_cards if card.group_name == group_name]
            num_tools = len(group_tools)

            if num_tools == 0:
                debug_print(f"ToolLauncher._calculate_group_layouts: Skipping group '{group_name}' - no cards found.")
                continue 

            debug_print(f"ToolLauncher._calculate_group_layouts: Processing group '{group_name}' with {num_tools} tools.")

            inner_width = width - (2 * GROUP_PADDING) 
            debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': Initial inner_width = {inner_width:.2f} (width={width})")

            # Enforce exactly 3 columns (or fewer if <3 tools)
            best_cols = min(3, num_tools)
            self.last_group_cols[group_name] = best_cols

            tool_rows = (num_tools + best_cols - 1) // best_cols

            total_padding_width = (best_cols - 1) * CARD_PADDING
            available_for_cards = max(1, inner_width - total_padding_width)
            actual_card_width = max(MIN_BUTTON_WIDTH, available_for_cards / max(1, best_cols))
            actual_card_width = min(MAX_BUTTON_WIDTH, actual_card_width)

            debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}' -> FINAL Cols: {best_cols}, Rows: {tool_rows}")

            layouts.append({
                "group_name": group_name,
                "num_tools": num_tools,
                "tool_cols": best_cols,
                "tool_rows": tool_rows,
                "card_width": actual_card_width,
                "group_tools": group_tools 
            })

        debug_print(f"ToolLauncher._calculate_group_layouts: Finished calculations. {len(layouts)} layouts generated.")
        return layouts

    def _place_headers_and_tools(self, layouts, card_height, width):
        debug_print(f"_place_headers_and_tools: Start. Card Height={card_height}, Width={width}")
        self.inner_frame.grid_rowconfigure(0, weight=0) 
        self.inner_frame.grid_columnconfigure(0, weight=0) 
        for i in range(self.inner_frame.grid_size()[1]): self.inner_frame.grid_rowconfigure(i, weight=0)
        for i in range(self.inner_frame.grid_size()[0]): self.inner_frame.grid_columnconfigure(i, weight=0)

        for widget in self.inner_frame.winfo_children():
            widget.grid_forget()
            
        if not self.group_headers and not self.tool_cards:
            debug_print("ToolLauncher._place_headers_and_tools: No headers or cards to place. Aborting.")
            return

        current_y = 0 

        for i, layout in enumerate(layouts):
            group_name = layout["group_name"]
            actual_card_width = layout["card_width"]
            num_rows_in_group = layout["tool_rows"] 
            debug_print(f"_place_headers_and_tools: Processing Group {i+1}/{len(layouts)}: '{group_name}' ({num_rows_in_group} rows)")

            header = next((h for h in self.group_headers if h.group_name == group_name), None)
            header_placed_height = 0 
            if header and isinstance(header, GroupHeader):
                 header_width = width - (2 * GROUP_PADDING) 
                 debug_print(f"    _place_headers_and_tools: Placing header '{group_name}' at y={current_y}")
                 header.place(x=GROUP_PADDING, y=current_y, width=header_width, height=HEADER_HEIGHT, anchor='nw')
                 header_placed_height = HEADER_HEIGHT 
                 debug_print(f"    _place_headers_and_tools: Header placed. Used height: {header_placed_height}")
            else:
                 debug_print(f"  _place_headers_and_tools: WARNING - Header not found or invalid for group '{group_name}'.")

            current_y += header_placed_height
            if header_placed_height > 0: 
                current_y += GROUP_PADDING
            debug_print(f"    _place_headers_and_tools: current_y after header processing: {current_y}")

            group_tool_cards = [card for card in self.tool_cards if card.group_name == group_name]
            debug_print(f"  _place_headers_and_tools: Found {len(group_tool_cards)} cards for group '{group_name}'. Placing starting at y={current_y}")

            if not group_tool_cards:
                 debug_print(f"  _place_headers_and_tools: No cards to place for group '{group_name}'. Skipping to next group.")
                 continue 

            group_start_card_y = current_y 
            tool_rows = layout["tool_rows"] 

            for idx, card in enumerate(group_tool_cards):
                 row = idx // layout["tool_cols"]
                 col = idx % layout["tool_cols"]
                 x = GROUP_PADDING + col * (actual_card_width + CARD_PADDING)
                 y_pos = group_start_card_y + row * (card_height + CARD_PADDING)
                 debug_print(f"      _place_headers_and_tools: Placing card '{card.tool_file}' (idx={idx}, row={row}, col={col}) at x={x:.1f}, y={y_pos:.1f} W={actual_card_width:.1f} H={card_height:.1f} [group_start_y={group_start_card_y}]")
                 card.place(x=x, y=y_pos, width=actual_card_width, height=card_height)

            group_card_area_height = num_rows_in_group * card_height + max(0, num_rows_in_group - 1) * CARD_PADDING
            debug_print(f"    _place_headers_and_tools: Calculated card area height for group: {group_card_area_height}")
            current_y = group_start_card_y + group_card_area_height + GROUP_PADDING
            debug_print(f"    _place_headers_and_tools: current_y updated for next group: {current_y}")

        debug_print(f"_place_headers_and_tools: FINISHED placement loop. Final calculated current_y={current_y}")
        self.inner_frame.update_idletasks()
        debug_print(f"    _place_headers_and_tools: inner_frame geometry AFTER update: W={self.inner_frame.winfo_width()}, H={self.inner_frame.winfo_height()}")

        debug_print("_place_headers_and_tools: --- Post-Placement Validation ---")
        placed_widgets = self.inner_frame.winfo_children()
        if not placed_widgets:
            debug_print("    _place_headers_and_tools: VALIDATION FAILED - No child widgets found in inner_frame!")
        else:
            debug_print(f"    _place_headers_and_tools: Validating {len(placed_widgets)} widgets in inner_frame...")
            for i, widget in enumerate(placed_widgets):
                widget_class = widget.winfo_class()
                is_mapped = widget.winfo_ismapped() 
                try:
                    p_info = widget.place_info()
                    act_x = widget.winfo_x()
                    act_y = widget.winfo_y()
                    act_w = widget.winfo_width()
                    act_h = widget.winfo_height()
                    debug_print(f"    Widget {i+1}/{len(placed_widgets)}: Class={widget_class}, Mapped={is_mapped}")
                    debug_print(f"        Placed Args: {p_info}")
                    debug_print(f"        Actual Geom: x={act_x}, y={act_y}, W={act_w}, H={act_h}")
                except Exception as e:
                    debug_print(f"    Widget {i+1}/{len(placed_widgets)}: Class={widget_class}, Mapped={is_mapped} - ERROR getting info: {e}")
        debug_print("_place_headers_and_tools: --- End Validation ---")

    def _do_resize_logic(self, width, height):
        debug_print(f"\n--- _do_resize_logic triggered for W={width}, H={height} ---")
        if self._resize_in_progress:
            debug_print("_do_resize_logic: Resize already in progress, skipping.")
            return
        if width == self._last_width and height == self._last_height:
            debug_print(f"_do_resize_logic: Size unchanged ({width}x{height}) since last run, skipping.")
            self._resize_after_id = None
            return

        debug_print(f"_do_resize_logic: Calculating layouts...")
        layouts = self._calculate_group_layouts(width)
        debug_print(f"_do_resize_logic: Layout calculation complete. Result: {layouts}") 

        if not layouts:
             debug_print("_do_resize_logic: No layouts calculated, aborting placement.")
             return 

        total_rows = sum(1 + layout['tool_rows'] for layout in layouts)
        debug_print(f"_do_resize_logic: Total calculated rows (headers + tools): {total_rows}")
        
        total_fixed_vertical_space = 0 
        num_groups_with_headers = 0
        num_padding_gaps_between_cards = 0

        for i, layout in enumerate(layouts):
            rows_in_group = layout.get("tool_rows", 0)
            if layout.get("header"):
                total_fixed_vertical_space += HEADER_HEIGHT
                num_groups_with_headers += 1
            if rows_in_group > 1:
                num_padding_gaps_between_cards += (rows_in_group - 1)
            if i > 0 :
                total_fixed_vertical_space += GROUP_PADDING

        if layouts:
             total_fixed_vertical_space += GROUP_PADDING

        total_fixed_vertical_space += num_groups_with_headers * GROUP_PADDING

        total_fixed_vertical_space += num_padding_gaps_between_cards * CARD_PADDING


        available_height_for_all_cards = max(1, height - total_fixed_vertical_space)
        debug_print(f"    _do_resize_logic: TotalRows={total_rows}, FixedSpace={total_fixed_vertical_space}, AvailableForCards={available_height_for_all_cards}")

        if total_rows > 0:
            calculated_card_height = available_height_for_all_cards / total_rows
        else:
            calculated_card_height = 60 

        card_height = max(MIN_CARD_HEIGHT, min(MAX_CARD_HEIGHT, int(calculated_card_height)))

        debug_print(f"    _do_resize_logic: Calculated Card Height: {calculated_card_height:.2f} -> Clamped: {card_height}")
        
        debug_print(f"  _do_resize_logic: Placing widgets with dynamic CardHeight={card_height}")
        self._place_headers_and_tools(layouts, card_height, width) 

        self._last_width = width
        self._last_height = height
        debug_print(f"_do_resize_logic: Updated last size to W={self._last_width}, H={self._last_height}") 
        debug_print(f"_do_resize_logic: Marked _initial_layout_done = True")

    def _on_resize(self, event=None):
        if event and event.widget != self:
            return

        new_width = self.winfo_width()
        new_height = self.winfo_height()

        if self._resize_job:
            self.after_cancel(self._resize_job)

        self._resize_job = self.after(250, lambda w=new_width, h=new_height: self._do_resize_logic(w, h))

if __name__ == '__main__':
    app = ToolLauncher()
    app.mainloop()
