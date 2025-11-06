"""
ACRIMA Dataset Organization Script
Organizes ACRIMA fundus images into train/val/test splits
"""
import os
import shutil
from pathlib import Path
import random

# CONFIGURATION - UPDATE THIS PATH IF NEEDED
SOURCE_DIR = r"C:\Users\DELL\Downloads\archive (4)\Database\Images"
TARGET_BASE_DIR = "data"

# Split ratios
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Set random seed for reproducibility
random.seed(42)


def identify_label(filename):
    """
    Identify if image is glaucomatous or normal based on filename
    ACRIMA naming: Im001_ACRIMA.jpg (normal) or Im001_g_ACRIMA.jpg (glaucoma)
    """
    if "_g_" in filename:
        return "glaucoma"
    else:
        return "normal"


def organize_dataset(source_dir, target_base_dir):
    """Organize ACRIMA dataset into train/val/test splits"""
    
    print("=" * 70)
    print("ACRIMA DATASET ORGANIZATION")
    print("=" * 70)
    print(f"\nSource: {source_dir}")
    print(f"Target: {target_base_dir}\n")
    
    # Check if source directory exists
    if not os.path.exists(source_dir):
        print(f"❌ ERROR: Source directory not found!")
        print(f"   Expected: {source_dir}")
        print("\n💡 Please update SOURCE_DIR in this script to match your path.")
        return False
    
    # Get all image files
    all_images = [f for f in os.listdir(source_dir) 
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if len(all_images) == 0:
        print(f"❌ ERROR: No images found in {source_dir}")
        return False
    
    print(f"✅ Found {len(all_images)} total images\n")
    
    # Separate by class
    glaucoma_images = [f for f in all_images if identify_label(f) == "glaucoma"]
    normal_images = [f for f in all_images if identify_label(f) == "normal"]
    
    print("📊 CLASS DISTRIBUTION:")
    print(f"   Glaucoma images: {len(glaucoma_images)}")
    print(f"   Normal images: {len(normal_images)}")
    print()
    
    # Shuffle for random split
    random.shuffle(glaucoma_images)
    random.shuffle(normal_images)
    
    # Calculate split indices
    def split_data(images, train_ratio, val_ratio):
        total = len(images)
        train_end = int(total * train_ratio)
        val_end = train_end + int(total * val_ratio)
        
        return {
            'train': images[:train_end],
            'val': images[train_end:val_end],
            'test': images[val_end:]
        }
    
    glaucoma_split = split_data(glaucoma_images, TRAIN_RATIO, VAL_RATIO)
    normal_split = split_data(normal_images, TRAIN_RATIO, VAL_RATIO)
    
    # Print split distribution
    print("=" * 70)
    print("SPLIT DISTRIBUTION (70% / 15% / 15%)")
    print("=" * 70)
    print(f"\n{'Split':<10} {'Glaucoma':<12} {'Normal':<12} {'Total':<12}")
    print("-" * 50)
    
    for split in ['train', 'val', 'test']:
        g_count = len(glaucoma_split[split])
        n_count = len(normal_split[split])
        total = g_count + n_count
        print(f"{split.upper():<10} {g_count:<12} {n_count:<12} {total:<12}")
    
    total_g = sum(len(glaucoma_split[s]) for s in ['train', 'val', 'test'])
    total_n = sum(len(normal_split[s]) for s in ['train', 'val', 'test'])
    print("-" * 50)
    print(f"{'TOTAL':<10} {total_g:<12} {total_n:<12} {total_g + total_n:<12}")
    print()
    
    # Create target directories
    print("=" * 70)
    print("CREATING DIRECTORIES")
    print("=" * 70)
    
    splits = ['train', 'val', 'test']
    classes = ['glaucoma', 'normal']
    
    for split in splits:
        for class_name in classes:
            target_dir = os.path.join(target_base_dir, split, class_name)
            os.makedirs(target_dir, exist_ok=True)
            print(f"✅ Created: {target_dir}")
    
    print()
    
    # Copy files
    print("=" * 70)
    print("COPYING FILES")
    print("=" * 70)
    print()
    
    total_copied = 0
    
    for split in splits:
        print(f"📁 {split.upper()}:")
        
        # Copy glaucoma images
        for filename in glaucoma_split[split]:
            src = os.path.join(source_dir, filename)
            dst = os.path.join(target_base_dir, split, 'glaucoma', filename)
            shutil.copy2(src, dst)
            total_copied += 1
        
        # Copy normal images
        for filename in normal_split[split]:
            src = os.path.join(source_dir, filename)
            dst = os.path.join(target_base_dir, split, 'normal', filename)
            shutil.copy2(src, dst)
            total_copied += 1
        
        g_count = len(glaucoma_split[split])
        n_count = len(normal_split[split])
        print(f"   ✅ Copied {g_count} glaucoma + {n_count} normal = {g_count + n_count} images")
    
    print()
    print("=" * 70)
    print(f"✅ SUCCESS! Copied {total_copied} images")
    print("=" * 70)
    print()
    print("📂 YOUR DATA IS NOW ORGANIZED:")
    print(f"   data/train/glaucoma/  - {len(glaucoma_split['train'])} images")
    print(f"   data/train/normal/    - {len(normal_split['train'])} images")
    print(f"   data/val/glaucoma/    - {len(glaucoma_split['val'])} images")
    print(f"   data/val/normal/      - {len(normal_split['val'])} images")
    print(f"   data/test/glaucoma/   - {len(glaucoma_split['test'])} images")
    print(f"   data/test/normal/     - {len(normal_split['test'])} images")
    print()
    print("🚀 NEXT STEPS:")
    print("   1. Verify: python verify_setup.py")
    print("   2. Train: cd src && python train.py")
    print("   3. Deploy: cd api && python main.py")
    print()
    
    return True


if __name__ == "__main__":
    success = organize_dataset(SOURCE_DIR, TARGET_BASE_DIR)
    
    if not success:
        print("\n❌ Organization failed. Please check the error messages above.")
    else:
        print("✅ Organization complete!")