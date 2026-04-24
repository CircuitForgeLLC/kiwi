"""
Runtime parser for active/passive time split and equipment detection.

Operates over a list of direction strings. No I/O — pure Python functions.
Sub-millisecond for up to 20 recipes (20 × ~10 steps each = 200 regex calls).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Final

# ── Passive step keywords (whole-word, case-insensitive) ──────────────────

_PASSIVE_PATTERNS: Final[list[str]] = [
    "simmer", "bake", "roast", "broil", "refrigerate", "marinate",
    "chill", "cool", "freeze", "rest", "stand", "set", "soak",
    "steep", "proof", "rise", "let", "wait", "overnight", "braise",
    r"slow\s+cook", r"pressure\s+cook",
]

# Pre-compiled as a single alternation — avoids re-compiling on every call.
_PASSIVE_RE: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(_PASSIVE_PATTERNS) + r")\b",
    re.IGNORECASE,
)

# ── Time extraction regex ─────────────────────────────────────────────────

# Two-branch pattern:
#   Branch A (groups 1-3): range  "15-20 minutes", "15–20 min"
#   Branch B (groups 4-5): single "10 minutes", "2 hours", "30 sec"
#
# Separator characters: plain hyphen (-), en-dash (–), or literal "-to-"
_TIME_RE: re.Pattern[str] = re.compile(
    r"(\d+)\s*(?:[-\u2013]|-to-)\s*(\d+)\s*(hour|hr|minute|min|second|sec)s?"
    r"|"
    r"(\d+)\s*(hour|hr|minute|min|second|sec)s?",
    re.IGNORECASE,
)

_MAX_MINUTES_PER_STEP: Final[int] = 480  # 8 hours sanity cap

# ── Equipment detection (keyword → label, in detection priority order) ────

_EQUIPMENT_RULES: Final[list[tuple[re.Pattern[str], str]]] = [
    (re.compile(r"\b(?:chop|dice|mince|slice|julienne)\b", re.IGNORECASE), "Knife"),
    (re.compile(r"\b(?:skillet|sauté|saute|fry|sear|pan-fry|pan fry)\b", re.IGNORECASE), "Skillet"),
    (re.compile(r"\b(?:wooden spoon|spatula|stir|fold)\b", re.IGNORECASE), "Spoon"),
    (re.compile(r"\b(?:pot|boil|simmer|blanch|stock)\b", re.IGNORECASE), "Pot"),
    (re.compile(r"\b(?:oven|bake|roast|preheat|broil)\b", re.IGNORECASE), "Oven"),
    (re.compile(r"\b(?:blender|blend|purée|puree|food processor)\b", re.IGNORECASE), "Blender"),
    (re.compile(r"\b(?:stand mixer|hand mixer|whip|beat)\b", re.IGNORECASE), "Mixer"),
    (re.compile(r"\b(?:grill|barbecue|char|griddle)\b", re.IGNORECASE), "Grill"),
    (re.compile(r"\b(?:slow cooker|crockpot|low and slow)\b", re.IGNORECASE), "Slow cooker"),
    (re.compile(r"\b(?:pressure cooker|instant pot)\b", re.IGNORECASE), "Pressure cooker"),
    (re.compile(r"\b(?:drain|strain|colander|rinse pasta)\b", re.IGNORECASE), "Colander"),
]

# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StepAnalysis:
    """Analysis result for a single direction step."""
    is_passive: bool
    detected_minutes: int | None  # None when no time mention found in text


@dataclass(frozen=True)
class TimeEffortProfile:
    """Aggregated time and effort profile for a full recipe."""
    active_min: int                    # total minutes requiring active attention
    passive_min: int                   # total minutes the cook can step away
    total_min: int                     # active_min + passive_min
    step_analyses: list[StepAnalysis]  # one entry per direction step
    equipment: list[str]               # ordered, deduplicated equipment labels
    effort_label: str                  # "quick" | "moderate" | "involved"


# ── Core parsing logic ────────────────────────────────────────────────────


def _extract_minutes(text: str) -> int | None:
    """Return the number of minutes mentioned in text, or None.

    Range values (e.g. "15-20 minutes") return the integer midpoint.
    Hours are converted to minutes. Seconds are rounded up to 1 minute minimum.
    Result is capped at _MAX_MINUTES_PER_STEP.
    """
    m = _TIME_RE.search(text)
    if m is None:
        return None

    if m.group(1) is not None:
        # Branch A: range match (e.g. "15-20 minutes")
        low = int(m.group(1))
        high = int(m.group(2))
        unit = m.group(3).lower()
        raw_value: float = (low + high) / 2
    else:
        # Branch B: single value match (e.g. "10 minutes")
        low = int(m.group(4))
        unit = m.group(5).lower()
        raw_value = float(low)

    if unit in ("hour", "hr"):
        minutes: float = raw_value * 60
    elif unit in ("second", "sec"):
        minutes = max(1.0, math.ceil(raw_value / 60))
    else:
        minutes = raw_value

    return min(int(minutes), _MAX_MINUTES_PER_STEP)


def _classify_passive(text: str) -> bool:
    """Return True if the step text matches any passive keyword (whole-word)."""
    return _PASSIVE_RE.search(text) is not None


def _detect_equipment(all_text: str, has_passive: bool) -> list[str]:
    """Return ordered, deduplicated list of equipment labels detected in text.

    all_text should be all direction steps joined with spaces.
    has_passive controls whether 'Timer' is appended at the end.
    """
    seen: set[str] = set()
    result: list[str] = []
    for pattern, label in _EQUIPMENT_RULES:
        if label not in seen and pattern.search(all_text):
            seen.add(label)
            result.append(label)
    if has_passive and "Timer" not in seen:
        result.append("Timer")
    return result


def _effort_label(step_count: int) -> str:
    """Derive effort label from step count."""
    if step_count <= 3:
        return "quick"
    if step_count <= 7:
        return "moderate"
    return "involved"


def parse_time_effort(directions: list[str]) -> TimeEffortProfile:
    """Parse a list of direction strings into a TimeEffortProfile.

    Returns a zero-value profile with empty lists when directions is empty.
    Never raises — all failures silently produce sensible defaults.
    """
    if not directions:
        return TimeEffortProfile(
            active_min=0,
            passive_min=0,
            total_min=0,
            step_analyses=[],
            equipment=[],
            effort_label="quick",
        )

    step_analyses: list[StepAnalysis] = []
    active_min = 0
    passive_min = 0
    has_any_passive = False

    for step in directions:
        is_passive = _classify_passive(step)
        detected = _extract_minutes(step)

        if is_passive:
            has_any_passive = True
            if detected is not None:
                passive_min += detected
        else:
            if detected is not None:
                active_min += detected

        step_analyses.append(StepAnalysis(
            is_passive=is_passive,
            detected_minutes=detected,
        ))

    combined_text = " ".join(directions)
    equipment = _detect_equipment(combined_text, has_any_passive)

    return TimeEffortProfile(
        active_min=active_min,
        passive_min=passive_min,
        total_min=active_min + passive_min,
        step_analyses=step_analyses,
        equipment=equipment,
        effort_label=_effort_label(len(directions)),
    )
