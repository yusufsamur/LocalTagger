"""
LocalTagger - Main Application Class
===================================
Main window and application coordination.
"""

from pathlib import Path
from utils.path_utils import get_resource_path
from PySide6.QtWidgets import QMainWindow, QStatusBar, QFileDialog, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QIcon

from ui.main_window import MainWindow
from ui.dialogs.class_management_dialog import ClassManagementDialog
from ui.dialogs.export_dialog_v2 import ExportWizard
from ui.widgets.class_selector_popup import ClassSelectorPopup
from core.project import Project
from core.class_manager import ClassManager
from core.annotation_manager import AnnotationManager
from core.annotation import BoundingBox, Polygon
from core.sam_worker import SAMWorker


class LocalTaggerApp(QMainWindow):
    """LocalTagger main application window."""
    
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff", ".tif"}
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("LocalTagger - Data Annotation Tool"))
        self.setWindowIcon(QIcon(str(get_resource_path("resources/icon/LocalTagger.ico"))))
        self.setMinimumSize(1200, 800)
        
        # Language manager (set from main.py)
        self._language_manager = None
        
        # Managers
        self.project = Project()
        self.class_manager = ClassManager()
        self.annotation_manager = AnnotationManager()
        
        # Last used class ID
        self._last_used_class_id = 0
        
        # Pending bbox (for popup class selection)
        self._pending_bbox = None  # (x1, y1, x2, y2)
        
        # Track selected annotation (for copy/paste)
        self._selected_annotation = None  # (type: "bbox"|"polygon", index)
        
        # Track active popup (only 1 popup at a time)
        self._active_popup = None
        
        # Default classes
        self._add_default_classes()
        
        # UI Setup
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
        self._setup_shortcuts()
        self._connect_signals()
        
        self.setAcceptDrops(True)
        
        # SAM Worker (AI-assisted labeling)
        self._setup_sam_worker()
        
    def _add_default_classes(self):
        """Add default label classes."""
        if self.class_manager.count == 0:
            self.class_manager.add_class("object")
        
    def _setup_ui(self):
        self.main_window = MainWindow(self.class_manager, self.annotation_manager, self)
        self.setCentralWidget(self.main_window)
        
    def _setup_menubar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu(self.tr("&File"))
        file_menu.addAction(self.tr("Open Folder..."), self._open_folder, QKeySequence("Ctrl+O"))
        file_menu.addAction(self.tr("Open File..."), self._open_file, QKeySequence("Ctrl+Shift+O"))
        file_menu.addSeparator()
        file_menu.addAction(self.tr("Save"), self._save_annotations, QKeySequence("Ctrl+S"))
        file_menu.addAction(self.tr("Save All"), self._save_all_annotations, QKeySequence("Ctrl+Shift+S"))
        file_menu.addSeparator()
        file_menu.addAction(self.tr("Export..."), self._export_labels, QKeySequence("Ctrl+E"))
        file_menu.addSeparator()
        file_menu.addAction(self.tr("Exit"), self.close, QKeySequence("Ctrl+Q"))
        
        # Edit menu
        edit_menu = menubar.addMenu(self.tr("&Edit"))
        edit_menu.addAction(self.tr("🏷️ Class Management..."), self._open_class_management)
        edit_menu.addSeparator()
        edit_menu.addAction(self.tr("Delete Selected Annotation"), self._delete_selected_annotation, QKeySequence("Delete"))
        edit_menu.addAction(self.tr("Clear All Annotations"), self._clear_all_annotations)
        
        # View menu
        view_menu = menubar.addMenu(self.tr("&View"))
        view_menu.addAction(self.tr("Zoom In"), self._zoom_in, QKeySequence("Ctrl+="))
        view_menu.addAction(self.tr("Zoom Out"), self._zoom_out, QKeySequence("Ctrl+-"))
        view_menu.addAction(self.tr("Fit to Window"), self._zoom_fit, QKeySequence("Ctrl+0"))
        view_menu.addAction(self.tr("Actual Size"), self._zoom_reset, QKeySequence("Ctrl+1"))
        
        # Language menu (top level)
        self._language_menu = menubar.addMenu(self.tr("&Language"))
        self._setup_language_menu()
        
        # Help menu
        help_menu = menubar.addMenu(self.tr("&Help"))
        help_menu.addAction(self.tr("About"), self._show_about)
        
    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(self.tr("Ready - Press Ctrl+O to open a folder"))
        
    def _setup_shortcuts(self):
        # Navigation
        QShortcut(QKeySequence("D"), self, self._next_image)
        QShortcut(QKeySequence("A"), self, self._prev_image)
        QShortcut(QKeySequence("Right"), self, self._next_image)
        QShortcut(QKeySequence("Left"), self, self._prev_image)
        
        # Tools
        QShortcut(QKeySequence("Q"), self, lambda: self.main_window.set_tool("select"))
        QShortcut(QKeySequence("W"), self, lambda: self.main_window.set_tool("bbox"))
        QShortcut(QKeySequence("E"), self, lambda: self.main_window.set_tool("polygon"))
        QShortcut(QKeySequence("T"), self, self._toggle_magic_pixel)  # Magic Pixel toggle
        QShortcut(QKeySequence("Y"), self, self._toggle_magic_box)  # Magic Box toggle
        
        # Undo/Redo
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        
        # Copy/Paste
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy_annotations)
        QShortcut(QKeySequence("Ctrl+V"), self, self._paste_annotations)
        
        # Bulk delete
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), self, self._delete_all_annotations)
    
    def set_language_manager(self, manager):
        """Set language manager from main.py."""
        self._language_manager = manager
        self._update_language_menu()
    
    def _setup_language_menu(self):
        """Setup language selection submenu."""
        if not hasattr(self, '_language_menu'):
            return
        self._language_menu.clear()
        
        # Add language options
        from PySide6.QtGui import QActionGroup
        self._lang_action_group = QActionGroup(self)
        self._lang_action_group.setExclusive(True)
        
        languages = [("en", "English"), ("tr", "Türkçe")]
        
        for code, name in languages:
            action = self._language_menu.addAction(name)
            action.setCheckable(True)
            action.setData(code)
            self._lang_action_group.addAction(action)
            action.triggered.connect(lambda checked, c=code: self._on_language_selected(c))
    
    def _update_language_menu(self):
        """Update language menu checkmarks based on current language."""
        if not self._language_manager or not hasattr(self, '_lang_action_group'):
            return
        
        current = self._language_manager.current_language
        for action in self._lang_action_group.actions():
            action.setChecked(action.data() == current)
    
    def _on_language_selected(self, lang_code: str):
        """Handle language selection from menu."""
        if not self._language_manager:
            return
        
        current = self._language_manager.current_language
        if lang_code == current:
            return
        
        # Change language
        self._language_manager.set_language(lang_code)
        
        # Show restart message
        QMessageBox.information(
            self,
            self.tr("Language Changed"),
            self.tr("The language will be fully applied after restarting the application.")
        )

        
    def _connect_signals(self):
        canvas = self.main_window.canvas_view
        canvas.zoom_changed.connect(self._on_zoom_changed)
        canvas.mouse_position.connect(self._on_mouse_position)
        canvas.files_dropped.connect(self._on_files_dropped)
        canvas.bbox_created.connect(self._on_bbox_created)
        canvas.polygon_created.connect(self._on_polygon_created)
        
        # BBox editing signals
        canvas.bbox_moved.connect(self._on_bbox_moved)
        canvas.bbox_delete_requested.connect(self._on_bbox_delete)
        canvas.bbox_class_change_requested.connect(self._on_bbox_class_change)
        
        # Polygon editing signals
        canvas.polygon_moved.connect(self._on_polygon_moved)
        canvas.polygon_delete_requested.connect(self._on_polygon_delete)
        canvas.polygon_class_change_requested.connect(self._on_polygon_class_change)
        
        # Annotation click - auto switch to select mode
        canvas.annotation_clicked.connect(self._on_annotation_clicked)
        
        # Close popup when image changes
        self.main_window.image_selected.connect(self._on_image_changed)
        
        self.main_window.tool_changed.connect(self._on_tool_changed)
        
        # SAM signals
        canvas.sam_click_requested.connect(self._on_sam_click)
        canvas.sam_box_requested.connect(self._on_sam_box)
        self.main_window.sam_toggled.connect(self._on_sam_toggled)
        
        # Annotation list widget signals
        self.main_window.annotation_list_widget.clear_all_requested.connect(self._delete_all_annotations)
    
    def _on_image_changed(self, image_path: str):
        """When image changes - close open popups and start SAM encoding."""
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        # If SAM enabled, start encoding for new image
        if self.main_window.sam_enabled:
            self._encode_current_image()
    
    def _on_annotation_clicked(self):
        """When an annotation is clicked - switch to select mode."""
        self.main_window.set_tool("select")
    
    def _on_popup_closed(self):
        """When popup closed - focus canvas and return to drawing mode."""
        self._active_popup = None
        
        # Store index of item being edited
        editing_index = getattr(self, '_pending_class_change_index', None)
        editing_type = getattr(self, '_last_edit_type', 'bbox')
        
        # Refresh canvas - clear editing marks
        self.main_window.refresh_canvas()
        
        # If an item was being edited, select it again
        if editing_index is not None:
            canvas = self.main_window.canvas_view
            if canvas._annotation_items and 0 <= editing_index < len(canvas._annotation_items):
                item = canvas._annotation_items[editing_index]
                item.setSelected(True)
        
        # Focus canvas (for delete keys)
        self.main_window.canvas_view.setFocus()
        
        # Change tool mode based on last edited type
        self.main_window.set_tool(editing_type)
    
    def _on_popup_navigate(self, direction: str):
        """When navigation requested from popup."""
        self._active_popup = None
        if direction == 'next':
            self._next_image()
        elif direction == 'prev':
            self._prev_image()
        
    # ─────────────────────────────────────────────────────────────────
    # Annotation Event Handlers
    # ─────────────────────────────────────────────────────────────────
    
    def _on_bbox_created(self, x1: float, y1: float, x2: float, y2: float):
        """When BBox created - add immediately, then show popup."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Normalize pixel coordinates
        w, h = self.main_window.canvas_view.scene.image_size
        if w == 0 or h == 0:
            return
        
        # Add immediately with default or last used class
        class_id = self._last_used_class_id
        if self.class_manager.get_by_id(class_id) is None and self.class_manager.count > 0:
            class_id = self.class_manager.classes[0].id
            
        bbox = BoundingBox(
            class_id=class_id,
            x_center=(x1 + x2) / 2 / w,
            y_center=(y1 + y2) / 2 / h,
            width=(x2 - x1) / w,
            height=(y2 - y1) / h
        )
        
        self.annotation_manager.add_bbox(image_path, bbox)
        
        # Save immediately
        self.main_window._save_current_annotations()
        
        # Refresh canvas - bbox appears as EditableRectItem
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        # Select the newly added bbox (show dashed line)
        canvas = self.main_window.canvas_view
        if canvas._annotation_items:
            last_item = canvas._annotation_items[-1]
            last_item.setSelected(True)
        
        # Store index of newly added bbox (for class change)
        annotations = self.annotation_manager.get_annotations(image_path)
        self._pending_bbox_index = len(annotations.bboxes) - 1
        
        # Show popup at top-right corner of bbox (with slight offset)
        scene_pos = canvas.mapFromScene(x2 + 15, y1)  # 15px right offset
        global_pos = canvas.mapToGlobal(scene_pos)
        
        # If a popup is already open, do not open a new one
        if self._active_popup is not None:
            return
        
        self._class_popup = ClassSelectorPopup(
            self.class_manager, 
            self._last_used_class_id, 
            self
        )
        self._class_popup.class_selected.connect(self._on_new_bbox_class_selected)
        self._class_popup.cancelled.connect(self._on_new_bbox_cancelled)
        self._class_popup.closed.connect(self._on_popup_closed)
        self._class_popup.navigate_requested.connect(self._on_popup_navigate)
        self._class_popup.show_at(global_pos)
        
        # Register as active popup and set last edit type
        self._last_edit_type = "bbox"
        self._active_popup = self._class_popup
        
        # Switch to select mode - bbox can be edited
        self.main_window.set_tool("select")
    
    def _on_new_bbox_class_selected(self, class_id: int):
        """When class selected from popup for new bbox."""
        if not hasattr(self, '_pending_bbox_index'):
            return
        
        index = self._pending_bbox_index
        del self._pending_bbox_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.bboxes):
            # Update class
            annotations.bboxes[index].class_id = class_id
            self._last_used_class_id = class_id
            self.annotation_manager._mark_dirty(image_path)
            
            # Save immediately
            self.main_window._save_current_annotations()
            
            # Refresh canvas
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            # Update color
            label_class = self.class_manager.get_by_id(class_id)
            if label_class:
                self.main_window.canvas_view.set_draw_color(label_class.color)
            
            self.statusbar.showMessage(self.tr("✓ BBox added: {}").format(label_class.name if label_class else 'object'))
            
            # Switch back to drawing mode
            self.main_window.set_tool("bbox")
    
    def _on_new_bbox_cancelled(self):
        """When new bbox class selection cancelled - remove bbox."""
        if not hasattr(self, '_pending_bbox_index'):
            return
        
        index = self._pending_bbox_index
        del self._pending_bbox_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Delete bbox
        self.annotation_manager.remove_bbox(image_path, index)
        
        # Save and refresh
        self.main_window._save_current_annotations()
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        self.statusbar.showMessage(self.tr("BBox cancelled"))
    
    def _on_bbox_cancelled(self):
        """When bbox class selection cancelled."""
        if self._pending_bbox:
            # Remove bbox from canvas (last drawn item)
            if self.main_window.canvas_view._annotation_items:
                last_item = self.main_window.canvas_view._annotation_items.pop()
                try:
                    if last_item.scene():
                        self.main_window.canvas_view.scene.removeItem(last_item)
                except RuntimeError:
                    pass
        self._pending_bbox = None
        self.statusbar.showMessage(self.tr("BBox cancelled"))
        
    def _on_polygon_created(self, points: list):
        """When polygon created - show popup."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Store pixel points
        self._pending_polygon = points
        
        # Show popup next to last point
        if points:
            last_x, last_y = points[-1]
            canvas = self.main_window.canvas_view
            from PySide6.QtCore import QPointF
            scene_pos = canvas.mapFromScene(QPointF(last_x, last_y))
            global_pos = canvas.mapToGlobal(scene_pos)
            
            popup = ClassSelectorPopup(
                self.class_manager, 
                self._last_used_class_id, 
                self
            )
            popup.class_selected.connect(self._on_polygon_class_selected)
            popup.cancelled.connect(self._on_polygon_cancelled)
            popup.navigate_requested.connect(self._on_popup_navigate)
            popup.show_at(global_pos)
            
            # Save as active popup
            self._active_popup = popup
    
    def _on_polygon_class_selected(self, class_id: int):
        """When polygon class selected from popup."""
        if not self._pending_polygon:
            return
        
        points = self._pending_polygon
        self._pending_polygon = None
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Update class
        self._last_used_class_id = class_id
        
        # Normalize
        w, h = self.main_window.canvas_view.scene.image_size
        if w == 0 or h == 0:
            return
            
        normalized_points = [(x / w, y / h) for x, y in points]
        
        polygon = Polygon(class_id=class_id, points=normalized_points)
        self.annotation_manager.add_polygon(image_path, polygon)
        
        # Refresh Canvas - polygon appears as EditablePolygonItem
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        label_class = self.class_manager.get_by_id(class_id)
        self.statusbar.showMessage(self.tr("✓ Polygon added: {}").format(label_class.name if label_class else 'object'))
    
    def _on_polygon_cancelled(self):
        """When polygon class selection cancelled."""
        if self._pending_polygon:
            # Remove polygon from canvas (last drawn item)
            if self.main_window.canvas_view._annotation_items:
                last_item = self.main_window.canvas_view._annotation_items.pop()
                try:
                    if last_item.scene():
                        self.main_window.canvas_view.scene.removeItem(last_item)
                except RuntimeError:
                    pass
        self._pending_polygon = None
        self.statusbar.showMessage(self.tr("Polygon cancelled"))
    
    def _on_ai_polygon_class_selected(self, class_id: int):
        """When class selected from popup for AI polygon."""
        if not hasattr(self, '_pending_polygon_index'):
            return
        
        index = self._pending_polygon_index
        del self._pending_polygon_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.polygons):
            # Update class
            annotations.polygons[index].class_id = class_id
            self._last_used_class_id = class_id
            self.annotation_manager._mark_dirty(image_path)
            
            # Save immediately
            self.main_window._save_current_annotations()
            
            # Refresh canvas
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            # Update color
            label_class = self.class_manager.get_by_id(class_id)
            if label_class:
                self.main_window.canvas_view.set_draw_color(label_class.color)
            
            self.statusbar.showMessage(self.tr("✓ AI Polygon class: {}").format(label_class.name if label_class else 'object'))
            
            # Switch back to polygon mode
            self.main_window.set_tool("polygon")
    
    def _on_ai_polygon_cancelled(self):
        """When AI polygon class selection cancelled - remove polygon."""
        if not hasattr(self, '_pending_polygon_index'):
            return
        
        index = self._pending_polygon_index
        del self._pending_polygon_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Delete Polygon
        self.annotation_manager.remove_polygon(image_path, index)
        
        # Save and refresh
        self.main_window._save_current_annotations()
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        self._pending_polygon = None
        self.statusbar.showMessage(self.tr("AI Polygon cancelled"))
        
    def _on_class_selected(self, class_id: int):
        """When class selected."""
        self._last_used_class_id = class_id
        label_class = self.class_manager.get_by_id(class_id)
        if label_class:
            self.main_window.set_draw_color(class_id)
            self.statusbar.showMessage(self.tr("Class: {}").format(label_class.name))
    
    def _on_bbox_moved(self, index: int, new_rect):
        """When BBox moved or resized."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.bboxes):
            w, h = self.main_window.canvas_view.scene.image_size
            if w == 0 or h == 0:
                return
            
            # Calculate new coordinates
            bbox = annotations.bboxes[index]
            bbox.x_center = (new_rect.left() + new_rect.width() / 2) / w
            bbox.y_center = (new_rect.top() + new_rect.height() / 2) / h
            bbox.width = new_rect.width() / w
            bbox.height = new_rect.height() / h
            
            self.annotation_manager._mark_dirty(image_path)
            
            # Save to labels folder immediately
            self.main_window._save_current_annotations()
            
            self.statusbar.showMessage(self.tr("✓ BBox updated and saved"))
    
    def _on_bbox_delete(self, index: int):
        """When BBox deleted."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Close popup if open
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        if self.annotation_manager.remove_bbox(image_path, index):
            # Save
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage(self.tr("✓ BBox deleted"))
    
    def _on_bbox_class_change(self, index: int, pos):
        """Request BBox class change."""
        from PySide6.QtCore import QPoint
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # If a popup already open, do not open new one
        if self._active_popup is not None:
            return
        
        # Store current bbox
        self._pending_class_change_index = index
        
        # Show popup
        canvas = self.main_window.canvas_view
        view_pos = canvas.mapFromScene(pos)
        global_pos = canvas.mapToGlobal(view_pos)
        
        popup = ClassSelectorPopup(
            self.class_manager, 
            self._last_used_class_id, 
            self
        )
        popup.class_selected.connect(self._on_bbox_class_changed)
        popup.closed.connect(self._on_popup_closed)
        popup.navigate_requested.connect(self._on_popup_navigate)
        popup.show_at(global_pos)
        
        # Save as active popup and set last edit type
        self._last_edit_type = "bbox"
        self._active_popup = popup
    
    def _on_bbox_class_changed(self, new_class_id: int):
        """When BBox class changed."""
        if not hasattr(self, '_pending_class_change_index'):
            return
        
        index = self._pending_class_change_index
        del self._pending_class_change_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.bboxes):
            annotations.bboxes[index].class_id = new_class_id
            self._last_used_class_id = new_class_id
            self.annotation_manager._mark_dirty(image_path)
            
            # Save immediately
            self.main_window._save_current_annotations()
            
            # Refresh canvas
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            label_class = self.class_manager.get_by_id(new_class_id)
            self.statusbar.showMessage(self.tr("✓ BBox class updated: {}").format(label_class.name if label_class else 'object'))
    
    # ─────────────────────────────────────────────────────────────────
    # Polygon Editing Handlers
    # ─────────────────────────────────────────────────────────────────
    
    def _on_polygon_moved(self, index: int, new_points: list):
        """When polygon moved or points changed."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.polygons):
            w, h = self.main_window.canvas_view.scene.image_size
            if w == 0 or h == 0:
                return
            
            # Normalize coordinates
            normalized_points = [(x / w, y / h) for x, y in new_points]
            annotations.polygons[index].points = normalized_points
            
            self.annotation_manager._mark_dirty(image_path)
            
            # Save to labels folder immediately
            self.main_window._save_current_annotations()
            
            self.statusbar.showMessage(self.tr("✓ Polygon updated and saved"))
    
    def _on_polygon_delete(self, index: int):
        """When polygon deleted."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Close popup if open
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        if self.annotation_manager.remove_polygon(image_path, index):
            # Save
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage(self.tr("✓ Polygon deleted"))
    
    def _on_polygon_class_change(self, index: int, pos):
        """Request Polygon class change."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # If a popup already open, do not open new one
        if self._active_popup is not None:
            return
        
        # Store current polygon
        self._pending_polygon_class_change_index = index
        
        # Show popup
        canvas = self.main_window.canvas_view
        view_pos = canvas.mapFromScene(pos)
        global_pos = canvas.mapToGlobal(view_pos)
        
        popup = ClassSelectorPopup(
            self.class_manager, 
            self._last_used_class_id, 
            self
        )
        popup.class_selected.connect(self._on_polygon_class_changed)
        popup.closed.connect(self._on_popup_closed)
        popup.navigate_requested.connect(self._on_popup_navigate)
        popup.show_at(global_pos)
        
        # Save as active popup and set last edit type
        self._last_edit_type = "polygon"
        self._active_popup = popup
    
    def _on_polygon_class_changed(self, new_class_id: int):
        """When polygon class changed."""
        if not hasattr(self, '_pending_polygon_class_change_index'):
            return
        
        index = self._pending_polygon_class_change_index
        del self._pending_polygon_class_change_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.polygons):
            annotations.polygons[index].class_id = new_class_id
            self._last_used_class_id = new_class_id
            self.annotation_manager._mark_dirty(image_path)
            
            # Save immediately
            self.main_window._save_current_annotations()
            
            # Refresh canvas
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            label_class = self.class_manager.get_by_id(new_class_id)
            self.statusbar.showMessage(self.tr("✓ Polygon class updated: {}").format(label_class.name if label_class else 'object'))
            
    def _on_tool_changed(self, tool: str):
        """When tool changed."""
        tool_names = {"select": self.tr("Select"), "bbox": "BBox", "polygon": "Polygon"}
        self.statusbar.showMessage(self.tr("Tool: {}").format(tool_names.get(tool, tool)))
    
    def _open_class_management(self):
        """Open class management dialog."""
        dialog = ClassManagementDialog(
            self.class_manager, 
            self.annotation_manager, 
            self
        )
        dialog.classes_changed.connect(self._on_classes_changed)
        dialog.exec()
    
    def _on_classes_changed(self):
        """When classes changed."""
        # Update label summary
        self.main_window.annotation_list_widget.refresh()
        # Redraw canvas (for color changes)
        self.main_window.refresh_canvas()
        self.statusbar.showMessage(self.tr("Classes updated"))
    
    def _undo(self):
        """Undo last action."""
        if not self.annotation_manager.can_undo():
            self.statusbar.showMessage(self.tr("Nothing to undo"))
            return
        
        image_path, success = self.annotation_manager.undo()
        if success:
            # Save
            self.main_window._save_current_annotations()
            # Refresh canvas
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage(self.tr("↩️ Undone"))
        else:
            self.statusbar.showMessage(self.tr("Undo failed"))
    
    def _redo(self):
        """Redo last undone action."""
        if not self.annotation_manager.can_redo():
            self.statusbar.showMessage(self.tr("Nothing to redo"))
            return
        
        image_path, success = self.annotation_manager.redo()
        if success:
            # Save
            self.main_window._save_current_annotations()
            # Refresh canvas
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage(self.tr("↪️ Redone"))
        else:
            self.statusbar.showMessage(self.tr("Redo failed"))
    
    def _copy_annotations(self):
        """Copy selected label or all labels.
        
        If a bbox/polygon is selected on canvas, copy only that.
        If nothing selected, copy all labels.
        """
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage(self.tr("No image to copy from!"))
            return
        
        import copy
        
        # Find selected item from canvas
        canvas = self.main_window.canvas_view
        scene = canvas.scene
        
        selected_items = scene.selectedItems()
        
        if selected_items:
            # If selected item exists, copy only that
            from canvas.editable_rect_item import EditableRectItem
            from canvas.editable_polygon_item import EditablePolygonItem
            
            self._clipboard_bboxes = []
            self._clipboard_polygons = []
            
            for item in selected_items:
                if isinstance(item, EditableRectItem):
                    # Find BBox index
                    index = getattr(item, 'index', -1)
                    annotations = self.annotation_manager.get_annotations(image_path)
                    if 0 <= index < len(annotations.bboxes):
                        self._clipboard_bboxes.append(copy.deepcopy(annotations.bboxes[index]))
                elif isinstance(item, EditablePolygonItem):
                    # Find Polygon index
                    index = getattr(item, 'index', -1)
                    annotations = self.annotation_manager.get_annotations(image_path)
                    if 0 <= index < len(annotations.polygons):
                        self._clipboard_polygons.append(copy.deepcopy(annotations.polygons[index]))
            
            total = len(self._clipboard_bboxes) + len(self._clipboard_polygons)
            if total > 0:
                self.statusbar.showMessage(self.tr("📋 {} selected annotation(s) copied").format(total))
            else:
                self.statusbar.showMessage(self.tr("Selected annotation not found"))
        else:
            # Show warning if nothing selected
            self.statusbar.showMessage(self.tr("Select an annotation first to copy"))
    
    def _paste_annotations(self):
        """Paste copied labels to current image."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage(self.tr("No image to paste to!"))
            return
        
        # Clipboard check
        bboxes = getattr(self, '_clipboard_bboxes', [])
        polygons = getattr(self, '_clipboard_polygons', [])
        
        if not bboxes and not polygons:
            self.statusbar.showMessage(self.tr("Nothing to paste (copy with Ctrl+C first)"))
            return
        
        # Offset value (2% right-down shift)
        OFFSET = 0.02
        
        # Add labels (with offset)
        import copy
        for bbox in bboxes:
            new_bbox = copy.deepcopy(bbox)
            # Shift to bottom-right
            new_bbox.x_center = min(1.0, new_bbox.x_center + OFFSET)
            new_bbox.y_center = min(1.0, new_bbox.y_center + OFFSET)
            self.annotation_manager.add_bbox(image_path, new_bbox)
        
        for polygon in polygons:
            new_polygon = copy.deepcopy(polygon)
            # Shift all points
            new_polygon.points = [
                (min(1.0, x + OFFSET), min(1.0, y + OFFSET))
                for x, y in new_polygon.points
            ]
            self.annotation_manager.add_polygon(image_path, new_polygon)
        
        # Save and refresh
        self.main_window._save_current_annotations()
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        total = len(bboxes) + len(polygons)
        self.statusbar.showMessage(self.tr("📋 {} annotation(s) pasted").format(total))
    
    def _delete_all_annotations(self):
        """Delete all labels in current image."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage(self.tr("No image to delete from!"))
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        total = len(annotations.bboxes) + len(annotations.polygons)
        
        if total == 0:
            self.statusbar.showMessage(self.tr("No annotations to delete"))
            return
        
        # Get confirmation
        result = QMessageBox.question(
            self, self.tr("Delete All"),
            self.tr("Are you sure you want to delete {} annotations from this image?\n\nThis action cannot be undone!").format(total),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            self.annotation_manager.clear_annotations(image_path)
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage(self.tr("🗑️ {} annotation(s) deleted").format(total))
    
    # ─────────────────────────────────────────────────────────────────
    # Save Operations
    # ─────────────────────────────────────────────────────────────────
    
    def _save_annotations(self):
        """Save current image annotations to labels folder."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage(self.tr("No image to save!"))
            return
        
        # Determine labels folder
        image_p = Path(image_path)
        parent = image_p.parent
        if parent.name.lower() == "images":
            labels_dir = parent.parent / "labels"
        else:
            labels_dir = parent / "labels"
        
        labels_dir.mkdir(parents=True, exist_ok=True)
        self.annotation_manager.save_yolo(image_path, labels_dir)
        self.statusbar.showMessage(self.tr("✓ Saved: {}.txt").format(image_p.stem))
        
    def _save_all_annotations(self):
        """Save all annotations to labels folder."""
        if not self.project.root_path:
            self.statusbar.showMessage(self.tr("No source folder!"))
            return
        
        # Determine labels folder
        root = self.project.root_path
        if root.name.lower() == "images":
            labels_dir = root.parent / "labels"
        else:
            labels_dir = root / "labels"
        
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        count = 0
        for image_path in self.project.image_files:
            self.annotation_manager.save_yolo(str(image_path), labels_dir)
            count += 1
            
        # Save classes.txt
        self.class_manager.save_to_file(labels_dir / "classes.txt")
        self.statusbar.showMessage(self.tr("✓ {} file(s) saved").format(count))
        
    def _export_labels(self):
        """Open export dialog - with augmentation and split support."""
        if not self.project.root_path:
            self.statusbar.showMessage(self.tr("Open a folder first!"))
            return
        
        if not self.project.image_files:
            self.statusbar.showMessage(self.tr("No images to export!"))
            return
        
        # Save current image labels before export
        self.main_window._save_current_annotations()
        
        # Load all labels from disk before export
        self._load_all_labels_for_export()
        
        # Default output folder
        root = self.project.root_path
        if root.name.lower() == "images":
            default_output_dir = root.parent / "export"
        else:
            default_output_dir = root / "export"
        
        # Open Export Wizard (v1.5)
        dialog = ExportWizard(
            class_manager=self.class_manager,
            annotation_manager=self.annotation_manager,
            image_files=self.project.image_files,
            default_output_dir=default_output_dir,
            parent=self
        )
        dialog.exec()
    
    def _load_all_labels_for_export(self):
        """Load all labels from disk before export."""
        from pathlib import Path
        import cv2
        
        root = self.project.root_path
        if root.name.lower() == "images":
            labels_dir = root.parent / "labels"
        else:
            labels_dir = root / "labels"
        
        if not labels_dir.exists():
            return
        
        for image_path in self.project.image_files:
            key = str(image_path)
            
            # Skip if annotation already loaded for this image
            if key in self.annotation_manager._annotations:
                existing = self.annotation_manager._annotations[key]
                if existing.bboxes or existing.polygons:
                    continue
            
            # Find Labels file
            txt_path = labels_dir / f"{image_path.stem}.txt"
            if not txt_path.exists():
                continue
            
            # Get image dimensions
            try:
                img = cv2.imdecode(
                    __import__('numpy').frombuffer(open(str(image_path), 'rb').read(), __import__('numpy').uint8),
                    cv2.IMREAD_COLOR
                )
                if img is None:
                    continue
                h, w = img.shape[:2]
            except:
                continue
            
            # Load label
            self.annotation_manager._load_from_path(key, txt_path, w, h)
        
    def _delete_selected_annotation(self):
        """Delete selected label."""
        # TODO: Implement selection
        pass
        
    def _clear_all_annotations(self):
        """Clear all annotations."""
        image_path = self.main_window.get_current_image_path()
        if image_path:
            self.annotation_manager.clear_annotations(image_path)
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage(self.tr("All annotations cleared"))
    
    # ─────────────────────────────────────────────────────────────────
    # Drag & Drop
    # ─────────────────────────────────────────────────────────────────
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
            if paths:
                self._on_files_dropped(paths)
            event.acceptProposedAction()
    
    def _on_files_dropped(self, paths: list):
        if not paths:
            return
            
        first_path = Path(paths[0])
        
        if first_path.is_dir():
            self._load_folder(str(first_path))
        elif first_path.is_file():
            image_files = [
                Path(p) for p in paths 
                if Path(p).is_file() and Path(p).suffix.lower() in self.SUPPORTED_FORMATS
            ]
            if image_files:
                self._load_files(image_files)
    
    # ─────────────────────────────────────────────────────────────────
    # File Operations
    # ─────────────────────────────────────────────────────────────────
    
    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr("Select Image Folder"))
        if folder:
            self._load_folder(folder)
            
    def _open_file(self):
        formats = " ".join(f"*{ext}" for ext in self.SUPPORTED_FORMATS)
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Select Images"), "",
            self.tr("Image Files ({})").format(formats)
        )
        if files:
            self._load_files([Path(f) for f in files])
            
    def _load_folder(self, folder_path: str):
        count = self.project.load_folder(folder_path)
        
        if count > 0:
            folder = Path(folder_path)
            
            # Determine labels folder
            if folder.name.lower() == "images":
                labels_dir = folder.parent / "labels"
                root_dir = folder.parent
            else:
                labels_dir = folder / "labels"
                root_dir = folder
            
            classes_loaded = False
            
            # 1. Try loading classes from data.yaml first
            if self._load_classes_from_yaml(root_dir):
                classes_loaded = True
            
            # 2. Else load from classes.txt
            if not classes_loaded:
                classes_path = folder / "classes.txt"
                if not classes_path.exists():
                    classes_path = labels_dir / "classes.txt"
                if classes_path.exists():
                    self.class_manager.load_from_file(classes_path)
                    classes_loaded = True
            
            # 3. If neither exists, discover classes by scanning label files
            if not classes_loaded:
                self._discover_classes_from_labels(labels_dir)
            
            self.main_window.populate_file_list(self.project.image_files)
            self.main_window.file_list.setCurrentRow(0)
            
            # 4. Preload all annotations (for statistics)
            self._preload_all_annotations(labels_dir)
            
            class_count = self.class_manager.count
            self.statusbar.showMessage(self.tr("📁 {} images, {} classes loaded").format(count, class_count))
        else:
            self.statusbar.showMessage(self.tr("No images found in folder!"))
    
    def _load_classes_from_yaml(self, root_dir: Path) -> bool:
        """Load classes from data.yaml.
        
        Returns:
            True if successfully loaded
        """
        import yaml
        
        yaml_paths = [
            root_dir / "data.yaml",
            root_dir / "data.yml",
            root_dir.parent / "data.yaml",
            root_dir.parent / "data.yml",
        ]
        
        for yaml_path in yaml_paths:
            if yaml_path.exists():
                try:
                    with open(yaml_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    
                    names = data.get("names", {})
                    if names:
                        self.class_manager.clear()
                        
                        # names can be dict or list
                        if isinstance(names, dict):
                            for class_id, name in names.items():
                                self.class_manager.add_class_with_id(int(class_id), name)
                        elif isinstance(names, list):
                            for class_id, name in enumerate(names):
                                self.class_manager.add_class_with_id(class_id, name)
                        
                        self.statusbar.showMessage(self.tr("✓ {} classes loaded from data.yaml").format(len(names)))
                        return True
                except Exception as e:
                    print(f"data.yaml read error: {e}")
        
        return False
    
    def _discover_classes_from_labels(self, labels_dir: Path):
        """Discover used class IDs by scanning label files.
        
        This function is called only if classes.txt and data.yaml are missing.
        """
        if not labels_dir.exists():
            return
        
        # User info
        from PySide6.QtWidgets import QApplication
        self.statusbar.showMessage(self.tr("🔍 Scanning label files..."))
        QApplication.processEvents()  # Update UI
        
        discovered_ids = set()
        file_count = 0
        
        # Scan all .txt files (read only class IDs - optimized)
        txt_files = list(labels_dir.glob("*.txt"))
        total_files = len(txt_files)
        
        for txt_path in txt_files:
            if txt_path.name == "classes.txt":
                continue
            
            file_count += 1
            
            # Update UI every 100 files
            if file_count % 100 == 0:
                self.statusbar.showMessage(self.tr("🔍 Scanning... {}/{}").format(file_count, total_files))
                QApplication.processEvents()
            
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # YOLO format: class_id x_center y_center width height ...
                            parts = line.split()
                            if parts:
                                try:
                                    class_id = int(parts[0])
                                    discovered_ids.add(class_id)
                                except ValueError:
                                    continue
            except Exception:
                continue
        
        # Create discovered classes (assign different color to each)
        for class_id in sorted(discovered_ids):
            if self.class_manager.get_by_id(class_id) is None:
                self.class_manager.add_class_with_id(class_id, f"class_{class_id}")
        
        if discovered_ids:
            self.statusbar.showMessage(
                f"🔍 {len(discovered_ids)} classes discovered (classes.txt/data.yaml not found)"
            )
    
    def _preload_all_annotations(self, labels_dir: Path):
        """Preload all label files (for statistics).
        
        This function loads all .txt files into annotation_manager,
        so that class statistics are shown correctly from the start.
        """
        import cv2
        import numpy as np
        from PySide6.QtWidgets import QApplication
        
        if not labels_dir.exists():
            return
        
        self.statusbar.showMessage(self.tr("📊 Loading annotations..."))
        QApplication.processEvents()
        
        loaded_count = 0
        txt_files = list(labels_dir.glob("*.txt"))
        total_files = len(txt_files)
        
        for txt_path in txt_files:
            if txt_path.name == "classes.txt":
                continue
            
            loaded_count += 1
            
            # Update UI every 50 files
            if loaded_count % 50 == 0:
                self.statusbar.showMessage(self.tr("📊 Loading annotations... {}/{}").format(loaded_count, total_files))
                QApplication.processEvents()
            
            # Find matching image file
            image_path = None
            for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                potential_path = txt_path.parent.parent / "images" / f"{txt_path.stem}{ext}"
                if potential_path.exists():
                    image_path = potential_path
                    break
                # Could be in same folder
                potential_path = txt_path.parent / f"{txt_path.stem}{ext}"
                if potential_path.exists():
                    image_path = potential_path
                    break
            
            if not image_path:
                # Find from project files
                for img_file in self.project.image_files:
                    if img_file.stem == txt_path.stem:
                        image_path = img_file
                        break
            
            if not image_path:
                continue
            
            key = str(image_path)
            
            # Get image dimensions (if not loaded yet use default)
            # Since labels are normalized, dimension is not critical, use default
            w, h = 1920, 1080  # Default size (unimportant for normalized coords)
            
            # Load label
            self.annotation_manager._load_from_path(key, txt_path, w, h)
            
    def _load_files(self, image_files: list):
        self.project.image_files = sorted(image_files)
        self.project.current_index = 0
        self.project.root_path = image_files[0].parent if len(image_files) == 1 else None
        
        self.main_window.populate_file_list(self.project.image_files)
        self.main_window.file_list.setCurrentRow(0)
        self.statusbar.showMessage(self.tr("🖼️ {} images loaded").format(len(image_files)))
            
    def _next_image(self):
        # Close popup if open
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        current = self.main_window.file_list.currentRow()
        total = self.main_window.file_list.count()
        if current < total - 1:
            self.main_window.file_list.setCurrentRow(current + 1)
            
    def _prev_image(self):
        # Close popup if open
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        current = self.main_window.file_list.currentRow()
        if current > 0:
            self.main_window.file_list.setCurrentRow(current - 1)
    
    # ─────────────────────────────────────────────────────────────────
    # Zoom
    # ─────────────────────────────────────────────────────────────────
    
    def _zoom_in(self):
        self.main_window.canvas_view.zoom_in()
        
    def _zoom_out(self):
        self.main_window.canvas_view.zoom_out()
        
    def _zoom_fit(self):
        self.main_window.canvas_view.zoom_fit()
        
    def _zoom_reset(self):
        self.main_window.canvas_view.zoom_reset()
        
    def _on_zoom_changed(self, level: float):
        percent = int(level * 100)
        self.statusbar.showMessage(self.tr("Zoom: {}%").format(percent))
        
    def _on_mouse_position(self, x: int, y: int):
        percent = int(self.main_window.canvas_view.zoom_level * 100)
        current = self.main_window.file_list.currentRow() + 1
        total = self.main_window.file_list.count()
        self.statusbar.showMessage(f"[{current}/{total}] ({x}, {y}) | %{percent}")
    
    # ─────────────────────────────────────────────────────────────────
    # Help
    # ─────────────────────────────────────────────────────────────────
    
    def _show_about(self):
        about_text = self.tr("""<h2>LocalTagger</h2>
<p><b>Professional Data Annotation Tool</b></p>
<p>LocalTagger is a high-performance, privacy-centric application designed for efficient local data annotation. It integrates advanced AI capabilities with a robust manual labeling interface.</p>

<h3>Key Features</h3>
<ul>
<li><b>Secure & Local:</b> Operates entirely offline to ensure maximum data privacy.</li>
<li><b>AI Assistance:</b> Integrated MobileSAM model for automated object segmentation.</li>
<li><b>Multi-Format Export:</b> Supports YOLO, COCO, and Pascal VOC standards with built-in data augmentation.</li>
</ul>

<h3>Usage Guide</h3>
<p>To start annotating, load a folder of images using the File menu. Select a class from the list or create a new one.</p>
<ul>
<li><b>Drawing:</b> Use the Toolbar or shortcuts to switch between Bounding Box and Polygon modes.</li>
<li><b>Editing:</b> Switch to Select Mode to adjust existing annotations. Double-click a label to modify its class.</li>
<li><b>AI Mode:</b> Enable AI to automatically segment and annotate objects with a single click.</li>
</ul>

<h3>Keyboard Shortcuts</h3>
<table width="100%" cellspacing="4">
<tr><td><b>W</b></td><td>Bounding Box Tool</td><td><b>E</b></td><td>Polygon Tool</td></tr>
<tr><td><b>Q</b></td><td>Select/Edit Tool</td><td><b>T</b></td><td>Toggle AI Mode</td></tr>
<tr><td><b>A / D</b></td><td>Previous / Next Image</td><td><b>Del</b></td><td>Delete Selected</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save Changes</td><td><b>Ctrl+E</b></td><td>Export Data</td></tr>
</table>

<p style="color: grey; font-size: 10px; margin-top: 15px;">© 2026 LocalTagger</p>
""")
        msg = QMessageBox(self)
        msg.setWindowTitle(self.tr("About LocalTagger"))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    def closeEvent(self, event):
        """Check for unsaved changes when closing application."""
        # Save current image labels
        self.main_window._save_current_annotations()
        
        # Check if there are unsaved changes
        if self.annotation_manager.is_dirty():
            reply = QMessageBox.question(
                self,
                self.tr("Unsaved Changes"),
                self.tr("There are unsaved changes. Do you want to exit without saving?"),
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                # Save all changes
                self._save_all_annotations()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return
        
        event.accept()
    
    def keyPressEvent(self, event):
        """If active popup exists, redirect key events to popup."""
        if self._active_popup is not None and self._active_popup.isVisible():
            key = event.key()
            # 1-9 keys, Enter, ESC - redirect to popup
            if (Qt.Key.Key_1 <= key <= Qt.Key.Key_9 or 
                key in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                       Qt.Key.Key_A, Qt.Key.Key_D, Qt.Key.Key_Left, Qt.Key.Key_Right)):
                self._active_popup.keyPressEvent(event)
                return
        super().keyPressEvent(event)
    
    # ─────────────────────────────────────────────────────────────────
    # SAM / AI Integration
    # ─────────────────────────────────────────────────────────────────
    
    def _setup_sam_worker(self):
        """Start SAM worker."""
        # Model paths
        # Model paths
        # resources_dir = Path(__file__).parent / "resources" / "models"
        encoder_path = get_resource_path("resources/models/mobile_sam_encoder.onnx")
        decoder_path = get_resource_path("resources/models/mobile_sam.onnx")
        
        # Create worker
        self._sam_worker = SAMWorker(self)
        self._sam_worker.set_model_paths(str(encoder_path), str(decoder_path))
        
        # Connect signals
        self._sam_worker.model_loaded.connect(self._on_sam_model_loaded)
        self._sam_worker.model_load_failed.connect(self._on_sam_model_failed)
        self._sam_worker.encoding_started.connect(self._on_sam_encoding_started)
        self._sam_worker.encoding_finished.connect(self._on_sam_encoding_finished)
        self._sam_worker.mask_ready.connect(self._on_sam_mask_ready)
        self._sam_worker.error_occurred.connect(self._on_sam_error)
        
        # Load models (async)
        self.main_window.set_sam_ready(False)
        self._sam_worker.request_load_models()
    
    def _toggle_magic_pixel(self):
        """Magic Pixel toggle shortcut (T key)."""
        if not self._sam_worker.is_model_loaded:
            self.statusbar.showMessage(self.tr("⏳ SAM model is loading, please wait..."))
            return
        
        # If Magic Pixel active close, else open
        if self.main_window.sam_mode == "pixel":
            self.main_window.set_sam_mode(None)
        else:
            self.main_window.set_sam_mode("pixel")
    
    def _toggle_magic_box(self):
        """Magic Box toggle shortcut (Y key)."""
        if not self._sam_worker.is_model_loaded:
            self.statusbar.showMessage(self.tr("⏳ SAM model is loading, please wait..."))
            return
        
        # If Magic Box active close, else open
        if self.main_window.sam_mode == "box":
            self.main_window.set_sam_mode(None)
        else:
            self.main_window.set_sam_mode("box")
    
    def _on_sam_toggled(self, enabled: bool):
        """When SAM toggle changes."""
        if enabled:
            self.statusbar.showMessage(self.tr("🤖 AI mode enabled - Click on an object"))
            # If image exists start encoding
            self._encode_current_image()
        else:
            self.statusbar.showMessage(self.tr("🤖 AI mode disabled"))
    
    def _on_sam_model_loaded(self):
        """When SAM model loaded."""
        self.main_window.set_sam_ready(True)
        self.statusbar.showMessage(self.tr("✓ SAM model loaded - Press T to enable AI"))
    
    def _on_sam_model_failed(self, error: str):
        """SAM model load error."""
        self.main_window.set_sam_ready(False)
        self.statusbar.showMessage(self.tr("❌ SAM model error: {}").format(error))
    
    def _on_sam_encoding_started(self):
        """When image encoding starts."""
        self.main_window.set_sam_status(self.tr("⏳ Analyzing..."))
    
    def _on_sam_encoding_finished(self):
        """When image encoding finishes."""
        self.main_window.set_sam_status(self.tr("✓ Ready"))
        self.statusbar.showMessage(self.tr("🤖 AI ready - Click on an object"))
    
    def _on_sam_error(self, error: str):
        """When SAM error occurs."""
        self.main_window.set_sam_status("")
        self.statusbar.showMessage(self.tr("❌ SAM error: {}").format(error))
    
    def _on_sam_click(self, x: int, y: int, mode: str):
        """When SAM click received from canvas."""
        # Prevent new click if popup open
        if self._active_popup is not None:
            return
        
        if not self._sam_worker.is_ready:
            self.statusbar.showMessage(self.tr("⏳ Please wait, analyzing image..."))
            return
        
        self.statusbar.showMessage(self.tr("🔍 AI segmentation in progress... ({}, {})").format(x, y))
        self._sam_worker.request_infer_point(x, y, mode)
    
    def _on_sam_box(self, x1: int, y1: int, x2: int, y2: int, mode: str):
        """When SAM bbox request received from canvas (Magic Box mode).
        
        Args:
            x1, y1, x2, y2: Bbox koordinatları
            mode: 'bbox' or 'polygon' - result type
        """
        # Prevent new request if popup open
        if self._active_popup is not None:
            return
        
        if not self._sam_worker.is_ready:
            self.statusbar.showMessage("⏳ Please wait, analyzing image...")
            return
        
        mode_text = "bbox→bbox" if mode == "bbox" else "bbox→polygon"
        self.statusbar.showMessage(f"🔍 AI {mode_text} segmentation in progress...")
        self._sam_worker.request_infer_box(x1, y1, x2, y2, mode)
    
    def _on_sam_mask_ready(self, mask, mode: str, x: int, y: int):
        """When SAM mask is ready."""
        import numpy as np
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        w, h = self.main_window.canvas_view.scene.image_size
        if w == 0 or h == 0:
            return
        
        if mode == "bbox":
            # Mask → BBox
            result = self._sam_worker.get_bbox_from_mask(mask)
            if result is None:
                self.statusbar.showMessage("❌ Object not found")
                return
            
            x1, y1, x2, y2 = result
            
            # Create BBox
            self._on_bbox_created(float(x1), float(y1), float(x2), float(y2))
            self.statusbar.showMessage(f"✓ AI BBox created")
            
        elif mode == "polygon":
            # Mask → Polygon
            points = self._sam_worker.get_polygon_from_mask(mask)
            if points is None or len(points) < 3:
                self.statusbar.showMessage("❌ Object not found")
                return
            
            # Create polygon - use existing flow
            self._pending_polygon = list(points)
            
            # Add polygon temporarily first (for visual feedback)
            # Normalize
            w, h = self.main_window.canvas_view.scene.image_size
            normalized_points = [(x / w, y / h) for x, y in points]
            
            class_id = self._last_used_class_id
            if self.class_manager.get_by_id(class_id) is None and self.class_manager.count > 0:
                class_id = self.class_manager.classes[0].id
            
            polygon = Polygon(class_id=class_id, points=normalized_points)
            self.annotation_manager.add_polygon(image_path, polygon)
            
            # Save and refresh
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            # Store index of last added polygon
            annotations = self.annotation_manager.get_annotations(image_path)
            self._pending_polygon_index = len(annotations.polygons) - 1
            
            # Show popup next to last point
            if points:
                last_x, last_y = points[-1]
                canvas = self.main_window.canvas_view
                from PySide6.QtCore import QPointF
                scene_pos = canvas.mapFromScene(QPointF(last_x, last_y))
                global_pos = canvas.mapToGlobal(scene_pos)
                
                popup = ClassSelectorPopup(
                    self.class_manager, 
                    self._last_used_class_id, 
                    self
                )
                popup.class_selected.connect(self._on_ai_polygon_class_selected)
                popup.cancelled.connect(self._on_ai_polygon_cancelled)
                popup.closed.connect(self._on_popup_closed)
                popup.navigate_requested.connect(self._on_popup_navigate)
                popup.show_at(global_pos)
                
                # Save as active popup and set last edit type
                self._last_edit_type = "polygon"
                self._active_popup = popup
                
                # Switch to Select mode - allow polygon editing
                self.main_window.set_tool("select")
                
                self.statusbar.showMessage(self.tr("✓ AI Polygon created - Select class"))
    
    def _encode_current_image(self):
        """Encode current image for SAM."""
        import cv2
        import numpy as np
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        if not self._sam_worker.is_model_loaded:
            return
        
        # Read image
        try:
            img_data = np.frombuffer(open(image_path, 'rb').read(), np.uint8)
            image = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            if image is None:
                return
        except Exception as e:
            self.statusbar.showMessage(self.tr("❌ Could not read image: {}").format(e))
            return
        
        # Start encoding
        self._sam_worker.request_encode_image(image)

