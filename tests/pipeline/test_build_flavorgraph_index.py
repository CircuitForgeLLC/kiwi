import csv
import tempfile
from pathlib import Path


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_parse_flavorgraph_node():
    from scripts.pipeline.build_flavorgraph_index import parse_ingredient_nodes

    with tempfile.TemporaryDirectory() as tmp:
        nodes_path = Path(tmp) / "nodes.csv"
        edges_path = Path(tmp) / "edges.csv"

        _write_csv(nodes_path, [
            {"node_id": "1", "name": "beef",     "node_type": "ingredient"},
            {"node_id": "2", "name": "pyrazine",  "node_type": "compound"},
            {"node_id": "3", "name": "mushroom", "node_type": "ingredient"},
        ], ["node_id", "name", "node_type"])

        _write_csv(edges_path, [
            {"id_1": "1", "id_2": "2", "score": "0.8"},
            {"id_1": "3", "id_2": "2", "score": "0.7"},
        ], ["id_1", "id_2", "score"])

        ingredient_to_compounds, compound_names = parse_ingredient_nodes(nodes_path, edges_path)

        assert "beef" in ingredient_to_compounds
        assert "mushroom" in ingredient_to_compounds
        # compound node_id "2" maps to name "pyrazine"
        beef_compounds = ingredient_to_compounds["beef"]
        assert any(compound_names.get(c) == "pyrazine" for c in beef_compounds)
        mushroom_compounds = ingredient_to_compounds["mushroom"]
        assert any(compound_names.get(c) == "pyrazine" for c in mushroom_compounds)
