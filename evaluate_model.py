"""
Quick script to evaluate the trained model
"""
import torch
import yaml
import os
import sys
import numpy as np
from datetime import datetime

# Add src to path
sys.path.insert(0, 'src')

from model import create_model
from dataset import create_dataloaders
from train import validate
from utils import plot_confusion_matrix, plot_roc_curve

def main():
    print("="*70)
    print("GLAUCOMA MODEL EVALUATION")
    print("="*70)

    # Load config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Check if model exists
    model_path = os.path.join(config['checkpoint']['save_dir'], 'best_model.pth')
    if not os.path.exists(model_path):
        print(f"\nERROR: Model not found: {model_path}")
        print("Please train the model first using: python start_training.py")
        sys.exit(1)

    print(f"\nLoading model: {model_path}")

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
    print("\nLoading test data...")
    dataloaders = create_dataloaders(config)
    test_loader = dataloaders['test']

    if len(test_loader) == 0:
        print("ERROR: No test data found!")
        sys.exit(1)

    print(f"   Test images: {len(test_loader.dataset)}")

    # Create criterion
    if config['loss']['type'] == 'bce':
        criterion = torch.nn.BCEWithLogitsLoss()
    else:
        criterion = torch.nn.BCEWithLogitsLoss()  # Default

    # Evaluate
    print("\nRunning evaluation...")
    test_loss, test_metrics, test_calc = validate(
        model, test_loader, criterion, device, 'Test'
    )

    # Print results
    print(f"\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    print(f"Loss:          {test_loss:.4f}")
    print(f"Accuracy:      {test_metrics['accuracy']:.4f}")
    print(f"AUC:           {test_metrics['auc']:.4f}")
    print(f"Sensitivity:   {test_metrics['sensitivity']:.4f}")
    print(f"Specificity:   {test_metrics['specificity']:.4f}")
    print(f"F1 Score:      {test_metrics['f1']:.4f}")
    print(f"Precision:     {test_metrics['precision']:.4f}")

    # Find optimal threshold and save results
    if test_calc and len(test_calc.probabilities) > 0:
        target_spec = config['evaluation']['target_specificity']
        optimal_threshold = test_calc.find_threshold_at_specificity(target_spec=target_spec)
        print(f"\nOptimal threshold for {target_spec:.0%} specificity: {optimal_threshold:.3f}")

        # Create results directory
        results_dir = "evaluation_results"
        os.makedirs(results_dir, exist_ok=True)

        # Save plots
        preds = (np.array(test_calc.probabilities) >= optimal_threshold).astype(int)

        confusion_path = os.path.join(results_dir, 'confusion_matrix.png')
        plot_confusion_matrix(test_calc.labels, preds, save_path=confusion_path)
        print(f"\nConfusion matrix saved: {confusion_path}")

        roc_path = os.path.join(results_dir, 'roc_curve.png')
        plot_roc_curve(test_calc.labels, test_calc.probabilities, save_path=roc_path)
        print(f"ROC curve saved: {roc_path}")

        # Save detailed metrics to file
        metrics_path = os.path.join(results_dir, 'test_metrics.txt')
        with open(metrics_path, 'w') as f:
            f.write("="*70 + "\n")
            f.write("GLAUCOMA DETECTION - TEST EVALUATION RESULTS\n")
            f.write("="*70 + "\n\n")
            f.write(f"Evaluation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Model: {model_path}\n")
            f.write(f"Test Images: {len(test_loader.dataset)}\n\n")
            f.write("="*70 + "\n")
            f.write("METRICS\n")
            f.write("="*70 + "\n")
            f.write(f"Loss:           {test_loss:.4f}\n")
            f.write(f"Accuracy:       {test_metrics['accuracy']:.4f} ({test_metrics['accuracy']*100:.2f}%)\n")
            f.write(f"AUC:            {test_metrics['auc']:.4f}\n")
            f.write(f"Sensitivity:    {test_metrics['sensitivity']:.4f} ({test_metrics['sensitivity']*100:.2f}%)\n")
            f.write(f"Specificity:    {test_metrics['specificity']:.4f} ({test_metrics['specificity']*100:.2f}%)\n")
            f.write(f"F1 Score:       {test_metrics['f1']:.4f}\n")
            f.write(f"Precision:      {test_metrics['precision']:.4f}\n\n")
            f.write(f"Optimal Threshold: {optimal_threshold:.3f} (for {target_spec:.0%} specificity)\n\n")
            f.write("="*70 + "\n")
            f.write("FILES GENERATED\n")
            f.write("="*70 + "\n")
            f.write(f"- Confusion Matrix: {confusion_path}\n")
            f.write(f"- ROC Curve: {roc_path}\n")
            f.write(f"- Metrics Report: {metrics_path}\n")

        print(f"Metrics report saved: {metrics_path}")

    print("\n" + "="*70)
    print("Evaluation completed successfully!")
    print("="*70)
    print(f"\nResults saved in: {results_dir}/")
    print("   - confusion_matrix.png")
    print("   - roc_curve.png")
    print("   - test_metrics.txt")

if __name__ == "__main__":
    main()
