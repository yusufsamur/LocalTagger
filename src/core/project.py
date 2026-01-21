"""
Project Management
==================
Project opening, saving and state management.
"""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class Project:
    """Represents a labeling project."""
    
    # Project directory
    root_path: Optional[Path] = None
    
    # Image files list
    image_files: List[Path] = field(default_factory=list)
    
    # Current selected image index
    current_index: int = 0
    
    # Supported image formats
    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
    
    def load_folder(self, folder_path: str | Path) -> int:
        """
        Loads images from a folder.
        
        Args:
            folder_path: Path to image folder
            
        Returns:
            Number of found images
        """
        self.root_path = Path(folder_path)
        self.image_files = []
        self.current_index = 0
        
        if not self.root_path.exists():
            return 0
            
        # Find files in supported formats
        for file_path in sorted(self.root_path.iterdir()):
            if file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                self.image_files.append(file_path)
                
        return len(self.image_files)
    
    @property
    def current_image(self) -> Optional[Path]:
        """Returns path of currently selected image."""
        if 0 <= self.current_index < len(self.image_files):
            return self.image_files[self.current_index]
        return None
    
    @property
    def image_count(self) -> int:
        """Returns total image count."""
        return len(self.image_files)
    
    def next_image(self) -> Optional[Path]:
        """Go to next image."""
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
        return self.current_image
    
    def previous_image(self) -> Optional[Path]:
        """Go to previous image."""
        if self.current_index > 0:
            self.current_index -= 1
        return self.current_image
    
    def go_to_image(self, index: int) -> Optional[Path]:
        """Go to image at specific index."""
        if 0 <= index < len(self.image_files):
            self.current_index = index
        return self.current_image
