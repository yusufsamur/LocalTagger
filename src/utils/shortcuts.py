"""
Keyboard Shortcuts
==================
Application-wide keyboard shortcut management.
"""

from dataclasses import dataclass
from typing import Dict, Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget


@dataclass
class Shortcut:
    """Represents a keyboard shortcut."""
    key: str
    description: str
    callback: Callable


class ShortcutManager:
    """Manages keyboard shortcuts."""
    
    # Default shortcuts
    DEFAULTS = {
        "open_folder": ("Ctrl+O", "Open Folder"),
        "save": ("Ctrl+S", "Save"),
        "next_image": ("D", "Next Image"),
        "prev_image": ("A", "Previous Image"),
        "bbox_tool": ("W", "Bounding Box Tool"),
        "polygon_tool": ("E", "Polygon Tool"),
        "select_tool": ("Q", "Select Tool"),
        "zoom_in": ("Ctrl+=", "Zoom In"),
        "zoom_out": ("Ctrl+-", "Zoom Out"),
        "zoom_fit": ("Ctrl+0", "Fit to Screen"),
        "delete": ("Delete", "Delete Selected Label"),
        "undo": ("Ctrl+Z", "Undo"),
        "redo": ("Ctrl+Y", "Redo"),
    }
    
    def __init__(self, parent: QWidget):
        self._parent = parent
        self._shortcuts: Dict[str, QShortcut] = {}
        
    def register(self, name: str, callback: Callable):
        """Register a shortcut."""
        if name in self.DEFAULTS:
            key, desc = self.DEFAULTS[name]
            shortcut = QShortcut(QKeySequence(key), self._parent)
            shortcut.activated.connect(callback)
            self._shortcuts[name] = shortcut
            
    def unregister(self, name: str):
        """Unregister a shortcut."""
        if name in self._shortcuts:
            self._shortcuts[name].deleteLater()
            del self._shortcuts[name]
