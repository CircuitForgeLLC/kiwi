"""Tests for task-based routing added to _try_docuvision()."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _mock_doc_result(text: str = "RECEIPT TEXT") -> MagicMock:
    r = MagicMock()
    r.text = text
    return r


def _make_task_ctx(url: str = "http://node:9010") -> MagicMock:
    alloc = MagicMock()
    alloc.url = url
    alloc.allocation_id = "alloc-vis-1"
    alloc.service = "cf-docuvision"
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=alloc)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_task_not_registered() -> MagicMock:
    from app.services.task_inference import TaskNotRegistered
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(side_effect=TaskNotRegistered("not registered"))
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_direct_alloc(url: str = "http://node:9011") -> MagicMock:
    alloc = MagicMock()
    alloc.url = url
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=alloc)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_try_docuvision_task_path_returns_text(monkeypatch, tmp_path):
    """_try_docuvision() uses task allocation and returns extracted text on success."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    fake_image = tmp_path / "receipt.jpg"
    fake_image.write_bytes(b"fake")

    with patch("app.services.task_inference.task_allocate",
               return_value=_make_task_ctx(url="http://node:9010")), \
         patch("app.services.ocr.docuvision_client.DocuvisionClient") as MockDoc:
        MockDoc.return_value.extract_text.return_value = _mock_doc_result("STORE $12.34")
        from app.services.ocr.vl_model import _try_docuvision
        result = _try_docuvision(str(fake_image))

    assert result == "STORE $12.34"
    MockDoc.assert_called_once_with("http://node:9010")


def test_try_docuvision_falls_back_to_direct_on_task_not_registered(monkeypatch, tmp_path):
    """_try_docuvision() falls back to direct cf-docuvision allocation on TaskNotRegistered."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    fake_image = tmp_path / "receipt.jpg"
    fake_image.write_bytes(b"fake")

    with patch("app.services.task_inference.task_allocate",
               return_value=_make_task_not_registered()), \
         patch("circuitforge_orch.client.CFOrchClient") as MockClient, \
         patch("app.services.ocr.docuvision_client.DocuvisionClient") as MockDoc:
        MockClient.return_value.allocate.return_value = _make_direct_alloc("http://node:9011")
        MockDoc.return_value.extract_text.return_value = _mock_doc_result("FALLBACK TEXT")
        from app.services.ocr.vl_model import _try_docuvision
        result = _try_docuvision(str(fake_image))

    assert result == "FALLBACK TEXT"
    MockDoc.assert_called_once_with("http://node:9011")


def test_try_docuvision_returns_none_without_cf_orch_url(monkeypatch, tmp_path):
    """_try_docuvision() returns None immediately when CF_ORCH_URL is not set."""
    monkeypatch.delenv("CF_ORCH_URL", raising=False)
    fake_image = tmp_path / "receipt.jpg"
    fake_image.write_bytes(b"fake")

    from app.services.ocr.vl_model import _try_docuvision
    result = _try_docuvision(str(fake_image))

    assert result is None
