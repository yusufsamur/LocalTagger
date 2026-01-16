"""
SAM Inferencer Modülü
=====================
MobileSAM ONNX modelleri ile segmentasyon.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional


class SAMInferencer:
    """
    MobileSAM ONNX modelleri ile point-to-mask segmentasyon.
    
    Kullanım:
        inferencer = SAMInferencer(encoder_path, decoder_path)
        inferencer.load_models()
        inferencer.set_image(image)
        mask = inferencer.infer_point(x, y)
        bbox = inferencer.mask_to_bbox(mask)
        polygon = inferencer.mask_to_polygon(mask)
    """
    
    INPUT_SIZE = 1024
    
    def __init__(self, encoder_path: str, decoder_path: str):
        """
        Args:
            encoder_path: Encoder ONNX model yolu
            decoder_path: Decoder ONNX model yolu
        """
        self.encoder_path = Path(encoder_path)
        self.decoder_path = Path(decoder_path)
        
        self._encoder_session = None
        self._decoder_session = None
        self._image_embedding = None
        self._original_size = None  # (height, width)
        self._scale_factor = 1.0
        
    @property
    def is_loaded(self) -> bool:
        """Modeller yüklü mü?"""
        return self._encoder_session is not None and self._decoder_session is not None
    
    @property
    def has_embedding(self) -> bool:
        """Görsel embedding'i hesaplandı mı?"""
        return self._image_embedding is not None
    
    def load_models(self):
        """ONNX model session'larını başlat."""
        import onnxruntime
        
        if not self.encoder_path.exists():
            raise FileNotFoundError(f"Encoder model bulunamadı: {self.encoder_path}")
        if not self.decoder_path.exists():
            raise FileNotFoundError(f"Decoder model bulunamadı: {self.decoder_path}")
        
        providers = ['CPUExecutionProvider']
        self._encoder_session = onnxruntime.InferenceSession(
            str(self.encoder_path), providers=providers
        )
        self._decoder_session = onnxruntime.InferenceSession(
            str(self.decoder_path), providers=providers
        )
    
    def set_image(self, image: np.ndarray):
        """
        Görsel için embedding hesapla ve cache'le.
        
        Args:
            image: BGR formatında numpy array (OpenCV)
        """
        if not self.is_loaded:
            raise RuntimeError("Modeller yüklenmedi! Önce load_models() çağırın.")
        
        self._original_size = (image.shape[0], image.shape[1])  # (H, W)
        
        # Preprocess
        input_tensor = self._preprocess_image(image)
        
        # Encoder çalıştır
        inputs = {self._encoder_session.get_inputs()[0].name: input_tensor}
        outputs = self._encoder_session.run(None, inputs)
        self._image_embedding = outputs[0]
    
    def infer_point(self, x: int, y: int) -> np.ndarray:
        """
        Tıklanan noktadan maske üret.
        
        Args:
            x: Orijinal görsel üzerinde x koordinatı (piksel)
            y: Orijinal görsel üzerinde y koordinatı (piksel)
            
        Returns:
            Binary maske (uint8, 0 veya 1), orijinal görsel boyutunda
        """
        if not self.has_embedding:
            raise RuntimeError("Görsel ayarlanmadı! Önce set_image() çağırın.")
        
        # Koordinatları scale et
        onnx_x = x * self._scale_factor
        onnx_y = y * self._scale_factor
        
        # Decoder inputları hazırla
        input_point = np.array([[onnx_x, onnx_y]], dtype=np.float32)
        input_label = np.array([1], dtype=np.float32)  # 1 = foreground
        
        # 5 nokta gerekli (1 gerçek + 4 dummy)
        onnx_coord = np.concatenate([
            input_point, 
            np.array([[0.0, 0.0]] * 4, dtype=np.float32)
        ], axis=0)[None, :, :]
        
        onnx_label = np.concatenate([
            input_label, 
            np.array([-1] * 4, dtype=np.float32)
        ], axis=0)[None, :]
        
        mask_input = np.zeros((1, 1, 256, 256), dtype=np.float32)
        has_mask_input = np.zeros(1, dtype=np.float32)
        orig_size = np.array(self._original_size, dtype=np.float32)
        
        ort_inputs = {
            "image_embeddings": self._image_embedding.astype(np.float32),
            "point_coords": onnx_coord.astype(np.float32),
            "point_labels": onnx_label.astype(np.float32),
            "mask_input": mask_input.astype(np.float32),
            "has_mask_input": has_mask_input.astype(np.float32),
            "orig_im_size": orig_size.astype(np.float32)
        }
        
        masks, _, _ = self._decoder_session.run(None, ort_inputs)
        
        # Binary maske oluştur
        final_mask = masks[0, 0, :, :]
        final_mask = (final_mask > 0).astype(np.uint8)
        
        # Orijinal boyuta resize et
        if final_mask.shape[:2] != self._original_size:
            final_mask = cv2.resize(
                final_mask, 
                (self._original_size[1], self._original_size[0]),  # (W, H)
                interpolation=cv2.INTER_NEAREST
            )
        
        return final_mask
    
    def mask_to_bbox(self, mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Maske'den bounding box çıkar.
        
        Args:
            mask: Binary maske
            
        Returns:
            (x1, y1, x2, y2) veya None (maske boşsa)
        """
        # Mask'taki beyaz piksellerin konumlarını bul
        coords = np.where(mask > 0)
        if len(coords[0]) == 0:
            return None
        
        y1, y2 = coords[0].min(), coords[0].max()
        x1, x2 = coords[1].min(), coords[1].max()
        
        return (int(x1), int(y1), int(x2), int(y2))
    
    def mask_to_polygon(self, mask: np.ndarray, simplify_epsilon: float = 2.0) -> Optional[List[Tuple[int, int]]]:
        """
        Maske'den polygon noktaları çıkar.
        
        Args:
            mask: Binary maske
            simplify_epsilon: Douglas-Peucker simplification epsilon değeri
            
        Returns:
            [(x1, y1), (x2, y2), ...] veya None (maske boşsa)
        """
        # Kontürü bul
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return None
        
        # En büyük kontürü al
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Kontürü sadeleştir
        epsilon = simplify_epsilon
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        # Minimum 3 nokta olmalı
        if len(approx) < 3:
            return None
        
        # Noktaları listeye dönüştür
        points = [(int(p[0][0]), int(p[0][1])) for p in approx]
        
        return points
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Görseli encoder için hazırla.
        
        Args:
            image: BGR formatında numpy array
            
        Returns:
            (1, 3, 1024, 1024) float32 tensor
        """
        old_h, old_w = image.shape[:2]
        scale = self.INPUT_SIZE * 1.0 / max(old_h, old_w)
        self._scale_factor = scale
        
        new_h, new_w = int(old_h * scale), int(old_w * scale)
        resized_image = cv2.resize(image, (new_w, new_h))
        
        # ImageNet normalization
        pixel_mean = np.array([123.675, 116.28, 103.53], dtype=np.float32).reshape(1, 1, 3)
        pixel_std = np.array([58.395, 57.12, 57.375], dtype=np.float32).reshape(1, 1, 3)
        
        x = (resized_image.astype(np.float32) - pixel_mean) / pixel_std
        
        # Padding (sağa ve alta)
        pad_h = self.INPUT_SIZE - new_h
        pad_w = self.INPUT_SIZE - new_w
        x = np.pad(x, ((0, pad_h), (0, pad_w), (0, 0)), mode='constant', constant_values=0)
        
        # (H, W, C) -> (1, C, H, W)
        x = x.transpose(2, 0, 1)[None, :, :, :].astype(np.float32)
        
        return x
    
    def clear_embedding(self):
        """Embedding cache'i temizle."""
        self._image_embedding = None
        self._original_size = None
        self._scale_factor = 1.0
