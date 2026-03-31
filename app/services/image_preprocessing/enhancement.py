#!/usr/bin/env python
# app/services/image_preprocessing/
import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def enhance_image(
    image_path: Path,
    output_path: Optional[Path] = None,
    adaptive_threshold: bool = True,
    denoise: bool = True,
) -> Tuple[bool, str, Optional[Path]]:
    """
    Enhance receipt image for better OCR.
    
    Args:
        image_path: Path to input image
        output_path: Optional path to save enhanced image
        adaptive_threshold: Whether to apply adaptive thresholding
        denoise: Whether to apply denoising
        
    Returns:
        Tuple containing (success, message, output_path)
    """
    try:
        # Check if CUDA is available
        use_cuda = cv2.cuda.getCudaEnabledDeviceCount() > 0
        
        # Set output path if not provided
        if output_path is None:
            output_path = image_path.with_stem(f"{image_path.stem}_enhanced")
            
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            return False, f"Failed to read image: {image_path}", None
            
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply denoising if requested
        if denoise:
            if use_cuda:
                # GPU accelerated denoising
                gpu_img = cv2.cuda_GpuMat()
                gpu_img.upload(gray)
                gpu_result = cv2.cuda.createNonLocalMeans().apply(gpu_img)
                denoised = gpu_result.download()
            else:
                # CPU denoising
                denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        else:
            denoised = gray
            
        # Apply adaptive thresholding if requested
        if adaptive_threshold:
            # Adaptive thresholding works well for receipts with varying backgrounds
            binary = cv2.adaptiveThreshold(
                denoised, 
                255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 
                11, 
                2
            )
            processed = binary
        else:
            processed = denoised
            
        # Write enhanced image
        success = cv2.imwrite(str(output_path), processed)
        if not success:
            return False, f"Failed to write enhanced image to {output_path}", None
            
        return True, "Image enhanced successfully", output_path
        
    except Exception as e:
        logger.exception(f"Error enhancing image: {e}")
        return False, f"Error enhancing image: {str(e)}", None

def correct_perspective(
    image_path: Path,
    output_path: Optional[Path] = None,
) -> Tuple[bool, str, Optional[Path]]:
    """
    Correct perspective distortion in receipt image.
    
    Args:
        image_path: Path to input image
        output_path: Optional path to save corrected image
        
    Returns:
        Tuple containing (success, message, output_path)
    """
    try:
        # Set output path if not provided
        if output_path is None:
            output_path = image_path.with_stem(f"{image_path.stem}_perspective")
            
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            return False, f"Failed to read image: {image_path}", None
            
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply edge detection
        edges = cv2.Canny(blur, 50, 150, apertureSize=3)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        # Find the largest contour by area which is likely the receipt
        if not contours:
            return False, "No contours found in image", None
            
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Approximate the contour to get the corners
        epsilon = 0.02 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        # If we have a quadrilateral, we can apply perspective transform
        if len(approx) == 4:
            # Sort the points for the perspective transform
            # This is a simplified implementation
            src_pts = approx.reshape(4, 2).astype(np.float32)
            
            # Get width and height for the destination image
            width = int(max(
                np.linalg.norm(src_pts[0] - src_pts[1]),
                np.linalg.norm(src_pts[2] - src_pts[3])
            ))
            height = int(max(
                np.linalg.norm(src_pts[0] - src_pts[3]),
                np.linalg.norm(src_pts[1] - src_pts[2])
            ))
            
            # Define destination points
            dst_pts = np.array([
                [0, 0],
                [width - 1, 0],
                [width - 1, height - 1],
                [0, height - 1]
            ], dtype=np.float32)
            
            # Get perspective transform matrix
            M = cv2.getPerspectiveTransform(src_pts, dst_pts)
            
            # Apply perspective transform
            warped = cv2.warpPerspective(img, M, (width, height))
            
            # Write corrected image
            success = cv2.imwrite(str(output_path), warped)
            if not success:
                return False, f"Failed to write perspective-corrected image to {output_path}", None
                
            return True, "Perspective corrected successfully", output_path
        else:
            return False, "Receipt corners not clearly detected", None
            
    except Exception as e:
        logger.exception(f"Error correcting perspective: {e}")
        return False, f"Error correcting perspective: {str(e)}", None