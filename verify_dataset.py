"""
Dataset Verification and Cleaning Script
1. Verify labels against original CSV files
2. Remove .bmp files
3. Check class imbalance
4. Report statistics
"""

import os
import sys
from pathlib import Path
from collections import defaultdict
import pandas as pd
import shutil

def count_images_by_extension(folder: Path) -> dict:
    """Count images by file extension."""
    ext_counts = defaultdict(int)
    for f in folder.rglob('*'):
        if f.is_file():
            ext_counts[f.suffix.lower()] += 1
    return dict(ext_counts)

def remove_bmp_files(data_dir: Path, dry_run: bool = True) -> int:
    """Remove .bmp files from data directory."""
    bmp_files = list(data_dir.rglob('*.bmp')) + list(data_dir.rglob('*.BMP'))
    
    if not bmp_files:
        print("✅ No .bmp files found")
        return 0
    
    print(f"Found {len(bmp_files)} .bmp files:")
    for f in bmp_files[:10]:
        print(f"  - {f}")
    if len(bmp_files) > 10:
        print(f"  ... and {len(bmp_files) - 10} more")
    
    if not dry_run:
        for f in bmp_files:
            f.unlink()
        print(f"🗑️ Deleted {len(bmp_files)} .bmp files")
    else:
        print("(Dry run - no files deleted)")
    
    return len(bmp_files)

def verify_g1020_labels(data_dir: Path, csv_path: Path) -> dict:
    """Verify G1020 images are labeled correctly."""
    if not csv_path.exists():
        return {'error': 'CSV not found'}
    
    df = pd.read_csv(csv_path)
    
    # Create lookup: filename -> label
    label_map = {}
    for _, row in df.iterrows():
        fname = row['imageID']
        label = 'glaucoma' if row['binaryLabels'] == 1 else 'normal'
        label_map[fname] = label
    
    # Check images in data folders
    mismatches = []
    for split in ['train', 'val']:
        for cls in ['normal', 'glaucoma']:
            folder = data_dir / split / cls
            if not folder.exists():
                continue
            
            for img in folder.glob('g1020_*'):
                original_name = img.name.replace('g1020_', '')
                expected_label = label_map.get(original_name)
                
                if expected_label and expected_label != cls:
                    mismatches.append({
                        'file': str(img),
                        'current_label': cls,
                        'expected_label': expected_label
                    })
    
    return {
        'total_in_csv': len(df),
        'mismatches': mismatches,
        'mismatch_count': len(mismatches)
    }

def verify_origa_labels(data_dir: Path, csv_path: Path) -> dict:
    """Verify ORIGA images are labeled correctly."""
    if not csv_path.exists():
        return {'error': 'CSV not found'}
    
    df = pd.read_csv(csv_path)
    
    # Create lookup: filename -> label
    label_map = {}
    for _, row in df.iterrows():
        fname = row['Image'].split('/')[-1]  # Extract filename from path
        label = 'glaucoma' if row['Label'] == 1 else 'normal'
        label_map[fname] = label
    
    # Check images in data folders
    mismatches = []
    for split in ['train', 'val']:
        for cls in ['normal', 'glaucoma']:
            folder = data_dir / split / cls
            if not folder.exists():
                continue
            
            for img in folder.glob('origa_*'):
                original_name = img.name.replace('origa_', '')
                expected_label = label_map.get(original_name)
                
                if expected_label and expected_label != cls:
                    mismatches.append({
                        'file': str(img),
                        'current_label': cls,
                        'expected_label': expected_label
                    })
    
    return {
        'total_in_csv': len(df),
        'mismatches': mismatches,
        'mismatch_count': len(mismatches)
    }

def check_class_balance(data_dir: Path) -> dict:
    """Check class balance in dataset."""
    stats = {}
    
    for split in ['train', 'val', 'test']:
        split_dir = data_dir / split
        if not split_dir.exists():
            continue
        
        split_stats = {}
        for cls in ['normal', 'glaucoma']:
            cls_dir = split_dir / cls
            if cls_dir.exists():
                # Count only image files
                count = len([f for f in cls_dir.glob('*') 
                            if f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
                split_stats[cls] = count
        
        if split_stats:
            total = sum(split_stats.values())
            ratio = split_stats.get('glaucoma', 0) / max(split_stats.get('normal', 1), 1)
            split_stats['total'] = total
            split_stats['glaucoma_ratio'] = ratio
            stats[split] = split_stats
    
    return stats

def remove_macos_files(data_dir: Path) -> int:
    """Remove macOS resource fork files (._*)."""
    mac_files = list(data_dir.rglob('._*'))
    for f in mac_files:
        f.unlink()
    return len(mac_files)

def main():
    data_dir = Path('data')
    kaggle_dir = Path('data/kaggle_downloads')
    
    print("=" * 70)
    print("DATASET VERIFICATION AND CLEANING")
    print("=" * 70)
    
    # 1. Remove macOS resource files
    print("\n📁 Removing macOS resource files...")
    mac_removed = remove_macos_files(data_dir)
    print(f"   Removed {mac_removed} macOS files")
    
    # 2. Check file extensions
    print("\n📊 File extensions in dataset:")
    ext_counts = count_images_by_extension(data_dir / 'train')
    ext_counts.update(count_images_by_extension(data_dir / 'val'))
    for ext, count in sorted(ext_counts.items()):
        if ext not in ['.csv', '.json', '.txt', '']:
            status = "⚠️ REMOVE" if ext == '.bmp' else "✅"
            print(f"   {ext}: {count} {status}")
    
    # 3. Remove .bmp files
    print("\n🗑️ Removing .bmp files...")
    remove_bmp_files(data_dir, dry_run=False)
    
    # 4. Verify G1020 labels
    print("\n🔍 Verifying G1020 labels...")
    g1020_result = verify_g1020_labels(
        data_dir, 
        kaggle_dir / 'glaucoma-combined' / 'G1020' / 'G1020.csv'
    )
    if 'error' in g1020_result:
        print(f"   ⚠️ {g1020_result['error']}")
    else:
        if g1020_result['mismatch_count'] == 0:
            print(f"   ✅ All G1020 labels correct!")
        else:
            print(f"   ❌ Found {g1020_result['mismatch_count']} mismatches!")
            for m in g1020_result['mismatches'][:5]:
                print(f"      {m['file']}: {m['current_label']} → {m['expected_label']}")
    
    # 5. Verify ORIGA labels
    print("\n🔍 Verifying ORIGA labels...")
    origa_result = verify_origa_labels(
        data_dir,
        kaggle_dir / 'glaucoma-combined' / 'ORIGA' / 'origa_info.csv'
    )
    if 'error' in origa_result:
        print(f"   ⚠️ {origa_result['error']}")
    else:
        if origa_result['mismatch_count'] == 0:
            print(f"   ✅ All ORIGA labels correct!")
        else:
            print(f"   ❌ Found {origa_result['mismatch_count']} mismatches!")
            for m in origa_result['mismatches'][:5]:
                print(f"      {m['file']}: {m['current_label']} → {m['expected_label']}")
    
    # 6. Check class balance
    print("\n📊 CLASS BALANCE ANALYSIS")
    print("-" * 70)
    balance = check_class_balance(data_dir)
    
    total_normal = 0
    total_glaucoma = 0
    
    for split, stats in balance.items():
        print(f"\n{split.upper()}:")
        print(f"   Normal:   {stats.get('normal', 0):,}")
        print(f"   Glaucoma: {stats.get('glaucoma', 0):,}")
        print(f"   Ratio:    1:{stats.get('glaucoma_ratio', 0):.2f} (normal:glaucoma)")
        
        total_normal += stats.get('normal', 0)
        total_glaucoma += stats.get('glaucoma', 0)
    
    print("\n" + "-" * 70)
    print("OVERALL:")
    print(f"   Total Normal:   {total_normal:,}")
    print(f"   Total Glaucoma: {total_glaucoma:,}")
    overall_ratio = total_glaucoma / max(total_normal, 1)
    print(f"   Overall Ratio:  1:{overall_ratio:.2f} (normal:glaucoma)")
    
    # Imbalance analysis
    print("\n" + "=" * 70)
    print("⚖️ IMBALANCE ANALYSIS")
    print("=" * 70)
    
    if overall_ratio < 0.5:
        print(f"⚠️ Dataset is IMBALANCED (glaucoma ratio: {overall_ratio:.2f})")
        print("\nRecommendations to handle imbalance:")
        print("1. ✅ Use class weights in loss function (already configured)")
        print("2. ✅ Use Focal Loss for hard examples (configured in config.yaml)")
        print("3. ✅ Heavy augmentation on minority class (MixUp/CutMix enabled)")
        print("4. Consider oversampling glaucoma images during training")
        print("5. Use stratified sampling in dataloaders")
    else:
        print("✅ Dataset is reasonably balanced!")
    
    print("\n" + "=" * 70)
    print("🔄 FINAL CLEAN STATISTICS")
    print("=" * 70)
    final_balance = check_class_balance(data_dir)
    
    for split, stats in final_balance.items():
        print(f"{split.upper()}: {stats.get('normal', 0)} normal + {stats.get('glaucoma', 0)} glaucoma = {stats.get('total', 0)} total")

if __name__ == "__main__":
    main()
