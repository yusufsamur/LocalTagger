import sys
import os
from pathlib import Path

def get_resource_path(relative_path: str) -> Path:
    """
    Get absolute path to resource, works for dev and for PyInstaller
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # For development, use the src directory as base
        # This assumes this file is in src/utils/path_utils.py
        base_path = Path(__file__).parent.parent
        
    return Path(base_path) / relative_path
