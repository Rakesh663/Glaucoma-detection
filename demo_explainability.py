"""
Explainability Demo - Grad-CAM Visualization
Tests the Grad-CAM feature to show what the model is "looking at"
Ensures the model is NOT a black box!
"""

import os
import sys

# Use Agg backend for headless mode (no GUI)
import matplotlib
matplotlib.use('Agg')

import torch
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from pathlib import Path
import cv2
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from model import GlaucomaClassifier, GradCAM
from torchvision import transforms


def load_model(checkpoint_path: str, config_path: str = None):
    """Load the trained model from checkpoint."""
    print(f"📦 Loading model from: {checkpoint_path}")
    
    # Load checkpoint
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    
    # Load config
    if config_path:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {'model': {'architecture': 'efficientnet_b0', 'dropout': 0.4}}
    
    # Create model
    model = GlaucomaClassifier(
        architecture=config.get('model', {}).get('architecture', 'efficientnet_b0'),
        num_classes=1,
        pretrained=False,  # We're loading weights, not pretrained
        dropout=config.get('model', {}).get('dropout', 0.4),
        use_attention=True,
        mc_dropout=True
    )
    
    # Load state dict
    if 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
    else:
        model.load_state_dict(checkpoint)
    
    model.eval()
    
    # Print training info if available
    if 'epoch' in checkpoint:
        print(f"   Epoch: {checkpoint['epoch']}")
    if 'best_auc' in checkpoint:
        print(f"   Best AUC: {checkpoint['best_auc']:.4f}")
    if 'best_val_loss' in checkpoint:
        print(f"   Best Val Loss: {checkpoint['best_val_loss']:.4f}")
    
    return model


def preprocess_image(image_path: str, image_size: int = 512):
    """Preprocess image for model input."""
    # Load image
    image = Image.open(image_path).convert('RGB')
    original_image = np.array(image)
    
    # Define transforms
    transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    
    # Preprocess
    tensor = transform(image).unsqueeze(0)  # Add batch dimension
    
    return tensor, original_image


def generate_gradcam(model, input_tensor, original_image):
    """Generate Grad-CAM heatmap."""
    # Create GradCAM object
    gradcam = GradCAM(model)
    
    # Generate overlay
    overlay = gradcam.generate_overlay(
        image=original_image,
        input_tensor=input_tensor,
        alpha=0.5
    )
    
    # Also get raw heatmap
    heatmap = gradcam.generate(input_tensor)
    
    return heatmap, overlay


def predict_with_uncertainty(model, input_tensor, n_samples: int = 10):
    """Get prediction with uncertainty using Monte Carlo Dropout."""
    result = model.predict_with_uncertainty(input_tensor, n_samples=n_samples)
    
    prob = result['prediction'].item()
    uncertainty = result['uncertainty'].item()
    ci_low = result['ci_low'].item()
    ci_high = result['ci_high'].item()
    
    return {
        'probability': prob,
        'uncertainty': uncertainty,
        'ci_low': ci_low,
        'ci_high': ci_high,
        'prediction': 'Glaucoma' if prob > 0.5 else 'Normal'
    }


def visualize_explainability(image_path: str, model, output_path: str = None):
    """Create comprehensive explainability visualization."""
    print(f"\n🔍 Analyzing: {Path(image_path).name}")
    
    # Preprocess
    input_tensor, original_image = preprocess_image(image_path)
    
    # Get prediction with uncertainty
    pred_result = predict_with_uncertainty(model, input_tensor)
    
    print(f"   Prediction: {pred_result['prediction']}")
    print(f"   Probability: {pred_result['probability']:.2%}")
    print(f"   Uncertainty: ±{pred_result['uncertainty']:.2%}")
    print(f"   95% CI: [{pred_result['ci_low']:.2%}, {pred_result['ci_high']:.2%}]")
    
    # Generate Grad-CAM
    heatmap, overlay = generate_gradcam(model, input_tensor, original_image)
    
    # Resize original for display
    resized_original = cv2.resize(original_image, (512, 512))
    
    # Create visualization
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    
    # 1. Original image
    axes[0].imshow(resized_original)
    axes[0].set_title('Original Fundus Image', fontsize=12)
    axes[0].axis('off')
    
    # 2. Raw heatmap
    im = axes[1].imshow(heatmap, cmap='jet')
    axes[1].set_title('Grad-CAM Heatmap\n(Model Attention)', fontsize=12)
    axes[1].axis('off')
    plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    
    # 3. Overlay
    axes[2].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
    axes[2].set_title('Grad-CAM Overlay', fontsize=12)
    axes[2].axis('off')
    
    # 4. Prediction summary
    axes[3].axis('off')
    
    # Color based on prediction
    color = '#e74c3c' if pred_result['prediction'] == 'Glaucoma' else '#27ae60'
    
    summary_text = f"""
    🔬 PREDICTION RESULT
    
    Class: {pred_result['prediction']}
    
    Probability: {pred_result['probability']:.1%}
    
    Uncertainty: ±{pred_result['uncertainty']:.1%}
    
    95% Confidence Interval:
    [{pred_result['ci_low']:.1%}, {pred_result['ci_high']:.1%}]
    
    
    ✅ Model Focus Areas:
    The heatmap shows where the
    model is looking when making
    this prediction.
    
    Expected: Optic disc region
    """
    
    axes[3].text(0.1, 0.9, summary_text, transform=axes[3].transAxes,
                 fontsize=11, verticalalignment='top', fontfamily='monospace',
                 bbox=dict(boxstyle='round', facecolor=color, alpha=0.2))
    axes[3].set_title('Model Explanation', fontsize=12)
    
    plt.suptitle(f'Explainability Analysis: {Path(image_path).name}', fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    # Save if output path provided
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"   💾 Saved to: {output_path}")
    
    plt.close()  # Close figure (headless mode, no GUI)
    
    return pred_result, heatmap, overlay


def main():
    """Run explainability demo on sample images."""
    print("=" * 60)
    print("🧠 GLAUCOMA DETECTION - EXPLAINABILITY DEMO")
    print("=" * 60)
    print("\nThis demo shows that the model is NOT a black box!")
    print("We use Grad-CAM to visualize what the model focuses on.\n")
    
    # Paths
    model_path = "models/best_model.pth"
    config_path = "models/config.yaml"
    output_dir = "outputs/explainability"
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Load model
    if not os.path.exists(model_path):
        print(f"❌ Model not found at: {model_path}")
        print("   Please run training first or provide correct path.")
        return
    
    model = load_model(model_path, config_path)
    print(f"✅ Model loaded successfully!\n")
    
    # Find sample images (1 glaucoma, 1 normal from test set)
    test_images = []
    
    # Find glaucoma sample
    glaucoma_dir = Path("data/test/glaucoma")
    if glaucoma_dir.exists():
        glaucoma_images = list(glaucoma_dir.glob("*.jpg"))[:2]
        test_images.extend(glaucoma_images)
    
    # Find normal sample
    normal_dir = Path("data/test/normal")
    if normal_dir.exists():
        normal_images = list(normal_dir.glob("*.jpg"))[:2]
        test_images.extend(normal_images)
    
    if not test_images:
        print("❌ No test images found!")
        print("   Please check data/test/glaucoma and data/test/normal folders")
        return
    
    print(f"📊 Analyzing {len(test_images)} sample images...\n")
    
    # Analyze each image
    results = []
    for i, image_path in enumerate(test_images):
        output_path = os.path.join(
            output_dir, 
            f"explainability_{i+1}_{image_path.stem}.png"
        )
        
        result, heatmap, overlay = visualize_explainability(
            str(image_path), 
            model, 
            output_path
        )
        results.append({
            'image': image_path.name,
            'true_label': image_path.parent.name,
            **result
        })
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    for r in results:
        correct = (r['prediction'].lower() == r['true_label'])
        status = "✅" if correct else "❌"
        print(f"\n{status} {r['image']}")
        print(f"   True: {r['true_label']} | Predicted: {r['prediction']}")
        print(f"   Probability: {r['probability']:.1%} ± {r['uncertainty']:.1%}")
    
    print(f"\n💾 All visualizations saved to: {output_dir}/")
    print("\n✨ The model shows its reasoning through Grad-CAM!")
    print("   Doctors can see what regions influenced the prediction.")


if __name__ == "__main__":
    main()
