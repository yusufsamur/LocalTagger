"""
SAM Worker Modülü
=================
QThread tabanlı asenkron SAM işlemleri.
UI donmasını önlemek için encoding ve inference background thread'de yapılır.
"""

from pathlib import Path
from typing import Optional
import numpy as np

from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

from .sam_inferencer import SAMInferencer


class SAMWorker(QThread):
    """
    Background thread'de SAM işlemleri.
    
    Signals:
        model_loaded: Modeller başarıyla yüklendi
        model_load_failed: Model yükleme hatası (error_message)
        encoding_started: Görsel encoding başladı
        encoding_finished: Görsel encoding tamamlandı
        inference_started: Inference başladı
        mask_ready: Maske hazır (mask, mode, x, y)
        error_occurred: Hata oluştu (error_message)
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
        """Model yollarını ayarla."""
        with QMutexLocker(self._mutex):
            self._inferencer = SAMInferencer(encoder_path, decoder_path)
    
    def request_load_models(self):
        """Model yükleme isteği (async)."""
        with QMutexLocker(self._mutex):
            self._task = ("load",)
        if not self.isRunning():
            self.start()
    
    def request_encode_image(self, image: np.ndarray):
        """Görsel encoding isteği (async)."""
        with QMutexLocker(self._mutex):
            self._task = ("encode", image.copy())
        if not self.isRunning():
            self.start()
    
    def request_infer_point(self, x: int, y: int, mode: str):
        """
        Point inference isteği (async).
        
        Args:
            x, y: Tıklanan koordinatlar
            mode: "bbox" veya "polygon"
        """
        with QMutexLocker(self._mutex):
            self._task = ("infer", x, y, mode)
        if not self.isRunning():
            self.start()
    
    def request_infer_box(self, x1: int, y1: int, x2: int, y2: int, mode: str = "polygon"):
        """
        Box inference isteği (async) - bbox'tan segmentasyon.
        
        Args:
            x1, y1: Sol üst köşe
            x2, y2: Sağ alt köşe
            mode: 'bbox' veya 'polygon' - sonuç türü
        """
        with QMutexLocker(self._mutex):
            self._task = ("infer_box", x1, y1, x2, y2, mode)
        if not self.isRunning():
            self.start()
    
    @property
    def is_ready(self) -> bool:
        """Model yüklü ve embedding hazır mı?"""
        with QMutexLocker(self._mutex):
            if self._inferencer is None:
                return False
            return self._inferencer.is_loaded and self._inferencer.has_embedding
    
    @property
    def is_model_loaded(self) -> bool:
        """Sadece model yüklü mü?"""
        with QMutexLocker(self._mutex):
            if self._inferencer is None:
                return False
            return self._inferencer.is_loaded
    
    def run(self):
        """Thread ana döngüsü."""
        while self._running:
            task = None
            
            with QMutexLocker(self._mutex):
                if self._task is not None:
                    task = self._task
                    self._task = None
            
            if task is None:
                # Görev yoksa thread'i durdur
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
        """Model yükleme işlemi."""
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None:
                    self.model_load_failed.emit("Inferencer ayarlanmadı!")
                    return
                self._inferencer.load_models()
            self.model_loaded.emit()
        except Exception as e:
            self.model_load_failed.emit(str(e))
    
    def _do_encode_image(self, image: np.ndarray):
        """Görsel encoding işlemi."""
        self.encoding_started.emit()
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None or not self._inferencer.is_loaded:
                    self.error_occurred.emit("Model yüklenmedi!")
                    return
                self._inferencer.set_image(image)
            self.encoding_finished.emit()
        except Exception as e:
            self.error_occurred.emit(f"Encoding hatası: {e}")
    
    def _do_infer_point(self, x: int, y: int, mode: str):
        """Point inference işlemi."""
        self.inference_started.emit()
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None or not self._inferencer.has_embedding:
                    self.error_occurred.emit("Görsel encoding yapılmadı!")
                    return
                mask = self._inferencer.infer_point(x, y)
            self.mask_ready.emit(mask, mode, x, y)
        except Exception as e:
            self.error_occurred.emit(f"Inference hatası: {e}")
    
    def _do_infer_box(self, x1: int, y1: int, x2: int, y2: int, mode: str):
        """Box inference işlemi."""
        self.inference_started.emit()
        try:
            with QMutexLocker(self._mutex):
                if self._inferencer is None or not self._inferencer.has_embedding:
                    self.error_occurred.emit("Görsel encoding yapılmadı!")
                    return
                mask = self._inferencer.infer_box(x1, y1, x2, y2)
            # mode'a göre bbox veya polygon olarak sonuç dön
            self.mask_ready.emit(mask, mode, x1, y1)
        except Exception as e:
            self.error_occurred.emit(f"Box inference hatası: {e}")
    
    def get_bbox_from_mask(self, mask: np.ndarray):
        """Maske'den bbox çıkar (main thread'den çağrılabilir)."""
        with QMutexLocker(self._mutex):
            if self._inferencer is not None:
                return self._inferencer.mask_to_bbox(mask)
        return None
    
    def get_polygon_from_mask(self, mask: np.ndarray):
        """Maske'den polygon çıkar (main thread'den çağrılabilir)."""
        with QMutexLocker(self._mutex):
            if self._inferencer is not None:
                return self._inferencer.mask_to_polygon(mask)
        return None
    
    def stop(self):
        """Thread'i durdur."""
        self._running = False
        self.wait()
    
    def clear_embedding(self):
        """Embedding cache'i temizle."""
        with QMutexLocker(self._mutex):
            if self._inferencer is not None:
                self._inferencer.clear_embedding()
