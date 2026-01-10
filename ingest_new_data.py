"""
New Data Ingestion and Auto-Labeling Pipeline
For doctors to add new images that get automatically labeled and organized

Usage:
    python ingest_new_data.py --input_folder /path/to/new/images
    python ingest_new_data.py --input_folder /path/to/new/images --retrain
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from PIL import Image
import numpy as np
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.inference import GlaucomaDetector, PredictionResult


class DataIngestionPipeline:
    """
    Pipeline for ingesting new data from doctors/hospitals.
    
    Features:
    - Auto-labeling using trained model
    - Quality filtering
    - Confidence-based sorting
    - Optional human review for uncertain predictions
    - Automatic organization into train/val folders
    - Incremental retraining support
    """
    
    # Confidence thresholds for auto-labeling
    HIGH_CONFIDENCE_THRESHOLD = 0.85  # Auto-label
    LOW_CONFIDENCE_THRESHOLD = 0.60   # Needs review
    
    def __init__(
        self,
        model_path: str = "models/best_model.pth",
        config_path: str = "config/config.yaml",
        data_dir: str = "data",
        review_dir: str = "data/needs_review",
        log_dir: str = "logs/ingestion"
    ):
        """
        Initialize ingestion pipeline.
        
        Args:
            model_path: Path to trained model
            config_path: Path to config file
            data_dir: Base data directory
            review_dir: Directory for uncertain predictions
            log_dir: Directory for ingestion logs
        """
        self.model_path = model_path
        self.config_path = config_path
        self.data_dir = data_dir
        self.review_dir = review_dir
        self.log_dir = log_dir
        
        # Create directories
        os.makedirs(review_dir, exist_ok=True)
        os.makedirs(os.path.join(review_dir, 'normal'), exist_ok=True)
        os.makedirs(os.path.join(review_dir, 'glaucoma'), exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)
        
        # Initialize detector
        print("🔄 Loading model for auto-labeling...")
        self.detector = GlaucomaDetector(
            model_path=model_path,
            config_path=config_path,
            use_tta=True,
            use_mc_dropout=True,
            generate_explanations=False  # Speed up for batch processing
        )
        print("✅ Model loaded")
        
        # Ingestion stats
        self.stats = {
            'total_processed': 0,
            'auto_labeled_normal': 0,
            'auto_labeled_glaucoma': 0,
            'needs_review': 0,
            'rejected_quality': 0,
            'failed': 0
        }
    
    def ingest_folder(
        self,
        input_folder: str,
        destination: str = "train",  # "train" or "val"
        auto_label: bool = True,
        quality_filter: bool = True,
        move_files: bool = False
    ) -> Dict:
        """
        Ingest all images from a folder.
        
        Args:
            input_folder: Folder containing new images
            destination: Where to put labeled images ("train" or "val")
            auto_label: Use model to predict labels
            quality_filter: Reject low-quality images
            move_files: Move instead of copy
            
        Returns:
            Dict with ingestion results
        """
        print(f"\n{'=' * 70}")
        print(f"📁 INGESTING DATA FROM: {input_folder}")
        print(f"{'=' * 70}")
        
        # Get all image files
        image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')
        image_files = []
        
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                if file.lower().endswith(image_extensions):
                    image_files.append(os.path.join(root, file))
        
        print(f"📊 Found {len(image_files)} images")
        
        if len(image_files) == 0:
            print("⚠️ No images found!")
            return self.stats
        
        # Process each image
        results = []
        
        for i, image_path in enumerate(image_files):
            print(f"\r🔄 Processing {i + 1}/{len(image_files)}: {os.path.basename(image_path)}", end="")
            
            try:
                result = self._process_single_image(
                    image_path, destination, quality_filter, move_files
                )
                results.append(result)
            except Exception as e:
                print(f"\n⚠️ Failed to process {image_path}: {e}")
                self.stats['failed'] += 1
        
        print()  # New line after progress
        
        # Save ingestion log
        self._save_log(results, input_folder)
        
        # Print summary
        self._print_summary()
        
        return self.stats
    
    def _process_single_image(
        self,
        image_path: str,
        destination: str,
        quality_filter: bool,
        move_files: bool
    ) -> Dict:
        """Process a single image."""
        self.stats['total_processed'] += 1
        
        # Predict
        result = self.detector.predict(image_path, return_explanation=False)
        
        # Quality check
        if quality_filter and not result.quality_acceptable:
            self.stats['rejected_quality'] += 1
            return {
                'path': image_path,
                'status': 'rejected_quality',
                'quality_score': result.quality_score
            }
        
        # Determine confidence and destination
        confidence = result.confidence
        predicted_label = result.label
        
        if confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            # High confidence - auto-label
            dest_folder = os.path.join(
                self.data_dir, destination, predicted_label
            )
            status = 'auto_labeled'
            
            if predicted_label == 'normal':
                self.stats['auto_labeled_normal'] += 1
            else:
                self.stats['auto_labeled_glaucoma'] += 1
        else:
            # Low confidence - needs review
            dest_folder = os.path.join(self.review_dir, predicted_label)
            status = 'needs_review'
            self.stats['needs_review'] += 1
        
        # Copy/move file
        os.makedirs(dest_folder, exist_ok=True)
        dest_path = os.path.join(dest_folder, os.path.basename(image_path))
        
        # Avoid overwriting
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(dest_path)
            dest_path = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        
        if move_files:
            shutil.move(image_path, dest_path)
        else:
            shutil.copy2(image_path, dest_path)
        
        return {
            'path': image_path,
            'dest_path': dest_path,
            'status': status,
            'predicted_label': predicted_label,
            'probability': result.probability,
            'confidence': confidence,
            'uncertainty': result.uncertainty,
            'quality_score': result.quality_score
        }
    
    def _save_log(self, results: List[Dict], input_folder: str):
        """Save ingestion log."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(
            self.log_dir,
            f"ingestion_{timestamp}.json"
        )
        
        log_data = {
            'timestamp': timestamp,
            'input_folder': input_folder,
            'stats': self.stats,
            'results': results
        }
        
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        print(f"\n📝 Log saved: {log_path}")
    
    def _print_summary(self):
        """Print ingestion summary."""
        print(f"\n{'=' * 70}")
        print("📊 INGESTION SUMMARY")
        print(f"{'=' * 70}")
        print(f"   Total processed: {self.stats['total_processed']}")
        print(f"   Auto-labeled (Normal): {self.stats['auto_labeled_normal']}")
        print(f"   Auto-labeled (Glaucoma): {self.stats['auto_labeled_glaucoma']}")
        print(f"   Needs review: {self.stats['needs_review']}")
        print(f"   Rejected (quality): {self.stats['rejected_quality']}")
        print(f"   Failed: {self.stats['failed']}")
        print(f"{'=' * 70}")
        
        if self.stats['needs_review'] > 0:
            print(f"\n⚠️ {self.stats['needs_review']} images need manual review!")
            print(f"   Check: {self.review_dir}")
    
    def approve_reviewed_images(self, destination: str = "train"):
        """
        Move reviewed images from review folder to training data.
        Call this after manual review.
        """
        review_classes = ['normal', 'glaucoma']
        moved = 0
        
        for class_name in review_classes:
            review_folder = os.path.join(self.review_dir, class_name)
            dest_folder = os.path.join(self.data_dir, destination, class_name)
            
            os.makedirs(dest_folder, exist_ok=True)
            
            if os.path.exists(review_folder):
                for file in os.listdir(review_folder):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        src = os.path.join(review_folder, file)
                        dst = os.path.join(dest_folder, file)
                        shutil.move(src, dst)
                        moved += 1
        
        print(f"✅ Moved {moved} reviewed images to {destination} folder")
        return moved


def retrain_model(config_path: str = "config/config.yaml"):
    """Trigger model retraining with updated data."""
    print("\n🔄 Starting model retraining...")
    
    # Import and run training
    import subprocess
    result = subprocess.run(
        [sys.executable, "src/train.py", "--config", config_path],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    if result.returncode == 0:
        print("✅ Retraining complete!")
    else:
        print("❌ Retraining failed!")
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Ingest and auto-label new fundus images")
    parser.add_argument('--input_folder', type=str, required=True,
                        help="Folder containing new images")
    parser.add_argument('--destination', type=str, default='train',
                        choices=['train', 'val'],
                        help="Where to put labeled images")
    parser.add_argument('--move', action='store_true',
                        help="Move files instead of copying")
    parser.add_argument('--no_quality_filter', action='store_true',
                        help="Disable quality filtering")
    parser.add_argument('--retrain', action='store_true',
                        help="Retrain model after ingestion")
    parser.add_argument('--model_path', type=str, default='models/best_model.pth',
                        help="Path to model for auto-labeling")
    parser.add_argument('--approve_reviewed', action='store_true',
                        help="Move reviewed images to training data")
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = DataIngestionPipeline(
        model_path=args.model_path
    )
    
    if args.approve_reviewed:
        # Move reviewed images
        pipeline.approve_reviewed_images(args.destination)
    else:
        # Ingest new data
        pipeline.ingest_folder(
            input_folder=args.input_folder,
            destination=args.destination,
            quality_filter=not args.no_quality_filter,
            move_files=args.move
        )
    
    # Retrain if requested
    if args.retrain:
        retrain_model()


if __name__ == "__main__":
    main()
