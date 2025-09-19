"""
IMAGE and VIDEO COMPOSITOR

Given an input image and a video, this tool composites the video
onto a specific region of the image and outputs an animated looping WebP.
The video's first frame is used as a template, and multi-scale template matching is performed to determine the proper scale and placement. 
It is assumed that the video frame is a cropped (smaller) version of a region in the input image.
The UI is set to dark mode, includes an input for a desired output scale,
checkboxes to enable PingPong looping and auto-crop the video, and options to control
the refinement search range.
The techniques are as follows (with a coarse pass, a separate threaded refinement phase, and optional auto-cropping)
The final animated WebP is saved in the same folder as the input image with a
"_anim" suffix.
"""

import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
import cv2
import numpy as np
import os
import threading

class VideoCompositor:
    def __init__(self):
        self.input_image_cv = None      # Base image (BGR)
        self.input_image_pil = None     # Base image (PIL, RGB)
        self.first_frame_cv = None      # First video frame (BGR)
        self.bounding_box = None        # (x, y, w, h) for the matched region
        self.homography = None          # 3x3 transformation: scale + translation
        self.video_crop_box = None      # Crop rectangle for video frames (if autocrop enabled)
        self.progress_callback = None    # Callback for progress updates
        self.refinement_complete_callback = None  # Callback for refinement completion

    def set_callbacks(self, progress_callback=None, refinement_complete_callback=None):
        self.progress_callback = progress_callback
        self.refinement_complete_callback = refinement_complete_callback

    def load_image(self, image_path):
        if not os.path.isfile(image_path):
            raise ValueError("Invalid image path")
        self.input_image_cv = cv2.imread(image_path)
        if self.input_image_cv is None:
            raise ValueError("Could not load image with OpenCV")
        b, g, r = cv2.split(self.input_image_cv)
        self.input_image_pil = Image.fromarray(cv2.merge((r, g, b)))
        self.bounding_box = None
        self.homography = None
        return self.input_image_pil, self.input_image_cv.shape[:2]

    def auto_crop_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return frame, (0, 0, frame.shape[1], frame.shape[0])
        x, y, w, h = cv2.boundingRect(coords)
        cropped = frame[y:y+h, x:x+w]
        return cropped, (x, y, w, h)

    def find_match(self, video_path, autocrop=True, refine_offset=5, refine_scale=5):
        if self.input_image_cv is None:
            raise ValueError("Please load an image first")
            
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            raise ValueError("Could not read first frame from video")
            
        if autocrop:
            frame, crop_box = self.auto_crop_frame(frame)
            self.video_crop_box = crop_box
        else:
            self.video_crop_box = None
            
        self.first_frame_cv = frame
        gray_template = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_image = cv2.cvtColor(self.input_image_cv, cv2.COLOR_BGR2GRAY)
        
        template_h, template_w = gray_template.shape
        image_h, image_w = gray_image.shape
        max_scale = min(image_w / template_w, image_h / template_h)
        
        # Initial coarse search
        best_score = -1
        best_scale = 1.0
        best_loc = (0, 0)
        
        scales = np.linspace(0.1, max_scale, 20)
        if self.progress_callback:
            self.progress_callback(0)
            
        for idx, scale in enumerate(scales):
            scaled_template = cv2.resize(gray_template, None, fx=scale, fy=scale)
            result = cv2.matchTemplate(gray_image, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > best_score:
                best_score = max_val
                best_scale = scale
                best_loc = max_loc
                
            if self.progress_callback:
                progress = (idx + 1) / len(scales) * 50
                self.progress_callback(progress)
                
        # Start refinement in a separate thread
        threading.Thread(target=self._refine_match,
                       args=(gray_template, gray_image, best_scale, best_loc,
                             float(refine_offset), float(refine_scale))).start()
        
        return best_score, best_loc, best_scale

    def _refine_match(self, template, image, init_scale, init_loc, offset_range, scale_range):
        template_h, template_w = template.shape
        best_score = -1
        best_scale = init_scale
        best_loc = init_loc
        
        scale_min = init_scale * (1 - scale_range/100)
        scale_max = init_scale * (1 + scale_range/100)
        scales = np.linspace(scale_min, scale_max, 10)
        
        x_min = max(0, init_loc[0] - offset_range)
        x_max = min(image.shape[1], init_loc[0] + offset_range)
        y_min = max(0, init_loc[1] - offset_range)
        y_max = min(image.shape[0], init_loc[1] + offset_range)
        
        total_steps = len(scales)
        for idx, scale in enumerate(scales):
            scaled_template = cv2.resize(template, None, fx=scale, fy=scale)
            h, w = scaled_template.shape
            
            # Extract region of interest
            roi = image[int(y_min):int(y_max+h), int(x_min):int(x_max+w)]
            if roi.size == 0:
                continue
                
            result = cv2.matchTemplate(roi, scaled_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > best_score:
                best_score = max_val
                best_scale = scale
                best_loc = (max_loc[0] + x_min, max_loc[1] + y_min)
                
            if self.progress_callback:
                progress = 50 + (idx + 1) / total_steps * 50
                self.progress_callback(progress)
                
        # Calculate final size
        final_size = (int(template_w * best_scale), int(template_h * best_scale))
        
        if self.refinement_complete_callback:
            self.refinement_complete_callback(best_score, best_loc, best_scale, final_size)

    def export_animation(self, video_path, output_path, pingpong=False, output_scale=None):
        if self.homography is None:
            raise ValueError("No homography found. Please run match first.")
        if self.input_image_cv is None:
            raise ValueError("Please load an image first.")
            
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Could not open video file")
            
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25
            
        base_height, base_width = self.input_image_cv.shape[:2]
        base_bgra = cv2.cvtColor(self.input_image_cv, cv2.COLOR_BGR2BGRA)
        base_pil = Image.fromarray(cv2.cvtColor(base_bgra, cv2.COLOR_BGRA2RGBA))
        
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            if self.video_crop_box is not None:
                x, y, w, h = self.video_crop_box
                frame = frame[y:y+h, x:x+w]
                
            warp_frame = cv2.warpPerspective(frame, self.homography, (base_width, base_height),
                                         flags=cv2.INTER_LINEAR,
                                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            
            # Create and warp the mask
            mask_orig = np.ones((frame.shape[0], frame.shape[1]), dtype=np.uint8) * 255
            warp_mask = cv2.warpPerspective(mask_orig, self.homography, (base_width, base_height),
                                        flags=cv2.INTER_LINEAR,
                                        borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            
            # Feather the mask
            warp_mask = cv2.GaussianBlur(warp_mask, (5, 5), 0)
            
            # Convert to RGBA
            warp_frame_rgba = cv2.cvtColor(warp_frame, cv2.COLOR_BGR2RGBA)
            warp_frame_rgba[:, :, 3] = warp_mask
            
            # Create PIL frame
            frame_pil = Image.fromarray(warp_frame_rgba)
            composite = base_pil.copy()
            composite.alpha_composite(frame_pil)
            
            if output_scale:
                target_size = int(output_scale)
                current_max = max(composite.size)
                if current_max > target_size:
                    scale = target_size / current_max
                    new_size = tuple(int(dim * scale) for dim in composite.size)
                    composite = composite.resize(new_size, Image.LANCZOS)
                    
            frames.append(composite)
            
        cap.release()
        
        if pingpong:
            frames.extend(frames[-2:0:-1])
            
        if frames:
            frames[0].save(
                output_path,
                format='WEBP',
                save_all=True,
                append_images=frames[1:],
                duration=int(1000/fps),
                loop=0,
                quality=90
            )
        else:
            raise ValueError("No frames were processed from the video")

class VideoCompositorUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Video-In-Image Compositor")
        self.compositor = VideoCompositor()
        
        # Theme colors
        self.theme = {
            'bg_color': "#2e2e2e",
            'fg_color': "#ffffff",
            'entry_bg': "#424242",
            'button_bg': "#424242",
            'canvas_bg': "#2e2e2e"
        }
        self.master.configure(bg=self.theme['bg_color'])

        # Variables
        self.setup_variables()
        
        # UI Layout
        self.create_ui_elements()
        
        # Set up callbacks
        self.compositor.set_callbacks(
            progress_callback=self.update_progress,
            refinement_complete_callback=self.on_refinement_complete
        )

    def setup_variables(self):
        self.image_path = tk.StringVar()
        self.video_path = tk.StringVar()
        self.output_scale = tk.StringVar()
        self.pingpong = tk.BooleanVar(value=False)
        self.autocrop = tk.BooleanVar(value=True)
        self.refine_offset = tk.StringVar(value="5")
        self.refine_scale = tk.StringVar(value="5")
        self.progress_var = tk.DoubleVar()
        self.preview_image = None

    def create_ui_elements(self):
        # Image Path Row
        self.create_path_row("Image Path:", self.image_path, self.browse_image, 0)
        
        # Video Path Row
        self.create_path_row("Video Path:", self.video_path, self.browse_video, 1)
        
        # Output Scale Row
        self.create_scale_row(2)
        
        # Options Row
        self.create_options_row(3)
        
        # Refinement Options
        self.create_refinement_rows(4, 5)
        
        # Action Buttons
        self.create_action_buttons(6)
        
        # Preview Canvas
        self.create_preview_canvas(7)
        
        # Log Area
        self.create_log_area(8)
        
        # Progress Bar
        self.create_progress_bar(9)

    def create_path_row(self, label_text, variable, browse_command, row):
        tk.Label(self.master, text=label_text, bg=self.theme['bg_color'], 
                fg=self.theme['fg_color']).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(self.master, textvariable=variable, width=40,
                bg=self.theme['entry_bg'], fg=self.theme['fg_color'],
                insertbackground=self.theme['fg_color']).grid(row=row, column=1, padx=5, pady=5)
        tk.Button(self.master, text="Browse", command=browse_command,
                bg=self.theme['button_bg'], fg=self.theme['fg_color'],
                activebackground=self.theme['entry_bg']).grid(row=row, column=2, padx=5, pady=5)

    def create_scale_row(self, row):
        tk.Label(self.master, text="Output Scale (max dimension):", 
                bg=self.theme['bg_color'], fg=self.theme['fg_color']).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(self.master, textvariable=self.output_scale, width=40,
                bg=self.theme['entry_bg'], fg=self.theme['fg_color'],
                insertbackground=self.theme['fg_color']).grid(row=row, column=1, padx=5, pady=5)

    def create_options_row(self, row):
        tk.Checkbutton(self.master, text="Autocrop Video", variable=self.autocrop,
                    onvalue=True, offvalue=False, selectcolor="#00aa00",
                    command=lambda: self.log_message(f"Autocrop Video set to: {self.autocrop.get()}"),
                    bg=self.theme['bg_color'], fg=self.theme['fg_color'],
                    activebackground=self.theme['bg_color']).grid(row=row, column=0, sticky="w", padx=5, pady=5)
        tk.Checkbutton(self.master, text="PingPong Looping", variable=self.pingpong,
                    onvalue=True, offvalue=False, selectcolor="#00aa00",
                    command=lambda: self.log_message(f"PingPong Looping set to: {self.pingpong.get()}"),
                    bg=self.theme['bg_color'], fg=self.theme['fg_color'],
                    activebackground=self.theme['bg_color']).grid(row=row, column=1, sticky="w", padx=5, pady=5)

    def create_refinement_rows(self, offset_row, scale_row):
        # Offset Row
        tk.Label(self.master, text="Refinement Offset (pixels):", 
                bg=self.theme['bg_color'], fg=self.theme['fg_color']).grid(row=offset_row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(self.master, textvariable=self.refine_offset, width=40,
                bg=self.theme['entry_bg'], fg=self.theme['fg_color'],
                insertbackground=self.theme['fg_color']).grid(row=offset_row, column=1, padx=5, pady=5)

        # Scale Row
        tk.Label(self.master, text="Refinement Scale Variation (%) :", 
                bg=self.theme['bg_color'], fg=self.theme['fg_color']).grid(row=scale_row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(self.master, textvariable=self.refine_scale, width=40,
                bg=self.theme['entry_bg'], fg=self.theme['fg_color'],
                insertbackground=self.theme['fg_color']).grid(row=scale_row, column=1, padx=5, pady=5)

    def create_action_buttons(self, row):
        tk.Button(self.master, text="Load Image", command=self.load_image,
                bg=self.theme['button_bg'], fg=self.theme['fg_color'],
                activebackground=self.theme['entry_bg']).grid(row=row, column=0, padx=5, pady=5)
        tk.Button(self.master, text="Find Match & Preview", command=self.find_match_and_preview,
                bg=self.theme['button_bg'], fg=self.theme['fg_color'],
                activebackground=self.theme['entry_bg']).grid(row=row, column=1, padx=5, pady=5)
        tk.Button(self.master, text="Export Animated WebP", command=self.export_animated_webp,
                bg=self.theme['button_bg'], fg=self.theme['fg_color'],
                activebackground=self.theme['entry_bg']).grid(row=row, column=2, padx=5, pady=5)

    def create_preview_canvas(self, row):
        self.preview_canvas = tk.Canvas(self.master, width=500, height=400, bg=self.theme['canvas_bg'])
        self.preview_canvas.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
        self.canvas_image_id = None

    def create_log_area(self, row):
        self.log_text = tk.Text(self.master, width=80, height=10, 
                             bg=self.theme['entry_bg'], fg=self.theme['fg_color'])
        self.log_text.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
        self.log_text.config(state=tk.NORMAL)

    def create_progress_bar(self, row):
        self.progress_bar = ttk.Progressbar(self.master, variable=self.progress_var,
                                        orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
        self.progress_bar.grid_remove()

    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def browse_image(self):
        path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"), ("All Files", "*.*")]
        )
        if path:
            self.image_path.set(path)

    def browse_video(self):
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv"), ("All Files", "*.*")]
        )
        if path:
            self.video_path.set(path)

    def load_image(self):
        try:
            pil_image, (height, width) = self.compositor.load_image(self.image_path.get())
            self.display_preview_image(pil_image)
            default_max = max(width, height)
            self.output_scale.set(str(default_max))
            self.log_message("Image loaded successfully.")
        except ValueError as e:
            self.log_message(f"Error: {str(e)}")

    def display_preview_image(self, pil_img, box=None):
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        img_width, img_height = pil_img.size
        scale = min(canvas_width / img_width, canvas_height / img_height)
        
        if scale < 1:
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            pil_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
        else:
            new_width, new_height = img_width, img_height

        if box is not None:
            draw = ImageDraw.Draw(pil_img)
            x, y, w, h = [int(v * scale) for v in box]
            draw.rectangle([x, y, x + w, y + h], outline="red", width=2)

        self.preview_image = ImageTk.PhotoImage(pil_img)
        if self.canvas_image_id:
            self.preview_canvas.delete(self.canvas_image_id)
        self.canvas_image_id = self.preview_canvas.create_image(
            canvas_width // 2, canvas_height // 2,
            image=self.preview_image, anchor=tk.CENTER
        )

    def find_match_and_preview(self):
        if not self.video_path.get():
            self.log_message("Error: Invalid video path.")
            return
            
        try:
            self.progress_bar.grid()
            best_score, best_loc, best_scale = self.compositor.find_match(
                self.video_path.get(),
                autocrop=self.autocrop.get(),
                refine_offset=float(self.refine_offset.get()),
                refine_scale=float(self.refine_scale.get())
            )
            self.log_message(f"Initial match found. Score = {best_score:.3f}, Scale = {best_scale:.3f}")
        except ValueError as e:
            self.log_message(f"Error: {str(e)}")
            self.progress_bar.grid_remove()

    def export_animated_webp(self):
        try:
            output_path = os.path.splitext(self.image_path.get())[0] + "_anim.webp"
            output_scale = int(self.output_scale.get()) if self.output_scale.get() else None
            
            self.compositor.export_animation(
                self.video_path.get(),
                output_path,
                pingpong=self.pingpong.get(),
                output_scale=output_scale
            )
            
            self.log_message(f"Animation exported to: {output_path}")
        except ValueError as e:
            self.log_message(f"Error: {str(e)}")

    def update_progress(self, value):
        self.progress_var.set(value)
        self.master.update_idletasks()

    def on_refinement_complete(self, refined_score, refined_loc, refined_scale, refined_size):
        self.progress_bar.grid_remove()
        self.log_message(f"Refinement complete. New score = {refined_score:.3f}, Scale = {refined_scale:.3f}")
        
        self.compositor.bounding_box = (refined_loc[0], refined_loc[1], refined_size[0], refined_size[1])
        
        # Create homography matrix
        s = refined_scale
        t_x, t_y = refined_loc
        H = np.array([[s, 0, t_x],
                      [0, s, t_y],
                      [0, 0, 1]], dtype=np.float32)
        self.compositor.homography = H
        
        self.display_preview_image(self.compositor.input_image_pil, box=self.compositor.bounding_box)
        self.log_message("Match found and preview updated.")

def main():
    root = tk.Tk()
    app = VideoCompositorUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
