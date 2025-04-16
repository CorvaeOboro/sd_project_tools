"""
LAUNCH TOOLS 
a gui to display and launch tools from the sd project venv
arranges and prioritizes common tools
"""

import os
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import traceback
import argparse
import math

# --- Debug Print Helper ---
DEBUG = False
def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

# --- GLOBAL SIZING CONSTANTS ---
HEADER_HEIGHT_PX = 12
HEADER_HEIGHT = 30
MIN_CARD_HEIGHT = 40
MAX_CARD_HEIGHT = 120
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 16
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

# --- CONFIGURABLE ---
ICON_FOLDER = 'icons'
DARK_BG = '#181b22'
DARK_CARD = '#232635'
DARK_TEXT = '#e0e6f0'
DARK_HEADER = '#32364a'

# --- Tool Configuration ---
TOOL_CONFIG = {
    "Image Review": { 
        "color": "#7a5f7a", 
        "tools": [
            {"file": "image_review_and_rank_multi_project.py", "label": "Review & Rank Multi Project", "icon": "", "color": "#9f809f", "size_priority": 1},
            {"file": "image_review_and_rank.py", "label": "Review & Rank", "icon": "", "color": "#6b4f6b", "size_priority": 0},
            {"file": "image_review_and_rank_multi.py", "label": "Review & Rank Multi", "icon": "", "color": "#5a3f5a", "size_priority": 0},
        ]
    },
    "Prompt": { 
        "color": "#4a785f", 
        "tools": [
            {"file": "gen_project_prompt_entry.py", "label": "Gen Project Entry", "icon": "", "color": "#6aaa8f", "size_priority": 1},
            {"file": "image_text_prompt_tools.py", "label": "Image Text Prompt Tools", "icon": "", "color": "#3f6651", "size_priority": 0},
        ]
    },
    "Model Info and Sort": { 
        "color": "#4a7f7f", 
        "tools": [
            {"file": "sd_civitai_info_get.py", "label": "Civitai Info Get", "icon": "", "color": "#3f6b6b", "size_priority": 0},
            {"file": "sd_civitai_sort_by_type.py", "label": "Sort by Type", "icon": "", "color": "#6f9f9f", "size_priority": 0},
            {"file": "sd_sort_civitai_files.py", "label": "Sort Civitai Files", "icon": "", "color": "#5a8a8a", "size_priority": 0},
        ]
    },
    "Video": { 
        "color": "#6a5f8f", 
        "tools": [
            {"file": "video_combine.py", "label": "Video Combine", "icon": "", "color": "#5a4f7a", "size_priority": 0},
            {"file": "video_clip_marker.py", "label": "Clip Marker", "icon": "", "color": "#8f80bf", "size_priority": 1}, 
            {"file": "video_place_in_image_composite.py", "label": "Place in Composite", "icon": "", "color": "#7a6fb0", "size_priority": 0},
            {"file": "video_webp_pingpong.py", "label": "WebP PingPong", "icon": "", "color": "#4a3f6a", "size_priority": 0},
        ]
    },
    "SD webui Project ": { 
        "color": "#5f5f8f", 
        "tools": [
            {"file": "sd_batch_image_gen_auto1111_webui.py", "label": "Batch Gen WebUI", "icon": "", "color": "#8080bf", "size_priority": 1},
            {"file": "projects_from_civitai_info.py", "label": "Projects from Info", "icon": "", "color": "#4f4f7a", "size_priority": 0},
            {"file": "projects_from_images.py", "label": "Projects from Images", "icon": "", "color": "#7070b0", "size_priority": 0},
            {"file": "lora_variants.py", "label": "LoRA Variants", "icon": "", "color": "#60609f", "size_priority": 0},
            {"file": "gen_batch_prompts_in_projects.py", "label": "Batch Prompts", "icon": "", "color": "#45456a", "size_priority": 0},
            {"file": "gen_image_variant_grid_explore.py", "label": "Variant Grid Explore", "icon": "", "color": "#55558f", "size_priority": 0},
        ]
    }
}

# --- Utility Functions ---
def get_icon(tool_file, fallback_emoji):
    icon_path = os.path.join(ICON_FOLDER, os.path.splitext(tool_file)[0] + '.png')
    if os.path.exists(icon_path):
        try:
            img = Image.open(icon_path).resize((48, 48), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            debug_print(f"Error loading icon for {tool_file}: {traceback.format_exc()}")
            pass
    return fallback_emoji

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
        self.label = tk.Label(self, text=text.upper(), bg=DARK_HEADER, fg=DARK_TEXT,
                            font=("Segoe UI", 10, "bold"), anchor='w')
        self.label.pack(side='left', padx=5, pady=3)
        self.group_name = text

class ToolCard(tk.Frame):
    """A custom widget for tool buttons with consistent layout"""
    MAX_LABEL_LINES = 2
    MIN_HEIGHT = 50

    def __init__(self, parent, launcher_instance, group_name, tool_name, tool_file, icon_text, color, size_priority):
        debug_print(f"ToolCard.__init__: Creating card '{tool_name}' ({tool_file}) in group '{group_name}'")
        super().__init__(parent, bg=DARK_CARD, bd=0, relief='flat', highlightthickness=0) # Set bd=0, relief='flat', highlightthickness=0
        self.launcher = launcher_instance
        self.tool_file = tool_file
        self.tool_name = tool_name # Store for resize debugging
        self.group_name = group_name
        self.color = color
        self.size_priority = size_priority
        self.icon_text = icon_text

        self.content = tk.Frame(self, bg=color)
        self.content.pack(expand=True, fill='both', padx=2, pady=2)

        self.content.grid_rowconfigure(0, weight=55)  
        self.content.grid_rowconfigure(1, weight=45)  
        self.content.grid_columnconfigure(0, weight=1)

        if isinstance(icon_text, ImageTk.PhotoImage):
            self.icon_label = tk.Label(self.content, image=icon_text, bg=color)
            self.icon_image_tk = icon_text
        else:
            self.icon_label = tk.Label(self.content, text=icon_text, bg=color, fg=DARK_TEXT)
        self.icon_label.grid(row=0, column=0, sticky='nsew', padx=2, pady=(2, 0))

        self.text_label = tk.Label(self.content, text=tool_name, bg=color, fg=DARK_TEXT,
                                  justify='center', anchor='center')
        self.text_label.grid(row=1, column=0, sticky='nsew')

        for widget in (self, self.content, self.icon_label, self.text_label):
            widget.bind('<Button-1>', lambda e, t=self.tool_file: self.launcher.run_tool(t))
            widget.bind('<Enter>', lambda e: self._on_enter(color))
            widget.bind('<Leave>', lambda e: self._on_leave(color))

    def _on_enter(self, color):
        new_color = shade_color(color, 0.85)
        for widget in (self, self.content, self.icon_label, self.text_label):
            widget.configure(bg=new_color)

    def _on_leave(self, color):
        for widget in (self, self.content, self.icon_label, self.text_label):
            widget.configure(bg=color)

    def resize(self, card_height, card_width):
        debug_print(f"ToolCard.resize ({self.tool_name}): Target Height={card_height}, Width={card_width}")
        card_height = max(MIN_CARD_HEIGHT, int(card_height))
        card_width = max(MIN_BUTTON_WIDTH, int(card_width))
        debug_print(f"ToolCard.resize ({self.tool_name}): Clamped Height={card_height}, Width={card_width}")

        text = self.text_label.cget('text')
        text_lines = max(1, len(text.split()))
        chars_per_line = max(1, len(text) // text_lines)
        
        available_height = card_height - 4  
        icon_height = int(available_height * 0.55)  
        text_height = int(available_height * 0.45)  

        font_size = int(min(
            MAX_FONT_SIZE,
            max(MIN_FONT_SIZE,
                min(text_height // max(1, text_lines),  
                    (card_width - 4) // max(1, chars_per_line) * 1.2))  
        ))
        debug_print(f"ToolCard.resize ({self.tool_name}): Calculated Font Size={font_size}")

        icon_size = int(min(
            MAX_ICON_SIZE,
            max(MIN_ICON_SIZE,
                min(icon_height - 2,  
                    (card_width - 4) * 0.8))  
        ))
        debug_print(f"ToolCard.resize ({self.tool_name}): Calculated Icon Size={icon_size}")

        wrap_width = max(50, card_width - 4)
        self.text_label.configure(wraplength=wrap_width)
        
        if isinstance(self.icon_label.cget('image'), str):
            self.icon_label.configure(font=("Segoe UI Emoji", icon_size))
        self.text_label.configure(font=("Segoe UI", font_size, "bold"))

class ToolLauncher(tk.Tk):
    def __init__(self, *args, **kwargs):
        debug_print("ToolLauncher.__init__: Start")
        super().__init__(*args, **kwargs)
        self.title("SD Project Tool Launcher")
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
        self.inner_frame.pack(expand=True, fill='both', padx=2, pady=2) 

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
        tool_path = Path(tool_file)
        if not tool_path.is_absolute():
            tool_path = launcher_dir / tool_file

        if not tool_path.exists():
            messagebox.showerror("Error", f"Tool script not found:\n{tool_path}")
            debug_print(f"ERROR: Tool script not found at {tool_path}")
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
             messagebox.showerror("Error", f"Could not execute 'cmd' or Python executable '{python_executable}'. Is it in your system's PATH or is the path correct?")
             debug_print(f"ERROR: 'cmd' or Python not found ('{python_executable}'), cannot launch tool.")
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch tool '{tool_file}' using '{python_executable}':\n{e}")
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

            if MIN_BUTTON_WIDTH <= 0 or inner_width <= 0:
                debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': ERROR - Invalid MIN_BUTTON_WIDTH ({MIN_BUTTON_WIDTH}) or inner_width ({inner_width:.2f}), using 1 column.")
                best_cols = 1
                potential_new_cols = 1 
            else:
                col_divisor = MIN_BUTTON_WIDTH + CARD_PADDING
                potential_new_cols = max(1, int(inner_width // col_divisor))
                last_cols = self.last_group_cols.get(group_name, 1) 

                width_needed_for_last = (last_cols * MIN_BUTTON_WIDTH) + max(0, last_cols - 1) * CARD_PADDING
                hysteresis_buffer = MIN_BUTTON_WIDTH * 0.5 

                debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': PotentialNewCols={potential_new_cols}, LastCols={last_cols}, InnerW={inner_width:.1f}, NeededLast={width_needed_for_last:.1f}, Buffer={hysteresis_buffer:.1f}")

                if potential_new_cols > last_cols:
                    threshold_to_increase = width_needed_for_last + hysteresis_buffer
                    if inner_width >= threshold_to_increase:
                        best_cols = potential_new_cols
                        debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': Hysteresis -> Increasing cols to {best_cols} (InnerW {inner_width:.1f} >= Threshold {threshold_to_increase:.1f})")
                    else:
                        best_cols = last_cols
                        debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': Hysteresis -> Preventing increase from {last_cols} (InnerW {inner_width:.1f} < Threshold {threshold_to_increase:.1f})")
                elif potential_new_cols < last_cols:
                    threshold_to_decrease = width_needed_for_last - hysteresis_buffer
                    if inner_width < threshold_to_decrease:
                         best_cols = potential_new_cols
                         debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': Hysteresis -> Decreasing cols to {best_cols} (InnerW {inner_width:.1f} < Threshold {threshold_to_decrease:.1f})")
                    else:
                         best_cols = last_cols
                         debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': Hysteresis -> Preventing decrease from {last_cols} (InnerW {inner_width:.1f} >= Threshold {threshold_to_decrease:.1f})")
                else: 
                    best_cols = last_cols
                    debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': Hysteresis -> Maintaining cols at {best_cols}")

            best_cols = min(best_cols, num_tools)
            best_cols = max(1, best_cols)

            if num_tools > 4:
                forced_max_cols = math.ceil(num_tools / 2)
                best_cols = min(best_cols, forced_max_cols)
                debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': {num_tools} tools (>4). Forcing max cols based on tool count ({forced_max_cols}). Limited by width to {best_cols}.")
            else:
                debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': {num_tools} tools (<=4). Max cols based on width: {best_cols}.")

            self.last_group_cols[group_name] = best_cols

            tool_rows = (num_tools + best_cols - 1) // best_cols

            if best_cols <= 0:
                 debug_print(f"ToolLauncher._calculate_group_layouts: Group '{group_name}': ERROR - Invalid best_cols ({best_cols}) for group '{group_name}', defaulting card_width.")
                 actual_card_width = MIN_BUTTON_WIDTH 
            else:
                total_padding_width = (best_cols - 1) * CARD_PADDING
                available_for_cards = inner_width - total_padding_width
                actual_card_width = max(MIN_BUTTON_WIDTH, available_for_cards / best_cols if best_cols > 0 else MIN_BUTTON_WIDTH) 
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
    parser = argparse.ArgumentParser(description="SD Project Tool Launcher")
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug printing')
    args = parser.parse_args()

    DEBUG = args.debug 
    if DEBUG:
        debug_print("--- Debug mode enabled ---")
    app = ToolLauncher()
    app.mainloop()
