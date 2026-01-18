"""
Annotation Yönetimi
===================
Tüm görsel annotasyonlarını yönetir, cache ve kayıt işlemleri.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .annotation import BoundingBox, Polygon, ImageAnnotations


class AnnotationManager:
    """
    Tüm görsellerin annotasyonlarını yönetir.
    Bellek içi cache tutar ve disk'e kayıt yapar.
    """
    
    MAX_UNDO_STACK = 50  # Maksimum undo sayısı
    
    def __init__(self):
        # {image_path: ImageAnnotations}
        self._annotations: Dict[str, ImageAnnotations] = {}
        # Değişiklik takibi
        self._dirty: set = set()  # Kaydedilmemiş değişiklikler
        # Undo stack: [(image_path, action_type, data)]
        self._undo_stack: List[tuple] = []
        
    def get_annotations(self, image_path: str | Path) -> ImageAnnotations:
        """
        Bir görselin annotasyonlarını döndürür.
        Yoksa boş bir ImageAnnotations oluşturur.
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
        """Görsel boyutlarını ayarlar."""
        annotations = self.get_annotations(image_path)
        annotations.image_width = width
        annotations.image_height = height
        
    def add_bbox(self, image_path: str | Path, bbox: BoundingBox):
        """Görsel için BBox ekler."""
        annotations = self.get_annotations(image_path)
        # Undo için kaydet
        self._push_undo(str(image_path), 'add_bbox', len(annotations.bboxes))
        annotations.bboxes.append(bbox)
        self._mark_dirty(image_path)
        
    def add_polygon(self, image_path: str | Path, polygon: Polygon):
        """Görsel için Polygon ekler."""
        annotations = self.get_annotations(image_path)
        # Undo için kaydet
        self._push_undo(str(image_path), 'add_polygon', len(annotations.polygons))
        annotations.polygons.append(polygon)
        self._mark_dirty(image_path)
        
    def remove_bbox(self, image_path: str | Path, index: int) -> bool:
        """İndekse göre BBox siler."""
        annotations = self.get_annotations(image_path)
        if 0 <= index < len(annotations.bboxes):
            # Undo için kaydet
            removed_bbox = annotations.bboxes[index]
            self._push_undo(str(image_path), 'remove_bbox', (index, removed_bbox))
            annotations.bboxes.pop(index)
            self._mark_dirty(image_path)
            return True
        return False
    
    def remove_polygon(self, image_path: str | Path, index: int) -> bool:
        """İndekse göre Polygon siler."""
        annotations = self.get_annotations(image_path)
        if 0 <= index < len(annotations.polygons):
            # Undo için kaydet
            removed_polygon = annotations.polygons[index]
            self._push_undo(str(image_path), 'remove_polygon', (index, removed_polygon))
            annotations.polygons.pop(index)
            self._mark_dirty(image_path)
            return True
        return False
    
    def clear_annotations(self, image_path: str | Path):
        """Görselin tüm annotasyonlarını temizler."""
        key = str(image_path)
        if key in self._annotations:
            self._annotations[key].bboxes.clear()
            self._annotations[key].polygons.clear()
            self._mark_dirty(image_path)
    
    def _mark_dirty(self, image_path: str | Path):
        """Görseli 'kaydedilmemiş' olarak işaretle."""
        self._dirty.add(str(image_path))
    
    def _push_undo(self, image_path: str, action: str, data):
        """Undo stack'e işlem ekle."""
        self._undo_stack.append((image_path, action, data))
        # Stack limitini aş
        if len(self._undo_stack) > self.MAX_UNDO_STACK:
            self._undo_stack.pop(0)
    
    def undo(self) -> tuple:
        """
        Son işlemi geri al.
        Returns: (image_path, success) tuple - hangi görsel etkilendi ve başarılı mı
        """
        if not self._undo_stack:
            return (None, False)
        
        image_path, action, data = self._undo_stack.pop()
        annotations = self.get_annotations(image_path)
        
        if action == 'add_bbox':
            # Eklenen bbox'ı sil
            index = data
            if 0 <= index < len(annotations.bboxes):
                annotations.bboxes.pop(index)
        elif action == 'add_polygon':
            # Eklenen polygon'u sil
            index = data
            if 0 <= index < len(annotations.polygons):
                annotations.polygons.pop(index)
        elif action == 'remove_bbox':
            # Silinen bbox'ı geri ekle
            index, bbox = data
            annotations.bboxes.insert(index, bbox)
        elif action == 'remove_polygon':
            # Silinen polygon'u geri ekle
            index, polygon = data
            annotations.polygons.insert(index, polygon)
        else:
            return (image_path, False)
        
        self._mark_dirty(image_path)
        return (image_path, True)
    
    def can_undo(self) -> bool:
        """Geri alınabilecek işlem var mı?"""
        return len(self._undo_stack) > 0
        
    def is_dirty(self, image_path: str | Path = None) -> bool:
        """Kaydedilmemiş değişiklik var mı?"""
        if image_path is None:
            return len(self._dirty) > 0
        return str(image_path) in self._dirty
    
    def mark_saved(self, image_path: str | Path = None):
        """Kaydedildi olarak işaretle."""
        if image_path is None:
            self._dirty.clear()
        else:
            self._dirty.discard(str(image_path))
    
    def get_all_annotation_count(self) -> int:
        """Toplam annotation sayısını döndürür."""
        total = 0
        for ann in self._annotations.values():
            total += len(ann.bboxes) + len(ann.polygons)
        return total
    
    # ─────────────────────────────────────────────────────────────────
    # YOLO Dosya İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def save_yolo(self, image_path: str | Path, output_dir: Path):
        """
        Tek bir görselin annotasyonlarını YOLO formatında kaydeder.
        
        Args:
            image_path: Kaynak görsel yolu
            output_dir: Çıktı klasörü
        """
        annotations = self.get_annotations(image_path)
        
        # Görsel adından txt dosya adı oluştur
        image_name = Path(image_path).stem
        txt_path = output_dir / f"{image_name}.txt"
        
        lines = []
        
        # BBox'ları yaz
        for bbox in annotations.bboxes:
            lines.append(bbox.to_yolo_format())
            
        # Polygon'ları yaz (YOLO segmentation formatı)
        for polygon in annotations.polygons:
            if len(polygon.points) >= 3:
                points_str = " ".join(f"{x:.6f} {y:.6f}" for x, y in polygon.points)
                lines.append(f"{polygon.class_id} {points_str}")
        
        # Dosyayı yaz
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            
        self.mark_saved(image_path)
    
    def load_yolo(self, image_path: str | Path, width: int, height: int):
        """
        YOLO txt dosyasından annotasyonları yükler.
        
        Args:
            image_path: Görsel yolu (txt aynı klasörde aranır)
            width: Görsel genişliği
            height: Görsel yüksekliği
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
                    # BBox formatı: class x_center y_center width height
                    bbox = BoundingBox(
                        class_id=class_id,
                        x_center=float(parts[1]),
                        y_center=float(parts[2]),
                        width=float(parts[3]),
                        height=float(parts[4])
                    )
                    annotations.bboxes.append(bbox)
                else:
                    # Polygon formatı: class x1 y1 x2 y2 ...
                    points = []
                    for i in range(1, len(parts), 2):
                        if i + 1 < len(parts):
                            points.append((float(parts[i]), float(parts[i+1])))
                    if len(points) >= 3:
                        polygon = Polygon(class_id=class_id, points=points)
                        annotations.polygons.append(polygon)
    
    def _load_from_path(self, image_path: str | Path, txt_path: Path, width: int, height: int):
        """
        Belirli bir txt dosyasından annotasyonları yükler.
        
        Args:
            image_path: Görsel yolu
            txt_path: YOLO txt dosya yolu
            width: Görsel genişliği
            height: Görsel yüksekliği
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
                    # BBox formatı
                    bbox = BoundingBox(
                        class_id=class_id,
                        x_center=float(parts[1]),
                        y_center=float(parts[2]),
                        width=float(parts[3]),
                        height=float(parts[4])
                    )
                    annotations.bboxes.append(bbox)
                else:
                    # Polygon formatı
                    points = []
                    for i in range(1, len(parts), 2):
                        if i + 1 < len(parts):
                            points.append((float(parts[i]), float(parts[i+1])))
                    if len(points) >= 3:
                        polygon = Polygon(class_id=class_id, points=points)
                        annotations.polygons.append(polygon)
    
    def clear(self):
        """Tüm annotasyonları temizler."""
        self._annotations.clear()
        self._dirty.clear()
