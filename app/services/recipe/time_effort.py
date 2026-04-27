"""
Runtime parser for active/passive time split, prep effort, and equipment detection.

Operates over a list of direction strings plus an optional ingredient list.
No I/O — pure Python functions. Sub-millisecond for up to 20 recipes.

Time estimation strategy (in priority order):
1. Explicit time mention in step text  ("simmer for 20 minutes")
2. Passive keyword + per-technique default  ("bake until golden" → 30 min)
3. Prep action + ingredient quantity scaling  ("dice 2 lbs potatoes" → ~5 min)
4. Fallback active default  (assembly/misc steps → 2 min each)

Quantity scaling uses n^0.75 (sub-linear, matching human batch-work curves).
Pass `ingredients` + `ingredient_names` to enable cross-referenced scaling.
Without them, prep actions use base times only (no scaling).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Final

# ── Passive step keywords ─────────────────────────────────────────────────

_PASSIVE_PATTERNS: Final[list[str]] = [
    "simmer", "bake", "roast", "broil", "refrigerate", "marinate",
    "chill", "cool", "freeze", "rest", "stand", "set", "soak",
    "steep", "proof", "rise", "let", "wait", "overnight", "braise",
    r"slow\s+cook", r"pressure\s+cook",
]

_PASSIVE_RE: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(_PASSIVE_PATTERNS) + r")\b",
    re.IGNORECASE,
)

# Per-technique passive defaults (minutes) — used when no explicit time found.
# Calibrated to conservative midpoints from USDA FoodKeeper + culinary practice.
_PASSIVE_DEFAULTS: Final[list[tuple[re.Pattern[str], int]]] = [
    # Multi-word first (longer match wins)
    (re.compile(r"\bslow\s+cook\b", re.IGNORECASE), 300),      # 5 hr crockpot default
    (re.compile(r"\bpressure\s+cook\b", re.IGNORECASE), 15),
    (re.compile(r"\bovernight\b", re.IGNORECASE), 480),         # 8 hr
    # Single-word
    (re.compile(r"\bbraise\b", re.IGNORECASE), 90),
    (re.compile(r"\bmarinate\b", re.IGNORECASE), 60),
    (re.compile(r"\brefrigerate\b", re.IGNORECASE), 120),
    (re.compile(r"\bproof\b|\brise\b", re.IGNORECASE), 60),
    (re.compile(r"\bsoak\b", re.IGNORECASE), 30),
    (re.compile(r"\bfreeze\b", re.IGNORECASE), 120),
    (re.compile(r"\bchill\b", re.IGNORECASE), 60),
    (re.compile(r"\broast\b", re.IGNORECASE), 40),
    (re.compile(r"\bbake\b", re.IGNORECASE), 30),
    (re.compile(r"\bbroil\b", re.IGNORECASE), 8),
    (re.compile(r"\bsimmer\b", re.IGNORECASE), 20),
    (re.compile(r"\bset\b", re.IGNORECASE), 30),                # gelatin / custard set
    (re.compile(r"\bsteep\b", re.IGNORECASE), 5),
    (re.compile(r"\brest\b|\bstand\b", re.IGNORECASE), 10),
    (re.compile(r"\bcool\b", re.IGNORECASE), 15),
    (re.compile(r"\bwait\b|\blet\b", re.IGNORECASE), 5),
]

# ── Explicit time extraction ──────────────────────────────────────────────

_TIME_RE: re.Pattern[str] = re.compile(
    r"(\d+)\s*(?:[-\u2013]|-to-)\s*(\d+)\s*(hour|hr|minute|min|second|sec)s?"
    r"|"
    r"(\d+)\s*(hour|hr|minute|min|second|sec)s?",
    re.IGNORECASE,
)

_MAX_MINUTES_PER_STEP: Final[int] = 480  # 8-hour sanity cap

# ── Prep action detection ─────────────────────────────────────────────────

# Base times (minutes) per prep action, calibrated to ~3 items / 0.5 lb reference.
# These are starting points — flagged for calibration against real recipe timing data.
_PREP_ACTION_BASES: Final[dict[str, float]] = {
    # Peeling / stripping
    "peel": 1.5,
    "pare": 1.5,
    "hull": 1.5,
    "pit": 2.0,     # cherries, avocados
    "core": 1.0,
    "stem": 1.0,
    "trim": 1.0,
    # Cutting
    "chop": 2.0,
    "cut": 1.5,
    "dice": 2.5,    # more precise than chop
    "mince": 2.0,
    "slice": 1.5,
    "julienne": 4.0,
    "cube": 2.0,
    "quarter": 1.0,
    "halve": 0.5,
    "shred": 2.0,
    # Grating / zesting
    "grate": 3.0,
    "zest": 2.0,
    # Crushing
    "crush": 0.5,
    "smash": 0.5,
    "crack": 0.5,
    # Mixing / assembly (lower base — less physical effort)
    "knead": 8.0,       # bread dough: consistent regardless of quantity
    "whisk": 1.5,
    "beat": 2.0,
    "cream": 3.0,       # butter + sugar until fluffy
    "fold": 1.5,
    "stir": 0.5,
    "combine": 0.5,
    "mix": 1.0,
    "season": 0.5,
}

# Compiled regex — longer patterns first to avoid partial matches.
_PREP_RE: re.Pattern[str] = re.compile(
    r"\b(?:" + "|".join(
        re.escape(k) for k in sorted(_PREP_ACTION_BASES, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)

# Default active time per step when no explicit time and no prep action detected.
_ACTIVE_STEP_DEFAULT_MIN: Final[float] = 2.0

# ── Prep-needing ingredient classification ────────────────────────────────
#
# Only ingredients in this set get quantity-scaled prep time.
# Liquids, spices, canned goods, and dry staples are excluded — they require
# no physical prep beyond measuring.

_PREP_NEEDING: Final[frozenset[str]] = frozenset({
    # Alliums
    "onion", "shallot", "leek", "scallion", "green onion", "chive", "garlic",
    # Root / stem vegetables
    "ginger", "carrot", "celery", "potato", "sweet potato", "yam",
    "beet", "turnip", "parsnip", "radish", "fennel", "celeriac",
    # Squash / gourd family
    "zucchini", "squash", "pumpkin", "cucumber",
    # Peppers
    "pepper", "bell pepper", "jalapeño", "jalapeno", "chili", "chile",
    # Brassicas
    "broccoli", "cauliflower", "cabbage", "kale", "chard", "spinach",
    "brussels sprout",
    # Other vegetables
    "tomato", "eggplant", "aubergine", "corn", "artichoke", "asparagus",
    "green bean", "snow pea", "snap pea", "mushroom", "lettuce",
    # Fruits
    "apple", "pear", "peach", "nectarine", "plum", "apricot",
    "mango", "papaya", "pineapple", "melon", "watermelon", "cantaloupe",
    "avocado", "banana",
    "strawberry", "raspberry", "blackberry", "blueberry", "cherry",
    "citrus", "lemon", "lime", "orange", "grapefruit",
    # Protein (trimming / portioning)
    "chicken", "turkey", "duck",
    "beef", "pork", "lamb", "veal",
    "fish", "salmon", "tuna", "cod", "tilapia", "halibut", "shrimp",
    "scallop", "crab", "lobster",
    # Dairy requiring active prep
    "cheese",
    # Nuts / seeds (chopping)
    "almond", "walnut", "pecan", "cashew", "peanut", "hazelnut",
    "pistachio", "macadamia", "nut",
    # Fresh herbs (chopping / tearing)
    "basil", "parsley", "cilantro", "thyme", "rosemary", "sage",
    "dill", "mint", "tarragon",
    # Other
    "bread",
})


def _is_prep_needing(name: str) -> bool:
    """True if the normalized ingredient name contains any prep-needing keyword."""
    nl = name.lower()
    return any(kw in nl for kw in _PREP_NEEDING)


# ── Quantity extraction ───────────────────────────────────────────────────

_FRAC_RE: re.Pattern[str] = re.compile(r"(\d+)\s*/\s*(\d+)")

# Weight units → converted to pounds internally
_WEIGHT_RE: re.Pattern[str] = re.compile(
    r"(\d+(?:\.\d+)?|\d+\s*/\s*\d+)\s*"
    r"(pound|lb|ounce|oz|gram|g(?![a-z])|kilogram|kg)\s*s?\b",
    re.IGNORECASE,
)

# Volume (cups only — the common recipe unit for quantity scaling)
_VOLUME_CUP_RE: re.Pattern[str] = re.compile(
    r"(\d+(?:\.\d+)?|\d+\s*/\s*\d+)\s*cups?\b",
    re.IGNORECASE,
)

# Count — bare integer or decimal followed by optional size/unit word
_COUNT_RE: re.Pattern[str] = re.compile(
    r"(?<!\d)(\d+(?:\.\d+)?)\s*"
    r"(?:large|medium|small|whole|clove|cloves|head|heads|ear|ears|"
    r"stalk|stalks|sprig|sprigs|bunch|bunches|fillet|fillets|"
    r"breast|breasts|piece|pieces|slice|slices)?\s*\b",
    re.IGNORECASE,
)

# Reference quantities: the "1× base" for each unit type.
# Calibrated so that a typical single-ingredient amount = 1× prep time.
_QTY_REFS: Final[dict[str, float]] = {
    "lb":    0.5,    # 0.5 lb is the base → 1 lb = 1.4×, 2 lb = 2.0×
    "cup":   1.0,    # 1 cup = base
    "count": 3.0,    # 3 items = base → 1 = 0.46×, 6 = 1.6×
}

_SCALE_POWER:  Final[float] = 0.75   # sub-linear; revisit with empirical data
_MAX_SCALE:    Final[float] = 4.0    # cap at 4× regardless of quantity
_MIN_SCALE:    Final[float] = 0.33   # floor at 1/3× for tiny amounts


def _parse_fraction(s: str) -> float:
    m = _FRAC_RE.search(s)
    if m:
        try:
            return float(m.group(1)) / float(m.group(2))
        except (ValueError, ZeroDivisionError):
            return 1.0
    try:
        return float(s.replace(" ", ""))
    except ValueError:
        return 1.0


def _extract_qty(text: str) -> tuple[float, str] | None:
    """Return (quantity_in_canonical_units, unit_type) or None.

    Unit types: "lb" (weight in pounds), "cup", "count".
    All weights are normalised to pounds.
    """
    # Weight (most specific — check first)
    m = _WEIGHT_RE.search(text)
    if m:
        qty = _parse_fraction(m.group(1))
        u = m.group(2).lower().rstrip("s")
        if u in ("pound", "lb"):
            return (qty, "lb")
        if u in ("ounce", "oz"):
            return (qty / 16.0, "lb")
        if u in ("gram", "g"):
            return (qty / 453.6, "lb")
        if u in ("kilogram", "kg"):
            return (qty * 2.205, "lb")

    # Volume (cups)
    m = _VOLUME_CUP_RE.search(text)
    if m:
        return (_parse_fraction(m.group(1)), "cup")

    # Count — only accept values in a sane range to avoid false positives
    m = _COUNT_RE.search(text)
    if m:
        qty = float(m.group(1))
        if 0 < qty <= 24:
            return (qty, "count")

    return None


def _extract_inline_qty_for(text: str, ing_name: str) -> tuple[float, str] | None:
    """Extract the quantity specifically associated with `ing_name` in a direction step.

    Looks for a number immediately before the ingredient name (plus optional size/unit
    words). Falls back to None if the pattern does not match.

    Example: "Dice 2 large onions and 3 carrots" → for "onion" returns (2.0, "count").
    """
    pattern = re.compile(
        r"(\d+(?:\.\d+)?|\d+\s*/\s*\d+)\s*"
        r"(?:large|medium|small|whole|"
        r"(?:pound|lb|ounce|oz|gram|g|kilogram|kg|cup|clove|cloves|"
        r"head|heads|fillet|fillets|breast|breasts|piece|pieces)s?)??\s*"
        + re.escape(ing_name) + r"(?:es|s)?\b",
        re.IGNORECASE,
    )
    m = pattern.search(text)
    if m:
        # Re-extract with _extract_qty on the full matched span to get unit too
        span = text[m.start(): m.end()]
        result = _extract_qty(span)
        if result:
            return result
        # Fallback: bare count
        try:
            return (_parse_fraction(m.group(1)), "count")
        except Exception:
            pass
    return None


def _quantity_scale(qty: float, unit: str) -> float:
    """Apply n^0.75 scaling relative to unit reference, clamped to [MIN, MAX]."""
    ref = _QTY_REFS.get(unit, 1.0)
    if ref <= 0 or qty <= 0:
        return 1.0
    raw = (qty / ref) ** _SCALE_POWER
    return max(_MIN_SCALE, min(_MAX_SCALE, raw))


# ── Equipment detection ───────────────────────────────────────────────────

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


def _detect_equipment(all_text: str, has_passive: bool) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for pattern, label in _EQUIPMENT_RULES:
        if label not in seen and pattern.search(all_text):
            seen.add(label)
            result.append(label)
    if has_passive and "Timer" not in seen:
        result.append("Timer")
    return result


# ── Ingredient–step cross-reference ──────────────────────────────────────

def _ingredient_mentioned(text: str, name: str) -> bool:
    """True if `name` appears in `text` as a whole word.

    Handles both regular plurals (onion → onions) and -es plurals
    (potato → potatoes, tomato → tomatoes).
    """
    pattern = re.compile(r"\b" + re.escape(name.lower()) + r"(?:es|s)?\b", re.IGNORECASE)
    return bool(pattern.search(text))


def _build_step_ingredient_qtys(
    ingredients: list[str],
    ingredient_names: list[str],
    directions: list[str],
) -> list[dict[str, tuple[float, str]]]:
    """Return, for each direction step, {ing_name: (qty_for_this_step, unit)}.

    Strategy:
    - Filter ingredient pairs to prep-needing items only.
    - Parse total quantities from the raw ingredient strings.
    - For each step, try to find an inline quantity tied to that ingredient name.
    - If no inline quantity, distribute the total evenly across all steps that
      mention the ingredient (handles "3 onions" split across 2 steps).
    """
    # Build total qty map for prep-needing ingredients
    total_qtys: dict[str, tuple[float, str]] = {}
    for raw, name in zip(ingredients, ingredient_names):
        base = name.lower().strip()
        if not _is_prep_needing(base):
            continue
        result = _extract_qty(raw)
        if result is not None:
            total_qtys[base] = result

    if not total_qtys:
        return [{} for _ in directions]

    # Count how many steps mention each ingredient
    step_counts: dict[str, int] = {n: 0 for n in total_qtys}
    for step in directions:
        for name in total_qtys:
            if _ingredient_mentioned(step, name):
                step_counts[name] += 1

    # Build per-step qty maps
    per_step: list[dict[str, tuple[float, str]]] = []
    for step in directions:
        step_map: dict[str, tuple[float, str]] = {}
        for name, (total, unit) in total_qtys.items():
            if not _ingredient_mentioned(step, name):
                continue
            # Try ingredient-specific inline quantity first
            inline = _extract_inline_qty_for(step, name)
            if inline is not None:
                step_map[name] = inline
            else:
                # Distribute total across steps that reference this ingredient
                n = max(step_counts.get(name, 1), 1)
                step_map[name] = (total / n, unit)
        per_step.append(step_map)

    return per_step


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StepAnalysis:
    """Analysis result for a single direction step."""
    is_passive: bool
    detected_minutes: int | None   # explicit or estimated time (None = no signal)
    prep_min: int | None = None    # estimated physical prep time from action detection


@dataclass(frozen=True)
class TimeEffortProfile:
    """Aggregated time and effort profile for a full recipe."""
    active_min: int
    passive_min: int
    total_min: int
    step_analyses: list[StepAnalysis] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    effort_label: str = "moderate"   # "quick" | "moderate" | "involved"


# ── Core parsing helpers ──────────────────────────────────────────────────


def _extract_minutes(text: str) -> int | None:
    """Return explicit minutes from text, or None."""
    m = _TIME_RE.search(text)
    if m is None:
        return None
    if m.group(1) is not None:
        low, high = int(m.group(1)), int(m.group(2))
        unit = m.group(3).lower()
        raw: float = (low + high) / 2
    else:
        low = int(m.group(4))
        unit = m.group(5).lower()
        raw = float(low)

    if unit in ("hour", "hr"):
        minutes: float = raw * 60
    elif unit in ("second", "sec"):
        minutes = max(1.0, math.ceil(raw / 60))
    else:
        minutes = raw

    return min(int(minutes), _MAX_MINUTES_PER_STEP)


def _classify_passive(text: str) -> bool:
    return _PASSIVE_RE.search(text) is not None


def _passive_default(text: str) -> int | None:
    """Return estimated passive minutes from per-keyword defaults."""
    for pattern, minutes in _PASSIVE_DEFAULTS:
        if pattern.search(text):
            return minutes
    return None


def _prep_estimate(
    text: str,
    step_ing_qtys: dict[str, tuple[float, str]],
) -> int:
    """Estimate active prep time from the first detected prep action + ingredient qtys.

    If no prep-needing ingredient is identified in the step, uses the action's
    base time at 1× (no scaling).
    """
    m = _PREP_RE.search(text)
    if m is None:
        return 0

    action = m.group(0).lower()
    base = _PREP_ACTION_BASES.get(action, _ACTIVE_STEP_DEFAULT_MIN)

    # Find which prep-needing ingredients this step mentions
    matches: list[tuple[float, str]] = [
        qty_unit
        for name, qty_unit in step_ing_qtys.items()
        if _ingredient_mentioned(text, name)
    ]

    if not matches:
        return round(base)   # no ingredient context — use base unscaled

    total = sum(base * _quantity_scale(qty, unit) for qty, unit in matches)
    return round(total)


def _effort_label(total_min: int, step_count: int) -> str:
    """Effort label based on total estimated time; falls back to step count."""
    if total_min > 0:
        if total_min <= 20:
            return "quick"
        if total_min <= 45:
            return "moderate"
        return "involved"
    # No time signals at all — fall back to step count heuristic
    if step_count <= 3:
        return "quick"
    if step_count <= 7:
        return "moderate"
    return "involved"


# ── Public API ────────────────────────────────────────────────────────────


def parse_time_effort(
    directions: list[str],
    ingredients: list[str] | None = None,
    ingredient_names: list[str] | None = None,
) -> TimeEffortProfile:
    """Parse direction strings into a TimeEffortProfile.

    Args:
        directions:       List of step strings from the recipe corpus.
        ingredients:      Raw ingredient strings ("2 large onions", "1.5 lbs potatoes").
                          Parallel to ingredient_names.
        ingredient_names: Normalised ingredient names ("onion", "potato").
                          Required alongside ingredients to enable quantity scaling.

    Returns a zero-value profile with empty lists when directions is empty.
    Never raises — all failures produce sensible defaults.
    """
    if not directions:
        return TimeEffortProfile(
            active_min=0, passive_min=0, total_min=0,
            step_analyses=[], equipment=[], effort_label="quick",
        )

    # Build per-step ingredient quantity maps (empty dicts if no ingredient data)
    use_ingredients = (
        bool(ingredients)
        and bool(ingredient_names)
        and len(ingredients) == len(ingredient_names)
    )
    step_ing_qtys: list[dict[str, tuple[float, str]]]
    if use_ingredients:
        step_ing_qtys = _build_step_ingredient_qtys(
            list(ingredients),       # type: ignore[arg-type]
            list(ingredient_names),  # type: ignore[arg-type]
            directions,
        )
    else:
        step_ing_qtys = [{} for _ in directions]

    step_analyses: list[StepAnalysis] = []
    active_min = 0
    passive_min = 0
    has_any_passive = False

    for i, step in enumerate(directions):
        is_passive = _classify_passive(step)
        detected = _extract_minutes(step)
        prep_estimate: int | None = None

        if is_passive:
            has_any_passive = True
            if detected is not None:
                passive_min += detected
            else:
                # Fall back to per-technique default
                default = _passive_default(step)
                if default is not None:
                    passive_min += default
                    detected = default  # surface in UI as the hint time
        else:
            if detected is not None:
                active_min += detected

            # Estimate prep time from action detection + quantity scaling
            prep_est = _prep_estimate(step, step_ing_qtys[i])
            if prep_est > 0:
                prep_estimate = prep_est
                active_min += prep_est
            elif detected is None:
                # General active step with no time signal — apply a small default
                active_min += round(_ACTIVE_STEP_DEFAULT_MIN)

        step_analyses.append(StepAnalysis(
            is_passive=is_passive,
            detected_minutes=detected,
            prep_min=prep_estimate,
        ))

    combined_text = " ".join(directions)
    equipment = _detect_equipment(combined_text, has_any_passive)
    total = active_min + passive_min

    return TimeEffortProfile(
        active_min=active_min,
        passive_min=passive_min,
        total_min=total,
        step_analyses=step_analyses,
        equipment=equipment,
        effort_label=_effort_label(total, len(directions)),
    )
