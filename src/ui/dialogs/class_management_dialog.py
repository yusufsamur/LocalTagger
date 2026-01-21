"""
Class Management Dialog
=======================
Manages adding, deleting, editing and changing colors of label classes.
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
    Class management dialog.
    Manages adding, deleting, renaming and changing colors of classes.
    """
    
    # Signals
    classes_changed = Signal()  # When classes changed
    
    def __init__(self, class_manager: ClassManager, annotation_manager=None, parent=None):
        super().__init__(parent)
        self._class_manager = class_manager
        self._annotation_manager = annotation_manager
        
        self.setWindowTitle(self.tr("Class Management"))
        self.setMinimumSize(500, 400)
        
        self._setup_ui()
        self._connect_signals()
        self._refresh_table()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Title
        title = QLabel(self.tr("🏷️ Label Classes"))
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", self.tr("Class Name"), self.tr("Color"), self.tr("Labels"), self.tr("Images")])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton(self.tr("➕ Add New Class"))
        self.add_btn.setStyleSheet("padding: 8px 16px;")
        button_layout.addWidget(self.add_btn)
        
        self.rename_btn = QPushButton(self.tr("✏️ Rename"))
        self.rename_btn.setStyleSheet("padding: 8px 16px;")
        button_layout.addWidget(self.rename_btn)
        
        self.color_btn = QPushButton(self.tr("🎨 Change Color"))
        self.color_btn.setStyleSheet("padding: 8px 16px;")
        button_layout.addWidget(self.color_btn)
        
        self.delete_btn = QPushButton(self.tr("🗑️ Delete"))
        self.delete_btn.setStyleSheet("padding: 8px 16px; color: #ff4444;")
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
        
        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.close_btn = QPushButton(self.tr("Close"))
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
        """Refresh table."""
        self.table.setRowCount(0)
        
        # Calculate annotation and image count per class
        class_counts, class_images = self._count_annotations_per_class()
        
        for label_class in self._class_manager.classes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # ID
            id_item = QTableWidgetItem(str(label_class.id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setData(Qt.ItemDataRole.UserRole, label_class.id)
            self.table.setItem(row, 0, id_item)
            
            # Class name
            name_item = QTableWidgetItem(label_class.name)
            self.table.setItem(row, 1, name_item)
            
            # Color
            color_item = QTableWidgetItem()
            color_item.setIcon(self._create_color_icon(label_class.color, 24))
            color_item.setText(label_class.color)
            self.table.setItem(row, 2, color_item)
            
            # Annotation count
            count = class_counts.get(label_class.id, 0)
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if count == 0:
                count_item.setForeground(QColor("#888888"))
            self.table.setItem(row, 3, count_item)
            
            # Image count
            img_count = class_images.get(label_class.id, 0)
            img_item = QTableWidgetItem(str(img_count))
            img_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if img_count == 0:
                img_item.setForeground(QColor("#888888"))
            self.table.setItem(row, 4, img_item)
    
    def _count_annotations_per_class(self) -> tuple:
        """Calculate total annotation and image count per class.
        
        Returns:
            (counts, images) - counts: {class_id: count}, images: {class_id: image_count}
        """
        counts = {}  # class_id -> total annotation count
        images = {}  # class_id -> image count
        
        if self._annotation_manager:
            for image_path, annotations in self._annotation_manager._annotations.items():
                # Track classes in this image
                classes_in_image = set()
                
                for bbox in annotations.bboxes:
                    counts[bbox.class_id] = counts.get(bbox.class_id, 0) + 1
                    classes_in_image.add(bbox.class_id)
                for polygon in annotations.polygons:
                    counts[polygon.class_id] = counts.get(polygon.class_id, 0) + 1
                    classes_in_image.add(polygon.class_id)
                
                # Increase image count for each class
                for class_id in classes_in_image:
                    images[class_id] = images.get(class_id, 0) + 1
        
        return counts, images
            
    def _create_color_icon(self, color_hex: str, size: int = 16) -> QIcon:
        """Create color icon."""
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
        """Returns ID of selected class."""
        row = self.table.currentRow()
        if row < 0:
            return -1
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return -1
    
    def _add_class(self):
        """Add new class."""
        name, ok = QInputDialog.getText(
            self, self.tr("Add New Class"), self.tr("Class name:"),
            text=""
        )
        if ok and name.strip():
            new_class = self._class_manager.add_class(name.strip())
            self._refresh_table()
            self.classes_changed.emit()
            
            # Select new row
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == new_class.id:
                    self.table.selectRow(row)
                    break
    
    def _rename_class(self):
        """Rename selected class or merge with another."""
        class_id = self._get_selected_class_id()
        if class_id < 0:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a class."))
            return
            
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
            
        name, ok = QInputDialog.getText(
            self, self.tr("Rename Class"), self.tr("New name:"),
            text=label_class.name
        )
        if ok and name.strip():
            new_name = name.strip()
            
            # Check if class with same name exists
            existing_class = self._class_manager.get_by_name(new_name)
            
            if existing_class and existing_class.id != class_id:
                # Offer merge option
                result = QMessageBox.question(
                    self, self.tr("Merge Classes"),
                    self.tr("A class named '{}' already exists.\n\n"
                    "Would you like to move all labels from '{}' class "
                    "to '{}' class and merge them?\n\n"
                    "This action cannot be undone!").format(new_name, label_class.name, new_name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if result == QMessageBox.StandardButton.Yes:
                    self._merge_classes(class_id, existing_class.id)
            else:
                # Update name only
                self._class_manager.update_class(class_id, name=new_name)
                self._refresh_table()
                self.classes_changed.emit()
    
    def _merge_classes(self, source_id: int, target_id: int):
        """Merge two classes - move all labels from source to target.
        
        Args:
            source_id: Source class ID (to be deleted)
            target_id: Target class ID (to move labels to)
        """
        source_class = self._class_manager.get_by_id(source_id)
        target_class = self._class_manager.get_by_id(target_id)
        
        if not source_class or not target_class:
            return
        
        # Change source_id to target_id in all labels
        updated_count = 0
        updated_images = []
        
        if self._annotation_manager:
            for image_path, annotations in self._annotation_manager._annotations.items():
                image_updated = False
                
                for bbox in annotations.bboxes:
                    if bbox.class_id == source_id:
                        bbox.class_id = target_id
                        updated_count += 1
                        image_updated = True
                        
                for polygon in annotations.polygons:
                    if polygon.class_id == source_id:
                        polygon.class_id = target_id
                        updated_count += 1
                        image_updated = True
                
                # Mark image annotation as dirty and save
                if image_updated:
                    self._annotation_manager._mark_dirty(image_path)
                    updated_images.append(image_path)
            
            # Save labels of all updated images to disk
            from pathlib import Path
            for image_path in updated_images:
                image_p = Path(image_path)
                parent = image_p.parent
                
                # Determine labels directory
                if parent.name.lower() == "images":
                    labels_dir = parent.parent / "labels"
                else:
                    labels_dir = parent / "labels"
                
                labels_dir.mkdir(parents=True, exist_ok=True)
                self._annotation_manager.save_yolo(image_path, labels_dir)
        
        # Remove source class
        self._class_manager.remove_class(source_id)
        
        # Update classes.txt
        if updated_images:
            from pathlib import Path
            first_image = Path(updated_images[0])
            parent = first_image.parent
            if parent.name.lower() == "images":
                labels_dir = parent.parent / "labels"
            else:
                labels_dir = parent / "labels"
            self._class_manager.save_to_file(labels_dir / "classes.txt")
        
        # Refresh table
        self._refresh_table()
        self.classes_changed.emit()
        
        QMessageBox.information(
            self, self.tr("Merge Complete"),
            self.tr("Class '{}' was merged with '{}'.\n\n"
            "{} labels were updated and saved.").format(source_class.name, target_class.name, updated_count)
        )
    
    def _change_color(self):
        """Change color of selected class."""
        class_id = self._get_selected_class_id()
        if class_id < 0:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a class."))
            return
            
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
            
        color = QColorDialog.getColor(
            QColor(label_class.color), self, self.tr("Select Class Color")
        )
        if color.isValid():
            self._class_manager.update_class(class_id, color=color.name())
            self._refresh_table()
            self.classes_changed.emit()
    
    def _delete_class(self):
        """Delete selected class."""
        class_id = self._get_selected_class_id()
        if class_id < 0:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a class."))
            return
            
        label_class = self._class_manager.get_by_id(class_id)
        if not label_class:
            return
        
        # Warn if class has annotations
        annotation_count = 0
        affected_images = []
        if self._annotation_manager:
            for image_path, annotations in self._annotation_manager._annotations.items():
                has_affected = False
                for bbox in annotations.bboxes:
                    if bbox.class_id == class_id:
                        annotation_count += 1
                        has_affected = True
                for polygon in annotations.polygons:
                    if polygon.class_id == class_id:
                        annotation_count += 1
                        has_affected = True
                if has_affected:
                    affected_images.append(image_path)
        
        if annotation_count > 0:
            result = QMessageBox.warning(
                self, self.tr("Warning!"),
                self.tr("There are {} labels belonging to '{}' class.\n\n"
                "Deleting this class will also DELETE ALL these labels.\n\n"
                "Do you want to continue?").format(annotation_count, label_class.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        else:
            result = QMessageBox.question(
                self, self.tr("Delete Class"),
                self.tr("Are you sure you want to delete '{}' class?").format(label_class.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        
        # Delete all labels belonging to this class
        if self._annotation_manager and annotation_count > 0:
            from pathlib import Path
            
            for image_path in affected_images:
                annotations = self._annotation_manager._annotations.get(image_path)
                if not annotations:
                    continue
                
                # Delete bboxes of this class (reverse order to keep indices valid)
                for i in range(len(annotations.bboxes) - 1, -1, -1):
                    if annotations.bboxes[i].class_id == class_id:
                        annotations.bboxes.pop(i)
                
                # Delete polygons of this class
                for i in range(len(annotations.polygons) - 1, -1, -1):
                    if annotations.polygons[i].class_id == class_id:
                        annotations.polygons.pop(i)
                
                # Save changes to disk
                image_p = Path(image_path)
                parent = image_p.parent
                if parent.name.lower() == "images":
                    labels_dir = parent.parent / "labels"
                else:
                    labels_dir = parent / "labels"
                
                labels_dir.mkdir(parents=True, exist_ok=True)
                self._annotation_manager.save_yolo(image_path, labels_dir)
        
        # Remove class from memory
        self._class_manager.remove_class(class_id)
        
        # Update classes.txt
        labels_dir = None
        if affected_images:
            from pathlib import Path
            first_image = Path(affected_images[0])
            parent = first_image.parent
            if parent.name.lower() == "images":
                labels_dir = parent.parent / "labels"
            else:
                labels_dir = parent / "labels"
        elif self._annotation_manager and self._annotation_manager._annotations:
            # If deleting empty class, use any image path
            from pathlib import Path
            first_image = Path(list(self._annotation_manager._annotations.keys())[0])
            parent = first_image.parent
            if parent.name.lower() == "images":
                labels_dir = parent.parent / "labels"
            else:
                labels_dir = parent / "labels"
        
        if labels_dir:
            labels_dir.mkdir(parents=True, exist_ok=True)
            self._class_manager.save_to_file(labels_dir / "classes.txt")
        
        self._refresh_table()
        self.classes_changed.emit()
        
        if annotation_count > 0:
            QMessageBox.information(
                self, self.tr("Class Deleted"),
                self.tr("Class '{}' and {} labels were deleted.").format(label_class.name, annotation_count)
            )
    
    def _on_cell_double_clicked(self, row: int, column: int):
        """Table cell double clicked."""
        if column == 1:  # Class Name
            self._rename_class()
        elif column == 2:  # Color
            self._change_color()
