"""
Graphics View
=============
Tuval kontrolü: Zoom, Pan, Crosshair ve mouse event handling.
"""

from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsLineItem, QGraphicsPolygonItem, 
    QGraphicsEllipseItem, QGraphicsRectItem
)
from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QLineF
from PySide6.QtGui import (
    QMouseEvent, QWheelEvent, QPainter, QPen, QColor, QBrush,
    QDragEnterEvent, QDropEvent, QPolygonF, QKeyEvent
)

from .graphics_scene import AnnotationScene
from .editable_rect_item import EditableRectItem
from .editable_polygon_item import EditablePolygonItem


class AnnotationView(QGraphicsView):
    """
    Etiketleme tuvalinin görünüm sınıfı.
    Zoom, Pan, Crosshair ve çizim araç kontrollerini sağlar.
    """
    
    # Sinyaller
    zoom_changed = Signal(float)
    mouse_position = Signal(int, int)
    bbox_created = Signal(float, float, float, float)  # x1, y1, x2, y2
    polygon_created = Signal(list)  # [(x1,y1), (x2,y2), ...]
    files_dropped = Signal(list)
    
    # BBox düzenleme sinyalleri
    bbox_moved = Signal(int, QRectF)  # (index, new_rect)
    bbox_class_change_requested = Signal(int, QPointF)  # (index, position)
    bbox_delete_requested = Signal(int)  # index
    
    # Polygon düzenleme sinyalleri
    polygon_moved = Signal(int, list)  # (index, new_points)
    polygon_class_change_requested = Signal(int, QPointF)  # (index, position)
    polygon_delete_requested = Signal(int)  # index
    
    # Annotation tıklama sinyali - otomatik select moduna geçiş için
    annotation_clicked = Signal()  # herhangi bir annotasyona tıklandığında
    
    # SAM AI sinyali
    sam_click_requested = Signal(int, int, str)  # (x, y, mode) - AI ile tıklama
    sam_box_requested = Signal(int, int, int, int)  # (x1, y1, x2, y2) - AI ile bbox'tan polygon
    
    # Zoom limitleri
    MIN_ZOOM = 0.1
    MAX_ZOOM = 10.0
    ZOOM_FACTOR = 1.15
    
    # Araç tipleri
    TOOL_NONE = "none"
    TOOL_SELECT = "select"
    TOOL_BBOX = "bbox"
    TOOL_POLYGON = "polygon"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Sahne oluştur
        self._scene = AnnotationScene(self)
        self.setScene(self._scene)
        
        # Drag & Drop aktif
        self.setAcceptDrops(True)
        
        # Görünüm ayarları
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)  # Crosshair için gerekli
        
        # Durum değişkenleri
        self._zoom_level = 1.0
        self._is_panning = False
        self._pan_start_pos = QPointF()
        
        # Araç durumu
        self._current_tool = self.TOOL_NONE
        self._is_drawing = False
        self._draw_start_pos = QPointF()
        self._temp_rect_item = None
        
        # Polygon çizim durumu
        self._polygon_points: List[QPointF] = []
        self._temp_polygon_item = None
        self._temp_polygon_lines = []  # Geçici çizgi öğeleri
        self._temp_polygon_dots = []   # Nokta göstergeleri
        
        # Crosshair çizgileri
        self._crosshair_h = None
        self._crosshair_v = None
        self._crosshair_visible = False
        
        # Çizim rengi
        self._draw_color = QColor(255, 50, 50)
        self._crosshair_color = QColor(0, 200, 255, 180)
        
        # Çizilmiş annotation öğeleri (kalici etiketler)
        self._annotation_items: List = []
        
        # SAM modu
        self._sam_enabled = False
        
        # Polygon+AI için bbox çizimi
        self._is_drawing_bbox_for_polygon = False
        
    @property
    def scene(self) -> AnnotationScene:
        return self._scene
    
    @property
    def zoom_level(self) -> float:
        return self._zoom_level
    
    # ─────────────────────────────────────────────────────────────────
    # Drag & Drop
    # ─────────────────────────────────────────────────────────────────
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Sürükleme girişi."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):
        """Sürükleme hareketi."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        """Bırakma olayı."""
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path:
                    paths.append(path)
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()
    
    # ─────────────────────────────────────────────────────────────────
    # Crosshair (Kılavuz Çizgiler)
    # ─────────────────────────────────────────────────────────────────
    
    def _show_crosshair(self):
        """Crosshair'i göster."""
        if self._crosshair_visible:
            return
            
        pen = QPen(self._crosshair_color, 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        
        # Yatay çizgi
        self._crosshair_h = QGraphicsLineItem()
        self._crosshair_h.setPen(pen)
        self._crosshair_h.setZValue(1000)
        self._scene.addItem(self._crosshair_h)
        
        # Dikey çizgi
        self._crosshair_v = QGraphicsLineItem()
        self._crosshair_v.setPen(pen)
        self._crosshair_v.setZValue(1000)
        self._scene.addItem(self._crosshair_v)
        
        self._crosshair_visible = True
        
    def _hide_crosshair(self):
        """Crosshair'i gizle."""
        if not self._crosshair_visible:
            return
        
        # C++ nesnesi hala geçerli mi kontrol et
        try:
            if self._crosshair_h is not None:
                # Nesne hala sahne içindeyse kaldır
                if self._crosshair_h.scene() is not None:
                    self._scene.removeItem(self._crosshair_h)
        except RuntimeError:
            pass  # C++ nesnesi zaten silinmiş
        finally:
            self._crosshair_h = None
            
        try:
            if self._crosshair_v is not None:
                if self._crosshair_v.scene() is not None:
                    self._scene.removeItem(self._crosshair_v)
        except RuntimeError:
            pass
        finally:
            self._crosshair_v = None
            
        self._crosshair_visible = False
        
    def _update_crosshair(self, scene_pos: QPointF):
        """Crosshair pozisyonunu güncelle."""
        if not self._crosshair_visible or not self._scene.has_image:
            return
        
        # C++ nesneleri hala geçerli mi kontrol et
        try:
            if self._crosshair_h is None or self._crosshair_v is None:
                self._crosshair_visible = False
                return
            # Sahne içindeler mi kontrol et
            if self._crosshair_h.scene() is None or self._crosshair_v.scene() is None:
                self._crosshair_visible = False
                self._crosshair_h = None
                self._crosshair_v = None
                return
        except RuntimeError:
            # C++ nesnesi silinmiş
            self._crosshair_visible = False
            self._crosshair_h = None
            self._crosshair_v = None
            return
            
        img_w, img_h = self._scene.image_size
        x = scene_pos.x()
        y = scene_pos.y()
        
        # Görsel sınırları içinde tut
        x = max(0, min(x, img_w))
        y = max(0, min(y, img_h))
        
        # Yatay çizgi (tam genişlik)
        self._crosshair_h.setLine(QLineF(0, y, img_w, y))
        # Dikey çizgi (tam yükseklik)
        self._crosshair_v.setLine(QLineF(x, 0, x, img_h))
    
    # ─────────────────────────────────────────────────────────────────
    # Araç Yönetimi
    # ─────────────────────────────────────────────────────────────────
    
    def set_tool(self, tool: str):
        """Aktif aracı değiştir."""
        self.cancel_drawing()
        self._current_tool = tool
        
        if tool in (self.TOOL_BBOX, self.TOOL_POLYGON):
            # CrossCursor'ı hem view hem viewport'a uygula
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            if self._scene.has_image:
                self._show_crosshair()
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.viewport().unsetCursor()
            self._hide_crosshair()
    
    def set_draw_color(self, color: QColor | str):
        """Çizim rengini ayarla."""
        if isinstance(color, str):
            color = QColor(color)
        self._draw_color = color
    
    def set_sam_enabled(self, enabled: bool):
        """SAM modunu etkinleştir/devre dışı bırak."""
        self._sam_enabled = enabled
    
    @property
    def sam_enabled(self) -> bool:
        """SAM modu etkin mi?"""
        return self._sam_enabled
            
    def cancel_drawing(self):
        """Mevcut çizimi iptal et."""
        # BBox temizle
        if self._temp_rect_item:
            try:
                if self._temp_rect_item.scene():
                    self._scene.removeItem(self._temp_rect_item)
            except RuntimeError:
                pass
            self._temp_rect_item = None
        
        # Polygon temizle
        self._clear_polygon_temp_items()
        self._polygon_points.clear()
        
        self._is_drawing = False
    
    def _clear_polygon_temp_items(self):
        """Polygon geçici öğelerini temizle."""
        for item in self._temp_polygon_lines:
            try:
                if item.scene():
                    self._scene.removeItem(item)
            except RuntimeError:
                pass
        self._temp_polygon_lines.clear()
        
        for item in self._temp_polygon_dots:
            try:
                if item.scene():
                    self._scene.removeItem(item)
            except RuntimeError:
                pass
        self._temp_polygon_dots.clear()
        
        if self._temp_polygon_item:
            try:
                if self._temp_polygon_item.scene():
                    self._scene.removeItem(self._temp_polygon_item)
            except RuntimeError:
                pass
            self._temp_polygon_item = None
    
    # ─────────────────────────────────────────────────────────────────
    # Zoom İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def zoom_in(self):
        self._apply_zoom(self.ZOOM_FACTOR)
        
    def zoom_out(self):
        self._apply_zoom(1 / self.ZOOM_FACTOR)
        
    def zoom_fit(self):
        if self._scene.has_image:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_level = self.transform().m11()
            self.zoom_changed.emit(self._zoom_level)
            
    def zoom_reset(self):
        self.resetTransform()
        self._zoom_level = 1.0
        self.zoom_changed.emit(self._zoom_level)
        
    def _apply_zoom(self, factor: float):
        new_zoom = self._zoom_level * factor
        if new_zoom < self.MIN_ZOOM or new_zoom > self.MAX_ZOOM:
            return
        self.scale(factor, factor)
        self._zoom_level = new_zoom
        self.zoom_changed.emit(self._zoom_level)
    
    # ─────────────────────────────────────────────────────────────────
    # Mouse Events
    # ─────────────────────────────────────────────────────────────────
    
    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
            
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_panning(event)
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            if self._scene.has_image:
                # SAM modu etkinse
                if self._sam_enabled:
                    # BBOX modunda: tıklama ile AI inference
                    if self._current_tool == self.TOOL_BBOX:
                        scene_pos = self.mapToScene(event.pos())
                        img_w, img_h = self._scene.image_size
                        x = max(0, min(int(scene_pos.x()), img_w - 1))
                        y = max(0, min(int(scene_pos.y()), img_h - 1))
                        self.sam_click_requested.emit(x, y, "bbox")
                        return
                    # POLYGON modunda: bbox çiz, sonra segmentasyon
                    elif self._current_tool == self.TOOL_POLYGON:
                        self._start_bbox_for_polygon(event)
                        return
                
                if self._current_tool == self.TOOL_BBOX:
                    self._start_bbox_drawing(event)
                    return
                elif self._current_tool == self.TOOL_POLYGON:
                    self._add_polygon_point(event)
                    return
        
        # Sağ tık - polygon'u kapat
        if event.button() == Qt.MouseButton.RightButton:
            if self._current_tool == self.TOOL_POLYGON and len(self._polygon_points) >= 3:
                self._finish_polygon()
                return
                
        super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event: QMouseEvent):
        # Pan işlemi
        if self._is_panning:
            self._update_panning(event)
            return
        
        scene_pos = self.mapToScene(event.pos())
        
        # Crosshair güncelle
        if self._current_tool in (self.TOOL_BBOX, self.TOOL_POLYGON) and self._scene.has_image:
            self._update_crosshair(scene_pos)
            
        # BBox çizimi (normal veya polygon+AI için)
        if self._is_drawing and self._temp_rect_item:
            if self._is_drawing_bbox_for_polygon:
                self._update_bbox_for_polygon(event)
            else:
                self._update_bbox_drawing(event)
            
        # Polygon preview çizgisi
        if self._current_tool == self.TOOL_POLYGON and self._polygon_points:
            self._update_polygon_preview(scene_pos)
            
        # Mouse pozisyonunu bildir
        if self._scene.has_image:
            x = max(0, min(int(scene_pos.x()), self._scene.image_size[0] - 1))
            y = max(0, min(int(scene_pos.y()), self._scene.image_size[1] - 1))
            self.mouse_position.emit(x, y)
            
        super().mouseMoveEvent(event)
        
    def leaveEvent(self, event):
        if self._crosshair_visible:
            self._hide_crosshair()
        super().leaveEvent(event)
        
    def enterEvent(self, event):
        if self._current_tool in (self.TOOL_BBOX, self.TOOL_POLYGON) and self._scene.has_image:
            self._show_crosshair()
        super().enterEvent(event)
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._stop_panning()
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_drawing:
                if self._is_drawing_bbox_for_polygon:
                    self._finish_bbox_for_polygon(event)
                    return
                elif self._current_tool == self.TOOL_BBOX:
                    self._finish_bbox_drawing(event)
                    return
                
        super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Klavye olayları."""
        # Polygon çizim sırasında
        if self._current_tool == self.TOOL_POLYGON and self._polygon_points:
            # Enter - polygon'u kapat
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if len(self._polygon_points) >= 3:
                    self._finish_polygon()
                return
            # Backspace - son noktayı sil
            elif event.key() == Qt.Key.Key_Backspace:
                self._remove_last_polygon_point()
                return
            # ESC - polygon çizimini iptal et
            elif event.key() == Qt.Key.Key_Escape:
                self.cancel_drawing()
                return
                
        super().keyPressEvent(event)
    
    # ─────────────────────────────────────────────────────────────────
    # Pan İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def _start_panning(self, event: QMouseEvent):
        self._is_panning = True
        self._pan_start_pos = event.position()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._hide_crosshair()
        
    def _update_panning(self, event: QMouseEvent):
        delta = event.position() - self._pan_start_pos
        self._pan_start_pos = event.position()
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - int(delta.x())
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - int(delta.y())
        )
        
    def _stop_panning(self):
        self._is_panning = False
        if self._current_tool == self.TOOL_BBOX:
            self.setCursor(Qt.CursorShape.CrossCursor)
            if self._scene.has_image:
                self._show_crosshair()
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    # ─────────────────────────────────────────────────────────────────
    # BBox Çizimi
    # ─────────────────────────────────────────────────────────────────
    
    def _start_bbox_drawing(self, event: QMouseEvent):
        self._is_drawing = True
        self._draw_start_pos = self.mapToScene(event.pos())
        
        from PySide6.QtWidgets import QGraphicsRectItem
        
        self._temp_rect_item = QGraphicsRectItem(QRectF(self._draw_start_pos, self._draw_start_pos))
        
        pen = QPen(self._draw_color, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCosmetic(True)  # Zoom'dan bağımsız sabit çizgi kalınlığı
        self._temp_rect_item.setPen(pen)
        
        fill = QColor(self._draw_color)
        fill.setAlphaF(0.2)
        self._temp_rect_item.setBrush(QBrush(fill))
        
        self._scene.addItem(self._temp_rect_item)
        
    def _update_bbox_drawing(self, event: QMouseEvent):
        if not self._temp_rect_item:
            return
            
        current_pos = self.mapToScene(event.pos())
        
        x1 = min(self._draw_start_pos.x(), current_pos.x())
        y1 = min(self._draw_start_pos.y(), current_pos.y())
        x2 = max(self._draw_start_pos.x(), current_pos.x())
        y2 = max(self._draw_start_pos.y(), current_pos.y())
        
        img_w, img_h = self._scene.image_size
        x1 = max(0, min(x1, img_w))
        y1 = max(0, min(y1, img_h))
        x2 = max(0, min(x2, img_w))
        y2 = max(0, min(y2, img_h))
        
        self._temp_rect_item.setRect(QRectF(x1, y1, x2 - x1, y2 - y1))
        
    def _finish_bbox_drawing(self, event: QMouseEvent):
        self._is_drawing = False
        
        if not self._temp_rect_item:
            return
            
        rect = self._temp_rect_item.rect()
        
        if rect.width() < 5 or rect.height() < 5:
            self._scene.removeItem(self._temp_rect_item)
            self._temp_rect_item = None
            return
            
        pen = QPen(self._draw_color, 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)  # Zoom'dan bağımsız sabit çizgi kalınlığı
        self._temp_rect_item.setPen(pen)
        
        # Etiket listesine ekle
        self._annotation_items.append(self._temp_rect_item)
        
        self.bbox_created.emit(rect.x(), rect.y(), rect.right(), rect.bottom())
        
        self._temp_rect_item = None
    
    # ─────────────────────────────────────────────────────────────────
    # Polygon+AI için BBox Çizimi (bbox → SAM → polygon)
    # ─────────────────────────────────────────────────────────────────
    
    def _start_bbox_for_polygon(self, event: QMouseEvent):
        """Polygon+AI modunda bbox çizimini başlat."""
        self._is_drawing = True
        self._is_drawing_bbox_for_polygon = True
        self._draw_start_pos = self.mapToScene(event.pos())
        
        from PySide6.QtWidgets import QGraphicsRectItem
        
        self._temp_rect_item = QGraphicsRectItem(QRectF(self._draw_start_pos, self._draw_start_pos))
        
        # Özel stil: mor renkli kesikli çizgi
        pen = QPen(QColor(180, 100, 255), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._temp_rect_item.setPen(pen)
        
        fill = QColor(180, 100, 255)
        fill.setAlphaF(0.15)
        self._temp_rect_item.setBrush(QBrush(fill))
        
        self._scene.addItem(self._temp_rect_item)
    
    def _update_bbox_for_polygon(self, event: QMouseEvent):
        """Polygon+AI bbox çizimini güncelle."""
        if not self._temp_rect_item:
            return
            
        current_pos = self.mapToScene(event.pos())
        
        x1 = min(self._draw_start_pos.x(), current_pos.x())
        y1 = min(self._draw_start_pos.y(), current_pos.y())
        x2 = max(self._draw_start_pos.x(), current_pos.x())
        y2 = max(self._draw_start_pos.y(), current_pos.y())
        
        img_w, img_h = self._scene.image_size
        x1 = max(0, min(x1, img_w))
        y1 = max(0, min(y1, img_h))
        x2 = max(0, min(x2, img_w))
        y2 = max(0, min(y2, img_h))
        
        self._temp_rect_item.setRect(QRectF(x1, y1, x2 - x1, y2 - y1))
    
    def _finish_bbox_for_polygon(self, event: QMouseEvent):
        """Polygon+AI bbox çizimini tamamla ve SAM'a gönder."""
        self._is_drawing = False
        self._is_drawing_bbox_for_polygon = False
        
        if not self._temp_rect_item:
            return
            
        rect = self._temp_rect_item.rect()
        
        if rect.width() < 5 or rect.height() < 5:
            self._scene.removeItem(self._temp_rect_item)
            self._temp_rect_item = None
            return
        
        # Geçici rect'i kaldır
        self._scene.removeItem(self._temp_rect_item)
        self._temp_rect_item = None
        
        # SAM'a bbox gönder
        x1 = int(rect.x())
        y1 = int(rect.y())
        x2 = int(rect.right())
        y2 = int(rect.bottom())
        self.sam_box_requested.emit(x1, y1, x2, y2)
    
    # ─────────────────────────────────────────────────────────────────
    # Polygon Çizimi
    # ─────────────────────────────────────────────────────────────────
    
    def _add_polygon_point(self, event: QMouseEvent):
        """Polygon'a yeni nokta ekle."""
        scene_pos = self.mapToScene(event.pos())
        
        # Görsel sınırları içinde tut
        img_w, img_h = self._scene.image_size
        x = max(0, min(scene_pos.x(), img_w))
        y = max(0, min(scene_pos.y(), img_h))
        pos = QPointF(x, y)
        
        # İlk noktaya yakın tıklandıysa polygon'u kapat
        if len(self._polygon_points) >= 3:
            first_point = self._polygon_points[0]
            distance = ((pos.x() - first_point.x()) ** 2 + (pos.y() - first_point.y()) ** 2) ** 0.5
            if distance < 15:  # 15 piksel mesafe
                self._finish_polygon()
                return
        
        self._polygon_points.append(pos)
        
        # Nokta göstergesi ekle (ilk nokta özel görünüm)
        is_first = len(self._polygon_points) == 1
        dot_size = 12 if is_first else 8
        dot = QGraphicsEllipseItem(x - dot_size/2, y - dot_size/2, dot_size, dot_size)
        
        if is_first:
            # İlk nokta farklı renk (kapatma ipucu)
            dot.setBrush(QBrush(QColor("#FFD700")))  # Altın sarısı
            first_pen = QPen(self._draw_color, 2)
            first_pen.setCosmetic(True)
            dot.setPen(first_pen)
        else:
            dot.setBrush(QBrush(self._draw_color))
            other_pen = QPen(Qt.GlobalColor.white, 1)
            other_pen.setCosmetic(True)
            dot.setPen(other_pen)
        
        dot.setZValue(100)
        self._scene.addItem(dot)
        self._temp_polygon_dots.append(dot)
        
        # Çizgi ekle (en az 2 nokta varsa)
        if len(self._polygon_points) >= 2:
            p1 = self._polygon_points[-2]
            p2 = self._polygon_points[-1]
            line = QGraphicsLineItem(QLineF(p1, p2))
            pen = QPen(self._draw_color, 2)
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            line.setPen(pen)
            line.setZValue(99)
            self._scene.addItem(line)
            self._temp_polygon_lines.append(line)
    
    def _update_polygon_preview(self, scene_pos: QPointF):
        """Polygon önizleme çizgisini güncelle (son nokta → mouse)."""
        if not self._polygon_points:
            return
            
        # Geçici preview çizgisi varsa kaldır
        if self._temp_polygon_item:
            try:
                if self._temp_polygon_item.scene():
                    self._scene.removeItem(self._temp_polygon_item)
            except RuntimeError:
                pass
            self._temp_polygon_item = None
        
        # Son noktadan mouse'a çizgi çiz
        last_point = self._polygon_points[-1]
        line = QGraphicsLineItem(QLineF(last_point, scene_pos))
        pen = QPen(self._draw_color, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        line.setPen(pen)
        line.setZValue(98)
        self._scene.addItem(line)
        self._temp_polygon_item = line
    
    def _remove_last_polygon_point(self):
        """Son polygon noktasını sil."""
        if not self._polygon_points:
            return
            
        self._polygon_points.pop()
        
        # Son nokta göstergesini sil
        if self._temp_polygon_dots:
            dot = self._temp_polygon_dots.pop()
            try:
                if dot.scene():
                    self._scene.removeItem(dot)
            except RuntimeError:
                pass
        
        # Son çizgiyi sil
        if self._temp_polygon_lines:
            line = self._temp_polygon_lines.pop()
            try:
                if line.scene():
                    self._scene.removeItem(line)
            except RuntimeError:
                pass
    
    def _finish_polygon(self):
        """Polygon çizimini tamamla."""
        if len(self._polygon_points) < 3:
            self.cancel_drawing()
            return
        
        # Kalıcı polygon oluştur
        polygon = QPolygonF(self._polygon_points)
        polygon_item = QGraphicsPolygonItem(polygon)
        
        pen = QPen(self._draw_color, 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        polygon_item.setPen(pen)
        
        fill = QColor(self._draw_color)
        fill.setAlphaF(0.2)
        polygon_item.setBrush(QBrush(fill))
        polygon_item.setZValue(10)
        
        self._scene.addItem(polygon_item)
        self._annotation_items.append(polygon_item)
        
        # Piksel koordinatlarını listeye çevir
        points = [(p.x(), p.y()) for p in self._polygon_points]
        
        # Geçici öğeleri temizle
        self._clear_polygon_temp_items()
        self._polygon_points.clear()
        
        # Sinyal gönder
        self.polygon_created.emit(points)
    
    # ─────────────────────────────────────────────────────────────────
    # Annotation Render (Etiket Kalıcılığı)
    # ─────────────────────────────────────────────────────────────────
    
    def clear_annotations(self):
        """Çizilmiş etiketleri temizle."""
        for item in self._annotation_items:
            try:
                if item.scene() is not None:
                    self._scene.removeItem(item)
            except RuntimeError:
                pass
        self._annotation_items.clear()
    
    def draw_annotations(self, bboxes: list, polygons: list, class_manager):
        """
        Kayıtlı etiketleri canvas'a çiz.
        
        Args:
            bboxes: BoundingBox listesi
            polygons: Polygon listesi
            class_manager: Renk bilgisi için ClassManager
        """
        if not self._scene.has_image:
            return
            
        img_w, img_h = self._scene.image_size
        if img_w == 0 or img_h == 0:
            return
        
        # Önceki etiketleri temizle
        self.clear_annotations()
        
        # BBox'ları çiz (düzenlenebilir)
        for idx, bbox in enumerate(bboxes):
            # Normalize koordinatları piksel koordinatlarına çevir
            x_center = bbox.x_center * img_w
            y_center = bbox.y_center * img_h
            width = bbox.width * img_w
            height = bbox.height * img_h
            
            x1 = x_center - width / 2
            y1 = y_center - height / 2
            
            # Sınıf rengi al
            label_class = class_manager.get_by_id(bbox.class_id)
            color = QColor(label_class.color) if label_class else QColor("#888888")
            
            # Düzenlenebilir rect oluştur
            rect_item = EditableRectItem(
                QRectF(x1, y1, width, height),
                index=idx,
                class_id=bbox.class_id,
                color=color
            )
            rect_item.setZValue(10)
            
            # Sinyalleri bağla
            rect_item.signals.rect_changed.connect(self.bbox_moved.emit)
            rect_item.signals.class_change_requested.connect(self.bbox_class_change_requested.emit)
            rect_item.signals.delete_requested.connect(self.bbox_delete_requested.emit)
            rect_item.signals.clicked.connect(lambda idx: self.annotation_clicked.emit())
            
            self._scene.addItem(rect_item)
            self._annotation_items.append(rect_item)
        
        # Polygon'ları çiz (düzenlenebilir)
        for idx, polygon in enumerate(polygons):
            # Normalize koordinatları piksel koordinatlarına çevir
            points = [QPointF(x * img_w, y * img_h) for x, y in polygon.points]
            
            # Sınıf rengi al
            label_class = class_manager.get_by_id(polygon.class_id)
            color = QColor(label_class.color) if label_class else QColor("#888888")
            
            # Düzenlenebilir polygon oluştur
            polygon_qf = QPolygonF(points)
            polygon_item = EditablePolygonItem(
                polygon_qf,
                index=idx,
                class_id=polygon.class_id,
                color=color
            )
            polygon_item.setZValue(10)
            
            # Sinyalleri bağla
            polygon_item.signals.polygon_changed.connect(self.polygon_moved.emit)
            polygon_item.signals.class_change_requested.connect(self.polygon_class_change_requested.emit)
            polygon_item.signals.delete_requested.connect(self.polygon_delete_requested.emit)
            polygon_item.signals.clicked.connect(lambda idx: self.annotation_clicked.emit())
            
            self._scene.addItem(polygon_item)
            self._annotation_items.append(polygon_item)

