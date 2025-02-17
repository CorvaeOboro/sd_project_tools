"""
IMAGE and VIDEO COMPOSITOR

Given an input image and a video, this tool composites the video
onto a specific region of the image and outputs an animated looping WebP.
The video’s first frame is used as a template, and multi-scale template matching
(with a coarse pass, a separate threaded refinement phase, and optional auto-cropping)
is performed to determine the proper scale and placement. It is assumed that the video
frame is a cropped (smaller) version of a region in the input image.
The UI is set to dark mode, includes an input for a desired output scale,
checkboxes to enable PingPong looping and auto-crop the video, and two options
to control the refinement search range.
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

class VideoCompositorApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Video-In-Image Compositor")
        
        # Dark mode colors
        self.bg_color = "#2e2e2e"
        self.fg_color = "#ffffff"
        self.entry_bg = "#424242"
        self.button_bg = "#424242"
        self.canvas_bg = "#2e2e2e"
        self.master.configure(bg=self.bg_color)

        # ========== Variables ==========
        self.image_path = tk.StringVar()
        self.video_path = tk.StringVar()
        self.output_scale = tk.StringVar()  # Desired max dimension for output image
        self.pingpong = tk.BooleanVar(value=False)    # PingPong looping option
        self.autocrop = tk.BooleanVar(value=True)       # Auto-crop video (default ON)
        # Refinement options:
        self.refine_offset = tk.StringVar(value="5")      # Maximum pixel offset (default 5)
        self.refine_scale = tk.StringVar(value="5")       # Maximum scale variation (%) (default 5%)

        self.input_image_cv = None      # Base image (BGR)
        self.input_image_pil = None     # Base image (PIL, RGB)
        self.first_frame_cv = None      # First video frame (BGR)
        self.bounding_box = None        # (x, y, w, h) for the matched region
        self.homography = None          # 3x3 transformation: scale + translation
        self.video_crop_box = None      # Crop rectangle for video frames (if autocrop enabled)

        # ========== GUI Layout ==========
        # Row 0: Image path
        tk.Label(master, text="Image Path:", bg=self.bg_color, fg=self.fg_color).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.image_path, width=40,
                 bg=self.entry_bg, fg=self.fg_color, insertbackground=self.fg_color).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(master, text="Browse", command=self.browse_image,
                  bg=self.button_bg, fg=self.fg_color, activebackground=self.entry_bg).grid(row=0, column=2, padx=5, pady=5)

        # Row 1: Video path
        tk.Label(master, text="Video Path:", bg=self.bg_color, fg=self.fg_color).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.video_path, width=40,
                 bg=self.entry_bg, fg=self.fg_color, insertbackground=self.fg_color).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(master, text="Browse", command=self.browse_video,
                  bg=self.button_bg, fg=self.fg_color, activebackground=self.entry_bg).grid(row=1, column=2, padx=5, pady=5)

        # Row 2: Output Scale input
        tk.Label(master, text="Output Scale (max dimension):", bg=self.bg_color, fg=self.fg_color).grid(row=2, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.output_scale, width=40,
                 bg=self.entry_bg, fg=self.fg_color, insertbackground=self.fg_color).grid(row=2, column=1, padx=5, pady=5)

        # Row 3: Options (Autocrop and PingPong) with selectcolor for visual feedback
        tk.Checkbutton(master, text="Autocrop Video", variable=self.autocrop,
                       onvalue=True, offvalue=False, selectcolor="#00aa00",
                       command=lambda: self.log_message(f"Autocrop Video set to: {self.autocrop.get()}"),
                       bg=self.bg_color, fg=self.fg_color, activebackground=self.bg_color).grid(row=3, column=0, sticky="w", padx=5, pady=5)
        tk.Checkbutton(master, text="PingPong Looping", variable=self.pingpong,
                       onvalue=True, offvalue=False, selectcolor="#00aa00",
                       command=lambda: self.log_message(f"PingPong Looping set to: {self.pingpong.get()}"),
                       bg=self.bg_color, fg=self.fg_color, activebackground=self.bg_color).grid(row=3, column=1, sticky="w", padx=5, pady=5)

        # Row 4: Refinement Offset option
        tk.Label(master, text="Refinement Offset (pixels):", bg=self.bg_color, fg=self.fg_color).grid(row=4, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.refine_offset, width=40,
                 bg=self.entry_bg, fg=self.fg_color, insertbackground=self.fg_color).grid(row=4, column=1, padx=5, pady=5)

        # Row 5: Refinement Scale Variation option
        tk.Label(master, text="Refinement Scale Variation (%) :", bg=self.bg_color, fg=self.fg_color).grid(row=5, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.refine_scale, width=40,
                 bg=self.entry_bg, fg=self.fg_color, insertbackground=self.fg_color).grid(row=5, column=1, padx=5, pady=5)

        # Row 6: Action buttons
        tk.Button(master, text="Load Image", command=self.load_image,
                  bg=self.button_bg, fg=self.fg_color, activebackground=self.entry_bg).grid(row=6, column=0, padx=5, pady=5)
        tk.Button(master, text="Find Match & Preview", command=self.find_match_and_preview,
                  bg=self.button_bg, fg=self.fg_color, activebackground=self.entry_bg).grid(row=6, column=1, padx=5, pady=5)
        tk.Button(master, text="Export Animated WebP", command=self.export_animated_webp,
                  bg=self.button_bg, fg=self.fg_color, activebackground=self.entry_bg).grid(row=6, column=2, padx=5, pady=5)

        # Row 7: Preview canvas
        self.preview_canvas = tk.Canvas(master, width=500, height=400, bg=self.canvas_bg)
        self.preview_canvas.grid(row=7, column=0, columnspan=3, padx=5, pady=5)
        self.canvas_image_id = None

        # Row 8: Log text area
        self.log_text = tk.Text(master, width=80, height=10, bg=self.entry_bg, fg=self.fg_color)
        self.log_text.grid(row=8, column=0, columnspan=3, padx=5, pady=5)
        self.log_text.config(state=tk.NORMAL)

        # Row 9: Progress Bar (hidden initially)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(master, variable=self.progress_var,
                                            orient="horizontal", mode="determinate")
        self.progress_bar.grid(row=9, column=0, columnspan=3, padx=5, pady=5)
        self.progress_bar.grid_remove()

    # --- Logging helper ---
    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    # --- Auto-cropping function ---
    def auto_crop_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return frame, (0, 0, frame.shape[1], frame.shape[0])
        x, y, w, h = cv2.boundingRect(coords)
        cropped = frame[y:y+h, x:x+w]
        return cropped, (x, y, w, h)

    # --- File Browsers ---
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

    # --- Loading and Preview ---
    def load_image(self):
        img_path = self.image_path.get()
        if not os.path.isfile(img_path):
            self.log_message("Error: Invalid image path.")
            return

        self.input_image_cv = cv2.imread(img_path)
        if self.input_image_cv is None:
            self.log_message("Error: Could not load image with OpenCV.")
            return

        b, g, r = cv2.split(self.input_image_cv)
        self.input_image_pil = Image.fromarray(cv2.merge((r, g, b)))
        self.bounding_box = None
        self.homography = None

        self.display_preview_image(self.input_image_pil)
        h, w = self.input_image_cv.shape[:2]
        default_max = max(w, h)
        self.output_scale.set(str(default_max))
        self.log_message("Image loaded successfully.")

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
            x, y, w_box, h_box = box
            display_scale = new_width / self.input_image_pil.width
            box_coords = (
                int(x * display_scale),
                int(y * display_scale),
                int((x + w_box) * display_scale),
                int((y + h_box) * display_scale)
            )
            img_draw = pil_img.copy()
            draw = ImageDraw.Draw(img_draw)
            draw.rectangle(box_coords, outline="red", width=3)
            pil_img = img_draw

        tk_img = ImageTk.PhotoImage(pil_img)
        self.preview_canvas.delete("all")
        x_pos = (canvas_width - new_width) // 2
        y_pos = (canvas_height - new_height) // 2
        self.canvas_image_id = self.preview_canvas.create_image(x_pos, y_pos, anchor=tk.NW, image=tk_img)
        self.preview_canvas.image = tk_img

    def find_match_and_preview(self):
        video_path = self.video_path.get()
        if not os.path.isfile(video_path):
            self.log_message("Error: Invalid video path.")
            return
        if self.input_image_cv is None:
            self.log_message("Error: Please load an image first.")
            return

        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            self.log_message("Error: Could not read first frame from video.")
            return

        if self.autocrop.get():
            frame, crop_box = self.auto_crop_frame(frame)
            self.video_crop_box = crop_box
            self.log_message(f"Autocrop enabled. Crop box: {crop_box}")
        else:
            self.video_crop_box = None

        self.first_frame_cv = frame
        gray_template = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_image = cv2.cvtColor(self.input_image_cv, cv2.COLOR_BGR2GRAY)
        template_h, template_w = gray_template.shape
        image_h, image_w = gray_image.shape

        # Coarse matching phase
        max_scale = min(image_w / template_w, image_h / template_h)
        lower_bound = 1.0
        upper_bound = max_scale
        best_score = -1
        best_scale = None
        best_loc = None
        best_size = None

        for scale in np.linspace(lower_bound, upper_bound, num=20):
            new_w = int(template_w * scale)
            new_h = int(template_h * scale)
            if new_w < 1 or new_h < 1 or new_w > image_w or new_h > image_h:
                continue
            resized_template = cv2.resize(gray_template, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            result = cv2.matchTemplate(gray_image, resized_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc_candidate = cv2.minMaxLoc(result)
            if max_val > best_score:
                best_score = max_val
                best_scale = scale
                best_loc = max_loc_candidate
                best_size = (new_w, new_h)

        self.log_message(f"Coarse Match: Score = {best_score:.3f}, Scale = {best_scale:.3f}")

        # Start refinement phase in a separate thread
        total_iterations = (2 * int(self.refine_offset.get()) + 1) ** 2 * 5
        self.progress_bar['maximum'] = total_iterations
        self.progress_var.set(0)
        self.progress_bar.grid()
        threading.Thread(target=self.run_refinement_phase,
                         args=(best_score, best_loc, best_scale, best_size, template_w, template_h, image_w, image_h, gray_template, gray_image),
                         daemon=True).start()

    def run_refinement_phase(self, best_score, best_loc, best_scale, best_size, template_w, template_h, image_w, image_h, gray_template, gray_image):
        try:
            offset_val = int(self.refine_offset.get())
        except ValueError:
            offset_val = 5
        try:
            scale_variation = float(self.refine_scale.get()) / 100.0
        except ValueError:
            scale_variation = 0.05

        offset_range = np.linspace(-offset_val, offset_val, num=(2 * offset_val) + 1)
        scale_factors = np.linspace(1 - scale_variation, 1 + scale_variation, num=5)

        refined_score = best_score
        refined_loc = best_loc
        refined_scale = best_scale
        refined_size = best_size
        total_iterations = len(offset_range) * len(offset_range) * len(scale_factors)
        current_iteration = 0

        for dx in offset_range:
            for dy in offset_range:
                for factor in scale_factors:
                    candidate_scale = best_scale * factor
                    candidate_x = int(best_loc[0] + dx)
                    candidate_y = int(best_loc[1] + dy)
                    candidate_w = int(template_w * candidate_scale)
                    candidate_h = int(template_h * candidate_scale)
                    if candidate_x < 0 or candidate_y < 0 or candidate_x + candidate_w > image_w or candidate_y + candidate_h > image_h:
                        current_iteration += 1
                        if current_iteration % 10 == 0:
                            self.master.after(0, lambda it=current_iteration: self.progress_var.set(it))
                        continue

                    roi = gray_image[candidate_y:candidate_y+candidate_h, candidate_x:candidate_x+candidate_w]
                    candidate_template = cv2.resize(gray_template, (candidate_w, candidate_h), interpolation=cv2.INTER_CUBIC)
                    score = cv2.matchTemplate(roi, candidate_template, cv2.TM_CCOEFF_NORMED)[0, 0]
                    if score > refined_score:
                        refined_score = score
                        refined_loc = (candidate_x, candidate_y)
                        refined_scale = candidate_scale
                        refined_size = (candidate_w, candidate_h)
                    current_iteration += 1
                    if current_iteration % 10 == 0:
                        self.master.after(0, lambda it=current_iteration: self.progress_var.set(it))
        self.master.after(0, self.on_refinement_complete, refined_score, refined_loc, refined_scale, refined_size)

    def on_refinement_complete(self, refined_score, refined_loc, refined_scale, refined_size):
        self.progress_bar.grid_remove()
        self.log_message(f"Refinement complete. New score = {refined_score:.3f}, Scale = {refined_scale:.3f}")
        self.bounding_box = (refined_loc[0], refined_loc[1], refined_size[0], refined_size[1])
        s = refined_scale
        t_x, t_y = refined_loc
        H = np.array([[s, 0, t_x],
                      [0, s, t_y],
                      [0, 0, 1]], dtype=np.float32)
        self.homography = H
        self.display_preview_image(self.input_image_pil, box=self.bounding_box)
        self.log_message("Match found and preview updated.")

    def export_animated_webp(self):
        if self.homography is None:
            self.log_message("Error: No homography found. Please run match first.")
            return
        if self.input_image_cv is None:
            self.log_message("Error: Please load an image first.")
            return

        video_path = self.video_path.get()
        if not os.path.isfile(video_path):
            self.log_message("Error: Invalid video path.")
            return

        input_img_path = self.image_path.get()
        base_name, _ = os.path.splitext(os.path.basename(input_img_path))
        output_dir = os.path.dirname(input_img_path)
        out_path = os.path.join(output_dir, base_name + "_anim.webp")

        cap = cv2.VideoCapture(video_path)
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
            if self.autocrop.get() and self.video_crop_box is not None:
                x, y, w, h = self.video_crop_box
                frame = frame[y:y+h, x:x+w]
            warp_frame = cv2.warpPerspective(frame, self.homography, (base_width, base_height),
                                             flags=cv2.INTER_LINEAR,
                                             borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            mask_orig = np.ones((frame.shape[0], frame.shape[1]), dtype=np.uint8) * 255
            warp_mask = cv2.warpPerspective(mask_orig, self.homography, (base_width, base_height),
                                            flags=cv2.INTER_LINEAR,
                                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            warp_frame_bgra = cv2.cvtColor(warp_frame, cv2.COLOR_BGR2BGRA)
            warp_frame_bgra[:, :, 3] = warp_mask

            warp_pil = Image.fromarray(cv2.cvtColor(warp_frame_bgra, cv2.COLOR_BGRA2RGBA))
            composite = Image.alpha_composite(base_pil, warp_pil)
            frames.append(composite)

        cap.release()
        if not frames:
            self.log_message("Error: No frames were read from the video.")
            return

        try:
            desired_max = int(self.output_scale.get())
        except ValueError:
            self.log_message("Error: Invalid output scale value.")
            return

        resized_frames = []
        for frame in frames:
            orig_w, orig_h = frame.size
            factor = desired_max / max(orig_w, orig_h)
            new_size = (int(orig_w * factor), int(orig_h * factor))
            resized_frames.append(frame.resize(new_size, Image.LANCZOS))

        if self.pingpong.get() and len(resized_frames) > 1:
            pingpong_frames = resized_frames + resized_frames[-2::-1]
        else:
            pingpong_frames = resized_frames

        duration_ms = int(1000 / fps)
        first_frame = pingpong_frames[0]
        if len(pingpong_frames) == 1:
            first_frame.save(out_path, format="WEBP", loop=0)
        else:
            first_frame.save(
                out_path,
                format="WEBP",
                save_all=True,
                append_images=pingpong_frames[1:],
                duration=duration_ms,
                loop=0
            )

        self.log_message(f"Export successful. Output saved to:\n{out_path}")

def main():
    root = tk.Tk()
    app = VideoCompositorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
