#!/usr/bin/env python
# app/services/quality/assessment.py
import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class QualityAssessor:
    """
    Assesses the quality of receipt images for processing suitability.
    """
    
    def __init__(self, min_quality_score: float = 50.0):
        """
        Initialize the quality assessor.
        
        Args:
            min_quality_score: Minimum acceptable quality score (0-100)
        """
        self.min_quality_score = min_quality_score
        
    def assess_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Assess the quality of an image.
        
        Args:
            image_path: Path to the image
            
        Returns:
            Dictionary containing quality metrics
        """
        try:
            # Read image
            img = cv2.imread(str(image_path))
            if img is None:
                return {
                    "success": False,
                    "error": f"Failed to read image: {image_path}",
                    "overall_score": 0.0,
                }
            
            # Convert to grayscale for some metrics
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate various quality metrics
            blur_score = self._calculate_blur_score(gray)
            lighting_score = self._calculate_lighting_score(gray)
            contrast_score = self._calculate_contrast_score(gray)
            size_score = self._calculate_size_score(img.shape)
            
            # Check for potential fold lines
            fold_detected, fold_severity = self._detect_folds(gray)
            
            # Calculate overall quality score
            overall_score = self._calculate_overall_score({
                "blur": blur_score,
                "lighting": lighting_score,
                "contrast": contrast_score,
                "size": size_score,
                "fold": 100.0 if not fold_detected else (100.0 - fold_severity * 20.0)
            })
            
            # Create assessment result
            result = {
                "success": True,
                "metrics": {
                    "blur_score": blur_score,
                    "lighting_score": lighting_score,
                    "contrast_score": contrast_score,
                    "size_score": size_score,
                    "fold_detected": fold_detected,
                    "fold_severity": fold_severity if fold_detected else 0.0,
                },
                "overall_score": overall_score,
                "is_acceptable": overall_score >= self.min_quality_score,
                "improvement_suggestions": self._generate_suggestions({
                    "blur": blur_score,
                    "lighting": lighting_score,
                    "contrast": contrast_score,
                    "size": size_score,
                    "fold": fold_detected,
                    "fold_severity": fold_severity if fold_detected else 0.0,
                }),
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"Error assessing image quality: {e}")
            return {
                "success": False,
                "error": f"Error assessing image quality: {str(e)}",
                "overall_score": 0.0,
            }
    
    def _calculate_blur_score(self, gray_img: np.ndarray) -> float:
        """
        Calculate blur score using Laplacian variance.
        Higher variance = less blurry (higher score)
        
        Args:
            gray_img: Grayscale image
            
        Returns:
            Blur score (0-100)
        """
        # Use Laplacian for edge detection
        laplacian = cv2.Laplacian(gray_img, cv2.CV_64F)
        
        # Calculate variance of Laplacian
        variance = laplacian.var()
        
        # Map variance to a 0-100 score
        # These thresholds might need adjustment based on your specific requirements
        if variance < 10:
            return 0.0  # Very blurry
        elif variance < 100:
            return (variance - 10) / 90 * 50  # Map 10-100 to 0-50
        elif variance < 1000:
            return 50 + (variance - 100) / 900 * 50  # Map 100-1000 to 50-100
        else:
            return 100.0  # Very sharp
    
    def _calculate_lighting_score(self, gray_img: np.ndarray) -> float:
        """
        Calculate lighting score based on average brightness and std dev.
        
        Args:
            gray_img: Grayscale image
            
        Returns:
            Lighting score (0-100)
        """
        # Calculate mean brightness
        mean = gray_img.mean()
        
        # Calculate standard deviation of brightness
        std = gray_img.std()
        
        # Ideal mean would be around 127 (middle of 0-255)
        # Penalize if too dark or too bright
        mean_score = 100 - abs(mean - 127) / 127 * 100
        
        # Higher std dev generally means better contrast
        # But we'll cap at 60 for reasonable balance
        std_score = min(std / 60 * 100, 100)
        
        # Combine scores (weighted)
        return 0.6 * mean_score + 0.4 * std_score
    
    def _calculate_contrast_score(self, gray_img: np.ndarray) -> float:
        """
        Calculate contrast score.
        
        Args:
            gray_img: Grayscale image
            
        Returns:
            Contrast score (0-100)
        """
        # Calculate histogram
        hist = cv2.calcHist([gray_img], [0], None, [256], [0, 256])
        
        # Calculate percentage of pixels in each brightness range
        total_pixels = gray_img.shape[0] * gray_img.shape[1]
        dark_pixels = np.sum(hist[:50]) / total_pixels
        mid_pixels = np.sum(hist[50:200]) / total_pixels
        bright_pixels = np.sum(hist[200:]) / total_pixels
        
        # Ideal: good distribution across ranges with emphasis on mid-range
        # This is a simplified model - real receipts may need different distributions
        score = (
            (0.2 * min(dark_pixels * 500, 100)) +  # Want some dark pixels (text)
            (0.6 * min(mid_pixels * 200, 100)) +   # Want many mid pixels
            (0.2 * min(bright_pixels * 500, 100))  # Want some bright pixels (background)
        )
        
        return score
    
    def _calculate_size_score(self, shape: Tuple[int, int, int]) -> float:
        """
        Calculate score based on image dimensions.
        
        Args:
            shape: Image shape (height, width, channels)
            
        Returns:
            Size score (0-100)
        """
        height, width = shape[0], shape[1]
        
        # Minimum recommended dimensions for good OCR
        min_height, min_width = 800, 600
        
        # Calculate size score
        if height < min_height or width < min_width:
            # Penalize if below minimum dimensions
            return min(height / min_height, width / min_width) * 100
        else:
            # Full score if dimensions are adequate
            return 100.0
    
    def _detect_folds(self, gray_img: np.ndarray) -> Tuple[bool, float]:
        """
        Detect potential fold lines in the image.
        
        Args:
            gray_img: Grayscale image
            
        Returns:
            Tuple of (fold_detected, fold_severity)
            fold_severity is a value between 0 and 5, with 5 being the most severe
        """
        # Apply edge detection
        edges = cv2.Canny(gray_img, 50, 150, apertureSize=3)
        
        # Apply Hough Line Transform to detect straight lines
        lines = cv2.HoughLinesP(
            edges, 
            rho=1, 
            theta=np.pi/180, 
            threshold=100, 
            minLineLength=gray_img.shape[1] // 3,  # Look for lines at least 1/3 of image width
            maxLineGap=10
        )
        
        if lines is None:
            return False, 0.0
            
        # Check for horizontal or vertical lines that could be folds
        potential_folds = []
        height, width = gray_img.shape
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            angle = np.abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
            
            # Check if horizontal (0±10°) or vertical (90±10°)
            is_horizontal = angle < 10 or angle > 170
            is_vertical = abs(angle - 90) < 10
            
            # Check if length is significant
            is_significant = (is_horizontal and length > width * 0.5) or \
                             (is_vertical and length > height * 0.5)
            
            if (is_horizontal or is_vertical) and is_significant:
                # Calculate intensity variance along the line
                # This helps determine if it's a fold (sharp brightness change)
                # Simplified implementation for Phase 1
                potential_folds.append({
                    "length": length,
                    "is_horizontal": is_horizontal,
                })
        
        # Determine if folds are detected and their severity
        if not potential_folds:
            return False, 0.0
            
        # Severity based on number and length of potential folds
        # This is a simplified metric for Phase 1
        total_len = sum(fold["length"] for fold in potential_folds)
        if is_horizontal:
            severity = min(5.0, total_len / width * 2.5)
        else:
            severity = min(5.0, total_len / height * 2.5)
            
        return True, severity
    
    def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        """
        Calculate overall quality score from individual metrics.
        
        Args:
            scores: Dictionary of individual quality scores
            
        Returns:
            Overall quality score (0-100)
        """
        # Weights for different factors
        weights = {
            "blur": 0.30,
            "lighting": 0.25,
            "contrast": 0.25,
            "size": 0.10,
            "fold": 0.10,
        }
        
        # Calculate weighted average
        overall = sum(weights[key] * scores[key] for key in weights)
        
        return overall
    
    def _generate_suggestions(self, metrics: Dict[str, Any]) -> list:
        """
        Generate improvement suggestions based on metrics.
        
        Args:
            metrics: Dictionary of quality metrics
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        # Blur suggestions
        if metrics["blur"] < 60:
            suggestions.append("Hold the camera steady and ensure the receipt is in focus.")
            
        # Lighting suggestions
        if metrics["lighting"] < 60:
            suggestions.append("Improve lighting conditions and avoid shadows on the receipt.")
            
        # Contrast suggestions
        if metrics["contrast"] < 60:
            suggestions.append("Ensure good contrast between text and background.")
            
        # Size suggestions
        if metrics["size"] < 60:
            suggestions.append("Move the camera closer to the receipt for better resolution.")
            
        # Fold suggestions
        if metrics["fold"]:
            if metrics["fold_severity"] > 3.0:
                suggestions.append("The receipt has severe folds. Try to flatten it before capturing.")
            else:
                suggestions.append("Flatten the receipt to remove fold lines for better processing.")
                
        return suggestions