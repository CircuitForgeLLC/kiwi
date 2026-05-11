"""Kiwi MCP Server — read-only corpus DB access for tag/keyword audits.

Exposes four tools to Claude:
  kiwi_query_corpus   — run a read-only SQL query against the corpus DB
  kiwi_count_fts      — run an FTS5 MATCH expression and return row count
  kiwi_sample_tags    — return tag frequency distribution by prefix
  kiwi_browse_preview — call the browse endpoint and return first-page results

Run with:
  python -m app.mcp.server
  (from /Library/Development/CircuitForge/kiwi with cf conda env active)

Configure in Claude Code ~/.claude/settings.json mcpServers:
  "kiwi": {
    "command": "/devl/miniconda3/envs/cf/bin/python",
    "args": ["-m", "app.mcp.server"],
    "cwd": "/Library/Development/CircuitForge/kiwi",
    "env": {
      "KIWI_DB_PATH": "/Library/Development/CircuitForge/kiwi/data/kiwi.db",
      "KIWI_API_URL": "http://localhost:8512"
    }
  }
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

_DB_PATH = os.environ.get(
    "KIWI_DB_PATH",
    str(Path(__file__).parents[3] / "data" / "kiwi.db"),
)
_API_URL = os.environ.get("KIWI_API_URL", "http://localhost:8512")
_TIMEOUT = 30.0
_QUERY_ROW_LIMIT = 200

server = Server("kiwi")


def _open_ro() -> sqlite3.Connection:
    """Open the corpus DB in read-only mode."""
    uri = f"file:///{Path(_DB_PATH).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="kiwi_query_corpus",
            description=(
                "Run a read-only SQL SELECT query against the Kiwi corpus DB (kiwi.db). "
                "Returns up to 200 rows as a JSON array. "
                "Key tables: recipes (id, title, ingredient_names, inferred_tags, source_url), "
                "recipes_fts (FTS5 virtual table for full-text search), "
                "ingredient_profiles (name, elements, texture_profile). "
                "Use for schema exploration, spot-checking tag coverage, and counting results. "
                "Read-only — any write statement will be rejected by SQLite."
            ),
            inputSchema={
                "type": "object",
                "required": ["sql"],
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A SELECT statement. E.g.: "
                            "SELECT title, inferred_tags FROM recipes WHERE inferred_tags LIKE '%vegan%' LIMIT 10"
                        ),
                    },
                },
            },
        ),
        Tool(
            name="kiwi_count_fts",
            description=(
                "Run an FTS5 MATCH expression against the recipes_fts table and return the hit count. "
                "Useful for quickly auditing keyword coverage without a full query. "
                "Always double-quote all terms in MATCH expressions. "
                "E.g. match_expr='\"tofu\" OR \"tempeh\"' returns how many recipes include either."
            ),
            inputSchema={
                "type": "object",
                "required": ["match_expr"],
                "properties": {
                    "match_expr": {
                        "type": "string",
                        "description": (
                            "FTS5 MATCH expression string (without the MATCH keyword). "
                            'E.g. \'"lentil" OR "chickpea"\' or \'"pasta" AND "vegetarian"\''
                        ),
                    },
                },
            },
        ),
        Tool(
            name="kiwi_sample_tags",
            description=(
                "Return tag frequency distribution from the corpus. "
                "Queries inferred_tags column for tags matching the given prefix pattern. "
                "Useful for auditing how well a category keyword set covers the corpus, "
                "or discovering what tags exist under a domain (cuisine:, meal:, dietary:, texture:)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prefix": {
                        "type": "string",
                        "default": "",
                        "description": (
                            "Tag prefix to filter by. E.g. 'cuisine:' returns all cuisine tags, "
                            "'meal:' returns all meal type tags, '' returns all tags. "
                            "Returns top 50 by frequency."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Max number of tag entries to return (default 50, max 200).",
                    },
                },
            },
        ),
        Tool(
            name="kiwi_browse_preview",
            description=(
                "Call the Kiwi browse endpoint and return first-page results. "
                "Use to verify that a domain/category returns the expected recipes "
                "after a keyword or tag change, without opening the browser. "
                "Returns recipe titles, match counts, and total result count."
            ),
            inputSchema={
                "type": "object",
                "required": ["domain", "category"],
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": (
                            "Browse domain slug. "
                            "Known domains: cuisine, meal_type, dietary, ingredient, occasion, texture."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "description": "Category slug within the domain, e.g. 'italian', 'breakfast', 'vegan'.",
                    },
                    "subcategory": {
                        "type": "string",
                        "default": "",
                        "description": "Optional subcategory slug to narrow further.",
                    },
                    "page_size": {
                        "type": "integer",
                        "default": 10,
                        "description": "Results per page (default 10, max 50).",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "kiwi_query_corpus":
        return await _query_corpus(arguments)
    if name == "kiwi_count_fts":
        return await _count_fts(arguments)
    if name == "kiwi_sample_tags":
        return await _sample_tags(arguments)
    if name == "kiwi_browse_preview":
        return await _browse_preview(arguments)
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _query_corpus(args: dict) -> list[TextContent]:
    sql = args.get("sql", "").strip()
    if not sql.upper().startswith("SELECT"):
        return [TextContent(type="text", text="Error: only SELECT statements are allowed.")]

    def _run() -> list[dict]:
        conn = _open_ro()
        try:
            cur = conn.execute(sql)
            rows = cur.fetchmany(_QUERY_ROW_LIMIT)
            return [dict(r) for r in rows]
        finally:
            conn.close()

    try:
        rows = await asyncio.get_event_loop().run_in_executor(None, _run)
        return [TextContent(type="text", text=json.dumps(rows, indent=2, default=str))]
    except Exception as exc:
        return [TextContent(type="text", text=f"Query error: {exc}")]


async def _count_fts(args: dict) -> list[TextContent]:
    match_expr = args.get("match_expr", "").strip()
    if not match_expr:
        return [TextContent(type="text", text="Error: match_expr is required.")]

    def _run() -> int:
        conn = _open_ro()
        try:
            cur = conn.execute(
                "SELECT COUNT(*) FROM recipes_fts WHERE recipes_fts MATCH ?",
                (match_expr,),
            )
            return cur.fetchone()[0]
        finally:
            conn.close()

    try:
        count = await asyncio.get_event_loop().run_in_executor(None, _run)
        return [TextContent(type="text", text=json.dumps({"match_expr": match_expr, "count": count}))]
    except Exception as exc:
        return [TextContent(type="text", text=f"FTS error: {exc}")]


async def _sample_tags(args: dict) -> list[TextContent]:
    prefix = args.get("prefix", "")
    limit = min(int(args.get("limit", 50)), _QUERY_ROW_LIMIT)

    def _run() -> list[dict]:
        conn = _open_ro()
        try:
            # Split inferred_tags (comma or space separated) and count each tag
            sql = """
                WITH tag_rows AS (
                    SELECT trim(value) AS tag
                    FROM recipes, json_each('["' || replace(replace(inferred_tags, ', ', '","'), ',', '","') || '"]')
                    WHERE inferred_tags IS NOT NULL AND inferred_tags != ''
                )
                SELECT tag, COUNT(*) AS frequency
                FROM tag_rows
                WHERE tag LIKE ? AND tag != ''
                GROUP BY tag
                ORDER BY frequency DESC
                LIMIT ?
            """
            pattern = f"{prefix}%" if prefix else "%"
            cur = conn.execute(sql, (pattern, limit))
            return [{"tag": r["tag"], "frequency": r["frequency"]} for r in cur.fetchall()]
        finally:
            conn.close()

    try:
        tags = await asyncio.get_event_loop().run_in_executor(None, _run)
        return [TextContent(type="text", text=json.dumps({"prefix": prefix, "tags": tags}, indent=2))]
    except Exception as exc:
        return [TextContent(type="text", text=f"Tag query error: {exc}")]


async def _browse_preview(args: dict) -> list[TextContent]:
    domain = args.get("domain", "")
    category = args.get("category", "")
    subcategory = args.get("subcategory", "")
    page_size = min(int(args.get("page_size", 10)), 50)

    params: dict = {"page": 1, "page_size": page_size}
    if subcategory:
        params["subcategory"] = subcategory

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(
                f"{_API_URL}/api/v1/recipes/browse/{domain}/{category}",
                params=params,
            )
            resp.raise_for_status()
        except Exception as exc:
            return [TextContent(type="text", text=f"Browse error: {exc}")]

    data = resp.json()
    summary = {
        "domain": domain,
        "category": category,
        "subcategory": subcategory or None,
        "total": data.get("total", 0),
        "page_size": page_size,
        "titles": [r.get("title", "") for r in data.get("recipes", [])],
    }
    return [TextContent(type="text", text=json.dumps(summary, indent=2))]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_main())
