"""
Clinical-Grade Inference Engine for Glaucoma Detection
Production-ready with TTA, uncertainty estimation, and explainability

Key Features:
1. Fundus-specific preprocessing
2. Image quality assessment
3. Test-Time Augmentation (TTA)
4. Uncertainty estimation (Monte Carlo Dropout)
5. Grad-CAM explainability for doctors
6. Clinical decision support
"""

import os
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
import cv2
import yaml
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
import warnings
from datetime import datetime


# Import preprocessing modules
try:
    from preprocessing import (
        FundusPreprocessor,
        QualityAssessor,
        get_tta_transforms
    )
    from preprocessing.fundus_preprocessing import FUNDUS_MEAN, FUNDUS_STD
    HAS_PREPROCESSING = True
except ImportError:
    HAS_PREPROCESSING = False
    warnings.warn("Preprocessing modules not found. Using basic preprocessing.")
    FUNDUS_MEAN = [0.485, 0.285, 0.156]
    FUNDUS_STD = [0.229, 0.184, 0.134]

# Import model and Grad-CAM - support both relative and absolute imports
try:
    from src.model import create_model, optimize_for_cpu, GradCAM
except ImportError:
    try:
        from model import create_model, optimize_for_cpu, GradCAM
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.model import create_model, optimize_for_cpu, GradCAM



@dataclass
class PredictionResult:
    """Structured prediction result with all clinical information."""
    prediction: int  # 0 = normal, 1 = glaucoma
    label: str  # "normal" or "glaucoma"
    probability: float  # Probability of glaucoma
    confidence: float  # Confidence in prediction
    risk_level: str  # "Low", "Moderate", "High"
    uncertainty: float  # Model uncertainty (0-1)
    is_uncertain: bool  # Flag for high uncertainty
    quality_score: Optional[float]  # Image quality score
    quality_acceptable: bool  # Whether image quality is acceptable
    recommendations: List[str]  # Clinical recommendations
    attention_map: Optional[np.ndarray]  # Attention visualization
    gradcam_overlay: Optional[np.ndarray]  # Grad-CAM explanation
    confidence_interval: Tuple[float, float]  # 95% CI
    processing_time_ms: float  # Processing time
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            'prediction': self.prediction,
            'label': self.label,
            'probability': round(self.probability, 4),
            'confidence': round(self.confidence, 4),
            'risk_level': self.risk_level,
            'uncertainty': round(self.uncertainty, 4),
            'is_uncertain': self.is_uncertain,
            'quality_score': round(self.quality_score, 3) if self.quality_score else None,
            'quality_acceptable': self.quality_acceptable,
            'recommendations': self.recommendations,
            'confidence_interval': {
                'lower': round(self.confidence_interval[0], 4),
                'upper': round(self.confidence_interval[1], 4)
            },
            'processing_time_ms': round(self.processing_time_ms, 2)
        }


class GlaucomaDetector:
    """
    Production-grade inference engine for glaucoma detection.
    Designed for real-world hospital deployment.
    """
    
    # Risk level thresholds
    RISK_THRESHOLDS = {
        'low': 0.3,
        'moderate': 0.7,
        'high': 1.0
    }
    
    # Uncertainty threshold for flagging
    UNCERTAINTY_THRESHOLD = 0.15
    
    def __init__(
        self,
        model_path: str,
        config_path: Optional[str] = None,
        device: str = 'cpu',
        use_tta: bool = True,
        tta_augments: int = 5,
        use_mc_dropout: bool = True,
        mc_samples: int = 10,
        generate_explanations: bool = True
    ):
        """
        Initialize detector.
        
        Args:
            model_path: Path to model checkpoint
            config_path: Path to config file
            device: Device to use ('cpu' or 'cuda')
            use_tta: Enable Test-Time Augmentation
            tta_augments: Number of TTA augmentations
            use_mc_dropout: Enable Monte Carlo Dropout
            mc_samples: Number of MC samples
            generate_explanations: Generate Grad-CAM explanations
        """
        self.device = torch.device(device)
        self.use_tta = use_tta
        self.tta_augments = tta_augments
        self.use_mc_dropout = use_mc_dropout
        self.mc_samples = mc_samples
        self.generate_explanations = generate_explanations
        
        # Load config
        self.config = self._load_config(config_path)
        
        # Setup CPU optimization
        self._setup_cpu_optimization()
        
        # Load model
        print(f"🔄 Loading model: {model_path}")
        self.model = self._load_model(model_path)
        self.model.eval()
        
        # Initialize Grad-CAM
        if self.generate_explanations:
            try:
                self.gradcam = GradCAM(self.model)
                print("✅ Grad-CAM initialized for explainability")
            except Exception as e:
                print(f"⚠️ Grad-CAM initialization failed: {e}")
                self.gradcam = None
        else:
            self.gradcam = None
        
        # Initialize preprocessors
        if HAS_PREPROCESSING:
            self.preprocessor = FundusPreprocessor(
                target_size=(self.config['data']['image_size'],) * 2,
                apply_clahe=True,
                clahe_clip_limit=3.0,
                enhance_green_channel=True,
                crop_to_roi=True,
                illumination_correction=True,
                normalize_output=False
            )
            self.quality_assessor = QualityAssessor()
            self.tta_transforms = get_tta_transforms(self.config, self.tta_augments)
            print("✅ Clinical preprocessing initialized")
        else:
            self.preprocessor = None
            self.quality_assessor = None
            self.tta_transforms = None
        
        # Basic transform for final normalization
        self.transform = self._get_transform()
        
        print("✅ GlaucomaDetector ready")
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration."""
        default_config = {
            'data': {'image_size': 512},
            'normalization': {
                'type': 'fundus',
                'fundus_mean': FUNDUS_MEAN,
                'fundus_std': FUNDUS_STD
            },
            'evaluation': {'threshold': 0.5},
            'model': {
                'architecture': 'efficientnet_b0',
                'num_classes': 1,
                'pretrained': False,
                'dropout': 0.3,
                'use_attention': True
            }
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
                # Merge with defaults
                for key in loaded_config:
                    if key in default_config and isinstance(default_config[key], dict):
                        default_config[key].update(loaded_config[key])
                    else:
                        default_config[key] = loaded_config[key]
        
        return default_config
    
    def _setup_cpu_optimization(self):
        """Configure CPU optimizations."""
        num_threads = min(8, os.cpu_count() or 8)
        os.environ["OMP_NUM_THREADS"] = str(num_threads)
        os.environ["MKL_NUM_THREADS"] = str(num_threads)
        torch.set_num_threads(num_threads)
        
        if torch.backends.mkldnn.is_available():
            torch.backends.mkldnn.enabled = True
    
    def _load_model(self, model_path: str):
        """Load model from checkpoint."""
        # Check if TorchScript model
        if model_path.endswith('.pt') and 'scripted' in model_path.lower():
            model = torch.jit.load(model_path, map_location=self.device)
            return model
        
        # Create model from config
        model = create_model(self.config)
        
        # Load weights
        checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
        
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)
        
        # Optimize for CPU
        model = optimize_for_cpu(model, quantize=False)
        
        return model.to(self.device)
    
    def _get_transform(self):
        """Get preprocessing transform."""
        import albumentations as A
        from albumentations.pytorch import ToTensorV2
        
        image_size = self.config['data']['image_size']
        mean = self.config['normalization'].get('fundus_mean', FUNDUS_MEAN)
        std = self.config['normalization'].get('fundus_std', FUNDUS_STD)
        
        return A.Compose([
            A.Resize(image_size, image_size),
            A.Normalize(mean=mean, std=std),
            ToTensorV2()
        ])
    
    def preprocess(self, image: Union[np.ndarray, Image.Image, str]) -> Tuple[torch.Tensor, np.ndarray]:
        """
        Preprocess image for inference.
        
        Args:
            image: Input image (path, PIL, or numpy)
            
        Returns:
            Tuple of (tensor, original numpy image for visualization)
        """
        # Load if path
        if isinstance(image, str):
            image = Image.open(image).convert('RGB')
        
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        original_image = image.copy()
        
        # Apply fundus preprocessing
        if self.preprocessor is not None:
            try:
                image = self.preprocessor(image)
                if image.dtype == np.float32:
                    image = (image * 255).astype(np.uint8)
            except Exception as e:
                warnings.warn(f"Preprocessing failed: {e}")
        
        # Apply normalization transform
        augmented = self.transform(image=image)
        image_tensor = augmented['image']
        
        # Add batch dimension
        image_tensor = image_tensor.unsqueeze(0)
        
        # Convert to channels_last for CPU optimization
        image_tensor = image_tensor.to(self.device, memory_format=torch.channels_last)
        
        return image_tensor, original_image
    
    def assess_quality(self, image: Union[np.ndarray, Image.Image]) -> Tuple[float, bool, List[str]]:
        """
        Assess image quality.
        
        Returns:
            Tuple of (quality_score, is_acceptable, issues)
        """
        if self.quality_assessor is None:
            return 1.0, True, []
        
        try:
            if isinstance(image, Image.Image):
                image = np.array(image)
            
            report = self.quality_assessor.assess(image)
            return report.overall_score, report.is_acceptable, report.issues
        except Exception as e:
            warnings.warn(f"Quality assessment failed: {e}")
            return 1.0, True, []
    
    @torch.no_grad()
    def predict(
        self,
        image: Union[np.ndarray, Image.Image, str],
        return_explanation: bool = True
    ) -> PredictionResult:
        """
        Make prediction with full clinical output.
        
        Args:
            image: Input image
            return_explanation: Generate Grad-CAM explanation
            
        Returns:
            PredictionResult with all clinical information
        """
        start_time = datetime.now()
        
        # Load image if path
        if isinstance(image, str):
            image = Image.open(image).convert('RGB')
        
        original_image = np.array(image) if isinstance(image, Image.Image) else image.copy()
        
        # Assess quality
        quality_score, quality_acceptable, quality_issues = self.assess_quality(original_image)
        
        # Preprocess
        image_tensor, _ = self.preprocess(image)
        
        # Make prediction with optional TTA and MC Dropout
        if self.use_tta and self.tta_transforms is not None:
            result = self._predict_with_tta(original_image)
        elif self.use_mc_dropout and hasattr(self.model, 'predict_with_uncertainty'):
            result = self._predict_with_uncertainty(image_tensor)
        else:
            result = self._predict_simple(image_tensor)
        
        # Generate explanation if requested
        attention_map = None
        gradcam_overlay = None
        
        if return_explanation and self.generate_explanations:
            try:
                if self.gradcam is not None:
                    # Re-enable gradients for Grad-CAM
                    image_tensor.requires_grad_(True)
                    gradcam_heatmap = self.gradcam.generate(image_tensor)
                    gradcam_overlay = self.gradcam.generate_overlay(
                        original_image, image_tensor
                    )
                
                # Get attention map if available
                if hasattr(self.model, 'attention_map'):
                    attention_map = self.model.attention_map.squeeze().cpu().numpy()
            except Exception as e:
                warnings.warn(f"Explanation generation failed: {e}")
        
        # Determine risk level and recommendations
        risk_level = self._get_risk_level(result['probability'])
        recommendations = self._get_recommendations(
            result['probability'],
            result['uncertainty'],
            quality_acceptable
        )
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Determine if uncertain
        is_uncertain = result['uncertainty'] > self.UNCERTAINTY_THRESHOLD
        
        return PredictionResult(
            prediction=result['prediction'],
            label='glaucoma' if result['prediction'] == 1 else 'normal',
            probability=result['probability'],
            confidence=result['confidence'],
            risk_level=risk_level,
            uncertainty=result['uncertainty'],
            is_uncertain=is_uncertain,
            quality_score=quality_score,
            quality_acceptable=quality_acceptable,
            recommendations=recommendations,
            attention_map=attention_map,
            gradcam_overlay=gradcam_overlay,
            confidence_interval=result['ci'],
            processing_time_ms=processing_time
        )
    
    def _predict_simple(self, image_tensor: torch.Tensor) -> Dict:
        """Simple prediction without TTA or MC Dropout."""
        logits = self.model(image_tensor)
        prob = torch.sigmoid(logits).item()
        
        threshold = self.config['evaluation']['threshold']
        prediction = int(prob >= threshold)
        
        return {
            'prediction': prediction,
            'probability': prob,
            'confidence': prob if prediction == 1 else (1 - prob),
            'uncertainty': 0.0,  # No uncertainty estimate without MC
            'ci': (prob, prob)  # No confidence interval
        }
    
    def _predict_with_uncertainty(self, image_tensor: torch.Tensor) -> Dict:
        """Prediction with Monte Carlo Dropout uncertainty."""
        try:
            result = self.model.predict_with_uncertainty(
                image_tensor,
                n_samples=self.mc_samples
            )
            
            prob = result['prediction'].item()
            uncertainty = result['uncertainty'].item()
            ci_low = result['ci_low'].item()
            ci_high = result['ci_high'].item()
            
        except Exception as e:
            warnings.warn(f"MC Dropout failed: {e}")
            return self._predict_simple(image_tensor)
        
        threshold = self.config['evaluation']['threshold']
        prediction = int(prob >= threshold)
        
        return {
            'prediction': prediction,
            'probability': prob,
            'confidence': prob if prediction == 1 else (1 - prob),
            'uncertainty': uncertainty,
            'ci': (ci_low, ci_high)
        }
    
    def _predict_with_tta(self, image: np.ndarray) -> Dict:
        """Prediction with Test-Time Augmentation."""
        probabilities = []
        
        for transform in self.tta_transforms:
            try:
                augmented = transform(image=image)
                image_tensor = augmented['image'].unsqueeze(0)
                image_tensor = image_tensor.to(self.device, memory_format=torch.channels_last)
                
                logits = self.model(image_tensor)
                prob = torch.sigmoid(logits).item()
                probabilities.append(prob)
            except Exception as e:
                warnings.warn(f"TTA augmentation failed: {e}")
                continue
        
        if not probabilities:
            # Fallback to simple prediction
            image_tensor, _ = self.preprocess(image)
            return self._predict_simple(image_tensor)
        
        # Aggregate TTA predictions
        probabilities = np.array(probabilities)
        mean_prob = probabilities.mean()
        std_prob = probabilities.std()
        
        threshold = self.config['evaluation']['threshold']
        prediction = int(mean_prob >= threshold)
        
        return {
            'prediction': prediction,
            'probability': float(mean_prob),
            'confidence': float(mean_prob if prediction == 1 else (1 - mean_prob)),
            'uncertainty': float(std_prob),
            'ci': (float(np.percentile(probabilities, 2.5)),
                   float(np.percentile(probabilities, 97.5)))
        }
    
    def _get_risk_level(self, probability: float) -> str:
        """Determine risk level from probability."""
        if probability < self.RISK_THRESHOLDS['low']:
            return "Low"
        elif probability < self.RISK_THRESHOLDS['moderate']:
            return "Moderate"
        else:
            return "High"
    
    def _get_recommendations(
        self,
        probability: float,
        uncertainty: float,
        quality_acceptable: bool
    ) -> List[str]:
        """Generate clinical recommendations."""
        recommendations = []
        
        # Quality-based recommendations
        if not quality_acceptable:
            recommendations.append(
                "⚠️ Image quality is suboptimal. Consider recapturing for more accurate results."
            )
        
        # Uncertainty-based recommendations
        if uncertainty > self.UNCERTAINTY_THRESHOLD:
            recommendations.append(
                "⚠️ Model uncertainty is high. Manual verification by ophthalmologist recommended."
            )
        
        # Risk-based recommendations
        if probability < 0.3:
            recommendations.extend([
                "✅ Low risk indicators - no immediate signs of glaucoma detected",
                "📅 Continue routine annual eye examinations",
                "🍎 Maintain healthy lifestyle (exercise, balanced diet)",
                "👁️ Report any vision changes to your doctor"
            ])
        elif probability < 0.7:
            recommendations.extend([
                "⚡ Moderate risk indicators detected",
                "📋 Schedule comprehensive eye examination within 1-2 months",
                "🔬 Visual field testing (perimetry) recommended",
                "📊 Regular IOP (intraocular pressure) monitoring advised",
                "👨‍⚕️ Follow up with ophthalmologist for clinical evaluation"
            ])
        else:
            recommendations.extend([
                "🚨 HIGH RISK: Strong indicators of glaucoma detected",
                "📞 URGENT: Schedule ophthalmologist appointment within 1 week",
                "🏥 Comprehensive eye examination including:",
                "   - Optic nerve imaging (OCT)",
                "   - Visual field testing",
                "   - Gonioscopy (drainage angle assessment)",
                "   - IOP measurement",
                "⏰ Early treatment is critical to prevent vision loss"
            ])
        
        return recommendations
    
    def predict_batch(
        self,
        images: List[Union[np.ndarray, Image.Image, str]],
        batch_size: int = 16
    ) -> List[PredictionResult]:
        """
        Batch prediction.
        
        Args:
            images: List of images
            batch_size: Batch size for processing
            
        Returns:
            List of PredictionResults
        """
        results = []
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            
            for image in batch:
                result = self.predict(image, return_explanation=False)
                results.append(result)
        
        return results
    
    def get_model_info(self) -> Dict:
        """Get model information for API endpoints."""
        return {
            'architecture': self.config['model'].get('architecture', 'efficientnet_b0'),
            'image_size': self.config['data']['image_size'],
            'threshold': self.config['evaluation']['threshold'],
            'features': {
                'tta_enabled': self.use_tta,
                'tta_augments': self.tta_augments,
                'mc_dropout_enabled': self.use_mc_dropout,
                'mc_samples': self.mc_samples,
                'explanations_enabled': self.generate_explanations,
                'quality_assessment': self.quality_assessor is not None,
                'clinical_preprocessing': self.preprocessor is not None
            }
        }