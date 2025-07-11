"""
REMOVE DUPLICATES 
compare files by size and hash
store computed hashes to a cache file to avoid rehashing , in the target folder's locaiton 
remove duplicates favoring the oldest file without "(1)" suffix
"""
import os
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
import json
import threading

@dataclass
class FileStats:
    total_files: int = 0
    unique_sizes: int = 0
    potential_duplicates: int = 0
    bytes_saved: int = 0
    files_deleted: int = 0

def group_files_by_size(files: List[str], progress_cb=None) -> Dict[int, List[str]]:
    """
    First pass: Group files by size to identify potential duplicates.
    """
    size_dict: Dict[int, List[str]] = {}
    print("\n[1/4] Analyzing file sizes...")
    total = len(files)
    for idx, file in enumerate(files):
        try:
            size = os.path.getsize(file)
            size_dict.setdefault(size, []).append(file)
        except OSError as e:
            print(f"Error accessing file {file}: {e}")
        if progress_cb:
            progress_cb('Scanning files', idx+1, total)
    return size_dict

def filter_potential_duplicates(size_dict: Dict[int, List[str]]) -> Tuple[Dict[int, List[str]], FileStats]:
    """
    Filter out unique file sizes and collect statistics.
    """
    stats = FileStats(total_files=sum(len(files) for files in size_dict.values()))
    stats.unique_sizes = len(size_dict)
    
    # Only keep sizes with multiple files
    duplicate_sizes = {size: files for size, files in size_dict.items() if len(files) > 1}
    stats.potential_duplicates = sum(len(files) for files in duplicate_sizes.values())
    
    print(f"\nFile Analysis Summary:")
    print(f"- Total files scanned: {stats.total_files}")
    print(f"- Unique file sizes: {stats.unique_sizes}")
    print(f"- Files needing hash comparison: {stats.potential_duplicates}")
    
    return duplicate_sizes, stats

def load_hash_cache(cache_path: str) -> dict:
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load hash cache: {e}")
    return {}

def save_hash_cache(cache_path: str, cache: dict):
    try:
        with open(cache_path, 'w') as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"Failed to save hash cache: {e}")

def get_file_hash(file_path: str, hash_cache: dict = None) -> str:
    """
    Computes the SHA-256 hash of a file, using a cache if provided.
    """
    try:
        stat = os.stat(file_path)
        cache_key = f"{file_path}|{stat.st_size}|{stat.st_mtime}"
        if hash_cache is not None:
            cached = hash_cache.get(cache_key)
            if cached:
                return cached
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if hash_cache is not None:
            hash_cache[cache_key] = digest
        return digest
    except Exception as e:
        print(f"Error hashing file {file_path}: {e}")
        return ""

def find_duplicate_files(size_dict: Dict[int, List[str]], hash_cache: dict, cache_path: str, progress_cb=None) -> Tuple[Dict[str, List[List[str]]], FileStats]:
    """
    Second pass: Identify duplicate files by comparing hashes of files with same size.
    Uses a persistent hash cache to avoid unnecessary rehashing.
    """
    print("\n[2/4] Comparing file contents...")
    duplicates: Dict[str, List[List[str]]] = {}
    stats = FileStats()
    updated = False

    total_groups = len(size_dict)
    for idx, (size, files) in enumerate(size_dict.items()):
        hash_dict: Dict[str, List[str]] = {}
        for file in files:
            file_hash = get_file_hash(file, hash_cache)
            if file_hash:
                hash_dict.setdefault(file_hash, []).append(file)
                updated = True
        for file_hash, file_list in hash_dict.items():
            if len(file_list) > 1:
                dir_path = os.path.dirname(file_list[0])
                duplicates.setdefault(dir_path, []).append(file_list)
                stats.bytes_saved += os.path.getsize(file_list[0]) * (len(file_list) - 1)
        if progress_cb:
            progress_cb('Comparing files', idx+1, total_groups)

    if updated:
        save_hash_cache(cache_path, hash_cache)

    if duplicates:
        print(f"\nDuplicate Files Found:")
        print(f"- Potential space savings: {stats.bytes_saved / (1024*1024):.2f} MB")
    else:
        print("\nNo duplicate files found!")
    
    return duplicates, stats

def get_file_priority(file_path: str) -> Tuple[float, bool, int]:
    """
    Determines which file to keep based on modification time and name.
    """
    try:
        mtime = os.path.getmtime(file_path)
        basename = os.path.basename(file_path)
        has_suffix = any(f"({i})" in basename for i in range(1, 10))
        name_length = len(basename)
        return (mtime, has_suffix, name_length)
    except Exception as e:
        print(f"Error getting priority for file {file_path}: {e}")
        return (float('inf'), True, float('inf'))

def delete_duplicate_files(duplicates: Dict[str, List[List[str]]], hash_cache: dict, progress_cb=None) -> int:
    """
    Final pass: Delete duplicate files while keeping one copy. Logs full details to the log window.
    """
    print("\n[3/4] Removing duplicate files...")
    total_deleted = 0
    total_groups = sum(len(groups) for groups in duplicates.values())
    processed = 0
    for dir_path, file_groups in duplicates.items():
        for file_list in file_groups:
            # Prepare detailed info for this duplicate group
            hashes = [(f, get_file_hash(f, hash_cache)) for f in file_list]
            sizes = [(f, os.path.getsize(f)) for f in file_list]
            print(f"\nDuplicate group in directory: {dir_path}")
            for f, h in hashes:
                print(f"  File: {f}")
                print(f"    Size: {os.path.getsize(f)} bytes, Hash: {h}")
            file_list.sort(key=get_file_priority)
            file_to_keep = file_list[0]
            print(f"-> Keeping: {file_to_keep} (oldest, no '(1)' suffix if possible)")
            files_to_delete = file_list[1:]
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    print(f"-> Deleted: {file_path} (duplicate of {file_to_keep})")
                    print(f"   Reason: Same hash as kept file ({get_file_hash(file_path, hash_cache)})")
                    total_deleted += 1
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
            processed += 1
            if progress_cb:
                progress_cb('Removing duplicates', processed, total_groups)
    return total_deleted

def remove_duplicate_files(folder_path: str, progress_cb=None) -> Tuple[int, FileStats]:
    """
    Main function to remove duplicate files in a folder. Uses a persistent hash cache.
    """
    print(f"\n[Starting duplicate file removal in: {folder_path}]")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Prepare hash cache path
    cache_path = os.path.join(folder_path, ".duplicate_hash_cache.json")
    hash_cache = load_hash_cache(cache_path)

    # Get all files recursively
    all_files = [os.path.join(dp, f) for dp, dn, fn in os.walk(folder_path) for f in fn]
    if not all_files:
        print("No files found in the specified directory!")
        return 0, FileStats()
    
    # First pass: Group by size
    size_dict = group_files_by_size(all_files, progress_cb)
    
    # Filter and get statistics
    duplicate_sizes, stats = filter_potential_duplicates(size_dict)
    if not duplicate_sizes:
        return 0, stats
    
    # Second pass: Find actual duplicates (with cache)
    duplicates, stats = find_duplicate_files(duplicate_sizes, hash_cache, cache_path, progress_cb)
    if not duplicates:
        return 0, stats
    
    # Final pass: Delete duplicates (detailed log)
    stats.files_deleted = delete_duplicate_files(duplicates, hash_cache, progress_cb)
    
    print(f"\n[4/4] Operation completed successfully!")
    print(f"- Total files deleted: {stats.files_deleted}")
    print(f"- Space saved: {stats.bytes_saved / (1024*1024):.2f} MB")
    
    return stats.files_deleted, stats

def browse_folder():
    """
    GUI function to browse and select a folder.
    """
    folder_path = filedialog.askdirectory()
    if folder_path:
        total_deleted, stats = remove_duplicate_files(folder_path)
        messagebox.showinfo("Duplicate File Remover",
                          f"Process completed successfully!\n\n"
                          f"Files analyzed: {stats.total_files}\n"
                          f"Files deleted: {stats.files_deleted}\n"
                          f"Space saved: {stats.bytes_saved / (1024*1024):.2f} MB")

if __name__ == "__main__":
    from tkinter import scrolledtext

    class TextRedirector:
        def __init__(self, widget):
            self.widget = widget
        def write(self, s):
            self.widget.configure(state='normal')
            self.widget.insert(tk.END, s)
            self.widget.see(tk.END)
            self.widget.configure(state='disabled')
        def flush(self):
            pass

    def browse_folder():
        folder_path = filedialog.askdirectory()
        if folder_path:
            folder_entry.delete(0, tk.END)
            folder_entry.insert(0, folder_path)

    def update_progress_ui(stage, current, total):
        def _update():
            if total > 0:
                percent = int((current / total) * 100)
            else:
                percent = 0
            progress_label.config(text=f"{stage}: {current}/{total}")
            progressbar['value'] = percent
            root.update_idletasks()
        root.after(0, _update)

    import io
    import time

    def start_removal():
        folder_path = folder_entry.get()
        if not folder_path or not os.path.isdir(folder_path):
            print("Error: Please enter a valid folder path.")
            return
        log_text.configure(state='normal')
        log_text.delete(1.0, tk.END)
        log_text.configure(state='disabled')
        progressbar['value'] = 0
        progress_label.config(text="")
        start_btn.config(state='disabled')
        old_stdout = os.sys.stdout
        log_capture = io.StringIO()
        class Tee:
            def __init__(self, *writers):
                self.writers = writers
            def write(self, s):
                for w in self.writers:
                    w.write(s)
            def flush(self):
                for w in self.writers:
                    w.flush()
        os.sys.stdout = Tee(TextRedirector(log_text), log_capture)
        def run_removal():
            try:
                total_deleted, stats = remove_duplicate_files(folder_path, progress_cb=update_progress_ui)
                # Write report at the end
                timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                report_path = os.path.join(folder_path, f"duplicate_removal_report_{timestamp}.txt")
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(log_capture.getvalue())
                def show_done():
                    print("\n[Process completed]")
                    print(f"Files analyzed: {stats.total_files}")
                    print(f"Files deleted: {stats.files_deleted}")
                    print(f"Space saved: {stats.bytes_saved / (1024*1024):.2f} MB")
                    print(f"Report saved to: {report_path}")
                    start_btn.config(state='normal')
                    progress_label.config(text="Done.")
                root.after(0, show_done)
            finally:
                os.sys.stdout = old_stdout
        threading.Thread(target=run_removal, daemon=True).start()

    root = tk.Tk()
    root.title("Duplicate File Remover")
    root.geometry("600x550")
    root.configure(bg='#23272e')

    style_args = {
        'bg': '#23272e',
        'fg': '#e6e6e6',
        'insertbackground': '#e6e6e6',
        'highlightbackground': '#444',
        'highlightcolor': '#444',
        'selectbackground': '#444',
        'selectforeground': '#e6e6e6',
    }

    frame = tk.Frame(root, bg='#23272e', padx=20, pady=20)
    frame.pack(expand=False, fill='x')

    label = tk.Label(frame, text="Folder Path:", bg='#23272e', fg='#e6e6e6')
    label.grid(row=0, column=0, sticky='w')

    folder_entry = tk.Entry(frame, width=50, **style_args)
    folder_entry.grid(row=0, column=1, padx=(5, 0))

    browse_btn = tk.Button(frame, text="Browse", command=browse_folder, bg='#444', fg='#e6e6e6', activebackground='#666', activeforeground='#fff')
    browse_btn.grid(row=0, column=2, padx=5)

    start_btn = tk.Button(frame, text="Start", command=start_removal, bg='#444', fg='#e6e6e6', activebackground='#666', activeforeground='#fff', width=12)
    start_btn.grid(row=0, column=3, padx=5)

    progressbar = ttk.Progressbar(root, orient='horizontal', length=500, mode='determinate')
    progressbar.pack(pady=(10, 0))
    progress_label = tk.Label(root, text="", bg='#23272e', fg='#e6e6e6')
    progress_label.pack()

    log_label = tk.Label(root, text="Log:", bg='#23272e', fg='#e6e6e6')
    log_label.pack(anchor='w', padx=22)

    log_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20, width=70, font=("Consolas", 10),
                                         bg='#181a1b', fg='#e6e6e6', insertbackground='#e6e6e6',
                                         selectbackground='#444', selectforeground='#fff')
    log_text.pack(expand=True, fill='both', padx=20, pady=(0, 20))
    log_text.configure(state='disabled')

    root.mainloop()
