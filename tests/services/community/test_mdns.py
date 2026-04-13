# tests/services/community/test_mdns.py
import pytest
from unittest.mock import MagicMock, patch
from app.services.community.mdns import KiwiMDNS


def test_mdns_does_not_advertise_when_disabled():
    """When enabled=False, KiwiMDNS does not register any zeroconf service."""
    with patch("app.services.community.mdns.Zeroconf") as mock_zc:
        mdns = KiwiMDNS(enabled=False, port=8512, feed_url="http://localhost:8512/api/v1/community/local-feed")
        mdns.start()
        mock_zc.assert_not_called()


def test_mdns_advertises_when_enabled():
    with patch("app.services.community.mdns.Zeroconf") as mock_zc_cls:
        with patch("app.services.community.mdns.ServiceInfo") as mock_si:
            mock_zc = MagicMock()
            mock_zc_cls.return_value = mock_zc
            mdns = KiwiMDNS(enabled=True, port=8512, feed_url="http://localhost:8512/api/v1/community/local-feed")
            mdns.start()
            mock_zc.register_service.assert_called_once()


def test_mdns_stop_unregisters_when_enabled():
    with patch("app.services.community.mdns.Zeroconf") as mock_zc_cls:
        with patch("app.services.community.mdns.ServiceInfo"):
            mock_zc = MagicMock()
            mock_zc_cls.return_value = mock_zc
            mdns = KiwiMDNS(enabled=True, port=8512, feed_url="http://localhost:8512/api/v1/community/local-feed")
            mdns.start()
            mdns.stop()
            mock_zc.unregister_service.assert_called_once()
            mock_zc.close.assert_called_once()


def test_mdns_stop_is_noop_when_not_started():
    mdns = KiwiMDNS(enabled=False, port=8512, feed_url="http://localhost/feed")
    mdns.stop()  # must not raise
