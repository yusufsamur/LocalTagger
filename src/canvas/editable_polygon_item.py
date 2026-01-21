"""
Editable Polygon Item
=====================
Editable polygon with draggable vertices.
"""

from PySide6.QtWidgets import (
    QGraphicsPolygonItem, QGraphicsItem, QGraphicsEllipseItem,
    QMenu, QGraphicsSceneContextMenuEvent
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QPen, QColor, QBrush, QPainter, QPolygonF


class EditablePolygonSignals(QObject):
    """Helper class for signals."""
    polygon_changed = Signal(int, list)  # (index, new_points)
    class_change_requested = Signal(int, QPointF)  # (index, position)
    delete_requested = Signal(int)  # index
    selected_changed = Signal(int, bool)  # (index, is_selected)
    clicked = Signal(int)  # index - to switch to auto select mode when clicked


class EditablePolygonItem(QGraphicsPolygonItem):
    """
    Editable polygon item.
    - Vertices are draggable
    - Right-click menu for class changing/deletion
    """
    
    BASE_VERTEX_SIZE = 8  # Base vertex size
    MIN_VERTEX_SIZE = 4   # Minimum vertex size
    MAX_VERTEX_SIZE = 12  # Maximum vertex size
    
    def __init__(self, polygon: QPolygonF, index: int, class_id: int, color: QColor, parent=None):
        super().__init__(polygon, parent)
        self.index = index
        self.class_id = class_id
        self.color = color
        
        # Signals
        self.signals = EditablePolygonSignals()
        
        # Selectable and movable (with Q mode)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        
        # Style
        self._update_style()
        
        # Vertex drag state
        self._dragging_vertex = -1
        self._drag_start_pos = None
        
    def _update_style(self, selected: bool = False):
        """Update appearance."""
        if selected:
            pen = QPen(self.color, 3)
        else:
            pen = QPen(self.color, 2)
        pen.setCosmetic(True)  # Fixed line width independent of zoom
        self.setPen(pen)
        
        fill = QColor(self.color)
        fill.setAlphaF(0.15 if not selected else 0.25)
        self.setBrush(QBrush(fill))
    
    def _get_dynamic_vertex_size(self, scale: float = 1.0) -> float:
        """Dynamic vertex size based on zoom level."""
        if scale <= 0:
            scale = 1.0
        vs = self.BASE_VERTEX_SIZE / scale
        return max(self.MIN_VERTEX_SIZE, min(vs, self.MAX_VERTEX_SIZE))
    
    def _get_vertex_at(self, pos: QPointF) -> int:
        """Return index of vertex at position (-1 = none)."""
        polygon = self.polygon()
        # Get scale from View
        scale = 1.0
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            scale = view.transform().m11()
        vs = self._get_dynamic_vertex_size(scale)
        
        for i in range(polygon.count()):
            pt = polygon.at(i)
            rect = QRectF(pt.x() - vs/2, pt.y() - vs/2, vs, vs)
            if rect.contains(pos):
                return i
        return -1
    
    def paint(self, painter: QPainter, option, widget=None):
        """Draw - also draw vertices."""
        super().paint(painter, option, widget)
        
        if self.isSelected():
            polygon = self.polygon()
            # Dynamic vertex size based on zoom level
            scale = painter.transform().m11()
            vs = self._get_dynamic_vertex_size(scale)
            
            for i in range(polygon.count()):
                pt = polygon.at(i)
                rect = QRectF(pt.x() - vs/2, pt.y() - vs/2, vs, vs)
                
                # First point different color
                if i == 0:
                    painter.setBrush(QBrush(QColor("#FFD700")))
                else:
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                
                vertex_pen = QPen(self.color, 2)
                vertex_pen.setCosmetic(True)
                painter.setPen(vertex_pen)
                painter.drawEllipse(rect)
    
    def hoverMoveEvent(self, event):
        """Update cursor on hover."""
        if self.isSelected():
            vertex = self._get_vertex_at(event.pos())
            if vertex >= 0:
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Hover leave."""
        self.unsetCursor()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """On mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.isSelected():
                vertex = self._get_vertex_at(event.pos())
                if vertex >= 0:
                    # Start vertex drag
                    self._dragging_vertex = vertex
                    self._drag_start_pos = event.pos()
                    event.accept()
                    return
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Mouse move."""
        if self._dragging_vertex >= 0:
            # Drag vertex - create new polygon
            polygon = self.polygon()
            new_points = []
            for i in range(polygon.count()):
                if i == self._dragging_vertex:
                    new_points.append(event.pos())
                else:
                    new_points.append(polygon.at(i))
            new_polygon = QPolygonF(new_points)
            self.setPolygon(new_polygon)
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """On mouse release."""
        if self._dragging_vertex >= 0:
            # Vertex drag completed
            self._dragging_vertex = -1
            self._emit_polygon_changed()
            event.accept()
            return
        elif self._drag_start_pos is not None:
            # Polygon move completed
            if event.pos() != self._drag_start_pos:
                self._emit_polygon_changed()
            self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def _emit_polygon_changed(self):
        """Emit polygon change - in scene coordinates."""
        polygon = self.polygon()
        # Convert local coordinates to scene coordinates
        points = []
        for i in range(polygon.count()):
            local_pt = polygon.at(i)
            scene_pt = self.mapToScene(local_pt)
            points.append((scene_pt.x(), scene_pt.y()))
        self.signals.polygon_changed.emit(self.index, points)
    
    def itemChange(self, change, value):
        """Item change."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_style(value)
            self.signals.selected_changed.emit(self.index, value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Drag completed - report position change immediately (no race condition risk)
            self._emit_polygon_changed()
        return super().itemChange(change, value)
    
    def keyPressEvent(self, event):
        """Key events - deletion shortcuts."""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_Escape):
            self.signals.delete_requested.emit(self.index)
            event.accept()
            return
        super().keyPressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Double click - do nothing."""
        super().mouseDoubleClickEvent(event)
    
    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """Context menu."""
        from PySide6.QtCore import QCoreApplication
        menu = QMenu()
        change_class_action = menu.addAction(QCoreApplication.translate("EditablePolygonItem", "🏷️ Change Class"))
        menu.addSeparator()
        delete_action = menu.addAction(QCoreApplication.translate("EditablePolygonItem", "🗑️ Delete"))
        
        action = menu.exec(event.screenPos())
        
        if action == delete_action:
            self.signals.delete_requested.emit(self.index)
        elif action == change_class_action:
            self.signals.class_change_requested.emit(self.index, event.scenePos())
    
    def update_class(self, class_id: int, color: QColor):
        """Update class."""
        self.class_id = class_id
        self.color = color
        self._update_style(self.isSelected())
