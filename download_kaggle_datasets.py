"""
Kaggle Dataset Downloader for Glaucoma Detection
Downloads additional training data from Kaggle

AVAILABLE DATASETS:
1. arnavjain1/glaucoma-datasets - Combined (Drishti-GS + RIM-ONE + ACRIMA)
2. sshikamaru/glaucoma-detection - SMDG PyTorch format
3. andrewmvd/glaucoma-fundus-imaging-datasets - ORIGA + REFUGE + G1020
4. abcdefgh14/glaucoma-dataset - Balanced dataset

SETUP:
1. Install Kaggle CLI: pip install kaggle
2. Get API key from kaggle.com -> Account -> Create New API Token
3. Save kaggle.json to C:/Users/<USERNAME>/.kaggle/kaggle.json
4. Run: python download_kaggle_datasets.py --dataset all

Usage:
    python download_kaggle_datasets.py --list
    python download_kaggle_datasets.py --dataset glaucoma-combined
    python download_kaggle_datasets.py --dataset all
"""

import os
import sys
import subprocess
import zipfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import argparse


# Kaggle datasets with glaucoma data
KAGGLE_DATASETS = {
    'glaucoma-combined': {
        'kaggle_id': 'arnavjain1/glaucoma-datasets',
        'name': 'Combined Glaucoma Dataset',
        'description': 'Drishti-GS (101 images) + RIM-ONE DL (485 images) + ACRIMA (705 images)',
        'size': '~1290 images',
        'structure': {
            'glaucoma_folders': ['Drishti-GS1/Glaucoma', 'RIM-ONE_DL/Glaucoma', 'ACRIMA/Glaucomatous'],
            'normal_folders': ['Drishti-GS1/Normal', 'RIM-ONE_DL/Normal', 'ACRIMA/Normal']
        }
    },
    'smdg-pytorch': {
        'kaggle_id': 'sshikamaru/glaucoma-detection',
        'name': 'SMDG PyTorch Format',
        'description': 'Pre-formatted dataset ready for PyTorch training',
        'size': '~2000+ images',
        'structure': {
            'glaucoma_folders': ['train/Glaucoma Present', 'val/Glaucoma Present'],
            'normal_folders': ['train/Glaucoma Not Present', 'val/Glaucoma Not Present']
        }
    },
    'glaucoma-fundus': {
        'kaggle_id': 'andrewmvd/glaucoma-fundus-imaging-datasets',
        'name': 'ORIGA + REFUGE + G1020',
        'description': 'Three major datasets with segmentation masks',
        'size': '~2870 images',
        'structure': {
            'glaucoma_folders': ['ORIGA/glaucoma', 'REFUGE/glaucoma', 'G1020/glaucoma'],
            'normal_folders': ['ORIGA/normal', 'REFUGE/normal', 'G1020/normal']
        }
    },
    'balanced-glaucoma': {
        'kaggle_id': 'abcdefgh14/glaucoma-dataset',
        'name': 'Balanced Glaucoma Dataset',
        'description': 'Curated balanced dataset for training',
        'size': '~1000 images',
        'structure': {
            'glaucoma_folders': ['glaucoma'],
            'normal_folders': ['normal']
        }
    }
}


class KaggleDownloader:
    """Downloads and integrates Kaggle datasets."""
    
    def __init__(
        self,
        data_dir: str = "data",
        downloads_dir: str = "data/kaggle_downloads"
    ):
        self.data_dir = Path(data_dir)
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        
        # Check kaggle installation
        self._check_kaggle()
    
    def _check_kaggle(self):
        """Check if Kaggle CLI is installed and configured."""
        try:
            result = subprocess.run(
                ['kaggle', '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise Exception("Kaggle CLI not working")
            print(f"✅ Kaggle CLI: {result.stdout.strip()}")
        except FileNotFoundError:
            print("❌ Kaggle CLI not installed!")
            print("   Install with: pip install kaggle")
            print("   Get API key from: kaggle.com -> Account -> Create New API Token")
            print("   Save to: ~/.kaggle/kaggle.json")
            self.kaggle_available = False
            return
        
        # Check for API key
        kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
        if not kaggle_json.exists():
            # Try Windows path
            kaggle_json = Path(os.environ.get('USERPROFILE', '')) / ".kaggle" / "kaggle.json"
        
        if not kaggle_json.exists():
            print("⚠️ Kaggle API key not found!")
            print("   1. Go to kaggle.com -> Account -> Create New API Token")
            print(f"   2. Save kaggle.json to: {Path.home() / '.kaggle' / 'kaggle.json'}")
            self.kaggle_available = False
            return
        
        print(f"✅ Kaggle API key found: {kaggle_json}")
        self.kaggle_available = True
    
    def list_datasets(self):
        """List available datasets."""
        print("\n" + "=" * 70)
        print("📊 AVAILABLE KAGGLE DATASETS FOR GLAUCOMA")
        print("=" * 70)
        
        for key, info in KAGGLE_DATASETS.items():
            print(f"\n🔹 {info['name']}")
            print(f"   Key: {key}")
            print(f"   Kaggle ID: {info['kaggle_id']}")
            print(f"   Size: {info['size']}")
            print(f"   Description: {info['description']}")
        
        print("\n" + "=" * 70)
        print("📋 TO DOWNLOAD:")
        print("   python download_kaggle_datasets.py --dataset <key>")
        print("   python download_kaggle_datasets.py --dataset all")
        print("=" * 70)
    
    def download_dataset(self, dataset_key: str) -> bool:
        """
        Download a dataset from Kaggle.
        
        Args:
            dataset_key: Key of the dataset to download
            
        Returns:
            True if successful
        """
        if not self.kaggle_available:
            print("❌ Kaggle not available. Please install and configure.")
            return False
        
        if dataset_key not in KAGGLE_DATASETS:
            print(f"❌ Unknown dataset: {dataset_key}")
            print(f"   Available: {', '.join(KAGGLE_DATASETS.keys())}")
            return False
        
        info = KAGGLE_DATASETS[dataset_key]
        kaggle_id = info['kaggle_id']
        
        print(f"\n{'=' * 70}")
        print(f"📥 DOWNLOADING: {info['name']}")
        print(f"   From: kaggle.com/datasets/{kaggle_id}")
        print(f"{'=' * 70}")
        
        # Create dataset directory
        dataset_dir = self.downloads_dir / dataset_key
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # Download
        try:
            result = subprocess.run(
                ['kaggle', 'datasets', 'download', '-d', kaggle_id, '-p', str(dataset_dir), '--unzip'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Download failed: {result.stderr}")
                return False
            
            print(f"✅ Downloaded to: {dataset_dir}")
            return True
            
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def integrate_dataset(self, dataset_key: str, split_ratio: float = 0.85) -> Dict:
        """
        Integrate downloaded dataset into training data.
        
        Args:
            dataset_key: Key of the dataset
            split_ratio: Train/val split ratio
            
        Returns:
            Integration statistics
        """
        if dataset_key not in KAGGLE_DATASETS:
            print(f"❌ Unknown dataset: {dataset_key}")
            return {}
        
        info = KAGGLE_DATASETS[dataset_key]
        dataset_dir = self.downloads_dir / dataset_key
        
        if not dataset_dir.exists():
            print(f"❌ Dataset not downloaded: {dataset_dir}")
            print(f"   Run: python download_kaggle_datasets.py --dataset {dataset_key}")
            return {}
        
        print(f"\n{'=' * 70}")
        print(f"🔄 INTEGRATING: {info['name']}")
        print(f"{'=' * 70}")
        
        stats = {
            'dataset': dataset_key,
            'train_normal': 0,
            'train_glaucoma': 0,
            'val_normal': 0,
            'val_glaucoma': 0
        }
        
        structure = info.get('structure', {})
        
        # Process glaucoma images
        for folder in structure.get('glaucoma_folders', []):
            folder_path = dataset_dir / folder
            if folder_path.exists():
                stats = self._copy_images(folder_path, 'glaucoma', dataset_key, split_ratio, stats)
            else:
                # Try recursive search
                self._find_and_copy(dataset_dir, 'glaucoma', dataset_key, split_ratio, stats)
        
        # Process normal images
        for folder in structure.get('normal_folders', []):
            folder_path = dataset_dir / folder
            if folder_path.exists():
                stats = self._copy_images(folder_path, 'normal', dataset_key, split_ratio, stats)
            else:
                self._find_and_copy(dataset_dir, 'normal', dataset_key, split_ratio, stats)
        
        # Print summary
        print(f"\n{'=' * 70}")
        print("📊 INTEGRATION SUMMARY")
        print(f"{'=' * 70}")
        print(f"   Train Normal: {stats['train_normal']}")
        print(f"   Train Glaucoma: {stats['train_glaucoma']}")
        print(f"   Val Normal: {stats['val_normal']}")
        print(f"   Val Glaucoma: {stats['val_glaucoma']}")
        total = stats['train_normal'] + stats['train_glaucoma'] + stats['val_normal'] + stats['val_glaucoma']
        print(f"   TOTAL: {total} images added")
        print(f"{'=' * 70}")
        
        return stats
    
    def _copy_images(
        self,
        source_folder: Path,
        class_name: str,
        dataset_prefix: str,
        split_ratio: float,
        stats: Dict
    ) -> Dict:
        """Copy images from source folder to train/val."""
        import random
        
        # Get all images
        images = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff']:
            images.extend(source_folder.glob(ext))
            images.extend(source_folder.glob(ext.upper()))
        
        if not images:
            return stats
        
        print(f"   Found {len(images)} {class_name} images in {source_folder.name}")
        
        # Shuffle and split
        random.shuffle(images)
        split_idx = int(len(images) * split_ratio)
        
        train_images = images[:split_idx]
        val_images = images[split_idx:]
        
        # Copy to train
        train_dest = self.data_dir / "train" / class_name
        train_dest.mkdir(parents=True, exist_ok=True)
        
        for img in train_images:
            new_name = f"{dataset_prefix}_{img.name}"
            dest = train_dest / new_name
            if not dest.exists():
                shutil.copy2(img, dest)
                stats[f'train_{class_name}'] += 1
        
        # Copy to val
        val_dest = self.data_dir / "val" / class_name
        val_dest.mkdir(parents=True, exist_ok=True)
        
        for img in val_images:
            new_name = f"{dataset_prefix}_{img.name}"
            dest = val_dest / new_name
            if not dest.exists():
                shutil.copy2(img, dest)
                stats[f'val_{class_name}'] += 1
        
        return stats
    
    def _find_and_copy(
        self,
        base_dir: Path,
        target_class: str,
        dataset_prefix: str,
        split_ratio: float,
        stats: Dict
    ):
        """Recursively find and copy images matching class name."""
        class_variations = {
            'glaucoma': ['glaucoma', 'Glaucoma', 'GLAUCOMA', 'glaucomatous', 'Glaucomatous', 
                        'positive', 'Positive', '1', 'abnormal', 'Abnormal'],
            'normal': ['normal', 'Normal', 'NORMAL', 'healthy', 'Healthy', 
                      'negative', 'Negative', '0', 'non-glaucoma']
        }
        
        for folder in base_dir.rglob('*'):
            if folder.is_dir():
                folder_name = folder.name.lower()
                if any(v.lower() in folder_name for v in class_variations.get(target_class, [])):
                    self._copy_images(folder, target_class, dataset_prefix, split_ratio, stats)
    
    def download_all(self):
        """Download all available datasets."""
        for key in KAGGLE_DATASETS.keys():
            print(f"\n{'=' * 70}")
            self.download_dataset(key)
    
    def integrate_all(self):
        """Integrate all downloaded datasets."""
        for key in KAGGLE_DATASETS.keys():
            dataset_dir = self.downloads_dir / key
            if dataset_dir.exists():
                self.integrate_dataset(key)


def manual_download_instructions():
    """Print manual download instructions."""
    print("\n" + "=" * 70)
    print("📥 MANUAL DOWNLOAD INSTRUCTIONS")
    print("=" * 70)
    print("""
If Kaggle CLI is not working, you can download manually:

1. COMBINED DATASET (Recommended - 1290 images):
   URL: https://www.kaggle.com/datasets/arnavjain1/glaucoma-datasets
   - Click "Download" button
   - Extract to: data/kaggle_downloads/glaucoma-combined/
   - Run: python download_kaggle_datasets.py --integrate glaucoma-combined

2. SMDG PYTORCH FORMAT (2000+ images):
   URL: https://www.kaggle.com/datasets/sshikamaru/glaucoma-detection
   - Click "Download" button
   - Extract to: data/kaggle_downloads/smdg-pytorch/
   - Run: python download_kaggle_datasets.py --integrate smdg-pytorch

3. ORIGA + REFUGE + G1020 (2870 images):
   URL: https://www.kaggle.com/datasets/andrewmvd/glaucoma-fundus-imaging-datasets
   - Click "Download" button
   - Extract to: data/kaggle_downloads/glaucoma-fundus/
   - Run: python download_kaggle_datasets.py --integrate glaucoma-fundus

After downloading, your folder structure should look like:
data/
  kaggle_downloads/
    glaucoma-combined/
      Drishti-GS1/
      RIM-ONE_DL/
      ACRIMA/
    smdg-pytorch/
      train/
      val/
    glaucoma-fundus/
      ORIGA/
      REFUGE/
      G1020/
""")


def main():
    parser = argparse.ArgumentParser(description="Download Kaggle glaucoma datasets")
    parser.add_argument('--list', action='store_true',
                        help="List available datasets")
    parser.add_argument('--dataset', type=str,
                        help="Dataset to download (or 'all')")
    parser.add_argument('--integrate', type=str,
                        help="Integrate downloaded dataset (or 'all')")
    parser.add_argument('--manual', action='store_true',
                        help="Show manual download instructions")
    
    args = parser.parse_args()
    
    downloader = KaggleDownloader()
    
    if args.list:
        downloader.list_datasets()
    elif args.manual:
        manual_download_instructions()
    elif args.dataset:
        if args.dataset == 'all':
            downloader.download_all()
            downloader.integrate_all()
        else:
            if downloader.download_dataset(args.dataset):
                downloader.integrate_dataset(args.dataset)
    elif args.integrate:
        if args.integrate == 'all':
            downloader.integrate_all()
        else:
            downloader.integrate_dataset(args.integrate)
    else:
        parser.print_help()
        print("\n💡 Quick start:")
        print("   python download_kaggle_datasets.py --list")
        print("   python download_kaggle_datasets.py --dataset glaucoma-combined")


if __name__ == "__main__":
    main()
