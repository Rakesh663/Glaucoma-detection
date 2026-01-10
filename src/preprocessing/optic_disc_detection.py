"""
Optic Disc Detection and ROI Cropping
Enhances model accuracy by focusing on the clinically relevant region

Key Features:
1. Automatic optic disc localization using morphological operations
2. ROI cropping to focus on optic disc and cup region  
3. Fallback to center crop if detection fails
4. Integration with existing preprocessing pipeline
"""

import cv2
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class OpticDiscRegion:
    """Detected optic disc region information."""
    center_x: int
    center_y: int
    radius: int
    confidence: float
    roi: np.ndarray  # Cropped ROI image
    original_size: Tuple[int, int]


class OpticDiscDetector:
    """
    Detects and crops the optic disc region from fundus images.
    
    The optic disc is typically:
    - Bright circular/oval region
    - Located on the nasal side of the retina
    - Contains the optic cup (darker center)
    
    This detector uses:
    1. Red channel analysis (optic disc appears bright)
    2. Morphological operations for blob detection
    3. Hough circle detection
    4. Size and position heuristics
    """
    
    def __init__(
        self,
        roi_scale: float = 2.5,  # ROI size relative to disc radius
        min_disc_ratio: float = 0.05,  # Min disc size as fraction of image
        max_disc_ratio: float = 0.25,  # Max disc size as fraction of image
        target_roi_size: Tuple[int, int] = (512, 512),
        use_clahe: bool = True
    ):
        """
        Initialize optic disc detector.
        
        Args:
            roi_scale: How much larger to make ROI than detected disc
            min_disc_ratio: Minimum optic disc size relative to image
            max_disc_ratio: Maximum optic disc size relative to image
            target_roi_size: Output ROI dimensions
            use_clahe: Apply CLAHE for better detection
        """
        self.roi_scale = roi_scale
        self.min_disc_ratio = min_disc_ratio
        self.max_disc_ratio = max_disc_ratio
        self.target_roi_size = target_roi_size
        self.use_clahe = use_clahe
    
    def detect(self, image: np.ndarray) -> Optional[OpticDiscRegion]:
        """
        Detect optic disc and extract ROI.
        
        Args:
            image: RGB fundus image (H, W, 3)
            
        Returns:
            OpticDiscRegion if detected, None otherwise
        """
        if image is None or image.size == 0:
            return None
        
        h, w = image.shape[:2]
        original_size = (h, w)
        
        # Try multiple detection methods
        result = self._detect_by_brightness(image)
        
        if result is None:
            result = self._detect_by_hough(image)
        
        if result is None:
            # Fallback: center crop (optic disc often near center-right)
            result = self._fallback_center_crop(image)
        
        if result is not None:
            result.original_size = original_size
            result.roi = self._extract_roi(image, result)
        
        return result
    
    def _detect_by_brightness(self, image: np.ndarray) -> Optional[OpticDiscRegion]:
        """Detect optic disc using brightness analysis."""
        h, w = image.shape[:2]
        
        # Use red channel (optic disc is bright in red)
        if len(image.shape) == 3:
            red_channel = image[:, :, 0]
        else:
            red_channel = image
        
        # Apply CLAHE for better contrast
        if self.use_clahe:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            red_channel = clahe.apply(red_channel)
        
        # Threshold to find bright regions
        thresh_value = np.percentile(red_channel, 95)
        _, binary = cv2.threshold(red_channel, int(thresh_value), 255, cv2.THRESH_BINARY)
        
        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Find the most circular, appropriately sized contour
        min_area = (self.min_disc_ratio * min(h, w)) ** 2 * np.pi
        max_area = (self.max_disc_ratio * min(h, w)) ** 2 * np.pi
        
        best_contour = None
        best_circularity = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if area < min_area or area > max_area:
                continue
            
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * np.pi * area / (perimeter ** 2)
            
            if circularity > best_circularity and circularity > 0.5:
                best_circularity = circularity
                best_contour = contour
        
        if best_contour is None:
            return None
        
        # Get enclosing circle
        (cx, cy), radius = cv2.minEnclosingCircle(best_contour)
        
        return OpticDiscRegion(
            center_x=int(cx),
            center_y=int(cy),
            radius=int(radius),
            confidence=best_circularity,
            roi=None,
            original_size=(h, w)
        )
    
    def _detect_by_hough(self, image: np.ndarray) -> Optional[OpticDiscRegion]:
        """Detect optic disc using Hough circle detection."""
        h, w = image.shape[:2]
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        # Apply Gaussian blur
        gray = cv2.GaussianBlur(gray, (9, 9), 2)
        
        # Calculate radius range
        min_radius = int(self.min_disc_ratio * min(h, w))
        max_radius = int(self.max_disc_ratio * min(h, w))
        
        # Detect circles
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=min(h, w) // 4,
            param1=100,
            param2=30,
            minRadius=min_radius,
            maxRadius=max_radius
        )
        
        if circles is None:
            return None
        
        # Take the brightest circle as optic disc
        best_circle = None
        best_brightness = 0
        
        for circle in circles[0]:
            cx, cy, r = circle
            cx, cy, r = int(cx), int(cy), int(r)
            
            # Create mask for this circle
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            
            # Calculate mean brightness
            if len(image.shape) == 3:
                brightness = cv2.mean(image[:, :, 0], mask=mask)[0]
            else:
                brightness = cv2.mean(image, mask=mask)[0]
            
            if brightness > best_brightness:
                best_brightness = brightness
                best_circle = (cx, cy, r)
        
        if best_circle is None:
            return None
        
        cx, cy, r = best_circle
        
        return OpticDiscRegion(
            center_x=cx,
            center_y=cy,
            radius=r,
            confidence=0.7,  # Hough detection confidence
            roi=None,
            original_size=(h, w)
        )
    
    def _fallback_center_crop(self, image: np.ndarray) -> OpticDiscRegion:
        """
        Fallback: crop from center-right region (typical optic disc location).
        
        In standard fundus photos:
        - Right eye: optic disc is on the left side
        - Left eye: optic disc is on the right side
        - We crop a generous center region to cover both cases
        """
        h, w = image.shape[:2]
        
        # Optic disc is typically in center-left or center-right
        # Use center with slight bias to the right
        cx = int(w * 0.55)
        cy = int(h * 0.5)
        
        # Estimate radius based on typical fundus proportions
        radius = int(min(h, w) * 0.12)
        
        return OpticDiscRegion(
            center_x=cx,
            center_y=cy,
            radius=radius,
            confidence=0.3,  # Low confidence for fallback
            roi=None,
            original_size=(h, w)
        )
    
    def _extract_roi(self, image: np.ndarray, region: OpticDiscRegion) -> np.ndarray:
        """Extract ROI around detected optic disc."""
        h, w = image.shape[:2]
        
        # Calculate ROI bounds
        roi_radius = int(region.radius * self.roi_scale)
        
        x1 = max(0, region.center_x - roi_radius)
        y1 = max(0, region.center_y - roi_radius)
        x2 = min(w, region.center_x + roi_radius)
        y2 = min(h, region.center_y + roi_radius)
        
        # Extract ROI
        roi = image[y1:y2, x1:x2].copy()
        
        # Resize to target size
        if roi.size > 0:
            roi = cv2.resize(roi, self.target_roi_size, interpolation=cv2.INTER_LANCZOS4)
        
        return roi
    
    def __call__(self, image: np.ndarray) -> np.ndarray:
        """
        Detect optic disc and return cropped ROI.
        
        Args:
            image: RGB fundus image
            
        Returns:
            Cropped ROI focused on optic disc region
        """
        result = self.detect(image)
        
        if result is not None and result.roi is not None:
            return result.roi
        
        # If detection completely fails, return resized original
        return cv2.resize(image, self.target_roi_size, interpolation=cv2.INTER_LANCZOS4)


def detect_optic_disc(
    image: np.ndarray,
    roi_scale: float = 2.5,
    target_size: Tuple[int, int] = (512, 512)
) -> Tuple[np.ndarray, float]:
    """
    Convenience function to detect optic disc and crop.
    
    Args:
        image: RGB fundus image
        roi_scale: ROI size multiplier
        target_size: Output size
        
    Returns:
        Tuple of (cropped ROI, detection confidence)
    """
    detector = OpticDiscDetector(
        roi_scale=roi_scale,
        target_roi_size=target_size
    )
    
    result = detector.detect(image)
    
    if result is not None:
        return result.roi, result.confidence
    
    # Fallback
    roi = cv2.resize(image, target_size, interpolation=cv2.INTER_LANCZOS4)
    return roi, 0.0


if __name__ == "__main__":
    # Test the detector
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        image = cv2.imread(image_path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        detector = OpticDiscDetector(target_roi_size=(512, 512))
        result = detector.detect(image)
        
        if result:
            print(f"Optic disc detected!")
            print(f"  Center: ({result.center_x}, {result.center_y})")
            print(f"  Radius: {result.radius}")
            print(f"  Confidence: {result.confidence:.2f}")
            print(f"  ROI shape: {result.roi.shape}")
        else:
            print("Optic disc not detected, using fallback")
