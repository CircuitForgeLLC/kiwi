"""
Download recipe engine datasets from HuggingFace.

Usage:
    conda run -n cf python scripts/pipeline/download_datasets.py --data-dir data/pipeline

Downloads:
  - corbt/all-recipes               (no license) → data/pipeline/recipes_allrecipes.parquet  [2.1M recipes]
  - omid5/usda-fdc-foods-cleaned     (CC0)        → data/pipeline/usda_fdc_cleaned.parquet
  - jacktol/usda-branded-food-data   (MIT)        → data/pipeline/usda_branded.parquet
  - lishuyang/recipepairs            (GPL-3.0 ⚠)  → data/pipeline/recipepairs.parquet  [derive only, don't ship]
"""
from __future__ import annotations
import argparse
from pathlib import Path
from datasets import load_dataset


DATASETS = [
    ("corbt/all-recipes",            "train", "recipes_allrecipes.parquet"),
    ("omid5/usda-fdc-foods-cleaned", "train", "usda_fdc_cleaned.parquet"),
    ("jacktol/usda-branded-food-data","train", "usda_branded.parquet"),
    ("lishuyang/recipepairs",         "train", "recipepairs.parquet"),
]


def download_all(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for hf_path, split, filename in DATASETS:
        out = data_dir / filename
        if out.exists():
            print(f"  skip {filename} (already exists)")
            continue
        print(f"  downloading {hf_path} ...")
        ds = load_dataset(hf_path, split=split)
        ds.to_parquet(str(out))
        print(f"  saved → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    download_all(args.data_dir)
