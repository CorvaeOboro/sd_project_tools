"""
AUDIO HOTKEY ORGANIZER
speech recognize actions by phonetic closeness to trigger hotkeys or windows operations ,
actions : moving currently selected files in explorer to a targeted folder 
actions : trigger hotkey 
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
def move_file(path_start, path_end, backup):
    selected_files = get_selected_files()
    print("SELECTED FILES= " + str(selected_files))
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
        print("MOVE == " + str(current_selected_filepath) + " ****TO****** " + str(target_path))
        shutil.move(str(current_selected_filepath), str(target_path))

        # Backup if enabled
        if backup:
            backup_folderpath = Path(BACKUP_FOLDERPATH)  # Ensure this is a Path object
            os.makedirs(backup_folderpath, exist_ok=True)  # Create backup directory
            backup_path = backup_folderpath / current_selected_filepath.name

            # Create unique backup file path
            backup_counter = 1
            while backup_path.exists():
                backup_path = backup_folderpath / f"{current_selected_filepath.stem}_{backup_counter}{current_selected_filepath.suffix}"
                backup_counter += 1

            print("BACKUP PATH == " + str(backup_path))
            shutil.copy2(str(target_path), str(backup_path))

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
    if action['name'] == "folder":
        organize_file_into_folder()

    else:
        move_file(action['path_start'], action['path_end'], action['backup'])


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

# UI {#486,75} ===========================================
def display_actions_ui():  # Function to load and display actions in the listbox
    global actions
    actions_listbox.delete(0, tk.END)  # Clear existing entries
    for action in actions:
        actions_listbox.insert(tk.END, action['name'])

def update_label(event):  # Update label function
    global recognized_text_global
    label.config(text=recognized_text_global)

def log_action(action_name):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    with open("action_log.txt", "a") as log_file:
        log_file.write(f"{timestamp} - Executed action: {action_name}\n")

def update_match_threshold():  # Function to update match threshold
    global MATCH_THRESHOLD
    try:
        new_threshold = float(match_threshold_entry.get())
        MATCH_THRESHOLD = new_threshold
        status_label.config(text=f"Threshold updated to {MATCH_THRESHOLD}")
    except ValueError:
        status_label.config(text="Invalid input for threshold")

def update_audio_level():
    if not AUDIO_LEVELS.empty():
        audio_level = AUDIO_LEVELS.get()
        audio_level_progress['value'] = audio_level  # Update the progress bar value
        root.update_idletasks()  # Update the UI to reflect the change

def mainloop_update():
    update_audio_level()
    root.after(1000, mainloop_update)  # Schedule the function to be called every second

#//===========================================================================================
if __name__ == "__main__":
    load_actions()
    # Start the speech recognition thread
    thread = Thread(target=listen_and_recognize)
    thread.daemon = True
    thread.start()
    # UI Tkinter setup ===================================================
    # Dark theme colors
    DARK_BG = "#333333"
    DARK_FG = "#EEEEEE"
    DARK_BUTTON_BG = "#555555"

    root = tk.Tk()
    root.title("Voice Actions")
    root.configure(bg=DARK_BG)

    # Creating widgets for the UI
    label = tk.Label(root, text="Listening...", font=(FONT_NAME, 12), height=2, width=50, bg=DARK_BG, fg=DARK_FG)
    label.pack(pady=20)

    # History list
    history = scrolledtext.ScrolledText(root, height=15, width=50, bg=DARK_BG, fg=DARK_FG)
    history.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

    # Actions list
    actions_listbox = Listbox(root, height=15, width=50, bg=DARK_BG, fg=DARK_FG)
    actions_listbox.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
    display_actions_ui()  # Populate actions listbox

    # Add a button for CSV to JSON conversion
    convert_button = tk.Button(root, text="Convert CSV to JSON", command=csv_to_json_ui)
    convert_button.pack(pady=10)

    recognition_timeout_label = tk.Label(root, text="Recognition Timeout (seconds):", font=(FONT_NAME, FONT_SIZE))
    recognition_timeout_label.pack()

    recognition_timeout_entry = tk.Entry(root, font=(FONT_NAME, FONT_SIZE))
    recognition_timeout_entry.pack()
    recognition_timeout_entry.insert(0, str(recognition_timeout))  # Default value

    update_timeout_button = tk.Button(root, text="Update Timeout", command=update_recognition_settings)
    update_timeout_button.pack()

    status_label = tk.Label(root, text="", font=(FONT_NAME, FONT_SIZE))
    status_label.pack()

    audio_level_label = tk.Label(root, text="Audio Level:", font=(FONT_NAME, 10))
    audio_level_label.pack()

    # Create a Progressbar widget
    audio_level_progress = ttk.Progressbar(root, orient="horizontal", length=200, mode='determinate')
    audio_level_progress.pack()

    match_threshold_label = tk.Label(root, text="Match Threshold:", font=(FONT_NAME, FONT_SIZE))
    match_threshold_label.pack()

    match_threshold_entry = tk.Entry(root, font=(FONT_NAME, FONT_SIZE))
    match_threshold_entry.pack()
    match_threshold_entry.insert(0, str(MATCH_THRESHOLD))  # Default value

    update_threshold_button = tk.Button(root, text="Update Threshold", command=update_match_threshold)
    update_threshold_button.pack()

    python_log = scrolledtext.ScrolledText(root, height=10, width=50)
    python_log.pack(pady=10)
    sys.stdout = StdoutRedirector(python_log)

    # Bind the custom event to the update_label function
    root.bind("<<UpdateLabel>>", update_label)

    mainloop_update()
    root.mainloop()