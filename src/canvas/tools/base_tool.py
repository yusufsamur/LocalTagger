"""
Temel Araç Sınıfı
=================
Tüm çizim araçlarının türediği abstract base class.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Optional
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene


class ToolType(Enum):
    """Araç tipleri."""
    SELECT = auto()     # Seçim/Düzenleme
    BBOX = auto()       # Bounding Box çizimi
    POLYGON = auto()    # Polygon çizimi


class BaseTool(ABC):
    """
    Tüm çizim araçlarının temel sınıfı.
    Her araç bu sınıftan türemelidir.
    """
    
    def __init__(self, scene: QGraphicsScene):
        self._scene = scene
        self._is_active = False
        self._current_class_id = 0
        
    @property
    @abstractmethod
    def tool_type(self) -> ToolType:
        """Araç tipini döndürür."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Araç ismini döndürür."""
        pass
    
    @property
    @abstractmethod
    def shortcut(self) -> str:
        """Klavye kısayolunu döndürür."""
        pass
    
    def activate(self):
        """Aracı aktifleştir."""
        self._is_active = True
        
    def deactivate(self):
        """Aracı deaktifleştir."""
        self._is_active = False
        self.cancel()
        
    def set_class(self, class_id: int):
        """Çizim için kullanılacak sınıfı ayarla."""
        self._current_class_id = class_id
    
    # ─────────────────────────────────────────────────────────────────
    # Mouse Events - Alt sınıflar override eder
    # ─────────────────────────────────────────────────────────────────
    
    @abstractmethod
    def on_mouse_press(self, pos: QPointF, button: int) -> bool:
        """
        Mouse basıldığında çağrılır.
        
        Returns:
            Event'i tüketildiyse True
        """
        pass
    
    @abstractmethod
    def on_mouse_move(self, pos: QPointF) -> bool:
        """Mouse hareket ettiğinde çağrılır."""
        pass
    
    @abstractmethod
    def on_mouse_release(self, pos: QPointF, button: int) -> bool:
        """Mouse bırakıldığında çağrılır."""
        pass
    
    def on_key_press(self, key: int) -> bool:
        """Tuş basıldığında çağrılır. Override edilebilir."""
        return False
    
    @abstractmethod
    def cancel(self):
        """Mevcut çizimi iptal et."""
        pass
