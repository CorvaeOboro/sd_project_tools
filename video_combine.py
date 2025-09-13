"""
VIDEO COMBINER
using ffmepg quickly combine videos in a timeline 
- increase speed , fix generated videos unfavorable slow motion
- first frame clipping range , this is useful for img2vid to remove the bad "warmup" starting to move or shifting lighting
"""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from tqdm import tqdm

# ---------------------------------------------------------------
# Utility class to redirect tqdm output into the Tkinter text widget.
class TqdmToText:
    def __init__(self, widget):
        self.widget = widget

    def write(self, s):
        if s.strip():
            self.widget.after(0, lambda: (self.widget.insert("end", s), self.widget.see("end")))
    def flush(self):
        pass

# ---------------------------------------------------------------
# Helper function to check if a video file has an audio stream.
def has_audio(input_file, ffmpeg_path):
    # Try to locate ffprobe alongside ffmpeg.
    if "ffmpeg.exe" in ffmpeg_path.lower():
        ffprobe_path = ffmpeg_path.lower().replace("ffmpeg.exe", "ffprobe.exe")
    else:
        ffprobe_path = "ffprobe"
    command = [
        ffprobe_path,
        '-v', 'error',
        '-select_streams', 'a',
        '-show_entries', 'stream=codec_type',
        '-of', 'csv=p=0',
        input_file
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return bool(result.stdout.strip())

# ---------------------------------------------------------------
# Video processing functions that use settings from the UI

def speed_up_video(input_file, output_file, speed_factor, settings, log):
    video_filter = f"setpts=PTS/{speed_factor}"
    
    def build_atempo_chain(factor):
        chain = []
        # atempo only accepts values between 0.5 and 2.0; chain if needed.
        while factor > 2.0:
            chain.append("atempo=2.0")
            factor /= 2.0
        while factor < 0.5:
            chain.append("atempo=0.5")
            factor /= 0.5
        chain.append(f"atempo={factor:.2f}")
        return ",".join(chain)
    
    log("Speeding up video...")
    if has_audio(input_file, settings["ffmpeg_path"]):
        audio_filter = build_atempo_chain(speed_factor)
        filter_complex = f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]"
        command = [
            settings["ffmpeg_path"],
            '-i', input_file,
            '-filter_complex', filter_complex,
            '-map', "[v]",
            '-map', "[a]",
            '-r', settings["frame_rate"],
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-ar', '44100',
            '-ac', '2',
            '-b:a', '128k',
            output_file
        ]
    else:
        # No audio: process only video.
        filter_complex = f"[0:v]{video_filter}[v]"
        command = [
            settings["ffmpeg_path"],
            '-i', input_file,
            '-filter_complex', filter_complex,
            '-map', "[v]",
            '-r', settings["frame_rate"],
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            output_file
        ]
    subprocess.run(command, shell=True)
    log("Finished speeding up video.")

def process_videos(input_folder, settings, log, progress, log_widget):
    temp_folder = "./temp/"
    intermediate_file = "combined_video.mp4"
    final_output_file = "final_video.mp4"
    os.makedirs(temp_folder, exist_ok=True)
    
    video_files = [f for f in os.listdir(input_folder)
                   if f.lower().endswith(('.mp4', '.avi', '.mov'))]
    if not video_files:
        log("No video files found in the selected folder.")
        return
    
    total_steps = len(video_files) + 2  # conversion for each + combine + (optional) speed-up
    current_progress = 0
    tqdm_out = TqdmToText(log_widget)
    log(f"Starting conversion of {len(video_files)} videos...")
    
    # --- Convert videos ---
    for video in tqdm(video_files, desc="Converting videos", file=tqdm_out):
        input_path = os.path.join(input_folder, video)
        output_path = os.path.join(temp_folder, video)
        
        # Build filter chain: remove initial frames if requested,
        # then scale to fit (preserving aspect ratio) and pad with black.
        filter_chain = ""
        if settings["remove_first_frames"] and int(settings["frames_to_remove"]) > 0:
            filter_chain += f"select='gte(n,{settings['frames_to_remove']})',setpts=PTS-STARTPTS,"
        filter_chain += (
            f"scale={settings['video_width']}:{settings['video_height']}:force_original_aspect_ratio=decrease,"
            f"pad={settings['video_width']}:{settings['video_height']}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
        
        command = [
            settings["ffmpeg_path"],
            '-fflags', '+genpts',
            '-i', input_path,
            '-vf', filter_chain,
            '-r', settings["frame_rate"],
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            # Force audio re-encoding:
            '-c:a', 'aac',
            '-ar', '44100',
            '-ac', '2',
            '-b:a', '128k',
            output_path
        ]
        log(f"Converting {video} ...")
        subprocess.run(command, shell=True)
        log(f"Finished converting {video}.")
        
        current_progress += (100 / total_steps)
        progress(current_progress)
    
    # --- Combine videos ---
    log("Combining videos...")
    list_filename = "file_list.txt"
    with open(list_filename, "w") as file_list:
        for video in os.listdir(temp_folder):
            file_list.write(f"file '{os.path.join(temp_folder, video)}'\n")
    
    command = [
        settings["ffmpeg_path"],
        '-f', 'concat',
        '-safe', '0',
        '-i', list_filename,
        '-c:v', 'libx264',
        '-crf', settings["crf"],
        '-preset', 'medium',
        '-r', settings["frame_rate"],
        # Re-encode audio consistently:
        '-c:a', 'aac',
        '-ar', '44100',
        '-ac', '2',
        '-b:a', '128k',
        intermediate_file
    ]
    subprocess.run(command, shell=True)
    os.remove(list_filename)
    current_progress += (100 / total_steps)
    progress(current_progress)
    log("Finished combining videos.")
    
    # --- Speed-up (if requested) ---
    if float(settings["speed_up_factor"]) != 1.0:
        log("Speeding up video...")
        speed_up_video(intermediate_file, final_output_file, float(settings["speed_up_factor"]), settings, log)
        os.remove(intermediate_file)
        current_progress += (100 / total_steps)
        progress(current_progress)
    else:
        final_output_file = intermediate_file

    # --- Clean up temporary files ---
    for f in os.listdir(temp_folder):
        os.remove(os.path.join(temp_folder, f))
    os.rmdir(temp_folder)
    
    log("Processing complete!")
    log("Final video saved as: " + final_output_file)

# ---------------------------------------------------------------
# Tkinter UI code with dark mode styling

def log_message(msg):
    """Append a message to the log text widget in a thread-safe way."""
    log_widget.after(0, lambda: (log_widget.insert("end", msg + "\n"),
                                   log_widget.see("end")))

def update_progress(val):
    """Set the progress bar to a given value (0 to 100)."""
    progress_bar.after(0, lambda: progress_bar.config(value=val))

def process_videos_thread(folder, settings):
    process_videos(folder, settings, log_message, update_progress, log_widget)
    start_button.config(state="normal")  # Re-enable the start button when done

def start_processing():
    folder = folder_entry.get()
    if not folder:
        log_message("Please select an input folder.")
        return
    
    # Gather global settings from UI inputs
    settings = {
        "ffmpeg_path": ffmpeg_path_entry.get(),
        "video_width": video_width_entry.get(),
        "video_height": video_height_entry.get(),
        "frame_rate": frame_rate_entry.get(),
        "crf": crf_entry.get(),
        "remove_first_frames": remove_first_frames_var.get(),
        "frames_to_remove": frames_to_remove_entry.get(),
        "speed_up_factor": speed_up_factor_entry.get()
    }
    
    start_button.config(state="disabled")
    threading.Thread(target=process_videos_thread, args=(folder, settings), daemon=True).start()

def browse_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        folder_entry.delete(0, tk.END)
        folder_entry.insert(0, folder_selected)

def browse_ffmpeg():
    file_selected = filedialog.askopenfilename(filetypes=[("FFmpeg executable", "*.exe")])
    if file_selected:
        ffmpeg_path_entry.delete(0, tk.END)
        ffmpeg_path_entry.insert(0, file_selected)

# Build the main window
root = tk.Tk()
root.title("Video Combiner Tool")

# Set overall dark mode colors
DARK_BG = "#2e2e2e"
DARK_FG = "#ffffff"
ACCENT_BG = "#3e3e3e"

root.configure(bg=DARK_BG)

# Configure ttk style for dark mode
style = ttk.Style(root)
style.theme_use("clam")
style.configure("TLabel", background=DARK_BG, foreground=DARK_FG)
style.configure("TButton", background=ACCENT_BG, foreground=DARK_FG)
style.configure("TEntry", fieldbackground=ACCENT_BG, foreground=DARK_FG)
style.configure("TCheckbutton", background=DARK_BG, foreground=DARK_FG)
style.configure("TLabelframe", background=DARK_BG, foreground=DARK_FG)
style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_FG)
style.configure("Horizontal.TProgressbar", background=ACCENT_BG)

# --- Global Settings Frame ---
settings_frame = ttk.LabelFrame(root, text="Global Settings")
settings_frame.pack(padx=10, pady=5, fill="x")
settings_frame.configure(style="TLabelframe")

# FFMPEG Path
ffmpeg_path_label = ttk.Label(settings_frame, text="FFmpeg Path:")
ffmpeg_path_label.grid(row=0, column=0, sticky="e", padx=5, pady=2)
ffmpeg_path_entry = ttk.Entry(settings_frame, width=50)
ffmpeg_path_entry.insert(0, "c:/tools/ffmpeg.exe")
ffmpeg_path_entry.grid(row=0, column=1, padx=5, pady=2)
ffmpeg_browse_button = ttk.Button(settings_frame, text="Browse", command=browse_ffmpeg)
ffmpeg_browse_button.grid(row=0, column=2, padx=5, pady=2)

# Video Width
video_width_label = ttk.Label(settings_frame, text="Video Width:")
video_width_label.grid(row=1, column=0, sticky="e", padx=5, pady=2)
video_width_entry = ttk.Entry(settings_frame, width=10)
video_width_entry.insert(0, "1920")
video_width_entry.grid(row=1, column=1, sticky="w", padx=5, pady=2)

# Video Height
video_height_label = ttk.Label(settings_frame, text="Video Height:")
video_height_label.grid(row=2, column=0, sticky="e", padx=5, pady=2)
video_height_entry = ttk.Entry(settings_frame, width=10)
video_height_entry.insert(0, "1280")
video_height_entry.grid(row=2, column=1, sticky="w", padx=5, pady=2)

# Frame Rate
frame_rate_label = ttk.Label(settings_frame, text="Frame Rate:")
frame_rate_label.grid(row=3, column=0, sticky="e", padx=5, pady=2)
frame_rate_entry = ttk.Entry(settings_frame, width=10)
frame_rate_entry.insert(0, "30")
frame_rate_entry.grid(row=3, column=1, sticky="w", padx=5, pady=2)

# CRF
crf_label = ttk.Label(settings_frame, text="CRF:")
crf_label.grid(row=4, column=0, sticky="e", padx=5, pady=2)
crf_entry = ttk.Entry(settings_frame, width=10)
crf_entry.insert(0, "21")
crf_entry.grid(row=4, column=1, sticky="w", padx=5, pady=2)

# Remove First Frames Checkbox
remove_first_frames_var = tk.BooleanVar()
remove_first_frames_var.set(True)
remove_first_frames_check = ttk.Checkbutton(settings_frame, text="Remove First Frames", variable=remove_first_frames_var)
remove_first_frames_check.grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=2)

# Frames to Remove
frames_to_remove_label = ttk.Label(settings_frame, text="Frames to Remove:")
frames_to_remove_label.grid(row=6, column=0, sticky="e", padx=5, pady=2)
frames_to_remove_entry = ttk.Entry(settings_frame, width=10)
frames_to_remove_entry.insert(0, "10")
frames_to_remove_entry.grid(row=6, column=1, sticky="w", padx=5, pady=2)

# Speed Up Factor
speed_up_factor_label = ttk.Label(settings_frame, text="Speed Up Factor:")
speed_up_factor_label.grid(row=7, column=0, sticky="e", padx=5, pady=2)
speed_up_factor_entry = ttk.Entry(settings_frame, width=10)
speed_up_factor_entry.insert(0, "1.0")
speed_up_factor_entry.grid(row=7, column=1, sticky="w", padx=5, pady=2)

# --- Folder selection for input videos ---
folder_frame = tk.Frame(root, bg=DARK_BG)
folder_frame.pack(pady=10, padx=10, fill="x")
folder_label = tk.Label(folder_frame, text="Input Folder:", bg=DARK_BG, fg=DARK_FG)
folder_label.pack(side="left", padx=5)
folder_entry = ttk.Entry(folder_frame, width=50)
folder_entry.pack(side="left", padx=5)
browse_button = ttk.Button(folder_frame, text="Browse", command=browse_folder)
browse_button.pack(side="left", padx=5)

# --- Start button ---
start_button = ttk.Button(root, text="Start Processing", command=start_processing)
start_button.pack(pady=10)

# --- Progress bar ---
progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate", style="Horizontal.TProgressbar")
progress_bar.pack(pady=10)
progress_bar["maximum"] = 100

# --- Log output (with scrollbar) ---
log_frame = tk.Frame(root, bg=DARK_BG)
log_frame.pack(padx=10, pady=10, fill="both", expand=True)
log_widget = tk.Text(log_frame, height=15, bg=ACCENT_BG, fg=DARK_FG, insertbackground=DARK_FG)
log_widget.pack(side="left", fill="both", expand=True)
scrollbar = tk.Scrollbar(log_frame, command=log_widget.yview, bg=DARK_BG)
scrollbar.pack(side="right", fill="y")
log_widget.config(yscrollcommand=scrollbar.set)

# Start the GUI event loop
root.mainloop()
