import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class AssetDashboard(tk.Tk):
    def __init__(self, default_folder=""):
        super().__init__()
        self.title("Asset Dashboard")
        self.geometry("1400x800")  # widened for extra columns

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

        # A list to hold asset information
        self.assets_data = []

        # -------------------------------
        # Top control frame
        # -------------------------------
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # Label + text entry for folder input
        label_input_folder = ttk.Label(control_frame, text="Folder:")
        label_input_folder.pack(side=tk.LEFT, padx=3)

        folder_entry = ttk.Entry(control_frame, textvariable=self.folder_var, width=50)
        folder_entry.pack(side=tk.LEFT, padx=3)

        # Button to load/scan the folder
        load_button = ttk.Button(control_frame, text="Load", command=self.on_load_folder)
        load_button.pack(side=tk.LEFT, padx=3)

        # Button to generate MD files
        generate_button = ttk.Button(
            control_frame, text="Generate MD Files", command=self.on_generate_md_files
        )
        generate_button.pack(side=tk.LEFT, padx=3)

        # Checkbox to filter only assets with blank .md
        self.show_only_blank_var = tk.BooleanVar(value=False)
        filter_check = ttk.Checkbutton(
            control_frame,
            text="Show only assets with blank prompts",
            variable=self.show_only_blank_var,
            command=self.refresh_assets_display
        )
        filter_check.pack(side=tk.LEFT, padx=8)

        # -------------------------------
        # Header row (non-scrollable)
        # -------------------------------
        header_frame = ttk.Frame(self)
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Create labels for each column (smaller widths, tighter spacing)
        hdr_preview = ttk.Label(header_frame, text="Preview", anchor="center", width=10)
        hdr_preview.grid(row=0, column=0, padx=3)

        hdr_filename = ttk.Label(header_frame, text="Filename", anchor="center", width=14)
        hdr_filename.grid(row=0, column=1, padx=3)

        hdr_sdxl_pos = ttk.Label(header_frame, text="SDXL Pos", anchor="center", width=16)
        hdr_sdxl_pos.grid(row=0, column=2, padx=3)

        hdr_sdxl_neg = ttk.Label(header_frame, text="SDXL Neg", anchor="center", width=16)
        hdr_sdxl_neg.grid(row=0, column=3, padx=3)

        hdr_sd15_pos = ttk.Label(header_frame, text="SD15 Pos", anchor="center", width=16)
        hdr_sd15_pos.grid(row=0, column=4, padx=3)

        hdr_sd15_neg = ttk.Label(header_frame, text="SD15 Neg", anchor="center", width=16)
        hdr_sd15_neg.grid(row=0, column=5, padx=3)

        hdr_flux = ttk.Label(header_frame, text="Flux", anchor="center", width=16)
        hdr_flux.grid(row=0, column=6, padx=3)

        # -------------------------------
        # Scrollable area
        # -------------------------------
        self.container_frame = ttk.Frame(self)
        self.container_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.container_frame, bg="black", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = ttk.Scrollbar(self.container_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # This frame (items_frame) goes inside the canvas
        self.items_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.items_frame, anchor="nw")

        self.items_frame.bind("<Configure>", self.on_frame_configure)

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
        Given a PSD file name (e.g., 'example.psd'), create subfolder and MD files if missing.
        """
        base_name = os.path.splitext(psd_file)[0]
        folder_path = os.path.join(directory, base_name)
        
        # Create the directory if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        md_files = [
            "prompt_sd15.md",
            "prompt_sd15_negative.md",
            "prompt_sdxl.md",
            "prompt_sdxl_negative.md",
            "prompt_flux.md"
        ]
        
        for md_file in md_files:
            md_path = os.path.join(folder_path, md_file)
            if not os.path.exists(md_path):
                with open(md_path, 'w', encoding='utf-8') as f:
                    pass  # blank file

    # ------------------------------------------------------------------------
    # Scanning and Displaying
    # ------------------------------------------------------------------------

    def scan_folder(self):
        """Scan the input folder for .psd files and gather relevant data."""
        self.assets_data.clear()
        if not os.path.isdir(self.input_folder):
            return

        psd_files = [f for f in os.listdir(self.input_folder) if f.lower().endswith(".psd")]
        psd_files.sort()

        for psd in psd_files:
            base_name = os.path.splitext(psd)[0]
            psd_path = os.path.join(self.input_folder, psd)
            png_path = os.path.join(self.input_folder, base_name + ".png")
            if not os.path.isfile(png_path):
                png_path = None

            subfolder_path = os.path.join(self.input_folder, base_name)
            if not os.path.isdir(subfolder_path):
                continue

            # Identify potential .md files
            prompt_sdxl_path = os.path.join(subfolder_path, "prompt_sdxl.md")
            prompt_sdxl_neg_path = os.path.join(subfolder_path, "prompt_sdxl_negative.md")
            prompt_sd15_path = os.path.join(subfolder_path, "prompt_sd15.md")
            prompt_sd15_neg_path = os.path.join(subfolder_path, "prompt_sd15_negative.md")
            prompt_flux_path = os.path.join(subfolder_path, "prompt_flux.md")

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

                # File content
                "prompt_sdxl_content": prompt_sdxl_content,
                "prompt_sdxl_neg_content": prompt_sdxl_neg_content,
                "prompt_sd15_content": prompt_sd15_content,
                "prompt_sd15_neg_content": prompt_sd15_neg_content,
                "prompt_flux_content": prompt_flux_content,
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
                    asset["prompt_flux_content"].strip()):
                    continue
            
            row_frame = ttk.Frame(self.items_frame)
            row_frame.grid(row=row_index, column=0, sticky="ew", pady=3, padx=3)
            row_index += 1

            # Thumbnail
            if asset["png_path"] and os.path.isfile(asset["png_path"]):
                try:
                    img = Image.open(asset["png_path"])
                    img.thumbnail((128, 128), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    label_img = ttk.Label(row_frame, image=photo)
                    label_img.image = photo  # keep reference
                    label_img.grid(row=0, column=0, rowspan=2, padx=3, pady=3)
                except Exception as e:
                    print(f"Error loading image {asset['png_path']}: {e}")

            # PSD filename
            label_filename = ttk.Label(row_frame, text=asset["base_name"])
            label_filename.grid(row=0, column=1, sticky="w", padx=3)

            # SDXL Positive prompt
            prompt_text_sdxl = tk.Text(row_frame, width=25, height=6, bg="#3c3c3c", fg="white")
            prompt_text_sdxl.insert("1.0", asset["prompt_sdxl_content"])
            prompt_text_sdxl.grid(row=1, column=1, sticky="w", padx=3, pady=3)
            prompt_text_sdxl.bind("<KeyRelease>", 
                lambda e, a=asset, tw=prompt_text_sdxl, key="sdxl_pos": 
                    self.on_text_change(a, tw, key)
            )

            # SDXL Negative prompt
            neg_prompt_text_sdxl = tk.Text(row_frame, width=25, height=6, bg="#3c3c3c", fg="white")
            neg_prompt_text_sdxl.insert("1.0", asset["prompt_sdxl_neg_content"])
            neg_prompt_text_sdxl.grid(row=1, column=2, sticky="w", padx=3, pady=3)
            neg_prompt_text_sdxl.bind("<KeyRelease>",
                lambda e, a=asset, tw=neg_prompt_text_sdxl, key="sdxl_neg":
                    self.on_text_change(a, tw, key)
            )

            # SD15 Positive prompt
            prompt_text_sd15 = tk.Text(row_frame, width=25, height=6, bg="#3c3c3c", fg="white")
            prompt_text_sd15.insert("1.0", asset["prompt_sd15_content"])
            prompt_text_sd15.grid(row=1, column=3, sticky="w", padx=3, pady=3)
            prompt_text_sd15.bind("<KeyRelease>",
                lambda e, a=asset, tw=prompt_text_sd15, key="sd15_pos":
                    self.on_text_change(a, tw, key)
            )

            # SD15 Negative prompt
            neg_prompt_text_sd15 = tk.Text(row_frame, width=25, height=6, bg="#3c3c3c", fg="white")
            neg_prompt_text_sd15.insert("1.0", asset["prompt_sd15_neg_content"])
            neg_prompt_text_sd15.grid(row=1, column=4, sticky="w", padx=3, pady=3)
            neg_prompt_text_sd15.bind("<KeyRelease>",
                lambda e, a=asset, tw=neg_prompt_text_sd15, key="sd15_neg":
                    self.on_text_change(a, tw, key)
            )

            # Flux prompt
            prompt_text_flux = tk.Text(row_frame, width=25, height=6, bg="#3c3c3c", fg="white")
            prompt_text_flux.insert("1.0", asset["prompt_flux_content"])
            prompt_text_flux.grid(row=1, column=5, sticky="w", padx=3, pady=3)
            prompt_text_flux.bind("<KeyRelease>",
                lambda e, a=asset, tw=prompt_text_flux, key="flux":
                    self.on_text_change(a, tw, key)
            )

        self.items_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def on_text_change(self, asset, text_widget, md_key):
        """
        Handle changes in the text widgets and save automatically.
        md_key is one of: 'sdxl_pos', 'sdxl_neg', 'sd15_pos', 'sd15_neg', 'flux'.
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
        else:  # "flux"
            asset["prompt_flux_content"] = new_content
            file_path = asset["prompt_flux_path"]

        directory = os.path.dirname(file_path)
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)


def main():
    default_folder = r"/path/to/your/assets"
    app = AssetDashboard(default_folder)
    app.mainloop()

if __name__ == "__main__":
    main()
