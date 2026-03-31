#!/usr/bin/env python
"""
Pydantic schemas for OCR data models.
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator


class MerchantInfo(BaseModel):
    """Merchant/store information from receipt."""
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    tax_id: Optional[str] = None


class TransactionInfo(BaseModel):
    """Transaction details from receipt."""
    date: Optional[date] = None
    time: Optional[time] = None
    receipt_number: Optional[str] = None
    register: Optional[str] = None
    cashier: Optional[str] = None
    transaction_id: Optional[str] = None


class ReceiptItem(BaseModel):
    """Individual line item from receipt."""
    name: str
    quantity: float = 1.0
    unit_price: Optional[float] = None
    total_price: float
    category: Optional[str] = None
    tax_code: Optional[str] = None
    discount: Optional[float] = 0.0
    barcode: Optional[str] = None
    notes: Optional[str] = None


class ReceiptTotals(BaseModel):
    """Financial totals from receipt."""
    subtotal: float
    tax: Optional[float] = 0.0
    discount: Optional[float] = 0.0
    tip: Optional[float] = 0.0
    total: float
    payment_method: Optional[str] = None
    amount_paid: Optional[float] = None
    change: Optional[float] = 0.0
    calculated_subtotal: Optional[float] = None  # For validation


class ConfidenceScores(BaseModel):
    """Confidence scores for extracted data."""
    overall: float = Field(ge=0.0, le=1.0)
    merchant: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    items: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    totals: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    transaction: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)


class OCRResult(BaseModel):
    """Complete OCR extraction result."""
    merchant: MerchantInfo
    transaction: TransactionInfo
    items: List[ReceiptItem]
    totals: ReceiptTotals
    confidence: ConfidenceScores
    raw_text: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    processing_time: Optional[float] = None  # seconds


class ReceiptDataCreate(BaseModel):
    """Schema for creating receipt data."""
    receipt_id: UUID
    merchant_name: Optional[str] = None
    merchant_address: Optional[str] = None
    merchant_phone: Optional[str] = None
    transaction_date: Optional[date] = None
    transaction_time: Optional[time] = None
    receipt_number: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    tip: Optional[float] = None
    total: Optional[float] = None
    payment_method: Optional[str] = None
    raw_text: Optional[str] = None
    confidence_scores: Optional[Dict[str, float]] = None
    warnings: List[str] = Field(default_factory=list)


class ReceiptDataResponse(BaseModel):
    """Schema for receipt data response."""
    id: UUID
    receipt_id: UUID
    merchant_name: Optional[str]
    merchant_address: Optional[str]
    merchant_phone: Optional[str]
    transaction_date: Optional[date]
    transaction_time: Optional[time]
    receipt_number: Optional[str]
    items: List[Dict[str, Any]]
    subtotal: Optional[float]
    tax: Optional[float]
    tip: Optional[float]
    total: Optional[float]
    payment_method: Optional[str]
    raw_text: Optional[str]
    confidence_scores: Optional[Dict[str, float]]
    warnings: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OCRStatusResponse(BaseModel):
    """OCR processing status response."""
    receipt_id: UUID
    ocr_completed: bool
    has_data: bool
    confidence: Optional[float] = None
    item_count: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)


class OCRTriggerRequest(BaseModel):
    """Request to trigger OCR processing."""
    force_reprocess: bool = False
    use_quantization: bool = False
