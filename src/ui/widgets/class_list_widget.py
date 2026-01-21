"""
Class List Widget
=================
List widget for displaying and managing label classes.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMenu, QColorDialog, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush

from core.class_manager import ClassManager, LabelClass


class ClassListWidget(QWidget):
    """
    Class list widget.
    Manages adding, removing, changing color and selecting classes.
    """
    
    # Signals
    class_selected = Signal(int)  # class_id
    class_added = Signal(int)     # class_id
    class_removed = Signal(int)   # class_id
    class_updated = Signal(int)   # class_id
    
    def __init__(self, class_manager: ClassManager, parent=None):
        super().__init__(parent)
        self._class_manager = class_manager
        self._selected_class_id: int = -1
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Create UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Header and buttons
        header = QHBoxLayout()
        
        title = QLabel("🏷️ Sınıflar")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        
        header.addStretch()
        
        # Add button
        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(24, 24)
        self.add_btn.setToolTip("Yeni sınıf ekle")
        header.addWidget(self.add_btn)
        
        layout.addLayout(header)
        
        # Class list
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.list_widget)
        
        # Info label
        self.info_label = QLabel("Sınıf yok")
        self.info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.info_label)
        
    def _connect_signals(self):
        """Connect signals."""
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.list_widget.currentRowChanged.connect(self._on_selection_changed)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        
    def refresh(self):
        """Refresh list."""
        self.list_widget.clear()
        
        for cls in self._class_manager.classes:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cls.id)
            
            # Create color icon
            icon = self._create_color_icon(cls.color)
            item.setIcon(icon)
            item.setText(cls.name)
            
            self.list_widget.addItem(item)
            
        # Update info
        count = self._class_manager.count
        if count == 0:
            self.info_label.setText("Sınıf yok - '+' ile ekleyin")
        else:
            self.info_label.setText(f"{count} sınıf")
            
        # Keep previous selection
        if self._selected_class_id >= 0:
            self._select_class_by_id(self._selected_class_id)
    
    def _create_color_icon(self, color_hex: str, size: int = 16) -> QIcon:
        """Create color icon."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 3, 3)
        painter.end()
        
        return QIcon(pixmap)
    
    def _select_class_by_id(self, class_id: int):
        """Select class by ID."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == class_id:
                self.list_widget.setCurrentRow(i)
                return
                
    def get_selected_class(self) -> LabelClass | None:
        """Returns selected class."""
        if self._selected_class_id < 0:
            return None
        return self._class_manager.get_by_id(self._selected_class_id)
    
    # ─────────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────────
    
    def _on_add_clicked(self):
        """Add new class."""
        name, ok = QInputDialog.getText(
            self, 
            "Yeni Sınıf", 
            "Sınıf adı:",
            text=f"class_{self._class_manager.count}"
        )
        
        if ok and name.strip():
            # Color selection (optional - can be assigned automatically)
            label_class = self._class_manager.add_class(name.strip())
            self.refresh()
            self._select_class_by_id(label_class.id)
            self.class_added.emit(label_class.id)
            
    def _on_selection_changed(self, row: int):
        """Selection changed."""
        if row < 0:
            self._selected_class_id = -1
            return
            
        item = self.list_widget.item(row)
        if item:
            self._selected_class_id = item.data(Qt.ItemDataRole.UserRole)
            self.class_selected.emit(self._selected_class_id)
            
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Double click - change color."""
        class_id = item.data(Qt.ItemDataRole.UserRole)
        label_class = self._class_manager.get_by_id(class_id)
        
        if label_class:
            color = QColorDialog.getColor(
                QColor(label_class.color),
                self,
                "Sınıf Rengi Seç"
            )
            
            if color.isValid():
                self._class_manager.update_class(class_id, color=color.name())
                self.refresh()
                self.class_updated.emit(class_id)
    
    def _show_context_menu(self, pos):
        """Right click menu."""
        item = self.list_widget.itemAt(pos)
        if not item:
            return
            
        class_id = item.data(Qt.ItemDataRole.UserRole)
        
        menu = QMenu(self)
        
        rename_action = menu.addAction("Yeniden Adlandır")
        color_action = menu.addAction("Renk Değiştir")
        menu.addSeparator()
        delete_action = menu.addAction("Sil")
        
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        
        if action == rename_action:
            self._rename_class(class_id)
        elif action == color_action:
            self._change_color(class_id)
        elif action == delete_action:
            self._delete_class(class_id)
            
    def _rename_class(self, class_id: int):
        """Rename class."""
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
            
        name, ok = QInputDialog.getText(
            self, 
            "Sınıfı Yeniden Adlandır",
            "Yeni ad:",
            text=label_class.name
        )
        
        if ok and name.strip():
            self._class_manager.update_class(class_id, name=name.strip())
            self.refresh()
            self.class_updated.emit(class_id)
            
    def _change_color(self, class_id: int):
        """Change class color."""
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
            
        color = QColorDialog.getColor(
            QColor(label_class.color),
            self,
            "Sınıf Rengi Seç"
        )
        
        if color.isValid():
            self._class_manager.update_class(class_id, color=color.name())
            self.refresh()
            self.class_updated.emit(class_id)
            
    def _delete_class(self, class_id: int):
        """Delete class."""
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
            
        reply = QMessageBox.question(
            self,
            "Sınıfı Sil",
            f"'{label_class.name}' sınıfını silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._class_manager.remove_class(class_id)
            self.refresh()
            self.class_removed.emit(class_id)
