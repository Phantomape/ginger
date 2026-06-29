"""exp-20260628-017 (measurement_repair): Windows atomic-write rename robustness
+ daily-artifact orphan recovery.

Root cause: ``data_paths.atomic_write_text`` used a bare ``os.replace`` for the
final rename. On Windows that intermittently raises ``PermissionError``
(transient AV / search-indexer / concurrent-reader lock), and the daily pipeline
swallows per-step write failures, so the artifact silently ends up as an orphan
``.<name>.<rand>.tmp`` with NO final file. quant_signals_20260627.json was the
latest victim (5 earlier days were hand-recovered in exp-20260626-005, and the
backtester hit the same class in exp-20260627-021). The estimate_revision matcher
then reported ``no_daily_signal_match_artifacts_loaded`` for 2026-06-27.

Fix (shared, production):
  * data_paths.atomic_write_text now retries os.replace with backoff and
    re-raises on permanent failure (parity with backtester._atomic_write_json);
  * stale_artifact_sweep.recover_orphan_atomic_writes promotes a valid orphan
    temp to its missing final (recovery) / removes stale temps when the final
    exists (cleanup) / leaves invalid temps untouched (no data loss);
  * run.py calls recover_daily_artifacts_quietly() under the run lock at startup.

This runner records before/after orphan state for the daily signal dirs, runs the
recovery sweep, and verifies the matcher can now load 2026-06-27 signals. It does
NOT change any strategy behavior, order, ranking, or sizing.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))

import stale_artifact_sweep as sweep  # noqa: E402
from estimate_revision_ledger import load_daily_signal_match_records  # noqa: E402

AS_OF = "2026-06-27"
QUANT_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"
OUT = REPO_ROOT / "data" / "experiments" / "exp-20260628-017"
OUT.mkdir(parents=True, exist_ok=True)


def _orphan_state() -> dict:
    """For each '.<final>.<rand>.tmp' in the quant dir, is the final present?"""
    missing_final, stale_with_final = [], []
    if QUANT_DIR.is_dir():
        for entry in os.scandir(QUANT_DIR):
            if not (entry.is_file() and entry.name.endswith(".tmp")):
                continue
            final = sweep._final_name_for_temp(entry.name)
            if not final:
                continue
            (stale_with_final if (QUANT_DIR / final).exists() else missing_final).append(final)
    return {
        "orphan_temps_missing_final": sorted(missing_final),
        "stale_temps_with_final": sorted(stale_with_final),
        "quant_signals_20260627_final_exists": (QUANT_DIR / "quant_signals_20260627.json").exists(),
    }


def main() -> None:
    before = _orphan_state()
    before_match = load_daily_signal_match_records("data", AS_OF)

    recovery = sweep.recover_daily_artifacts_quietly(REPO_ROOT)

    after = _orphan_state()
    after_match = load_daily_signal_match_records("data", AS_OF)

    final_path = QUANT_DIR / "quant_signals_20260627.json"
    final_valid = False
    if final_path.exists():
        try:
            payload = json.loads(final_path.read_text(encoding="utf-8"))
            final_valid = isinstance(payload, dict) and "signals" in payload
        except ValueError:
            final_valid = False

    result = {
        "experiment_id": "exp-20260628-017",
        "lane": "measurement_repair",
        "as_of": AS_OF,
        "strategy_behavior_changed": False,
        "before": before,
        "after": after,
        "recovery_summary": recovery,
        "match_records_before": len(before_match),
        "match_records_after": len(after_match),
        "recovered_20260627_final_present": final_path.exists(),
        "recovered_20260627_final_valid_has_signals": final_valid,
    }
    out_file = OUT / "exp_20260628_017_windows_atomic_write_rename_robustness_and_orphan_recovery.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
