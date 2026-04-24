"""
Sensory filter dataclass and helpers.

SensoryExclude bridges user preferences (from user_settings) to the
store browse methods and recipe engine suggest flow.

Recipes with sensory_tags = '{}' (untagged) pass ALL filters --
graceful degradation when tag_sensory_profiles.py has not run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

_SMELL_LEVELS: tuple[str, ...] = ("mild", "aromatic", "pungent", "fermented")
_NOISE_LEVELS: tuple[str, ...] = ("quiet", "moderate", "loud", "very_loud")


@dataclass(frozen=True)
class SensoryExclude:
    """Derived filter criteria from user sensory preferences.

    textures:    texture tags to exclude (empty tuple = no texture filter)
    smell_above: if set, exclude recipes whose smell level is strictly above
                 this level in the smell spectrum
    noise_above: if set, exclude recipes whose noise level is strictly above
                 this level in the noise spectrum
    """
    textures: tuple[str, ...] = field(default_factory=tuple)
    smell_above: str | None = None
    noise_above: str | None = None

    @classmethod
    def empty(cls) -> "SensoryExclude":
        """No filtering -- pass-through for users with no preferences set."""
        return cls()

    def is_empty(self) -> bool:
        """True when no filtering will be applied."""
        return not self.textures and self.smell_above is None and self.noise_above is None


def build_sensory_exclude(prefs_json: str | None) -> SensoryExclude:
    """Parse user_settings value for 'sensory_preferences' into a SensoryExclude.

    Expected JSON shape:
      {
        "avoid_textures": ["mushy", "slimy"],
        "max_smell":      "pungent",
        "max_noise":      "loud"
      }

    Returns SensoryExclude.empty() on missing, null, or malformed input.
    """
    if not prefs_json:
        return SensoryExclude.empty()
    try:
        prefs = json.loads(prefs_json)
    except (json.JSONDecodeError, TypeError):
        return SensoryExclude.empty()
    if not isinstance(prefs, dict):
        return SensoryExclude.empty()

    avoid_textures = tuple(
        t for t in (prefs.get("avoid_textures") or [])
        if isinstance(t, str)
    )
    max_smell: str | None = prefs.get("max_smell") or None
    max_noise: str | None = prefs.get("max_noise") or None

    if max_smell and max_smell not in _SMELL_LEVELS:
        max_smell = None
    if max_noise and max_noise not in _NOISE_LEVELS:
        max_noise = None

    return SensoryExclude(
        textures=avoid_textures,
        smell_above=max_smell,
        noise_above=max_noise,
    )


def passes_sensory_filter(
    sensory_tags_raw: str | dict | None,
    exclude: SensoryExclude,
) -> bool:
    """Return True if the recipe passes the sensory exclude criteria.

    sensory_tags_raw: the sensory_tags column value (JSON string or already-parsed dict).
    exclude:          derived filter criteria.

    Untagged recipes (empty dict or '{}') always pass -- graceful degradation.
    Empty SensoryExclude always passes -- no preferences set.
    """
    if exclude.is_empty():
        return True

    if sensory_tags_raw is None:
        return True
    if isinstance(sensory_tags_raw, str):
        try:
            tags: dict = json.loads(sensory_tags_raw)
        except (json.JSONDecodeError, TypeError):
            return True
    else:
        tags = sensory_tags_raw

    if not tags:
        return True

    if exclude.textures:
        recipe_textures: list[str] = tags.get("textures") or []
        for t in recipe_textures:
            if t in exclude.textures:
                return False

    if exclude.smell_above is not None:
        recipe_smell: str | None = tags.get("smell")
        if recipe_smell and recipe_smell in _SMELL_LEVELS:
            max_idx = _SMELL_LEVELS.index(exclude.smell_above)
            recipe_idx = _SMELL_LEVELS.index(recipe_smell)
            if recipe_idx > max_idx:
                return False

    if exclude.noise_above is not None:
        recipe_noise: str | None = tags.get("noise")
        if recipe_noise and recipe_noise in _NOISE_LEVELS:
            max_idx = _NOISE_LEVELS.index(exclude.noise_above)
            recipe_idx = _NOISE_LEVELS.index(recipe_noise)
            if recipe_idx > max_idx:
                return False

    return True
