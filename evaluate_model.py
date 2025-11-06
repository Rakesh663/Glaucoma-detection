"""
Quick script to evaluate the trained model
"""
import torch
import yaml
import os
import sys

# Add src to path
sys.path.insert(0, 'src')

from model import create_model
from dataset import create_dataloaders
from train import validate

def main():
    print("="*70)
    print("🎯 GLAUCOMA MODEL EVALUATION")
    print("="*70)

    # Load config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Check if model exists
    model_path = os.path.join(config['checkpoint']['save_dir'], 'best_model.pth')
    if not os.path.exists(model_path):
        print(f"\n❌ Model not found: {model_path}")
        print("Please train the model first using: python start_training.py")
        sys.exit(1)

    print(f"\n✅ Loading model: {model_path}")

    # Setup device
    device = torch.device('cpu')

    # Create model
    model = create_model(config)

    # Load checkpoint
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    model.eval()

    best_metric = checkpoint.get('best_metric', None)
    if best_metric is not None:
        print(f"   Best validation AUC: {best_metric:.4f}")
    print(f"   Epoch: {checkpoint.get('epoch', 'N/A')}")

    # Load data
    print("\n📦 Loading test data...")
    dataloaders = create_dataloaders(config)
    test_loader = dataloaders['test']

    if len(test_loader) == 0:
        print("❌ No test data found!")
        sys.exit(1)

    print(f"   Test images: {len(test_loader.dataset)}")

    # Create criterion
    if config['loss']['type'] == 'bce':
        criterion = torch.nn.BCEWithLogitsLoss()
    else:
        criterion = torch.nn.BCEWithLogitsLoss()  # Default

    # Evaluate
    print("\n🧪 Running evaluation...")
    test_loss, test_metrics, test_calc = validate(
        model, test_loader, criterion, device, 'Test'
    )

    # Print results
    print(f"\n" + "="*70)
    print("📊 TEST RESULTS")
    print("="*70)
    print(f"Loss:          {test_loss:.4f}")
    print(f"Accuracy:      {test_metrics['accuracy']:.4f}")
    print(f"AUC:           {test_metrics['auc']:.4f}")
    print(f"Sensitivity:   {test_metrics['sensitivity']:.4f}")
    print(f"Specificity:   {test_metrics['specificity']:.4f}")
    print(f"F1 Score:      {test_metrics['f1']:.4f}")
    print(f"Precision:     {test_metrics['precision']:.4f}")

    # Find optimal threshold
    if test_calc and len(test_calc.probabilities) > 0:
        target_spec = config['evaluation']['target_specificity']
        optimal_threshold = test_calc.find_threshold_at_specificity(target_spec=target_spec)
        print(f"\n🎯 Optimal threshold for {target_spec:.0%} specificity: {optimal_threshold:.3f}")

    print("\n" + "="*70)
    print("✅ Evaluation completed successfully!")
    print("="*70)

if __name__ == "__main__":
    main()
