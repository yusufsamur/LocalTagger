"""
Düzenlenebilir Polygon Item
===========================
Sürüklenebilir köşe noktaları ile düzenlenebilir polygon.
"""

from PySide6.QtWidgets import (
    QGraphicsPolygonItem, QGraphicsItem, QGraphicsEllipseItem,
    QMenu, QGraphicsSceneContextMenuEvent
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QPen, QColor, QBrush, QPainter, QPolygonF


class EditablePolygonSignals(QObject):
    """Sinyaller için yardımcı sınıf."""
    polygon_changed = Signal(int, list)  # (index, new_points)
    class_change_requested = Signal(int, QPointF)  # (index, position)
    delete_requested = Signal(int)  # index
    selected_changed = Signal(int, bool)  # (index, is_selected)
    clicked = Signal(int)  # index - tıklandığında otomatik select moduna geçmek için


class EditablePolygonItem(QGraphicsPolygonItem):
    """
    Düzenlenebilir polygon item.
    - Köşe noktaları sürüklenebilir
    - Sağ tık menüsü ile sınıf değiştirme/silme
    """
    
    VERTEX_SIZE = 10
    
    def __init__(self, polygon: QPolygonF, index: int, class_id: int, color: QColor, parent=None):
        super().__init__(polygon, parent)
        self.index = index
        self.class_id = class_id
        self.color = color
        
        # Sinyaller
        self.signals = EditablePolygonSignals()
        
        # Seçilebilir ve taşınabilir (Q modu ile)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        
        # Stil
        self._update_style()
        
        # Vertex drag durumu
        self._dragging_vertex = -1
        self._drag_start_pos = None
        
    def _update_style(self, selected: bool = False):
        """Görünümü güncelle."""
        if selected:
            pen = QPen(self.color, 3)
        else:
            pen = QPen(self.color, 2)
        self.setPen(pen)
        
        fill = QColor(self.color)
        fill.setAlphaF(0.15 if not selected else 0.25)
        self.setBrush(QBrush(fill))
    
    def _get_vertex_at(self, pos: QPointF) -> int:
        """Pozisyondaki vertex indeksini döndür (-1 = yok)."""
        polygon = self.polygon()
        vs = self.VERTEX_SIZE
        
        for i in range(polygon.count()):
            pt = polygon.at(i)
            rect = QRectF(pt.x() - vs/2, pt.y() - vs/2, vs, vs)
            if rect.contains(pos):
                return i
        return -1
    
    def paint(self, painter: QPainter, option, widget=None):
        """Çizim - vertex'leri de çiz."""
        super().paint(painter, option, widget)
        
        if self.isSelected():
            polygon = self.polygon()
            vs = self.VERTEX_SIZE
            
            for i in range(polygon.count()):
                pt = polygon.at(i)
                rect = QRectF(pt.x() - vs/2, pt.y() - vs/2, vs, vs)
                
                # İlk nokta farklı renk
                if i == 0:
                    painter.setBrush(QBrush(QColor("#FFD700")))
                else:
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                
                painter.setPen(QPen(self.color, 2))
                painter.drawEllipse(rect)
    
    def hoverMoveEvent(self, event):
        """Hover'da cursor'u güncelle."""
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
        """Hover çıkışı."""
        self.unsetCursor()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Mouse basıldığında."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.isSelected():
                vertex = self._get_vertex_at(event.pos())
                if vertex >= 0:
                    # Vertex drag başlat
                    self._dragging_vertex = vertex
                    self._drag_start_pos = event.pos()
                    event.accept()
                    return
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Mouse hareket."""
        if self._dragging_vertex >= 0:
            # Vertex'i sürükle - yeni polygon oluştur
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
        """Mouse bırakıldığında."""
        if self._dragging_vertex >= 0:
            # Vertex drag tamamlandı
            self._dragging_vertex = -1
            self._emit_polygon_changed()
            event.accept()
            return
        elif self._drag_start_pos is not None:
            # Polygon taşıma tamamlandı
            if event.pos() != self._drag_start_pos:
                self._emit_polygon_changed()
            self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def _emit_polygon_changed(self):
        """Polygon değişikliğini bildir - sahne koordinatlarında."""
        polygon = self.polygon()
        # Yerel koordinatları sahne koordinatlarına dönüştür
        points = []
        for i in range(polygon.count()):
            local_pt = polygon.at(i)
            scene_pt = self.mapToScene(local_pt)
            points.append((scene_pt.x(), scene_pt.y()))
        self.signals.polygon_changed.emit(self.index, points)
    
    def itemChange(self, change, value):
        """Item değişikliği."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_style(value)
            self.signals.selected_changed.emit(self.index, value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Drag tamamlandı - konum değişikliğini bildir
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, self._emit_polygon_changed)
        return super().itemChange(change, value)
    
    def keyPressEvent(self, event):
        """Klavye olayları - silme kısayolları."""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_Escape):
            self.signals.delete_requested.emit(self.index)
            event.accept()
            return
        super().keyPressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Çift tıklama - hiçbir şey yapma."""
        super().mouseDoubleClickEvent(event)
    
    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """Sağ tık menüsü."""
        menu = QMenu()
        change_class_action = menu.addAction("🏷️ Sınıf Değiştir")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Sil")
        
        action = menu.exec(event.screenPos())
        
        if action == delete_action:
            self.signals.delete_requested.emit(self.index)
        elif action == change_class_action:
            self.signals.class_change_requested.emit(self.index, event.scenePos())
    
    def update_class(self, class_id: int, color: QColor):
        """Sınıfı güncelle."""
        self.class_id = class_id
        self.color = color
        self._update_style(self.isSelected())
