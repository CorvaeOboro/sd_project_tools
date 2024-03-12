#// IMAGE REVIEW AND RANK 
#// browse a folder of images with left right , move images into ranked folders using 1,2,3 , T for tiling view
#//===========================================================================================

IMAGE_SIZE = 500
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout,
                             QWidget, QGridLayout, QScrollArea, QMessageBox)
from PyQt5.QtGui import QPixmap, QMouseEvent
from PyQt5.QtCore import Qt
import qdarkstyle


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.folder_path = ''
        self.images = []
        self.image_labels = []
        self.image_width = IMAGE_SIZE
        self.image_height = IMAGE_SIZE
        self.num_rows = 2

    def init_ui(self):
        self.setWindowTitle("Image Review and Rank --- LEFT RIGHT --- RANK 1 2 3 --- T = TILED MODE")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: black;")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.scroll_area.setWidget(self.grid_widget)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            for i, label in enumerate(self.image_labels):
                if label.underMouse():
                    self.move_image_to_subfolder(i, str(1))
                    break
        elif event.button() == Qt.RightButton:
            for i, label in enumerate(self.image_labels):
                if label.underMouse():
                    self.move_image_to_subfolder(i, str(2))
                    break

    def move_image_to_subfolder(self, image_index, subfolder):
        subfolder_path = os.path.join(self.folder_path, '0' + subfolder)
        os.makedirs(subfolder_path, exist_ok=True)
        image_path = os.path.join(self.folder_path, self.images[image_index])
        new_path = os.path.join(subfolder_path, self.images[image_index])
        try:
            os.rename(image_path, new_path)
            self.images.pop(image_index)
            self.display_images()
        except OSError as e:
            print(f"Error moving file: {e}")

    def load_images(self, folder_path):
        self.folder_path = folder_path
        self.images = [file for file in os.listdir(folder_path) if file.lower().endswith(('.jpg', '.jpeg', '.png'))]
        self.display_images()

    def display_images(self):
        for i in range(len(self.image_labels)):
            self.grid_layout.itemAt(i).widget().deleteLater()

        self.image_labels = []
        scroll_area_width = self.scroll_area.width()
        num_columns = max(1, scroll_area_width // self.image_width)

        for i, image_file in enumerate(self.images):
            image_path = os.path.join(self.folder_path, image_file)
            pixmap = QPixmap(image_path).scaled(self.image_width, self.image_height, Qt.KeepAspectRatio)
            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignLeft)
            self.grid_layout.addWidget(label, i // 4, i % 4)
            self.image_labels.append(label)


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    folder_path = QFileDialog.getExistingDirectory(window, "Select Directory")
    if folder_path:
        window.load_images(folder_path)
    app.exec_()
