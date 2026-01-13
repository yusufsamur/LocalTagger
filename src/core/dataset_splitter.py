"""
Dataset Splitter
================
Veri setini train/validation/test'e böler.
"""

import random
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class SplitConfig:
    """Dataset bölme yapılandırması."""
    enabled: bool = False
    train_ratio: float = 0.7
    val_ratio: float = 0.2
    test_ratio: float = 0.1
    shuffle: bool = True
    seed: int = 42


class DatasetSplitter:
    """
    Veri setini train/validation/test'e böler.
    """
    
    def __init__(self, seed: int = 42):
        """
        Args:
            seed: Rastgelelik için seed değeri (tekrarlanabilirlik)
        """
        self.seed = seed
    
    def set_seed(self, seed: int):
        """Seed değerini değiştir."""
        self.seed = seed
    
    def split(
        self,
        image_files: List[Path],
        config: SplitConfig
    ) -> Dict[str, List[Path]]:
        """
        Görsel dosyalarını train/val/test'e böl.
        
        Args:
            image_files: Tüm görsel dosyaları
            config: Bölme yapılandırması
            
        Returns:
            {'train': [...], 'val': [...], 'test': [...]}
        """
        if not config.enabled:
            return {'all': list(image_files)}
        
        # Oranları doğrula
        total_ratio = config.train_ratio + config.val_ratio + config.test_ratio
        if abs(total_ratio - 1.0) > 0.01:
            # Normalize et
            config.train_ratio /= total_ratio
            config.val_ratio /= total_ratio
            config.test_ratio /= total_ratio
        
        # Kopyala ve karıştır
        files = list(image_files)
        if config.shuffle:
            random.seed(config.seed if config.seed else self.seed)
            random.shuffle(files)
        
        total = len(files)
        train_count = int(total * config.train_ratio)
        val_count = int(total * config.val_ratio)
        # test_count = kalan
        
        train_files = files[:train_count]
        val_files = files[train_count:train_count + val_count]
        test_files = files[train_count + val_count:]
        
        result = {}
        if train_files:
            result['train'] = train_files
        if val_files:
            result['val'] = val_files
        if test_files:
            result['test'] = test_files
        
        return result
    
    def get_split_info(
        self,
        total_count: int,
        config: SplitConfig
    ) -> Dict[str, int]:
        """
        Bölme istatistiklerini döndür (önizleme için).
        
        Returns:
            {'train': count, 'val': count, 'test': count}
        """
        if not config.enabled:
            return {'all': total_count}
        
        train_count = int(total_count * config.train_ratio)
        val_count = int(total_count * config.val_ratio)
        test_count = total_count - train_count - val_count
        
        return {
            'train': train_count,
            'val': val_count,
            'test': test_count
        }
    
    def validate_ratios(
        self, 
        train: float, 
        val: float, 
        test: float
    ) -> Tuple[bool, str]:
        """
        Oranları doğrula.
        
        Returns:
            (is_valid, error_message)
        """
        if train < 0 or val < 0 or test < 0:
            return False, "Oranlar negatif olamaz"
        
        total = train + val + test
        if abs(total - 1.0) > 0.01:
            return False, f"Oranların toplamı 1.0 olmalı (şu an: {total:.2f})"
        
        if train == 0:
            return False, "Train oranı 0 olamaz"
        
        return True, ""
