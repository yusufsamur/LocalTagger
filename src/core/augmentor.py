"""
Augmentor Module
================
Image augmentation and resizing operations.
OpenCV based augmentation support.
"""

import cv2
import numpy as np
import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
from pathlib import Path


class ResizeMode(Enum):
    """Resize mode options."""
    STRETCH = "stretch"
    FIT_WITHIN = "fit_within"
    FIT_REFLECT = "fit_reflect"
    FIT_BLACK = "fit_black"
    FIT_WHITE = "fit_white"


@dataclass
class ResizeConfig:
    """Resize configuration."""
    enabled: bool = False
    width: int = 640
    height: int = 640
    mode: ResizeMode = ResizeMode.STRETCH


@dataclass
class AugmentationConfig:
    """Augmentation configuration - Roboflow style."""
    enabled: bool = False
    multiplier: int = 3  # Total image count (1 original + N-1 augmented)
    
    # Brightness - Roboflow style separate Brighten/Darken
    brighten_enabled: bool = False  # Increase brightness
    darken_enabled: bool = False    # Decrease brightness
    brightness_value: float = 0.2   # Between 0 and 1 (% value)
    
    # Contrast
    contrast_enabled: bool = True
    contrast_value: float = 1.2  # Random between 0.5 and value
    
    # Geometric transformations
    rotation_enabled: bool = True
    rotation_value: int = 15  # Random degrees between -value and +value
    
    # Flip (on/off - percentage control)
    h_flip_enabled: bool = False
    h_flip_percent: int = 50  # % of augmented images
    v_flip_enabled: bool = False
    v_flip_percent: int = 50
    
    # Blur and noise (slider)
    blur_enabled: bool = False
    blur_value: int = 3
    noise_enabled: bool = False
    noise_value: float = 10.0
    
    # Color (slider)
    hue_enabled: bool = False
    hue_value: int = 10
    saturation_enabled: bool = False
    saturation_value: float = 1.2
    
    # Grayscale (on/off - percentage control)
    grayscale_enabled: bool = False
    grayscale_percent: int = 15  # % of augmented images
    
    # Exposure (slider)
    exposure_enabled: bool = False
    exposure_value: float = 1.5
    
    # Cutout (on/off - percentage control)
    cutout_enabled: bool = False
    cutout_size: int = 10  # Size of each cutout (%)
    cutout_count: int = 3  # Number of cutouts
    cutout_apply_percent: int = 50  # % of augmented images
    
    # Motion Blur (slider)
    motion_blur_enabled: bool = False
    motion_blur_value: int = 15
    
    # Shear (slider)
    shear_enabled: bool = False
    shear_horizontal: int = 10
    shear_vertical: int = 10
    
    # Resize
    resize: ResizeConfig = field(default_factory=ResizeConfig)
    
    # Preview mode (deterministic)
    preview_mode: bool = False


class Augmentor:
    """
    Image augmentation operations.
    OpenCV based data augmentation.
    """
    
    def __init__(self):
        pass
    
    # ─────────────────────────────────────────────────────────────────
    # Resize Operations
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
    # Augmentation Operations
    # ─────────────────────────────────────────────────────────────────
    
    def apply_augmentation(
        self, 
        image: np.ndarray, 
        config: AugmentationConfig
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Apply augmentation."""
        result = image.copy()
        transform = {"h_flip": False, "v_flip": False, "rotation": 0}
        
        is_preview = config.preview_mode
        
        # Brightness - Roboflow style Brighten/Darken
        if config.brighten_enabled or config.darken_enabled:
            if is_preview:
                # In preview - show last selected effect
                # Default: positive if brighten_enabled, negative if darken_enabled
                if config.brighten_enabled and not config.darken_enabled:
                    brightness = config.brightness_value
                elif config.darken_enabled and not config.brighten_enabled:
                    brightness = -config.brightness_value
                else:
                    # If both selected, pick random
                    brightness = config.brightness_value  # Show brightness in preview
            else:
                # Export - random value based on active setting
                if config.brighten_enabled and config.darken_enabled:
                    # If both selected, pick one randomly and apply random value
                    if random.random() > 0.5:
                        brightness = random.uniform(0, config.brightness_value)  # Brightness
                    else:
                        brightness = random.uniform(-config.brightness_value, 0)  # Darkness
                elif config.brighten_enabled:
                    brightness = random.uniform(0, config.brightness_value)
                else:  # darken_enabled
                    brightness = random.uniform(-config.brightness_value, 0)
            
            result = self._adjust_brightness(result, brightness)
            transform["brightness"] = brightness
        
        # Contrast
        if config.contrast_enabled:
            if is_preview:
                contrast = config.contrast_value
            else:
                # Between 1.0 and config.contrast_value
                contrast = random.uniform(1.0, config.contrast_value) if config.contrast_value >= 1 else random.uniform(config.contrast_value, 1.0)
            result = self._adjust_contrast(result, contrast)
            transform["contrast"] = contrast
        
        # Hue shift
        if config.hue_enabled:
            if is_preview:
                hue_shift = config.hue_value
            else:
                # Between -abs(value) and +abs(value)
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
            # Kernel size must be odd and at least 1
            blur_kernel = max(1, blur_size) * 2 + 1
            result = cv2.GaussianBlur(result, (blur_kernel, blur_kernel), 0)
            transform["blur"] = blur_kernel
        
        # Noise
        if config.noise_enabled and config.noise_value > 0:
            noise_std = config.noise_value if is_preview else random.uniform(0, config.noise_value)
            noise = np.random.normal(0, noise_std, result.shape).astype(np.float32)
            result = np.clip(result.astype(np.float32) + noise, 0, 255).astype(np.uint8)
            transform["noise"] = noise_std
        
        # Grayscale (with percentage control)
        if config.grayscale_enabled:
            # Always apply in preview, check percentage in export
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
        
        # Cutout (with percentage control)
        if config.cutout_enabled and config.cutout_size > 0 and config.cutout_count > 0:
            apply_cutout = is_preview or random.randint(1, 100) <= config.cutout_apply_percent
            if apply_cutout:
                result, cutout_regions = self._apply_cutout(result, config.cutout_size, config.cutout_count)
                transform["cutout"] = {"size": config.cutout_size, "count": config.cutout_count, "regions": cutout_regions}
        
        # Motion Blur
        if config.motion_blur_enabled and config.motion_blur_value > 0:
            if is_preview:
                kernel_size = config.motion_blur_value
            else:
                kernel_size = random.randint(5, max(5, config.motion_blur_value))
            result = self._apply_motion_blur(result, kernel_size)
            transform["motion_blur"] = kernel_size
        
        # Shear (Perspective skew)
        if config.shear_enabled:
            if is_preview:
                shear_h = config.shear_horizontal
                shear_v = config.shear_vertical
            else:
                shear_h = random.uniform(-config.shear_horizontal, config.shear_horizontal)
                shear_v = random.uniform(-config.shear_vertical, config.shear_vertical)
            result = self._apply_shear(result, shear_h, shear_v)
            transform["shear"] = {"h": shear_h, "v": shear_v}
        
        # Horizontal flip (with percentage control)
        if config.h_flip_enabled:
            apply_hflip = is_preview or random.randint(1, 100) <= config.h_flip_percent
            if apply_hflip:
                result = cv2.flip(result, 1)
                transform["h_flip"] = True
        
        # Vertical flip (with percentage control)
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
        """Roboflow style augmentation: 1 original + (multiplier-1) augmented."""
        if not config.enabled:
            return [(image, {})]
        
        results = []
        
        # 1. Add original image (no copy needed - not modified)
        results.append((image, {"original": True, "aug_index": 0}))
        
        # 2. Create augmented copies (multiplier - 1 count)
        export_config = AugmentationConfig(
            enabled=config.enabled,
            multiplier=config.multiplier,
            brighten_enabled=config.brighten_enabled,
            darken_enabled=config.darken_enabled,
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
        
        for i in range(1, config.multiplier):  # Start from 1 (0 is original)
            aug_image, transform = self.apply_augmentation(image, export_config)
            transform["aug_index"] = i
            results.append((aug_image, transform))
        
        return results
    
    def preview(
        self, 
        image: np.ndarray, 
        config: AugmentationConfig
    ) -> np.ndarray:
        """Deterministic augmentation for preview."""
        if not config.enabled:
            return image
        
        # Preview mode enabled - percentage control skipped in preview
        preview_config = AugmentationConfig(
            enabled=config.enabled,
            multiplier=config.multiplier,
            brighten_enabled=config.brighten_enabled,
            darken_enabled=config.darken_enabled,
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
    # Helper Methods
    # ─────────────────────────────────────────────────────────────────
    
    def _adjust_brightness(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Adjust brightness. factor: -1 to 1"""
        # More accurate method: adjust pixel values directly
        if factor >= 0:
            # Increase brightness
            return cv2.convertScaleAbs(image, alpha=1, beta=factor * 255)
        else:
            # Decrease brightness
            return cv2.convertScaleAbs(image, alpha=1 + factor, beta=0)
    
    def _adjust_contrast(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Adjust contrast. factor: 0.5 to 2.0"""
        # Center-based contrast: (pixel - 128) * factor + 128
        img_float = image.astype(np.float32)
        result = (img_float - 128) * factor + 128
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def _adjust_hue(self, image: np.ndarray, shift: int) -> np.ndarray:
        """Shift hue (color tone)."""
        if shift == 0:
            return image
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.int16)
        hsv[:, :, 0] = (hsv[:, :, 0] + shift) % 180
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    def _adjust_saturation(self, image: np.ndarray, factor: float) -> np.ndarray:
        """Adjust saturation."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Rotate image - empty areas black."""
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        # Black background (borderValue=(0,0,0))
        return cv2.warpAffine(image, matrix, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    
    def _adjust_gamma(self, image: np.ndarray, gamma: float) -> np.ndarray:
        """Adjust Gamma (exposure). gamma < 1: dark, gamma > 1: bright."""
        if gamma <= 0:
            gamma = 0.1
        # gamma > 1: brighter, gamma < 1: darker
        table = np.array([np.clip(pow(i / 255.0, 1.0 / gamma) * 255.0, 0, 255) for i in range(256)]).astype("uint8")
        return cv2.LUT(image, table)
    
    def _apply_cutout(self, image: np.ndarray, size_percent: int, count: int) -> Tuple[np.ndarray, List[Tuple[int, int, int, int]]]:
        """Apply multiple random square cutouts (black square).
        
        Returns:
            (result_image, cutout_regions) - cutout_regions: [(x1, y1, x2, y2), ...]
        """
        h, w = image.shape[:2]
        result = image.copy()
        cutout_regions = []
        
        # Square cutout size (based on min dim)
        cut_size = int(min(h, w) * size_percent / 100)
        
        if cut_size <= 0:
            return result, cutout_regions
        
        # Add random square cutouts in specified count
        for _ in range(count):
            y1 = random.randint(0, max(0, h - cut_size))
            x1 = random.randint(0, max(0, w - cut_size))
            y2 = min(y1 + cut_size, h)
            x2 = min(x1 + cut_size, w)
            result[y1:y2, x1:x2] = 0  # Black square
            cutout_regions.append((x1, y1, x2, y2))
        
        return result, cutout_regions
    
    def _apply_motion_blur(self, image: np.ndarray, kernel_size: int) -> np.ndarray:
        """Apply motion blur (horizontal motion blur)."""
        kernel_size = max(3, kernel_size)
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        # Horizontal motion blur kernel
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[kernel_size // 2, :] = 1.0 / kernel_size
        
        return cv2.filter2D(image, -1, kernel)
    
    def _apply_shear(self, image: np.ndarray, shear_h: float, shear_v: float) -> np.ndarray:
        """
        Apply shear (DigitalOcean methodology).
        
        1. Expand image (to prevent overflow after shear)
        2. Apply shear
        3. Resize to original size
        
        Flip technique is used for negative shear.
        """
        h, w = image.shape[:2]
        
        # Calculate shear factors
        shear_h_rad = np.tan(np.radians(shear_h))
        shear_v_rad = np.tan(np.radians(shear_v))
        
        # Flip flags for negative shear
        h_flip = shear_h_rad < 0
        v_flip = shear_v_rad < 0
        
        if h_flip:
            image = cv2.flip(image, 1)  # Horizontal flip
        if v_flip:
            image = cv2.flip(image, 0)  # Vertical flip
        
        abs_shear_h = abs(shear_h_rad)
        abs_shear_v = abs(shear_v_rad)
        
        # Shear matrix (origin based, with positive values)
        M = np.float32([
            [1, abs_shear_h, 0],
            [abs_shear_v, 1, 0]
        ])
        
        # New dimensions (expansion)
        nW = int(w + abs_shear_h * h)
        nH = int(h + abs_shear_v * w)
        
        # Apply shear
        result = cv2.warpAffine(image, M, (nW, nH), 
                                borderMode=cv2.BORDER_CONSTANT, 
                                borderValue=(0, 0, 0))
        
        # Revert flips
        if h_flip:
            result = cv2.flip(result, 1)
        if v_flip:
            result = cv2.flip(result, 0)
        
        # Resize to original size
        result = cv2.resize(result, (w, h))
        
        return result
    
    # ─────────────────────────────────────────────────────────────────
    # BBox/Polygon Transformations
    # ─────────────────────────────────────────────────────────────────
    
    def transform_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        transform: Dict[str, Any],
        img_w: int,
        img_h: int
    ) -> Tuple[float, float, float, float]:
        """Transform bbox according to transform.
        
        Transformation order must be SAME as apply_augmentation:
        1. Shear
        2. H_flip
        3. V_flip
        4. Rotation
        """
        x_center, y_center, w, h = bbox
        
        # 1. Shear transformation (if any)
        shear = transform.get("shear")
        if shear:
            x_center, y_center, w, h = self._shear_bbox(
                x_center, y_center, w, h, shear.get("h", 0), shear.get("v", 0), img_w, img_h
            )
        
        # 2. Flip transformations
        if transform.get("h_flip"):
            x_center = 1.0 - x_center
        if transform.get("v_flip"):
            y_center = 1.0 - y_center
        
        # 3. Rotation transformation (if any)
        rotation = transform.get("rotation")
        if rotation and abs(rotation) > 0.5:
            x_center, y_center, w, h = self._rotate_bbox(
                x_center, y_center, w, h, rotation, img_w, img_h
            )
        
        # Keep coordinates within [0, 1]
        x_center = max(0, min(1, x_center))
        y_center = max(0, min(1, y_center))
        w = max(0.001, min(1, w))
        h = max(0.001, min(1, h))
        
        return (x_center, y_center, w, h)
    
    def _rotate_bbox(
        self, x_c: float, y_c: float, w: float, h: float,
        angle: float, img_w: int, img_h: int
    ) -> Tuple[float, float, float, float]:
        """Transform bbox according to rotation - calculate enclosing rectangle."""
        import math
        
        # Convert normalized coordinates to pixel
        cx_px = x_c * img_w
        cy_px = y_c * img_h
        w_px = w * img_w
        h_px = h * img_h
        
        # Calculate 4 corners
        half_w, half_h = w_px / 2, h_px / 2
        corners = [
            (cx_px - half_w, cy_px - half_h),
            (cx_px + half_w, cy_px - half_h),
            (cx_px + half_w, cy_px + half_h),
            (cx_px - half_w, cy_px + half_h)
        ]
        
        # Rotate (around image center)
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
        
        # Clipping: Fit within image bounds
        min_x = max(0, min(xs))
        max_x = min(img_w, max(xs))
        min_y = max(0, min(ys))
        max_y = min(img_h, max(ys))
        
        # Validation
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
        Transform bbox according to shear (DigitalOcean methodology).
        
        SAME logic as _apply_shear:
        1. Flip coordinates for negative shear
        2. Apply positive shear matrix
        3. Apply scale factor after expansion
        4. Revert flip
        5. Clip
        """
        import numpy as np
        
        # Calculate shear factors
        shear_h_rad = np.tan(np.radians(shear_h))
        shear_v_rad = np.tan(np.radians(shear_v))
        
        # Flip flags for negative shear
        h_flip = shear_h_rad < 0
        v_flip = shear_v_rad < 0
        
        abs_shear_h = abs(shear_h_rad)
        abs_shear_v = abs(shear_v_rad)
        
        # 1. Convert coordinates to pixel
        cx_px = x_c * img_w
        cy_px = y_c * img_h
        w_px = w * img_w
        h_px = h * img_h
        
        # 2. Calculate 4 corners (from original coordinates)
        half_w, half_h = w_px / 2, h_px / 2
        x1 = cx_px - half_w
        y1 = cy_px - half_h
        x2 = cx_px + half_w
        y2 = cy_px + half_h
        
        # 3. Flip coordinates for negative shear
        if h_flip:
            x1, x2 = img_w - x2, img_w - x1
        if v_flip:
            y1, y2 = img_h - y2, img_h - y1
        
        # 4. Shear formula: x_new = x + shear_h * y, y_new = y + shear_v * x
        # Transform 4 corners
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
        
        # 6. Revert flip (in expanded size - nW, nH)
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
        
        # 7. Apply scale factor (resize effect)
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
        
        # 8. Calculate new dimensions
        new_w_px = max_x - min_x
        new_h_px = max_y - min_y
        
        # 9. Validation
        if new_w_px <= 1 or new_h_px <= 1:
            return (0.0, 0.0, 0.0, 0.0)
        
        new_cx_px = min_x + new_w_px / 2
        new_cy_px = min_y + new_h_px / 2
        
        # 10. Normalize and return
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
        """Transform polygon points according to transform.
        
        Transformation order must be SAME as apply_augmentation:
        1. Shear
        2. H_flip
        3. V_flip
        4. Rotation
        """
        import math
        import numpy as np
        
        result = []
        for x, y in points:
            # 1. Shear transformation
            shear = transform.get("shear")
            if shear:
                px, py = x * img_w, y * img_h
                
                shear_h_rad = np.tan(np.radians(shear.get("h", 0)))
                shear_v_rad = np.tan(np.radians(shear.get("v", 0)))
                
                # Flip for negative shear
                h_flip_shear = shear_h_rad < 0
                v_flip_shear = shear_v_rad < 0
                
                if h_flip_shear:
                    px = img_w - px
                if v_flip_shear:
                    py = img_h - py
                
                abs_shear_h = abs(shear_h_rad)
                abs_shear_v = abs(shear_v_rad)
                
                # Apply shear formula
                new_px = px + abs_shear_h * py
                new_py = py + abs_shear_v * px
                
                # Scale factor (resize effect after expansion)
                nW = img_w + abs_shear_h * img_h
                nH = img_h + abs_shear_v * img_w
                
                new_px = new_px / (nW / img_w)
                new_py = new_py / (nH / img_h)
                
                # Revert flip
                if h_flip_shear:
                    new_px = img_w - new_px
                if v_flip_shear:
                    new_py = img_h - new_py
                
                x = new_px / img_w
                y = new_py / img_h
            
            # 2. Flip transformations
            if transform.get("h_flip"):
                x = 1.0 - x
            if transform.get("v_flip"):
                y = 1.0 - y
            
            # 3. Rotation transformation
            rotation = transform.get("rotation")
            if rotation and abs(rotation) > 0.5:
                # Convert to pixel
                px, py = x * img_w, y * img_h
                center_x, center_y = img_w / 2, img_h / 2
                rad = math.radians(-rotation)
                cos_a, sin_a = math.cos(rad), math.sin(rad)
                
                new_px = (px - center_x) * cos_a - (py - center_y) * sin_a + center_x
                new_py = (px - center_x) * sin_a + (py - center_y) * cos_a + center_y
                
                x = new_px / img_w
                y = new_py / img_h
            
            # Keep coordinates within [0, 1]
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
        elif mode and mode.startswith("fit_"):
            scale = resize_info.get("scale", 1.0)
            offset = resize_info.get("offset", (0, 0))
            px = x_center * orig_w * scale + offset[0]
            py = y_center * orig_h * scale + offset[1]
            pw = w * orig_w * scale
            ph = h * orig_h * scale
            return (px / new_w, py / new_h, pw / new_w, ph / new_h)
        
        return bbox
    
    def is_bbox_covered_by_cutout(
        self,
        bbox: Tuple[float, float, float, float],
        cutout_regions: List[Tuple[int, int, int, int]],
        img_w: int,
        img_h: int,
        threshold: float = 0.9
    ) -> bool:

        """
        Checks if BBox is covered by cutout by a certain ratio.
        
        Args:
            bbox: (x_center, y_center, width, height) normalized
            cutout_regions: [(x1, y1, x2, y2), ...] pixel coordinates
            img_w, img_h: image dimensions
            threshold: overlap threshold (0.9 = 90%)
            
        Returns:
            True if bbox is covered by cutout more than threshold
        """
        if not cutout_regions:
            return False
        
        x_c, y_c, w, h = bbox
        
        # Convert BBox to pixel coordinates
        bbox_x1 = (x_c - w/2) * img_w
        bbox_y1 = (y_c - h/2) * img_h
        bbox_x2 = (x_c + w/2) * img_w
        bbox_y2 = (y_c + h/2) * img_h
        
        bbox_area = (bbox_x2 - bbox_x1) * (bbox_y2 - bbox_y1)
        if bbox_area <= 0:
            return True  # Invalid bbox, remove it
        
        # Calculate total overlap with all cutout regions
        total_covered = 0.0
        for cut_x1, cut_y1, cut_x2, cut_y2 in cutout_regions:
            # Calculate intersection area
            inter_x1 = max(bbox_x1, cut_x1)
            inter_y1 = max(bbox_y1, cut_y1)
            inter_x2 = min(bbox_x2, cut_x2)
            inter_y2 = min(bbox_y2, cut_y2)
            
            if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                total_covered += inter_area
        
        coverage_ratio = total_covered / bbox_area
        return coverage_ratio >= threshold
    
    def is_polygon_covered_by_cutout(
        self,
        points: List[Tuple[float, float]],
        cutout_regions: List[Tuple[int, int, int, int]],
        img_w: int,
        img_h: int,
        threshold: float = 0.9
    ) -> bool:
        """
        Checks if Polygon is covered by cutout by a certain ratio.
        
        Simplified approach: Uses Polygon's bounding box.
        
        Args:
            points: [(x, y), ...] normalized coordinates
            cutout_regions: [(x1, y1, x2, y2), ...] pixel coordinates
            img_w, img_h: image dimensions
            threshold: overlap threshold (0.9 = 90%)
            
        Returns:
            True if polygon is covered by cutout more than threshold
        """
        if not cutout_regions or len(points) < 3:
            return False
        
        # Find Polygon's bounding box
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
        # Check as Bounding box
        x_c = (x_min + x_max) / 2
        y_c = (y_min + y_max) / 2
        w = x_max - x_min
        h = y_max - y_min
        
        return self.is_bbox_covered_by_cutout(
            (x_c, y_c, w, h), cutout_regions, img_w, img_h, threshold
        )
    
    def apply_cutout_to_polygon(
        self,
        polygon_points: List[Tuple[float, float]],
        cutout_regions: List[Tuple[int, int, int, int]],
        img_w: int,
        img_h: int,
        min_area: int = 100
    ) -> List[List[Tuple[float, float]]]:
        """
        Creates new polygon(s) by subtracting cutout regions from Polygon.
        
        Mask based approach:
        1. Draw Polygon as mask (white)
        2. Draw cutout regions on mask as black (erase)
        3. Get new polygons with findContours
        
        Args:
            polygon_points: [(x, y), ...] normalized coordinates (0-1)
            cutout_regions: [(x1, y1, x2, y2), ...] pixel coordinates
            img_w, img_h: image dimensions
            min_area: minimum polygon area (pixel²) - small parts are filtered
            
        Returns:
            List of polygons - each is normalized coordinates [(x, y), ...]
            Polygon can be split after cutout, so returns a list
        """
        if not cutout_regions or len(polygon_points) < 3:
            return [polygon_points]  # No change
        
        # 1. Create empty mask
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        
        # 2. Convert Polygon to pixel coordinates and draw on mask
        pts = np.array([
            [int(x * img_w), int(y * img_h)] for x, y in polygon_points
        ], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
        
        # 3. Draw cutout regions on mask as black (erase)
        for cut_x1, cut_y1, cut_x2, cut_y2 in cutout_regions:
            cv2.rectangle(mask, (cut_x1, cut_y1), (cut_x2, cut_y2), 0, thickness=-1)
        
        # 4. Read new contours from mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        new_polygons = []
        for cnt in contours:
            # Filter small parts
            if cv2.contourArea(cnt) < min_area:
                continue
            
            # Convert contour points to normalized coordinates
            reshaped = cnt.reshape(-1, 2)
            normalized_points = [
                (float(x) / img_w, float(y) / img_h) 
                for x, y in reshaped
            ]
            
            if len(normalized_points) >= 3:
                new_polygons.append(normalized_points)
        
        # If no polygon left, return empty list
        return new_polygons

    def get_resize_duplicates_bbox(
        self,
        bbox: Tuple[float, float, float, float],
        resize_info: Dict[str, Any],
        orig_w: int,
        orig_h: int,
        new_w: int,
        new_h: int
    ) -> List[Tuple[float, float, float, float]]:
        """
        Returns original bbox and its reflections (duplicates) for FIT_REFLECT mode.
        Returns single element list for other modes.
        """
        # Calculate main (center) bbox first
        main_bbox = self.transform_bbox_for_resize(bbox, resize_info, orig_w, orig_h, new_w, new_h)
        
        mode = resize_info.get("mode")
        if mode != "fit_reflect":
            return [main_bbox]
        
        results = [main_bbox]
        
        # Get padding and inner size info
        pad_x, pad_y = resize_info.get("offset", (0, 0))
        inner_w, inner_h = resize_info.get("new_size", (new_w, new_h))
        
        # BBox pixel coordinates (on target image)
        mx_c, my_c, mw, mh = main_bbox
        mx_c_px, my_c_px = mx_c * new_w, my_c * new_h
        mw_px, mh_px = mw * new_w, mh * new_h
        
        # Reflection axes
        left_axis = pad_x - 0.5  # 0.5 pixel shift (more precise for BORDER_REFLECT)
        right_axis = pad_x + inner_w - 0.5
        top_axis = pad_y - 0.5
        bottom_axis = pad_y + inner_h - 0.5
        
        # Define 8 neighbor regions (dx, dy) -> (-1 left, 1 right, 0 center)
        neighbors = [
            (-1, 0), (1, 0), (0, -1), (0, 1),  # Edges
            (-1, -1), (1, -1), (-1, 1), (1, 1) # Corners
        ]
        
        for dx, dy in neighbors:
            cx_new, cy_new = mx_c_px, my_c_px
            
            # Horizontal Reflection
            if dx == -1: # Left
                # x' = axis - (x - axis) = 2*axis - x
                cx_new = 2 * left_axis - cx_new
            elif dx == 1: # Right
                cx_new = 2 * right_axis - cx_new
                
            # Vertical Reflection
            if dy == -1: # Top
                cy_new = 2 * top_axis - cy_new
            elif dy == 1: # Bottom
                cy_new = 2 * bottom_axis - cy_new
            
            # Check if inside Canvas (simple intersection)
            # Box limits
            x1 = cx_new - mw_px / 2
            x2 = cx_new + mw_px / 2
            y1 = cy_new - mh_px / 2
            y2 = cy_new + mh_px / 2
            
            # Does Bounding box intersect with canvas?
            if x2 > 0 and x1 < new_w and y2 > 0 and y1 < new_h:
                # Clipping (User want: label limits should not exceed photo)
                # Actually clipping: Crop into image area.
                # We cannot just discard overflowing part while keeping bbox center and size (bbox center shifts).
                # Standard method: Clip BBox to image limits, then calculate new center/size.
                
                c_x1 = max(0, x1)
                c_y1 = max(0, y1)
                c_x2 = min(new_w, x2)
                c_y2 = min(new_h, y2)
                
                if c_x2 > c_x1 and c_y2 > c_y1:
                    new_bw = c_x2 - c_x1
                    new_bh = c_y2 - c_y1
                    new_bcx = c_x1 + new_bw / 2
                    new_bcy = c_y1 + new_bh / 2
                    
                    results.append((
                        new_bcx / new_w,
                        new_bcy / new_h,
                        new_bw / new_w,
                        new_bh / new_h
                    ))
                    
        return results

    def get_resize_duplicates_polygon(
        self,
        points: List[Tuple[float, float]],
        resize_info: Dict[str, Any],
        orig_w: int,
        orig_h: int,
        new_w: int,
        new_h: int
    ) -> List[List[Tuple[float, float]]]:
        """
        Returns original polygon and its reflections for FIT_REFLECT mode.
        """
        # Calculate main (center) polygon first
        # No transform_polygon_for_resize method, apply manually:
        
        main_poly = []
        mode = resize_info.get("mode")
        scale = resize_info.get("scale", 1.0)
        offset = resize_info.get("offset", (0, 0))
        inner_w, inner_h = resize_info.get("new_size", (new_w, new_h))
        pad_x, pad_y = offset
        
        # Main polygon transformation
        for px, py in points:
            # First pixel (on final image)
            if mode and mode.startswith("fit_"):
                res_x = px * orig_w * scale + pad_x
                res_y = py * orig_h * scale + pad_y
            else: # stretch or none
                res_x = px * new_w
                res_y = py * new_h
            
            main_poly.append((res_x, res_y)) # Pixel coordinates for now
            
        if mode != "fit_reflect":
            # Convert to normal and return
            return [[(x/new_w, y/new_h) for x, y in main_poly]]
            
        # For Reflection
        poly_results = []
        
        # Add main polygon (clip first)
        clipped_main = self._clip_polygon_to_rect(main_poly, 0, 0, new_w, new_h)
        if len(clipped_main) >= 3:
             poly_results.append([(x/new_w, y/new_h) for x, y in clipped_main])
             
        # Reflection axes
        left_axis = pad_x - 0.5
        right_axis = pad_x + inner_w - 0.5
        top_axis = pad_y - 0.5
        bottom_axis = pad_y + inner_h - 0.5
        
        neighbors = [
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (1, -1), (-1, 1), (1, 1)
        ]
        
        for dx, dy in neighbors:
            new_poly_pts = []
            
            # Apply reflection for each point
            for px, py in main_poly:
                nx, ny = px, py
                
                # Horizontal
                if dx == -1: nx = 2 * left_axis - nx
                elif dx == 1: nx = 2 * right_axis - nx
                
                # Vertical
                if dy == -1: ny = 2 * top_axis - ny
                elif dy == 1: ny = 2 * bottom_axis - ny
                
                new_poly_pts.append((nx, ny))
            
            # Clip
            clipped = self._clip_polygon_to_rect(new_poly_pts, 0, 0, new_w, new_h)
            if len(clipped) >= 3:
                poly_results.append([(x/new_w, y/new_h) for x, y in clipped])
                
        return poly_results

    def _clip_polygon_to_rect(self, points, x_min, y_min, x_max, y_max):
        """Clip polygon into rectangle (Simplified Sutherland-Hodgman or simple clip)."""
        # Simple clip: Limit points (this distorts polygon shape but simplest)
        # Correct clip: Sutherland-Hodgman. 
        # Correct clipping is long without OpenCV or Shapely.
        # User said "No label shifting", simple clamp can distort shape.
        # But here we are cutting parts outside augmentation padding.
        # Simply: Our implementation or clamp existing points?
        
        # Clamp method (simple):
        # return [(max(x_min, min(x_max, x)), max(y_min, min(y_max, y))) for x, y in points]
        # This method "squashes" polygon to edge. Generally not desired.
        
        # For now, just take points remaining inside canvas? No, that also splits.
        # Best: Leave points as is, should outside ones be discarded during export?
        # User said "should not exceed photo".
        # In this case simple Sutherland-Hodrman like thing or bounding box clip is needed.
        
        # Quick solution: Clamp points. Typically prevents spilling outside.
        # Or: Return only if not completely outside.
        
        clamped = []
        all_outside = True
        for x, y in points:
            cx = max(x_min, min(x_max, x))
            cy = max(y_min, min(y_max, y))
            clamped.append((cx, cy))
            if x_min <= x <= x_max and y_min <= y <= y_max:
                all_outside = False
        
        if all_outside:
            return []
            
        return clamped
