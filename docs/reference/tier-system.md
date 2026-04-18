# Tier System

Kiwi uses CircuitForge's standard four-tier model. The free tier covers the full pantry tracking workflow. AI features are gated behind Paid or BYOK.

## Feature matrix

| Feature | Free | Paid | Premium |
|---------|------|------|---------|
| **Inventory** | | | |
| Inventory CRUD | ✓ | ✓ | ✓ |
| Barcode scan | ✓ | ✓ | ✓ |
| Receipt upload | ✓ | ✓ | ✓ |
| Expiry alerts | ✓ | ✓ | ✓ |
| CSV export | ✓ | ✓ | ✓ |
| **Recipes** | | | |
| Recipe browser | ✓ | ✓ | ✓ |
| Pantry match (L1) | ✓ | ✓ | ✓ |
| Substitution (L2) | ✓ | ✓ | ✓ |
| Style templates (L3) | BYOK | ✓ | ✓ |
| Full generation (L4) | BYOK | ✓ | ✓ |
| Leftover mode | 5/day | Unlimited | Unlimited |
| **Saved recipes** | | | |
| Save + notes + star rating | ✓ | ✓ | ✓ |
| Style tags (manual) | ✓ | ✓ | ✓ |
| LLM style auto-classifier | — | BYOK | ✓ |
| Named collections | — | ✓ | ✓ |
| Meal planning | — | ✓ | ✓ |
| **OCR** | | | |
| Receipt OCR | BYOK | ✓ | ✓ |
| **Account** | | | |
| Multi-household | — | — | ✓ |

**BYOK** = Bring Your Own LLM backend. Configure a local or cloud inference endpoint and these features activate at any tier. See [LLM Setup](../getting-started/llm-setup.md).

## Pricing

| Tier | Monthly | Lifetime |
|------|---------|----------|
| Free | $0 | — |
| Paid | $8/mo | $129 |
| Premium | $16/mo | $249 |

Lifetime licenses are available at [circuitforge.tech](https://circuitforge.tech).

## Self-hosting

Self-hosted Kiwi is free under the MIT license (inventory/pipeline) and BSL 1.1 (AI features, free for personal non-commercial use). You run it on your own hardware with your own LLM backend. No subscription required.

The cloud-managed instance at `menagerie.circuitforge.tech/kiwi` runs the same codebase and requires a CircuitForge account.

## Free key

Claim a free Paid-tier key (30 days) at [circuitforge.tech](https://circuitforge.tech/free-key). No credit card required.
