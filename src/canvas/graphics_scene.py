"""
Graphics Scene
==============
Main scene class for the annotation canvas.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal


class AnnotationScene(QGraphicsScene):
    """
    Main scene where annotation operations take place.
    Hosts image and annotation items.
    """
    
    # Signals
    image_loaded = Signal(int, int)  # (width, height)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Background color
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        
        # Image item
        self._image_item: Optional[QGraphicsPixmapItem] = None
        self._current_pixmap: Optional[QPixmap] = None
        
    def load_image(self, image_path: str | Path) -> bool:
        """
        Loads an image into the scene.
        
        Args:
            image_path: Path to image file
            
        Returns:
            True if successful
        """
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return False
            
        return self.set_image(pixmap)
    
    def set_image(self, pixmap: QPixmap) -> bool:
        """
        Sets a QPixmap to the scene.
        
        Args:
            pixmap: Image to display
            
        Returns:
            True if successful
        """
        # Clear all previous items (image + annotations)
        self.clear()
            
        self._current_pixmap = pixmap
        self._image_item = QGraphicsPixmapItem(pixmap)
        self._image_item.setZValue(-1)  # Send to back
        self.addItem(self._image_item)
        
        # Update scene bounds
        self.setSceneRect(self._image_item.boundingRect())
        
        # Emit signal
        self.image_loaded.emit(pixmap.width(), pixmap.height())
        
        return True
    
    def clear_image(self):
        """Clears the current image."""
        if self._image_item is not None:
            self.removeItem(self._image_item)
            self._image_item = None
            self._current_pixmap = None
            
    @property
    def image_size(self) -> tuple[int, int]:
        """Returns current image size."""
        if self._current_pixmap is None:
            return (0, 0)
        return (self._current_pixmap.width(), self._current_pixmap.height())
    
    @property
    def has_image(self) -> bool:
        """Is there an image loaded?"""
        return self._current_pixmap is not None
