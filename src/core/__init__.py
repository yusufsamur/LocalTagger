"""
Core modülü - İş mantığı ve veri modelleri
==========================================
"""

from .project import Project
from .image_loader import ImageLoader
from .class_manager import ClassManager, LabelClass
from .annotation_manager import AnnotationManager
from .annotation import BoundingBox, Polygon, AnnotationType, ImageAnnotations
from .exporter import (
    BaseExporter, YOLOExporter, COCOExporter, 
    CustomTXTExporter, CustomJSONExporter
)

__all__ = [
    "Project", 
    "ImageLoader",
    "ClassManager",
    "LabelClass",
    "AnnotationManager",
    "BoundingBox",
    "Polygon",
    "AnnotationType",
    "ImageAnnotations",
    "BaseExporter",
    "YOLOExporter",
    "COCOExporter",
    "CustomTXTExporter",
    "CustomJSONExporter"
]
