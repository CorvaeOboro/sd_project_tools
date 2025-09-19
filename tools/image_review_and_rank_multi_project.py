"""
IMAGE REVIEW AND RANK PROJECT SCALE
Browse folders of images, move images into ranked folders with mouse clicks
Project scale review and ranking for diffusion projects
Supports animated webp with temp preview 
Set and Save Project settings

TODO:
- add a button near the top that will open file explorer to the current folder that is being viewed 
- if the folder contains images that are vertical aspect ratio , then adjust the spacing . we dont really want to do this dynamiacally , instead we want to decide once on loading the folder , setting the spacing variable then . if a new folder is selected then the calculation occurs again .
- add a button to view the "01" subfolder , the best of the best in the current folder, like a toggle
"""
# ===========================================================================================
import os
import sys
import json
import tempfile
import shutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout,
                             QWidget, QGridLayout, QScrollArea, QPushButton, QHBoxLayout,
                             QLineEdit, QFileDialog, QCheckBox, QScrollBar, QFrame)
from PyQt5.QtGui import QPixmap, QMouseEvent, QFontMetrics, QImage, QMovie, QColor
from PyQt5.QtCore import (Qt, QThreadPool, QRunnable, pyqtSignal, QObject,
                          QSize, QEvent, QRect, QPoint, QTimer)
import qdarkstyle

# ===========================================================================================
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class ImageLoader(QRunnable):
    """
    ImageLoader handles normal images and animated WebP/WebM.
    For animated images, just flag them; do not create temp files here.
    """
    def __init__(self, image_paths, image_width, image_height, temp_dir):
        super().__init__()
        self.image_paths = image_paths
        self.image_width = image_width
        self.image_height = image_height
        self.temp_dir = temp_dir
        self.signals = WorkerSignals()

    def run(self):
        images = []
        for path in self.image_paths:
            ext = os.path.splitext(path)[1].lower()
            if ext in ('.webp', '.webm'):
                images.append((path, None, True))  # (orig_path, None, is_animated)
            else:
                # Static image: create a thumbnail
                try:
                    image = QImage(path)
                    if image.isNull():
                        continue
                    thumbnail = image.scaled(
                        self.image_width,
                        self.image_height,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    images.append((path, thumbnail, False))
                except Exception as e:
                    self.signals.error.emit((e, path))

        self.signals.result.emit(images)
        self.signals.finished.emit()

# ===========================================================================================
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Settings file path
        self.settings_file = os.path.join(os.path.dirname(__file__), 'image_review_settings.json')
        
        # Basic config
        self.project_folder = os.getcwd()
        self.middle_folder = ''
        self.category_exclusion_list = []
        self.item_exclusion_prefix = '00_'
        self.default_font_size = 12
        self.image_width = 200
        self.image_height = 200
        self.current_category = None
        self.current_item = None
        self.folder_path = ''
        self.current_project_name = ''

        # Data structures
        self.images = []
        self.image_labels = []       # holds references to labels that are currently displayed
        self.image_cache = {}        # For static images: path -> QPixmap
        self.webp_movies = {}        # For animated WebP: path -> QMovie or None
        self.item_buttons_dict = {}  # ITEM buttons by name
        self.item_image_counts = {}  # Count images per ITEM
        self.threadpool = QThreadPool()

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Image Review and Rank --- LEFT CLICK = 1 --- RIGHT CLICK = 2")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: black;")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(2)

        # Project settings panel at the very top
        self.settings_widget = QWidget()
        self.settings_layout = QHBoxLayout(self.settings_widget)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_layout.setSpacing(2)
        
        # Project name input
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Project Settings Name")
        self.project_name_input.setText(self.current_project_name)
        
        # Save settings button
        self.save_settings_btn = QPushButton("Save Settings")
        self.save_settings_btn.clicked.connect(self.save_current_settings)
        
        # Add to settings layout
        self.settings_layout.addWidget(self.project_name_input)
        self.settings_layout.addWidget(self.save_settings_btn)
        
        # Project buttons container
        self.projects_container = QFrame()
        self.projects_layout = QHBoxLayout(self.projects_container)
        self.projects_layout.setContentsMargins(0, 0, 0, 0)
        self.projects_layout.setSpacing(2)
        self.load_project_buttons()
        
        # Add settings widgets to main layout
        self.main_layout.addWidget(self.settings_widget)
        self.main_layout.addWidget(self.projects_container)
        
        # Add a separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #404040; margin: 0;")
        separator.setMaximumHeight(1)
        self.main_layout.addWidget(separator)

        # Top panel for PROJECT folder selection
        self.top_widget = QWidget()
        self.top_layout = QHBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(2)
        self.project_line_edit = QLineEdit()
        self.project_line_edit.setPlaceholderText("Enter PROJECT folder path")
        self.project_line_edit.setText(self.project_folder)
        self.project_line_edit.returnPressed.connect(self.project_folder_changed)

        self.middle_folder_line_edit = QLineEdit()
        self.middle_folder_line_edit.setPlaceholderText("Enter optional middle folder name")
        self.middle_folder_line_edit.returnPressed.connect(self.middle_folder_changed)

        self.use_gen_folder_checkbox = QCheckBox("Use 'gen' folder")
        self.use_gen_folder_checkbox.setChecked(True)
        self.use_gen_folder_checkbox.toggled.connect(self.use_gen_folder_toggled)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_project_folder)

        # Add widgets to the top layout
        self.top_layout.addWidget(self.project_line_edit)
        self.top_layout.addWidget(self.middle_folder_line_edit)
        self.top_layout.addWidget(self.use_gen_folder_checkbox)
        self.top_layout.addWidget(self.browse_button)
        self.main_layout.addWidget(self.top_widget)

        # Main horizontal layout for CATEGORY, ITEM, and images
        self.horizontal_layout = QHBoxLayout()
        self.main_layout.addLayout(self.horizontal_layout)

        # Left panel (CATEGORY)
        self.category_widget = QWidget()
        self.category_layout = QVBoxLayout()
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setSpacing(1)
        self.category_widget.setLayout(self.category_layout)
        self.category_scroll_area = QScrollArea()
        self.category_scroll_area.setWidgetResizable(True)
        self.category_scroll_area.setWidget(self.category_widget)
        self.horizontal_layout.addWidget(self.category_scroll_area)

        self.category_multiplier_line_edit = QLineEdit()
        self.category_multiplier_line_edit.setPlaceholderText("Multiplier (default 1.0)")
        self.category_multiplier_line_edit.setText("1.0")
        self.category_multiplier_line_edit.returnPressed.connect(self.adjust_sizes)
        self.category_layout.addWidget(self.category_multiplier_line_edit)

        # Middle panel (ITEM)
        self.item_widget = QWidget()
        self.item_layout = QVBoxLayout()
        self.item_layout.setContentsMargins(0, 0, 0, 0)
        self.item_layout.setSpacing(1)
        self.item_widget.setLayout(self.item_layout)
        self.item_scroll_area = QScrollArea()
        self.item_scroll_area.setWidgetResizable(True)
        self.item_scroll_area.setWidget(self.item_widget)
        self.horizontal_layout.addWidget(self.item_scroll_area)

        self.item_multiplier_line_edit = QLineEdit()
        self.item_multiplier_line_edit.setPlaceholderText("Multiplier (default 1.0)")
        self.item_multiplier_line_edit.setText("1.0")
        self.item_multiplier_line_edit.returnPressed.connect(self.adjust_sizes)
        self.item_layout.addWidget(self.item_multiplier_line_edit)

        # Right panel (images)
        self.image_widget = QWidget()
        self.image_layout = QVBoxLayout()
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.image_layout.setSpacing(1)
        self.image_widget.setLayout(self.image_layout)
        self.horizontal_layout.addWidget(self.image_widget)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.scroll_area.setWidget(self.grid_widget)
        self.image_layout.addWidget(self.scroll_area)

        self.image_multiplier_line_edit = QLineEdit()
        self.image_multiplier_line_edit.setPlaceholderText("Multiplier (default 1.0)")
        self.image_multiplier_line_edit.setText("1.0")
        self.image_multiplier_line_edit.returnPressed.connect(self.adjust_sizes)
        self.image_layout.addWidget(self.image_multiplier_line_edit)

        # --- Filename hover label (added for user request) ---
        filename_row = QHBoxLayout()
        filename_row.addStretch(1)
        self.filename_hover_label = QLabel("")
        self.filename_hover_label.setStyleSheet("color: #A0A0A0; background: transparent; font-size: 12px;")
        filename_row.addWidget(self.filename_hover_label)
        self.image_layout.addLayout(filename_row)

        # Connect scroll events to trigger lazy loading
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.update_visible_movies)
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.update_visible_movies)

        # Load initial CATEGORY buttons
        self.load_categories()

    # -----------------------------------------------------------------------
    # Folder & UI Setup
    # -----------------------------------------------------------------------
    def project_folder_changed(self):
        self.project_folder = self.project_line_edit.text()
        if os.path.exists(self.project_folder):
            self.load_categories()
        else:
            # Replace QMessageBox with status label
            status_label = QLabel("The specified PROJECT folder does not exist.")
            status_label.setStyleSheet("color: red;")
            self.main_layout.addWidget(status_label)
            QTimer.singleShot(3000, status_label.deleteLater)

    def middle_folder_changed(self):
        self.middle_folder = self.middle_folder_line_edit.text()
        if self.current_category:
            category_path = os.path.join(self.project_folder, self.current_category)
            self.load_items(category_path)

    def browse_project_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select PROJECT Directory")
        if folder:
            self.project_folder = folder
            self.project_line_edit.setText(self.project_folder)
            self.load_categories()

    def use_gen_folder_toggled(self, checked):
        # Reload items to update image counts and button colors
        if self.current_category:
            category_path = os.path.join(self.project_folder, self.current_category)
            self.load_items(category_path)
            # If an item is currently selected, reload images
            if self.current_item:
                if self.middle_folder:
                    item_path = os.path.join(category_path, self.middle_folder, self.current_item)
                else:
                    item_path = os.path.join(category_path, self.current_item)
                self.load_images(item_path)

    # -----------------------------------------------------------------------
    # Load Categories and Items
    # -----------------------------------------------------------------------
    def load_categories(self):
        # Clear existing CATEGORY buttons (except the lineEdit)
        for i in reversed(range(self.category_layout.count() - 1)):
            widget = self.category_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        categories = [
            name for name in os.listdir(self.project_folder)
            if os.path.isdir(os.path.join(self.project_folder, name))
            and name not in self.category_exclusion_list
        ]
        categories.sort()

        self.category_buttons = []
        for category in categories:
            button = QPushButton(category)
            button.clicked.connect(self.category_button_clicked)
            self.category_layout.insertWidget(self.category_layout.count() - 1, button)
            self.category_buttons.append(button)

        self.adjust_sizes()

    def category_button_clicked(self):
        button = self.sender()
        category_name = button.text()
        self.current_category = category_name
        category_path = os.path.join(self.project_folder, category_name)
        self.load_items(category_path)

    def load_items(self, category_path):
        for i in reversed(range(self.item_layout.count() - 1)):
            widget = self.item_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        self.item_buttons_dict.clear()
        self.item_image_counts.clear()
        self.item_buttons = []

        if self.middle_folder:
            item_parent_path = os.path.join(category_path, self.middle_folder)
        else:
            item_parent_path = category_path

        if not os.path.exists(item_parent_path):
            # Replace QMessageBox with status label
            status_label = QLabel(f"Item folder not found in {item_parent_path}")
            status_label.setStyleSheet("color: red;")
            self.main_layout.addWidget(status_label)
            QTimer.singleShot(3000, status_label.deleteLater)
            return

        items = [
            name for name in os.listdir(item_parent_path)
            if os.path.isdir(os.path.join(item_parent_path, name))
            and not name.startswith(self.item_exclusion_prefix)
        ]
        items.sort()

        for item in items:
            button = QPushButton(item)
            button.clicked.connect(self.item_button_clicked)
            self.item_layout.insertWidget(self.item_layout.count() - 1, button)
            self.item_buttons.append(button)
            self.item_buttons_dict[item] = button

            # Count images
            if self.middle_folder:
                item_path = os.path.join(category_path, self.middle_folder, item)
            else:
                item_path = os.path.join(category_path, item)

            if self.use_gen_folder_checkbox.isChecked():
                image_folder_path = os.path.join(item_path, 'gen')
            else:
                image_folder_path = item_path

            if os.path.exists(image_folder_path):
                valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
                num_images = len([
                    f for f in os.listdir(image_folder_path)
                    if os.path.isfile(os.path.join(image_folder_path, f)) 
                    and f.lower().endswith(valid_exts)
                ])
            else:
                num_images = 0

            self.item_image_counts[item] = num_images

        self.adjust_sizes()

    def item_button_clicked(self):
        button = self.sender()
        item_name = button.text()
        self.current_item = item_name
        category_path = os.path.join(self.project_folder, self.current_category)
        if self.middle_folder:
            item_path = os.path.join(category_path, self.middle_folder, item_name)
        else:
            item_path = os.path.join(category_path, item_name)
        self.load_images(item_path)

    # -----------------------------------------------------------------------
    # Load & Display Images
    # -----------------------------------------------------------------------
    def load_images(self, item_path):
        if self.use_gen_folder_checkbox.isChecked():
            image_folder_path = os.path.join(item_path, 'gen')
            if not os.path.exists(image_folder_path):
                # Replace QMessageBox with status label
                status_label = QLabel(f"'gen' folder not found in {item_path}")
                status_label.setStyleSheet("color: red;")
                self.main_layout.addWidget(status_label)
                QTimer.singleShot(3000, status_label.deleteLater)
                return
        else:
            image_folder_path = item_path

        self.folder_path = image_folder_path
        valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
        self.images = [
            os.path.join(self.folder_path, file)
            for file in os.listdir(image_folder_path)
            if file.lower().endswith(valid_exts) and os.path.isfile(os.path.join(image_folder_path, file))
        ]
        self.display_images_async()

    def display_images_async(self):
        # Clear existing labels
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        self.image_labels = []
        self.image_cache.clear()
        self.webp_movies.clear()
        self.animated_temp_map = {}  # orig_path -> temp_path

        # Create/ensure temp dir exists
        if hasattr(self, 'folder_path') and self.folder_path:
            temp_dir = os.path.join(self.folder_path, 'temp_anim')
        else:
            temp_dir = os.path.join(tempfile.gettempdir(), 'image_review_temp_anim')
        os.makedirs(temp_dir, exist_ok=True)
        self.temp_dir = temp_dir

        # Start asynchronous load
        worker = ImageLoader(self.images, self.image_width, self.image_height, temp_dir)
        worker.signals.result.connect(self.on_images_loaded)
        self.threadpool.start(worker)

    def on_images_loaded(self, images):
        """
        images: list of (orig_path, thumbnail_or_temp, is_animated)
        For animated: (orig_path, temp_path, True)
        For static: (orig_path, thumbnail, False)
        """
        num_columns = max(1, self.scroll_area.width() // (self.image_width + 20))

        for i, (image_path, thumb_or_temp, is_animated) in enumerate(images):
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setObjectName(image_path)

            if is_animated:
                # We'll lazy-load the QMovie upon visibility
                self.webp_movies[image_path] = None
                self.animated_temp_map[image_path] = None  # temp path will be set on demand
                # Placeholder gray
                placeholder = QImage(self.image_width, self.image_height, QImage.Format_ARGB32)
                placeholder.fill(QColor("darkGray"))
                label.setPixmap(QPixmap.fromImage(placeholder))
            else:
                # Static image
                pixmap = QPixmap.fromImage(thumb_or_temp)
                label.setPixmap(pixmap)
                self.image_cache[image_path] = pixmap

            self.grid_layout.addWidget(label, i // num_columns, i % num_columns)
            self.image_labels.append(label)

        # Event filter for clicks and mouse movement
        self.grid_widget.installEventFilter(self)
        self.grid_widget.setMouseTracking(True)
        for label in self.image_labels:
            label.setMouseTracking(True)

        # Update to start playing any visible animated images
        self.update_visible_movies()

    # -----------------------------------------------------------------------
    # Lazy-loading for WebP
    # -----------------------------------------------------------------------
    def update_visible_movies(self):
        """
        Called on scroll/resize. Start WebP animations that are visible, stop if out of view.
        """
        if not self.image_labels:
            return

        viewport = self.scroll_area.viewport()
        visible_rect = viewport.rect()

        # We'll iterate over a copy of image_labels in case we remove from it
        for label in list(self.image_labels):
            # If label is already removed or invalid, skip
            if not label:
                continue

            # Check if label is valid (not deleted)
            try:
                label_pos = label.mapTo(viewport, QPoint(0, 0))
            except RuntimeError:
                # Label is deleted
                if label in self.image_labels:
                    self.image_labels.remove(label)
                continue

            label_rect = QRect(label_pos, label.size())

            if visible_rect.intersects(label_rect):
                self.ensure_webp_movie_started(label)
            else:
                self.stop_webp_movie(label)

    def ensure_webp_movie_started(self, label):
        """
        If label is for an animated image and we haven't started a QMovie yet, do so.
        Create temp file and QMovie only when needed.
        """
        path = label.objectName()
        if path not in self.webp_movies:
            return  # not animated
        temp_path = self.animated_temp_map.get(path)
        if temp_path is None or not os.path.exists(temp_path):
            # Create temp file for this image
            base = os.path.basename(path)
            temp_dir = getattr(self, 'temp_dir', tempfile.gettempdir())
            temp_path = os.path.join(temp_dir, base)
            try:
                shutil.copy2(path, temp_path)
            except Exception as e:
                print(f"[ERROR] Could not create temp file for {path}: {e}")
                return
            self.animated_temp_map[path] = temp_path
        # Now temp_path exists
        if self.webp_movies[path] is None:
            movie = QMovie(temp_path)
            if not movie.isValid():
                return
            # Jump to frame 0 to measure original dimension
            movie.jumpToFrame(0)
            first_frame = movie.currentImage()
            if not first_frame.isNull():
                orig_w = first_frame.width()
                orig_h = first_frame.height()
                if orig_w and orig_h:
                    ratio = min(self.image_width / orig_w, self.image_height / orig_h)
                    scaled_w = int(orig_w * ratio)
                    scaled_h = int(orig_h * ratio)
                    movie.setScaledSize(QSize(scaled_w, scaled_h))
            movie.setProperty("loopCount", 0)
            self.webp_movies[path] = movie
            label.setMovie(movie)
            movie.start()
        else:
            # If movie exists but is not playing, start it
            movie = self.webp_movies[path]
            if label.movie() != movie:
                label.setMovie(movie)
            if movie.state() != QMovie.Running:
                movie.start()

    def stop_webp_movie(self, label):
        """
        Stop the movie if it's playing and detach from label.
        Also delete the temp file if present.
        """
        path = label.objectName()
        if path in self.webp_movies:
            movie = self.webp_movies[path]
            if movie:
                movie.stop()
                label.setMovie(None)
                movie.deleteLater()
                self.webp_movies[path] = None
            # Remove temp file if exists
            temp_path = self.animated_temp_map.get(path)
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            self.animated_temp_map[path] = None

    # -----------------------------------------------------------------------
    # Event filter for left/right click
    # -----------------------------------------------------------------------
    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseButtonPress:
            if event.button() in (Qt.LeftButton, Qt.RightButton):
                pos = event.pos()
                widget = source.childAt(pos)
                if isinstance(widget, QLabel):
                    image_path = widget.objectName()
                    if event.button() == Qt.LeftButton:
                        self.move_image_to_subfolder(image_path, '01')
                    elif event.button() == Qt.RightButton:
                        self.move_image_to_subfolder(image_path, '02')
                    return True
        elif event.type() == QEvent.MouseMove:
            # Mouse move: update filename label
            pos = event.pos()
            widget = source.childAt(pos)
            if isinstance(widget, QLabel):
                image_path = widget.objectName()
                filename = os.path.basename(image_path)
                self.filename_hover_label.setText(filename)
            else:
                self.filename_hover_label.setText("")
        elif event.type() == QEvent.Leave:
            # Mouse left the grid area
            self.filename_hover_label.setText("")
        return super().eventFilter(source, event)

    def move_image_to_subfolder(self, image_path, subfolder):
        """
        Unload QMovie and delete temp file before moving to avoid file-in-use errors.
        Also remove the label from self.image_labels so we don't reference a deleted label.
        """
        # 1) Stop/unload if it's animated
        if image_path in self.webp_movies:
            movie = self.webp_movies[image_path]
            if movie:
                movie.stop()
            # Detach from label
            label = self.find_label_by_path(image_path)
            if label and label.movie() == movie:
                label.setMovie(None)
            if movie:
                movie.deleteLater()
            self.webp_movies[image_path] = None
        # Remove temp file if exists
        temp_path = self.animated_temp_map.get(image_path)
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        if image_path in self.animated_temp_map:
            del self.animated_temp_map[image_path]

        # Force Qt to release file handles
        QApplication.processEvents()

        # 2) Move (rename) the file
        subfolder_path = os.path.join(os.path.dirname(image_path), subfolder)
        os.makedirs(subfolder_path, exist_ok=True)
        image_name = os.path.basename(image_path)
        new_path = os.path.join(subfolder_path, image_name)

        try:
            os.rename(image_path, new_path)
            self.images.remove(image_path)

            # 3) Remove the label from the grid layout **and** from self.image_labels
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                if widget and widget.objectName() == image_path:
                    if widget in self.image_labels:
                        self.image_labels.remove(widget)
                    widget.deleteLater()
                    break

            # Update the ITEM button color
            self.update_item_button_color(self.current_item)


        except OSError as e:
            print(f"Error moving file: {e}")

    def find_label_by_path(self, image_path):
        for lbl in self.image_labels:
            if lbl.objectName() == image_path:
                return lbl
        return None

    # -----------------------------------------------------------------------
    # ITEM button color updates, etc.
    # -----------------------------------------------------------------------
    def update_item_button_color(self, item_name):
        button = self.item_buttons_dict.get(item_name)
        if button:
            category_path = os.path.join(self.project_folder, self.current_category)
            if self.middle_folder:
                item_path = os.path.join(category_path, self.middle_folder, item_name)
            else:
                item_path = os.path.join(category_path, item_name)

            if self.use_gen_folder_checkbox.isChecked():
                image_folder_path = os.path.join(item_path, 'gen')
            else:
                image_folder_path = item_path

            if os.path.exists(image_folder_path):
                valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
                num_images = len([
                    f for f in os.listdir(image_folder_path)
                    if os.path.isfile(os.path.join(image_folder_path, f))
                    and f.lower().endswith(valid_exts)
                ])
            else:
                num_images = 0

            self.item_image_counts[item_name] = num_images
            font_size_item = int(self.default_font_size * self.get_multiplier(self.item_multiplier_line_edit))
            self.set_item_button_style(button, num_images, font_size_item)

    def set_item_button_style(self, button, num_images, font_size):
        if num_images == 0:
            color = '#404040'  # dark grey instead of red
        elif num_images == 1:
            color = '#4287f5'  # blue for exactly 1 image
        elif num_images <= 5:
            color = 'orange'
        else:
            color = 'green'
        button.setStyleSheet(f"""
            QPushButton {{
                font-size: {font_size}px;
                color: {color};
                padding: 2px 10px;
                text-align: left;
                border: none;
                background-color: transparent;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
        """)

    # -----------------------------------------------------------------------
    # Sizing
    # -----------------------------------------------------------------------
    def adjust_sizes(self):
        category_multiplier = self.get_multiplier(self.category_multiplier_line_edit)
        item_multiplier = self.get_multiplier(self.item_multiplier_line_edit)
        image_multiplier = self.get_multiplier(self.image_multiplier_line_edit)

        font_size_category = int(self.default_font_size * category_multiplier)
        font_size_item = int(self.default_font_size * item_multiplier)

        self.image_width = int(200 * image_multiplier)
        self.image_height = int(200 * image_multiplier)

        # CATEGORY buttons
        max_category_width = 0
        for i in range(self.category_layout.count() - 1):
            widget = self.category_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                widget.setStyleSheet(f"font-size: {font_size_category}px;")
                font = widget.font()
                fm = QFontMetrics(font)
                text_width = fm.horizontalAdvance(widget.text())
                max_category_width = max(max_category_width, text_width)

        # ITEM buttons
        max_item_width = 0
        for item_name, button in self.item_buttons_dict.items():
            num_images = self.item_image_counts.get(item_name, 0)
            self.set_item_button_style(button, num_images, font_size_item)
            font = button.font()
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(button.text())
            max_item_width = max(max_item_width, text_width)

        # Set widths for panels
        padding = 40
        self.category_scroll_area.setFixedWidth(max_category_width + padding)
        self.item_scroll_area.setFixedWidth(max_item_width + padding)

        # If images are loaded, re-display them (thumbnails)
        if self.images:
            self.display_images_async()

    def get_multiplier(self, line_edit):
        try:
            return float(line_edit.text())
        except ValueError:
            return 1.0

    def resizeEvent(self, event):
        self.adjust_sizes()
        super().resizeEvent(event)
        self.update_visible_movies()  # re-check which WebPs are in view

    def save_current_settings(self):
        project_name = self.project_name_input.text().strip()
        if not project_name:
            status_label = QLabel("Please enter a project name")
            status_label.setStyleSheet("color: red;")
            self.main_layout.addWidget(status_label)
            QTimer.singleShot(3000, status_label.deleteLater)
            return

        settings = {
            'project_folder': self.project_folder,
            'middle_folder': self.middle_folder,
            'image_width': self.image_width,
            'image_height': self.image_height,
            'category_multiplier': self.category_multiplier_line_edit.text(),
            'item_multiplier': self.item_multiplier_line_edit.text(),
            'image_multiplier': self.image_multiplier_line_edit.text(),
            'use_gen_folder': self.use_gen_folder_checkbox.isChecked()
        }

        try:
            # Load existing settings
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}

            # Update with new settings
            all_settings[project_name] = settings

            # Save back to file
            with open(self.settings_file, 'w') as f:
                json.dump(all_settings, f, indent=4)

            # Refresh project buttons
            self.load_project_buttons()

            # Show success message
            status_label = QLabel(f"Settings saved as '{project_name}'")
            status_label.setStyleSheet("color: green;")
            self.main_layout.addWidget(status_label)
            QTimer.singleShot(3000, status_label.deleteLater)

        except Exception as e:
            status_label = QLabel(f"Error saving settings: {str(e)}")
            status_label.setStyleSheet("color: red;")
            self.main_layout.addWidget(status_label)
            QTimer.singleShot(3000, status_label.deleteLater)

    def load_project_buttons(self):
        # Clear existing buttons
        for i in reversed(range(self.projects_layout.count())):
            widget = self.projects_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add label
        label = QLabel("Saved Projects:")
        label.setStyleSheet("color: #808080;")
        self.projects_layout.addWidget(label)

        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    all_settings = json.load(f)
                
                for project_name in all_settings:
                    btn = QPushButton(project_name)
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #2a2a2a;
                            border: none;
                            padding: 2px 10px;
                            color: #c0c0c0;
                        }
                        QPushButton:hover {
                            background-color: #404040;
                        }
                    """)
                    btn.clicked.connect(lambda checked, name=project_name: self.load_project_settings(name))
                    self.projects_layout.addWidget(btn)
        except Exception as e:
            print(f"Error loading project buttons: {e}")

    def load_project_settings(self, project_name):
        try:
            with open(self.settings_file, 'r') as f:
                all_settings = json.load(f)
            
            if project_name in all_settings:
                settings = all_settings[project_name]
                
                # Apply settings
                self.project_folder = settings['project_folder']
                self.middle_folder = settings['middle_folder']
                self.image_width = settings['image_width']
                self.image_height = settings['image_height']
                
                # Update UI elements
                self.project_line_edit.setText(self.project_folder)
                self.middle_folder_line_edit.setText(self.middle_folder)
                self.category_multiplier_line_edit.setText(settings['category_multiplier'])
                self.item_multiplier_line_edit.setText(settings['item_multiplier'])
                self.image_multiplier_line_edit.setText(settings['image_multiplier'])
                self.use_gen_folder_checkbox.setChecked(settings['use_gen_folder'])
                self.project_name_input.setText(project_name)
                self.current_project_name = project_name
                
                # Reload UI
                self.load_categories()
                
                # Show success message
                status_label = QLabel(f"Loaded settings from '{project_name}'")
                status_label.setStyleSheet("color: green;")
                self.main_layout.addWidget(status_label)
                QTimer.singleShot(3000, status_label.deleteLater)

        except Exception as e:
            status_label = QLabel(f"Error loading settings: {str(e)}")
            status_label.setStyleSheet("color: red;")
            self.main_layout.addWidget(status_label)
            QTimer.singleShot(3000, status_label.deleteLater)

# ===========================================================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    app.exec_()
