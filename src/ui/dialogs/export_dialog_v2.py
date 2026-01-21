"""
Export Wizard v1.5
==================
Step-by-step export wizard - Dataset Split → Augmentation → Format
"""

from pathlib import Path
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QPushButton, QLabel, QComboBox, QLineEdit, QFileDialog,
    QProgressBar, QMessageBox, QButtonGroup, QWidget, QStackedWidget,
    QCheckBox, QSlider, QSpinBox, QScrollArea, QFrame, QSizePolicy,
    QFormLayout
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QRect
from PySide6.QtGui import QFont, QPixmap, QImage, QPainter, QColor, QPen

from core.class_manager import ClassManager
from core.annotation_manager import AnnotationManager
from core.exporter import (
    YOLOExporter, COCOExporter, CustomTXTExporter, CustomJSONExporter
)
from core.augmentor import (
    Augmentor, AugmentationConfig, ResizeConfig, ResizeMode
)
from core.dataset_splitter import DatasetSplitter, SplitConfig


class RangeSlider(QWidget):
    """Two-handle range slider - For Train/Val/Test split."""
    
    valuesChanged = Signal(int, int, int)  # train, val, test
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setMinimumWidth(300)
        
        self._min = 0
        self._max = 100
        self._handle1 = 70  # Train/Val border
        self._handle2 = 90  # Val/Test border
        
        self._dragging = None
        self._handle_width = 12
        
        self.setMouseTracking(True)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width() - self._handle_width
        h = self.height()
        bar_height = 20
        bar_y = (h - bar_height) // 2
        
        # Train region (green)
        x1 = self._handle_width // 2
        x2 = int(self._handle1 / 100 * w) + self._handle_width // 2
        painter.fillRect(QRect(x1, bar_y, x2 - x1, bar_height), QColor("#4CAF50"))
        
        # Val region (blue)
        x3 = int(self._handle2 / 100 * w) + self._handle_width // 2
        painter.fillRect(QRect(x2, bar_y, x3 - x2, bar_height), QColor("#2196F3"))
        
        # Test region (orange)
        x4 = w + self._handle_width // 2
        painter.fillRect(QRect(x3, bar_y, x4 - x3, bar_height), QColor("#FF9800"))
        
        # Handle 1
        painter.setPen(QPen(QColor("#333"), 2))
        painter.setBrush(QColor("white"))
        painter.drawEllipse(x2 - self._handle_width//2, bar_y - 5, 
                           self._handle_width, bar_height + 10)
        
        # Handle 2
        painter.drawEllipse(x3 - self._handle_width//2, bar_y - 5,
                           self._handle_width, bar_height + 10)
        
        # Labels
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        
        train_pct = self._handle1
        val_pct = self._handle2 - self._handle1
        test_pct = 100 - self._handle2
        
        # Train label
        if train_pct >= 15:
            painter.drawText(QRect(x1, bar_y, x2-x1, bar_height), 
                           Qt.AlignmentFlag.AlignCenter, f"Train {train_pct}%")
        
        # Val label
        if val_pct >= 10:
            painter.drawText(QRect(x2, bar_y, x3-x2, bar_height),
                           Qt.AlignmentFlag.AlignCenter, f"Val {val_pct}%")
        
        # Test label
        if test_pct >= 10:
            painter.drawText(QRect(x3, bar_y, x4-x3, bar_height),
                           Qt.AlignmentFlag.AlignCenter, f"Test {test_pct}%")
    
    def mousePressEvent(self, event):
        x = event.position().x()
        w = self.width() - self._handle_width
        
        h1_x = int(self._handle1 / 100 * w) + self._handle_width // 2
        h2_x = int(self._handle2 / 100 * w) + self._handle_width // 2
        
        if abs(x - h1_x) < self._handle_width:
            self._dragging = 1
        elif abs(x - h2_x) < self._handle_width:
            self._dragging = 2
    
    def mouseReleaseEvent(self, event):
        self._dragging = None
    
    def mouseMoveEvent(self, event):
        if self._dragging is None:
            return
        
        x = event.position().x()
        w = self.width() - self._handle_width
        value = int((x - self._handle_width // 2) / w * 100)
        value = max(0, min(100, value))  # 0-100 arası
        
        if self._dragging == 1:
            # Handle1: Train end, min 0, max handle2
            self._handle1 = min(value, self._handle2)
        elif self._dragging == 2:
            # Handle2: Val end, min handle1, max 100
            self._handle2 = max(value, self._handle1)
        
        self.update()
        self.valuesChanged.emit(self._handle1, 
                                 self._handle2 - self._handle1,
                                 100 - self._handle2)
    
    def values(self):
        """Returns (train%, val%, test%)."""
        return (self._handle1, 
                self._handle2 - self._handle1, 
                100 - self._handle2)
    
    def setValues(self, train, val, test=None):
        """Set values."""
        self._handle1 = train
        self._handle2 = train + val
        self.update()


class ExportWorkerV2(QThread):
    """Runs export process in background."""
    
    progress = Signal(int, int)
    finished = Signal(int)
    error = Signal(str)
    
    def __init__(self, exporter, annotations_dict, output_dir, image_files,
                 augmentation_config=None, split_config=None, export_format="yolo"):
        super().__init__()
        self.exporter = exporter
        self.annotations_dict = annotations_dict
        self.output_dir = output_dir
        self.image_files = image_files
        self.aug_config = augmentation_config
        self.split_config = split_config
        self.export_format = export_format  # "yolo", "coco", "voc"
        self.augmentor = Augmentor()
        self.splitter = DatasetSplitter()
    
    def run(self):
        try:
            from concurrent.futures import ThreadPoolExecutor
            import os
            
            output_dir = Path(self.output_dir)
            
            if self.split_config and self.split_config.enabled:
                self.splitter.set_seed(self.split_config.seed)
                splits = self.splitter.split(self.image_files, self.split_config)
            else:
                splits = {'': list(self.image_files)}
            
            total_files = sum(len(files) for files in splits.values())
            if self.aug_config and self.aug_config.enabled:
                total_files *= self.aug_config.multiplier
            
            self._current = 0
            self._exported_count = 0
            self._lock = __import__('threading').Lock()
            
            # Annotation collector for COCO
            if self.export_format == "coco":
                self._coco_data = {}  # split_name -> COCO dict
            
            # Collect all tasks
            tasks = []
            for split_name, files in splits.items():
                if split_name:
                    split_dir = output_dir / split_name
                    images_dir = split_dir / "images"
                    labels_dir = split_dir / "labels"
                else:
                    images_dir = output_dir / "images"
                    labels_dir = output_dir / "labels"
                
                images_dir.mkdir(parents=True, exist_ok=True)
                if self.export_format != "coco":
                    labels_dir.mkdir(parents=True, exist_ok=True)
                
                # Create data structure per split for COCO
                if self.export_format == "coco":
                    self._coco_data[split_name] = {
                        "images": [],
                        "annotations": [],
                        "categories": [
                            {"id": cls.id + 1, "name": cls.name, "supercategory": "none"}  # COCO IDs start from 1
                            for cls in self.exporter.class_manager.classes
                        ]
                    }
                
                for image_path in files:
                    tasks.append((image_path, images_dir, labels_dir, total_files, split_name))
            
            # Parallel processing
            max_workers = min(os.cpu_count() or 4, 8)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(self._process_image, tasks)
            
            # Save COCO JSON files
            if self.export_format == "coco":
                self._save_coco_json(output_dir, splits)
            
            self._save_classes_txt(output_dir)
            self.finished.emit(self._exported_count)
            
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")
    
    def _process_image(self, task):
        """Process a single image (thread-safe)."""
        image_path, images_dir, labels_dir, total_files, split_name = task
        
        try:
            img = self._read_image(str(image_path))
            if img is None:
                return
            
            key = str(image_path)
            annotations = self.annotations_dict.get(key)
            
            if self.aug_config and self.aug_config.enabled:
                augmentations = self.augmentor.generate_augmentations(img, self.aug_config)
            else:
                augmentations = [(img, {})]
            
            orig_ext = image_path.suffix.lower()
            if orig_ext not in ['.jpg', '.jpeg', '.png']:
                orig_ext = '.jpg'
            
            for aug_idx, (aug_img, transform) in enumerate(augmentations):
                if self.aug_config and self.aug_config.resize.enabled:
                    aug_img, resize_info = self.augmentor.resize_image(aug_img, self.aug_config.resize)
                else:
                    resize_info = {}
                
                # Roboflow style naming
                orig_filename = image_path.name  # e.g: asd9.jpg
                if aug_idx == 0:
                    # Original image - keep name as is
                    new_name = image_path.stem
                else:
                    # Augmented image - generate unique ID
                    unique_id = self._generate_unique_id(orig_filename, aug_idx, transform)
                    new_name = f"{orig_filename}.rf.{unique_id}"
                
                out_img_path = images_dir / f"{new_name}.jpg"
                self._write_image(str(out_img_path), aug_img)
                
                if annotations:
                    if self.export_format == "voc":
                        self._save_voc_xml(
                            annotations, transform, resize_info,
                            labels_dir / f"{new_name}.xml",
                            out_img_path.name,
                            img.shape[1], img.shape[0],
                            aug_img.shape[1], aug_img.shape[0]
                        )
                    elif self.export_format == "coco":
                        self._add_coco_annotation(
                            annotations, transform, resize_info,
                            split_name, f"{new_name}.jpg",
                            img.shape[1], img.shape[0],
                            aug_img.shape[1], aug_img.shape[0]
                        )
                    else:  # yolo
                        self._save_transformed_labels(
                            annotations, transform, resize_info,
                            labels_dir / f"{new_name}.txt",
                            img.shape[1], img.shape[0],
                            aug_img.shape[1], aug_img.shape[0]
                        )
                else:
                    if self.export_format == "coco":
                        # Add empty image entry for COCO
                        self._add_coco_annotation(
                            None, transform, resize_info,
                            split_name, f"{new_name}.jpg",
                            img.shape[1], img.shape[0],
                            aug_img.shape[1], aug_img.shape[0]
                        )
                    elif self.export_format == "voc":
                        pass  # No need to generate XML for empty annotation
                    else:
                        (labels_dir / f"{new_name}.txt").touch()
                
                with self._lock:
                    self._exported_count += 1
                    self._current += 1
                    self.progress.emit(self._current, total_files)
        except Exception as e:
            import traceback
            print(f"Export error: {e}\n{traceback.format_exc()}")
    
    def _add_coco_annotation(self, annotations, transform, resize_info,
                              split_name, image_filename, orig_w, orig_h, new_w, new_h):
        """Add annotation in COCO format (thread-safe)."""
        with self._lock:
            coco_data = self._coco_data[split_name]
            
            # Image ID (based on current image count)
            image_id = len(coco_data["images"]) + 1
            
            # Add image entry
            coco_data["images"].append({
                "id": image_id,
                "file_name": image_filename,
                "width": new_w,
                "height": new_h
            })
            
            if annotations is None:
                return
            
            # Get cutout regions (if any)
            cutout_regions = []
            if transform and "cutout" in transform:
                cutout_regions = transform["cutout"].get("regions", [])
            
            # Annotation ID (based on current annotation count)
            ann_id = len(coco_data["annotations"]) + 1
            
            # Add BBoxes
            for bbox in annotations.bboxes:
                coords = (bbox.x_center, bbox.y_center, bbox.width, bbox.height)
                
                # Cutout check (skip if covered 90%+)
                if cutout_regions:
                    if self.augmentor.is_bbox_covered_by_cutout(coords, cutout_regions, orig_w, orig_h, 0.9):
                        continue
                
                if transform:
                    coords = self.augmentor.transform_bbox(coords, transform, orig_w, orig_h)
                
                # Resize and Duplicate check
                if resize_info:
                    final_bboxes = self.augmentor.get_resize_duplicates_bbox(
                        coords, resize_info, orig_w, orig_h, new_w, new_h)
                else:
                    final_bboxes = [coords]
                
                for final_bbox in final_bboxes:
                    x_c, y_c, w, h = final_bbox
                    # YOLO format from COCO format (x, y, width, height - top-left corner)
                    x = (x_c - w/2) * new_w
                    y = (y_c - h/2) * new_h
                    width = w * new_w
                    height = h * new_h
                    
                    coco_data["annotations"].append({
                        "id": ann_id,
                        "image_id": image_id,
                        "category_id": bbox.class_id + 1,  # COCO categories start from 1
                        "bbox": [round(x, 2), round(y, 2), round(width, 2), round(height, 2)],
                        "area": round(width * height, 2),
                        "segmentation": [],  # Empty segmentation for BBox
                        "iscrowd": 0
                    })
                    ann_id += 1
            
            # Add Polygons (as segmentation)
            for polygon in annotations.polygons:
                if len(polygon.points) < 3:
                    continue
                
                points = polygon.points
                
                # Cutout clipping: Remove cutout regions from Polygon
                if cutout_regions:
                    clipped_polygons = self.augmentor.apply_cutout_to_polygon(
                        points, cutout_regions, orig_w, orig_h
                    )
                else:
                    clipped_polygons = [points]
                
                # Add separate annotation for each clipped polygon
                for clipped_points in clipped_polygons:
                    if len(clipped_points) < 3:
                        continue
                    
                    final_points_list = [clipped_points]
                    
                    if transform:
                        # Apply transform
                        new_points = self.augmentor.transform_polygon(clipped_points, transform, orig_w, orig_h)
                        final_points_list = [new_points]
                    
                    # Get resize and duplicates
                    processed_polygons = []
                    for pts in final_points_list:
                        if resize_info:
                            dups = self.augmentor.get_resize_duplicates_polygon(
                                pts, resize_info, orig_w, orig_h, new_w, new_h
                            )
                            processed_polygons.extend(dups)
                        else:
                            processed_polygons.append(pts)
                            
                    for poly_pts in processed_polygons:
                        # Flattened coordinate list for segmentation [x1, y1, x2, y2, ...]
                        seg_points = []
                        min_x = float('inf')
                        min_y = float('inf')
                        max_x = float('-inf')
                        max_y = float('-inf')
                        
                        for px, py in poly_pts:
                            px_abs = px * new_w
                            py_abs = py * new_h
                            
                            seg_points.extend([round(px_abs, 2), round(py_abs, 2)])
                            min_x = min(min_x, px_abs)
                            min_y = min(min_y, py_abs)
                            max_x = max(max_x, px_abs)
                            max_y = max(max_y, py_abs)
                    
                    # Calculate bounding box (from polygon)
                    bbox_x = min_x
                    bbox_y = min_y
                    bbox_w = max_x - min_x
                    bbox_h = max_y - min_y
                    
                    # Calculate area (shoelace formula)
                    area = 0.0
                    n = len(poly_pts)
                    for i in range(n):
                        j = (i + 1) % n
                        x1, y1 = poly_pts[i]
                        x2, y2 = poly_pts[j]
                        area += (x1 * new_w) * (y2 * new_h)
                        area -= (x2 * new_w) * (y1 * new_h)
                    area = abs(area) / 2.0
                    
                    coco_data["annotations"].append({
                        "id": ann_id,
                        "image_id": image_id,
                        "category_id": polygon.class_id + 1,  # COCO categories start from 1
                        "bbox": [round(bbox_x, 2), round(bbox_y, 2), round(bbox_w, 2), round(bbox_h, 2)],
                        "area": round(area, 2),
                        "segmentation": [seg_points],  # Polygon points
                        "iscrowd": 0
                    })
                    ann_id += 1
    
    def _save_coco_json(self, output_dir: Path, splits: dict):
        """Save COCO JSON files."""
        import json
        
        for split_name, coco_data in self._coco_data.items():
            if split_name:
                json_path = output_dir / split_name / "annotations.json"
            else:
                json_path = output_dir / "annotations.json"
            
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(coco_data, f, indent=2, ensure_ascii=False)
    
    def _save_transformed_labels(self, annotations, transform, resize_info,
                                   output_path, orig_w, orig_h, new_w, new_h):
        lines = []
        
        # Get cutout regions (if any)
        cutout_regions = []
        if transform and "cutout" in transform:
            cutout_regions = transform["cutout"].get("regions", [])
        
        for bbox in annotations.bboxes:
            coords = (bbox.x_center, bbox.y_center, bbox.width, bbox.height)
            
            # Cutout check (skip if covered 90%+)
            if cutout_regions:
                if self.augmentor.is_bbox_covered_by_cutout(coords, cutout_regions, orig_w, orig_h, 0.9):
                    continue  # Don't save this bbox
            
            if transform:
                coords = self.augmentor.transform_bbox(coords, transform, orig_w, orig_h)
            
            # Resize and Duplicate check
            if resize_info:
                final_bboxes = self.augmentor.get_resize_duplicates_bbox(
                    coords, resize_info, orig_w, orig_h, new_w, new_h)
            else:
                final_bboxes = [coords]
            
            for final_bbox in final_bboxes:
                x_c, y_c, w, h = final_bbox
                lines.append(f"{bbox.class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}")
        
        for polygon in annotations.polygons:
            if len(polygon.points) >= 3:
                points = polygon.points
                
                # Cutout clipping: Remove cutout regions from Polygon
                if cutout_regions:
                    clipped_polygons = self.augmentor.apply_cutout_to_polygon(
                        points, cutout_regions, orig_w, orig_h
                    )
                    
                    # Clipping result can be multiple polygons
                    for clipped_points in clipped_polygons:
                        if len(clipped_points) >= 3:
                            final_points_list = [clipped_points]
                            if transform:
                                final_points_list = [self.augmentor.transform_polygon(clipped_points, transform, orig_w, orig_h)]
                            
                            processed_polygons = []
                            for pts in final_points_list:
                                if resize_info:
                                    dups = self.augmentor.get_resize_duplicates_polygon(
                                        pts, resize_info, orig_w, orig_h, new_w, new_h
                                    )
                                    processed_polygons.extend(dups)
                                else:
                                    processed_polygons.append(pts)
                            
                            for pts in processed_polygons:
                                points_str = " ".join(f"{x:.6f} {y:.6f}" for x, y in pts)
                                lines.append(f"{polygon.class_id} {points_str}")
                else:
                    # Process normally if no cutout
                    points_list = [points]
                    if transform:
                        points_list = [self.augmentor.transform_polygon(points, transform, orig_w, orig_h)]
                    
                    processed_polygons = []
                    for pts in points_list:
                         if resize_info:
                             dups = self.augmentor.get_resize_duplicates_polygon(
                                 pts, resize_info, orig_w, orig_h, new_w, new_h
                             )
                             processed_polygons.extend(dups)
                         else:
                             processed_polygons.append(pts)

                    for pts in processed_polygons:
                        points_str = " ".join(f"{x:.6f} {y:.6f}" for x, y in pts)
                        lines.append(f"{polygon.class_id} {points_str}")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def _save_voc_xml(self, annotations, transform, resize_info,
                      output_path, image_filename, orig_w, orig_h, new_w, new_h):
        """Save label in Pascal VOC XML format."""
        from xml.etree.ElementTree import Element, SubElement, tostring
        from xml.dom import minidom
        
        output_path = Path(output_path)  # Path tipine dönüştür
        
        # Root element
        annotation = Element('annotation')
        
        # Folder and filename
        SubElement(annotation, 'folder').text = 'images'
        SubElement(annotation, 'filename').text = image_filename
        SubElement(annotation, 'path').text = image_filename  # Simple path
        
        # Source
        source = SubElement(annotation, 'source')
        SubElement(source, 'database').text = 'LocalTagger'
        
        # Size
        size = SubElement(annotation, 'size')
        SubElement(size, 'width').text = str(new_w)
        SubElement(size, 'height').text = str(new_h)
        SubElement(size, 'depth').text = '3'
        
        SubElement(annotation, 'segmented').text = '0'
        
        # Class name mapping
        class_names = {cls.id: cls.name for cls in self.exporter.class_manager.classes}
        
        # Objects (bboxes)
        for bbox in annotations.bboxes:
            coords = (bbox.x_center, bbox.y_center, bbox.width, bbox.height)
            if transform:
                coords = self.augmentor.transform_bbox(coords, transform, orig_w, orig_h)
            
            # Resize and Duplicate check
            if resize_info:
                final_bboxes = self.augmentor.get_resize_duplicates_bbox(
                    coords, resize_info, orig_w, orig_h, new_w, new_h)
            else:
                final_bboxes = [coords]
            
            for final_bbox in final_bboxes:
                x_c, y_c, w, h = final_bbox
                # YOLO format to VOC format (xmin, ymin, xmax, ymax)
                xmin = int((x_c - w/2) * new_w)
                ymin = int((y_c - h/2) * new_h)
                xmax = int((x_c + w/2) * new_w)
                ymax = int((y_c + h/2) * new_h)
                
                # Check boundaries
                xmin = max(0, min(new_w, xmin))
                xmax = max(0, min(new_w, xmax))
                ymin = max(0, min(new_h, ymin))
                ymax = max(0, min(new_h, ymax))
                
                obj = SubElement(annotation, 'object')
                SubElement(obj, 'name').text = class_names.get(bbox.class_id, f'class_{bbox.class_id}')
                SubElement(obj, 'pose').text = 'Unspecified'
                SubElement(obj, 'truncated').text = '0'
                SubElement(obj, 'difficult').text = '0'
                
                bndbox = SubElement(obj, 'bndbox')
                SubElement(bndbox, 'xmin').text = str(xmin)
                SubElement(bndbox, 'ymin').text = str(ymin)
                SubElement(bndbox, 'xmax').text = str(xmax)
                SubElement(bndbox, 'ymax').text = str(ymax)
        
        # Pretty print XML
        xml_str = minidom.parseString(tostring(annotation)).toprettyxml(indent="  ")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)
    
    def _save_classes_txt(self, output_dir: Path):
        classes_path = output_dir / "classes.txt"
        lines = [cls.name for cls in self.exporter.class_manager.classes]
        with open(classes_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        for split_name in ['train', 'val', 'test']:
            split_dir = output_dir / split_name
            if split_dir.exists():
                with open(split_dir / "classes.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
    
    def _generate_unique_id(self, orig_filename: str, aug_idx: int, transform: dict) -> str:
        """Generate Roboflow-style deterministic unique ID."""
        import hashlib
        
        # Convert transform to string (sorted and deterministic)
        transform_parts = []
        for key in sorted(transform.keys()):
            val = transform[key]
            if isinstance(val, dict):
                val_str = "_".join(f"{k}{v}" for k, v in sorted(val.items()))
            elif isinstance(val, float):
                val_str = f"{val:.4f}"
            else:
                val_str = str(val)
            transform_parts.append(f"{key}{val_str}")
        
        # Create hash: filename + aug_idx + transform
        hash_input = f"{orig_filename}_{aug_idx}_{'_'.join(transform_parts)}"
        hash_bytes = hashlib.md5(hash_input.encode()).hexdigest()
        
        # Take first 6 chars (Roboflow style short ID)
        return hash_bytes[:6]
    
    def _read_image(self, path: str) -> np.ndarray:
        """Read image with Turkish character support."""
        try:
            # Direct binary read (avoids Turkish character issue)
            with open(path, 'rb') as f:
                data = np.frombuffer(f.read(), np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            return None
    
    def _write_image(self, path: str, img: np.ndarray) -> bool:
        """Write image with Turkish character support."""
        try:
            # Try normal cv2.imwrite first
            success = cv2.imwrite(path, img)
            if success:
                return True
            
            # If Turkish character issue, write binary
            ext = Path(path).suffix.lower()
            if ext in ['.jpg', '.jpeg']:
                encode_param = [cv2.IMWRITE_JPEG_QUALITY, 95]
                _, data = cv2.imencode('.jpg', img, encode_param)
            else:
                _, data = cv2.imencode(ext, img)
            
            with open(path, 'wb') as f:
                f.write(data.tobytes())
            return True
        except Exception:
            return False


class AugmentationSlider(QWidget):
    """Slider widget for augmentation parameter."""
    
    valueChanged = Signal()
    
    def __init__(self, name: str, min_val: int, max_val: int, default_val: int, 
                 suffix: str = "", help_text: str = "", parent=None):
        super().__init__(parent)
        self.name = name
        self.suffix = suffix
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        
        self.checkbox = QCheckBox(name)
        self.checkbox.setMinimumWidth(130)
        layout.addWidget(self.checkbox)
        
        # Help icon (with tooltip)
        if help_text:
            self.help_label = QLabel("?")
            self.help_label.setFixedSize(18, 18)
            self.help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.help_label.setStyleSheet("""
                QLabel {
                    background-color: #555;
                    color: white;
                    border-radius: 9px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QLabel:hover {
                    background-color: #0078d4;
                }
            """)
            self.help_label.setToolTip(help_text)
            self.help_label.setCursor(Qt.CursorShape.WhatsThisCursor)
            layout.addWidget(self.help_label)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(default_val)
        self.slider.setEnabled(False)
        layout.addWidget(self.slider, 1)
        
        self.value_label = QLabel(f"{default_val}{suffix}")
        self.value_label.setMinimumWidth(60)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.value_label)
        
        self.default_btn = QPushButton("↺")
        self.default_btn.setFixedWidth(30)
        self.default_btn.setToolTip(f"Önerilen: {default_val}{suffix}")
        self.default_btn.setEnabled(False)
        layout.addWidget(self.default_btn)
        
        self._default = default_val
        
        self.checkbox.toggled.connect(self._on_toggle)
        self.slider.valueChanged.connect(self._on_value_changed)
        self.default_btn.clicked.connect(self._reset_to_default)
    
    def _on_toggle(self, checked):
        self.slider.setEnabled(checked)
        self.default_btn.setEnabled(checked)
        self.valueChanged.emit()
    
    def _on_value_changed(self, value):
        self.value_label.setText(f"{value}{self.suffix}")
        self.valueChanged.emit()
    
    def _reset_to_default(self):
        self.slider.setValue(self._default)
    
    def is_enabled(self) -> bool:
        return self.checkbox.isChecked()
    
    def value(self) -> int:
        return self.slider.value()


class ExportWizard(QDialog):
    """
    Step-by-step export wizard.
    Step 1: Dataset Split
    Step 2: Augmentation
    Step 3: Format & Export
    """
    
    def __init__(self, class_manager: ClassManager, annotation_manager: AnnotationManager,
                 image_files: list, default_output_dir: Path = None, parent=None):
        super().__init__(parent)
        self._class_manager = class_manager
        self._annotation_manager = annotation_manager
        self._image_files = image_files
        self._default_output_dir = default_output_dir
        
        self._worker = None
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)
        
        self._augmentor = Augmentor()
        self._preview_image = None
        self._last_brightness_effect = None  # Last selected brightness effect: 'brighten' or 'darken'
        
        self.setWindowTitle(self.tr("Export Wizard"))
        self.setMinimumWidth(800)
        self.setMinimumHeight(620)
        
        self._setup_ui()
        self._connect_signals()
        self._load_preview_image()
        self._update_navigation()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header = QHBoxLayout()
        self.step_label = QLabel(self.tr("Step 1/3: Dataset Split"))
        self.step_label.setFont(QFont("", 14, QFont.Weight.Bold))
        header.addWidget(self.step_label)
        header.addStretch()
        layout.addLayout(header)
        
        # Stacked widget
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        
        self.stack.addWidget(self._create_split_page())
        self.stack.addWidget(self._create_augmentation_page())
        self.stack.addWidget(self._create_format_page())
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        # Navigation
        nav_layout = QHBoxLayout()
        
        self.back_btn = QPushButton(self.tr("← Back"))
        self.back_btn.setStyleSheet("padding: 10px 25px;")
        nav_layout.addWidget(self.back_btn)
        
        nav_layout.addStretch()
        
        self.cancel_btn = QPushButton(self.tr("Cancel"))
        self.cancel_btn.setStyleSheet("padding: 10px 20px;")
        nav_layout.addWidget(self.cancel_btn)
        
        self.next_btn = QPushButton(self.tr("Next →"))
        self.next_btn.setStyleSheet("padding: 10px 25px; background-color: #0d6efd; color: white;")
        nav_layout.addWidget(self.next_btn)
        
        layout.addLayout(nav_layout)
    
    def _create_split_page(self) -> QWidget:
        """Step 1: Dataset Split."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        info = QLabel(self.tr("📊 Total {} images").format(len(self._image_files)))
        info.setStyleSheet("font-size: 14px; color: #2196F3; padding: 10px;")
        layout.addWidget(info)
        
        self.split_enabled = QCheckBox(self.tr("Enable Dataset Split"))
        self.split_enabled.setChecked(True)
        self.split_enabled.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(self.split_enabled)
        
        # Range slider
        self.split_group = QGroupBox(self.tr("Split Ratios (drag to adjust)"))
        split_layout = QVBoxLayout(self.split_group)
        
        self.range_slider = RangeSlider()
        split_layout.addWidget(self.range_slider)
        
        # Summary label
        self.split_info = QLabel("Train: 70% | Validation: 20% | Test: 10%")
        self.split_info.setStyleSheet("font-size: 12px; color: #666; padding: 5px;")
        self.split_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        split_layout.addWidget(self.split_info)
        
        self.split_group.setEnabled(True)  # Active by default
        layout.addWidget(self.split_group)
        
        # Shuffle & Seed
        self.shuffle_group = QGroupBox(self.tr("Shuffle Settings"))
        shuffle_layout = QVBoxLayout(self.shuffle_group)
        
        self.shuffle_check = QCheckBox(self.tr("Shuffle Data"))
        self.shuffle_check.setChecked(True)
        shuffle_layout.addWidget(self.shuffle_check)
        
        seed_layout = QHBoxLayout()
        seed_layout.addWidget(QLabel("Seed:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        seed_layout.addWidget(self.seed_spin)
        seed_layout.addStretch()
        shuffle_layout.addLayout(seed_layout)
        
        self.shuffle_group.setEnabled(True)  # Active by default
        layout.addWidget(self.shuffle_group)
        
        # Unlabeled files option
        self.unlabeled_group = QGroupBox(self.tr("Unlabeled Files"))
        unlabeled_layout = QVBoxLayout(self.unlabeled_group)
        
        self.include_unlabeled = QCheckBox(self.tr("Include unlabeled images"))
        self.include_unlabeled.setChecked(False)
        self.include_unlabeled.setToolTip(self.tr("If disabled, only labeled files will be exported"))
        self.include_unlabeled.toggled.connect(self._on_unlabeled_toggled)
        unlabeled_layout.addWidget(self.include_unlabeled)
        
        # Show unlabeled file count
        unlabeled_count = self._count_unlabeled_files()
        labeled_count = len(self._image_files) - unlabeled_count
        self.unlabeled_info = QLabel(self.tr("📊 {} labeled, {} unlabeled files").format(labeled_count, unlabeled_count))
        self.unlabeled_info.setStyleSheet("color: #666; font-size: 11px; margin-left: 20px;")
        unlabeled_layout.addWidget(self.unlabeled_info)
        
        layout.addWidget(self.unlabeled_group)
        
        # Image count summary
        self.split_summary = QLabel()
        self.split_summary.setStyleSheet("color: #888; padding: 10px; font-size: 12px;")
        layout.addWidget(self.split_summary)
        self._update_split_summary()
        
        layout.addStretch()
        return page
    
    def _create_augmentation_page(self) -> QWidget:
        """Step 2: Augmentation."""
        page = QWidget()
        main_layout = QHBoxLayout(page)
        
        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        self.aug_enabled = QCheckBox(self.tr("Enable Augmentation"))
        self.aug_enabled.setStyleSheet("font-size: 13px; padding: 5px;")
        left_layout.addWidget(self.aug_enabled)
        
        mult_layout = QHBoxLayout()
        mult_layout.addWidget(QLabel(self.tr("Multiplier:")))
        self.aug_multiplier = QComboBox()
        self._update_multiplier_options()
        mult_layout.addWidget(self.aug_multiplier)
        mult_layout.addStretch()
        left_layout.addLayout(mult_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        
        # Resize
        resize_group = QGroupBox(self.tr("Resize"))
        resize_layout = QVBoxLayout(resize_group)
        
        self.resize_enabled = QCheckBox(self.tr("Enable Resize"))
        resize_layout.addWidget(self.resize_enabled)
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel(self.tr("Size:")))
        self.resize_width = QSpinBox()
        self.resize_width.setRange(32, 4096)
        self.resize_width.setValue(640)
        size_layout.addWidget(self.resize_width)
        size_layout.addWidget(QLabel("x"))
        self.resize_height = QSpinBox()
        self.resize_height.setRange(32, 4096)
        self.resize_height.setValue(640)
        size_layout.addWidget(self.resize_height)
        size_layout.addStretch()
        resize_layout.addLayout(size_layout)
        
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel(self.tr("Mode:")))
        self.resize_mode = QComboBox()
        self.resize_mode.addItems([
            "Stretch to", "Fit within",
            "Fit (reflect edges)", "Fit (black edges)", "Fit (white edges)"
        ])
        mode_layout.addWidget(self.resize_mode)
        resize_layout.addLayout(mode_layout)
        settings_layout.addWidget(resize_group)
        
        # Augmentation sliders
        aug_group = QGroupBox(self.tr("Augmentation Parameters"))
        aug_layout = QVBoxLayout(aug_group)
        
        # Brightness - Roboflow style Brighten/Darken checkboxes
        brightness_group = QGroupBox(self.tr("Brightness"))
        brightness_group.setToolTip(
            self.tr("Brightness: Adjusts the light/dark level of the image.\n\n"
            "• Brighten: Lightens the image\n"
            "• Darken: Darkens the image\n"
            "• Value %: Effect intensity\n\n"
            "Used for generalization under different lighting conditions.")
        )
        brightness_layout = QVBoxLayout(brightness_group)
        
        # Slider (0-99%)
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel(self.tr("Value:")))
        self.brightness_slider_value = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider_value.setRange(0, 99)
        self.brightness_slider_value.setValue(20)
        slider_layout.addWidget(self.brightness_slider_value, 1)
        self.brightness_value_label = QLabel("20%")
        self.brightness_value_label.setMinimumWidth(40)
        slider_layout.addWidget(self.brightness_value_label)
        brightness_layout.addLayout(slider_layout)
        
        # Checkboxes
        checkbox_layout = QHBoxLayout()
        self.brighten_checkbox = QCheckBox(self.tr("Brighten"))
        self.darken_checkbox = QCheckBox(self.tr("Darken"))
        checkbox_layout.addWidget(self.brighten_checkbox)
        checkbox_layout.addWidget(self.darken_checkbox)
        checkbox_layout.addStretch()
        brightness_layout.addLayout(checkbox_layout)
        
        aug_layout.addWidget(brightness_group)
        
        self.contrast_slider = AugmentationSlider(
            self.tr("Contrast"), 50, 150, 120, "%",
            help_text=self.tr("Contrast: Adjusts the difference between light and dark tones.\n\n"
                      "• 100%: Original contrast\n"
                      "• <100%: Low contrast (more faded)\n"
                      "• >100%: High contrast (sharper)\n\n"
                      "Used for generalization under different lighting conditions.")
        )
        aug_layout.addWidget(self.contrast_slider)
        
        self.rotation_slider = AugmentationSlider(
            self.tr("Rotation"), 0, 45, 15, "°",
            help_text=self.tr("Rotation: Rotates the image at random angles.\n\n"
                      "• 0°: No rotation\n"
                      "• 15°: Rotation in ±15° range\n"
                      "• 45°: Rotation in ±45° range\n\n"
                      "Teaches recognition of objects from different angles.")
        )
        aug_layout.addWidget(self.rotation_slider)
        
        # Flip
        flip_group = QGroupBox(self.tr("Flip"))
        flip_group.setToolTip(
            self.tr("Flip: Mirrors the image.\n\n"
            "• Horizontal: Left-right mirroring\n"
            "• Vertical: Top-bottom mirroring\n"
            "• Percentage: Application probability\n\n"
            "Provides generalization for symmetric objects and different viewing angles.")
        )
        flip_group.setCheckable(True)
        flip_group.setChecked(False)
        flip_layout = QFormLayout(flip_group)
        
        self.flip_enabled = flip_group
        
        self.hflip_percent_spin = QSpinBox()
        self.hflip_percent_spin.setRange(0, 100)
        self.hflip_percent_spin.setValue(50)
        self.hflip_percent_spin.setSuffix("%")
        flip_layout.addRow(self.tr("Horizontal:"), self.hflip_percent_spin)
        
        self.vflip_percent_spin = QSpinBox()
        self.vflip_percent_spin.setRange(0, 100)
        self.vflip_percent_spin.setValue(50)
        self.vflip_percent_spin.setSuffix("%")
        flip_layout.addRow(self.tr("Vertical:"), self.vflip_percent_spin)
        
        aug_layout.addWidget(flip_group)
        
        self.blur_slider = AugmentationSlider(
            self.tr("Blur"), 0, 50, 15, "",
            help_text=self.tr("Blur: Adds Gaussian blur to the image.\n\n"
                      "Unit: Kernel size (pixels)\n\n"
                      "Teaches handling of out-of-focus or moving objects.")
        )
        aug_layout.addWidget(self.blur_slider)
        
        self.noise_slider = AugmentationSlider(
            self.tr("Noise"), 0, 50, 10, "",
            help_text=self.tr("Noise: Adds random pixel noise to the image.\n\n"
                      "Unit: Standard deviation (sigma)\n"
                      "Random values of ±sigma are added to pixel values.\n\n"
                      "For generalization with low quality or noisy camera sensors.")
        )
        aug_layout.addWidget(self.noise_slider)
        
        self.hue_slider = AugmentationSlider(
            self.tr("Hue"), -30, 30, 10, "°",
            help_text=self.tr("Hue: Shifts colors in the color spectrum.\n\n"
                      "Adapts to different lighting color temperatures.")
        )
        aug_layout.addWidget(self.hue_slider)
        
        # Grayscale (with percentage control)
        grayscale_group = QGroupBox(self.tr("Grayscale"))
        grayscale_group.setToolTip(
            self.tr("Grayscale: Converts the image to black and white.\n\n"
            "• Rate %: Percentage of images to convert to grayscale\n\n"
            "Teaches object recognition without color information.")
        )
        grayscale_group.setCheckable(True)
        grayscale_group.setChecked(False)
        grayscale_layout = QFormLayout(grayscale_group)
        
        self.grayscale_enabled = grayscale_group
        
        self.grayscale_percent_spin = QSpinBox()
        self.grayscale_percent_spin.setRange(0, 100)
        self.grayscale_percent_spin.setValue(15)
        self.grayscale_percent_spin.setSuffix("%")
        grayscale_layout.addRow(self.tr("Rate:"), self.grayscale_percent_spin)
        
        aug_layout.addWidget(grayscale_group)
        
        # NEW: Exposure
        self.exposure_slider = AugmentationSlider(
            self.tr("Exposure"), 50, 200, 150, "%",
            help_text=self.tr("Exposure (Gamma): Adjusts light exposure.\n\n"
                      "• 100%: Original\n"
                      "• <100%: Underexposed (darker)\n"
                      "• >100%: Overexposed (brighter)\n\n"
                      "Unlike brightness, preserves color tones.")
        )
        aug_layout.addWidget(self.exposure_slider)
        
        # NEW: Cutout - Single checkbox, size, count and application percentage
        cutout_group = QGroupBox(self.tr("Cutout"))
        cutout_group.setToolTip(
            self.tr("Cutout: Adds random black squares to the image.\n\n"
            "Unit: Percentage of image size\n"
            "• Size 10% = 64px square on 640px image\n\n"
            "• Count: Number of squares to add\n"
            "• Rate %: Application probability\n\n"
            "Teaches the model to work with missing information (occlusion robustness).\n\n"
            "⚠ WARNING: Some modern models like YOLOv8 may automatically apply\n"
            "similar techniques (e.g., erasing) during training.\n"
            "Applying this both here and during training (double application)\n"
            "may negatively affect model performance.")
        )
        cutout_group.setCheckable(True)
        cutout_group.setChecked(False)
        cutout_layout = QFormLayout(cutout_group)
        
        self.cutout_enabled = cutout_group
        
        self.cutout_size_spin = QSpinBox()
        self.cutout_size_spin.setRange(5, 50)
        self.cutout_size_spin.setValue(10)
        self.cutout_size_spin.setSuffix("%")
        cutout_layout.addRow(self.tr("Size:"), self.cutout_size_spin)
        
        self.cutout_count_spin = QSpinBox()
        self.cutout_count_spin.setRange(1, 25)
        self.cutout_count_spin.setValue(3)
        cutout_layout.addRow(self.tr("Count:"), self.cutout_count_spin)
        
        self.cutout_apply_percent_spin = QSpinBox()
        self.cutout_apply_percent_spin.setRange(0, 100)
        self.cutout_apply_percent_spin.setValue(50)
        self.cutout_apply_percent_spin.setSuffix("%")
        cutout_layout.addRow(self.tr("Rate:"), self.cutout_apply_percent_spin)
        
        aug_layout.addWidget(cutout_group)
        
        # NEW: Motion Blur
        self.motion_blur_slider = AugmentationSlider(
            self.tr("Motion Blur"), 0, 30, 15, "",
            help_text=self.tr("Motion Blur: Adds horizontal motion effect.\n\n"
                      "Unit: Kernel size (pixels)\n\n"
                      "Teaches detection of moving objects.")
        )
        aug_layout.addWidget(self.motion_blur_slider)
        
        # NEW: Shear - Single checkbox, horizontal and vertical
        shear_group = QGroupBox(self.tr("Shear"))
        shear_group.setToolTip(
            self.tr("Shear: Tilts the image horizontally/vertically.\n\n"
            "• Horizontal: Horizontal tilt angle\n"
            "• Vertical: Vertical tilt angle\n\n"
            "Provides perspective variation,\n"
            "teaches generalization from different viewing angles.")
        )
        shear_group.setCheckable(True)
        shear_group.setChecked(False)
        shear_layout = QFormLayout(shear_group)
        
        self.shear_enabled = shear_group
        
        self.shear_h_spin = QSpinBox()
        self.shear_h_spin.setRange(0, 45)
        self.shear_h_spin.setValue(10)
        self.shear_h_spin.setSuffix("°")
        shear_layout.addRow(self.tr("Horizontal:"), self.shear_h_spin)
        
        self.shear_v_spin = QSpinBox()
        self.shear_v_spin.setRange(0, 45)
        self.shear_v_spin.setValue(10)
        self.shear_v_spin.setSuffix("°")
        shear_layout.addRow(self.tr("Vertical:"), self.shear_v_spin)
        
        aug_layout.addWidget(shear_group)
        
        settings_layout.addWidget(aug_group)
        settings_layout.addStretch()
        
        scroll.setWidget(settings_widget)
        left_layout.addWidget(scroll)
        
        main_layout.addWidget(left_panel, 1)
        
        # Right panel - Preview
        right_panel = QGroupBox(self.tr("Live Preview"))
        right_layout = QVBoxLayout(right_panel)
        
        self.preview_label = QLabel(self.tr("Enable augmentation"))
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(320, 320)
        self.preview_label.setStyleSheet("background-color: #1a1a1a; border: 1px solid #444; border-radius: 4px;")
        right_layout.addWidget(self.preview_label)
        
        main_layout.addWidget(right_panel, 1)
        
        return page
    
    def _create_format_page(self) -> QWidget:
        """Step 3: Format & Export."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        format_group = QGroupBox(self.tr("Export Format"))
        format_layout = QVBoxLayout(format_group)
        
        self.format_btn_group = QButtonGroup(self)
        
        self.yolo_radio = QRadioButton("YOLO")
        self.yolo_radio.setChecked(True)
        self.format_btn_group.addButton(self.yolo_radio, 0)
        
        yolo_layout = QHBoxLayout()
        yolo_layout.addWidget(self.yolo_radio)
        self.yolo_version = QComboBox()
        self.yolo_version.addItems(["YOLOv5", "YOLOv6", "YOLOv7", "YOLOv8", "YOLOv9", "YOLOv10", "YOLOv11"])
        self.yolo_version.setCurrentText("YOLOv8")
        yolo_layout.addWidget(self.yolo_version)
        yolo_layout.addStretch()
        format_layout.addLayout(yolo_layout)
        
        self.coco_radio = QRadioButton("COCO (JSON)")
        self.format_btn_group.addButton(self.coco_radio, 1)
        format_layout.addWidget(self.coco_radio)
        
        self.voc_radio = QRadioButton("Pascal VOC (XML)")
        self.format_btn_group.addButton(self.voc_radio, 2)
        format_layout.addWidget(self.voc_radio)
        
        self.custom_radio = QRadioButton("Custom")
        self.format_btn_group.addButton(self.custom_radio, 3)
        format_layout.addWidget(self.custom_radio)
        
        layout.addWidget(format_group)
        
        self.custom_group = QGroupBox("Custom Format")
        custom_layout = QVBoxLayout(self.custom_group)
        
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel(self.tr("Type:")))
        self.custom_type = QComboBox()
        self.custom_type.addItems(["TXT", "JSON"])
        type_layout.addWidget(self.custom_type)
        type_layout.addStretch()
        custom_layout.addLayout(type_layout)
        
        custom_layout.addWidget(QLabel("Format string:"))
        self.format_string = QLineEdit("{class_id} {x_center} {y_center} {width} {height}")
        custom_layout.addWidget(self.format_string)
        
        self.custom_group.setVisible(False)
        layout.addWidget(self.custom_group)
        
        output_group = QGroupBox(self.tr("Output Folder"))
        output_layout = QHBoxLayout(output_group)
        
        self.output_path = QLineEdit()
        if self._default_output_dir:
            self.output_path.setText(str(self._default_output_dir))
        self.output_path.setPlaceholderText(self.tr("Select output folder..."))
        output_layout.addWidget(self.output_path)
        
        self.browse_btn = QPushButton(self.tr("📁 Browse..."))
        output_layout.addWidget(self.browse_btn)
        
        layout.addWidget(output_group)
        
        self.export_summary = QLabel()
        self.export_summary.setStyleSheet("color: #2196F3; padding: 15px; font-size: 13px;")
        layout.addWidget(self.export_summary)
        
        layout.addStretch()
        return page
    
    def _connect_signals(self):
        self.back_btn.clicked.connect(self._go_back)
        self.next_btn.clicked.connect(self._go_next)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.split_enabled.toggled.connect(self._on_split_toggled)
        self.range_slider.valuesChanged.connect(self._on_range_changed)
        
        self.aug_enabled.toggled.connect(self._on_aug_toggled)
        
        # Separate tracking for each slider
        # Brightness - new UI
        self.brightness_slider_value.valueChanged.connect(self._on_brightness_value_changed)
        self.brighten_checkbox.toggled.connect(lambda: self._on_brightness_checkbox_changed('brighten'))
        self.darken_checkbox.toggled.connect(lambda: self._on_brightness_checkbox_changed('darken'))
        
        self.contrast_slider.valueChanged.connect(lambda: self._on_slider_changed('contrast'))
        self.rotation_slider.valueChanged.connect(lambda: self._on_slider_changed('rotation'))
        self.blur_slider.valueChanged.connect(lambda: self._on_slider_changed('blur'))
        self.noise_slider.valueChanged.connect(lambda: self._on_slider_changed('noise'))
        self.hue_slider.valueChanged.connect(lambda: self._on_slider_changed('hue'))
        self.exposure_slider.valueChanged.connect(lambda: self._on_slider_changed('exposure'))
        self.motion_blur_slider.valueChanged.connect(lambda: self._on_slider_changed('motion_blur'))
        
        # Cutout group
        self.cutout_enabled.toggled.connect(lambda: self._on_slider_changed('cutout'))
        self.cutout_size_spin.valueChanged.connect(lambda: self._on_slider_changed('cutout'))
        self.cutout_count_spin.valueChanged.connect(lambda: self._on_slider_changed('cutout'))
        self.cutout_apply_percent_spin.valueChanged.connect(lambda: self._on_slider_changed('cutout'))
        
        # Shear group
        self.shear_enabled.toggled.connect(lambda: self._on_slider_changed('shear'))
        self.shear_h_spin.valueChanged.connect(lambda: self._on_slider_changed('shear'))
        self.shear_v_spin.valueChanged.connect(lambda: self._on_slider_changed('shear'))
        
        # Flip group (with percentage control)
        self.flip_enabled.toggled.connect(lambda: self._on_slider_changed('flip'))
        self.hflip_percent_spin.valueChanged.connect(lambda: self._on_slider_changed('flip'))
        self.vflip_percent_spin.valueChanged.connect(lambda: self._on_slider_changed('flip'))
        
        # Grayscale group (with percentage control)
        self.grayscale_enabled.toggled.connect(lambda: self._on_slider_changed('grayscale'))
        self.grayscale_percent_spin.valueChanged.connect(lambda: self._on_slider_changed('grayscale'))
        
        self.resize_enabled.toggled.connect(lambda: self._on_slider_changed('resize'))
        self.resize_mode.currentIndexChanged.connect(lambda: self._on_slider_changed('resize'))
        
        self.format_btn_group.buttonClicked.connect(self._on_format_changed)
        self.browse_btn.clicked.connect(self._browse_output)
    
    def _go_back(self):
        current = self.stack.currentIndex()
        if current > 0:
            self.stack.setCurrentIndex(current - 1)
            self._update_navigation()
    
    def _go_next(self):
        current = self.stack.currentIndex()
        if current < 2:
            self.stack.setCurrentIndex(current + 1)
            self._update_navigation()
            if current + 1 == 2:
                self._update_export_summary()
        else:
            self._start_export()
    
    def _update_navigation(self):
        current = self.stack.currentIndex()
        steps = [self.tr("Dataset Split"), self.tr("Augmentation"), self.tr("Format & Export")]
        self.step_label.setText(self.tr("Step {}/3: {}").format(current + 1, steps[current]))
        
        self.back_btn.setVisible(current > 0)
        
        if current == 2:
            self.next_btn.setText(self.tr("📦 Export"))
            self.next_btn.setStyleSheet("padding: 10px 25px; background-color: #4CAF50; color: white; font-weight: bold;")
        else:
            self.next_btn.setText(self.tr("Next →"))
            self.next_btn.setStyleSheet("padding: 10px 25px; background-color: #0d6efd; color: white;")
    
    def _on_split_toggled(self, enabled):
        self.split_group.setEnabled(enabled)
        self.shuffle_group.setEnabled(enabled)
        self._update_split_summary()
    
    def _on_range_changed(self, train, val, test):
        self.split_info.setText(f"Train: {train}% | Validation: {val}% | Test: {test}%")
        self._update_split_summary()
    
    def _update_split_summary(self):
        # Use filtered file count
        filtered_files = self._get_filtered_image_files()
        total = len(filtered_files)
        
        if not self.split_enabled.isChecked():
            self.split_summary.setText(self.tr("Split disabled - {} images to single folder").format(total))
            return
        
        train_pct, val_pct, test_pct = self.range_slider.values()
        train = int(total * train_pct / 100)
        val = int(total * val_pct / 100)
        test = total - train - val
        
        self.split_summary.setText(self.tr("📂 Train: {} images | Val: {} images | Test: {} images").format(train, val, test))
    
    def _on_unlabeled_toggled(self, checked: bool):
        """Update all sections when unlabeled checkbox toggles."""
        self._update_split_summary()
        self._update_multiplier_options()
        # Update summary if on export page
        if self.stack.currentIndex() == 2:
            self._update_export_summary()
    
    def _update_multiplier_options(self):
        """Update multiplier options with image count."""
        # Use filtered file count
        filtered = self._get_filtered_image_files()
        count = len(filtered)
        self.aug_multiplier.clear()
        for mult in [2, 3, 5, 8, 10, 15]:
            # Roboflow style: 1 original + (mult-1) augmented = total mult images
            self.aug_multiplier.addItem(self.tr("{}x → {} images (1 original + {} augmented)").format(mult, count * mult, mult-1))
    
    def _on_slider_changed(self, slider_name: str):
        """Track which slider changed and update preview."""
        self._last_changed_slider = slider_name
        self._schedule_preview()
    
    def _on_aug_toggled(self, enabled):
        if enabled:
            self._last_changed_slider = None  # Show all
            self._update_preview()
        else:
            self.preview_label.setText("Augmentation'ı aktifleştirin")
    
    def _on_brightness_value_changed(self, value):
        """When brightness slider value changes."""
        self.brightness_value_label.setText(f"{value}%")
        self._schedule_preview()
    
    def _on_brightness_checkbox_changed(self, checkbox_type: str):
        """When Brighten or Darken checkbox changes."""
        # Track last selected effect (for live preview)
        if checkbox_type == 'brighten' and self.brighten_checkbox.isChecked():
            self._last_brightness_effect = 'brighten'
        elif checkbox_type == 'darken' and self.darken_checkbox.isChecked():
            self._last_brightness_effect = 'darken'
        elif not self.brighten_checkbox.isChecked() and not self.darken_checkbox.isChecked():
            self._last_brightness_effect = None
        
        self._last_changed_slider = 'brightness'
        self._schedule_preview()
    
    def _schedule_preview(self):
        self._preview_timer.start(100)
    
    def _load_preview_image(self):
        if self._image_files:
            first_image = self._image_files[0]
            img_path = str(first_image) if hasattr(first_image, '__fspath__') else first_image
            
            try:
                # Try binary read first (avoids Turkish character issue)
                with open(img_path, 'rb') as f:
                    data = np.frombuffer(f.read(), np.uint8)
                self._preview_image = cv2.imdecode(data, cv2.IMREAD_COLOR)
            except Exception as e:
                print(f"Preview yüklenemedi: {e}")
                self._preview_image = None
    
    def _update_preview(self):
        if self._preview_image is None:
            self._load_preview_image()
            if self._preview_image is None:
                self.preview_label.setText("Görsel yüklenemedi\n(Klasör açın)")
                return
        
        if not self.aug_enabled.isChecked():
            self.preview_label.setText("Augmentation'ı aktifleştirin")
            return
        
        try:
            # Determine last adjusted augmentation
            last_slider = getattr(self, '_last_changed_slider', None)
            config = self._get_single_augmentation_config(last_slider)
            aug_img = self._augmentor.preview(self._preview_image.copy(), config)
            
            if config.resize.enabled:
                aug_img, _ = self._augmentor.resize_image(aug_img, config.resize)
            
            # BGR -> RGB
            rgb_img = cv2.cvtColor(aug_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_img.shape
            bytes_per_line = ch * w
            
            # Create QImage
            qt_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            qt_img = qt_img.copy()  # Copy data
            
            pixmap = QPixmap.fromImage(qt_img)
            scaled = pixmap.scaled(
                self.preview_label.width() - 10,
                self.preview_label.height() - 10,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
            
        except Exception as e:
            self.preview_label.setText(f"Önizleme hatası:\n{str(e)}")
    
    def _on_format_changed(self, btn):
        self.custom_group.setVisible(self.custom_radio.isChecked())
    
    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.tr("Select Export Folder"),
            str(self._default_output_dir) if self._default_output_dir else ""
        )
        if folder:
            self.output_path.setText(folder)
    
    def _update_export_summary(self):
        # Use filtered file count
        filtered = self._get_filtered_image_files()
        total = len(filtered)
        
        if self.aug_enabled.isChecked():
            mult_text = self.aug_multiplier.currentText().split('x')[0]
            mult = int(mult_text) if mult_text.isdigit() else 2
            total *= mult
        
        parts = [self.tr("📊 Total {} images to export").format(total)]
        
        if self.aug_enabled.isChecked():
            mult_text = self.aug_multiplier.currentText().split('x')[0]
            parts.append(f"🎨 {mult_text}x Augmentation")
        
        if self.split_enabled.isChecked():
            train_pct, val_pct, test_pct = self.range_slider.values()
            train = int(total * train_pct / 100)
            val = int(total * val_pct / 100)
            test = total - train - val
            parts.append(f"📂 Train: {train}, Val: {val}, Test: {test}")
        
        self.export_summary.setText("\n".join(parts))
    
    def _get_augmentation_config(self) -> AugmentationConfig:
        resize_mode_map = {
            0: ResizeMode.STRETCH,
            1: ResizeMode.FIT_WITHIN, 2: ResizeMode.FIT_REFLECT,
            3: ResizeMode.FIT_BLACK, 4: ResizeMode.FIT_WHITE
        }
        
        # Extract only multiplier from "2x -> 24 images" format
        mult_text = self.aug_multiplier.currentText().split('x')[0]
        multiplier = int(mult_text) if mult_text.isdigit() else 2
        
        return AugmentationConfig(
            enabled=self.aug_enabled.isChecked(),
            multiplier=multiplier,
            # New brightness system - Brighten and Darken separate
            brighten_enabled=self.brighten_checkbox.isChecked(),
            darken_enabled=self.darken_checkbox.isChecked(),
            brightness_value=self.brightness_slider_value.value() / 100,
            contrast_enabled=self.contrast_slider.is_enabled(),
            contrast_value=self.contrast_slider.value() / 100,
            rotation_enabled=self.rotation_slider.is_enabled(),
            rotation_value=self.rotation_slider.value(),
            h_flip_enabled=self.flip_enabled.isChecked() and self.hflip_percent_spin.value() > 0,
            h_flip_percent=self.hflip_percent_spin.value(),
            v_flip_enabled=self.flip_enabled.isChecked() and self.vflip_percent_spin.value() > 0,
            v_flip_percent=self.vflip_percent_spin.value(),
            blur_enabled=self.blur_slider.is_enabled(),
            blur_value=self.blur_slider.value() / 10,
            noise_enabled=self.noise_slider.is_enabled(),
            noise_value=float(self.noise_slider.value()),
            hue_enabled=self.hue_slider.is_enabled(),
            hue_value=abs(self.hue_slider.value()),
            grayscale_enabled=self.grayscale_enabled.isChecked(),
            grayscale_percent=self.grayscale_percent_spin.value(),
            exposure_enabled=self.exposure_slider.is_enabled(),
            exposure_value=self.exposure_slider.value() / 100,
            cutout_enabled=self.cutout_enabled.isChecked(),
            cutout_size=self.cutout_size_spin.value(),
            cutout_count=self.cutout_count_spin.value(),
            cutout_apply_percent=self.cutout_apply_percent_spin.value(),
            motion_blur_enabled=self.motion_blur_slider.is_enabled(),
            motion_blur_value=self.motion_blur_slider.value(),
            shear_enabled=self.shear_enabled.isChecked(),
            shear_horizontal=self.shear_h_spin.value(),
            shear_vertical=self.shear_v_spin.value(),
            resize=ResizeConfig(
                enabled=self.resize_enabled.isChecked(),
                width=self.resize_width.value(),
                height=self.resize_height.value(),
                mode=resize_mode_map.get(self.resize_mode.currentIndex(), ResizeMode.STRETCH)
            )
        )
    
    def _get_single_augmentation_config(self, slider_name: str = None) -> AugmentationConfig:
        """Return config activating only specified augmentation."""
        resize_mode_map = {
            0: ResizeMode.STRETCH,
            1: ResizeMode.FIT_WITHIN, 2: ResizeMode.FIT_REFLECT,
            3: ResizeMode.FIT_BLACK, 4: ResizeMode.FIT_WHITE
        }
        
        # If slider_name is None, show all active augmentations
        show_all = slider_name is None
        
        return AugmentationConfig(
            enabled=True,
            multiplier=1,
            # Brightness - show last selected effect for live preview
            brighten_enabled=(slider_name == 'brightness' or show_all) and self.brighten_checkbox.isChecked() and getattr(self, '_last_brightness_effect', None) == 'brighten',
            darken_enabled=(slider_name == 'brightness' or show_all) and self.darken_checkbox.isChecked() and getattr(self, '_last_brightness_effect', None) == 'darken',
            brightness_value=self.brightness_slider_value.value() / 100,
            contrast_enabled=(slider_name == 'contrast' or show_all) and self.contrast_slider.is_enabled(),
            contrast_value=self.contrast_slider.value() / 100,
            rotation_enabled=(slider_name == 'rotation' or show_all) and self.rotation_slider.is_enabled(),
            rotation_value=self.rotation_slider.value(),
            h_flip_enabled=(slider_name == 'flip' or show_all) and self.flip_enabled.isChecked() and self.hflip_percent_spin.value() > 0,
            h_flip_percent=self.hflip_percent_spin.value(),
            v_flip_enabled=(slider_name == 'flip' or show_all) and self.flip_enabled.isChecked() and self.vflip_percent_spin.value() > 0,
            v_flip_percent=self.vflip_percent_spin.value(),
            blur_enabled=(slider_name == 'blur' or show_all) and self.blur_slider.is_enabled(),
            blur_value=self.blur_slider.value() / 10,
            noise_enabled=(slider_name == 'noise' or show_all) and self.noise_slider.is_enabled(),
            noise_value=float(self.noise_slider.value()),
            hue_enabled=(slider_name == 'hue' or show_all) and self.hue_slider.is_enabled(),
            hue_value=abs(self.hue_slider.value()),
            grayscale_enabled=(slider_name == 'grayscale' or show_all) and self.grayscale_enabled.isChecked(),
            grayscale_percent=self.grayscale_percent_spin.value(),
            exposure_enabled=(slider_name == 'exposure' or show_all) and self.exposure_slider.is_enabled(),
            exposure_value=self.exposure_slider.value() / 100,
            cutout_enabled=(slider_name == 'cutout' or show_all) and self.cutout_enabled.isChecked(),
            cutout_size=self.cutout_size_spin.value(),
            cutout_count=self.cutout_count_spin.value(),
            cutout_apply_percent=self.cutout_apply_percent_spin.value(),
            motion_blur_enabled=(slider_name == 'motion_blur' or show_all) and self.motion_blur_slider.is_enabled(),
            motion_blur_value=self.motion_blur_slider.value(),
            shear_enabled=(slider_name == 'shear' or show_all) and self.shear_enabled.isChecked(),
            shear_horizontal=self.shear_h_spin.value(),
            shear_vertical=self.shear_v_spin.value(),
            resize=ResizeConfig(
                enabled=(slider_name == 'resize' or show_all) and self.resize_enabled.isChecked(),
                width=self.resize_width.value(),
                height=self.resize_height.value(),
                mode=resize_mode_map.get(self.resize_mode.currentIndex(), ResizeMode.STRETCH)
            ),
            preview_mode=True
        )
    
    def _get_split_config(self) -> SplitConfig:
        train_pct, val_pct, test_pct = self.range_slider.values()
        return SplitConfig(
            enabled=self.split_enabled.isChecked(),
            train_ratio=train_pct / 100,
            val_ratio=val_pct / 100,
            test_ratio=test_pct / 100,
            shuffle=self.shuffle_check.isChecked(),
            seed=self.seed_spin.value()
        )
    
    def _create_exporter(self):
        if self.yolo_radio.isChecked():
            version = self.yolo_version.currentText().replace("YOLO", "")
            return YOLOExporter(self._class_manager, version)
        elif self.coco_radio.isChecked():
            return COCOExporter(self._class_manager)
        elif self.voc_radio.isChecked():
            # YOLO exporter is used for VOC too (for class_manager)
            # Actual format is determined in export worker
            return YOLOExporter(self._class_manager, "v8")
        elif self.custom_radio.isChecked():
            if self.custom_type.currentText() == "TXT":
                return CustomTXTExporter(self._class_manager, self.format_string.text())
            else:
                return CustomJSONExporter(self._class_manager, {})
        return None
    
    def _start_export(self):
        output = self.output_path.text().strip()
        if not output:
            QMessageBox.warning(self, "Uyarı", "Lütfen çıktı klasörünü seçin.")
            return
        
        exporter = self._create_exporter()
        if exporter is None:
            return
        
        # Unlabeled file filtering
        image_files = self._get_filtered_image_files()
        
        annotations_dict = {}
        for image_path in image_files:
            key = str(image_path)
            if key in self._annotation_manager._annotations:
                annotations_dict[key] = self._annotation_manager._annotations[key]
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText(self.tr("Starting export..."))
        self.next_btn.setEnabled(False)
        
        # Determine format
        format_id = self.format_btn_group.checkedId()
        if format_id == 0:
            export_format = "yolo"
        elif format_id == 1:
            export_format = "coco"
        elif format_id == 2:
            export_format = "voc"
        else:
            export_format = "yolo"
        
        self._worker = ExportWorkerV2(
            exporter, annotations_dict, Path(output), image_files,
            self._get_augmentation_config(), self._get_split_config(), export_format
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_export_finished)
        self._worker.error.connect(self._on_export_error)
        self._worker.start()
    
    def _on_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(self.tr("Exporting: {}/{}").format(current, total))
    
    def _on_export_finished(self, count):
        self.progress_bar.setValue(self.progress_bar.maximum())
        QMessageBox.information(self, self.tr("Success"), self.tr("✓ {} images exported.\n\nLocation: {}").format(count, self.output_path.text()))
        self.accept()
    
    def _on_export_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        self.next_btn.setEnabled(True)
        QMessageBox.critical(self, self.tr("Error"), self.tr("Export error:\n{}").format(error_msg))
    
    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        super().closeEvent(event)
    
    def _count_unlabeled_files(self) -> int:
        """Calculate unlabeled file count."""
        unlabeled = 0
        
        if not self._image_files:
            return 0
        
        # Find labels folder
        first_path = Path(self._image_files[0])
        parent = first_path.parent
        
        if parent.name.lower() == "images":
            labels_dir = parent.parent / "labels"
        else:
            labels_dir = parent / "labels"
        
        for path in self._image_files:
            p = Path(path)
            txt_file = labels_dir / f"{p.stem}.txt"
            if not txt_file.exists() or txt_file.stat().st_size == 0:
                unlabeled += 1
        
        return unlabeled
    
    def _get_filtered_image_files(self) -> list:
        """include_unlabeled seçeneğine göre filtrelenmiş dosya listesi döndür."""
        if self.include_unlabeled.isChecked():
            return self._image_files
        
        # Sadece etiketli dosyaları döndür
        if not self._image_files:
            return []
        
        first_path = Path(self._image_files[0])
        parent = first_path.parent
        
        if parent.name.lower() == "images":
            labels_dir = parent.parent / "labels"
        else:
            labels_dir = parent / "labels"
        
        labeled_files = []
        for path in self._image_files:
            p = Path(path)
            txt_file = labels_dir / f"{p.stem}.txt"
            if txt_file.exists() and txt_file.stat().st_size > 0:
                labeled_files.append(path)
        
        return labeled_files
