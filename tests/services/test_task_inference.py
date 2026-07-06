"""Tests for app/services/task_inference.py"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _ok_resp(url: str = "http://node:8080", allocation_id: str = "alloc-123") -> MagicMock:
    m = MagicMock()
    m.status_code = 200
    m.is_success = True
    m.json.return_value = {
        "url": url,
        "allocation_id": allocation_id,
        "gpu_id": 0,
        "started": True,
        "warm": False,
    }
    return m


def _err_resp(status_code: int, text: str = "error") -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.is_success = False
    m.text = text
    return m


def test_task_allocate_yields_allocation_on_200(monkeypatch):
    """task_allocate() yields Allocation with url, allocation_id, service on 200."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    with patch("app.services.task_inference.httpx.post", return_value=_ok_resp()) as mock_post, \
         patch("app.services.task_inference.httpx.delete") as mock_del:
        from app.services.task_inference import task_allocate
        with task_allocate("kiwi", "meal_plan", service_hint="cf-text") as alloc:
            assert alloc.url == "http://node:8080"
            assert alloc.allocation_id == "alloc-123"
            assert alloc.service == "cf-text"
        called_url = mock_post.call_args[0][0]
        assert called_url == "http://coord:7700/api/inference/task"
        mock_del.assert_called_once()


def test_task_allocate_uses_service_from_response_when_present(monkeypatch):
    """task_allocate() uses service from response dict over service_hint when available."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    resp = _ok_resp()
    resp.json.return_value["service"] = "cf-vision"
    with patch("app.services.task_inference.httpx.post", return_value=resp), \
         patch("app.services.task_inference.httpx.delete"):
        from app.services.task_inference import task_allocate
        with task_allocate("kiwi", "ocr", service_hint="cf-docuvision") as alloc:
            assert alloc.service == "cf-vision"


def test_task_allocate_404_raises_task_not_registered(monkeypatch):
    """task_allocate() raises TaskNotRegistered on coordinator 404."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    with patch("app.services.task_inference.httpx.post", return_value=_err_resp(404)):
        from app.services.task_inference import TaskNotRegistered, task_allocate
        with pytest.raises(TaskNotRegistered):
            with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
                pass


def test_task_allocate_503_raises_runtime_error(monkeypatch):
    """task_allocate() raises RuntimeError on non-404 coordinator errors."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    with patch("app.services.task_inference.httpx.post", return_value=_err_resp(503, "no GPU")):
        from app.services.task_inference import task_allocate
        with pytest.raises(RuntimeError, match="HTTP 503"):
            with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
                pass


def test_task_allocate_release_called_on_clean_exit(monkeypatch):
    """task_allocate() DELETEs the allocation on clean context exit."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    with patch("app.services.task_inference.httpx.post", return_value=_ok_resp(allocation_id="xyz")), \
         patch("app.services.task_inference.httpx.delete") as mock_del:
        from app.services.task_inference import task_allocate
        with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
            pass
        release_url = mock_del.call_args[0][0]
        assert "cf-text" in release_url
        assert "xyz" in release_url


def test_task_allocate_release_called_when_inner_block_raises(monkeypatch):
    """task_allocate() DELETEs the allocation even when the inner block raises."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    with patch("app.services.task_inference.httpx.post", return_value=_ok_resp(allocation_id="abc")), \
         patch("app.services.task_inference.httpx.delete") as mock_del:
        from app.services.task_inference import task_allocate
        with pytest.raises(ValueError):
            with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
                raise ValueError("inner error")
        mock_del.assert_called_once()


def test_task_allocate_release_failure_is_swallowed(monkeypatch):
    """task_allocate() does not propagate DELETE failures."""
    import httpx as _httpx
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    with patch("app.services.task_inference.httpx.post", return_value=_ok_resp()), \
         patch("app.services.task_inference.httpx.delete",
               side_effect=_httpx.RequestError("gone", request=MagicMock())):
        from app.services.task_inference import task_allocate
        with task_allocate("kiwi", "meal_plan", service_hint="cf-text") as alloc:
            assert alloc.url == "http://node:8080"
        # no exception raised


def test_task_allocate_no_orch_url_raises_runtime_error(monkeypatch):
    """task_allocate() raises RuntimeError when CF_ORCH_URL is not set."""
    monkeypatch.delenv("CF_ORCH_URL", raising=False)
    from app.services.task_inference import task_allocate
    with pytest.raises(RuntimeError, match="CF_ORCH_URL"):
        with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
            pass


def test_task_allocate_network_error_raises_runtime_error(monkeypatch):
    """task_allocate() wraps httpx.RequestError in RuntimeError."""
    import httpx as _httpx
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    with patch("app.services.task_inference.httpx.post",
               side_effect=_httpx.RequestError("timeout", request=MagicMock())):
        from app.services.task_inference import task_allocate
        with pytest.raises(RuntimeError, match="unreachable"):
            with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
                pass


def test_task_allocate_malformed_json_raises_runtime_error(monkeypatch):
    """task_allocate() raises RuntimeError when coordinator returns non-JSON on 200."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    bad_resp = MagicMock()
    bad_resp.status_code = 200
    bad_resp.is_success = True
    bad_resp.text = "<html>proxy error</html>"
    bad_resp.json.side_effect = ValueError("not json")
    with patch("app.services.task_inference.httpx.post", return_value=bad_resp):
        from app.services.task_inference import task_allocate
        with pytest.raises(RuntimeError, match="malformed"):
            with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
                pass


def test_task_allocate_missing_url_field_raises_runtime_error(monkeypatch):
    """task_allocate() raises RuntimeError when coordinator response is missing url field."""
    monkeypatch.setenv("CF_ORCH_URL", "http://coord:7700")
    bad_resp = MagicMock()
    bad_resp.status_code = 200
    bad_resp.is_success = True
    bad_resp.text = '{"allocation_id": "x"}'
    bad_resp.json.return_value = {"allocation_id": "x"}  # missing "url"
    with patch("app.services.task_inference.httpx.post", return_value=bad_resp):
        from app.services.task_inference import task_allocate
        with pytest.raises(RuntimeError, match="malformed"):
            with task_allocate("kiwi", "meal_plan", service_hint="cf-text"):
                pass
