"""
Project Status Dashboard Tool

A GUI tool for managing project items and their property stored in .md files.
Each project item is represented by a .md file with front matter using double colon syntax.

Features:
    - Spreadsheet-like dashboard for viewing and editing project items
    - Mass editing of property with multi-select support
    - Variables stored in .md front matter matching dataview syntax (e.g., DATEMODIFIED::20250718050312)
    - Full .md file editing in side panel

Usage:
    1. Launch the tool and select a project folder
    2. The tool will scan for .md files in item subfolders
    3. Use the spreadsheet interface to edit property
    4. Select multiple items for batch editing
    5. Click item names to edit full .md content

Project Structure:
    project_folder/
    ├── item_example/                        # Item folder
    │   └── item_example.md                  # Item property file
    ├── item_example2/                       # Another item folder
    │   └── item_example2.md                 # Item property file
    └── ...

property Format in .md files:
    DATEMODIFIED::20250718050312
    STATUS::working
    PRIORITY::1
    DESCRIPTION::Project description here
    
    # Item Content
    Main content of the item goes here...
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
from datetime import datetime
import json

class ProjectStatusDashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Project Status Dashboard")
        self.geometry("1800x900")
        
        # Dark theme styling
        self.configure(bg="black")
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        
        # Configure dark theme
        self.style.configure("TLabel", background="black", foreground="white")
        self.style.configure("TButton", background="#3c3c3c", foreground="white")
        self.style.configure("TEntry", background="#404040", foreground="white", insertcolor="white", selectbackground="#606060")
        self.style.configure("TFrame", background="black")
        self.style.configure("TCheckbutton", background="black", foreground="white")
        self.style.configure("Treeview", background="#2c2c2c", foreground="white", fieldbackground="#2c2c2c")
        self.style.configure("Treeview.Heading", background="#3c3c3c", foreground="white")
        
        # Color-coded button styles with muted colors
        # Muted Green for primary actions (Browse, Load, Refresh)
        self.style.configure("Green.TButton", background="#4a6741", foreground="white", focuscolor="none")
        self.style.map("Green.TButton", background=[('active', '#5a7751'), ('pressed', '#3a5731')])
        
        # Muted Blue for secondary actions (Populate MD, Update Selected)
        self.style.configure("Blue.TButton", background="#3d5a7a", foreground="white", focuscolor="none")
        self.style.map("Blue.TButton", background=[('active', '#4d6a8a'), ('pressed', '#2d4a6a')])
        
        # Muted Purple for selection actions (Select All, Clear Selection)
        self.style.configure("Purple.TButton", background="#5a4a7a", foreground="white", focuscolor="none")
        self.style.map("Purple.TButton", background=[('active', '#6a5a8a'), ('pressed', '#4a3a6a')])
        
        # Red for destructive actions (Remove Item)
        self.style.configure("Red.TButton", background="#8b4444", foreground="white", focuscolor="none")
        self.style.map("Red.TButton", background=[('active', '#9b5454'), ('pressed', '#7b3434')])
        
        # Data storage
        self.project_folder = ""
        self.items_data = []
        self.selected_items = set()
        
        # Property fields to display in the dashboard
        self.property_fields = [
            "STATUS", "PRIORITY", "DATEMODIFIED", "DESCRIPTION", 
            "ASSIGNEE", "TAGS", "CATEGORY", "PROGRESS"
        ]
        
        # Exclusion patterns for folders to skip when populating .md files
        self.exclusion_patterns = [
            "00_ref", "00_backup", "00_archive", "00_temp", "00_old",
            ".git", ".vscode", "__pycache__", "node_modules", "venv",
            "backup", "temp", "tmp", "logs", "cache"
        ]
        
        self.create_widgets()
        
    def create_widgets(self):
        """Create the main UI components"""
        # Top toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        # Project folder selection
        ttk.Label(toolbar, text="Project Folder:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.folder_var = tk.StringVar()
        folder_entry = tk.Entry(toolbar, textvariable=self.folder_var, width=60, 
                               bg="#404040", fg="white", insertbackground="white", selectbackground="#606060")
        folder_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        # Primary actions - Muted Green
        ttk.Button(toolbar, text="Browse", command=self.browse_folder, style="Green.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(toolbar, text="Load", command=self.load_project, style="Green.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_data, style="Green.TButton").pack(side=tk.LEFT, padx=(0, 10))
        
        # Secondary actions - Muted Blue
        ttk.Button(toolbar, text="Populate MD", command=self.populate_md_files, style="Blue.TButton").pack(side=tk.LEFT, padx=(0, 5))
        
        # Destructive action - Red
        ttk.Button(toolbar, text="Remove Item", command=self.remove_selected_item, style="Red.TButton").pack(side=tk.LEFT, padx=(0, 5))
        
        # Batch operations
        ttk.Label(toolbar, text="Batch:").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Button(toolbar, text="Update Selected", command=self.batch_update_dialog, style="Blue.TButton").pack(side=tk.LEFT, padx=(0, 5))
        
        # Selection actions - Muted Purple
        ttk.Button(toolbar, text="Select All", command=self.select_all, style="Purple.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Clear Selection", command=self.clear_selection, style="Purple.TButton").pack(side=tk.LEFT)
        
        # Main content area
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Dashboard table
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Create treeview for spreadsheet-like interface
        self.create_treeview(left_panel)
        
        # Right panel - Item editor
        right_panel = ttk.Frame(main_frame, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)
        
        self.create_editor_panel(right_panel)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_treeview(self, parent):
        """Create the main treeview widget for the dashboard"""
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Columns: checkbox, item name, and property fields
        columns = ["Select", "Item Name"] + self.property_fields
        
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20, selectmode="extended")
        
        # Configure columns
        self.tree.heading("Select", text="☐")
        self.tree.column("Select", width=50, minwidth=50)
        
        self.tree.heading("Item Name", text="Item Name", command=lambda: self.sort_by_column("Item Name"))
        self.tree.column("Item Name", width=200, minwidth=150)
        
        for field in self.property_fields:
            self.tree.heading(field, text=field, command=lambda f=field: self.sort_by_column(f))
            self.tree.column(field, width=120, minwidth=80)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack scrollbars and tree
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind events
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<KeyPress>", self.on_tree_keypress)
        self.tree.bind("<Button-3>", self.on_tree_right_click)  # Right-click context menu
        self.tree.bind("<Return>", self.on_tree_enter)
        self.tree.bind("<F2>", self.start_edit_cell)
        
    def create_editor_panel(self, parent):
        """Create the right panel for editing item details"""
        ttk.Label(parent, text="Item Editor", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        # Current item info
        self.current_item_var = tk.StringVar(value="No item selected")
        ttk.Label(parent, textvariable=self.current_item_var).pack(pady=(0, 10))
        
        # Quick property editor
        property_frame = ttk.LabelFrame(parent, text="Quick property Edit")
        property_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.property_vars = {}
        for field in self.property_fields[:4]:  # Show first 4 fields for quick edit
            row_frame = ttk.Frame(property_frame)
            row_frame.pack(fill=tk.X, padx=5, pady=2)
            
            ttk.Label(row_frame, text=f"{field}:", width=12).pack(side=tk.LEFT)
            var = tk.StringVar()
            entry = tk.Entry(row_frame, textvariable=var, bg="#404040", fg="white", 
                           insertbackground="white", selectbackground="#606060")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            entry.bind("<KeyRelease>", lambda e, f=field: self.on_property_change(f))
            
            self.property_vars[field] = var
        
        # Full content editor
        content_frame = ttk.LabelFrame(parent, text="Full Content")
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Text editor with scrollbar
        text_frame = ttk.Frame(content_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.content_text = tk.Text(text_frame, bg="#2c2c2c", fg="white", insertbackground="white",
                                   wrap=tk.WORD, font=("Consolas", 10))
        content_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.content_text.yview)
        self.content_text.configure(yscrollcommand=content_scrollbar.set)
        
        self.content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind content change event
        self.content_text.bind("<KeyRelease>", self.on_content_change)
        
        # Save button
        ttk.Button(content_frame, text="Save Content", command=self.save_current_item).pack(pady=5)
        
        self.current_item = None
        
        # In-place editing variables
        self.edit_item = None
        self.edit_column = None
        self.edit_entry = None
        
        # Sorting variables
        self.sort_column = None
        self.sort_reverse = False
        
        # Multi-cell batch editing variables
        self.selected_cells = set()  # Set of (item_id, column_index) tuples
        self.batch_edit_column = None  # Current column for batch editing
        self.batch_edit_mode = False
        self.cell_colors = {}  # Store original cell colors for restoration
        
    def browse_folder(self):
        """Open folder browser dialog"""
        folder = filedialog.askdirectory(title="Select Project Folder")
        if folder:
            self.folder_var.set(folder)
            
    def load_project(self):
        """Load project from the selected folder"""
        folder = self.folder_var.get().strip()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Error", "Please select a valid project folder")
            return
            
        self.project_folder = folder
        self.scan_project_items()
        self.refresh_treeview()
        self.status_var.set(f"Loaded {len(self.items_data)} items from {folder}")
        
    def populate_md_files(self):
        """Create .md files for item folders that don't have them, skipping exclusion folders"""
        if not self.project_folder or not os.path.exists(self.project_folder):
            messagebox.showerror("Error", "Please load a project folder first")
            return
            
        created_count = 0
        skipped_count = 0
        
        try:
            for item_name in os.listdir(self.project_folder):
                item_path = os.path.join(self.project_folder, item_name)
                
                # Skip files, only process directories
                if not os.path.isdir(item_path):
                    continue
                    
                # Check if folder should be excluded
                if self.should_exclude_folder(item_name):
                    skipped_count += 1
                    continue
                    
                # Check if .md file already exists
                md_file = os.path.join(item_path, f"{item_name}.md")
                
                if not os.path.exists(md_file):
                    # Create the .md file with default property
                    self.create_default_md_file(md_file, item_name)
                    created_count += 1
                    
            # Refresh the data after creating files
            self.scan_project_items()
            self.refresh_treeview()
            
            message = f"Created {created_count} .md files"
            if skipped_count > 0:
                message += f" (skipped {skipped_count} excluded folders)"
                
            self.status_var.set(message)
            
            if created_count > 0:
                messagebox.showinfo("Success", message)
            else:
                messagebox.showinfo("Info", "All item folders already have .md files")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to populate .md files: {e}")
            
    def should_exclude_folder(self, folder_name):
        """Check if a folder should be excluded based on exclusion patterns"""
        folder_lower = folder_name.lower()
        
        for pattern in self.exclusion_patterns:
            if pattern.lower() in folder_lower or folder_lower.startswith(pattern.lower()):
                return True
                
        return False
        
    def create_default_md_file(self, file_path, item_name):
        """Create a default .md file with basic property"""
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        
        default_content_start = f"""---"""
        default_content_status = f"""STATUS::new"""
        default_content_priority = f"""PRIORITY::3"""
        default_content_datemod = f"""DATEMODIFIED::{current_time}"""
        default_content_end = f"""---"""
        default_content_title = f"""# {item_name}"""
        default_content_body = f""""""
        
        # Combine all content parts with newlines
        default_content = "\n".join([
            default_content_start,
            default_content_status,
            default_content_priority,
            default_content_datemod,
            default_content_end,
            "",  # Empty line after front matter
            default_content_title,
            default_content_body
        ])
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(default_content)
        
    def scan_project_items(self):
        """Scan the project folder for .md files in item subfolders"""
        self.items_data = []
        
        if not os.path.exists(self.project_folder):
            return
            
        for item_name in os.listdir(self.project_folder):
            item_path = os.path.join(self.project_folder, item_name)
            
            # Skip files, only process directories
            if not os.path.isdir(item_path):
                continue
                
            # Look for .md file with same name as folder
            md_file = os.path.join(item_path, f"{item_name}.md")
            
            if os.path.exists(md_file):
                item_data = self.parse_md_file(md_file, item_name)
                if item_data:
                    self.items_data.append(item_data)
                    
    def parse_md_file(self, file_path, item_name):
        """Parse a .md file and extract property using double colon syntax from anywhere in the file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract all property with double colon syntax from anywhere in the file
            property = {}
            lines = content.split('\n')
            
            # Scan all lines for double colon property
            for line in lines:
                line = line.strip()
                # Look for KEY::VALUE pattern, but skip markdown headers and comments
                if '::' in line and not line.startswith('#') and not line.startswith('<!--'):
                    # Split only on the first :: to handle values that might contain ::
                    parts = line.split('::', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # Only accept keys that look like property (uppercase, no spaces)
                        if key.isupper() and ' ' not in key and key.isalnum() or '_' in key:
                            property[key] = value
            
            # For main content, we'll keep everything as-is since property can be anywhere
            # We'll just remove the property lines when displaying "clean" content if needed
            main_content_lines = []
            for line in lines:
                line_stripped = line.strip()
                # Skip property lines when building main content
                if '::' in line_stripped and not line_stripped.startswith('#'):
                    parts = line_stripped.split('::', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        if key.isupper() and ' ' not in key and (key.isalnum() or '_' in key):
                            continue  # Skip this property line
                main_content_lines.append(line)
            
            main_content = '\n'.join(main_content_lines).strip()
            
            return {
                'name': item_name,
                'file_path': file_path,
                'property': property,
                'content': main_content,
                'full_content': content
            }
            
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None
            
    def refresh_treeview(self):
        """Refresh the treeview with current items data"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add items
        for item_data in self.items_data:
            values = ["☐", item_data['name']]
            
            # Add property values
            for field in self.property_fields:
                value = item_data['property'].get(field, "")
                values.append(value)
                
            item_id = self.tree.insert("", tk.END, values=values)
            
    def sort_by_column(self, column_name):
        """Sort the treeview by the specified column"""
        # End any current editing
        self.end_edit_cell()
        
        # Determine if we're reversing the sort
        if self.sort_column == column_name:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column_name
            self.sort_reverse = False
            
        # Get all items with their data
        items_with_data = []
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id)["values"]
            items_with_data.append((item_id, values))
            
        # Determine column index for sorting
        if column_name == "Item Name":
            sort_index = 1
        elif column_name in self.property_fields:
            sort_index = self.property_fields.index(column_name) + 2  # +2 for Select and Item Name columns
        else:
            return  # Unknown column
            
        # Sort function that handles different data types
        def sort_key(item):
            values = item[1]
            if sort_index >= len(values):
                return ""
            value = values[sort_index]
            
            # Handle different data types for better sorting
            if column_name == "PRIORITY":
                # Treat as numeric, empty as highest priority (0)
                try:
                    return int(value) if value else 0
                except ValueError:
                    return 999  # Non-numeric priorities go to end
            elif column_name == "DATEMODIFIED":
                # Sort dates chronologically
                return value if value else "0"
            elif column_name == "PROGRESS":
                # Treat as numeric
                try:
                    return int(value) if value else 0
                except ValueError:
                    return 0
            else:
                # String sorting (case-insensitive) - handle mixed types
                if value:
                    return str(value).lower()
                else:
                    return ""
                
        # Sort the items
        items_with_data.sort(key=sort_key, reverse=self.sort_reverse)
        
        # Clear and repopulate the treeview in sorted order
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)
            
        for item_id, values in items_with_data:
            self.tree.insert("", tk.END, values=values)
            
        # Update column headers to show sort indicators
        self.update_column_headers()
        
        # Update status
        sort_direction = "descending" if self.sort_reverse else "ascending"
        self.status_var.set(f"Sorted by {column_name} ({sort_direction})")
        
    def update_column_headers(self):
        """Update column headers to show sort indicators"""
        # Reset all headers first
        self.tree.heading("Item Name", text="Item Name")
        for field in self.property_fields:
            self.tree.heading(field, text=field)
            
        # Add sort indicator to current sort column
        if self.sort_column:
            indicator = " ▼" if self.sort_reverse else " ▲"
            current_text = self.sort_column + indicator
            
            if self.sort_column == "Item Name":
                self.tree.heading("Item Name", text=current_text)
            elif self.sort_column in self.property_fields:
                self.tree.heading(self.sort_column, text=current_text)
            
    def on_tree_click(self, event):
        """Handle tree click events with multi-cell selection support"""
        # End any current editing
        self.end_edit_cell()
        
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            col_index = int(column.replace('#', '')) - 1
            
            if column == "#1":  # Select column
                self.toggle_item_selection(item)
            elif column == "#2":  # Item name column
                self.select_item_for_editing(item)
            elif col_index >= 2:  # property columns
                # Set the target column for batch editing
                self.set_batch_edit_column(col_index)
                # Update status to show what will be batch edited
                self.update_batch_edit_status()
                
    def on_tree_double_click(self, event):
        """Handle double-click to start in-place editing"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            
            # Only allow editing property columns (not select or item name)
            col_index = int(column.replace('#', '')) - 1
            if col_index >= 2:  # property columns start at index 2
                self.start_edit_cell(event, item, column)
            elif column == "#2":  # Item name column - open in editor panel
                self.select_item_for_editing(item)
                
    def on_tree_keypress(self, event):
        """Handle keyboard shortcuts"""
        if event.keysym == "space":
            # Toggle selection with spacebar
            selected = self.tree.selection()
            if selected:
                for item in selected:
                    self.toggle_item_selection(item)
        elif event.keysym == "Delete":
            # Clear selected cells
            if self.selected_cells:
                self.clear_cell_selection()
            else:
                self.clear_selected_cells()
        elif event.keysym == "Escape":
            # Clear cell selection
            self.clear_cell_selection()
        elif event.char and event.char.isprintable():
            # Start typing to edit cell
            if self.selected_cells:
                # Start batch editing with the typed character
                self.start_batch_edit_with_char(event.char)
            else:
                selected = self.tree.selection()
                if len(selected) == 1:
                    # Find the focused column and start editing
                    self.start_edit_cell_with_char(selected[0], event.char)
                
    def on_tree_right_click(self, event):
        """Handle right-click context menu"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.tree.identify_row(event.y)
            column = self.tree.identify_column(event.x)
            
            # Select the item if not already selected
            if item not in self.tree.selection():
                self.tree.selection_set(item)
                
            self.show_context_menu(event, item, column)
            
    def on_tree_enter(self, event):
        """Handle Enter key to start batch editing or confirm edit"""
        if self.edit_entry:
            self.end_edit_cell()
        else:
            selected = self.tree.selection()
            if selected and self.batch_edit_column is not None:
                # Start batch editing mode for selected rows and target column
                self.start_batch_edit_mode_for_rows()
            elif len(selected) == 1:
                # Start editing the first property column
                self.start_edit_cell(event, selected[0], "#3")  # First property column
                
    def select_cell(self, item_id, col_index):
        """Select a single cell for batch editing"""
        self.selected_cells.add((item_id, col_index))
        self.batch_edit_column = col_index
        self.update_cell_visual_feedback()
        self.update_status_for_selection()
        
    def toggle_cell_selection(self, item_id, col_index):
        """Toggle selection of a cell for batch editing"""
        cell_key = (item_id, col_index)
        
        if cell_key in self.selected_cells:
            self.selected_cells.remove(cell_key)
        else:
            # Only allow selection within the same column for batch editing
            if self.batch_edit_column is None or self.batch_edit_column == col_index:
                self.selected_cells.add(cell_key)
                self.batch_edit_column = col_index
            else:
                # Different column - clear selection and start new
                self.clear_cell_selection()
                self.selected_cells.add(cell_key)
                self.batch_edit_column = col_index
                
        self.update_cell_visual_feedback()
        self.update_status_for_selection()
        
    def set_batch_edit_column(self, col_index):
        """Set the target column for batch editing based on selected rows"""
        self.batch_edit_column = col_index
        # Clear any previous cell-specific selections since we're using row selection now
        self.selected_cells.clear()
        
    def update_batch_edit_status(self):
        """Update status bar to show batch edit info based on selected rows"""
        selected_items = self.tree.selection()
        if not selected_items or self.batch_edit_column is None:
            self.status_var.set("Ready")
            return
            
        field_name = self.property_fields[self.batch_edit_column - 2] if self.batch_edit_column >= 2 else "Unknown"
        item_count = len(selected_items)
        
        if item_count == 1:
            self.status_var.set(f"Selected 1 item for {field_name} editing - Press Enter to edit")
        else:
            self.status_var.set(f"Selected {item_count} items for {field_name} batch editing - Press Enter to edit")
        
    def start_batch_edit_mode_for_rows(self):
        """Start batch editing mode for selected rows and target column"""
        selected_items = self.tree.selection()
        if not selected_items or self.batch_edit_column is None:
            return
            
        field_name = self.property_fields[self.batch_edit_column - 2]
        count = len(selected_items)
        
        # Create batch edit dialog
        dialog = tk.Toplevel(self)
        dialog.title(f"Batch Edit {field_name}")
        dialog.geometry("400x200")
        dialog.configure(bg="black")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.winfo_rootx() + 50, self.winfo_rooty() + 50))
        
        # Dialog content
        ttk.Label(dialog, text=f"Set {field_name} for {count} selected items:", 
                 background="black", foreground="white").pack(pady=10)
        
        # Entry field
        entry_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=entry_var, bg="#404040", fg="white", 
                        insertbackground="white", selectbackground="#666666")
        entry.pack(pady=10, padx=20, fill=tk.X)
        entry.focus_set()
        
        # Buttons frame
        button_frame = tk.Frame(dialog, bg="black")
        button_frame.pack(pady=10)
        
        def apply_batch_edit():
            new_value = entry_var.get().strip()
            self.apply_batch_edit_to_rows(selected_items, field_name, new_value)
            dialog.destroy()
            
        def cancel_batch_edit():
            dialog.destroy()
            
        # Buttons
        tk.Button(button_frame, text="Apply", command=apply_batch_edit, 
                 bg="#404040", fg="white", activebackground="#666666").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=cancel_batch_edit,
                 bg="#404040", fg="white", activebackground="#666666").pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to apply
        entry.bind('<Return>', lambda e: apply_batch_edit())
        dialog.bind('<Escape>', lambda e: cancel_batch_edit())
        
    def apply_batch_edit_to_rows(self, selected_items, field_name, new_value):
        """Apply batch edit to all selected rows for the specified field"""
        updated_count = 0
        
        for item_id in selected_items:
            item_values = self.tree.item(item_id)["values"]
            item_name = item_values[1]
            
            # Find the item data
            item_data = next((item for item in self.items_data if item['name'] == item_name), None)
            if not item_data:
                continue
                
            # Update the property
            item_data['property'][field_name] = new_value
            
            # Save to file
            if self.save_item_properties(item_data):
                updated_count += 1
                
                # Update the treeview display
                field_index = self.property_fields.index(field_name)
                col_index = field_index + 2  # Account for checkbox and name columns
                
                # Update the values in the treeview
                updated_values = list(item_values)
                updated_values[col_index] = new_value
                self.tree.item(item_id, values=updated_values)
        
        # Update status
        self.status_var.set(f"Updated {field_name} for {updated_count} items")
        
        # Clear batch edit state
        self.batch_edit_column = None
        
    def save_item_properties(self, item_data):
        """Save updated properties back to the .md file"""
        try:
            md_file = item_data['file_path']
            
            # Read the current file content
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            updated_lines = []
            property_keys_updated = set()
            
            # Process each line, updating existing property or keeping as-is
            for line in lines:
                line_stripped = line.strip()
                
                # Check if this is a property line
                if '::' in line_stripped and not line_stripped.startswith('#') and not line_stripped.startswith('<!--'):
                    parts = line_stripped.split('::', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        # Check if this is a valid property key that we might have updated
                        if key.isupper() and ' ' not in key and (key.isalnum() or '_' in key):
                            if key in item_data['property']:
                                # Update this property line with new value
                                new_value = item_data['property'][key]
                                # Preserve original line indentation
                                indent = line[:len(line) - len(line.lstrip())]
                                updated_lines.append(f"{indent}{key}::{new_value}")
                                property_keys_updated.add(key)
                            else:
                                # Keep the original line if we don't have this key in our property
                                updated_lines.append(line)
                        else:
                            # Not a valid property key, keep original line
                            updated_lines.append(line)
                    else:
                        # Not a proper :: format, keep original line
                        updated_lines.append(line)
                else:
                    # Not a property line, keep as-is
                    updated_lines.append(line)
            
            # Add any new property keys that weren't in the original file
            new_property_lines = []
            for key, value in item_data['property'].items():
                if key not in property_keys_updated and value:  # Only add non-empty values
                    new_property_lines.append(f"{key}::{value}")
            
            # If we have new property, add it at the top of the file
            if new_property_lines:
                # Insert new property after any existing front matter or at the beginning
                insert_index = 0
                # Look for a good place to insert (after any existing property block)
                for i, line in enumerate(updated_lines):
                    if line.strip() and not line.strip().startswith('#') and '::' not in line:
                        insert_index = i
                        break
                
                # Insert new property lines
                for i, new_line in enumerate(new_property_lines):
                    updated_lines.insert(insert_index + i, new_line)
            
            # Write the updated content back to the file
            updated_content = '\n'.join(updated_lines)
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            return True
            
        except Exception as e:
            print(f"Error saving property for {item_data['name']}: {e}")
            return False
        
    def clear_cell_selection(self):
        """Clear all cell selections"""
        # Restore original colors
        for item_id, col_index in self.selected_cells:
            self.restore_cell_color(item_id, col_index)
            
        self.selected_cells.clear()
        self.batch_edit_column = None
        self.batch_edit_mode = False
        self.update_status_for_selection()
        
    def update_cell_visual_feedback(self):
        """Update visual feedback for selected cells"""
        # First restore all cells to normal
        for item_id in self.tree.get_children():
            for col_index in range(2, len(self.property_fields) + 2):
                self.restore_cell_color(item_id, col_index)
                
        # Highlight selected cells
        for item_id, col_index in self.selected_cells:
            self.highlight_cell(item_id, col_index)
            
    def highlight_cell(self, item_id, col_index):
        """Highlight a cell to show it's selected for batch editing"""
        try:
            # Store original tags if not already stored
            if item_id not in self.cell_colors:
                self.cell_colors[item_id] = {}
                
            # Create a unique tag for this cell
            tag_name = f"selected_cell_{item_id}_{col_index}"
            
            # Configure the tag with highlight colors
            self.tree.tag_configure(tag_name, background="#4a6741", foreground="white")
            
            # Apply the tag to the item
            current_tags = list(self.tree.item(item_id, "tags"))
            if tag_name not in current_tags:
                current_tags.append(tag_name)
                self.tree.item(item_id, tags=current_tags)
                
        except Exception as e:
            print(f"Error highlighting cell: {e}")
            
    def restore_cell_color(self, item_id, col_index):
        """Restore a cell to its original color"""
        try:
            tag_name = f"selected_cell_{item_id}_{col_index}"
            current_tags = list(self.tree.item(item_id, "tags"))
            
            if tag_name in current_tags:
                current_tags.remove(tag_name)
                self.tree.item(item_id, tags=current_tags)
                
        except Exception as e:
            print(f"Error restoring cell color: {e}")
            
    def update_status_for_selection(self):
        """Update status bar to show current selection info"""
        if not self.selected_cells:
            self.status_var.set("Ready")
            return
            
        field_name = self.property_fields[self.batch_edit_column - 2] if self.batch_edit_column and self.batch_edit_column >= 2 else "Unknown"
        cell_count = len(self.selected_cells)
        
        # Count unique items (rows) affected
        unique_items = set(item_id for item_id, col_index in self.selected_cells)
        item_count = len(unique_items)
        
        if cell_count == 1:
            self.status_var.set(f"Selected 1 cell in {field_name} column (1 item) - Press Enter to batch edit")
        else:
            if item_count == 1:
                self.status_var.set(f"Selected {cell_count} cells in {field_name} column (1 item) - Press Enter to batch edit")
            else:
                self.status_var.set(f"Selected {cell_count} cells in {field_name} column ({item_count} items) - Press Enter to batch edit")
            
    def start_batch_edit_mode(self):
        """Start batch editing mode with a popup input dialog"""
        if not self.selected_cells or self.batch_edit_column is None:
            return
            
        field_name = self.property_fields[self.batch_edit_column - 2]
        count = len(self.selected_cells)
        
        # Create batch edit dialog
        dialog = tk.Toplevel(self)
        dialog.title(f"Batch Edit {field_name}")
        dialog.geometry("400x200")
        dialog.configure(bg="black")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.winfo_rootx() + 50, self.winfo_rooty() + 50))
        
        # Dialog content
        ttk.Label(dialog, text=f"Set {field_name} for {count} selected items:", 
                 background="black", foreground="white").pack(pady=10)
        
        # Entry field
        entry_var = tk.StringVar()
        entry = tk.Entry(dialog, textvariable=entry_var, bg="#404040", fg="white", 
                        insertbackground="white", selectbackground="#606060", font=('Arial', 12))
        entry.pack(pady=10, padx=20, fill=tk.X)
        entry.focus()
        
        # Buttons
        button_frame = tk.Frame(dialog, bg="black")
        button_frame.pack(pady=10)
        
        def apply_batch_edit():
            value = entry_var.get()
            self.apply_batch_edit_value(value)
            dialog.destroy()
            
        def cancel_batch_edit():
            dialog.destroy()
            
        tk.Button(button_frame, text="Apply", command=apply_batch_edit, 
                 bg="#4a6741", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=cancel_batch_edit, 
                 bg="#3c3c3c", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        entry.bind("<Return>", lambda e: apply_batch_edit())
        dialog.bind("<Escape>", lambda e: cancel_batch_edit())
        
    def start_batch_edit_with_char(self, char):
        """Start batch editing and pre-fill with the typed character"""
        if not self.selected_cells or self.batch_edit_column is None:
            return
            
        field_name = self.property_fields[self.batch_edit_column - 2]
        count = len(self.selected_cells)
        
        # Create batch edit dialog with pre-filled character
        dialog = tk.Toplevel(self)
        dialog.title(f"Batch Edit {field_name}")
        dialog.geometry("400x200")
        dialog.configure(bg="black")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.winfo_rootx() + 50, self.winfo_rooty() + 50))
        
        # Dialog content
        ttk.Label(dialog, text=f"Set {field_name} for {count} selected items:", 
                 background="black", foreground="white").pack(pady=10)
        
        # Entry field with pre-filled character
        entry_var = tk.StringVar(value=char)
        entry = tk.Entry(dialog, textvariable=entry_var, bg="#404040", fg="white", 
                        insertbackground="white", selectbackground="#606060", font=('Arial', 12))
        entry.pack(pady=10, padx=20, fill=tk.X)
        entry.focus()
        entry.icursor(tk.END)  # Position cursor at end
        
        # Buttons
        button_frame = tk.Frame(dialog, bg="black")
        button_frame.pack(pady=10)
        
        def apply_batch_edit():
            value = entry_var.get()
            self.apply_batch_edit_value(value)
            dialog.destroy()
            
        def cancel_batch_edit():
            dialog.destroy()
            
        tk.Button(button_frame, text="Apply", command=apply_batch_edit, 
                 bg="#4a6741", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=cancel_batch_edit, 
                 bg="#3c3c3c", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key
        entry.bind("<Return>", lambda e: apply_batch_edit())
        dialog.bind("<Escape>", lambda e: cancel_batch_edit())
        
    def apply_batch_edit_value(self, value):
        """Apply the batch edit value to all selected cells with safe sequential updates"""
        if not self.selected_cells or self.batch_edit_column is None:
            return
            
        field_name = self.property_fields[self.batch_edit_column - 2]
        updated_count = 0
        failed_count = 0
        
        # Update each selected cell sequentially to avoid file corruption
        for item_id, col_index in self.selected_cells:
            try:
                # Update treeview display
                values = list(self.tree.item(item_id)["values"])
                if col_index < len(values):
                    values[col_index] = value
                    self.tree.item(item_id, values=values)
                    
                    # Update data and save to file (sequential, not parallel)
                    self.update_item_property(item_id, col_index - 2, value)
                    updated_count += 1
                    
                    # Small delay to prevent file system overload
                    self.update_idletasks()
                    
            except Exception as e:
                print(f"Error updating item {item_id}: {e}")
                failed_count += 1
                
        # Clear selection after successful batch edit
        self.clear_cell_selection()
        
        # Update status
        if failed_count == 0:
            self.status_var.set(f"Successfully updated {field_name} for {updated_count} items")
        else:
            self.status_var.set(f"Updated {updated_count} items, {failed_count} failed")
                
    def start_edit_cell(self, event=None, item_id=None, column=None):
        """Start in-place editing of a cell"""
        # End any current editing first
        self.end_edit_cell()
        
        # Determine what to edit
        if item_id is None or column is None:
            if event:
                region = self.tree.identify_region(event.x, event.y)
                if region == "cell":
                    column = self.tree.identify_column(event.x, event.y)
                    item_id = self.tree.identify_row(event.y)
            else:
                # Use current selection
                selected = self.tree.selection()
                if selected:
                    item_id = selected[0]
                    column = "#3"  # Default to first property column
                    
        if not item_id or not column:
            return
            
        # Only allow editing property columns
        col_index = int(column.replace('#', '')) - 1
        if col_index < 2:  # Skip select and item name columns
            return
            
        # Get current value
        values = self.tree.item(item_id)["values"]
        if col_index >= len(values):
            return
            
        current_value = values[col_index]
        
        # Get cell position
        bbox = self.tree.bbox(item_id, column)
        if not bbox:
            return
            
        # Create entry widget for editing
        self.edit_item = item_id
        self.edit_column = column
        
        self.edit_entry = tk.Entry(self.tree, bg="#404040", fg="white", insertbackground="white")
        self.edit_entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        self.edit_entry.insert(0, current_value)
        self.edit_entry.select_range(0, tk.END)
        self.edit_entry.focus()
        
        # Bind events
        self.edit_entry.bind("<Return>", lambda e: self.end_edit_cell(save=True))
        self.edit_entry.bind("<Escape>", lambda e: self.end_edit_cell(save=False))
        self.edit_entry.bind("<FocusOut>", lambda e: self.end_edit_cell(save=True))
        
    def start_edit_cell_with_char(self, item_id, char):
        """Start editing a cell and insert the typed character"""
        self.start_edit_cell(item_id=item_id, column="#3")  # Default to first property column
        if self.edit_entry:
            self.edit_entry.delete(0, tk.END)
            self.edit_entry.insert(0, char)
            
    def end_edit_cell(self, save=True):
        """End in-place editing and optionally save the value"""
        if not self.edit_entry:
            return
            
        if save and self.edit_item and self.edit_column:
            # Get new value
            new_value = self.edit_entry.get()
            
            # Update the treeview
            values = list(self.tree.item(self.edit_item)["values"])
            col_index = int(self.edit_column.replace('#', '')) - 1
            values[col_index] = new_value
            self.tree.item(self.edit_item, values=values)
            
            # Update the data and save to file
            self.update_item_property(self.edit_item, col_index - 2, new_value)  # -2 because property starts at index 2
            
        # Clean up
        if self.edit_entry:
            self.edit_entry.destroy()
        self.edit_entry = None
        self.edit_item = None
        self.edit_column = None
        
    def clear_selected_cells(self):
        """Clear the values of selected cells"""
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        # For now, clear the first property column of selected items
        for item_id in selected_items:
            values = list(self.tree.item(item_id)["values"])
            if len(values) > 2:  # Has property columns
                values[2] = ""  # Clear first property column (STATUS)
                self.tree.item(item_id, values=values)
                self.update_item_property(item_id, 0, "")  # Update STATUS field
                
    def show_context_menu(self, event, item_id, column):
        """Show context menu for spreadsheet operations"""
        context_menu = tk.Menu(self, tearoff=0, bg="#3c3c3c", fg="white")
        
        # Get column info
        col_index = int(column.replace('#', '')) - 1
        if col_index >= 2:  # property column
            field_name = self.property_fields[col_index - 2]
            
            context_menu.add_command(label=f"Edit {field_name}", 
                                   command=lambda: self.start_edit_cell(item_id=item_id, column=column))
            context_menu.add_separator()
            
            # Quick set options for common fields
            if field_name == "STATUS":
                for status in ["new", "working", "review", "done", "blocked"]:
                    context_menu.add_command(label=f"Set to '{status}'", 
                                           command=lambda s=status: self.set_selected_field_value(field_name, s))
            elif field_name == "PRIORITY":
                for priority in ["1", "2", "3", "4", "5"]:
                    context_menu.add_command(label=f"Priority {priority}", 
                                           command=lambda p=priority: self.set_selected_field_value(field_name, p))
                                           
        context_menu.add_separator()
        context_menu.add_command(label="Clear Cell", command=lambda: self.clear_cell(item_id, col_index))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
            
    def set_selected_field_value(self, field_name, value):
        """Set a field value for all selected items"""
        selected_items = self.tree.selection()
        if not selected_items:
            return
            
        field_index = self.property_fields.index(field_name) if field_name in self.property_fields else -1
        if field_index == -1:
            return
            
        updated_count = 0
        for item_id in selected_items:
            # Update treeview
            values = list(self.tree.item(item_id)["values"])
            col_index = field_index + 2  # +2 because property starts at column 2
            if col_index < len(values):
                values[col_index] = value
                self.tree.item(item_id, values=values)
                
                # Update data and save
                self.update_item_property(item_id, field_index, value)
                updated_count += 1
                
        self.status_var.set(f"Updated {field_name} for {updated_count} items")
        
    def clear_cell(self, item_id, col_index):
        """Clear a specific cell"""
        if col_index >= 2:  # Only property columns
            values = list(self.tree.item(item_id)["values"])
            if col_index < len(values):
                values[col_index] = ""
                self.tree.item(item_id, values=values)
                self.update_item_property(item_id, col_index - 2, "")
                
    def update_item_property(self, item_id, field_index, new_value):
        """Update an item's properties and save to file"""
        print(f"DEBUG: update_item_property called - item_id: {item_id}, field_index: {field_index}, new_value: '{new_value}'")
        
        # Get item name
        values = self.tree.item(item_id)["values"]
        item_name = values[1]
        print(f"DEBUG: Updating item: {item_name}")
        
        # Find the item data
        item_data = next((item for item in self.items_data if item['name'] == item_name), None)
        if not item_data:
            print(f"ERROR: Could not find item data for {item_name}")
            return
        
        print(f"DEBUG: Found item data with keys: {list(item_data.keys())}")
            
        # Update properties
        if field_index < len(self.property_fields):
            field_name = self.property_fields[field_index]
            print(f"DEBUG: Updating field '{field_name}' to '{new_value}'")
            print(f"DEBUG: Current property keys: {list(item_data.get('property', {}).keys())}")
            
            if 'property' not in item_data:
                print(f"ERROR: Item data missing 'property' key for {item_name}")
                print(f"ERROR: Available keys: {list(item_data.keys())}")
                return
                
            item_data['property'][field_name] = new_value
            print(f"DEBUG: Successfully set {field_name} = '{new_value}'")
            
            # Auto-update DATEMODIFIED
            current_time = datetime.now().strftime("%Y%m%d%H%M%S")
            item_data['property']['DATEMODIFIED'] = current_time
            print(f"DEBUG: Updated DATEMODIFIED to {current_time}")
            
            # Save to file
            try:
                print(f"DEBUG: Attempting to save item {item_name} to disk")
                self.save_item_to_disk(item_data)
                print(f"DEBUG: Successfully saved {item_name} to disk")
                
                # Update DATEMODIFIED in treeview if it's visible
                if 'DATEMODIFIED' in self.property_fields:
                    datemod_index = self.property_fields.index('DATEMODIFIED') + 2
                    if datemod_index < len(values):
                        values = list(self.tree.item(item_id)["values"])
                        values[datemod_index] = current_time
                        self.tree.item(item_id, values=values)
                        
            except Exception as e:
                print(f"ERROR: Exception occurred while saving {item_name}:")
                print(f"ERROR: Exception type: {type(e).__name__}")
                print(f"ERROR: Exception message: {str(e)}")
                print(f"ERROR: Item data structure: {item_data}")
                import traceback
                print(f"ERROR: Full traceback:")
                traceback.print_exc()
                messagebox.showerror("Error", f"Failed to save {item_name}: {e}")
                
    def toggle_item_selection(self, item_id):
        """Toggle selection state of an item"""
        current_values = list(self.tree.item(item_id)["values"])
        
        if item_id in self.selected_items:
            self.selected_items.remove(item_id)
            current_values[0] = "☐"
        else:
            self.selected_items.add(item_id)
            current_values[0] = "☑"
            
        self.tree.item(item_id, values=current_values)
        
    def select_item_for_editing(self, item_id):
        """Select an item for editing in the right panel"""
        item_values = self.tree.item(item_id)["values"]
        item_name = item_values[1]
        
        # Find the item data
        item_data = next((item for item in self.items_data if item['name'] == item_name), None)
        if not item_data:
            print(f"Warning: Could not find item data for {item_name}")
            return
            
        self.current_item = item_data
        self.current_item_var.set(f"Editing: {item_name}")
        
        # Update property fields in the right panel
        for field in self.property_fields[:4]:  # First 4 fields for quick edit
            if field in self.property_vars:
                value = item_data['property'].get(field, "")
                self.property_vars[field].set(value)
                
        # Update content editor with full content
        self.content_text.delete("1.0", tk.END)
        self.content_text.insert("1.0", item_data['full_content'])
        
        # Update status
        self.status_var.set(f"Selected item: {item_name}")
        
    def select_cell(self, item_id, col_index):
        """Select a single cell for batch editing"""
        self.selected_cells.add((item_id, col_index))
        self.batch_edit_column = col_index
        self.update_cell_visual_feedback()
        self.update_status_for_selection()
        
    def on_property_change(self, field):
        """Handle property field changes"""
        if not self.current_item:
            return
            
        new_value = self.property_vars[field].get()
        self.current_item['property'][field] = new_value
        
        # Update the treeview
        self.update_treeview_item(self.current_item['name'])
        
        # Auto-save
        self.save_current_item()
        
    def on_content_change(self, event):
        """Handle content editor changes"""
        if not self.current_item:
            return
            
        # Update the full content
        self.current_item['full_content'] = self.content_text.get("1.0", tk.END + "-1c")
        
    def update_treeview_item(self, item_name):
        """Update a specific item in the treeview"""
        for item_id in self.tree.get_children():
            values = self.tree.item(item_id)["values"]
            if values[1] == item_name:
                # Update the values
                item_data = next((item for item in self.items_data if item['name'] == item_name), None)
                if item_data:
                    new_values = [values[0], item_name]  # Keep selection state and name
                    for field in self.property_fields:
                        new_values.append(item_data['property'].get(field, ""))
                    self.tree.item(item_id, values=new_values)
                break
                
    def save_current_item(self):
        """Save the currently selected item to disk"""
        if not self.current_item:
            return
            
        try:
            # Reconstruct the file content with property front matter
            content_lines = []
            
            # Add properties with double colon syntax
            for field in self.property_fields:
                if field in self.current_item['property'] and self.current_item['property'][field]:
                    content_lines.append(f"{field}::{self.current_item['property'][field]}")
                    
            # Add a blank line before main content if there's property
            if content_lines:
                content_lines.append("")
                
            # Add main content (everything after property)
            full_content = self.current_item['full_content']
            lines = full_content.split('\n')
            
            # Find where main content starts (after property)
            main_start = 0
            for i, line in enumerate(lines):
                if '::' not in line or line.startswith('#'):
                    main_start = i
                    break
                    
            # Skip empty lines at the start of main content
            while main_start < len(lines) and lines[main_start].strip() == '':
                main_start += 1
                
            if main_start < len(lines):
                content_lines.extend(lines[main_start:])
                
            # Write to file
            final_content = '\n'.join(content_lines)
            with open(self.current_item['file_path'], 'w', encoding='utf-8') as f:
                f.write(final_content)
                
            # Update DATEMODIFIED
            current_time = datetime.now().strftime("%Y%m%d%H%M%S")
            self.current_item['properties']['DATEMODIFIED'] = current_time
            
            if 'DATEMODIFIED' in self.property_vars:
                self.property_vars['DATEMODIFIED'].set(current_time)
                
            self.update_treeview_item(self.current_item['name'])
            self.status_var.set(f"Saved {self.current_item['name']}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save item: {e}")
            
    def select_all(self):
        """Select all items"""
        for item_id in self.tree.get_children():
            if item_id not in self.selected_items:
                self.toggle_item_selection(item_id)
                
    def clear_selection(self):
        """Clear all selections"""
        for item_id in list(self.selected_items):
            self.toggle_item_selection(item_id)
            
    def remove_selected_item(self):
        """Remove selected items' .md files and remove from dashboard"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "No items selected for removal")
            return
        
        # Collect item information for all selected items
        items_to_remove = []
        for item_id in selected:
            item_values = self.tree.item(item_id)["values"]
            item_name = item_values[1]
            
            # Find the item data
            item_data = next((item for item in self.items_data if item['name'] == item_name), None)
            if item_data:
                items_to_remove.append({
                    'id': item_id,
                    'name': item_name,
                    'data': item_data
                })
        
        if not items_to_remove:
            messagebox.showerror("Error", "Could not find data for selected items")
            return
        
        # Create confirmation message listing all items
        if len(items_to_remove) == 1:
            item = items_to_remove[0]
            confirmation_msg = (
                f"Are you sure you want to remove '{item['name']}'?\n\n"
                f"This will permanently delete the .md file:\n{item['data']['file_path']}\n\n"
                f"This action cannot be undone."
            )
        else:
            item_list = "\n".join([f"• {item['name']} ({item['data']['file_path']})" for item in items_to_remove])
            confirmation_msg = (
                f"Are you sure you want to remove {len(items_to_remove)} items?\n\n"
                f"Items to be deleted:\n{item_list}\n\n"
                f"This will permanently delete all .md files.\n"
                f"This action cannot be undone."
            )
        
        # Single confirmation dialog for all items
        result = messagebox.askyesno(
            "Confirm Removal",
            confirmation_msg,
            icon="warning"
        )
        
        if not result:
            return
        
        # Remove all selected items
        removed_count = 0
        removed_names = []
        
        try:
            import os
            for item in items_to_remove:
                try:
                    # Delete the .md file
                    if os.path.exists(item['data']['file_path']):
                        os.remove(item['data']['file_path'])
                        print(f"DEBUG: Deleted file {item['data']['file_path']}")
                    
                    # Remove from items_data
                    self.items_data = [i for i in self.items_data if i['name'] != item['name']]
                    
                    # Remove from treeview
                    self.tree.delete(item['id'])
                    
                    # Clear current item if it was one of the deleted ones
                    if self.current_item and self.current_item['name'] == item['name']:
                        self.current_item = None
                        self.current_item_var.set("No item selected")
                        self.content_text.delete("1.0", tk.END)
                        for field in self.property_fields[:4]:
                            if field in self.property_vars:
                                self.property_vars[field].set("")
                    
                    removed_count += 1
                    removed_names.append(item['name'])
                    print(f"DEBUG: Successfully removed item {item['name']}")
                    
                except Exception as e:
                    print(f"ERROR: Failed to remove {item['name']}: {e}")
                    messagebox.showerror("Error", f"Failed to remove {item['name']}: {str(e)}")
            
            # Update status
            if removed_count == 1:
                self.status_var.set(f"Removed item: {removed_names[0]}")
            else:
                self.status_var.set(f"Removed {removed_count} items: {', '.join(removed_names)}")
                
        except Exception as e:
            print(f"ERROR: Exception during bulk removal: {e}")
            messagebox.showerror("Error", f"Failed to remove items: {str(e)}")
            
    def batch_update_dialog(self):
        """Open dialog for batch updating selected items"""
        if not self.selected_items:
            messagebox.showwarning("Warning", "No items selected for batch update")
            return
            
        # Create batch update dialog
        dialog = tk.Toplevel(self)
        dialog.title("Batch Update")
        dialog.geometry("400x300")
        dialog.configure(bg="black")
        
        # Apply dark theme to dialog
        dialog_style = ttk.Style()
        dialog_style.configure("Dialog.TLabel", background="black", foreground="white")
        dialog_style.configure("Dialog.TFrame", background="black")
        
        ttk.Label(dialog, text=f"Update {len(self.selected_items)} selected items:", 
                 style="Dialog.TLabel").pack(pady=10)
        
        # Fields to update
        update_vars = {}
        for field in self.property_fields:
            frame = ttk.Frame(dialog, style="Dialog.TFrame")
            frame.pack(fill=tk.X, padx=20, pady=2)
            
            var = tk.StringVar()
            check_var = tk.BooleanVar()
            
            ttk.Checkbutton(frame, text=field, variable=check_var, 
                           style="Dialog.TCheckbutton").pack(side=tk.LEFT)
            ttk.Entry(frame, textvariable=var, width=20).pack(side=tk.RIGHT)
            
            update_vars[field] = (check_var, var)
            
        # Buttons
        button_frame = ttk.Frame(dialog, style="Dialog.TFrame")
        button_frame.pack(pady=20)
        
        def apply_batch_update():
            self.apply_batch_update(update_vars)
            dialog.destroy()
            
        ttk.Button(button_frame, text="Apply", command=apply_batch_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def apply_batch_update(self, update_vars):
        """Apply batch updates to selected items"""
        updated_count = 0
        
        for item_id in self.selected_items:
            item_values = self.tree.item(item_id)["values"]
            item_name = item_values[1]
            
            # Find the item data
            item_data = next((item for item in self.items_data if item['name'] == item_name), None)
            if not item_data:
                continue
                
            # Apply updates
            for field, (check_var, value_var) in update_vars.items():
                if check_var.get():  # Field is selected for update
                    new_value = value_var.get()
                    item_data['property'][field] = new_value
                    
            # Save the item
            try:
                self.save_item_to_disk(item_data)
                updated_count += 1
            except Exception as e:
                print(f"Error updating {item_name}: {e}")
                
        # Refresh the display
        self.refresh_treeview()
        self.status_var.set(f"Updated {updated_count} items")
        
    def save_item_to_disk(self, item_data):
        """Save an item's data to its .md file"""
        print(f"DEBUG: save_item_to_disk called for item: {item_data.get('name', 'UNKNOWN')}")
        print(f"DEBUG: item_data keys: {list(item_data.keys())}")
        
        content_lines = []
        
        # Add property
        for field in self.property_fields:
            if field in item_data['property'] and item_data['property'][field]:
                content_lines.append(f"{field}::{item_data['property'][field]}")
                print(f"DEBUG: Added property {field}::{item_data['property'][field]}")
                
        # Add blank line and main content
        if content_lines:
            content_lines.append("")
            
        # Extract main content (non-property part)
        if 'content' in item_data and item_data['content']:
            content_lines.append(item_data['content'])
            
        # Write to file
        with open(item_data['file_path'], 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_lines))
            
        # Update modification time
        current_time = datetime.now().strftime("%Y%m%d%H%M%S")
        item_data['property']['DATEMODIFIED'] = current_time
        
    def refresh_data(self):
        """Refresh data from disk"""
        if self.project_folder:
            self.scan_project_items()
            self.refresh_treeview()
            self.status_var.set(f"Refreshed {len(self.items_data)} items")

def main():
    app = ProjectStatusDashboard()
    app.mainloop()

if __name__ == "__main__":
    main()
