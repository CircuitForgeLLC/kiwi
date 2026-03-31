"""
Import FlavorGraph compound->ingredient map into flavor_molecules table.

FlavorGraph GitHub: https://github.com/lamypark/FlavorGraph
Download: git clone https://github.com/lamypark/FlavorGraph /tmp/flavorgraph

Usage:
    conda run -n job-seeker python scripts/pipeline/build_flavorgraph_index.py \
        --db /path/to/kiwi.db \
        --graph-json /tmp/flavorgraph/data/graph.json
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path


def parse_ingredient_nodes(graph: dict) -> dict[str, list[str]]:
    """Return {ingredient_name: [compound_id, ...]} from a FlavorGraph JSON."""
    ingredient_compounds: dict[str, list[str]] = defaultdict(list)
    ingredient_ids: dict[str, str] = {}   # node_id -> ingredient_name

    for node in graph.get("nodes", []):
        if node.get("type") == "ingredient":
            ingredient_ids[node["id"]] = node["name"].lower()

    for link in graph.get("links", []):
        src, tgt = link.get("source", ""), link.get("target", "")
        if src in ingredient_ids:
            ingredient_compounds[ingredient_ids[src]].append(tgt)
        if tgt in ingredient_ids:
            ingredient_compounds[ingredient_ids[tgt]].append(src)

    return dict(ingredient_compounds)


def build(db_path: Path, graph_json_path: Path) -> None:
    graph = json.loads(graph_json_path.read_text())
    ingredient_map = parse_ingredient_nodes(graph)

    compound_ingredients: dict[str, list[str]] = defaultdict(list)
    compound_names: dict[str, str] = {}

    for node in graph.get("nodes", []):
        if node.get("type") == "compound":
            compound_names[node["id"]] = node["name"]

    for ingredient, compounds in ingredient_map.items():
        for cid in compounds:
            compound_ingredients[cid].append(ingredient)

    conn = sqlite3.connect(db_path)

    for ingredient, compounds in ingredient_map.items():
        conn.execute("""
            UPDATE ingredient_profiles
            SET flavor_molecule_ids = ?
            WHERE name = ?
        """, (json.dumps(compounds), ingredient))

    for cid, ingredients in compound_ingredients.items():
        conn.execute("""
            INSERT OR IGNORE INTO flavor_molecules (compound_id, compound_name, ingredient_names)
            VALUES (?, ?, ?)
        """, (cid, compound_names.get(cid, cid), json.dumps(ingredients)))

    conn.commit()
    conn.close()
    print(f"Indexed {len(ingredient_map)} ingredients, {len(compound_ingredients)} compounds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",         required=True, type=Path)
    parser.add_argument("--graph-json", required=True, type=Path)
    args = parser.parse_args()
    build(args.db, args.graph_json)
