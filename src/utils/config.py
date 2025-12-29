"""
Uygulama Konfigürasyonu
=======================
Ayarların saklanması ve yönetimi.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class Config:
    """Uygulama ayarları."""
    
    last_folder: Optional[str] = None
    dark_mode: bool = True
    window_width: int = 1200
    window_height: int = 800
    
    def save(self, path: Path):
        """Ayarları dosyaya kaydet."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_folder": self.last_folder,
            "dark_mode": self.dark_mode,
            "window_width": self.window_width,
            "window_height": self.window_height,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
    @classmethod
    def load(cls, path: Path) -> "Config":
        """Ayarları dosyadan yükle."""
        config = cls()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config.last_folder = data.get("last_folder")
                config.dark_mode = data.get("dark_mode", True)
            except (json.JSONDecodeError, KeyError):
                pass
        return config
        