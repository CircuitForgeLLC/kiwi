# Recipe Engine

Kiwi uses a four-level recipe suggestion system. Each level adds more intelligence and better results, but requires more resources. Levels 1–2 are fully deterministic and work without any LLM. Levels 3–4 require an LLM backend.

## Level overview

| Level | Name | LLM required | Description |
|-------|------|-------------|-------------|
| L1 | Pantry match | No | Rank existing corpus by ingredient overlap |
| L2 | Substitution | No | Suggest swaps for missing ingredients |
| L3 | Style templates | Yes | Generate recipe variations from style templates |
| L4 | Full generation | Yes | Generate new recipes from scratch |

## L1 — Pantry match

The simplest level. Kiwi scores every recipe in the corpus by how many of its ingredients you already have:

```
score = (matched ingredients) / (total ingredients)
```

Recipes are sorted by this score descending. If leftover mode is active, the score is further weighted by expiry proximity.

This works entirely offline with no LLM — just set arithmetic on your current pantry.

## L2 — Substitution

L2 extends L1 by suggesting substitutions for missing ingredients. When a recipe scores well but you're missing one or two items, Kiwi checks a substitution table to see if something in your pantry could stand in:

- Buttermilk → plain yogurt + lemon juice
- Heavy cream → evaporated milk
- Fresh herbs → dried herbs (adjusted quantity)

Substitutions are sourced from a curated table — no LLM involved. L2 raises the effective match score for recipes where a reasonable substitute exists.

## L3 — Style templates

L3 uses the LLM to generate recipe variations from a style template. Rather than generating fully free-form text, it fills in a structured template:

```
[protein] + [vegetable] + [starch] + [sauce/flavor profile]
```

The template is populated from your pantry contents and the style tags you've set (e.g., "quick", "Italian"). The LLM fills in the techniques, proportions, and instructions.

Style templates produce consistent, practical results with less hallucination risk than fully open-ended generation.

## L4 — Full generation

L4 gives the LLM full creative freedom. Kiwi passes:

- Your full pantry inventory
- Your dietary preferences
- Any expiring items (if leftover mode is active)
- Your saved recipe history and style tags

The LLM generates a new recipe optimized for your situation. Results are more creative than L1–L3 but require a capable model (7B+ recommended) and take longer to generate.

## Escalation

When you click **Suggest**, Kiwi tries each level in order and returns results as soon as a level produces usable output:

1. L1 and L2 run immediately (no LLM)
2. If no good matches exist (all scores < 30%), Kiwi escalates to L3
3. If L3 produces no results (LLM unavailable or error), Kiwi falls back to best L1 result
4. L4 is only triggered explicitly by the user ("Generate something new")

## Tier gates

| Level | Free | Paid | BYOK (any tier) |
|-------|------|------|-----------------|
| L1 — Pantry match | ✓ | ✓ | ✓ |
| L2 — Substitution | ✓ | ✓ | ✓ |
| L3 — Style templates | — | ✓ | ✓ |
| L4 — Full generation | — | ✓ | ✓ |
