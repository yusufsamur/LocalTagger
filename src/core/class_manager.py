"""
Class Management
================
Manages annotation classes (add, remove, assign color).
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import random


@dataclass
class LabelClass:
    """Represents an annotation class."""
    id: int
    name: str
    color: str  # Hex format: "#FF0000"
    
    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "color": self.color}
    
    @classmethod
    def from_dict(cls, data: dict) -> "LabelClass":
        return cls(id=data["id"], name=data["name"], color=data["color"])


class ClassManager:
    """
    Manages annotation classes.
    Works compatible with classes.txt file.
    """
    
    # Default color palette - distinct colors
    DEFAULT_COLORS = [
        "#FF0000",  # Red
        "#00FF00",  # Green
        "#0000FF",  # Blue
        "#FFFF00",  # Yellow
        "#FF00FF",  # Purple
        "#00FFFF",  # Cyan
        "#FF8C00",  # Orange
        "#8B00FF",  # Violet
        "#00CED1",  # Turquoise
        "#FF1493",  # Pink
        "#32CD32",  # Lime Green
        "#FFD700",  # Gold
        "#DC143C",  # Crimson
        "#4169E1",  # Royal Blue
        "#228B22",  # Forest Green
        "#FF6347",  # Tomato
        "#9400D3",  # Dark Violet
        "#20B2AA",  # Light Sea Green
        "#F08080",  # Light Coral
        "#6B8E23",  # Olive
    ]
    
    def __init__(self):
        self._classes: List[LabelClass] = []
        self._next_id: int = 0
        self._color_index: int = 0
        
    @property
    def classes(self) -> List[LabelClass]:
        """Returns all classes."""
        return self._classes.copy()
    
    @property
    def count(self) -> int:
        """Returns class count."""
        return len(self._classes)
    
    def add_class(self, name: str, color: Optional[str] = None) -> LabelClass:
        """
        Adds a new class.
        
        Args:
            name: Class name
            color: Hex color code (optional, assigned automatically)
            
        Returns:
            Created LabelClass
        """
        # Assign automatic color
        if color is None:
            color = self._get_next_color()
            
        label_class = LabelClass(
            id=self._next_id,
            name=name,
            color=color
        )
        
        self._classes.append(label_class)
        self._next_id += 1
        
        return label_class
    
    def add_class_with_id(self, class_id: int, name: str, color: Optional[str] = None) -> LabelClass:
        """
        Adds a class with a specific ID (used when loading labeled data).
        
        Args:
            class_id: Class ID
            name: Class name
            color: Hex color code (optional)
            
        Returns:
            Created LabelClass
        """
        # If ID already exists, return current
        existing = self.get_by_id(class_id)
        if existing:
            return existing
        
        # Assign automatic color
        if color is None:
            color = self._get_next_color()
            
        label_class = LabelClass(
            id=class_id,
            name=name,
            color=color
        )
        
        self._classes.append(label_class)
        
        # Update _next_id (must be larger than max ID)
        if class_id >= self._next_id:
            self._next_id = class_id + 1
        
        return label_class
    
    def remove_class(self, class_id: int) -> bool:
        """
        Removes class by ID.
        
        Returns:
            True if deletion successful
        """
        for i, cls in enumerate(self._classes):
            if cls.id == class_id:
                self._classes.pop(i)
                return True
        return False
    
    def update_class(self, class_id: int, name: Optional[str] = None, 
                     color: Optional[str] = None) -> bool:
        """
        Updates class information.
        
        Returns:
            True if update successful
        """
        label_class = self.get_by_id(class_id)
        if label_class is None:
            return False
            
        if name is not None:
            label_class.name = name
        if color is not None:
            label_class.color = color
            
        return True
    
    def get_by_id(self, class_id: int) -> Optional[LabelClass]:
        """Returns class by ID."""
        for cls in self._classes:
            if cls.id == class_id:
                return cls
        return None
    
    def get_by_name(self, name: str) -> Optional[LabelClass]:
        """Returns class by name."""
        for cls in self._classes:
            if cls.name == name:
                return cls
        return None
    
    def get_index(self, class_id: int) -> int:
        """Returns the index of the class in the list (for YOLO export)."""
        for i, cls in enumerate(self._classes):
            if cls.id == class_id:
                return i
        return -1
    
    def _get_next_color(self) -> str:
        """Returns next automatic color."""
        if self._color_index < len(self.DEFAULT_COLORS):
            color = self.DEFAULT_COLORS[self._color_index]
            self._color_index += 1
        else:
            # Generate random color
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        return color
    
    # ─────────────────────────────────────────────────────────────────
    # File Operations
    # ─────────────────────────────────────────────────────────────────
    
    def save_to_file(self, file_path: Path | str):
        """
        Saves classes in classes.txt format.
        
        Format (each line):
            class_name
            
        Separate JSON file can be used for extra metadata.
        """
        file_path = Path(file_path)
        
        # Only names (YOLO compatible classes.txt)
        with open(file_path, "w", encoding="utf-8") as f:
            for cls in self._classes:
                f.write(f"{cls.name}\n")
                
        # Save color info in separate file
        meta_path = file_path.with_suffix(".json")
        import json
        meta = {
            "classes": [cls.to_dict() for cls in self._classes],
            "next_id": self._next_id
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
    
    def load_from_file(self, file_path: Path | str):
        """
        Loads classes from classes.txt file.
        Also loads colors if .json metadata exists.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return
            
        self._classes.clear()
        self._color_index = 0
        
        # Try JSON metadata first
        meta_path = file_path.with_suffix(".json")
        if meta_path.exists():
            import json
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                for cls_data in meta.get("classes", []):
                    self._classes.append(LabelClass.from_dict(cls_data))
                self._next_id = meta.get("next_id", len(self._classes))
                # Update color index based on class count (new classes get different colors)
                self._color_index = len(self._classes)
                return
            except (json.JSONDecodeError, KeyError):
                pass  # JSON broken, load from txt
        
        # Load from classes.txt only
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    self.add_class(name)
    
    def clear(self):
        """Clears all classes."""
        self._classes.clear()
        self._next_id = 0
        self._color_index = 0
