#!/usr/bin/env bash
# Dependent job: force-refresh all 1229 companyfacts CIK files to LATEST.
# Waits for the in-flight backfill (run_backfill.sh) to finish first, so SEC
# EDGAR is never hit concurrently (shared ~10 req/s per-IP fair-access limit).
set -u
PY=".venv/Scripts/python.exe"
DIR="data/experiments/exp-20260613-023"
LOG="$DIR/cf_refresh.log"
TKSP=$(tr ',' ' ' < "$DIR/broad_tickers.txt")

echo "=== cf_refresh queued $(date -u); waiting for backfill done marker ===" > "$LOG"
# Poll the backfill log for completion (max ~12h safety cap = 720 * 60s).
for i in $(seq 1 720); do
  if grep -q "=== backfill done" "$DIR/backfill.log" 2>/dev/null; then
    echo "backfill done detected at $(date -u); starting refresh" >> "$LOG"
    break
  fi
  sleep 60
done

if ! grep -q "=== backfill done" "$DIR/backfill.log" 2>/dev/null; then
  echo "ABORT: backfill done marker not seen within cap; not starting refresh to avoid concurrent SEC load $(date -u)" >> "$LOG"
  exit 1
fi

echo "--- companyfacts --refresh (all 1229, latest) $(date -u) ---" >> "$LOG"
$PY -B quant/sec_companyfacts_backfill.py \
  --tickers $TKSP --start 2024-08-01 --end 2026-06-13 --refresh \
  --sleep-seconds 0.15 \
  --output "$DIR/refresh_companyfacts_rows.jsonl" \
  --summary-output "$DIR/refresh_companyfacts_summary.json" >> "$LOG" 2>&1
echo "companyfacts --refresh exit=$? $(date -u)" >> "$LOG"
echo "=== cf_refresh done $(date -u) ===" >> "$LOG"
