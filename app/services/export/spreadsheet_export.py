# app/services/export/spreadsheet_export.py
"""
Service for exporting receipt data to CSV and Excel formats.

This module provides functionality to convert receipt and quality assessment
data into spreadsheet formats for easy viewing and analysis.
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from app.models.schemas.receipt import ReceiptResponse
from app.models.schemas.quality import QualityAssessment


class SpreadsheetExporter:
    """
    Service for exporting receipt data to CSV/Excel formats.

    Provides methods to convert receipt and quality assessment data into
    spreadsheet formats that can be opened in Excel, Google Sheets, or
    LibreOffice Calc.
    """

    def export_to_csv(
        self,
        receipts: List[ReceiptResponse],
        quality_data: Dict[str, QualityAssessment],
        ocr_data: Optional[Dict[str, Dict]] = None
    ) -> str:
        """
        Export receipts to CSV format.

        Args:
            receipts: List of receipt responses
            quality_data: Dict mapping receipt_id to quality assessment
            ocr_data: Optional dict mapping receipt_id to OCR extracted data

        Returns:
            CSV string ready for download
        """
        df = self._receipts_to_dataframe(receipts, quality_data, ocr_data)
        return df.to_csv(index=False)

    def export_to_excel(
        self,
        receipts: List[ReceiptResponse],
        quality_data: Dict[str, QualityAssessment],
        output_path: str,
        ocr_data: Optional[Dict[str, Dict]] = None
    ) -> None:
        """
        Export receipts to Excel format with multiple sheets.

        Creates an Excel file with sheets:
        - Receipts: Main receipt data with OCR results
        - Line Items: Detailed items from all receipts (if OCR available)
        - Quality Details: Detailed quality metrics
        - Summary: Aggregated statistics

        Args:
            receipts: List of receipt responses
            quality_data: Dict mapping receipt_id to quality assessment
            output_path: Path to save Excel file
            ocr_data: Optional dict mapping receipt_id to OCR extracted data
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Sheet 1: Receipts with OCR data
            receipts_df = self._receipts_to_dataframe(receipts, quality_data, ocr_data)
            receipts_df.to_excel(writer, sheet_name='Receipts', index=False)

            # Sheet 2: Line Items (if OCR data available)
            if ocr_data:
                items_df = self._items_to_dataframe(receipts, ocr_data)
                if not items_df.empty:
                    items_df.to_excel(writer, sheet_name='Line Items', index=False)

            # Sheet 3: Quality Details
            if quality_data:
                quality_df = self._quality_to_dataframe(quality_data)
                quality_df.to_excel(writer, sheet_name='Quality Details', index=False)

            # Sheet 4: Summary
            summary_df = self._create_summary(receipts, quality_data, ocr_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

    def _receipts_to_dataframe(
        self,
        receipts: List[ReceiptResponse],
        quality_data: Dict[str, QualityAssessment],
        ocr_data: Optional[Dict[str, Dict]] = None
    ) -> pd.DataFrame:
        """
        Convert receipts to pandas DataFrame.

        Args:
            receipts: List of receipt responses
            quality_data: Dict mapping receipt_id to quality assessment
            ocr_data: Optional dict mapping receipt_id to OCR extracted data

        Returns:
            DataFrame with receipt data
        """
        data = []
        for receipt in receipts:
            quality = quality_data.get(receipt.id)
            ocr = ocr_data.get(receipt.id) if ocr_data else None

            # Base columns
            row = {
                'ID': receipt.id,
                'Filename': receipt.filename,
                'Status': receipt.status,
                'Quality Score': quality.overall_score if quality else None,
            }

            # Add OCR data if available
            if ocr:
                merchant = ocr.get('merchant', {})
                transaction = ocr.get('transaction', {})
                totals = ocr.get('totals', {})
                items = ocr.get('items', [])

                row.update({
                    'Merchant': merchant.get('name', ''),
                    'Store Address': merchant.get('address', ''),
                    'Store Phone': merchant.get('phone', ''),
                    'Date': transaction.get('date', ''),
                    'Time': transaction.get('time', ''),
                    'Receipt Number': transaction.get('receipt_number', ''),
                    'Item Count': len(items),
                    'Subtotal': totals.get('subtotal', ''),
                    'Tax': totals.get('tax', ''),
                    'Total': totals.get('total', ''),
                    'Payment Method': totals.get('payment_method', ''),
                    'OCR Confidence': ocr.get('confidence', {}).get('overall', ''),
                })

                # Add items as text
                items_text = '; '.join([
                    f"{item.get('name', 'Unknown')} (${item.get('total_price', 0):.2f})"
                    for item in items[:10]  # Limit to first 10 items for CSV
                ])
                if len(items) > 10:
                    items_text += f'; ... and {len(items) - 10} more items'
                row['Items'] = items_text
            else:
                # No OCR data - show image metadata instead
                row.update({
                    'Merchant': 'N/A - No OCR',
                    'Date': '',
                    'Total': '',
                    'Item Count': 0,
                    'Width': receipt.metadata.get('width'),
                    'Height': receipt.metadata.get('height'),
                    'File Size (KB)': round(receipt.metadata.get('file_size_bytes', 0) / 1024, 2),
                })

            data.append(row)

        return pd.DataFrame(data)

    def _items_to_dataframe(
        self,
        receipts: List[ReceiptResponse],
        ocr_data: Dict[str, Dict]
    ) -> pd.DataFrame:
        """
        Convert line items from all receipts to DataFrame.

        Args:
            receipts: List of receipt responses
            ocr_data: Dict mapping receipt_id to OCR extracted data

        Returns:
            DataFrame with all line items from all receipts
        """
        data = []
        for receipt in receipts:
            ocr = ocr_data.get(receipt.id)
            if not ocr:
                continue

            merchant = ocr.get('merchant', {}).get('name', 'Unknown')
            date = ocr.get('transaction', {}).get('date', '')
            items = ocr.get('items', [])

            for item in items:
                data.append({
                    'Receipt ID': receipt.id,
                    'Receipt File': receipt.filename,
                    'Merchant': merchant,
                    'Date': date,
                    'Item Name': item.get('name', 'Unknown'),
                    'Quantity': item.get('quantity', 1),
                    'Unit Price': item.get('unit_price', ''),
                    'Total Price': item.get('total_price', 0),
                    'Category': item.get('category', ''),
                    'Tax Code': item.get('tax_code', ''),
                    'Discount': item.get('discount', 0),
                })

        return pd.DataFrame(data)

    def _quality_to_dataframe(
        self,
        quality_data: Dict[str, QualityAssessment]
    ) -> pd.DataFrame:
        """
        Convert quality assessments to DataFrame.

        Args:
            quality_data: Dict mapping receipt_id to quality assessment

        Returns:
            DataFrame with quality metrics
        """
        data = []
        for receipt_id, quality in quality_data.items():
            metrics = quality.metrics
            row = {
                'Receipt ID': receipt_id,
                'Overall Score': round(quality.overall_score, 2),
                'Acceptable': quality.is_acceptable,
                'Blur Score': round(metrics.get('blur_score', 0), 2),
                'Lighting Score': round(metrics.get('lighting_score', 0), 2),
                'Contrast Score': round(metrics.get('contrast_score', 0), 2),
                'Size Score': round(metrics.get('size_score', 0), 2),
                'Fold Detected': metrics.get('fold_detected', False),
                'Fold Severity': round(metrics.get('fold_severity', 0), 2),
                'Suggestions': '; '.join(quality.suggestions) if quality.suggestions else 'None',
            }
            data.append(row)

        return pd.DataFrame(data)

    def _create_summary(
        self,
        receipts: List[ReceiptResponse],
        quality_data: Dict[str, QualityAssessment],
        ocr_data: Optional[Dict[str, Dict]] = None
    ) -> pd.DataFrame:
        """
        Create summary statistics DataFrame.

        Args:
            receipts: List of receipt responses
            quality_data: Dict mapping receipt_id to quality assessment
            ocr_data: Optional dict mapping receipt_id to OCR extracted data

        Returns:
            DataFrame with summary statistics
        """
        quality_scores = [q.overall_score for q in quality_data.values() if q]

        # Count statuses
        status_counts = {}
        for receipt in receipts:
            status_counts[receipt.status] = status_counts.get(receipt.status, 0) + 1

        metrics = [
            'Total Receipts',
            'Processed',
            'Processing',
            'Uploaded',
            'Failed',
            'Average Quality Score',
            'Best Quality Score',
            'Worst Quality Score',
            'Acceptable Quality Count',
            'Unacceptable Quality Count',
        ]

        values = [
            len(receipts),
            status_counts.get('processed', 0),
            status_counts.get('processing', 0),
            status_counts.get('uploaded', 0),
            status_counts.get('error', 0),
            f"{sum(quality_scores) / len(quality_scores):.2f}" if quality_scores else 'N/A',
            f"{max(quality_scores):.2f}" if quality_scores else 'N/A',
            f"{min(quality_scores):.2f}" if quality_scores else 'N/A',
            len([q for q in quality_data.values() if q and q.is_acceptable]),
            len([q for q in quality_data.values() if q and not q.is_acceptable]),
        ]

        # Add OCR statistics if available
        if ocr_data:
            receipts_with_ocr = len([r for r in receipts if r.id in ocr_data])
            total_items = sum(len(ocr.get('items', [])) for ocr in ocr_data.values())
            total_spent = sum(
                ocr.get('totals', {}).get('total', 0) or 0
                for ocr in ocr_data.values()
            )
            avg_confidence = sum(
                ocr.get('confidence', {}).get('overall', 0) or 0
                for ocr in ocr_data.values()
            ) / len(ocr_data) if ocr_data else 0

            metrics.extend([
                '',  # Blank row
                'OCR Statistics',
                'Receipts with OCR Data',
                'Total Line Items Extracted',
                'Total Amount Spent',
                'Average OCR Confidence',
            ])

            values.extend([
                '',
                '',
                receipts_with_ocr,
                total_items,
                f"${total_spent:.2f}" if total_spent > 0 else 'N/A',
                f"{avg_confidence:.2%}" if avg_confidence > 0 else 'N/A',
            ])

        summary = {
            'Metric': metrics,
            'Value': values
        }

        return pd.DataFrame(summary)
