"""
Remove blank/corrupt REFUGE images from dataset.
"""
import os
from pathlib import Path
from PIL import Image
import numpy as np

def check_and_remove_blank_images(data_dir: str, pattern: str = "refuge"):
    """Find and remove blank/corrupt images matching pattern."""
    data_path = Path(data_dir)
    
    removed = []
    checked = 0
    
    print(f"Scanning for blank '{pattern}' images in: {data_dir}")
    print("=" * 60)
    
    for split in ['train', 'val', 'test']:
        for label in ['normal', 'glaucoma']:
            folder = data_path / split / label
            if not folder.exists():
                continue
            
            for img_path in folder.glob(f"*{pattern}*"):
                checked += 1
                try:
                    img = Image.open(img_path)
                    img_array = np.array(img)
                    
                    # Check if blank (all same color or very low variance)
                    is_blank = False
                    
                    # Check 1: All pixels same value
                    if img_array.std() < 5:
                        is_blank = True
                        reason = "near-zero variance (solid color)"
                    
                    # Check 2: Image too small
                    elif img_array.shape[0] < 50 or img_array.shape[1] < 50:
                        is_blank = True
                        reason = f"too small ({img_array.shape})"
                    
                    # Check 3: All black or all white
                    elif img_array.mean() < 5 or img_array.mean() > 250:
                        is_blank = True
                        reason = f"too dark/bright (mean={img_array.mean():.1f})"
                    
                    if is_blank:
                        print(f"  ❌ BLANK: {img_path.name} - {reason}")
                        removed.append(str(img_path))
                        os.remove(img_path)
                    else:
                        # Image is OK
                        pass
                        
                except Exception as e:
                    print(f"  ❌ CORRUPT: {img_path.name} - {str(e)}")
                    removed.append(str(img_path))
                    try:
                        os.remove(img_path)
                    except:
                        pass
    
    print("=" * 60)
    print(f"Checked: {checked} images")
    print(f"Removed: {len(removed)} blank/corrupt images")
    
    return removed

if __name__ == "__main__":
    # Remove blank REFUGE images
    removed = check_and_remove_blank_images("data", pattern="refuge")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if removed:
        print(f"\nRemoved {len(removed)} files:")
        for f in removed[:10]:
            print(f"  - {f}")
        if len(removed) > 10:
            print(f"  ... and {len(removed) - 10} more")
    else:
        print("No blank images found! All REFUGE images are valid.")
    
    print("\n✅ Dataset cleaned. Ready to train again!")
