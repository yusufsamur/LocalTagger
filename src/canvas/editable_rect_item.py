"""
Düzenlenebilir BBox Item
========================
Sürüklenebilir ve yeniden boyutlandırılabilir bounding box.
Köşe ve kenarlardan resize destekler.
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
    selected_changed = Signal(int, bool)  # (index, is_selected)
    clicked = Signal(int)  # index - tıklandığında otomatik select moduna geçmek için


class EditableRectItem(QGraphicsRectItem):
    """
    Düzenlenebilir bounding box item.
    - Sürükleyerek taşıma
    - Köşe ve kenarlardan yeniden boyutlandırma
    - Sağ tık menüsü ile sınıf değiştirme/silme
    """
    
    CORNER_HANDLE_SIZE = 10
    EDGE_HANDLE_SIZE = 8
    
    # Handle türleri
    HANDLES = ['tl', 'tr', 'bl', 'br', 'top', 'bottom', 'left', 'right']
    
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
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        
        # Stil
        self._update_style()
        
        # Resize durumu
        self._resize_handle = None
        self._resize_start_rect = None
        self._resize_start_pos = None
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
        
    def _get_handles(self) -> dict:
        """Tüm handle noktalarını döndür (köşe + kenar)."""
        r = self.rect()
        cs = self.CORNER_HANDLE_SIZE
        es = self.EDGE_HANDLE_SIZE
        
        # Kenar orta noktaları
        mid_x = r.left() + r.width() / 2
        mid_y = r.top() + r.height() / 2
        
        return {
            # Köşeler (daha büyük)
            'tl': QRectF(r.left() - cs/2, r.top() - cs/2, cs, cs),
            'tr': QRectF(r.right() - cs/2, r.top() - cs/2, cs, cs),
            'bl': QRectF(r.left() - cs/2, r.bottom() - cs/2, cs, cs),
            'br': QRectF(r.right() - cs/2, r.bottom() - cs/2, cs, cs),
            # Kenarlar (daha küçük, dikdörtgen)
            'top': QRectF(mid_x - es/2, r.top() - es/2, es, es),
            'bottom': QRectF(mid_x - es/2, r.bottom() - es/2, es, es),
            'left': QRectF(r.left() - es/2, mid_y - es/2, es, es),
            'right': QRectF(r.right() - es/2, mid_y - es/2, es, es),
        }
    
    def _get_handle_at(self, pos: QPointF) -> str:
        """Pozisyondaki handle'ı döndür."""
        handles = self._get_handles()
        for name, rect in handles.items():
            if rect.contains(pos):
                return name
        return None
    
    def _get_cursor_for_handle(self, handle: str):
        """Handle için cursor döndür."""
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
        """Çizim - handle'ları da çiz."""
        super().paint(painter, option, widget)
        
        if self.isSelected():
            handles = self._get_handles()
            
            for name, rect in handles.items():
                if name in ('tl', 'tr', 'bl', 'br'):
                    # Köşe handle'ları - yuvarlak, beyaz
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.setPen(QPen(self.color, 2))
                    painter.drawEllipse(rect)
                else:
                    # Kenar handle'ları - kare, açık renk
                    painter.setBrush(QBrush(QColor(200, 200, 200)))
                    painter.setPen(QPen(self.color, 1))
                    painter.drawRect(rect)
    
    def hoverMoveEvent(self, event):
        """Hover'da cursor'u güncelle."""
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
        """Hover çıkışı."""
        self.unsetCursor()
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        """Mouse basıldığında."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.isSelected():
                handle = self._get_handle_at(event.pos())
                if handle:
                    # Resize başlat
                    self._resize_handle = handle
                    self._resize_start_rect = self.rect()
                    self._resize_start_pos = event.pos()
                    event.accept()
                    return
            # Drag için başlangıç pozisyonunu kaydet
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Mouse hareket."""
        if self._resize_handle:
            # Resize işlemi
            delta = event.pos() - self._resize_start_pos
            old_rect = self._resize_start_rect
            new_rect = QRectF(old_rect)
            
            handle = self._resize_handle
            
            # Köşe resize
            if handle == 'tl':
                new_rect.setTopLeft(old_rect.topLeft() + delta)
            elif handle == 'tr':
                new_rect.setTopRight(old_rect.topRight() + delta)
            elif handle == 'bl':
                new_rect.setBottomLeft(old_rect.bottomLeft() + delta)
            elif handle == 'br':
                new_rect.setBottomRight(old_rect.bottomRight() + delta)
            # Kenar resize
            elif handle == 'top':
                new_rect.setTop(old_rect.top() + delta.y())
            elif handle == 'bottom':
                new_rect.setBottom(old_rect.bottom() + delta.y())
            elif handle == 'left':
                new_rect.setLeft(old_rect.left() + delta.x())
            elif handle == 'right':
                new_rect.setRight(old_rect.right() + delta.x())
            
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
            # Sahne koordinatlarında rect gönder
            scene_rect = self.mapRectToScene(self.rect())
            self.signals.rect_changed.emit(self.index, scene_rect)
            event.accept()
            return
        elif self._drag_start_pos is not None:
            # Drag tamamlandı - konum değişikliğini bildir
            if event.pos() != self._drag_start_pos:
                # Sahne koordinatlarında rect gönder
                scene_rect = self.mapRectToScene(self.rect())
                self.signals.rect_changed.emit(self.index, scene_rect)
            self._drag_start_pos = None
        super().mouseReleaseEvent(event)
    
    def itemChange(self, change, value):
        """Item değişikliği."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_style(value)
            self.signals.selected_changed.emit(self.index, value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Drag tamamlandı - konum değişikliğini bildir
            from PySide6.QtCore import QTimer
            # Küçük gecikme ile sinyal gönder (drag tamamen bitsin)
            QTimer.singleShot(50, self._emit_position_changed)
        return super().itemChange(change, value)
    
    def _emit_position_changed(self):
        """Pozisyon değişikliğini bildir."""
        scene_rect = self.mapRectToScene(self.rect())
        self.signals.rect_changed.emit(self.index, scene_rect)
    
    def keyPressEvent(self, event):
        """Klavye olayları - silme kısayolları."""
        key = event.key()
        
        # A/D/Left/Right tuşlarını ignore et - navigasyon için üst pencereye iletilsin
        if key in (Qt.Key.Key_A, Qt.Key.Key_D, Qt.Key.Key_Left, Qt.Key.Key_Right):
            event.ignore()
            return
        
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace, Qt.Key.Key_Escape):
            self.signals.delete_requested.emit(self.index)
            event.accept()
            return
        super().keyPressEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Çift tıklama - sınıf değiştirme menüsü + düzenleme moduna geç."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Önce select moduna geç
            self.signals.clicked.emit(self.index)
            # Sonra sınıf değiştirme popup'ı göster
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
