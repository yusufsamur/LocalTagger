"""
Sınıf Seçici Popup Widget
=========================
BBox çizimi sonrasında sağ üst köşede açılan sınıf seçim menüsü.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush, QKeyEvent


class ClassSelectorPopup(QFrame):
    """
    Sınıf seçici popup widget.
    BBox çizimi tamamlandığında sağ üst köşede gösterilir.
    """
    
    # Sinyaller
    class_selected = Signal(int)  # Seçilen sınıf ID'si
    cancelled = Signal()
    closed = Signal()  # Popup kapandığında
    navigate_requested = Signal(str)  # 'next' veya 'prev' - foto değiştirme isteği
    
    def __init__(self, class_manager, last_used_class_id: int = 0, parent=None):
        super().__init__(parent)
        self._class_manager = class_manager
        self._last_used_class_id = last_used_class_id
        self._buttons = []
        
        # Drag state for movable popup
        self._drag_pos = None
        
        # Non-modal window - bbox ile etkileşime izin ver
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border: 2px solid #0d6efd;
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #3c3c3c;
            }
            QPushButton:focus {
                background: #0d6efd;
            }
            QLabel {
                color: #888;
                font-size: 11px;
                padding: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Başlık
        title = QLabel("Sınıf Seç (1-9 veya Enter)")
        layout.addWidget(title)
        
        # Sınıf butonları
        for idx, label_class in enumerate(self._class_manager.classes):
            btn = QPushButton()
            btn.setIcon(self._create_color_icon(label_class.color))
            
            # Klavye kısayolu göster (1-9)
            shortcut_text = f"[{idx + 1}]" if idx < 9 else ""
            btn.setText(f"{shortcut_text} {label_class.name}")
            btn.setProperty("class_id", label_class.id)
            
            # Varsayılan sınıfı vurgula
            if label_class.id == self._last_used_class_id:
                btn.setStyleSheet(btn.styleSheet() + "background: #0d6efd;")
                btn.setFocus()
            
            btn.clicked.connect(lambda checked, cid=label_class.id: self._on_class_clicked(cid))
            layout.addWidget(btn)
            self._buttons.append(btn)
        
        # İptal bilgisi
        cancel_label = QLabel("ESC: İptal")
        layout.addWidget(cancel_label)
        
    def _create_color_icon(self, color_hex: str, size: int = 16) -> QIcon:
        """Renk ikonu oluştur."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 3, 3)
        painter.end()
        
        return QIcon(pixmap)
    
    def _on_class_clicked(self, class_id: int):
        """Sınıf butonuna tıklandığında."""
        self.class_selected.emit(class_id)
        self.close()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Klavye olayları."""
        key = event.key()
        
        # ESC - iptal
        if key == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
            return
        
        # Enter - varsayılan sınıfı seç
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.class_selected.emit(self._last_used_class_id)
            self.close()
            return
        
        # A/Left - önceki görsel
        if key in (Qt.Key.Key_A, Qt.Key.Key_Left):
            self.navigate_requested.emit('prev')
            self.close()
            return
        
        # D/Right - sonraki görsel
        if key in (Qt.Key.Key_D, Qt.Key.Key_Right):
            self.navigate_requested.emit('next')
            self.close()
            return
        
        # 1-9 tuşları - sınıf seç
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < len(self._buttons):
                class_id = self._buttons[idx].property("class_id")
                self.class_selected.emit(class_id)
                self.close()
                return
        
        super().keyPressEvent(event)
    
    def show_at(self, global_pos: QPoint):
        """Belirtilen pozisyonda göster."""
        self.move(global_pos)
        self.show()
        self.setFocus()
    
    def closeEvent(self, event):
        """Popup kapandığında sinyal gönder."""
        self.closed.emit()
        super().closeEvent(event)
    
    def mousePressEvent(self, event):
        """Popup'ı sürüklemek için başlangıç pozisyonunu kaydet."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Popup'ı sürükle."""
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + diff)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Sürükleme tamamlandı."""
        self._drag_pos = None
        super().mouseReleaseEvent(event)
