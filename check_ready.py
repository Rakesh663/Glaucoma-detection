"""
PRE-TRAINING CHECKLIST
Run this before starting training
"""
import os
import sys

def check_mark(condition):
    return "✅" if condition else "❌"

print("="*70)
print("🔍 PRE-TRAINING CHECKLIST")
print("="*70)

checks_passed = 0
total_checks = 0

# Check 1: Data directories
print("\n📁 DATA DIRECTORIES:")
total_checks += 1
data_dirs_exist = all([
    os.path.exists('data/train/glaucoma'),
    os.path.exists('data/train/normal'),
    os.path.exists('data/val/glaucoma'),
    os.path.exists('data/val/normal'),
    os.path.exists('data/test/glaucoma'),
    os.path.exists('data/test/normal')
])
if data_dirs_exist:
    checks_passed += 1
print(f"  {check_mark(data_dirs_exist)} All data directories exist")

# Check 2: Training images
print("\n📷 TRAINING DATA:")
total_checks += 1
try:
    train_g = len([f for f in os.listdir('data/train/glaucoma') if f.endswith(('.jpg', '.png', '.jpeg'))])
    train_n = len([f for f in os.listdir('data/train/normal') if f.endswith(('.jpg', '.png', '.jpeg'))])
    has_train_data = train_g > 0 and train_n > 0
    if has_train_data:
        checks_passed += 1
    print(f"  {check_mark(has_train_data)} Glaucoma: {train_g} images")
    print(f"  {check_mark(has_train_data)} Normal: {train_n} images")
except:
    has_train_data = False
    print(f"  {check_mark(False)} Could not read training data")

# Check 3: Validation images
print("\n📷 VALIDATION DATA:")
total_checks += 1
try:
    val_g = len([f for f in os.listdir('data/val/glaucoma') if f.endswith(('.jpg', '.png', '.jpeg'))])
    val_n = len([f for f in os.listdir('data/val/normal') if f.endswith(('.jpg', '.png', '.jpeg'))])
    has_val_data = val_g > 0 and val_n > 0
    if has_val_data:
        checks_passed += 1
    print(f"  {check_mark(has_val_data)} Glaucoma: {val_g} images")
    print(f"  {check_mark(has_val_data)} Normal: {val_n} images")
except:
    has_val_data = False
    print(f"  {check_mark(False)} Could not read validation data")

# Check 4: Core files
print("\n📄 CODE FILES:")
total_checks += 1
core_files_exist = all([
    os.path.exists('src/train.py'),
    os.path.exists('src/model.py'),
    os.path.exists('src/dataset.py'),
    os.path.exists('src/utils.py'),
    os.path.exists('config/config.yaml')
])
if core_files_exist:
    checks_passed += 1
print(f"  {check_mark(core_files_exist)} All required files present")

# Check 5: Dependencies
print("\n📦 DEPENDENCIES:")
total_checks += 1
deps = ['torch', 'timm', 'albumentations', 'sklearn', 'yaml', 'tqdm']
missing = []
for dep in deps:
    try:
        __import__(dep)
    except:
        missing.append(dep)

deps_ok = len(missing) == 0
if deps_ok:
    checks_passed += 1
print(f"  {check_mark(deps_ok)} Python packages")
if missing:
    print(f"     Missing: {', '.join(missing)}")
    print(f"     Run: pip install -r requirements.txt")

# Check 6: Output directories
print("\n📁 OUTPUT DIRECTORIES:")
total_checks += 1
output_dirs = ['models', 'logs']
output_dirs_exist = all([os.path.exists(d) for d in output_dirs])
if output_dirs_exist:
    checks_passed += 1
print(f"  {check_mark(output_dirs_exist)} Models and logs directories ready")

# Summary
print("\n" + "="*70)
print(f"📊 RESULT: {checks_passed}/{total_checks} checks passed")
print("="*70)

if checks_passed == total_checks:
    print("\n✅ ALL CHECKS PASSED!")
    print("\n🚀 READY TO TRAIN!")
    print("\n   Run: python start_training.py")
    print("   Or:  cd src && python train.py")
else:
    print("\n❌ SOME CHECKS FAILED")
    print("\n💡 FIX ISSUES ABOVE BEFORE TRAINING")
    
    if not data_dirs_exist or not has_train_data:
        print("\n   📌 Run: python organize_data.py")
    
    if missing:
        print("\n   📌 Run: pip install -r requirements.txt")

print()