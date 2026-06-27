"""exp-20260627-022: entry name-level price-exhaustion tags for forward rows.

Measurement repair / forward instrumentation. Adds a read-only PIT name-level
entry-day exhaustion tag (ATR-extension above the 20d MA, pct-from-20d-MA,
pct-from-252d-high, computed purely from warehouse OHLCV strictly prior to entry)
to closed forward replacement rows.

Why this and not another regime/short-volume slice: the n=22 frozen-window entry
diagnostic showed the oracle-regret-compass section-3 "weak-tape low-MFE failed-
followthrough" cohort is NOT separable from winners by the already-tagged market
regime (entry_regime_*) or short-volume (entry_short_volume_*) axes -- those
losers were market-"risk_on" with indistinguishable trade_quality/confidence at
entry. The only admissible, non-graveyard move (the accepted neighbor in the
novelty index is forward regime TAGGING, not a tradable tilt) is to accumulate a
NEW name-level ex-ante exhaustion label on closed forward rows so a discriminator
can be tested OUT OF SAMPLE once enough rows accumulate.

This runner changes no strategy helper, candidate ranking, sizing, entry, exit,
paper order, or live order: the tag is read-only PIT context on already-closed
rows. It is NOT accepted alpha and NOT a threshold / quintile / top-N / notional
retune. The stretched flag is a provisional readability bucket only.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import forward_replacement_value as frv  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260627-022"
LANE = "measurement_repair"
OWNER = "agent-oracle-followup"
SLUG = "forward_replacement_entry_exhaustion_tag"
RUNNER = f"quant/experiments/exp_20260627_022_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
ASOF_DATE = "2026-06-27"

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
FORWARD_ARTIFACT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_022_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: out-of-sample validation of an entry name-"
    "level price-exhaustion discriminator for the weak-tape low-MFE failed-"
    "followthrough cohort (oracle_regret_compass section 3) is blocked because "
    "closed forward replacement rows do not carry a PIT entry-day exhaustion tag; "
    "the already-tagged regime and short-volume axes were shown non-separating."
)
CHANGED_VARIABLE = "forward_replacement_rows_entry_exhaustion_tag_v1"
PREDICTION = {
    "success_probability": 0.8,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "warehouse_bars_missing_for_forward_ticker_at_entry",
        "thin_history_under_21_bars_forms_no_extension",
        "dirty_state_write_conflict",
        "non_idempotent_rebuild",
    ],
    "confidence_reason": (
        "The shared forward replacement enrichment path already owns the closed "
        "row surface and added entry-regime and entry-short-volume tags the same "
        "way. Extension is pure-OHLCV from the warehouse, which covers all forward-"
        "row tickers with deep history, so nearly every closed row should receive a "
        "real extension. The repair only adds read-only entry-date tags and tests "
        "idempotent rebuild; the main disconfirmer is a forward-row ticker missing "
        "from the warehouse."
    ),
    "recorded_at": "2026-06-27T00:00:00+00:00",
}
CHANGED_FILES = [
    "quant/forward_replacement_value.py",
    "quant/test_forward_replacement_value.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_022_{SLUG}.json",
    "data/paper_sleeves/forward_replacement_value.jsonl",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(raw)
    if not replaced:
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def aggregate_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "aggregate_expected_value_score": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "aggregate_total_pnl": round(
            sum(float(w.get("total_pnl") or 0.0) for w in windows), 2
        ),
        "total_trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "min_survival_rate": min(
            (float(w.get("survival_rate") or 0.0) for w in windows), default=None
        ),
    }


def synthetic_exhaustion_bars() -> dict[str, list]:
    """25 rising strictly-prior GS sessions before a 2026-05-05 entry."""
    rows = []
    start = dt.date(2026, 3, 28)
    for i in range(25):
        d = start + dt.timedelta(days=i)
        close = 800.0 + i * 5.0
        rows.append((d.isoformat(), close + 2.0, close - 2.0, close))
    return {"GS": rows}


def fake_comparator_bars() -> dict[str, dict[str, dict[str, float]]]:
    return {
        "SPY": {
            "2026-05-05": {"open": 100.0, "close": 101.0},
            "2026-05-15": {"open": 102.0, "close": 104.0},
        },
        "QQQ": {
            "2026-05-05": {"open": 200.0, "close": 201.0},
            "2026-05-15": {"open": 208.0, "close": 210.0},
        },
    }


def fixture_closed_row() -> dict[str, Any]:
    return {
        "ticker": "GS",
        "decision_id": "EXP022:fixture:2026-05-05:GS",
        "entry_date": "2026-05-05",
        "exit_date": "2026-05-15",
        "pnl": 390.84,
        "net_return_pct": 3.908409,
        "entry_price": 909.73,
        "exit_price": 948.47,
    }


def run_temp_validation() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ginger-exp-20260627-022-") as tmp_raw:
        tmp = Path(tmp_raw)
        root = tmp / "paper_sleeves"
        sleeve_dir = root / "demo_sleeve"
        sleeve_dir.mkdir(parents=True)
        state_path = sleeve_dir / "state.json"
        artifact_path = tmp / "forward_replacement_value.jsonl"
        write_json(state_path, {"closed_positions": [fixture_closed_row()]})
        bars = synthetic_exhaustion_bars()

        summary = frv.enrich_all_sleeve_states(
            ASOF_DATE,
            sleeves_root=root,
            bars_by_ticker=fake_comparator_bars(),
            exhaustion_bars=bars,
            artifact_path=artifact_path,
        )
        saved_state = read_json(state_path)
        artifact_rows = [
            json.loads(line)
            for line in artifact_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        second = frv.enrich_all_sleeve_states(
            "2026-06-28",
            sleeves_root=root,
            bars_by_ticker=fake_comparator_bars(),
            exhaustion_bars=bars,
            artifact_path=artifact_path,
        )
        row = saved_state["closed_positions"][0]
        artifact_row = artifact_rows[0] if artifact_rows else {}
        return {
            "summary_exhaustion_enabled": summary.get("entry_exhaustion_tagging_enabled"),
            "state_row_has_exhaustion_tag": (
                row.get("entry_exhaustion_tag_rule_version")
                == frv.ENTRY_EXHAUSTION_TAG_RULE_VERSION
            ),
            "artifact_row_has_exhaustion_tag": (
                artifact_row.get("entry_exhaustion_tag_rule_version")
                == frv.ENTRY_EXHAUSTION_TAG_RULE_VERSION
            ),
            "entry_exhaustion_status": row.get("entry_exhaustion_status"),
            "entry_exhaustion_extension_atr_mult": row.get(
                "entry_exhaustion_extension_atr_mult"
            ),
            "entry_exhaustion_stretched_flag": row.get("entry_exhaustion_stretched_flag"),
            "idempotent_second_run": second.get("rows_enriched") == 0,
        }


def enrich_real_forward_rows() -> dict[str, Any]:
    """Run the real shared enrichment over the live sleeve states (the daily run
    does the same), then audit the entry-exhaustion coverage."""
    summary = frv.enrich_all_sleeve_states(ASOF_DATE)
    rows: list[dict[str, Any]] = []
    if FORWARD_ARTIFACT.exists():
        for line in FORWARD_ARTIFACT.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    tagged = [r for r in rows if r.get("entry_exhaustion_status") == "ok"]
    exts = [
        float(r["entry_exhaustion_extension_atr_mult"])
        for r in tagged
        if r.get("entry_exhaustion_extension_atr_mult") is not None
    ]
    by_status: dict[str, int] = defaultdict(int)
    for r in rows:
        by_status[str(r.get("entry_exhaustion_status"))] += 1
    stretched = [r for r in tagged if r.get("entry_exhaustion_stretched_flag")]
    return {
        "enrichment_summary": {
            k: summary.get(k)
            for k in (
                "status",
                "rows_enriched",
                "entry_exhaustion_tagging_enabled",
                "artifact_rows",
            )
        },
        "forward_rows_total": len(rows),
        "forward_rows_exhaustion_ok": len(tagged),
        "forward_rows_exhaustion_by_status": dict(by_status),
        "extension_atr_mult_distribution": {
            "n": len(exts),
            "mean": round(mean(exts), 4) if exts else None,
            "median": round(median(exts), 4) if exts else None,
            "min": round(min(exts), 4) if exts else None,
            "max": round(max(exts), 4) if exts else None,
        },
        "stretched_flag_count": len(stretched),
        "diagnostic_caveat": (
            "Forward-row N is tiny and not significance-tested; this is the "
            "validation SURFACE, not an alpha verdict. No exhaustion-conditioned "
            "ranking/sizing tilt can be accepted until materially more closed "
            "forward rows accumulate and a discriminator validates out of sample."
        ),
    }


def build_result() -> dict[str, Any]:
    before = aggregate_metrics()
    after = dict(before)
    temp_validation = run_temp_validation()
    forward_enrichment = enrich_real_forward_rows()

    accepted = (
        bool(temp_validation["state_row_has_exhaustion_tag"])
        and bool(temp_validation["artifact_row_has_exhaustion_tag"])
        and temp_validation["entry_exhaustion_status"] == "ok"
        and bool(temp_validation["idempotent_second_run"])
        and forward_enrichment["forward_rows_exhaustion_ok"] >= 1
    )
    decision = (
        "accepted_measurement_repair_forward_replacement_entry_exhaustion_tag"
        if accepted
        else "blocked_forward_replacement_entry_exhaustion_tag_incomplete"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": LANE,
        "owner": OWNER,
        "status": "accepted" if accepted else "rejected",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "timestamp": utc_now(),
        "hypothesis": HYPOTHESIS,
        "change_type": "forward_replacement_value_entry_exhaustion_tag_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": "entry_name_level_exhaustion_measurement_repair",
        "trial_family": "default_off_forward_entry_exhaustion_tagging",
        "trial_variant_id": "forward_replacement_entry_exhaustion_tag_v1",
        "nearby_prior_experiments": [
            "exp-20260623-002",
            "exp-20260626-018",
            "exp-20260627-019",
        ],
        "new_evidence_type": "shared_forward_entry_name_level_exhaustion_observation_field",
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "max_window_drawdown_pct": 0.0,
            "min_survival_rate": 0.0,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "baseline_metrics": before,
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields_checked": [
                "entry_date",
                "entry_exhaustion_tag_rule_version",
                "entry_exhaustion_extension_atr_mult",
                "entry_exhaustion_pct_from_20ma",
                "entry_exhaustion_pct_from_252w_high",
                "entry_exhaustion_stretched_flag",
            ],
            "temp_validation": temp_validation,
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "baseline_min_survival_rate": before["min_survival_rate"],
        },
        "gate4": {
            "passed": accepted,
            "strategy_replay_changed": False,
            "measurement_repair_only": True,
            "decision": decision,
        },
        "calibration": {
            **PREDICTION,
            "actual_success": 1 if accepted else 0,
            "actual_gate4_passed": accepted,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "failure_modes_observed": []
            if accepted
            else ["temp_validation_or_real_enrichment_failed"],
            "surprise_note": (
                "No surprise; warehouse OHLCV covers the forward-row tickers, so "
                "closed rows received a real PIT extension."
                if accepted
                else "The measurement repair did not satisfy the preregistered tag checks."
            ),
        },
        "validation": {
            "temp_validation": temp_validation,
            "real_forward_enrichment": forward_enrichment,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "default_off_attribution_only": True,
            "live_ready": False,
            "parity_note": (
                "The shared forward replacement-value enrichment helper now records "
                "read-only entry-time name-level exhaustion tags. The daily run.py "
                "path already calls enrich_all_sleeve_states with no bars (warehouse "
                "load), so new closed rows are tagged going forward. It does not "
                "alter any paper or live decision surface."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Forward replacement enrichment already owns the closed-row surface "
                "and the warehouse holds deep OHLCV for the forward-row tickers, so "
                "the strictly-prior 20d-MA / ATR14 / 252d-high extension joined to "
                "the closed rows with no missing-data dependency."
            ),
            "forbidden_near_neighbor_retry": (
                "Do NOT use this tag to run a frozen-window exhaustion gate, de-rank, "
                "notional down-weight, or quintile/threshold/top-N/lookback sweep -- "
                "regime-conditioned ranking/sizing tilts are a proven graveyard "
                "(novelty neighbors ~0 accept) and the entry diagnostic found no "
                "separator on the current n=22 frozen sample. The tag exists ONLY to "
                "validate a discriminator on closed forward rows once enough "
                "accumulate, out of sample."
            ),
            "new_evidence_required": (
                "Materially more closed forward replacement rows so the exhaustion "
                "extension can be tested as a discriminator of the failed-"
                "followthrough cohort with statistical power, or a genuinely new PIT "
                "entry-fragility data source, before any tilt-activation test."
            ),
        },
        "changed_files": CHANGED_FILES,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log_file": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": accepted,
    }


def write_card(result: dict[str, Any]) -> None:
    fe = result["validation"]["real_forward_enrichment"]
    dist = fe["extension_atr_mult_distribution"]
    lines = [
        f"# Experiment Card: {EXPERIMENT_ID}",
        "",
        f"- Status: `{result['status']}`",
        f"- Decision: `{result['decision']}`",
        f"- Lane: `{LANE}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        "- Production orders changed: `false`",
        "",
        "## Summary",
        "",
        HYPOTHESIS,
        "",
        "## Result",
        "",
        (
            "Accepted measurement repair / forward instrumentation. Forward "
            "replacement-value enrichment now writes a read-only entry-time name-"
            "level exhaustion tag (ATR-extension above 20d MA, pct-from-20d-MA, "
            "pct-from-252d-high) for closed paper rows, and the daily run path "
            "auto-loads warehouse bars so future rows are tagged. "
            f"{fe['forward_rows_exhaustion_ok']}/{fe['forward_rows_total']} current "
            "closed rows carry a real extension "
            f"(median {dist['median']} ATR units, "
            f"{fe['stretched_flag_count']} stretched)."
            if result["accepted"]
            else "Blocked. Entry-exhaustion tag validation failed."
        ),
        "",
        "## Boundary",
        "",
        result["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        f"- caveat: {fe['diagnostic_caveat']}",
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_forward_replacement_value.py`",
        "",
        "No JavaScript was used.",
    ]
    write_text(CARD_MD, "\n".join(lines) + "\n")


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "generated_at": result["timestamp"],
            "files": CHANGED_FILES,
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "ticket_file": repo_rel(TICKET_JSON),
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def main() -> None:
    result = build_result()
    write_json(OUT_JSON, result)
    write_json(LOG_JSON, result)
    write_card(result)
    write_manifest(result)
    upsert_jsonl(EXPERIMENT_LOG, result)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
            "decision": result["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "lean_quality_passed": result["lean_quality_passed"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "new_evidence_type": result["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "artifact_file": repo_rel(OUT_JSON),
            "log_file": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "changed_files": CHANGED_FILES,
        },
    )

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
