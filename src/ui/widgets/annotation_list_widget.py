"""
Annotation Summary Widget
=========================
Displays class-based summary of annotations in the current image.
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
    Displays class-based summary of annotations in the current image.
    Format: class_name: count (e.g. car: 3, person: 0)
    """
    
    # Signals
    annotation_selected = Signal(str, int)  # (type: "bbox" | "polygon", index)
    annotation_deleted = Signal(str, int)   # (type, index)
    clear_all_requested = Signal()          # Request to delete all
    
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
        
        # Title
        header = QHBoxLayout()
        title = QLabel(self.tr("📊 Annotation Summary"))
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()
        
        # Clear button
        self.clear_btn = QPushButton("🗑")
        self.clear_btn.setFixedSize(24, 24)
        self.clear_btn.setToolTip(self.tr("Delete all annotations"))
        header.addWidget(self.clear_btn)
        
        layout.addLayout(header)
        
        # Class based summary list
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
        
        # Info
        self.info_label = QLabel(self.tr("No image selected"))
        self.info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.info_label)
        
    def _connect_signals(self):
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        
    def set_current_image(self, image_path: str):
        """Set displayed image."""
        self._current_image = image_path
        self.refresh()
        
    def refresh(self):
        """Refresh list - show class based summary."""
        self.list_widget.clear()
        
        if not self._current_image:
            self.info_label.setText(self.tr("No image selected"))
            return
            
        annotations = self._annotation_manager.get_annotations(self._current_image)
        
        # Count by class
        class_counts = defaultdict(int)
        
        for bbox in annotations.bboxes:
            class_counts[bbox.class_id] += 1
            
        for polygon in annotations.polygons:
            class_counts[polygon.class_id] += 1
        
        # List all classes (show 0 even if no label)
        for label_class in self._class_manager.classes:
            count = class_counts.get(label_class.id, 0)
            
            item = QListWidgetItem()
            item.setIcon(self._create_color_icon(label_class.color))
            item.setText(f"{label_class.name}: {count}")
            
            # Bold font if has annotations
            if count > 0:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setForeground(QColor("#888888"))
                
            self.list_widget.addItem(item)
        
        # Update info
        total = len(annotations.bboxes) + len(annotations.polygons)
        if total == 0:
            self.info_label.setText(self.tr("No annotations - Start drawing"))
        else:
            bbox_count = len(annotations.bboxes)
            poly_count = len(annotations.polygons)
            parts = []
            if bbox_count > 0:
                parts.append(f"{bbox_count} bbox")
            if poly_count > 0:
                parts.append(f"{poly_count} polygon")
            self.info_label.setText(self.tr("Total: {} ({})").format(total, ', '.join(parts)))
            
    def _create_color_icon(self, color_hex: str) -> QIcon:
        """Create color icon."""
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
        """Send clear all signal."""
        if self._current_image:
            self.clear_all_requested.emit()
