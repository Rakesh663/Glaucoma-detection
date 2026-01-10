"""
Clinical-Grade Data Augmentation for Small Fundus Datasets
Designed to maximize learning from limited training data (900 images)

Key Techniques:
1. MixUp - Blend images and labels
2. CutMix - Cut and paste image regions  
3. Mosaic - Combine 4 images into 1
4. Camera Simulation - Simulate different fundus cameras
5. Clinical Variations - Simulate real-world hospital conditions
"""

import cv2
import numpy as np
import albumentations as A
from albumentations.pytorch import ToTensorV2
from typing import Tuple, Dict, Optional, List, Callable
import random


class MixUpCutMix:
    """
    MixUp and CutMix augmentation for training.
    Critical for small datasets - significantly improves generalization.
    
    MixUp: image = λ*img1 + (1-λ)*img2, label = λ*label1 + (1-λ)*label2
    CutMix: Paste random region from img2 onto img1, adjust labels by area
    """
    
    def __init__(
        self,
        mixup_alpha: float = 0.4,
        cutmix_alpha: float = 1.0,
        mixup_prob: float = 0.3,
        cutmix_prob: float = 0.3
    ):
        """
        Initialize MixUp/CutMix augmentation.
        
        Args:
            mixup_alpha: Beta distribution parameter for MixUp
            cutmix_alpha: Beta distribution parameter for CutMix
            mixup_prob: Probability of applying MixUp
            cutmix_prob: Probability of applying CutMix
        """
        self.mixup_alpha = mixup_alpha
        self.cutmix_alpha = cutmix_alpha
        self.mixup_prob = mixup_prob
        self.cutmix_prob = cutmix_prob
    
    def mixup(
        self,
        images: np.ndarray,
        labels: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply MixUp augmentation to a batch.
        
        Args:
            images: Batch of images (N, H, W, C) or (N, C, H, W)
            labels: Batch of labels (N,) or (N, 1)
            
        Returns:
            Mixed images and labels
        """
        if random.random() > self.mixup_prob:
            return images, labels
        
        batch_size = len(images)
        
        # Sample lambda from Beta distribution
        lam = np.random.beta(self.mixup_alpha, self.mixup_alpha)
        
        # Random shuffle for pairing
        indices = np.random.permutation(batch_size)
        
        # Mix images
        mixed_images = lam * images + (1 - lam) * images[indices]
        
        # Mix labels
        labels = labels.flatten() if len(labels.shape) > 1 else labels
        mixed_labels = lam * labels + (1 - lam) * labels[indices]
        
        return mixed_images.astype(images.dtype), mixed_labels.astype(np.float32)
    
    def cutmix(
        self,
        images: np.ndarray,
        labels: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply CutMix augmentation to a batch.
        
        Args:
            images: Batch of images (N, H, W, C)
            labels: Batch of labels (N,) or (N, 1)
            
        Returns:
            CutMixed images and labels
        """
        if random.random() > self.cutmix_prob:
            return images, labels
        
        batch_size = len(images)
        
        # Sample lambda from Beta distribution
        lam = np.random.beta(self.cutmix_alpha, self.cutmix_alpha)
        
        # Random shuffle for pairing
        indices = np.random.permutation(batch_size)
        
        # Get image dimensions
        if len(images.shape) == 4:
            _, h, w, _ = images.shape
        else:
            raise ValueError(f"Expected 4D array, got shape {images.shape}")
        
        # Get random bounding box
        bbx1, bby1, bbx2, bby2 = self._rand_bbox(h, w, lam)
        
        # Apply CutMix
        mixed_images = images.copy()
        mixed_images[:, bby1:bby2, bbx1:bbx2, :] = images[indices, bby1:bby2, bbx1:bbx2, :]
        
        # Adjust lambda based on actual box area
        lam_adjusted = 1 - ((bbx2 - bbx1) * (bby2 - bby1) / (h * w))
        
        # Mix labels
        labels = labels.flatten() if len(labels.shape) > 1 else labels
        mixed_labels = lam_adjusted * labels + (1 - lam_adjusted) * labels[indices]
        
        return mixed_images, mixed_labels.astype(np.float32)
    
    def _rand_bbox(self, h: int, w: int, lam: float) -> Tuple[int, int, int, int]:
        """Generate random bounding box for CutMix."""
        cut_ratio = np.sqrt(1 - lam)
        cut_h = int(h * cut_ratio)
        cut_w = int(w * cut_ratio)
        
        # Center point
        cx = np.random.randint(w)
        cy = np.random.randint(h)
        
        # Bounding box
        bbx1 = np.clip(cx - cut_w // 2, 0, w)
        bby1 = np.clip(cy - cut_h // 2, 0, h)
        bbx2 = np.clip(cx + cut_w // 2, 0, w)
        bby2 = np.clip(cy + cut_h // 2, 0, h)
        
        return int(bbx1), int(bby1), int(bbx2), int(bby2)
    
    def __call__(
        self,
        images: np.ndarray,
        labels: np.ndarray,
        mode: str = 'both'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply MixUp, CutMix, or both randomly.
        
        Args:
            images: Batch of images
            labels: Batch of labels
            mode: 'mixup', 'cutmix', or 'both'
            
        Returns:
            Augmented images and labels
        """
        if mode == 'mixup':
            return self.mixup(images, labels)
        elif mode == 'cutmix':
            return self.cutmix(images, labels)
        else:
            # Randomly choose between MixUp and CutMix
            if random.random() < 0.5:
                return self.mixup(images, labels)
            else:
                return self.cutmix(images, labels)


class CameraSimulator:
    """
    Simulate images from different fundus camera models.
    Helps the model generalize across different hospital equipment.
    """
    
    def __init__(self):
        # Camera profiles (approximate color shifts and characteristics)
        self.camera_profiles = {
            'topcon': {
                'color_shift': [1.0, 1.05, 0.95],  # Slightly warmer
                'vignette_strength': 0.3,
                'brightness_adjust': 1.0
            },
            'canon': {
                'color_shift': [0.98, 1.0, 1.02],  # Slightly cooler
                'vignette_strength': 0.25,
                'brightness_adjust': 1.05
            },
            'zeiss': {
                'color_shift': [1.02, 0.98, 1.0],  # Slightly reddish
                'vignette_strength': 0.2,
                'brightness_adjust': 0.95
            },
            'nikon': {
                'color_shift': [1.0, 1.0, 1.0],  # Neutral
                'vignette_strength': 0.35,
                'brightness_adjust': 1.0
            }
        }
    
    def simulate(
        self,
        image: np.ndarray,
        camera: Optional[str] = None
    ) -> np.ndarray:
        """
        Simulate image from a different camera.
        
        Args:
            image: Input image (H, W, C), float32 0-1 or uint8
            camera: Camera name or None for random
            
        Returns:
            Simulated image
        """
        # Random camera if not specified
        if camera is None:
            camera = random.choice(list(self.camera_profiles.keys()))
        
        profile = self.camera_profiles.get(camera, self.camera_profiles['topcon'])
        
        # Normalize to float32 if needed
        if image.dtype == np.uint8:
            image = image.astype(np.float32) / 255.0
        
        # Apply color shift
        color_shift = np.array(profile['color_shift'])
        image = image * color_shift
        
        # Apply brightness adjustment
        image = image * profile['brightness_adjust']
        
        # Apply vignette
        image = self._apply_vignette(image, profile['vignette_strength'])
        
        # Clip values
        image = np.clip(image, 0, 1)
        
        return image
    
    def _apply_vignette(
        self,
        image: np.ndarray,
        strength: float
    ) -> np.ndarray:
        """Apply vignette effect (darker corners)."""
        h, w = image.shape[:2]
        
        # Create vignette mask
        x = np.linspace(-1, 1, w)
        y = np.linspace(-1, 1, h)
        X, Y = np.meshgrid(x, y)
        
        # Radial distance from center
        distance = np.sqrt(X**2 + Y**2)
        
        # Vignette mask (1 at center, decreasing towards edges)
        vignette = 1 - (distance * strength)
        vignette = np.clip(vignette, 0.5, 1)
        
        # Apply to image
        if len(image.shape) == 3:
            vignette = vignette[:, :, np.newaxis]
        
        return image * vignette


class ClinicalAugmentation:
    """
    Clinical-grade augmentation pipeline for fundus images.
    Simulates real-world hospital imaging conditions.
    """
    
    def __init__(
        self,
        image_size: int = 512,
        apply_camera_sim: bool = True,
        apply_lighting_var: bool = True,
        apply_motion_blur: bool = True,
        apply_dust_artifacts: bool = True,
        aggressive: bool = True  # More aggressive for small datasets
    ):
        self.image_size = image_size
        self.apply_camera_sim = apply_camera_sim
        self.apply_lighting_var = apply_lighting_var
        self.apply_motion_blur = apply_motion_blur
        self.apply_dust_artifacts = apply_dust_artifacts
        self.aggressive = aggressive
        
        self.camera_simulator = CameraSimulator()
    
    def __call__(self, image: np.ndarray) -> np.ndarray:
        """Apply clinical augmentations."""
        return self.augment(image)
    
    def augment(self, image: np.ndarray) -> np.ndarray:
        """
        Apply clinical-grade augmentations.
        
        Args:
            image: Input image (H, W, C), uint8 or float32
            
        Returns:
            Augmented image
        """
        # Convert to float32 if needed
        if image.dtype == np.uint8:
            image = image.astype(np.float32) / 255.0
            was_uint8 = True
        else:
            was_uint8 = False
        
        # Camera simulation
        if self.apply_camera_sim and random.random() < 0.3:
            image = self.camera_simulator.simulate(image)
        
        # Lighting variation (uneven illumination)
        if self.apply_lighting_var and random.random() < 0.4:
            image = self._apply_lighting_variation(image)
        
        # Motion blur (patient movement)
        if self.apply_motion_blur and random.random() < 0.2:
            image = self._apply_motion_blur(image)
        
        # Dust/artifact simulation
        if self.apply_dust_artifacts and random.random() < 0.15:
            image = self._apply_dust_artifacts(image)
        
        # Clip values
        image = np.clip(image, 0, 1)
        
        # Convert back to uint8 if needed
        if was_uint8:
            image = (image * 255).astype(np.uint8)
        
        return image
    
    def _apply_lighting_variation(self, image: np.ndarray) -> np.ndarray:
        """Simulate uneven lighting across the image."""
        h, w = image.shape[:2]
        
        # Random gradient direction
        angle = random.uniform(0, 2 * np.pi)
        
        # Create gradient
        x = np.linspace(-1, 1, w)
        y = np.linspace(-1, 1, h)
        X, Y = np.meshgrid(x, y)
        
        gradient = np.cos(angle) * X + np.sin(angle) * Y
        gradient = (gradient - gradient.min()) / (gradient.max() - gradient.min())
        
        # Apply gradient as brightness variation
        strength = random.uniform(0.1, 0.3)
        gradient_factor = 1 - strength + strength * gradient
        
        if len(image.shape) == 3:
            gradient_factor = gradient_factor[:, :, np.newaxis]
        
        return image * gradient_factor
    
    def _apply_motion_blur(self, image: np.ndarray) -> np.ndarray:
        """Simulate motion blur from patient movement."""
        # Convert to uint8 for OpenCV
        image_uint8 = (image * 255).astype(np.uint8)
        
        # Random kernel size and angle
        kernel_size = random.choice([3, 5, 7])
        angle = random.uniform(0, 180)
        
        # Create motion blur kernel
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[kernel_size // 2, :] = 1.0 / kernel_size
        
        # Rotate kernel
        center = (kernel_size // 2, kernel_size // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        kernel = cv2.warpAffine(kernel, M, (kernel_size, kernel_size))
        kernel = kernel / kernel.sum()
        
        # Apply motion blur
        blurred = cv2.filter2D(image_uint8, -1, kernel)
        
        return blurred.astype(np.float32) / 255.0
    
    def _apply_dust_artifacts(self, image: np.ndarray) -> np.ndarray:
        """Simulate dust on camera lens."""
        h, w = image.shape[:2]
        
        # Random number of dust spots
        num_spots = random.randint(1, 5)
        
        for _ in range(num_spots):
            # Random position
            cx = random.randint(0, w - 1)
            cy = random.randint(0, h - 1)
            
            # Random size
            radius = random.randint(3, 15)
            
            # Create circular dust spot
            y, x = np.ogrid[:h, :w]
            mask = ((x - cx) ** 2 + (y - cy) ** 2) <= radius ** 2
            
            # Darken the dust spot area
            dust_factor = random.uniform(0.5, 0.8)
            if len(image.shape) == 3:
                for c in range(image.shape[2]):
                    image[:, :, c] = np.where(mask, image[:, :, c] * dust_factor, image[:, :, c])
            else:
                image = np.where(mask, image * dust_factor, image)
        
        return image


def get_clinical_train_transform(config: Dict) -> A.Compose:
    """
    Get production-grade training augmentation pipeline.
    Designed for small fundus datasets (< 1000 images).
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Albumentations Compose pipeline
    """
    image_size = config['data']['image_size']
    aug_config = config.get('augmentation', {})
    
    # Get normalization stats (fundus-specific or ImageNet)
    norm_type = config.get('normalization', {}).get('type', 'fundus')
    if norm_type == 'fundus':
        mean = config.get('normalization', {}).get('fundus_mean', [0.485, 0.285, 0.156])
        std = config.get('normalization', {}).get('fundus_std', [0.229, 0.184, 0.134])
    else:
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]
    
    # Build aggressive augmentation pipeline for small dataset
    transforms = [
        # Resize with high-quality interpolation
        A.Resize(image_size, image_size, interpolation=cv2.INTER_LANCZOS4),
        
        # Geometric augmentations (fundus images are rotation-invariant)
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.Rotate(limit=30, p=0.5, border_mode=cv2.BORDER_CONSTANT),
        
        # Affine transforms
        A.Affine(
            scale=(0.9, 1.1),
            translate_percent=(-0.05, 0.05),
            rotate=(-15, 15),
            shear=(-5, 5),
            p=0.3
        ),
        
        # Color augmentations (important for camera variation)
        A.RandomBrightnessContrast(
            brightness_limit=0.3,
            contrast_limit=0.3,
            p=0.6
        ),
        A.HueSaturationValue(
            hue_shift_limit=10,
            sat_shift_limit=20,
            val_shift_limit=20,
            p=0.4
        ),
        A.ColorJitter(
            brightness=0.2,
            contrast=0.2,
            saturation=0.2,
            hue=0.05,
            p=0.3
        ),
        
        # Channel manipulation
        A.ChannelShuffle(p=0.1),
        A.RGBShift(r_shift_limit=10, g_shift_limit=10, b_shift_limit=10, p=0.2),
        
        # Blur augmentations (simulate focus issues)
        A.OneOf([
            A.GaussianBlur(blur_limit=(3, 7), p=1.0),
            A.MedianBlur(blur_limit=5, p=1.0),
            A.MotionBlur(blur_limit=5, p=1.0),
        ], p=0.3),
        
        # Noise augmentations (simulate sensor noise)
        A.OneOf([
            A.GaussNoise(var_limit=(10.0, 50.0), p=1.0),
            A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=1.0),
            A.MultiplicativeNoise(multiplier=(0.9, 1.1), p=1.0),
        ], p=0.3),
        
        # Contrast enhancement (important for fundus)
        A.CLAHE(clip_limit=4.0, tile_grid_size=(8, 8), p=0.4),
        A.Equalize(p=0.2),
        
        # Dropout augmentations (regularization)
        A.OneOf([
            A.CoarseDropout(
                max_holes=8,
                max_height=image_size // 16,
                max_width=image_size // 16,
                fill_value=0,
                p=1.0
            ),
            A.GridDropout(ratio=0.3, p=1.0),
        ], p=0.2),
        
        # Final normalization
        A.Normalize(mean=mean, std=std),
        ToTensorV2()
    ]
    
    return A.Compose(transforms)


def get_clinical_val_transform(config: Dict) -> A.Compose:
    """
    Get validation/test transform (no augmentation, only preprocessing).
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Albumentations Compose pipeline
    """
    image_size = config['data']['image_size']
    
    # Get normalization stats
    norm_type = config.get('normalization', {}).get('type', 'fundus')
    if norm_type == 'fundus':
        mean = config.get('normalization', {}).get('fundus_mean', [0.485, 0.285, 0.156])
        std = config.get('normalization', {}).get('fundus_std', [0.229, 0.184, 0.134])
    else:
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]
    
    return A.Compose([
        A.Resize(image_size, image_size, interpolation=cv2.INTER_LANCZOS4),
        A.Normalize(mean=mean, std=std),
        ToTensorV2()
    ])


def get_tta_transforms(config: Dict, n_augments: int = 5) -> List[A.Compose]:
    """
    Get Test-Time Augmentation transforms.
    
    Args:
        config: Configuration dictionary
        n_augments: Number of augmentation variants
        
    Returns:
        List of Albumentations Compose pipelines
    """
    image_size = config['data']['image_size']
    
    norm_type = config.get('normalization', {}).get('type', 'fundus')
    if norm_type == 'fundus':
        mean = config.get('normalization', {}).get('fundus_mean', [0.485, 0.285, 0.156])
        std = config.get('normalization', {}).get('fundus_std', [0.229, 0.184, 0.134])
    else:
        mean = [0.485, 0.456, 0.406]
        std = [0.229, 0.224, 0.225]
    
    base_transform = A.Compose([
        A.Resize(image_size, image_size),
        A.Normalize(mean=mean, std=std),
        ToTensorV2()
    ])
    
    tta_transforms = [base_transform]  # Original
    
    if n_augments >= 2:
        # Horizontal flip
        tta_transforms.append(A.Compose([
            A.Resize(image_size, image_size),
            A.HorizontalFlip(p=1.0),
            A.Normalize(mean=mean, std=std),
            ToTensorV2()
        ]))
    
    if n_augments >= 3:
        # Vertical flip
        tta_transforms.append(A.Compose([
            A.Resize(image_size, image_size),
            A.VerticalFlip(p=1.0),
            A.Normalize(mean=mean, std=std),
            ToTensorV2()
        ]))
    
    if n_augments >= 4:
        # Rotate 90
        tta_transforms.append(A.Compose([
            A.Resize(image_size, image_size),
            A.Rotate(limit=(90, 90), p=1.0),
            A.Normalize(mean=mean, std=std),
            ToTensorV2()
        ]))
    
    if n_augments >= 5:
        # Slight brightness adjustment
        tta_transforms.append(A.Compose([
            A.Resize(image_size, image_size),
            A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=1.0),
            A.Normalize(mean=mean, std=std),
            ToTensorV2()
        ]))
    
    return tta_transforms
