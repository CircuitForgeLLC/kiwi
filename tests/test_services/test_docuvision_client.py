"""Tests for DocuvisionClient and the _try_docuvision fast path."""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.ocr.docuvision_client import DocuvisionClient, DocuvisionResult


# ---------------------------------------------------------------------------
# DocuvisionClient unit tests
# ---------------------------------------------------------------------------


def test_extract_text_sends_base64_image(tmp_path: Path) -> None:
    """extract_text() POSTs a base64-encoded image and returns parsed text."""
    image_file = tmp_path / "test.jpg"
    image_file.write_bytes(b"fake-image-bytes")

    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Cheerios", "confidence": 0.95}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        client = DocuvisionClient("http://docuvision:8080")
        result = client.extract_text(image_file)

    assert result.text == "Cheerios"
    assert result.confidence == 0.95

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[0][0] == "http://docuvision:8080/extract"
    posted_json = call_kwargs[1]["json"]
    expected_b64 = base64.b64encode(b"fake-image-bytes").decode()
    assert posted_json["image"] == expected_b64


def test_extract_text_raises_on_http_error(tmp_path: Path) -> None:
    """extract_text() propagates HTTP errors from the server."""
    image_file = tmp_path / "test.jpg"
    image_file.write_bytes(b"fake-image-bytes")

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=MagicMock(),
        response=MagicMock(),
    )

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        client = DocuvisionClient("http://docuvision:8080")
        with pytest.raises(httpx.HTTPStatusError):
            client.extract_text(image_file)


# ---------------------------------------------------------------------------
# _try_docuvision fast-path tests
# ---------------------------------------------------------------------------


def test_try_docuvision_returns_none_without_cf_orch_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_try_docuvision() returns None immediately when CF_ORCH_URL is not set."""
    monkeypatch.delenv("CF_ORCH_URL", raising=False)

    # Import after env manipulation so the function sees the unset var
    from app.services.ocr.vl_model import _try_docuvision

    with patch("httpx.Client") as mock_client_cls:
        result = _try_docuvision(tmp_path / "test.jpg")

    assert result is None
    mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# extract_receipt_data docuvision fast-path fallthrough tests
# ---------------------------------------------------------------------------


def test_extract_receipt_data_falls_through_when_docuvision_yields_empty_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When docuvision returns garbled text that parses to an empty structure,
    extract_receipt_data must fall through to the local VLM rather than
    returning an empty skeleton dict as a successful result."""
    from app.services.ocr.vl_model import VisionLanguageOCR

    vlm = VisionLanguageOCR()

    # Simulate docuvision returning some text that cannot be meaningfully parsed
    garbled_text = "not valid json at all @@##!!"

    local_vlm_result = {
        "merchant": {"name": "Whole Foods"},
        "transaction": {},
        "items": [{"name": "Milk", "quantity": 1, "unit_price": 3.99, "total_price": 3.99}],
        "totals": {"total": 3.99},
        "confidence": {"overall": 0.9},
        "raw_text": "Whole Foods\nMilk $3.99",
    }

    with (
        patch("app.services.ocr.vl_model._try_docuvision", return_value=garbled_text),
        patch.object(vlm, "_load_model"),
        patch.object(vlm, "_parse_json_from_text", wraps=vlm._parse_json_from_text) as spy_parse,
        patch.object(vlm, "_validate_result", side_effect=lambda r: r) as mock_validate,
    ):
        # Intercept the VLM path by making generate/processor unavailable
        # by patching extract_receipt_data at the local-VLM branch entry.
        # We do this by replacing the second call to _parse_json_from_text
        # (the one from the local VLM branch) with the known good result.
        call_count = {"n": 0}
        original_parse = vlm._parse_json_from_text.__wrapped__ if hasattr(
            vlm._parse_json_from_text, "__wrapped__"
        ) else None

        def _fake_parse(text: str) -> dict:
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: docuvision path — return the real (empty) result
                return vlm.__class__._parse_json_from_text(vlm, text)
            # Second call: local VLM path — return populated result
            return local_vlm_result

        spy_parse.side_effect = _fake_parse

        # Also stub the model inference bits so we don't need a real GPU
        from unittest.mock import MagicMock
        import torch

        vlm._model_loaded = True
        vlm.model = MagicMock()
        vlm.processor = MagicMock()
        vlm.processor.return_value = {}
        vlm.processor.decode.return_value = "Whole Foods\nMilk $3.99"
        vlm.processor.tokenizer = MagicMock()
        vlm.model.generate.return_value = [torch.tensor([1, 2, 3])]

        # Provide a minimal image file
        img_path = tmp_path / "receipt.jpg"
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (10, 10), color=(255, 255, 255))
        img.save(img_path)

        result = vlm.extract_receipt_data(str(img_path))

    # The result must NOT be the empty skeleton — it should come from the local VLM path
    assert result.get("merchant") or result.get("items"), (
        "extract_receipt_data returned an empty skeleton instead of falling "
        "through to the local VLM when docuvision parse yielded no content"
    )
    # parse was called at least twice (once for docuvision, once for local VLM)
    assert call_count["n"] >= 2, (
        "Expected _parse_json_from_text to be called for both the docuvision "
        f"path and the local VLM path, but it was called {call_count['n']} time(s)"
    )


def test_extract_receipt_data_uses_docuvision_when_parse_succeeds(
    tmp_path: Path,
) -> None:
    """When docuvision returns text that yields meaningful parsed content,
    extract_receipt_data must return that result and skip the local VLM."""
    from app.services.ocr.vl_model import VisionLanguageOCR

    vlm = VisionLanguageOCR()

    populated_parse = {
        "merchant": {"name": "Target"},
        "transaction": {},
        "items": [{"name": "Shampoo", "quantity": 1, "unit_price": 5.99, "total_price": 5.99}],
        "totals": {"total": 5.99},
        "confidence": {"overall": 0.88},
    }
    docuvision_text = '{"merchant": {"name": "Target"}, "items": [...]}'

    with (
        patch("app.services.ocr.vl_model._try_docuvision", return_value=docuvision_text),
        patch.object(vlm, "_parse_json_from_text", return_value=populated_parse),
        patch.object(vlm, "_validate_result", side_effect=lambda r: r),
        patch.object(vlm, "_load_model") as mock_load,
    ):
        result = vlm.extract_receipt_data(str(tmp_path / "receipt.jpg"))

    # Local VLM should NOT have been loaded — docuvision fast path handled it
    mock_load.assert_not_called()
    assert result["merchant"]["name"] == "Target"
    assert result["raw_text"] == docuvision_text
