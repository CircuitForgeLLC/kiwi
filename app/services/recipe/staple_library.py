"""
StapleLibrary -- bulk-preparable base component reference data.
Loaded from YAML files in app/staples/.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_STAPLES_DIR = Path(__file__).parents[2] / "staples"


@dataclass(frozen=True)
class StapleEntry:
    slug: str
    name: str
    description: str
    dietary_labels: list[str]
    base_ingredients: list[str]
    base_method: str
    base_time_minutes: int
    yield_formats: dict[str, dict]
    compatible_styles: list[str]


class StapleLibrary:
    def __init__(self, staples_dir: Path = _STAPLES_DIR) -> None:
        self._staples: dict[str, StapleEntry] = {}
        for yaml_path in sorted(staples_dir.glob("*.yaml")):
            entry = self._load(yaml_path)
            self._staples[entry.slug] = entry

    def get(self, slug: str) -> StapleEntry | None:
        return self._staples.get(slug)

    def list_all(self) -> list[StapleEntry]:
        return list(self._staples.values())

    def filter_by_dietary(self, label: str) -> list[StapleEntry]:
        return [s for s in self._staples.values() if label in s.dietary_labels]

    def _load(self, path: Path) -> StapleEntry:
        data = yaml.safe_load(path.read_text())
        return StapleEntry(
            slug=data["slug"],
            name=data["name"],
            description=data.get("description", ""),
            dietary_labels=data.get("dietary_labels", []),
            base_ingredients=data.get("base_ingredients", []),
            base_method=data.get("base_method", ""),
            base_time_minutes=int(data.get("base_time_minutes", 0)),
            yield_formats=data.get("yield_formats", {}),
            compatible_styles=data.get("compatible_styles", []),
        )
