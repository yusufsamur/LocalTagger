"""
Export Wizard v1.5
==================
Adım adım export wizard - Dataset Split → Augmentation → Format
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
    """İki noktalı range slider - Train/Val/Test bölme için."""
    
    valuesChanged = Signal(int, int, int)  # train, val, test
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setMinimumWidth(300)
        
        self._min = 0
        self._max = 100
        self._handle1 = 70  # Train/Val sınırı
        self._handle2 = 90  # Val/Test sınırı
        
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
        
        # Train bölgesi (yeşil)
        x1 = self._handle_width // 2
        x2 = int(self._handle1 / 100 * w) + self._handle_width // 2
        painter.fillRect(QRect(x1, bar_y, x2 - x1, bar_height), QColor("#4CAF50"))
        
        # Val bölgesi (mavi)
        x3 = int(self._handle2 / 100 * w) + self._handle_width // 2
        painter.fillRect(QRect(x2, bar_y, x3 - x2, bar_height), QColor("#2196F3"))
        
        # Test bölgesi (turuncu)
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
        
        # Etiketler
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
            # Handle1: Train sonu, min 0, max handle2
            self._handle1 = min(value, self._handle2)
        elif self._dragging == 2:
            # Handle2: Val sonu, min handle1, max 100
            self._handle2 = max(value, self._handle1)
        
        self.update()
        self.valuesChanged.emit(self._handle1, 
                                 self._handle2 - self._handle1,
                                 100 - self._handle2)
    
    def values(self):
        """(train%, val%, test%) döndür."""
        return (self._handle1, 
                self._handle2 - self._handle1, 
                100 - self._handle2)
    
    def setValues(self, train, val, test=None):
        """Değerleri ayarla."""
        self._handle1 = train
        self._handle2 = train + val
        self.update()


class ExportWorkerV2(QThread):
    """Export işlemini arka planda çalıştırır."""
    
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
            
            # COCO için annotation collector
            if self.export_format == "coco":
                self._coco_data = {}  # split_name -> COCO dict
            
            # Tüm görevleri topla
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
                
                # COCO için split başına data structure oluştur
                if self.export_format == "coco":
                    self._coco_data[split_name] = {
                        "images": [],
                        "annotations": [],
                        "categories": [
                            {"id": cls.id + 1, "name": cls.name, "supercategory": "none"}  # COCO ID'leri 1'den başlar
                            for cls in self.exporter.class_manager.classes
                        ]
                    }
                
                for image_path in files:
                    tasks.append((image_path, images_dir, labels_dir, total_files, split_name))
            
            # Paralel işleme
            max_workers = min(os.cpu_count() or 4, 8)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(self._process_image, tasks)
            
            # COCO JSON dosyalarını kaydet
            if self.export_format == "coco":
                self._save_coco_json(output_dir, splits)
            
            self._save_classes_txt(output_dir)
            self.finished.emit(self._exported_count)
            
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n{traceback.format_exc()}")
    
    def _process_image(self, task):
        """Tek bir görseli işle (thread-safe)."""
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
                
                # Roboflow tarzı isimlendirme
                orig_filename = image_path.name  # örn: asd9.jpg
                if aug_idx == 0:
                    # Orijinal görsel - ismi aynen koru
                    new_name = image_path.stem
                else:
                    # Augmented görsel - unique ID oluştur
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
                        # COCO için boş image entry ekle
                        self._add_coco_annotation(
                            None, transform, resize_info,
                            split_name, f"{new_name}.jpg",
                            img.shape[1], img.shape[0],
                            aug_img.shape[1], aug_img.shape[0]
                        )
                    elif self.export_format == "voc":
                        pass  # Boş annotation için XML oluşturmaya gerek yok
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
        """COCO formatında annotation ekle (thread-safe)."""
        with self._lock:
            coco_data = self._coco_data[split_name]
            
            # Image ID (mevcut image sayısına göre)
            image_id = len(coco_data["images"]) + 1
            
            # Image entry ekle
            coco_data["images"].append({
                "id": image_id,
                "file_name": image_filename,
                "width": new_w,
                "height": new_h
            })
            
            if annotations is None:
                return
            
            # Cutout bölgelerini al (varsa)
            cutout_regions = []
            if transform and "cutout" in transform:
                cutout_regions = transform["cutout"].get("regions", [])
            
            # Annotation ID (mevcut annotation sayısına göre)
            ann_id = len(coco_data["annotations"]) + 1
            
            # BBox'ları ekle
            for bbox in annotations.bboxes:
                coords = (bbox.x_center, bbox.y_center, bbox.width, bbox.height)
                
                # Cutout kontrolü (%90+ kaplama varsa atla)
                if cutout_regions:
                    if self.augmentor.is_bbox_covered_by_cutout(coords, cutout_regions, orig_w, orig_h, 0.9):
                        continue
                
                if transform:
                    coords = self.augmentor.transform_bbox(coords, transform, orig_w, orig_h)
                if resize_info:
                    coords = self.augmentor.transform_bbox_for_resize(
                        coords, resize_info, orig_w, orig_h, new_w, new_h)
                
                x_c, y_c, w, h = coords
                # YOLO formatından COCO formatına (x, y, width, height - üst sol köşe)
                x = (x_c - w/2) * new_w
                y = (y_c - h/2) * new_h
                width = w * new_w
                height = h * new_h
                
                coco_data["annotations"].append({
                    "id": ann_id,
                    "image_id": image_id,
                    "category_id": bbox.class_id + 1,  # COCO kategorileri 1'den başlar
                    "bbox": [round(x, 2), round(y, 2), round(width, 2), round(height, 2)],
                    "area": round(width * height, 2),
                    "segmentation": [],  # BBox için boş segmentasyon
                    "iscrowd": 0
                })
                ann_id += 1
            
            # Polygon'ları ekle (segmentasyon olarak)
            for polygon in annotations.polygons:
                if len(polygon.points) < 3:
                    continue
                
                points = polygon.points
                
                # Cutout kırpma: Polygon'dan cutout bölgelerini çıkar
                if cutout_regions:
                    clipped_polygons = self.augmentor.apply_cutout_to_polygon(
                        points, cutout_regions, orig_w, orig_h
                    )
                else:
                    clipped_polygons = [points]
                
                # Her kırpılmış polygon için ayrı annotation ekle
                for clipped_points in clipped_polygons:
                    if len(clipped_points) < 3:
                        continue
                    
                    final_points = clipped_points
                    if transform:
                        final_points = self.augmentor.transform_polygon(final_points, transform, orig_w, orig_h)
                    
                    # Segmentasyon için düzleştirilmiş koordinat listesi [x1, y1, x2, y2, ...]
                    seg_points = []
                    min_x = float('inf')
                    min_y = float('inf')
                    max_x = float('-inf')
                    max_y = float('-inf')
                    
                    for px, py in final_points:
                        # Resize dönüşümü uygula (koordinatlar normalize)
                        if resize_info:
                            mode = resize_info.get("mode")
                            if mode and mode.startswith("fit_"):
                                scale = resize_info.get("scale", 1.0)
                                offset = resize_info.get("offset", (0, 0))
                                px_abs = px * orig_w * scale + offset[0]
                                py_abs = py * orig_h * scale + offset[1]
                            elif mode == "fill_crop":
                                scale = resize_info.get("scale", 1.0)
                                crop_offset = resize_info.get("crop_offset", (0, 0))
                                px_abs = px * orig_w * scale - crop_offset[0]
                                py_abs = py * orig_h * scale - crop_offset[1]
                            else:
                                px_abs = px * new_w
                                py_abs = py * new_h
                        else:
                            px_abs = px * new_w
                            py_abs = py * new_h
                        
                        seg_points.extend([round(px_abs, 2), round(py_abs, 2)])
                        min_x = min(min_x, px_abs)
                        min_y = min(min_y, py_abs)
                        max_x = max(max_x, px_abs)
                        max_y = max(max_y, py_abs)
                    
                    # Bounding box hesapla (polygon'dan)
                    bbox_x = min_x
                    bbox_y = min_y
                    bbox_w = max_x - min_x
                    bbox_h = max_y - min_y
                    
                    # Alan hesapla (shoelace formülü)
                    area = 0.0
                    n = len(final_points)
                    for i in range(n):
                        j = (i + 1) % n
                        x1, y1 = final_points[i]
                        x2, y2 = final_points[j]
                        area += (x1 * new_w) * (y2 * new_h)
                        area -= (x2 * new_w) * (y1 * new_h)
                    area = abs(area) / 2.0
                    
                    coco_data["annotations"].append({
                        "id": ann_id,
                        "image_id": image_id,
                        "category_id": polygon.class_id + 1,  # COCO kategorileri 1'den başlar
                        "bbox": [round(bbox_x, 2), round(bbox_y, 2), round(bbox_w, 2), round(bbox_h, 2)],
                        "area": round(area, 2),
                        "segmentation": [seg_points],  # Polygon noktaları
                        "iscrowd": 0
                    })
                    ann_id += 1
    
    def _save_coco_json(self, output_dir: Path, splits: dict):
        """COCO JSON dosyalarını kaydet."""
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
        
        # Cutout bölgelerini al (varsa)
        cutout_regions = []
        if transform and "cutout" in transform:
            cutout_regions = transform["cutout"].get("regions", [])
        
        for bbox in annotations.bboxes:
            coords = (bbox.x_center, bbox.y_center, bbox.width, bbox.height)
            
            # Cutout kontrolü (%90+ kaplama varsa atla)
            if cutout_regions:
                if self.augmentor.is_bbox_covered_by_cutout(coords, cutout_regions, orig_w, orig_h, 0.9):
                    continue  # Bu bbox'ı kaydetme
            
            if transform:
                coords = self.augmentor.transform_bbox(coords, transform, orig_w, orig_h)
            if resize_info:
                coords = self.augmentor.transform_bbox_for_resize(
                    coords, resize_info, orig_w, orig_h, new_w, new_h)
            x_c, y_c, w, h = coords
            lines.append(f"{bbox.class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}")
        
        for polygon in annotations.polygons:
            if len(polygon.points) >= 3:
                points = polygon.points
                
                # Cutout kırpma: Polygon'dan cutout bölgelerini çıkar
                if cutout_regions:
                    clipped_polygons = self.augmentor.apply_cutout_to_polygon(
                        points, cutout_regions, orig_w, orig_h
                    )
                    
                    # Kırpma sonucu birden fazla polygon oluşabilir
                    for clipped_points in clipped_polygons:
                        if len(clipped_points) >= 3:
                            final_points = clipped_points
                            if transform:
                                final_points = self.augmentor.transform_polygon(final_points, transform, orig_w, orig_h)
                            points_str = " ".join(f"{x:.6f} {y:.6f}" for x, y in final_points)
                            lines.append(f"{polygon.class_id} {points_str}")
                else:
                    # Cutout yoksa normal işle
                    if transform:
                        points = self.augmentor.transform_polygon(points, transform, orig_w, orig_h)
                    points_str = " ".join(f"{x:.6f} {y:.6f}" for x, y in points)
                    lines.append(f"{polygon.class_id} {points_str}")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def _save_voc_xml(self, annotations, transform, resize_info,
                      output_path, image_filename, orig_w, orig_h, new_w, new_h):
        """Pascal VOC XML formatında etiket kaydet."""
        from xml.etree.ElementTree import Element, SubElement, tostring
        from xml.dom import minidom
        
        output_path = Path(output_path)  # Path tipine dönüştür
        
        # Root element
        annotation = Element('annotation')
        
        # Folder ve filename
        SubElement(annotation, 'folder').text = 'images'
        SubElement(annotation, 'filename').text = image_filename
        SubElement(annotation, 'path').text = image_filename  # Basit path
        
        # Source
        source = SubElement(annotation, 'source')
        SubElement(source, 'database').text = 'LocalFlow'
        
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
            if resize_info:
                coords = self.augmentor.transform_bbox_for_resize(
                    coords, resize_info, orig_w, orig_h, new_w, new_h)
            
            x_c, y_c, w, h = coords
            # YOLO formatından VOC formatına (xmin, ymin, xmax, ymax)
            xmin = int((x_c - w/2) * new_w)
            ymin = int((y_c - h/2) * new_h)
            xmax = int((x_c + w/2) * new_w)
            ymax = int((y_c + h/2) * new_h)
            
            # Sınırları kontrol et
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
        """Roboflow tarzı deterministik unique ID üret."""
        import hashlib
        
        # Transform'u string'e çevir (sıralı ve deterministik)
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
        
        # Hash oluştur: filename + aug_idx + transform
        hash_input = f"{orig_filename}_{aug_idx}_{'_'.join(transform_parts)}"
        hash_bytes = hashlib.md5(hash_input.encode()).hexdigest()
        
        # İlk 6 karakter al (Roboflow tarzı kısa ID)
        return hash_bytes[:6]
    
    def _read_image(self, path: str) -> np.ndarray:
        """Türkçe karakter destekli görsel okuma."""
        try:
            # Doğrudan binary okuma (Türkçe karakter sorununu önler)
            with open(path, 'rb') as f:
                data = np.frombuffer(f.read(), np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            return None
    
    def _write_image(self, path: str, img: np.ndarray) -> bool:
        """Türkçe karakter destekli görsel yazma."""
        try:
            # Önce normal cv2.imwrite dene
            success = cv2.imwrite(path, img)
            if success:
                return True
            
            # Türkçe karakter sorunu varsa binary yazma yap
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
    """Augmentation parametresi için slider widget."""
    
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
        
        # Yardım ikonu (tooltip ile)
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
    Adım adım export wizard.
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
        self._last_brightness_effect = None  # Son seçilen parlaklık efekti: 'brighten' veya 'darken'
        
        self.setWindowTitle("Dışa Aktar Wizard")
        self.setMinimumWidth(800)
        self.setMinimumHeight(620)
        
        self._setup_ui()
        self._connect_signals()
        self._load_preview_image()
        self._update_navigation()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Başlık
        header = QHBoxLayout()
        self.step_label = QLabel("Adım 1/3: Dataset Split")
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
        
        self.back_btn = QPushButton("← Geri")
        self.back_btn.setStyleSheet("padding: 10px 25px;")
        nav_layout.addWidget(self.back_btn)
        
        nav_layout.addStretch()
        
        self.cancel_btn = QPushButton("İptal")
        self.cancel_btn.setStyleSheet("padding: 10px 20px;")
        nav_layout.addWidget(self.cancel_btn)
        
        self.next_btn = QPushButton("İleri →")
        self.next_btn.setStyleSheet("padding: 10px 25px; background-color: #0d6efd; color: white;")
        nav_layout.addWidget(self.next_btn)
        
        layout.addLayout(nav_layout)
    
    def _create_split_page(self) -> QWidget:
        """Step 1: Dataset Split."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        info = QLabel(f"📊 Toplam {len(self._image_files)} görsel")
        info.setStyleSheet("font-size: 14px; color: #2196F3; padding: 10px;")
        layout.addWidget(info)
        
        self.split_enabled = QCheckBox("Dataset Split'i Etkinleştir")
        self.split_enabled.setChecked(True)  # Default olarak aktif
        self.split_enabled.setStyleSheet("font-size: 13px; padding: 5px;")
        layout.addWidget(self.split_enabled)
        
        # Range slider
        self.split_group = QGroupBox("Bölme Oranları (sürükleyerek ayarlayın)")
        split_layout = QVBoxLayout(self.split_group)
        
        self.range_slider = RangeSlider()
        split_layout.addWidget(self.range_slider)
        
        # Özet label
        self.split_info = QLabel("Train: 70% | Validation: 20% | Test: 10%")
        self.split_info.setStyleSheet("font-size: 12px; color: #666; padding: 5px;")
        self.split_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        split_layout.addWidget(self.split_info)
        
        self.split_group.setEnabled(True)  # Default olarak aktif
        layout.addWidget(self.split_group)
        
        # Shuffle & Seed
        self.shuffle_group = QGroupBox("Karıştırma Ayarları")
        shuffle_layout = QVBoxLayout(self.shuffle_group)
        
        self.shuffle_check = QCheckBox("Verileri Karıştır (Shuffle)")
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
        
        self.shuffle_group.setEnabled(True)  # Default olarak aktif
        layout.addWidget(self.shuffle_group)
        
        # Etiketsiz dosyalar seçeneği
        self.unlabeled_group = QGroupBox("Etiketsiz Dosyalar")
        unlabeled_layout = QVBoxLayout(self.unlabeled_group)
        
        self.include_unlabeled = QCheckBox("Etiketsiz görselleri dahil et")
        self.include_unlabeled.setChecked(False)  # Default olarak dahil değil
        self.include_unlabeled.setToolTip("Devre dışı bırakırsan, sadece etiketli dosyalar export edilir")
        self.include_unlabeled.toggled.connect(self._on_unlabeled_toggled)  # Tüm bölümleri güncelle
        unlabeled_layout.addWidget(self.include_unlabeled)
        
        # Etiketsiz dosya sayısını göster
        unlabeled_count = self._count_unlabeled_files()
        labeled_count = len(self._image_files) - unlabeled_count
        self.unlabeled_info = QLabel(f"📊 {labeled_count} etiketli, {unlabeled_count} etiketsiz dosya")
        self.unlabeled_info.setStyleSheet("color: #666; font-size: 11px; margin-left: 20px;")
        unlabeled_layout.addWidget(self.unlabeled_info)
        
        layout.addWidget(self.unlabeled_group)
        
        # Görsel sayısı özeti
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
        
        # Sol panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        self.aug_enabled = QCheckBox("Augmentation'ı Etkinleştir")
        self.aug_enabled.setStyleSheet("font-size: 13px; padding: 5px;")
        left_layout.addWidget(self.aug_enabled)
        
        mult_layout = QHBoxLayout()
        mult_layout.addWidget(QLabel("Çarpan:"))
        self.aug_multiplier = QComboBox()
        self._update_multiplier_options()  # Görsel sayısıyla birlikte
        mult_layout.addWidget(self.aug_multiplier)
        mult_layout.addStretch()
        left_layout.addLayout(mult_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        
        # Resize
        resize_group = QGroupBox("Resize")
        resize_layout = QVBoxLayout(resize_group)
        
        self.resize_enabled = QCheckBox("Resize Aktif")
        resize_layout.addWidget(self.resize_enabled)
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Boyut:"))
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
        mode_layout.addWidget(QLabel("Mod:"))
        self.resize_mode = QComboBox()
        self.resize_mode.addItems([
            "Stretch to", "Fill (center crop)", "Fit within",
            "Fit (reflect edges)", "Fit (black edges)", "Fit (white edges)"
        ])
        mode_layout.addWidget(self.resize_mode)
        resize_layout.addLayout(mode_layout)
        settings_layout.addWidget(resize_group)
        
        # Augmentation sliders
        aug_group = QGroupBox("Augmentation Parametreleri")
        aug_layout = QVBoxLayout(aug_group)
        
        # Parlaklık - Roboflow tarzı Brighten/Darken checkboxları
        brightness_group = QGroupBox("Parlaklık")
        brightness_group.setToolTip(
            "Parlaklık: Görselin aydınlık/karanlık seviyesini ayarlar.\n\n"
            "• Brighten: Görseli aydınlatır\n"
            "• Darken: Görseli karartır\n"
            "• Değer %: Efekt yoğunluğu\n\n"
            "Farklı ışık koşullarında genelleme için kullanılır."
        )
        brightness_layout = QVBoxLayout(brightness_group)
        
        # Sürgü (0-99%)
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Değer:"))
        self.brightness_slider_value = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider_value.setRange(0, 99)
        self.brightness_slider_value.setValue(20)
        slider_layout.addWidget(self.brightness_slider_value, 1)
        self.brightness_value_label = QLabel("20%")
        self.brightness_value_label.setMinimumWidth(40)
        slider_layout.addWidget(self.brightness_value_label)
        brightness_layout.addLayout(slider_layout)
        
        # Checkbox'lar
        checkbox_layout = QHBoxLayout()
        self.brighten_checkbox = QCheckBox("Parlaklık (Brighten)")
        self.darken_checkbox = QCheckBox("Karanlık (Darken)")
        checkbox_layout.addWidget(self.brighten_checkbox)
        checkbox_layout.addWidget(self.darken_checkbox)
        checkbox_layout.addStretch()
        brightness_layout.addLayout(checkbox_layout)
        
        aug_layout.addWidget(brightness_group)
        
        self.contrast_slider = AugmentationSlider(
            "Kontrast", 50, 150, 120, "%",
            help_text="Kontrast: Açık ve koyu tonlar arasındaki farkı ayarlar.\n\n"
                      "• 100%: Orijinal kontrast\n"
                      "• <100%: Düşük kontrast (daha soluk)\n"
                      "• >100%: Yüksek kontrast (daha keskin)\n\n"
                      "Farklı aydınlatma koşullarında genelleme için kullanılır."
        )
        aug_layout.addWidget(self.contrast_slider)
        
        self.rotation_slider = AugmentationSlider(
            "Döndürme", 0, 45, 15, "°",
            help_text="Döndürme (Rotation): Görseli rastgele açılarla döndürür.\n\n"
                      "• 0°: Döndürme yok\n"
                      "• 15°: ±15° aralığında döndürme\n"
                      "• 45°: ±45° aralığında döndürme\n\n"
                      "Nesnelerin farklı açılardan görünmesini öğretir."
        )
        aug_layout.addWidget(self.rotation_slider)
        
        # Flip (yüzde kontrolü ile)
        flip_group = QGroupBox("Çevirme")
        flip_group.setToolTip(
            "Çevirme (Flip): Görseli ayna gibi yansıtır.\n\n"
            "• Yatay: Sol-sağ yansıtma\n"
            "• Dikey: Üst-alt yansıtma\n"
            "• Yüzde: Uygulanma olasılığı\n\n"
            "Simetrik nesnelerde ve farklı bakış açılarında genelleme sağlar."
        )
        flip_group.setCheckable(True)
        flip_group.setChecked(False)
        flip_layout = QFormLayout(flip_group)
        
        self.flip_enabled = flip_group
        
        self.hflip_percent_spin = QSpinBox()
        self.hflip_percent_spin.setRange(0, 100)
        self.hflip_percent_spin.setValue(50)
        self.hflip_percent_spin.setSuffix("%")
        flip_layout.addRow("Yatay:", self.hflip_percent_spin)
        
        self.vflip_percent_spin = QSpinBox()
        self.vflip_percent_spin.setRange(0, 100)
        self.vflip_percent_spin.setValue(50)
        self.vflip_percent_spin.setSuffix("%")
        flip_layout.addRow("Dikey:", self.vflip_percent_spin)
        
        aug_layout.addWidget(flip_group)
        
        self.blur_slider = AugmentationSlider(
            "Blur", 0, 50, 15, "",
            help_text="Blur (Bulanıklık): Görsele Gaussian bulanıklık ekler.\n\n"
                      "Birim: Kernel boyutu (piksel)\n\n"
                      "Odak dışı veya hareketli nesnelerle başa çıkmayı öğretir."
        )
        aug_layout.addWidget(self.blur_slider)
        
        self.noise_slider = AugmentationSlider(
            "Gürültü", 0, 50, 10, "",
            help_text="Gürültü (Noise): Görsele rastgele piksel gürültüsü ekler.\n\n"
                      "Birim: Standart sapma (sigma)\n"
                      "Piksel değerlerine ±sigma kadar rastgele ekleme yapılır.\n\n"
                      "Düşük kaliteli veya sensör gürültülü kameralarda genelleme için."
        )
        aug_layout.addWidget(self.noise_slider)
        
        self.hue_slider = AugmentationSlider(
            "Renk Tonu", -30, 30, 10, "°",
            help_text="Renk Tonu (Hue): Renk spektrumunda kaydırma yapar.\n\n"
                      "Farklı aydınlatma renk sıcaklıklarına uyum sağlar."
        )
        aug_layout.addWidget(self.hue_slider)
        
        # Grayscale (yüzde kontrolü ile)
        grayscale_group = QGroupBox("Gri Tonlama")
        grayscale_group.setToolTip(
            "Gri Tonlama (Grayscale): Görseli siyah-beyaz yapar.\n\n"
            "• Oran %: Gri tonlamaya dönüştürülecek görsel yüzdesi\n\n"
            "Renk bilgisi olmadan da nesne tanıma öğretir."
        )
        grayscale_group.setCheckable(True)
        grayscale_group.setChecked(False)
        grayscale_layout = QFormLayout(grayscale_group)
        
        self.grayscale_enabled = grayscale_group
        
        self.grayscale_percent_spin = QSpinBox()
        self.grayscale_percent_spin.setRange(0, 100)
        self.grayscale_percent_spin.setValue(15)
        self.grayscale_percent_spin.setSuffix("%")
        grayscale_layout.addRow("Oran:", self.grayscale_percent_spin)
        
        aug_layout.addWidget(grayscale_group)
        
        # YENİ: Exposure
        self.exposure_slider = AugmentationSlider(
            "Pozlama (Exposure)", 50, 200, 150, "%",
            help_text="Pozlama (Exposure/Gamma): Işık maruziyetini ayarlar.\n\n"
                      "• 100%: Orijinal\n"
                      "• <100%: Az pozlanmış (karanlık)\n"
                      "• >100%: Çok pozlanmış (aydınlık)\n\n"
                      "Parlaklıktan farklı olarak renk tonlarını korur."
        )
        aug_layout.addWidget(self.exposure_slider)
        
        # YENİ: Cutout - Tek checkbox, boyut, adet ve uygulama yüzdesi
        cutout_group = QGroupBox("Cutout")
        cutout_group.setToolTip(
            "Cutout: Görsele rastgele siyah kareler ekler.\n\n"
            "Birim: Görsel boyutunun yüzdesi\n"
            "• Boyut 10% = 640px görselde 64px kare\n\n"
            "• Adet: Eklenecek kare sayısı\n"
            "• Oran %: Uygulanma olasılığı\n\n"
            "Modelin eksik bilgiyle çalışmasını (occlusion robustness) öğretir.\n\n"
            "⚠ DİKKAT: YOLOv8 gibi bazı modern modeller, eğitim sırasında \n"
            "benzer teknikleri (örn: erasing) otomatik uygulayabilir.\n"
            "Bu işlemi hem burada hem eğitimde yapmak (çift uygulama),\n"
            "model başarısını olumsuz etkileyebilir."
        )
        cutout_group.setCheckable(True)
        cutout_group.setChecked(False)
        cutout_layout = QFormLayout(cutout_group)
        
        self.cutout_enabled = cutout_group
        
        self.cutout_size_spin = QSpinBox()
        self.cutout_size_spin.setRange(5, 50)
        self.cutout_size_spin.setValue(10)
        self.cutout_size_spin.setSuffix("%")
        cutout_layout.addRow("Boyut:", self.cutout_size_spin)
        
        self.cutout_count_spin = QSpinBox()
        self.cutout_count_spin.setRange(1, 25)
        self.cutout_count_spin.setValue(3)
        cutout_layout.addRow("Adet:", self.cutout_count_spin)
        
        self.cutout_apply_percent_spin = QSpinBox()
        self.cutout_apply_percent_spin.setRange(0, 100)
        self.cutout_apply_percent_spin.setValue(50)
        self.cutout_apply_percent_spin.setSuffix("%")
        cutout_layout.addRow("Oran:", self.cutout_apply_percent_spin)
        
        aug_layout.addWidget(cutout_group)
        
        # YENİ: Motion Blur
        self.motion_blur_slider = AugmentationSlider(
            "Hareket Bulanıklığı", 0, 30, 15, "",
            help_text="Hareket Bulanıklığı (Motion Blur): Yatay hareket efekti ekler.\n\n"
                      "Birim: Kernel boyutu (piksel)\n\n"
                      "Hareketli nesneleri algılamayı öğretir."
        )
        aug_layout.addWidget(self.motion_blur_slider)
        
        # YENİ: Shear - Tek checkbox, yatay ve dikey
        shear_group = QGroupBox("Shear (Eğiklik)")
        shear_group.setToolTip(
            "Shear (Eğiklik): Görseli yatay/dikey olarak eğer.\n\n"
            "• Yatay: Yatay eğiklik açısı\n"
            "• Dikey: Dikey eğiklik açısı\n\n"
            "Perspektif varyasyonu sağlar,\n"
            "farklı bakış açılarından genelleme öğretir."
        )
        shear_group.setCheckable(True)
        shear_group.setChecked(False)
        shear_layout = QFormLayout(shear_group)
        
        self.shear_enabled = shear_group
        
        self.shear_h_spin = QSpinBox()
        self.shear_h_spin.setRange(0, 45)
        self.shear_h_spin.setValue(10)
        self.shear_h_spin.setSuffix("°")
        shear_layout.addRow("Yatay:", self.shear_h_spin)
        
        self.shear_v_spin = QSpinBox()
        self.shear_v_spin.setRange(0, 45)
        self.shear_v_spin.setValue(10)
        self.shear_v_spin.setSuffix("°")
        shear_layout.addRow("Dikey:", self.shear_v_spin)
        
        aug_layout.addWidget(shear_group)
        
        settings_layout.addWidget(aug_group)
        settings_layout.addStretch()
        
        scroll.setWidget(settings_widget)
        left_layout.addWidget(scroll)
        
        main_layout.addWidget(left_panel, 1)
        
        # Sağ panel - Önizleme
        right_panel = QGroupBox("Canlı Önizleme")
        right_layout = QVBoxLayout(right_panel)
        
        self.preview_label = QLabel("Augmentation'ı aktifleştirin")
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
        
        format_group = QGroupBox("Export Formatı")
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
        type_layout.addWidget(QLabel("Tip:"))
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
        
        output_group = QGroupBox("Çıktı Klasörü")
        output_layout = QHBoxLayout(output_group)
        
        self.output_path = QLineEdit()
        if self._default_output_dir:
            self.output_path.setText(str(self._default_output_dir))
        self.output_path.setPlaceholderText("Çıktı klasörünü seçin...")
        output_layout.addWidget(self.output_path)
        
        self.browse_btn = QPushButton("📁 Gözat...")
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
        
        # Her slider için ayrı tracking
        # Parlaklık - yeni UI
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
        
        # Flip group (yüzde kontrolü ile)
        self.flip_enabled.toggled.connect(lambda: self._on_slider_changed('flip'))
        self.hflip_percent_spin.valueChanged.connect(lambda: self._on_slider_changed('flip'))
        self.vflip_percent_spin.valueChanged.connect(lambda: self._on_slider_changed('flip'))
        
        # Grayscale group (yüzde kontrolü ile)
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
        steps = ["Dataset Split", "Augmentation", "Format & Export"]
        self.step_label.setText(f"Adım {current + 1}/3: {steps[current]}")
        
        self.back_btn.setVisible(current > 0)
        
        if current == 2:
            self.next_btn.setText("📦 Dışa Aktar")
            self.next_btn.setStyleSheet("padding: 10px 25px; background-color: #4CAF50; color: white; font-weight: bold;")
        else:
            self.next_btn.setText("İleri →")
            self.next_btn.setStyleSheet("padding: 10px 25px; background-color: #0d6efd; color: white;")
    
    def _on_split_toggled(self, enabled):
        self.split_group.setEnabled(enabled)
        self.shuffle_group.setEnabled(enabled)
        self._update_split_summary()
    
    def _on_range_changed(self, train, val, test):
        self.split_info.setText(f"Train: {train}% | Validation: {val}% | Test: {test}%")
        self._update_split_summary()
    
    def _update_split_summary(self):
        # Filtrelenmiş dosya sayısını kullan
        filtered_files = self._get_filtered_image_files()
        total = len(filtered_files)
        
        if not self.split_enabled.isChecked():
            self.split_summary.setText(f"Split devre dışı - {total} görsel tek klasöre yazılacak")
            return
        
        train_pct, val_pct, test_pct = self.range_slider.values()
        train = int(total * train_pct / 100)
        val = int(total * val_pct / 100)
        test = total - train - val
        
        self.split_summary.setText(f"📂 Train: {train} görsel | Val: {val} görsel | Test: {test} görsel")
    
    def _on_unlabeled_toggled(self, checked: bool):
        """Etiketsiz checkbox değiştiğinde tüm bölümleri güncelle."""
        self._update_split_summary()
        self._update_multiplier_options()
        # Export sayfasındaysa summary'yi de güncelle
        if self.stack.currentIndex() == 2:
            self._update_export_summary()
    
    def _update_multiplier_options(self):
        """Çarpan seçeneklerini görsel sayısıyla güncelle."""
        # Filtrelenmiş dosya sayısını kullan
        filtered = self._get_filtered_image_files()
        count = len(filtered)
        self.aug_multiplier.clear()
        for mult in [2, 3, 5, 8, 10, 15]:
            # Roboflow tarzı: 1 orijinal + (mult-1) augmented = toplam mult görsel
            self.aug_multiplier.addItem(f"{mult}x → {count * mult} görsel (1 orijinal + {mult-1} augmented)")
    
    def _on_slider_changed(self, slider_name: str):
        """Hangi slider'ın değiştiğini takip et ve önizlemeyi güncelle."""
        self._last_changed_slider = slider_name
        self._schedule_preview()
    
    def _on_aug_toggled(self, enabled):
        if enabled:
            self._last_changed_slider = None  # Tümünü göster
            self._update_preview()
        else:
            self.preview_label.setText("Augmentation'ı aktifleştirin")
    
    def _on_brightness_value_changed(self, value):
        """Parlaklık slider değeri değiştiğinde."""
        self.brightness_value_label.setText(f"{value}%")
        self._schedule_preview()
    
    def _on_brightness_checkbox_changed(self, checkbox_type: str):
        """Brighten veya Darken checkbox değiştiğinde."""
        # Son seçilen efekti takip et (canlı önizleme için)
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
                # Önce binary okuma dene (Türkçe karakter sorununu önler)
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
            # Son ayarlanan augmentation'ı belirle
            last_slider = getattr(self, '_last_changed_slider', None)
            config = self._get_single_augmentation_config(last_slider)
            aug_img = self._augmentor.preview(self._preview_image.copy(), config)
            
            if config.resize.enabled:
                aug_img, _ = self._augmentor.resize_image(aug_img, config.resize)
            
            # BGR -> RGB
            rgb_img = cv2.cvtColor(aug_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_img.shape
            bytes_per_line = ch * w
            
            # QImage oluştur
            qt_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            qt_img = qt_img.copy()  # Data'yı kopyala
            
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
            self, "Çıktı Klasörü Seç",
            str(self._default_output_dir) if self._default_output_dir else ""
        )
        if folder:
            self.output_path.setText(folder)
    
    def _update_export_summary(self):
        # Filtrelenmiş dosya sayısını kullan
        filtered = self._get_filtered_image_files()
        total = len(filtered)
        
        if self.aug_enabled.isChecked():
            mult_text = self.aug_multiplier.currentText().split('x')[0]
            mult = int(mult_text) if mult_text.isdigit() else 2
            total *= mult
        
        parts = [f"📊 Toplam {total} görsel export edilecek"]
        
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
            0: ResizeMode.STRETCH, 1: ResizeMode.FILL_CENTER_CROP,
            2: ResizeMode.FIT_WITHIN, 3: ResizeMode.FIT_REFLECT,
            4: ResizeMode.FIT_BLACK, 5: ResizeMode.FIT_WHITE
        }
        
        # "2x → 24 görsel" formatından sadece çarpanı al
        mult_text = self.aug_multiplier.currentText().split('x')[0]
        multiplier = int(mult_text) if mult_text.isdigit() else 2
        
        return AugmentationConfig(
            enabled=self.aug_enabled.isChecked(),
            multiplier=multiplier,
            # Yeni parlaklık sistemi - Brighten ve Darken ayrı
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
        """Sadece belirtilen augmentation'ı aktif eden config döndür."""
        resize_mode_map = {
            0: ResizeMode.STRETCH, 1: ResizeMode.FILL_CENTER_CROP,
            2: ResizeMode.FIT_WITHIN, 3: ResizeMode.FIT_REFLECT,
            4: ResizeMode.FIT_BLACK, 5: ResizeMode.FIT_WHITE
        }
        
        # Eğer slider_name None ise, tüm aktif augmentation'ları göster
        show_all = slider_name is None
        
        return AugmentationConfig(
            enabled=True,
            multiplier=1,
            # Parlaklık - canlı önizleme için son seçilen efekti göster
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
            # VOC için de YOLO exporter kullanılıyor (class_manager için)
            # Gerçek format export worker'da belirleniyor
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
        
        # Etiketsiz dosya filtreleme
        image_files = self._get_filtered_image_files()
        
        annotations_dict = {}
        for image_path in image_files:
            key = str(image_path)
            if key in self._annotation_manager._annotations:
                annotations_dict[key] = self._annotation_manager._annotations[key]
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Export başlatılıyor...")
        self.next_btn.setEnabled(False)
        
        # Format belirleme
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
        self.status_label.setText(f"Export ediliyor: {current}/{total}")
    
    def _on_export_finished(self, count):
        self.progress_bar.setValue(self.progress_bar.maximum())
        QMessageBox.information(self, "Başarılı", f"✓ {count} görsel dışa aktarıldı.\n\nKonum: {self.output_path.text()}")
        self.accept()
    
    def _on_export_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        self.next_btn.setEnabled(True)
        QMessageBox.critical(self, "Hata", f"Export hatası:\n{error_msg}")
    
    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        super().closeEvent(event)
    
    def _count_unlabeled_files(self) -> int:
        """Etiketsiz dosya sayısını hesapla."""
        unlabeled = 0
        
        if not self._image_files:
            return 0
        
        # Labels klasörünü bul
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
