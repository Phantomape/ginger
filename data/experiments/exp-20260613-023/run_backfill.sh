#!/usr/bin/env bash
# One-time broad-universe historical backfill for the 3 PIT-complete SEC streams.
# Sequential (not parallel) to respect SEC ~10 req/s per-IP fair-access limit.
# Materializes the breadth side of exp-20260613-023 (CIK map fix 0->10341).
set -u
PY=".venv/Scripts/python.exe"
DIR="data/experiments/exp-20260613-023"
TK=$(cat "$DIR/broad_tickers.txt")          # comma-separated, 1229 names
TKSP=$(tr ',' ' ' < "$DIR/broad_tickers.txt")  # space-separated for nargs
START="2024-08-01"
END="2026-06-13"
LOG="$DIR/backfill.log"
echo "=== backfill start $(date -u) | start=$START end=$END | tickers=1229 ===" > "$LOG"

echo "--- [1/3] companyfacts (breadth fill, no --refresh) $(date -u) ---" | tee -a "$LOG"
$PY -B quant/sec_companyfacts_backfill.py \
  --tickers $TKSP --start "$START" --end "$END" \
  --sleep-seconds 0.15 \
  --output "$DIR/backfill_companyfacts_rows.jsonl" \
  --summary-output "$DIR/backfill_companyfacts_summary.json" >> "$LOG" 2>&1
echo "companyfacts exit=$? $(date -u)" | tee -a "$LOG"

echo "--- [2/3] form4 (broad, CIK map fixed) $(date -u) ---" | tee -a "$LOG"
$PY -B quant/form4_backfill.py \
  --tickers "$TK" --start "$START" --end "$END" \
  --sleep-seconds 0.15 \
  --output "$DIR/backfill_form4_rows.jsonl" \
  --summary-output "$DIR/backfill_form4_summary.json" >> "$LOG" 2>&1
echo "form4 exit=$? $(date -u)" | tee -a "$LOG"

echo "--- [3/3] sec_filing (broad) $(date -u) ---" | tee -a "$LOG"
$PY -B quant/sec_filing_backfill.py \
  --tickers "$TK" --start "$START" --end "$END" \
  --sleep-seconds 0.15 \
  --output "$DIR/backfill_sec_filing_rows.jsonl" \
  --summary-output "$DIR/backfill_sec_filing_summary.json" >> "$LOG" 2>&1
echo "sec_filing exit=$? $(date -u)" | tee -a "$LOG"
echo "=== backfill done $(date -u) ===" | tee -a "$LOG"
