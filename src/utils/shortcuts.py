"""
Klavye Kısayolları
==================
Uygulama genelinde klavye kısayolu yönetimi.
"""

from dataclasses import dataclass
from typing import Dict, Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


@dataclass
class Shortcut:
    """Bir klavye kısayolunu temsil eder."""
    key: str
    description: str
    callback: Callable


class ShortcutManager:
    """Klavye kısayollarını yönetir."""
    
    # Varsayılan kısayollar
    DEFAULTS = {
        "open_folder": ("Ctrl+O", "Klasör Aç"),
        "save": ("Ctrl+S", "Kaydet"),
        "next_image": ("D", "Sonraki Görsel"),
        "prev_image": ("A", "Önceki Görsel"),
        "bbox_tool": ("W", "Bounding Box Aracı"),
        "polygon_tool": ("E", "Polygon Aracı"),
        "select_tool": ("Q", "Seçim Aracı"),
        "zoom_in": ("Ctrl+=", "Yakınlaştır"),
        "zoom_out": ("Ctrl+-", "Uzaklaştır"),
        "zoom_fit": ("Ctrl+0", "Sığdır"),
        "delete": ("Delete", "Seçili Etiketi Sil"),
        "undo": ("Ctrl+Z", "Geri Al"),
        "redo": ("Ctrl+Y", "Yinele"),
    }
    
    def __init__(self, parent: QWidget):
        self._parent = parent
        self._shortcuts: Dict[str, QShortcut] = {}
        
    def register(self, name: str, callback: Callable):
        """Bir kısayol kaydet."""
        if name in self.DEFAULTS:
            key, desc = self.DEFAULTS[name]
            shortcut = QShortcut(QKeySequence(key), self._parent)
            shortcut.activated.connect(callback)
            self._shortcuts[name] = shortcut
            
    def unregister(self, name: str):
        """Bir kısayolu kaldır."""
        if name in self._shortcuts:
            self._shortcuts[name].deleteLater()
            del self._shortcuts[name]
