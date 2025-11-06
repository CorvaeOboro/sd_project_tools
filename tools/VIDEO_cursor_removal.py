"""
VIDEO cursor removal 

a generalized cursor remover for videos 
example = in a ultima video the cursor is a gauntlet that has multiple variations ( directional )
tinted red in war mode and angled based on area of the screen . 
a system to match the gauntlet based on reference images 
as well as track it in the scene to create a mask that could be used for video inpainting
or if the shot is static a "last uncovered frame" would suffice .
the system needs to be flexible because of different scaled video footage , or zooming 
, and possible compression or low quality capture . 
in this example we can provide some example images of the gauntlet  images as guidance 

TODO:
add temporal confidence , we know the mouse likely wont jump across the screen unless scene change
add guidance confidence ( extremely high ) if the user has corrected the detection
include the recording of frames where no cursor was detected as its own classification , so it doesnt always compute non detected frames
decrease confidence of detection when near marked good frames , more likely a flase positive if we know the cursor wasnt seen recently 
add a re view toggle to each pass , so for example we can flag poorly inpainted frames that need to be replaced , 
for each scene that has static background , we could predict the highest unchanged pixel across frames ,

STATUS:: work in progress , currently very slow requires many guidance images and corrections , also replacement is bad in motion
VERSION::20251002
"""

import os
import sys
import cv2
import time
import glob
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import json


UI_BG = "#0b0b0b"
PANEL_BG = "#1a1a1a"
TEXT_FG = "#dcdcdc"
SUBTEXT_FG = "#bdbdbd"
ENTRY_BG = "#0f0f0f"
ENTRY_FG = "#dcdcdc"
HEADER_BLUE = "#1890ff"
HEADER_GREEN = "#52c41a"
HEADER_PURPLE = "#9254de"
HEADER_FONT = ("Segoe UI", 14, "bold")


class OutputMultiplexer:
    """
    Multiplex writes to multiple output streams, e.g., a Tkinter Text widget and a file/console.

    Example:
        log_capture = io.StringIO()
        sys.stdout = OutputMultiplexer(TextRedirector(text_widget), log_capture)
        print("Hello")  # Goes to both
    """

    def __init__(self, *streams):
        if not streams:
            raise ValueError("OutputMultiplexer requires at least one stream")
        for s in streams:
            if not hasattr(s, "write") or not hasattr(s, "flush"):
                raise TypeError("All streams must have write() and flush() methods")
        self.streams = streams

    def write(self, data):
        s = str(data)
        for stream in self.streams:
            try:
                stream.write(s)
            except Exception as e:
                # Do not raise; keep other streams functional
                sys.__stderr__.write(f"[OutputMultiplexer] Warning: {e}\n")

    def flush(self):
        for stream in self.streams:
            try:
                stream.flush()
            except Exception as e:
                sys.__stderr__.write(f"[OutputMultiplexer] Flush warning: {e}\n")

class TextRedirector:
    """ wrapper to send prints to a Tkinter Text widget."""

    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget

    def write(self, s: str):
        self.text_widget.insert(tk.END, s)
        self.text_widget.see(tk.END)

    def flush(self):
        pass

# ===================== Data classes & states =====================
@dataclass
class DetectionResult:
    frame_index: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    score: float
    template_name: str

@dataclass
class TrackPoint:
    frame_index: int
    bbox: Tuple[int, int, int, int]
    score: float

# ========== Utilities ==========
def imread_grayscale(path: str) -> Optional[np.ndarray]:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"[WARN] Failed to read template: {path}")
    return img

def draw_bbox(image_bgr: np.ndarray, bbox: Tuple[int, int, int, int], color=(0, 255, 0), label: Optional[str] = None):
    x, y, w, h = bbox
    cv2.rectangle(image_bgr, (x, y), (x + w, y + h), color, 2)
    if label:
        cv2.putText(image_bgr, label, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

def to_tk_image(frame_bgr: np.ndarray, max_w: int, max_h: int) -> ImageTk.PhotoImage:
    h, w = frame_bgr.shape[:2]
    scale = min(max_w / max(w, 1), max_h / max(h, 1))
    scale = max(scale, 1e-6)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return ImageTk.PhotoImage(Image.fromarray(rgb))

def create_mask_from_bbox(shape: Tuple[int, int], bbox: Tuple[int, int, int, int], dilation: int = 3) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)
    x, y, bw, bh = bbox
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w, x + bw), min(h, y + bh)
    mask[y0:y1, x0:x1] = 255
    if dilation > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation, dilation))
        mask = cv2.dilate(mask, kernel, iterations=1)
    return mask

def inpaint_frame(frame_bgr: np.ndarray, mask: np.ndarray, method: str = "telea", radius: int = 3) -> np.ndarray:
    method_flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    return cv2.inpaint(frame_bgr, (mask > 0).astype(np.uint8) * 255, radius, method_flag)

# ====================== Template matching logic ======================
class MultiScaleTemplateMatcher:
    def __init__(self, templates: Dict[str, np.ndarray], scales: List[float]):
        self.templates = templates  # name -> grayscale image
        self.scales = scales
        self._cache: List[Tuple[str, float, np.ndarray, Tuple[int,int]]] = []
        self._build_cache()

    def _build_cache(self):
        self._cache.clear()
        for tmpl_name, tmpl in self.templates.items():
            if tmpl is None or tmpl.size == 0:
                continue
            for s in self.scales:
                th, tw = tmpl.shape[:2]
                th_s, tw_s = max(1, int(th * s)), max(1, int(tw * s))
                if th_s < 3 or tw_s < 3:
                    continue
                try:
                    tmpl_s = cv2.resize(tmpl, (tw_s, th_s), interpolation=cv2.INTER_AREA)
                except Exception:
                    continue
                self._cache.append((tmpl_name, s, tmpl_s, (tw_s, th_s)))

    def refresh_templates(self, templates: Dict[str, np.ndarray]):
        self.templates = templates
        self._build_cache()

    def detect(self, frame_gray: np.ndarray, method=cv2.TM_CCOEFF_NORMED, threshold: float = 0.75, parallel: bool = False, workers: int = 0, early_stop_at: float = 0.985) -> Optional[DetectionResult]:
        if not self._cache:
            return None
        best: Optional[DetectionResult] = None

        def eval_one(entry: Tuple[str, float, np.ndarray, Tuple[int,int]]):
            tmpl_name, s, tmpl_s, (tw_s, th_s) = entry
            try:
                res = cv2.matchTemplate(frame_gray, tmpl_s, method)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                score = max_val if method in (cv2.TM_CCOEFF, cv2.TM_CCOEFF_NORMED) else 1.0 - min_val
                if score < threshold:
                    return None
                loc = max_loc if method in (cv2.TM_CCOEFF, cv2.TM_CCOEFF_NORMED) else min_loc
                return DetectionResult(frame_index=-1, bbox=(int(loc[0]), int(loc[1]), tw_s, th_s), score=float(score), template_name=f"{tmpl_name}@{s:.2f}")
            except Exception:
                return None

        if parallel:
            try:
                import concurrent.futures
                max_workers = workers if workers and workers > 0 else max(1, min(32, (os.cpu_count() or 4)))
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                    for det in ex.map(eval_one, self._cache):
                        if det is None:
                            continue
                        if (best is None) or (det.score > best.score):
                            best = det
            except Exception:
                # Fallback to sequential
                for entry in self._cache:
                    det = eval_one(entry)
                    if det is not None and ((best is None) or det.score > best.score):
                        best = det
        else:
            for entry in self._cache:
                det = eval_one(entry)
                if det is not None and ((best is None) or det.score > best.score):
                    best = det
                # Early stop on very confident match
                if best is not None and best.score >= early_stop_at:
                    break
        return best

class GpuTemplateMatcher:
    def __init__(self, templates: Dict[str, np.ndarray], scales: List[float]):
        self.scales = scales
        self.device_ok = hasattr(cv2, 'cuda') and cv2.cuda.getCudaEnabledDeviceCount() > 0
        self.gpu_templates: List[Tuple[str, float, any, Tuple[int,int]]] = []  # (name, scale, GpuMat, (tw,th))
        if self.device_ok:
            self._upload_templates(templates)

    def _upload_templates(self, templates: Dict[str, np.ndarray]):
        self.gpu_templates.clear()
        for name, tmpl in templates.items():
            for s in self.scales:
                t = cv2.resize(tmpl, (max(1, int(tmpl.shape[1]*s)), max(1, int(tmpl.shape[0]*s))), interpolation=cv2.INTER_AREA)
                if t.size == 0:
                    continue
                g = cv2.cuda_GpuMat()
                g.upload(t)
                self.gpu_templates.append((name, s, g, (t.shape[1], t.shape[0])))

    def refresh_templates(self, templates: Dict[str, np.ndarray]):
        if not self.device_ok:
            return
        self._upload_templates(templates)

    def detect(self, frame_gray: np.ndarray, threshold: float = 0.75) -> Optional[DetectionResult]:
        if not self.device_ok or not self.gpu_templates:
            return None
        gframe = cv2.cuda_GpuMat()
        gframe.upload(frame_gray)
        best: Optional[DetectionResult] = None
        best_val = -1.0
        # Create matcher once per frame
        matcher = cv2.cuda.createTemplateMatching(gframe.type(), cv2.TM_CCOEFF_NORMED)
        for name, s, gtmpl, (tw, th) in self.gpu_templates:
            res = matcher.match(gframe, gtmpl)
            # Download only max location
            res_host = res.download()
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res_host)
            if max_val >= threshold and max_val > best_val:
                x, y = max_loc
                det = DetectionResult(name=name, scale=s, score=float(max_val), bbox=(x, y, tw, th), frame_index=-1)
                best = det
                best_val = max_val
        return best

# =============== Video utilities ===============
class VideoReader:
    def __init__(self, path: str):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            print(f"[ERROR] Failed to open video: {path}")
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS)) or 30.0
        self.w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
        self.h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0

    def read_frame(self, index: int) -> Optional[np.ndarray]:
        if index < 0 or index >= self.frame_count:
            return None
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self.cap.read()
        if not ok:
            return None
        return frame

    def release(self):
        try:
            self.cap.release()
        except Exception:
            pass

def build_tracker() -> Optional[cv2.Tracker]:
    # Prefer CSRT if available
    if hasattr(cv2, 'TrackerCSRT_create'):
        return cv2.TrackerCSRT_create()
    if hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerCSRT_create'):
        return cv2.legacy.TrackerCSRT_create()
    # Fallbacks
    if hasattr(cv2, 'TrackerKCF_create'):
        return cv2.TrackerKCF_create()
    if hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerKCF_create'):
        return cv2.legacy.TrackerKCF_create()
    print("[WARN] No supported OpenCV tracker found. Tracking disabled.")
    return None

# =============== Main Tkinter UI ===============
class VideoCursorRemovalApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Video Cursor Removal - Review, Detect, Track")

        # State
        self.video_path: Optional[str] = None
        self.reader: Optional[VideoReader] = None
        self.cur_frame_idx: int = 0
        self.cur_frame: Optional[np.ndarray] = None
        self.playing: bool = False

        self.templates: Dict[str, np.ndarray] = {}
        self.scales = [0.5, 0.75, 1.0, 1.25, 1.5]
        self.matcher = MultiScaleTemplateMatcher(self.templates, scales=self.scales)
        # GPU/Parallel detection toggles
        self.use_gpu = tk.BooleanVar(value=(hasattr(cv2, 'cuda') and cv2.cuda.getCudaEnabledDeviceCount() > 0))
        self.gpu_matcher = GpuTemplateMatcher(self.templates, scales=self.scales) if self.use_gpu.get() else None
        self.use_parallel = tk.BooleanVar(value=True)
        self.detect_downscale = tk.DoubleVar(value=1.0)  # e.g., 0.75 for speed
        self.last_detection: Optional[DetectionResult] = None
        self.tracks: Dict[int, TrackPoint] = {}  # frame_index -> track point
        self.show_detection = tk.BooleanVar(value=True)
        self.show_tracking = tk.BooleanVar(value=True)
        self.show_mask = tk.BooleanVar(value=True)

        self.threshold = tk.DoubleVar(value=0.85)
        self.dilation = tk.IntVar(value=5)
        self.inpaint_method = tk.StringVar(value="telea")
        self.inpaint_radius = tk.IntVar(value=3)
        # Temporal inpaint settings
        self.temporal_scene_thresh = tk.DoubleVar(value=0.90)
        self.temporal_max_search = tk.IntVar(value=120)
        # Frame jump UI state (1-based display)
        self.frame_entry_var = tk.StringVar(value="1")
        # Saved data usage
        self.use_saved_data = tk.BooleanVar(value=True)
        self.detections_cache: Dict[int, Dict[str, any]] = {}
        # Auto-save preview results
        self.auto_save_preview = tk.BooleanVar(value=True)
        # Debug logging toggle
        self.debug_logging = tk.BooleanVar(value=True)
        # Frames marked as good (skip processing)
        self.good_frames: set[int] = set()
        # Last preview bbox for interactions
        self.last_preview_bbox: Optional[Tuple[int,int,int,int]] = None
        # Cache of bad detections loaded from bad_detections.jsonl: frame -> list of dicts
        self.bad_detections: Dict[int, List[Dict[str, any]]] = {}
        # View toggles for cached artifacts
        self.view_cached_mask = tk.BooleanVar(value=False)
        self.view_cached_inpaint = tk.BooleanVar(value=False)
        # Preview mode (SOURCE, DETECTION, MASK, INPAINT)
        self.preview_mode = tk.StringVar(value="SOURCE")

        # Guidance/dataset state
        self.guidance_mode = tk.BooleanVar(value=False)
        self.crop_w = tk.IntVar(value=85)
        self.crop_h = tk.IntVar(value=85)
        self.add_to_templates = tk.BooleanVar(value=True)
        self.dataset_dir: Optional[str] = None
        self.dataset_path_var = tk.StringVar(value="")
        self.display_scale: float = 1.0
        self.display_size: Tuple[int, int] = (0, 0)
        self.display_user_scale = tk.DoubleVar(value=0.5)  # 75% default

        # Preset / trueform learning
        self.active_preset = tk.StringVar(value="default_gauntlet")
        self.use_trueform_mask = tk.BooleanVar(value=True)
        self.presets: Dict[str, List[np.ndarray]] = {}
        self.trueforms: Dict[str, Dict[str, np.ndarray]] = {}  # name -> { 'median': np.ndarray, 'mask': np.ndarray }
        # Overlay mask video
        self.overlay_mask_enabled = tk.BooleanVar(value=False)
        self.mask_overlay_path = tk.StringVar(value="")
        self.mask_overlay_reader: Optional[VideoReader] = None

        self._setup_theme()
        self._build_ui()
        self._setup_logging()
        # General OpenCV runtime optimizations
        try:
            cv2.setUseOptimized(True)
            cv2.setNumThreads(max(1, os.cpu_count() or 1))
            try:
                cv2.ocl.setUseOpenCL(True)
            except Exception:
                pass
        except Exception:
            pass

    # ---------- UI ----------
    def _build_ui(self):
        self.root.geometry("1280x800")

        main = ttk.Frame(self.root, style="Dark.TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        # Row 0: Preview mode bar (top-most)
        mode_row = ttk.Frame(main, style="Dark.TFrame")
        mode_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(4, 0))
        ttk.Label(mode_row, text="Preview:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(2,6))
        ttk.Button(mode_row, text="SOURCE", command=lambda: self.set_preview_mode("SOURCE"), style="Blue.TButton").pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(mode_row, text="DETECTION", command=lambda: self.set_preview_mode("DETECTION"), style="Blue.TButton").pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(mode_row, text="MASK", command=lambda: self.set_preview_mode("MASK"), style="Blue.TButton").pack(side=tk.LEFT, padx=4, pady=4)
        ttk.Button(mode_row, text="INPAINT", command=lambda: self.set_preview_mode("INPAINT"), style="Blue.TButton").pack(side=tk.LEFT, padx=4, pady=4)

        # Row 1: Compact progress + counts
        progress_row = ttk.Frame(main, style="Dark.TFrame")
        progress_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(2, 2))
        ttk.Label(progress_row, text="Progress:", style="Dark.TLabel").pack(side=tk.LEFT, padx=(2,6))
        self.progress_label = ttk.Label(progress_row, text="Detections: 0/0 (0%)  |  Masks: 0/0 (0%)  |  Inpainted: 0/0 (0%)", style="Dark.TLabel")
        self.progress_label.pack(side=tk.LEFT, padx=(0,4))

        # Row 2: Timeline visualization (under progress, above sections)
        sep0 = ttk.Separator(main, orient=tk.HORIZONTAL)
        sep0.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0,2))
        self.timeline_canvas = tk.Canvas(main, height=56, bg=UI_BG, highlightthickness=0)
        self.timeline_canvas.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0,2))
        self.timeline_canvas.bind('<Button-1>', self._on_timeline_click)
        sep1 = ttk.Separator(main, orient=tk.HORIZONTAL)
        sep1.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(0,4))

        # Row 1: Video only
        video_row = ttk.Frame(main, style="Dark.TFrame")
        video_row.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))
        self.canvas = tk.Label(video_row, background="#111111")
        self.canvas.pack(side=tk.TOP, expand=True)
        # Right-click to mark BAD detection on current frame if clicking inside detection region
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Row 2: Playback controls centered
        playback_row = ttk.Frame(main, style="Dark.TFrame")
        playback_row.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 3))
        play_inner = ttk.Frame(playback_row, style="Dark.TFrame")
        play_inner.pack(side=tk.TOP)
        ttk.Button(play_inner, text="Open Video", command=self.open_video, style="Green.TButton").pack(side=tk.LEFT, padx=6, pady=1)
        ttk.Button(play_inner, text="<< Prev", command=self.prev_frame, style="Blue.TButton").pack(side=tk.LEFT, padx=6, pady=1)
        ttk.Button(play_inner, text="Play", command=self.play, style="Blue.TButton").pack(side=tk.LEFT, padx=6, pady=1)
        ttk.Button(play_inner, text="Pause", command=self.pause, style="Blue.TButton").pack(side=tk.LEFT, padx=6, pady=1)
        ttk.Button(play_inner, text="Next >>", command=self.next_frame, style="Blue.TButton").pack(side=tk.LEFT, padx=6, pady=1)
        ttk.Button(play_inner, text="Next Uncached DET", command=self.next_missing_detection, style="Blue.TButton").pack(side=tk.LEFT, padx=6, pady=1)
        # Dynamic frame entry (1-based)
        tk.Label(play_inner, text="Frame:", bg=PANEL_BG, fg=TEXT_FG).pack(side=tk.LEFT, padx=(12,4))
        frame_entry = tk.Entry(play_inner, textvariable=self.frame_entry_var, width=8, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        frame_entry.pack(side=tk.LEFT, padx=4)
        frame_entry.bind('<Return>', lambda e: self._jump_to_frame_from_entry())
        frame_entry.bind('<FocusOut>', lambda e: self._jump_to_frame_from_entry())

        # Controls grid container (2 rows x 4 columns)
        controls_grid = ttk.Frame(main, style="Dark.TFrame")
        controls_grid.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=6, pady=(1, 2))
        for i in range(4):
            controls_grid.columnconfigure(i, weight=1)

        # Helper to create a section cell
        def add_section(title: str, color: str, grid_row: int, grid_col: int):
            row = self._section(controls_grid, title, color)
            inner = ttk.Frame(row, style="Dark.TFrame")
            inner.pack(fill=tk.X)
            row.grid(row=grid_row, column=grid_col, padx=6, pady=1, sticky="nsew")
            return inner

        # Row 0
        view_inner = add_section("VIEW", HEADER_BLUE, 0, 0)
        settings_inner = add_section("SETTINGS (General)", HEADER_BLUE, 0, 1)
        dataset_inner = add_section("DATASET", HEADER_GREEN, 0, 2)
        training_inner = add_section("TRAINING", HEADER_GREEN, 0, 3)

        # Row 1
        detection_inner = add_section("DETECTION", HEADER_BLUE, 1, 0)
        mask_inner = add_section("MASK", HEADER_BLUE, 1, 1)
        inpaint_inner = add_section("INPAINT", HEADER_PURPLE, 1, 2)
        final_inner = add_section("FINAL", HEADER_PURPLE, 1, 3)

        # VIEW
        vr = view_inner; r,c,maxc = 0,0,4
        def vplace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=2, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        vplace(ttk.Label(vr, text="Display Scale (0.25..2.0)", style="Dark.TLabel"))
        scale_entry = tk.Entry(vr, textvariable=self.display_user_scale, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        scale_entry.bind('<Return>', lambda e: self._read_and_show())
        scale_entry.bind('<FocusOut>', lambda e: self._read_and_show())
        vplace(scale_entry)
        vplace(ttk.Checkbutton(vr, text="Show Detection", variable=self.show_detection, style="Dark.TCheckbutton"))
        vplace(ttk.Checkbutton(vr, text="Show Tracking", variable=self.show_tracking, style="Dark.TCheckbutton"))
        vplace(ttk.Checkbutton(vr, text="Show Mask", variable=self.show_mask, style="Dark.TCheckbutton"))
        vplace(ttk.Checkbutton(vr, text="Overlay Saved Mask", variable=self.overlay_mask_enabled, style="Dark.TCheckbutton"))
        vplace(ttk.Button(vr, text="Load Mask Video", command=self.load_mask_overlay_video, style="Blue.TButton"))

        # SETTINGS (General)
        sr = settings_inner; r,c,maxc = 0,0,4
        def splace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=2, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        splace(ttk.Checkbutton(sr, text="Use GPU", variable=self.use_gpu, command=self._toggle_gpu, style="Dark.TCheckbutton"))
        splace(ttk.Checkbutton(sr, text="Use Parallel", variable=self.use_parallel, style="Dark.TCheckbutton"))
        splace(ttk.Checkbutton(sr, text="Use Saved Data", variable=self.use_saved_data, style="Dark.TCheckbutton"))
        splace(ttk.Label(sr, text="Detect Scale", style="Dark.TLabel"))
        ds_entry = tk.Entry(sr, textvariable=self.detect_downscale, width=5, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        splace(ds_entry)
        splace(ttk.Checkbutton(sr, text="Auto-Save Preview", variable=self.auto_save_preview, style="Dark.TCheckbutton"))
        splace(ttk.Checkbutton(sr, text="Debug Log", variable=self.debug_logging, style="Dark.TCheckbutton"))

        # DATASET
        dr = dataset_inner; r,c,maxc = 0,0,4
        def dsetplace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=2, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        dsetplace(ttk.Label(dr, text="Dataset Folder", style="Dark.TLabel"))
        ds_path = tk.Entry(dr, textvariable=self.dataset_path_var, width=28, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        dsetplace(ds_path, colspan=2)
        dsetplace(ttk.Button(dr, text="Browse", command=self.set_dataset_folder, style="Blue.TButton"))
        dsetplace(ttk.Button(dr, text="Reload Dataset", command=self.reload_dataset_from_path, style="Blue.TButton"))
        dsetplace(ttk.Button(dr, text="Open Templates", command=self.open_templates_folder, style="Blue.TButton"))

        # TRAINING
        tr = training_inner; r,c,maxc = 0,0,4
        def tplace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=2, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        tplace(ttk.Label(tr, text="Active Preset", style="Dark.TLabel"))
        ap_entry = tk.Entry(tr, textvariable=self.active_preset, width=16, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        tplace(ap_entry)
        tplace(ttk.Checkbutton(tr, text="Use Trueform Mask", variable=self.use_trueform_mask, style="Dark.TCheckbutton"))
        tplace(ttk.Button(tr, text="Build Trueform", command=self.build_trueform_for_active, style="Green.TButton"))
        tplace(ttk.Button(tr, text="Toggle Guidance Mode", command=self.toggle_guidance_mode, style="Green.TButton"))

        # DETECTION
        de = detection_inner; r,c,maxc = 0,0,4
        def deplace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=2, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        deplace(ttk.Label(de, text="Threshold", style="Dark.TLabel"))
        thr_entry = tk.Entry(de, textvariable=self.threshold, width=6, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        thr_entry.bind('<Return>', lambda e: self._read_and_show())
        thr_entry.bind('<FocusOut>', lambda e: self._read_and_show())
        deplace(thr_entry)
        deplace(ttk.Button(de, text="Detect (Frame)", command=self.detect_current_frame, style="Blue.TButton"))
        deplace(ttk.Button(de, text="Start Track", command=self.start_tracking_from_here, style="Green.TButton"))
        deplace(ttk.Button(de, text="Clear Tracks", command=self.clear_tracks, style="Green.TButton"))
        deplace(ttk.Button(de, text="Compute Detections (JSONL)", command=self.compute_and_save_detections, style="Blue.TButton"), colspan=2)

        # MASK
        mk = mask_inner; r,c,maxc = 0,0,4
        def mplace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=2, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        mplace(ttk.Label(mk, text="Dilation", style="Dark.TLabel"))
        dil_entry = tk.Entry(mk, textvariable=self.dilation, width=5, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        mplace(dil_entry)
        mplace(ttk.Button(mk, text="Compute Masks (PNGs)", command=self.compute_and_save_masks_from_detections, style="Blue.TButton"), colspan=2)
        mplace(ttk.Button(mk, text="Mark Frame Good", command=self.mark_current_frame_good, style="Green.TButton"))
        mplace(ttk.Button(mk, text="Unmark Frame Good", command=self.unmark_current_frame_good, style="Green.TButton"))

        # INPAINT (per-frame)
        ip = inpaint_inner; r,c,maxc = 0,0,4
        def iplace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=2, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        iplace(ttk.Button(ip, text="Inpaint (This Frame)", command=self.inpaint_current_frame, style="Green.TButton"))
        iplace(ttk.Button(ip, text="Inpaint (Temporal)", command=self.inpaint_current_frame_temporal, style="Green.TButton"))
        iplace(ttk.Label(ip, text="Method", style="Dark.TLabel"))
        meth_entry = tk.Entry(ip, textvariable=self.inpaint_method, width=8, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        iplace(meth_entry)
        iplace(ttk.Label(ip, text="Radius", style="Dark.TLabel"))
        rad_entry = tk.Entry(ip, textvariable=self.inpaint_radius, width=5, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        iplace(rad_entry)
        iplace(ttk.Label(ip, text="Scene Thresh", style="Dark.TLabel"))
        st_entry = tk.Entry(ip, textvariable=self.temporal_scene_thresh, width=6, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        iplace(st_entry)
        iplace(ttk.Label(ip, text="Max Search", style="Dark.TLabel"))
        ms_entry = tk.Entry(ip, textvariable=self.temporal_max_search, width=6, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        iplace(ms_entry)
        iplace(ttk.Button(ip, text="Compute All Uncached Inpaint", command=self.compute_all_uncached_inpaint, style="Green.TButton"), colspan=2)

        # FINAL (exports)
        fn = final_inner; r,c,maxc = 0,0,4
        def fplace(w, colspan=1):
            nonlocal r,c
            w.grid(row=r, column=c, padx=6, pady=1, sticky="w", columnspan=colspan)
            c += colspan
            if c >= maxc:
                r += 1; c = 0
        fplace(ttk.Button(fn, text="Export Mask Video", command=self.export_mask_video, style="Blue.TButton"))
        fplace(ttk.Button(fn, text="Export Inpainted Video", command=self.export_inpaint_video, style="Blue.TButton"))

        # Info spanning all columns
        info_row = ttk.LabelFrame(main, text="Info", style="Dark.TLabelframe")
        info_row.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=6, pady=(2,1))
        self.info_text = tk.Text(info_row, height=6, bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ENTRY_FG)
        self.info_text.pack(fill=tk.BOTH, expand=True)

        self.root.after(33, self._update_loop)

    def _setup_logging(self):
        
        print("[INIT] UI ready. Use Open Video to begin.")

    # ---------- Video I/O ----------
    def open_video(self):
        path = filedialog.askopenfilename(title="Select Video", filetypes=[("Video", "*.mp4;*.mov;*.avi;*.mkv;*.webm"), ("All", "*.*")])
        if not path:
            return
        if self.reader:
            self.reader.release()
        self.reader = VideoReader(path)
        self.video_path = path
        self.cur_frame_idx = 0
        self.tracks.clear()
        self.last_detection = None
        self._read_and_show()
        print(f"[VIDEO] Opened: {path} ({self.reader.w}x{self.reader.h} @ {self.reader.fps:.2f} fps, {self.reader.frame_count} frames)")
        # Default dataset directory to <video_dir>/cursor
        default_ds = os.path.join(os.path.dirname(path), "cursor")
        self.dataset_dir = default_ds
        self.dataset_path_var.set(default_ds)
        if os.path.isdir(default_ds):
            self._load_dataset_to_templates(default_ds)
        else:
            print(f"[DATASET] Default cursor folder not found: {default_ds}")
        # Initial progress update
        self._update_progress_labels()
        # Load any saved good frames for this video
        self._load_good_frames()
        # Load bad detections (per-bbox) cache
        self._load_bad_detections_cache()

    def open_templates_folder(self):
        # Backward-compatible manual load, but templates == dataset
        folder = filedialog.askdirectory(title="Select Dataset/Templates Folder")
        if not folder:
            return
        self.dataset_dir = folder
        self.dataset_path_var.set(folder)
        self._load_dataset_to_templates(folder)

    # ---------- Playback ----------
    def toggle_play(self):
        if not self.reader:
            print("[WARN] Open a video first.")
            return
        self.playing = not self.playing
        print(f"[PLAY] {'Playing' if self.playing else 'Paused'}")

    def play(self):
        if not self.reader:
            print("[WARN] Open a video first.")
            return
        self.playing = True
        print("[PLAY] Playing")

    def pause(self):
        self.playing = False
        print("[PLAY] Paused")

    def next_frame(self):
        if not self.reader:
            return
        self.cur_frame_idx = (self.cur_frame_idx + 1) % self.reader.frame_count
        self._read_and_show()

    def prev_frame(self):
        if not self.reader:
            return
        self.cur_frame_idx = (self.cur_frame_idx - 1) % self.reader.frame_count
        self.cur_frame_idx = max(self.cur_frame_idx - 1, 0)
        self._read_and_show()

    def _update_loop(self):
        if self.playing and self.reader:
            self.cur_frame_idx += 1
            if self.cur_frame_idx >= self.reader.frame_count:
                # Loop playback
                self.cur_frame_idx = 0
            self._read_and_show()
        # Schedule next tick
        # Periodically refresh progress (guard in case method not yet bound)
        if getattr(self, '_progress_tick', 0) % 15 == 0 and hasattr(self, '_update_progress_labels'):
            try:
                self._update_progress_labels()
            except Exception as e:
                print(f"[UI] Progress update skipped: {e}")
        self._progress_tick = getattr(self, '_progress_tick', 0) + 1
        self.root.after( int(1000 / (self.reader.fps if self.reader else 30.0)), self._update_loop)

    def _read_and_show(self):
        t_all0 = time.time()
        if not self.reader:
            return
        frame = self.reader.read_frame(self.cur_frame_idx)
        if frame is None:
            return
        self.dlog(f"[PREVIEW] Frame {self.cur_frame_idx}: begin")
        self.cur_frame = frame
        vis = frame.copy()

        # Apply preview mode shortcuts first
        pmode = (self.preview_mode.get() or "SOURCE").upper()
        if pmode == "INPAINT":
            ip = self._inpainted_path_for_frame(self.cur_frame_idx)
            if ip and os.path.isfile(ip):
                img = cv2.imread(ip, cv2.IMREAD_COLOR)
                if img is not None and img.shape[:2] == (self.reader.h, self.reader.w):
                    vis = img.copy()
            # In non-SOURCE modes, skip overlays entirely
            bbox = None; det_score = None
        elif pmode == "MASK":
            mp = self._mask_path_for_frame(self.cur_frame_idx)
            if mp and os.path.isfile(mp):
                mimg = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
                if mimg is not None and mimg.shape[:2] == (self.reader.h, self.reader.w):
                    vis = cv2.cvtColor(mimg, cv2.COLOR_GRAY2BGR)
            bbox = None; det_score = None
        else:
            # default SOURCE/DETECTION handled below; we allow detection bbox for DETECTION
            pass

        # If frame is marked good, skip detection/mask overlays and label the frame (SOURCE/DETECTION only)
        if pmode in ("SOURCE", "DETECTION") and self.cur_frame_idx in self.good_frames:
            cv2.putText(vis, "GOOD (skipped)", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 0), 2, cv2.LINE_AA)
            bbox = None
            det_score = None
        elif False:  # deprecated bad_frames logic
            pass
        elif pmode in ("SOURCE", "DETECTION"):
            # Live detection preview and pixel mask overlay using current dataset/trueforms
            bbox = None
            det_score = None
            # In DETECTION mode, we still allow bbox but ignore mask overlay and autosave
            if (pmode == "DETECTION") or (self.show_detection.get() or self.show_mask.get()):
                # Prefer saved detections for current frame
                det = None
                if self.use_saved_data.get():
                    self._load_detections_cache()
                    if self.cur_frame_idx in self.detections_cache:
                        d = self.detections_cache[self.cur_frame_idx]
                        bbox = tuple(d.get('bbox', [0,0,0,0]))  # type: ignore
                        det_score = d.get('score', None)
                    else:
                        t0 = time.time()
                        det = self._detect_bbox(frame)
                        self.dlog(f"[PREVIEW] live detect took {(time.time()-t0)*1000:.1f} ms")
                else:
                    t0 = time.time()
                    det = self._detect_bbox(frame)
                    self.dlog(f"[PREVIEW] live detect took {(time.time()-t0)*1000:.1f} ms")
                if det is not None:
                    # If this frame has bad detections, ignore overlapping candidate
                    if self._is_bad_candidate(self.cur_frame_idx, det.bbox):
                        det = None
                if det is not None:
                    bbox = det.bbox
                    det_score = det.score
                if bbox is not None:
                    draw_bbox(vis, bbox, (0, 255, 255), f"DET {det_score:.2f}" if det_score is not None else "DET")
        # Overlay mask (trueform preferred) — only in SOURCE mode, no auto-inpaint
        saved_any = False
        if pmode == "SOURCE" and (self.cur_frame_idx not in self.good_frames) and self.show_mask.get() and bbox is not None:
            # Prefer saved mask for current frame
            mask = None
            det_used: Optional[DetectionResult] = None
            if self.use_saved_data.get():
                t0 = time.time()
                mask = self._load_saved_mask_for_frame(self.cur_frame_idx)
                self.dlog(f"[PREVIEW] load saved mask took {(time.time()-t0)*1000:.1f} ms")
            if mask is None:
                # Compute on the fly
                if self.use_saved_data.get() and (self.cur_frame_idx in getattr(self, 'detections_cache', {})):
                    try:
                        bb = tuple(self.detections_cache[self.cur_frame_idx].get('bbox', [0,0,0,0]))  # type: ignore
                    except Exception:
                        bb = None
                    if bb is not None and not self._is_bad_candidate(self.cur_frame_idx, bb):
                        tfm = self._get_trueform_mask_for_bbox(bb)
                        if tfm is None:
                            mask = create_mask_from_bbox((self.reader.h, self.reader.w), bb, self.dilation.get())
                        else:
                            mask = np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                            x,y,w,h = bb
                            tf_resized = cv2.resize(tfm, (w, h), interpolation=cv2.INTER_NEAREST)
                            mask[y:y+h, x:x+w] = (tf_resized > 0).astype(np.uint8) * 255
                if mask is None:
                    det2 = self._detect_bbox(frame)
                    if det2 is not None and not self._is_bad_candidate(self.cur_frame_idx, det2.bbox):
                        det_used = det2
                        tfm = self._get_trueform_mask_for_bbox(det2.bbox)
                        if tfm is None:
                            mask = create_mask_from_bbox((self.reader.h, self.reader.w), det2.bbox, self.dilation.get())
                        else:
                            mask = np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                            x,y,w,h = det2.bbox
                            tf_resized = cv2.resize(tfm, (w, h), interpolation=cv2.INTER_NEAREST)
                            mask[y:y+h, x:x+w] = (tf_resized > 0).astype(np.uint8) * 255
            # Overlay only
            if mask is not None:
                colored = vis.copy()
                colored[mask > 0] = (0, 0, 255)
                vis = cv2.addWeighted(vis, 0.7, colored, 0.3, 0)
                # Optional auto-save of preview outputs
                if self.auto_save_preview.get():
                    try:
                        self._ensure_output_dirs()
                        # Save detection record if missing and we have a live det
                        if bbox is not None and det_used is not None:
                            self._load_detections_cache()
                            if (self.cur_frame_idx not in self.detections_cache):
                                self._append_detection_jsonl(det_used, self.cur_frame_idx)
                                saved_any = True
                        # Save mask PNG if not exists
                        mp = self._mask_path_for_frame(self.cur_frame_idx)
                        if mp and not os.path.isfile(mp):
                            cv2.imwrite(mp, mask)
                            self.dlog("[PREVIEW] autosave mask write")
                            saved_any = True
                    except Exception as e:
                        self.dlog(f"[PREVIEW] autosave preview failed: {e}")

        # Optional overlay of a saved mask video for review
        if self.overlay_mask_enabled.get() and self.mask_overlay_reader is not None:
            if 0 <= self.cur_frame_idx < self.mask_overlay_reader.frame_count:
                mframe = self.mask_overlay_reader.read_frame(self.cur_frame_idx)
                if mframe is not None:
                    # Accept grayscale or BGR; derive mask
                    if len(mframe.shape) == 3:
                        mgray = cv2.cvtColor(mframe, cv2.COLOR_BGR2GRAY)
                    else:
                        mgray = mframe
                    ov_mask = (mgray > 0).astype(np.uint8)
                    colored = vis.copy()
                    colored[ov_mask > 0] = (0, 0, 255)
                    vis = cv2.addWeighted(vis, 0.6, colored, 0.4, 0)

        # Update canvas using user display scale (no cropping, consistent mapping)
        h, w = vis.shape[:2]
        scale = max(0.01, float(self.display_user_scale.get()))
        disp_w, disp_h = int(w * scale), int(h * scale)
        resized = cv2.resize(vis, (disp_w, disp_h), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        tkimg = ImageTk.PhotoImage(Image.fromarray(rgb))
        # Store display mapping info (no letterboxing offsets)
        self.display_scale = scale
        self.display_size = (disp_w, disp_h)
        self.display_offset = (0, 0)
        self.canvas.configure(image=tkimg)
        self.canvas.image = tkimg

        # Update info
        self.info_text.delete("1.0", tk.END)
        if self.reader:
            self.info_text.insert(tk.END, f"Frame: {self.cur_frame_idx+1}/{self.reader.frame_count}\n")
            if bbox is not None and det_score is not None:
                self.info_text.insert(tk.END, f"Detect(live): {bbox} score={det_score:.3f}\n")
            if self.mask_overlay_reader is not None and self.overlay_mask_enabled.get():
                self.info_text.insert(tk.END, f"Overlay: {os.path.basename(self.mask_overlay_path.get())}\n")
            # Keep frame entry synced (1-based)
            try:
                self.frame_entry_var.set(str(self.cur_frame_idx + 1))
            except Exception:
                pass
            # If anything was saved, refresh progress label
            if saved_any:
                try:
                    self._update_progress_labels()
                except Exception:
                    pass
        # Remember last preview bbox for interactions
        self.last_preview_bbox = bbox
        self.dlog(f"[PREVIEW] total took {(time.time()-t_all0)*1000:.1f} ms")

    def set_preview_mode(self, mode: str):
        m = (mode or "SOURCE").upper()
        if m not in ("SOURCE", "DETECTION", "MASK", "INPAINT"):
            m = "SOURCE"
        self.preview_mode.set(m)
        # Keep legacy booleans in sync (so existing code paths work)
        if m == "INPAINT":
            self.view_cached_inpaint.set(True)
            self.view_cached_mask.set(False)
        elif m == "MASK":
            self.view_cached_inpaint.set(False)
            self.view_cached_mask.set(True)
        else:
            self.view_cached_inpaint.set(False)
            self.view_cached_mask.set(False)
        # Redraw
        self._read_and_show()

    def _jump_to_frame_from_entry(self):
        if not self.reader:
            return
        txt = self.frame_entry_var.get().strip()
        try:
            val = int(float(txt))  # tolerate "10.0"
        except Exception:
            # reset to current
            self.frame_entry_var.set(str(self.cur_frame_idx + 1))
            return
        # Convert to 0-based index
        idx0 = max(1, val) - 1
        idx0 = min(idx0, max(0, self.reader.frame_count - 1))
        if idx0 != self.cur_frame_idx:
            self.cur_frame_idx = idx0
            self._read_and_show()

    def load_mask_overlay_video(self):
        path = filedialog.askopenfilename(title="Select Mask Video", filetypes=[("Video", "*.mp4;*.avi;*.mkv;*.mov;*.webm"), ("All", "*.*")])
        if not path:
            return
        try:
            self.mask_overlay_reader = VideoReader(path)
            self.mask_overlay_path.set(path)
            print(f"[OVERLAY] Loaded mask overlay video: {path}")
        except Exception as e:
            self.mask_overlay_reader = None
            self.mask_overlay_path.set("")
            print(f"[OVERLAY] Failed to load overlay video: {e}")

    # ---------- Detection & tracking ----------
    def _detect_bbox(self, frame_bgr: np.ndarray) -> Optional[DetectionResult]:
        if not self.templates:
            return None
        # Convert to grayscale and optionally downscale for speed
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        s = max(0.1, float(self.detect_downscale.get()))
        if s != 1.0:
            dsz = (max(1, int(gray.shape[1]*s)), max(1, int(gray.shape[0]*s)))
            gray_ds = cv2.resize(gray, dsz, interpolation=cv2.INTER_AREA)
        else:
            gray_ds = gray
        thr = float(self.threshold.get())

        # Optional ROI search using cached detection for this frame or last live detection
        det: Optional[DetectionResult] = None
        roi_img = gray_ds
        roi_offset = (0, 0)
        try_roi = False
        # Try to use cached bbox for current frame
        self._load_detections_cache()
        cached_bbox = None
        if self.use_saved_data.get() and (self.cur_frame_idx in self.detections_cache):
            try:
                bb = self.detections_cache[self.cur_frame_idx].get('bbox', [0,0,0,0])
                cached_bbox = (int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3]))
            except Exception:
                cached_bbox = None
        src_bbox = cached_bbox if cached_bbox is not None else (self.last_detection.bbox if getattr(self, 'last_detection', None) is not None else None)
        if src_bbox is not None:
            x, y, w, h = src_bbox
            xs = int(x * s); ys = int(y * s); ws = int(max(8, w * s)); hs = int(max(8, h * s))
            margin = int(0.75 * max(ws, hs))
            rx0 = max(0, xs - margin)
            ry0 = max(0, ys - margin)
            rx1 = min(gray_ds.shape[1], xs + ws + margin)
            ry1 = min(gray_ds.shape[0], ys + hs + margin)
            if rx1 - rx0 >= 8 and ry1 - ry0 >= 8:
                roi_img = gray_ds[ry0:ry1, rx0:rx1]
                roi_offset = (rx0, ry0)
                try_roi = True

        def run_detect_local(img: np.ndarray) -> Optional[DetectionResult]:
            dloc = None
            if self.use_gpu.get() and self.gpu_matcher is not None:
                dloc = self.gpu_matcher.detect(img, threshold=thr)
            if dloc is None:
                dloc = self.matcher.detect(
                    img,
                    threshold=thr,
                    parallel=bool(self.use_parallel.get()),
                    workers=os.cpu_count() or 0,
                )
            return dloc

        # Try ROI first
        if try_roi:
            det = run_detect_local(roi_img)
            if det is not None:
                ox, oy = roi_offset
                x, y, w, h = det.bbox
                det = DetectionResult(
                    frame_index=self.cur_frame_idx,
                    bbox=(x + ox, y + oy, w, h),
                    score=det.score,
                    template_name=det.template_name,
                )
        # Fallback to full frame
        if det is None:
            det = run_detect_local(gray_ds)
            if det is not None:
                det.frame_index = self.cur_frame_idx
        if det is None:
            return None
        # Rescale bbox to original image coordinates if downscaled
        if s != 1.0:
            x, y, w, h = det.bbox
            inv = 1.0 / s
            det = DetectionResult(
                frame_index=det.frame_index,
                bbox=(int(x*inv), int(y*inv), int(w*inv), int(h*inv)),
                score=det.score,
                template_name=det.template_name,
            )
        return det

    def detect_current_frame(self):
        if not self.reader or self.cur_frame is None:
            print("[WARN] Open a video and move to a frame.")
            return
        if not self.templates:
            print("[WARN] Load a templates folder first.")
            return
        det = self._detect_bbox(self.cur_frame)
        if det is None:
            print(f"[DETECT] No match at frame {self.cur_frame_idx}.")
            self.last_detection = None
        else:
            det.frame_index = self.cur_frame_idx
            self.last_detection = det
            print(f"[DETECT] Frame {self.cur_frame_idx}: bbox={det.bbox} score={det.score:.3f} tmpl={det.template_name}")
        self._read_and_show()

    def start_tracking_from_here(self):
        if not self.reader or self.cur_frame is None:
            print("[WARN] Open a video and move to a frame.")
            return
        # Determine initial bbox
        init_bbox = None
        if self.cur_frame_idx in self.tracks:
            init_bbox = self.tracks[self.cur_frame_idx].bbox
        elif self.last_detection and self.last_detection.frame_index == self.cur_frame_idx:
            init_bbox = self.last_detection.bbox
        if init_bbox is None:
            print("[TRACK] Need a detection at current frame first (or existing track). Run Detect.")
            return

        tracker = build_tracker()
        if tracker is None:
            return

        x, y, w, h = init_bbox
        ok = tracker.init(self.cur_frame, (x, y, w, h))
        if not ok:
            print("[TRACK] Failed to initialize tracker.")
            return

        print(f"[TRACK] Tracking started at frame {self.cur_frame_idx} with bbox={init_bbox}")

        # Track forward until the end
        for fi in range(self.cur_frame_idx, self.reader.frame_count):
            frame = self.reader.read_frame(fi)
            if frame is None:
                break
            ok, bb = tracker.update(frame)
            if not ok:
                print(f"[TRACK] Lost at frame {fi}")
                break
            x, y, w, h = [int(v) for v in bb]
            self.tracks[fi] = TrackPoint(frame_index=fi, bbox=(x, y, w, h), score=1.0)
            if fi % 50 == 0:
                print(f"[TRACK] ... at frame {fi}")

        print(f"[TRACK] Tracking done. Tracked {len(self.tracks)} frames.")
        self._read_and_show()

    def clear_tracks(self):
        self.tracks.clear()
        print("[TRACK] Cleared all tracks.")
        self._read_and_show()

    # ---------- Export ----------
    def export_mask_video(self):
        if not self.reader:
            print("[WARN] Open a video first.")
            return
        out_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4"), ("AVI", "*.avi"), ("All", "*.*")], title="Save Mask Video")
        if not out_path:
            return
        fourcc = cv2.VideoWriter_fourcc(*('mp4v' if out_path.lower().endswith('.mp4') else 'XVID'))
        writer = cv2.VideoWriter(out_path, fourcc, self.reader.fps, (self.reader.w, self.reader.h), isColor=False)
        if not writer.isOpened():
            print(f"[ERROR] Failed to open writer: {out_path}")
            return

        print(f"[EXPORT] Writing mask video to {out_path}")
        chunk = 64
        total = self.reader.frame_count
        for start in range(0, total, chunk):
            end = min(total, start + chunk)
            frames = [self.reader.read_frame(i) for i in range(start, end)]
            indices = list(range(start, end))
            if self.use_parallel.get():
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4)//2)) as ex:
                    results = list(ex.map(self._make_mask_for_frame_or_saved, indices, frames))
            else:
                results = [self._make_mask_for_frame_or_saved(i, f) for i, f in zip(indices, frames)]
            for i, mask in zip(indices, results):
                # Skip masks for good frames
                if i in self.good_frames:
                    mask_out = np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                else:
                    mask_out = mask if mask is not None else np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                writer.write(mask_out)
                if i % 100 == 0:
                    print(f"[EXPORT] Mask frame {i}/{total}")
        writer.release()
        print("[STEP] Masks saved.")
        self._update_progress_labels()

    def export_inpaint_video(self):
        if not self.reader:
            print("[WARN] Open a video first.")
            return
        out_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4"), ("AVI", "*.avi"), ("All", "*.*")], title="Save Inpainted Video")
        if not out_path:
            return
        fourcc = cv2.VideoWriter_fourcc(*('mp4v' if out_path.lower().endswith('.mp4') else 'XVID'))
        writer = cv2.VideoWriter(out_path, fourcc, self.reader.fps, (self.reader.w, self.reader.h), isColor=True)
        if not writer.isOpened():
            print(f"[ERROR] Failed to open writer: {out_path}")
            return

        print(f"[EXPORT] Writing final inpainted video from cached frames to {out_path}")
        total = int(self.reader.frame_count)
        for i in range(total):
            # Use source for good frames
            if i in self.good_frames:
                frame = self.reader.read_frame(i)
                if frame is not None:
                    writer.write(frame)
                else:
                    # Write a black frame if read fails
                    writer.write(np.zeros((self.reader.h, self.reader.w, 3), dtype=np.uint8))
                if i % 100 == 0:
                    print(f"[EXPORT] Frame {i}/{total} (GOOD)")
                continue
            # Use cached inpainted frame
            ipath = self._inpainted_path_for_frame(i)
            if ipath and os.path.isfile(ipath):
                img = cv2.imread(ipath, cv2.IMREAD_COLOR)
                if img is None or img.shape[:2] != (self.reader.h, self.reader.w):
                    # Fallback to source dimensions
                    src = self.reader.read_frame(i)
                    if src is None:
                        src = np.zeros((self.reader.h, self.reader.w, 3), dtype=np.uint8)
                    if img is not None and img.shape[:2] != (self.reader.h, self.reader.w):
                        img = cv2.resize(img, (self.reader.w, self.reader.h), interpolation=cv2.INTER_AREA)
                    out = img if img is not None else src
                else:
                    out = img
                writer.write(out)
            else:
                # If missing, fallback to source frame
                frame = self.reader.read_frame(i)
                if frame is None:
                    frame = np.zeros((self.reader.h, self.reader.w, 3), dtype=np.uint8)
                writer.write(frame)
            if i % 100 == 0:
                print(f"[EXPORT] Frame {i}/{total}")
        writer.release()
        print("[EXPORT] Final inpainted video complete.")

    def next_missing_detection(self):
        if not self.reader:
            print("[WARN] Open a video first.")
            return
        total = int(self.reader.frame_count)
        # Build set of frames that have detections
        seen = set()
        p = self._detections_jsonl_path()
        if p and os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            fi = int(d.get('frame', -1))
                            if 0 <= fi < total:
                                seen.add(fi)
                        except Exception:
                            continue
            except Exception as e:
                print(f"[NAV] Failed to read detections: {e}")
        # Find next index without detection cache, skipping frames marked good
        start = self.cur_frame_idx
        for off in range(1, total+1):
            idx = (start + off) % total
            if (idx not in seen) and (idx not in self.good_frames):
                self.cur_frame_idx = idx
                self._read_and_show()
                print(f"[NAV] Jumped to frame without detection: {idx}")
                return
        print("[NAV] All non-good frames have detection cache.")

    def compute_all_uncached_inpaint(self):
        if not self.reader:
            print("[WARN] Open a video first.")
            return
        method = (self.inpaint_method.get() or 'telea').strip().lower()
        radius = int(self.inpaint_radius.get())
        total = int(self.reader.frame_count)
        print(f"[BATCH] Computing inpaint for uncached frames using method={method}, radius={radius}")
        for i in range(total):
            # Skip frames marked good
            if i in self.good_frames:
                continue
            outp = self._inpainted_path_for_frame(i)
            if outp and os.path.isfile(outp):
                continue
            frame = self.reader.read_frame(i)
            if frame is None:
                continue
            mask = self._make_mask_for_frame_or_saved(i, frame)
            try:
                if mask is None or not np.any(mask > 0):
                    # Fallback: save original to avoid reprocessing repeatedly
                    if outp:
                        cv2.imwrite(outp, frame)
                else:
                    if method == 'temporal':
                        out = self._compute_temporal_fill(
                            i,
                            frame,
                            mask,
                            max_search=int(self.temporal_max_search.get()),
                            scene_thresh=float(self.temporal_scene_thresh.get()),
                        )
                        if out is None:
                            out = inpaint_frame(frame, mask, method='telea', radius=radius)
                    else:
                        out = inpaint_frame(frame, mask, method=method, radius=radius)
                    if outp:
                        cv2.imwrite(outp, out)
            except Exception as e:
                print(f"[BATCH] Inpaint failed at frame {i}: {e}")
            if i % 50 == 0:
                print(f"[BATCH] Inpaint progress {i}/{total}")
        print("[BATCH] Inpaint batch complete.")
        self._update_progress_labels()

    # ---------- Single-frame inpaint helpers ----------
    def _inpainted_path_for_frame(self, fi: int) -> Optional[str]:
        root = self._output_root()
        if root is None:
            return None
        idir = os.path.join(root, "inpainted")
        os.makedirs(idir, exist_ok=True)
        return os.path.join(idir, f"{fi:06d}.png")

    def inpaint_current_frame(self):
        if not self.reader or self.cur_frame is None:
            print("[INPAINT] Open a video and move to a frame.")
            return
        fi = self.cur_frame_idx
        outp = self._inpainted_path_for_frame(fi)
        if outp is None:
            print("[INPAINT] No output path available.")
            return
        frame = self.cur_frame
        # If marked good, just store original frame
        if fi in self.good_frames:
            try:
                cv2.imwrite(outp, frame)
                print(f"[INPAINT] Saved original frame as inpainted (GOOD): {outp}")
            except Exception as e:
                print(f"[INPAINT] Failed to save inpainted frame: {e}")
            self._update_progress_labels()
            if self.view_cached_inpaint.get():
                self._read_and_show()
            return
        # Build or load mask
        mask = self._load_saved_mask_for_frame(fi)
        if mask is None:
            # Compute on the fly
            det = None
            if self.use_saved_data.get():
                self._load_detections_cache()
                if fi in self.detections_cache:
                    try:
                        bb = tuple(self.detections_cache[fi].get('bbox', [0,0,0,0]))  # type: ignore
                    except Exception:
                        bb = None
                    if bb is not None and not self._is_bad_candidate(fi, bb):
                        tfm = self._get_trueform_mask_for_bbox(bb)
                        if tfm is None:
                            mask = create_mask_from_bbox((self.reader.h, self.reader.w), bb, self.dilation.get())
                        else:
                            mask = np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                            x,y,w,h = bb
                            tf_resized = cv2.resize(tfm, (w, h), interpolation=cv2.INTER_NEAREST)
                            mask[y:y+h, x:x+w] = (tf_resized > 0).astype(np.uint8) * 255
            if mask is None:
                det = self._detect_bbox(frame)
                if det is not None and not self._is_bad_candidate(fi, det.bbox):
                    tfm = self._get_trueform_mask_for_bbox(det.bbox)
                    if tfm is None:
                        mask = create_mask_from_bbox((self.reader.h, self.reader.w), det.bbox, self.dilation.get())
                    else:
                        mask = np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                        x,y,w,h = det.bbox
                        tf_resized = cv2.resize(tfm, (w, h), interpolation=cv2.INTER_NEAREST)
                        mask[y:y+h, x:x+w] = (tf_resized > 0).astype(np.uint8) * 255
        if mask is None:
            print("[INPAINT] No mask available; saving original frame.")
            try:
                cv2.imwrite(outp, frame)
            except Exception as e:
                print(f"[INPAINT] Failed to save frame: {e}")
            self._update_progress_labels()
            if self.view_cached_inpaint.get():
                self._read_and_show()
            return
        # Inpaint and save
        method = self.inpaint_method.get().strip().lower()
        radius = int(self.inpaint_radius.get())
        try:
            if method == 'temporal':
                t0 = time.time()
                out = self._compute_temporal_fill(
                    fi,
                    frame,
                    mask,
                    max_search=int(self.temporal_max_search.get()),
                    scene_thresh=float(self.temporal_scene_thresh.get()),
                )
                self.dlog(f"[INPAINT] temporal fill took {(time.time()-t0)*1000:.1f} ms")
                # Fallback if temporal didn't fill everything
                if out is None:
                    out = inpaint_frame(frame, mask, method='telea', radius=radius)
            else:
                out = inpaint_frame(frame, mask, method=method, radius=radius)
            cv2.imwrite(outp, out)
            print(f"[INPAINT] Saved inpainted frame: {outp}")
        except Exception as e:
            print(f"[INPAINT] Inpaint failed: {e}")
        self._update_progress_labels()
        if self.view_cached_inpaint.get():
            self._read_and_show()

    def inpaint_current_frame_temporal(self):
        """Convenience trigger: set method to 'temporal' and inpaint this frame."""
        try:
            self.inpaint_method.set('temporal')
        except Exception:
            pass
        self.inpaint_current_frame()

    def _compute_temporal_fill(self, fi: int, frame_bgr: np.ndarray, mask: np.ndarray, max_search: int = 120, scene_thresh: float = 0.90) -> Optional[np.ndarray]:
        """
        Composite the masked region from neighboring frames that belong to the same scene.
        Strategy:
          1) Search backward up to max_search frames, picking frames with high scene similarity.
          2) Copy pixels only from regions that are not masked in the candidate frame.
          3) If region not fully filled, search forward similarly.
          4) Return frame with filled pixels; if nothing filled, return None.
        """
        H, W = frame_bgr.shape[:2]
        target = frame_bgr.copy()
        to_fill = (mask > 0)
        if not np.any(to_fill):
            return target
        # Precompute reference descriptor for scene matching
        ref_desc = self._frame_descriptor(frame_bgr)
        # Backward search
        filled_any = False
        def try_composite_from(idx: int) -> bool:
            nonlocal target, to_fill
            cand = self.reader.read_frame(idx)
            if cand is None:
                return False
            # Scene check
            sim = self._scene_similarity(ref_desc, self._frame_descriptor(cand))
            if sim < scene_thresh:
                return False
            # Respect candidate's saved mask (avoid copying its corrupted pixels)
            cm = self._load_saved_mask_for_frame(idx)
            valid = np.ones((H, W), dtype=bool) if cm is None else (cm == 0)
            # Copy only where we still need fill and candidate is valid
            sel = to_fill & valid
            if not np.any(sel):
                return False
            target[sel] = cand[sel]
            to_fill[sel] = False
            return True
        # Backward
        for k in range(1, max_search+1):
            j = fi - k
            if j < 0:
                break
            if try_composite_from(j):
                filled_any = True
            if not np.any(to_fill):
                break
        # Forward if needed
        if np.any(to_fill):
            for k in range(1, max_search+1):
                j = fi + k
                if self.reader and j >= self.reader.frame_count:
                    break
                if try_composite_from(j):
                    filled_any = True
                if not np.any(to_fill):
                    break
        if filled_any:
            # For any remaining holes, do a small Telea pass on the result
            remain = (to_fill.astype(np.uint8) * 255)
            try:
                out = inpaint_frame(target, remain, method='telea', radius=2)
            except Exception:
                out = target
            return out
        return None

    def _frame_descriptor(self, img_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Return downscaled grayscale and color histogram as a scene descriptor."""
        try:
            small = cv2.resize(img_bgr, (128, 72), interpolation=cv2.INTER_AREA)
        except Exception:
            h, w = img_bgr.shape[:2]
            small = cv2.resize(img_bgr, (max(16, w//10), max(16, h//10)), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5,5), 0)
        # Color histogram in HSV for robustness
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0,1], None, [16,16], [0,180, 0,256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        return gray, hist

    def _scene_similarity(self, ref_desc: Tuple[np.ndarray, np.ndarray], cand_desc: Tuple[np.ndarray, np.ndarray]) -> float:
        """Combine grayscale MSE-based score and HSV histogram correlation to estimate scene similarity (0..1)."""
        try:
            ref_gray, ref_hist = ref_desc
            c_gray, c_hist = cand_desc
            # Histogram correlation in [0..1]
            hc = float(cv2.compareHist(ref_hist, c_hist, cv2.HISTCMP_CORREL))
            hc = max(0.0, min(1.0, hc))
            # Grayscale similarity via normalized MSE -> convert to score in [0..1]
            diff = cv2.absdiff(ref_gray, c_gray)
            mse = float(np.mean(diff.astype(np.float32)**2))
            # Normalize roughly by 255^2
            nmse = mse / (255.0*255.0)
            gs = max(0.0, 1.0 - nmse*10.0)  # tolerate some noise
            # Combine (weighted)
            score = 0.6*hc + 0.4*gs
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.0

    # ---------- Persistent steps (UI buttons) ----------
    def compute_and_save_detections(self):
        if not self.reader:
            print("[STEP] Open a video first.")
            return
        det_dir, _ = self._ensure_output_dirs()
        print(f"[STEP] Computing detections to {det_dir}...")
        total = self.reader.frame_count
        # Reset cache so we don't count stale values
        self.detections_cache.clear()
        p = self._detections_jsonl_path()
        # Ensure file exists
        if p and not os.path.isfile(p):
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'a').close()
            except Exception:
                pass
        for fi in range(total):
            if fi in self.good_frames:
                continue
            frame = self.reader.read_frame(fi)
            if frame is None:
                continue
            det = self._detect_bbox(frame)
            if det is not None:
                # Skip detections that overlap any known bad bbox for this frame
                if self._is_bad_candidate(fi, det.bbox):
                    det = None
            if det is not None:
                self._append_detection_jsonl(det, fi)
            if fi % 100 == 0:
                print(f"[STEP] Detections {fi}/{total}")
        print("[STEP] Detections saved.")
        self._update_progress_labels()

    def compute_and_save_masks_from_detections(self):
        if not self.reader:
            print("[STEP] Open a video first.")
            return
        det_dir, msk_dir = self._ensure_output_dirs()
        # Load detections
        self.detections_cache.clear()
        self._load_detections_cache()
        print(f"[STEP] Computing masks to {msk_dir}...")
        total = self.reader.frame_count
        for fi in range(total):
            if fi in self.good_frames:
                continue
            frame = self.reader.read_frame(fi)
            if frame is None:
                continue
            mp = self._mask_path_for_frame(fi)
            if mp and os.path.isfile(mp):
                continue  # skip existing
            bbox = None
            if fi in self.detections_cache:
                d = self.detections_cache[fi]
                try:
                    bbox = tuple(d.get('bbox', [0,0,0,0]))  # type: ignore
                except Exception:
                    bbox = None
                # Skip if bbox matches a known bad detection
                if bbox is not None and self._is_bad_candidate(fi, bbox):
                    bbox = None
            else:
                det = self._detect_bbox(frame)
                bbox = det.bbox if det is not None else None
                if bbox is not None and self._is_bad_candidate(fi, bbox):
                    bbox = None
            if bbox is None:
                continue
            tf_mask = self._get_trueform_mask_for_bbox(bbox)
            if tf_mask is None:
                mask = create_mask_from_bbox((self.reader.h, self.reader.w), bbox, self.dilation.get())
            else:
                mask = np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                x,y,w,h = bbox
                tf_resized = cv2.resize(tf_mask, (w, h), interpolation=cv2.INTER_NEAREST)
                mask[y:y+h, x:x+w] = (tf_resized > 0).astype(np.uint8) * 255
            # Save mask
            if mp:
                try:
                    cv2.imwrite(mp, mask)
                except Exception as e:
                    print(f"[STEP] Failed to save mask for frame {fi}: {e}")
            if fi % 100 == 0:
                print(f"[STEP] Masks {fi}/{total}")
        print("[STEP] Masks saved.")
        self._update_progress_labels()

    # ---------- Persistent data helpers ----------
    def _output_root(self) -> Optional[str]:
        if not self.video_path:
            return None
        base = os.path.splitext(os.path.basename(self.video_path))[0]
        root = os.path.join(os.path.dirname(self.video_path), "cursor_cache", base)
        return root

    def _ensure_output_dirs(self) -> Tuple[str, str]:
        root = self._output_root()
        if root is None:
            raise RuntimeError("No video loaded")
        det_dir = os.path.join(root, "detections")
        msk_dir = os.path.join(root, "masks")
        os.makedirs(det_dir, exist_ok=True)
        os.makedirs(msk_dir, exist_ok=True)
        return det_dir, msk_dir

    def _detections_jsonl_path(self) -> Optional[str]:
        root = self._output_root()
        return os.path.join(root, "detections", "detections.jsonl") if root else None

    def _mask_path_for_frame(self, fi: int) -> Optional[str]:
        root = self._output_root()
        if root is None:
            return None
        return os.path.join(root, "masks", f"{fi:06d}.png")

    def _load_detections_cache(self):
        # Load JSONL detections into in-memory dict once per session
        if self.detections_cache:
            return
        p = self._detections_jsonl_path()
        if p and os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            fi = int(d.get('frame', -1))
                            if fi >= 0:
                                self.detections_cache[fi] = d
                        except Exception:
                            continue
                print(f"[CACHE] Loaded {len(self.detections_cache)} detections from {p}")
            except Exception as e:
                print(f"[CACHE] Failed to load detections: {e}")

    def _append_detection_jsonl(self, det: DetectionResult, frame_index: int):
        return self._append_detection_jsonl_ex(det, frame_index, source="auto")

    def _append_detection_jsonl_ex(self, det: DetectionResult, frame_index: int, source: str = "auto"):
        p = self._detections_jsonl_path()
        if not p:
            return
        rec = {
            'frame': int(frame_index),
            'bbox': [int(det.bbox[0]), int(det.bbox[1]), int(det.bbox[2]), int(det.bbox[3])],
            'score': float(det.score),
            'template': getattr(det, 'template_name', det.template_name if hasattr(det, 'template_name') else ""),
            'source': source
        }
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec) + "\n")
        except Exception as e:
            print(f"[CACHE] Failed to append detection: {e}")

    def _bad_detections_jsonl_path(self) -> Optional[str]:
        root = self._output_root()
        return os.path.join(root, "detections", "bad_detections.jsonl") if root else None

    def _append_bad_detection(self, frame_index: int, bbox: Tuple[int,int,int,int], score: Optional[float]=None, template: str="", source: str="bad_click"):
        p = self._bad_detections_jsonl_path()
        if not p:
            return
        rec = {
            'frame': int(frame_index),
            'bbox': [int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])],
            'score': float(score) if score is not None else None,
            'template': template,
            'source': source
        }
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec) + "\n")
        except Exception as e:
            print(f"[BAD] Failed to append bad detection: {e}")

    def _load_bad_detections_cache(self):
        self.bad_detections.clear()
        p = self._bad_detections_jsonl_path()
        if p and os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            fi = int(d.get('frame', -1))
                            if fi >= 0:
                                self.bad_detections.setdefault(fi, []).append(d)
                        except Exception:
                            continue
                print(f"[BAD] Loaded bad detections for {len(self.bad_detections)} frames")
            except Exception as e:
                print(f"[BAD] Failed to load bad detections: {e}")

    def _iou(self, a: Tuple[int,int,int,int], b: Tuple[int,int,int,int]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ax2, ay2 = ax+aw, ay+ah
        bx2, by2 = bx+bw, by+bh
        inter_w = max(0, min(ax2, bx2) - max(ax, bx))
        inter_h = max(0, min(ay2, by2) - max(ay, by))
        inter = inter_w * inter_h
        ua = aw*ah + bw*bh - inter
        return float(inter) / float(ua) if ua > 0 else 0.0

    def _is_bad_candidate(self, frame_index: int, bbox: Tuple[int,int,int,int]) -> bool:
        bads = self.bad_detections.get(frame_index, [])
        for d in bads:
            bb = d.get('bbox', [0,0,0,0])
            try:
                bb_t = (int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3]))
            except Exception:
                continue
            if self._iou(bbox, bb_t) > 0.3:
                return True
        return False

    def _load_saved_mask_for_frame(self, fi: int) -> Optional[np.ndarray]:
        mp = self._mask_path_for_frame(fi)
        if mp and os.path.isfile(mp):
            img = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
            if img is not None and self.reader and img.shape[:2] == (self.reader.h, self.reader.w):
                return (img > 0).astype(np.uint8) * 255
        return None

    # ---------- Progress helpers ----------
    def _update_progress_labels(self):
        if not getattr(self, 'progress_label', None) or not self.reader:
            return
        total = int(self.reader.frame_count)
        # Detections count (unique frames in JSONL)
        det_n = 0
        det_set = set()
        p = self._detections_jsonl_path()
        if p and os.path.isfile(p):
            try:
                seen = set()
                with open(p, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            fi = int(d.get('frame', -1))
                            if 0 <= fi < total:
                                seen.add(fi)
                        except Exception:
                            continue
                det_n = len(seen)
                det_set = seen
            except Exception:
                det_n = 0
        # Masks count
        mcount = 0
        mask_set = set()
        root = self._output_root()
        if root:
            mdir = os.path.join(root, "masks")
            if os.path.isdir(mdir):
                mfiles = glob.glob(os.path.join(mdir, "*.png"))
                mcount = len(mfiles)
                try:
                    mask_set = set(int(os.path.splitext(os.path.basename(p))[0]) for p in mfiles)
                except Exception:
                    mask_set = set()
        # Inpainted count (optional future)
        icount = 0
        inpaint_set = set()
        if root:
            idir = os.path.join(root, "inpainted")
            if os.path.isdir(idir):
                ifiles = glob.glob(os.path.join(idir, "*.png"))
                icount = len(ifiles)
                try:
                    inpaint_set = set(int(os.path.splitext(os.path.basename(p))[0]) for p in ifiles)
                except Exception:
                    inpaint_set = set()
        pct = lambda n: int(round((n / total) * 100)) if total > 0 else 0
        combined_set = set(getattr(self, 'good_frames', set()) or set()) | det_set | mask_set
        combined_n = len(combined_set)
        text = (
            f"Combined+Good: {combined_n}/{total} ({pct(combined_n)}%)  |  "
            f"Detections: {det_n}/{total} ({pct(det_n)}%)  |  Masks: {mcount}/{total} ({pct(mcount)}%)  |  Inpainted: {icount}/{total} ({pct(icount)}%)"
        )
        try:
            self.progress_label.configure(text=text)
        except Exception:
            pass
        # Update timeline visualization
        try:
            self._update_timeline(det_set, mask_set, inpaint_set)
        except Exception as e:
            self.dlog(f"[UI] Timeline update skipped: {e}")

    def _update_timeline(self, det_set: set, mask_set: set, inpaint_set: set):
        if not hasattr(self, 'timeline_canvas') or not self.reader:
            return
        canvas = self.timeline_canvas
        canvas.delete('all')
        total = max(1, int(self.reader.frame_count))
        w = max(100, canvas.winfo_width() or (total))
        h_row = 8
        gap = 2
        rows = [
            ("good", (0,100,0)),       # dark green
            ("det", (218,165,32)),     # gold
            ("mask", (24,144,255)),    # blue
            ("ip", (146,84,222)),      # purple
            ("total", (82,196,26)),    # green
        ]
        # Build sets
        good = getattr(self, 'good_frames', set()) or set()
        dets = det_set
        masks = mask_set
        ips = inpaint_set
        # Map index to x
        def x_for_idx(i: int) -> int:
            return int(i * (w-1) / max(1, total-1))
        # Draw bars
        for r, (name, color) in enumerate(rows):
            y0 = r * (h_row + gap)
            for i in range(total):
                ok = False
                if name == 'good':
                    ok = (i in good)
                elif name == 'det':
                    ok = (i in dets)
                elif name == 'mask':
                    ok = (i in masks)
                elif name == 'ip':
                    ok = (i in ips)
                elif name == 'total':
                    ok = (i in good) or ((i in dets) and (i in masks) and (i in ips))
                x = x_for_idx(i)
                if ok:
                    canvas.create_line(x, y0, x, y0 + h_row - 1, fill="#%02x%02x%02x" % color)
                else:
                    canvas.create_line(x, y0, x, y0 + h_row - 1, fill="#000000")
        # Store for click mapping
        canvas.configure(height=len(rows)*(h_row+gap)-gap)

    def _on_timeline_click(self, event):
        if not self.reader:
            return
        total = max(1, int(self.reader.frame_count))
        w = max(100, self.timeline_canvas.winfo_width() or total)
        x = max(0, min(event.x, w-1))
        fi = int(round(x * (total-1) / max(1, w-1)))
        self.cur_frame_idx = fi
        self._read_and_show()

    def _make_mask_for_frame_or_saved(self, frame_index: int, frame_bgr: Optional[np.ndarray]) -> Optional[np.ndarray]:
        # Prefer saved mask
        if self.use_saved_data.get():
            m = self._load_saved_mask_for_frame(frame_index)
            if m is not None:
                return m
        # Skip computation for good frames
        if frame_index in self.good_frames:
            return np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
        return self._make_mask_for_frame(frame_bgr)

    # ---------- Good frames marking ----------
    def _good_frames_path(self) -> Optional[str]:
        root = self._output_root()
        if not root:
            return None
        return os.path.join(root, "good_frames.json")

    def _load_good_frames(self):
        self.good_frames.clear()
        p = self._good_frames_path()
        if p and os.path.isfile(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.good_frames = set(int(x) for x in data)
                print(f"[GOOD] Loaded {len(self.good_frames)} good frames")
            except Exception as e:
                print(f"[GOOD] Failed to load good frames: {e}")

    def _save_good_frames(self):
        p = self._good_frames_path()
        if not p:
            return
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(sorted(list(self.good_frames)), f)
        except Exception as e:
            print(f"[GOOD] Failed to save good frames: {e}")

    def on_right_click(self, event):
        # Map click to frame coords
        if not self.reader:
            return
        t0_all = time.time()
        scale = self.display_scale if self.display_scale > 0 else 1.0
        x_frame = int(event.x / scale)
        y_frame = int(event.y / scale)
        bb = self.last_preview_bbox
        if bb is not None:
            x, y, w, h = bb
            if x <= x_frame < x + w and y <= y_frame < y + h:
                # Remove matching detection(s) from detections.jsonl by overlap and append to bad_detections.jsonl
                detp = self._detections_jsonl_path()
                if detp and os.path.isfile(detp):
                    try:
                        t0 = time.time()
                        with open(detp, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        self.dlog(f"[BAD] read detections.jsonl took {(time.time()-t0)*1000:.1f} ms")
                        kept = []
                        removed_any = False
                        for ln in lines:
                            try:
                                d = json.loads(ln)
                                if int(d.get('frame', -1)) == self.cur_frame_idx:
                                    bb2 = d.get('bbox', [0,0,0,0])
                                    bb2t = (int(bb2[0]), int(bb2[1]), int(bb2[2]), int(bb2[3]))
                                    if self._iou(bb2t, bb) > 0.3:
                                        # Move to bad file
                                        self._append_bad_detection(self.cur_frame_idx, bb2t, d.get('score', None), d.get('template', ''), source="bad_click")
                                        removed_any = True
                                        continue
                                kept.append(ln)
                            except Exception:
                                kept.append(ln)
                        if removed_any:
                            t0 = time.time()
                            with open(detp, 'w', encoding='utf-8') as f:
                                f.writelines(kept)
                            self.dlog(f"[BAD] rewrite detections.jsonl took {(time.time()-t0)*1000:.1f} ms")
                            # Clear caches and reload
                            self.detections_cache.clear()
                            self._load_bad_detections_cache()
                            # Remove any saved mask for this frame so it won't be used
                            mp = self._mask_path_for_frame(self.cur_frame_idx)
                            if mp and os.path.isfile(mp):
                                try:
                                    t0 = time.time()
                                    os.remove(mp)
                                    self.dlog(f"[BAD] remove mask took {(time.time()-t0)*1000:.1f} ms")
                                    print(f"[BAD] Deleted saved mask for frame {self.cur_frame_idx}")
                                except Exception as e:
                                    print(f"[BAD] Failed to delete mask: {e}")
                            print(f"[BAD] Removed detection(s) at frame {self.cur_frame_idx} and recorded as bad.")
                            try:
                                self._update_progress_labels()
                            except Exception:
                                pass
                        else:
                            # If no record existed yet (live-only), still record as bad with the clicked bbox
                            self._append_bad_detection(self.cur_frame_idx, bb, None, "", source="bad_click")
                            print(f"[BAD] Marked live detection at frame {self.cur_frame_idx} as bad.")
                    except Exception as e:
                        print(f"[BAD] Failed to update bad detections: {e}")
                else:
                    # No detections file yet; just record bad
                    self._append_bad_detection(self.cur_frame_idx, bb, None, "", source="bad_click")
                    print(f"[BAD] Marked live detection at frame {self.cur_frame_idx} as bad.")
                try:
                    self._update_progress_labels()
                except Exception:
                    pass
                self._read_and_show()
        self.dlog(f"[BAD] right-click handler total took {(time.time()-t0_all)*1000:.1f} ms")

    # -------- Debug logging helper --------
    def dlog(self, msg: str):
        if self.debug_logging.get():
            try:
                print(msg)
            except Exception:
                pass

    def mark_current_frame_good(self):
        if not self.reader:
            print("[GOOD] Open a video first.")
            return
        fi = self.cur_frame_idx
        self.good_frames.add(fi)
        self._save_good_frames()
        # Remove any detections for this frame and mark them bad
        detp = self._detections_jsonl_path()
        if detp and os.path.isfile(detp):
            try:
                with open(detp, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                kept = []
                removed = 0
                for ln in lines:
                    try:
                        d = json.loads(ln)
                        if int(d.get('frame', -1)) == fi:
                            bb = d.get('bbox', [0,0,0,0])
                            try:
                                bb_t = (int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3]))
                            except Exception:
                                bb_t = (0,0,0,0)
                            self._append_bad_detection(fi, bb_t, d.get('score', None), d.get('template', ''), source="auto_good")
                            removed += 1
                            continue
                    except Exception:
                        pass
                    kept.append(ln)
                with open(detp, 'w', encoding='utf-8') as f:
                    f.writelines(kept)
                if removed:
                    print(f"[GOOD] Removed {removed} detection(s) at frame {fi} and recorded as bad.")
                # Invalidate cached detections memory
                try:
                    if fi in self.detections_cache:
                        del self.detections_cache[fi]
                except Exception:
                    self.detections_cache = {}
            except Exception as e:
                print(f"[GOOD] Failed to update detections: {e}")
        # Remove mask cache for this frame
        mp = self._mask_path_for_frame(fi)
        if mp and os.path.isfile(mp):
            try:
                os.remove(mp)
                print(f"[GOOD] Removed mask cache for frame {fi}.")
            except Exception as e:
                print(f"[GOOD] Failed to remove mask cache: {e}")
        print(f"[GOOD] Marked frame {fi} as good (skipped).")
        # Update progress and refresh preview quickly
        try:
            self._update_progress_labels()
        except Exception:
            pass

    def unmark_current_frame_good(self):
        if not self.reader:
            print("[GOOD] Open a video first.")
            return
        if self.cur_frame_idx in self.good_frames:
            self.good_frames.remove(self.cur_frame_idx)
            self._save_good_frames()
            print(f"[GOOD] Unmarked frame {self.cur_frame_idx}.")
        else:
            print(f"[GOOD] Frame {self.cur_frame_idx} was not marked.")
        # Avoid immediate preview refresh
        try:
            self._update_progress_labels()
        except Exception:
            pass

    # ---------- Guidance & Dataset ----------
    def toggle_guidance_mode(self):
        new_state = not self.guidance_mode.get()
        self.guidance_mode.set(new_state)
        if new_state:
            self.canvas.bind("<Button-1>", self.on_canvas_click)
            print("[GUIDE] Guidance mode enabled. Click on the video to set cursor position and save a crop.")
        else:
            self.canvas.unbind("<Button-1>")
            print("[GUIDE] Guidance mode disabled.")

    def set_dataset_folder(self):
        folder = filedialog.askdirectory(title="Select Dataset Folder")
        if not folder:
            return
        self.dataset_dir = folder
        self.dataset_path_var.set(folder)
        self._load_dataset_to_templates(folder)
        print(f"[GUIDE] Dataset folder set to: {folder}")

    def reload_dataset_from_path(self):
        path = self.dataset_path_var.get().strip()
        if not path:
            print("[DATASET] Enter a dataset path.")
            return
        self.dataset_dir = path
        self._load_dataset_to_templates(path)

    def on_canvas_click(self, event):
        if not self.reader or self.cur_frame is None:
            print("[GUIDE] Open a video first.")
            return
        # Map click using current display scale (no offsets as we avoid letterboxing)
        scale = self.display_scale if self.display_scale > 0 else 1.0
        # Ignore clicks outside the image area (based on scaled size)
        if event.x < 0 or event.y < 0:
            return
        if event.x > self.display_size[0] or event.y > self.display_size[1]:
            return
        x_frame = int(event.x / scale)
        y_frame = int(event.y / scale)
        self._apply_guidance(x_frame, y_frame)

    def _apply_guidance(self, x: int, y: int):
        H, W = (self.reader.h, self.reader.w) if self.reader else (0, 0)
        cw = max(8, int(self.crop_w.get()))
        ch = max(8, int(self.crop_h.get()))
        x0 = int(x - cw // 2)
        y0 = int(y - ch // 2)
        # Clamp bbox within frame
        x0 = max(0, min(x0, W - cw))
        y0 = max(0, min(y0, H - ch))
        bbox = (x0, y0, cw, ch)

        # Set detection for current frame
        det = DetectionResult(frame_index=self.cur_frame_idx, bbox=bbox, score=1.0, template_name="guided")
        self.last_detection = det
        # Also seed track at this frame
        self.tracks[self.cur_frame_idx] = TrackPoint(frame_index=self.cur_frame_idx, bbox=bbox, score=1.0)
        print(f"[GUIDE] Guided bbox at frame {self.cur_frame_idx}: {bbox}")

        # Store last guided bbox for explicit actions
        self.last_guided_bbox = bbox

        # Optionally auto-add/save based on current settings
        crop = self.cur_frame[y0:y0+ch, x0:x0+cw]
        if self.dataset_dir:
            self._save_crop_to_dataset(crop)
        if self.add_to_templates.get():
            self._add_crop_to_templates(crop)

        # Persist guided detection and mask immediately
        try:
            self._ensure_output_dirs()
            self._append_detection_jsonl_ex(det, self.cur_frame_idx, source="guided")
            # Build a mask for the guided bbox (trueform preferred)
            tf_mask = self._get_trueform_mask_for_bbox(bbox)
            if tf_mask is None:
                mask = create_mask_from_bbox((self.reader.h, self.reader.w), bbox, self.dilation.get())
            else:
                mask = np.zeros((self.reader.h, self.reader.w), dtype=np.uint8)
                xg, yg, wg, hg = bbox
                tf_resized = cv2.resize(tf_mask, (wg, hg), interpolation=cv2.INTER_NEAREST)
                mask[yg:yg+hg, xg:xg+wg] = (tf_resized > 0).astype(np.uint8) * 255
            mp = self._mask_path_for_frame(self.cur_frame_idx)
            if mp:
                cv2.imwrite(mp, mask)
            # Invalidate cached detections memory so preview can pick up
            self.detections_cache.clear()
            self._update_progress_labels()
            print("[GUIDE] Persisted guided detection and mask.")
        except Exception as e:
            print(f"[GUIDE] Failed to persist guided detection/mask: {e}")

        self._read_and_show()

    def _save_crop_to_dataset(self, crop: np.ndarray) -> Optional[str]:
        if self.dataset_dir is None:
            print("[GUIDE] Dataset folder not set.")
            return None
        ts = int(time.time()*1000)
        base = f"cursor_f{self.cur_frame_idx:06d}_w{crop.shape[1]}_h{crop.shape[0]}_{ts}"
        color_path = os.path.join(self.dataset_dir, base + ".png")
        ok = cv2.imwrite(color_path, crop)
        if ok:
            print(f"[GUIDE] Saved crop: {color_path}")
            return color_path
        else:
            print(f"[GUIDE] Failed to save crop: {color_path}")
            return None

    def _add_crop_to_templates(self, crop: np.ndarray) -> Optional[str]:
        # Keep templates and dataset unified: write to dataset and reload
        p = self._save_crop_to_dataset(crop)
        if p:
            self._load_dataset_to_templates(self.dataset_dir)
            return os.path.basename(p)
        return None

    def save_guided_crop(self):
        if not hasattr(self, 'last_guided_bbox') or self.cur_frame is None:
            print("[GUIDE] No guided bbox yet. Use Guide Cursor and click on the video.")
            return
        x0, y0, w, h = self.last_guided_bbox
        crop = self.cur_frame[y0:y0+h, x0:x0+w]
        self._save_crop_to_dataset(crop)

    def add_guided_crop_to_templates(self):
        if not hasattr(self, 'last_guided_bbox') or self.cur_frame is None:
            print("[GUIDE] No guided bbox yet. Use Guide Cursor and click on the video.")
            return
        x0, y0, w, h = self.last_guided_bbox
        crop = self.cur_frame[y0:y0+h, x0:x0+w]
        self._add_crop_to_templates(crop)

    # ---------- Preset / Trueform ----------
    def _ensure_preset(self, name: str):
        if name not in self.presets:
            self.presets[name] = []

    def add_guided_crop_to_preset(self):
        name = self.active_preset.get().strip()
        if not name:
            print("[PRESET] Enter a preset name first.")
            return
        if not hasattr(self, 'last_guided_bbox') or self.cur_frame is None:
            print("[PRESET] No guided bbox yet. Use Guide Cursor and click on the video.")
            return
        x0, y0, w, h = self.last_guided_bbox
        crop = self.cur_frame[y0:y0+h, x0:x0+w].copy()
        self._ensure_preset(name)
        self.presets[name].append(crop)
        print(f"[PRESET] Added crop to preset '{name}'. Total: {len(self.presets[name])}")

    def build_trueform_for_active(self):
        name = self.active_preset.get().strip()
        if not name:
            print("[PRESET] Enter a preset name first.")
            return
        if not self.dataset_dir:
            print("[PRESET] Set Dataset Folder first. Trueform builds from all images in that folder.")
            return
        crops = self._load_crops_from_dataset()
        if len(crops) < 2:
            print(f"[PRESET] Need at least 2 images in dataset folder to build trueform. Found {len(crops)}")
            return
        # Cluster by orientation bins to separate shape variants (e.g., right/up/down)
        bins: Dict[str, List[np.ndarray]] = { 'right': [], 'down': [], 'left': [], 'up': [] }
        for img in crops:
            bin_name = self._compute_orientation_bin(img)
            bins[bin_name].append(img)
        built_any = False
        for bin_name, bin_crops in bins.items():
            if len(bin_crops) < 2:
                continue
            print(f"[PRESET] Building trueform for bin '{bin_name}' with {len(bin_crops)} images...")
            median_img, mask = self._compute_trueform_enhanced(bin_crops)
            # Refine mask with GrabCut using median as image prior
            mask = self._refine_mask_grabcut(median_img, mask)
            # Crop to mask bounding box for a tight trueform
            ys, xs = np.where(mask > 0)
            if len(xs) > 0 and len(ys) > 0:
                x0, x1 = xs.min(), xs.max()+1
                y0, y1 = ys.min(), ys.max()+1
                median_img = median_img[y0:y1, x0:x1]
                mask = mask[y0:y1, x0:x1]
            key = f"{name}_{bin_name}"
            self.trueforms[key] = { 'median': median_img, 'mask': mask }
            out_path = self._save_trueform_rgba(key, median_img, mask)
            if out_path:
                print(f"[PRESET] Saved trueform: {out_path}")
                built_any = True
        if not built_any:
            print("[PRESET] Not enough images per orientation bin to build any trueforms. Collect more varied samples.")

    def _compute_trueform_enhanced(self, crops: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        # Determine reference size (median) and align all crops to first reference using ECC
        hs = [c.shape[0] for c in crops]
        ws = [c.shape[1] for c in crops]
        H = int(np.median(hs))
        W = int(np.median(ws))
        ref = cv2.resize(crops[0], (W, H), interpolation=cv2.INTER_AREA)
        aligned = [self._align_to_reference(ref, cv2.resize(c, (W, H), interpolation=cv2.INTER_AREA)) for c in crops]
        stack = np.stack(aligned, axis=0).astype(np.float32)  # N,H,W,3
        # Median image
        median_img = np.median(stack, axis=0).astype(np.uint8)
        # Robust variation (MAD) per pixel
        med = np.median(stack, axis=0)
        mad = np.median(np.abs(stack - med), axis=0)
        mad_gray = np.mean(mad, axis=2)
        # Edge consensus
        edges = []
        for img in aligned:
            gray = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2GRAY)
            e = cv2.Canny(gray, 50, 150)
            edges.append((e > 0).astype(np.float32))
        edge_sum = np.sum(np.stack(edges, axis=0), axis=0)  # H,W
        edge_consensus = edge_sum / max(1, len(edges))
        # Normalize MAD via robust scaling
        q1, q3 = np.percentile(mad_gray, [25, 75])
        iqr = max(1e-6, q3 - q1)
        mad_norm = np.clip((mad_gray - q1) / iqr, 0, 3.0) / 3.0  # 0..1
        # Combine: prefer low MAD (stable across samples) and high edge consensus (consistent edges)
        prob = (1.0 - mad_norm) * (edge_consensus ** 0.7)
        # Threshold adaptively
        thr = max(0.2, np.percentile(prob, 70) * 0.7)
        mask = (prob > thr).astype(np.uint8) * 255
        # Cleanup
        mask = cv2.medianBlur(mask, 3)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return median_img, mask

    def _get_trueform_mask_for_bbox(self, bbox: Tuple[int,int,int,int]) -> Optional[np.ndarray]:
        if not self.use_trueform_mask.get():
            return None
        name = self.active_preset.get().strip()
        if not name:
            return None
        # Try exact preset match first
        if name in self.trueforms:
            return self.trueforms[name]['mask']
        # Otherwise select the variant that best matches current frame crop via template matching
        return self._select_best_trueform_by_match(name, bbox)

    def _compute_orientation_bin(self, img: np.ndarray) -> str:
        # Use edge orientation via PCA to determine primary direction, map to bins
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        e = cv2.Canny(gray, 50, 150)
        ys, xs = np.where(e > 0)
        if len(xs) < 50:
            return 'right'  # default
        pts = np.column_stack((xs, ys)).astype(np.float32)
        pts -= pts.mean(axis=0)
        cov = np.cov(pts, rowvar=False)
        eigvals, eigvecs = np.linalg.eig(cov)
        v = eigvecs[:, np.argmax(eigvals)]
        angle = np.degrees(np.arctan2(v[1], v[0])) % 180.0
        # Map angle to bins
        if 315 <= angle or angle < 45:
            return 'right'
        elif 45 <= angle < 135:
            return 'down'
        elif 135 <= angle < 225:
            return 'left'
        else:
            return 'up'

    def _align_to_reference(self, ref: np.ndarray, img: np.ndarray) -> np.ndarray:
        # Robust ECC alignment with fallbacks and normalization to avoid NaNs.
        ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Normalize to [0,1] float32 and blur slightly to reduce noise
        ref_f = cv2.GaussianBlur(ref_gray, (3,3), 0).astype(np.float32) / 255.0
        img_f = cv2.GaussianBlur(img_gray, (3,3), 0).astype(np.float32) / 255.0
        # Replace any NaNs/Infs just in case
        ref_f = np.nan_to_num(ref_f, nan=0.0, posinf=1.0, neginf=0.0)
        img_f = np.nan_to_num(img_f, nan=0.0, posinf=1.0, neginf=0.0)
        # Try Euclidean first, then translation
        for warp_mode in (cv2.MOTION_EUCLIDEAN, cv2.MOTION_TRANSLATION):
            warp_matrix = np.eye(2, 3, dtype=np.float32)
            try:
                criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 150, 1e-6)
                cc, warp_matrix = cv2.findTransformECC(ref_f, img_f, warp_matrix, warp_mode, criteria)
                if not np.isfinite(warp_matrix).all():
                    raise ValueError("warp_matrix not finite")
                aligned = cv2.warpAffine(img, warp_matrix, (ref.shape[1], ref.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
                return aligned
            except Exception as e:
                print(f"[PRESET] ECC alignment failed ({'EUCLIDEAN' if warp_mode==cv2.MOTION_EUCLIDEAN else 'TRANSLATION'}): {e}")
                continue
        # Fallback: return original resized image if alignment fails
        return img

    def harvest_samples_from_video(self):
        if not self.reader or self.cur_frame is None:
            print("[HARVEST] Open a video and move to a frame to start harvesting.")
            return
        if not self.dataset_dir:
            print("[HARVEST] Set Dataset Folder first.")
            return
        if not self.templates:
            print("[HARVEST] Load a templates folder first to enable detection-based harvesting.")
            return
        max_per_bin = 200
        step = 3  # sample every N frames for speed
        saved = 0
        print(f"[HARVEST] Scanning frames every {step} frames for detections (threshold={float(self.threshold.get()):.2f})...")
        for fi in range(0, self.reader.frame_count, step):
            frame = self.reader.read_frame(fi)
            if frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            det = self.matcher.detect(gray, threshold=float(self.threshold.get()))
            if det is None:
                continue
            x, y, w, h = det.bbox
            # Pad slightly
            pad = int(0.1 * max(w, h))
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(self.reader.w, x + w + pad)
            y1 = min(self.reader.h, y + h + pad)
            crop = frame[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            self._save_crop_to_dataset(crop)
            saved += 1
            if saved % 25 == 0:
                print(f"[HARVEST] Saved {saved} crops so far...")
            if saved >= max_per_bin:
                break
        print(f"[HARVEST] Done. Saved {saved} crops to dataset: {self.dataset_dir}")

    def _refine_mask_grabcut(self, image_bgr: np.ndarray, init_mask: np.ndarray) -> np.ndarray:
        # Prepare GrabCut mask
        h, w = init_mask.shape[:2]
        gc_mask = np.full((h, w), cv2.GC_PR_BGD, dtype=np.uint8)
        gc_mask[init_mask > 0] = cv2.GC_PR_FGD
        # Seed a confident fg core by eroding
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        core = cv2.erode((init_mask > 0).astype(np.uint8), kernel, iterations=1)
        gc_mask[core > 0] = cv2.GC_FGD
        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(image_bgr, gc_mask, None, bgdModel, fgdModel, 3, cv2.GC_INIT_WITH_MASK)
            refined = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
            refined = cv2.morphologyEx(refined, cv2.MORPH_OPEN, kernel, iterations=1)
            refined = cv2.morphologyEx(refined, cv2.MORPH_CLOSE, kernel, iterations=1)
            return refined
        except Exception as e:
            print(f"[PRESET] GrabCut refinement failed: {e}")
            return init_mask

    def _select_best_trueform_by_match(self, base_name: str, bbox: Tuple[int,int,int,int]) -> Optional[np.ndarray]:
        if self.cur_frame is None:
            return None
        x, y, w, h = bbox
        crop = self.cur_frame[y:y+h, x:x+w]
        if crop.size == 0:
            return None
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        best_score = -1.0
        best_mask = None
        for key, data in self.trueforms.items():
            if not (key == base_name or key.startswith(base_name + "_")):
                continue
            median = data['median']
            mask = data['mask']
            if median is None or mask is None:
                continue
            med_gray = cv2.cvtColor(median, cv2.COLOR_BGR2GRAY)
            med_resized = cv2.resize(med_gray, (w, h), interpolation=cv2.INTER_AREA)
            # Use normalized cross-correlation
            try:
                res = cv2.matchTemplate(crop_gray, med_resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = max_val
                    best_mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
            except Exception as e:
                continue
        return best_mask

    def _load_crops_from_dataset(self) -> List[np.ndarray]:
        crops: List[np.ndarray] = []
        if not self.dataset_dir:
            return crops
        patterns = ["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"]
        files: List[str] = []
        for pat in patterns:
            files.extend(glob.glob(os.path.join(self.dataset_dir, pat)))
        if not files:
            print(f"[PRESET] No images found in dataset folder: {self.dataset_dir}")
            return crops
        for fp in files:
            img = cv2.imread(fp, cv2.IMREAD_COLOR)
            if img is None:
                print(f"[PRESET] Failed to read: {fp}")
                continue
            crops.append(img)
        print(f"[PRESET] Loaded {len(crops)} images from dataset for trueform build.")
        return crops

    def _save_trueform_rgba(self, name: str, median_img_bgr: np.ndarray, mask: np.ndarray) -> Optional[str]:
        if self.dataset_dir is None:
            return None
        # Ensure output dir
        out_dir = os.path.join(self.dataset_dir, "trueforms")
        os.makedirs(out_dir, exist_ok=True)
        # Convert BGR to RGBA
        rgb = cv2.cvtColor(median_img_bgr, cv2.COLOR_BGR2RGB)
        alpha = (mask > 0).astype(np.uint8) * 255
        rgba = np.dstack([rgb, alpha])
        out_path = os.path.join(out_dir, f"{name}_trueform.png")
        # cv2.imwrite expects BGR(A); convert back to BGRA
        bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        ok = cv2.imwrite(out_path, bgra)
        return out_path if ok else None

    def _load_dataset_to_templates(self, folder: str):
        self.templates.clear()
        count = 0
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"):
            for p in glob.glob(os.path.join(folder, ext)):
                name = os.path.basename(p)
                img = imread_grayscale(p)
                if img is None:
                    continue
                self.templates[name] = img
                count += 1
        print(f"[DATASET] Loaded {count} images from {folder} into templates.")
        # Refresh CPU matcher cache
        try:
            self.matcher.refresh_templates(self.templates)
        except Exception:
            pass
        # Refresh GPU templates if enabled
        if self.use_gpu.get():
            if self.gpu_matcher is None:
                self.gpu_matcher = GpuTemplateMatcher(self.templates, scales=self.scales)
            else:
                self.gpu_matcher.refresh_templates(self.templates)

    def _toggle_gpu(self):
        enabled = self.use_gpu.get()
        if enabled and (self.gpu_matcher is None):
            self.gpu_matcher = GpuTemplateMatcher(self.templates, scales=self.scales)
            if not self.gpu_matcher.device_ok:
                print("[GPU] CUDA not available; falling back to CPU.")
                self.use_gpu.set(False)
                self.gpu_matcher = None
            else:
                print("[GPU] Enabled CUDA template matching.")
        elif not enabled:
            self.gpu_matcher = None
            print("[GPU] Disabled; using CPU.")

    def _setup_theme(self):
 
        self.root.configure(bg=UI_BG)
        style = ttk.Style(self.root)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure("Dark.TFrame", background=PANEL_BG)
        style.configure("Dark.TLabelframe", background=PANEL_BG, foreground=TEXT_FG)
        style.configure("Dark.TLabel", background=PANEL_BG, foreground=TEXT_FG)
        style.configure("Dark.TCheckbutton", background=PANEL_BG, foreground=TEXT_FG)
        # Buttons
        style.configure("Blue.TButton", background="#224b7b", foreground=TEXT_FG)
        style.map("Blue.TButton", background=[('active', '#2b5d9a')])
        style.configure("Green.TButton", background="#275e2a", foreground=TEXT_FG)
        style.map("Green.TButton", background=[('active', '#2f7a34')])
        style.configure("Purple.TButton", background="#4b2a7b", foreground=TEXT_FG)
        style.map("Purple.TButton", background=[('active', '#5e379c')])

    def _section(self, parent, title: str, color: str) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Dark.TFrame")
        header = tk.Label(frame, text=title, bg=PANEL_BG, fg=color, font=HEADER_FONT)
        header.pack(side=tk.TOP, padx=6, pady=(6, 1))
        return frame

def main():
    root = tk.Tk()

    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    app = VideoCursorRemovalApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

