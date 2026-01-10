"""Quick script to organize ORIGA images."""
import pandas as pd
import shutil
from pathlib import Path
import random

base = Path('data/kaggle_downloads/glaucoma-combined/ORIGA')
csv = pd.read_csv(base / 'origa_info.csv')
img_dir = base / 'Images_Square'
target = Path('data')

print(f"ORIGA CSV has {len(csv)} rows")
print(f"Images_Square has {len(list(img_dir.glob('*')))} files")

glaucoma_files = csv[csv['Label'] == 1]['Image'].tolist()
normal_files = csv[csv['Label'] == 0]['Image'].tolist()
print(f'ORIGA: {len(glaucoma_files)} glaucoma, {len(normal_files)} normal')

copied = 0
random.shuffle(glaucoma_files)
random.shuffle(normal_files)

for files, cls in [(glaucoma_files, 'glaucoma'), (normal_files, 'normal')]:
    split_idx = int(len(files) * 0.85)
    
    for split, file_list in [('train', files[:split_idx]), ('val', files[split_idx:])]:
        dest = target / split / cls
        dest.mkdir(parents=True, exist_ok=True)
        
        for fname in file_list:
            # Find matching file - use os.listdir instead of glob
            for f in img_dir.iterdir():
                if f.name.startswith(str(fname)):
                    dst = dest / f'origa_{f.name}'
                    if not dst.exists():
                        shutil.copy2(f, dst)
                        copied += 1
                    break

print(f'ORIGA: Copied {copied} images')

# Final summary
print('\n========================================')
print('FINAL DATASET STATISTICS')
print('========================================')
total = 0
for split in ['train', 'val', 'test']:
    split_dir = target / split
    if split_dir.exists():
        print(f'{split.upper()}:')
        for cls in ['normal', 'glaucoma']:
            cls_dir = split_dir / cls
            if cls_dir.exists():
                count = len(list(cls_dir.glob('*')))
                total += count
                print(f'  {cls}: {count}')
print(f'\nTOTAL IMAGES: {total}')
print('========================================')
