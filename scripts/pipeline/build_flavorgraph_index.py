"""
Import FlavorGraph compound->ingredient map into flavor_molecules table.

FlavorGraph GitHub: https://github.com/lamypark/FlavorGraph
Download: git clone https://github.com/lamypark/FlavorGraph /tmp/flavorgraph

Usage:
    conda run -n cf python scripts/pipeline/build_flavorgraph_index.py \
        --db data/kiwi.db \
        --flavorgraph-dir /tmp/flavorgraph/input
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd


def parse_ingredient_nodes(
    nodes_path: Path, edges_path: Path
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Parse FlavorGraph CSVs → (ingredient→compounds, compound→name)."""
    nodes = pd.read_csv(nodes_path, dtype=str).fillna("")
    edges = pd.read_csv(edges_path, dtype=str).fillna("")

    ingredient_ids: dict[str, str] = {}   # node_id -> ingredient_name
    compound_names: dict[str, str] = {}   # node_id -> compound_name

    for _, row in nodes.iterrows():
        nid = row["node_id"]
        name = row["name"].lower().replace("_", " ").strip()
        if row["node_type"] == "ingredient":
            ingredient_ids[nid] = name
        else:
            compound_names[nid] = name

    ingredient_compounds: dict[str, list[str]] = defaultdict(list)
    for _, row in edges.iterrows():
        src, tgt = row["id_1"], row["id_2"]
        if src in ingredient_ids:
            ingredient_compounds[ingredient_ids[src]].append(tgt)
        if tgt in ingredient_ids:
            ingredient_compounds[ingredient_ids[tgt]].append(src)

    return dict(ingredient_compounds), compound_names


def build(db_path: Path, flavorgraph_dir: Path) -> None:
    nodes_path = flavorgraph_dir / "nodes_191120.csv"
    edges_path = flavorgraph_dir / "edges_191120.csv"

    ingredient_map, compound_names = parse_ingredient_nodes(nodes_path, edges_path)

    compound_ingredients: dict[str, list[str]] = defaultdict(list)
    for ingredient, compounds in ingredient_map.items():
        for cid in compounds:
            compound_ingredients[cid].append(ingredient)

    conn = sqlite3.connect(db_path)
    try:
        for ingredient, compounds in ingredient_map.items():
            conn.execute(
                "UPDATE ingredient_profiles SET flavor_molecule_ids = ? WHERE name = ?",
                (json.dumps(compounds), ingredient),
            )

        for cid, ingredients in compound_ingredients.items():
            conn.execute(
                "INSERT OR IGNORE INTO flavor_molecules (compound_id, compound_name, ingredient_names)"
                " VALUES (?, ?, ?)",
                (cid, compound_names.get(cid, cid), json.dumps(ingredients)),
            )

        conn.commit()
    finally:
        conn.close()

    print(f"Indexed {len(ingredient_map)} ingredients, {len(compound_ingredients)} compounds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",               required=True, type=Path)
    parser.add_argument("--flavorgraph-dir",  required=True, type=Path)
    args = parser.parse_args()
    build(args.db, args.flavorgraph_dir)
