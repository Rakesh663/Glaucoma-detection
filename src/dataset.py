"""
Clinical-Grade Dataset Loader for Glaucoma Detection
Integrates fundus-specific preprocessing and heavy augmentation

Key Features:
1. Fundus-specific normalization (not ImageNet)
2. Clinical preprocessing pipeline
3. Heavy augmentation for small datasets
4. Quality filtering option
"""

import os
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import numpy as np
from typing import Dict, Optional, Tuple, List
import warnings

# Albumentations imports
import albumentations as A
from albumentations.pytorch import ToTensorV2

# Import clinical preprocessing
try:
    from preprocessing import (
        FundusPreprocessor,
        QualityAssessor,
        get_clinical_train_transform,
        get_clinical_val_transform
    )
    HAS_CLINICAL_PREPROCESSING = True
except ImportError:
    HAS_CLINICAL_PREPROCESSING = False
    warnings.warn("Clinical preprocessing not available. Using basic transforms.")


# Fundus-specific normalization statistics
# Computed from EyePACS, ACRIMA, and ORIGA datasets
FUNDUS_MEAN = [0.485, 0.285, 0.156]
FUNDUS_STD = [0.229, 0.184, 0.134]

# ImageNet statistics (for comparison/fallback)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


class GlaucomaDataset(Dataset):
    """
    Clinical-grade dataset for glaucoma detection.
    
    Features:
    - Fundus-specific preprocessing
    - Quality-based filtering
    - Efficient data loading
    """
    
    def __init__(
        self,
        data_dir: str,
        transform=None,
        image_size: int = 512,
        apply_preprocessing: bool = True,
        quality_filter: bool = False,
        quality_threshold: float = 0.5,
        return_metadata: bool = False
    ):
        """
        Initialize dataset.
        
        Args:
            data_dir: Path to data directory
            transform: Albumentations transform pipeline
            image_size: Target image size
            apply_preprocessing: Apply fundus preprocessing
            quality_filter: Filter out low-quality images
            quality_threshold: Minimum quality score
            return_metadata: Return additional metadata with samples
        """
        self.data_dir = data_dir
        self.transform = transform
        self.image_size = image_size
        self.apply_preprocessing = apply_preprocessing
        self.quality_filter = quality_filter
        self.quality_threshold = quality_threshold
        self.return_metadata = return_metadata
        
        self.samples = []
        self.class_names = ['normal', 'glaucoma']
        self.class_to_idx = {name: idx for idx, name in enumerate(self.class_names)}
        
        # Initialize preprocessor
        if self.apply_preprocessing and HAS_CLINICAL_PREPROCESSING:
            self.preprocessor = FundusPreprocessor(
                target_size=(image_size, image_size),
                apply_clahe=True,
                clahe_clip_limit=3.0,
                enhance_green_channel=True,
                crop_to_roi=True,
                illumination_correction=True,
                normalize_output=False  # We'll normalize in transform
            )
            self.quality_assessor = QualityAssessor()
        else:
            self.preprocessor = None
            self.quality_assessor = None
        
        # Load samples
        self._load_samples()
        
        # Print dataset info
        self._print_info()
    
    def _load_samples(self):
        """Load and validate image samples."""
        for class_idx, class_name in enumerate(self.class_names):
            class_dir = os.path.join(self.data_dir, class_name)
            
            if not os.path.exists(class_dir):
                warnings.warn(f"Directory not found: {class_dir}")
                continue
            
            for img_name in os.listdir(class_dir):
                if not img_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                    continue
                
                img_path = os.path.join(class_dir, img_name)
                
                sample = {
                    'path': img_path,
                    'label': class_idx,
                    'class_name': class_name,
                    'filename': img_name
                }
                
                # Optional quality filtering
                if self.quality_filter and self.quality_assessor is not None:
                    try:
                        image = Image.open(img_path).convert('RGB')
                        quality_report = self.quality_assessor.assess(np.array(image))
                        
                        if quality_report.overall_score < self.quality_threshold:
                            continue  # Skip low-quality images
                        
                        sample['quality_score'] = quality_report.overall_score
                    except Exception as e:
                        warnings.warn(f"Quality check failed for {img_path}: {e}")
                
                self.samples.append(sample)
    
    def _print_info(self):
        """Print dataset information."""
        total = len(self.samples)
        if total == 0:
            print(f"⚠️ No images loaded from {self.data_dir}")
            return
        
        print(f"\n📁 Loaded {total} images from {self.data_dir}")
        
        # Class distribution
        class_counts = {}
        for sample in self.samples:
            class_name = sample['class_name']
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        print("📊 Class distribution:")
        for class_name, count in class_counts.items():
            pct = (count / total) * 100
            print(f"   {class_name}: {count} ({pct:.1f}%)")
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int):
        """
        Get a sample.
        
        Returns:
            Tuple of (image_tensor, label) or
            Tuple of (image_tensor, label, metadata) if return_metadata=True
        """
        sample = self.samples[idx]
        
        # Load image
        image = Image.open(sample['path']).convert('RGB')
        image = np.array(image)
        
        # Apply fundus preprocessing
        if self.preprocessor is not None:
            try:
                image = self.preprocessor(image)
                # Convert back to uint8 for albumentations
                if image.dtype == np.float32:
                    image = (image * 255).astype(np.uint8)
            except Exception as e:
                warnings.warn(f"Preprocessing failed for {sample['path']}: {e}")
        
        # Apply augmentation/transform
        if self.transform is not None:
            augmented = self.transform(image=image)
            image = augmented['image']
        else:
            # Basic transform if none provided
            transform = A.Compose([
                A.Resize(self.image_size, self.image_size),
                A.Normalize(mean=FUNDUS_MEAN, std=FUNDUS_STD),
                ToTensorV2()
            ])
            augmented = transform(image=image)
            image = augmented['image']
        
        # Label
        label = torch.tensor(sample['label'], dtype=torch.float32)
        
        if self.return_metadata:
            metadata = {
                'path': sample['path'],
                'filename': sample['filename'],
                'class_name': sample['class_name']
            }
            return image, label, metadata
        
        return image, label
    
    def get_class_weights(self) -> torch.Tensor:
        """
        Get class weights for handling imbalanced data.
        
        Returns:
            Tensor of class weights
        """
        class_counts = [0] * len(self.class_names)
        
        for sample in self.samples:
            class_counts[sample['label']] += 1
        
        total = sum(class_counts)
        weights = [total / (len(self.class_names) * count) for count in class_counts]
        
        return torch.tensor(weights, dtype=torch.float32)


def get_train_transform(config: Dict) -> A.Compose:
    """
    Get training augmentation pipeline.
    Uses clinical augmentation if available.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Albumentations Compose pipeline
    """
    if HAS_CLINICAL_PREPROCESSING:
        return get_clinical_train_transform(config)
    
    # Fallback to basic augmentation
    image_size = config['data']['image_size']
    aug_config = config.get('augmentation', {})
    
    # Use fundus normalization
    norm_type = config.get('normalization', {}).get('type', 'fundus')
    if norm_type == 'fundus':
        mean = FUNDUS_MEAN
        std = FUNDUS_STD
    else:
        mean = IMAGENET_MEAN
        std = IMAGENET_STD
    
    return A.Compose([
        A.Resize(image_size, image_size),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.5),
        A.Rotate(limit=20, p=0.5),
        A.RandomBrightnessContrast(brightness_limit=0.3, contrast_limit=0.3, p=0.6),
        A.OneOf([
            A.GaussianBlur(blur_limit=5, p=1.0),
            A.MedianBlur(blur_limit=5, p=1.0),
            A.MotionBlur(p=1.0),
        ], p=0.4),
        A.CLAHE(clip_limit=2.0, p=0.4),
        A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.3),
        A.GaussNoise(var_limit=(10.0, 50.0), p=0.3),
        A.Normalize(mean=mean, std=std),
        ToTensorV2()
    ])


def get_val_transform(config: Dict) -> A.Compose:
    """
    Get validation/test transform (no augmentation).
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Albumentations Compose pipeline
    """
    if HAS_CLINICAL_PREPROCESSING:
        return get_clinical_val_transform(config)
    
    image_size = config['data']['image_size']
    
    norm_type = config.get('normalization', {}).get('type', 'fundus')
    if norm_type == 'fundus':
        mean = FUNDUS_MEAN
        std = FUNDUS_STD
    else:
        mean = IMAGENET_MEAN
        std = IMAGENET_STD
    
    return A.Compose([
        A.Resize(image_size, image_size),
        A.Normalize(mean=mean, std=std),
        ToTensorV2()
    ])


def create_dataloaders(config: Dict) -> Dict[str, DataLoader]:
    """
    Create train, validation, and test dataloaders.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dict with 'train', 'val', 'test' dataloaders
    """
    batch_size = config['training']['batch_size']
    num_workers = config['data'].get('num_workers', 4)
    apply_preprocessing = config.get('preprocessing', {}).get('enabled', True)
    
    # Create datasets
    train_dataset = GlaucomaDataset(
        data_dir=config['data']['train_dir'],
        transform=get_train_transform(config),
        image_size=config['data']['image_size'],
        apply_preprocessing=apply_preprocessing,
        quality_filter=False  # Don't filter training data
    )
    
    val_dataset = GlaucomaDataset(
        data_dir=config['data']['val_dir'],
        transform=get_val_transform(config),
        image_size=config['data']['image_size'],
        apply_preprocessing=apply_preprocessing,
        quality_filter=False
    )
    
    test_dataset = GlaucomaDataset(
        data_dir=config['data']['test_dir'],
        transform=get_val_transform(config),
        image_size=config['data']['image_size'],
        apply_preprocessing=apply_preprocessing,
        quality_filter=False
    )
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=True  # Important for batch normalization
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=False
    )
    
    return {
        'train': train_loader,
        'val': val_loader,
        'test': test_loader
    }


class MixUpDataset(Dataset):
    """
    Dataset wrapper that applies MixUp and CutMix augmentation.
    Critical for small datasets.
    """
    
    def __init__(
        self,
        dataset: Dataset,
        mixup_alpha: float = 0.4,
        cutmix_alpha: float = 1.0,
        mixup_prob: float = 0.3,
        cutmix_prob: float = 0.3
    ):
        self.dataset = dataset
        self.mixup_alpha = mixup_alpha
        self.cutmix_alpha = cutmix_alpha
        self.mixup_prob = mixup_prob
        self.cutmix_prob = cutmix_prob
    
    def __len__(self):
        return len(self.dataset)
    
    def __getitem__(self, idx):
        image1, label1 = self.dataset[idx]
        
        # Decide augmentation type
        rand = np.random.random()
        
        if rand < self.mixup_prob:
            # MixUp
            idx2 = np.random.randint(len(self.dataset))
            image2, label2 = self.dataset[idx2]
            
            lam = np.random.beta(self.mixup_alpha, self.mixup_alpha)
            image = lam * image1 + (1 - lam) * image2
            label = lam * label1 + (1 - lam) * label2
            
            return image, label
        
        elif rand < self.mixup_prob + self.cutmix_prob:
            # CutMix
            idx2 = np.random.randint(len(self.dataset))
            image2, label2 = self.dataset[idx2]
            
            lam = np.random.beta(self.cutmix_alpha, self.cutmix_alpha)
            
            # Get image dimensions
            _, h, w = image1.shape
            
            # Random box
            cut_ratio = np.sqrt(1 - lam)
            cut_h = int(h * cut_ratio)
            cut_w = int(w * cut_ratio)
            
            cx = np.random.randint(w)
            cy = np.random.randint(h)
            
            x1 = np.clip(cx - cut_w // 2, 0, w)
            y1 = np.clip(cy - cut_h // 2, 0, h)
            x2 = np.clip(cx + cut_w // 2, 0, w)
            y2 = np.clip(cy + cut_h // 2, 0, h)
            
            # Apply CutMix
            image = image1.clone()
            image[:, y1:y2, x1:x2] = image2[:, y1:y2, x1:x2]
            
            # Adjust label
            lam_adjusted = 1 - ((x2 - x1) * (y2 - y1) / (h * w))
            label = lam_adjusted * label1 + (1 - lam_adjusted) * label2
            
            return image, label
        
        return image1, label1