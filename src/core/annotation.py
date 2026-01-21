"""
Annotation Data Models
======================
Bounding Box, Polygon and other annotation types.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


class AnnotationType(Enum):
    """Annotation type."""
    BBOX = "bbox"           # Bounding Box
    POLYGON = "polygon"     # Polygon
    POINT = "point"         # Point


@dataclass
class BoundingBox:
    """
    Bounding Box annotation.
    Coordinates are stored as normalized values (0-1).
    """
    class_id: int
    x_center: float    # Center X (normalized)
    y_center: float    # Center Y (normalized)
    width: float       # Width (normalized)
    height: float      # Height (normalized)
    
    @classmethod
    def from_corners(
        cls, 
        class_id: int,
        x1: float, y1: float,  # Top-left corner
        x2: float, y2: float,  # Bottom-right corner
        img_width: int,
        img_height: int
    ) -> "BoundingBox":
        """Creates BoundingBox from corner coordinates."""
        # Normalize
        x_center = ((x1 + x2) / 2) / img_width
        y_center = ((y1 + y2) / 2) / img_height
        width = abs(x2 - x1) / img_width
        height = abs(y2 - y1) / img_height
        
        return cls(class_id, x_center, y_center, width, height)
    
    def to_corners(self, img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """Converts to pixel coordinates (x1, y1, x2, y2)."""
        w = self.width * img_width
        h = self.height * img_height
        cx = self.x_center * img_width
        cy = self.y_center * img_height
        
        x1 = int(cx - w / 2)
        y1 = int(cy - h / 2)
        x2 = int(cx + w / 2)
        y2 = int(cy + h / 2)
        
        return (x1, y1, x2, y2)
    
    def to_yolo_format(self) -> str:
        """Returns string in YOLO format."""
        return f"{self.class_id} {self.x_center:.6f} {self.y_center:.6f} {self.width:.6f} {self.height:.6f}"


@dataclass 
class Polygon:
    """
    Polygon annotation.
    Points are stored as normalized coordinates.
    """
    class_id: int
    points: List[Tuple[float, float]] = field(default_factory=list)  # [(x, y), ...]
    
    def add_point(self, x: float, y: float, img_width: int, img_height: int):
        """Adds a normalized point."""
        self.points.append((x / img_width, y / img_height))
        
    def to_pixel_points(self, img_width: int, img_height: int) -> List[Tuple[int, int]]:
        """Converts to pixel coordinates."""
        return [
            (int(x * img_width), int(y * img_height))
            for x, y in self.points
        ]


@dataclass
class ImageAnnotations:
    """Holds all annotations for an image."""
    image_path: str
    image_width: int
    image_height: int
    bboxes: List[BoundingBox] = field(default_factory=list)
    polygons: List[Polygon] = field(default_factory=list)
