"""
Dataset Expansion Script
Fetches and integrates additional public glaucoma datasets for training

Available Public Datasets:
1. ORIGA (Online Retinal fundus Image database for Glaucoma Analysis)
2. REFUGE (Retinal Fundus Glaucoma Challenge)
3. RIM-ONE (Retinal Image database for Optic Nerve Evaluation)
4. Drishti-GS (Glaucoma Screening dataset)
5. HRF (High-Resolution Fundus)
6. MESSIDOR (for additional fundus variety)

Usage:
    python expand_dataset.py --list              # List available datasets
    python expand_dataset.py --download refuge   # Download REFUGE dataset
    python expand_dataset.py --integrate all     # Integrate all downloaded data
"""

import os
import sys
import shutil
import argparse
import requests
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from tqdm import tqdm
import json


# Public glaucoma datasets with download information
AVAILABLE_DATASETS = {
    'origa': {
        'name': 'ORIGA - Online Retinal fundus Image database',
        'size': '~650 images',
        'url_info': 'https://origa.ipal.cnrs.fr/',
        'requires_registration': True,
        'labels': ['normal', 'glaucoma'],
        'description': 'High-quality fundus images with glaucoma labels'
    },
    'refuge': {
        'name': 'REFUGE - Retinal Fundus Glaucoma Challenge',
        'size': '~1200 images',
        'url_info': 'https://refuge.grand-challenge.org/',
        'requires_registration': True,
        'labels': ['normal', 'glaucoma'],
        'description': 'Challenge dataset with segmentation and classification labels'
    },
    'rim_one': {
        'name': 'RIM-ONE - Retinal Image database for Optic Nerve Evaluation',
        'size': '~455 images',
        'url_info': 'http://medimrg.webs.ull.es/research/rim-one/',
        'requires_registration': False,
        'labels': ['normal', 'glaucoma'],
        'description': 'Multiple versions (r1, r2, r3, DL) available'
    },
    'drishti_gs': {
        'name': 'Drishti-GS - Glaucoma Screening dataset',
        'size': '~101 images',
        'url_info': 'https://cvit.iiit.ac.in/projects/mip/drishti-gs/',
        'requires_registration': False,
        'labels': ['normal', 'glaucoma'],
        'description': 'Indian population fundus images'
    },
    'hrf': {
        'name': 'HRF - High-Resolution Fundus images',
        'size': '~45 images',
        'url_info': 'https://www5.cs.fau.de/research/data/fundus-images/',
        'requires_registration': False,
        'labels': ['healthy', 'glaucoma', 'diabetic_retinopathy'],
        'description': 'Very high resolution fundus images'
    },
    'g1020': {
        'name': 'G1020 - Glaucoma dataset with 1020 images',
        'size': '~1020 images',
        'url_info': 'https://www.kaggle.com/datasets/arnavjain1/glaucoma-datasets',
        'requires_registration': True,
        'labels': ['normal', 'glaucoma'],
        'description': 'Kaggle dataset with balanced classes'
    },
    'eyepacs': {
        'name': 'EyePACS - Diabetic Retinopathy Detection',
        'size': '~35000 images',
        'url_info': 'https://www.kaggle.com/c/diabetic-retinopathy-detection',
        'requires_registration': True,
        'labels': ['0', '1', '2', '3', '4'],
        'description': 'Large dataset for general fundus understanding'
    }
}


class DatasetExpander:
    """
    Manages downloading and integrating external datasets.
    """
    
    def __init__(
        self,
        data_dir: str = "data",
        downloads_dir: str = "data/downloads",
        external_dir: str = "data/external"
    ):
        """
        Initialize dataset expander.
        
        Args:
            data_dir: Main data directory
            downloads_dir: Where to store downloads
            external_dir: Where to extract external datasets
        """
        self.data_dir = Path(data_dir)
        self.downloads_dir = Path(downloads_dir)
        self.external_dir = Path(external_dir)
        
        # Create directories
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.external_dir.mkdir(parents=True, exist_ok=True)
        
        # Track integrated datasets
        self.integration_log = self.data_dir / "dataset_integration.json"
    
    def list_datasets(self):
        """Print available datasets."""
        print("\n" + "=" * 70)
        print("📊 AVAILABLE PUBLIC GLAUCOMA DATASETS")
        print("=" * 70)
        
        for key, info in AVAILABLE_DATASETS.items():
            print(f"\n🔹 {info['name']}")
            print(f"   Key: {key}")
            print(f"   Size: {info['size']}")
            print(f"   Labels: {', '.join(info['labels'])}")
            print(f"   URL: {info['url_info']}")
            print(f"   Registration Required: {'Yes' if info['requires_registration'] else 'No'}")
            print(f"   Description: {info['description']}")
        
        print("\n" + "=" * 70)
        print("📋 HOW TO ADD DATASETS:")
        print("=" * 70)
        print("""
1. MANUAL DOWNLOAD (Recommended):
   - Visit the dataset URL above
   - Register if required and download
   - Extract to: data/external/<dataset_name>/
   - Run: python expand_dataset.py --integrate <dataset_name>

2. KAGGLE DATASETS:
   - Install Kaggle CLI: pip install kaggle
   - Set up API key: ~/.kaggle/kaggle.json
   - Download: kaggle datasets download -d <dataset>
   - Extract to: data/external/<dataset_name>/
   - Run: python expand_dataset.py --integrate <dataset_name>

3. IMPORT FROM FOLDER:
   - Place your images in a folder with structure:
     /your_folder/
       /glaucoma/    (glaucoma images)
       /normal/      (normal images)
   - Run: python expand_dataset.py --import_folder /path/to/your_folder
""")
    
    def import_from_folder(
        self,
        source_folder: str,
        dataset_name: str = "custom",
        split_ratio: float = 0.8  # 80% train, 20% val
    ) -> Dict:
        """
        Import images from an external folder.
        
        Args:
            source_folder: Folder with images organized by class
            dataset_name: Name for this dataset
            split_ratio: Train/val split ratio
            
        Returns:
            Dict with import statistics
        """
        source = Path(source_folder)
        
        print(f"\n{'=' * 70}")
        print(f"📁 IMPORTING DATASET: {dataset_name}")
        print(f"   Source: {source}")
        print(f"{'=' * 70}")
        
        stats = {
            'dataset': dataset_name,
            'source': str(source),
            'train_normal': 0,
            'train_glaucoma': 0,
            'val_normal': 0,
            'val_glaucoma': 0
        }
        
        # Detect class folders
        class_mappings = {
            'normal': ['normal', 'healthy', 'non-glaucoma', 'nonglaucoma', 'negative', '0'],
            'glaucoma': ['glaucoma', 'glaucomatous', 'positive', '1', 'abnormal']
        }
        
        for target_class, possible_names in class_mappings.items():
            # Find matching folder
            source_class_folder = None
            for name in possible_names:
                candidate = source / name
                if candidate.exists():
                    source_class_folder = candidate
                    break
                # Case-insensitive search
                for item in source.iterdir():
                    if item.is_dir() and item.name.lower() == name.lower():
                        source_class_folder = item
                        break
                if source_class_folder:
                    break
            
            if source_class_folder is None:
                print(f"⚠️ No folder found for class: {target_class}")
                continue
            
            # Get all images
            image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff', '*.tif']:
                image_files.extend(source_class_folder.glob(ext))
                image_files.extend(source_class_folder.glob(ext.upper()))
            
            print(f"📊 Found {len(image_files)} {target_class} images")
            
            # Split into train/val
            import random
            random.shuffle(image_files)
            split_idx = int(len(image_files) * split_ratio)
            
            train_files = image_files[:split_idx]
            val_files = image_files[split_idx:]
            
            # Copy to train
            train_dest = self.data_dir / "train" / target_class
            train_dest.mkdir(parents=True, exist_ok=True)
            
            for f in tqdm(train_files, desc=f"Copying {target_class} to train"):
                # Add dataset prefix to avoid conflicts
                new_name = f"{dataset_name}_{f.name}"
                dest = train_dest / new_name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    stats[f'train_{target_class}'] += 1
            
            # Copy to val
            val_dest = self.data_dir / "val" / target_class
            val_dest.mkdir(parents=True, exist_ok=True)
            
            for f in tqdm(val_files, desc=f"Copying {target_class} to val"):
                new_name = f"{dataset_name}_{f.name}"
                dest = val_dest / new_name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    stats[f'val_{target_class}'] += 1
        
        # Save integration log
        self._update_integration_log(stats)
        
        # Print summary
        print(f"\n{'=' * 70}")
        print("📊 IMPORT SUMMARY")
        print(f"{'=' * 70}")
        print(f"   Train Normal: {stats['train_normal']}")
        print(f"   Train Glaucoma: {stats['train_glaucoma']}")
        print(f"   Val Normal: {stats['val_normal']}")
        print(f"   Val Glaucoma: {stats['val_glaucoma']}")
        total = sum([stats['train_normal'], stats['train_glaucoma'],
                     stats['val_normal'], stats['val_glaucoma']])
        print(f"   TOTAL: {total} images added")
        print(f"{'=' * 70}")
        
        return stats
    
    def integrate_dataset(self, dataset_key: str) -> Dict:
        """
        Integrate a downloaded dataset.
        
        Args:
            dataset_key: Key of the dataset to integrate
            
        Returns:
            Integration statistics
        """
        if dataset_key not in AVAILABLE_DATASETS:
            print(f"❌ Unknown dataset: {dataset_key}")
            print(f"   Available: {', '.join(AVAILABLE_DATASETS.keys())}")
            return {}
        
        # Check if downloaded
        dataset_folder = self.external_dir / dataset_key
        if not dataset_folder.exists():
            print(f"❌ Dataset not found: {dataset_folder}")
            print(f"   Please download it first and extract to: {dataset_folder}")
            return {}
        
        return self.import_from_folder(
            source_folder=str(dataset_folder),
            dataset_name=dataset_key
        )
    
    def _update_integration_log(self, stats: Dict):
        """Update integration log file."""
        existing = []
        if self.integration_log.exists():
            with open(self.integration_log, 'r') as f:
                existing = json.load(f)
        
        stats['timestamp'] = datetime.now().isoformat()
        existing.append(stats)
        
        with open(self.integration_log, 'w') as f:
            json.dump(existing, f, indent=2)
    
    def show_current_data_stats(self):
        """Show statistics of current training data."""
        print("\n" + "=" * 70)
        print("📊 CURRENT DATASET STATISTICS")
        print("=" * 70)
        
        for split in ['train', 'val', 'test']:
            split_dir = self.data_dir / split
            if not split_dir.exists():
                continue
            
            print(f"\n📁 {split.upper()}:")
            for class_name in ['normal', 'glaucoma']:
                class_dir = split_dir / class_name
                if class_dir.exists():
                    count = len(list(class_dir.glob('*')))
                    print(f"   {class_name}: {count} images")
        
        # Check integration log
        if self.integration_log.exists():
            print(f"\n📋 Integration History:")
            with open(self.integration_log, 'r') as f:
                history = json.load(f)
            for entry in history[-5:]:  # Last 5 entries
                print(f"   - {entry.get('dataset', 'unknown')} @ {entry.get('timestamp', 'unknown')}")
        
        print("=" * 70)


def download_sample_augmentation_images():
    """
    Create synthetic variations of existing images to increase dataset.
    This is a fallback when external datasets aren't available.
    """
    print("\n🔄 Generating synthetic augmentations...")
    print("   This creates additional training data from existing images.")
    
    # Import augmentation utilities
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    
    try:
        from preprocessing.clinical_augmentation import ClinicalAugmentation
        from preprocessing.fundus_preprocessing import FundusPreprocessor
        from PIL import Image
        import numpy as np
        
        augmentor = ClinicalAugmentation(
            apply_camera_sim=True,
            apply_lighting_var=True,
            apply_motion_blur=True,
            apply_dust_artifacts=True
        )
        
        data_dir = Path("data/train")
        augmented_count = 0
        
        for class_name in ['normal', 'glaucoma']:
            class_dir = data_dir / class_name
            if not class_dir.exists():
                continue
            
            images = list(class_dir.glob('*.jpg')) + list(class_dir.glob('*.png'))
            
            for img_path in tqdm(images[:50], desc=f"Augmenting {class_name}"):
                try:
                    img = Image.open(img_path).convert('RGB')
                    img_np = np.array(img)
                    
                    # Generate 2 augmented versions
                    for i in range(2):
                        aug_img = augmentor.augment(img_np)
                        aug_img_pil = Image.fromarray((aug_img * 255).astype(np.uint8))
                        
                        # Save with augmentation suffix
                        base_name = img_path.stem
                        new_name = f"{base_name}_aug{i+1}.jpg"
                        aug_img_pil.save(class_dir / new_name, quality=95)
                        augmented_count += 1
                except Exception as e:
                    print(f"⚠️ Failed to augment {img_path}: {e}")
        
        print(f"✅ Generated {augmented_count} augmented images")
        
    except Exception as e:
        print(f"❌ Augmentation failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Expand training dataset with public data")
    parser.add_argument('--list', action='store_true',
                        help="List available public datasets")
    parser.add_argument('--stats', action='store_true',
                        help="Show current dataset statistics")
    parser.add_argument('--integrate', type=str,
                        help="Integrate a downloaded dataset by key")
    parser.add_argument('--import_folder', type=str,
                        help="Import images from a folder")
    parser.add_argument('--dataset_name', type=str, default='custom',
                        help="Name for imported dataset")
    parser.add_argument('--generate_augmented', action='store_true',
                        help="Generate augmented versions of existing images")
    
    args = parser.parse_args()
    
    expander = DatasetExpander()
    
    if args.list:
        expander.list_datasets()
    elif args.stats:
        expander.show_current_data_stats()
    elif args.integrate:
        if args.integrate == 'all':
            for key in AVAILABLE_DATASETS.keys():
                expander.integrate_dataset(key)
        else:
            expander.integrate_dataset(args.integrate)
    elif args.import_folder:
        expander.import_from_folder(
            source_folder=args.import_folder,
            dataset_name=args.dataset_name
        )
    elif args.generate_augmented:
        download_sample_augmentation_images()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
