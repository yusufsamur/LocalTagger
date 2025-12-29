"""
Graphics Scene
==============
Etiketleme tuvalinin ana sahne sınıfı.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal


class AnnotationScene(QGraphicsScene):
    """
    Etiketleme işlemlerinin yapıldığı ana sahne.
    Görsel ve etiket öğelerini barındırır.
    """
    
    # Sinyaller
    image_loaded = Signal(int, int)  # (width, height)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Arka plan rengi
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        
        # Görsel öğesi
        self._image_item: Optional[QGraphicsPixmapItem] = None
        self._current_pixmap: Optional[QPixmap] = None
        
    def load_image(self, image_path: str | Path) -> bool:
        """
        Sahneye bir görsel yükler.
        
        Args:
            image_path: Görsel dosyasının yolu
            
        Returns:
            Başarılı ise True
        """
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return False
            
        return self.set_image(pixmap)
    
    def set_image(self, pixmap: QPixmap) -> bool:
        """
        Sahneye bir QPixmap ayarlar.
        
        Args:
            pixmap: Gösterilecek görsel
            
        Returns:
            Başarılı ise True
        """
        # Önceki görseli temizle
        if self._image_item is not None:
            self.removeItem(self._image_item)
            
        self._current_pixmap = pixmap
        self._image_item = QGraphicsPixmapItem(pixmap)
        self._image_item.setZValue(-1)  # En arkada olsun
        self.addItem(self._image_item)
        
        # Sahne sınırlarını güncelle
        self.setSceneRect(self._image_item.boundingRect())
        
        # Sinyal gönder
        self.image_loaded.emit(pixmap.width(), pixmap.height())
        
        return True
    
    def clear_image(self):
        """Mevcut görseli temizler."""
        if self._image_item is not None:
            self.removeItem(self._image_item)
            self._image_item = None
            self._current_pixmap = None
            
    @property
    def image_size(self) -> tuple[int, int]:
        """Mevcut görsel boyutunu döndürür."""
        if self._current_pixmap is None:
            return (0, 0)
        return (self._current_pixmap.width(), self._current_pixmap.height())
    
    @property
    def has_image(self) -> bool:
        """Yüklü bir görsel var mı?"""
        return self._current_pixmap is not None
