"""
IMAGE EDITOR LAYERED
a pyQt interface and will be a layered image editor . 
it will show a canvas and a stacked layer order with blendmodes .
each layer has an eye toggle button to toggle it visible or not . 
each layer has a secondary "Mask" layer that can be painted with greyscale to handle how the alpha channel of the layer ends up looking , it is separated so that it is non destructive . 
when an image is dragged onto the UI and no existing working file is loaded then it becomes to base layer and the canvas , if another image is dragged on top it is added as a new layer . 

Smart Alignment Snap =
 a function that will try to algorithmically transform the current layer's size and position ,
  so that it "snaps" to the underlying layer . 
  for example imagine Layer 0 the base layer is three black rectangles on a white background  , 
  in the currently selected Layer 1 is an image of those same rectangles but with different colors inside and it has been scaled , cropped , and offset 
  so that it currently is no longer aligned with the original version . 
  this button will initiate a function to compare the layers using various techniques like
   sobel edge , and high contrast ( mostly isolating pure black lines )
    to find what the best scale and offset the current layer should be in order to have its image line up with the original .  

A PyQt-based layered image editor supporting stacked image layers, blend modes, adjustment layers, non-destructive mask painting, and algorithmic layer alignment. This document provides a high-level overview and breakdown of each core class and their critical functions in the pipeline.

PIPELINE & CLASS BREAKDOWN
==========================

1. Layer (class)
   - Represents a single image layer.
   - Attributes: name, image (QImage), filepath, visibility, blend mode, opacity, mask (QImage), painting state, scale, offset, rotation, is_adjustment.
   - Used for both standard and adjustment layers.

2. AdjustmentLayer (class, subclass of Layer)
   - Represents a non-destructive adjustment layer (e.g., hue shift).
   - Adds attributes for hue targeting and shifting.
   - Critical function: update_adjustment() — applies hue shift to regions within a target hue range.

3. LayeredImageProject (class)
   - Manages the list of layers and project-level operations.
   - Functions: add_layer, delete_layer, reorder_layers, set_layer_property, save/load project (JSON), export flattened image, snap layer to underlying layer (alignment algorithm).
   - Handles all persistent state and serialization.

4. LayerListWidget (class, QListWidget)
   - UI component for displaying and managing the layer stack.
   - Handles selection, drag-and-drop reordering, and visibility toggling.
   - Syncs with LayeredImageProject and notifies the main editor of changes.

5. CanvasView (class, QGraphicsView)
   - Main image display and editing area.
   - Handles painting, mask painting, eyedropper, and compositing all layers.
   - Functions: set_tools_properties_callback, set_show_alpha_mask, set_eyedropper_mode, set_brush_color/radius, mouse event handling, compositing via LayeredImage_composite_layers.
   - Implements blending, mask painting, and drag-and-drop image import.

6. LayeredImageEditor (class, QMainWindow)
   - Main application window and controller.
   - Initializes UI, manages toolbars, property panels, and integrates all subsystems.
   - Handles all user actions: adding/removing layers, mask painting, property editing, adjustment layers, project save/load/export, and layer alignment.
   - All methods use verbose, class-prefixed naming for clarity and maintainability.

7. Utility Functions:
   - LayeredImage_composite_layers: Composites a list of Layer objects into a single QImage, handling blend modes, masks, and adjustment layers.
   - LayeredImage_blend_adjustment_layer: Applies adjustment layer effects to the composited image below.
   - Blending and conversion helpers (static methods in CanvasView).

PIPELINE FLOW
======================
- User loads or drags images → Layer objects are created and managed by LayeredImageProject.
- LayerListWidget displays and lets user reorder/select/toggle layers.
- CanvasView composites all visible layers (LayeredImage_composite_layers), displays result, and supports painting/mask editing.
- LayeredImageEditor orchestrates all UI, connects signals, and manages project state.
- AdjustmentLayer(s) can be inserted for non-destructive edits (e.g., hue shift), composited in the pipeline.
- Project can be saved/loaded (JSON), and final result exported as a flattened image.
- Alignment snap uses edge detection and template matching to auto-align layers.

"""

import sys
import os
import json
import base64
from datetime import datetime
import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QGraphicsView, QGraphicsScene, QComboBox, QAbstractItemView, QSplitter, QColorDialog, QSizePolicy, QGridLayout, QSpacerItem, QSpinBox, QDoubleSpinBox, QFormLayout, QDialog, QSlider, QGroupBox
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor, QDragEnterEvent, QDropEvent, QMouseEvent, QIcon, QTransform
from PyQt5.QtCore import Qt, QSize, QByteArray, QMimeData, QRectF

#//==================================================================

class Layer:
    def __init__(self, Layer_name, Layer_image=None, Layer_filepath=None):
        self.Layer_name = Layer_name
        self.Layer_image = Layer_image  # QImage
        self.Layer_filepath = Layer_filepath  # Full path to image file
        self.Layer_visible = True
        self.Layer_blend_mode = 'Normal'
        self.Layer_opacity = 1.0  # Opacity multiplier, 0.0-1.0
        self.Layer_mask = None  # QImage, greyscale alpha mask
        self.Layer_mask_painting = False
        self.Layer_scale = 1.0
        self.Layer_offset = (0, 0)
        self.Layer_rotation = 0.0
        self.Layer_is_adjustment = False  # For distinguishing adjustment layers

class AdjustmentLayer(Layer):
    def __init__(self, AdjustmentLayer_name, AdjustmentLayer_base_image, AdjustmentLayer_target_hue=0, AdjustmentLayer_hue_range=30, AdjustmentLayer_hue_shift=0):
        super().__init__(AdjustmentLayer_name, AdjustmentLayer_base_image)
        self.Layer_is_adjustment = True
        self.AdjustmentLayer_base_image = AdjustmentLayer_base_image.copy() if AdjustmentLayer_base_image else None
        self.AdjustmentLayer_target_hue = AdjustmentLayer_target_hue  # 0-179 (OpenCV HSV)
        self.AdjustmentLayer_hue_range = AdjustmentLayer_hue_range    # 0-179
        self.AdjustmentLayer_hue_shift = AdjustmentLayer_hue_shift    # -179 to 179
        self.AdjustmentLayer_update_adjustment()

    def AdjustmentLayer_update_adjustment(self):
        if self.AdjustmentLayer_base_image is None:
            self.Layer_image = None
            return
        adjustment_layer_base_image_qimage = self.AdjustmentLayer_base_image
        adjustment_layer_base_image_qimage = adjustment_layer_base_image_qimage.convertToFormat(QImage.Format_RGBA8888)
        adjustment_layer_base_image_qbyte_pointer = adjustment_layer_base_image_qimage.bits()
        adjustment_layer_base_image_qbyte_pointer.setsize(adjustment_layer_base_image_qimage.byteCount())
        adjustment_layer_base_image_numpy_array = np.frombuffer(
            adjustment_layer_base_image_qbyte_pointer, np.uint8
        ).reshape((adjustment_layer_base_image_qimage.height(), adjustment_layer_base_image_qimage.width(), 4)).copy()
        base_image_bgr_array = adjustment_layer_base_image_numpy_array[...,:3][...,::-1]  # Convert RGBA to BGR
        base_image_hsv_array = cv2.cvtColor(base_image_bgr_array, cv2.COLOR_BGR2HSV)
        # Create mask for hue range
        target_hue_lower_bound = (self.AdjustmentLayer_target_hue - self.AdjustmentLayer_hue_range//2) % 180
        target_hue_upper_bound = (self.AdjustmentLayer_target_hue + self.AdjustmentLayer_hue_range//2) % 180
        if target_hue_lower_bound < target_hue_upper_bound:
            hue_selection_boolean_mask_array = (
                (base_image_hsv_array[...,0] >= target_hue_lower_bound) & (base_image_hsv_array[...,0] <= target_hue_upper_bound)
            )
        else:
            hue_selection_boolean_mask_array = (
                (base_image_hsv_array[...,0] >= target_hue_lower_bound) | (base_image_hsv_array[...,0] <= target_hue_upper_bound)
            )
        # Shift hue only where mask is true
        hue_shifted_hsv_array = base_image_hsv_array.copy()
        hue_shifted_hsv_array[...,0][hue_selection_boolean_mask_array] = (
            base_image_hsv_array[...,0][hue_selection_boolean_mask_array].astype(int) + self.AdjustmentLayer_hue_shift
        ) % 180
        hue_shifted_bgr_array = cv2.cvtColor(hue_shifted_hsv_array, cv2.COLOR_HSV2BGR)
        hue_shifted_rgba_numpy_array = adjustment_layer_base_image_numpy_array.copy()
        hue_shifted_rgba_numpy_array[...,:3] = hue_shifted_bgr_array[...,::-1]
        # Alpha: 255 where mask, 0 elsewhere
        hue_shifted_rgba_numpy_array[...,3] = np.where(hue_selection_boolean_mask_array, 255, 0).astype(np.uint8)
        self.Layer_image = QImage(
            hue_shifted_rgba_numpy_array.data,
            adjustment_layer_base_image_qimage.width(),
            adjustment_layer_base_image_qimage.height(),
            4*adjustment_layer_base_image_qimage.width(),
            QImage.Format_RGBA8888
        ).copy()

class LayeredImageProject:
    """
    Core image project logic: manages layers and all image processing.
    Maintains base layer as a separate attribute, all other layers in a list.
    """
    def __init__(self):
        self.LayeredImageProject_base_layer = None  # Always the first image dragged in
        self.LayeredImageProject_other_layers = []  # All non-base layers, in stacking order (bottom to top)
        print('[DEBUG] LayeredImageProject.__init__: self.LayeredImageProject_other_layers initialized:', self.LayeredImageProject_other_layers)

    def LayeredImageProject_add_layer(self, img, name, filepath=None):
        print('[DEBUG] LayeredImageProject.add_layer called. img:', img, 'name:', name, 'filepath:', filepath)
        print('[DEBUG] LayeredImageProject.add_layer before insert: base =', self.LayeredImageProject_base_layer, 'others =', self.LayeredImageProject_other_layers)
        if not name and filepath:
            name = os.path.basename(filepath)
        elif filepath:
            name = os.path.basename(filepath)
        layer = Layer(name, img, Layer_filepath=filepath or name)
        if self.LayeredImageProject_base_layer is None:
            self.LayeredImageProject_base_layer = layer
        else:
            self.LayeredImageProject_other_layers.append(layer)
        print('[DEBUG] LayeredImageProject.add_layer after insert: base =', self.LayeredImageProject_base_layer, 'others =', self.LayeredImageProject_other_layers)

    def LayeredImageProject_delete_layer(self, idx):
        # idx is in the combined stack: 0 = base, 1 = first above base, ...
        if idx == 0:
            print('[ERROR] Cannot delete base layer!')
            return
        idx_other = idx - 1
        if 0 <= idx_other < len(self.LayeredImageProject_other_layers):
            del self.LayeredImageProject_other_layers[idx_other]

    def LayeredImageProject_reorder_layers(self, new_order_names):
        # Only reorder non-base layers
        new_others = []
        for name in new_order_names:
            for layer in self.LayeredImageProject_other_layers:
                if layer.Layer_name == name:
                    new_others.append(layer)
                    break
        self.LayeredImageProject_other_layers = new_others

    def get_all_layers(self):
        # Returns [base, ...others] for compositing/UI
        if self.LayeredImageProject_base_layer:
            return [self.LayeredImageProject_base_layer] + self.LayeredImageProject_other_layers
        else:
            return []


    def LayeredImageProject_set_layer_property(self, idx, prop, value):
        if 0 <= idx < len(self.get_all_layers()):
            setattr(self.get_all_layers()[idx], prop, value)

    def LayeredImageProject_get_layer(self, idx):
        if 0 <= idx < len(self.get_all_layers()):
            return self.get_all_layers()[idx]
        return None

    def LayeredImageProject_save_project(self, fname):
        data = []
        for layer in self.get_all_layers():
            mask_data = None
            if layer.Layer_mask:
                buffer = QByteArray()
                layer.Layer_mask.save(buffer, 'PNG')
                mask_data = base64.b64encode(buffer.data()).decode('utf-8')
            data.append({
                'name': layer.Layer_name,
                'filepath': layer.Layer_filepath,
                'visible': layer.Layer_visible,
                'blend_mode': layer.Layer_blend_mode,
                'opacity': layer.Layer_opacity,
                'scale': layer.Layer_scale,
                'offset': layer.Layer_offset,
                'rotation': layer.Layer_rotation,
                'mask': mask_data
            })
        with open(fname, 'w') as f:
            json.dump(data, f, indent=2)

    def LayeredImageProject_load_project(self, fname):
        with open(fname, 'r') as f:
            data = json.load(f)
        self.LayeredImageProject_base_layer = None
        self.LayeredImageProject_other_layers = []
        for idx, entry in enumerate(data):
            img = QImage(entry['filepath'])
            layer = Layer(entry['name'], img, Layer_filepath=entry['filepath'])
            layer.Layer_visible = entry.get('visible', True)
            layer.Layer_blend_mode = entry.get('blend_mode', 'Normal')
            layer.Layer_opacity = entry.get('opacity', 1.0)
            layer.Layer_scale = entry.get('scale', 1.0)
            layer.Layer_offset = tuple(entry.get('offset', (0,0)))
            layer.Layer_rotation = entry.get('rotation', 0.0)
            mask_data = entry.get('mask')
            if mask_data:
                mask_bytes = base64.b64decode(mask_data)
                mask_img = QImage()
                mask_img.loadFromData(mask_bytes, 'PNG')
                layer.Layer_mask = mask_img
            if idx == 0:
                self.LayeredImageProject_base_layer = layer
            else:
                self.LayeredImageProject_other_layers.append(layer)

    def LayeredImageProject_export_flattened_image(self, fname):
        base = LayeredImage_composite_layers(self.get_all_layers())
        if base:
            base.save(fname, 'PNG')

    def LayeredImageProject_snap_to_underlying_layer(self, layer_index_to_align):
        if layer_index_to_align < 1 or layer_index_to_align >= len(self.get_all_layers()):
            return
        top_layer = self.get_all_layers()[layer_index_to_align]
        base_layer = self.get_all_layers()[layer_index_to_align-1]
        if top_layer.image is None or base_layer.image is None:
            return
        def convert_qimage_to_grayscale_numpy_array(qimage_input):
            qimage_grayscale = qimage_input.convertToFormat(QImage.Format_Grayscale8)
            qimage_pointer = qimage_grayscale.bits()
            grayscale_numpy_array = np.array(qimage_pointer).reshape((qimage_grayscale.height(), qimage_grayscale.width()))
            return grayscale_numpy_array.copy()
        top_layer_grayscale_numpy_array = convert_qimage_to_grayscale_numpy_array(top_layer.image)
        base_layer_grayscale_numpy_array = convert_qimage_to_grayscale_numpy_array(base_layer.image)
        top_layer_sobel_edges_numpy_array = cv2.Sobel(top_layer_grayscale_numpy_array, cv2.CV_32F, 1, 0, ksize=3) + cv2.Sobel(top_layer_grayscale_numpy_array, cv2.CV_32F, 0, 1, ksize=3)
        base_layer_sobel_edges_numpy_array = cv2.Sobel(base_layer_grayscale_numpy_array, cv2.CV_32F, 1, 0, ksize=3) + cv2.Sobel(base_layer_grayscale_numpy_array, cv2.CV_32F, 0, 1, ksize=3)
        top_layer_sobel_edges_numpy_array = cv2.convertScaleAbs(top_layer_sobel_edges_numpy_array)
        base_layer_sobel_edges_numpy_array = cv2.convertScaleAbs(base_layer_sobel_edges_numpy_array)
        _, top_layer_binary_edge_mask_numpy_array = cv2.threshold(top_layer_sobel_edges_numpy_array, 40, 255, cv2.THRESH_BINARY)
        _, base_layer_binary_edge_mask_numpy_array = cv2.threshold(base_layer_sobel_edges_numpy_array, 40, 255, cv2.THRESH_BINARY)
        best_template_matching_score = None
        best_alignment_parameters = (1.0, 0, 0)
        candidate_scale_factors = np.linspace(0.8, 1.2, 17)
        for candidate_scale_factor in candidate_scale_factors:
            scaled_top_layer_binary_edge_mask_numpy_array = cv2.resize(
                top_layer_binary_edge_mask_numpy_array, (0,0), fx=candidate_scale_factor, fy=candidate_scale_factor, interpolation=cv2.INTER_LINEAR)
            if (scaled_top_layer_binary_edge_mask_numpy_array.shape[0] > base_layer_binary_edge_mask_numpy_array.shape[0] or
                scaled_top_layer_binary_edge_mask_numpy_array.shape[1] > base_layer_binary_edge_mask_numpy_array.shape[1]):
                continue
            template_matching_result_numpy_array = cv2.matchTemplate(
                base_layer_binary_edge_mask_numpy_array, scaled_top_layer_binary_edge_mask_numpy_array, cv2.TM_CCOEFF_NORMED)
            template_matching_min_value, template_matching_max_value, template_matching_min_location, template_matching_max_location = cv2.minMaxLoc(template_matching_result_numpy_array)
            if best_template_matching_score is None or template_matching_max_value > best_template_matching_score:
                best_template_matching_score = template_matching_max_value
                best_alignment_parameters = (candidate_scale_factor, template_matching_max_location[0], template_matching_max_location[1])
        best_scale_factor, best_aligned_left, best_aligned_top = best_alignment_parameters
        top_layer_height, top_layer_width = top_layer_grayscale_numpy_array.shape
        scaled_top_layer_width, scaled_top_layer_height = int(top_layer_width * best_scale_factor), int(top_layer_height * best_scale_factor)
        top_layer_rgba_qimage = top_layer.image.convertToFormat(QImage.Format_RGBA8888)
        top_layer_rgba_numpy_array = np.array(top_layer_rgba_qimage.bits()).reshape((top_layer_rgba_qimage.height(), top_layer_rgba_qimage.width(), 4)).copy()
        top_layer_rgba_numpy_array = cv2.resize(top_layer_rgba_numpy_array, (scaled_top_layer_width, scaled_top_layer_height), interpolation=cv2.INTER_LINEAR)
        base_layer_height, base_layer_width = base_layer_grayscale_numpy_array.shape
        output_aligned_rgba_numpy_array = np.zeros((base_layer_height, base_layer_width, 4), dtype=np.uint8)
        aligned_right = min(best_aligned_left+scaled_top_layer_width, base_layer_width)
        aligned_bottom = min(best_aligned_top+scaled_top_layer_height, base_layer_height)
        aligned_rgba_crop_numpy_array = top_layer_rgba_numpy_array[0:aligned_bottom-best_aligned_top, 0:aligned_right-best_aligned_left]
        output_aligned_rgba_numpy_array[best_aligned_top:aligned_bottom, best_aligned_left:aligned_right] = aligned_rgba_crop_numpy_array
        aligned_output_qimage = QImage(output_aligned_rgba_numpy_array.data, base_layer_width, base_layer_height, 4*base_layer_width, QImage.Format_RGBA8888).copy()
        top_layer.image = aligned_output_qimage

class LayerListWidget(QListWidget):
    def __init__(self, editor, LayerListWidget_parent=None):
        super().__init__(LayerListWidget_parent)
        self.editor = editor
        self.LayerListWidget_selected_index = None
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSpacing(4)
        self.setAlternatingRowColors(True)
        self.setStyleSheet('background: #232323; color: #e0e0e0; selection-background-color: #444;')
        self.currentRowChanged.connect(self.on_selection_changed)
        self.itemChanged.connect(self.on_item_changed)
        self.refresh_layer_list()

    def refresh_layer_list(self):
        self.blockSignals(True)
        self.clear()
        layers = self.editor.LayeredImageEditor_project.get_all_layers()
        ui_names = []
        for idx, layer in enumerate(layers):
            item = QListWidgetItem(layer.Layer_name)
            flags = item.flags() | Qt.ItemIsEditable | Qt.ItemIsUserCheckable
            if idx != 0:
                flags |= Qt.ItemIsDragEnabled
            else:
                flags &= ~Qt.ItemIsDragEnabled  # base layer cannot be dragged
            item.setFlags(flags)
            item.setCheckState(Qt.Checked if layer.Layer_visible else Qt.Unchecked)
            self.addItem(item)
            ui_names.append(layer.Layer_name)
        # Enhanced debug output
        print("\n[DEBUG][UI] LayerListWidget.refresh_layer_list():")
        print("  UI order (top to bottom):")
        for i in range(self.count()):
            print(f"    UI idx {i}: {self.item(i).text()}")
        print("  get_all_layers() order (index 0 = base):")
        for i, layer in enumerate(layers):
            print(f"    Model idx {i}: {layer.Layer_name}")
        self.blockSignals(False)

    def on_selection_changed(self, selected_index):
        layers = self.editor.LayeredImageEditor_project.get_all_layers()
        if selected_index is not None and 0 <= selected_index < len(layers):
            self.selected_layer_index = selected_index
        else:
            self.selected_layer_index = None
        self.editor.LayeredImageEditor_on_layer_selected()

    def on_item_changed(self, item):
        ui_idx = self.row(item)
        layers = self.editor.LayeredImageEditor_project.get_all_layers()
        model_idx = ui_idx
        # Prevent toggling base layer visibility
        if model_idx == 0:
            self.item(ui_idx).setCheckState(Qt.Checked)
            print('[DEBUG] Attempt to toggle base layer visibility ignored.')
            return
        if 0 <= model_idx < len(layers):
            is_layer_visible = item.checkState() == Qt.Checked
            layers[model_idx].Layer_visible = is_layer_visible
            self.editor.canvas.CanvasView_update_canvas()
        else:
            print(f"[DEBUG] on_item_changed: Invalid model_idx {model_idx} for layers list of length {len(layers)}")

    def dropEvent(self, event):
        super().dropEvent(event)
        new_order = [self.item(i).text() for i in range(self.count())]
        # Do not include base layer in reorder
        new_order = [name for name in new_order if name != self.editor.LayeredImageEditor_project.LayeredImageProject_base_layer.Layer_name]
        self.editor.LayeredImageEditor_project.LayeredImageProject_reorder_layers(new_order)
        self.refresh_layer_list()

def LayeredImage_composite_layers(project):
    """
    Composite a list of Layer objects into a single QImage.
    Output image and scene rect are always the base layer's size (project.LayeredImageProject_base_layer). All other layers are composited (with transforms) into this fixed-size image, clipped to the base.
    """
    base_layer = project.LayeredImageProject_base_layer
    if base_layer is None or base_layer.Layer_image is None or base_layer.Layer_image.isNull():
        print('[DEBUG][CANVAS] No valid base layer for compositing.')
        return None
    base_width = base_layer.Layer_image.width()
    base_height = base_layer.Layer_image.height()
    result_img = QImage(base_width, base_height, QImage.Format_RGBA8888)
    result_img.fill(Qt.transparent)
    painter = QPainter(result_img)
    # Draw all layers, from bottom (base) to top
    drew_any = False
    for layer in project.get_all_layers():
        if not layer.Layer_visible or layer.Layer_image is None or layer.Layer_image.isNull():
            continue
        composed_img = layer.Layer_image.copy()
        composed_t = QTransform()
        cx = composed_img.width() / 2
        cy = composed_img.height() / 2
        composed_t.translate(cx, cy)
        composed_t.rotate(layer.Layer_rotation)
        composed_t.scale(layer.Layer_scale, layer.Layer_scale)
        composed_t.translate(-cx, -cy)
        offset = getattr(layer, 'Layer_offset', (0,0))
        # Only apply rotation and scale to the transform
        # Offset will be used as the draw position
        # Debug print to confirm visual update, opacity, and transform
        print(f"[DEBUG][CANVAS] Drawing layer '{getattr(layer, 'Layer_name', '?')}' (id={id(layer)})")
        print(f"    Offset used: {offset}")
        print(f"    Layer_offset property: {getattr(layer, 'Layer_offset', None)}")
        print(f"    Opacity: {getattr(layer, 'Layer_opacity', 1.0)}")
        print(f"    Rotation: {getattr(layer, 'Layer_rotation', 0.0)}")
        print(f"    Scale: {getattr(layer, 'Layer_scale', 1.0)}")
        print(f"    QTransform matrix: {composed_t}")
        # Transform mask too if present
        if layer.Layer_mask is not None and not layer.Layer_mask.isNull():
            mask_img = layer.Layer_mask.transformed(composed_t, Qt.SmoothTransformation)
        else:
            mask_img = None
        transformed_img = composed_img.transformed(composed_t, Qt.SmoothTransformation)
        if mask_img is not None:
            transformed_img.setAlphaChannel(mask_img)
        painter.setOpacity(getattr(layer, 'Layer_opacity', 1.0))
        painter.drawImage(offset[0], offset[1], transformed_img)
        print(f"    [DRAW] At position ({offset[0]}, {offset[1]}) on base canvas")
        painter.setOpacity(1.0)  # Reset for next layer
        drew_any = True
        # --- Validation: Sample composited image at several points ---
        sample_points = [(0,0), (int(base_width/2), int(base_height/2)), (base_width-1, base_height-1)]
        for (sx, sy) in sample_points:
            if 0 <= sx < result_img.width() and 0 <= sy < result_img.height():
                rgba = result_img.pixelColor(sx, sy).getRgb()
                print(f"    [VALIDATE] Pixel at ({sx},{sy}): RGBA={rgba}")
    painter.end()
    if not drew_any and base_layer.Layer_image is not None and not base_layer.Layer_image.isNull():
        # Draw the base layer image directly if nothing else was drawn
        result_img = base_layer.Layer_image.copy()
    return result_img


def LayeredImage_blend_adjustment_layer(base, adj_img):
    # base, adj_img: QImage, both RGBA
    base = base.convertToFormat(QImage.Format_RGBA8888)
    adj_img = adj_img.convertToFormat(QImage.Format_RGBA8888)
    w = min(base.width(), adj_img.width())
    h = min(base.height(), adj_img.height())
    base_ptr = base.bits(); base_ptr.setsize(base.byteCount())
    adj_ptr = adj_img.bits(); adj_ptr.setsize(adj_img.byteCount())
    base_np = np.frombuffer(base_ptr, np.uint8).reshape((base.height(), base.width(), 4))[:h, :w]
    adj_np = np.frombuffer(adj_ptr, np.uint8).reshape((adj_img.height(), adj_img.width(), 4))[:h, :w]
    # Where adj alpha > 0, use adj RGB; else use base
    mask = adj_np[...,3] > 0
    result = base_np.copy()
    result[mask] = adj_np[mask]
    return QImage(result.data, w, h, 4*w, QImage.Format_RGBA8888).copy()

class CanvasView(QGraphicsView):
    def __init__(self, editor, project=None, CanvasView_parent=None):
        super().__init__(CanvasView_parent)
        self.editor = editor
        self.project = project
        self.CanvasView_show_alpha_mask = False  # Mode switch for showing mask only
        self.CanvasView_layers = []
        self.CanvasView_active_layer_idx = None
        self.CanvasView_mask_painting = False
        self.CanvasView_brush_radius = 16
        self.CanvasView_brush_color = QColor(255,255,255)
        self.CanvasView_tools_properties_callback = None
        self.CanvasView_last_hover_color = QColor(0,0,0)
        self.CanvasView_eyedropper_mode = False
        # --- Standard PyQt setup ---
        self.setAcceptDrops(True)
        self.CanvasView_scene = QGraphicsScene(self)
        self.setScene(self.CanvasView_scene)
        print('[DEBUG] CanvasView.__init__: self.CanvasView_layers initialized:', self.CanvasView_layers)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(Qt.black)

    def CanvasView_set_tools_properties_callback(self, callback):
        self.CanvasView_tools_properties_callback = callback

    def CanvasView_set_show_alpha_mask(self, enabled):
        self.CanvasView_show_alpha_mask = enabled
        self.CanvasView_update_canvas()

    def CanvasView_set_eyedropper_mode(self, enabled):
        self.CanvasView_eyedropper_mode = enabled

    def CanvasView_set_brush_color(self, color):
        self.CanvasView_brush_color = color
        if self.CanvasView_tools_properties_callback:
            self.CanvasView_tools_properties_callback(brush_color=self.CanvasView_brush_color, hover_color=self.CanvasView_last_hover_color, brush_size=self.CanvasView_brush_radius)

    def CanvasView_set_brush_radius(self, radius):
        self.CanvasView_brush_radius = radius
        if self.CanvasView_tools_properties_callback:
            self.CanvasView_tools_properties_callback(brush_color=self.CanvasView_brush_color, hover_color=self.CanvasView_last_hover_color, brush_size=self.CanvasView_brush_radius)

    def mouseMoveEvent(self, event: QMouseEvent):
        # Update hovered color
        scene_pos = self.mapToScene(event.pos())
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        img = self.CanvasView_get_composited_image()
        color = QColor(0,0,0)
        if img and 0 <= x < img.width() and 0 <= y < img.height():
            color = QColor(img.pixel(x, y))
        self.CanvasView_last_hover_color = color
        if self.CanvasView_tools_properties_callback:
            self.CanvasView_tools_properties_callback(brush_color=self.CanvasView_brush_color, hover_color=color, brush_size=self.CanvasView_brush_radius)
        # Continue normal paint logic
        if self.CanvasView_mask_painting and self.CanvasView_active_layer_idx is not None and event.buttons() & Qt.LeftButton:
            self.CanvasView_paint_mask(event.pos())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if getattr(self, 'CanvasView_eyedropper_mode', False):
            scene_pos = self.mapToScene(event.pos())
            x = int(scene_pos.x())
            y = int(scene_pos.y())
            img = self.CanvasView_get_composited_image()
            if img and 0 <= x < img.width() and 0 <= y < img.height():
                color = QColor(img.pixel(x, y)).getRgb()
                # Call back to editor
                if hasattr(self.parent(), 'on_canvas_color_picked'):
                    self.parent().on_canvas_color_picked((x, y), color)
            self.CanvasView_eyedropper_mode = False
            return
        if self.CanvasView_mask_painting and self.CanvasView_active_layer_idx is not None:
            self.CanvasView_paint_mask(event.pos())
        super().mousePressEvent(event)

    def CanvasView_get_composited_image(self):
        if self.project and self.project.get_all_layers():
            return LayeredImage_composite_layers(self.project)
        return None

    def CanvasView_update_canvas(self):
        print('[DEBUG] CanvasView.update_canvas called. self.project =', self.project)
        self.CanvasView_scene.clear()
        # Always determine base layer (bottom-most visible layer) for canvas size
        base_layer = None
        layers = self.project.get_all_layers() if self.project else []
        for l in reversed(layers):
            if l.Layer_visible and l.Layer_image is not None and not l.Layer_image.isNull():
                base_layer = l
                break
        base_width, base_height = 512, 512
        if base_layer is not None and base_layer.Layer_image is not None and not base_layer.Layer_image.isNull():
            base_width = base_layer.Layer_image.width()
            base_height = base_layer.Layer_image.height()
        if self.CanvasView_show_alpha_mask:
            idx = self.CanvasView_active_layer_idx
            if idx is not None and 0 <= idx < len(layers):
                layer = layers[idx]
                mask = layer.Layer_mask
                if mask is not None and not mask.isNull():
                    mask_img = mask.convertToFormat(QImage.Format_Grayscale8)
                    pix = QPixmap.fromImage(mask_img)
                    self.CanvasView_scene.addPixmap(pix)
                    self.setSceneRect(QRectF(0, 0, base_width, base_height))
                    return
                else:
                    print('[DEBUG] CanvasView.update_canvas: No valid mask to display.')
            self.setSceneRect(QRectF(0,0,base_width,base_height))
            return
        if not layers:
            print('[DEBUG] CanvasView.update_canvas: No layers to display.')
            self.setSceneRect(QRectF(0,0,base_width,base_height))
            return
        # Always use the project reference for compositing and sizing
        project = self.project
        if project is not None:
            base = LayeredImage_composite_layers(project)
            if base and not base.isNull():
                pix = QPixmap.fromImage(base)
                self.CanvasView_scene.addPixmap(pix)
                self.setSceneRect(QRectF(0, 0, base.width(), base.height()))
            else:
                print('[DEBUG] CanvasView.update_canvas: No valid base image after compositing.')
                if project.LayeredImageProject_base_layer and project.LayeredImageProject_base_layer.Layer_image:
                    w = project.LayeredImageProject_base_layer.Layer_image.width()
                    h = project.LayeredImageProject_base_layer.Layer_image.height()
                    self.setSceneRect(QRectF(0, 0, w, h))
                else:
                    self.setSceneRect(QRectF(0, 0, 512, 512))
        else:
            print('[DEBUG] CanvasView.update_canvas: No project ref found.')
            self.setSceneRect(QRectF(0, 0, 512, 512))


    def CanvasView_set_layers(self, project):
        print('[DEBUG] CanvasView.set_layers called. project =', project)
        self.project = project
        self.CanvasView_layers = project.get_all_layers() if project else []
        print(f"[DEBUG][CANVAS] CanvasView_set_layers: project set to {project}, layers = {self.CanvasView_layers}")
        self.CanvasView_update_canvas()

    def CanvasView_paint_mask(self, pos):
        idx = self.CanvasView_active_layer_idx
        if idx is None or idx < 0 or idx >= len(self.project.get_all_layers()):
            return
        layer = self.project.get_all_layers()[idx]
        layer = self.CanvasView_layers[idx]
        if layer.Layer_mask is None:
            layer.Layer_mask = QImage(layer.Layer_image.size(), QImage.Format_Grayscale8)
            layer.Layer_mask.fill(255)
        scene_pos = self.mapToScene(pos)
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        painter = QPainter(layer.Layer_mask)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.CanvasView_brush_color)
        painter.drawEllipse(x-self.CanvasView_brush_radius//2, y-self.CanvasView_brush_radius//2, self.CanvasView_brush_radius, self.CanvasView_brush_radius)
        painter.end()
        self.CanvasView_update_canvas()

    @staticmethod
    def LayeredImage_blend_images_static(base, top, opacity=1.0, blend_mode='Normal'):
        try:
            base_np = CanvasView.qimage_to_np_static(base)
            top_np = CanvasView.qimage_to_np_static(top)
        except Exception as e:
            print(f"[ERROR] blend_images_static: Failed to convert QImage to numpy array: {e}")
            raise
        # Ensure shapes match
        if base_np.shape != top_np.shape:
            h = min(base_np.shape[0], top_np.shape[0])
            w = min(base_np.shape[1], top_np.shape[1])
            base_np = base_np[:h, :w]
            top_np = top_np[:h, :w]
        # Apply opacity to top alpha
        top_alpha = (top_np[...,3:4].astype(np.float32) * opacity).clip(0,255)
        base_alpha = base_np[...,3:4].astype(np.float32)
        if blend_mode == 'Normal':
            alpha = top_alpha/255.0
            out_rgb = base_np[...,:3] * (1-alpha) + top_np[...,:3] * alpha
            out_alpha = 255 * (1 - (1 - top_alpha/255.0) * (1 - base_alpha/255.0))
            out = np.concatenate([out_rgb, out_alpha], axis=-1)
        elif blend_mode == 'Multiply':
            out_rgb = CanvasView.multiply_blend_static(base_np[...,:3], top_np[...,:3])
            out_alpha = 255 * (1 - (1 - top_alpha/255.0) * (1 - base_alpha/255.0))
            out = np.concatenate([out_rgb, out_alpha], axis=-1)
        elif blend_mode == 'Darken':
            out_rgb = CanvasView.darken_blend_static(base_np[...,:3], top_np[...,:3])
            out_alpha = 255 * (1 - (1 - top_alpha/255.0) * (1 - base_alpha/255.0))
            out = np.concatenate([out_rgb, out_alpha], axis=-1)
        elif blend_mode == 'Screen':
            out_rgb = 255 - (255-base_np[...,:3])*(255-top_np[...,:3])/255
            out_alpha = 255 * (1 - (1 - top_alpha/255.0) * (1 - base_alpha/255.0))
            out = np.concatenate([out_rgb, out_alpha], axis=-1)
        else:
            out = top_np
        out = np.clip(out,0,255).astype(np.uint8)
        return CanvasView.np_to_qimage_static(out)

    def blend_images(self, base, top, mode, opacity=1.0):
        return CanvasView.LayeredImage_blend_images_static(base, top, mode, opacity)

    @staticmethod
    def multiply_blend_static(base_np, top_np):
        return (base_np/255.0 * top_np/255.0 * 255).astype(np.uint8)

    @staticmethod
    def darken_blend_static(base_np, top_np):
        return np.minimum(base_np, top_np)

    @staticmethod
    def qimage_to_np_static(img):
        if img is None or img.isNull():
            raise ValueError("Invalid QImage for conversion to numpy array.")
        img = img.convertToFormat(QImage.Format_RGBA8888)
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        arr = np.frombuffer(ptr, np.uint8).reshape((img.height(), img.width(), 4))
        return arr.copy()

    @staticmethod
    def np_to_qimage_static(arr):
        h, w, c = arr.shape
        img = QImage(arr.data, w, h, 4*w, QImage.Format_RGBA8888)
        return img.copy()

    def multiply_blend(self, base_np, top_np):
        return CanvasView.multiply_blend_static(base_np, top_np)

    def darken_blend(self, base_np, top_np):
        return CanvasView.darken_blend_static(base_np, top_np)

    def qimage_to_np(self, img):
        return CanvasView.qimage_to_np_static(img)

    def np_to_qimage(self, arr):
        return CanvasView.np_to_qimage_static(arr)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            img = QImage(path)
            if img.isNull():
                continue
            self.parent().add_image_layer(img, path)

    def mousePressEvent(self, event: QMouseEvent):
        if self.CanvasView_mask_painting and self.CanvasView_active_layer_idx is not None:
            self.CanvasView_paint_mask(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.CanvasView_mask_painting and self.CanvasView_active_layer_idx is not None and event.buttons() & Qt.LeftButton:
            self.CanvasView_paint_mask(event.pos())
        super().mouseMoveEvent(event)

    def paint_mask(self, pos):
        idx = self.CanvasView_active_layer_idx
        if idx is None or idx < 0 or idx >= len(self.CanvasView_layers):
            return
        layer = self.CanvasView_layers[idx]
        if layer.Layer_mask is None:
            layer.Layer_mask = QImage(layer.Layer_image.size(), QImage.Format_Grayscale8)
            layer.Layer_mask.fill(255)
        # Map view pos to image coordinates
        scene_pos = self.mapToScene(pos)
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        painter = QPainter(layer.Layer_mask)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.CanvasView_brush_color)
        painter.drawEllipse(x-self.CanvasView_brush_radius//2, y-self.CanvasView_brush_radius//2, self.CanvasView_brush_radius, self.CanvasView_brush_radius)
        painter.end()
        self.CanvasView_update_canvas()
        
class LayeredImageEditor(QMainWindow):
    def debug_print_layer_stack(self, context=None):
        layers = self.LayeredImageEditor_project.get_all_layers()
        base = self.LayeredImageEditor_project.LayeredImageProject_base_layer
        selected_idx = None
        if hasattr(self, 'LayerListWidget_layer_list'):
            selected_idx = self.LayerListWidget_layer_list.currentRow()
        print(f'\n[DEBUG][{context}] Current Layer Stack:')
        for i, layer in enumerate(layers):
            tag = 'BASE' if layer == base else ''
            sel = '<-- SELECTED' if selected_idx == i else ''
            print(f'  [{i}] {layer.Layer_name} {tag} {sel} (visible={getattr(layer, "Layer_visible", "?")}, opacity={getattr(layer, "Layer_opacity", "?")}, blend={getattr(layer, "Layer_blend_mode", "?")}, scale={getattr(layer, "Layer_scale", "?")}, offset={getattr(layer, "Layer_offset", "?")}, rotation={getattr(layer, "Layer_rotation", "?")})')
        print('')
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.LayeredImageEditor_constructor()

    """
    Main window and controller for the Layered Image Editor application.
    """
    def LayeredImageEditor_constructor(self):
        super().__init__()
        self.LayeredImageEditor_window_title = 'Layered Image Editor'
        self.setWindowTitle(self.LayeredImageEditor_window_title)
        self.LayeredImageEditor_window_width = 1200
        self.LayeredImageEditor_window_height = 800
        self.resize(self.LayeredImageEditor_window_width, self.LayeredImageEditor_window_height)
        self.LayeredImageEditor_project = LayeredImageProject()
        self.LayeredImageEditor_init_ui()

    def LayeredImageEditor_init_ui(self):
        # Ensure central widget and layout are set up only once
        if not self.centralWidget():
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout()
            central_widget.setLayout(main_layout)
        else:
            main_layout = self.centralWidget().layout()

        # --- Restore full UI: layer stack, toolbar, canvas, and properties panel ---

        # Main horizontal splitter: left = canvas, right = all controls stacked
        self.LayeredImageEditor_main_splitter = QSplitter()
        self.LayeredImageEditor_main_splitter.setOrientation(Qt.Horizontal)
        main_layout.addWidget(self.LayeredImageEditor_main_splitter)

        # --- Left: Canvas (takes up most space) ---
        self.canvas = CanvasView(self, project=self.LayeredImageEditor_project)
        self.LayeredImageEditor_main_splitter.addWidget(self.canvas)

        # --- Right: All controls stacked vertically ---
        self.LayeredImageEditor_right_panel = QWidget()
        self.LayeredImageEditor_right_panel.setAcceptDrops(True)
        self.LayeredImageEditor_right_panel.installEventFilter(self)
        self.LayeredImageEditor_right_panel_layout = QVBoxLayout()
        self.LayeredImageEditor_right_panel_layout.setContentsMargins(0,0,0,0)
        self.LayeredImageEditor_right_panel.setLayout(self.LayeredImageEditor_right_panel_layout)

        # Layer stack viewer
        self.LayerListWidget_layer_list = LayerListWidget(editor=self, LayerListWidget_parent=None)
        self.LayeredImageEditor_right_panel_layout.addWidget(self.LayerListWidget_layer_list)

        # Function buttons panel (color-coded)
        self.LayeredImageEditor_toolbar_panel = LayerToolbarPanel(self)
        self.LayeredImageEditor_right_panel_layout.addWidget(self.LayeredImageEditor_toolbar_panel)

        # Properties panel
        self.LayeredImageEditor_properties_panel = LayerPropertiesPanel(self)
        self.LayeredImageEditor_right_panel_layout.addWidget(self.LayeredImageEditor_properties_panel)

        self.LayeredImageEditor_right_panel_layout.addStretch()
        self.LayeredImageEditor_right_panel.setMinimumWidth(200)
        self.LayeredImageEditor_right_panel.setMaximumWidth(320)

        self.LayeredImageEditor_main_splitter.addWidget(self.LayeredImageEditor_right_panel)
        self.LayeredImageEditor_main_splitter.setStretchFactor(0, 5)  # canvas stretches more
        self.LayeredImageEditor_main_splitter.setStretchFactor(1, 1)  # right panel less

        # --- Toolbar (now in right panel, vertical stack) ---
        self.toolbar_layout = QVBoxLayout()
        self.toolbar_layout.setSpacing(6)
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setLayout(self.toolbar_layout)
        self.LayeredImageEditor_add_show_alpha_mask_button()
        self.LayeredImageEditor_add_color_range_select_button()
        self.LayeredImageEditor_setup_tools_properties_panel()
        self.canvas.CanvasView_set_tools_properties_callback(self.LayeredImageEditor_update_tools_properties_panel)
        self.LayeredImageEditor_update_tools_properties_panel(
            brush_color=self.canvas.CanvasView_brush_color,
            hover_color=QColor(0,0,0),
            brush_size=self.canvas.CanvasView_brush_radius
        )
        self.LayeredImageEditor_right_panel_layout.insertWidget(0, self.toolbar_widget)
        # Initial refresh
        self.LayeredImageEditor_refresh_layers()
        # Apply dark mode theme
        self.LayeredImageEditor_apply_dark_mode()

    def LayeredImageEditor_setup_tools_properties_panel(self):
        self.LayeredImageEditor_tools_properties_group = QGroupBox('Tools Properties:')
        layout = QVBoxLayout()
        # Brush color
        brush_row = QHBoxLayout()
        brush_row.addWidget(QLabel('Brush Color:'))
        self.LayeredImageEditor_brush_color_swatch = QLabel()
        self.LayeredImageEditor_brush_color_swatch.setFixedSize(32, 20)
        brush_row.addWidget(self.LayeredImageEditor_brush_color_swatch)
        layout.addLayout(brush_row)
        # Hover color
        hover_row = QHBoxLayout()
        hover_row.addWidget(QLabel('Color Under Mouse:'))
        self.LayeredImageEditor_hover_color_swatch = QLabel()
        self.LayeredImageEditor_hover_color_swatch.setFixedSize(32, 20)
        hover_row.addWidget(self.LayeredImageEditor_hover_color_swatch)
        layout.addLayout(hover_row)
        # Brush size
        self.LayeredImageEditor_brush_size_label = QLabel('Brush Size: 16')
        layout.addWidget(self.LayeredImageEditor_brush_size_label)
        self.LayeredImageEditor_tools_properties_group.setLayout(layout)
        self.toolbar_layout.addWidget(self.LayeredImageEditor_tools_properties_group, alignment=Qt.AlignRight)

    def LayeredImageEditor_update_tools_properties_panel(self, brush_color=None, hover_color=None, brush_size=None):
        if brush_color is not None:
            self.LayeredImageEditor_brush_color_swatch.setStyleSheet(f'background: {brush_color.name()}; border: 1px solid #888;')
        if hover_color is not None:
            self.LayeredImageEditor_hover_color_swatch.setStyleSheet(f'background: {hover_color.name()}; border: 1px solid #888;')
        if brush_size is not None:
            self.LayeredImageEditor_brush_size_label.setText(f'Brush Size: {brush_size}')

    def LayeredImageEditor_add_show_alpha_mask_button(self):
        LayeredImageEditor_show_alpha_mask_button = QPushButton('Show Alpha Mask')
        LayeredImageEditor_show_alpha_mask_button.setCheckable(True)
        LayeredImageEditor_show_alpha_mask_button.toggled.connect(self.LayeredImageEditor_on_show_alpha_mask_toggled)
        self.toolbar_layout.addWidget(LayeredImageEditor_show_alpha_mask_button)
        self.LayeredImageEditor_show_alpha_mask_btn = LayeredImageEditor_show_alpha_mask_button

    def LayeredImageEditor_on_show_alpha_mask_toggled(self, checked):
        self.canvas.CanvasView_set_show_alpha_mask(checked)

    def LayeredImageEditor_add_color_range_select_button(self):
        LayeredImageEditor_color_range_select_button = QPushButton('Color Range Select')
        LayeredImageEditor_color_range_select_button.clicked.connect(self.LayeredImageEditor_on_color_range_select)
        self.toolbar_layout.addWidget(LayeredImageEditor_color_range_select_button)
        self.LayeredImageEditor_color_range_select_btn = LayeredImageEditor_color_range_select_button

    def LayeredImageEditor_on_color_range_select(self):
        self.canvas.CanvasView_set_eyedropper_mode(True)
        self.statusBar().showMessage('Click a pixel on the canvas to select color range...')

    def LayeredImageEditor_on_canvas_color_picked(self, canvas_pixel_position, canvas_pixel_color_tuple):
        LayeredImageEditor_canvas_pixel_bgr_array = np.uint8([[list(canvas_pixel_color_tuple[:3])[::-1]]])
        LayeredImageEditor_canvas_pixel_hsv_array = cv2.cvtColor(LayeredImageEditor_canvas_pixel_bgr_array, cv2.COLOR_BGR2HSV)
        LayeredImageEditor_canvas_pixel_hue_value = int(LayeredImageEditor_canvas_pixel_hsv_array[0,0,0])
        LayeredImageEditor_current_layer_object = self.LayeredImageEditor_project.get_all_layers()[self.LayerListWidget_layer_list.currentRow()] if self.LayerListWidget_layer_list.currentRow() >= 0 else None
        LayeredImageEditor_base_image_qimage = LayeredImageEditor_current_layer_object.image if LayeredImageEditor_current_layer_object and LayeredImageEditor_current_layer_object.image else None
        LayeredImageEditor_new_adjustment_layer = AdjustmentLayer(f'Hue Shift ({LayeredImageEditor_canvas_pixel_hue_value})', LayeredImageEditor_base_image_qimage, target_hue=LayeredImageEditor_canvas_pixel_hue_value, hue_range=30, hue_shift=30)
        self.LayeredImageEditor_project.get_all_layers().insert(0, LayeredImageEditor_new_adjustment_layer)
        self.LayeredImageEditor_refresh_layers()
        self.canvas.CanvasView_set_eyedropper_mode(False)
        self.statusBar().showMessage('Adjustment layer added. Adjust properties in the layer panel.')

    def LayeredImageEditor_apply_dark_mode(self):
        """
        Apply a professional dark mode style to the whole editor, including canvas, buttons, and panels.
        """
        dark_palette = """
            QWidget {
                background-color: #181818;
                color: #e0e0e0;
            }
            QMainWindow {
                background-color: #181818;
            }
            QMenuBar, QMenu, QToolTip, QListWidget, QAbstractItemView, QDialog {
                background-color: #232323;
                color: #e0e0e0;
                border: 1px solid #444;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSlider {
                background-color: #232323;
                color: #e0e0e0;
                border: 1px solid #444;
            }
            QLabel {
                color: #e0e0e0;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #232323;
                border: 1px solid #444;
            }
            QPushButton {
                background-color: #232323;
                color: #fafafa;
                border: 2px solid #444;
                border-radius: 6px;
                padding: 6px 0;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #333333;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #111111;
                color: #cccccc;
            }
            QListWidget {
                background: #232323;
                color: #e0e0e0;
                selection-background-color: #333333;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #444;
                margin-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
            }
        """
        self.setStyleSheet(dark_palette)
        # Canvas background
        self.canvas.setBackgroundBrush(Qt.black)
        # Update color swatches for dark mode
        if hasattr(self, 'LayeredImageEditor_brush_color_swatch'):
            self.LayeredImageEditor_brush_color_swatch.setStyleSheet(f'background: {self.canvas.CanvasView_brush_color.name()}; border: 1px solid #888;')
        if hasattr(self, 'LayeredImageEditor_hover_color_swatch'):
            self.LayeredImageEditor_hover_color_swatch.setStyleSheet('background: #000; border: 1px solid #888;')
        if hasattr(self, 'LayeredImageEditor_tools_properties_group'):
            self.LayeredImageEditor_tools_properties_group.setStyleSheet('QGroupBox { color: #e0e0e0; border: 1px solid #444; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px 0 3px; } QLabel { color: #e0e0e0; }')
        # Update all QPushButtons to use dark mode style
        for btn in self.findChildren(QPushButton):
            btn.setStyleSheet('background-color: #232323; color: #fafafa; border: 2px solid #444; border-radius: 6px; padding: 6px 0; font-weight: bold;')

        # Button color styles (bevel/emboss, muted colors)
        btn_styles = {
            'add': 'background-color: #3e5e4b; color: #e0f2e9; font-weight: bold; border: 3px outset #5fa87a; border-radius: 7px; padding: 7px 0; font-size: 15px;',
            'save': 'background-color: #2f3f5e; color: #dbe8fa; font-weight: bold; border: 3px outset #4a6a9c; border-radius: 7px; padding: 7px 0; font-size: 15px;',
            'load': 'background-color: #2f3f5e; color: #dbe8fa; font-weight: bold; border: 3px outset #4a6a9c; border-radius: 7px; padding: 7px 0; font-size: 15px;',
            'export': 'background-color: #2f3f5e; color: #dbe8fa; font-weight: bold; border: 3px outset #4a6a9c; border-radius: 7px; padding: 7px 0; font-size: 15px;',
            'del': 'background-color: #4d3e5e; color: #f2e9fa; font-weight: bold; border: 3px outset #8a6ab8; border-radius: 7px; padding: 7px 0; font-size: 15px;',
            'mask': 'background-color: #4d3e5e; color: #f2e9fa; font-weight: bold; border: 3px outset #8a6ab8; border-radius: 7px; padding: 7px 0; font-size: 15px;',
            'snap': 'background-color: #4d3e5e; color: #f2e9fa; font-weight: bold; border: 3px outset #8a6ab8; border-radius: 7px; padding: 7px 0; font-size: 15px;',
            'diff': 'background-color: #7e6c2e; color: #f7f4e0; font-weight: bold; border: 3px outset #bba94a; border-radius: 7px; padding: 7px 0; font-size: 15px;'
        }
        btn_map = getattr(self, '_dark_mode_btn_map', None)
        if btn_map is None:
            # Map button names to instance variables if not already mapped
            btn_map = {}
            for btn in self.findChildren(QPushButton):
                text = btn.text().lower()
                if 'add' in text:
                    btn_map['add'] = btn
                elif 'save' in text:
                    btn_map['save'] = btn
                elif 'load' in text:
                    btn_map['load'] = btn
                elif 'export' in text:
                    btn_map['export'] = btn
                elif 'delete' in text:
                    btn_map['del'] = btn
                elif 'mask' in text:
                    btn_map['mask'] = btn
                elif 'snap' in text:
                    btn_map['snap'] = btn
                elif 'diff' in text:
                    btn_map['diff'] = btn
            self._dark_mode_btn_map = btn_map
        for key, btn in btn_map.items():
            if key in btn_styles:
                btn.setStyleSheet(btn_styles[key])


    def LayeredImageEditor_add_layer_dialog(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Add Image Layer', '', 'Images (*.png *.jpg *.jpeg *.bmp)')
        if fname:
            img = QImage(fname)
            if not img.isNull():
                self.LayeredImageEditor_add_image_layer(img, fname, filepath=fname)

    def LayeredImageEditor_add_image_layer(self, image_to_add, image_layer_name, image_layer_filepath=None):
        self.debug_print_layer_stack('add_image_layer')
        self.LayeredImageEditor_project.LayeredImageProject_add_layer(image_to_add, image_layer_name, image_layer_filepath)
        self.LayeredImageEditor_refresh_layers()
        self.LayerListWidget_layer_list.setCurrentRow(0)

    def LayeredImageEditor_delete_layer(self):
        self.debug_print_layer_stack('delete_layer')
        idx = self.LayerListWidget_layer_list.currentRow()
        self.LayeredImageEditor_project.LayeredImageProject_delete_layer(idx)
        self.LayeredImageEditor_refresh_layers()

    def LayeredImageEditor_toggle_mask_paint(self):
        idx = self.LayerListWidget_layer_list.currentRow()
        if 0 <= idx < len(self.LayeredImageEditor_project.get_all_layers()):
            self.canvas.mask_painting = not self.canvas.mask_painting
            self.canvas.active_layer_idx = idx

    def LayeredImageEditor_save_project(self):
        fname, _ = QFileDialog.getSaveFileName(self, 'Save Project', '', 'Layered Image Project (*.json)')
        if not fname:
            return
        self.LayeredImageEditor_project.LayeredImageProject_save_project(fname)

    def LayeredImageEditor_load_project(self):
        fname, _ = QFileDialog.getOpenFileName(self, 'Load Project', '', 'Layered Image Project (*.json)')
        if not fname:
            return
        self.LayeredImageEditor_project.LayeredImageProject_load_project(fname)
        self.LayeredImageEditor_refresh_layers()

    def LayeredImageEditor_export_flattened_image(self):
        now = datetime.now()
        suffix = now.strftime("_%Y%m%d%H%M%S")
        fname, _ = QFileDialog.getSaveFileName(self, 'Export Flattened PNG', f"flattened{suffix}.png", 'PNG Files (*.png)')
        if not fname:
            return
        self.LayeredImageEditor_project.LayeredImageProject_export_flattened_image(fname)

    def LayeredImageEditor_fit_layer_to_canvas(self):
        idx = self.LayerListWidget_layer_list.currentRow()
        if idx is None or idx < 0 or idx >= len(self.LayeredImageEditor_project.get_all_layers()):
            return
        layer = self.LayeredImageEditor_project.get_all_layers()[idx]
        if layer.Layer_image is None or layer.Layer_image.isNull():
            return
        # Always use the BASE layer as the guide, regardless of visibility or order
        base_layer = self.LayeredImageEditor_project.LayeredImageProject_base_layer
        if base_layer is None or base_layer.Layer_image is None or base_layer.Layer_image.isNull():
            return
        base_width = base_layer.Layer_image.width()
        base_height = base_layer.Layer_image.height()
        img_width = layer.Layer_image.width()
        img_height = layer.Layer_image.height()
        if img_width == 0:
            return
        scale = base_width / img_width
        layer.Layer_scale = scale
        new_img_width = img_width * scale
        new_img_height = img_height * scale
        offset_x = (base_width - new_img_width) / 2
        offset_y = (base_height - new_img_height) / 2
        layer.Layer_offset = (int(offset_x), int(offset_y))
        self.canvas.CanvasView_update_canvas()


    def LayeredImageEditor_show_diff_mask(self):
        idx = self.LayerListWidget_layer_list.currentRow()
        if idx < 1 or idx >= len(self.LayeredImageEditor_project.get_all_layers()):
            print("Need at least two layers and a valid selection to show diff mask.")
            return
        layer_top = self.LayeredImageEditor_project.get_all_layers()[idx]
        layer_base = self.LayeredImageEditor_project.get_all_layers()[idx-1]
        if layer_top.Layer_image is None or layer_base.Layer_image is None:
            print("Both selected and underlying layers must have images.")
            return
        # Convert both images to grayscale, same size
        img1 = layer_top.Layer_image.convertToFormat(QImage.Format_Grayscale8)
        img2 = layer_base.Layer_image.convertToFormat(QImage.Format_Grayscale8)
        LayeredImageEditor_diff_image_width = min(img1.width(), img2.width())
        LayeredImageEditor_diff_image_height = min(img1.height(), img2.height())
        img1 = img1.copy(0, 0, LayeredImageEditor_diff_image_width, LayeredImageEditor_diff_image_height)
        img2 = img2.copy(0, 0, LayeredImageEditor_diff_image_width, LayeredImageEditor_diff_image_height)
        LayeredImageEditor_diff_image_ptr1 = img1.bits()
        LayeredImageEditor_diff_image_arr1 = np.array(LayeredImageEditor_diff_image_ptr1).reshape((LayeredImageEditor_diff_image_height, LayeredImageEditor_diff_image_width)).copy()
        LayeredImageEditor_diff_image_ptr2 = img2.bits()
        LayeredImageEditor_diff_image_arr2 = np.array(LayeredImageEditor_diff_image_ptr2).reshape((LayeredImageEditor_diff_image_height, LayeredImageEditor_diff_image_width)).copy()
        # Compute absolute difference
        LayeredImageEditor_diff_image_difference_array = np.abs(LayeredImageEditor_diff_image_arr1.astype(np.int16) - LayeredImageEditor_diff_image_arr2.astype(np.int16)).astype(np.uint8)
        # Enhance for visibility: scale up contrast
        LayeredImageEditor_diff_image_difference_array = (LayeredImageEditor_diff_image_difference_array * 4).clip(0, 255).astype(np.uint8)
        # Convert back to QImage
        LayeredImageEditor_diff_image_qimage = QImage(LayeredImageEditor_diff_image_difference_array.data, LayeredImageEditor_diff_image_width, LayeredImageEditor_diff_image_height, LayeredImageEditor_diff_image_width, QImage.Format_Grayscale8)
        self.canvas.show_diff_mask(LayeredImageEditor_diff_image_qimage)

    def LayeredImageEditor_snap_to_underlying_layer(self):
        idx = self.LayerListWidget_layer_list.currentRow()
        self.LayeredImageEditor_project.LayeredImageProject_snap_to_underlying_layer(idx)
        self.refresh_layers()

    def LayeredImageEditor_refresh_layers(self):
        self.debug_print_layer_stack('refresh_layers')
        print('[DEBUG] LayeredImageEditor.refresh_layers: self.LayeredImageEditor_project.get_all_layers() =', self.LayeredImageEditor_project.get_all_layers())
        self.LayerListWidget_layer_list.blockSignals(True)
        self.LayerListWidget_layer_list.clear()
        for LayeredImageEditor_layer_index, LayeredImageEditor_layer_object in enumerate(self.LayeredImageEditor_project.get_all_layers()):
            # Thumbnail preview
            if LayeredImageEditor_layer_object.Layer_image and not LayeredImageEditor_layer_object.Layer_image.isNull():
                thumb = LayeredImageEditor_layer_object.Layer_image.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                icon = QIcon(QPixmap.fromImage(thumb))
            else:
                icon = QIcon()
            LayeredImageEditor_layer_list_widget_item = QListWidgetItem(icon, LayeredImageEditor_layer_object.Layer_name)
            LayeredImageEditor_layer_list_widget_item.setCheckState(Qt.Checked if LayeredImageEditor_layer_object.Layer_visible else Qt.Unchecked)
            LayeredImageEditor_layer_list_widget_item.setFlags(LayeredImageEditor_layer_list_widget_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.LayerListWidget_layer_list.addItem(LayeredImageEditor_layer_list_widget_item)
        self.LayerListWidget_layer_list.blockSignals(False)
        self.LayerListWidget_layer_list.itemChanged.connect(self.LayeredImageEditor_on_layer_checkbox_changed)
        self.canvas.CanvasView_set_layers(self.LayeredImageEditor_project)

    def LayeredImageEditor_add_opacity_sliders(self):
        # Remove old sliders if any
        for layer_list_index in range(self.LayerListWidget_layer_list.count()):
            opacity_slider_widget = self.LayerListWidget_layer_list.itemWidget(self.LayerListWidget_layer_list.item(layer_list_index))
            if opacity_slider_widget:
                self.LayerListWidget_layer_list.removeItemWidget(self.LayerListWidget_layer_list.item(layer_list_index))

        # Add sliders for each layer
        print('[DEBUG] LayeredImageEditor.refresh_layers: self.LayeredImageEditor_project.get_all_layers() =', self.LayeredImageEditor_project.get_all_layers())
        for layer_index, layer_object in enumerate(self.LayeredImageEditor_project.get_all_layers()):
            opacity_slider = QSlider(Qt.Horizontal)
            opacity_slider.setMinimum(0)
            opacity_slider.setMaximum(100)
            opacity_slider.setValue(int(layer_object.opacity*100))
            opacity_slider.setFixedWidth(100)
            opacity_slider.valueChanged.connect(lambda new_opacity_value, slider_index=layer_index: self.LayeredImageEditor_on_opacity_changed(slider_index, new_opacity_value))
            opacity_slider_widget_container = QWidget()
            opacity_slider_layout = QHBoxLayout()
            opacity_slider_layout.setContentsMargins(0,0,0,0)
            opacity_slider_layout.addWidget(opacity_slider)
            opacity_slider_widget_container.setLayout(opacity_slider_layout)
            self.LayerListWidget_layer_list.setItemWidget(self.LayerListWidget_layer_list.item(layer_index), opacity_slider_widget_container)

    def LayeredImageEditor_on_opacity_changed(self, layer_opacity_slider_index, new_opacity_value):
        if 0 <= layer_opacity_slider_index < len(self.LayeredImageEditor_project.get_all_layers()):
            self.LayeredImageEditor_project.get_all_layers()[layer_opacity_slider_index].opacity = new_opacity_value/100.0
            self.canvas.CanvasView_set_layers(self.LayeredImageEditor_project)

    def LayeredImageEditor_on_layer_checkbox_changed(self, LayeredImageEditor_layer_list_widget_item):
        LayeredImageEditor_layer_index = self.LayerListWidget_layer_list.row(LayeredImageEditor_layer_list_widget_item)
        if LayeredImageEditor_layer_index is not None and 0 <= LayeredImageEditor_layer_index < len(self.LayeredImageEditor_project.get_all_layers()):
            is_visible = (LayeredImageEditor_layer_list_widget_item.checkState() == Qt.Checked)
            self.LayeredImageEditor_project.get_all_layers()[LayeredImageEditor_layer_index].Layer_visible = is_visible
            self.canvas.CanvasView_set_layers(self.LayeredImageEditor_project)

    def LayeredImageEditor_on_layer_selected(self):
        self.debug_print_layer_stack('on_layer_selected')
        LayeredImageEditor_selected_layer_index = self.LayerListWidget_layer_list.currentRow()
        self.canvas.active_layer_idx = LayeredImageEditor_selected_layer_index
        self.LayeredImageEditor_update_properties_panel(LayeredImageEditor_selected_layer_index)

    def LayeredImageEditor_update_properties_panel(self, LayeredImageEditor_selected_layer_index):
        if LayeredImageEditor_selected_layer_index is None or LayeredImageEditor_selected_layer_index < 0 or LayeredImageEditor_selected_layer_index >= len(self.LayeredImageEditor_project.get_all_layers()):
            self.LayeredImageEditor_properties_panel.setEnabled(False)
            return
        self.LayeredImageEditor_properties_panel.setEnabled(True)
        LayeredImageEditor_selected_layer_object = self.LayeredImageEditor_project.get_all_layers()[LayeredImageEditor_selected_layer_index]
        self.LayeredImageEditor_properties_panel.prop_blend.blockSignals(True)
        self.LayeredImageEditor_properties_panel.prop_blend.setCurrentText(LayeredImageEditor_selected_layer_object.Layer_blend_mode)
        self.LayeredImageEditor_properties_panel.prop_blend.blockSignals(False)
        self.LayeredImageEditor_properties_panel.prop_opacity.blockSignals(True)
        self.LayeredImageEditor_properties_panel.prop_opacity.setValue(int(LayeredImageEditor_selected_layer_object.Layer_opacity*100))
        self.LayeredImageEditor_properties_panel.prop_opacity.blockSignals(False)
        self.LayeredImageEditor_properties_panel.prop_scale.blockSignals(True)
        self.LayeredImageEditor_properties_panel.prop_scale.setValue(LayeredImageEditor_selected_layer_object.Layer_scale)
        self.LayeredImageEditor_properties_panel.prop_scale.blockSignals(False)
        self.LayeredImageEditor_properties_panel.prop_offset_x.blockSignals(True)
        self.LayeredImageEditor_properties_panel.prop_offset_x.setValue(LayeredImageEditor_selected_layer_object.Layer_offset[0])
        self.LayeredImageEditor_properties_panel.prop_offset_x.blockSignals(False)
        self.LayeredImageEditor_properties_panel.prop_offset_y.blockSignals(True)
        self.LayeredImageEditor_properties_panel.prop_offset_y.setValue(LayeredImageEditor_selected_layer_object.Layer_offset[1])
        self.LayeredImageEditor_properties_panel.prop_offset_y.blockSignals(False)
        self.LayeredImageEditor_properties_panel.prop_rotation.blockSignals(True)
        self.LayeredImageEditor_properties_panel.prop_rotation.setValue(LayeredImageEditor_selected_layer_object.Layer_rotation)
        self.LayeredImageEditor_properties_panel.prop_rotation.blockSignals(False)

    def LayeredImageEditor_on_prop_blend_changed(self, LayeredImageEditor_new_blend_mode_value):
        self.debug_print_layer_stack('on_prop_blend_changed')
        LayeredImageEditor_selected_layer_index = self.LayerListWidget_layer_list.currentRow()
        if LayeredImageEditor_selected_layer_index is not None and 0 <= LayeredImageEditor_selected_layer_index < len(self.LayeredImageEditor_project.get_all_layers()):
            self.LayeredImageEditor_project.get_all_layers()[LayeredImageEditor_selected_layer_index].Layer_blend_mode = LayeredImageEditor_new_blend_mode_value
            self.canvas.CanvasView_update_canvas()

    def LayeredImageEditor_on_prop_opacity_changed(self, LayeredImageEditor_new_opacity_value):
        self.debug_print_layer_stack('on_prop_opacity_changed')
        LayeredImageEditor_selected_layer_index = self.LayerListWidget_layer_list.currentRow()
        if LayeredImageEditor_selected_layer_index is not None and 0 <= LayeredImageEditor_selected_layer_index < len(self.LayeredImageEditor_project.get_all_layers()):
            self.LayeredImageEditor_project.get_all_layers()[LayeredImageEditor_selected_layer_index].Layer_opacity = LayeredImageEditor_new_opacity_value/100.0
            self.canvas.CanvasView_update_canvas()

    def LayeredImageEditor_on_prop_scale_changed(self, LayeredImageEditor_new_scale_value):
        self.debug_print_layer_stack('on_prop_scale_changed')
        LayeredImageEditor_selected_layer_index = self.LayerListWidget_layer_list.currentRow()
        if LayeredImageEditor_selected_layer_index is not None and 0 <= LayeredImageEditor_selected_layer_index < len(self.LayeredImageEditor_project.get_all_layers()):
            self.LayeredImageEditor_project.get_all_layers()[LayeredImageEditor_selected_layer_index].Layer_scale = LayeredImageEditor_new_scale_value
            self.canvas.CanvasView_update_canvas()
            self.canvas.CanvasView_set_layers(self.LayeredImageEditor_project)

    def LayeredImageEditor_on_prop_offset_changed(self, LayeredImageEditor_new_offset_value):
        self.debug_print_layer_stack('on_prop_offset_changed')
        LayeredImageEditor_selected_layer_index = self.LayerListWidget_layer_list.currentRow()
        if LayeredImageEditor_selected_layer_index is not None and 0 <= LayeredImageEditor_selected_layer_index < len(self.LayeredImageEditor_project.get_all_layers()):
            layer = self.LayeredImageEditor_project.get_all_layers()[LayeredImageEditor_selected_layer_index]
            old_offset = getattr(layer, 'Layer_offset', None)
            new_offset = (
                self.LayeredImageEditor_properties_panel.prop_offset_x.value(),
                self.LayeredImageEditor_properties_panel.prop_offset_y.value()
            )
            print(f"[DEBUG][PROP] Updating offset for layer '{getattr(layer, 'Layer_name', '?')}' (idx {LayeredImageEditor_selected_layer_index}): {old_offset} -> {new_offset}")
            layer.Layer_offset = new_offset
            # Update canvas to reflect new offset visually
            self.canvas.CanvasView_set_layers(self.LayeredImageEditor_project)
            self.canvas.CanvasView_update_canvas()

    def LayeredImageEditor_on_prop_rotation_changed(self, LayeredImageEditor_new_rotation_value):
        self.debug_print_layer_stack('on_prop_rotation_changed')
        LayeredImageEditor_selected_layer_index = self.LayerListWidget_layer_list.currentRow()
        if LayeredImageEditor_selected_layer_index is not None and 0 <= LayeredImageEditor_selected_layer_index < len(self.LayeredImageEditor_project.get_all_layers()):
            self.LayeredImageEditor_project.get_all_layers()[LayeredImageEditor_selected_layer_index].rotation = LayeredImageEditor_new_rotation_value
            self.canvas.CanvasView_set_layers(self.LayeredImageEditor_project)

    def LayeredImageEditor_on_layers_reordered(self, model_parent, model_start_row, model_end_row, model_dest_parent, model_dest_row):
        self.debug_print_layer_stack('on_layers_reordered')
        # Reorder self.LayeredImageEditor_project.get_all_layers() to match QListWidget
        LayeredImageEditor_new_layers_list = []
        for LayeredImageEditor_layer_list_index in range(self.LayerListWidget_layer_list.count()):
            LayeredImageEditor_layer_list_widget_item = self.LayerListWidget_layer_list.item(LayeredImageEditor_layer_list_index)
            LayeredImageEditor_layer_name = LayeredImageEditor_layer_list_widget_item.text()
            # Find corresponding layer by name (should be unique for now)
            for LayeredImageEditor_layer_object in self.LayeredImageEditor_project.get_all_layers():
                if LayeredImageEditor_layer_object.name == LayeredImageEditor_layer_name:
                    LayeredImageEditor_new_layers_list.append(LayeredImageEditor_layer_object)
                    break
        if LayeredImageEditor_new_layers_list:
            self.LayeredImageEditor_project.LayeredImageProject_base_layer = LayeredImageEditor_new_layers_list[0]
            self.LayeredImageEditor_project.LayeredImageProject_other_layers = LayeredImageEditor_new_layers_list[1:]
        self.canvas.CanvasView_set_layers(self.LayeredImageEditor_project)

    def dragEnterEvent(self, event: QDragEnterEvent):
        # Accept drag if any file is an image
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        # Accept image drops anywhere on the main window
        LayeredImageEditor_image_file_extensions = ('.png', '.jpg', '.jpeg', '.bmp')
        LayeredImageEditor_dropped_image_paths = [url.toLocalFile() for url in event.mimeData().urls()]
        for LayeredImageEditor_image_path in LayeredImageEditor_dropped_image_paths:
            if not LayeredImageEditor_image_path.lower().endswith(LayeredImageEditor_image_file_extensions):
                continue
            LayeredImageEditor_qimage = QImage(LayeredImageEditor_image_path)
            if LayeredImageEditor_qimage.isNull():
                continue
            if len(self.LayeredImageEditor_project.get_all_layers()) == 0:
                self.LayeredImageEditor_add_image_layer(
                    LayeredImageEditor_qimage,
                    LayeredImageEditor_image_path,
                    image_layer_filepath=LayeredImageEditor_image_path
                )
            else:
                self.LayeredImageEditor_add_image_layer(
                    LayeredImageEditor_qimage,
                    LayeredImageEditor_image_path,
                    image_layer_filepath=LayeredImageEditor_image_path
                )
        event.acceptProposedAction()

    # Also enable drag/drop on right panel by forwarding events to main window
    def eventFilter(self, obj, event):
        if obj == self.LayeredImageEditor_right_panel:
            if event.type() == event.DragEnter:
                self.dragEnterEvent(event)
                return True
            elif event.type() == event.Drop:
                self.dropEvent(event)
                return True
        return super().eventFilter(obj, event)

class LayerToolbarPanel(QWidget):
    def __init__(self, parent_editor):
        super().__init__()

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        self.add_btn = QPushButton('Add Layer')
        self.add_btn.clicked.connect(parent_editor.LayeredImageEditor_add_layer_dialog)
        self.del_btn = QPushButton('Delete Layer')
        self.del_btn.clicked.connect(parent_editor.LayeredImageEditor_delete_layer)
        self.mask_btn = QPushButton('Paint Mask')
        self.mask_btn.clicked.connect(parent_editor.LayeredImageEditor_toggle_mask_paint)
        self.save_btn = QPushButton('Save Project')
        self.save_btn.clicked.connect(parent_editor.LayeredImageEditor_save_project)
        self.load_btn = QPushButton('Load Project')
        self.load_btn.clicked.connect(parent_editor.LayeredImageEditor_load_project)
        self.export_btn = QPushButton('Export Flattened PNG')
        self.export_btn.clicked.connect(parent_editor.LayeredImageEditor_export_flattened_image)
        self.snap_btn = QPushButton('Snap to Underlying Layer')
        self.snap_btn.clicked.connect(parent_editor.LayeredImageEditor_snap_to_underlying_layer)
        self.fit_btn = QPushButton('Fit Layer to Canvas')
        self.fit_btn.clicked.connect(parent_editor.LayeredImageEditor_fit_layer_to_canvas)
        self.diff_btn = QPushButton('Show Diff Mask')
        self.diff_btn.clicked.connect(parent_editor.LayeredImageEditor_show_diff_mask)
        btn_styles = {
            self.add_btn: 'background-color: #3fa46a; color: white; font-weight: bold; border: 2px outset #5fc98a; border-radius: 6px; padding: 4px; ',
            self.del_btn: 'background-color: #8c4fa3; color: white; font-weight: bold; border: 2px outset #b074d6; border-radius: 6px; padding: 4px; ',
            self.mask_btn: 'background-color: #8c4fa3; color: white; font-weight: bold; border: 2px outset #b074d6; border-radius: 6px; padding: 4px; ',
            self.save_btn: 'background-color: #3f6aa4; color: white; font-weight: bold; border: 2px outset #5a8ddb; border-radius: 6px; padding: 4px; ',
            self.load_btn: 'background-color: #3f6aa4; color: white; font-weight: bold; border: 2px outset #5a8ddb; border-radius: 6px; padding: 4px; ',
            self.export_btn: 'background-color: #3f6aa4; color: white; font-weight: bold; border: 2px outset #5a8ddb; border-radius: 6px; padding: 4px; ',
            self.snap_btn: 'background-color: #8c4fa3; color: white; font-weight: bold; border: 2px outset #b074d6; border-radius: 6px; padding: 4px; ',
            self.fit_btn: 'background-color: #3fa49c; color: white; font-weight: bold; border: 2px outset #5fc9ba; border-radius: 6px; padding: 4px; ',
            self.diff_btn: 'background-color: #b8a33e; color: white; font-weight: bold; border: 2px outset #e2d36a; border-radius: 6px; padding: 4px; '
        }
        for btn, style in btn_styles.items():
            btn.setStyleSheet(style)
            btn.setFixedWidth(160)
            btn_layout.addWidget(self.fit_btn)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        self.setLayout(btn_layout)
        self.setMaximumWidth(180)

class LayerPropertiesPanel(QWidget):
    def __init__(self, parent_editor):
        super().__init__()
        
        self.prop_blend = QComboBox()
        self.prop_blend.addItems(["Normal", "Multiply", "Darken", "Screen"])
        self.prop_opacity = QSlider(Qt.Horizontal)
        self.prop_opacity.setMinimum(0)
        self.prop_opacity.setMaximum(100)
        self.prop_opacity.setSingleStep(1)
        self.prop_scale = QDoubleSpinBox()
        self.prop_scale.setRange(0.01, 10.0)
        self.prop_scale.setSingleStep(0.01)
        self.prop_offset_x = QSpinBox()
        self.prop_offset_x.setRange(-10000, 10000)
        self.prop_offset_y = QSpinBox()
        self.prop_offset_y.setRange(-10000, 10000)
        self.prop_rotation = QDoubleSpinBox()
        self.prop_rotation.setRange(-360, 360)
        self.prop_rotation.setSingleStep(0.1)
        prop_layout = QFormLayout()
        prop_layout.setLabelAlignment(Qt.AlignRight)
        prop_layout.setFormAlignment(Qt.AlignTop)
        prop_layout.addRow(QLabel("Blend Mode:"), self.prop_blend)
        prop_layout.addRow(QLabel("Opacity:"), self.prop_opacity)
        prop_layout.addRow(QLabel("Scale:"), self.prop_scale)
        prop_layout.addRow(QLabel("Offset X:"), self.prop_offset_x)
        prop_layout.addRow(QLabel("Offset Y:"), self.prop_offset_y)
        prop_layout.addRow(QLabel("Rotation:"), self.prop_rotation)
        self.setLayout(prop_layout)
        self.setMaximumWidth(180)
        # Connect signals to parent's handlers
        self.prop_blend.currentTextChanged.connect(parent_editor.LayeredImageEditor_on_prop_blend_changed)
        self.prop_opacity.valueChanged.connect(parent_editor.LayeredImageEditor_on_prop_opacity_changed)
        self.prop_scale.valueChanged.connect(parent_editor.LayeredImageEditor_on_prop_scale_changed)
        self.prop_offset_x.valueChanged.connect(parent_editor.LayeredImageEditor_on_prop_offset_changed)
        self.prop_offset_y.valueChanged.connect(parent_editor.LayeredImageEditor_on_prop_offset_changed)
        self.prop_rotation.valueChanged.connect(parent_editor.LayeredImageEditor_on_prop_rotation_changed)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = LayeredImageEditor()
    win.show()
    sys.exit(app.exec_())
