"""
Base Tool Class
===============
Abstract base class from which all drawing tools derive.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Optional
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene


class ToolType(Enum):
    """Tool types."""
    SELECT = auto()     # Selection/Editing
    BBOX = auto()       # Bounding Box drawing
    POLYGON = auto()    # Polygon drawing


class BaseTool(ABC):
    """
    Base class for all drawing tools.
    Every tool must inherit from this class.
    """
    
    def __init__(self, scene: QGraphicsScene):
        self._scene = scene
        self._is_active = False
        self._current_class_id = 0
        
    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        """Returns the tool type."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the tool name."""
        pass
    
    @property
    @abstractmethod
    def shortcut(self) -> str:
        """Returns the keyboard shortcut."""
        pass
    
    def activate(self):
        """Activate the tool."""
        self._is_active = True
        
    def deactivate(self):
        """Deactivate the tool."""
        self._is_active = False
        self.cancel()
        
    def set_class(self, class_id: int):
        """Set the class to be used for drawing."""
        self._current_class_id = class_id
    
    # ─────────────────────────────────────────────────────────────────
    # Mouse Events - Subclasses override these
    # ─────────────────────────────────────────────────────────────────
    
    @abstractmethod
    def on_mouse_press(self, pos: QPointF, button: int) -> bool:
        """
        Called when mouse is pressed.
        
        Returns:
            True if event was consumed
        """
        pass
    
    @abstractmethod
    def on_mouse_move(self, pos: QPointF) -> bool:
        """Called when mouse moves."""
        pass
    
    @abstractmethod
    def on_mouse_release(self, pos: QPointF, button: int) -> bool:
        """Called when mouse is released."""
        pass
    
    def on_key_press(self, key: int) -> bool:
        """Called when a key is pressed. Can be overridden."""
        return False
    
    @abstractmethod
    def cancel(self):
        """Cancel current drawing."""
        pass
