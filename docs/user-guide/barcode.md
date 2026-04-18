# Barcode Scanning

Kiwi's barcode scanner uses your device camera to look up products instantly. It works for UPC-A, UPC-E, EAN-13, EAN-8, and QR codes on packaged foods.

## How to scan

1. Open the **Inventory** tab
2. Click the **Scan barcode** button (camera icon)
3. Hold the barcode in the camera frame
4. Kiwi decodes it and looks up the product

## What happens after a scan

**Product found in database:**
Kiwi fills in the product name, category, and any nutritional metadata from the open barcode database. You confirm the quantity and expiry date, then save.

**Product not found:**
You'll see a manual entry form with the raw barcode pre-filled. Add a name and the product is saved to your personal pantry (not contributed to the shared database).

## Supported formats

| Format | Common use |
|--------|-----------|
| UPC-A (12 digit) | US grocery products |
| EAN-13 (13 digit) | International grocery products |
| UPC-E (compressed) | Small packaging |
| EAN-8 | Small packaging |
| QR Code | Some specialty products |

## Tips for reliable scanning

- **Good lighting**: scanning works best in well-lit conditions
- **Steady hand**: hold the camera still for 1–2 seconds
- **Fill the frame**: bring the barcode close enough to fill most of the camera view
- **Flat surface**: wrinkled or curved barcodes are harder to decode

## Manual barcode entry

If camera scanning isn't available (browser permissions denied, no camera, etc.), you can type the barcode number directly into the **Barcode** field on the manual add form.
