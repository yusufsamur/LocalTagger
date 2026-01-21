"""
Main Window Content
===================
Main widget containing the center canvas and side panels.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QFrame, QToolBar, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

from canvas import AnnotationView
from core.class_manager import ClassManager
from core.annotation_manager import AnnotationManager
from ui.widgets.annotation_list_widget import AnnotationListWidget


class MainWindow(QWidget):
    """
    Application main content area.
    Left panel (file list) + Center (canvas) + Right panel (classes + labels)
    """
    
    # Signals
    image_selected = Signal(str)
    tool_changed = Signal(str)
    sam_toggled = Signal(bool)  # AI toggle signal
    
    def __init__(self, class_manager: ClassManager, 
                 annotation_manager: AnnotationManager, parent=None):
        super().__init__(parent)
        self._class_manager = class_manager
        self._annotation_manager = annotation_manager
        self._current_image_path = ""
        # AI mode: None, "pixel", or "box"
        self._sam_mode = None
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Top Toolbar
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)
        
        # Main splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)
        
        # Left Panel - File List
        self.left_panel = self._create_left_panel()
        self.splitter.addWidget(self.left_panel)
        
        # Center - Canvas
        self.canvas_view = AnnotationView()
        self.splitter.addWidget(self.canvas_view)
        
        # Right Panel - Classes + Labels
        self.right_panel = self._create_right_panel()
        self.splitter.addWidget(self.right_panel)
        
        # Panel widths
        self.splitter.setSizes([200, 800, 220])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        
    def _create_toolbar(self) -> QToolBar:
        """Create toolbar."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar { 
                background: #2b2b2b; 
                border-bottom: 1px solid #3c3c3c;
                padding: 2px;
            }
            QToolButton {
                padding: 6px 12px;
                margin: 2px;
                border-radius: 4px;
            }
            QToolButton:checked {
                background: #0d6efd;
                color: white;
            }
            QToolButton:hover {
                background: #3c3c3c;
            }
        """)
        
        # Tool buttons
        self.select_btn = QPushButton(self.tr("🔲 Select (Q)"))
        self.select_btn.setCheckable(True)
        self.select_btn.clicked.connect(lambda: self._on_tool_clicked("select"))
        self.select_btn.setToolTip(self.tr("BBox selection and editing mode"))
        toolbar.addWidget(self.select_btn)
        
        self.bbox_btn = QPushButton(self.tr("⬜ BBox (W)"))
        self.bbox_btn.setCheckable(True)
        self.bbox_btn.setChecked(True)
        self.bbox_btn.clicked.connect(lambda: self._on_tool_clicked("bbox"))
        self.bbox_btn.setToolTip(self.tr("BBox drawing mode"))
        toolbar.addWidget(self.bbox_btn)
        
        self.polygon_btn = QPushButton(self.tr("◇ Polygon (E)"))
        self.polygon_btn.setCheckable(True)
        self.polygon_btn.clicked.connect(lambda: self._on_tool_clicked("polygon"))
        self.polygon_btn.setToolTip(self.tr("Polygon drawing mode"))
        toolbar.addWidget(self.polygon_btn)
        
        toolbar.addSeparator()
        
        # Info label
        self.toolbar_info = QLabel(self.tr("  Tool: BBox"))
        self.toolbar_info.setStyleSheet("color: #888;")
        toolbar.addWidget(self.toolbar_info)
        
        # Spacer for right alignment
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding, 
                             spacer.sizePolicy().verticalPolicy().Preferred)
        toolbar.addWidget(spacer)
        
        # Magic Pixel Button
        self.magic_pixel_btn = QPushButton(self.tr("✨ Magic Pixel"))
        self.magic_pixel_btn.setCheckable(True)
        self.magic_pixel_btn.setToolTip(self.tr("Click to label - Point-based (T)"))
        self.magic_pixel_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                margin: 2px;
                border-radius: 4px;
                background: #3c3c3c;
            }
            QPushButton:checked {
                background: #198754;
                color: white;
            }
            QPushButton:hover {
                background: #4a4a4a;
            }
            QPushButton:checked:hover {
                background: #157347;
            }
        """)
        self.magic_pixel_btn.clicked.connect(self._on_magic_pixel_clicked)
        toolbar.addWidget(self.magic_pixel_btn)
        
        # Magic Box Button
        self.magic_box_btn = QPushButton(self.tr("📦 Magic Box"))
        self.magic_box_btn.setCheckable(True)
        self.magic_box_btn.setToolTip(self.tr("Draw bbox, AI refines - Box-based (Y)"))
        self.magic_box_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                margin: 2px;
                border-radius: 4px;
                background: #3c3c3c;
            }
            QPushButton:checked {
                background: #6f42c1;
                color: white;
            }
            QPushButton:hover {
                background: #4a4a4a;
            }
            QPushButton:checked:hover {
                background: #5a3295;
            }
        """)
        self.magic_box_btn.clicked.connect(self._on_magic_box_clicked)
        toolbar.addWidget(self.magic_box_btn)
        
        # SAM Status Label
        self.sam_status = QLabel("")
        self.sam_status.setStyleSheet("color: #888; margin-left: 8px;")
        toolbar.addWidget(self.sam_status)
        
        return toolbar
    
    def _on_tool_clicked(self, tool: str):
        """When tool button is clicked."""
        # Uncheck all buttons
        self.select_btn.setChecked(tool == "select")
        self.bbox_btn.setChecked(tool == "bbox")
        self.polygon_btn.setChecked(tool == "polygon")
        
        self.canvas_view.set_tool(tool)
        self.tool_changed.emit(tool)
        
        tool_names = {"select": self.tr("Select"), "bbox": "BBox", "polygon": "Polygon"}
        self.toolbar_info.setText(self.tr("  Tool: {}").format(tool_names.get(tool, tool)))
        
    def _create_left_panel(self) -> QFrame:
        """Create left panel (file list)."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(150)
        panel.setMaximumWidth(300)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.files_title = QLabel(self.tr("📁 Files (0)"))
        self.files_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.files_title)
        
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setStyleSheet("font-size: 11px;")  # Küçük font
        layout.addWidget(self.file_list)
        
        # Labeled/Unlabeled count
        self.labeled_count_label = QLabel(self.tr("✅ 0 labeled  ⭕ 0 unlabeled"))
        self.labeled_count_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.labeled_count_label)
        
        self.file_info_label = QLabel(self.tr("No folder opened"))
        self.file_info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.file_info_label)
        
        return panel
    
    def _create_right_panel(self) -> QFrame:
        """Create right panel (annotation summary)."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel) 
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(320)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Annotation summary widget
        self.annotation_list_widget = AnnotationListWidget(
            self._annotation_manager, 
            self._class_manager
        )
        layout.addWidget(self.annotation_list_widget, stretch=1)
        
        return panel
    
    def _connect_signals(self):
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        self.annotation_list_widget.annotation_deleted.connect(self._on_annotation_deleted)
        
    def _on_file_selected(self, row: int):
        """When an item is selected from file list."""
        item = self.file_list.item(row)
        if item:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                # Save annotations of previous image
                self._save_current_annotations()
                
                self._current_image_path = file_path
                self.image_selected.emit(file_path)
                self.canvas_view.cancel_drawing()
                
                if self.canvas_view.scene.load_image(file_path):
                    self.canvas_view.zoom_fit()
                    
                    # Notify annotation manager about image size
                    w, h = self.canvas_view.scene.image_size
                    self._annotation_manager.set_image_size(file_path, w, h)
                    
                    # If YOLO txt exists, load it (from labels folder)
                    self._load_annotations_from_labels(file_path, w, h)
                    
                    # Draw saved annotations
                    annotations = self._annotation_manager.get_annotations(file_path)
                    self.canvas_view.draw_annotations(
                        annotations.bboxes, 
                        annotations.polygons, 
                        self._class_manager
                    )
                    
                    # Update annotation list
                    self.annotation_list_widget.set_current_image(file_path)
                    
                    # Set default class color
                    if self._class_manager.count > 0:
                        first_class = self._class_manager.classes[0]
                        self.canvas_view.set_draw_color(first_class.color)
    
    def _get_labels_dir(self) -> 'Path':
        """Return labels directory."""
        from pathlib import Path
        if not self._current_image_path:
            return None
        image_path = Path(self._current_image_path)
        parent = image_path.parent
        
        # If images folder exists, create labels next to it
        if parent.name.lower() == "images":
            return parent.parent / "labels"
        else:
            return parent / "labels"
    
    def _save_current_annotations(self):
        """Save annotations of current image to labels folder."""
        if not self._current_image_path:
            return
        
        labels_dir = self._get_labels_dir()
        if labels_dir:
            labels_dir.mkdir(parents=True, exist_ok=True)
            self._annotation_manager.save_yolo(self._current_image_path, labels_dir)
            
            # Save classes.txt too (to prevent losing new classes)
            self._class_manager.save_to_file(labels_dir / "classes.txt")
            
            # Update labeled/unlabeled count
            self.refresh_labeled_count()
    
    def _load_annotations_from_labels(self, image_path: str, w: int, h: int):
        """Load annotations from labels folder."""
        from pathlib import Path
        image_p = Path(image_path)
        parent = image_p.parent
        
        # Try labels folder first
        if parent.name.lower() == "images":
            labels_dir = parent.parent / "labels"
        else:
            labels_dir = parent / "labels"
        
        txt_path = labels_dir / f"{image_p.stem}.txt"
        if txt_path.exists():
            # Custom load: from labels folder
            self._annotation_manager._load_from_path(image_path, txt_path, w, h)
            # Create missing classes automatically
            self._ensure_classes_exist(image_path)
        else:
            # Fallback: load from same folder
            self._annotation_manager.load_yolo(image_path, w, h)
            # Create missing classes automatically
            self._ensure_classes_exist(image_path)
    
    def _ensure_classes_exist(self, image_path: str):
        """Automatically create missing classes in loaded annotations."""
        annotations = self._annotation_manager.get_annotations(image_path)
        
        # Collect all class_ids
        class_ids = set()
        for bbox in annotations.bboxes:
            class_ids.add(bbox.class_id)
        for polygon in annotations.polygons:
            class_ids.add(polygon.class_id)
        
        # Create missing classes
        for class_id in class_ids:
            if self._class_manager.get_by_id(class_id) is None:
                # Create placeholder class
                self._class_manager.add_class_with_id(class_id, f"none_{class_id}")
    
    def set_draw_color(self, class_id: int):
        """Set class color."""
        label_class = self._class_manager.get_by_id(class_id)
        if label_class:
            self.canvas_view.set_draw_color(label_class.color)
            
    def _on_annotation_deleted(self, ann_type: str, index: int):
        """When annotation is deleted."""
        if ann_type == "bbox":
            self._annotation_manager.remove_bbox(self._current_image_path, index)
        else:
            self._annotation_manager.remove_polygon(self._current_image_path, index)
        
        # Refresh canvas
        self.refresh_canvas()
        self.annotation_list_widget.refresh()
        
    def refresh_canvas(self):
        """Redraw canvas (with all annotations)."""
        if not self._current_image_path:
            return
        
        # Redraw saved annotations
        annotations = self._annotation_manager.get_annotations(self._current_image_path)
        self.canvas_view.draw_annotations(
            annotations.bboxes, 
            annotations.polygons, 
            self._class_manager
        )
    
    def populate_file_list(self, file_paths: list):
        """Populate file list."""
        self.file_list.clear()
        
        for path in file_paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)
        
        # Update title
        self.files_title.setText(self.tr("📁 Files ({})").format(len(file_paths)))
        self.file_info_label.setText(self.tr("{} images").format(len(file_paths)))
        
        # Update labeled/unlabeled count
        self._update_labeled_count(file_paths)
        
    def get_current_image_path(self) -> str:
        return self._current_image_path
    
    def set_tool(self, tool: str):
        """Change tool."""
        self._on_tool_clicked(tool)
    
    # ─────────────────────────────────────────────────────────────────
    # SAM / AI Methods
    # ─────────────────────────────────────────────────────────────────
    
    def _on_magic_pixel_clicked(self):
        """When Magic Pixel button is clicked."""
        if self.magic_pixel_btn.isChecked():
            # Magic Pixel active - Close Magic Box
            self.magic_box_btn.setChecked(False)
            self._sam_mode = "pixel"
        else:
            # Clicked again - close
            self._sam_mode = None
        
        self._update_sam_state()
    
    def _on_magic_box_clicked(self):
        """When Magic Box button is clicked."""
        if self.magic_box_btn.isChecked():
            # Magic Box active - Close Magic Pixel
            self.magic_pixel_btn.setChecked(False)
            self._sam_mode = "box"
        else:
            # Clicked again - close
            self._sam_mode = None
        
        self._update_sam_state()
    
    def _update_sam_state(self):
        """Notify canvas and signal about SAM state."""
        self.canvas_view.set_sam_mode(self._sam_mode)
        self.sam_toggled.emit(self._sam_mode is not None)
    
    def set_sam_mode(self, mode: str):
        """Set SAM mode (externally) - 'pixel', 'box', or None."""
        self._sam_mode = mode
        self.magic_pixel_btn.setChecked(mode == "pixel")
        self.magic_box_btn.setChecked(mode == "box")
        self.canvas_view.set_sam_mode(mode)
    
    def set_sam_status(self, status: str):
        """Set SAM status message."""
        self.sam_status.setText(status)
    
    def set_sam_ready(self, ready: bool):
        """Set SAM ready status."""
        self.magic_pixel_btn.setEnabled(ready)
        self.magic_box_btn.setEnabled(ready)
        if not ready:
            self.sam_status.setText(self.tr("Model loading..."))
        else:
            self.sam_status.setText("")
    
    @property
    def sam_enabled(self) -> bool:
        """Is SAM enabled? (True if any mode is active)"""
        return self._sam_mode is not None
    
    @property
    def sam_mode(self) -> str:
        """Active SAM mode - 'pixel', 'box', or None."""
        return self._sam_mode
    
    def _update_labeled_count(self, file_paths: list):
        """Update labeled and unlabeled file count."""
        from pathlib import Path
        
        if not file_paths:
            self.labeled_count_label.setText(self.tr("✅ 0 labeled  ⭕ 0 unlabeled"))
            return
        
        labeled = 0
        unlabeled = 0
        
        # Find labels folder
        first_path = Path(file_paths[0])
        parent = first_path.parent
        
        if parent.name.lower() == "images":
            labels_dir = parent.parent / "labels"
        else:
            labels_dir = parent / "labels"
        
        for path in file_paths:
            p = Path(path)
            txt_file = labels_dir / f"{p.stem}.txt"
            if txt_file.exists() and txt_file.stat().st_size > 0:
                labeled += 1
            else:
                unlabeled += 1
        
        self.labeled_count_label.setText(self.tr("✅ {} labeled  ⭕ {} unlabeled").format(labeled, unlabeled))
    
    def refresh_labeled_count(self):
        """Refresh labeled/unlabeled count - from current file list."""
        from pathlib import Path
        file_paths = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path_str = item.data(Qt.ItemDataRole.UserRole)
            if path_str:
                file_paths.append(Path(path_str))
        
        if file_paths:
            self._update_labeled_count(file_paths)

