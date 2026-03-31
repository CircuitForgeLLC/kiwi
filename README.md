# 🥝 Kiwi

> *Part of the CircuitForge LLC "AI for the tasks the system made hard on purpose" suite.*

**Pantry tracking and leftover recipe suggestions.**

Scan barcodes, photograph receipts, and get recipe ideas based on what you already have — before it expires.

**Status:** Pre-alpha · CircuitForge LLC

---

## What it does

- **Inventory tracking** — add items by barcode scan, receipt upload, or manually
- **Expiry alerts** — know what's about to go bad
- **Receipt OCR** — extract line items from receipt photos automatically (Paid tier)
- **Recipe suggestions** — LLM-powered ideas based on what's expiring (Paid tier, BYOK-unlockable)
- **Leftover mode** — prioritize nearly-expired items in recipe ranking (Premium tier)

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
| Receipt OCR | BYOK | ✓ | ✓ |
| Recipe suggestions | BYOK | ✓ | ✓ |
| Meal planning | — | ✓ | ✓ |
| Multi-household | — | — | ✓ |
| Leftover mode | — | — | ✓ |

BYOK = bring your own LLM backend (configure `~/.config/circuitforge/llm.yaml`)

## License

Discovery/pipeline layer: MIT
AI features: BSL 1.1 (free for personal non-commercial self-hosting)
