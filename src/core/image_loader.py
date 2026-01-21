"""
Image Loader
============
Image loading, caching and lazy loading.
"""

from pathlib import Path
from typing import Optional
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QSize


class ImageLoader:
    """
    Image loading and caching class.
    Supports large datasets with lazy loading.
    """
    
    def __init__(self, cache_size: int = 10):
        """
        Args:
            cache_size: Max number of images to keep in cache
        """
        self._cache: dict[Path, QPixmap] = {}
        self._cache_order: list[Path] = []
        self._cache_size = cache_size
        
    def load(self, image_path: Path | str) -> Optional[QPixmap]:
        """
        Loads an image (from cache or disk).
        
        Args:
            image_path: Path to image file
            
        Returns:
            QPixmap object or None (if error)
        """
        path = Path(image_path)
        
        # Check if in cache
        if path in self._cache:
            return self._cache[path]
            
        # Load from disk
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
            
        # Add to cache
        self._add_to_cache(path, pixmap)
        
        return pixmap
    
    def load_thumbnail(
        self, 
        image_path: Path | str, 
        size: QSize = QSize(100, 100)
    ) -> Optional[QPixmap]:
        """
        Loads a scaled thumbnail for image.
        
        Args:
            image_path: Path to image file
            size: Thumbnail size
            
        Returns:
            Scaled QPixmap
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
        """Adds image to cache, removes old items if needed."""
        # If cache is full, remove oldest item
        if len(self._cache_order) >= self._cache_size:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]
            
        self._cache[path] = pixmap
        self._cache_order.append(path)
        
    def clear_cache(self):
        """Clears cache."""
        self._cache.clear()
        self._cache_order.clear()


# Qt import for thumbnail scaling
from PySide6.QtCore import Qt
