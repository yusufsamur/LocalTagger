"""
LocalFlow - Ana Uygulama Sınıfı
===============================
Uygulamanın ana penceresi ve genel koordinasyonu.
"""

from PySide6.QtWidgets import QMainWindow, QDockWidget, QStatusBar
from PySide6.QtCore import Qt

from ui.main_window import MainWindow


class LocalFlowApp(QMainWindow):
    """LocalFlow ana uygulama penceresi."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalFlow - Veri Etiketleme Aracı")
        self.setMinimumSize(1200, 800)
        
        # Ana pencere içeriğini oluştur
        self._setup_ui()
        self._setup_menubar()
        self._setup_statusbar()
        
    def _setup_ui(self):
        """Kullanıcı arayüzünü kur."""
        self.main_window = MainWindow(self)
        self.setCentralWidget(self.main_window)
        
    def _setup_menubar(self):
        """Menü çubuğunu oluştur."""
        menubar = self.menuBar()
        
        # Dosya menüsü
        file_menu = menubar.addMenu("&Dosya")
        file_menu.addAction("Klasör Aç...", self._open_folder)
        file_menu.addSeparator()
        file_menu.addAction("Çıkış", self.close)
        
        # Görünüm menüsü
        view_menu = menubar.addMenu("&Görünüm")
        view_menu.addAction("Yakınlaştır", lambda: None)
        view_menu.addAction("Uzaklaştır", lambda: None)
        view_menu.addAction("Sığdır", lambda: None)
        
        # Yardım menüsü
        help_menu = menubar.addMenu("&Yardım")
        help_menu.addAction("Hakkında", self._show_about)
        
    def _setup_statusbar(self):
        """Durum çubuğunu oluştur."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Hazır - Bir klasör açın veya görsel sürükleyin")
        
    def _open_folder(self):
        """Klasör açma işlemi."""
        # TODO: Klasör seçimi ve görsel yükleme
        pass
    
    def _show_about(self):
        """Hakkında diyaloğu."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "LocalFlow Hakkında",
            "LocalFlow v0.5.0\n\n"
            "Yerel Veri Etiketleme Aracı\n"
            "Gizlilik odaklı, offline çalışan\n"
            "veri etiketleme uygulaması."
        )
