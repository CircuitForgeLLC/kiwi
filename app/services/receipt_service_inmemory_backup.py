#!/usr/bin/env python
# app/services/receipt_service.py
import os
import uuid
import shutil
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import UploadFile, BackgroundTasks, HTTPException
import asyncio
import logging
import sys
from app.utils.progress import ProgressIndicator

from app.services.image_preprocessing.format_conversion import convert_to_standard_format, extract_metadata
from app.services.image_preprocessing.enhancement import enhance_image, correct_perspective
from app.services.quality.assessment import QualityAssessor
from app.models.schemas.receipt import ReceiptCreate, ReceiptResponse
from app.models.schemas.quality import QualityAssessment
from app.core.config import settings

logger = logging.getLogger(__name__)

class ReceiptService:
    """
    Service for handling receipt processing.
    """
    
    def __init__(self):
        """
        Initialize the receipt service.
        """
        self.quality_assessor = QualityAssessor()
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.processing_dir = Path(settings.PROCESSING_DIR)
        
        # Create directories if they don't exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage for Phase 1 (would be replaced by DB in production)
        self.receipts = {}
        self.quality_assessments = {}
        
    async def process_receipt(
        self, 
        file: UploadFile, 
        background_tasks: BackgroundTasks
    ) -> ReceiptResponse:
        """
        Process a single receipt file.
        
        Args:
            file: Uploaded receipt file
            background_tasks: FastAPI background tasks
            
        Returns:
            ReceiptResponse object
        """
        # Generate unique ID for receipt
        receipt_id = str(uuid.uuid4())
        
        # Save uploaded file
        upload_path = self.upload_dir / f"{receipt_id}_{file.filename}"
        await self._save_upload_file(file, upload_path)
        
        # Create receipt entry
        receipt = {
            "id": receipt_id,
            "filename": file.filename,
            "status": "uploaded",
            "original_path": str(upload_path),
            "processed_path": None,
            "metadata": {},
        }
        
        self.receipts[receipt_id] = receipt
        
        # Add background task for processing
        background_tasks.add_task(
            self._process_receipt_background,
            receipt_id,
            upload_path
        )
        
        return ReceiptResponse(
            id=receipt_id,
            filename=file.filename,
            status="processing",
            metadata={},
            quality_score=None,
        )
        
    async def get_receipt(self, receipt_id: str) -> Optional[ReceiptResponse]:
        """
        Get receipt by ID.
        
        Args:
            receipt_id: Receipt ID
            
        Returns:
            ReceiptResponse object or None if not found
        """
        receipt = self.receipts.get(receipt_id)
        if not receipt:
            return None
            
        quality = self.quality_assessments.get(receipt_id)
        quality_score = quality.get("overall_score") if quality else None
        
        return ReceiptResponse(
            id=receipt["id"],
            filename=receipt["filename"],
            status=receipt["status"],
            metadata=receipt["metadata"],
            quality_score=quality_score,
        )
        
    async def get_receipt_quality(self, receipt_id: str) -> Optional[QualityAssessment]:
        """
        Get quality assessment for a receipt.
        
        Args:
            receipt_id: Receipt ID
            
        Returns:
            QualityAssessment object or None if not found
        """
        quality = self.quality_assessments.get(receipt_id)
        if not quality:
            return None
            
        return QualityAssessment(
            receipt_id=receipt_id,
            overall_score=quality["overall_score"],
            is_acceptable=quality["is_acceptable"],
            metrics=quality["metrics"],
            suggestions=quality["improvement_suggestions"],
        )

    def list_receipts(self) -> List[ReceiptResponse]:
        """
        List all receipts.

        Returns:
            List of ReceiptResponse objects
        """
        result = []
        for receipt_id, receipt in self.receipts.items():
            quality = self.quality_assessments.get(receipt_id)
            quality_score = quality.get("overall_score") if quality else None

            result.append(ReceiptResponse(
                id=receipt["id"],
                filename=receipt["filename"],
                status=receipt["status"],
                metadata=receipt["metadata"],
                quality_score=quality_score,
            ))

        return result

    def get_quality_assessments(self) -> Dict[str, QualityAssessment]:
        """
        Get all quality assessments.

        Returns:
            Dict mapping receipt_id to QualityAssessment object
        """
        result = {}
        for receipt_id, quality in self.quality_assessments.items():
            result[receipt_id] = QualityAssessment(
                receipt_id=receipt_id,
                overall_score=quality["overall_score"],
                is_acceptable=quality["is_acceptable"],
                metrics=quality["metrics"],
                suggestions=quality["improvement_suggestions"],
            )
        return result

    async def _save_upload_file(self, file: UploadFile, destination: Path) -> None:
        """
        Save an uploaded file to disk.
        
        Args:
            file: Uploaded file
            destination: Destination path
        """
        try:
            async with aiofiles.open(destination, 'wb') as out_file:
                # Read in chunks to handle large files
                content = await file.read(1024 * 1024)  # 1MB chunks
                while content:
                    await out_file.write(content)
                    content = await file.read(1024 * 1024)
                    
        except Exception as e:
            logger.exception(f"Error saving upload file: {e}")
            raise HTTPException(status_code=500, detail=f"Error saving upload file: {str(e)}")
            
    async def _process_receipt_background(self, receipt_id: str, upload_path: Path) -> None:
        """
        Background task for processing a receipt with progress indicators.
        
        Args:
            receipt_id: Receipt ID
            upload_path: Path to uploaded file
        """
        try:
            # Print a message to indicate start of processing
            print(f"\nProcessing receipt {receipt_id}...")
            
            # Update status
            self.receipts[receipt_id]["status"] = "processing"
            
            # Create processing directory for this receipt
            receipt_dir = self.processing_dir / receipt_id
            receipt_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 1: Convert to standard format
            print("  Step 1/4: Converting to standard format...")
            converted_path = receipt_dir / f"{receipt_id}_converted.png"
            success, message, actual_converted_path = convert_to_standard_format(
                upload_path, 
                converted_path
            )
            
            if not success:
                print(f"  ✗ Format conversion failed: {message}")
                self.receipts[receipt_id]["status"] = "error"
                self.receipts[receipt_id]["error"] = message
                return
            print("  ✓ Format conversion complete")
                
            # Step 2: Correct perspective
            print("  Step 2/4: Correcting perspective...")
            perspective_path = receipt_dir / f"{receipt_id}_perspective.png"
            success, message, actual_perspective_path = correct_perspective(
                actual_converted_path, 
                perspective_path
            )
            
            # Use corrected image if available, otherwise use converted image
            current_path = actual_perspective_path if success else actual_converted_path
            if success:
                print("  ✓ Perspective correction complete")
            else:
                print(f"  ⚠ Perspective correction skipped: {message}")
            
            # Step 3: Enhance image
            print("  Step 3/4: Enhancing image...")
            enhanced_path = receipt_dir / f"{receipt_id}_enhanced.png"
            success, message, actual_enhanced_path = enhance_image(
                current_path, 
                enhanced_path
            )
            
            if not success:
                print(f"  ⚠ Enhancement warning: {message}")
                # Continue with current path
            else:
                current_path = actual_enhanced_path
                print("  ✓ Image enhancement complete")
                    
            # Step 4: Assess quality
            print("  Step 4/4: Assessing quality...")
            quality_assessment = self.quality_assessor.assess_image(current_path)
            self.quality_assessments[receipt_id] = quality_assessment
            print(f"  ✓ Quality assessment complete: score {quality_assessment['overall_score']:.1f}/100")
            
            # Step 5: Extract metadata
            print("  Extracting metadata...")
            metadata = extract_metadata(upload_path)
            if current_path != upload_path:
                processed_metadata = extract_metadata(current_path)
                metadata["processed"] = {
                    "width": processed_metadata.get("width"),
                    "height": processed_metadata.get("height"),
                    "format": processed_metadata.get("original_format"),
                }
            print("  ✓ Metadata extraction complete")
                
            # Update receipt entry
            self.receipts[receipt_id].update({
                "status": "processed",
                "processed_path": str(current_path),
                "metadata": metadata,
            })
            
            print(f"✓ Receipt {receipt_id} processed successfully!")
            
        except Exception as e:
            print(f"✗ Error processing receipt {receipt_id}: {e}")
            self.receipts[receipt_id]["status"] = "error"
            self.receipts[receipt_id]["error"] = str(e)