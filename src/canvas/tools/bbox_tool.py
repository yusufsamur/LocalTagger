"""
Bounding Box Aracı
==================
Dikdörtgen kutu çizimi için araç.
"""

from typing import Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem
from PySide6.QtGui import QPen, QColor, QBrush

from .base_tool import BaseTool, ToolType


class BBoxTool(BaseTool):
    """Bounding Box (Dikdörtgen Kutu) çizim aracı."""
    
    # Varsayılan stil
    DEFAULT_COLOR = QColor(255, 0, 0)  # Kırmızı
    LINE_WIDTH = 2
    FILL_OPACITY = 0.2
    
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        
        # Çizim durumu
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
        """Çizim rengini ayarla."""
        self._color = color
    
    def on_mouse_press(self, pos: QPointF, button: int) -> bool:
        """Çizime başla."""
        if button != Qt.MouseButton.LeftButton:
            return False
            
        if not self._is_active:
            return False
            
        self._is_drawing = True
        self._start_pos = pos
        
        # Geçici dikdörtgen oluştur
        self._create_temp_rect(pos)
        
        return True
    
    def on_mouse_move(self, pos: QPointF) -> bool:
        """Çizimi güncelle."""
        if not self._is_drawing or self._temp_rect is None:
            return False
            
        # Dikdörtgeni güncelle
        self._update_temp_rect(pos)
        
        return True
    
    def on_mouse_release(self, pos: QPointF, button: int) -> bool:
        """Çizimi tamamla."""
        if button != Qt.MouseButton.LeftButton:
            return False
            
        if not self._is_drawing:
            return False
            
        self._is_drawing = False
        
        # Minimum boyut kontrolü (çok küçük kutular oluşmasın)
        if self._temp_rect is not None:
            rect = self._temp_rect.rect()
            if rect.width() < 5 or rect.height() < 5:
                # Çok küçük, iptal et
                self._scene.removeItem(self._temp_rect)
            else:
                # Kalıcı yap (geçici stili kaldır)
                self._finalize_rect()
                
        self._temp_rect = None
        self._start_pos = None
        
        return True
    
    def cancel(self):
        """Mevcut çizimi iptal et."""
        if self._temp_rect is not None:
            self._scene.removeItem(self._temp_rect)
            self._temp_rect = None
        self._is_drawing = False
        self._start_pos = None
    
    # ─────────────────────────────────────────────────────────────────
    # Yardımcı Metodlar
    # ─────────────────────────────────────────────────────────────────
    
    def _create_temp_rect(self, pos: QPointF):
        """Geçici dikdörtgen oluştur."""
        rect = QRectF(pos, pos)
        self._temp_rect = QGraphicsRectItem(rect)
        
        # Stil ayarla
        pen = QPen(self._color, self.LINE_WIDTH)
        pen.setStyle(Qt.PenStyle.DashLine)  # Çizim sırasında kesikli çizgi
        pen.setCosmetic(True)  # Zoom'dan bağımsız sabit çizgi kalınlığı
        self._temp_rect.setPen(pen)
        
        fill_color = QColor(self._color)
        fill_color.setAlphaF(self.FILL_OPACITY)
        self._temp_rect.setBrush(QBrush(fill_color))
        
        self._scene.addItem(self._temp_rect)
    
    def _update_temp_rect(self, pos: QPointF):
        """Geçici dikdörtgeni yeni pozisyona göre güncelle."""
        if self._temp_rect is None or self._start_pos is None:
            return
            
        # Sol-üst ve sağ-alt köşeleri hesapla
        x1 = min(self._start_pos.x(), pos.x())
        y1 = min(self._start_pos.y(), pos.y())
        x2 = max(self._start_pos.x(), pos.x())
        y2 = max(self._start_pos.y(), pos.y())
        
        rect = QRectF(x1, y1, x2 - x1, y2 - y1)
        self._temp_rect.setRect(rect)
    
    def _finalize_rect(self):
        """Dikdörtgeni kalıcı yap."""
        if self._temp_rect is None:
            return
            
        # Düz çizgi stiline geç
        pen = QPen(self._color, self.LINE_WIDTH)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)  # Zoom'dan bağımsız sabit çizgi kalınlığı
        self._temp_rect.setPen(pen)
        
        # TODO: Etiket datasını kaydet
        # TODO: Handles (köşe tutamakları) ekle
