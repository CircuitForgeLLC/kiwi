# app/services/community/mdns.py
# MIT License
# mDNS advertisement for Kiwi instances on the local network.
# Advertises _kiwi._tcp.local so other Kiwi instances (and discovery apps)
# can find this one without manual configuration.
#
# Opt-in only: enabled=False by default. Users are prompted on first community
# tab access. Never advertised without explicit consent (a11y requirement).

from __future__ import annotations

import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

# Deferred import — avoid hard failure when zeroconf is not installed.
try:
    from zeroconf import ServiceInfo, Zeroconf
    _ZEROCONF_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ZEROCONF_AVAILABLE = False


class KiwiMDNS:
    """Context manager that advertises this Kiwi instance via mDNS (_kiwi._tcp.local).

    Defaults to disabled. User must explicitly opt in via Settings.
    feed_url is broadcast in the TXT record so peer instances know where to fetch posts.

    Usage:
        mdns = KiwiMDNS(
            enabled=settings.MDNS_ENABLED,
            port=8512,
            feed_url="http://10.0.0.5:8512/api/v1/community/local-feed",
        )
        mdns.start()   # in lifespan startup
        mdns.stop()    # in lifespan shutdown
    """

    SERVICE_TYPE = "_kiwi._tcp.local."

    def __init__(
        self,
        port: int = 8512,
        name: str | None = None,
        feed_url: str = "",
        enabled: bool = False,
    ) -> None:
        self._port = port
        self._name = name or f"kiwi-{socket.gethostname()}"
        self._feed_url = feed_url
        self._enabled = enabled
        self._zc: Any = None
        self._info: Any = None

    def start(self) -> None:
        if not self._enabled:
            logger.info("mDNS advertisement disabled (user opt-in required)")
            return
        try:
            local_ip = _get_local_ip()
            props = {b"product": b"kiwi", b"version": b"1"}
            if self._feed_url:
                props[b"feed"] = self._feed_url.encode()

            self._info = ServiceInfo(
                type_=self.SERVICE_TYPE,
                name=f"{self._name}.{self.SERVICE_TYPE}",
                addresses=[socket.inet_aton(local_ip)],
                port=self._port,
                properties=props,
                server=f"{socket.gethostname()}.local.",
            )
            self._zc = Zeroconf()
            self._zc.register_service(self._info)
            logger.info("mDNS: advertising %s on %s:%d", self._name, local_ip, self._port)
        except Exception as exc:
            logger.warning("mDNS advertisement failed (non-fatal): %s", exc)
            self._zc = None
            self._info = None

    def stop(self) -> None:
        if self._zc and self._info:
            try:
                self._zc.unregister_service(self._info)
                self._zc.close()
                logger.info("mDNS: unregistered %s", self._name)
            except Exception as exc:
                logger.warning("mDNS unregister failed (non-fatal): %s", exc)
            finally:
                self._zc = None
                self._info = None

    def __enter__(self) -> "KiwiMDNS":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


def _get_local_ip() -> str:
    """Return the primary non-loopback IPv4 address of this host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
