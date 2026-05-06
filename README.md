<!-- Logo coming soon — replace docs/kiwi-logo.svg when final icon ships -->
<div align="center">
  <img src="docs/kiwi-logo.svg" alt="Kiwi logo" width="96" height="96" />

  # Kiwi

  **Pantry tracking and recipe suggestions — with or without an LLM.**

  [![License: MIT/BSL](https://img.shields.io/badge/license-MIT%20%2F%20BSL%201.1-blue)](#license)
  [![CI](https://git.opensourcesolarpunk.com/Circuit-Forge/kiwi/badges/workflows/ci.yml/badge.svg)](https://git.opensourcesolarpunk.com/Circuit-Forge/kiwi/actions)
  [![Version](https://img.shields.io/badge/version-0.5.0--beta-green)](https://git.opensourcesolarpunk.com/Circuit-Forge/kiwi/releases)

  [Documentation](https://docs.circuitforge.tech/kiwi) · [Live demo](https://menagerie.circuitforge.tech/kiwi) · [circuitforge.tech](https://circuitforge.tech)

  *Part of the CircuitForge LLC suite — "AI for the tasks the system made hard on purpose."*
</div>

---

> **The LLM is optional.** Barcode scanning, receipt upload, expiry alerts, the full 200k+ recipe browser, and CSV export all work with zero LLM configured. Recipe suggestions and receipt OCR activate when a backend is available, and are BYOK-unlockable at any tier. You are never forced to send your data anywhere.

---

## What Kiwi does

| Feature | Notes |
|---|---|
| **Inventory tracking** | Add items by barcode scan, receipt upload, or manually |
| **Expiry alerts** | Know what is about to go bad before it does |
| **Recipe browser** | 200k+ recipes — filter by cuisine, meal type, dietary preference, or main ingredient; pantry match percentage shown inline |
| **Leftover mode** | Prioritizes nearly-expired items in recipe ranking (5/day free, unlimited at Paid+) |
| **Recipe suggestions** | Four levels: direct corpus match, substitution/swap, cuisine-style adapter, full LLM generation |
| **Meal planning** | Plan meals for the week; pull from saved recipes or suggestions |
| **Saved recipes** | Bookmark any recipe with notes, 0-5 star rating, and free-text style tags; organize into named collections (Paid) |
| **Receipt OCR** | Extract line items from receipt photos automatically |
| **Dietary profiles** | Vegan, gluten-free, diabetic, and other constraints respected throughout |
| **Style auto-classifier** | LLM suggests style tags (comforting, hands-off, quick, etc.) for saved recipes |
| **Community feed** | Browse and share recipes with other Kiwi users |
| **CSV export** | Full pantry export, always available, no tier gate |

---

## Quick start

**One-line install (self-hosted, Docker required):**

```bash
bash <(curl -fsSL https://git.opensourcesolarpunk.com/Circuit-Forge/kiwi/raw/branch/main/install.sh)
```

**Or clone and run manually:**

```bash
git clone https://git.opensourcesolarpunk.com/Circuit-Forge/kiwi.git
cd kiwi
cp .env.example .env
./manage.sh build
./manage.sh start
# Web:  http://localhost:8511
# API:  http://localhost:8512
```

**Live cloud instance** (free account required):
[menagerie.circuitforge.tech/kiwi](https://menagerie.circuitforge.tech/kiwi)

Full setup and configuration guide: [docs.circuitforge.tech/kiwi](https://docs.circuitforge.tech/kiwi)

---

## Tiers

| Feature | Free | Paid | Premium |
|---|:---:|:---:|:---:|
| Inventory CRUD | Yes | Yes | Yes |
| Barcode scan | Yes | Yes | Yes |
| Receipt upload | Yes | Yes | Yes |
| Expiry alerts | Yes | Yes | Yes |
| CSV export | Yes | Yes | Yes |
| Recipe browser (200k+ recipes) | Yes | Yes | Yes |
| Save recipes + notes + star rating | Yes | Yes | Yes |
| Style tags (manual, free-text) | Yes | Yes | Yes |
| Leftover mode (5/day) | Yes | Yes | Yes |
| Receipt OCR | BYOK | Yes | Yes |
| Recipe suggestions (L1–L4) | BYOK | Yes | Yes |
| Named recipe collections | — | Yes | Yes |
| LLM style auto-classifier | — | BYOK | Yes |
| Meal planning | — | Yes | Yes |
| Multi-household | — | — | Yes |

**BYOK** = bring your own LLM backend. Configure `~/.config/circuitforge/llm.yaml` to unlock AI features at any tier without a paid subscription.

---

## Stack

- **Frontend:** Vue 3 SPA (Vite + TypeScript), served on port 8511
- **Backend:** FastAPI + SQLite via `circuitforge-core`, API on port 8512
- **Auth:** CircuitForge session cookie (cloud mode); local mode requires no account
- **Licensing:** Heimdall — free tier auto-provisioned at signup

---

## Forgejo-primary

Kiwi is developed and maintained on Forgejo at [git.opensourcesolarpunk.com/Circuit-Forge/kiwi](https://git.opensourcesolarpunk.com/Circuit-Forge/kiwi). GitHub and Codeberg are read-only mirrors. File issues and submit pull requests on Forgejo.

---

## License

Kiwi uses a split license:

- **Discovery and inventory pipeline** (barcode scan, expiry tracking, pantry CRUD, CSV export, recipe browser): [MIT](LICENSE-MIT)
- **AI features** (receipt OCR, LLM recipe suggestions, style auto-classifier): [BSL 1.1](LICENSE-BSL) — free for personal non-commercial self-hosting; commercial use or SaaS re-hosting requires a paid license. Converts to MIT after 4 years.

Privacy · Safety · Accessibility — co-equal, non-negotiable across all CircuitForge products.
