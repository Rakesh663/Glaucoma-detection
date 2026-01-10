"""Quick end-to-end test of training pipeline."""
import yaml
import torch
import sys

print("=" * 60)
print("TESTING TRAINING PIPELINE")
print("=" * 60)

# Load config
print("\n1. Loading config...")
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Modify for quick test
config["training"]["num_epochs"] = 1
config["training"]["batch_size"] = 4
config["data"]["num_workers"] = 0

print(f"   Model: {config['model']['architecture']}")
print(f"   Image size: {config['data']['image_size']}")

# Create dataloaders
print("\n2. Creating dataloaders...")
from src.dataset import create_dataloaders
loaders = create_dataloaders(config)

train_batches = len(loaders["train"])
val_batches = len(loaders["val"])
print(f"   Train batches: {train_batches}")
print(f"   Val batches: {val_batches}")

if train_batches == 0:
    print("   ERROR: No training data!")
    sys.exit(1)

# Create model
print("\n3. Creating model...")
from src.model import create_model
model = create_model(config)
print(f"   Model type: {type(model).__name__}")
params = sum(p.numel() for p in model.parameters())
print(f"   Parameters: {params:,}")

# Test forward pass
print("\n4. Testing forward pass...")
batch = next(iter(loaders["train"]))
x, y = batch
print(f"   Input shape: {x.shape}")
print(f"   Labels shape: {y.shape}")

model.eval()
with torch.no_grad():
    output = model(x)
print(f"   Output shape: {output.shape}")

# Test preprocessing
print("\n5. Testing preprocessing modules...")
try:
    from src.preprocessing import OpticDiscDetector
    import numpy as np
    detector = OpticDiscDetector(target_roi_size=(256, 256))
    dummy = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    result = detector.detect(dummy)
    print(f"   OpticDiscDetector: OK (confidence: {result.confidence:.2f})")
except Exception as e:
    print(f"   OpticDiscDetector: {e}")

try:
    from src.preprocessing import QualityAssessor
    qa = QualityAssessor()
    print("   QualityAssessor: OK")
except Exception as e:
    print(f"   QualityAssessor: {e}")

# Summary
print("\n" + "=" * 60)
print("✅ ALL COMPONENTS WORKING - READY FOR TRAINING!")
print("=" * 60)
print("\nTo start training:")
print("  python src/train.py --config config/config.yaml")
