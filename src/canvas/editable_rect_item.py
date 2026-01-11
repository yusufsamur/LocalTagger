"""
Düzenlenebilir BBox Item
========================
Sürüklenebilir ve yeniden boyutlandırılabilir bounding box.
"""

from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsItem, QGraphicsEllipseItem,
    QMenu, QGraphicsSceneContextMenuEvent
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QPen, QColor, QBrush, QPainter, QCursor


class EditableRectSignals(QObject):
    """Sinyaller için yardımcı sınıf."""
    rect_changed = Signal(int, QRectF)  # (index, new_rect)
    class_change_requested = Signal(int, QPointF)  # (index, position)
    delete_requested = Signal(int)  # index


class EditableRectItem(QGraphicsRectItem):
    """
    Düzenlenebilir bounding box item.
    - Sürükleyerek taşıma
    - Köşelerden yeniden boyutlandırma
    - Sağ tık menüsü ile sınıf değiştirme/silme
    """
    
    HANDLE_SIZE = 8
    HANDLE_HOVER_SIZE = 10
    
    def __init__(self, rect: QRectF, index: int, class_id: int, color: QColor, parent=None):
        super().__init__(rect, parent)
        self.index = index
        self.class_id = class_id
        self.color = color
        
        # Sinyaller
        self.signals = EditableRectSignals()
        
        # Seçilebilir ve taşınabilir
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        
        # Stil
        self._update_style()
        
        # Resize durumu
        self._resize_handle = None  # 'tl', 'tr', 'bl', 'br' veya None
        self._resize_start_rect = None
        self._resize_start_pos = None
        self._is_hovering_handle = False
        
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
        
    def _get_handles(self) -> dict:
        """Köşe noktalarını döndür."""
        r = self.rect()
        hs = self.HANDLE_SIZE
        return {
            'tl': QRectF(r.left() - hs/2, r.top() - hs/2, hs, hs),
            'tr': QRectF(r.right() - hs/2, r.top() - hs/2, hs, hs),
            'bl': QRectF(r.left() - hs/2, r.bottom() - hs/2, hs, hs),
            'br': QRectF(r.right() - hs/2, r.bottom() - hs/2, hs, hs),
        }
    
    def _get_handle_at(self, pos: QPointF) -> str:
        """Pozisyondaki handle'ı döndür."""
        handles = self._get_handles()
        for name, rect in handles.items():
            if rect.contains(pos):
                return name
        return None
    
    def paint(self, painter: QPainter, option, widget=None):
        """Çizim - handle'ları da çiz."""
        super().paint(painter, option, widget)
        
        if self.isSelected():
            # Handle'ları çiz
            handles = self._get_handles()
            painter.setBrush(QBrush(Qt.GlobalColor.white))
            painter.setPen(QPen(self.color, 2))
            
            for name, rect in handles.items():
                painter.drawEllipse(rect)
    
    def hoverMoveEvent(self, event):
        """Hover'da cursor'u güncelle."""
        handle = self._get_handle_at(event.pos())
        if handle:
            if handle in ('tl', 'br'):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            self._is_hovering_handle = True
        else:
            if self.isSelected():
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self._is_hovering_handle = False
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        """Hover çıkışı."""
        self.unsetCursor()  # View'ın cursor'una dön
        self._is_hovering_handle = False
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Mouse basıldığında."""
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._get_handle_at(event.pos())
            if handle and self.isSelected():
                # Resize başlat
                self._resize_handle = handle
                self._resize_start_rect = self.rect()
                self._resize_start_pos = event.pos()
                event.accept()
                return
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Mouse hareket."""
        if self._resize_handle:
            # Resize işlemi
            delta = event.pos() - self._resize_start_pos
            old_rect = self._resize_start_rect
            new_rect = QRectF(old_rect)
            
            if self._resize_handle == 'tl':
                new_rect.setTopLeft(old_rect.topLeft() + delta)
            elif self._resize_handle == 'tr':
                new_rect.setTopRight(old_rect.topRight() + delta)
            elif self._resize_handle == 'bl':
                new_rect.setBottomLeft(old_rect.bottomLeft() + delta)
            elif self._resize_handle == 'br':
                new_rect.setBottomRight(old_rect.bottomRight() + delta)
            
            # Minimum boyut kontrolü
            if new_rect.width() >= 10 and new_rect.height() >= 10:
                self.setRect(new_rect.normalized())
            
            event.accept()
            return
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Mouse bırakıldığında."""
        if self._resize_handle:
            # Resize tamamlandı
            self._resize_handle = None
            self.signals.rect_changed.emit(self.index, self.rect())
            event.accept()
            return
        super().mouseReleaseEvent(event)
    
    def itemChange(self, change, value):
        """Item değişikliği."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Taşıma tamamlandı
            pass  # rect değişikliğini mouseRelease'de emit ediyoruz
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_style(value)
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """Çift tıklama - sınıf değiştirme menüsü."""
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            self.signals.class_change_requested.emit(self.index, scene_pos)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
    
    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """Sağ tık menüsü."""
        menu = QMenu()
        change_class_action = menu.addAction("🏷️ Sınıf Değiştir")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Sil")
        delete_action.setShortcut("Delete")
        
        action = menu.exec(event.screenPos())
        
        if action == delete_action:
            self.signals.delete_requested.emit(self.index)
        elif action == change_class_action:
            self.signals.class_change_requested.emit(self.index, event.scenePos())
    
    def get_scene_rect(self) -> QRectF:
        """Sahne koordinatlarında rect döndür."""
        return self.mapRectToScene(self.rect())
    
    def update_class(self, class_id: int, color: QColor):
        """Sınıfı güncelle."""
        self.class_id = class_id
        self.color = color
        self._update_style(self.isSelected())
