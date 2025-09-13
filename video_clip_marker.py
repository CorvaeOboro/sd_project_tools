import os
import json
import cv2
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from PIL import Image, ImageTk
import subprocess
import shutil

# Constants
CLIP_FRAME_COUNT = 73  # Default number of frames for each extracted clip (used for initial assumptions)
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv')  # Extend as needed

class VideoReviewClipGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Review - Set Marker - Export Clip Generator ")

        # --- Create and configure  ttk widgets ---
        style = ttk.Style(self.root)
        style.theme_use('clam')  # or another theme that supports overrides

        # General style for :
        style.configure(
            ".",
            background="black",
            foreground="white",
            fieldbackground="black",
            highlightthickness=0
        )
        style.configure("TFrame",
            background="black"
        )
        style.configure("TLabel",
            background="black",
            foreground="white"
        )
        style.configure("TButton",
            background="black",
            foreground="white"
        )
        style.configure("TScale",
            background="black",
            troughcolor="#333333"
        )
        style.map("TButton",
                  background=[("active", "#444444")],
                  foreground=[("active", "white")])

        # Main frames
        self.video_frame = ttk.Frame(self.root)
        self.video_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Canvas for the video display
        self.canvas = tk.Canvas(self.video_frame, bg="black", highlightthickness=0)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Controls frame at bottom
        self.controls_frame = ttk.Frame(self.root)
        self.controls_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Timeline frame
        self.timeline_frame = ttk.Frame(self.controls_frame)
        self.timeline_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # A horizontal Scale for scrubbing
        self.timeline_scale = ttk.Scale(
            self.timeline_frame, 
            orient="horizontal", 
            from_=0, 
            to=100,
            command=self.on_scrub  # called for every move
        )
        self.timeline_scale.pack(side=tk.TOP, fill=tk.X)

        # Detect when user *starts* and *stops* scrubbing
        self.timeline_scale.bind("<Button-1>", self.on_scrub_start)  
        self.timeline_scale.bind("<ButtonRelease-1>", self.on_scrub_end)

        # A small canvas for marker lines and highlight regions
        self.marker_canvas = tk.Canvas(self.timeline_frame, height=20, bg="black", highlightthickness=0)
        self.marker_canvas.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))

        # Buttons frame
        self.button_frame = ttk.Frame(self.controls_frame)
        self.button_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Button: Select folder
        self.select_folder_btn = ttk.Button(self.button_frame, text="Select Folder",
                                            command=self.select_folder)
        self.select_folder_btn.grid(row=0, column=0, padx=5, pady=5)

        # Button: Previous video
        self.prev_btn = ttk.Button(self.button_frame, text="Previous",
                                   command=self.prev_video)
        self.prev_btn.grid(row=0, column=1, padx=5, pady=5)

        # Button: Play/Pause toggle
        self.play_pause_btn = ttk.Button(self.button_frame, text="Play",
                                         command=self.toggle_play_pause)
        self.play_pause_btn.grid(row=0, column=2, padx=5, pady=5)

        # Button: Next video
        self.next_btn = ttk.Button(self.button_frame, text="Next",
                                   command=self.next_video)
        self.next_btn.grid(row=0, column=3, padx=5, pady=5)

        # Button: Add marker
        self.marker_btn = ttk.Button(self.button_frame, text="Add Marker (Hotkey: M)",
                                     command=self.add_marker)
        self.marker_btn.grid(row=0, column=4, padx=5, pady=5)

        # Button: Export clips
        self.export_btn = ttk.Button(self.button_frame, text="Export Clips",
                                     command=self.export_clips)
        self.export_btn.grid(row=0, column=5, padx=5, pady=5)

        # Settings frame (clip range, audio export, playback speed)
        self.settings_frame = ttk.Frame(self.controls_frame)
        self.settings_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Clip pre/post seconds
        ttk.Label(self.settings_frame, text="Clip pre (s):").grid(row=0, column=0, sticky=tk.E, padx=(0,4))
        self.pre_seconds_var = tk.DoubleVar(value=0.0)
        self.pre_entry = ttk.Entry(self.settings_frame, textvariable=self.pre_seconds_var, width=6)
        self.pre_entry.grid(row=0, column=1, sticky=tk.W, padx=(0,10))

        ttk.Label(self.settings_frame, text="Clip post (s):").grid(row=0, column=2, sticky=tk.E, padx=(0,4))
        # Default post seconds based on CLIP_FRAME_COUNT and an assumed 30 fps until actual fps is known
        self.post_seconds_var = tk.DoubleVar(value=max(1.0, CLIP_FRAME_COUNT / 30.0))
        self.post_entry = ttk.Entry(self.settings_frame, textvariable=self.post_seconds_var, width=6)
        self.post_entry.grid(row=0, column=3, sticky=tk.W, padx=(0,10))

        # Include audio checkbox
        self.include_audio_var = tk.BooleanVar(value=False)
        self.include_audio_chk = ttk.Checkbutton(self.settings_frame, text="Include audio in export", variable=self.include_audio_var)
        self.include_audio_chk.grid(row=0, column=4, sticky=tk.W, padx=(0,10))

        # Playback speed control
        ttk.Label(self.settings_frame, text="Playback speed:").grid(row=0, column=5, sticky=tk.E, padx=(0,4))
        self.playback_speed_var = tk.DoubleVar(value=1.0)
        self.playback_speed_scale = ttk.Scale(
            self.settings_frame,
            from_=0.25,
            to=3.0,
            orient="horizontal",
            command=self.on_speed_change,
            value=1.0
        )
        self.playback_speed_scale.grid(row=0, column=6, sticky=tk.EW)
        self.settings_frame.columnconfigure(6, weight=1)
        self.speed_label = ttk.Label(self.settings_frame, text="1.00x")
        self.speed_label.grid(row=0, column=7, sticky=tk.W, padx=(6,0))

        # Status Label
        self.status_label = ttk.Label(self.controls_frame, text="No folder selected.")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Video/marker tracking
        self.video_files = []
        self.current_video_index = 0
        self.cap = None
        self.frame_count = 0
        self.current_frame_index = 0
        self.is_playing = False
        self.was_playing = False  # track old state during scrubs
        self.fps = 30.0
        self.markers = []

        # Bind hotkey for adding a marker
        self.root.bind('<m>', lambda event: self.add_marker())

        # Keep updating frames
        self.update_video()

        # Redraw markers on resize
        self.marker_canvas.bind("<Configure>", lambda e: self.draw_timeline_markers())

    # --------------------------------------------------------------------------
    # Video/File Management
    # --------------------------------------------------------------------------
    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            # Gather all valid videos in the folder
            self.video_files = [
                os.path.join(folder_selected, f)
                for f in os.listdir(folder_selected)
                if f.lower().endswith(VIDEO_EXTENSIONS)
            ]
            self.video_files.sort()

            if not self.video_files:
                self.status_label.config(text="No video files found in the folder.")
                return

            self.current_video_index = 0
            self.load_video(self.video_files[self.current_video_index])

    def load_video(self, video_path):
        """Load a new video, release old capture, read marker data, reset timeline."""
        self.release_video()
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            self.status_label.config(text=f"Cannot open video: {video_path}")
            return

        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.current_frame_index = 0
        self.is_playing = False
        self.play_pause_btn.config(text="Play")

        # Adjust default post seconds to match actual fps when first loading a video, if user hasn't changed it
        try:
            if hasattr(self, 'post_seconds_var') and self.post_seconds_var.get() == max(1.0, CLIP_FRAME_COUNT / 30.0):
                self.post_seconds_var.set(max(1.0, CLIP_FRAME_COUNT / max(self.fps, 1e-6)))
        except Exception:
            pass

        # Load markers
        self.load_markers_from_json(video_path)

        filename = os.path.basename(video_path)
        self.status_label.config(text=f"Loaded: {filename}")

        self.timeline_scale.config(to=max(self.frame_count - 1, 0))
        self.timeline_scale.set(0)
        self.draw_timeline_markers()

    def release_video(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.cap = None
        self.is_playing = False

    def prev_video(self):
        if not self.video_files:
            return
        self.current_video_index = (self.current_video_index - 1) % len(self.video_files)
        self.load_video(self.video_files[self.current_video_index])

    def next_video(self):
        if not self.video_files:
            return
        self.current_video_index = (self.current_video_index + 1) % len(self.video_files)
        self.load_video(self.video_files[self.current_video_index])

    # --------------------------------------------------------------------------
    # Play/Pause and Scrubbing
    # --------------------------------------------------------------------------
    def toggle_play_pause(self):
        """Toggle between playing and paused states."""
        if self.is_playing:
            # Currently playing -> pause
            self.is_playing = False
            self.play_pause_btn.config(text="Play")
        else:
            # Currently paused -> play
            self.is_playing = True
            self.play_pause_btn.config(text="Pause")

    def on_scrub(self, value):
        """
        Called continuously as the user moves the scale.
        We just set the frame in the capture to the new position,
        then display that single frame (paused).
        """
        if not self.cap or not self.cap.isOpened():
            return
        frame_num = int(float(value))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        self.current_frame_index = frame_num
        self.display_frame()

    def on_scrub_start(self, event):
        """User clicked on the scale: remember if we were playing, then pause."""
        self.was_playing = self.is_playing
        self.is_playing = False
        self.play_pause_btn.config(text="Play")

    def on_scrub_end(self, event):
        """User released the mouse on the scale: restore playing state if was playing."""
        if self.was_playing:
            self.is_playing = True
            self.play_pause_btn.config(text="Pause")

    # --------------------------------------------------------------------------
    # Marker Management
    # --------------------------------------------------------------------------
    def load_markers_from_json(self, video_path):
        """Load markers from <basename>_marker.json if it exists."""
        self.markers = []
        json_path = self.get_marker_json_path(video_path)
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                self.markers = data.get('markers', [])
                self.markers.sort()
                print(f"Loaded markers: {self.markers} from {json_path}")
            except Exception as e:
                print(f"Error loading markers: {e}")
        else:
            print(f"No markers found for {video_path}. Starting empty.")
        self.draw_timeline_markers()

    def save_markers_to_json(self, video_path):
        """Save markers to <basename>_marker.json."""
        json_path = self.get_marker_json_path(video_path)
        data = {'markers': self.markers}
        try:
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved markers to {json_path}: {self.markers}")
        except Exception as e:
            print(f"Error saving markers: {e}")

    def get_marker_json_path(self, video_path):
        """Generate a path to store marker data (e.g., MyVideo_marker.json)."""
        folder = os.path.dirname(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        return os.path.join(folder, f"{base_name}_marker.json")

    def add_marker(self):
        """Add a marker at the current frame. Immediately save to JSON."""
        if not self.cap or not self.cap.isOpened():
            return
        frame_idx = self.current_frame_index
        if frame_idx not in self.markers:
            self.markers.append(frame_idx)
            self.markers.sort()
            print(f"Marker added at frame {frame_idx}")
            video_path = self.video_files[self.current_video_index]
            self.save_markers_to_json(video_path)
            self.draw_timeline_markers()

    # --------------------------------------------------------------------------
    # Marker Visualization
    # --------------------------------------------------------------------------
    def draw_timeline_markers(self):
        """Draw markers and a highlight region around each marker based on pre/post seconds."""
        self.marker_canvas.delete("all")
        if self.frame_count <= 0:
            return

        width = self.marker_canvas.winfo_width()
        height = self.marker_canvas.winfo_height()

        # Compute highlight length based on pre/post seconds settings
        pre_s = max(0.0, float(self.pre_seconds_var.get()) if hasattr(self, 'pre_seconds_var') else 0.0)
        post_s = max(0.0, float(self.post_seconds_var.get()) if hasattr(self, 'post_seconds_var') else (CLIP_FRAME_COUNT / max(self.fps, 1e-6)))
        pre_frames = int(round(pre_s * max(self.fps, 1e-6)))
        post_frames = int(round(post_s * max(self.fps, 1e-6)))

        for m in self.markers:
            # Marker x position (red vertical line)
            x_marker = int((m / (self.frame_count - 1)) * width) if self.frame_count > 1 else 0

            # Highlight region from (marker - pre) to (marker + post)
            m_start = max(m - pre_frames, 0)
            m_end = min(m + post_frames, self.frame_count - 1)
            x_start = int((m_start / (self.frame_count - 1)) * width) if self.frame_count > 1 else 0
            x_end  = int((m_end / (self.frame_count - 1)) * width) if self.frame_count > 1 else 0

            # Draw the highlight rectangle first (e.g. orange stipple)
            if x_end > x_start:
                self.marker_canvas.create_rectangle(
                    x_start, 0, x_end, height,
                    fill="orange",
                    stipple="gray50",  # pseudo-transparency
                    outline=""
                )

            # Draw the red marker line on top
            self.marker_canvas.create_line(
                x_marker, 0, x_marker, height,
                fill="red", width=2
            )

    # --------------------------------------------------------------------------
    # Clip Export
    # --------------------------------------------------------------------------
    def export_clips(self):
        """Export clips for each marker using configured pre/post seconds and optional audio."""
        if not self.video_files:
            return
        video_path = self.video_files[self.current_video_index]
        if not os.path.exists(video_path):
            print("Video file does not exist for exporting clips.")
            return

        # Save current markers
        self.save_markers_to_json(video_path)

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_folder = os.path.dirname(video_path)

        # Reopen for exporting
        cap_export = cv2.VideoCapture(video_path)
        if not cap_export.isOpened():
            print("Could not open video for exporting clips.")
            return

        fps = cap_export.get(cv2.CAP_PROP_FPS) or self.fps
        width = int(cap_export.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap_export.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Compute pre/post frames from settings
        pre_s = max(0.0, float(self.pre_seconds_var.get()))
        post_s = max(0.0, float(self.post_seconds_var.get()))
        pre_frames = int(round(pre_s * max(fps, 1e-6)))
        post_frames = int(round(post_s * max(fps, 1e-6)))

        for i, marker_frame in enumerate(self.markers):
            clip_name = f"{base_name}_marker{i}.mp4"
            clip_path = os.path.join(output_folder, clip_name)

            # Determine start and end frames based on pre/post settings
            start_frame = max(marker_frame - pre_frames, 0)
            end_frame = min(marker_frame + post_frames, self.frame_count - 1)

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(clip_path, fourcc, fps, (width, height))

            cap_export.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            frames_written = 0
            total_to_write = (end_frame - start_frame) + 1
            while frames_written < total_to_write:
                ret, frame = cap_export.read()
                if not ret:
                    break
                out.write(frame)
                frames_written += 1

            out.release()
            print(f"Exported clip (video): {clip_path} | frames {start_frame}-{end_frame}")

            # If requested, attempt to include audio using ffmpeg
            if self.include_audio_var.get():
                self._mux_audio_segment(video_path, clip_path, start_frame, end_frame, fps)

        cap_export.release()
        print("All clips exported.")

    # --------------------------------------------------------------------------
    # Video Looping and Display
    # --------------------------------------------------------------------------
    def update_video(self):
        """Called repeatedly to update frames if video is playing."""
        if self.is_playing and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                # Loop back to start
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.current_frame_index = 0
            else:
                self.current_frame_index += 1
                self.display_frame(frame)

            # Sync scale position (if not scrubbing)
            if self.frame_count > 0:
                self.timeline_scale.set(self.current_frame_index)

        # Schedule next update based on playback speed and fps
        self.root.after(self.get_update_delay_ms(), self.update_video)

    def on_speed_change(self, value):
        """Callback when playback speed slider moves."""
        try:
            speed = float(value)
        except Exception:
            speed = 1.0
        speed = max(0.25, min(3.0, speed))
        self.playback_speed_var.set(speed)
        self.speed_label.config(text=f"{speed:0.2f}x")

    def get_update_delay_ms(self):
        """Compute the delay in ms between frames based on fps and playback speed."""
        fps = self.fps if self.fps and self.fps > 0 else 30.0
        speed = self.playback_speed_var.get() if hasattr(self, 'playback_speed_var') else 1.0
        effective_fps = max(1e-3, fps * max(0.25, min(3.0, speed)))
        delay = int(max(1, round(1000.0 / effective_fps)))
        return delay

    def _mux_audio_segment(self, source_video, clip_video_path, start_frame, end_frame, fps):
        """
        Use ffmpeg (if available) to mux the corresponding audio segment from the source
        into the clip video. If ffmpeg is not found, print a message and skip.
        """
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            print("ffmpeg not found in PATH. Skipping audio muxing for:", clip_video_path)
            return

        start_time = max(0.0, float(start_frame) / max(fps, 1e-6))
        # end frame is inclusive, add one frame for end timestamp
        end_time = float(end_frame + 1) / max(fps, 1e-6)

        temp_audio = clip_video_path.replace('.mp4', '.__temp_audio.m4a')
        temp_muxed = clip_video_path.replace('.mp4', '.__temp_muxed.mp4')

        # Extract audio segment from source
        extract_cmd = [
            ffmpeg_path,
            '-y',
            '-ss', f"{start_time:.6f}",
            '-to', f"{end_time:.6f}",
            '-i', source_video,
            '-vn',
            '-acodec', 'copy',
            temp_audio
        ]

        # Mux with the video clip
        mux_cmd = [
            ffmpeg_path,
            '-y',
            '-i', clip_video_path,
            '-i', temp_audio,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            temp_muxed
        ]

        try:
            subprocess.run(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            subprocess.run(mux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            # Replace original clip with muxed version
            os.replace(temp_muxed, clip_video_path)
            if os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass
            print(f"Added audio to clip: {clip_video_path}")
        except subprocess.CalledProcessError as e:
            print(f"ffmpeg error during audio muxing: {e}")
            # Cleanup temp files if exist
            for p in (temp_audio, temp_muxed):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    def display_frame(self, frame=None):
        """
        Display a single frame on the canvas, scaled to fit the canvas size.
        If frame is None, read from cap at the current frame position.
        """
        if frame is None:
            if not self.cap or not self.cap.isOpened():
                return
            ret, frame = self.cap.read()
            if not ret:
                return

        # Convert to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # --- Scale the frame to fit the current canvas size ---
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w > 0 and canvas_h > 0:
            # Use Pillow to resize
            pil_img = Image.fromarray(frame_rgb)
            pil_img = pil_img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        else:
            # If canvas not ready or zero, just use the original
            pil_img = Image.fromarray(frame_rgb)

        # Convert to ImageTk
        imgtk = ImageTk.PhotoImage(image=pil_img)
        self.canvas.imgtk = imgtk  # keep reference
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)

def main():
    root = tk.Tk()
    app = VideoReviewClipGenerator(root)
    root.mainloop()

if __name__ == "__main__":
    main()
