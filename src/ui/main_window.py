"""
Ana Pencere İçeriği
===================
Merkez canvas ve yan panelleri içeren ana widget.
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
    Uygulamanın ana içerik alanı.
    Sol panel (dosya listesi) + Merkez (canvas) + Sağ panel (sınıflar + etiketler)
    """
    
    # Sinyaller
    image_selected = Signal(str)
    tool_changed = Signal(str)
    sam_toggled = Signal(bool)  # AI toggle sinyali
    
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
        
        # Üst Toolbar
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)
        
        # Ana splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)
        
        # Sol Panel - Dosya Listesi
        self.left_panel = self._create_left_panel()
        self.splitter.addWidget(self.left_panel)
        
        # Merkez - Canvas
        self.canvas_view = AnnotationView()
        self.splitter.addWidget(self.canvas_view)
        
        # Sağ Panel - Sınıflar + Etiketler
        self.right_panel = self._create_right_panel()
        self.splitter.addWidget(self.right_panel)
        
        # Panel genişlikleri
        self.splitter.setSizes([200, 800, 220])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        
    def _create_toolbar(self) -> QToolBar:
        """Araç çubuğu oluştur."""
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
        
        # Araç butonları
        self.select_btn = QPushButton("🔲 Seç (Q)")
        self.select_btn.setCheckable(True)
        self.select_btn.clicked.connect(lambda: self._on_tool_clicked("select"))
        self.select_btn.setToolTip("BBox seçme ve düzenleme modu")
        toolbar.addWidget(self.select_btn)
        
        self.bbox_btn = QPushButton("⬜ BBox (W)")
        self.bbox_btn.setCheckable(True)
        self.bbox_btn.setChecked(True)
        self.bbox_btn.clicked.connect(lambda: self._on_tool_clicked("bbox"))
        toolbar.addWidget(self.bbox_btn)
        
        self.polygon_btn = QPushButton("◇ Polygon (E)")
        self.polygon_btn.setCheckable(True)
        self.polygon_btn.clicked.connect(lambda: self._on_tool_clicked("polygon"))
        toolbar.addWidget(self.polygon_btn)
        
        toolbar.addSeparator()
        
        # Bilgi etiketi
        self.toolbar_info = QLabel("  Araç: BBox")
        self.toolbar_info.setStyleSheet("color: #888;")
        toolbar.addWidget(self.toolbar_info)
        
        # Sağa hizalamak için spacer
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding, 
                             spacer.sizePolicy().verticalPolicy().Preferred)
        toolbar.addWidget(spacer)
        
        # Magic Pixel Butonu
        self.magic_pixel_btn = QPushButton("✨ Magic Pixel")
        self.magic_pixel_btn.setCheckable(True)
        self.magic_pixel_btn.setToolTip("Tek tıkla AI segmentasyon - Nokta tabanlı (T)")
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
        
        # Magic Box Butonu
        self.magic_box_btn = QPushButton("📦 Magic Box")
        self.magic_box_btn.setCheckable(True)
        self.magic_box_btn.setToolTip("BBox çizerek AI segmentasyon - Kutu tabanlı (Y)")
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
        """Araç butonuna tıklandığında."""
        # Tüm butonları uncheck yap
        self.select_btn.setChecked(tool == "select")
        self.bbox_btn.setChecked(tool == "bbox")
        self.polygon_btn.setChecked(tool == "polygon")
        
        self.canvas_view.set_tool(tool)
        self.tool_changed.emit(tool)
        
        tool_names = {"select": "Seç", "bbox": "BBox", "polygon": "Polygon"}
        self.toolbar_info.setText(f"  Araç: {tool_names.get(tool, tool)}")
        
    def _create_left_panel(self) -> QFrame:
        """Sol panel (dosya listesi) oluştur."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(150)
        panel.setMaximumWidth(300)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        title = QLabel("📁 Dosyalar")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        layout.addWidget(self.file_list)
        
        self.file_info_label = QLabel("Klasör açılmadı")
        self.file_info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.file_info_label)
        
        return panel
    
    def _create_right_panel(self) -> QFrame:
        """Sağ panel (etiket özeti) oluştur."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel) 
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(320)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Etiket özeti widget
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
        """Dosya listesinden bir öğe seçildiğinde."""
        item = self.file_list.item(row)
        if item:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                # Önceki görselin etiketlerini kaydet
                self._save_current_annotations()
                
                self._current_image_path = file_path
                self.image_selected.emit(file_path)
                self.canvas_view.cancel_drawing()
                
                if self.canvas_view.scene.load_image(file_path):
                    self.canvas_view.zoom_fit()
                    
                    # Görsel boyutunu annotation manager'a bildir
                    w, h = self.canvas_view.scene.image_size
                    self._annotation_manager.set_image_size(file_path, w, h)
                    
                    # Eğer YOLO txt varsa yükle (labels klasöründen)
                    self._load_annotations_from_labels(file_path, w, h)
                    
                    # Kayıtlı etiketleri çiz
                    annotations = self._annotation_manager.get_annotations(file_path)
                    self.canvas_view.draw_annotations(
                        annotations.bboxes, 
                        annotations.polygons, 
                        self._class_manager
                    )
                    
                    # Etiket listesini güncelle
                    self.annotation_list_widget.set_current_image(file_path)
                    
                    # Varsayılan sınıf rengini ayarla
                    if self._class_manager.count > 0:
                        first_class = self._class_manager.classes[0]
                        self.canvas_view.set_draw_color(first_class.color)
    
    def _get_labels_dir(self) -> 'Path':
        """Labels klasörünü döndür."""
        from pathlib import Path
        if not self._current_image_path:
            return None
        image_path = Path(self._current_image_path)
        parent = image_path.parent
        
        # images klasörü varsa yanında labels oluştur
        if parent.name.lower() == "images":
            return parent.parent / "labels"
        else:
            return parent / "labels"
    
    def _save_current_annotations(self):
        """Mevcut görselin etiketlerini labels klasörüne kaydet."""
        if not self._current_image_path:
            return
        
        labels_dir = self._get_labels_dir()
        if labels_dir:
            labels_dir.mkdir(parents=True, exist_ok=True)
            self._annotation_manager.save_yolo(self._current_image_path, labels_dir)
    
    def _load_annotations_from_labels(self, image_path: str, w: int, h: int):
        """Labels klasöründen etiketleri yükle."""
        from pathlib import Path
        image_p = Path(image_path)
        parent = image_p.parent
        
        # Önce labels klasöründen dene
        if parent.name.lower() == "images":
            labels_dir = parent.parent / "labels"
        else:
            labels_dir = parent / "labels"
        
        txt_path = labels_dir / f"{image_p.stem}.txt"
        if txt_path.exists():
            # Özel yükleme: labels klasöründen
            self._annotation_manager._load_from_path(image_path, txt_path, w, h)
            # Eksik sınıfları otomatik oluştur
            self._ensure_classes_exist(image_path)
        else:
            # Fallback: aynı klasörden yükle
            self._annotation_manager.load_yolo(image_path, w, h)
            # Eksik sınıfları otomatik oluştur
            self._ensure_classes_exist(image_path)
    
    def _ensure_classes_exist(self, image_path: str):
        """Yüklenen etiketlerdeki eksik sınıfları otomatik oluştur."""
        annotations = self._annotation_manager.get_annotations(image_path)
        
        # Tüm class_id'leri topla
        class_ids = set()
        for bbox in annotations.bboxes:
            class_ids.add(bbox.class_id)
        for polygon in annotations.polygons:
            class_ids.add(polygon.class_id)
        
        # Eksik sınıfları oluştur
        for class_id in class_ids:
            if self._class_manager.get_by_id(class_id) is None:
                # Placeholder sınıf oluştur
                self._class_manager.add_class_with_id(class_id, f"none_{class_id}")
    
    def set_draw_color(self, class_id: int):
        """Sınıf rengini ayarla."""
        label_class = self._class_manager.get_by_id(class_id)
        if label_class:
            self.canvas_view.set_draw_color(label_class.color)
            
    def _on_annotation_deleted(self, ann_type: str, index: int):
        """Etiket silindiğinde."""
        if ann_type == "bbox":
            self._annotation_manager.remove_bbox(self._current_image_path, index)
        else:
            self._annotation_manager.remove_polygon(self._current_image_path, index)
        
        # Canvas'ı yenile
        self.refresh_canvas()
        self.annotation_list_widget.refresh()
        
    def refresh_canvas(self):
        """Canvas'ı yeniden çiz (tüm etiketlerle birlikte)."""
        if not self._current_image_path:
            return
        
        # Kayıtlı etiketleri tekrar çiz
        annotations = self._annotation_manager.get_annotations(self._current_image_path)
        self.canvas_view.draw_annotations(
            annotations.bboxes, 
            annotations.polygons, 
            self._class_manager
        )
    
    def populate_file_list(self, file_paths: list):
        """Dosya listesini doldur."""
        self.file_list.clear()
        
        for path in file_paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)
            
        self.file_info_label.setText(f"{len(file_paths)} görsel")
        
    def get_current_image_path(self) -> str:
        return self._current_image_path
    
    def set_tool(self, tool: str):
        """Aracı değiştir."""
        self._on_tool_clicked(tool)
    
    # ─────────────────────────────────────────────────────────────────
    # SAM / AI Methods
    # ─────────────────────────────────────────────────────────────────
    
    def _on_magic_pixel_clicked(self):
        """Magic Pixel butonuna tıklandığında."""
        if self.magic_pixel_btn.isChecked():
            # Magic Pixel aktif - Magic Box'ı kapat
            self.magic_box_btn.setChecked(False)
            self._sam_mode = "pixel"
        else:
            # Tekrar tıklandı - kapat
            self._sam_mode = None
        
        self._update_sam_state()
    
    def _on_magic_box_clicked(self):
        """Magic Box butonuna tıklandığında."""
        if self.magic_box_btn.isChecked():
            # Magic Box aktif - Magic Pixel'i kapat
            self.magic_pixel_btn.setChecked(False)
            self._sam_mode = "box"
        else:
            # Tekrar tıklandı - kapat
            self._sam_mode = None
        
        self._update_sam_state()
    
    def _update_sam_state(self):
        """SAM durumunu canvas'a ve sinyale bildir."""
        self.canvas_view.set_sam_mode(self._sam_mode)
        self.sam_toggled.emit(self._sam_mode is not None)
    
    def set_sam_mode(self, mode: str):
        """SAM modunu ayarla (dışarıdan) - 'pixel', 'box', veya None."""
        self._sam_mode = mode
        self.magic_pixel_btn.setChecked(mode == "pixel")
        self.magic_box_btn.setChecked(mode == "box")
        self.canvas_view.set_sam_mode(mode)
    
    def set_sam_status(self, status: str):
        """SAM durum mesajını ayarla."""
        self.sam_status.setText(status)
    
    def set_sam_ready(self, ready: bool):
        """SAM hazır durumunu ayarla."""
        self.magic_pixel_btn.setEnabled(ready)
        self.magic_box_btn.setEnabled(ready)
        if not ready:
            self.sam_status.setText("Model yükleniyor...")
        else:
            self.sam_status.setText("")
    
    @property
    def sam_enabled(self) -> bool:
        """SAM etkin mi? (herhangi bir mod aktifse True)"""
        return self._sam_mode is not None
    
    @property
    def sam_mode(self) -> str:
        """Aktif SAM modu - 'pixel', 'box', veya None."""
        return self._sam_mode

