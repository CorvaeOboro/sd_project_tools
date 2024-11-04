# IMAGE REVIEW AND RANK
# Browse folders of images, move images into ranked folders with mouse clicks
# ===========================================================================================
import os
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout,
                             QWidget, QGridLayout, QScrollArea, QMessageBox, QPushButton, QHBoxLayout,
                             QLineEdit, QFileDialog, QCheckBox)
from PyQt5.QtGui import QPixmap, QMouseEvent, QFontMetrics, QImage
from PyQt5.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject, QSize, QEvent
import qdarkstyle

# ===========================================================================================
class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class ImageLoader(QRunnable):
    def __init__(self, image_paths, image_width, image_height):
        super().__init__()
        self.image_paths = image_paths
        self.image_width = image_width
        self.image_height = image_height
        self.signals = WorkerSignals()

    def run(self):
        images = []
        for path in self.image_paths:
            try:
                image = QImage(path)
                if image.isNull():
                    continue
                thumbnail = image.scaled(self.image_width, self.image_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                images.append((path, thumbnail))
            except Exception as e:
                self.signals.error.emit((e, path))
        self.signals.result.emit(images)
        self.signals.finished.emit()

# ===========================================================================================
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_folder = os.getcwd()
        self.middle_folder = ''  # Initialize middle folder as empty
        self.category_exclusion_list = []  # Add any categories to exclude
        self.item_exclusion_prefix = '00_'
        self.default_font_size = 12  # Default font size
        self.image_width = 200  # Default values
        self.image_height = 200
        self.current_category = None
        self.current_item = None
        self.folder_path = ''
        self.images = []
        self.image_labels = []
        self.image_cache = {}  # Cache for loaded images
        self.item_buttons_dict = {}    # Store ITEM buttons with item names as keys
        self.item_image_counts = {}    # Store image counts for each ITEM
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

        # Add the checkbox
        self.use_gen_folder_checkbox = QCheckBox("Use 'gen' folder")
        self.use_gen_folder_checkbox.setChecked(True)
        self.use_gen_folder_checkbox.toggled.connect(self.use_gen_folder_toggled)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_project_folder)

        # Add widgets to the layout
        self.top_layout.addWidget(self.project_line_edit)
        self.top_layout.addWidget(self.middle_folder_line_edit)
        self.top_layout.addWidget(self.use_gen_folder_checkbox)
        self.top_layout.addWidget(self.browse_button)
        self.main_layout.addWidget(self.top_widget)

        # Main horizontal layout for CATEGORY, ITEM, and Images
        self.horizontal_layout = QHBoxLayout()
        self.main_layout.addLayout(self.horizontal_layout)

        # Left panel for CATEGORY buttons
        self.category_widget = QWidget()
        self.category_layout = QVBoxLayout()
        self.category_widget.setLayout(self.category_layout)
        self.category_scroll_area = QScrollArea()
        self.category_scroll_area.setWidgetResizable(True)
        self.category_scroll_area.setWidget(self.category_widget)
        self.horizontal_layout.addWidget(self.category_scroll_area)

        # Multiplier input for CATEGORY font size
        self.category_multiplier_line_edit = QLineEdit()
        self.category_multiplier_line_edit.setPlaceholderText("Multiplier (default 1.0)")
        self.category_multiplier_line_edit.setText("1.0")
        self.category_multiplier_line_edit.returnPressed.connect(self.adjust_sizes)
        self.category_layout.addWidget(self.category_multiplier_line_edit)

        # Middle panel for ITEM buttons
        self.item_widget = QWidget()
        self.item_layout = QVBoxLayout()
        self.item_widget.setLayout(self.item_layout)
        self.item_scroll_area = QScrollArea()
        self.item_scroll_area.setWidgetResizable(True)
        self.item_scroll_area.setWidget(self.item_widget)
        self.horizontal_layout.addWidget(self.item_scroll_area)

        # Multiplier input for ITEM font size
        self.item_multiplier_line_edit = QLineEdit()
        self.item_multiplier_line_edit.setPlaceholderText("Multiplier (default 1.0)")
        self.item_multiplier_line_edit.setText("1.0")
        self.item_multiplier_line_edit.returnPressed.connect(self.adjust_sizes)
        self.item_layout.addWidget(self.item_multiplier_line_edit)

        # Right panel for images
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

        # Multiplier input for image size
        self.image_multiplier_line_edit = QLineEdit()
        self.image_multiplier_line_edit.setPlaceholderText("Multiplier (default 1.0)")
        self.image_multiplier_line_edit.setText("1.0")
        self.image_multiplier_line_edit.returnPressed.connect(self.adjust_sizes)
        self.image_layout.addWidget(self.image_multiplier_line_edit)

        # Load CATEGORY buttons
        self.load_categories()

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

    def load_categories(self):
        # Clear existing CATEGORY buttons
        for i in reversed(range(self.category_layout.count() - 1)):  # Exclude the multiplier input
            widget = self.category_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # List CATEGORY folders in project folder
        categories = [name for name in os.listdir(self.project_folder)
                      if os.path.isdir(os.path.join(self.project_folder, name))
                      and name not in self.category_exclusion_list]

        categories.sort()

        # Create buttons for each CATEGORY
        self.category_buttons = []  # Store buttons to calculate max width later
        for category in categories:
            button = QPushButton(category)
            button.clicked.connect(self.category_button_clicked)
            self.category_layout.insertWidget(self.category_layout.count() - 1, button)  # Insert before multiplier
            self.category_buttons.append(button)

        self.adjust_sizes()

    def category_button_clicked(self):
        button = self.sender()
        category_name = button.text()
        self.current_category = category_name
        category_path = os.path.join(self.project_folder, category_name)
        self.load_items(category_path)

    def load_items(self, category_path):
        # Clear existing ITEM buttons
        for i in reversed(range(self.item_layout.count() - 1)):  # Exclude the multiplier input
            widget = self.item_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        # Clear previous ITEM buttons and counts
        self.item_buttons_dict.clear()
        self.item_image_counts.clear()
        self.item_buttons = []

        # Adjust category_path to include middle folder if specified
        if self.middle_folder:
            item_parent_path = os.path.join(category_path, self.middle_folder)
        else:
            item_parent_path = category_path

        if not os.path.exists(item_parent_path):
            QMessageBox.warning(self, "Warning", f"Item folder not found in {item_parent_path}")
            return

        # List ITEM folders in item_parent_path
        items = [name for name in os.listdir(item_parent_path)
                 if os.path.isdir(os.path.join(item_parent_path, name))
                 and not name.startswith(self.item_exclusion_prefix)]

        items.sort()

        # Get current font size for ITEM buttons
        font_size_item = int(self.default_font_size * self.get_multiplier(self.item_multiplier_line_edit))

        # Create buttons for each ITEM and count images
        for item in items:
            button = QPushButton(item)
            button.clicked.connect(self.item_button_clicked)
            self.item_layout.insertWidget(self.item_layout.count() - 1, button)  # Insert before multiplier
            self.item_buttons.append(button)
            self.item_buttons_dict[item] = button  # Store in dict for easy access

            # Get path to ITEM
            if self.middle_folder:
                item_path = os.path.join(category_path, self.middle_folder, item)
            else:
                item_path = os.path.join(category_path, item)

            # Determine image folder path
            if self.use_gen_folder_checkbox.isChecked():
                image_folder_path = os.path.join(item_path, 'gen')
            else:
                image_folder_path = item_path

            # Count images in image folder (excluding subfolders)
            if os.path.exists(image_folder_path):
                num_images = len([f for f in os.listdir(image_folder_path)
                                  if os.path.isfile(os.path.join(image_folder_path, f)) and f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            else:
                num_images = 0

            # Store image count
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

    def load_images(self, item_path):
        # Determine the folder to load images from
        if self.use_gen_folder_checkbox.isChecked():
            # Use 'gen' folder within ITEM
            image_folder_path = os.path.join(item_path, 'gen')
            if not os.path.exists(image_folder_path):
                QMessageBox.warning(self, "Warning", f"'gen' folder not found in {item_path}")
                return
        else:
            # Use base ITEM folder
            image_folder_path = item_path

        self.folder_path = image_folder_path
        self.images = [os.path.join(self.folder_path, file) for file in os.listdir(image_folder_path)
                       if file.lower().endswith(('.jpg', '.jpeg', '.png')) and os.path.isfile(os.path.join(image_folder_path, file))]
        self.display_images_async()

    def display_images_async(self):
        # Clear existing images
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        self.image_labels = []
        self.image_cache.clear()

        # Start asynchronous image loading
        worker = ImageLoader(self.images, self.image_width, self.image_height)
        worker.signals.result.connect(self.on_images_loaded)
        self.threadpool.start(worker)

    def on_images_loaded(self, images):
        num_columns = max(1, self.scroll_area.width() // (self.image_width + 20))  # Adjust as needed

        for i, (image_path, thumbnail) in enumerate(images):
            pixmap = QPixmap.fromImage(thumbnail)
            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignCenter)
            label.setObjectName(image_path)
            self.grid_layout.addWidget(label, i // num_columns, i % num_columns)
            self.image_labels.append(label)
            self.image_cache[image_path] = pixmap

        # Install event filter to detect clicks on images
        self.grid_widget.installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
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
        subfolder_path = os.path.join(os.path.dirname(image_path), subfolder)
        os.makedirs(subfolder_path, exist_ok=True)
        image_name = os.path.basename(image_path)
        new_path = os.path.join(subfolder_path, image_name)
        try:
            os.rename(image_path, new_path)
            self.images.remove(image_path)
            # Remove the label from the grid layout
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                if widget and widget.objectName() == image_path:
                    widget.deleteLater()
                    break
            # Update the ITEM button color
            self.update_item_button_color(self.current_item)
        except OSError as e:
            print(f"Error moving file: {e}")

    def update_item_button_color(self, item_name):
        button = self.item_buttons_dict.get(item_name)
        if button:
            # Get the path to the ITEM's image folder (either 'gen' or base folder)
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
                num_images = len([f for f in os.listdir(image_folder_path)
                                  if os.path.isfile(os.path.join(image_folder_path, f)) and f.lower().endswith(('.jpg', '.jpeg', '.png'))])
            else:
                num_images = 0
            self.item_image_counts[item_name] = num_images
            font_size_item = int(self.default_font_size * self.get_multiplier(self.item_multiplier_line_edit))
            self.set_item_button_style(button, num_images, font_size_item)

    def set_item_button_style(self, button, num_images, font_size):
        # Set the button's text color based on num_images
        if num_images == 0:
            color = 'red'
        elif num_images <= 5:
            color = 'orange'
        else:
            color = 'green'
        button.setStyleSheet(f"font-size: {font_size}px; color: {color};")

    def adjust_sizes(self):
        # Calculate multipliers from input fields
        category_multiplier = self.get_multiplier(self.category_multiplier_line_edit)
        item_multiplier = self.get_multiplier(self.item_multiplier_line_edit)
        image_multiplier = self.get_multiplier(self.image_multiplier_line_edit)

        # Adjust font sizes for CATEGORY and ITEM buttons
        font_size_category = int(self.default_font_size * category_multiplier)
        font_size_item = int(self.default_font_size * item_multiplier)

        # Adjust image sizes
        self.image_width = int(200 * image_multiplier)
        self.image_height = int(200 * image_multiplier)

        # Update CATEGORY buttons
        max_category_width = 0
        for i in range(self.category_layout.count() - 1):  # Exclude multiplier input
            widget = self.category_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                widget.setStyleSheet(f"font-size: {font_size_category}px;")
                # Calculate the width of the button text
                font = widget.font()
                fm = QFontMetrics(font)
                text_width = fm.horizontalAdvance(widget.text())
                max_category_width = max(max_category_width, text_width)

        # Update ITEM buttons
        max_item_width = 0
        for item_name, button in self.item_buttons_dict.items():
            num_images = self.item_image_counts.get(item_name, 0)
            self.set_item_button_style(button, num_images, font_size_item)
            # Calculate the width of the button text
            font = button.font()
            fm = QFontMetrics(font)
            text_width = fm.horizontalAdvance(button.text())
            max_item_width = max(max_item_width, text_width)

        # Set widths for CATEGORY and ITEM panels
        padding = 40  # Extra space for padding and scrollbar
        self.category_scroll_area.setFixedWidth(max_category_width + padding)
        self.item_scroll_area.setFixedWidth(max_item_width + padding)

        # Redisplay images with new sizes if images are loaded
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

# ===========================================================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    app.exec_()
