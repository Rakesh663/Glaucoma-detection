"""
Model Explainability Script
===========================
Run after training to verify the model is learning correct patterns.

Features:
1. Grad-CAM heatmaps showing what regions model focuses on
2. Attention visualization
3. Prediction confidence analysis
4. Clinical report generation for doctor review

Usage:
    python explain_model.py --model models/best_model.pth --images data/test
"""

import os
import sys
import argparse
import yaml
import numpy as np
from pathlib import Path
from datetime import datetime
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_config(config_path: str) -> dict:
    """Load configuration file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def create_gradcam_visualization(image: np.ndarray, heatmap: np.ndarray, 
                                  prediction: str, confidence: float,
                                  save_path: str = None) -> np.ndarray:
    """
    Create a side-by-side visualization of original image and Grad-CAM overlay.
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # 1. Original image
    axes[0].imshow(image)
    axes[0].set_title("Original Fundus Image", fontsize=12)
    axes[0].axis('off')
    
    # 2. Grad-CAM heatmap
    axes[1].imshow(heatmap, cmap='jet')
    axes[1].set_title("Grad-CAM Attention Map\n(Where model is looking)", fontsize=12)
    axes[1].axis('off')
    
    # 3. Overlay
    axes[2].imshow(image)
    axes[2].imshow(heatmap, cmap='jet', alpha=0.5)
    axes[2].set_title(f"Prediction: {prediction}\nConfidence: {confidence:.1%}", fontsize=12)
    axes[2].axis('off')
    
    # Add legend
    red_patch = mpatches.Patch(color='red', label='High attention')
    blue_patch = mpatches.Patch(color='blue', label='Low attention')
    fig.legend(handles=[red_patch, blue_patch], loc='lower center', ncol=2)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    
    return fig


def analyze_attention_distribution(heatmap: np.ndarray, image_size: int = 512) -> dict:
    """
    Analyze where the model is focusing.
    Returns metrics about attention distribution.
    """
    h, w = heatmap.shape[:2]
    center_y, center_x = h // 2, w // 2
    
    # Define regions
    center_mask = np.zeros((h, w), dtype=bool)
    cv_y, cv_x = np.ogrid[:h, :w]
    center_radius = min(h, w) // 4
    center_mask = ((cv_y - center_y)**2 + (cv_x - center_x)**2) <= center_radius**2
    
    # Calculate attention in different regions
    if len(heatmap.shape) == 3:
        heatmap_gray = np.mean(heatmap, axis=2)
    else:
        heatmap_gray = heatmap
    
    heatmap_norm = (heatmap_gray - heatmap_gray.min()) / (heatmap_gray.max() - heatmap_gray.min() + 1e-8)
    
    center_attention = np.mean(heatmap_norm[center_mask])
    edge_attention = np.mean(heatmap_norm[~center_mask])
    
    # Find peak attention location
    peak_y, peak_x = np.unravel_index(np.argmax(heatmap_norm), heatmap_norm.shape)
    
    # Distance from center
    peak_distance = np.sqrt((peak_y - center_y)**2 + (peak_x - center_x)**2)
    peak_distance_ratio = peak_distance / (min(h, w) / 2)
    
    return {
        'center_attention': center_attention,
        'edge_attention': edge_attention,
        'attention_ratio': center_attention / (edge_attention + 1e-8),
        'peak_location': (peak_x, peak_y),
        'peak_distance_from_center': peak_distance_ratio,
        'is_focused_on_center': center_attention > edge_attention,
        'focus_quality': 'GOOD' if center_attention > edge_attention else 'CONCERNING'
    }


def generate_clinical_report(results: list, output_dir: Path) -> str:
    """
    Generate a clinical validation report.
    """
    report = []
    report.append("=" * 70)
    report.append("MODEL EXPLAINABILITY REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 70)
    report.append("")
    
    # Summary statistics
    total = len(results)
    correct_focus = sum(1 for r in results if r['attention_analysis']['is_focused_on_center'])
    glaucoma_predictions = sum(1 for r in results if r['prediction'] == 'glaucoma')
    normal_predictions = sum(1 for r in results if r['prediction'] == 'normal')
    
    report.append("SUMMARY")
    report.append("-" * 40)
    report.append(f"Total images analyzed: {total}")
    report.append(f"Glaucoma predictions: {glaucoma_predictions}")
    report.append(f"Normal predictions: {normal_predictions}")
    report.append(f"Images with correct focus (optic disc): {correct_focus}/{total} ({100*correct_focus/max(total,1):.1f}%)")
    report.append("")
    
    # Attention quality
    avg_attention_ratio = np.mean([r['attention_analysis']['attention_ratio'] for r in results])
    report.append("ATTENTION QUALITY")
    report.append("-" * 40)
    report.append(f"Average center-to-edge attention ratio: {avg_attention_ratio:.2f}")
    if avg_attention_ratio > 1.5:
        report.append("✅ Model is strongly focused on the optic disc region (GOOD)")
    elif avg_attention_ratio > 1.0:
        report.append("⚠️ Model has moderate focus on optic disc (ACCEPTABLE)")
    else:
        report.append("❌ Model may be looking at wrong regions (NEEDS REVIEW)")
    report.append("")
    
    # Confidence distribution
    confidences = [r['confidence'] for r in results]
    avg_confidence = np.mean(confidences)
    report.append("CONFIDENCE ANALYSIS")
    report.append("-" * 40)
    report.append(f"Average confidence: {avg_confidence:.1%}")
    report.append(f"Min confidence: {min(confidences):.1%}")
    report.append(f"Max confidence: {max(confidences):.1%}")
    
    uncertain = sum(1 for c in confidences if c < 0.7)
    report.append(f"Uncertain predictions (<70%): {uncertain}/{total}")
    report.append("")
    
    # Individual results
    report.append("INDIVIDUAL RESULTS")
    report.append("-" * 40)
    for i, r in enumerate(results[:20]):  # Show first 20
        focus = "✅" if r['attention_analysis']['is_focused_on_center'] else "❌"
        report.append(f"{i+1}. {r['filename']}")
        report.append(f"   Prediction: {r['prediction']} ({r['confidence']:.1%})")
        report.append(f"   Focus: {focus} (ratio: {r['attention_analysis']['attention_ratio']:.2f})")
    
    if len(results) > 20:
        report.append(f"... and {len(results) - 20} more images")
    
    report.append("")
    report.append("=" * 70)
    report.append("CLINICAL INTERPRETATION GUIDE")
    report.append("=" * 70)
    report.append("")
    report.append("Grad-CAM Heatmap Colors:")
    report.append("  RED/YELLOW = High attention (model focuses here for decision)")
    report.append("  BLUE/GREEN = Low attention")
    report.append("")
    report.append("For CORRECT glaucoma detection, model should focus on:")
    report.append("  ✅ Optic disc center (cup-to-disc ratio)")
    report.append("  ✅ Neuroretinal rim")
    report.append("  ✅ Optic nerve head")
    report.append("")
    report.append("CONCERNING if model focuses on:")
    report.append("  ❌ Image corners or borders")
    report.append("  ❌ Areas away from optic disc")
    report.append("  ❌ Text/annotations in image")
    report.append("")
    report.append("=" * 70)
    
    # Save report
    report_text = "\n".join(report)
    report_path = output_dir / "clinical_report.txt"
    with open(report_path, 'w') as f:
        f.write(report_text)
    
    return report_text


def main():
    parser = argparse.ArgumentParser(description="Model Explainability Analysis")
    parser.add_argument("--model", type=str, default="models/best_model.pth",
                       help="Path to trained model")
    parser.add_argument("--config", type=str, default="config/config.yaml",
                       help="Path to config file")
    parser.add_argument("--images", type=str, default="data/test",
                       help="Path to test images directory")
    parser.add_argument("--output", type=str, default="explanations",
                       help="Output directory for visualizations")
    parser.add_argument("--num_samples", type=int, default=20,
                       help="Number of images to analyze")
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gradcam").mkdir(exist_ok=True)
    (output_dir / "glaucoma").mkdir(exist_ok=True)
    (output_dir / "normal").mkdir(exist_ok=True)
    
    print("=" * 60)
    print("MODEL EXPLAINABILITY ANALYSIS")
    print("=" * 60)
    
    # Check if model exists
    if not os.path.exists(args.model):
        print(f"\n❌ Model not found: {args.model}")
        print("Please train the model first:")
        print("  python src/train.py --config config/config.yaml")
        return
    
    # Load model
    print(f"\n📦 Loading model: {args.model}")
    try:
        from src.inference import GlaucomaDetector
        detector = GlaucomaDetector(args.model, args.config)
        print("   ✅ Model loaded successfully")
    except Exception as e:
        print(f"   ❌ Failed to load model: {e}")
        return
    
    # Find test images
    print(f"\n🔍 Finding images in: {args.images}")
    image_dir = Path(args.images)
    
    if not image_dir.exists():
        print(f"   ❌ Directory not found: {args.images}")
        return
    
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
        image_files.extend(image_dir.rglob(ext))
    
    image_files = list(image_files)[:args.num_samples]
    print(f"   Found {len(image_files)} images to analyze")
    
    if not image_files:
        print("   ❌ No images found!")
        return
    
    # Analyze each image
    print(f"\n🔬 Analyzing images...")
    results = []
    
    for i, img_path in enumerate(image_files):
        print(f"   [{i+1}/{len(image_files)}] {img_path.name}")
        
        try:
            # Load image
            image = Image.open(img_path).convert('RGB')
            image_np = np.array(image)
            
            # Get prediction with Grad-CAM
            result = detector.predict(image, return_attention=True)
            
            # Analyze attention
            if result.gradcam_overlay is not None:
                attention_analysis = analyze_attention_distribution(result.gradcam_overlay)
                
                # Save visualization
                save_path = output_dir / "gradcam" / f"{img_path.stem}_gradcam.png"
                create_gradcam_visualization(
                    image_np, result.gradcam_overlay,
                    result.label, result.confidence,
                    str(save_path)
                )
                
                # Copy to prediction folder
                pred_folder = output_dir / result.label
                (pred_folder / f"{img_path.stem}.png").write_bytes(save_path.read_bytes())
            else:
                attention_analysis = {
                    'is_focused_on_center': True,
                    'attention_ratio': 1.0,
                    'focus_quality': 'UNKNOWN'
                }
            
            results.append({
                'filename': img_path.name,
                'prediction': result.label,
                'probability': result.probability,
                'confidence': result.confidence,
                'uncertainty': result.uncertainty,
                'quality_score': result.quality_score,
                'attention_analysis': attention_analysis
            })
            
        except Exception as e:
            print(f"      ⚠️ Error: {e}")
    
    # Generate report
    print(f"\n📝 Generating clinical report...")
    report = generate_clinical_report(results, output_dir)
    print(report)
    
    # Save results summary
    print(f"\n✅ Results saved to: {output_dir}/")
    print(f"   - {output_dir}/gradcam/ - All Grad-CAM visualizations")
    print(f"   - {output_dir}/glaucoma/ - Predicted glaucoma cases")
    print(f"   - {output_dir}/normal/ - Predicted normal cases")
    print(f"   - {output_dir}/clinical_report.txt - Full report")
    
    print("\n" + "=" * 60)
    print("🔍 REVIEW THE GRAD-CAM IMAGES TO VERIFY:")
    print("   1. Model focuses on optic disc (center of retina)")
    print("   2. Attention is NOT on image borders/corners")
    print("   3. Predictions align with visual attention")
    print("=" * 60)


if __name__ == "__main__":
    main()
