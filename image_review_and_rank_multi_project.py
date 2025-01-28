# IMAGE REVIEW AND RANK
# Browse folders of images, move images into ranked folders with mouse clicks
# ===========================================================================================
import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout,
                             QWidget, QGridLayout, QScrollArea, QMessageBox, QPushButton, QHBoxLayout,
                             QLineEdit, QFileDialog, QCheckBox, QScrollBar)
from PyQt5.QtGui import QPixmap, QMouseEvent, QFontMetrics, QImage, QMovie, QColor
from PyQt5.QtCore import (Qt, QThreadPool, QRunnable, pyqtSignal, QObject,
                          QSize, QEvent, QRect, QPoint)
import qdarkstyle

# ===========================================================================================
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class ImageLoader(QRunnable):
    """
    Modified ImageLoader to distinguish between normal images vs. animated WebP.
    If the file is .webp, skip creating a QImage thumbnail here to preserve frames.
    Instead, pass a flag indicating it's WebP for lazy creation of QMovie in the GUI.
    """
    def __init__(self, image_paths, image_width, image_height):
        super().__init__()
        self.image_paths = image_paths
        self.image_width = image_width
        self.image_height = image_height
        self.signals = WorkerSignals()

    def run(self):
        images = []
        for path in self.image_paths:
            ext = os.path.splitext(path)[1].lower()
            if ext == '.webp':
                # We'll handle QMovie creation later, for lazy loading.
                images.append((path, None, True))  # (path, thumbnail, is_webp)
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

        # Top panel for PROJECT folder selection
        self.top_widget = QWidget()
        self.top_layout = QHBoxLayout(self.top_widget)
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
            QMessageBox.warning(self, "Warning", "The specified PROJECT folder does not exist.")

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
            QMessageBox.warning(self, "Warning", f"Item folder not found in {item_parent_path}")
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
                QMessageBox.warning(self, "Warning", f"'gen' folder not found in {item_path}")
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

        # Start asynchronous load
        worker = ImageLoader(self.images, self.image_width, self.image_height)
        worker.signals.result.connect(self.on_images_loaded)
        self.threadpool.start(worker)

    def on_images_loaded(self, images):
        """
        images: list of (image_path, thumbnail, is_webp)
        """
        num_columns = max(1, self.scroll_area.width() // (self.image_width + 20))

        for i, (image_path, thumbnail, is_webp) in enumerate(images):
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setObjectName(image_path)

            if is_webp:
                # We'll lazy-load the QMovie upon visibility
                self.webp_movies[image_path] = None
                # Placeholder gray
                placeholder = QImage(self.image_width, self.image_height, QImage.Format_ARGB32)
                placeholder.fill(QColor("darkGray"))
                label.setPixmap(QPixmap.fromImage(placeholder))
            else:
                # Static image
                pixmap = QPixmap.fromImage(thumbnail)
                label.setPixmap(pixmap)
                self.image_cache[image_path] = pixmap

            self.grid_layout.addWidget(label, i // num_columns, i % num_columns)
            self.image_labels.append(label)

        # Event filter for clicks
        self.grid_widget.installEventFilter(self)

        # Update to start playing any visible WebPs
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
        If label is for a WebP and we haven't started a QMovie yet, do so.
        Keep aspect ratio to fit self.image_width/height.
        """
        path = label.objectName()
        if path not in self.webp_movies:
            return  # not a WebP

        if self.webp_movies[path] is None:
            movie = QMovie(path)
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
        Stop the movie if it's playing and detach from label
        to free resources (and unlock the file).
        """
        path = label.objectName()
        if path in self.webp_movies:
            movie = self.webp_movies[path]
            if movie:
                movie.stop()
                label.setMovie(None)

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
        return super().eventFilter(source, event)

    def move_image_to_subfolder(self, image_path, subfolder):
        """
        Strategy A: Unload QMovie before moving to avoid file-in-use errors on Windows.
        Also remove the label from self.image_labels so we don't reference a deleted label.
        """
        # 1) Stop/unload if it's a WebP
        if image_path in self.webp_movies:
            movie = self.webp_movies[image_path]
            if movie:
                movie.stop()
            # Detach from label
            label = self.find_label_by_path(image_path)
            if label and label.movie() == movie:
                label.setMovie(None)
            # Request Qt to delete it
            if movie:
                movie.deleteLater()
            self.webp_movies[image_path] = None

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
            color = 'red'
        elif num_images <= 5:
            color = 'orange'
        else:
            color = 'green'
        button.setStyleSheet(f"font-size: {font_size}px; color: {color};")

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

# ===========================================================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    app.exec_()
