#// IMAGE REVIEW AND RANK 
#// browse a folder of images with left right , move images into ranked folders using 1,2,3 , T for tiling view
#//===========================================================================================
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFileDialog, QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt5.QtGui import QPixmap, QKeyEvent ,QPainter
from PyQt5.QtCore import Qt
import qdarkstyle

# //=========================================================================================================
class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.tiling_mode = False

    def init_ui(self):
        self.setWindowTitle("Image Review and Rank --- LEFT RIGHT --- RANK 1 2 3 --- T = TILED MODE")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: black;")
        self.central_widget = QLabel(self)
        self.setCentralWidget(self.central_widget)
        self.image_index = 0
        self.folder_path = ''
        self.images = []
        # TILED TEXTURE MODE
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.image_label = QLabel(self)
        self.tiled_label = QLabel(self)
        self.layout.addWidget(self.image_label)
        self.layout.addWidget(self.tiled_label)
        self.tiled_label.hide()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in [Qt.Key_Right, Qt.Key_Left, Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_T] and self.images:
            self.handle_key_event(event.key())

    def handle_key_event(self, key):
        if key == Qt.Key_Right:
            self.cycle_image(1)
        elif key == Qt.Key_Left:
            self.cycle_image(-1)
        elif key == Qt.Key_T:
            self.toggle_tiling_mode()
        elif key == Qt.Key_1:
            self.move_image_to_subfolder(str(1))
        elif key == Qt.Key_2:
            self.move_image_to_subfolder(str(2))
        elif key == Qt.Key_3:
            self.move_image_to_subfolder(str(3))

    def cycle_image(self, direction):
        self.image_index = (self.image_index + direction) % len(self.images)
        self.show_image()

    def move_image_to_subfolder(self, subfolder):
        subfolder_path = os.path.join(self.folder_path, '0' + subfolder)
        os.makedirs(subfolder_path, exist_ok=True)
        image_path = os.path.join(self.folder_path, self.images[self.image_index])
        new_path = os.path.join(subfolder_path, self.images[self.image_index])
        try:
            os.rename(image_path, new_path)
            self.images.pop(self.image_index)
            if self.image_index >= len(self.images):
                self.image_index = 0
            self.show_image()
        except OSError as e:
            print(f"Error moving file: {e}")

    def load_images(self, folder_path):
        self.folder_path = folder_path
        self.images = [file for file in os.listdir(folder_path) if file.lower().endswith(('.jpg', '.jpeg', '.png'))]
        self.image_index = 0
        self.show_image()

    def show_image(self):
        if self.images:
            image_path = os.path.join(self.folder_path, self.images[self.image_index])
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                if self.tiling_mode:
                    self.update_tiled_view()
                    pixmap_rescaled = pixmap.scaledToHeight(1024)  # or any other suitable size
                    self.image_label.setPixmap(pixmap_rescaled)
                    self.image_label.setAlignment(Qt.AlignCenter)
                else:
                    pixmap_rescaled = pixmap.scaledToHeight(1024)  # or any other suitable size
                    self.image_label.setPixmap(pixmap_rescaled)
                    self.image_label.setAlignment(Qt.AlignCenter)
            else:
                print(f"Image not found: {image_path}")
        else:
            print("No images to display.")

    #//==================================================== TILED TEXTURE MODE
    def toggle_tiling_mode(self):
        self.tiling_mode = not self.tiling_mode
        if self.tiling_mode:
            self.tiled_label.show()
            self.update_tiled_view()
        else:
            self.tiled_label.hide()
        self.show_image()

    def update_tiled_view(self):
        if not self.images:
            return

        image_path = os.path.join(self.folder_path, self.images[self.image_index])
        pixmap = QPixmap(image_path)
        tile_size = pixmap.size() / 3

        tiled_pixmap = QPixmap(tile_size.width() * 3, tile_size.height() * 3)
        painter = QPainter(tiled_pixmap)
        for row in range(3):
            for col in range(3):
                painter.drawPixmap(col * tile_size.width(), row * tile_size.height(), tile_size.width(), tile_size.height(), pixmap)
        painter.end()

        self.tiled_label.setPixmap(tiled_pixmap)

#//===================================================================
if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    folder_path = QFileDialog.getExistingDirectory(window, "Select Directory")
    if folder_path:
        window.load_images(folder_path)
    app.exec_()
