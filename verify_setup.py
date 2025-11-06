"""
Setup Verification Script
Run: python verify_setup.py
"""
import os

def check(passed):
    return "✅" if passed else "❌"

print("="*60)
print("GLAUCOMA DETECTION - SETUP VERIFICATION")
print("="*60)

# Check directories
print("\n📁 CHECKING DIRECTORIES:")
dirs = [
    'data/train/glaucoma', 'data/train/normal',
    'data/val/glaucoma', 'data/val/normal',
    'data/test/glaucoma', 'data/test/normal',
    'models', 'logs', 'config', 'src', 'api'
]
all_dirs = all(os.path.exists(d) for d in dirs)
for d in dirs:
    print(f"  {check(os.path.exists(d))} {d}")

# Check files
print("\n📄 CHECKING FILES:")
files = [
    'config/config.yaml', 'src/model.py', 'src/dataset.py',
    'src/train.py', 'src/utils.py', 'src/inference.py',
    'api/main.py', 'requirements.txt', 'README.md'
]
all_files = all(os.path.exists(f) for f in files)
for f in files:
    print(f"  {check(os.path.exists(f))} {f}")

# Check data
print("\n📷 CHECKING TRAINING DATA:")
data_dirs = [
    ('data/train/glaucoma', 'Training - Glaucoma'),
    ('data/train/normal', 'Training - Normal'),
]
has_data = False
for dir_path, name in data_dirs:
    if os.path.exists(dir_path):
        imgs = [f for f in os.listdir(dir_path) 
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        count = len(imgs)
        if count > 0:
            has_data = True
            print(f"  ✅ {name}: {count} images")
        else:
            print(f"  ❌ {name}: No images")

if not has_data:
    print("\n  ⚠️  NO TRAINING DATA FOUND")
    print("     Add images to data/train/glaucoma/ and data/train/normal/")

# Check model
print("\n🤖 CHECKING TRAINED MODEL:")
model_exists = os.path.exists('models/best_model.pth')
print(f"  {check(model_exists)} models/best_model.pth")

if not model_exists:
    print("\n  ⚠️  NO TRAINED MODEL")
    print("     Run: cd src && python train.py")

# Summary
print("\n" + "="*60)
if all_dirs and all_files:
    print("✅ SETUP COMPLETE")
    print("="*60)
    if has_data:
        print("\n📋 NEXT STEPS:")
        if not model_exists:
            print("  1. Train: cd src && python train.py")
            print("  2. Deploy: cd api && python main.py")
        else:
            print("  • Deploy: cd api && python main.py")
            print("  • Docs: http://localhost:8000/docs")
    else:
        print("\n📋 NEXT STEPS:")
        print("  1. Add images to data/train/glaucoma/ and /normal/")
        print("  2. Train: cd src && python train.py")
        print("  3. Deploy: cd api && python main.py")
else:
    print("❌ SETUP INCOMPLETE")
    print("="*60)
    print("\nSome files/folders missing. Re-extract the project.")

print()