"""
LocalFlow - Ana Giriş Noktası
=============================
Uygulamayı başlatmak için bu dosyayı çalıştırın:
    python src/main.py
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app import LocalFlowApp


def main():
    """Uygulama giriş noktası."""
    # High DPI desteği
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("LocalFlow")
    app.setApplicationVersion("0.5.0")
    app.setOrganizationName("LocalFlow")
    
    # Ana pencereyi oluştur ve göster
    window = LocalFlowApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
