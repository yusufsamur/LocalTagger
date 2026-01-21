"""
LocalTagger - Main Entry Point
=============================
Run this file to start the application:
    python src/main.py
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.language_manager import LanguageManager
from app import LocalTaggerApp


# Global language manager instance
language_manager = None


def main():
    """Application entry point."""
    global language_manager
    
    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("LocalTagger")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("LocalTagger")
    
    # Initialize language manager and load saved preference
    language_manager = LanguageManager(app)
    language_manager.load_saved_language()
    
    # Create and show main window
    window = LocalTaggerApp()
    window.set_language_manager(language_manager)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

