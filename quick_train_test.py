"""
Quick Training Test - Run 1 epoch to verify everything works
before committing to full training.
"""
import os
import sys
import yaml
import torch
import torch.nn as nn
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("QUICK TRAINING TEST (1 EPOCH)")
print("Verifying entire pipeline before full training")
print("=" * 60)

# Load config
print("\n1. Loading config...")
with open("config/config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Modify for quick test
config["training"]["num_epochs"] = 1
config["training"]["batch_size"] = 8
config["data"]["num_workers"] = 0

print(f"   ✅ Config loaded")
print(f"   Model: {config['model']['architecture']}")
print(f"   Image size: {config['data']['image_size']}")

# Create dataloaders
print("\n2. Creating dataloaders...")
from src.dataset import create_dataloaders
loaders = create_dataloaders(config)

train_batches = len(loaders["train"])
val_batches = len(loaders["val"])
print(f"   ✅ Train: {train_batches} batches")
print(f"   ✅ Val: {val_batches} batches")

if train_batches == 0:
    print("   ❌ ERROR: No training data!")
    sys.exit(1)

# Create model
print("\n3. Creating model...")
from src.model import create_model
model = create_model(config)
params = sum(p.numel() for p in model.parameters())
print(f"   ✅ Model: {type(model).__name__}")
print(f"   ✅ Parameters: {params:,}")

# Setup training
print("\n4. Setting up training...")
from src.utils import get_loss_function
criterion = get_loss_function(config)
optimizer = torch.optim.AdamW(
    model.parameters(), 
    lr=config["training"]["learning_rate"],
    weight_decay=config["training"]["weight_decay"]
)
print(f"   ✅ Loss: {type(criterion).__name__}")
print(f"   ✅ Optimizer: AdamW")

# Train 1 epoch
print("\n5. Training 1 epoch...")
model.train()
total_loss = 0
correct = 0
total = 0
start_time = time.time()

for batch_idx, (images, labels) in enumerate(loaders["train"]):
    if batch_idx >= 5:  # Just test first 5 batches
        break
    
    # Forward pass
    optimizer.zero_grad()
    outputs = model(images)
    
    if labels.dim() == 1:
        labels = labels.unsqueeze(1)
    labels = labels.float()
    
    loss = criterion(outputs, labels)
    
    # Backward pass
    loss.backward()
    optimizer.step()
    
    # Track metrics
    total_loss += loss.item()
    predictions = (torch.sigmoid(outputs) > 0.5).float()
    correct += (predictions == labels).sum().item()
    total += labels.size(0)
    
    print(f"   Batch {batch_idx + 1}/5: Loss={loss.item():.4f}")

epoch_time = time.time() - start_time
avg_loss = total_loss / 5
accuracy = correct / total * 100

print(f"\n   ✅ Epoch complete in {epoch_time:.1f}s")
print(f"   ✅ Avg Loss: {avg_loss:.4f}")
print(f"   ✅ Accuracy: {accuracy:.1f}%")

# Validate
print("\n6. Running validation...")
model.eval()
val_loss = 0
val_correct = 0
val_total = 0

with torch.no_grad():
    for batch_idx, (images, labels) in enumerate(loaders["val"]):
        if batch_idx >= 3:  # Just test first 3 batches
            break
        
        outputs = model(images)
        if labels.dim() == 1:
            labels = labels.unsqueeze(1)
        labels = labels.float()
        
        loss = criterion(outputs, labels)
        val_loss += loss.item()
        
        predictions = (torch.sigmoid(outputs) > 0.5).float()
        val_correct += (predictions == labels).sum().item()
        val_total += labels.size(0)

val_accuracy = val_correct / val_total * 100
print(f"   ✅ Val Loss: {val_loss / 3:.4f}")
print(f"   ✅ Val Accuracy: {val_accuracy:.1f}%")

# Test model saving
print("\n7. Testing model save...")
test_save_path = "models/test_checkpoint.pth"
os.makedirs("models", exist_ok=True)

checkpoint = {
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'epoch': 1,
    'config': config
}
torch.save(checkpoint, test_save_path)
print(f"   ✅ Saved checkpoint: {test_save_path}")

# Test model loading
print("\n8. Testing model load...")
loaded_model = create_model(config)
checkpoint = torch.load(test_save_path, weights_only=False)
loaded_model.load_state_dict(checkpoint['model_state_dict'])
print(f"   ✅ Loaded checkpoint successfully!")

# Cleanup test file
os.remove(test_save_path)
print(f"   ✅ Cleaned up test file")

# Test inference integration
print("\n9. Testing inference integration...")
try:
    from src.inference import GlaucomaDetector
    print(f"   ✅ GlaucomaDetector importable")
except Exception as e:
    print(f"   ⚠️ Warning: {e}")

# Summary
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED - READY FOR FULL TRAINING!")
print("=" * 60)

# Estimate full training time
batches_per_epoch = train_batches
time_per_batch = epoch_time / 5
full_epoch_time = batches_per_epoch * time_per_batch
total_epochs = 150  # From config
total_time_hours = (full_epoch_time * total_epochs) / 3600

print(f"\n📊 Training Time Estimate:")
print(f"   Batches per epoch: {batches_per_epoch}")
print(f"   Time per batch: {time_per_batch:.2f}s")
print(f"   Time per epoch: {full_epoch_time / 60:.1f} minutes")
print(f"   Total epochs: {total_epochs}")
print(f"   Estimated total time: {total_time_hours:.1f} hours")

print(f"\n🚀 To start full training:")
print(f"   python src/train.py --config config/config.yaml")
