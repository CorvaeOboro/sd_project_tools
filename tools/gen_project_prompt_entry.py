"""
GEN Input Prompt Entry UI for Stable Diffusion Project 

A GUI tool for managing and organizing projects with multiple Stable Diffusion prompt files.
a visual interface for prompt entry and review.

Features:
    - Visual dashboard displaying asset PSD preview and their associated prompts in prompt subfolder
    - prompt .md text files for :
        * SDXL positive + negative , SD1.5 positive + negative  Flux , Video  , Florence2 generated 
    - Support for both flat and hierarchical file organization

Usage:
    1. Launch the tool , paste project folder path , 
    2. Choose your preferred file organization (flat or subfolder)
    3. click Load
    4. Edit prompts directly in the UI
    5. Changes are automatically saved

TypeA Project Structure psds are in main folder :
    project_folder/
    ├── item_example.psd                     # Source PSD file
    ├── item_example/                        # Asset subfolder
    │   ├── prompt/                          # Prompt files subfolder
    │   │   ├── prompt_sdxl.md               # SDXL positive prompts
    │   │   ├── prompt_sdxl_negative.md      # SDXL negative prompts
    │   │   ├── prompt_sd15.md               # SD1.5 positive prompts
    │   │   ├── prompt_sd15_negative.md      # SD1.5 negative prompts
    │   │   ├── prompt_flux.md               # Additional notes/metadata
    │   │   ├── prompt_video.md              # Video prompts
    │   │   └── prompt_florence.md           # Florence generated prompts
    ├── item_exampleB.psd                    # Source PSD file
    ├── item_exampleB/                       # Asset subfolder
    │   ├── prompt/                          # Prompt files subfolder
    │   │   ├── prompt_sdxl.md               # SDXL positive prompts
    │   │   ├── ...                          # continued

TypeB Project Structure psds are in subfolders:
    project_folder/
    ├── item_example/                        # Asset subfolder
    │   ├── item_example.psd                 # Source PSD file
    │   ├── prompt/                          # Prompt files subfolder
    │   │   ├── prompt_sdxl.md               # SDXL positive prompts
    │   │   ├── ...                          # continued
    ├── item_exampleB/                       # Asset subfolder
    │   ├── item_exampleB.psd                # Source PSD file
    │   ├── prompt/                          # Prompt files subfolder
    │   │   ├── prompt_sdxl.md               # SDXL positive prompts
    │   │   ├── ...                          # continued

FEATURES TODO :
- [ ] use florence and other llms to add to and modify a prompt toward a style guide and examples per the modeltype
- [ ] separate the UI into its own class for modularity 
- [ ] color code the video prompt entryas muted purple 
- [ ] add a button to multiply the strength of anythig with strength over 1 , to reduce 
add more Simplify prompt buttons such as = ( remove loras ) , deduplicate ( comma delimeter based)
"""


import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import re
from PIL import Image
import shutil
import json

class AssetDataEntryUI(tk.Tk):
    def __init__(self, default_folder=""):
        super().__init__()
        self.title("Asset Data Entry")
        self.geometry("1600x800")  # widened for extra columns

        # Dark (black) mode styles
        self.configure(bg="black")
        style = ttk.Style(self)
        style.theme_use("clam")

        # Make label text white, background black
        style.configure("TLabel", background="black", foreground="white")
        style.configure("TCheckbutton", background="black", foreground="white")
        style.configure("TFrame", background="black")

        # Scrollbar in dark style
        style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background="#3c3c3c",
            darkcolor="#3c3c3c",
            lightcolor="#3c3c3c",
            troughcolor="#1c1c1c",
            bordercolor="#3c3c3c"
        )

        # Button style
        style.configure("TButton", background="#3c3c3c", foreground="white")

        # Store the folder in a StringVar so the user can change it via the UI
        self.folder_var = tk.StringVar(value=default_folder)
        self.input_folder = default_folder

        # StringVar for new entry name
        self.add_entry_var = tk.StringVar()

        # A list to hold asset information
        self.assets_data = []

        # Store the active text field info
        self.active_text_widget = None
        self.active_text_label = None
        self.active_preview_image = None
        self.active_asset = None
        self.active_md_key = None

        # -------------------------------
        # Top control frame (now multi-row)
        # -------------------------------
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # --- Row 1: Project name, save, saved projects ---
        row1 = ttk.Frame(control_frame)
        row1.pack(side=tk.TOP, fill=tk.X, pady=2)
        self.project_name_var = tk.StringVar()
        project_name_entry = ttk.Entry(row1, textvariable=self.project_name_var, width=18)
        project_name_entry.pack(side=tk.LEFT, padx=(0, 3))
        project_name_entry.insert(0, "ProjectName")
        save_project_btn = ttk.Button(row1, text="Save Project", command=self.save_current_project_settings)
        save_project_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.saved_projects_frame = ttk.Frame(row1)
        self.saved_projects_frame.pack(side=tk.LEFT, padx=(0, 12))
        self.status_label = ttk.Label(row1, text="", foreground="#80ff80", background="black")
        self.status_label.pack(side=tk.LEFT, padx=(0, 12))
        self.refresh_saved_project_buttons()

        # --- Row 2: Folder input, load, generate ---
        row2 = ttk.Frame(control_frame)
        row2.pack(side=tk.TOP, fill=tk.X, pady=2)
        label_input_folder = ttk.Label(row2, text="Folder:")
        label_input_folder.pack(side=tk.LEFT, padx=3)
        folder_entry = ttk.Entry(row2, textvariable=self.folder_var, width=50)
        folder_entry.pack(side=tk.LEFT, padx=3)
        load_button = ttk.Button(row2, text="Load", command=self.on_load_folder)
        load_button.pack(side=tk.LEFT, padx=3)
        generate_button = ttk.Button(row2, text="Generate MD Files", command=self.on_generate_md_files)
        generate_button.pack(side=tk.LEFT, padx=3)

        # --- Row 3: Add entry, filter, structure ---
        row3 = ttk.Frame(control_frame)
        row3.pack(side=tk.TOP, fill=tk.X, pady=2)
        add_entry_field = ttk.Entry(row3, textvariable=self.add_entry_var, width=20)
        add_entry_field.pack(side=tk.LEFT, padx=(20,3))
        add_entry_field.insert(0, "NewEntryName")
        add_entry_button = ttk.Button(row3, text="ADD entry", command=self.on_add_entry)
        add_entry_button.pack(side=tk.LEFT, padx=3)
        self.show_only_blank_var = tk.BooleanVar(value=False)
        filter_check = ttk.Checkbutton(
            row3,
            text="Show only assets with blank prompts",
            variable=self.show_only_blank_var,
            command=self.refresh_assets_display
        )
        filter_check.pack(side=tk.LEFT, padx=8)
        self.psds_in_root_var = tk.BooleanVar(value=True)
        structure_check = ttk.Checkbutton(
            row3,
            text="PSDs in root folder (vs. in subfolders)",
            variable=self.psds_in_root_var,
            command=self.scan_folder
        )
        structure_check.pack(side=tk.LEFT, padx=8)

        # -------------------------------
        # Header row (non-scrollable)
        # -------------------------------
        header_frame = ttk.Frame(self)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Create labels for each column (smaller widths, tighter spacing)
        # Empty space for image column
        hdr_preview = ttk.Label(header_frame, text="", anchor="center", width=20)
        hdr_preview.grid(row=0, column=0, padx=(5,10))

        # Headers for text fields
        hdr_sdxl_pos = ttk.Label(header_frame, text="SDXL Positive", anchor="center", width=25)
        hdr_sdxl_pos.grid(row=0, column=1, padx=(0,30))

        hdr_sdxl_neg = ttk.Label(header_frame, text="SDXL Negative", anchor="center", width=25)
        hdr_sdxl_neg.grid(row=0, column=2, padx=(0,30))

        hdr_sd15_pos = ttk.Label(header_frame, text="SD15 Positive", anchor="center", width=25)
        hdr_sd15_pos.grid(row=0, column=3, padx=(0,30))

        hdr_sd15_neg = ttk.Label(header_frame, text="SD15 Negative", anchor="center", width=25)
        hdr_sd15_neg.grid(row=0, column=4, padx=(0,30))

        hdr_flux = ttk.Label(header_frame, text="Flux", anchor="center", width=25)
        hdr_flux.grid(row=0, column=5, padx=(0,30))

        hdr_video = ttk.Label(header_frame, text="Video", anchor="center", width=25)
        hdr_video.grid(row=0, column=6, padx=(0,30))

        hdr_florence = ttk.Label(header_frame, text="Florence", anchor="center", width=25)
        hdr_florence.grid(row=0, column=7, padx=(0,30))

        # -------------------------------
        # Main content area with split view
        # -------------------------------
        main_content = ttk.Frame(self)
        main_content.pack(fill=tk.BOTH, expand=True)

        # Left side (scrollable list)
        self.container_frame = ttk.Frame(main_content)
        self.container_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.container_frame, bg="black", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.container_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # This frame (items_frame) goes inside the canvas
        self.items_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.items_frame, anchor="nw")

        self.items_frame.bind("<Configure>", self.on_frame_configure)

        # Right side panel for active text field
        self.right_panel = ttk.Frame(main_content, style="Dark.TFrame")
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=5)

        # --- Refactored: Use a single vertical frame for all right panel widgets ---
        self.right_panel_content = ttk.Frame(self.right_panel)
        self.right_panel_content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Asset name label at very top
        self.active_asset_name_label = ttk.Label(self.right_panel_content, text="", font=("TkDefaultFont", 14, "bold"), foreground="#c0e0ff", background="black")
        self.active_asset_name_label.pack(side=tk.TOP, pady=(5,0))

        # Preview image below asset name
        self.active_preview_label = ttk.Label(self.right_panel_content, text="")
        self.active_preview_label.pack(side=tk.TOP, pady=5)

        # Label for active field
        self.active_field_label = ttk.Label(self.right_panel_content, text="No field selected", font=("TkDefaultFont", 12, "bold"))
        self.active_field_label.pack(side=tk.TOP, pady=5)

        # --- Button frame just below type label ---
        self.right_panel_button_frame = ttk.Frame(self.right_panel_content)
        self.right_panel_button_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        # Copy to... dropdown and button
        self.copy_to_var = tk.StringVar()
        self.copy_to_options = [
            ("SDXL Positive", "sdxl_pos"),
            ("SDXL Negative", "sdxl_neg"),
            ("SD15 Positive", "sd15_pos"),
            ("SD15 Negative", "sd15_neg"),
            ("Flux", "flux"),
            ("Video", "video"),
            ("Florence", "florence"),
        ]
        self.copy_to_menu = ttk.OptionMenu(self.right_panel_button_frame, self.copy_to_var, None, *[label for label, key in self.copy_to_options])
        self.copy_to_menu.pack(side=tk.LEFT, padx=(0, 5))
        self.copy_to_btn = ttk.Button(self.right_panel_button_frame, text="Copy to selected field", command=self.copy_active_text_to_field)
        self.copy_to_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.copy_to_menu.pack_forget()
        self.copy_to_btn.pack_forget()

        # Simplify Prompt button
        self.simplify_btn = ttk.Button(self.right_panel_button_frame, text="Simplify Prompt (Remove Strength)", command=self.simplify_active_prompt)
        self.simplify_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Text widget for active field (expands vertically, now below the buttons)
        self.active_text_area = tk.Text(self.right_panel_content, width=40, height=30, bg="#2d2d2d", fg="white")
        self.active_text_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        self.active_text_area.bind("<KeyRelease>", self.on_active_text_change)

        # Initially hide the right panel
        self.right_panel.pack_forget()


        # -------------------------------
        # Mouse wheel binding
        # -------------------------------
        self.bind_all("<MouseWheel>", self._on_mousewheel, add=True)   # Windows
        self.bind_all("<Button-4>", self._on_mousewheel, add=True)     # Linux
        self.bind_all("<Button-5>", self._on_mousewheel, add=True)     # Linux

        # (Optional) Uncomment these if you want to load on startup:
        # self.scan_folder()
        # self.refresh_assets_display()

    # ------------------------------------------------------------------------
    # Add entry logic
    # ------------------------------------------------------------------------
    def on_add_entry(self):
        """
        Handle the ADD entry button: create new asset folder and stub .psd/.png files, then refresh UI.
        """
        entry_name = self.add_entry_var.get().strip()
        if not entry_name:
            return
        # Only allow safe folder/file names (alphanumeric, dash, underscore)
        if not re.match(r'^[\w\- ]+$', entry_name):
            print("Invalid entry name.")
            return
        base_folder = self.folder_var.get().strip()
        if not base_folder or not os.path.isdir(base_folder):
            print("No valid project folder loaded.")
            return
        psds_in_root = self.psds_in_root_var.get()
        if psds_in_root:
            # TypeA: PSD and PNG in root, subfolder for prompts
            psd_path = os.path.join(base_folder, f"{entry_name}.psd")
            png_path = os.path.join(base_folder, f"{entry_name}.png")
            subfolder_path = os.path.join(base_folder, entry_name)
        else:
            # TypeB: Subfolder, psd and png inside
            subfolder_path = os.path.join(base_folder, entry_name)
            psd_path = os.path.join(subfolder_path, f"{entry_name}.psd")
            png_path = os.path.join(subfolder_path, f"{entry_name}.png")
        # Create subfolder if needed
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
        # Create stub .png as 1024x1024 black image if not exist
        if not os.path.exists(png_path):
            img = Image.new("RGB", (1024, 1024), color="black")
            img.save(png_path, format="PNG")
        # For PSD stub, just copy the PNG (so it's a PNG with .psd extension)
        if not os.path.exists(psd_path):
            shutil.copyfile(png_path, psd_path)
        # Create prompt subfolder and blank .md files
        prompt_folder = os.path.join(subfolder_path, "prompt")
        if not os.path.exists(prompt_folder):
            os.makedirs(prompt_folder)
        md_files = [
            "prompt_sd15.md",
            "prompt_sd15_negative.md",
            "prompt_sdxl.md",
            "prompt_sdxl_negative.md",
            "prompt_flux.md",
            "prompt_video.md",
            "prompt_florence.md"
        ]
        for md_file in md_files:
            md_path = os.path.join(prompt_folder, md_file)
            if not os.path.exists(md_path):
                with open(md_path, 'w', encoding='utf-8') as f:
                    pass
        # Refresh UI
        self.scan_folder()
        self.refresh_assets_display()
        self.add_entry_var.set("")

    # ------------------------------------------------------------------------
    # Saved Projects Logic
    # ------------------------------------------------------------------------
    @property
    def settings_file(self):
        return os.path.join(os.path.dirname(__file__), 'gen_project_prompt_settings.json')

    def save_current_project_settings(self):
        project_name = self.project_name_var.get().strip()
        if not project_name:
            self.show_status("Please enter a project name", error=True)
            return
        # Gather current settings
        settings = {
            'folder': self.folder_var.get().strip(),
            'psds_in_root': self.psds_in_root_var.get(),
            # Add more fields as needed
        }
        # Load or create settings file
        all_settings = {}
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    all_settings = json.load(f)
            except Exception:
                all_settings = {}
        all_settings[project_name] = settings
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(all_settings, f, indent=2)
            self.show_status(f"Settings saved as '{project_name}'", error=False)
            self.refresh_saved_project_buttons()
        except Exception as e:
            self.show_status(f"Error saving settings: {str(e)}", error=True)

    def load_project_settings(self, project_name):
        if not os.path.exists(self.settings_file):
            self.show_status("No saved projects found.", error=True)
            return
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                all_settings = json.load(f)
            if project_name not in all_settings:
                self.show_status(f"Project '{project_name}' not found.", error=True)
                return
            settings = all_settings[project_name]
            # Restore settings
            self.folder_var.set(settings.get('folder', ''))
            self.psds_in_root_var.set(settings.get('psds_in_root', True))
            self.input_folder = settings.get('folder', '')
            # Trigger UI refresh
            self.scan_folder()
            self.refresh_assets_display()
            self.show_status(f"Loaded settings from '{project_name}'", error=False)
        except Exception as e:
            self.show_status(f"Error loading settings: {str(e)}", error=True)

    def refresh_saved_project_buttons(self):
        # Clear old buttons
        for widget in self.saved_projects_frame.winfo_children():
            widget.destroy()
        # Load project names
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    all_settings = json.load(f)
                for pname in all_settings.keys():
                    btn = ttk.Button(self.saved_projects_frame, text=pname, width=14,
                        command=lambda n=pname: self.load_project_settings(n))
                    btn.pack(side=tk.LEFT, padx=2)
            except Exception:
                pass

    def show_status(self, msg, error=False):
        self.status_label.config(text=msg, foreground=("#ff8080" if error else "#80ff80"))
        self.status_label.after(3000, lambda: self.status_label.config(text=""))

    # ------------------------------------------------------------------------
    # Mouse wheel handling
    # ------------------------------------------------------------------------
    def _on_mousewheel(self, event):
        """Scroll the canvas unless the event widget is a Text widget."""
        if event.widget.winfo_class() == 'Text':
            return

        if event.num == 4:  # Linux scroll up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux scroll down
            self.canvas.yview_scroll(1, "units")
        else:
            # Windows or Mac
            direction = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(direction, "units")

    # ------------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------------

    def on_frame_configure(self, event):
        """Reset the scroll region to encompass the inner frame."""
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def on_load_folder(self):
        """Handle the Load button: scan the user-specified folder and refresh the display."""
        folder = self.folder_var.get().strip()
        if not folder:
            return

        if not os.path.isdir(folder):
            print(f"Folder does not exist: {folder}")
            return
        
        self.input_folder = folder
        self.scan_folder()
        self.refresh_assets_display()

    def on_generate_md_files(self):
        """
        Creates blank .md files for each .psd in the currently loaded folder,
        if the subfolder or md files do not already exist. Then rescans and refreshes.
        """
        if not self.input_folder or not os.path.isdir(self.input_folder):
            print("No valid folder loaded. Cannot generate MD files.")
            return
        
        psd_files = [
            f for f in os.listdir(self.input_folder)
            if f.lower().endswith('.psd') and os.path.isfile(os.path.join(self.input_folder, f))
        ]

        for psd_file in psd_files:
            self.create_md_files_for_psd(psd_file, self.input_folder)

        self.scan_folder()
        self.refresh_assets_display()

    def create_md_files_for_psd(self, psd_file, directory):
        """
        Given a PSD file name (e.g., 'item_example.psd'), create subfolder and MD files if missing.
        """
        base_name = os.path.splitext(psd_file)[0]
        subfolder_path = os.path.join(directory, base_name)
        
        # Create the subfolder if it doesn't exist
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
        
        # Create prompt subfolder
        prompt_folder = os.path.join(subfolder_path, "prompt")
        if not os.path.exists(prompt_folder):
            os.makedirs(prompt_folder)
        
        md_files = [
            "prompt_sd15.md",
            "prompt_sd15_negative.md",
            "prompt_sdxl.md",
            "prompt_sdxl_negative.md",
            "prompt_flux.md",
            "prompt_video.md",
            "prompt_florence.md"
        ]
        
        for md_file in md_files:
            md_path = os.path.join(prompt_folder, md_file)
            if not os.path.exists(md_path):
                with open(md_path, 'w', encoding='utf-8') as f:
                    pass  # blank file

    # ------------------------------------------------------------------------
    # Scanning and Displaying
    # ------------------------------------------------------------------------

    def scan_folder(self):
        """Scan the input folder for .psd files and gather relevant data."""
        self.assets_data = []
        
        if not self.input_folder or not os.path.isdir(self.input_folder):
            return

        if self.psds_in_root_var.get():  # TypeA: PSDs/PSBs in root
            asset_files = [f for f in os.listdir(self.input_folder) if f.lower().endswith((".psd", ".psb"))]
            asset_files.sort()

            for asset in asset_files:
                base_name = os.path.splitext(asset)[0]
                asset_path = os.path.join(self.input_folder, asset)
                png_path = os.path.join(self.input_folder, base_name + ".png")
                if not os.path.isfile(png_path):
                    png_path = None

                subfolder_path = os.path.join(self.input_folder, base_name)
                if not os.path.isdir(subfolder_path):
                    continue

                self._add_asset_data(base_name, asset_path, png_path, subfolder_path)

        else:  # TypeB: PSDs/PSBs in subfolders
            subfolders = [f for f in os.listdir(self.input_folder) if os.path.isdir(os.path.join(self.input_folder, f))]
            subfolders.sort()

            for subfolder in subfolders:
                subfolder_path = os.path.join(self.input_folder, subfolder)
                asset_files = [f for f in os.listdir(subfolder_path) if f.lower().endswith((".psd", ".psb"))]
                
                for asset in asset_files:
                    base_name = os.path.splitext(asset)[0]
                    asset_path = os.path.join(subfolder_path, asset)
                    png_path = os.path.join(subfolder_path, base_name + ".png")
                    if not os.path.isfile(png_path):
                        png_path = None

                    self._add_asset_data(base_name, asset_path, png_path, subfolder_path)

        self.refresh_assets_display()

    def _add_asset_data(self, base_name, psd_path, png_path, subfolder_path):
        """Helper method to add asset data to self.assets_data"""
        # Create path to prompt folder
        prompt_folder = os.path.join(subfolder_path, "prompt")
        
        # Identify potential .md files
        prompt_sdxl_path = os.path.join(prompt_folder, "prompt_sdxl.md")
        prompt_sdxl_neg_path = os.path.join(prompt_folder, "prompt_sdxl_negative.md")
        prompt_sd15_path = os.path.join(prompt_folder, "prompt_sd15.md")
        prompt_sd15_neg_path = os.path.join(prompt_folder, "prompt_sd15_negative.md")
        prompt_flux_path = os.path.join(prompt_folder, "prompt_flux.md")
        prompt_video_path = os.path.join(prompt_folder, "prompt_video.md")
        prompt_florence_path = os.path.join(prompt_folder, "prompt_florence.md")

        # Read existing content
        prompt_sdxl_content = ""
        if os.path.isfile(prompt_sdxl_path):
            with open(prompt_sdxl_path, "r", encoding="utf-8") as f:
                prompt_sdxl_content = f.read()
        
        prompt_sdxl_neg_content = ""
        if os.path.isfile(prompt_sdxl_neg_path):
            with open(prompt_sdxl_neg_path, "r", encoding="utf-8") as f:
                prompt_sdxl_neg_content = f.read()

        prompt_sd15_content = ""
        if os.path.isfile(prompt_sd15_path):
            with open(prompt_sd15_path, "r", encoding="utf-8") as f:
                prompt_sd15_content = f.read()
        
        prompt_sd15_neg_content = ""
        if os.path.isfile(prompt_sd15_neg_path):
            with open(prompt_sd15_neg_path, "r", encoding="utf-8") as f:
                prompt_sd15_neg_content = f.read()

        prompt_flux_content = ""
        if os.path.isfile(prompt_flux_path):
            with open(prompt_flux_path, "r", encoding="utf-8") as f:
                prompt_flux_content = f.read()

        prompt_video_content = ""
        if os.path.isfile(prompt_video_path):
            with open(prompt_video_path, "r", encoding="utf-8") as f:
                prompt_video_content = f.read()

        prompt_florence_content = ""
        if os.path.isfile(prompt_florence_path):
            with open(prompt_florence_path, "r", encoding="utf-8") as f:
                prompt_florence_content = f.read()

        self.assets_data.append({
            "base_name": base_name,
            "psd_path": psd_path,
            "png_path": png_path,
            "subfolder_path": subfolder_path,

            # File path references
            "prompt_sdxl_path": prompt_sdxl_path,
            "prompt_sdxl_neg_path": prompt_sdxl_neg_path,
            "prompt_sd15_path": prompt_sd15_path,
            "prompt_sd15_neg_path": prompt_sd15_neg_path,
            "prompt_flux_path": prompt_flux_path,
            "prompt_video_path": prompt_video_path,
            "prompt_florence_path": prompt_florence_path,

            # File content
            "prompt_sdxl_content": prompt_sdxl_content,
            "prompt_sdxl_neg_content": prompt_sdxl_neg_content,
            "prompt_sd15_content": prompt_sd15_content,
            "prompt_sd15_neg_content": prompt_sd15_neg_content,
            "prompt_flux_content": prompt_flux_content,
            "prompt_video_content": prompt_video_content,
            "prompt_florence_content": prompt_florence_content,
        })

    def refresh_assets_display(self):
        """Clear and rebuild the list of assets in the scrollable frame."""
        for child in self.items_frame.winfo_children():
            child.destroy()

        show_only_blank = self.show_only_blank_var.get()

        row_index = 0
        for asset in self.assets_data:
            # If filter is ON, skip if any content is non-empty
            if show_only_blank:
                if (asset["prompt_sdxl_content"].strip() or
                    asset["prompt_sdxl_neg_content"].strip() or
                    asset["prompt_sd15_content"].strip() or
                    asset["prompt_sd15_neg_content"].strip() or
                    asset["prompt_flux_content"].strip() or
                    asset["prompt_video_content"].strip() or
                    asset["prompt_florence_content"].strip()):
                    continue
            
            row_frame = ttk.Frame(self.items_frame)
            row_frame.grid(row=row_index, column=0, sticky="ew", pady=2, padx=5)
            row_index += 1

            # Base name label at top
            base_name_label = ttk.Label(row_frame, text=asset["base_name"], anchor="w", font=("TkDefaultFont", 10, "bold"))
            base_name_label.grid(row=0, column=0, columnspan=8, sticky="w", padx=5, pady=(2,0))

            # Create a frame for the image and content side by side
            content_container = ttk.Frame(row_frame)
            content_container.grid(row=1, column=0, columnspan=8, sticky="ew", pady=2)

            # Thumbnail on the left
            if asset["png_path"] and os.path.isfile(asset["png_path"]):
                try:
                    img = Image.open(asset["png_path"])
                    img.thumbnail((128, 128), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    label_img = ttk.Label(content_container, image=photo)
                    label_img.image = photo  # keep reference
                    label_img.grid(row=0, column=0, padx=(5,10), pady=2, sticky="nw")
                except Exception as e:
                    print(f"Error loading image {asset['png_path']}: {e}")

            # Content frame for text fields to the right of the image
            content_frame = ttk.Frame(content_container)
            content_frame.grid(row=0, column=1, sticky="ew")

            # SDXL Positive prompt - slight green tint
            prompt_text_sdxl = tk.Text(content_frame, width=25, height=6, bg="#2a332a", fg="white")
            prompt_text_sdxl.insert("1.0", asset["prompt_sdxl_content"])
            prompt_text_sdxl.grid(row=0, column=0, sticky="w", padx=0, pady=1)
            prompt_text_sdxl.bind("<KeyRelease>", 
                lambda e, a=asset, tw=prompt_text_sdxl, key="sdxl_pos": 
                    self.on_text_change(a, tw, key)
            )
            prompt_text_sdxl.bind("<FocusIn>",
                lambda e, tw=prompt_text_sdxl, label="SDXL Positive", a=asset, key="sdxl_pos":
                    self.on_text_field_focus(tw, label, a, key)
            )

            # SDXL Negative prompt - slight red tint
            neg_prompt_text_sdxl = tk.Text(content_frame, width=25, height=6, bg="#332a2a", fg="white")
            neg_prompt_text_sdxl.insert("1.0", asset["prompt_sdxl_neg_content"])
            neg_prompt_text_sdxl.grid(row=0, column=1, sticky="w", padx=0, pady=1)
            neg_prompt_text_sdxl.bind("<KeyRelease>",
                lambda e, a=asset, tw=neg_prompt_text_sdxl, key="sdxl_neg":
                    self.on_text_change(a, tw, key)
            )
            neg_prompt_text_sdxl.bind("<FocusIn>",
                lambda e, tw=neg_prompt_text_sdxl, label="SDXL Negative", a=asset, key="sdxl_neg":
                    self.on_text_field_focus(tw, label, a, key)
            )

            # SD15 Positive prompt - slight green tint
            prompt_text_sd15 = tk.Text(content_frame, width=25, height=6, bg="#2a332a", fg="white")
            prompt_text_sd15.insert("1.0", asset["prompt_sd15_content"])
            prompt_text_sd15.grid(row=0, column=2, sticky="w", padx=0, pady=1)
            prompt_text_sd15.bind("<KeyRelease>",
                lambda e, a=asset, tw=prompt_text_sd15, key="sd15_pos":
                    self.on_text_change(a, tw, key)
            )
            prompt_text_sd15.bind("<FocusIn>",
                lambda e, tw=prompt_text_sd15, label="SD15 Positive", a=asset, key="sd15_pos":
                    self.on_text_field_focus(tw, label, a, key)
            )

            # SD15 Negative prompt - slight red tint
            neg_prompt_text_sd15 = tk.Text(content_frame, width=25, height=6, bg="#332a2a", fg="white")
            neg_prompt_text_sd15.insert("1.0", asset["prompt_sd15_neg_content"])
            neg_prompt_text_sd15.grid(row=0, column=3, sticky="w", padx=0, pady=1)
            neg_prompt_text_sd15.bind("<KeyRelease>",
                lambda e, a=asset, tw=neg_prompt_text_sd15, key="sd15_neg":
                    self.on_text_change(a, tw, key)
            )
            neg_prompt_text_sd15.bind("<FocusIn>",
                lambda e, tw=neg_prompt_text_sd15, label="SD15 Negative", a=asset, key="sd15_neg":
                    self.on_text_field_focus(tw, label, a, key)
            )

            # Flux prompt - neutral dark gray
            prompt_text_flux = tk.Text(content_frame, width=25, height=6, bg="#2d2d2d", fg="white")
            prompt_text_flux.insert("1.0", asset["prompt_flux_content"])
            prompt_text_flux.grid(row=0, column=4, sticky="w", padx=0, pady=1)
            prompt_text_flux.bind("<KeyRelease>",
                lambda e, a=asset, tw=prompt_text_flux, key="flux":
                    self.on_text_change(a, tw, key)
            )
            prompt_text_flux.bind("<FocusIn>",
                lambda e, tw=prompt_text_flux, label="Flux", a=asset, key="flux":
                    self.on_text_field_focus(tw, label, a, key)
            )

            # Video prompt - neutral dark gray
            prompt_text_video = tk.Text(content_frame, width=25, height=6, bg="#2d2d2d", fg="white")
            prompt_text_video.insert("1.0", asset["prompt_video_content"])
            prompt_text_video.grid(row=0, column=5, sticky="w", padx=0, pady=1)
            prompt_text_video.bind("<KeyRelease>",
                lambda e, a=asset, tw=prompt_text_video, key="video":
                    self.on_text_change(a, tw, key)
            )
            prompt_text_video.bind("<FocusIn>",
                lambda e, tw=prompt_text_video, label="Video", a=asset, key="video":
                    self.on_text_field_focus(tw, label, a, key)
            )

            # Florence prompt - neutral dark gray
            prompt_text_florence = tk.Text(content_frame, width=25, height=6, bg="#2d2d2d", fg="white")
            prompt_text_florence.insert("1.0", asset["prompt_florence_content"])
            prompt_text_florence.grid(row=0, column=6, sticky="w", padx=0, pady=1)
            prompt_text_florence.bind("<KeyRelease>",
                lambda e, a=asset, tw=prompt_text_florence, key="florence":
                    self.on_text_change(a, tw, key)
            )
            prompt_text_florence.bind("<FocusIn>",
                lambda e, tw=prompt_text_florence, label="Florence", a=asset, key="florence":
                    self.on_text_field_focus(tw, label, a, key)
            )

        self.items_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def on_text_change(self, asset, text_widget, md_key):
        """
        Handle changes in the text widgets and save automatically.
        md_key is one of: 'sdxl_pos', 'sdxl_neg', 'sd15_pos', 'sd15_neg', 'flux', 'video', 'florence'.
        """
        new_content = text_widget.get("1.0", tk.END).rstrip("\n")

        if md_key == "sdxl_pos":
            asset["prompt_sdxl_content"] = new_content
            file_path = asset["prompt_sdxl_path"]
        elif md_key == "sdxl_neg":
            asset["prompt_sdxl_neg_content"] = new_content
            file_path = asset["prompt_sdxl_neg_path"]
        elif md_key == "sd15_pos":
            asset["prompt_sd15_content"] = new_content
            file_path = asset["prompt_sd15_path"]
        elif md_key == "sd15_neg":
            asset["prompt_sd15_neg_content"] = new_content
            file_path = asset["prompt_sd15_neg_path"]
        elif md_key == "flux":
            asset["prompt_flux_content"] = new_content
            file_path = asset["prompt_flux_path"]
        elif md_key == "video":
            asset["prompt_video_content"] = new_content
            file_path = asset["prompt_video_path"]
        elif md_key == "florence":
            asset["prompt_florence_content"] = new_content
            file_path = asset["prompt_florence_path"]

        # Ensure the directory structure exists
        directory = os.path.dirname(file_path)
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

        # Save the prompt content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def on_text_field_focus(self, text_widget, label_text, asset, md_key):
        """Handle when a text field gains focus"""
        # Update active field tracking
        self.active_text_widget = text_widget
        self.active_text_label = label_text
        self.active_asset = asset
        self.active_md_key = md_key

        # Show the right panel
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=5)
        
        # Update the asset name label
        self.active_asset_name_label.config(text=asset.get("base_name", ""))

        # Update the label
        self.active_field_label.config(text=label_text)
        
        # Update the content
        self.active_text_area.delete("1.0", tk.END)
        self.active_text_area.insert("1.0", text_widget.get("1.0", tk.END).rstrip("\n"))

        # Update preview image
        if asset["png_path"] and os.path.isfile(asset["png_path"]):
            try:
                img = Image.open(asset["png_path"])
                img.thumbnail((256, 256), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.active_preview_label.config(image=photo)
                self.active_preview_label.image = photo
            except Exception as e:
                print(f"Error loading preview image: {e}")
                self.active_preview_label.config(image="")
        else:
            self.active_preview_label.config(image="")

        # Update copy-to options (hide current field)
        available = [(label, key) for label, key in self.copy_to_options if key != md_key]
        menu = self.copy_to_menu["menu"]
        menu.delete(0, "end")
        for label, key in available:
            menu.add_command(label=label, command=lambda l=label: self.copy_to_var.set(l))
        if available:
            self.copy_to_var.set(available[0][0])
            self.copy_to_menu.pack(side=tk.LEFT, padx=(0, 5))
            self.copy_to_btn.pack(side=tk.LEFT, padx=(0, 10))
        else:
            self.copy_to_menu.pack_forget()
            self.copy_to_btn.pack_forget()

    def on_active_text_change(self, event):
        """Handle changes in the active text area"""
        if self.active_text_widget and self.active_asset:
            # Update both text widgets
            new_content = self.active_text_area.get("1.0", tk.END).rstrip("\n")
            self.active_text_widget.delete("1.0", tk.END)
            self.active_text_widget.insert("1.0", new_content)
            
            # Save the changes
            self.on_text_change(self.active_asset, self.active_text_widget, self.active_md_key)

    def copy_active_text_to_field(self):
        """Copy the active text area content to the selected prompt field for the same asset.
        When copying from flux to sdxl, remove <lora:...> tags as they are not compatible.
        Also update the UI for the copied-to field if visible."""
        if not self.active_asset or not self.active_md_key:
            return
        # Get selected label and key
        selected_label = self.copy_to_var.get()
        key_map = {label: key for label, key in self.copy_to_options}
        target_key = key_map.get(selected_label)
        if not target_key or target_key == self.active_md_key:
            return
        # Get content to copy
        content = self.active_text_area.get("1.0", tk.END).rstrip("\n")
        # Remove all references to 'lora' when copying, for compatibility
        # Remove <lora:...> tags
        content = re.sub(r"<lora:[^>]+>", "", content, flags=re.IGNORECASE)
        # Do NOT normalize whitespace or strip; preserve all original newlines and spacing
        # Map key to asset field and file path
        field_map = {
            "sdxl_pos": ("prompt_sdxl_content", "prompt_sdxl_path"),
            "sdxl_neg": ("prompt_sdxl_neg_content", "prompt_sdxl_neg_path"),
            "sd15_pos": ("prompt_sd15_content", "prompt_sd15_path"),
            "sd15_neg": ("prompt_sd15_neg_content", "prompt_sd15_neg_path"),
            "flux": ("prompt_flux_content", "prompt_flux_path"),
            "video": ("prompt_video_content", "prompt_video_path"),
            "florence": ("prompt_florence_content", "prompt_florence_path"),
        }
        field_name, file_path_name = field_map[target_key]
        # Update asset data
        self.active_asset[field_name] = content
        file_path = self.active_asset[file_path_name]
        # Save to disk
        directory = os.path.dirname(file_path)
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Update the main table's text widget for the target field if visible
        # Try to find the widget: loop through items_frame children for this asset and key
        if hasattr(self, 'items_frame'):
            for row in self.items_frame.winfo_children():
                # Find the row for this asset
                for child in row.winfo_children():
                    # Find the content_container frame
                    if isinstance(child, ttk.Frame):
                        for content_frame in child.winfo_children():
                            # Find the prompt text widgets
                            if isinstance(content_frame, ttk.Frame):
                                text_widgets = content_frame.winfo_children()
                                key_order = ["sdxl_pos", "sdxl_neg", "sd15_pos", "sd15_neg", "flux", "video", "florence"]
                                for idx, key in enumerate(key_order):
                                    if key == target_key:
                                        try:
                                            # Check if this row is for the active asset
                                            base_name_label = row.winfo_children()[0]
                                            if base_name_label.cget("text") == self.active_asset.get("base_name", ""):
                                                tw = text_widgets[idx]
                                                tw.delete("1.0", tk.END)
                                                tw.insert("1.0", content)
                                        except Exception:
                                            pass
        # If the copied-to field is selected in the right panel, update it as well
        if self.active_md_key == target_key:
            self.active_text_area.delete("1.0", tk.END)
            self.active_text_area.insert("1.0", content)

    def simplify_active_prompt(self):
        """Remove all (word:number) patterns from the currently selected prompt and save."""
        if not self.active_text_area or not self.active_asset or not self.active_md_key:
            return
        content = self.active_text_area.get("1.0", tk.END)
        # Remove patterns like (berry:1.3) or (word:0.9)
        simplified = re.sub(r"\([^\s:()]+:[0-9.]+\)", "", content)
        # Update the UI
        self.active_text_area.delete("1.0", tk.END)
        self.active_text_area.insert("1.0", simplified.strip())
        # Update the main table text widget if visible
        if self.active_text_widget:
            self.active_text_widget.delete("1.0", tk.END)
            self.active_text_widget.insert("1.0", simplified.strip())
        # Save to disk and update asset data
        self.on_active_text_change(None)

def main():
    default_folder = r"/path/to/your/project"
    app = AssetDataEntryUI(default_folder)
    app.mainloop()

if __name__ == "__main__":
    main()