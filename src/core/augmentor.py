"""
Augmentor Modülü
================
Görsel veri artırma (augmentation) ve resize işlemleri.
OpenCV tabanlı augmentation desteği.
"""

import cv2
import numpy as np
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
from pathlib import Path


class ResizeMode(Enum):
    """Resize mod seçenekleri."""
    STRETCH = "stretch"
    FILL_CENTER_CROP = "fill_crop"
    FIT_WITHIN = "fit_within"
    FIT_REFLECT = "fit_reflect"
    FIT_BLACK = "fit_black"
    FIT_WHITE = "fit_white"


@dataclass
class ResizeConfig:
    """Resize yapılandırması."""
    enabled: bool = False
    width: int = 640
    height: int = 640
    mode: ResizeMode = ResizeMode.STRETCH


@dataclass
class AugmentationConfig:
    """Augmentation yapılandırması - Roboflow tarzı."""
    enabled: bool = False
    multiplier: int = 3  # Toplam görsel sayısı (1 orijinal + N-1 augmented)
    
    # Parlaklık/Kontrast (sürgülü - parametre rastgele)
    brightness_enabled: bool = True
    brightness_value: float = 0.2  # -value ile +value arası rastgele
    contrast_enabled: bool = True
    contrast_value: float = 1.2  # 0.5 ile value arası rastgele
    
    # Geometrik dönüşümler
    rotation_enabled: bool = True
    rotation_value: int = 15  # -value ile +value arası rastgele derece
    
    # Flip (on/off - yüzde kontrolü)
    h_flip_enabled: bool = False
    h_flip_percent: int = 50  # Augmented görsellerin %'si
    v_flip_enabled: bool = False
    v_flip_percent: int = 50
    
    # Blur ve noise (sürgülü)
    blur_enabled: bool = False
    blur_value: int = 3
    noise_enabled: bool = False
    noise_value: float = 10.0
    
    # Renk (sürgülü)
    hue_enabled: bool = False
    hue_value: int = 10
    saturation_enabled: bool = False
    saturation_value: float = 1.2
    
    # Grayscale (on/off - yüzde kontrolü)
    grayscale_enabled: bool = False
    grayscale_percent: int = 15  # Augmented görsellerin %'si
    
    # Exposure (sürgülü)
    exposure_enabled: bool = False
    exposure_value: float = 1.5
    
    # Cutout (on/off - yüzde kontrolü)
    cutout_enabled: bool = False
    cutout_size: int = 10  # Her cutout'un boyutu (%)
    cutout_count: int = 3  # Kaç adet cutout
    cutout_apply_percent: int = 50  # Augmented görsellerin %'si
    
    # Motion Blur (sürgülü)
    motion_blur_enabled: bool = False
    motion_blur_value: int = 15
    
    # Shear (sürgülü)
    shear_enabled: bool = False
    shear_horizontal: int = 10
    shear_vertical: int = 10
    
    # Resize
    resize: ResizeConfig = field(default_factory=ResizeConfig)
    
    # Önizleme modu (deterministik)
    preview_mode: bool = False


class Augmentor:
    """
    Görsel augmentation işlemleri.
    OpenCV tabanlı veri artırma.
    """
    
    def __init__(self):
        pass
    
    # ─────────────────────────────────────────────────────────────────
    # Resize İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def resize_image(
        self, 
        image: np.ndarray, 
        config: ResizeConfig
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        if not config.enabled:
            return image, {"scale": 1.0, "offset": (0, 0), "mode": None}
        
        h, w = image.shape[:2]
        target_w, target_h = config.width, config.height
        
        if config.mode == ResizeMode.STRETCH:
            return self._resize_stretch(image, target_w, target_h)
        elif config.mode == ResizeMode.FILL_CENTER_CROP:
            return self._resize_fill_crop(image, target_w, target_h)
        elif config.mode == ResizeMode.FIT_WITHIN:
            return self._resize_fit(image, target_w, target_h, border_mode="black")
        elif config.mode == ResizeMode.FIT_REFLECT:
            return self._resize_fit(image, target_w, target_h, border_mode="reflect")
        elif config.mode == ResizeMode.FIT_BLACK:
            return self._resize_fit(image, target_w, target_h, border_mode="black")
        elif config.mode == ResizeMode.FIT_WHITE:
            return self._resize_fit(image, target_w, target_h, border_mode="white")
        
        return image, {"scale": 1.0, "offset": (0, 0), "mode": None}
    
    def _resize_stretch(self, image: np.ndarray, target_w: int, target_h: int) -> Tuple[np.ndarray, Dict]:
        h, w = image.shape[:2]
        resized = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        return resized, {"mode": "stretch", "scale_x": target_w / w, "scale_y": target_h / h, "offset": (0, 0)}
    
    def _resize_fill_crop(self, image: np.ndarray, target_w: int, target_h: int) -> Tuple[np.ndarray, Dict]:
        h, w = image.shape[:2]
        scale = max(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        start_x, start_y = (new_w - target_w) // 2, (new_h - target_h) // 2
        cropped = resized[start_y:start_y+target_h, start_x:start_x+target_w]
        return cropped, {"mode": "fill_crop", "scale": scale, "crop_offset": (start_x, start_y), "offset": (0, 0)}
    
    def _resize_fit(self, image: np.ndarray, target_w: int, target_h: int, border_mode: str) -> Tuple[np.ndarray, Dict]:
        h, w = image.shape[:2]
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        pad_x, pad_y = (target_w - new_w) // 2, (target_h - new_h) // 2
        
        if border_mode == "reflect":
            result = cv2.copyMakeBorder(resized, pad_y, target_h - new_h - pad_y, pad_x, target_w - new_w - pad_x, cv2.BORDER_REFLECT)
        elif border_mode == "white":
            result = cv2.copyMakeBorder(resized, pad_y, target_h - new_h - pad_y, pad_x, target_w - new_w - pad_x, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        else:
            result = cv2.copyMakeBorder(resized, pad_y, target_h - new_h - pad_y, pad_x, target_w - new_w - pad_x, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        
        return result, {"mode": f"fit_{border_mode}", "scale": scale, "offset": (pad_x, pad_y), "new_size": (new_w, new_h)}
    
    # ─────────────────────────────────────────────────────────────────
    # Augmentation İşlemleri
    # ─────────────────────────────────────────────────────────────────
    
    def apply_augmentation(
        self, 
        image: np.ndarray, 
        config: AugmentationConfig
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Augmentation uygula."""
        result = image.copy()
        transform = {"h_flip": False, "v_flip": False, "rotation": 0}
        
        is_preview = config.preview_mode
        
        # Parlaklık
        if config.brightness_enabled:
            if is_preview:
                brightness = config.brightness_value
            else:
                brightness = random.uniform(-abs(config.brightness_value), abs(config.brightness_value))
            result = self._adjust_brightness(result, brightness)
            transform["brightness"] = brightness
        
        # Kontrast
        if config.contrast_enabled:
            if is_preview:
                contrast = config.contrast_value
            else:
                # 1.0 ile config.contrast_value arası
                contrast = random.uniform(1.0, config.contrast_value) if config.contrast_value >= 1 else random.uniform(config.contrast_value, 1.0)
            result = self._adjust_contrast(result, contrast)
            transform["contrast"] = contrast
        
        # Hue shift
        if config.hue_enabled:
            if is_preview:
                hue_shift = config.hue_value
            else:
                # -abs(value) ile +abs(value) arası
                hue_shift = random.randint(-abs(config.hue_value), abs(config.hue_value)) if config.hue_value != 0 else 0
            result = self._adjust_hue(result, hue_shift)
            transform["hue"] = hue_shift
        
        # Saturation
        if config.saturation_enabled:
            if is_preview:
                saturation = config.saturation_value
            else:
                saturation = random.uniform(1.0, config.saturation_value) if config.saturation_value >= 1 else random.uniform(config.saturation_value, 1.0)
            result = self._adjust_saturation(result, saturation)
            transform["saturation"] = saturation
        
        # Blur
        if config.blur_enabled and config.blur_value > 0:
            if is_preview:
                blur_size = int(config.blur_value)
            else:
                blur_size = random.randint(1, max(1, int(config.blur_value)))
            # Kernel size tek sayı ve en az 1 olmalı
            blur_kernel = max(1, blur_size) * 2 + 1
            result = cv2.GaussianBlur(result, (blur_kernel, blur_kernel), 0)
            transform["blur"] = blur_kernel
        
        # Noise
        if config.noise_enabled and config.noise_value > 0:
            noise_std = config.noise_value if is_preview else random.uniform(0, config.noise_value)
            noise = np.random.normal(0, noise_std, result.shape).astype(np.float32)
            result = np.clip(result.astype(np.float32) + noise, 0, 255).astype(np.uint8)
            transform["noise"] = noise_std
        
        # Grayscale (yüzde kontrolü ile)
        if config.grayscale_enabled:
            # Önizlemede her zaman uygula, export'ta yüzde kontrolü
            apply_grayscale = is_preview or random.randint(1, 100) <= config.grayscale_percent
            if apply_grayscale:
                gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
                result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                transform["grayscale"] = True
        
        # Exposure (Gamma)
        if config.exposure_enabled:
            if is_preview:
                gamma = config.exposure_value
            else:
                gamma = random.uniform(0.5, config.exposure_value) if config.exposure_value >= 1 else random.uniform(config.exposure_value, 1.5)
            result = self._adjust_gamma(result, gamma)
            transform["exposure"] = gamma
        
        # Cutout (yüzde kontrolü ile)
        if config.cutout_enabled and config.cutout_size > 0 and config.cutout_count > 0:
            apply_cutout = is_preview or random.randint(1, 100) <= config.cutout_apply_percent
            if apply_cutout:
                result = self._apply_cutout(result, config.cutout_size, config.cutout_count)
                transform["cutout"] = {"size": config.cutout_size, "count": config.cutout_count}
        
        # Motion Blur
        if config.motion_blur_enabled and config.motion_blur_value > 0:
            if is_preview:
                kernel_size = config.motion_blur_value
            else:
                kernel_size = random.randint(5, max(5, config.motion_blur_value))
            result = self._apply_motion_blur(result, kernel_size)
            transform["motion_blur"] = kernel_size
        
        # Shear (Perspektif eğikliği)
        if config.shear_enabled:
            if is_preview:
                shear_h = config.shear_horizontal
                shear_v = config.shear_vertical
            else:
                shear_h = random.uniform(-config.shear_horizontal, config.shear_horizontal)
                shear_v = random.uniform(-config.shear_vertical, config.shear_vertical)
            result = self._apply_shear(result, shear_h, shear_v)
            transform["shear"] = {"h": shear_h, "v": shear_v}
        
        # Horizontal flip (yüzde kontrolü ile)
        if config.h_flip_enabled:
            apply_hflip = is_preview or random.randint(1, 100) <= config.h_flip_percent
            if apply_hflip:
                result = cv2.flip(result, 1)
                transform["h_flip"] = True
        
        # Vertical flip (yüzde kontrolü ile)
        if config.v_flip_enabled:
            apply_vflip = is_preview or random.randint(1, 100) <= config.v_flip_percent
            if apply_vflip:
                result = cv2.flip(result, 0)
                transform["v_flip"] = True
        
        # Rotation
        if config.rotation_enabled and config.rotation_value > 0:
            if is_preview:
                angle = config.rotation_value
            else:
                angle = random.uniform(-config.rotation_value, config.rotation_value)
            if abs(angle) > 0.5:
                result = self._rotate_image(result, angle)
                transform["rotation"] = angle
        
        return result, transform
    
    def generate_augmentations(
        self,
        image: np.ndarray,
        config: AugmentationConfig
    ) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
        """Roboflow tarzı augmentation: 1 orijinal + (multiplier-1) augmented."""
        if not config.enabled:
            return [(image, {})]
        
        results = []
        
        # 1. Orijinal görseli ekle (kopyalamaya gerek yok - değiştirilmiyor)
        results.append((image, {"original": True, "aug_index": 0}))
        
        # 2. Augmented kopyalar oluştur (multiplier - 1 adet)
        export_config = AugmentationConfig(
            enabled=config.enabled,
            multiplier=config.multiplier,
            brightness_enabled=config.brightness_enabled,
            brightness_value=config.brightness_value,
            contrast_enabled=config.contrast_enabled,
            contrast_value=config.contrast_value,
            rotation_enabled=config.rotation_enabled,
            rotation_value=config.rotation_value,
            h_flip_enabled=config.h_flip_enabled,
            h_flip_percent=config.h_flip_percent,
            v_flip_enabled=config.v_flip_enabled,
            v_flip_percent=config.v_flip_percent,
            blur_enabled=config.blur_enabled,
            blur_value=config.blur_value,
            noise_enabled=config.noise_enabled,
            noise_value=config.noise_value,
            hue_enabled=config.hue_enabled,
            hue_value=config.hue_value,
            saturation_enabled=config.saturation_enabled,
            saturation_value=config.saturation_value,
            grayscale_enabled=config.grayscale_enabled,
            grayscale_percent=config.grayscale_percent,
            exposure_enabled=config.exposure_enabled,
            exposure_value=config.exposure_value,
            cutout_enabled=config.cutout_enabled,
            cutout_size=config.cutout_size,
            cutout_count=config.cutout_count,
            cutout_apply_percent=config.cutout_apply_percent,
            motion_blur_enabled=config.motion_blur_enabled,
            motion_blur_value=config.motion_blur_value,
            shear_enabled=config.shear_enabled,
            shear_horizontal=config.shear_horizontal,
            shear_vertical=config.shear_vertical,
            resize=config.resize,
            preview_mode=False
        )
        
        for i in range(1, config.multiplier):  # 1'den başla (0 orijinal)
            aug_image, transform = self.apply_augmentation(image, export_config)
            transform["aug_index"] = i
            results.append((aug_image, transform))
        
        return results
    
    def preview(
        self, 
        image: np.ndarray, 
        config: AugmentationConfig
    ) -> np.ndarray:
        """Önizleme için deterministik augmentation."""
        if not config.enabled:
            return image
        
        # Preview mode açık - yüzde kontrolü önizlemede atlanır
        preview_config = AugmentationConfig(
            enabled=config.enabled,
            multiplier=config.multiplier,
            brightness_enabled=config.brightness_enabled,
            brightness_value=config.brightness_value,
            contrast_enabled=config.contrast_enabled,
            contrast_value=config.contrast_value,
            rotation_enabled=config.rotation_enabled,
            rotation_value=config.rotation_value,
            h_flip_enabled=config.h_flip_enabled,
            h_flip_percent=config.h_flip_percent,
            v_flip_enabled=config.v_flip_enabled,
            v_flip_percent=config.v_flip_percent,
            blur_enabled=config.blur_enabled,
            blur_value=config.blur_value,
            noise_enabled=config.noise_enabled,
            noise_value=config.noise_value,
            hue_enabled=config.hue_enabled,
            hue_value=config.hue_value,
            saturation_enabled=config.saturation_enabled,
            saturation_value=config.saturation_value,
            grayscale_enabled=config.grayscale_enabled,
            grayscale_percent=config.grayscale_percent,
            exposure_enabled=config.exposure_enabled,
            exposure_value=config.exposure_value,
            cutout_enabled=config.cutout_enabled,
            cutout_size=config.cutout_size,
            cutout_count=config.cutout_count,
            cutout_apply_percent=config.cutout_apply_percent,
            motion_blur_enabled=config.motion_blur_enabled,
            motion_blur_value=config.motion_blur_value,
            shear_enabled=config.shear_enabled,
            shear_horizontal=config.shear_horizontal,
            shear_vertical=config.shear_vertical,
            resize=config.resize,
            preview_mode=True
        )
        
        aug_image, _ = self.apply_augmentation(image, preview_config)
        return aug_image
    
    # ─────────────────────────────────────────────────────────────────
    # Yardımcı Metodlar
    # ─────────────────────────────────────────────────────────────────
    
    def _adjust_brightness(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Parlaklık ayarla. factor: -1 to 1"""
        # Daha doğru yöntem: doğrudan piksel değerlerini ayarla
        if factor >= 0:
            # Parlaklık artır
            return cv2.convertScaleAbs(image, alpha=1, beta=factor * 255)
        else:
            # Parlaklık azalt
            return cv2.convertScaleAbs(image, alpha=1 + factor, beta=0)
    
    def _adjust_contrast(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Kontrast ayarla. factor: 0.5 to 2.0"""
        # Merkez tabanlı kontrast: (pixel - 128) * factor + 128
        img_float = image.astype(np.float32)
        result = (img_float - 128) * factor + 128
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def _adjust_hue(self, image: np.ndarray, shift: int) -> np.ndarray:
        """Hue (renk tonu) kaydır."""
        if shift == 0:
            return image
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.int16)
        hsv[:, :, 0] = (hsv[:, :, 0] + shift) % 180
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    def _adjust_saturation(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Saturation ayarla."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Görseli döndür - boş alanlar siyah."""
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        # Siyah arka plan (borderValue=(0,0,0))
        return cv2.warpAffine(image, matrix, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    
    def _adjust_gamma(self, image: np.ndarray, gamma: float) -> np.ndarray:
        """Gamma (exposure) ayarla. gamma < 1: karanlık, gamma > 1: aydınlık."""
        if gamma <= 0:
            gamma = 0.1
        # gamma > 1: daha aydınlık, gamma < 1: daha karanlık
        table = np.array([np.clip(pow(i / 255.0, 1.0 / gamma) * 255.0, 0, 255) for i in range(256)]).astype("uint8")
        return cv2.LUT(image, table)
    
    def _apply_cutout(self, image: np.ndarray, size_percent: int, count: int) -> np.ndarray:
        """Birden fazla rastgele kare cutout (siyah kare) uygula."""
        h, w = image.shape[:2]
        result = image.copy()
        
        # Kare cutout boyutu (min boyutu baz al)
        cut_size = int(min(h, w) * size_percent / 100)
        
        if cut_size <= 0:
            return result
        
        # Belirtilen sayıda rastgele kare cutout ekle
        for _ in range(count):
            y1 = random.randint(0, max(0, h - cut_size))
            x1 = random.randint(0, max(0, w - cut_size))
            y2 = min(y1 + cut_size, h)
            x2 = min(x1 + cut_size, w)
            result[y1:y2, x1:x2] = 0  # Siyah kare
        
        return result
    
    def _apply_motion_blur(self, image: np.ndarray, kernel_size: int) -> np.ndarray:
        """Motion blur uygula (yatay hareket bulanıklığı)."""
        kernel_size = max(3, kernel_size)
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        # Yatay motion blur kernel
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[kernel_size // 2, :] = 1.0 / kernel_size
        
        return cv2.filter2D(image, -1, kernel)
    
    def _apply_shear(self, image: np.ndarray, shear_h: float, shear_v: float) -> np.ndarray:
        """
        Shear uygula (DigitalOcean metodolojisi).
        
        1. Görüntüyü genişlet (shear sonrası taşmayı önlemek için)
        2. Shear uygula
        3. Orijinal boyuta resize et
        
        Negatif shear için flip tekniği kullanılır.
        """
        h, w = image.shape[:2]
        
        # Shear faktörlerini hesapla
        shear_h_rad = np.tan(np.radians(shear_h))
        shear_v_rad = np.tan(np.radians(shear_v))
        
        # Negatif shear için flip tekniği
        h_flip = shear_h_rad < 0
        v_flip = shear_v_rad < 0
        
        if h_flip:
            image = cv2.flip(image, 1)  # Horizontal flip
        if v_flip:
            image = cv2.flip(image, 0)  # Vertical flip
        
        abs_shear_h = abs(shear_h_rad)
        abs_shear_v = abs(shear_v_rad)
        
        # Shear matrisi (orijin bazlı, pozitif değerlerle)
        M = np.float32([
            [1, abs_shear_h, 0],
            [abs_shear_v, 1, 0]
        ])
        
        # Yeni boyutlar (genişleme)
        nW = int(w + abs_shear_h * h)
        nH = int(h + abs_shear_v * w)
        
        # Shear uygula
        result = cv2.warpAffine(image, M, (nW, nH), 
                                borderMode=cv2.BORDER_CONSTANT, 
                                borderValue=(0, 0, 0))
        
        # Flip'leri geri al
        if h_flip:
            result = cv2.flip(result, 1)
        if v_flip:
            result = cv2.flip(result, 0)
        
        # Orijinal boyuta resize et
        result = cv2.resize(result, (w, h))
        
        return result
    
    # ─────────────────────────────────────────────────────────────────
    # BBox/Polygon Dönüşümleri
    # ─────────────────────────────────────────────────────────────────
    
    def transform_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        transform: Dict[str, Any],
        img_w: int,
        img_h: int
    ) -> Tuple[float, float, float, float]:
        """BBox'ı transform'a göre dönüştür.
        
        Dönüşüm sırası apply_augmentation ile AYNI olmalı:
        1. Shear
        2. H_flip
        3. V_flip
        4. Rotation
        """
        x_center, y_center, w, h = bbox
        
        # 1. Shear dönüşümü (varsa)
        shear = transform.get("shear")
        if shear:
            x_center, y_center, w, h = self._shear_bbox(
                x_center, y_center, w, h, shear.get("h", 0), shear.get("v", 0), img_w, img_h
            )
        
        # 2. Flip dönüşümleri
        if transform.get("h_flip"):
            x_center = 1.0 - x_center
        if transform.get("v_flip"):
            y_center = 1.0 - y_center
        
        # 3. Rotation dönüşümü (varsa)
        rotation = transform.get("rotation")
        if rotation and abs(rotation) > 0.5:
            x_center, y_center, w, h = self._rotate_bbox(
                x_center, y_center, w, h, rotation, img_w, img_h
            )
        
        # Koordinatları [0, 1] aralığında tut
        x_center = max(0, min(1, x_center))
        y_center = max(0, min(1, y_center))
        w = max(0.001, min(1, w))
        h = max(0.001, min(1, h))
        
        return (x_center, y_center, w, h)
    
    def _rotate_bbox(
        self, x_c: float, y_c: float, w: float, h: float,
        angle: float, img_w: int, img_h: int
    ) -> Tuple[float, float, float, float]:
        """BBox'ı rotation'a göre dönüştür - enclosing rectangle hesapla."""
        import math
        
        # Normalize koordinatları piksele çevir
        cx_px = x_c * img_w
        cy_px = y_c * img_h
        w_px = w * img_w
        h_px = h * img_h
        
        # 4 köşeyi hesapla
        half_w, half_h = w_px / 2, h_px / 2
        corners = [
            (cx_px - half_w, cy_px - half_h),
            (cx_px + half_w, cy_px - half_h),
            (cx_px + half_w, cy_px + half_h),
            (cx_px - half_w, cy_px + half_h)
        ]
        
        # Döndürme (görsel merkezi etrafında)
        rad = math.radians(-angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        center_x, center_y = img_w / 2, img_h / 2
        
        rotated = []
        for x, y in corners:
            x_new = (x - center_x) * cos_a - (y - center_y) * sin_a + center_x
            y_new = (x - center_x) * sin_a + (y - center_y) * cos_a + center_y
            rotated.append((x_new, y_new))
        
        # Enclosing rectangle
        xs = [p[0] for p in rotated]
        ys = [p[1] for p in rotated]
        
        # Clipping: Görüntü sınırları içine al
        min_x = max(0, min(xs))
        max_x = min(img_w, max(xs))
        min_y = max(0, min(ys))
        max_y = min(img_h, max(ys))
        
        # Validasyon
        if max_x <= min_x or max_y <= min_y:
            return (0.0, 0.0, 0.0, 0.0)
        
        new_cx = (min_x + max_x) / 2 / img_w
        new_cy = (min_y + max_y) / 2 / img_h
        new_w = (max_x - min_x) / img_w
        new_h = (max_y - min_y) / img_h
        
        return (new_cx, new_cy, new_w, new_h)
    
    def _shear_bbox(
        self, x_c: float, y_c: float, w: float, h: float,
        shear_h: float, shear_v: float, img_w: int, img_h: int
    ) -> Tuple[float, float, float, float]:
        """
        BBox'ı shear'a göre dönüştür (DigitalOcean metodolojisi).
        
        _apply_shear ile AYNI mantık:
        1. Negatif shear için koordinatları flip et
        2. Pozitif shear matrisi uygula
        3. Genişleme sonrası scale factor uygula
        4. Flip'i geri al
        5. Clip et
        """
        import numpy as np
        
        # Shear faktörlerini hesapla
        shear_h_rad = np.tan(np.radians(shear_h))
        shear_v_rad = np.tan(np.radians(shear_v))
        
        # Negatif shear için flip flag'leri
        h_flip = shear_h_rad < 0
        v_flip = shear_v_rad < 0
        
        abs_shear_h = abs(shear_h_rad)
        abs_shear_v = abs(shear_v_rad)
        
        # 1. Koordinatları piksele çevir
        cx_px = x_c * img_w
        cy_px = y_c * img_h
        w_px = w * img_w
        h_px = h * img_h
        
        # 2. 4 köşeyi hesapla (orijinal koordinatlardan)
        half_w, half_h = w_px / 2, h_px / 2
        x1 = cx_px - half_w
        y1 = cy_px - half_h
        x2 = cx_px + half_w
        y2 = cy_px + half_h
        
        # 3. Negatif shear için koordinatları flip et
        if h_flip:
            x1, x2 = img_w - x2, img_w - x1
        if v_flip:
            y1, y2 = img_h - y2, img_h - y1
        
        # 4. Shear formülü: x_new = x + shear_h * y, y_new = y + shear_v * x
        # 4 köşeyi dönüştür
        corners = [
            (x1 + abs_shear_h * y1, y1 + abs_shear_v * x1),  # top-left
            (x2 + abs_shear_h * y1, y1 + abs_shear_v * x2),  # top-right
            (x2 + abs_shear_h * y2, y2 + abs_shear_v * x2),  # bottom-right
            (x1 + abs_shear_h * y2, y2 + abs_shear_v * x1)   # bottom-left
        ]
        
        corners_x = [c[0] for c in corners]
        corners_y = [c[1] for c in corners]
        
        # 5. Enclosing box
        min_x = min(corners_x)
        max_x = max(corners_x)
        min_y = min(corners_y)
        max_y = max(corners_y)
        
        # 6. Flip'i geri al (genişlemiş boyutta - nW, nH)
        nW = img_w + abs_shear_h * img_h
        nH = img_h + abs_shear_v * img_w
        
        if h_flip:
            old_min_x = min_x
            min_x = nW - max_x
            max_x = nW - old_min_x
        if v_flip:
            old_min_y = min_y
            min_y = nH - max_y
            max_y = nH - old_min_y
        
        # 7. Scale factor uygula (resize etkisi)
        scale_x = nW / img_w
        scale_y = nH / img_h
        
        min_x = min_x / scale_x
        max_x = max_x / scale_x
        min_y = min_y / scale_y
        max_y = max_y / scale_y
        
        # 7. Clipping
        min_x = np.clip(min_x, 0, img_w)
        max_x = np.clip(max_x, 0, img_w)
        min_y = np.clip(min_y, 0, img_h)
        max_y = np.clip(max_y, 0, img_h)
        
        # 8. Yeni boyutları hesapla
        new_w_px = max_x - min_x
        new_h_px = max_y - min_y
        
        # 9. Validasyon
        if new_w_px <= 1 or new_h_px <= 1:
            return (0.0, 0.0, 0.0, 0.0)
        
        new_cx_px = min_x + new_w_px / 2
        new_cy_px = min_y + new_h_px / 2
        
        # 10. Normalize et ve döndür
        return (
            new_cx_px / img_w,
            new_cy_px / img_h,
            new_w_px / img_w,
            new_h_px / img_h
        )
    
    def transform_polygon(
        self,
        points: List[Tuple[float, float]],
        transform: Dict[str, Any],
        img_w: int,
        img_h: int
    ) -> List[Tuple[float, float]]:
        """Polygon noktalarını transform'a göre dönüştür.
        
        Dönüşüm sırası apply_augmentation ile AYNI olmalı:
        1. Shear
        2. H_flip
        3. V_flip
        4. Rotation
        """
        import math
        import numpy as np
        
        result = []
        for x, y in points:
            # 1. Shear dönüşümü
            shear = transform.get("shear")
            if shear:
                px, py = x * img_w, y * img_h
                
                shear_h_rad = np.tan(np.radians(shear.get("h", 0)))
                shear_v_rad = np.tan(np.radians(shear.get("v", 0)))
                
                # Negatif shear için flip
                h_flip_shear = shear_h_rad < 0
                v_flip_shear = shear_v_rad < 0
                
                if h_flip_shear:
                    px = img_w - px
                if v_flip_shear:
                    py = img_h - py
                
                abs_shear_h = abs(shear_h_rad)
                abs_shear_v = abs(shear_v_rad)
                
                # Shear formülü uygula
                new_px = px + abs_shear_h * py
                new_py = py + abs_shear_v * px
                
                # Scale factor (genişleme sonrası resize etkisi)
                nW = img_w + abs_shear_h * img_h
                nH = img_h + abs_shear_v * img_w
                
                new_px = new_px / (nW / img_w)
                new_py = new_py / (nH / img_h)
                
                # Flip'i geri al
                if h_flip_shear:
                    new_px = img_w - new_px
                if v_flip_shear:
                    new_py = img_h - new_py
                
                x = new_px / img_w
                y = new_py / img_h
            
            # 2. Flip dönüşümleri
            if transform.get("h_flip"):
                x = 1.0 - x
            if transform.get("v_flip"):
                y = 1.0 - y
            
            # 3. Rotation dönüşümü
            rotation = transform.get("rotation")
            if rotation and abs(rotation) > 0.5:
                # Piksele çevir
                px, py = x * img_w, y * img_h
                center_x, center_y = img_w / 2, img_h / 2
                rad = math.radians(-rotation)
                cos_a, sin_a = math.cos(rad), math.sin(rad)
                
                new_px = (px - center_x) * cos_a - (py - center_y) * sin_a + center_x
                new_py = (px - center_x) * sin_a + (py - center_y) * cos_a + center_y
                
                x = new_px / img_w
                y = new_py / img_h
            
            # Koordinatları [0, 1] aralığında tut
            x = max(0, min(1, x))
            y = max(0, min(1, y))
            
            result.append((x, y))
        return result
    
    def transform_bbox_for_resize(
        self,
        bbox: Tuple[float, float, float, float],
        resize_info: Dict[str, Any],
        orig_w: int,
        orig_h: int,
        new_w: int,
        new_h: int
    ) -> Tuple[float, float, float, float]:
        x_center, y_center, w, h = bbox
        mode = resize_info.get("mode")
        
        if mode == "stretch":
            return bbox
        elif mode == "fill_crop":
            scale = resize_info.get("scale", 1.0)
            crop_offset = resize_info.get("crop_offset", (0, 0))
            px = x_center * orig_w * scale - crop_offset[0]
            py = y_center * orig_h * scale - crop_offset[1]
            pw = w * orig_w * scale
            ph = h * orig_h * scale
            return (px / new_w, py / new_h, pw / new_w, ph / new_h)
        elif mode and mode.startswith("fit_"):
            scale = resize_info.get("scale", 1.0)
            offset = resize_info.get("offset", (0, 0))
            px = x_center * orig_w * scale + offset[0]
            py = y_center * orig_h * scale + offset[1]
            pw = w * orig_w * scale
            ph = h * orig_h * scale
            return (px / new_w, py / new_h, pw / new_w, ph / new_h)
        
        return bbox
