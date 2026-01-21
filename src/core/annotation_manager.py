"""
Annotation Management
=====================
Manages all image annotations, caching and saving operations.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .annotation import BoundingBox, Polygon, ImageAnnotations


class AnnotationManager:
    """
    Manages annotations for all images.
    Keeps in-memory cache and saves to disk.
    """
    
    MAX_UNDO_STACK = 50  # Maximum undo count
    
    def __init__(self):
        # {image_path: ImageAnnotations}
        self._annotations: Dict[str, ImageAnnotations] = {}
        # Change tracking
        self._dirty: set = set()  # Unsaved changes
        # Undo stack: [(image_path, action_type, data)]
        self._undo_stack: List[tuple] = []
        # Redo stack: [(image_path, action_type, data)]
        self._redo_stack: List[tuple] = []
        
    def get_annotations(self, image_path: str | Path) -> ImageAnnotations:
        """
        Returns annotations for an image.
        Creates empty ImageAnnotations if not exists.
        """
        key = str(image_path)
        
        if key not in self._annotations:
            self._annotations[key] = ImageAnnotations(
                image_path=key,
                image_width=0,
                image_height=0
            )
        return self._annotations[key]
    
    def set_image_size(self, image_path: str | Path, width: int, height: int):
        """Sets image dimensions."""
        annotations = self.get_annotations(image_path)
        annotations.image_width = width
        annotations.image_height = height
        
    def add_bbox(self, image_path: str | Path, bbox: BoundingBox):
        """Adds BBox for image."""
        annotations = self.get_annotations(image_path)
        # Save for Undo
        self._push_undo(str(image_path), 'add_bbox', len(annotations.bboxes))
        annotations.bboxes.append(bbox)
        self._mark_dirty(image_path)
        
    def add_polygon(self, image_path: str | Path, polygon: Polygon):
        """Adds Polygon for image."""
        annotations = self.get_annotations(image_path)
        # Save for Undo
        self._push_undo(str(image_path), 'add_polygon', len(annotations.polygons))
        annotations.polygons.append(polygon)
        self._mark_dirty(image_path)
        
    def remove_bbox(self, image_path: str | Path, index: int) -> bool:
        """Removes BBox by index."""
        annotations = self.get_annotations(image_path)
        if 0 <= index < len(annotations.bboxes):
            # Save for Undo
            removed_bbox = annotations.bboxes[index]
            self._push_undo(str(image_path), 'remove_bbox', (index, removed_bbox))
            annotations.bboxes.pop(index)
            self._mark_dirty(image_path)
            return True
        return False
    
    def remove_polygon(self, image_path: str | Path, index: int) -> bool:
        """Removes Polygon by index."""
        annotations = self.get_annotations(image_path)
        if 0 <= index < len(annotations.polygons):
            # Save for Undo
            removed_polygon = annotations.polygons[index]
            self._push_undo(str(image_path), 'remove_polygon', (index, removed_polygon))
            annotations.polygons.pop(index)
            self._mark_dirty(image_path)
            return True
        return False
    
    def clear_annotations(self, image_path: str | Path):
        """Clears all annotations for the image."""
        key = str(image_path)
        if key in self._annotations:
            self._annotations[key].bboxes.clear()
            self._annotations[key].polygons.clear()
            self._mark_dirty(image_path)
    
    def _mark_dirty(self, image_path: str | Path):
        """Mark image as 'unsaved'."""
        self._dirty.add(str(image_path))
    
    def _push_undo(self, image_path: str, action: str, data):
        """Add action to Undo stack."""
        self._undo_stack.append((image_path, action, data))
        # Exceed stack limit
        if len(self._undo_stack) > self.MAX_UNDO_STACK:
            self._undo_stack.pop(0)
        # Clear redo stack when new action is added
        self._redo_stack.clear()
    
    def undo(self) -> tuple:
        """
        Undo last action.
        Returns: (image_path, success) tuple - which image affected and success status
        """
        if not self._undo_stack:
            return (None, False)
        
        image_path, action, data = self._undo_stack.pop()
        annotations = self.get_annotations(image_path)
        
        # Record reverse action for Redo
        redo_action = None
        redo_data = None
        
        if action == 'add_bbox':
            # Remove added bbox
            index = data
            if 0 <= index < len(annotations.bboxes):
                removed = annotations.bboxes.pop(index)
                redo_action = 'remove_bbox'
                redo_data = (index, removed)
        elif action == 'add_polygon':
            # Remove added polygon
            index = data
            if 0 <= index < len(annotations.polygons):
                removed = annotations.polygons.pop(index)
                redo_action = 'remove_polygon'
                redo_data = (index, removed)
        elif action == 'remove_bbox':
            # Add back removed bbox
            index, bbox = data
            annotations.bboxes.insert(index, bbox)
            redo_action = 'add_bbox'
            redo_data = index
        elif action == 'remove_polygon':
            # Add back removed polygon
            index, polygon = data
            annotations.polygons.insert(index, polygon)
            redo_action = 'add_polygon'
            redo_data = index
        else:
            return (image_path, False)
        
        # Add to Redo stack
        if redo_action:
            self._redo_stack.append((image_path, redo_action, redo_data))
        
        self._mark_dirty(image_path)
        return (image_path, True)
    
    def can_undo(self) -> bool:
        """Is there any action to undo?"""
        return len(self._undo_stack) > 0
    
    def redo(self) -> tuple:
        """
        Redo last undone action.
        Returns: (image_path, success) tuple
        """
        if not self._redo_stack:
            return (None, False)
        
        image_path, action, data = self._redo_stack.pop()
        annotations = self.get_annotations(image_path)
        
        # Save for Undo (should not affect redo stack)
        undo_action = None
        undo_data = None
        
        if action == 'add_bbox':
            # Remove added bbox
            index = data
            if 0 <= index < len(annotations.bboxes):
                removed = annotations.bboxes.pop(index)
                undo_action = 'remove_bbox'
                undo_data = (index, removed)
        elif action == 'add_polygon':
            # Remove added polygon
            index = data
            if 0 <= index < len(annotations.polygons):
                removed = annotations.polygons.pop(index)
                undo_action = 'remove_polygon'
                undo_data = (index, removed)
        elif action == 'remove_bbox':
            # Add back removed bbox
            index, bbox = data
            annotations.bboxes.insert(index, bbox)
            undo_action = 'add_bbox'
            undo_data = index
        elif action == 'remove_polygon':
            # Add back removed polygon
            index, polygon = data
            annotations.polygons.insert(index, polygon)
            undo_action = 'add_polygon'
            undo_data = index
        else:
            return (image_path, False)
        
        # Add to Undo stack (without clearing redo_stack)
        if undo_action:
            self._undo_stack.append((image_path, undo_action, undo_data))
        
        self._mark_dirty(image_path)
        return (image_path, True)
    
    def can_redo(self) -> bool:
        """Is there any action to redo?"""
        return len(self._redo_stack) > 0
        
    def is_dirty(self, image_path: str | Path = None) -> bool:
        """Is there any unsaved change?"""
        if image_path is None:
            return len(self._dirty) > 0
        return str(image_path) in self._dirty
    
    def mark_saved(self, image_path: str | Path = None):
        """Mark as saved."""
        if image_path is None:
            self._dirty.clear()
        else:
            self._dirty.discard(str(image_path))
    
    def get_all_annotation_count(self) -> int:
        """Returns total annotation count."""
        total = 0
        for ann in self._annotations.values():
            total += len(ann.bboxes) + len(ann.polygons)
        return total
    
    # ─────────────────────────────────────────────────────────────────
    # YOLO File Operations
    # ─────────────────────────────────────────────────────────────────
    
    def save_yolo(self, image_path: str | Path, output_dir: Path):
        """
        Saves annotations for a single image in YOLO format.
        
        Args:
            image_path: Source image path
            output_dir: Output directory
        """
        annotations = self.get_annotations(image_path)
        
        # Create txt filename from image name
        image_name = Path(image_path).stem
        txt_path = output_dir / f"{image_name}.txt"
        
        lines = []
        
        # Write BBoxes
        for bbox in annotations.bboxes:
            lines.append(bbox.to_yolo_format())
            
        # Write Polygons (YOLO segmentation format)
        for polygon in annotations.polygons:
            if len(polygon.points) >= 3:
                points_str = " ".join(f"{x:.6f} {y:.6f}" for x, y in polygon.points)
                lines.append(f"{polygon.class_id} {points_str}")
        
        # Write file
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            
        self.mark_saved(image_path)
    
    def load_yolo(self, image_path: str | Path, width: int, height: int):
        """
        Loads annotations from YOLO txt file.
        
        Args:
            image_path: Image path (txt is searched in same folder)
            width: Image width
            height: Image height
        """
        txt_path = Path(image_path).with_suffix(".txt")
        
        if not txt_path.exists():
            return
            
        annotations = self.get_annotations(image_path)
        annotations.image_width = width
        annotations.image_height = height
        annotations.bboxes.clear()
        annotations.polygons.clear()
        
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                    
                class_id = int(parts[0])
                
                if len(parts) == 5:
                    # BBox format: class x_center y_center width height
                    bbox = BoundingBox(
                        class_id=class_id,
                        x_center=float(parts[1]),
                        y_center=float(parts[2]),
                        width=float(parts[3]),
                        height=float(parts[4])
                    )
                    annotations.bboxes.append(bbox)
                else:
                    # Polygon format: class x1 y1 x2 y2 ...
                    points = []
                    for i in range(1, len(parts), 2):
                        if i + 1 < len(parts):
                            points.append((float(parts[i]), float(parts[i+1])))
                    if len(points) >= 3:
                        polygon = Polygon(class_id=class_id, points=points)
                        annotations.polygons.append(polygon)
    
    def _load_from_path(self, image_path: str | Path, txt_path: Path, width: int, height: int):
        """
        Loads annotations from a specific txt file.
        
        Args:
            image_path: Image path
            txt_path: YOLO txt file path
            width: Image width
            height: Image height
        """
        if not txt_path.exists():
            return
            
        annotations = self.get_annotations(image_path)
        annotations.image_width = width
        annotations.image_height = height
        annotations.bboxes.clear()
        annotations.polygons.clear()
        
        with open(txt_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                    
                class_id = int(parts[0])
                
                if len(parts) == 5:
                    # BBox format
                    bbox = BoundingBox(
                        class_id=class_id,
                        x_center=float(parts[1]),
                        y_center=float(parts[2]),
                        width=float(parts[3]),
                        height=float(parts[4])
                    )
                    annotations.bboxes.append(bbox)
                else:
                    # Polygon format
                    points = []
                    for i in range(1, len(parts), 2):
                        if i + 1 < len(parts):
                            points.append((float(parts[i]), float(parts[i+1])))
                    if len(points) >= 3:
                        polygon = Polygon(class_id=class_id, points=points)
                        annotations.polygons.append(polygon)
    
    def clear(self):
        """Clears all annotations."""
        self._annotations.clear()
        self._dirty.clear()
