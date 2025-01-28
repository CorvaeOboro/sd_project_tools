# IMAGE and VIDEO COMPOSITER 
# given an input image and a video , composite the video onto a specific region of the image and output an animated looping webp 
# the videos first frame should match a section of the image , this finds the bounds and decides the position and scale of to composite the video on the image 
# this is designed for use with magic the gathering cards and an animated art video that is a crop of the artwork , the video first frame should match the art section of the image 

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageSequence
import cv2
import os

class VideoCompositorApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Video-In-Image Compositor")

        # ========== Variables ==========
        self.image_path = tk.StringVar()
        self.video_path = tk.StringVar()
        self.output_path = tk.StringVar()

        self.input_image_cv = None   # Will hold the original image in OpenCV format
        self.input_image_pil = None  # Will hold the original image in PIL format
        self.first_frame_cv = None   # First frame of video in CV2 format
        self.bounding_box = None     # (x, y, w, h) match region

        # ========== GUI Layout ==========
        # Image path
        tk.Label(master, text="Image Path:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.image_path, width=40).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(master, text="Browse", command=self.browse_image).grid(row=0, column=2, padx=5, pady=5)

        # Video path
        tk.Label(master, text="Video Path:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.video_path, width=40).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(master, text="Browse", command=self.browse_video).grid(row=1, column=2, padx=5, pady=5)

        # Output path
        tk.Label(master, text="Output (Animated WebP):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(master, textvariable=self.output_path, width=40).grid(row=2, column=1, padx=5, pady=5)
        tk.Button(master, text="Browse", command=self.browse_output).grid(row=2, column=2, padx=5, pady=5)

        # Action buttons
        tk.Button(master, text="Load Image", command=self.load_image).grid(row=3, column=0, padx=5, pady=5)
        tk.Button(master, text="Find Match & Preview", command=self.find_match_and_preview).grid(row=3, column=1, padx=5, pady=5)
        tk.Button(master, text="Export Animated WebP", command=self.export_animated_webp).grid(row=3, column=2, padx=5, pady=5)

        # Preview canvas
        self.preview_canvas = tk.Canvas(master, width=500, height=400, bg="grey")
        self.preview_canvas.grid(row=4, column=0, columnspan=3, padx=5, pady=5)

        # Keep track of the displayed image ID in the canvas
        self.canvas_image_id = None

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

    def browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Save Animated WebP",
            defaultextension=".webp",
            filetypes=[("WebP Image", "*.webp"), ("All Files", "*.*")]
        )
        if path:
            self.output_path.set(path)

    # --- Loading and Preview ---
    def load_image(self):
        """
        Loads the user-selected image into memory (both as OpenCV and PIL),
        then updates the preview canvas.
        """
        img_path = self.image_path.get()
        if not os.path.isfile(img_path):
            messagebox.showerror("Error", "Invalid image path.")
            return

        # Load with OpenCV (BGR)
        self.input_image_cv = cv2.imread(img_path)
        if self.input_image_cv is None:
            messagebox.showerror("Error", "Could not load image with OpenCV.")
            return
        
        # Convert to PIL
        b, g, r = cv2.split(self.input_image_cv)
        self.input_image_pil = Image.fromarray(cv2.merge((r, g, b)))  # Convert BGR to RGB

        # Reset bounding box
        self.bounding_box = None

        # Display on canvas
        self.display_preview_image(self.input_image_pil)

    def display_preview_image(self, pil_img, box=None):
        """
        Displays a PIL image on the preview canvas. Optionally draws a bounding
        box in red if `box` is provided as (x, y, w, h).
        """
        # Resize image to fit the canvas if necessary, but keep aspect ratio
        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()

        img_width, img_height = pil_img.size
        scale = min(canvas_width / img_width, canvas_height / img_height)

        if scale < 1:
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            pil_img = pil_img.resize((new_width, new_height), Image.ANTIALIAS)
        else:
            new_width = img_width
            new_height = img_height

        # If there's a bounding box, we draw it on a copy of the image
        if box is not None:
            x, y, w, h = box
            # We need to scale these coordinates to match the displayed image
            display_scale = new_width / self.input_image_pil.width
            draw_x = int(x * display_scale)
            draw_y = int(y * display_scale)
            draw_w = int(w * display_scale)
            draw_h = int(h * display_scale)

            img_draw = pil_img.copy()
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img_draw)
            draw.rectangle([draw_x, draw_y, draw_x+draw_w, draw_y+draw_h],
                           outline="red", width=3)
            pil_img = img_draw

        # Convert to ImageTk
        tk_img = ImageTk.PhotoImage(pil_img)

        # Clear the canvas
        self.preview_canvas.delete("all")

        # Center the image
        x_pos = (canvas_width - new_width) // 2
        y_pos = (canvas_height - new_height) // 2

        self.canvas_image_id = self.preview_canvas.create_image(x_pos, y_pos, anchor=tk.NW, image=tk_img)
        # Keep a reference to avoid garbage collection
        self.preview_canvas.image = tk_img

    def find_match_and_preview(self):
        """
        Extracts first frame from video, does template matching in input image,
        finds best match bounding box, stores it, and updates preview.
        """
        video_path = self.video_path.get()
        if not os.path.isfile(video_path):
            messagebox.showerror("Error", "Invalid video path.")
            return
        if self.input_image_cv is None:
            messagebox.showerror("Error", "Please load an image first.")
            return

        # Open video, grab the first frame
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            messagebox.showerror("Error", "Could not read first frame from video.")
            return

        self.first_frame_cv = frame

        # Convert to grayscale for matching
        gray_image = cv2.cvtColor(self.input_image_cv, cv2.COLOR_BGR2GRAY)
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Template matching
        result = cv2.matchTemplate(gray_image, gray_frame, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # The bounding box in the input image
        h, w = gray_frame.shape
        top_left = max_loc
        self.bounding_box = (top_left[0], top_left[1], w, h)

        # Update preview
        self.display_preview_image(self.input_image_pil, box=self.bounding_box)
        messagebox.showinfo("Match Found", f"Best match value: {max_val:.3f}")

    def export_animated_webp(self):
        """
        Reads frames from the video, composites them into the bounding box of
        the original image, and saves an animated WebP.
        """
        if self.bounding_box is None:
            messagebox.showerror("Error", "No bounding box found. Please run match first.")
            return

        out_path = self.output_path.get()
        if not out_path:
            messagebox.showerror("Error", "Please specify an output path.")
            return

        video_path = self.video_path.get()
        if not os.path.isfile(video_path):
            messagebox.showerror("Error", "Invalid video path.")
            return
        if self.input_image_pil is None:
            messagebox.showerror("Error", "Please load an image first.")
            return

        x, y, w, h = self.bounding_box
        # Convert original image to RGBA (to handle blending easily)
        base_image_rgba = self.input_image_pil.convert("RGBA")

        # Prepare an array to store each composited frame (as PIL images)
        frames = []

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25  # fallback if FPS is not properly obtained

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # Convert frame to PIL
            b, g, r = cv2.split(frame)
            frame_pil = Image.fromarray(cv2.merge((r, g, b)), mode="RGB")

            # Resize frame_pil to match bounding box
            frame_pil = frame_pil.resize((w, h), Image.ANTIALIAS)

            # Composite this frame into a copy of the base image
            composite = base_image_rgba.copy()
            composite.paste(frame_pil, (x, y))

            frames.append(composite)

        cap.release()

        if not frames:
            messagebox.showerror("Error", "No frames were read from the video.")
            return

        # Export frames as animated WebP, looping infinitely
        # Using duration = 1000/fps (in ms) as an approximation
        duration_ms = int(1000 / fps) if fps > 0 else 100

        # frames[0] as base, append rest
        # Pillow requires save_all=True and append_images to create an animated WebP
        # loop=0 means infinite
        first_frame = frames[0]
        if len(frames) == 1:
            # Only one frame? Just save a single image
            first_frame.save(out_path, format="WEBP", loop=0)
        else:
            first_frame.save(
                out_path,
                format="WEBP",
                save_all=True,
                append_images=frames[1:],
                duration=duration_ms,
                loop=0
            )

        messagebox.showinfo("Success", f"Exported animated WebP to: {out_path}")

def main():
    root = tk.Tk()
    app = VideoCompositorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
