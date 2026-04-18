# Settings

The Settings page lets you configure your LLM backend, dietary preferences, notification behavior, and account details.

## LLM backend

Shows the currently configured inference backend and its connection status. A green indicator means Kiwi can reach the backend and AI features are active. A red indicator means the backend is unreachable — check the URL and whether the server is running.

To change or add a backend, edit your `.env` file and restart:

```bash
LLM_BACKEND=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=llama3.1
```

See [LLM Backend Setup](../getting-started/llm-setup.md) for full configuration options.

## Dietary preferences

Set your default dietary filters here. These are applied automatically when you browse recipes and get suggestions:

- Vegetarian
- Vegan
- Gluten-free
- Dairy-free
- Nut-free
- Low-carb
- Halal
- Kosher

Dietary preferences are stored locally and not shared with any server.

## Expiry alert thresholds

Configure when Kiwi starts flagging items:

| Indicator | Default |
|-----------|---------|
| Red (urgent) | 2 days |
| Orange (soon) | 7 days |
| Yellow (upcoming) | 14 days |

## Notification settings

Kiwi can send browser notifications when items are about to expire. Enable this in Settings by clicking **Allow notifications**. Your browser will ask for permission.

Notifications are sent once per day for items entering the red (2-day) window.

## Account and tier

Shows your current tier (Free / Paid / Premium) and account email (cloud mode only). Includes a link to manage your subscription.

## Affiliate links

When browsing recipes that call for specialty ingredients, Kiwi may show eBay links to find them at a discount. You can:

- **Disable affiliate links entirely** — turn off all affiliate link insertion
- **Use your own affiliate ID** — if you have an eBay Partner Network (EPN) ID, enter it here and your ID will be used instead of CircuitForge's (Premium tier)

## Export

Click **Export pantry** to download your full inventory as a CSV file. The export includes all items, quantities, categories, expiry dates, and notes.
