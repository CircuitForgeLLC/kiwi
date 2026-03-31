#!/usr/bin/env python
# app/services/image_preprocessing/format_conversion.py
import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def convert_to_standard_format(
    image_path: Path,
    output_path: Optional[Path] = None,
    target_format: str = "png"
) -> Tuple[bool, str, Optional[Path]]:
    """
    Convert image to standard internal format.
    
    Args:
        image_path: Path to input image
        output_path: Optional path to save converted image
        target_format: Target format (png, jpg)
        
    Returns:
        Tuple containing (success, message, output_path)
    """
    try:
        # Check if CUDA is available and set up GPU processing
        if cv2.cuda.getCudaEnabledDeviceCount() > 0:
            logger.info("CUDA available, using GPU acceleration")
            use_cuda = True
        else:
            logger.info("CUDA not available, using CPU processing")
            use_cuda = False
            
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            return False, f"Failed to read image: {image_path}", None
            
        # If PDF, extract first page (simplified for Phase 1)
        if image_path.suffix.lower() == '.pdf':
            # This is a placeholder for PDF handling
            # In a real implementation, you'd use a PDF processing library
            return False, "PDF processing not implemented in Phase 1", None
            
        # Set output path if not provided
        if output_path is None:
            output_path = image_path.with_suffix(f".{target_format}")
            
        # Write converted image
        success = cv2.imwrite(str(output_path), img)
        if not success:
            return False, f"Failed to write converted image to {output_path}", None
            
        return True, "Image converted successfully", output_path
        
    except Exception as e:
        logger.exception(f"Error converting image: {e}")
        return False, f"Error converting image: {str(e)}", None

def extract_metadata(image_path: Path) -> dict:
    """
    Extract metadata from image file.
    
    Args:
        image_path: Path to input image
        
    Returns:
        Dictionary containing metadata
    """
    metadata = {
        "filename": image_path.name,
        "original_format": image_path.suffix.lstrip(".").lower(),
        "file_size_bytes": image_path.stat().st_size,
    }
    
    try:
        img = cv2.imread(str(image_path))
        if img is not None:
            metadata.update({
                "width": img.shape[1],
                "height": img.shape[0],
                "channels": img.shape[2] if len(img.shape) > 2 else 1,
            })
    except Exception as e:
        logger.exception(f"Error extracting image metadata: {e}")
        
    return metadata