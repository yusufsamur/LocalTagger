"""
Graphics View
=============
Tuval kontrolü: Zoom, Pan ve mouse event handling.
"""

from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QMouseEvent, QWheelEvent, QPainter

from .graphics_scene import AnnotationScene


class AnnotationView(QGraphicsView):
    """
    Etiketleme tuvalinin görünüm sınıfı.
    Zoom, Pan ve çizim araç kontrollerini sağlar.
    """
    
    # Sinyaller
    zoom_changed = Signal(float)  # Zoom seviyesi değişti
    mouse_position = Signal(int, int)  # Mouse pozisyonu (piksel)
    
    # Zoom limitleri
    MIN_ZOOM = 0.1
    MAX_ZOOM = 10.0
    ZOOM_FACTOR = 1.15
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Sahne oluştur
        self._scene = AnnotationScene(self)
        self.setScene(self._scene)
        
        # Görünüm ayarları
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # Durum değişkenleri
        self._zoom_level = 1.0
        self._is_panning = False
        self._pan_start_pos = QPointF()
        
    @property
    def scene(self) -> AnnotationScene:
        """Sahne nesnesini döndürür."""
        return self._scene
    
    @property
    def zoom_level(self) -> float:
        """Mevcut zoom seviyesini döndürür."""
        return self._zoom_level
    
    # ─────────────────────────────────────────────────────────────────
    # Zoom İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def zoom_in(self):
        """Yakınlaştır."""
        self._apply_zoom(self.ZOOM_FACTOR)
        
    def zoom_out(self):
        """Uzaklaştır."""
        self._apply_zoom(1 / self.ZOOM_FACTOR)
        
    def zoom_fit(self):
        """Görseli pencereye sığdır."""
        if self._scene.has_image:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom_level = self.transform().m11()
            self.zoom_changed.emit(self._zoom_level)
            
    def zoom_reset(self):
        """Zoom'u %100'e sıfırla."""
        self.resetTransform()
        self._zoom_level = 1.0
        self.zoom_changed.emit(self._zoom_level)
        
    def _apply_zoom(self, factor: float):
        """Zoom faktörünü uygular."""
        new_zoom = self._zoom_level * factor
        
        # Limitleri kontrol et
        if new_zoom < self.MIN_ZOOM or new_zoom > self.MAX_ZOOM:
            return
            
        self.scale(factor, factor)
        self._zoom_level = new_zoom
        self.zoom_changed.emit(self._zoom_level)
    
    # ─────────────────────────────────────────────────────────────────
    # Mouse Events
    # ─────────────────────────────────────────────────────────────────
    
    def wheelEvent(self, event: QWheelEvent):
        """Mouse tekerleği ile zoom."""
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
            
    def mousePressEvent(self, event: QMouseEvent):
        """Mouse basma olayı."""
        # Orta tuş veya Space + Sol tuş ile pan başlat
        if event.button() == Qt.MouseButton.MiddleButton:
            self._start_panning(event)
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event: QMouseEvent):
        """Mouse hareket olayı."""
        # Pan işlemi
        if self._is_panning:
            self._update_panning(event)
        else:
            # Mouse pozisyonunu sahne koordinatlarına çevir
            scene_pos = self.mapToScene(event.pos())
            if self._scene.has_image:
                self.mouse_position.emit(int(scene_pos.x()), int(scene_pos.y()))
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Mouse bırakma olayı."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._stop_panning()
        else:
            super().mouseReleaseEvent(event)
    
    # ─────────────────────────────────────────────────────────────────
    # Pan İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def _start_panning(self, event: QMouseEvent):
        """Pan işlemini başlat."""
        self._is_panning = True
        self._pan_start_pos = event.position()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        
    def _update_panning(self, event: QMouseEvent):
        """Pan işlemini güncelle."""
        delta = event.position() - self._pan_start_pos
        self._pan_start_pos = event.position()
        
        # Scroll bar'ları hareket ettir
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - int(delta.x())
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - int(delta.y())
        )
        
    def _stop_panning(self):
        """Pan işlemini durdur."""
        self._is_panning = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
