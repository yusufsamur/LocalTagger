"""
SAM Worker Module
=================
QThread based asynchronous SAM operations.
Encoding and inference are performed in a background thread to prevent UI freezing.
"""

from pathlib import Path
from typing import Optional
import numpy as np

from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

from .sam_inferencer import SAMInferencer


class SAMWorker(QThread):
    """
    SAM operations in background thread.
    
    Signals:
        model_loaded: Models successfully loaded
        model_load_failed: Model loading error (error_message)
        encoding_started: Image encoding started
        encoding_finished: Image encoding finished
        inference_started: Inference started
        mask_ready: Mask ready (mask, mode, x, y)
        error_occurred: Error occurred (error_message)
    """
    
    # Signals
    model_loaded = Signal()
    model_load_failed = Signal(str)
    encoding_started = Signal()
    encoding_finished = Signal()
    inference_started = Signal()
    mask_ready = Signal(object, str, int, int)  # (mask, mode, x, y)
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._inferencer: Optional[SAMInferencer] = None
        self._mutex = QMutex()
        
        # Task queue
        self._task = None  # ("load", paths) | ("encode", image) | ("infer", x, y, mode)
        self._running = True
        
    def set_model_paths(self, encoder_path: str, decoder_path: str):
        """Set model paths."""
        with QMutexLocker(self._mutex):
            self._inferencer = SAMInferencer(encoder_path, decoder_path)
    
    def request_load_models(self):
        """Request model loading (async)."""
        with QMutexLocker(self._mutex):
            self._task = ("load",)
        if not self.isRunning():
            self.start()
    
    def request_encode_image(self, image: np.ndarray):
        """Request image encoding (async)."""
        with QMutexLocker(self._mutex):
            self._task = ("encode", image.copy())
        if not self.isRunning():
            self.start()
    
    def request_infer_point(self, x: int, y: int, mode: str):
        """
        Request point inference (async).
        
        Args:
            x, y: Clicked coordinates
            mode: "bbox" or "polygon"
        """
        with QMutexLocker(self._mutex):
            self._task = ("infer", x, y, mode)
        if not self.isRunning():
            self.start()
    
    def request_infer_box(self, x1: int, y1: int, x2: int, y2: int, mode: str = "polygon"):
        """
        Request box inference (async) - segmentation from bbox.
        
        Args:
            x1, y1: Top-left corner
            x2, y2: Bottom-right corner
            mode: 'bbox' or 'polygon' - result type
        """
        with QMutexLocker(self._mutex):
            self._task = ("infer_box", x1, y1, x2, y2, mode)
        if not self.isRunning():
            self.start()
    
    @property
    def is_ready(self) -> bool:
        """Are models loaded and embedding ready?"""
        with QMutexLocker(self._mutex):
            if self._inferencer is None:
                return False
            return self._inferencer.is_loaded and self._inferencer.has_embedding
    
    @property
    def is_model_loaded(self) -> bool:
        """Are models loaded?"""
        with QMutexLocker(self._mutex):
            if self._inferencer is None:
                return False
            return self._inferencer.is_loaded
    
    def run(self):
        """Thread main loop."""
        while self._running:
            task = None
            
            with QMutexLocker(self._mutex):
                if self._task is not None:
                    task = self._task
                    self._task = None
            
            if task is None:
                # Stop thread if no task
                break
            
            try:
                if task[0] == "load":
                    self._do_load_models()
                elif task[0] == "encode":
                    self._do_encode_image(task[1])
                elif task[0] == "infer":
                    self._do_infer_point(task[1], task[2], task[3])
                elif task[0] == "infer_box":
                    self._do_infer_box(task[1], task[2], task[3], task[4], task[5])
            except Exception as e:
                self.error_occurred.emit(str(e))
    
    def _do_load_models(self):
        """Model loading operation."""
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None:
                    self.model_load_failed.emit("Inferencer not set!")
                    return
                self._inferencer.load_models()
            self.model_loaded.emit()
        except Exception as e:
            self.model_load_failed.emit(str(e))
    
    def _do_encode_image(self, image: np.ndarray):
        """Image encoding operation."""
        self.encoding_started.emit()
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None or not self._inferencer.is_loaded:
                    self.error_occurred.emit("Models not loaded!")
                    return
                self._inferencer.set_image(image)
            self.encoding_finished.emit()
        except Exception as e:
            self.error_occurred.emit(f"Encoding error: {e}")
    
    def _do_infer_point(self, x: int, y: int, mode: str):
        """Point inference operation."""
        self.inference_started.emit()
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None or not self._inferencer.has_embedding:
                    self.error_occurred.emit("Image encoding not done!")
                    return
                mask = self._inferencer.infer_point(x, y)
            self.mask_ready.emit(mask, mode, x, y)
        except Exception as e:
            self.error_occurred.emit(f"Inference error: {e}")
    
    def _do_infer_box(self, x1: int, y1: int, x2: int, y2: int, mode: str):
        """Box inference operation."""
        self.inference_started.emit()
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None or not self._inferencer.has_embedding:
                    self.error_occurred.emit("Image encoding not done!")
                    return
                mask = self._inferencer.infer_box(x1, y1, x2, y2)
            # Return result as bbox or polygon based on mode
            self.mask_ready.emit(mask, mode, x1, y1)
        except Exception as e:
            self.error_occurred.emit(f"Box inference error: {e}")
    
    def get_bbox_from_mask(self, mask: np.ndarray):
        """Extract bbox from mask (can be called from main thread)."""
        with QMutexLocker(self._mutex):
            if self._inferencer is not None:
                return self._inferencer.mask_to_bbox(mask)
        return None
    
    def get_polygon_from_mask(self, mask: np.ndarray):
        """Extract polygon from mask (can be called from main thread)."""
        with QMutexLocker(self._mutex):
            if self._inferencer is not None:
                return self._inferencer.mask_to_polygon(mask)
        return None
    
    def stop(self):
        """Stop thread."""
        self._running = False
        self.wait()
    
    def clear_embedding(self):
        """Clear embedding cache."""
        with QMutexLocker(self._mutex):
            if self._inferencer is not None:
                self._inferencer.clear_embedding()
