"""
Sınıf Yönetimi Dialogu
======================
Etiket sınıflarını ekleme, silme, düzenleme ve renk değiştirme işlemlerini yönetir.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QColorDialog, QInputDialog, QMessageBox,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QBrush

from core.class_manager import ClassManager, LabelClass


class ClassManagementDialog(QDialog):
    """
    Sınıf yönetimi dialogu.
    Sınıf ekleme, silme, yeniden adlandırma ve renk değiştirme işlemlerini yönetir.
    """
    
    # Sinyaller
    classes_changed = Signal()  # Sınıflar değiştiğinde
    
    def __init__(self, class_manager: ClassManager, annotation_manager=None, parent=None):
        super().__init__(parent)
        self._class_manager = class_manager
        self._annotation_manager = annotation_manager
        
        self.setWindowTitle("Sınıf Yönetimi")
        self.setMinimumSize(500, 400)
        
        self._setup_ui()
        self._connect_signals()
        self._refresh_table()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Başlık
        title = QLabel("🏷️ Etiket Sınıfları")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title)
        
        # Tablo
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Sınıf Adı", "Renk"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        # Butonlar
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Yeni Sınıf Ekle")
        self.add_btn.setStyleSheet("padding: 8px 16px;")
        button_layout.addWidget(self.add_btn)
        
        self.rename_btn = QPushButton("✏️ Yeniden Adlandır")
        self.rename_btn.setStyleSheet("padding: 8px 16px;")
        button_layout.addWidget(self.rename_btn)
        
        self.color_btn = QPushButton("🎨 Renk Değiştir")
        self.color_btn.setStyleSheet("padding: 8px 16px;")
        button_layout.addWidget(self.color_btn)
        
        self.delete_btn = QPushButton("🗑️ Sil")
        self.delete_btn.setStyleSheet("padding: 8px 16px; color: #ff4444;")
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
        
        # Kapat butonu
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.close_btn = QPushButton("Kapat")
        self.close_btn.setStyleSheet("padding: 8px 24px;")
        close_layout.addWidget(self.close_btn)
        layout.addLayout(close_layout)
        
    def _connect_signals(self):
        self.add_btn.clicked.connect(self._add_class)
        self.rename_btn.clicked.connect(self._rename_class)
        self.color_btn.clicked.connect(self._change_color)
        self.delete_btn.clicked.connect(self._delete_class)
        self.close_btn.clicked.connect(self.accept)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        
    def _refresh_table(self):
        """Tabloyu yenile."""
        self.table.setRowCount(0)
        
        for label_class in self._class_manager.classes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # ID
            id_item = QTableWidgetItem(str(label_class.id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setData(Qt.ItemDataRole.UserRole, label_class.id)
            self.table.setItem(row, 0, id_item)
            
            # Sınıf adı
            name_item = QTableWidgetItem(label_class.name)
            self.table.setItem(row, 1, name_item)
            
            # Renk
            color_item = QTableWidgetItem()
            color_item.setIcon(self._create_color_icon(label_class.color, 24))
            color_item.setText(label_class.color)
            self.table.setItem(row, 2, color_item)
            
    def _create_color_icon(self, color_hex: str, size: int = 16) -> QIcon:
        """Renk ikonu oluştur."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, size, size, 4, 4)
        painter.end()
        
        return QIcon(pixmap)
    
    def _get_selected_class_id(self) -> int:
        """Seçili sınıfın ID'sini döndür."""
        row = self.table.currentRow()
        if row < 0:
            return -1
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return -1
    
    def _add_class(self):
        """Yeni sınıf ekle."""
        name, ok = QInputDialog.getText(
            self, "Yeni Sınıf Ekle", "Sınıf adı:",
            text=""
        )
        if ok and name.strip():
            new_class = self._class_manager.add_class(name.strip())
            self._refresh_table()
            self.classes_changed.emit()
            
            # Yeni satırı seç
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == new_class.id:
                    self.table.selectRow(row)
                    break
    
    def _rename_class(self):
        """Seçili sınıfı yeniden adlandır."""
        class_id = self._get_selected_class_id()
        if class_id < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sınıf seçin.")
            return
            
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
            
        name, ok = QInputDialog.getText(
            self, "Sınıfı Yeniden Adlandır", "Yeni ad:",
            text=label_class.name
        )
        if ok and name.strip():
            self._class_manager.update_class(class_id, name=name.strip())
            self._refresh_table()
            self.classes_changed.emit()
    
    def _change_color(self):
        """Seçili sınıfın rengini değiştir."""
        class_id = self._get_selected_class_id()
        if class_id < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sınıf seçin.")
            return
            
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
            
        color = QColorDialog.getColor(
            QColor(label_class.color), self, "Sınıf Rengi Seç"
        )
        if color.isValid():
            self._class_manager.update_class(class_id, color=color.name())
            self._refresh_table()
            self.classes_changed.emit()
    
    def _delete_class(self):
        """Seçili sınıfı sil."""
        class_id = self._get_selected_class_id()
        if class_id < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir sınıf seçin.")
            return
            
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
        
        # Eğer bu sınıfa ait etiket varsa uyar
        annotation_count = 0
        if self._annotation_manager:
            for image_path, annotations in self._annotation_manager._annotations.items():
                for bbox in annotations.bboxes:
                    if bbox.class_id == class_id:
                        annotation_count += 1
                for polygon in annotations.polygons:
                    if polygon.class_id == class_id:
                        annotation_count += 1
        
        if annotation_count > 0:
            result = QMessageBox.warning(
                self, "Dikkat!",
                f"'{label_class.name}' sınıfına ait {annotation_count} etiket bulunmaktadır.\n\n"
                f"Bu sınıfı silmek, bu etiketlerin geçersiz hale gelmesine neden olacaktır.\n\n"
                f"Devam etmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        else:
            result = QMessageBox.question(
                self, "Sınıfı Sil",
                f"'{label_class.name}' sınıfını silmek istediğinize emin misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        
        self._class_manager.remove_class(class_id)
        self._refresh_table()
        self.classes_changed.emit()
    
    def _on_cell_double_clicked(self, row: int, column: int):
        """Hücreye çift tıklandığında."""
        if column == 1:  # Sınıf adı
            self._rename_class()
        elif column == 2:  # Renk
            self._change_color()
