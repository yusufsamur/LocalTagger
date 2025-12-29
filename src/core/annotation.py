"""
Etiket Veri Modelleri
=====================
Bounding Box, Polygon ve diğer etiket tipleri.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from enum import Enum


class AnnotationType(Enum):
    """Etiket tipi."""
    BBOX = "bbox"           # Bounding Box (Kutu)
    POLYGON = "polygon"     # Polygon (Çokgen)
    POINT = "point"         # Nokta


@dataclass
class BoundingBox:
    """
    Bounding Box (Sınırlayıcı Kutu) etiketi.
    Koordinatlar normalize edilmiş (0-1 arası) olarak saklanır.
    """
    class_id: int
    x_center: float    # Merkez X (normalize)
    y_center: float    # Merkez Y (normalize)
    width: float       # Genişlik (normalize)
    height: float      # Yükseklik (normalize)
    
    @classmethod
    def from_corners(
        cls, 
        class_id: int,
        x1: float, y1: float,  # Sol üst köşe
        x2: float, y2: float,  # Sağ alt köşe
        img_width: int,
        img_height: int
    ) -> "BoundingBox":
        """Köşe koordinatlarından BoundingBox oluşturur."""
        # Normalize et
        x_center = ((x1 + x2) / 2) / img_width
        y_center = ((y1 + y2) / 2) / img_height
        width = abs(x2 - x1) / img_width
        height = abs(y2 - y1) / img_height
        
        return cls(class_id, x_center, y_center, width, height)
    
    def to_corners(self, img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """Piksel koordinatlarına dönüştürür (x1, y1, x2, y2)."""
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
        """YOLO formatında string döndürür."""
        return f"{self.class_id} {self.x_center:.6f} {self.y_center:.6f} {self.width:.6f} {self.height:.6f}"


@dataclass 
class Polygon:
    """
    Polygon (Çokgen) etiketi.
    Noktalar normalize edilmiş koordinatlar olarak saklanır.
    """
    class_id: int
    points: List[Tuple[float, float]] = field(default_factory=list)  # [(x, y), ...]
    
    def add_point(self, x: float, y: float, img_width: int, img_height: int):
        """Normalize edilmiş nokta ekler."""
        self.points.append((x / img_width, y / img_height))
        
    def to_pixel_points(self, img_width: int, img_height: int) -> List[Tuple[int, int]]:
        """Piksel koordinatlarına dönüştürür."""
        return [
            (int(x * img_width), int(y * img_height))
            for x, y in self.points
        ]


@dataclass
class ImageAnnotations:
    """Bir görsele ait tüm etiketleri tutar."""
    image_path: str
    image_width: int
    image_height: int
    bboxes: List[BoundingBox] = field(default_factory=list)
    polygons: List[Polygon] = field(default_factory=list)
