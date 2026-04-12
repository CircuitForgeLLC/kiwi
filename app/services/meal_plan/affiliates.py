# app/services/meal_plan/affiliates.py
"""Register Kiwi-specific affiliate programs and provide search URL builders.

Called once at API startup. Programs not yet in core.affiliates are registered
here. The actual affiliate IDs are read from environment variables at call
time, so the process can start before accounts are approved (plain URLs
returned when env vars are absent).
"""
from __future__ import annotations

from urllib.parse import quote_plus

from circuitforge_core.affiliates import AffiliateProgram, register_program, wrap_url


# ── URL builders ──────────────────────────────────────────────────────────────

def _walmart_search(url: str, affiliate_id: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}affil=apa&affiliateId={affiliate_id}"


def _target_search(url: str, affiliate_id: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}afid={affiliate_id}"


def _thrive_search(url: str, affiliate_id: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}raf={affiliate_id}"


def _misfits_search(url: str, affiliate_id: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}ref={affiliate_id}"


# ── Registration ──────────────────────────────────────────────────────────────

def register_kiwi_programs() -> None:
    """Register Kiwi retailer programs. Safe to call multiple times (idempotent)."""
    register_program(AffiliateProgram(
        name="Walmart",
        retailer_key="walmart",
        env_var="WALMART_AFFILIATE_ID",
        build_url=_walmart_search,
    ))
    register_program(AffiliateProgram(
        name="Target",
        retailer_key="target",
        env_var="TARGET_AFFILIATE_ID",
        build_url=_target_search,
    ))
    register_program(AffiliateProgram(
        name="Thrive Market",
        retailer_key="thrive",
        env_var="THRIVE_AFFILIATE_ID",
        build_url=_thrive_search,
    ))
    register_program(AffiliateProgram(
        name="Misfits Market",
        retailer_key="misfits",
        env_var="MISFITS_AFFILIATE_ID",
        build_url=_misfits_search,
    ))


# ── Search URL helpers ─────────────────────────────────────────────────────────

_SEARCH_TEMPLATES: dict[str, str] = {
    "amazon":    "https://www.amazon.com/s?k={q}",
    "instacart": "https://www.instacart.com/store/search_v3/term?term={q}",
    "walmart":   "https://www.walmart.com/search?q={q}",
    "target":    "https://www.target.com/s?searchTerm={q}",
    "thrive":    "https://thrivemarket.com/search?q={q}",
    "misfits":   "https://www.misfitsmarket.com/shop?search={q}",
}

KIWI_RETAILERS = list(_SEARCH_TEMPLATES.keys())


def get_retailer_links(ingredient_name: str) -> list[dict]:
    """Return affiliate-wrapped search links for *ingredient_name*.

    Returns a list of dicts: {"retailer": str, "label": str, "url": str}.
    Falls back to plain search URL when no affiliate ID is configured.
    """
    q = quote_plus(ingredient_name)
    links = []
    for key, template in _SEARCH_TEMPLATES.items():
        plain_url = template.format(q=q)
        try:
            affiliate_url = wrap_url(plain_url, retailer=key)
        except Exception:
            affiliate_url = plain_url
        links.append({"retailer": key, "label": _label(key), "url": affiliate_url})
    return links


def _label(key: str) -> str:
    return {
        "amazon": "Amazon",
        "instacart": "Instacart",
        "walmart": "Walmart",
        "target": "Target",
        "thrive": "Thrive Market",
        "misfits": "Misfits Market",
    }.get(key, key.title())
