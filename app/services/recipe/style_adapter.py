"""
StyleAdapter — cuisine-mode overlay that biases element dimensions.
YAML templates in app/styles/.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_STYLES_DIR = Path(__file__).parents[2] / "styles"


@dataclass(frozen=True)
class StyleTemplate:
    style_id: str
    name: str
    aromatics: list[str]
    depth_sources: list[str]
    brightness_sources: list[str]
    method_bias: list[str]
    structure_forms: list[str]
    seasoning_bias: str
    finishing_fat: str


class StyleAdapter:
    def __init__(self, styles_dir: Path = _STYLES_DIR) -> None:
        self._styles: dict[str, StyleTemplate] = {}
        for yaml_path in sorted(styles_dir.glob("*.yaml")):
            try:
                template = self._load(yaml_path)
                self._styles[template.style_id] = template
            except (KeyError, yaml.YAMLError) as exc:
                raise ValueError(f"Failed to load style from {yaml_path}: {exc}") from exc

    def get(self, style_id: str) -> StyleTemplate | None:
        return self._styles.get(style_id)

    def list_all(self) -> list[StyleTemplate]:
        return list(self._styles.values())

    def bias_aroma_selection(self, style_id: str, pantry_items: list[str]) -> list[str]:
        """Return pantry items that match the style's preferred aromatics.
        Falls back to all pantry items if no match found."""
        template = self._styles.get(style_id)
        if not template:
            return pantry_items
        matched = [
            item for item in pantry_items
            if any(
                aroma.lower() in item.lower() or item.lower() in aroma.lower()
                for aroma in template.aromatics
            )
        ]
        return matched if matched else pantry_items

    def apply(self, style_id: str, pantry_items: list[str]) -> dict:
        """Return style-biased ingredient guidance for each element dimension."""
        template = self._styles.get(style_id)
        if not template:
            return {}
        return {
            "aroma_candidates":       self.bias_aroma_selection(style_id, pantry_items),
            "depth_suggestions":      template.depth_sources,
            "brightness_suggestions": template.brightness_sources,
            "method_bias":            template.method_bias,
            "structure_forms":        template.structure_forms,
            "seasoning_bias":         template.seasoning_bias,
            "finishing_fat":          template.finishing_fat,
        }

    def _load(self, path: Path) -> StyleTemplate:
        data = yaml.safe_load(path.read_text())
        return StyleTemplate(
            style_id=data["style_id"],
            name=data["name"],
            aromatics=data.get("aromatics", []),
            depth_sources=data.get("depth_sources", []),
            brightness_sources=data.get("brightness_sources", []),
            method_bias=data.get("method_bias", []),
            structure_forms=data.get("structure_forms", []),
            seasoning_bias=data.get("seasoning_bias", ""),
            finishing_fat=data.get("finishing_fat", ""),
        )
