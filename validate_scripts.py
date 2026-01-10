"""
Validate all scripts are ready for training.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print('=' * 70)
print('VALIDATING ALL SCRIPTS FOR TRAINING READINESS')
print('=' * 70)

errors = []

# 1. Test preprocessing imports
print('\n📦 Testing preprocessing module...')
try:
    from src.preprocessing import (
        FundusPreprocessor, 
        QualityAssessor, 
        ClinicalAugmentation,
        OpticDiscDetector,
        get_clinical_train_transform
    )
    print('   ✅ All preprocessing imports successful')
except Exception as e:
    print(f'   ❌ Preprocessing import error: {e}')
    errors.append(f'Preprocessing: {e}')

# 2. Test model imports
print('\n📦 Testing model module...')
try:
    from src.model import create_model, GlaucomaClassifier, GradCAM
    print('   ✅ All model imports successful')
except Exception as e:
    print(f'   ❌ Model import error: {e}')
    errors.append(f'Model: {e}')

# 3. Test dataset imports
print('\n📦 Testing dataset module...')
try:
    from src.dataset import GlaucomaDataset, create_dataloaders, MixUpDataset
    print('   ✅ All dataset imports successful')
except Exception as e:
    print(f'   ❌ Dataset import error: {e}')
    errors.append(f'Dataset: {e}')

# 4. Test inference imports
print('\n📦 Testing inference module...')
try:
    from src.inference import GlaucomaDetector, PredictionResult
    print('   ✅ All inference imports successful')
except Exception as e:
    print(f'   ❌ Inference import error: {e}')
    errors.append(f'Inference: {e}')

# 5. Test train imports
print('\n📦 Testing train module...')
try:
    from src.train import train, LabelSmoothingBCELoss, WarmupCosineScheduler
    print('   ✅ All train imports successful')
except Exception as e:
    print(f'   ❌ Train import error: {e}')
    errors.append(f'Train: {e}')

# 6. Test utils imports
print('\n📦 Testing utils module...')
try:
    from src.utils import MetricsCalculator, EarlyStopping, get_loss_function
    print('   ✅ All utils imports successful')
except Exception as e:
    print(f'   ❌ Utils import error: {e}')
    errors.append(f'Utils: {e}')

# 7. Test config loading
print('\n📄 Testing config loading...')
try:
    import yaml
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print('   ✅ Config loaded successfully')
    print(f"   Model: {config['model']['architecture']}")
    print(f"   Image size: {config['data']['image_size']}")
except Exception as e:
    print(f'   ❌ Config error: {e}')
    errors.append(f'Config: {e}')

# 8. Quick model creation test
print('\n🤖 Testing model creation...')
try:
    import torch
    model = create_model(config)
    dummy_input = torch.randn(1, 3, 512, 512)
    output = model(dummy_input)
    print('   ✅ Model created and forward pass works')
    print(f"   Output shape: {output.shape}")
except Exception as e:
    print(f'   ❌ Model creation error: {e}')
    errors.append(f'Model creation: {e}')

# 9. Test optic disc detector
print('\n🔍 Testing optic disc detector...')
try:
    import numpy as np
    detector = OpticDiscDetector(target_roi_size=(512, 512))
    # Create dummy image
    dummy_img = np.random.randint(0, 255, (1024, 1024, 3), dtype=np.uint8)
    result = detector.detect(dummy_img)
    print('   ✅ Optic disc detector works')
    if result:
        print(f"   Confidence: {result.confidence:.2f}")
except Exception as e:
    print(f'   ❌ Optic disc detector error: {e}')
    errors.append(f'Optic disc: {e}')

# Summary
print('\n' + '=' * 70)
if errors:
    print('❌ VALIDATION FAILED')
    print(f'   {len(errors)} error(s) found:')
    for err in errors:
        print(f'   - {err}')
    sys.exit(1)
else:
    print('✅ ALL VALIDATIONS PASSED - READY FOR TRAINING!')
print('=' * 70)
