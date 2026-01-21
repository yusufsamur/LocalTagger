"""
Editable BBox Item
==================
Draggable and resizable bounding box.
Supports resize from corners and edges.
"""

from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsItem, QGraphicsEllipseItem,
    QMenu, QGraphicsSceneContextMenuEvent
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QPen, QColor, QBrush, QPainter, QCursor


class EditableRectSignals(QObject):
    """Helper class for signals."""
    rect_changed = Signal(int, QRectF)  # (index, new_rect)
    class_change_requested = Signal(int, QPointF)  # (index, position)
    delete_requested = Signal(int)  # index
    selected_changed = Signal(int, bool)  # (index, is_selected)
    clicked = Signal(int)  # index - to switch to auto select mode when clicked


class EditableRectItem(QGraphicsRectItem):
    """
    Editable bounding box item.
    - Move by dragging
    - Resize from corners and edges
    - Right-click menu for class changing/deletion
    """
    
    BASE_CORNER_SIZE = 6  # Base corner detection size
    MIN_CORNER_SIZE = 3   # Minimum corner size
    MAX_CORNER_SIZE = 10  # Maximum corner size
    BASE_EDGE_THRESHOLD = 4  # Base edge detection threshold
    MIN_RESIZE_SIZE = 3   # Minimum bbox size (pixels)
    
    # Handle types
    HANDLES = ['tl', 'tr', 'bl', 'br', 'top', 'bottom', 'left', 'right']
    
    def __init__(self, rect: QRectF, index: int, class_id: int, color: QColor, parent=None):
        super().__init__(rect, parent)
        self.index = index
        self.class_id = class_id
        self.color = color
        
        # Signals
        self.signals = EditableRectSignals()
        
        # Selectable and movable
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        
        # Style
        self._update_style()
        
        # Resize state
        self._resize_handle = None
        self._resize_start_rect = None
        self._resize_start_pos = None
        self._drag_start_pos = None
        
    def _update_style(self, selected: bool = False):
        """Update appearance."""
        if selected:
            pen = QPen(self.color, 2)
            pen.setStyle(Qt.PenStyle.DashLine)  # Dashed line when selected
        else:
            pen = QPen(self.color, 2)
            pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)  # Fixed line width independent of zoom
        self.setPen(pen)
        
        fill = QColor(self.color)
        fill.setAlphaF(0.15 if not selected else 0.25)
        self.setBrush(QBrush(fill))
        
    def _get_dynamic_sizes(self) -> tuple:
        """Dynamic corner and edge sizes based on zoom level."""
        scale = 1.0
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            scale = view.transform().m11()
        if scale <= 0:
            scale = 1.0
        
        # Corner size: decrease as zoom increases
        corner_size = self.BASE_CORNER_SIZE / scale
        corner_size = max(self.MIN_CORNER_SIZE, min(corner_size, self.MAX_CORNER_SIZE))
        
        # Edge threshold: decrease as zoom increases
        edge_threshold = self.BASE_EDGE_THRESHOLD / scale
        edge_threshold = max(2, min(edge_threshold, 8))
        
        return corner_size, edge_threshold
    
    def _get_handles(self) -> dict:
        """Return corner handle points (dynamic size)."""
        r = self.rect()
        cs, _ = self._get_dynamic_sizes()
        
        return {
            'tl': QRectF(r.left() - cs/2, r.top() - cs/2, cs, cs),
            'tr': QRectF(r.right() - cs/2, r.top() - cs/2, cs, cs),
            'bl': QRectF(r.left() - cs/2, r.bottom() - cs/2, cs, cs),
            'br': QRectF(r.right() - cs/2, r.bottom() - cs/2, cs, cs),
        }
    
    def _get_edge_at(self, pos: QPointF) -> str:
        """Detecting from any point on the edge (dynamic threshold)."""
        r = self.rect()
        cs, t = self._get_dynamic_sizes()
        x, y = pos.x(), pos.y()
        
        # Use corner size for edge detection outside the corner region
        corner_margin = cs / 2
        
        # Top edge (detect edge first)
        if abs(y - r.top()) < t and r.left() + corner_margin < x < r.right() - corner_margin:
            return 'top'
        # Bottom edge
        if abs(y - r.bottom()) < t and r.left() + corner_margin < x < r.right() - corner_margin:
            return 'bottom'
        # Left edge
        if abs(x - r.left()) < t and r.top() + corner_margin < y < r.bottom() - corner_margin:
            return 'left'
        # Right edge
        if abs(x - r.right()) < t and r.top() + corner_margin < y < r.bottom() - corner_margin:
            return 'right'
        return None
    
    def _get_handle_at(self, pos: QPointF) -> str:
        """Check edge first, then corner (edge priority)."""
        # Check edges first
        edge = self._get_edge_at(pos)
        if edge:
            return edge
        # Then check corners
        handles = self._get_handles()
        for name, rect in handles.items():
            if rect.contains(pos):
                return name
        return None
    
    def _get_cursor_for_handle(self, handle: str):
        """Return cursor for handle."""
        cursors = {
            'tl': Qt.CursorShape.SizeFDiagCursor,
            'br': Qt.CursorShape.SizeFDiagCursor,
            'tr': Qt.CursorShape.SizeBDiagCursor,
            'bl': Qt.CursorShape.SizeBDiagCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
        }
        return cursors.get(handle, Qt.CursorShape.ArrowCursor)
    
    def paint(self, painter: QPainter, option, widget=None):
        """Draw only bbox - no handle circles."""
        super().paint(painter, option, widget)
        # Handle circles removed - dashed line used as selection indicator only
    
    def hoverMoveEvent(self, event):
        """Update cursor on hover."""
        if self.isSelected():
            handle = self._get_handle_at(event.pos())
            if handle:
                self.setCursor(self._get_cursor_for_handle(handle))
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
                handle = self._get_handle_at(event.pos())
                if handle:
                    # Start resize
                    self._resize_handle = handle
                    self._resize_start_rect = self.rect()
                    self._resize_start_pos = event.pos()
                    event.accept()
                    return
            # Save start position for drag
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Mouse move."""
        if self._resize_handle:
            # Resize operation
            delta = event.pos() - self._resize_start_pos
            old_rect = self._resize_start_rect
            new_rect = QRectF(old_rect)
            
            handle = self._resize_handle
            
            # Corner resize
            if handle == 'tl':
                new_rect.setTopLeft(old_rect.topLeft() + delta)
            elif handle == 'tr':
                new_rect.setTopRight(old_rect.topRight() + delta)
            elif handle == 'bl':
                new_rect.setBottomLeft(old_rect.bottomLeft() + delta)
            elif handle == 'br':
                new_rect.setBottomRight(old_rect.bottomRight() + delta)
            # Edge resize
            elif handle == 'top':
                new_rect.setTop(old_rect.top() + delta.y())
            elif handle == 'bottom':
                new_rect.setBottom(old_rect.bottom() + delta.y())
            elif handle == 'left':
                new_rect.setLeft(old_rect.left() + delta.x())
            elif handle == 'right':
                new_rect.setRight(old_rect.right() + delta.x())
            
            # Minimum size check (3 pixels)
            if new_rect.width() >= self.MIN_RESIZE_SIZE and new_rect.height() >= self.MIN_RESIZE_SIZE:
                self.setRect(new_rect.normalized())
            
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """On mouse release."""
        if self._resize_handle:
            # Resize completed
            self._resize_handle = None
            # Emit rect in scene coordinates
            scene_rect = self.mapRectToScene(self.rect())
            self.signals.rect_changed.emit(self.index, scene_rect)
            event.accept()
            return
        elif self._drag_start_pos is not None:
            # Drag completed - report position change
            if event.pos() != self._drag_start_pos:
                # Emit rect in scene coordinates
                scene_rect = self.mapRectToScene(self.rect())
                self.signals.rect_changed.emit(self.index, scene_rect)
            self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def itemChange(self, change, value):
        """Item change."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_style(value)
            self.signals.selected_changed.emit(self.index, value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Drag completed - report position change
            from PySide6.QtCore import QTimer
            # Send signal with small delay (wait for drag to fully finish)
            QTimer.singleShot(50, self._emit_position_changed)
        return super().itemChange(change, value)
    
    def _emit_position_changed(self):
        """Report position change."""
        scene_rect = self.mapRectToScene(self.rect())
        self.signals.rect_changed.emit(self.index, scene_rect)
    
    def keyPressEvent(self, event):
        """Key events - deletion shortcuts."""
        key = event.key()
        
        # Ignore A/D/Left/Right keys - let them pass to parent window for navigation
        if key in (Qt.Key.Key_A, Qt.Key.Key_D, Qt.Key.Key_Left, Qt.Key.Key_Right):
            event.ignore()
            return
        
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_Escape):
            self.signals.delete_requested.emit(self.index)
            event.accept()
            return
        super().keyPressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Double click - class change menu + switch to select mode."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Switch to select mode first
            self.signals.clicked.emit(self.index)
            # Select item and give focus (needed for key events)
            self.setSelected(True)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            # Show class change popup
            scene_pos = self.mapToScene(event.pos())
            self.signals.class_change_requested.emit(self.index, scene_pos)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
    
    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """Context menu."""
        from PySide6.QtCore import QCoreApplication
        menu = QMenu()
        change_class_action = menu.addAction(QCoreApplication.translate("EditableRectItem", "🏷️ Change Class"))
        menu.addSeparator()
        delete_action = menu.addAction(QCoreApplication.translate("EditableRectItem", "🗑️ Delete"))
        
        action = menu.exec(event.screenPos())
        
        if action == delete_action:
            self.signals.delete_requested.emit(self.index)
        elif action == change_class_action:
            self.signals.class_change_requested.emit(self.index, event.scenePos())
    
    def get_scene_rect(self) -> QRectF:
        """Return rect in scene coordinates."""
        return self.mapRectToScene(self.rect())
    
    def update_class(self, class_id: int, color: QColor):
        """Update class."""
        self.class_id = class_id
        self.color = color
        self._update_style(self.isSelected())
