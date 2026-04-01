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
import os
import shutil
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import hf_hub_download


# Standard HuggingFace datasets: (hf_path, split, output_filename)
HF_DATASETS = [
    ("corbt/all-recipes",             "train", "recipes_allrecipes.parquet"),
    ("omid5/usda-fdc-foods-cleaned",  "train", "usda_fdc_cleaned.parquet"),
    ("jacktol/usda-branded-food-data","train", "usda_branded.parquet"),
]

# Datasets that expose raw parquet files directly (no HF dataset builder)
HF_PARQUET_FILES = [
    # (repo_id, repo_filename, output_filename)
    # lishuyang/recipepairs: GPL-3.0 ⚠ — derive only, don't ship
    ("lishuyang/recipepairs", "pairs.parquet", "recipepairs.parquet"),
]


def download_all(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)

    for hf_path, split, filename in HF_DATASETS:
        out = data_dir / filename
        if out.exists():
            print(f"  skip {filename} (already exists)")
            continue
        print(f"  downloading {hf_path} ...")
        ds = load_dataset(hf_path, split=split)
        ds.to_parquet(str(out))
        print(f"  saved → {out}")

    for repo_id, repo_file, filename in HF_PARQUET_FILES:
        out = data_dir / filename
        if out.exists():
            print(f"  skip {filename} (already exists)")
            continue
        print(f"  downloading {repo_id}/{repo_file} ...")
        cached = hf_hub_download(repo_id=repo_id, filename=repo_file, repo_type="dataset")
        shutil.copy2(cached, out)
        print(f"  saved → {out}")


_DEFAULT_DATA_DIR = Path(
    os.environ.get("KIWI_PIPELINE_DATA_DIR", "data/pipeline")
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_DEFAULT_DATA_DIR,
        help="Directory for downloaded parquets (default: $KIWI_PIPELINE_DATA_DIR or data/pipeline)",
    )
    args = parser.parse_args()
    download_all(args.data_dir)
