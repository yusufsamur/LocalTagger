"""
Etiket Özeti Widget
===================
Mevcut görseldeki etiketlerin sınıf bazlı özetini gösterir.
"""

from collections import defaultdict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush

from core.annotation_manager import AnnotationManager
from core.class_manager import ClassManager


class AnnotationListWidget(QWidget):
    """
    Mevcut görseldeki etiketlerin sınıf bazlı özetini gösterir.
    Format: sınıf_adı: sayı (örn: araba: 3, insan: 0)
    """
    
    # Sinyaller
    annotation_selected = Signal(str, int)  # (type: "bbox" | "polygon", index)
    annotation_deleted = Signal(str, int)   # (type, index)
    clear_all_requested = Signal()          # Tümünü sil isteği
    
    def __init__(self, annotation_manager: AnnotationManager, 
                 class_manager: ClassManager, parent=None):
        super().__init__(parent)
        self._annotation_manager = annotation_manager
        self._class_manager = class_manager
        self._current_image: str = ""
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Başlık
        header = QHBoxLayout()
        title = QLabel("📊 Etiket Özeti")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()
        
        # Temizle butonu
        self.clear_btn = QPushButton("🗑")
        self.clear_btn.setFixedSize(24, 24)
        self.clear_btn.setToolTip("Tüm etiketleri sil")
        header.addWidget(self.clear_btn)
        
        layout.addLayout(header)
        
        # Sınıf bazlı özet listesi
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.list_widget.setStyleSheet("""
            QListWidget::item {
                padding: 4px 8px;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.list_widget)
        
        # Bilgi
        self.info_label = QLabel("Görsel seçilmedi")
        self.info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.info_label)
        
    def _connect_signals(self):
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        
    def set_current_image(self, image_path: str):
        """Gösterilen görseli ayarla."""
        self._current_image = image_path
        self.refresh()
        
    def refresh(self):
        """Listeyi yenile - sınıf bazlı özet göster."""
        self.list_widget.clear()
        
        if not self._current_image:
            self.info_label.setText("Görsel seçilmedi")
            return
            
        annotations = self._annotation_manager.get_annotations(self._current_image)
        
        # Sınıf bazlı sayım yap
        class_counts = defaultdict(int)
        
        for bbox in annotations.bboxes:
            class_counts[bbox.class_id] += 1
            
        for polygon in annotations.polygons:
            class_counts[polygon.class_id] += 1
        
        # Tüm sınıfları listele (etiket olmayanları da 0 olarak göster)
        for label_class in self._class_manager.classes:
            count = class_counts.get(label_class.id, 0)
            
            item = QListWidgetItem()
            item.setIcon(self._create_color_icon(label_class.color))
            item.setText(f"{label_class.name}: {count}")
            
            # Eğer etiket varsa kalın font
            if count > 0:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setForeground(QColor("#888888"))
                
            self.list_widget.addItem(item)
        
        # Bilgi güncelle
        total = len(annotations.bboxes) + len(annotations.polygons)
        if total == 0:
            self.info_label.setText("Etiket yok - Çizim yapın")
        else:
            bbox_count = len(annotations.bboxes)
            poly_count = len(annotations.polygons)
            parts = []
            if bbox_count > 0:
                parts.append(f"{bbox_count} bbox")
            if poly_count > 0:
                parts.append(f"{poly_count} polygon")
            self.info_label.setText(f"Toplam: {total} ({', '.join(parts)})")
            
    def _create_color_icon(self, color_hex: str) -> QIcon:
        """Renk ikonu oluştur."""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 16, 16, 3, 3)
        painter.end()
        
        return QIcon(pixmap)
                
    def _on_clear_clicked(self):
        """Tüm etiketleri temizle sinyali gönder."""
        if self._current_image:
            self.clear_all_requested.emit()
