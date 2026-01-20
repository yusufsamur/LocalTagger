"""
Language Manager
================
Qt Linguist ile çoklu dil desteği yönetimi.
"""

from pathlib import Path
from typing import List, Tuple, Optional
from PySide6.QtCore import QObject, QTranslator, QLocale, QCoreApplication, QSettings


class LanguageManager(QObject):
    """
    Uygulama dil yönetimi.
    
    Kullanım:
        lang_mgr = LanguageManager(app)
        lang_mgr.load_saved_language()
        
        # Dil değiştirme
        lang_mgr.set_language("tr")
    """
    
    # Desteklenen diller: (kod, görünen_ad)
    LANGUAGES = [
        ("en", "English"),
        ("tr", "Türkçe"),
    ]
    
    def __init__(self, app: QCoreApplication):
        super().__init__()
        self._app = app
        self._translator: Optional[QTranslator] = None
        self._current_language = "en"
        self._settings = QSettings("LocalFlow", "Preferences")
        
        # Translations klasörünü bul
        self._translations_dir = Path(__file__).parent.parent / "translations"
    
    @property
    def current_language(self) -> str:
        """Aktif dil kodu."""
        return self._current_language
    
    @property
    def current_language_name(self) -> str:
        """Aktif dil adı."""
        for code, name in self.LANGUAGES:
            if code == self._current_language:
                return name
        return "English"
    
    def get_available_languages(self) -> List[Tuple[str, str]]:
        """Mevcut dilleri döndürür: [(kod, ad), ...]"""
        return self.LANGUAGES.copy()
    
    def load_saved_language(self) -> bool:
        """
        Kayıtlı dil tercihini yükler.
        
        Returns:
            True eğer başarılı yüklendiyse
        """
        saved_lang = self._settings.value("language", "en")
        return self.set_language(saved_lang)
    
    def set_language(self, lang_code: str) -> bool:
        """
        Dili değiştirir.
        
        Args:
            lang_code: "en" veya "tr"
            
        Returns:
            True eğer başarılı olduysa
        """
        # Mevcut translator'u kaldır
        if self._translator is not None:
            self._app.removeTranslator(self._translator)
            self._translator = None
        
        self._current_language = lang_code
        
        # İngilizce varsayılan - çeviri dosyası yüklemeye gerek yok
        if lang_code == "en":
            self._settings.setValue("language", lang_code)
            return True
        
        # Diğer diller için çeviri dosyasını yükle
        self._translator = QTranslator()
        
        # Çeviri dosyası yolları
        qm_file = self._translations_dir / f"{lang_code}.qm"
        
        if qm_file.exists():
            if self._translator.load(str(qm_file)):
                self._app.installTranslator(self._translator)
                self._settings.setValue("language", lang_code)
                return True
        
        # Fallback: Qt'nin locale sistemini kullan
        locale = QLocale(lang_code)
        if self._translator.load(locale, "localflow", "_", str(self._translations_dir)):
            self._app.installTranslator(self._translator)
            self._settings.setValue("language", lang_code)
            return True
        
        # Çeviri dosyası bulunamadı - İngilizce'ye geri dön
        print(f"Warning: Translation file not found for '{lang_code}'")
        self._current_language = "en"
        return False
    
    def is_language_available(self, lang_code: str) -> bool:
        """Dil mevcut mu?"""
        return any(code == lang_code for code, _ in self.LANGUAGES)
