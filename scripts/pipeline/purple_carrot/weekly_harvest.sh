#!/usr/bin/env bash
# Weekly Purple Carrot recipe harvest
# Runs every Sunday night via cron.
# Discovers this week's menu and scrapes full recipe data.
# Logs to /Library/Assets/kiwi/pipeline/logs/purple_carrot_harvest.log

set -euo pipefail

REPO="/Library/Development/CircuitForge/kiwi"
MENU_OUT="/Library/Assets/kiwi/pipeline/recipes_purplecarrot_menu.parquet"
LIVE_OUT="/Library/Assets/kiwi/pipeline/recipes_purplecarrot_live.parquet"
LOG_DIR="/Library/Assets/kiwi/pipeline/logs"
LOG="$LOG_DIR/purple_carrot_harvest.log"

mkdir -p "$LOG_DIR"

echo "=== Purple Carrot harvest $(date -u '+%Y-%m-%d %H:%M UTC') ===" >> "$LOG"

cd "$REPO"

# Step 1: discover this week's menu slugs
echo "[1/2] Discovering current menu slugs..." | tee -a "$LOG"
conda run -n cf python3 scripts/pipeline/purple_carrot/discover_current_menu.py \
  --out "$MENU_OUT" 2>&1 | tee -a "$LOG"

# Step 2: scrape full recipe data for new slugs only (--resume skips already-scraped)
echo "[2/2] Scraping live recipe pages..." | tee -a "$LOG"
conda run -n cf python3 scripts/pipeline/purple_carrot/scrape_live.py \
  --slugs-from "$MENU_OUT" \
  --out "$LIVE_OUT" \
  --resume \
  --delay 3.0 2>&1 | tee -a "$LOG"

# Step 3: ingest new recipes into the shared corpus DB
echo "[3/3] Ingesting into corpus DB..." | tee -a "$LOG"
conda run -n cf python3 scripts/pipeline/ingest_purplecarrot.py \
  --parquet "$LIVE_OUT" \
  --db /Library/Assets/kiwi/kiwi.db 2>&1 | tee -a "$LOG"

echo "=== Done $(date -u '+%Y-%m-%d %H:%M UTC') ===" >> "$LOG"
echo "" >> "$LOG"
