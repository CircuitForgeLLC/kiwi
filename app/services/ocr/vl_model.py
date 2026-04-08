#!/usr/bin/env python
"""
Vision-Language Model service for receipt OCR and structured data extraction.

Uses Qwen3-VL-2B-Instruct for intelligent receipt processing that combines
OCR with understanding of receipt structure to extract structured JSON data.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from PIL import Image
import torch
from transformers import (
    Qwen2VLForConditionalGeneration,
    AutoProcessor,
    BitsAndBytesConfig
)

from app.core.config import settings

logger = logging.getLogger(__name__)


def _try_docuvision(image_path: str | Path) -> str | None:
    """Try to extract text via cf-docuvision. Returns None if unavailable."""
    cf_orch_url = os.environ.get("CF_ORCH_URL")
    if not cf_orch_url:
        return None
    try:
        from circuitforge_orch.client import CFOrchClient
        from app.services.ocr.docuvision_client import DocuvisionClient

        client = CFOrchClient(cf_orch_url)
        with client.allocate(
            service="cf-docuvision",
            model_candidates=["cf-docuvision"],
            ttl_s=60.0,
            caller="kiwi-ocr",
        ) as alloc:
            if alloc is None:
                return None
            doc_client = DocuvisionClient(alloc.url)
            result = doc_client.extract_text(image_path)
            return result.text if result.text else None
    except Exception as exc:
        logger.debug("cf-docuvision fast-path failed, falling back: %s", exc)
        return None


class VisionLanguageOCR:
    """Vision-Language Model for receipt OCR and structured extraction."""

    def __init__(self, use_quantization: bool = False):
        """
        Initialize the VLM OCR service.

        Args:
            use_quantization: Use 8-bit quantization to reduce memory usage
        """
        self.model = None
        self.processor = None
        self.device = "cuda" if torch.cuda.is_available() and settings.USE_GPU else "cpu"
        self.use_quantization = use_quantization
        self.model_name = "Qwen/Qwen2.5-VL-7B-Instruct"

        logger.info(f"Initializing VisionLanguageOCR with device: {self.device}")

        # Lazy loading - model will be loaded on first use
        self._model_loaded = False

    def _load_model(self):
        """Load the VLM model (lazy loading)."""
        if self._model_loaded:
            return

        logger.info(f"Loading VLM model: {self.model_name}")

        try:
            if self.use_quantization and self.device == "cuda":
                # Use 8-bit quantization for lower memory usage
                quantization_config = BitsAndBytesConfig(
                    load_in_8bit=True,
                    llm_int8_threshold=6.0
                )

                self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                    self.model_name,
                    quantization_config=quantization_config,
                    device_map="auto",
                    low_cpu_mem_usage=True
                )
                logger.info("Model loaded with 8-bit quantization")
            else:
                # Standard FP16 loading
                self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    device_map="auto" if self.device == "cuda" else None,
                    low_cpu_mem_usage=True
                )

                if self.device == "cpu":
                    self.model = self.model.to("cpu")

                logger.info(f"Model loaded in {'FP16' if self.device == 'cuda' else 'FP32'} mode")

            self.processor = AutoProcessor.from_pretrained(self.model_name)
            self.model.eval()  # Set to evaluation mode

            self._model_loaded = True
            logger.info("VLM model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load VLM model: {e}")
            raise RuntimeError(f"Could not load VLM model: {e}")

    def extract_receipt_data(self, image_path: str) -> Dict[str, Any]:
        """
        Extract structured data from receipt image.

        Args:
            image_path: Path to the receipt image

        Returns:
            Dictionary containing extracted receipt data with structure:
            {
                "merchant": {...},
                "transaction": {...},
                "items": [...],
                "totals": {...},
                "confidence": {...},
                "raw_text": "...",
                "warnings": [...]
            }
        """
        # Try docuvision fast path first (skips heavy local VLM if available)
        docuvision_text = _try_docuvision(image_path)
        if docuvision_text is not None:
            parsed = self._parse_json_from_text(docuvision_text)
            # Only accept the docuvision result if it yielded meaningful content;
            # an empty-skeleton dict (no items, no merchant) means the text was
            # garbled and we should fall through to the local VLM instead.
            if parsed.get("items") or parsed.get("merchant"):
                parsed["raw_text"] = docuvision_text
                return self._validate_result(parsed)
            # Parsed result has no meaningful content — fall through to local VLM

        self._load_model()

        try:
            # Load image
            image = Image.open(image_path)

            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Build extraction prompt
            prompt = self._build_extraction_prompt()

            # Process image and text
            logger.info(f"Processing receipt image: {image_path}")
            inputs = self.processor(
                images=image,
                text=prompt,
                return_tensors="pt"
            )

            # Move to device
            if self.device == "cuda":
                inputs = {k: v.to("cuda", torch.float16) if isinstance(v, torch.Tensor) else v
                         for k, v in inputs.items()}

            # Generate
            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    do_sample=False,  # Deterministic for consistency
                    temperature=0.0,
                    pad_token_id=self.processor.tokenizer.pad_token_id,
                    eos_token_id=self.processor.tokenizer.eos_token_id,
                )

            # Decode output
            output_text = self.processor.decode(
                output_ids[0],
                skip_special_tokens=True
            )

            # Remove the prompt from output
            output_text = output_text.replace(prompt, "").strip()

            logger.info(f"VLM output length: {len(output_text)} characters")

            # Parse JSON from output
            result = self._parse_json_from_text(output_text)

            # Add raw text for reference
            result["raw_text"] = output_text

            # Validate and enhance result
            result = self._validate_result(result)

            return result

        except Exception as e:
            logger.error(f"Error extracting receipt data: {e}", exc_info=True)
            return {
                "error": str(e),
                "merchant": {},
                "transaction": {},
                "items": [],
                "totals": {},
                "confidence": {"overall": 0.0},
                "warnings": [f"Extraction failed: {str(e)}"]
            }

    def _build_extraction_prompt(self) -> str:
        """Build the prompt for receipt data extraction."""
        return """You are a receipt OCR specialist. Extract all information from this receipt image and return it in the exact JSON format specified below.

Return a JSON object with this exact structure:
{
  "merchant": {
    "name": "Store Name",
    "address": "123 Main St, City, State ZIP",
    "phone": "555-1234"
  },
  "transaction": {
    "date": "2025-10-30",
    "time": "14:30:00",
    "receipt_number": "12345",
    "register": "01",
    "cashier": "Jane"
  },
  "items": [
    {
      "name": "Product name",
      "quantity": 2,
      "unit_price": 10.99,
      "total_price": 21.98,
      "category": "grocery",
      "tax_code": "F",
      "discount": 0.00
    }
  ],
  "totals": {
    "subtotal": 21.98,
    "tax": 1.98,
    "discount": 0.00,
    "total": 23.96,
    "payment_method": "Credit Card",
    "amount_paid": 23.96,
    "change": 0.00
  },
  "confidence": {
    "overall": 0.95,
    "merchant": 0.98,
    "items": 0.92,
    "totals": 0.97
  }
}

Important instructions:
1. Extract ALL items from the receipt, no matter how many there are
2. Use null for fields you cannot find
3. For dates, use YYYY-MM-DD format
4. For times, use HH:MM:SS format
5. For prices, use numeric values (not strings)
6. Estimate confidence scores (0.0-1.0) based on image quality and text clarity
7. Return ONLY the JSON object, no other text or explanation"""

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from model output text.

        Args:
            text: Raw text output from the model

        Returns:
            Parsed JSON dictionary
        """
        # Try to find JSON object in text
        # Look for content between first { and last }
        json_match = re.search(r'\{.*\}', text, re.DOTALL)

        if json_match:
            json_str = json_match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON: {e}")
                # Try to fix common issues
                json_str = self._fix_json(json_str)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    logger.error("Could not parse JSON even after fixes")

        # Return empty structure if parsing fails
        logger.warning("No valid JSON found in output, returning empty structure")
        return {
            "merchant": {},
            "transaction": {},
            "items": [],
            "totals": {},
            "confidence": {"overall": 0.1}
        }

    def _fix_json(self, json_str: str) -> str:
        """Attempt to fix common JSON formatting issues."""
        # Remove trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)

        # Fix single quotes to double quotes
        json_str = json_str.replace("'", '"')

        return json_str

    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and enhance extracted data.

        Args:
            result: Extracted receipt data

        Returns:
            Validated and enhanced result with warnings
        """
        warnings = []

        # Ensure required fields exist
        required_fields = ["merchant", "transaction", "items", "totals", "confidence"]
        for field in required_fields:
            if field not in result:
                result[field] = {} if field != "items" else []
                warnings.append(f"Missing required field: {field}")

        # Validate items
        if not result.get("items"):
            warnings.append("No items found on receipt")
        else:
            # Validate item structure
            for i, item in enumerate(result["items"]):
                if "total_price" not in item and "unit_price" in item and "quantity" in item:
                    item["total_price"] = item["unit_price"] * item["quantity"]

        # Validate totals
        if result.get("items") and result.get("totals"):
            calculated_subtotal = sum(
                item.get("total_price", 0)
                for item in result["items"]
            )
            reported_subtotal = result["totals"].get("subtotal", 0)

            # Allow small variance (rounding errors)
            if abs(calculated_subtotal - reported_subtotal) > 0.10:
                warnings.append(
                    f"Total mismatch: calculated ${calculated_subtotal:.2f}, "
                    f"reported ${reported_subtotal:.2f}"
                )
                result["totals"]["calculated_subtotal"] = calculated_subtotal

        # Validate date format
        if result.get("transaction", {}).get("date"):
            try:
                datetime.strptime(result["transaction"]["date"], "%Y-%m-%d")
            except ValueError:
                warnings.append(f"Invalid date format: {result['transaction']['date']}")

        # Add warnings to result
        if warnings:
            result["warnings"] = warnings

        # Ensure confidence exists
        if "confidence" not in result or not result["confidence"]:
            result["confidence"] = {
                "overall": 0.5,
                "merchant": 0.5,
                "items": 0.5,
                "totals": 0.5
            }

        return result

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "quantization": self.use_quantization,
            "loaded": self._model_loaded,
            "gpu_available": torch.cuda.is_available(),
            "gpu_memory_allocated": torch.cuda.memory_allocated() if torch.cuda.is_available() else 0,
            "gpu_memory_reserved": torch.cuda.memory_reserved() if torch.cuda.is_available() else 0
        }

    def clear_cache(self):
        """Clear GPU memory cache."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("GPU cache cleared")
