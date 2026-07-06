"""Tests for active_min/passive_min fields on browse endpoint responses."""
from app.services.recipe.time_effort import parse_time_effort


class TestBrowseTimeEffortFields:
    """Unit-level: verify that browse result dicts gain active_min/passive_min."""

    def _make_recipe_row(self, recipe_id: int, directions: list[str]) -> dict:
        """Build a minimal recipe row as browse_recipes would return."""
        import json
        return {
            "id": recipe_id,
            "title": f"Recipe {recipe_id}",
            "category": "Italian",
            "match_pct": None,
            "directions": json.dumps(directions),  # stored as JSON string
        }

    def test_active_passive_attached_when_directions_present(self):
        """Simulate the enrichment logic that the endpoint applies."""
        import json
        row = self._make_recipe_row(1, ["Chop onion.", "Simmer for 20 minutes."])

        # Reproduce the enrichment logic from the endpoint:
        directions = row.get("directions") or []
        if isinstance(directions, str):
            try:
                directions = json.loads(directions)
            except Exception:
                directions = []
        if directions:
            profile = parse_time_effort(directions)
            row["active_min"] = profile.active_min
            row["passive_min"] = profile.passive_min
        else:
            row["active_min"] = None
            row["passive_min"] = None

        # "Chop onion." triggers the chop prep action (base 2.0 min) → active_min >= 1
        assert row["active_min"] > 0
        assert row["passive_min"] == 20

    def test_null_when_directions_empty(self):
        """active_min and passive_min are None when directions list is empty."""
        import json
        row = self._make_recipe_row(2, [])

        directions = row.get("directions") or []
        if isinstance(directions, str):
            try:
                directions = json.loads(directions)
            except Exception:
                directions = []
        if directions:
            profile = parse_time_effort(directions)
            row["active_min"] = profile.active_min
            row["passive_min"] = profile.passive_min
        else:
            row["active_min"] = None
            row["passive_min"] = None

        assert row["active_min"] is None
        assert row["passive_min"] is None

    def test_null_when_directions_missing_key(self):
        """active_min and passive_min are None when key is absent."""
        row = {"id": 3, "title": "Test", "category": "X", "match_pct": None}

        directions = row.get("directions") or []
        if isinstance(directions, str):
            try:
                import json
                directions = json.loads(directions)
            except Exception:
                directions = []
        if directions:
            profile = parse_time_effort(directions)
            row["active_min"] = profile.active_min
            row["passive_min"] = profile.passive_min
        else:
            row["active_min"] = None
            row["passive_min"] = None

        assert row["active_min"] is None
        assert row["passive_min"] is None


class TestDetailTimeEffortField:
    """Verify that the detail endpoint response gains a time_effort key."""

    def test_time_effort_field_structure(self):
        """Detail endpoint must return the full TimeEffortProfile shape."""
        from app.services.recipe.time_effort import parse_time_effort

        directions = [
            "Dice the onion.",
            "Sear chicken for 5 minutes.",
            "Simmer sauce for 20 minutes.",
        ]

        profile = parse_time_effort(directions)

        # Simulate what the endpoint serialises
        time_effort_dict = {
            "active_min": profile.active_min,
            "passive_min": profile.passive_min,
            "total_min": profile.total_min,
            "effort_label": profile.effort_label,
            "equipment": profile.equipment,
            "step_analyses": [
                {"is_passive": sa.is_passive, "detected_minutes": sa.detected_minutes}
                for sa in profile.step_analyses
            ],
        }

        # "Gather all ingredients." → active default (2 min); "Sear for 5 min" → 5 min
        assert time_effort_dict["active_min"] == 7
        assert time_effort_dict["passive_min"] == 20
        assert time_effort_dict["total_min"] == 27
        # 27 min total → moderate (21-45 min range)
        assert time_effort_dict["effort_label"] == "moderate"
        assert isinstance(time_effort_dict["equipment"], list)
        assert len(time_effort_dict["step_analyses"]) == 3
        assert time_effort_dict["step_analyses"][2]["is_passive"] is True

    def test_time_effort_none_when_no_directions(self):
        """time_effort should be None when recipe has empty directions."""
        from app.services.recipe.time_effort import parse_time_effort

        recipe_dict = {
            "id": 99,
            "title": "Empty",
            "directions": [],
        }

        directions = recipe_dict.get("directions") or []
        if directions:
            profile = parse_time_effort(directions)
            recipe_dict["time_effort"] = {
                "active_min": profile.active_min,
                "passive_min": profile.passive_min,
                "total_min": profile.total_min,
                "effort_label": profile.effort_label,
                "equipment": profile.equipment,
                "step_analyses": [
                    {"is_passive": sa.is_passive, "detected_minutes": sa.detected_minutes}
                    for sa in profile.step_analyses
                ],
            }
        else:
            recipe_dict["time_effort"] = None

        assert recipe_dict["time_effort"] is None
