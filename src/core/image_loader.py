"""
Görsel Yükleme
==============
Görselleri yükleme, önbellekleme ve lazy loading.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QSize


class ImageLoader:
    """
    Görsel yükleme ve önbellekleme sınıfı.
    Lazy loading ile büyük veri setlerini destekler.
    """
    
    def __init__(self, cache_size: int = 10):
        """
        Args:
            cache_size: Önbellekte tutulacak maksimum görsel sayısı
        """
        self._cache: dict[Path, QPixmap] = {}
        self._cache_order: list[Path] = []
        self._cache_size = cache_size
        
    def load(self, image_path: Path | str) -> Optional[QPixmap]:
        """
        Bir görseli yükler (önbellekten veya diskten).
        
        Args:
            image_path: Görsel dosyasının yolu
            
        Returns:
            QPixmap nesnesi veya None (hata durumunda)
        """
        path = Path(image_path)
        
        # Önbellekte var mı kontrol et
        if path in self._cache:
            return self._cache[path]
            
        # Diskten yükle
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
            
        # Önbelleğe ekle
        self._add_to_cache(path, pixmap)
        
        return pixmap
    
    def load_thumbnail(
        self, 
        image_path: Path | str, 
        size: QSize = QSize(100, 100)
    ) -> Optional[QPixmap]:
        """
        Görsel için küçültülmüş önizleme yükler.
        
        Args:
            image_path: Görsel dosyasının yolu
            size: Thumbnail boyutu
            
        Returns:
            Küçültülmüş QPixmap
        """
        pixmap = self.load(image_path)
        if pixmap is None:
            return None
            
        return pixmap.scaled(
            size,
            aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
            mode=Qt.TransformationMode.SmoothTransformation
        )
    
    def _add_to_cache(self, path: Path, pixmap: QPixmap):
        """Önbelleğe görsel ekler, gerekirse eski öğeleri siler."""
        # Önbellek dolu ise en eski öğeyi sil
        if len(self._cache_order) >= self._cache_size:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]
            
        self._cache[path] = pixmap
        self._cache_order.append(path)
        
    def clear_cache(self):
        """Önbelleği temizler."""
        self._cache.clear()
        self._cache_order.clear()


# Qt import for thumbnail scaling
from PySide6.QtCore import Qt
