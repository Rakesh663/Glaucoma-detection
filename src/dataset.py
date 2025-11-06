"""
Dataset loader for glaucoma detection
"""
import os
import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import albumentations as A
from albumentations.pytorch import ToTensorV2
import numpy as np


class GlaucomaDataset(Dataset):
    """Dataset for glaucoma detection"""
    
    def __init__(self, data_dir, transform=None, image_size=640):
        self.data_dir = data_dir
        self.transform = transform
        self.image_size = image_size
        
        self.samples = []
        self.class_names = ['normal', 'glaucoma']
        
        for class_idx, class_name in enumerate(self.class_names):
            class_dir = os.path.join(data_dir, class_name)
            
            if not os.path.exists(class_dir):
                print(f"Warning: Directory not found: {class_dir}")
                continue
            
            for img_name in os.listdir(class_dir):
                if img_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    img_path = os.path.join(class_dir, img_name)
                    self.samples.append({
                        'path': img_path,
                        'label': class_idx,
                        'class_name': class_name
                    })
        
        print(f"Loaded {len(self.samples)} images from {data_dir}")
        if len(self.samples) > 0:
            class_counts = {}
            for sample in self.samples:
                class_name = sample['class_name']
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
            print(f"Class distribution: {class_counts}")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        sample = self.samples[idx]
        image = Image.open(sample['path']).convert('RGB')
        image = np.array(image)
        
        if self.transform:
            augmented = self.transform(image=image)
            image = augmented['image']
        else:
            basic_transform = A.Compose([
                A.Resize(self.image_size, self.image_size),
                A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ToTensorV2()
            ])
            augmented = basic_transform(image=image)
            image = augmented['image']
        
        label = torch.tensor(sample['label'], dtype=torch.float32)
        return image, label


def get_train_transform(config):
    """Get training augmentation pipeline - Production grade"""
    aug_config = config['augmentation']
    image_size = config['data']['image_size']
    
    return A.Compose([
        A.Resize(image_size, image_size),
        A.HorizontalFlip(p=aug_config['horizontal_flip']),
        A.VerticalFlip(p=aug_config['vertical_flip']),
        A.Rotate(limit=aug_config['rotation_limit'], p=0.5),
        A.RandomBrightnessContrast(
            brightness_limit=aug_config['brightness_limit'],
            contrast_limit=aug_config['contrast_limit'],
            p=0.6
        ),
        A.OneOf([
            A.GaussianBlur(blur_limit=aug_config['blur_limit'], p=1.0),
            A.MedianBlur(blur_limit=5, p=1.0),
            A.MotionBlur(p=1.0),
        ], p=0.4),
        A.CLAHE(clip_limit=2.0, p=0.4),
        A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.3),
        A.GaussNoise(var_limit=(10.0, 50.0), p=0.3),
        A.Normalize(
            mean=aug_config['normalize']['mean'],
            std=aug_config['normalize']['std']
        ),
        ToTensorV2()
    ])


def get_val_transform(config):
    """Get validation/test transform"""
    aug_config = config['augmentation']
    image_size = config['data']['image_size']
    
    return A.Compose([
        A.Resize(image_size, image_size),
        A.Normalize(
            mean=aug_config['normalize']['mean'],
            std=aug_config['normalize']['std']
        ),
        ToTensorV2()
    ])


def create_dataloaders(config):
    """Create train, validation, and test dataloaders"""
    batch_size = config['training']['batch_size']
    num_workers = config['data']['num_workers']
    
    train_dataset = GlaucomaDataset(
        data_dir=config['data']['train_dir'],
        transform=get_train_transform(config),
        image_size=config['data']['image_size']
    )
    
    val_dataset = GlaucomaDataset(
        data_dir=config['data']['val_dir'],
        transform=get_val_transform(config),
        image_size=config['data']['image_size']
    )
    
    test_dataset = GlaucomaDataset(
        data_dir=config['data']['test_dir'],
        transform=get_val_transform(config),
        image_size=config['data']['image_size']
    )
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=False
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