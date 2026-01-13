"""
VIDEO CLIP CROP LOOP
input video , select region , clip timeline range , 
export to gif (low) or webp (high) animated forever 
extra delay for start and end frames 

TODO:
rearrange the UI into better sections 
START to END section  , buttons next to the start(s) to use the current scrubbed frame poistion as the start , another button for setting the end
better display of the current TIME of the scrubbed frame position 
add a "zoom into time range" 
SPACEBAR should play / pause 
add an option to set the frame rate of the output , this OPTIMIZES other timing settings in order to reduce the total frames and the frame rate , dropping extra frames as needed ( for example a 60 frame webp that players over 3 seconds , could be made into a 12fps webp over the same 3 seconds ) 

TIMING SECTION
- target total time , or delay per frame . , then the custom extra delay for the start and end frame .

when editing big video but only cropping a part of it , the processing may be long
we could consider first chopping the big video , then doing framesimilarity etc after 
example a 6gb video took 20 min to crop a small section of a few seconds 

VERSION::20251002
"""
import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageTk

# Supported video extensions
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".webm")

# Default settings
DEFAULT_THRESHOLD = 0.002
DEFAULT_DELAY_MS = 33
DEFAULT_FIRST_DELAY_MS = 0
DEFAULT_LAST_DELAY_MS = 0
DEFAULT_GIF_COLORS = 256
DEFAULT_GIF_OPTIMIZE = False
DEFAULT_GIF_DITHER = False
DEFAULT_WEBP_QUALITY = 95
DEFAULT_WEBP_LOSSLESS = True

class VideoToGifCropper:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Clip to WebP Cropper")

        # --- Dark theme for ttk ---
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            ".",
            background="black",
            foreground="white",
            fieldbackground="black",
            highlightthickness=0,
        )
        style.configure("TFrame", background="black")
        style.configure("TLabel", background="black", foreground="white")
        style.configure("TButton", background="black", foreground="white")
        style.configure("TScale", background="black", troughcolor="#333333")
        style.map(
            "TButton",
            background=[("active", "#444444")],
            foreground=[("active", "white")],
        )

        # Categorized button styles (muted colors)
        style.configure("Green.TButton", background="#335d3a", foreground="white")
        style.map("Green.TButton", background=[("active", "#3e6b45")])
        style.configure("Blue.TButton", background="#2b3f5c", foreground="white")
        style.map("Blue.TButton", background=[("active", "#34506f")])
        style.configure("Purple.TButton", background="#4a2b5c", foreground="white")
        style.map("Purple.TButton", background=[("active", "#57356d")])

        # --- Layout ---
        self.video_frame = ttk.Frame(self.root)
        self.video_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.video_frame, bg="black", highlightthickness=0, cursor="cross")
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        controls = ttk.Frame(self.root)
        controls.pack(side=tk.BOTTOM, fill=tk.X)

        # Timeline
        self.timeline_frame = ttk.Frame(controls)
        self.timeline_frame.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 2))

        self.timeline_scale = ttk.Scale(
            self.timeline_frame,
            orient="horizontal",
            from_=0,
            to=100,
            command=self.on_scrub,
        )
        self.timeline_scale.pack(side=tk.TOP, fill=tk.X)
        self.timeline_scale.bind("<Button-1>", self.on_scrub_start)
        self.timeline_scale.bind("<ButtonRelease-1>", self.on_scrub_end)

        # Timeline overlay canvas (range + playhead)
        self.range_canvas = tk.Canvas(self.timeline_frame, height=18, bg="black", highlightthickness=0)
        self.range_canvas.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))

        # Buttons row 1
        row1 = ttk.Frame(controls)
        row1.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        self.btn_open = ttk.Button(row1, text="Open Video", style="Green.TButton", command=self.open_video)
        self.btn_open.grid(row=0, column=0, padx=4, pady=2)

        self.btn_prev = ttk.Button(row1, text="⏮", width=4, style="Blue.TButton", command=self.prev_frame)
        self.btn_prev.grid(row=0, column=1, padx=4, pady=2)

        self.btn_play = ttk.Button(row1, text="Play", style="Blue.TButton", command=self.toggle_play_pause)
        self.btn_play.grid(row=0, column=2, padx=4, pady=2)

        self.btn_next = ttk.Button(row1, text="⏭", width=4, style="Blue.TButton", command=self.next_frame)
        self.btn_next.grid(row=0, column=3, padx=4, pady=2)

        # Current position display
        ttk.Label(row1, text="Current:").grid(row=0, column=4, padx=(12, 4))
        self.lbl_current_time = ttk.Label(row1, text="0.000s")
        self.lbl_current_time.grid(row=0, column=5, sticky=tk.W)

        # Start/End time controls
        ttk.Label(row1, text="Start:").grid(row=0, column=6, padx=(12, 2))
        self.start_time_var = tk.DoubleVar(value=0.0)
        self.entry_start = ttk.Entry(row1, width=7, textvariable=self.start_time_var)
        self.entry_start.grid(row=0, column=7, sticky=tk.W, padx=2)
        self.btn_set_start = ttk.Button(row1, text="Set START", style="Blue.TButton", command=self.set_start_from_current)
        self.btn_set_start.grid(row=0, column=8, padx=2, pady=2)

        ttk.Label(row1, text="End:").grid(row=0, column=9, padx=(8, 2))
        self.end_time_var = tk.DoubleVar(value=0.0)
        self.entry_end = ttk.Entry(row1, width=7, textvariable=self.end_time_var)
        self.entry_end.grid(row=0, column=10, sticky=tk.W, padx=2)
        self.btn_set_end = ttk.Button(row1, text="Set END", style="Blue.TButton", command=self.set_end_from_current)
        self.btn_set_end.grid(row=0, column=11, padx=2, pady=2)

        ttk.Label(row1, text="Output:").grid(row=0, column=12, padx=(12, 4))
        self.output_type = tk.StringVar(value="WEBP")
        ttk.Radiobutton(row1, text="GIF", value="GIF", variable=self.output_type).grid(row=0, column=13)
        ttk.Radiobutton(row1, text="WebP", value="WEBP", variable=self.output_type).grid(row=0, column=14)

        # Buttons row 2 - similarity + timing
        row2 = ttk.Frame(controls)
        row2.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        ttk.Label(row2, text="Similarity threshold (%):").grid(row=0, column=0, sticky=tk.W)
        # Threshold range [0..100] mapped to [0..1] diff
        # Accept DEFAULT_THRESHOLD as fraction (<=1) or percent (>1)
        _thr_percent_default = (DEFAULT_THRESHOLD * 100.0) if (DEFAULT_THRESHOLD <= 1.0) else float(DEFAULT_THRESHOLD)
        self.sim_thresh = tk.DoubleVar(value=_thr_percent_default)  # percent difference
        self.sim_scale = ttk.Scale(row2, from_=0.0, to=100.0, orient="horizontal", command=self.on_similarity_changed)
        self.sim_scale.set(self.sim_thresh.get())
        self.sim_scale.grid(row=0, column=1, sticky="ew", padx=6)
        row2.columnconfigure(1, weight=1)

        # Precise numeric entry synced with slider
        self.sim_entry = ttk.Entry(row2, width=6)
        self.sim_entry.insert(0, f"{self.sim_thresh.get():.1f}")
        self.sim_entry.grid(row=0, column=2, sticky=tk.W)

        self.lbl_kept = ttk.Label(row2, text="Kept frames: -")
        self.lbl_kept.grid(row=0, column=3, padx=6)

        # Timing settings (OPTIONAL overrides)
        self.use_total_time = tk.BooleanVar(value=False)
        self.chk_total_time = ttk.Checkbutton(row2, text="[OPTIONAL] Target total time (s)", variable=self.use_total_time, command=self.on_timing_mode_changed)
        self.chk_total_time.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))

        self.total_time_var = tk.DoubleVar(value=3.0)
        self.entry_total_time = ttk.Entry(row2, width=8, textvariable=self.total_time_var)
        self.entry_total_time.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6, 0))

        ttk.Label(row2, text="[OPTIONAL] Or delay per frame (ms):").grid(row=1, column=2, sticky=tk.E, pady=(6, 0))
        self.delay_ms_var = tk.IntVar(value=int(DEFAULT_DELAY_MS))
        self.entry_delay = ttk.Entry(row2, width=8, textvariable=self.delay_ms_var)
        self.entry_delay.grid(row=1, column=3, sticky=tk.W, padx=6, pady=(6, 0))

        # Buttons row 3
        row3 = ttk.Frame(controls)
        row3.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0, 6))

        self.btn_analyze = ttk.Button(row3, text="Analyze (count frames)", style="Green.TButton", command=self.analyze_video)
        self.btn_analyze.grid(row=0, column=0, padx=4, pady=2)

        self.btn_export = ttk.Button(row3, text="Export GIF/WebP", style="Purple.TButton", command=self.export_animation)
        self.btn_export.grid(row=0, column=1, padx=4, pady=2)

        # Checkbox for center guide lines
        self.show_center_guides = tk.BooleanVar(value=True)
        self.chk_center_guides = ttk.Checkbutton(row3, text="Show center guides", variable=self.show_center_guides, command=self.on_center_guides_changed)
        self.chk_center_guides.grid(row=0, column=2, padx=(12, 4), pady=2)

        # Row 4 - Note about range
        row4 = ttk.Frame(controls)
        row4.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0, 6))
        ttk.Label(row4, text="Note: Only the Start-End range is analyzed/exported. By default, timing matches original video FPS.").grid(row=0, column=0, sticky=tk.W)

        self.status_label = ttk.Label(controls, text="Open a video to begin.")
        self.status_label.pack(side=tk.LEFT, padx=8, pady=4)

        # State
        self.cap = None
        self.frame_count = 0
        self.fps = 30.0
        self.current_frame_index = 0
        self.is_playing = False
        self.was_playing = False

        # For display scaling
        self.last_frame_bgr = None
        self.display_size = (0, 0)  # (w, h)
        # Aspect-ratio aware render mapping
        self.render_scale = 1.0
        self.render_offset = (0, 0)  # (ox, oy)
        self.render_size = (0, 0)    # (rw, rh)

        # Crop rectangle (original-frame coordinates)
        self.crop_rect = None  # (x0, y0, x1, y1)
        self.drag_start = None  # canvas coords
        self.canvas_rect_id = None
        self.canvas_guide_h_id = None  # horizontal center guide line
        self.canvas_guide_v_id = None  # vertical center guide line

        # Bind canvas mouse for marquee selection
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Bindings: similarity entry + start/end time entries
        self.sim_entry.bind("<Return>", self.on_similarity_entry_commit)
        self.sim_entry.bind("<FocusOut>", self.on_similarity_entry_commit)
        self.entry_start.bind("<Return>", self.on_time_changed)
        self.entry_start.bind("<FocusOut>", self.on_time_changed)
        self.entry_end.bind("<Return>", self.on_time_changed)
        self.entry_end.bind("<FocusOut>", self.on_time_changed)

        # Row 5 - First/Last frame delay overrides (OPTIONAL)
        row5 = ttk.Frame(controls)
        row5.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0, 6))
        ttk.Label(row5, text="[OPTIONAL] First frame extra delay (ms):").grid(row=0, column=0, sticky=tk.W)
        self.first_delay_ms_var = tk.IntVar(value=int(DEFAULT_FIRST_DELAY_MS))
        self.entry_first_delay = ttk.Entry(row5, width=8, textvariable=self.first_delay_ms_var)
        self.entry_first_delay.grid(row=0, column=1, sticky=tk.W, padx=(2, 8))
        ttk.Label(row5, text="[OPTIONAL] Last frame extra delay (ms):").grid(row=0, column=2, sticky=tk.W)
        self.last_delay_ms_var = tk.IntVar(value=int(DEFAULT_LAST_DELAY_MS))
        self.entry_last_delay = ttk.Entry(row5, width=8, textvariable=self.last_delay_ms_var)
        self.entry_last_delay.grid(row=0, column=3, sticky=tk.W, padx=(2, 8))

        # Row 6 - Export quality settings
        row6 = ttk.Frame(controls)
        row6.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0, 8))
        # GIF settings
        ttk.Label(row6, text="GIF colors:" ).grid(row=0, column=0, sticky=tk.W)
        self.gif_colors_var = tk.IntVar(value=int(DEFAULT_GIF_COLORS))
        ttk.Entry(row6, width=6, textvariable=self.gif_colors_var).grid(row=0, column=1, sticky=tk.W, padx=(2, 8))
        self.gif_optimize_var = tk.BooleanVar(value=bool(DEFAULT_GIF_OPTIMIZE))
        ttk.Checkbutton(row6, text="Optimize", variable=self.gif_optimize_var).grid(row=0, column=2, sticky=tk.W, padx=(2, 8))
        self.gif_dither_var = tk.BooleanVar(value=bool(DEFAULT_GIF_DITHER))
        ttk.Checkbutton(row6, text="Dither", variable=self.gif_dither_var).grid(row=0, column=3, sticky=tk.W, padx=(2, 8))
        # WebP settings
        ttk.Label(row6, text="WebP quality:" ).grid(row=0, column=4, sticky=tk.E)
        self.webp_quality_var = tk.IntVar(value=int(DEFAULT_WEBP_QUALITY))
        ttk.Entry(row6, width=6, textvariable=self.webp_quality_var).grid(row=0, column=5, sticky=tk.W, padx=(2, 8))
        self.webp_lossless_var = tk.BooleanVar(value=bool(DEFAULT_WEBP_LOSSLESS))
        ttk.Checkbutton(row6, text="Lossless", variable=self.webp_lossless_var).grid(row=0, column=6, sticky=tk.W)

        # Kick off loop
        self.update_video_loop()

    # ----------------------------- UI Handlers -----------------------------
    def on_scrub(self, value):
        if not self.cap or not self.cap.isOpened():
            return
        frame_num = int(float(value))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        self.current_frame_index = frame_num
        self.show_frame()
        self.update_current_time_label()
        self.draw_range_overlay()

    def on_scrub_start(self, _evt):
        self.was_playing = self.is_playing
        self.is_playing = False
        self.btn_play.config(text="Play")

    def on_scrub_end(self, _evt):
        if self.was_playing:
            self.is_playing = True
            self.btn_play.config(text="Pause")

    def on_similarity_changed(self, _val):
        self.sim_thresh.set(self.sim_scale.get())
        # keep entry in sync
        self.sim_entry.delete(0, tk.END)
        self.sim_entry.insert(0, f"{self.sim_thresh.get():.1f}")
        # Optionally, we could auto-update kept frame count live if cheap enough.
        # We'll keep it manual via Analyze to avoid full reread on each drag.

    def on_similarity_entry_commit(self, _evt):
        try:
            val = float(self.sim_entry.get())
        except Exception:
            val = float(self.sim_thresh.get())
        val = max(0.0, min(100.0, val))
        self.sim_thresh.set(val)
        self.sim_scale.set(val)
        # normalize entry text
        self.sim_entry.delete(0, tk.END)
        self.sim_entry.insert(0, f"{val:.1f}")

    def on_timing_mode_changed(self):
        # No dialog boxes per user preference; use status and prints
        if self.use_total_time.get():
            self.status("Timing mode: target total time.")
        else:
            self.status("Timing mode: fixed delay per frame.")

    def toggle_play_pause(self):
        if not self.cap or not self.cap.isOpened():
            return
        self.is_playing = not self.is_playing
        self.btn_play.config(text="Pause" if self.is_playing else "Play")

    def prev_frame(self):
        if not self.cap:
            return
        idx = max(self.current_frame_index - 1, 0)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        self.current_frame_index = idx
        self.timeline_scale.set(idx)
        self.show_frame()
        self.update_current_time_label()

    def next_frame(self):
        if not self.cap:
            return
        idx = min(self.current_frame_index + 1, max(self.frame_count - 1, 0))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        self.current_frame_index = idx
        self.timeline_scale.set(idx)
        self.show_frame()
        self.update_current_time_label()

    def open_video(self):
        path = filedialog.askopenfilename(title="Select video", filetypes=[("Video", "*.mp4 *.avi *.mov *.mkv *.webm"), ("All", "*.*")])
        if not path:
            return
        if not os.path.exists(path) or not path.lower().endswith(VIDEO_EXTENSIONS):
            self.status("Invalid video file selected.")
            return
        self.load_video(path)

    def release_video(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.last_frame_bgr = None

    # ----------------------------- Canvas crop -----------------------------
    def on_canvas_press(self, event):
        if self.last_frame_bgr is None:
            return
        self.drag_start = (event.x, event.y)
        # Reset existing rect
        if self.canvas_rect_id is not None:
            self.canvas.delete(self.canvas_rect_id)
            self.canvas_rect_id = None

    def on_canvas_drag(self, event):
        if not self.drag_start:
            return
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        if self.canvas_rect_id is None:
            self.canvas_rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline="orange", width=2)
        else:
            self.canvas.coords(self.canvas_rect_id, x0, y0, x1, y1)

    def on_canvas_release(self, event):
        if not self.drag_start:
            return
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        self.drag_start = None
        # Normalize
        x0, x1 = sorted([x0, x1])
        y0, y1 = sorted([y0, y1])
        # Map canvas rect to original frame coordinates
        self.crop_rect = self.canvas_to_frame_rect((x0, y0, x1, y1))
        if self.crop_rect:
            fx0, fy0, fx1, fy1 = self.crop_rect
            self.status(f"Crop set: ({fx0},{fy0})-({fx1},{fy1})")
        else:
            self.status("Crop cleared.")

    def canvas_to_frame_rect(self, rect_canvas):
        if self.last_frame_bgr is None:
            return None
        w_orig = self.last_frame_bgr.shape[1]
        h_orig = self.last_frame_bgr.shape[0]
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        x0, y0, x1, y1 = rect_canvas
        # Clamp to canvas
        x0 = max(0, min(cw, x0))
        x1 = max(0, min(cw, x1))
        y0 = max(0, min(ch, y0))
        y1 = max(0, min(ch, y1))
        if x1 - x0 < 3 or y1 - y0 < 3:
            return None
        # Convert canvas coords to frame coords accounting for letterbox
        ox, oy = self.render_offset
        scale = self.render_scale if self.render_scale != 0 else 1.0
        # Adjust by offset
        ax0 = x0 - ox
        ay0 = y0 - oy
        ax1 = x1 - ox
        ay1 = y1 - oy
        # Clamp to rendered area
        rw, rh = self.render_size
        ax0 = max(0, min(rw, ax0))
        ay0 = max(0, min(rh, ay0))
        ax1 = max(0, min(rw, ax1))
        ay1 = max(0, min(rh, ay1))
        # Map to original frame space
        fx0 = int(round(ax0 / scale))
        fy0 = int(round(ay0 / scale))
        fx1 = int(round(ax1 / scale))
        fy1 = int(round(ay1 / scale))
        # Clamp to frame
        fx0 = max(0, min(w_orig - 1, fx0))
        fy0 = max(0, min(h_orig - 1, fy0))
        fx1 = max(1, min(w_orig, fx1))
        fy1 = max(1, min(h_orig, fy1))
        if fx1 <= fx0 + 1 or fy1 <= fy0 + 1:
            return None
        return (fx0, fy0, fx1, fy1)

    # ----------------------------- Display -----------------------------
    def update_video_loop(self):
        if self.is_playing and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                # Loop
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.current_frame_index = 0
            else:
                self.current_frame_index += 1
                self.show_frame(frame)
            if self.frame_count > 0:
                self.timeline_scale.set(self.current_frame_index)
            self.update_current_time_label()
            self.draw_range_overlay()
        self.root.after(15, self.update_video_loop)

    def show_frame(self, frame=None):
        if frame is None:
            if not self.cap or not self.cap.isOpened():
                return
            ret, frame = self.cap.read()
            if not ret:
                return
        self.last_frame_bgr = frame
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        fw = frame.shape[1]
        fh = frame.shape[0]
        # Compute aspect preserving render size
        scale = min(cw / max(fw, 1), ch / max(fh, 1))
        rw = max(1, int(round(fw * scale)))
        rh = max(1, int(round(fh * scale)))
        ox = (cw - rw) // 2
        oy = (ch - rh) // 2
        self.render_scale = scale
        self.render_offset = (ox, oy)
        self.render_size = (rw, rh)
        # Prepare black canvas and paste scaled frame
        pil_bg = Image.new("RGB", (cw, ch), (0, 0, 0))
        pil_frame = Image.fromarray(frame_rgb).resize((rw, rh), Image.Resampling.LANCZOS)
        pil_bg.paste(pil_frame, (ox, oy))
        imgtk = ImageTk.PhotoImage(image=pil_bg)
        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
        # Re-draw crop outline for feedback
        if self.crop_rect is not None:
            # Map frame rect to canvas coords for display
            fx0, fy0, fx1, fy1 = self.crop_rect
            cx0 = int(round(self.render_offset[0] + fx0 * self.render_scale))
            cy0 = int(round(self.render_offset[1] + fy0 * self.render_scale))
            cx1 = int(round(self.render_offset[0] + fx1 * self.render_scale))
            cy1 = int(round(self.render_offset[1] + fy1 * self.render_scale))
            # Remove previous rect and guides
            if self.canvas_rect_id is not None:
                self.canvas.delete(self.canvas_rect_id)
                self.canvas_rect_id = None
            if self.canvas_guide_h_id is not None:
                self.canvas.delete(self.canvas_guide_h_id)
                self.canvas_guide_h_id = None
            if self.canvas_guide_v_id is not None:
                self.canvas.delete(self.canvas_guide_v_id)
                self.canvas_guide_v_id = None
            
            # Draw crop rectangle
            self.canvas_rect_id = self.canvas.create_rectangle(cx0, cy0, cx1, cy1, outline="orange", width=2)
            
            # Draw center guide lines if enabled
            if self.show_center_guides.get():
                # Calculate center positions
                center_x = (cx0 + cx1) // 2
                center_y = (cy0 + cy1) // 2
                # Draw dashed horizontal center line
                self.canvas_guide_h_id = self.canvas.create_line(
                    cx0, center_y, cx1, center_y,
                    fill="cyan", width=1, dash=(4, 4)
                )
                # Draw dashed vertical center line
                self.canvas_guide_v_id = self.canvas.create_line(
                    center_x, cy0, center_x, cy1,
                    fill="cyan", width=1, dash=(4, 4)
                )

    def on_center_guides_changed(self):
        """Callback when center guides checkbox is toggled."""
        # Refresh the display to show/hide guides
        self.show_frame()

    def update_current_time_label(self):
        """Update the current position time label."""
        if not self.cap or not self.cap.isOpened():
            self.lbl_current_time.config(text="0.000s")
            return
        current_time = self.current_frame_index / self.fps if self.fps > 0 else 0.0
        self.lbl_current_time.config(text=f"{current_time:.3f}s")

    def set_start_from_current(self):
        """Set the start time to the current timeline position."""
        if not self.cap or not self.cap.isOpened():
            return
        current_time = self.current_frame_index / self.fps if self.fps > 0 else 0.0
        self.start_time_var.set(round(current_time, 3))
        self.on_time_changed()
        self.status(f"Start time set to {current_time:.3f}s (frame {self.current_frame_index})")

    def set_end_from_current(self):
        """Set the end time to the current timeline position."""
        if not self.cap or not self.cap.isOpened():
            return
        current_time = self.current_frame_index / self.fps if self.fps > 0 else 0.0
        self.end_time_var.set(round(current_time, 3))
        self.on_time_changed()
        self.status(f"End time set to {current_time:.3f}s (frame {self.current_frame_index})")

    def on_time_changed(self, _evt=None):
        # Clamp and normalize times
        duration = getattr(self, "duration_sec", 0.0)
        try:
            start = float(self.start_time_var.get())
        except Exception:
            start = 0.0
        try:
            end = float(self.end_time_var.get())
        except Exception:
            end = duration
        start = max(0.0, min(duration, start))
        end = max(0.0, min(duration, end))
        if end < start:
            end = start
        self.start_time_var.set(round(start, 3))
        self.end_time_var.set(round(end, 3))
        self.draw_range_overlay()

    def draw_range_overlay(self):
        # Visualize selected time range and playhead
        self.range_canvas.delete("all")
        width = max(self.range_canvas.winfo_width(), 1)
        height = max(self.range_canvas.winfo_height(), 1)
        if self.frame_count <= 0 or self.fps <= 0:
            return
        duration = self.frame_count / self.fps
        try:
            start = float(self.start_time_var.get())
            end = float(self.end_time_var.get())
        except Exception:
            return
        start = max(0.0, min(duration, start))
        end = max(0.0, min(duration, end))
        # Convert to x positions
        x0 = int(round((start / max(duration, 1e-6)) * (width - 1)))
        x1 = int(round((end / max(duration, 1e-6)) * (width - 1)))
        # Draw shaded selection (muted purple)
        if x1 > x0:
            self.range_canvas.create_rectangle(x0, 0, x1, height, fill="#4a2b5c", outline="")
        # Draw playhead line
        cur_t = (self.current_frame_index / self.fps)
        xp = int(round((cur_t / max(duration, 1e-6)) * (width - 1)))
        self.range_canvas.create_line(xp, 0, xp, height, fill="#dddddd")

    # ----------------------------- Analysis & Export -----------------------------
    def _compute_diff(self, img_a, img_b):
        """Compute normalized L1 difference between two images [0..1].
        Downscale + grayscale for speed and stability.
        """
        if img_a is None or img_b is None:
            return 1.0
        # Convert to gray
        a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
        # Downscale to fixed small size
        target = (96, 96)
        a = cv2.resize(a, target, interpolation=cv2.INTER_AREA)
        b = cv2.resize(b, target, interpolation=cv2.INTER_AREA)
        # Normalize to [0,1]
        a = a.astype(np.float32) / 255.0
        b = b.astype(np.float32) / 255.0
        diff = np.abs(a - b).mean()
        return float(diff)

    def analyze_video(self):
        if not self.cap or not self.cap.isOpened():
            self.status("No video open.")
            return
        # Reopen for clean pass
        path = self._current_video_path()
        if not path:
            self.status("Analyze: path unavailable.")
            return
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            self.status("Analyze: cannot re-open video.")
            return
        # Time range to frames
        duration = self.frame_count / self.fps if self.fps > 0 else 0
        start_s = max(0.0, min(duration, float(self.start_time_var.get()))) if duration > 0 else 0.0
        end_s = max(0.0, min(duration, float(self.end_time_var.get()))) if duration > 0 else 0.0
        start_f = int(round(start_s * self.fps))
        end_f = int(round(end_s * self.fps))
        if end_f <= start_f:
            end_f = start_f
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
        kept = 0
        last_kept = None
        thresh = float(self.sim_thresh.get()) / 100.0
        total_all = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total = max(0, end_f - start_f + 1)
        step = max(total // 100, 1) if total > 0 else 1
        idx = 0
        cur_frame = start_f
        while cur_frame <= end_f:
            ret, frame = cap.read()
            if not ret:
                break
            # Crop if set
            crop_frame = self.apply_crop(frame)
            if last_kept is None:
                kept += 1
                last_kept = crop_frame
            else:
                d = self._compute_diff(crop_frame, last_kept)
                if d >= thresh:
                    kept += 1
                    last_kept = crop_frame
            idx += 1
            cur_frame += 1
            if idx % step == 0:
                self.status(f"Analyzing… {idx}/{total} frames (range), kept so far: {kept}")
                self.root.update_idletasks()
        cap.release()
        self.lbl_kept.config(text=f"Kept frames: {kept}")
        self.status(f"Analyze complete. Kept {kept}/{total} frames in range at threshold {self.sim_thresh.get():.1f}%.")

    def apply_crop(self, frame):
        if self.crop_rect is None:
            return frame
        x0, y0, x1, y1 = self.crop_rect
        x0 = max(0, min(frame.shape[1] - 1, x0))
        x1 = max(1, min(frame.shape[1], x1))
        y0 = max(0, min(frame.shape[0] - 1, y0))
        y1 = max(1, min(frame.shape[0], y1))
        if x1 <= x0 + 1 or y1 <= y0 + 1:
            return frame
        return frame[y0:y1, x0:x1]

    def export_animation(self):
        if not self.cap or not self.cap.isOpened():
            self.status("No video open.")
            return
        # Choose path
        initial_ext = ".gif" if self.output_type.get() == "GIF" else ".webp"
        filetypes = [("GIF", "*.gif"), ("WebP", "*.webp"), ("All", "*.*")]
        out_path = filedialog.asksaveasfilename(defaultextension=initial_ext, filetypes=filetypes, title="Save animation as…")
        if not out_path:
            return
        # Ensure extension matches selection
        ext = os.path.splitext(out_path)[1].lower()
        fmt = self.output_type.get()
        if fmt == "GIF" and ext != ".gif":
            out_path += ".gif"
        if fmt == "WEBP" and ext != ".webp":
            out_path += ".webp"

        # Reopen to process
        path = self._current_video_path()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            self.status("Export: cannot re-open video.")
            return

        frames_pil = []
        last_kept = None
        thresh = float(self.sim_thresh.get()) / 100.0

        # Time range to frames
        duration = self.frame_count / self.fps if self.fps > 0 else 0
        start_s = max(0.0, min(duration, float(self.start_time_var.get()))) if duration > 0 else 0.0
        end_s = max(0.0, min(duration, float(self.end_time_var.get()))) if duration > 0 else 0.0
        start_f = int(round(start_s * self.fps))
        end_f = int(round(end_s * self.fps))
        if end_f <= start_f:
            end_f = start_f
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)

        total = max(0, end_f - start_f + 1)
        idx = 0
        cur_frame = start_f
        while cur_frame <= end_f:
            ret, frame = cap.read()
            if not ret:
                break
            crop_frame = self.apply_crop(frame)
            keep = False
            if last_kept is None:
                keep = True
            else:
                d = self._compute_diff(crop_frame, last_kept)
                keep = d >= thresh
            if keep:
                last_kept = crop_frame
                # Convert BGR->RGB and to PIL
                rgb = cv2.cvtColor(crop_frame, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(rgb)
                frames_pil.append(pil)
            idx += 1
            cur_frame += 1
            if idx % 50 == 0:
                self.status(f"Exporting… processed {idx}/{total} frames, kept {len(frames_pil)}")
                self.root.update_idletasks()
        cap.release()

        if not frames_pil:
            self.status("No frames to export (threshold too high?).")
            return

        # Timing
        if self.use_total_time.get():
            total_ms = max(1, int(self.total_time_var.get() * 1000))
            delay_ms = max(1, int(round(total_ms / max(1, len(frames_pil)))))
        else:
            delay_ms = max(1, int(self.delay_ms_var.get()))

        # Per-frame durations with first/last EXTRA delays (added to base delay)
        try:
            first_extra_ms = int(self.first_delay_ms_var.get())
        except Exception:
            first_extra_ms = 0
        try:
            last_extra_ms = int(self.last_delay_ms_var.get())
        except Exception:
            last_extra_ms = 0
        durations = [delay_ms for _ in range(len(frames_pil))]
        if durations:
            durations[0] = max(1, delay_ms + first_extra_ms)
            if len(durations) > 1:
                durations[-1] = max(1, delay_ms + last_extra_ms)

        # Save
        try:
            if self.output_type.get() == "GIF":
                # Apply quantization according to settings
                colors = max(2, min(256, int(self.gif_colors_var.get())))
                dither_flag = Image.FLOYDSTEINBERG if bool(self.gif_dither_var.get()) else Image.NONE
                optimized = bool(self.gif_optimize_var.get())
                frames_q = [frm.convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT, dither=dither_flag) for frm in frames_pil]
                frames_q[0].save(
                    out_path,
                    save_all=True,
                    append_images=frames_q[1:],
                    optimize=optimized,
                    loop=0,  # forever loop
                    duration=durations,
                    disposal=2,
                )
            else:
                # Animated WebP
                quality = max(1, min(100, int(self.webp_quality_var.get())))
                lossless = bool(self.webp_lossless_var.get())
                frames_pil[0].save(
                    out_path,
                    format="WEBP",
                    save_all=True,
                    append_images=frames_pil[1:],
                    loop=0,
                    duration=durations,
                    method=6,
                    lossless=lossless,
                    quality=quality,
                )
            self.status(f"Saved: {out_path} | frames={len(frames_pil)}, base_delay={delay_ms} ms, first={durations[0]} ms, last={durations[-1]} ms")
        except Exception as e:
            self.status(f"Export failed: {e}")

    def _current_video_path(self):
        # OpenCV doesn't store path; we re-query by asking user to re-open path isn't ideal.
        # Instead, keep last path by reading CAP_PROP_FILENAME if available. Not standard.
        # Simpler: store path on load using a shadow attribute.
        return getattr(self, "_video_path", None)

    # Override load_video to store path
    def load_video(self, path):  # type: ignore[override]
        self._video_path = path
        # Call the actual implementation
        self._load_video_impl(path)

    def _load_video_impl(self, path):
        self.release_video()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            self.status(f"Cannot open video: {path}")
            return
        self.cap = cap
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self.current_frame_index = 0
        self.is_playing = False
        self.btn_play.config(text="Play")
        self.timeline_scale.config(to=max(self.frame_count - 1, 0))
        self.timeline_scale.set(0)
        self.crop_rect = None
        self.status(f"Loaded: {os.path.basename(path)} | {self.frame_count} frames @ {self.fps:.2f} fps")
        self.show_frame()
        # Init time range: full duration (ensure UI reflects range upon load)
        self.duration_sec = (self.frame_count / self.fps) if self.fps > 0 else 0.0
        self.start_time_var.set(0.0)
        self.end_time_var.set(round(self.duration_sec, 3))
        # Set default delay to match video FPS for exact timing
        if self.fps > 0:
            default_delay = int(round(1000.0 / self.fps))
            self.delay_ms_var.set(default_delay)
        self.update_current_time_label()
        self.draw_range_overlay()

    def status(self, msg: str):
        print(msg)
        self.status_label.config(text=msg)


def main():
    root = tk.Tk()
    app = VideoToGifCropper(root)
    root.mainloop()


if __name__ == "__main__":
    main()
