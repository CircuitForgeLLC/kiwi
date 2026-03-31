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
    aromatics: tuple[str, ...]
    depth_sources: tuple[str, ...]
    brightness_sources: tuple[str, ...]
    method_bias: dict[str, float]
    structure_forms: tuple[str, ...]
    seasoning_bias: str
    finishing_fat_str: str

    def bias_aroma_selection(self, pantry_items: list[str]) -> list[str]:
        """Return aromatics present in pantry (bidirectional substring match)."""
        result = []
        for aroma in self.aromatics:
            for item in pantry_items:
                if aroma.lower() in item.lower() or item.lower() in aroma.lower():
                    result.append(aroma)
                    break
        return result

    def preferred_depth_sources(self, pantry_items: list[str]) -> list[str]:
        """Return depth_sources present in pantry."""
        result = []
        for src in self.depth_sources:
            for item in pantry_items:
                if src.lower() in item.lower() or item.lower() in src.lower():
                    result.append(src)
                    break
        return result

    def preferred_structure_forms(self, pantry_items: list[str]) -> list[str]:
        """Return structure_forms present in pantry."""
        result = []
        for form in self.structure_forms:
            for item in pantry_items:
                if form.lower() in item.lower() or item.lower() in form.lower():
                    result.append(form)
                    break
        return result

    def method_weights(self) -> dict[str, float]:
        """Return method bias weights."""
        return dict(self.method_bias)

    def seasoning_vector(self) -> str:
        """Return seasoning bias."""
        return self.seasoning_bias

    def finishing_fat(self) -> str:
        """Return finishing fat."""
        return self.finishing_fat_str


class StyleAdapter:
    def __init__(self, styles_dir: Path = _STYLES_DIR) -> None:
        self._styles: dict[str, StyleTemplate] = {}
        for yaml_path in sorted(styles_dir.glob("*.yaml")):
            try:
                template = self._load(yaml_path)
                self._styles[template.style_id] = template
            except (KeyError, yaml.YAMLError, TypeError) as exc:
                raise ValueError(f"Failed to load style from {yaml_path}: {exc}") from exc

    @property
    def styles(self) -> dict[str, StyleTemplate]:
        return self._styles

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
            "depth_suggestions":      list(template.depth_sources),
            "brightness_suggestions": list(template.brightness_sources),
            "method_bias":            template.method_bias,
            "structure_forms":        list(template.structure_forms),
            "seasoning_bias":         template.seasoning_bias,
            "finishing_fat":          template.finishing_fat_str,
        }

    def _load(self, path: Path) -> StyleTemplate:
        data = yaml.safe_load(path.read_text())
        return StyleTemplate(
            style_id=data["style_id"],
            name=data["name"],
            aromatics=tuple(data.get("aromatics", [])),
            depth_sources=tuple(data.get("depth_sources", [])),
            brightness_sources=tuple(data.get("brightness_sources", [])),
            method_bias=dict(data.get("method_bias", {})),
            structure_forms=tuple(data.get("structure_forms", [])),
            seasoning_bias=data.get("seasoning_bias", ""),
            finishing_fat_str=data.get("finishing_fat", ""),
        )
