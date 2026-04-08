# 🥝 Kiwi

> *Part of the CircuitForge LLC "AI for the tasks the system made hard on purpose" suite.*

**Pantry tracking and leftover recipe suggestions.**

Scan barcodes, photograph receipts, and get recipe ideas based on what you already have — before it expires.

**LLM support is optional.** Inventory tracking, barcode scanning, expiry alerts, CSV export, and receipt upload all work without any LLM configured. AI features (receipt OCR, recipe suggestions, meal planning) activate when a backend is available and are BYOK-unlockable at any tier.

**Status:** Beta · CircuitForge LLC

---

## What it does

- **Inventory tracking** — add items by barcode scan, receipt upload, or manually
- **Expiry alerts** — know what's about to go bad
- **Recipe browser** — browse the full recipe corpus by cuisine, meal type, dietary preference, or main ingredient; pantry match percentage shown inline (Free)
- **Saved recipes** — bookmark any recipe with notes, a 0–5 star rating, and free-text style tags (Free); organize into named collections (Paid)
- **Receipt OCR** — extract line items from receipt photos automatically (Paid tier, BYOK-unlockable)
- **Recipe suggestions** — four levels from pantry-match to full LLM generation (Paid tier, BYOK-unlockable)
- **Style auto-classifier** — LLM suggests style tags (comforting, hands-off, quick, etc.) for saved recipes (Paid tier, BYOK-unlockable)
- **Leftover mode** — prioritize nearly-expired items in recipe ranking (Premium tier)
- **LLM backend config** — configure inference via `circuitforge-core` env-var system; BYOK unlocks Paid AI features at any tier
- **Feedback FAB** — in-app feedback button; status probed on load, hidden if CF feedback endpoint unreachable

## Stack

- **Frontend:** Vue 3 SPA (Vite + TypeScript)
- **Backend:** FastAPI + SQLite (via `circuitforge-core`)
- **Auth:** CF session cookie → Directus JWT (cloud mode)
- **Licensing:** Heimdall (free tier auto-provisioned at signup)

## Running locally

```bash
cp .env.example .env
./manage.sh build
./manage.sh start
# Web: http://localhost:8511
# API: http://localhost:8512
```

## Cloud instance

```bash
./manage.sh cloud-build
./manage.sh cloud-start
# Served at menagerie.circuitforge.tech/kiwi (JWT-gated)
```

## Tiers

| Feature | Free | Paid | Premium |
|---------|------|------|---------|
| Inventory CRUD | ✓ | ✓ | ✓ |
| Barcode scan | ✓ | ✓ | ✓ |
| Receipt upload | ✓ | ✓ | ✓ |
| Expiry alerts | ✓ | ✓ | ✓ |
| CSV export | ✓ | ✓ | ✓ |
| Recipe browser (domain/category) | ✓ | ✓ | ✓ |
| Save recipes + notes + star rating | ✓ | ✓ | ✓ |
| Style tags (manual, free-text) | ✓ | ✓ | ✓ |
| Receipt OCR | BYOK | ✓ | ✓ |
| Recipe suggestions (L1–L4) | BYOK | ✓ | ✓ |
| Named recipe collections | — | ✓ | ✓ |
| LLM style auto-classifier | — | BYOK | ✓ |
| Meal planning | — | ✓ | ✓ |
| Multi-household | — | — | ✓ |
| Leftover mode | — | — | ✓ |

BYOK = bring your own LLM backend (configure `~/.config/circuitforge/llm.yaml`)

## License

Discovery/pipeline layer: MIT
AI features: BSL 1.1 (free for personal non-commercial self-hosting)
