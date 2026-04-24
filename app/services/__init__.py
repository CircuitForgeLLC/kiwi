# app/services/__init__.py
"""
Business logic services for Kiwi.
"""

__all__ = ["ReceiptService"]


def __getattr__(name: str):
    if name == "ReceiptService":
        from app.services.receipt_service import ReceiptService
        return ReceiptService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
