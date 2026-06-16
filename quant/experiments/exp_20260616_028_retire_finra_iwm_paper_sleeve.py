"""exp-20260616-028: retire the default-off FINRA/IWM borrow-pressure paper sleeve.

Measurement_repair / cleanup. The FINRA borrow-pressure source (exp-20260603-006)
was disproven across windows and universes:

* exp-20260616-024 (core ~47 universe): REJECTED, late_strong regressed.
* exp-20260616-026 (broad ~1440 universe): REJECTED, aggregate +$110 / 327 trades
  (~$0.34/trade), drawdown drift over cap, per-window sign flips => noise.
* The live default-off sleeve produced ~0 closed forward rows across 30 snapshots.
* A stop/TP grid only "helped" by overfitting the frozen windows; old_thin stayed
  negative in every config.

This run gates the daily paper build OFF (DEFAULT_CONFIG paper_enabled=False plus
an early short-circuit in build_finra_iwm_paper_sleeve_snapshot). It is fully
reversible (set paper_enabled=True). No live orders, core ranking, sizing, exits,
LLM/news, or watchlist behavior change (the sleeve was already trade_enabled=False).
The FINRA short-interest archive and the FTD+FINRA refresh path are untouched, so
sec_ftd_finra and the data backfill keep working. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260616-028"
LANE = "measurement_repair"
OWNER = "alpha-search-automation"
STEM = "retire_finra_iwm_paper_sleeve"
CHANGED_VARIABLE = "retire_finra_iwm_borrow_pressure_default_off_paper_sleeve_reversible"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_028_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SLEEVE_PY = REPO_ROOT / "quant" / "finra_iwm_paper_sleeve.py"
TEST_PY = REPO_ROOT / "quant" / "test_finra_iwm_paper_sleeve.py"

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "replay_only": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "trade_enabled": False,
    "reversible": True,
    "parity_note": (
        "Retires a default-off paper observation only. The sleeve was already "
        "trade_enabled=False; the daily build now short-circuits to an empty "
        "snapshot. FINRA archive refresh and sec_ftd_finra are untouched."
    ),
}

DECISION = "accepted_measurement_repair_retired_finra_iwm_borrow_pressure_paper_sleeve"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_retired() -> dict[str, Any]:
    """Confirm the production default path now short-circuits to an empty snapshot."""
    from finra_iwm_paper_sleeve import (  # noqa: E402
        DEFAULT_CONFIG,
        build_finra_iwm_paper_sleeve_snapshot,
        empty_finra_iwm_paper_state,
    )

    snapshot = build_finra_iwm_paper_sleeve_snapshot(
        as_of="2026-06-16",
        ohlcv_by_ticker={"SPY": [{"date": "2026-06-16", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]},
        candidate_universe=["AAPL"],
        state=empty_finra_iwm_paper_state(),
        persist=False,
        config=None,  # production default
    )
    return {
        "default_paper_enabled": bool(DEFAULT_CONFIG.get("paper_enabled", True)),
        "default_snapshot_candidate_count": int(snapshot.get("candidate_count", -1)),
        "default_snapshot_reason": snapshot.get("error"),
        "short_circuits_on_default": (
            DEFAULT_CONFIG.get("paper_enabled") is False
            and snapshot.get("candidate_count") == 0
            and snapshot.get("error") == "retired_default_off_paper_disabled"
        ),
    }


def build_record() -> dict[str, Any]:
    verify = _verify_retired()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": LANE,
        "status": "accepted",
        "decision": DECISION,
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "default_off_paper_sleeve_retirement",
        "trial_family": "identity_or_measurement_repair",
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Retire the default-off FINRA/IWM borrow-pressure paper sleeve whose "
            "source is disproven across windows and universes and which produces "
            "no forward evidence, to stop spending daily broad-universe FINRA "
            "compute; reversible."
        ),
        "evidence": {
            "exp-20260616-024_core_reject": "late_strong regressed; agg +$3,772 driven by old_thin only",
            "exp-20260616-026_broad_reject": "agg EV +0.0393 / +$109.77 over 327 trades (~$0.34/trade), DD drift +0.88pp, per-window sign flips",
            "forward_rows": "~0 closed rows across 30 finra_iwm snapshots",
            "stop_tp_grid": "only improved by overfitting frozen windows; old_thin stayed negative in every config",
        },
        "action": (
            "Set DEFAULT_CONFIG['paper_enabled']=False and added an early "
            "short-circuit in build_finra_iwm_paper_sleeve_snapshot returning an "
            "empty 'retired_default_off_paper_disabled' snapshot before any OHLCV "
            "or network work."
        ),
        "reversibility": "Set paper_enabled=True (config or DEFAULT_CONFIG) to restore.",
        "verification": verify,
        "untouched": [
            "FINRA short-interest archive (data/non_ohlcv/finra_short_interest)",
            "refresh_finra_short_interest_archive",
            "sec_ftd_finra_paper_sleeve",
            "live orders / core ranking / sizing / exits / watchlist",
        ],
        "gate4": {
            "applicable": False,
            "reason": "Retires a default-off paper observation; no buy/sell/filter/rank/sizing/exit/order behavior changed.",
            "baseline_unchanged": True,
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "FINRA short-interest borrow-pressure is not a directional edge; "
                "high days-to-cover predicts dispersion, so the signal nets to "
                "~zero and reshaping exits only overfits the frozen windows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not re-enable or retune days_to_cover / short-change / "
                "freshness / universe / stop / TP / top-N / hold / cooldown / "
                "notional on the frozen windows."
            ),
            "new_evidence_required": (
                "Re-activation needs a materially different PIT borrow-cost / "
                "hard-to-borrow / loan-availability field or closed forward "
                "replacement-value rows from a pre-committed rule."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(SLEEVE_PY),
            _repo_rel(TEST_PY),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _build_card(record: dict[str, Any]) -> str:
    v = record["verification"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Retire FINRA/IWM Borrow-Pressure Paper Sleeve",
            "",
            f"Status: `{record['status']}`",
            f"Decision: `{record['decision']}`",
            "",
            "## Why",
            "",
            "FINRA borrow-pressure (exp-20260603-006) is disproven: exp-20260616-024 "
            "(core) and exp-20260616-026 (broad, +$110 / 327 trades) both rejected; "
            "~0 forward rows; stop/TP only overfits. The signal predicts dispersion, "
            "not direction.",
            "",
            "## Action (reversible)",
            "",
            record["action"],
            "",
            f"- default paper_enabled: `{v['default_paper_enabled']}`",
            f"- default snapshot candidate_count: `{v['default_snapshot_candidate_count']}`",
            f"- default snapshot reason: `{v['default_snapshot_reason']}`",
            f"- short-circuits on default: `{v['short_circuits_on_default']}`",
            "",
            "## Untouched",
            "",
            "FINRA archive, refresh path, sec_ftd_finra, and all live behavior are unchanged.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _write_manifest(record: dict[str, Any]) -> None:
    paths = [Path(__file__), SLEEVE_PY, TEST_PY, OUT_JSON, LOG_JSON, CARD_MD, TICKET_JSON]
    _write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": record["status"],
            "decision": record["decision"],
            "created_at": record["timestamp"],
            "anti_js": "No JavaScript was used.",
            "allowed_write_scope": [_repo_rel(p) for p in paths],
            "file_hashes": {_repo_rel(p): _sha256(p) for p in paths if p.exists()},
        },
    )


def main() -> None:
    record = build_record()
    if not record["verification"]["short_circuits_on_default"]:
        raise RuntimeError(f"retirement not effective: {record['verification']}")
    _write_json(OUT_JSON, record)
    _write_json(LOG_JSON, record)
    CARD_MD.write_text(_build_card(record), encoding="utf-8")
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=None,
        result={
            "decision": record["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "verification": record["verification"],
            "accepted": True,
        },
        status=record["status"],
        fields={
            "owner": OWNER,
            "hypothesis": record["hypothesis"],
            "change_type": record["change_type"],
            "mechanism_family": record["mechanism_family"],
            "trial_family": record["trial_family"],
            "trial_variant_id": record["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "decision": record["decision"],
            "summary": "Retired the disproven default-off FINRA/IWM borrow-pressure paper sleeve (reversible).",
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket_file": _repo_rel(TICKET_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        },
    )
    _write_manifest(record)
    print(json.dumps(record["verification"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
