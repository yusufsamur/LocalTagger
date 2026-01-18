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
    
    BASE_CORNER_SIZE = 6  # Temel köşe algılama boyutu
    MIN_CORNER_SIZE = 3   # Minimum köşe boyutu
    MAX_CORNER_SIZE = 10  # Maksimum köşe boyutu
    BASE_EDGE_THRESHOLD = 4  # Temel kenar algılama eşiği
    MIN_RESIZE_SIZE = 3   # Minimum bbox boyutu (piksel)
    
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
            pen = QPen(self.color, 2)
            pen.setStyle(Qt.PenStyle.DashLine)  # Seçiliyken kesikli çizgi
        else:
            pen = QPen(self.color, 2)
            pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)  # Zoom'dan bağımsız sabit çizgi kalınlığı
        self.setPen(pen)
        
        fill = QColor(self.color)
        fill.setAlphaF(0.15 if not selected else 0.25)
        self.setBrush(QBrush(fill))
        
    def _get_dynamic_sizes(self) -> tuple:
        """Zoom seviyesine göre dinamik köşe ve kenar boyutları."""
        scale = 1.0
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            scale = view.transform().m11()
        if scale <= 0:
            scale = 1.0
        
        # Köşe boyutu: zoom arttıkça küçülsun
        corner_size = self.BASE_CORNER_SIZE / scale
        corner_size = max(self.MIN_CORNER_SIZE, min(corner_size, self.MAX_CORNER_SIZE))
        
        # Kenar eşiği: zoom arttıkça küçülsun
        edge_threshold = self.BASE_EDGE_THRESHOLD / scale
        edge_threshold = max(2, min(edge_threshold, 8))
        
        return corner_size, edge_threshold
    
    def _get_handles(self) -> dict:
        """Köşe handle noktalarını döndür (dinamik boyut)."""
        r = self.rect()
        cs, _ = self._get_dynamic_sizes()
        
        return {
            'tl': QRectF(r.left() - cs/2, r.top() - cs/2, cs, cs),
            'tr': QRectF(r.right() - cs/2, r.top() - cs/2, cs, cs),
            'bl': QRectF(r.left() - cs/2, r.bottom() - cs/2, cs, cs),
            'br': QRectF(r.right() - cs/2, r.bottom() - cs/2, cs, cs),
        }
    
    def _get_edge_at(self, pos: QPointF) -> str:
        """Kenarın herhangi bir noktasından algılama (dinamik eşik)."""
        r = self.rect()
        cs, t = self._get_dynamic_sizes()
        x, y = pos.x(), pos.y()
        
        # Köşe bölgesi dışındaki kenar algılaması için köşe boyutunu kullan
        corner_margin = cs / 2
        
        # Üst kenar (önce kenar algılama)
        if abs(y - r.top()) < t and r.left() + corner_margin < x < r.right() - corner_margin:
            return 'top'
        # Alt kenar
        if abs(y - r.bottom()) < t and r.left() + corner_margin < x < r.right() - corner_margin:
            return 'bottom'
        # Sol kenar
        if abs(x - r.left()) < t and r.top() + corner_margin < y < r.bottom() - corner_margin:
            return 'left'
        # Sağ kenar
        if abs(x - r.right()) < t and r.top() + corner_margin < y < r.bottom() - corner_margin:
            return 'right'
        return None
    
    def _get_handle_at(self, pos: QPointF) -> str:
        """Önce kenar, sonra köşe kontrol et (kenar önceliği)."""
        # Önce kenarları kontrol et
        edge = self._get_edge_at(pos)
        if edge:
            return edge
        # Sonra köşeleri kontrol et
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
        """Sadece bbox çiz - handle daireleri yok."""
        super().paint(painter, option, widget)
        # Handle daireleri kaldırıldı - sadece kesikli çizgi seçim göstergesi olarak kullanılıyor
    
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
            
            # Minimum boyut kontrolü (3 piksel)
            if new_rect.width() >= self.MIN_RESIZE_SIZE and new_rect.height() >= self.MIN_RESIZE_SIZE:
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
            # Item'ı seç ve focus ver (klavye olayları için gerekli)
            self.setSelected(True)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
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
