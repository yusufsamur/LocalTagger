"""
Ana Pencere İçeriği
===================
Merkez canvas ve yan panelleri içeren ana widget.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal

from canvas import AnnotationView


class MainWindow(QWidget):
    """
    Uygulamanın ana içerik alanı.
    Sol panel (dosya listesi) + Merkez (canvas) + Sağ panel (etiketler)
    """
    
    # Sinyaller
    image_selected = Signal(str)  # Dosya yolu
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Arayüzü oluştur."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Ana splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)
        
        # Sol Panel - Dosya Listesi
        self.left_panel = self._create_left_panel()
        self.splitter.addWidget(self.left_panel)
        
        # Merkez - Canvas
        self.canvas_view = AnnotationView()
        self.splitter.addWidget(self.canvas_view)
        
        # Sağ Panel - Etiket Listesi (v0.5'te placeholder)
        self.right_panel = self._create_right_panel()
        self.splitter.addWidget(self.right_panel)
        
        # Panel genişlikleri
        self.splitter.setSizes([200, 800, 200])
        self.splitter.setStretchFactor(0, 0)  # Sol panel sabit
        self.splitter.setStretchFactor(1, 1)  # Canvas esnek
        self.splitter.setStretchFactor(2, 0)  # Sağ panel sabit
        
    def _create_left_panel(self) -> QFrame:
        """Sol panel (dosya listesi) oluştur."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setMinimumWidth(150)
        panel.setMaximumWidth(300)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Başlık
        title = QLabel("📁 Dosyalar")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Dosya listesi
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        layout.addWidget(self.file_list)
        
        # Bilgi etiketi
        self.file_info_label = QLabel("Klasör açılmadı")
        self.file_info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.file_info_label)
        
        return panel
    
    def _create_right_panel(self) -> QFrame:
        """Sağ panel (etiket listesi) oluştur."""
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel) 
        panel.setMinimumWidth(150)
        panel.setMaximumWidth(300)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Başlık
        title = QLabel("🏷️ Etiketler")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Etiket listesi (placeholder)
        self.label_list = QListWidget()
        self.label_list.setAlternatingRowColors(True)
        layout.addWidget(self.label_list)
        
        # Placeholder mesajı
        placeholder = QLabel("Etiket yok\n\nGörsel yükleyin ve\netiketlemeye başlayın")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray;")
        layout.addWidget(placeholder)
        
        return panel
    
    def _connect_signals(self):
        """Sinyalleri bağla."""
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        
    def _on_file_selected(self, row: int):
        """Dosya listesinden bir öğe seçildiğinde."""
        item = self.file_list.item(row)
        if item:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                self.image_selected.emit(file_path)
                self.canvas_view.scene.load_image(file_path)
    
    def populate_file_list(self, file_paths: list):
        """Dosya listesini doldur."""
        self.file_list.clear()
        
        for path in file_paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)
            
        self.file_info_label.setText(f"{len(file_paths)} görsel")
