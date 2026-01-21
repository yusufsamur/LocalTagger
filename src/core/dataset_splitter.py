"""
Dataset Splitter
================
Splits dataset into train/validation/test sets.
"""

import random
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class SplitConfig:
    """Dataset split configuration."""
    enabled: bool = False
    train_ratio: float = 0.7
    val_ratio: float = 0.2
    test_ratio: float = 0.1
    shuffle: bool = True
    seed: int = 42


class DatasetSplitter:
    """
    Splits dataset into train/validation/test sets.
    """
    
    def __init__(self, seed: int = 42):
        """
        Args:
            seed: Seed value for randomness (reproducibility)
        """
        self.seed = seed
    
    def set_seed(self, seed: int):
        """Change seed value."""
        self.seed = seed
    
    def split(
        self,
        image_files: List[Path],
        config: SplitConfig
    ) -> Dict[str, List[Path]]:
        """
        Split image files into train/val/test.
        
        Args:
            image_files: All image files
            config: Split configuration
            
        Returns:
            {'train': [...], 'val': [...], 'test': [...]}
        """
        if not config.enabled:
            return {'all': list(image_files)}
        
        # Validate ratios
        total_ratio = config.train_ratio + config.val_ratio + config.test_ratio
        if abs(total_ratio - 1.0) > 0.01:
            # Normalize
            config.train_ratio /= total_ratio
            config.val_ratio /= total_ratio
            config.test_ratio /= total_ratio
        
        # Copy and shuffle
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
        Return split statistics (for preview).
        
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
        Validate ratios.
        
        Returns:
            (is_valid, error_message)
        """
        if train < 0 or val < 0 or test < 0:
            return False, "Ratios cannot be negative"
        
        total = train + val + test
        if abs(total - 1.0) > 0.01:
            return False, f"Sum of ratios must be 1.0 (current: {total:.2f})"
        
        if train == 0:
            return False, "Train ratio cannot be 0"
        
        return True, ""
