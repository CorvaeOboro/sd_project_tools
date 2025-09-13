"""
Audio Batch Extractor

- Extracts audio clips from many multimedia files (any format, e.g., .mkv .mp4 .mp3 .wav .flac)
- Removes silence gaps
- Concatenates all audio sections with 0.1s gaps
- Normalizes loudness across sections

Usage:
    python video_audio_batch_processor.py <video1> <video2> ...
    # If no arguments, launches GUI

VERSION::20250906    
"""

import os
import sys
import tempfile
import subprocess
import glob
from typing import List
from pydub import AudioSegment, silence, effects
import numpy as np
import soundfile as sf
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tqdm import tqdm

# --- Audio Processing Core ---

FFMPEG_PATH = "ffmpeg"  # Assumes ffmpeg is in PATH
OUTPUT_WAV = "output_final.wav"
DEFAULT_SILENCE_THRESH = -40  # dBFS
MIN_SILENCE_LEN = 500  # ms
GAP_BETWEEN_SECTIONS_MS = 100


def extract_audio_to_wav(video_path: str, wav_path: str):
    """Extracts audio from video using ffmpeg and saves as WAV."""
    cmd = [
        FFMPEG_PATH, '-y', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '1', wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def split_and_remove_silence(audio: AudioSegment, silence_thresh: int) -> List[AudioSegment]:
    """Splits audio into non-silent chunks."""
    chunks = silence.split_on_silence(
        audio,
        min_silence_len=MIN_SILENCE_LEN,
        silence_thresh=silence_thresh,
        keep_silence=0
    )
    return chunks

def apply_fade_to_chunks(chunks: List[AudioSegment], fade_ms: int) -> List[AudioSegment]:
    """Apply short fade in/out to each chunk."""
    if fade_ms <= 0:
        return chunks
    faded = []
    for c in chunks:
        dur = len(c)
        fade_amt = min(fade_ms, dur // 2)
        faded.append(c.fade_in(fade_amt).fade_out(fade_amt))
    return faded

def match_target_amplitude(chunk: AudioSegment, target_dBFS: float) -> AudioSegment:
    """Normalize chunk to target dBFS."""
    change_in_dBFS = target_dBFS - chunk.dBFS
    return chunk.apply_gain(change_in_dBFS)

def normalize_chunks(chunks: List[AudioSegment]) -> List[AudioSegment]:
    """Normalize all chunks to the same loudness."""
    # Compute average loudness
    dBFS_vals = [c.dBFS for c in chunks if c.dBFS != float('-inf')]
    target_dBFS = np.median(dBFS_vals) if dBFS_vals else -20
    return [match_target_amplitude(c, target_dBFS) for c in chunks]

def concatenate_chunks(chunks: List[AudioSegment], gap_ms: int) -> AudioSegment:
    """Concatenate chunks with specified gap."""
    gap = AudioSegment.silent(duration=gap_ms)
    output = AudioSegment.empty()
    for i, c in enumerate(chunks):
        output += c
        if i < len(chunks) - 1:
            output += gap
    return output

def process_videos(video_files: List[str], output_path: str = OUTPUT_WAV, log_callback=None, fade_ms: int = 20, silence_thresh: int = DEFAULT_SILENCE_THRESH):
    temp_dir = tempfile.mkdtemp()
    all_chunks = []
    for vid in tqdm(video_files, desc="Processing videos"):
        wav_path = os.path.join(temp_dir, os.path.splitext(os.path.basename(vid))[0] + ".wav")
        if log_callback:
            log_callback(f"Extracting audio from {vid}...")
        extract_audio_to_wav(vid, wav_path)
        audio = AudioSegment.from_wav(wav_path)
        if log_callback:
            log_callback(f"Removing silence from {wav_path} (threshold {silence_thresh} dBFS)...")
        chunks = split_and_remove_silence(audio, silence_thresh)
        if log_callback:
            log_callback(f"Found {len(chunks)} audio sections.")
        # Apply fade in/out to each chunk
        chunks = apply_fade_to_chunks(chunks, fade_ms)
        all_chunks.extend(chunks)
    if log_callback:
        log_callback(f"Normalizing volume across {len(all_chunks)} sections...")
    all_chunks = normalize_chunks(all_chunks)
    if log_callback:
        log_callback(f"Concatenating all sections with {GAP_BETWEEN_SECTIONS_MS}ms gaps...")
    final_audio = concatenate_chunks(all_chunks, GAP_BETWEEN_SECTIONS_MS)
    final_audio.export(output_path, format="wav")
    if log_callback:
        log_callback(f"Saved output to {output_path}")

# --- CLI Entry Point ---

import datetime

def main_cli():
    import argparse
    parser = argparse.ArgumentParser(description="Batch process video audio, remove silence, normalize, and concatenate.")
    parser.add_argument('videos', nargs='*', help='Input video files')
    parser.add_argument('--fade', type=int, default=20, help='Fade in/out (ms) per section')
    parser.add_argument('--silence-thresh', type=int, default=DEFAULT_SILENCE_THRESH, help='Silence threshold in dBFS (default -40)')
    args = parser.parse_args()
    video_files = args.videos
    if not video_files:
        launch_gui()
        return
    # Determine output folder and name
    if len(video_files) == 0:
        print("No input files provided.")
        return
    # Use the parent folder of the first file
    folder = os.path.dirname(video_files[0])
    folder_name = os.path.basename(folder.rstrip("/\\"))
    dt_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    out_name = f"{folder_name}_{dt_str}.wav"
    out_path = os.path.join(folder, out_name)
    process_videos(video_files, out_path, fade_ms=args.fade, silence_thresh=args.silence_thresh)

# --- Tkinter GUI ---

class VideoAudioBatchGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Audio Batch Processor")
        self.root.geometry("650x420")
        self.root.configure(bg="#23272e")
        self.video_files = []
        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", background="#2d333b", foreground="#fafbfc", font=("Segoe UI", 11, "bold"))
        style.configure("TLabel", background="#23272e", foreground="#fafbfc", font=("Segoe UI", 10))
        style.configure("TFrame", background="#23272e")
        style.configure("TProgressbar", background="#7289da", troughcolor="#2d333b", bordercolor="#23272e")

        frm = ttk.Frame(self.root)
        frm.pack(fill="both", expand=True, padx=18, pady=18)

        self.start_btn = ttk.Button(frm, text="Start Processing", command=self.start_processing)
        self.start_btn.pack(pady=(0, 18), anchor="n")

        self.label = ttk.Label(frm, text="Select video files to process:")
        self.label.pack(anchor="w")

        self.file_listbox = tk.Listbox(frm, bg="#181a20", fg="#fafbfc", selectbackground="#7289da", font=("Consolas", 10), height=7)
        self.file_listbox.pack(fill="x", pady=8)

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill="x")
        self.add_btn = ttk.Button(btn_frame, text="Add Files", command=self.add_files)
        self.add_btn.pack(side="left", padx=(0, 8))
        self.clear_btn = ttk.Button(btn_frame, text="Clear List", command=self.clear_files)
        self.clear_btn.pack(side="left")

        # Output filename is now automatic and shown as a label
        self.out_label = ttk.Label(frm, text="Output WAV will be saved in the input folder with a timestamped name.")
        self.out_label.pack(anchor="w", pady=(14,0))
        self.out_name_var = tk.StringVar()
        self.out_name_label = ttk.Label(frm, textvariable=self.out_name_var, font=("Consolas", 10, "italic"))
        self.out_name_label.pack(anchor="w")

        self.progress = ttk.Progressbar(frm, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=(16, 0))

        fade_row = ttk.Frame(frm)
        fade_row.pack(fill="x", pady=(8,0))
        ttk.Label(fade_row, text="Fade in/out (ms):").pack(side="left")
        self.fade_entry = ttk.Entry(fade_row, width=6)
        self.fade_entry.insert(0, "20")
        self.fade_entry.pack(side="left", padx=(6,0))

        silence_row = ttk.Frame(frm)
        silence_row.pack(fill="x", pady=(8,0))
        ttk.Label(silence_row, text="Silence threshold (dBFS):").pack(side="left")
        self.silence_entry = ttk.Entry(silence_row, width=6)
        self.silence_entry.insert(0, str(DEFAULT_SILENCE_THRESH))
        self.silence_entry.pack(side="left", padx=(6,0))

        self.log_text = tk.Text(frm, bg="#181a20", fg="#fafbfc", height=7, font=("Consolas", 9), state="disabled")
        self.log_text.pack(fill="both", pady=(10,0), expand=True)

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="Select Video Files",
            filetypes=[("Video Files", "*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.mpg *.mpeg *.m4v"), ("All Files", "*.*")]
        )
        for f in files:
            if f not in self.video_files:
                self.video_files.append(f)
                self.file_listbox.insert(tk.END, os.path.basename(f))
        self.update_output_name()

    def clear_files(self):
        self.video_files.clear()
        self.file_listbox.delete(0, tk.END)
        self.update_output_name()

    def update_output_name(self):
        if not self.video_files:
            self.out_name_var.set("")
            return
        folder = os.path.dirname(self.video_files[0])
        folder_name = os.path.basename(folder.rstrip("/\\"))
        dt_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        out_name = f"{folder_name}_{dt_str}.wav"
        self.out_name_var.set(out_name)

    def clear_files(self):
        self.video_files.clear()
        self.file_listbox.delete(0, tk.END)

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def start_processing(self):
        if not self.video_files:
            self.log("No video files selected.")
            return
        # Output path logic
        folder = os.path.dirname(self.video_files[0])
        folder_name = os.path.basename(folder.rstrip("/\\"))
        dt_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        out_path = os.path.join(folder, f"{folder_name}_{dt_str}.wav")
        fade_ms = 20
        silence_thresh = DEFAULT_SILENCE_THRESH
        try:
            fade_ms = int(self.fade_entry.get())
        except Exception:
            pass
        try:
            silence_thresh = int(self.silence_entry.get())
        except Exception:
            pass
        self.progress.config(maximum=len(self.video_files), value=0)
        def log_callback(msg):
            self.log(msg)
        try:
            process_videos(self.video_files, out_path, log_callback=log_callback, fade_ms=fade_ms, silence_thresh=silence_thresh)
            self.progress.config(value=len(self.video_files))
            self.log(f"Done! Output saved as: {out_path}")
        except Exception as e:
            self.log(f"Error: {e}")


def launch_gui():
    root = tk.Tk()
    app = VideoAudioBatchGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main_cli()
