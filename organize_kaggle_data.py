"""
Organize Downloaded Kaggle Datasets
Reads CSV labels and organizes images into train/val folders
"""

import os
import shutil
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import random


def organize_g1020(source_dir: Path, target_dir: Path, split_ratio: float = 0.85):
    """Organize G1020 dataset using CSV labels."""
    csv_path = source_dir / "G1020.csv"
    images_dir = source_dir / "Images_Square"  # Use square cropped images
    
    if not csv_path.exists():
        print(f"⚠️ G1020 CSV not found: {csv_path}")
        return 0
    
    # Read labels
    df = pd.read_csv(csv_path)
    print(f"📊 G1020: {len(df)} images")
    
    # Check column names
    print(f"   Columns: {df.columns.tolist()}")
    
    # Determine label column
    label_col = None
    for col in ['glaucoma', 'Glaucoma', 'label', 'Label', 'diagnosis']:
        if col in df.columns:
            label_col = col
            break
    
    if label_col is None:
        print(f"⚠️ Could not find label column")
        print(df.head())
        return 0
    
    # Find image filename column
    file_col = None
    for col in ['filename', 'Filename', 'image', 'Image', 'imageId']:
        if col in df.columns:
            file_col = col
            break
    
    if file_col is None:
        file_col = df.columns[0]  # First column
    
    # Organize
    copied = 0
    glaucoma_files = df[df[label_col] == 1][file_col].tolist()
    normal_files = df[df[label_col] == 0][file_col].tolist()
    
    print(f"   Glaucoma: {len(glaucoma_files)}, Normal: {len(normal_files)}")
    
    # Shuffle and split
    random.shuffle(glaucoma_files)
    random.shuffle(normal_files)
    
    for files, class_name in [(glaucoma_files, 'glaucoma'), (normal_files, 'normal')]:
        split_idx = int(len(files) * split_ratio)
        train_files = files[:split_idx]
        val_files = files[split_idx:]
        
        for split, file_list in [('train', train_files), ('val', val_files)]:
            dest_dir = target_dir / split / class_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for filename in file_list:
                # Try different extensions
                for ext in ['', '.jpg', '.png', '.jpeg']:
                    src = images_dir / f"{filename}{ext}"
                    if src.exists():
                        dst = dest_dir / f"g1020_{src.name}"
                        if not dst.exists():
                            shutil.copy2(src, dst)
                            copied += 1
                        break
    
    return copied


def organize_origa(source_dir: Path, target_dir: Path, split_ratio: float = 0.85):
    """Organize ORIGA dataset using CSV labels."""
    csv_path = source_dir / "origa_info.csv"
    images_dir = source_dir / "Images_Square"
    
    if not csv_path.exists():
        csv_path = source_dir / "OrigaList.csv"
    
    if not csv_path.exists():
        print(f"⚠️ ORIGA CSV not found")
        return 0
    
    df = pd.read_csv(csv_path)
    print(f"📊 ORIGA: {len(df)} images")
    print(f"   Columns: {df.columns.tolist()}")
    
    # Find label column
    label_col = None
    for col in df.columns:
        if 'glaucoma' in col.lower() or 'label' in col.lower():
            label_col = col
            break
    
    if label_col is None:
        print(f"⚠️ Could not find label column. First 5 rows:")
        print(df.head())
        return 0
    
    # Find filename column
    file_col = df.columns[0]
    for col in df.columns:
        if 'file' in col.lower() or 'image' in col.lower() or 'name' in col.lower():
            file_col = col
            break
    
    copied = 0
    
    # Get unique label values
    print(f"   Label values: {df[label_col].unique()}")
    
    # Organize by label
    for label in df[label_col].unique():
        files = df[df[label_col] == label][file_col].tolist()
        
        if label in [1, '1', 'glaucoma', 'Glaucoma', True]:
            class_name = 'glaucoma'
        else:
            class_name = 'normal'
        
        random.shuffle(files)
        split_idx = int(len(files) * split_ratio)
        
        for split, file_list in [('train', files[:split_idx]), ('val', files[split_idx:])]:
            dest_dir = target_dir / split / class_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for filename in file_list:
                for ext in ['', '.jpg', '.png', '.jpeg']:
                    src = images_dir / f"{filename}{ext}"
                    if src.exists():
                        dst = dest_dir / f"origa_{src.name}"
                        if not dst.exists():
                            shutil.copy2(src, dst)
                            copied += 1
                        break
    
    return copied


def organize_refuge(source_dir: Path, target_dir: Path):
    """Organize REFUGE dataset - already split into train/val/test."""
    copied = 0
    
    for split in ['train', 'val', 'test']:
        split_dir = source_dir / split
        if not split_dir.exists():
            continue
        
        # REFUGE has glaucoma and non-glaucoma subfolders
        for subfolder in split_dir.iterdir():
            if not subfolder.is_dir():
                continue
            
            folder_name = subfolder.name.lower()
            if 'glaucoma' in folder_name and 'non' not in folder_name:
                class_name = 'glaucoma'
            else:
                class_name = 'normal'
            
            # Map test to val for our structure
            target_split = 'val' if split == 'test' else split
            
            dest_dir = target_dir / target_split / class_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for img in subfolder.glob('*'):
                if img.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
                    dst = dest_dir / f"refuge_{img.name}"
                    if not dst.exists():
                        shutil.copy2(img, dst)
                        copied += 1
    
    return copied


def organize_smdg(source_dir: Path, target_dir: Path):
    """Organize SMDG PyTorch format dataset - already has train/val structure."""
    copied = 0
    
    for split in ['train', 'val']:
        split_dir = source_dir / split
        if not split_dir.exists():
            continue
        
        for class_folder in split_dir.iterdir():
            if not class_folder.is_dir():
                continue
            
            folder_name = class_folder.name.lower()
            if 'present' in folder_name or 'positive' in folder_name or 'glaucoma' in folder_name.replace('not', '').replace('non', ''):
                if 'not' in folder_name or 'non' in folder_name:
                    class_name = 'normal'
                else:
                    class_name = 'glaucoma'
            else:
                class_name = 'normal'
            
            dest_dir = target_dir / split / class_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            for img in class_folder.glob('*'):
                if img.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
                    dst = dest_dir / f"smdg_{img.name}"
                    if not dst.exists():
                        shutil.copy2(img, dst)
                        copied += 1
    
    return copied


def main():
    downloads_dir = Path("data/kaggle_downloads")
    target_dir = Path("data")
    
    total_copied = 0
    
    print("\n" + "=" * 70)
    print("📁 ORGANIZING DOWNLOADED DATASETS")
    print("=" * 70)
    
    # G1020
    g1020_dir = downloads_dir / "glaucoma-combined" / "G1020"
    if g1020_dir.exists():
        print(f"\n🔄 Processing G1020...")
        copied = organize_g1020(g1020_dir, target_dir)
        print(f"   ✅ Copied {copied} images")
        total_copied += copied
    
    # ORIGA
    origa_dir = downloads_dir / "glaucoma-combined" / "ORIGA"
    if origa_dir.exists():
        print(f"\n🔄 Processing ORIGA...")
        copied = organize_origa(origa_dir, target_dir)
        print(f"   ✅ Copied {copied} images")
        total_copied += copied
    
    # REFUGE
    refuge_dir = downloads_dir / "glaucoma-combined" / "REFUGE"
    if refuge_dir.exists():
        print(f"\n🔄 Processing REFUGE...")
        copied = organize_refuge(refuge_dir, target_dir)
        print(f"   ✅ Copied {copied} images")
        total_copied += copied
    
    # SMDG
    smdg_dir = downloads_dir / "smdg-pytorch"
    if smdg_dir.exists():
        print(f"\n🔄 Processing SMDG...")
        copied = organize_smdg(smdg_dir, target_dir)
        print(f"   ✅ Copied {copied} images")
        total_copied += copied
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 FINAL DATA STATISTICS")
    print("=" * 70)
    
    for split in ['train', 'val', 'test']:
        split_dir = target_dir / split
        if split_dir.exists():
            print(f"\n📁 {split.upper()}:")
            for class_name in ['normal', 'glaucoma']:
                class_dir = split_dir / class_name
                if class_dir.exists():
                    count = len(list(class_dir.glob('*')))
                    print(f"   {class_name}: {count} images")
    
    print(f"\n✅ TOTAL NEW IMAGES: {total_copied}")
    print("=" * 70)


if __name__ == "__main__":
    main()
