"""
Check for data leakage between train/val/test splits.
"""
from pathlib import Path
import hashlib

def get_image_hash(path):
    """Get hash of image content (not filename)."""
    try:
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

def main():
    data_dir = Path('data')

    print('=' * 60)
    print('DATA LEAKAGE CHECK')
    print('=' * 60)

    # Collect all file hashes by split
    splits = {}
    for split in ['train', 'val', 'test']:
        splits[split] = {}
        split_dir = data_dir / split
        if not split_dir.exists():
            continue
        
        for label in ['normal', 'glaucoma']:
            label_dir = split_dir / label
            if not label_dir.exists():
                continue
            
            for img_path in label_dir.glob('*'):
                if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    h = get_image_hash(img_path)
                    if h:
                        splits[split][h] = str(img_path.name)

    print(f'\nFiles per split:')
    for split, hashes in splits.items():
        print(f'  {split}: {len(hashes)} unique files')

    # Check for overlaps
    print(f'\n' + '=' * 60)
    print('CHECKING FOR DUPLICATES BETWEEN SPLITS:')
    print('=' * 60)

    leaks = []

    # Train vs Val
    train_val = set(splits.get('train', {}).keys()) & set(splits.get('val', {}).keys())
    if train_val:
        print(f'\n❌ LEAK: {len(train_val)} images in BOTH train AND val!')
        for h in list(train_val)[:5]:
            print(f'   - {splits["train"][h]}')
        leaks.extend(train_val)
    else:
        print(f'\n✅ No duplicates between train and val')

    # Train vs Test
    train_test = set(splits.get('train', {}).keys()) & set(splits.get('test', {}).keys())
    if train_test:
        print(f'❌ LEAK: {len(train_test)} images in BOTH train AND test!')
        leaks.extend(train_test)
    else:
        print(f'✅ No duplicates between train and test')

    # Val vs Test
    val_test = set(splits.get('val', {}).keys()) & set(splits.get('test', {}).keys())
    if val_test:
        print(f'❌ LEAK: {len(val_test)} images in BOTH val AND test!')
        leaks.extend(val_test)
    else:
        print(f'✅ No duplicates between val and test')

    print(f'\n' + '=' * 60)
    if leaks:
        print(f'⚠️  TOTAL LEAKS FOUND: {len(set(leaks))}')
        print('   These need to be fixed!')
    else:
        print('✅ NO DATA LEAKAGE DETECTED!')
        print('   Train/Val/Test sets are properly separated.')
    print('=' * 60)

if __name__ == "__main__":
    main()
