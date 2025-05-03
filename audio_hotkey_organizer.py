"""
AUDIO HOTKEY ORGANIZER
speech recognized by phonetic closeness to trigger "actions" windows operations for file organization
actions : organize > moving currently selected files in explorer to a targeted folder 
actions : archive > copy selected files to a backup folder in the same directory 
actions : 01 or 02 > move selected files to a folder named 01 or 02 in the same directory used for rating
actions : hotkey > trigger a hotkey 
JSON stores the different actions and their parameters 'audio_hotkey_organizer.json'
by default all actioned files are stored to BACKUP folder 
"""
#//==============================================================================================================
from vosk import Model, KaldiRecognizer # speech recognition works offline 
# import speech_recognition as sr  # removed , no longer using , doesnt work offline
import pyautogui
from threading import Thread
from datetime import datetime
import sys
import os
import shutil
from pathlib import Path

import win32com.client # GET SELECTED FILES FROM WINDOWS EXPLORER 
import win32gui
from ctypes.wintypes import HWND, LPARAM

import tkinter as tk # ui
from tkinter import ttk  # Import ttk module
from tkinter import scrolledtext # ui
from tkinter import filedialog, messagebox # ui
from tkinter import scrolledtext, filedialog, messagebox, Listbox # ui
import csv # csv to json
import json # json stores the actions data
import Levenshtein  # For calculating string similarity
import queue  # For audio level monitoring
import sounddevice as sd  # For capturing audio
import numpy as np  # For audio processing
from threading import Lock
import pyttsx3  # For computer-generated voice feedback
import webbrowser  # For opening URLs

# GLOBAL SETTINGS ===========================================================
JSON_DATA = 'audio_hotkey_organizer.json'
recognition_timeout = 3  # Default timeout in seconds
MATCH_THRESHOLD = 0.7  # Minimum similarity score to consider a match
AUDIO_LEVELS = queue.Queue(maxsize=10)  # Queue to hold recent audio levels
BACKUP_FOLDERPATH = "C:/BACKUP/"
recognized_text_global = "" # Initialize
actions = []  # Initialize actions as a global variable
FONT_NAME = "Arial"
FONT_SIZE = 10

#//==============================================================================================================
# Load the offline Vosk model for speech recognition
model_path = "./vosk-model-en-us-0.42-gigaspeech"  # Replace this with the path to your Vosk model directory
if not os.path.exists(model_path):
    print("Please download the model from https://alphacephei.com/vosk/models  vosk-model-en-us-0.42-gigaspeech into local folder with same name. more information on their github https://github.com/alphacep/vosk-api")
    sys.exit(1)
model = Model(model_path)

# Function to recognize speech
def recognize_speech(recognizer, audio):
    if recognizer.AcceptWaveform(audio):
        result = json.loads(recognizer.Result())
        return result.get("text", "")
    return ""

# JSON {#4ca,74}  ========================
# EXAMPLE JSON
def create_example_json(json_file):
    example_data = [
        {
            "name": "Move_Example",
            "phonetic_words": ["move", "test"],
            "enabled": True,
            "hotkey": "",
            "path_start": "C:\\path\\to\\project\\",
            "path_end": "example",
            "backup": True,
            "press_hotkey": False
        },
        {
            "name": "Hotkey_Example",
            "phonetic_words": ["notepad", "open"],
            "enabled": True,
            "hotkey": "ctrl+N",
            "path_start": "",
            "path_end": "",
            "backup": False,
            "press_hotkey": True
        }
    ]

    with open(json_file, 'w') as file:
        json.dump(example_data, file, indent=4)

def str_to_bool(value):
    true_values = ['true', 'yes', '1', 'on', 'enabled']
    return str(value).lower() in true_values

# CSV to JSON conversion with UI integration
def csv_to_json_ui():
    csv_filepath = filedialog.askopenfilename(title="Select CSV File", filetypes=[("CSV files", "*.csv")])
    if not csv_filepath:
        return  # User canceled the file selection

    new_actions = []
    with open(csv_filepath, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            json_action = {
                "name": row["name"],
                "phonetic_words": row["phonetic"].split(","),
                "enabled": str_to_bool(row.get("enabled", True)),
                "hotkey": row["hotkey"],
                "path_start": row.get("path_start", ""),
                "path_end": row.get("path_end", ""),
                "backup": str_to_bool(row.get("backup", True)),
                "press_hotkey": str_to_bool(row.get("press_hotkey", True))
            }
            new_actions.append(json_action)
            log_csv_to_json_conversion(row, json_action)

    # Ask user to overwrite or append
    if messagebox.askyesno("Overwrite JSON", "Do you want to overwrite the existing JSON?"):
        with open(JSON_DATA, 'w') as file:
            json.dump(new_actions, file, indent=4)
    else:
        append_to_json(new_actions, JSON_DATA)

# Function to log CSV to JSON conversion
def log_csv_to_json_conversion(csv_row, json_action):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_message = f"{timestamp} - CSV Row: {csv_row} converted to JSON action: {json_action}\n"
    with open("conversion_log.txt", "a") as log_file:
        log_file.write(log_message)

def append_to_json(new_actions, json_file):
    existing_actions = load_actions(json_file)
    updated_actions = existing_actions + new_actions
    with open(json_file, 'w') as file:
        json.dump(updated_actions, file, indent=4)

# WINDOWS EXPLORER {#25d,38} ========================================
def window_enumeration_handler(hwnd, top_windows):
    # enumerate window titles to find the full path
    top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))

def get_foreground_explorer_path():
    # get the full path of the foreground Explorer window
    shell = win32com.client.Dispatch("Shell.Application")
    windows = shell.Windows()

    foreground_window_handle = win32gui.GetForegroundWindow()
    
    for window in windows:
        # Only consider Explorer windows
        if window.Name == "File Explorer":
            # Compare HWND values to find the foreground Explorer window
            if int(window.HWND) == foreground_window_handle:
                # Extract the full folder path
                full_path = window.LocationURL.replace('file:///', '').replace('/', '\\')
                return full_path
    return None

def get_selected_files():
    shell = win32com.client.Dispatch("Shell.Application")
    explorers = shell.Windows()
    foreground_path = get_foreground_explorer_path()

    selected_files = []
    if foreground_path:
        for explorer in explorers:
            try:
                if explorer.LocationURL.startswith("file:"):
                    explorer_path = Path(explorer.LocationURL[8:].replace('/', '\\'))
                    if explorer_path == Path(foreground_path):
                        selected_items = explorer.Document.SelectedItems()
                        selected_files.extend(item.Path for item in selected_items)
            except Exception as e:
                print("Error accessing Explorer window:", e)
    return selected_files

#  MOVE FILES {#582,39} =============================================
# move files based on action parameters
def move_file(path_start, path_end, backup, action_name=None, action_obj=None):
    selected_files = get_selected_files()
    moved_files = []
    # Determine folder to open if no files are selected
    explorer_folder = None
    if action_obj and isinstance(action_obj, dict):
        explorer_folder = action_obj.get('explorer_folder')
    if not explorer_folder:
        explorer_folder = path_start
    if not selected_files:
        try:
            os.startfile(explorer_folder)
            if 'app' in globals():
                app.log_both(f"Opened folder: {explorer_folder}", f"No files selected. Opened: {explorer_folder}")
        except Exception as e:
            if 'app' in globals():
                app.log_both("Could not open folder.", f"Error opening {explorer_folder}: {e}")
        return
    for current_selected_filepath in selected_files:
        current_selected_filepath = Path(current_selected_filepath)
        if not current_selected_filepath.is_file():
            continue
        # Create target path
        target_path = Path(path_start) / path_end / current_selected_filepath.name
        os.makedirs(target_path.parent, exist_ok=True)
        # Create unique target path
        counter = 1
        while target_path.exists():
            target_path = target_path.parent / f"{target_path.stem}_{counter}{target_path.suffix}"
            counter += 1
        # Move file
        shutil.move(str(current_selected_filepath), str(target_path))
        moved_files.append(target_path)
        # Backup if enabled
        if backup:
            backup_folderpath = Path(BACKUP_FOLDERPATH)
            os.makedirs(backup_folderpath, exist_ok=True)
            backup_path = backup_folderpath / current_selected_filepath.name
            backup_counter = 1
            while backup_path.exists():
                backup_path = backup_folderpath / f"{current_selected_filepath.stem}_{backup_counter}{current_selected_filepath.suffix}"
                backup_counter += 1
            shutil.copy2(str(target_path), str(backup_path))
    # Concise logging for UI
    if 'app' in globals():
        concise = f"{len(moved_files)} file{'s' if len(moved_files)!=1 else ''} moved to {path_end}" if moved_files else "No files moved."
        full = f"Moved files: {[str(f) for f in moved_files]}"
        app.log_both(concise, full)

def organize_file_into_folder():
    selected_files = get_selected_files()
    for file_path in selected_files:
        file_path = Path(file_path)
        if not file_path.is_file():
            continue

        # Create a new folder in the same directory with the same name as the file
        folder_path = file_path.with_suffix('')
        os.makedirs(folder_path, exist_ok=True)

        # Generate a unique file name if needed
        new_file_path = folder_path / file_path.name
        counter = 1
        while new_file_path.exists():
            new_file_path = folder_path / f"{file_path.stem}_{counter}{file_path.suffix}"
            counter += 1

        # Move the file into the newly created folder
        shutil.move(str(file_path), str(new_file_path))
        print(f"Moved {file_path} to {new_file_path}")

def archive_selected_files_to_local_backup():
    selected_files = get_selected_files()
    if not selected_files:
        if 'app' in globals():
            app.log_both("No files selected for backup.")
        return
    # Get the folder of the first selected file
    base_folder = str(Path(selected_files[0]).parent)
    today_str = datetime.now().strftime("%Y%m%d")
    archive_folder = os.path.join(base_folder, "backup", today_str)
    os.makedirs(archive_folder, exist_ok=True)
    copied_files = []
    for file_path in selected_files:
        src = Path(file_path)
        if src.is_file():
            dst = os.path.join(archive_folder, src.name)
            shutil.copy2(str(src), dst)
            copied_files.append(dst)
    if 'app' in globals():
        concise = f"Archived {len(copied_files)} file{'s' if len(copied_files)!=1 else ''} to {archive_folder}" if copied_files else "No files archived."
        full = f"Archived files: {[str(f) for f in copied_files]}"
        app.log_both(concise, full)

# LISTEN {#eee,44} =============================================
def listen_and_recognize():
    recognizer = KaldiRecognizer(model, 16000)
    recognition_lock = Lock()

    def audio_callback(indata, frames, time, status):
        nonlocal recognizer
        if status:
            print(status, file=sys.stderr)
        audio_data = np.frombuffer(indata, dtype=np.int16)
        if recognition_lock.acquire(blocking=False):  # Try to acquire the lock
            try:
                if recognizer.AcceptWaveform(audio_data.tobytes()):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        print("Recognized:", text)
                        process_recognized_speech(text)
            finally:
                recognition_lock.release()  # Release the lock

    with sd.InputStream(callback=audio_callback, dtype='int16', channels=1, samplerate=16000):
        print("Say something!")
        while True:
            sd.sleep(1000)

def update_recognition_settings(): 
    # UI Function to update recognition settings
    global recognition_timeout
    try:
        new_timeout = float(recognition_timeout_entry.get())
        recognition_timeout = new_timeout
        status_label.config(text=f"Timeout updated to {recognition_timeout} seconds")
    except ValueError:
        status_label.config(text="Invalid input for timeout")


def process_recognized_speech(text):
    # process recognized speech and trigger actions
    global actions
    action_triggered = False
    for action in actions:
        for word in action['phonetic_words']:
            similarity = Levenshtein.ratio(text, word)
            if similarity >= MATCH_THRESHOLD and action['enabled']:
                print(f"Action triggered: {action['name']}")
                execute_action(action)
                action_triggered = True
                break
        if action_triggered:
            break

# ACTIONS {#363,27} =============================

def execute_action(action):
    # actions are hotkeys or move_files
    if action['press_hotkey']:
        pyautogui.hotkey(*action['hotkey'].split('+'))
        if 'app' in globals():
            app.log_both(f"Hotkey '{action['hotkey']}' triggered.")
    if action['name'].lower() == "folder":
        organize_file_into_folder()
    elif action['name'].lower() == "archive":
        archive_selected_files_to_local_backup()
    else:
        move_file(action['path_start'], action['path_end'], action['backup'], action_name=action.get('name'), action_obj=action)
    # TTS: Say back the action name if enabled
    try:
        if 'app' in globals():
            app.on_action_triggered(action['name'])
    except Exception as e:
        print(f"TTS error: {e}")

def load_actions():
    #load actions from JSON file
    global actions
    with open(JSON_DATA, 'r') as file:
        actions = json.load(file)

def match_action(recognized_text, actions):
    for action in actions:
        for word in action['phonetic_words']:
            similarity = Levenshtein.ratio(recognized_text, word)
            if similarity >= MATCH_THRESHOLD:
                return action['enabled'], action['name'], similarity
    return None, None, 0

#//=======================================================================
class StdoutRedirector(object):
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, str):
        self.text_widget.insert(tk.END, str)
        self.text_widget.see(tk.END)  # Auto-scroll to the end

    def flush(self):
        pass  # No flushing needed

class AudioHotkeyOrganizerUI:
    def __init__(self, master, actions, load_actions_func, listen_and_recognize_func, process_recognized_speech_func):
        self.master = master
        self.actions = actions
        self.load_actions_func = load_actions_func
        self.listen_and_recognize_func = listen_and_recognize_func
        self.process_recognized_speech_func = process_recognized_speech_func

        # TTS engine
        self.tts_engine = pyttsx3.init()
        self.say_action_enabled = tk.BooleanVar(value=False)

        # Dark mode colors
        self.DARK_BG = "#23272e"
        self.DARK_FG = "#e0e0e0"
        self.DARK_ENTRY_BG = "#1a1d22"
        self.DARK_ENTRY_FG = "#e0e0e0"
        self.DARK_BUTTON_BG = "#353b45"
        self.DARK_BUTTON_FG = "#e0e0e0"
        self.DARK_HIGHLIGHT = "#3a3f4b"
        self.DARK_SELECT_BG = "#444a58"
        self.DARK_SELECT_FG = "#ffffff"

        master.title("Voice Actions")
        master.configure(bg=self.DARK_BG)

        # Create three main columns
        self.left_frame = tk.Frame(master, bg=self.DARK_BG)
        self.center_frame = tk.Frame(master, bg=self.DARK_BG)
        self.right_frame = tk.Frame(master, bg=self.DARK_BG)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.center_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)
        self.right_frame.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        # LEFT COLUMN: Logging
        self.concise_log_var = tk.StringVar(value="Ready.")
        self.concise_log_label = tk.Label(self.left_frame, textvariable=self.concise_log_var, bg=self.DARK_BG, fg="#a8ff60", font=(FONT_NAME, 11, "bold"))
        self.concise_log_label.pack(pady=(0,4), anchor="w")
        self.history = scrolledtext.ScrolledText(self.left_frame, height=15, width=50, bg=self.DARK_ENTRY_BG, fg=self.DARK_ENTRY_FG, insertbackground=self.DARK_FG)
        self.history.pack(fill=tk.BOTH, expand=True)

        # CENTER COLUMN: Actions list
        self.actions_listbox = Listbox(self.center_frame, height=25, width=30, bg=self.DARK_ENTRY_BG, fg=self.DARK_ENTRY_FG, selectbackground=self.DARK_SELECT_BG, selectforeground=self.DARK_SELECT_FG, highlightbackground=self.DARK_HIGHLIGHT)
        self.actions_listbox.pack(fill=tk.BOTH, expand=True)
        self.add_action_button = tk.Button(self.center_frame, text="Add Action", command=self.open_add_action_window, bg=self.DARK_BUTTON_BG, fg=self.DARK_BUTTON_FG)
        self.add_action_button.pack(pady=5)
        self.actions_listbox.bind("<<ListboxSelect>>", self.update_label)

        # RIGHT COLUMN: Settings
        # JSON file row
        json_row = tk.Frame(self.right_frame, bg=self.DARK_BG)
        tk.Label(json_row, text="Settings:", bg=self.DARK_BG, fg=self.DARK_FG).pack(side=tk.LEFT, padx=(0,4))
        self.json_path_var = tk.StringVar(value=JSON_DATA)
        self.json_path_entry = tk.Entry(json_row, textvariable=self.json_path_var, bg=self.DARK_ENTRY_BG, fg=self.DARK_ENTRY_FG, insertbackground=self.DARK_FG, width=28, highlightbackground=self.DARK_HIGHLIGHT)
        self.json_path_entry.pack(side=tk.LEFT, padx=(0,4))
        self.load_json_button = tk.Button(json_row, text="Load", command=self.load_json_file, bg=self.DARK_BUTTON_BG, fg=self.DARK_BUTTON_FG)
        self.load_json_button.pack(side=tk.LEFT, padx=(0,4))
        self.browse_json_button = tk.Button(json_row, text="Browse", command=self.browse_json_file, bg=self.DARK_BUTTON_BG, fg=self.DARK_BUTTON_FG)
        self.browse_json_button.pack(side=tk.LEFT)
        json_row.pack(fill=tk.X, pady=2)

        # Backup folder row
        backup_row = tk.Frame(self.right_frame, bg=self.DARK_BG)
        tk.Label(backup_row, text="Backup Folder:", bg=self.DARK_BG, fg=self.DARK_FG).pack(side=tk.LEFT, padx=(0,4))
        self.backup_folder_var = tk.StringVar(value=BACKUP_FOLDERPATH)
        self.backup_folder_entry = tk.Entry(backup_row, textvariable=self.backup_folder_var, bg=self.DARK_ENTRY_BG, fg=self.DARK_ENTRY_FG, insertbackground=self.DARK_FG, width=28, highlightbackground=self.DARK_HIGHLIGHT)
        self.backup_folder_entry.pack(side=tk.LEFT)
        backup_row.pack(fill=tk.X, pady=2)

        # Vosk model row
        vosk_row = tk.Frame(self.right_frame, bg=self.DARK_BG)
        tk.Label(vosk_row, text="Vosk Model:", bg=self.DARK_BG, fg=self.DARK_FG).pack(side=tk.LEFT, padx=(0,4))
        self.vosk_model_var = tk.StringVar(value="./vosk-model-en-us-0.42-gigaspeech")
        self.vosk_model_entry = tk.Entry(vosk_row, textvariable=self.vosk_model_var, bg=self.DARK_ENTRY_BG, fg=self.DARK_ENTRY_FG, insertbackground=self.DARK_FG, width=28, highlightbackground=self.DARK_HIGHLIGHT)
        self.vosk_model_entry.pack(side=tk.LEFT, padx=(0,4))
        self.vosk_download_button = tk.Button(vosk_row, text="Download", command=self.open_vosk_download, bg=self.DARK_BUTTON_BG, fg=self.DARK_BUTTON_FG)
        self.vosk_download_button.pack(side=tk.LEFT)
        vosk_row.pack(fill=tk.X, pady=2)

        # Match threshold row
        threshold_row = tk.Frame(self.right_frame, bg=self.DARK_BG)
        tk.Label(threshold_row, text="Match Threshold:", bg=self.DARK_BG, fg=self.DARK_FG).pack(side=tk.LEFT, padx=(0,4))
        self.match_threshold_entry = tk.Entry(threshold_row, bg=self.DARK_ENTRY_BG, fg=self.DARK_ENTRY_FG, insertbackground=self.DARK_FG, width=8, highlightbackground=self.DARK_HIGHLIGHT)
        self.match_threshold_entry.insert(0, str(MATCH_THRESHOLD))
        self.match_threshold_entry.pack(side=tk.LEFT, padx=(0,4))
        self.update_threshold_button = tk.Button(threshold_row, text="Update", bg=self.DARK_BUTTON_BG, fg=self.DARK_BUTTON_FG, command=self.update_match_threshold)
        self.update_threshold_button.pack(side=tk.LEFT)
        threshold_row.pack(fill=tk.X, pady=2)

        # Checkbox for TTS feedback
        tts_row = tk.Frame(self.right_frame, bg=self.DARK_BG)
        self.say_action_checkbox = tk.Checkbutton(
            tts_row, text="Say back action name", variable=self.say_action_enabled,
            bg=self.DARK_BG, fg=self.DARK_FG, selectcolor=self.DARK_ENTRY_BG, activebackground=self.DARK_BG, activeforeground=self.DARK_FG
        )
        self.say_action_checkbox.pack(side=tk.LEFT)
        tts_row.pack(fill=tk.X, pady=2)

        # Label for recognized text
        self.label = tk.Label(self.right_frame, text="Listening...", font=(FONT_NAME, 12), height=2, width=32, bg=self.DARK_BG, fg=self.DARK_FG)
        self.label.pack(pady=8)

        # Status label
        self.status_label = tk.Label(self.right_frame, text="", bg=self.DARK_BG, fg=self.DARK_FG)
        self.status_label.pack(pady=2)

        # Progress bar for audio level
        self.audio_level_progress = ttk.Progressbar(self.right_frame, orient="horizontal", length=200, mode="determinate")
        self.audio_level_progress.pack(pady=5)
        self._style_dark_progressbar()

        # Redirect stdout to history widget
        sys.stdout = StdoutRedirector(self.history)

        # Initial population of actions
        self.display_actions_ui()

        # Start periodic UI updates
        self.master.after(1000, self.mainloop_update)

    def load_json_file(self):
        global JSON_DATA
        JSON_DATA = self.json_path_var.get()
        try:
            self.actions = load_actions()
            self.display_actions_ui()
            self.status_label.config(text=f"Loaded actions from {JSON_DATA}")
        except Exception as e:
            self.status_label.config(text=f"Error loading JSON: {e}")

    def browse_json_file(self):
        file_path = filedialog.askopenfilename(title="Select JSON File", filetypes=[("JSON files", "*.json")])
        if file_path:
            self.json_path_var.set(file_path)
            self.load_json_file()

    def open_vosk_download(self):
        webbrowser.open_new_tab("https://alphacephei.com/vosk/models")

    def get_backup_folder(self):
        return self.backup_folder_var.get()

    def get_vosk_model_path(self):
        return self.vosk_model_var.get()

    def speak_action_name(self, action_name):
        self.tts_engine.say(action_name)
        self.tts_engine.runAndWait()

    def on_action_triggered(self, action_name):
        if self.say_action_enabled.get():
            self.speak_action_name(action_name)

    def _style_dark_progressbar(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", troughcolor=self.DARK_ENTRY_BG, background="#3a7afe", bordercolor=self.DARK_HIGHLIGHT, lightcolor=self.DARK_HIGHLIGHT, darkcolor=self.DARK_HIGHLIGHT)

    def display_actions_ui(self):
        self.actions_listbox.delete(0, tk.END)
        for action in self.actions:
            self.actions_listbox.insert(tk.END, action['name'])

    def update_label(self, event=None):
        self.label.config(text=recognized_text_global)

    def log_action(self, action_name):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        with open("action_log.txt", "a") as log_file:
            log_file.write(f"{timestamp} - Executed action: {action_name}\n")

    def update_match_threshold(self):
        global MATCH_THRESHOLD
        try:
            new_threshold = float(self.match_threshold_entry.get())
            MATCH_THRESHOLD = new_threshold
            self.status_label.config(text=f"Threshold updated to {MATCH_THRESHOLD}")
        except ValueError:
            self.status_label.config(text="Invalid input for threshold")

    def update_audio_level(self):
        if not AUDIO_LEVELS.empty():
            audio_level = AUDIO_LEVELS.get()
            self.audio_level_progress['value'] = audio_level
            self.master.update_idletasks()

    def mainloop_update(self):
        self.update_audio_level()
        self.master.after(1000, self.mainloop_update)

    def log_concise(self, message):
        self.concise_log_var.set(message)

    def log_full(self, message):
        self.history.insert(tk.END, message + "\n")
        self.history.see(tk.END)

    def log_both(self, concise, full=None):
        self.log_concise(concise)
        if full is not None:
            self.log_full(full)
        else:
            self.log_full(concise)

    def open_add_action_window(self):
        win = tk.Toplevel(self.master)
        win.title("Add New Action")
        win.configure(bg=self.DARK_BG)

        # Field labels and entries
        fields = [
            ("Name", "name"),
            ("Phonetic Words (comma-separated)", "phonetic_words"),
            ("Enabled (true/false)", "enabled"),
            ("Hotkey (e.g. ctrl+N)", "hotkey"),
            ("Path Start", "path_start"),
            ("Path End", "path_end"),
            ("Backup (true/false)", "backup"),
            ("Press Hotkey (true/false)", "press_hotkey"),
            ("Explorer Folder (optional)", "explorer_folder")
        ]
        entries = {}
        for idx, (label, key) in enumerate(fields):
            tk.Label(win, text=label, bg=self.DARK_BG, fg=self.DARK_FG).grid(row=idx, column=0, sticky='e', padx=4, pady=2)
            entry = tk.Entry(win, bg=self.DARK_ENTRY_BG, fg=self.DARK_ENTRY_FG, insertbackground=self.DARK_FG, width=30, highlightbackground=self.DARK_HIGHLIGHT)
            entry.grid(row=idx, column=1, padx=4, pady=2)
            entries[key] = entry
        # Set some defaults
        entries['enabled'].insert(0, 'true')
        entries['backup'].insert(0, 'true')
        entries['press_hotkey'].insert(0, 'false')

        def submit():
            try:
                action = {
                    "name": entries['name'].get().strip(),
                    "phonetic_words": [w.strip() for w in entries['phonetic_words'].get().split(',') if w.strip()],
                    "enabled": entries['enabled'].get().strip().lower() in ['true', '1', 'yes', 'on', 'enabled'],
                    "hotkey": entries['hotkey'].get().strip(),
                    "path_start": entries['path_start'].get().strip(),
                    "path_end": entries['path_end'].get().strip(),
                    "backup": entries['backup'].get().strip().lower() in ['true', '1', 'yes', 'on', 'enabled'],
                    "press_hotkey": entries['press_hotkey'].get().strip().lower() in ['true', '1', 'yes', 'on', 'enabled']
                }
                explorer_folder_val = entries['explorer_folder'].get().strip()
                if explorer_folder_val:
                    action['explorer_folder'] = explorer_folder_val
                # Append to JSON file
                with open(JSON_DATA, 'r') as f:
                    data = json.load(f)
                data.append(action)
                with open(JSON_DATA, 'w') as f:
                    json.dump(data, f, indent=4)
                self.actions = data
                self.display_actions_ui()
                self.log_both(f"Added action '{action['name']}'", f"Added: {action}")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add action: {e}")

        submit_btn = tk.Button(win, text="Add", command=submit, bg=self.DARK_BUTTON_BG, fg=self.DARK_BUTTON_FG)
        submit_btn.grid(row=len(fields), column=0, columnspan=2, pady=8)

if __name__ == "__main__":
    load_actions()
    # Start the speech recognition thread
    thread = Thread(target=listen_and_recognize)
    thread.daemon = True
    thread.start()

    root = tk.Tk()
    global app
    app = AudioHotkeyOrganizerUI(
        root,
        actions,
        load_actions_func=load_actions,
        listen_and_recognize_func=listen_and_recognize,
        process_recognized_speech_func=process_recognized_speech
    )
    root.mainloop()