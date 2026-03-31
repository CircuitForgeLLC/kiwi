"""
Barcode scanning service using pyzbar.

This module provides functionality to detect and decode barcodes
from images (UPC, EAN, QR codes, etc.).
"""

import cv2
import numpy as np
from pyzbar import pyzbar
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BarcodeScanner:
    """
    Service for scanning barcodes from images.

    Supports various barcode formats:
    - UPC-A, UPC-E
    - EAN-8, EAN-13
    - Code 39, Code 128
    - QR codes
    - And more via pyzbar/libzbar
    """

    def scan_image(self, image_path: Path) -> List[Dict[str, Any]]:
        """
        Scan an image for barcodes.

        Args:
            image_path: Path to the image file

        Returns:
            List of detected barcodes, each as a dictionary with:
            - data: Barcode data (string)
            - type: Barcode type (e.g., 'EAN13', 'QRCODE')
            - quality: Quality score (0-100)
            - rect: Bounding box (x, y, width, height)
        """
        try:
            # Read image
            image = cv2.imread(str(image_path))
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return []

            # Convert to grayscale for better detection
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Try multiple preprocessing techniques and rotations for better detection
            barcodes = []

            # 1. Try on original grayscale
            barcodes.extend(self._detect_barcodes(gray, image))

            # 2. Try with adaptive thresholding (helps with poor lighting)
            if not barcodes:
                thresh = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )
                barcodes.extend(self._detect_barcodes(thresh, image))

            # 3. Try with sharpening (helps with blurry images)
            if not barcodes:
                kernel = np.array([[-1, -1, -1],
                                   [-1,  9, -1],
                                   [-1, -1, -1]])
                sharpened = cv2.filter2D(gray, -1, kernel)
                barcodes.extend(self._detect_barcodes(sharpened, image))

            # 4. Try rotations if still no barcodes found (handles tilted/rotated barcodes)
            if not barcodes:
                logger.info("No barcodes found in standard orientation, trying rotations...")
                # Try incremental angles: 30°, 60°, 90° (covers 0-90° range)
                # 0° already tried, 180° is functionally same as 0°, 90°/270° are same axis
                for angle in [30, 60, 90]:
                    rotated_gray = self._rotate_image(gray, angle)
                    rotated_color = self._rotate_image(image, angle)
                    detected = self._detect_barcodes(rotated_gray, rotated_color)
                    if detected:
                        logger.info(f"Found barcode(s) at {angle}° rotation")
                        barcodes.extend(detected)
                        break  # Stop after first successful rotation

            # Remove duplicates (same data)
            unique_barcodes = self._deduplicate_barcodes(barcodes)

            logger.info(f"Found {len(unique_barcodes)} barcode(s) in {image_path}")
            return unique_barcodes

        except Exception as e:
            logger.error(f"Error scanning image {image_path}: {e}")
            return []

    def _detect_barcodes(
        self,
        image: np.ndarray,
        original_image: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Detect barcodes in a preprocessed image.

        Args:
            image: Preprocessed image (grayscale)
            original_image: Original color image (for quality assessment)

        Returns:
            List of detected barcodes
        """
        detected = pyzbar.decode(image)
        barcodes = []

        for barcode in detected:
            # Decode barcode data
            barcode_data = barcode.data.decode("utf-8")
            barcode_type = barcode.type

            # Get bounding box
            rect = barcode.rect
            bbox = {
                "x": rect.left,
                "y": rect.top,
                "width": rect.width,
                "height": rect.height,
            }

            # Assess quality of barcode region
            quality = self._assess_barcode_quality(original_image, bbox)

            barcodes.append({
                "data": barcode_data,
                "type": barcode_type,
                "quality": quality,
                "rect": bbox,
            })

        return barcodes

    def _assess_barcode_quality(
        self,
        image: np.ndarray,
        bbox: Dict[str, int]
    ) -> int:
        """
        Assess the quality of a detected barcode.

        Args:
            image: Original image
            bbox: Bounding box of barcode

        Returns:
            Quality score (0-100)
        """
        try:
            # Extract barcode region
            x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]

            # Add padding
            pad = 10
            y1 = max(0, y - pad)
            y2 = min(image.shape[0], y + h + pad)
            x1 = max(0, x - pad)
            x2 = min(image.shape[1], x + w + pad)

            region = image[y1:y2, x1:x2]

            if region.size == 0:
                return 50

            # Convert to grayscale if needed
            if len(region.shape) == 3:
                region = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

            # Calculate sharpness (Laplacian variance)
            laplacian_var = cv2.Laplacian(region, cv2.CV_64F).var()
            sharpness_score = min(100, laplacian_var / 10)  # Normalize

            # Calculate contrast
            min_val, max_val = region.min(), region.max()
            contrast = (max_val - min_val) / 255.0 * 100

            # Calculate size score (larger is better, up to a point)
            area = w * h
            size_score = min(100, area / 100)  # Normalize

            # Weighted average
            quality = (sharpness_score * 0.4 + contrast * 0.4 + size_score * 0.2)

            return int(quality)

        except Exception as e:
            logger.warning(f"Error assessing barcode quality: {e}")
            return 50

    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """
        Rotate an image by a given angle.

        Args:
            image: Input image
            angle: Rotation angle in degrees (any angle, but optimized for 90° increments)

        Returns:
            Rotated image
        """
        # Use fast optimized rotation for common angles
        if angle == 90:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(image, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif angle == 0:
            return image
        else:
            # For arbitrary angles, use affine transformation
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)

            # Get rotation matrix
            M = cv2.getRotationMatrix2D(center, angle, 1.0)

            # Calculate new bounding dimensions
            cos = np.abs(M[0, 0])
            sin = np.abs(M[0, 1])
            new_w = int((h * sin) + (w * cos))
            new_h = int((h * cos) + (w * sin))

            # Adjust rotation matrix for new dimensions
            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]

            # Perform rotation
            return cv2.warpAffine(image, M, (new_w, new_h),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)

    def _deduplicate_barcodes(
        self,
        barcodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate barcodes (same data).

        If multiple detections of the same barcode, keep the one
        with the highest quality score.

        Args:
            barcodes: List of detected barcodes

        Returns:
            Deduplicated list
        """
        seen = {}
        for barcode in barcodes:
            data = barcode["data"]
            if data not in seen or barcode["quality"] > seen[data]["quality"]:
                seen[data] = barcode

        return list(seen.values())

    def scan_from_bytes(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Scan barcodes from image bytes (uploaded file).

        Args:
            image_bytes: Image data as bytes

        Returns:
            List of detected barcodes
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                logger.error("Failed to decode image from bytes")
                return []

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Try multiple approaches for better detection
            barcodes = []

            # 1. Try original orientation
            barcodes.extend(self._detect_barcodes(gray, image))

            # 2. Try with adaptive thresholding
            if not barcodes:
                thresh = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )
                barcodes.extend(self._detect_barcodes(thresh, image))

            # 3. Try rotations if still no barcodes found
            if not barcodes:
                logger.info("No barcodes found in uploaded image, trying rotations...")
                # Try incremental angles: 30°, 60°, 90° (covers 0-90° range)
                for angle in [30, 60, 90]:
                    rotated_gray = self._rotate_image(gray, angle)
                    rotated_color = self._rotate_image(image, angle)
                    detected = self._detect_barcodes(rotated_gray, rotated_color)
                    if detected:
                        logger.info(f"Found barcode(s) in uploaded image at {angle}° rotation")
                        barcodes.extend(detected)
                        break

            return self._deduplicate_barcodes(barcodes)

        except Exception as e:
            logger.error(f"Error scanning image from bytes: {e}")
            return []

    def validate_barcode(self, barcode: str, barcode_type: str) -> bool:
        """
        Validate a barcode using check digits (for EAN/UPC).

        Args:
            barcode: Barcode string
            barcode_type: Type of barcode (e.g., 'EAN13', 'UPCA')

        Returns:
            True if valid, False otherwise
        """
        if barcode_type in ["EAN13", "UPCA"]:
            return self._validate_ean13(barcode)
        elif barcode_type == "EAN8":
            return self._validate_ean8(barcode)

        # For other types, assume valid if detected
        return True

    def _validate_ean13(self, barcode: str) -> bool:
        """Validate EAN-13 barcode using check digit."""
        if len(barcode) != 13 or not barcode.isdigit():
            return False

        # Calculate check digit
        odd_sum = sum(int(barcode[i]) for i in range(0, 12, 2))
        even_sum = sum(int(barcode[i]) for i in range(1, 12, 2))
        total = odd_sum + (even_sum * 3)
        check_digit = (10 - (total % 10)) % 10

        return int(barcode[12]) == check_digit

    def _validate_ean8(self, barcode: str) -> bool:
        """Validate EAN-8 barcode using check digit."""
        if len(barcode) != 8 or not barcode.isdigit():
            return False

        # Calculate check digit
        odd_sum = sum(int(barcode[i]) for i in range(1, 7, 2))
        even_sum = sum(int(barcode[i]) for i in range(0, 7, 2))
        total = (odd_sum * 3) + even_sum
        check_digit = (10 - (total % 10)) % 10

        return int(barcode[7]) == check_digit
