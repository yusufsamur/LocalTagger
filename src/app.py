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
from ui.widgets.class_selector_popup import ClassSelectorPopup
from core.project import Project
from core.class_manager import ClassManager
from core.annotation_manager import AnnotationManager
from core.annotation import BoundingBox, Polygon


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
        file_menu.addAction("YOLO Olarak Dışa Aktar...", self._export_yolo, QKeySequence("Ctrl+E"))
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
        
        self.main_window.tool_changed.connect(self._on_tool_changed)
    
    def _on_annotation_clicked(self):
        """Bir annotasyona tıklandığında - select moduna geç."""
        self.main_window.set_tool("select")
    
    def _on_popup_closed(self):
        """Popup kapandığında - son düzenlenen türüne göre çizim moduna dön."""
        self._active_popup = None
        # Son düzenlenen türüne göre mod değiştir
        last_type = getattr(self, '_last_edit_type', 'bbox')
        self.main_window.set_tool(last_type)
        
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
        
        # Son eklenen bbox'ın indeksini sakla (sınıf değişikliği için)
        annotations = self.annotation_manager.get_annotations(image_path)
        self._pending_bbox_index = len(annotations.bboxes) - 1
        
        # Popup'u bbox'ın sağ üst köşesinde göster
        canvas = self.main_window.canvas_view
        scene_pos = canvas.mapFromScene(x2, y1)
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
            popup.show_at(global_pos)
    
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
        
        if self.annotation_manager.remove_bbox(image_path, index):
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
        
        if self.annotation_manager.remove_polygon(image_path, index):
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
    
    # ─────────────────────────────────────────────────────────────────
    # Kayıt İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def _save_annotations(self):
        """Mevcut görselin annotasyonlarını kaydet."""
        image_path = self.main_window.get_current_image_path()
        if not image_path:
            self.statusbar.showMessage("Kaydedilecek görsel yok!")
            return
            
        output_dir = Path(image_path).parent
        self.annotation_manager.save_yolo(image_path, output_dir)
        self.statusbar.showMessage(f"✓ Kaydedildi: {Path(image_path).stem}.txt")
        
    def _save_all_annotations(self):
        """Tüm annotasyonları kaydet."""
        if not self.project.root_path:
            self.statusbar.showMessage("Kaynak klasör yok!")
            return
            
        output_dir = self.project.root_path
        count = 0
        for image_path in self.project.image_files:
            self.annotation_manager.save_yolo(str(image_path), output_dir)
            count += 1
            
        # classes.txt kaydet
        self.class_manager.save_to_file(output_dir / "classes.txt")
        self.statusbar.showMessage(f"✓ {count} dosya kaydedildi")
        
    def _export_yolo(self):
        """YOLO formatında dışa aktar - labels klasörüne otomatik kaydet."""
        if not self.project.root_path:
            self.statusbar.showMessage("Önce bir klasör açın!")
            return
        
        if not self.project.image_files:
            self.statusbar.showMessage("Export edilecek görsel yok!")
            return
            
        # labels klasörünü belirle
        root = self.project.root_path
        if root.name.lower() == "images":
            # images klasörünün yanında labels oluştur
            labels_dir = root.parent / "labels"
        else:
            # Aynı klasörde labels alt klasörü oluştur
            labels_dir = root / "labels"
        
        # Klasörü oluştur
        labels_dir.mkdir(parents=True, exist_ok=True)
        
        count = 0
        for image_path in self.project.image_files:
            self.annotation_manager.save_yolo(str(image_path), labels_dir)
            count += 1
            
        self.class_manager.save_to_file(labels_dir / "classes.txt")
        
        QMessageBox.information(
            self, "Dışa Aktarım Tamamlandı",
            f"✓ {count} görsel YOLO formatında dışa aktarıldı.\n\n"
            f"Konum: {labels_dir}"
        )
        
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
            # classes.txt varsa yükle
            classes_path = Path(folder_path) / "classes.txt"
            if classes_path.exists():
                self.class_manager.load_from_file(classes_path)
                self.main_window.class_list_widget.refresh()
                
            self.main_window.populate_file_list(self.project.image_files)
            self.main_window.file_list.setCurrentRow(0)
            self.statusbar.showMessage(f"📁 {count} görsel yüklendi")
        else:
            self.statusbar.showMessage("Klasörde görsel bulunamadı!")
            
    def _load_files(self, image_files: list):
        self.project.image_files = sorted(image_files)
        self.project.current_index = 0
        self.project.root_path = image_files[0].parent if len(image_files) == 1 else None
        
        self.main_window.populate_file_list(self.project.image_files)
        self.main_window.file_list.setCurrentRow(0)
        self.statusbar.showMessage(f"🖼️ {len(image_files)} görsel yüklendi")
            
    def _next_image(self):
        current = self.main_window.file_list.currentRow()
        total = self.main_window.file_list.count()
        if current < total - 1:
            self.main_window.file_list.setCurrentRow(current + 1)
            
    def _prev_image(self):
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
        about_text = """<h2>LocalFlow v2.2</h2>
<p><b>YOLO Etiketleme Aracı</b></p>

<h3>⌨️ Kısayollar</h3>
<table>
<tr><td><b>W</b></td><td>BBox çiz</td><td><b>E</b></td><td>Polygon çiz</td></tr>
<tr><td><b>Q</b></td><td>Düzenle</td><td><b>A/D</b></td><td>Görsel değiştir</td></tr>
<tr><td><b>1-9</b></td><td>Sınıf seç</td><td><b>Del</b></td><td>Sil</td></tr>
<tr><td><b>Enter</b></td><td>Onayla</td><td><b>ESC</b></td><td>İptal</td></tr>
</table>

<h3>💡 İpuçları</h3>
<ul>
<li>BBox: Çift tık = sınıf değiştir</li>
<li>Q modu: Seç, taşı, boyutlandır</li>
<li>Popup sürüklenebilir</li>
<li>Otomatik kayıt aktif</li>
</ul>

<p style="color: gray; font-size: 10px;">© 2025 LocalFlow</p>
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("LocalFlow Hakkında")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

