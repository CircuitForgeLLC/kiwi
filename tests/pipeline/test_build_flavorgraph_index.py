def test_parse_flavorgraph_node():
    from scripts.pipeline.build_flavorgraph_index import parse_ingredient_nodes
    sample = {
        "nodes": [
            {"id": "I_beef", "type": "ingredient", "name": "beef"},
            {"id": "C_pyrazine", "type": "compound", "name": "pyrazine"},
            {"id": "I_mushroom", "type": "ingredient", "name": "mushroom"},
        ],
        "links": [
            {"source": "I_beef",    "target": "C_pyrazine"},
            {"source": "I_mushroom","target": "C_pyrazine"},
        ]
    }
    result = parse_ingredient_nodes(sample)
    assert "beef" in result
    assert "C_pyrazine" in result["beef"]
    assert "mushroom" in result
    assert "C_pyrazine" in result["mushroom"]
