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
