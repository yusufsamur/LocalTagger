"""
Exporter Module
===============
Annotation export operations in various formats.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import json
import datetime

from .annotation import BoundingBox, Polygon, ImageAnnotations
from .class_manager import ClassManager


class BaseExporter(ABC):
    """Base exporter class."""
    
    def __init__(self, class_manager: ClassManager):
        self.class_manager = class_manager
        self.progress_callback: Optional[Callable[[int, int], None]] = None
    
    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """Sets progress callback. callback(current, total)"""
        self.progress_callback = callback
    
    def _report_progress(self, current: int, total: int):
        """Report progress."""
        if self.progress_callback:
            self.progress_callback(current, total)
    
    @abstractmethod
    def export(
        self, 
        annotations_dict: Dict[str, ImageAnnotations], 
        output_dir: Path,
        image_files: List[Path]
    ) -> int:
        """
        Exports annotations.
        
        Args:
            annotations_dict: {image_path: ImageAnnotations}
            output_dir: Output directory
            image_files: List of image files
            
        Returns:
            Count of exported files
        """
        pass
    
    @abstractmethod
    def get_format_name(self) -> str:
        """Returns format name."""
        pass


class YOLOExporter(BaseExporter):
    """
    Export in YOLO format (v5-v11 same format).
    
    BBox: class_id x_center y_center width height
    Polygon: class_id x1 y1 x2 y2 x3 y3 ...
    """
    
    def __init__(self, class_manager: ClassManager, version: str = "v8"):
        super().__init__(class_manager)
        self.version = version  # For info, format is same
    
    def get_format_name(self) -> str:
        return f"YOLO {self.version}"
    
    def export(
        self, 
        annotations_dict: Dict[str, ImageAnnotations], 
        output_dir: Path,
        image_files: List[Path]
    ) -> int:
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        total = len(image_files)
        
        for i, image_path in enumerate(image_files):
            key = str(image_path)
            annotations = annotations_dict.get(key)
            
            if annotations is None:
                annotations = ImageAnnotations(
                    image_path=key, 
                    image_width=0, 
                    image_height=0
                )
            
            # Create TXT file
            txt_path = output_dir / f"{image_path.stem}.txt"
            lines = []
            
            # Write BBoxes
            for bbox in annotations.bboxes:
                lines.append(
                    f"{bbox.class_id} {bbox.x_center:.6f} {bbox.y_center:.6f} "
                    f"{bbox.width:.6f} {bbox.height:.6f}"
                )
            
            # Write Polygons
            for polygon in annotations.polygons:
                if len(polygon.points) >= 3:
                    points_str = " ".join(
                        f"{x:.6f} {y:.6f}" for x, y in polygon.points
                    )
                    lines.append(f"{polygon.class_id} {points_str}")
            
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            count += 1
            self._report_progress(i + 1, total)
        
        # Save classes.txt
        self._save_classes_txt(output_dir)
        
        return count
    
    def _save_classes_txt(self, output_dir: Path):
        """Save classes.txt file."""
        classes_path = output_dir / "classes.txt"
        lines = []
        for cls in self.class_manager.classes:
            lines.append(cls.name)
        with open(classes_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


class COCOExporter(BaseExporter):
    """
    Export in COCO JSON format.
    
    Structure:
    {
        "info": {...},
        "licenses": [...],
        "categories": [...],
        "images": [...],
        "annotations": [...]
    }
    """
    
    def get_format_name(self) -> str:
        return "COCO JSON"
    
    def export(
        self, 
        annotations_dict: Dict[str, ImageAnnotations], 
        output_dir: Path,
        image_files: List[Path]
    ) -> int:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        coco_data = {
            "info": {
                "description": "LocalTagger Export",
                "version": "1.0",
                "year": datetime.datetime.now().year,
                "date_created": datetime.datetime.now().isoformat()
            },
            "licenses": [],
            "categories": [],
            "images": [],
            "annotations": []
        }
        
        # Add categories
        for cls in self.class_manager.classes:
            coco_data["categories"].append({
                "id": cls.id,
                "name": cls.name,
                "supercategory": "object"
            })
        
        annotation_id = 1
        total = len(image_files)
        
        for i, image_path in enumerate(image_files):
            key = str(image_path)
            annotations = annotations_dict.get(key)
            
            if annotations is None:
                annotations = ImageAnnotations(
                    image_path=key, 
                    image_width=0, 
                    image_height=0
                )
            
            image_id = i + 1
            
            # Image info
            coco_data["images"].append({
                "id": image_id,
                "file_name": image_path.name,
                "width": annotations.image_width,
                "height": annotations.image_height
            })
            
            img_w = annotations.image_width or 1
            img_h = annotations.image_height or 1
            
            # BBox annotations
            for bbox in annotations.bboxes:
                # COCO bbox: [x, y, width, height] (top-left corner + size)
                x = (bbox.x_center - bbox.width / 2) * img_w
                y = (bbox.y_center - bbox.height / 2) * img_h
                w = bbox.width * img_w
                h = bbox.height * img_h
                area = w * h
                
                coco_data["annotations"].append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": bbox.class_id,
                    "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                    "area": round(area, 2),
                    "iscrowd": 0
                })
                annotation_id += 1
            
            # Polygon annotations (segmentation)
            for polygon in annotations.polygons:
                if len(polygon.points) >= 3:
                    # Segmentation: [x1, y1, x2, y2, ...] (flat list)
                    segmentation = []
                    for x, y in polygon.points:
                        segmentation.extend([
                            round(x * img_w, 2), 
                            round(y * img_h, 2)
                        ])
                    
                    # Calculate bounding box
                    xs = [p[0] * img_w for p in polygon.points]
                    ys = [p[1] * img_h for p in polygon.points]
                    x_min, x_max = min(xs), max(xs)
                    y_min, y_max = min(ys), max(ys)
                    w = x_max - x_min
                    h = y_max - y_min
                    area = w * h  # Approximate area
                    
                    coco_data["annotations"].append({
                        "id": annotation_id,
                        "image_id": image_id,
                        "category_id": polygon.class_id,
                        "segmentation": [segmentation],
                        "bbox": [round(x_min, 2), round(y_min, 2), round(w, 2), round(h, 2)],
                        "area": round(area, 2),
                        "iscrowd": 0
                    })
                    annotation_id += 1
            
            self._report_progress(i + 1, total)
        
        # Save JSON file
        json_path = output_dir / "annotations.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(coco_data, f, indent=2, ensure_ascii=False)
        
        return len(image_files)


class CustomTXTExporter(BaseExporter):
    """
    Export in User Defined TXT format.
    
    Supported placeholders:
    - {class_id}, {class_name}
    - {x_center}, {y_center}, {width}, {height}
    - {x1}, {y1}, {x2}, {y2} (normalized corners)
    - {x1_pixel}, {y1_pixel}, {x2_pixel}, {y2_pixel}
    """
    
    def __init__(self, class_manager: ClassManager, format_string: str):
        super().__init__(class_manager)
        self.format_string = format_string
    
    def get_format_name(self) -> str:
        return "Custom TXT"
    
    def export(
        self, 
        annotations_dict: Dict[str, ImageAnnotations], 
        output_dir: Path,
        image_files: List[Path]
    ) -> int:
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        total = len(image_files)
        
        for i, image_path in enumerate(image_files):
            key = str(image_path)
            annotations = annotations_dict.get(key)
            
            if annotations is None:
                annotations = ImageAnnotations(
                    image_path=key, 
                    image_width=0, 
                    image_height=0
                )
            
            txt_path = output_dir / f"{image_path.stem}.txt"
            lines = []
            
            img_w = annotations.image_width or 1
            img_h = annotations.image_height or 1
            
            # Write BBoxes
            for bbox in annotations.bboxes:
                line = self._format_bbox(bbox, img_w, img_h)
                lines.append(line)
            
            # Write Polygons as BBox (bounding box)
            for polygon in annotations.polygons:
                if len(polygon.points) >= 3:
                    # Convert Polygon to bounding box
                    xs = [p[0] for p in polygon.points]
                    ys = [p[1] for p in polygon.points]
                    x_min, x_max = min(xs), max(xs)
                    y_min, y_max = min(ys), max(ys)
                    
                    fake_bbox = BoundingBox(
                        class_id=polygon.class_id,
                        x_center=(x_min + x_max) / 2,
                        y_center=(y_min + y_max) / 2,
                        width=x_max - x_min,
                        height=y_max - y_min
                    )
                    line = self._format_bbox(fake_bbox, img_w, img_h)
                    lines.append(line)
            
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            count += 1
            self._report_progress(i + 1, total)
        
        return count
    
    def _format_bbox(self, bbox: BoundingBox, img_w: int, img_h: int) -> str:
        """Format bbox according to format string."""
        # Corner coordinates (normalized)
        x1 = bbox.x_center - bbox.width / 2
        y1 = bbox.y_center - bbox.height / 2
        x2 = bbox.x_center + bbox.width / 2
        y2 = bbox.y_center + bbox.height / 2
        
        # Pixel coordinates
        x1_pixel = int(x1 * img_w)
        y1_pixel = int(y1 * img_h)
        x2_pixel = int(x2 * img_w)
        y2_pixel = int(y2 * img_h)
        
        # Class name
        label_class = self.class_manager.get_by_id(bbox.class_id)
        class_name = label_class.name if label_class else str(bbox.class_id)
        
        # Fill format string
        return self.format_string.format(
            class_id=bbox.class_id,
            class_name=class_name,
            x_center=f"{bbox.x_center:.6f}",
            y_center=f"{bbox.y_center:.6f}",
            width=f"{bbox.width:.6f}",
            height=f"{bbox.height:.6f}",
            x1=f"{x1:.6f}",
            y1=f"{y1:.6f}",
            x2=f"{x2:.6f}",
            y2=f"{y2:.6f}",
            x1_pixel=x1_pixel,
            y1_pixel=y1_pixel,
            x2_pixel=x2_pixel,
            y2_pixel=y2_pixel
        )


class CustomJSONExporter(BaseExporter):
    """
    Export based on User Defined JSON template.
    
    Supported placeholders in template:
    - {{class_id}}, {{class_name}}
    - {{x_center}}, {{y_center}}, {{width}}, {{height}}
    - {{x1}}, {{y1}}, {{x2}}, {{y2}}
    - {{image_path}}, {{image_width}}, {{image_height}}
    - {{annotations}} - Special marker for Annotation list
    """
    
    def __init__(self, class_manager: ClassManager, template: Dict[str, Any]):
        super().__init__(class_manager)
        self.template = template
    
    def get_format_name(self) -> str:
        return "Custom JSON"
    
    def export(
        self, 
        annotations_dict: Dict[str, ImageAnnotations], 
        output_dir: Path,
        image_files: List[Path]
    ) -> int:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        result = {
            "info": {
                "description": "LocalTagger Custom Export",
                "date": datetime.datetime.now().isoformat()
            },
            "images": []
        }
        
        total = len(image_files)
        
        for i, image_path in enumerate(image_files):
            key = str(image_path)
            annotations = annotations_dict.get(key)
            
            if annotations is None:
                annotations = ImageAnnotations(
                    image_path=key, 
                    image_width=0, 
                    image_height=0
                )
            
            img_w = annotations.image_width or 1
            img_h = annotations.image_height or 1
            
            image_data = {
                "file_name": image_path.name,
                "width": img_w,
                "height": img_h,
                "annotations": []
            }
            
            # BBoxes
            for bbox in annotations.bboxes:
                ann_data = self._format_annotation(bbox, img_w, img_h)
                image_data["annotations"].append(ann_data)
            
            # Polygons
            for polygon in annotations.polygons:
                if len(polygon.points) >= 3:
                    ann_data = self._format_polygon(polygon, img_w, img_h)
                    image_data["annotations"].append(ann_data)
            
            result["images"].append(image_data)
            self._report_progress(i + 1, total)
        
        # Save JSON file
        json_path = output_dir / "custom_annotations.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        return len(image_files)
    
    def _format_annotation(self, bbox: BoundingBox, img_w: int, img_h: int) -> Dict:
        """Format annotation for BBox."""
        label_class = self.class_manager.get_by_id(bbox.class_id)
        class_name = label_class.name if label_class else str(bbox.class_id)
        
        # Corner coordinates
        x1 = bbox.x_center - bbox.width / 2
        y1 = bbox.y_center - bbox.height / 2
        x2 = bbox.x_center + bbox.width / 2
        y2 = bbox.y_center + bbox.height / 2
        
        return {
            "type": "bbox",
            "class_id": bbox.class_id,
            "class_name": class_name,
            "x_center": round(bbox.x_center, 6),
            "y_center": round(bbox.y_center, 6),
            "width": round(bbox.width, 6),
            "height": round(bbox.height, 6),
            "x1": round(x1, 6),
            "y1": round(y1, 6),
            "x2": round(x2, 6),
            "y2": round(y2, 6),
            "x1_pixel": int(x1 * img_w),
            "y1_pixel": int(y1 * img_h),
            "x2_pixel": int(x2 * img_w),
            "y2_pixel": int(y2 * img_h)
        }
    
    def _format_polygon(self, polygon: Polygon, img_w: int, img_h: int) -> Dict:
        """Format annotation for Polygon."""
        label_class = self.class_manager.get_by_id(polygon.class_id)
        class_name = label_class.name if label_class else str(polygon.class_id)
        
        # Normalized and pixel coordinates
        points_normalized = [
            {"x": round(x, 6), "y": round(y, 6)} 
            for x, y in polygon.points
        ]
        points_pixel = [
            {"x": int(x * img_w), "y": int(y * img_h)} 
            for x, y in polygon.points
        ]
        
        # Calculate bounding box
        xs = [p[0] for p in polygon.points]
        ys = [p[1] for p in polygon.points]
        
        return {
            "type": "polygon",
            "class_id": polygon.class_id,
            "class_name": class_name,
            "points": points_normalized,
            "points_pixel": points_pixel,
            "bbox": {
                "x1": round(min(xs), 6),
                "y1": round(min(ys), 6),
                "x2": round(max(xs), 6),
                "y2": round(max(ys), 6)
            }
        }
