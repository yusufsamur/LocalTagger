"""
Language Manager
================
Multi-language support management with Qt Linguist.
"""

from pathlib import Path
from typing import List, Tuple, Optional
from PySide6.QtCore import QObject, QTranslator, QLocale, QCoreApplication, QSettings


class LanguageManager(QObject):
    """
    Application language management.
    
    Usage:
        lang_mgr = LanguageManager(app)
        lang_mgr.load_saved_language()
        
        # Change language
        lang_mgr.set_language("tr")
    """
    
    # Supported languages: (code, display_name)
    LANGUAGES = [
        ("en", "English"),
        ("tr", "Türkçe"),
    ]
    
    def __init__(self, app: QCoreApplication):
        super().__init__()
        self._app = app
        self._translator: Optional[QTranslator] = None
        self._current_language = "en"
        self._settings = QSettings("LocalTagger", "Preferences")
        
        # Find translations directory
        self._translations_dir = Path(__file__).parent.parent / "translations"
    
    @property
    def current_language(self) -> str:
        """Active language code."""
        return self._current_language
    
    @property
    def current_language_name(self) -> str:
        """Active language name."""
        for code, name in self.LANGUAGES:
            if code == self._current_language:
                return name
        return "English"
    
    def get_available_languages(self) -> List[Tuple[str, str]]:
        """Returns available languages: [(code, name), ...]"""
        return self.LANGUAGES.copy()
    
    def load_saved_language(self) -> bool:
        """
        Loads saved language preference.
        
        Returns:
            True if loaded successfully
        """
        saved_lang = self._settings.value("language", "en")
        return self.set_language(saved_lang)
    
    def set_language(self, lang_code: str) -> bool:
        """
        Changes language.
        
        Args:
            lang_code: "en" or "tr"
            
        Returns:
            True if successful
        """
        # Remove current translator
        if self._translator is not None:
            self._app.removeTranslator(self._translator)
            self._translator = None
        
        self._current_language = lang_code
        
        # English is default - no need to load translation file
        if lang_code == "en":
            self._settings.setValue("language", lang_code)
            return True
        
        # Load translation file for other languages
        self._translator = QTranslator()
        
        # Translation file paths
        qm_file = self._translations_dir / f"{lang_code}.qm"
        
        if qm_file.exists():
            if self._translator.load(str(qm_file)):
                self._app.installTranslator(self._translator)
                self._settings.setValue("language", lang_code)
                return True
        
        # Fallback: Use Qt's locale system
        locale = QLocale(lang_code)
        if self._translator.load(locale, "localtagger", "_", str(self._translations_dir)):
            self._app.installTranslator(self._translator)
            self._settings.setValue("language", lang_code)
            return True
        
        # Translation file not found - revert to English
        print(f"Warning: Translation file not found for '{lang_code}'")
        self._current_language = "en"
        return False
    
    def is_language_available(self, lang_code: str) -> bool:
        """Is language available?"""
        return any(code == lang_code for code, _ in self.LANGUAGES)
