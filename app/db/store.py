"""
SQLite data store for Kiwi.
Uses circuitforge-core for connection management and migrations.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from circuitforge_core.db.base import get_connection
from circuitforge_core.db.migrations import run_migrations

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Module-level cache for recipe counts by keyword set.
# The recipe corpus is static at runtime — counts are computed once per
# (db_path, keyword_set) and reused for all subsequent requests.
# Key: (db_path_str, sorted_keywords_tuple) → int
_COUNT_CACHE: dict[tuple[str, ...], int] = {}


class Store:
    def __init__(self, db_path: Path, key: str = "") -> None:
        self._db_path = str(db_path)
        self.conn: sqlite3.Connection = get_connection(db_path, key)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        run_migrations(self.conn, MIGRATIONS_DIR)

    def close(self) -> None:
        self.conn.close()

    # ── helpers ───────────────────────────────────────────────────────────

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        # Deserialise any TEXT columns that contain JSON
        for key in ("metadata", "nutrition_data", "source_data", "items",
                    "metrics", "improvement_suggestions", "confidence_scores",
                    "warnings",
                    # recipe columns
                    "ingredients", "ingredient_names", "directions",
                    "keywords", "element_coverage",
                    # saved recipe columns
                    "style_tags"):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    def _fetch_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        self.conn.row_factory = sqlite3.Row
        row = self.conn.execute(sql, params).fetchone()
        return self._row_to_dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _dump(self, value: Any) -> str:
        """Serialise a Python object to a JSON string for storage."""
        return json.dumps(value)

    # ── receipts ──────────────────────────────────────────────────────────

    def _insert_returning(self, sql: str, params: tuple = ()) -> dict[str, Any]:
        """Execute an INSERT ... RETURNING * and return the new row as a dict.
        Fetches the row BEFORE committing — SQLite requires the cursor to be
        fully consumed before the transaction is committed."""
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.execute(sql, params)
        row = self._row_to_dict(cur.fetchone())
        self.conn.commit()
        return row

    def create_receipt(self, filename: str, original_path: str) -> dict[str, Any]:
        return self._insert_returning(
            "INSERT INTO receipts (filename, original_path) VALUES (?, ?) RETURNING *",
            (filename, original_path),
        )

    def get_receipt(self, receipt_id: int) -> dict[str, Any] | None:
        return self._fetch_one("SELECT * FROM receipts WHERE id = ?", (receipt_id,))

    def list_receipts(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM receipts ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def update_receipt_status(self, receipt_id: int, status: str,
                               error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE receipts SET status = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
            (status, error, receipt_id),
        )
        self.conn.commit()

    def update_receipt_metadata(self, receipt_id: int, metadata: dict) -> None:
        self.conn.execute(
            "UPDATE receipts SET metadata = ?, updated_at = datetime('now') WHERE id = ?",
            (self._dump(metadata), receipt_id),
        )
        self.conn.commit()

    # ── quality assessments ───────────────────────────────────────────────

    def upsert_quality_assessment(self, receipt_id: int, overall_score: float,
                                   is_acceptable: bool, metrics: dict,
                                   suggestions: list) -> dict[str, Any]:
        self.conn.execute(
            """INSERT INTO quality_assessments
                   (receipt_id, overall_score, is_acceptable, metrics, improvement_suggestions)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (receipt_id) DO UPDATE SET
                   overall_score = excluded.overall_score,
                   is_acceptable = excluded.is_acceptable,
                   metrics = excluded.metrics,
                   improvement_suggestions = excluded.improvement_suggestions""",
            (receipt_id, overall_score, int(is_acceptable),
             self._dump(metrics), self._dump(suggestions)),
        )
        self.conn.commit()
        return self._fetch_one(
            "SELECT * FROM quality_assessments WHERE receipt_id = ?", (receipt_id,)
        )

    # ── products ──────────────────────────────────────────────────────────

    def get_or_create_product(self, name: str, barcode: str | None = None,
                               **kwargs) -> tuple[dict[str, Any], bool]:
        """Returns (product, created). Looks up by barcode first, then name."""
        if barcode:
            existing = self._fetch_one(
                "SELECT * FROM products WHERE barcode = ?", (barcode,)
            )
            if existing:
                return existing, False

        existing = self._fetch_one("SELECT * FROM products WHERE name = ?", (name,))
        if existing:
            return existing, False

        row = self._insert_returning(
            """INSERT INTO products (name, barcode, brand, category, description,
                   image_url, nutrition_data, source, source_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *""",
            (
                name, barcode,
                kwargs.get("brand"), kwargs.get("category"),
                kwargs.get("description"), kwargs.get("image_url"),
                self._dump(kwargs.get("nutrition_data", {})),
                kwargs.get("source", "manual"),
                self._dump(kwargs.get("source_data", {})),
            ),
        )
        return row, True

    def get_product(self, product_id: int) -> dict[str, Any] | None:
        return self._fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))

    def list_products(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM products ORDER BY name")

    # ── inventory ─────────────────────────────────────────────────────────

    def add_inventory_item(self, product_id: int, location: str,
                           quantity: float = 1.0, unit: str = "count",
                           **kwargs) -> dict[str, Any]:
        return self._insert_returning(
            """INSERT INTO inventory_items
                   (product_id, receipt_id, quantity, unit, location, sublocation,
                    purchase_date, expiration_date, notes, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *""",
            (
                product_id, kwargs.get("receipt_id"),
                quantity, unit, location, kwargs.get("sublocation"),
                kwargs.get("purchase_date"), kwargs.get("expiration_date"),
                kwargs.get("notes"), kwargs.get("source", "manual"),
            ),
        )

    def get_inventory_item(self, item_id: int) -> dict[str, Any] | None:
        return self._fetch_one(
            """SELECT i.*, p.name as product_name, p.barcode, p.category
               FROM inventory_items i
               JOIN products p ON p.id = i.product_id
               WHERE i.id = ?""",
            (item_id,),
        )

    def list_inventory(self, location: str | None = None,
                       status: str = "available") -> list[dict[str, Any]]:
        if location:
            return self._fetch_all(
                """SELECT i.*, p.name as product_name, p.barcode, p.category
                   FROM inventory_items i
                   JOIN products p ON p.id = i.product_id
                   WHERE i.status = ? AND i.location = ?
                   ORDER BY i.expiration_date ASC NULLS LAST""",
                (status, location),
            )
        return self._fetch_all(
            """SELECT i.*, p.name as product_name, p.barcode, p.category
               FROM inventory_items i
               JOIN products p ON p.id = i.product_id
               WHERE i.status = ?
               ORDER BY i.expiration_date ASC NULLS LAST""",
            (status,),
        )

    def update_inventory_item(self, item_id: int, **kwargs) -> dict[str, Any] | None:
        allowed = {"quantity", "unit", "location", "sublocation",
                   "expiration_date", "status", "notes", "consumed_at"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_inventory_item(item_id)
        sets = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [item_id]
        self.conn.execute(
            f"UPDATE inventory_items SET {sets}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        self.conn.commit()
        return self.get_inventory_item(item_id)

    def expiring_soon(self, days: int = 7) -> list[dict[str, Any]]:
        return self._fetch_all(
            """SELECT i.*, p.name as product_name, p.category
               FROM inventory_items i
               JOIN products p ON p.id = i.product_id
               WHERE i.status = 'available'
                 AND i.expiration_date IS NOT NULL
                 AND date(i.expiration_date) <= date('now', ? || ' days')
               ORDER BY i.expiration_date ASC""",
            (str(days),),
        )

    def recalculate_expiry(
        self,
        tier: str = "local",
        has_byok: bool = False,
    ) -> tuple[int, int]:
        """Re-run the expiration predictor over all available inventory items.

        Uses each item's existing purchase_date (falls back to today if NULL)
        and its current location. Skips items that have an explicit
        expiration_date from a source other than auto-prediction (i.e. items
        whose expiry was found on a receipt or entered by the user) cannot be
        distinguished — all available items are recalculated.

        Returns (updated_count, skipped_count).
        """
        from datetime import date
        from app.services.expiration_predictor import ExpirationPredictor

        predictor = ExpirationPredictor()
        rows = self._fetch_all(
            """SELECT i.id, i.location, i.purchase_date,
                      p.name AS product_name, p.category AS product_category
               FROM inventory_items i
               JOIN products p ON p.id = i.product_id
               WHERE i.status = 'available'""",
            (),
        )

        updated = skipped = 0
        for row in rows:
            cat = predictor.get_category_from_product(
                row["product_name"] or "",
                product_category=row.get("product_category"),
                location=row.get("location"),
            )
            purchase_date_raw = row.get("purchase_date")
            try:
                purchase_date = (
                    date.fromisoformat(purchase_date_raw)
                    if purchase_date_raw
                    else date.today()
                )
            except (ValueError, TypeError):
                purchase_date = date.today()

            exp = predictor.predict_expiration(
                cat,
                row["location"] or "pantry",
                purchase_date=purchase_date,
                product_name=row["product_name"],
                tier=tier,
                has_byok=has_byok,
            )
            if exp is None:
                skipped += 1
                continue

            self.conn.execute(
                "UPDATE inventory_items SET expiration_date = ?, updated_at = datetime('now') WHERE id = ?",
                (str(exp), row["id"]),
            )
            updated += 1

        self.conn.commit()
        return updated, skipped

    # ── receipt_data ──────────────────────────────────────────────────────

    def upsert_receipt_data(self, receipt_id: int, data: dict) -> dict[str, Any]:
        fields = [
            "merchant_name", "merchant_address", "merchant_phone", "merchant_email",
            "merchant_website", "merchant_tax_id", "transaction_date", "transaction_time",
            "receipt_number", "register_number", "cashier_name", "transaction_id",
            "items", "subtotal", "tax", "discount", "tip", "total",
            "payment_method", "amount_paid", "change_given",
            "raw_text", "confidence_scores", "warnings", "processing_time",
        ]
        json_fields = {"items", "confidence_scores", "warnings"}
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        values = [
            self._dump(data.get(f)) if f in json_fields and data.get(f) is not None
            else data.get(f)
            for f in fields
        ]
        self.conn.execute(
            f"""INSERT INTO receipt_data (receipt_id, {cols})
                VALUES (?, {placeholders})
                ON CONFLICT (receipt_id) DO UPDATE SET
                {', '.join(f'{f} = excluded.{f}' for f in fields)},
                updated_at = datetime('now')""",
            [receipt_id] + values,
        )
        self.conn.commit()
        return self._fetch_one(
            "SELECT * FROM receipt_data WHERE receipt_id = ?", (receipt_id,)
        )

    # ── recipes ───────────────────────────────────────────────────────────

    def _fts_ready(self) -> bool:
        """Return True if the recipes_fts virtual table exists."""
        row = self._fetch_one(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='recipes_fts'"
        )
        return row is not None

    # Words that carry no recipe-ingredient signal and should be filtered
    # out when tokenising multi-word product names for FTS expansion.
    _FTS_TOKEN_STOPWORDS: frozenset[str] = frozenset({
        # Common English stopwords
        "a", "an", "the", "of", "in", "for", "with", "and", "or", "to",
        "from", "at", "by", "as", "on", "into",
        # Brand / marketing words that appear in product names
        "lean", "cuisine", "healthy", "choice", "stouffer", "original",
        "classic", "deluxe", "homestyle", "family", "style", "grade",
        "premium", "select", "natural", "organic", "fresh", "lite",
        "ready", "quick", "easy", "instant", "microwave", "frozen",
        "brand", "size", "large", "small", "medium", "extra",
        # Plant-based / alt-meat brand names
        "daring", "gardein", "morningstar", "lightlife", "tofurky",
        "quorn", "omni", "nuggs", "simulate", "simulate",
        # Preparation states — "cut up chicken" is still chicken
        "cut", "diced", "sliced", "chopped", "minced", "shredded",
        "cooked", "raw", "whole", "boneless", "skinless", "trimmed",
        "pre", "prepared", "marinated", "seasoned", "breaded", "battered",
        "grilled", "roasted", "smoked", "canned", "dried", "dehydrated",
        "pieces", "piece", "strips", "strip", "chunks", "chunk",
        "fillets", "fillet", "cutlets", "cutlet", "tenders", "nuggets",
        # Units / packaging
        "oz", "lb", "lbs", "pkg", "pack", "box", "can", "bag", "jar",
    })

    # Maps substrings found in product-label names to canonical recipe-corpus
    # ingredient terms.  Checked as substring matches against the lower-cased
    # full product name, then against each individual token.
    _FTS_SYNONYMS: dict[str, str] = {
        # Ground / minced beef
        "burger patt":  "hamburger",
        "beef patt":    "hamburger",
        "ground beef":  "hamburger",
        "ground chuck": "hamburger",
        "ground round": "hamburger",
        "mince":        "hamburger",
        "veggie burger":   "hamburger",
        "beyond burger":   "hamburger",
        "impossible burger": "hamburger",
        "plant burger":    "hamburger",
        "chicken patt":    "hamburger",  # FTS match only — recipe scoring still works
        # Sausages
        "kielbasa":     "sausage",
        "bratwurst":    "sausage",
        "brat ":        "sausage",
        "frankfurter":  "hotdog",
        "wiener":       "hotdog",
        # Chicken cuts + plant-based chicken → generic chicken for broader matching
        "chicken breast":   "chicken",
        "chicken thigh":    "chicken",
        "chicken drumstick": "chicken",
        "chicken wing":     "chicken",
        "rotisserie chicken": "chicken",
        "chicken tender":   "chicken",
        "chicken strip":    "chicken",
        "chicken piece":    "chicken",
        "fake chicken":     "chicken",
        "plant chicken":    "chicken",
        "vegan chicken":    "chicken",
        "daring":           "chicken",   # Daring Foods brand
        "gardein chick":    "chicken",
        "quorn chick":      "chicken",
        "chick'n":          "chicken",
        "chikn":            "chicken",
        "not-chicken":      "chicken",
        "no-chicken":       "chicken",
        # Plant-based beef subs — map to broad "beef" not "hamburger"
        # (texture varies: strips ≠ ground; let corpus handle the specific form)
        "not-beef":         "beef",
        "no-beef":          "beef",
        "plant beef":       "beef",
        "vegan beef":       "beef",
        # Plant-based pork subs
        "not-pork":         "pork",
        "no-pork":          "pork",
        "plant pork":       "pork",
        "vegan pork":       "pork",
        "omnipork":         "pork",
        "omni pork":        "pork",
        # Generic alt-meat catch-alls → broad "beef" (safer than hamburger)
        "fake meat":        "beef",
        "plant meat":       "beef",
        "vegan meat":       "beef",
        "meat-free":        "beef",
        "meatless":         "beef",
        # Pork cuts
        "pork chop":    "pork",
        "pork loin":    "pork",
        "pork tenderloin": "pork",
        # Tomato-based sauces
        "marinara":     "tomato sauce",
        "pasta sauce":  "tomato sauce",
        "spaghetti sauce": "tomato sauce",
        "pizza sauce":  "tomato sauce",
        # Pasta shapes — map to generic "pasta" so FTS finds any pasta recipe
        "macaroni":     "pasta",
        "noodles":      "pasta",
        "spaghetti":    "pasta",
        "penne":        "pasta",
        "fettuccine":   "pasta",
        "rigatoni":     "pasta",
        "linguine":     "pasta",
        "rotini":       "pasta",
        "farfalle":     "pasta",
        # Cheese variants → "cheese" for broad matching
        "shredded cheese":  "cheese",
        "sliced cheese":    "cheese",
        "american cheese":  "cheese",
        "cheddar":      "cheese",
        "mozzarella":   "cheese",
        # Cream variants
        "heavy cream":  "cream",
        "whipping cream": "cream",
        "half and half": "cream",
        # Buns / rolls
        "burger bun":   "buns",
        "hamburger bun": "buns",
        "hot dog bun":  "buns",
        "bread roll":   "buns",
        "dinner roll":  "buns",
        # Tortillas / wraps
        "flour tortilla": "tortillas",
        "corn tortilla":  "tortillas",
        "tortilla wrap":  "tortillas",
        "soft taco shell": "tortillas",
        "taco shell":     "taco shells",
        "pita bread":     "pita",
        "flatbread":      "flatbread",
        # Canned beans
        "black bean":     "beans",
        "pinto bean":     "beans",
        "kidney bean":    "beans",
        "refried bean":   "beans",
        "chickpea":       "beans",
        "garbanzo":       "beans",
        # Rice variants
        "white rice":     "rice",
        "brown rice":     "rice",
        "jasmine rice":   "rice",
        "basmati rice":   "rice",
        "instant rice":   "rice",
        "microwavable rice": "rice",
        # Salsa / hot sauce
        "hot sauce":      "salsa",
        "taco sauce":     "salsa",
        "enchilada sauce": "salsa",
        # Sour cream substitute
        "greek yogurt":   "sour cream",
        # Prepackaged meals
        "lean cuisine":   "casserole",
        "stouffer":       "casserole",
        "healthy choice": "casserole",
        "marie callender": "casserole",
    }

    @staticmethod
    def _normalize_for_fts(name: str) -> list[str]:
        """Expand one pantry item to all FTS search terms it should contribute.

        Returns the original name plus:
        - Any synonym-map canonical terms (handles product-label → corpus name)
        - Individual significant tokens from multi-word product names
          (handles packaged meals like "Lean Cuisine Chicken Alfredo" → also
           searches for "chicken" and "alfredo" independently)
        """
        lower = name.lower().strip()
        if not lower:
            return []

        terms: list[str] = [lower]

        # Substring synonym check on full name
        for pattern, canonical in Store._FTS_SYNONYMS.items():
            if pattern in lower:
                terms.append(canonical)

        # For multi-word product names, also add individual significant tokens
        if " " in lower:
            for token in lower.split():
                if len(token) <= 3 or token in Store._FTS_TOKEN_STOPWORDS:
                    continue
                if token not in terms:
                    terms.append(token)
                # Synonym-expand individual tokens too
                if token in Store._FTS_SYNONYMS:
                    canonical = Store._FTS_SYNONYMS[token]
                    if canonical not in terms:
                        terms.append(canonical)

        return terms

    @staticmethod
    def _build_fts_query(ingredient_names: list[str]) -> str:
        """Build an FTS5 MATCH expression ORing all ingredient terms.

        Each pantry item is expanded via _normalize_for_fts so that
        product-label names (e.g. "burger patties") also search for their
        recipe-corpus equivalents (e.g. "hamburger"), and multi-word packaged
        product names contribute their individual ingredient tokens.
        """
        parts: list[str] = []
        seen: set[str] = set()
        for name in ingredient_names:
            for term in Store._normalize_for_fts(name):
                # Strip characters that break FTS5 query syntax
                clean = term.replace('"', "").replace("'", "")
                if not clean or clean in seen:
                    continue
                seen.add(clean)
                parts.append(f'"{clean}"')
        return " OR ".join(parts)

    def search_recipes_by_ingredients(
        self,
        ingredient_names: list[str],
        limit: int = 20,
        category: str | None = None,
        max_calories: float | None = None,
        max_sugar_g: float | None = None,
        max_carbs_g: float | None = None,
        max_sodium_mg: float | None = None,
        excluded_ids: list[int] | None = None,
        exclude_generic: bool = False,
    ) -> list[dict]:
        """Find recipes containing any of the given ingredient names.
        Scores by match count and returns highest-scoring first.

        Uses FTS5 index (migration 015) when available — O(log N) per query.
        Falls back to LIKE scans on older databases.

        Nutrition filters use NULL-passthrough: rows without nutrition data
        always pass (they may be estimated or absent entirely).

        exclude_generic: when True, skips recipes marked is_generic=1.
        Pass True for Level 1 ("Use What I Have") to suppress catch-all recipes.
        """
        if not ingredient_names:
            return []

        extra_clauses: list[str] = []
        extra_params: list = []
        if category:
            extra_clauses.append("r.category = ?")
            extra_params.append(category)
        if max_calories is not None:
            extra_clauses.append("(r.calories IS NULL OR r.calories <= ?)")
            extra_params.append(max_calories)
        if max_sugar_g is not None:
            extra_clauses.append("(r.sugar_g IS NULL OR r.sugar_g <= ?)")
            extra_params.append(max_sugar_g)
        if max_carbs_g is not None:
            extra_clauses.append("(r.carbs_g IS NULL OR r.carbs_g <= ?)")
            extra_params.append(max_carbs_g)
        if max_sodium_mg is not None:
            extra_clauses.append("(r.sodium_mg IS NULL OR r.sodium_mg <= ?)")
            extra_params.append(max_sodium_mg)
        if excluded_ids:
            placeholders = ",".join("?" * len(excluded_ids))
            extra_clauses.append(f"r.id NOT IN ({placeholders})")
            extra_params.extend(excluded_ids)
        if exclude_generic:
            extra_clauses.append("r.is_generic = 0")
        where_extra = (" AND " + " AND ".join(extra_clauses)) if extra_clauses else ""

        if self._fts_ready():
            return self._search_recipes_fts(
                ingredient_names, limit, where_extra, extra_params
            )
        return self._search_recipes_like(
            ingredient_names, limit, where_extra, extra_params
        )

    def _search_recipes_fts(
        self,
        ingredient_names: list[str],
        limit: int,
        where_extra: str,
        extra_params: list,
    ) -> list[dict]:
        """FTS5-backed ingredient search. Candidates fetched via inverted index;
        match_count computed in Python over the small candidate set."""
        fts_query = self._build_fts_query(ingredient_names)
        if not fts_query:
            return []

        # Pull up to 10× limit candidates so ranking has enough headroom.
        sql = f"""
            SELECT r.*
            FROM recipes_fts
            JOIN recipes r ON r.id = recipes_fts.rowid
            WHERE recipes_fts MATCH ?
            {where_extra}
            LIMIT ?
        """
        rows = self._fetch_all(sql, (fts_query, *extra_params, limit * 10))

        pantry_set = {n.lower().strip() for n in ingredient_names}
        scored: list[dict] = []
        for row in rows:
            raw = row.get("ingredient_names") or []
            names: list[str] = raw if isinstance(raw, list) else json.loads(raw or "[]")
            match_count = sum(1 for n in names if n.lower() in pantry_set)
            scored.append({**row, "match_count": match_count})

        scored.sort(key=lambda r: (-r["match_count"], r["id"]))
        return scored[:limit]

    def _search_recipes_like(
        self,
        ingredient_names: list[str],
        limit: int,
        where_extra: str,
        extra_params: list,
    ) -> list[dict]:
        """Legacy LIKE-based ingredient search (O(N×rows) — slow on large corpora)."""
        like_params = [f'%"{n}"%' for n in ingredient_names]
        like_clauses = " OR ".join(
            "r.ingredient_names LIKE ?" for _ in ingredient_names
        )
        match_score = " + ".join(
            "CASE WHEN r.ingredient_names LIKE ? THEN 1 ELSE 0 END"
            for _ in ingredient_names
        )
        sql = f"""
            SELECT r.*, ({match_score}) AS match_count
            FROM recipes r
            WHERE ({like_clauses})
            {where_extra}
            ORDER BY match_count DESC, r.id ASC
            LIMIT ?
        """
        all_params = like_params + like_params + extra_params + [limit]
        return self._fetch_all(sql, tuple(all_params))

    def get_recipe(self, recipe_id: int) -> dict | None:
        return self._fetch_one("SELECT * FROM recipes WHERE id = ?", (recipe_id,))

    def get_element_profiles(self, names: list[str]) -> dict[str, list[str]]:
        """Return {ingredient_name: [element_tag, ...]} for the given names.

        Only names present in ingredient_profiles are returned -- missing names
        are silently omitted so callers can distinguish "no profile" from "empty
        elements list".
        """
        if not names:
            return {}
        placeholders = ",".join("?" * len(names))
        rows = self._fetch_all(
            f"SELECT name, elements FROM ingredient_profiles WHERE name IN ({placeholders})",
            tuple(names),
        )
        result: dict[str, list[str]] = {}
        for row in rows:
            try:
                elements = json.loads(row["elements"]) if row["elements"] else []
            except (json.JSONDecodeError, TypeError):
                elements = []
            result[row["name"]] = elements
        return result

    # ── rate limits ───────────────────────────────────────────────────────

    def check_and_increment_rate_limit(
        self, feature: str, daily_max: int
    ) -> tuple[bool, int]:
        """Check daily counter for feature; only increment if under the limit.
        Returns (allowed, current_count). Rejected calls do not consume quota."""
        from datetime import date
        today = date.today().isoformat()
        row = self._fetch_one(
            "SELECT count FROM rate_limits WHERE feature = ? AND window_date = ?",
            (feature, today),
        )
        current = row["count"] if row else 0
        if current >= daily_max:
            return (False, current)
        self.conn.execute("""
            INSERT INTO rate_limits (feature, window_date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(feature, window_date) DO UPDATE SET count = count + 1
        """, (feature, today))
        self.conn.commit()
        return (True, current + 1)

    # ── user settings ────────────────────────────────────────────────────

    def get_setting(self, key: str) -> str | None:
        """Return the value for a settings key, or None if not set."""
        row = self._fetch_one(
            "SELECT value FROM user_settings WHERE key = ?", (key,)
        )
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        """Upsert a settings key-value pair."""
        self.conn.execute(
            "INSERT INTO user_settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ── substitution feedback ─────────────────────────────────────────────

    def log_substitution_feedback(
        self,
        original: str,
        substitute: str,
        constraint: str | None,
        compensation_used: list[str],
        approved: bool,
        opted_in: bool,
    ) -> None:
        self.conn.execute("""
            INSERT INTO substitution_feedback
              (original_name, substitute_name, constraint_label,
               compensation_used, approved, opted_in)
            VALUES (?,?,?,?,?,?)
        """, (
            original, substitute, constraint,
            self._dump(compensation_used),
            int(approved), int(opted_in),
        ))
        self.conn.commit()

    # ── saved recipes ─────────────────────────────────────────────────────

    def save_recipe(
        self,
        recipe_id: int,
        notes: str | None,
        rating: int | None,
    ) -> dict:
        return self._insert_returning(
            """
            INSERT INTO saved_recipes (recipe_id, notes, rating)
            VALUES (?, ?, ?)
            ON CONFLICT(recipe_id) DO UPDATE SET
                notes  = excluded.notes,
                rating = excluded.rating
            RETURNING *
            """,
            (recipe_id, notes, rating),
        )

    def unsave_recipe(self, recipe_id: int) -> None:
        self.conn.execute(
            "DELETE FROM saved_recipes WHERE recipe_id = ?", (recipe_id,)
        )
        self.conn.commit()

    def is_recipe_saved(self, recipe_id: int) -> bool:
        row = self._fetch_one(
            "SELECT id FROM saved_recipes WHERE recipe_id = ?", (recipe_id,)
        )
        return row is not None

    def update_saved_recipe(
        self,
        recipe_id: int,
        notes: str | None,
        rating: int | None,
        style_tags: list[str],
    ) -> dict:
        self.conn.execute(
            """
            UPDATE saved_recipes
            SET notes = ?, rating = ?, style_tags = ?
            WHERE recipe_id = ?
            """,
            (notes, rating, self._dump(style_tags), recipe_id),
        )
        self.conn.commit()
        row = self._fetch_one(
            "SELECT * FROM saved_recipes WHERE recipe_id = ?", (recipe_id,)
        )
        return row  # type: ignore[return-value]

    def get_saved_recipes(
        self,
        sort_by: str = "saved_at",
        collection_id: int | None = None,
    ) -> list[dict]:
        order = {
            "saved_at": "sr.saved_at DESC",
            "rating":   "sr.rating DESC",
            "title":    "r.title ASC",
        }.get(sort_by, "sr.saved_at DESC")

        if collection_id is not None:
            return self._fetch_all(
                f"""
                SELECT sr.*, r.title
                FROM saved_recipes sr
                JOIN recipes r ON r.id = sr.recipe_id
                JOIN recipe_collection_members rcm ON rcm.saved_recipe_id = sr.id
                WHERE rcm.collection_id = ?
                ORDER BY {order}
                """,
                (collection_id,),
            )
        return self._fetch_all(
            f"""
            SELECT sr.*, r.title
            FROM saved_recipes sr
            JOIN recipes r ON r.id = sr.recipe_id
            ORDER BY {order}
            """,
        )

    def get_saved_recipe_collection_ids(self, saved_recipe_id: int) -> list[int]:
        rows = self._fetch_all(
            "SELECT collection_id FROM recipe_collection_members WHERE saved_recipe_id = ?",
            (saved_recipe_id,),
        )
        return [r["collection_id"] for r in rows]

    # ── recipe collections ────────────────────────────────────────────────

    def create_collection(self, name: str, description: str | None) -> dict:
        return self._insert_returning(
            "INSERT INTO recipe_collections (name, description) VALUES (?, ?) RETURNING *",
            (name, description),
        )

    def delete_collection(self, collection_id: int) -> None:
        self.conn.execute(
            "DELETE FROM recipe_collections WHERE id = ?", (collection_id,)
        )
        self.conn.commit()

    def rename_collection(
        self, collection_id: int, name: str, description: str | None
    ) -> dict:
        self.conn.execute(
            """
            UPDATE recipe_collections
            SET name = ?, description = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (name, description, collection_id),
        )
        self.conn.commit()
        row = self._fetch_one(
            "SELECT * FROM recipe_collections WHERE id = ?", (collection_id,)
        )
        return row  # type: ignore[return-value]

    def get_collections(self) -> list[dict]:
        return self._fetch_all(
            """
            SELECT rc.*,
                   COUNT(rcm.saved_recipe_id) AS member_count
            FROM recipe_collections rc
            LEFT JOIN recipe_collection_members rcm ON rcm.collection_id = rc.id
            GROUP BY rc.id
            ORDER BY rc.created_at ASC
            """
        )

    def add_to_collection(self, collection_id: int, saved_recipe_id: int) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO recipe_collection_members (collection_id, saved_recipe_id)
            VALUES (?, ?)
            """,
            (collection_id, saved_recipe_id),
        )
        self.conn.commit()

    def remove_from_collection(
        self, collection_id: int, saved_recipe_id: int
    ) -> None:
        self.conn.execute(
            """
            DELETE FROM recipe_collection_members
            WHERE collection_id = ? AND saved_recipe_id = ?
            """,
            (collection_id, saved_recipe_id),
        )
        self.conn.commit()

    # ── recipe browser ────────────────────────────────────────────────────

    def get_browser_categories(
        self, domain: str, keywords_by_category: dict[str, list[str]]
    ) -> list[dict]:
        """Return [{category, recipe_count}] for each category in the domain.

        keywords_by_category maps category name to the keyword list used to
        match against recipes.category and recipes.keywords.
        """
        results = []
        for category, keywords in keywords_by_category.items():
            count = self._count_recipes_for_keywords(keywords)
            results.append({"category": category, "recipe_count": count})
        return results

    @staticmethod
    def _browser_fts_query(keywords: list[str]) -> str:
        """Build an FTS5 MATCH expression that ORs all keywords as exact phrases."""
        phrases = ['"' + kw.replace('"', '""') + '"' for kw in keywords]
        return " OR ".join(phrases)

    def _count_recipes_for_keywords(self, keywords: list[str]) -> int:
        if not keywords:
            return 0
        cache_key = (self._db_path, *sorted(keywords))
        if cache_key in _COUNT_CACHE:
            return _COUNT_CACHE[cache_key]
        match_expr = self._browser_fts_query(keywords)
        row = self.conn.execute(
            "SELECT count(*) FROM recipe_browser_fts WHERE recipe_browser_fts MATCH ?",
            (match_expr,),
        ).fetchone()
        count = row[0] if row else 0
        _COUNT_CACHE[cache_key] = count
        return count

    def browse_recipes(
        self,
        keywords: list[str],
        page: int,
        page_size: int,
        pantry_items: list[str] | None = None,
    ) -> dict:
        """Return a page of recipes matching the keyword set.

        Each recipe row includes match_pct (float | None) when pantry_items
        is provided. match_pct is the fraction of ingredient_names covered by
        the pantry set — computed deterministically, no LLM needed.
        """
        if not keywords:
            return {"recipes": [], "total": 0, "page": page}

        match_expr = self._browser_fts_query(keywords)
        offset = (page - 1) * page_size

        # Reuse cached count — avoids a second index scan on every page turn.
        total = self._count_recipes_for_keywords(keywords)

        rows = self._fetch_all(
            """
            SELECT id, title, category, keywords, ingredient_names,
                   calories, fat_g, protein_g, sodium_mg
            FROM recipes
            WHERE id IN (
                SELECT rowid FROM recipe_browser_fts
                WHERE recipe_browser_fts MATCH ?
            )
            ORDER BY id ASC
            LIMIT ? OFFSET ?
            """,
            (match_expr, page_size, offset),
        )

        pantry_set = {p.lower() for p in pantry_items} if pantry_items else None
        recipes = []
        for r in rows:
            entry = {
                "id":         r["id"],
                "title":      r["title"],
                "category":   r["category"],
                "match_pct":  None,
            }
            if pantry_set:
                names = r.get("ingredient_names") or []
                if names:
                    matched = sum(
                        1 for n in names if n.lower() in pantry_set
                    )
                    entry["match_pct"] = round(matched / len(names), 3)
            recipes.append(entry)

        return {"recipes": recipes, "total": total, "page": page}

    def log_browser_telemetry(
        self,
        domain: str,
        category: str,
        page: int,
        result_count: int,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO browser_telemetry (domain, category, page, result_count)
            VALUES (?, ?, ?, ?)
            """,
            (domain, category, page, result_count),
        )
        self.conn.commit()

    def get_current_pseudonym(self, directus_user_id: str) -> str | None:
        """Return the current community pseudonym for this user, or None if not set."""
        cur = self.conn.execute(
            "SELECT pseudonym FROM community_pseudonyms "
            "WHERE directus_user_id = ? AND is_current = 1 LIMIT 1",
            (directus_user_id,),
        )
        row = cur.fetchone()
        return row["pseudonym"] if row else None

    def set_pseudonym(self, directus_user_id: str, pseudonym: str) -> None:
        """Set the current community pseudonym for this user.

        Marks any previous pseudonym as non-current (retains history for attribution).
        """
        self.conn.execute(
            "UPDATE community_pseudonyms SET is_current = 0 WHERE directus_user_id = ?",
            (directus_user_id,),
        )
        self.conn.execute(
            "INSERT INTO community_pseudonyms (pseudonym, directus_user_id, is_current) "
            "VALUES (?, ?, 1)",
            (pseudonym, directus_user_id),
        )
        self.conn.commit()
