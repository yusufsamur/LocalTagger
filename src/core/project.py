"""
Proje Yönetimi
==============
Proje açma, kaydetme ve durum yönetimi.
"""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class Project:
    """Bir etiketleme projesini temsil eder."""
    
    # Proje dizini
    root_path: Optional[Path] = None
    
    # Görsel dosyaları listesi
    image_files: List[Path] = field(default_factory=list)
    
    # Mevcut seçili görsel indeksi
    current_index: int = 0
    
    # Desteklenen görsel formatları
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
    
    def load_folder(self, folder_path: str | Path) -> int:
        """
        Bir klasördeki görselleri yükler.
        
        Args:
            folder_path: Görsel klasörünün yolu
            
        Returns:
            Bulunan görsel sayısı
        """
        self.root_path = Path(folder_path)
        self.image_files = []
        self.current_index = 0
        
        if not self.root_path.exists():
            return 0
            
        # Desteklenen formatlardaki dosyaları bul
        for file_path in sorted(self.root_path.iterdir()):
            if file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                self.image_files.append(file_path)
                
        return len(self.image_files)
    
    @property
    def current_image(self) -> Optional[Path]:
        """Mevcut seçili görselin yolunu döndürür."""
        if 0 <= self.current_index < len(self.image_files):
            return self.image_files[self.current_index]
        return None
    
    @property
    def image_count(self) -> int:
        """Toplam görsel sayısını döndürür."""
        return len(self.image_files)
    
    def next_image(self) -> Optional[Path]:
        """Sonraki görsele geç."""
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
        return self.current_image
    
    def previous_image(self) -> Optional[Path]:
        """Önceki görsele geç."""
        if self.current_index > 0:
            self.current_index -= 1
        return self.current_image
    
    def go_to_image(self, index: int) -> Optional[Path]:
        """Belirli bir indeksteki görsele git."""
        if 0 <= index < len(self.image_files):
            self.current_index = index
        return self.current_image
