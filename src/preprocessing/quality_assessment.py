"""
Image Quality Assessment for Fundus Images
Detects poor quality images before inference to prevent unreliable predictions

Key Quality Metrics:
1. Blur Detection (Laplacian variance)
2. Exposure Analysis (histogram-based)
3. Artifact Detection (reflection spots, dust)
4. FOV Coverage (how much fundus is visible)
5. Contrast Assessment
6. Overall Quality Score
"""

import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Dict, List, Union, Optional
from dataclasses import dataclass
from enum import Enum


class QualityLevel(Enum):
    """Quality level classifications."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    REJECTED = "rejected"


@dataclass
class QualityReport:
    """Structured quality assessment report."""
    overall_score: float  # 0-1, higher is better
    quality_level: QualityLevel
    is_acceptable: bool
    blur_score: float
    exposure_score: float
    contrast_score: float
    artifact_score: float
    fov_score: float
    issues: List[str]
    recommendations: List[str]
    details: Dict
    
    def to_dict(self) -> Dict:
        """Convert report to dictionary."""
        return {
            'overall_score': round(self.overall_score, 3),
            'quality_level': self.quality_level.value,
            'is_acceptable': self.is_acceptable,
            'scores': {
                'blur': round(self.blur_score, 3),
                'exposure': round(self.exposure_score, 3),
                'contrast': round(self.contrast_score, 3),
                'artifacts': round(self.artifact_score, 3),
                'fov_coverage': round(self.fov_score, 3)
            },
            'issues': self.issues,
            'recommendations': self.recommendations,
            'details': self.details
        }


class QualityAssessor:
    """
    Clinical-grade image quality assessment for fundus images.
    
    Designed to:
    - Detect images that may lead to unreliable predictions
    - Provide actionable feedback for image recapture
    - Filter out poor quality images before processing
    """
    
    # Quality thresholds (tuned for fundus images)
    BLUR_THRESHOLD = 100  # Laplacian variance (lower = more blur)
    MIN_EXPOSURE = 30     # Minimum mean intensity
    MAX_EXPOSURE = 225    # Maximum mean intensity
    MIN_CONTRAST = 40     # Minimum std deviation
    MAX_ARTIFACT_RATIO = 0.05  # Max acceptable artifact coverage
    MIN_FOV_COVERAGE = 0.5     # Minimum fundus area coverage
    
    # Quality level thresholds
    EXCELLENT_THRESHOLD = 0.9
    GOOD_THRESHOLD = 0.75
    ACCEPTABLE_THRESHOLD = 0.5
    POOR_THRESHOLD = 0.3
    
    def __init__(
        self,
        blur_weight: float = 0.25,
        exposure_weight: float = 0.20,
        contrast_weight: float = 0.20,
        artifact_weight: float = 0.15,
        fov_weight: float = 0.20
    ):
        """
        Initialize quality assessor with metric weights.
        
        Args:
            blur_weight: Weight for blur assessment
            exposure_weight: Weight for exposure assessment
            contrast_weight: Weight for contrast assessment
            artifact_weight: Weight for artifact detection
            fov_weight: Weight for FOV coverage
        """
        # Normalize weights
        total = blur_weight + exposure_weight + contrast_weight + artifact_weight + fov_weight
        self.blur_weight = blur_weight / total
        self.exposure_weight = exposure_weight / total
        self.contrast_weight = contrast_weight / total
        self.artifact_weight = artifact_weight / total
        self.fov_weight = fov_weight / total
    
    def __call__(self, image: Union[np.ndarray, Image.Image]) -> QualityReport:
        """Assess image quality and return detailed report."""
        return self.assess(image)
    
    def assess(self, image: Union[np.ndarray, Image.Image]) -> QualityReport:
        """
        Perform comprehensive quality assessment.
        
        Args:
            image: Input fundus image
            
        Returns:
            QualityReport with scores and recommendations
        """
        # Convert to numpy if needed
        if isinstance(image, Image.Image):
            image = np.array(image.convert('RGB'))
        
        # Ensure correct format
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
        # Compute individual quality metrics
        blur_score, blur_details = self._assess_blur(image)
        exposure_score, exposure_details = self._assess_exposure(image)
        contrast_score, contrast_details = self._assess_contrast(image)
        artifact_score, artifact_details = self._assess_artifacts(image)
        fov_score, fov_details = self._assess_fov_coverage(image)
        
        # Compute weighted overall score
        overall_score = (
            self.blur_weight * blur_score +
            self.exposure_weight * exposure_score +
            self.contrast_weight * contrast_score +
            self.artifact_weight * artifact_score +
            self.fov_weight * fov_score
        )
        
        # Determine quality level
        if overall_score >= self.EXCELLENT_THRESHOLD:
            quality_level = QualityLevel.EXCELLENT
        elif overall_score >= self.GOOD_THRESHOLD:
            quality_level = QualityLevel.GOOD
        elif overall_score >= self.ACCEPTABLE_THRESHOLD:
            quality_level = QualityLevel.ACCEPTABLE
        elif overall_score >= self.POOR_THRESHOLD:
            quality_level = QualityLevel.POOR
        else:
            quality_level = QualityLevel.REJECTED
        
        # Determine if acceptable for processing
        is_acceptable = quality_level in [
            QualityLevel.EXCELLENT,
            QualityLevel.GOOD,
            QualityLevel.ACCEPTABLE
        ]
        
        # Generate issues list
        issues = []
        recommendations = []
        
        if blur_score < 0.5:
            issues.append("Image is blurry")
            recommendations.append("Ensure patient is still and camera is focused properly")
        
        if exposure_score < 0.5:
            if exposure_details.get('mean_intensity', 128) < self.MIN_EXPOSURE:
                issues.append("Image is underexposed (too dark)")
                recommendations.append("Increase lighting or camera exposure settings")
            else:
                issues.append("Image is overexposed (too bright)")
                recommendations.append("Reduce lighting or camera exposure settings")
        
        if contrast_score < 0.5:
            issues.append("Low contrast - vessel structures not clearly visible")
            recommendations.append("Adjust camera settings for better contrast")
        
        if artifact_score < 0.5:
            issues.append("Artifacts detected (reflections or dust)")
            recommendations.append("Clean camera lens and reduce direct reflections")
        
        if fov_score < 0.5:
            issues.append("Incomplete fundus visibility")
            recommendations.append("Reposition camera to capture full fundus")
        
        if not issues:
            recommendations.append("Image quality is acceptable for analysis")
        
        # Compile details
        details = {
            'blur': blur_details,
            'exposure': exposure_details,
            'contrast': contrast_details,
            'artifacts': artifact_details,
            'fov': fov_details,
            'image_size': image.shape[:2]
        }
        
        return QualityReport(
            overall_score=overall_score,
            quality_level=quality_level,
            is_acceptable=is_acceptable,
            blur_score=blur_score,
            exposure_score=exposure_score,
            contrast_score=contrast_score,
            artifact_score=artifact_score,
            fov_score=fov_score,
            issues=issues,
            recommendations=recommendations,
            details=details
        )
    
    def _assess_blur(self, image: np.ndarray) -> Tuple[float, Dict]:
        """
        Assess image blur using Laplacian variance.
        Higher variance = sharper image.
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Compute Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        
        # Also compute gradient magnitude
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.mean(np.sqrt(sobelx**2 + sobely**2))
        
        # Normalize to 0-1 score (higher is better)
        # Using sigmoid-like mapping for smooth threshold
        score = 1 / (1 + np.exp(-(variance - self.BLUR_THRESHOLD) / 50))
        
        details = {
            'laplacian_variance': float(variance),
            'gradient_magnitude': float(gradient_magnitude),
            'threshold': self.BLUR_THRESHOLD
        }
        
        return float(np.clip(score, 0, 1)), details
    
    def _assess_exposure(self, image: np.ndarray) -> Tuple[float, Dict]:
        """
        Assess image exposure using histogram analysis.
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        mean_intensity = np.mean(gray)
        
        # Check if within acceptable range
        if mean_intensity < self.MIN_EXPOSURE:
            # Underexposed - score based on how dark
            score = mean_intensity / self.MIN_EXPOSURE
        elif mean_intensity > self.MAX_EXPOSURE:
            # Overexposed - score based on how bright
            score = (255 - mean_intensity) / (255 - self.MAX_EXPOSURE)
        else:
            # Good exposure
            # Prefer middle range
            optimal = (self.MIN_EXPOSURE + self.MAX_EXPOSURE) / 2
            distance = abs(mean_intensity - optimal)
            max_distance = (self.MAX_EXPOSURE - self.MIN_EXPOSURE) / 2
            score = 1 - (distance / max_distance) * 0.3  # Small penalty for non-optimal
        
        # Histogram analysis
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()
        
        # Check for clipping (too many pixels at 0 or 255)
        clipping_low = hist[0:5].sum()
        clipping_high = hist[250:256].sum()
        total_clipping = clipping_low + clipping_high
        
        # Penalize clipping
        if total_clipping > 0.1:
            score *= (1 - total_clipping)
        
        details = {
            'mean_intensity': float(mean_intensity),
            'clipping_low': float(clipping_low),
            'clipping_high': float(clipping_high),
            'acceptable_range': (self.MIN_EXPOSURE, self.MAX_EXPOSURE)
        }
        
        return float(np.clip(score, 0, 1)), details
    
    def _assess_contrast(self, image: np.ndarray) -> Tuple[float, Dict]:
        """
        Assess image contrast using standard deviation and dynamic range.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        std_dev = np.std(gray)
        dynamic_range = np.max(gray) - np.min(gray)
        
        # Score based on standard deviation
        if std_dev < self.MIN_CONTRAST:
            score = std_dev / self.MIN_CONTRAST
        else:
            score = min(1.0, 0.7 + (std_dev - self.MIN_CONTRAST) / 100)
        
        # Also consider dynamic range
        if dynamic_range < 100:
            score *= dynamic_range / 100
        
        details = {
            'std_deviation': float(std_dev),
            'dynamic_range': float(dynamic_range),
            'min_contrast_threshold': self.MIN_CONTRAST
        }
        
        return float(np.clip(score, 0, 1)), details
    
    def _assess_artifacts(self, image: np.ndarray) -> Tuple[float, Dict]:
        """
        Detect artifacts like reflections, dust spots, and other anomalies.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Detect bright spots (reflections)
        _, bright_spots = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)
        bright_ratio = np.sum(bright_spots > 0) / bright_spots.size
        
        # Detect very dark spots (potential dust)
        _, dark_spots = cv2.threshold(gray, 5, 255, cv2.THRESH_BINARY_INV)
        dark_ratio = np.sum(dark_spots > 0) / dark_spots.size
        
        # Total artifact ratio
        total_artifact_ratio = bright_ratio + dark_ratio
        
        # Score (lower artifacts = higher score)
        if total_artifact_ratio > self.MAX_ARTIFACT_RATIO:
            score = self.MAX_ARTIFACT_RATIO / total_artifact_ratio
        else:
            score = 1 - (total_artifact_ratio / self.MAX_ARTIFACT_RATIO) * 0.2
        
        details = {
            'bright_spot_ratio': float(bright_ratio),
            'dark_spot_ratio': float(dark_ratio),
            'total_artifact_ratio': float(total_artifact_ratio),
            'max_acceptable': self.MAX_ARTIFACT_RATIO
        }
        
        return float(np.clip(score, 0, 1)), details
    
    def _assess_fov_coverage(self, image: np.ndarray) -> Tuple[float, Dict]:
        """
        Assess how much of the fundus is visible in the image.
        Detects if image has too much black border or incomplete capture.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Threshold to find fundus region
        _, mask = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
        
        # Calculate coverage ratio
        coverage_ratio = np.sum(mask > 0) / mask.size
        
        # Score based on coverage
        if coverage_ratio < self.MIN_FOV_COVERAGE:
            score = coverage_ratio / self.MIN_FOV_COVERAGE
        else:
            # Slight preference for higher coverage but not required
            score = 0.8 + (coverage_ratio - self.MIN_FOV_COVERAGE) * 0.4
        
        # Check for circular fundus shape
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        circularity = 0
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            perimeter = cv2.arcLength(largest_contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)
        
        details = {
            'coverage_ratio': float(coverage_ratio),
            'circularity': float(circularity),
            'min_coverage_threshold': self.MIN_FOV_COVERAGE
        }
        
        return float(np.clip(score, 0, 1)), details
    
    def is_quality_acceptable(self, image: Union[np.ndarray, Image.Image]) -> bool:
        """Quick check if image quality is acceptable for processing."""
        report = self.assess(image)
        return report.is_acceptable


def assess_image_quality(
    image: Union[np.ndarray, Image.Image, str],
    return_dict: bool = False
) -> Union[QualityReport, Dict]:
    """
    Convenience function for quick quality assessment.
    
    Args:
        image: Input image (numpy, PIL, or file path)
        return_dict: If True, return dict instead of QualityReport
        
    Returns:
        QualityReport or dict with quality assessment
    """
    if isinstance(image, str):
        image = Image.open(image).convert('RGB')
    
    assessor = QualityAssessor()
    report = assessor.assess(image)
    
    if return_dict:
        return report.to_dict()
    return report
