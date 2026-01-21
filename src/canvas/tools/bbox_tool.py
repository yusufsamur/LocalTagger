"""
Bounding Box Tool
=================
Tool for drawing rectangular boxes.
"""

from typing import Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem
from PySide6.QtGui import QPen, QColor, QBrush

from .base_tool import BaseTool, ToolType


class BBoxTool(BaseTool):
    """Bounding Box drawing tool."""
    
    # Default style
    DEFAULT_COLOR = QColor(255, 0, 0)  # Red
    LINE_WIDTH = 2
    FILL_OPACITY = 0.2
    
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        
        # Drawing state
        self._is_drawing = False
        self._start_pos: Optional[QPointF] = None
        self._temp_rect: Optional[QGraphicsRectItem] = None
        self._color = self.DEFAULT_COLOR
        
    @property
    def tool_type(self) -> ToolType:
        return ToolType.BBOX
    
    @property
    def name(self) -> str:
        return "Bounding Box"
    
    @property
    def shortcut(self) -> str:
        return "W"
    
    def set_color(self, color: QColor):
        """Set drawing color."""
        self._color = color
    
    def on_mouse_press(self, pos: QPointF, button: int) -> bool:
        """Start drawing."""
        if button != Qt.MouseButton.LeftButton:
            return False
            
        if not self._is_active:
            return False
            
        self._is_drawing = True
        self._start_pos = pos
        
        # Create temporary rectangle
        self._create_temp_rect(pos)
        
        return True
    
    def on_mouse_move(self, pos: QPointF) -> bool:
        """Update drawing."""
        if not self._is_drawing or self._temp_rect is None:
            return False
            
        # Update rectangle
        self._update_temp_rect(pos)
        
        return True
    
    def on_mouse_release(self, pos: QPointF, button: int) -> bool:
        """Complete drawing."""
        if button != Qt.MouseButton.LeftButton:
            return False
            
        if not self._is_drawing:
            return False
            
        self._is_drawing = False
        
        # Minimum size check (prevent very small boxes)
        if self._temp_rect is not None:
            rect = self._temp_rect.rect()
            if rect.width() < 5 or rect.height() < 5:
                # Too small, cancel
                self._scene.removeItem(self._temp_rect)
            else:
                # Make permanent (remove temp style)
                self._finalize_rect()
                
        self._temp_rect = None
        self._start_pos = None
        
        return True
    
    def cancel(self):
        """Cancel current drawing."""
        if self._temp_rect is not None:
            self._scene.removeItem(self._temp_rect)
            self._temp_rect = None
        self._is_drawing = False
        self._start_pos = None
    
    # ─────────────────────────────────────────────────────────────────
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────
    
    def _create_temp_rect(self, pos: QPointF):
        """Create temporary rectangle."""
        rect = QRectF(pos, pos)
        self._temp_rect = QGraphicsRectItem(rect)
        
        # Set style
        pen = QPen(self._color, self.LINE_WIDTH)
        pen.setStyle(Qt.PenStyle.DashLine)  # Dashed line while drawing
        pen.setCosmetic(True)  # Fixed line width independent of zoom
        self._temp_rect.setPen(pen)
        
        fill_color = QColor(self._color)
        fill_color.setAlphaF(self.FILL_OPACITY)
        self._temp_rect.setBrush(QBrush(fill_color))
        
        self._scene.addItem(self._temp_rect)
    
    def _update_temp_rect(self, pos: QPointF):
        """Update temporary rectangle with new position."""
        if self._temp_rect is None or self._start_pos is None:
            return
            
        # Calculate top-left and bottom-right corners
        x1 = min(self._start_pos.x(), pos.x())
        y1 = min(self._start_pos.y(), pos.y())
        x2 = max(self._start_pos.x(), pos.x())
        y2 = max(self._start_pos.y(), pos.y())
        
        rect = QRectF(x1, y1, x2 - x1, y2 - y1)
        self._temp_rect.setRect(rect)
    
    def _finalize_rect(self):
        """Make rectangle permanent."""
        if self._temp_rect is None:
            return
            
        # Switch to solid line style
        pen = QPen(self._color, self.LINE_WIDTH)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)  # Fixed line width independent of zoom
        self._temp_rect.setPen(pen)
        
        # Rectangle made permanent, data recording is managed via app.py signals.
