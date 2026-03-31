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


class Store:
    def __init__(self, db_path: Path, key: str = "") -> None:
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
                    "keywords", "element_coverage"):
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

    def search_recipes_by_ingredients(
        self,
        ingredient_names: list[str],
        limit: int = 20,
        category: str | None = None,
    ) -> list[dict]:
        """Find recipes containing any of the given ingredient names.
        Scores by match count and returns highest-scoring first."""
        if not ingredient_names:
            return []
        like_params = [f'%"{n}"%' for n in ingredient_names]
        like_clauses = " OR ".join(
            "r.ingredient_names LIKE ?" for _ in ingredient_names
        )
        match_score = " + ".join(
            "CASE WHEN r.ingredient_names LIKE ? THEN 1 ELSE 0 END"
            for _ in ingredient_names
        )
        category_clause = ""
        category_params: list = []
        if category:
            category_clause = "AND r.category = ?"
            category_params = [category]
        sql = f"""
            SELECT r.*, ({match_score}) AS match_count
            FROM recipes r
            WHERE ({like_clauses})
            {category_clause}
            ORDER BY match_count DESC, r.id ASC
            LIMIT ?
        """
        all_params = like_params + like_params + category_params + [limit]
        return self._fetch_all(sql, tuple(all_params))

    def get_recipe(self, recipe_id: int) -> dict | None:
        return self._fetch_one("SELECT * FROM recipes WHERE id = ?", (recipe_id,))

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
