"""
Sınıf Yönetimi
==============
Etiket sınıflarını yönetir (ekleme, silme, renk atama).
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import random


@dataclass
class LabelClass:
    """Bir etiket sınıfını temsil eder."""
    id: int
    name: str
    color: str  # Hex format: "#FF0000"
    
    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "color": self.color}
    
    @classmethod
    def from_dict(cls, data: dict) -> "LabelClass":
        return cls(id=data["id"], name=data["name"], color=data["color"])


class ClassManager:
    """
    Etiket sınıflarını yönetir.
    classes.txt dosyası ile uyumlu çalışır.
    """
    
    # Varsayılan renk paleti
    DEFAULT_COLORS = [
        "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF",
        "#FF8000", "#8000FF", "#00FF80", "#FF0080", "#80FF00", "#0080FF",
        "#FF4040", "#40FF40", "#4040FF", "#FFFF40", "#FF40FF", "#40FFFF",
    ]
    
    def __init__(self):
        self._classes: List[LabelClass] = []
        self._next_id: int = 0
        self._color_index: int = 0
        
    @property
    def classes(self) -> List[LabelClass]:
        """Tüm sınıfları döndürür."""
        return self._classes.copy()
    
    @property
    def count(self) -> int:
        """Sınıf sayısını döndürür."""
        return len(self._classes)
    
    def add_class(self, name: str, color: Optional[str] = None) -> LabelClass:
        """
        Yeni sınıf ekler.
        
        Args:
            name: Sınıf adı
            color: Hex renk kodu (opsiyonel, otomatik atanır)
            
        Returns:
            Oluşturulan LabelClass
        """
        # Otomatik renk ata
        if color is None:
            color = self._get_next_color()
            
        label_class = LabelClass(
            id=self._next_id,
            name=name,
            color=color
        )
        
        self._classes.append(label_class)
        self._next_id += 1
        
        return label_class
    
    def add_class_with_id(self, class_id: int, name: str, color: Optional[str] = None) -> LabelClass:
        """
        Belirli bir ID ile sınıf ekler (etiketli veri yüklerken kullanılır).
        
        Args:
            class_id: Sınıf ID'si
            name: Sınıf adı
            color: Hex renk kodu (opsiyonel)
            
        Returns:
            Oluşturulan LabelClass
        """
        # Eğer bu ID zaten varsa, güncelle
        existing = self.get_by_id(class_id)
        if existing:
            return existing
        
        # Otomatik renk ata
        if color is None:
            color = self._get_next_color()
            
        label_class = LabelClass(
            id=class_id,
            name=name,
            color=color
        )
        
        self._classes.append(label_class)
        
        # _next_id'yi güncelle (en büyük ID'den büyük olmalı)
        if class_id >= self._next_id:
            self._next_id = class_id + 1
        
        return label_class
    
    def remove_class(self, class_id: int) -> bool:
        """
        Sınıfı ID'ye göre siler.
        
        Returns:
            Silme başarılı ise True
        """
        for i, cls in enumerate(self._classes):
            if cls.id == class_id:
                self._classes.pop(i)
                return True
        return False
    
    def update_class(self, class_id: int, name: Optional[str] = None, 
                     color: Optional[str] = None) -> bool:
        """
        Sınıf bilgilerini günceller.
        
        Returns:
            Güncelleme başarılı ise True
        """
        label_class = self.get_by_id(class_id)
        if label_class is None:
            return False
            
        if name is not None:
            label_class.name = name
        if color is not None:
            label_class.color = color
            
        return True
    
    def get_by_id(self, class_id: int) -> Optional[LabelClass]:
        """ID'ye göre sınıf döndürür."""
        for cls in self._classes:
            if cls.id == class_id:
                return cls
        return None
    
    def get_by_name(self, name: str) -> Optional[LabelClass]:
        """İsme göre sınıf döndürür."""
        for cls in self._classes:
            if cls.name == name:
                return cls
        return None
    
    def get_index(self, class_id: int) -> int:
        """Sınıfın listedeki indeksini döndürür (YOLO export için)."""
        for i, cls in enumerate(self._classes):
            if cls.id == class_id:
                return i
        return -1
    
    def _get_next_color(self) -> str:
        """Sonraki otomatik rengi döndürür."""
        if self._color_index < len(self.DEFAULT_COLORS):
            color = self.DEFAULT_COLORS[self._color_index]
            self._color_index += 1
        else:
            # Rastgele renk üret
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        return color
    
    # ─────────────────────────────────────────────────────────────────
    # Dosya İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def save_to_file(self, file_path: Path | str):
        """
        Sınıfları classes.txt formatında kaydeder.
        
        Format (her satır):
            class_name
            
        Ekstra metadata için ayrı JSON dosyası kullanılabilir.
        """
        file_path = Path(file_path)
        
        # Sadece isimler (YOLO uyumlu classes.txt)
        with open(file_path, "w", encoding="utf-8") as f:
            for cls in self._classes:
                f.write(f"{cls.name}\n")
                
        # Renk bilgilerini ayrı dosyada sakla
        meta_path = file_path.with_suffix(".json")
        import json
        meta = {
            "classes": [cls.to_dict() for cls in self._classes],
            "next_id": self._next_id
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    
    def load_from_file(self, file_path: Path | str):
        """
        classes.txt dosyasından sınıfları yükler.
        Eğer .json metadata varsa renkleri de yükler.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return
            
        self._classes.clear()
        self._color_index = 0
        
        # Önce JSON metadata'yı dene
        meta_path = file_path.with_suffix(".json")
        if meta_path.exists():
            import json
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                for cls_data in meta.get("classes", []):
                    self._classes.append(LabelClass.from_dict(cls_data))
                self._next_id = meta.get("next_id", len(self._classes))
                return
            except (json.JSONDecodeError, KeyError):
                pass  # JSON hatalı, txt'den yükle
        
        # Sadece classes.txt'den yükle
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    self.add_class(name)
    
    def clear(self):
        """Tüm sınıfları temizler."""
        self._classes.clear()
        self._next_id = 0
        self._color_index = 0
