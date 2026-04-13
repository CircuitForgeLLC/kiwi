# app/services/community/mdns.py
# MIT License

from __future__ import annotations

import logging
import socket

logger = logging.getLogger(__name__)

# Import deferred to avoid hard failure when zeroconf is not installed
try:
    from zeroconf import ServiceInfo, Zeroconf
    _ZEROCONF_AVAILABLE = True
except ImportError:
    _ZEROCONF_AVAILABLE = False


class KiwiMDNS:
    """Advertise this Kiwi instance on the LAN via mDNS (_kiwi._tcp.local).

    Defaults to disabled (enabled=False). User must explicitly opt in via the
    Settings page. This matches the CF a11y requirement: no surprise broadcasting.

    Usage:
        mdns = KiwiMDNS(enabled=settings.MDNS_ENABLED, port=settings.PORT,
                        feed_url=f"http://{hostname}:{settings.PORT}/api/v1/community/local-feed")
        mdns.start()   # in lifespan startup
        mdns.stop()    # in lifespan shutdown
    """

    SERVICE_TYPE = "_kiwi._tcp.local."

    def __init__(self, enabled: bool, port: int, feed_url: str) -> None:
        self._enabled = enabled
        self._port = port
        self._feed_url = feed_url
        self._zc: "Zeroconf | None" = None
        self._info: "ServiceInfo | None" = None

    def start(self) -> None:
        if not self._enabled:
            logger.debug("mDNS advertisement disabled (user has not opted in)")
            return
        if not _ZEROCONF_AVAILABLE:
            logger.warning("zeroconf package not installed — mDNS advertisement unavailable")
            return

        hostname = socket.gethostname()
        service_name = f"kiwi-{hostname}.{self.SERVICE_TYPE}"
        self._info = ServiceInfo(
            type_=self.SERVICE_TYPE,
            name=service_name,
            port=self._port,
            properties={
                b"feed_url": self._feed_url.encode(),
                b"version": b"1",
            },
            addresses=[socket.inet_aton("127.0.0.1")],
        )
        self._zc = Zeroconf()
        self._zc.register_service(self._info)
        logger.info("mDNS: advertising %s on port %d", service_name, self._port)

    def stop(self) -> None:
        if self._zc is None or self._info is None:
            return
        self._zc.unregister_service(self._info)
        self._zc.close()
        self._zc = None
        self._info = None
        logger.info("mDNS: advertisement stopped")
