"""
LocalFlow - Ana Uygulama Sınıfı
===============================
Uygulamanın ana penceresi ve genel koordinasyonu.
"""

from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QStatusBar, QFileDialog, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from ui.main_window import MainWindow
from ui.dialogs.class_management_dialog import ClassManagementDialog
from ui.dialogs.export_dialog_v2 import ExportWizard
from ui.widgets.class_selector_popup import ClassSelectorPopup
from core.project import Project
from core.class_manager import ClassManager
from core.annotation_manager import AnnotationManager
from core.annotation import BoundingBox, Polygon
from core.sam_worker import SAMWorker


class LocalFlowApp(QMainWindow):
    """LocalFlow ana uygulama penceresi."""
    
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff", ".tif"}
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalFlow v2.0 - Veri Etiketleme Aracı")
        self.setMinimumSize(1200, 800)
        
        # Managers
        self.project = Project()
        self.class_manager = ClassManager()
        self.annotation_manager = AnnotationManager()
        
        # Son kullanılan sınıf ID'si
        self._last_used_class_id = 0
        
        # Bekleyen bbox (popup sınıf seçimi için)
        self._pending_bbox = None  # (x1, y1, x2, y2)
        
        # Seçili annotation takibi (kopyala/yapıştır için)
        self._selected_annotation = None  # (type: "bbox"|"polygon", index)
        
        # Aktif popup takibi (aynı anda sadece 1 popup)
        self._active_popup = None
        
        # Varsayılan sınıflar
        self._add_default_classes()
        
        # Arayüz
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
        self._setup_shortcuts()
        self._connect_signals()
        
        self.setAcceptDrops(True)
        
        # SAM Worker (AI destekli etiketleme)
        self._setup_sam_worker()
        
    def _add_default_classes(self):
        """Varsayılan etiket sınıflarını ekle."""
        if self.class_manager.count == 0:
            self.class_manager.add_class("object")
        
    def _setup_ui(self):
        self.main_window = MainWindow(self.class_manager, self.annotation_manager, self)
        self.setCentralWidget(self.main_window)
        
    def _setup_menubar(self):
        menubar = self.menuBar()
        
        # Dosya menüsü
        file_menu = menubar.addMenu("&Dosya")
        file_menu.addAction("Klasör Aç...", self._open_folder, QKeySequence("Ctrl+O"))
        file_menu.addAction("Dosya Aç...", self._open_file, QKeySequence("Ctrl+Shift+O"))
        file_menu.addSeparator()
        file_menu.addAction("Kaydet", self._save_annotations, QKeySequence("Ctrl+S"))
        file_menu.addAction("Tümünü Kaydet", self._save_all_annotations, QKeySequence("Ctrl+Shift+S"))
        file_menu.addSeparator()
        file_menu.addAction("Dışa Aktar...", self._export_labels, QKeySequence("Ctrl+E"))
        file_menu.addSeparator()
        file_menu.addAction("Çıkış", self.close, QKeySequence("Ctrl+Q"))
        
        # Düzenle menüsü
        edit_menu = menubar.addMenu("&Düzenle")
        edit_menu.addAction("🏷️ Sınıf Yönetimi...", self._open_class_management)
        edit_menu.addSeparator()
        edit_menu.addAction("Seçili Etiketi Sil", self._delete_selected_annotation, QKeySequence("Delete"))
        edit_menu.addAction("Tüm Etiketleri Temizle", self._clear_all_annotations)
        
        # Görünüm menüsü
        view_menu = menubar.addMenu("&Görünüm")
        view_menu.addAction("Yakınlaştır", self._zoom_in, QKeySequence("Ctrl+="))
        view_menu.addAction("Uzaklaştır", self._zoom_out, QKeySequence("Ctrl+-"))
        view_menu.addAction("Sığdır", self._zoom_fit, QKeySequence("Ctrl+0"))
        view_menu.addAction("Gerçek Boyut", self._zoom_reset, QKeySequence("Ctrl+1"))
        
        # Yardım menüsü
        help_menu = menubar.addMenu("&Yardım")
        help_menu.addAction("Hakkında", self._show_about)
        
    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Hazır - Ctrl+O ile klasör açın")
        
    def _setup_shortcuts(self):
        # Navigasyon
        QShortcut(QKeySequence("D"), self, self._next_image)
        QShortcut(QKeySequence("A"), self, self._prev_image)
        QShortcut(QKeySequence("Right"), self, self._next_image)
        QShortcut(QKeySequence("Left"), self, self._prev_image)
        
        # Araçlar
        QShortcut(QKeySequence("Q"), self, lambda: self.main_window.set_tool("select"))
        QShortcut(QKeySequence("W"), self, lambda: self.main_window.set_tool("bbox"))
        QShortcut(QKeySequence("E"), self, lambda: self.main_window.set_tool("polygon"))
        QShortcut(QKeySequence("T"), self, self._toggle_magic_pixel)  # Magic Pixel toggle
        QShortcut(QKeySequence("Y"), self, self._toggle_magic_box)  # Magic Box toggle
        
        # Undo/Redo
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        
        # Kopyala/Yapıştır
        QShortcut(QKeySequence("Ctrl+C"), self, self._copy_annotations)
        QShortcut(QKeySequence("Ctrl+V"), self, self._paste_annotations)
        
        # Toplu silme
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), self, self._delete_all_annotations)
        
    def _connect_signals(self):
        canvas = self.main_window.canvas_view
        canvas.zoom_changed.connect(self._on_zoom_changed)
        canvas.mouse_position.connect(self._on_mouse_position)
        canvas.files_dropped.connect(self._on_files_dropped)
        canvas.bbox_created.connect(self._on_bbox_created)
        canvas.polygon_created.connect(self._on_polygon_created)
        
        # BBox düzenleme sinyalleri
        canvas.bbox_moved.connect(self._on_bbox_moved)
        canvas.bbox_delete_requested.connect(self._on_bbox_delete)
        canvas.bbox_class_change_requested.connect(self._on_bbox_class_change)
        
        # Polygon düzenleme sinyalleri
        canvas.polygon_moved.connect(self._on_polygon_moved)
        canvas.polygon_delete_requested.connect(self._on_polygon_delete)
        canvas.polygon_class_change_requested.connect(self._on_polygon_class_change)
        
        # Annotation tıklama - otomatik select moduna geçiş
        canvas.annotation_clicked.connect(self._on_annotation_clicked)
        
        # Görsel değiştiğinde popup kapat
        self.main_window.image_selected.connect(self._on_image_changed)
        
        self.main_window.tool_changed.connect(self._on_tool_changed)
        
        # SAM sinyalleri
        canvas.sam_click_requested.connect(self._on_sam_click)
        canvas.sam_box_requested.connect(self._on_sam_box)  # Polygon+AI için bbox→polygon
        self.main_window.sam_toggled.connect(self._on_sam_toggled)
        
        # Annotation list widget sinyalleri
        self.main_window.annotation_list_widget.clear_all_requested.connect(self._delete_all_annotations)
    
    def _on_image_changed(self, image_path: str):
        """Görsel değiştiğinde - açık popup'ları kapat ve SAM encoding başlat."""
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        # SAM etkinse yeni görsel için encoding başlat
        if self.main_window.sam_enabled:
            self._encode_current_image()
    
    def _on_annotation_clicked(self):
        """Bir annotasyona tıklandığında - select moduna geç."""
        self.main_window.set_tool("select")
    
    def _on_popup_closed(self):
        """Popup kapandığında - canvas'a focus ver ve çizim moduna dön."""
        self._active_popup = None
        
        # Düzenlenen item'ın indeksini sakla
        editing_index = getattr(self, '_pending_class_change_index', None)
        editing_type = getattr(self, '_last_edit_type', 'bbox')
        
        # Canvas'ı yenile - düzenleme işaretlerini temizle
        self.main_window.refresh_canvas()
        
        # Eğer bir item düzenleniyor idiyse, o item'ı tekrar seç
        if editing_index is not None:
            canvas = self.main_window.canvas_view
            if canvas._annotation_items and 0 <= editing_index < len(canvas._annotation_items):
                item = canvas._annotation_items[editing_index]
                item.setSelected(True)
        
        # Canvas'a focus ver (delete tuşları için)
        self.main_window.canvas_view.setFocus()
        
        # Son düzenlenen türüne göre mod değiştir
        self.main_window.set_tool(editing_type)
    
    def _on_popup_navigate(self, direction: str):
        """Popup'tan navigasyon isteği geldiğinde."""
        self._active_popup = None
        if direction == 'next':
            self._next_image()
        elif direction == 'prev':
            self._prev_image()
        
    # ─────────────────────────────────────────────────────────────────
    # Annotation Event Handlers
    # ─────────────────────────────────────────────────────────────────
    
    def _on_bbox_created(self, x1: float, y1: float, x2: float, y2: float):
        """BBox oluşturulduğunda - hemen ekle, sonra popup göster."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Piksel koordinatlarını normalize et
        w, h = self.main_window.canvas_view.scene.image_size
        if w == 0 or h == 0:
            return
        
        # Varsayılan veya son kullanılan sınıf ile hemen ekle
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
        
        # Hemen kaydet
        self.main_window._save_current_annotations()
        
        # Canvas'ı yenile - bbox EditableRectItem olarak görünsün
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        # Son eklenen bbox'ı seçili yap (kesikli çizgi görünsün)
        canvas = self.main_window.canvas_view
        if canvas._annotation_items:
            last_item = canvas._annotation_items[-1]
            last_item.setSelected(True)
        
        # Son eklenen bbox'ın indeksini sakla (sınıf değişikliği için)
        annotations = self.annotation_manager.get_annotations(image_path)
        self._pending_bbox_index = len(annotations.bboxes) - 1
        
        # Popup'u bbox'ın sağ üst köşesinde göster (biraz sağa ofset ile)
        scene_pos = canvas.mapFromScene(x2 + 15, y1)  # 15px sağa ofset
        global_pos = canvas.mapToGlobal(scene_pos)
        
        # Eğer zaten bir popup açıksa, yeni popup açma
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
        
        # Aktif popup olarak kaydet ve son düzenleme türünü belirle
        self._last_edit_type = "bbox"
        self._active_popup = self._class_popup
        
        # Select moduna geç - bbox düzenlenebilsin
        self.main_window.set_tool("select")
    
    def _on_new_bbox_class_selected(self, class_id: int):
        """Yeni bbox için popup'tan sınıf seçildiğinde."""
        if not hasattr(self, '_pending_bbox_index'):
            return
        
        index = self._pending_bbox_index
        del self._pending_bbox_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.bboxes):
            # Sınıfı güncelle
            annotations.bboxes[index].class_id = class_id
            self._last_used_class_id = class_id
            self.annotation_manager._mark_dirty(image_path)
            
            # Hemen kaydet
            self.main_window._save_current_annotations()
            
            # Canvas'ı yenile
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            # Rengi güncelle
            label_class = self.class_manager.get_by_id(class_id)
            if label_class:
                self.main_window.canvas_view.set_draw_color(label_class.color)
            
            self.statusbar.showMessage(f"✓ BBox eklendi: {label_class.name if label_class else 'object'}")
            
            # Geri çizim moduna geç
            self.main_window.set_tool("bbox")
    
    def _on_new_bbox_cancelled(self):
        """Yeni bbox sınıf seçimi iptal edildiğinde - bbox'ı sil."""
        if not hasattr(self, '_pending_bbox_index'):
            return
        
        index = self._pending_bbox_index
        del self._pending_bbox_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # BBox'ı sil
        self.annotation_manager.remove_bbox(image_path, index)
        
        # Kaydet ve yenile
        self.main_window._save_current_annotations()
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        self.statusbar.showMessage("BBox iptal edildi")
    
    def _on_bbox_cancelled(self):
        """Bbox sınıf seçimi iptal edildiğinde."""
        if self._pending_bbox:
            # Canvas'tan bbox'u kaldır (çizilmiş son item)
            if self.main_window.canvas_view._annotation_items:
                last_item = self.main_window.canvas_view._annotation_items.pop()
                try:
                    if last_item.scene():
                        self.main_window.canvas_view.scene.removeItem(last_item)
                except RuntimeError:
                    pass
        self._pending_bbox = None
        self.statusbar.showMessage("BBox iptal edildi")
        
    def _on_polygon_created(self, points: list):
        """Polygon oluşturulduğunda - popup göster."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Piksel noktaları sakla
        self._pending_polygon = points
        
        # Popup'u son noktanın yanında göster
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
            
            # Aktif popup olarak kaydet
            self._active_popup = popup
    
    def _on_polygon_class_selected(self, class_id: int):
        """Popup'tan polygon sınıfı seçildiğinde."""
        if not self._pending_polygon:
            return
        
        points = self._pending_polygon
        self._pending_polygon = None
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Sınıfı güncelle
        self._last_used_class_id = class_id
        
        # Normalize et
        w, h = self.main_window.canvas_view.scene.image_size
        if w == 0 or h == 0:
            return
            
        normalized_points = [(x / w, y / h) for x, y in points]
        
        polygon = Polygon(class_id=class_id, points=normalized_points)
        self.annotation_manager.add_polygon(image_path, polygon)
        
        # Canvas'ı yenile - polygon EditablePolygonItem olarak görünsün
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        label_class = self.class_manager.get_by_id(class_id)
        self.statusbar.showMessage(f"✓ Polygon eklendi: {label_class.name if label_class else 'object'}")
    
    def _on_polygon_cancelled(self):
        """Polygon sınıf seçimi iptal edildiğinde."""
        if self._pending_polygon:
            # Canvas'tan polygon'u kaldır (çizilmiş son item)
            if self.main_window.canvas_view._annotation_items:
                last_item = self.main_window.canvas_view._annotation_items.pop()
                try:
                    if last_item.scene():
                        self.main_window.canvas_view.scene.removeItem(last_item)
                except RuntimeError:
                    pass
        self._pending_polygon = None
        self.statusbar.showMessage("Polygon iptal edildi")
    
    def _on_ai_polygon_class_selected(self, class_id: int):
        """AI polygon için popup'tan sınıf seçildiğinde."""
        if not hasattr(self, '_pending_polygon_index'):
            return
        
        index = self._pending_polygon_index
        del self._pending_polygon_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.polygons):
            # Sınıfı güncelle
            annotations.polygons[index].class_id = class_id
            self._last_used_class_id = class_id
            self.annotation_manager._mark_dirty(image_path)
            
            # Hemen kaydet
            self.main_window._save_current_annotations()
            
            # Canvas'ı yenile
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            # Rengi güncelle
            label_class = self.class_manager.get_by_id(class_id)
            if label_class:
                self.main_window.canvas_view.set_draw_color(label_class.color)
            
            self.statusbar.showMessage(f"✓ AI Polygon sınıfı: {label_class.name if label_class else 'object'}")
            
            # Geri polygon moduna geç
            self.main_window.set_tool("polygon")
    
    def _on_ai_polygon_cancelled(self):
        """AI polygon sınıf seçimi iptal edildiğinde - polygon'u sil."""
        if not hasattr(self, '_pending_polygon_index'):
            return
        
        index = self._pending_polygon_index
        del self._pending_polygon_index
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Polygon'u sil
        self.annotation_manager.remove_polygon(image_path, index)
        
        # Kaydet ve yenile
        self.main_window._save_current_annotations()
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        self._pending_polygon = None
        self.statusbar.showMessage("AI Polygon iptal edildi")
        
    def _on_class_selected(self, class_id: int):
        """Sınıf seçildiğinde."""
        self._last_used_class_id = class_id
        label_class = self.class_manager.get_by_id(class_id)
        if label_class:
            self.main_window.set_draw_color(class_id)
            self.statusbar.showMessage(f"Sınıf: {label_class.name}")
    
    def _on_bbox_moved(self, index: int, new_rect):
        """BBox taşındığında veya yeniden boyutlandırıldığında."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.bboxes):
            w, h = self.main_window.canvas_view.scene.image_size
            if w == 0 or h == 0:
                return
            
            # Yeni koordinatları hesapla
            bbox = annotations.bboxes[index]
            bbox.x_center = (new_rect.left() + new_rect.width() / 2) / w
            bbox.y_center = (new_rect.top() + new_rect.height() / 2) / h
            bbox.width = new_rect.width() / w
            bbox.height = new_rect.height() / h
            
            self.annotation_manager._mark_dirty(image_path)
            
            # Hemen labels klasörüne kaydet
            self.main_window._save_current_annotations()
            
            self.statusbar.showMessage("✓ BBox güncellendi ve kaydedildi")
    
    def _on_bbox_delete(self, index: int):
        """BBox silindiğinde."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Açık popup varsa kapat
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        if self.annotation_manager.remove_bbox(image_path, index):
            # Kaydet
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage("✓ BBox silindi")
    
    def _on_bbox_class_change(self, index: int, pos):
        """BBox sınıf değiştirme isteğinde."""
        from PySide6.QtCore import QPoint
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Eğer zaten bir popup açıksa, yeni popup açma
        if self._active_popup is not None:
            return
        
        # Geçerli bbox'ı sakla
        self._pending_class_change_index = index
        
        # Popup göster
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
        
        # Aktif popup olarak kaydet ve son düzenleme türünü belirle
        self._last_edit_type = "bbox"
        self._active_popup = popup
    
    def _on_bbox_class_changed(self, new_class_id: int):
        """BBox sınıfı değiştirildiğinde."""
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
            
            # Hemen kaydet
            self.main_window._save_current_annotations()
            
            # Canvas'ı yenile
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            label_class = self.class_manager.get_by_id(new_class_id)
            self.statusbar.showMessage(f"✓ BBox sınıfı güncellendi: {label_class.name if label_class else 'object'}")
    
    # ─────────────────────────────────────────────────────────────────
    # Polygon Editing Handlers
    # ─────────────────────────────────────────────────────────────────
    
    def _on_polygon_moved(self, index: int, new_points: list):
        """Polygon taşındığında veya noktaları değiştiğinde."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        if 0 <= index < len(annotations.polygons):
            w, h = self.main_window.canvas_view.scene.image_size
            if w == 0 or h == 0:
                return
            
            # Normalize koordinatları
            normalized_points = [(x / w, y / h) for x, y in new_points]
            annotations.polygons[index].points = normalized_points
            
            self.annotation_manager._mark_dirty(image_path)
            
            # Hemen labels klasörüne kaydet
            self.main_window._save_current_annotations()
            
            self.statusbar.showMessage("✓ Polygon güncellendi ve kaydedildi")
    
    def _on_polygon_delete(self, index: int):
        """Polygon silindiğinde."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Açık popup varsa kapat
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        if self.annotation_manager.remove_polygon(image_path, index):
            # Kaydet
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage("✓ Polygon silindi")
    
    def _on_polygon_class_change(self, index: int, pos):
        """Polygon sınıf değiştirme isteğinde."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        # Eğer zaten bir popup açıksa, yeni popup açma
        if self._active_popup is not None:
            return
        
        # Geçerli polygon'u sakla
        self._pending_polygon_class_change_index = index
        
        # Popup göster
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
        
        # Aktif popup olarak kaydet ve son düzenleme türünü belirle
        self._last_edit_type = "polygon"
        self._active_popup = popup
    
    def _on_polygon_class_changed(self, new_class_id: int):
        """Polygon sınıfı değiştirildiğinde."""
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
            
            # Hemen kaydet
            self.main_window._save_current_annotations()
            
            # Canvas'ı yenile
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            label_class = self.class_manager.get_by_id(new_class_id)
            self.statusbar.showMessage(f"✓ Polygon sınıfı güncellendi: {label_class.name if label_class else 'object'}")
            
    def _on_tool_changed(self, tool: str):
        """Araç değiştiğinde."""
        tool_names = {"select": "Seç", "bbox": "BBox", "polygon": "Polygon"}
        self.statusbar.showMessage(f"Araç: {tool_names.get(tool, tool)}")
    
    def _open_class_management(self):
        """Sınıf yönetimi dialogunu aç."""
        dialog = ClassManagementDialog(
            self.class_manager, 
            self.annotation_manager, 
            self
        )
        dialog.classes_changed.connect(self._on_classes_changed)
        dialog.exec()
    
    def _on_classes_changed(self):
        """Sınıflar değiştiğinde."""
        # Etiket özetini güncelle
        self.main_window.annotation_list_widget.refresh()
        # Canvas'ı yeniden çiz (renk değişiklikleri için)
        self.main_window.refresh_canvas()
        self.statusbar.showMessage("Sınıflar güncellendi")
    
    def _undo(self):
        """Son işlemi geri al."""
        if not self.annotation_manager.can_undo():
            self.statusbar.showMessage("Geri alınacak işlem yok")
            return
        
        image_path, success = self.annotation_manager.undo()
        if success:
            # Kaydet
            self.main_window._save_current_annotations()
            # Canvas'ı yenile
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage("↩️ Geri alındı")
        else:
            self.statusbar.showMessage("Geri alma başarısız")
    
    def _redo(self):
        """Son geri alınan işlemi yeniden yap."""
        if not self.annotation_manager.can_redo():
            self.statusbar.showMessage("İleri alınacak işlem yok")
            return
        
        image_path, success = self.annotation_manager.redo()
        if success:
            # Kaydet
            self.main_window._save_current_annotations()
            # Canvas'ı yenile
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage("↪️ Yeniden yapıldı")
        else:
            self.statusbar.showMessage("İleri alma başarısız")
    
    def _copy_annotations(self):
        """Seçili etiketi veya tüm etiketleri kopyala.
        
        Canvas'ta seçili bir bbox/polygon varsa sadece onu kopyalar.
        Seçili bir şey yoksa tüm etiketleri kopyalar.
        """
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage("Kopyalanacak görsel yok!")
            return
        
        import copy
        
        # Canvas'tan seçili item'ı bul
        canvas = self.main_window.canvas_view
        scene = canvas.scene
        
        selected_items = scene.selectedItems()
        
        if selected_items:
            # Seçili item varsa sadece onu kopyala
            from canvas.editable_rect_item import EditableRectItem
            from canvas.editable_polygon_item import EditablePolygonItem
            
            self._clipboard_bboxes = []
            self._clipboard_polygons = []
            
            for item in selected_items:
                if isinstance(item, EditableRectItem):
                    # BBox indeksini bul
                    index = getattr(item, 'index', -1)
                    annotations = self.annotation_manager.get_annotations(image_path)
                    if 0 <= index < len(annotations.bboxes):
                        self._clipboard_bboxes.append(copy.deepcopy(annotations.bboxes[index]))
                elif isinstance(item, EditablePolygonItem):
                    # Polygon indeksini bul
                    index = getattr(item, 'index', -1)
                    annotations = self.annotation_manager.get_annotations(image_path)
                    if 0 <= index < len(annotations.polygons):
                        self._clipboard_polygons.append(copy.deepcopy(annotations.polygons[index]))
            
            total = len(self._clipboard_bboxes) + len(self._clipboard_polygons)
            if total > 0:
                self.statusbar.showMessage(f"📋 {total} seçili etiket kopyalandı")
            else:
                self.statusbar.showMessage("Seçili etiket bulunamadı")
        else:
            # Hiçbir şey seçili değilse uyarı göster
            self.statusbar.showMessage("Kopyalamak için önce bir etiket seçin")
    
    def _paste_annotations(self):
        """Kopyalanan etiketleri mevcut görsele yapıştır."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage("Yapıştırılacak görsel yok!")
            return
        
        # Clipboard kontrolü
        bboxes = getattr(self, '_clipboard_bboxes', [])
        polygons = getattr(self, '_clipboard_polygons', [])
        
        if not bboxes and not polygons:
            self.statusbar.showMessage("Yapıştırılacak etiket yok (önce Ctrl+C ile kopyalayın)")
            return
        
        # Offset değeri (%2 sağ-aşağı kaydırma)
        OFFSET = 0.02
        
        # Etiketleri ekle (offset ile)
        import copy
        for bbox in bboxes:
            new_bbox = copy.deepcopy(bbox)
            # Sağ alt tarafa kaydır
            new_bbox.x_center = min(1.0, new_bbox.x_center + OFFSET)
            new_bbox.y_center = min(1.0, new_bbox.y_center + OFFSET)
            self.annotation_manager.add_bbox(image_path, new_bbox)
        
        for polygon in polygons:
            new_polygon = copy.deepcopy(polygon)
            # Tüm noktaları kaydır
            new_polygon.points = [
                (min(1.0, x + OFFSET), min(1.0, y + OFFSET))
                for x, y in new_polygon.points
            ]
            self.annotation_manager.add_polygon(image_path, new_polygon)
        
        # Kaydet ve yenile
        self.main_window._save_current_annotations()
        self.main_window.refresh_canvas()
        self.main_window.annotation_list_widget.refresh()
        
        total = len(bboxes) + len(polygons)
        self.statusbar.showMessage(f"📋 {total} etiket yapıştırıldı")
    
    def _delete_all_annotations(self):
        """Mevcut görseldeki tüm etiketleri sil."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage("Silinecek görsel yok!")
            return
        
        annotations = self.annotation_manager.get_annotations(image_path)
        total = len(annotations.bboxes) + len(annotations.polygons)
        
        if total == 0:
            self.statusbar.showMessage("Silinecek etiket yok")
            return
        
        # Onay al
        result = QMessageBox.question(
            self, "Tümünü Sil",
            f"Bu görseldeki {total} etiketi silmek istediğinize emin misiniz?\n\n"
            "Bu işlem geri alınamaz!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            self.annotation_manager.clear_annotations(image_path)
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage(f"🗑️ {total} etiket silindi")
    
    # ─────────────────────────────────────────────────────────────────
    # Kayıt İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def _save_annotations(self):
        """Mevcut görselin annotasyonlarını labels klasörüne kaydet."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage("Kaydedilecek görsel yok!")
            return
        
        # Labels klasörünü belirle
        image_p = Path(image_path)
        parent = image_p.parent
        if parent.name.lower() == "images":
            labels_dir = parent.parent / "labels"
        else:
            labels_dir = parent / "labels"
        
        labels_dir.mkdir(parents=True, exist_ok=True)
        self.annotation_manager.save_yolo(image_path, labels_dir)
        self.statusbar.showMessage(f"✓ Kaydedildi: {image_p.stem}.txt")
        
    def _save_all_annotations(self):
        """Tüm annotasyonları labels klasörüne kaydet."""
        if not self.project.root_path:
            self.statusbar.showMessage("Kaynak klasör yok!")
            return
        
        # Labels klasörünü belirle
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
            
        # classes.txt kaydet
        self.class_manager.save_to_file(labels_dir / "classes.txt")
        self.statusbar.showMessage(f"✓ {count} dosya kaydedildi")
        
    def _export_labels(self):
        """Dışa aktarım dialogunu aç - augmentation ve split destekli."""
        if not self.project.root_path:
            self.statusbar.showMessage("Önce bir klasör açın!")
            return
        
        if not self.project.image_files:
            self.statusbar.showMessage("Export edilecek görsel yok!")
            return
        
        # Export öncesi mevcut görselin etiketlerini kaydet
        self.main_window._save_current_annotations()
        
        # Export öncesi tüm görsellerin etiketlerini diskten yükle
        self._load_all_labels_for_export()
        
        # Varsayılan çıktı klasörü
        root = self.project.root_path
        if root.name.lower() == "images":
            default_output_dir = root.parent / "export"
        else:
            default_output_dir = root / "export"
        
        # Export wizard'ı aç (v1.5)
        dialog = ExportWizard(
            class_manager=self.class_manager,
            annotation_manager=self.annotation_manager,
            image_files=self.project.image_files,
            default_output_dir=default_output_dir,
            parent=self
        )
        dialog.exec()
    
    def _load_all_labels_for_export(self):
        """Export öncesi tüm etiketleri diskten yükle."""
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
            
            # Eğer bu görsel için annotation zaten yüklüyse atla
            if key in self.annotation_manager._annotations:
                existing = self.annotation_manager._annotations[key]
                if existing.bboxes or existing.polygons:
                    continue
            
            # Labels dosyasını bul
            txt_path = labels_dir / f"{image_path.stem}.txt"
            if not txt_path.exists():
                continue
            
            # Görsel boyutlarını al
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
            
            # Etiketi yükle
            self.annotation_manager._load_from_path(key, txt_path, w, h)
        
    def _delete_selected_annotation(self):
        """Seçili etiketi sil."""
        # TODO: Implement selection
        pass
        
    def _clear_all_annotations(self):
        """Tüm etiketleri temizle."""
        image_path = self.main_window.get_current_image_path()
        if image_path:
            self.annotation_manager.clear_annotations(image_path)
            self.main_window.annotation_list_widget.refresh()
            self.statusbar.showMessage("Tüm etiketler temizlendi")
    
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
    # Dosya İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Görsel Klasörü Seç")
        if folder:
            self._load_folder(folder)
            
    def _open_file(self):
        formats = " ".join(f"*{ext}" for ext in self.SUPPORTED_FORMATS)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Görsel Dosyaları Seç", "",
            f"Görsel Dosyaları ({formats})"
        )
        if files:
            self._load_files([Path(f) for f in files])
            
    def _load_folder(self, folder_path: str):
        count = self.project.load_folder(folder_path)
        
        if count > 0:
            folder = Path(folder_path)
            
            # Labels klasörünü belirle
            if folder.name.lower() == "images":
                labels_dir = folder.parent / "labels"
                root_dir = folder.parent
            else:
                labels_dir = folder / "labels"
                root_dir = folder
            
            classes_loaded = False
            
            # 1. Önce data.yaml'dan sınıfları yüklemeyi dene
            if self._load_classes_from_yaml(root_dir):
                classes_loaded = True
            
            # 2. Yoksa classes.txt'den yükle
            if not classes_loaded:
                classes_path = folder / "classes.txt"
                if not classes_path.exists():
                    classes_path = labels_dir / "classes.txt"
                if classes_path.exists():
                    self.class_manager.load_from_file(classes_path)
                    classes_loaded = True
            
            # 3. Hiçbiri yoksa etiket dosyalarını tarayarak sınıfları keşfet
            if not classes_loaded:
                self._discover_classes_from_labels(labels_dir)
            
            self.main_window.populate_file_list(self.project.image_files)
            self.main_window.file_list.setCurrentRow(0)
            
            # 4. Tüm etiketleri preload et (istatistikler için)
            self._preload_all_annotations(labels_dir)
            
            class_count = self.class_manager.count
            self.statusbar.showMessage(f"📁 {count} görsel, {class_count} sınıf yüklendi")
        else:
            self.statusbar.showMessage("Klasörde görsel bulunamadı!")
    
    def _load_classes_from_yaml(self, root_dir: Path) -> bool:
        """data.yaml dosyasından sınıfları yükle.
        
        Returns:
            True eğer başarılı yüklendiyse
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
                        
                        # names dict veya list olabilir
                        if isinstance(names, dict):
                            for class_id, name in names.items():
                                self.class_manager.add_class_with_id(int(class_id), name)
                        elif isinstance(names, list):
                            for class_id, name in enumerate(names):
                                self.class_manager.add_class_with_id(class_id, name)
                        
                        self.statusbar.showMessage(f"✓ data.yaml'dan {len(names)} sınıf yüklendi")
                        return True
                except Exception as e:
                    print(f"data.yaml okuma hatası: {e}")
        
        return False
    
    def _discover_classes_from_labels(self, labels_dir: Path):
        """Etiket dosyalarını tarayarak kullanılan sınıf ID'lerini keşfet.
        
        Bu fonksiyon sadece classes.txt ve data.yaml yoksa çağrılır.
        """
        if not labels_dir.exists():
            return
        
        # Kullanıcıya bilgi ver
        from PySide6.QtWidgets import QApplication
        self.statusbar.showMessage("🔍 Etiket dosyaları taranıyor...")
        QApplication.processEvents()  # UI'ı güncelle
        
        discovered_ids = set()
        file_count = 0
        
        # Tüm .txt dosyalarını tara (sadece class ID'leri oku - optimize)
        txt_files = list(labels_dir.glob("*.txt"))
        total_files = len(txt_files)
        
        for txt_path in txt_files:
            if txt_path.name == "classes.txt":
                continue
            
            file_count += 1
            
            # Her 100 dosyada bir UI güncelle
            if file_count % 100 == 0:
                self.statusbar.showMessage(f"🔍 Taranıyor... {file_count}/{total_files}")
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
        
        # Keşfedilen sınıfları oluştur (her birine farklı renk)
        for class_id in sorted(discovered_ids):
            if self.class_manager.get_by_id(class_id) is None:
                self.class_manager.add_class_with_id(class_id, f"class_{class_id}")
        
        if discovered_ids:
            self.statusbar.showMessage(
                f"🔍 {len(discovered_ids)} sınıf keşfedildi (classes.txt/data.yaml bulunamadı)"
            )
    
    def _preload_all_annotations(self, labels_dir: Path):
        """Tüm etiket dosyalarını preload et (istatistikler için).
        
        Bu fonksiyon tüm .txt dosyalarını okuyarak annotation_manager'a yükler,
        böylece sınıf istatistikleri başlangıçtan itibaren doğru gösterilir.
        """
        import cv2
        import numpy as np
        from PySide6.QtWidgets import QApplication
        
        if not labels_dir.exists():
            return
        
        self.statusbar.showMessage("📊 Etiketler yükleniyor...")
        QApplication.processEvents()
        
        loaded_count = 0
        txt_files = list(labels_dir.glob("*.txt"))
        total_files = len(txt_files)
        
        for txt_path in txt_files:
            if txt_path.name == "classes.txt":
                continue
            
            loaded_count += 1
            
            # Her 50 dosyada bir UI güncelle
            if loaded_count % 50 == 0:
                self.statusbar.showMessage(f"📊 Etiketler yükleniyor... {loaded_count}/{total_files}")
                QApplication.processEvents()
            
            # Eşleşen görsel dosyasını bul
            image_path = None
            for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
                potential_path = txt_path.parent.parent / "images" / f"{txt_path.stem}{ext}"
                if potential_path.exists():
                    image_path = potential_path
                    break
                # Aynı klasörde olabilir
                potential_path = txt_path.parent / f"{txt_path.stem}{ext}"
                if potential_path.exists():
                    image_path = potential_path
                    break
            
            if not image_path:
                # Proje dosyalarından bul
                for img_file in self.project.image_files:
                    if img_file.stem == txt_path.stem:
                        image_path = img_file
                        break
            
            if not image_path:
                continue
            
            key = str(image_path)
            
            # Görsel boyutlarını al (eğer henüz yüklenmemişse varsayılan değer kullan)
            # Etiketler normalize olduğu için boyut kritik değil, varsayılan kullan
            w, h = 1920, 1080  # Varsayılan boyut (normalize koordinatlar için önemsiz)
            
            # Etiketi yükle
            self.annotation_manager._load_from_path(key, txt_path, w, h)
            
    def _load_files(self, image_files: list):
        self.project.image_files = sorted(image_files)
        self.project.current_index = 0
        self.project.root_path = image_files[0].parent if len(image_files) == 1 else None
        
        self.main_window.populate_file_list(self.project.image_files)
        self.main_window.file_list.setCurrentRow(0)
        self.statusbar.showMessage(f"🖼️ {len(image_files)} görsel yüklendi")
            
    def _next_image(self):
        # Açık popup varsa kapat
        if self._active_popup is not None:
            self._active_popup.close()
            self._active_popup = None
        
        current = self.main_window.file_list.currentRow()
        total = self.main_window.file_list.count()
        if current < total - 1:
            self.main_window.file_list.setCurrentRow(current + 1)
            
    def _prev_image(self):
        # Açık popup varsa kapat
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
        self.statusbar.showMessage(f"Zoom: %{percent}")
        
    def _on_mouse_position(self, x: int, y: int):
        percent = int(self.main_window.canvas_view.zoom_level * 100)
        current = self.main_window.file_list.currentRow() + 1
        total = self.main_window.file_list.count()
        self.statusbar.showMessage(f"[{current}/{total}] ({x}, {y}) | %{percent}")
    
    # ─────────────────────────────────────────────────────────────────
    # Yardım
    # ─────────────────────────────────────────────────────────────────
    
    def _show_about(self):
        about_text = """<h2>LocalFlow v2.0</h2>
<p><b>AI Destekli Veri Etiketleme Aracı</b></p>

<h3>🤖 AI Özellikleri (MobileSAM)</h3>
<ul>
<li><b>T</b> tuşu ile AI'ı etkinleştir</li>
<li>Tıkla → Otomatik BBox veya Polygon</li>
<li>Arka planda çalışır, UI donmaz</li>
</ul>

<h3>⌨️ Kısayollar</h3>
<table>
<tr><td><b>T</b></td><td>AI Toggle</td><td><b>W</b></td><td>BBox çiz</td></tr>
<tr><td><b>E</b></td><td>Polygon çiz</td><td><b>Q</b></td><td>Seç/Düzenle</td></tr>
<tr><td><b>A/D</b></td><td>Görsel değiştir</td><td><b>Ctrl+S</b></td><td>Kaydet</td></tr>
<tr><td><b>Ctrl+E</b></td><td>Dışa Aktar</td><td><b>Del</b></td><td>Sil</td></tr>
<tr><td><b>ESC</b></td><td>İptal</td><td></td><td></td></tr>
</table>

<h3>📦 Export Formatları</h3>
<ul>
<li><b>YOLO</b>: v5, v6, v7, v8, v9, v10, v11</li>
<li><b>COCO</b>: JSON formatı (segmentation dahil)</li>
<li><b>Pascal VOC</b>: XML formatı</li>
<li><b>Custom</b>: Özel TXT veya JSON format</li>
</ul>

<h3>💡 İpuçları</h3>
<ul>
<li>BBox/Polygon: Çift tık = sınıf değiştir</li>
<li>Q modu: Seç, taşı, köşelerden boyutlandır</li>
<li>Etiketler otomatik labels/ klasörüne kaydedilir</li>
<li>AI modunda nesneye tıkla, otomatik segmentasyon!</li>
</ul>

<p style="color: gray; font-size: 10px;">© 2026 LocalFlow</p>
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("LocalFlow Hakkında")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    def closeEvent(self, event):
        """Uygulama kapanırken kaydedilmemiş değişiklikleri kontrol et."""
        # Mevcut görselin etiketlerini kaydet
        self.main_window._save_current_annotations()
        
        # Kaydedilmemiş değişiklik var mı kontrol et
        if self.annotation_manager.is_dirty():
            reply = QMessageBox.question(
                self,
                "Kaydedilmemiş Değişiklikler",
                "Kaydedilmemiş değişiklikler var. Kaydetmeden çıkmak istiyor musunuz?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                # Tüm değişiklikleri kaydet
                self._save_all_annotations()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return
        
        event.accept()
    
    def keyPressEvent(self, event):
        """Aktif popup varsa tuş olaylarını popup'a yönlendir."""
        if self._active_popup is not None and self._active_popup.isVisible():
            key = event.key()
            # 1-9 tuşları, Enter, ESC - popup'a yönlendir
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
        """SAM worker'ı başlat."""
        # Model yolları
        resources_dir = Path(__file__).parent / "resources" / "models"
        encoder_path = resources_dir / "mobile_sam_encoder.onnx"
        decoder_path = resources_dir / "mobile_sam.onnx"
        
        # Worker oluştur
        self._sam_worker = SAMWorker(self)
        self._sam_worker.set_model_paths(str(encoder_path), str(decoder_path))
        
        # Sinyalleri bağla
        self._sam_worker.model_loaded.connect(self._on_sam_model_loaded)
        self._sam_worker.model_load_failed.connect(self._on_sam_model_failed)
        self._sam_worker.encoding_started.connect(self._on_sam_encoding_started)
        self._sam_worker.encoding_finished.connect(self._on_sam_encoding_finished)
        self._sam_worker.mask_ready.connect(self._on_sam_mask_ready)
        self._sam_worker.error_occurred.connect(self._on_sam_error)
        
        # Modelleri yükle (async)
        self.main_window.set_sam_ready(False)
        self._sam_worker.request_load_models()
    
    def _toggle_magic_pixel(self):
        """Magic Pixel toggle kısayolu (T tuşu)."""
        if not self._sam_worker.is_model_loaded:
            self.statusbar.showMessage("⏳ SAM modeli yükleniyor, lütfen bekleyin...")
            return
        
        # Magic Pixel aktifse kapat, değilse aç
        if self.main_window.sam_mode == "pixel":
            self.main_window.set_sam_mode(None)
        else:
            self.main_window.set_sam_mode("pixel")
    
    def _toggle_magic_box(self):
        """Magic Box toggle kısayolu (Y tuşu)."""
        if not self._sam_worker.is_model_loaded:
            self.statusbar.showMessage("⏳ SAM modeli yükleniyor, lütfen bekleyin...")
            return
        
        # Magic Box aktifse kapat, değilse aç
        if self.main_window.sam_mode == "box":
            self.main_window.set_sam_mode(None)
        else:
            self.main_window.set_sam_mode("box")
    
    def _on_sam_toggled(self, enabled: bool):
        """SAM toggle değiştiğinde."""
        if enabled:
            self.statusbar.showMessage("🤖 AI modu açıldı - Nesneye tıklayın")
            # Eğer görsel varsa encoding başlat
            self._encode_current_image()
        else:
            self.statusbar.showMessage("🤖 AI modu kapatıldı")
    
    def _on_sam_model_loaded(self):
        """SAM modeli yüklendiğinde."""
        self.main_window.set_sam_ready(True)
        self.statusbar.showMessage("✓ SAM modeli yüklendi - T tuşu ile AI'ı etkinleştirin")
    
    def _on_sam_model_failed(self, error: str):
        """SAM model yükleme hatası."""
        self.main_window.set_sam_ready(False)
        self.statusbar.showMessage(f"❌ SAM model hatası: {error}")
    
    def _on_sam_encoding_started(self):
        """Görsel encoding başladığında."""
        self.main_window.set_sam_status("⏳ Analiz ediliyor...")
    
    def _on_sam_encoding_finished(self):
        """Görsel encoding tamamlandığında."""
        self.main_window.set_sam_status("✓ Hazır")
        self.statusbar.showMessage("🤖 AI hazır - Nesneye tıklayın")
    
    def _on_sam_error(self, error: str):
        """SAM hatası oluştuğunda."""
        self.main_window.set_sam_status("")
        self.statusbar.showMessage(f"❌ SAM hatası: {error}")
    
    def _on_sam_click(self, x: int, y: int, mode: str):
        """Canvas'tan SAM tıklaması geldiğinde."""
        # Popup açıksa yeni tıklamayı engelle
        if self._active_popup is not None:
            return
        
        if not self._sam_worker.is_ready:
            self.statusbar.showMessage("⏳ Lütfen bekleyin, görsel analiz ediliyor...")
            return
        
        self.statusbar.showMessage(f"🔍 AI segmentasyon yapılıyor... ({x}, {y})")
        self._sam_worker.request_infer_point(x, y, mode)
    
    def _on_sam_box(self, x1: int, y1: int, x2: int, y2: int, mode: str):
        """Canvas'tan SAM bbox isteği geldiğinde (Magic Box modu).
        
        Args:
            x1, y1, x2, y2: Bbox koordinatları
            mode: 'bbox' veya 'polygon' - sonucun türü
        """
        # Popup açıksa yeni isteği engelle
        if self._active_popup is not None:
            return
        
        if not self._sam_worker.is_ready:
            self.statusbar.showMessage("⏳ Lütfen bekleyin, görsel analiz ediliyor...")
            return
        
        mode_text = "bbox→bbox" if mode == "bbox" else "bbox→polygon"
        self.statusbar.showMessage(f"🔍 AI {mode_text} segmentasyon yapılıyor...")
        self._sam_worker.request_infer_box(x1, y1, x2, y2, mode)
    
    def _on_sam_mask_ready(self, mask, mode: str, x: int, y: int):
        """SAM mask hazır olduğunda."""
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
                self.statusbar.showMessage("❌ Nesne bulunamadı")
                return
            
            x1, y1, x2, y2 = result
            
            # BBox oluştur
            self._on_bbox_created(float(x1), float(y1), float(x2), float(y2))
            self.statusbar.showMessage(f"✓ AI BBox oluşturuldu")
            
        elif mode == "polygon":
            # Mask → Polygon
            points = self._sam_worker.get_polygon_from_mask(mask)
            if points is None or len(points) < 3:
                self.statusbar.showMessage("❌ Nesne bulunamadı")
                return
            
            # Polygon oluştur - mevcut akışı kullan
            self._pending_polygon = list(points)
            
            # Önce polygon'u geçici olarak ekle (görsel feedback için)
            # Normalize et
            w, h = self.main_window.canvas_view.scene.image_size
            normalized_points = [(x / w, y / h) for x, y in points]
            
            class_id = self._last_used_class_id
            if self.class_manager.get_by_id(class_id) is None and self.class_manager.count > 0:
                class_id = self.class_manager.classes[0].id
            
            polygon = Polygon(class_id=class_id, points=normalized_points)
            self.annotation_manager.add_polygon(image_path, polygon)
            
            # Kaydet ve yenile
            self.main_window._save_current_annotations()
            self.main_window.refresh_canvas()
            self.main_window.annotation_list_widget.refresh()
            
            # Son eklenen polygon'un indeksini sakla
            annotations = self.annotation_manager.get_annotations(image_path)
            self._pending_polygon_index = len(annotations.polygons) - 1
            
            # Popup'u son noktanın yanında göster
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
                
                # Aktif popup olarak kaydet ve son düzenleme türünü belirle
                self._last_edit_type = "polygon"
                self._active_popup = popup
                
                # Select moduna geç - polygon düzenlenebilsin
                self.main_window.set_tool("select")
                
                self.statusbar.showMessage(f"✓ AI Polygon oluşturuldu - Sınıf seçin")
    
    def _encode_current_image(self):
        """Mevcut görseli SAM için encode et."""
        import cv2
        import numpy as np
        
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            return
        
        if not self._sam_worker.is_model_loaded:
            return
        
        # Görseli oku
        try:
            img_data = np.frombuffer(open(image_path, 'rb').read(), np.uint8)
            image = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
            if image is None:
                return
        except Exception as e:
            self.statusbar.showMessage(f"❌ Görsel okunamadı: {e}")
            return
        
        # Encoding başlat
        self._sam_worker.request_encode_image(image)

