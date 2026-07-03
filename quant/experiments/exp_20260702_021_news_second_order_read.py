"""exp-20260702-021: second-order news propagation read (baseline-controlled).

Alpha-lane observed-only read on the exp-20260702-020 ledger. Fixed
predeclared bundle (ticket exp-20260702-021):

- closed rows only; POOLED by event polarity, no relation_type/theme slicing;
- metric: row excess_10d minus the exposure ticker's unconditional same-span
  open->10d-close SPY-excess median (removes the 2026H1 tech-beta the raw
  ledger stats showed);
- dedup: unique (exposure_ticker, entry_date, event_polarity);
- verdict (declared before looking): lead iff positive-minus-negative median
  delta separation >= 25bp in EITHER direction (normal: pos>neg, inverted:
  neg>pos), the SAME direction pattern holds in both halves of the
  2026-01..06 span, and each polarity has >= 500 deduped rows. Otherwise no
  edge and the ledger parks under the same-population saturation rule.

Read-only. No strategy behavior change either way.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from news_event_exposure_observer import load_frames, _excess  # noqa: E402

EXPERIMENT_ID = "exp-20260702-021"
OWNER = "daniel-agent"
SLUG = "news_second_order_read"
RUNNER = f"quant/experiments/exp_20260702_021_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

LEDGER_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "news_event_exposure_observations"
    / "rows.jsonl"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_021_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SPAN_START = "2026-01-22"
SPAN_MID = "2026-04-15"  # calendar midpoint of the event span, fixed ex ante
SPAN_END = "2026-06-30"
MIN_ROWS_PER_POLARITY = 500
MIN_SEPARATION_BP = 25.0
HORIZON = 10

CHANGED_FILES = [
    f"quant/experiments/exp_20260702_021_{SLUG}.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_021_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    "docs/alpha_next_direction_20260701.md",
]
REPRO_COMMANDS = [RUNNER_COMMAND]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_read() -> dict[str, Any]:
    rows = [
        json.loads(l)
        for l in LEDGER_ROWS.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    closed = [
        r
        for r in rows
        if r["outcome_status"] == "closed"
        and r["excess_10d"] is not None
        and r["event_polarity"] in ("positive", "negative")
    ]
    # dedup unique (exposure_ticker, entry_date, polarity)
    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in closed:
        key = (row["exposure_ticker"], row["entry_date"], row["event_polarity"])
        dedup.setdefault(key, row)
    deduped = list(dedup.values())

    tickers = {r["exposure_ticker"] for r in deduped} | {"SPY"}
    frames = load_frames(tickers)
    spy = frames["SPY"]

    # unconditional same-span per-ticker baseline median (10d SPY-excess)
    baselines: dict[str, float] = {}
    s, e = pd.Timestamp(SPAN_START), pd.Timestamp(SPAN_END)
    for ticker in {r["exposure_ticker"] for r in deduped}:
        frame = frames.get(ticker)
        if frame is None:
            continue
        days = frame.index[(frame.index >= s) & (frame.index <= e)]
        vals = []
        for day in days:
            v = _excess(frame, spy, day, HORIZON)
            if v is not None:
                vals.append(v)
        if vals:
            baselines[ticker] = median(vals)

    def half_of(entry_date: str) -> str:
        return "h1" if entry_date <= SPAN_MID else "h2"

    cells: dict[tuple[str, str], list[float]] = {}
    pooled: dict[str, list[float]] = {"positive": [], "negative": []}
    skipped_no_baseline = 0
    first_order_counter: Counter = Counter()
    for row in deduped:
        base = baselines.get(row["exposure_ticker"])
        if base is None:
            skipped_no_baseline += 1
            continue
        delta = row["excess_10d"] - base
        polarity = row["event_polarity"]
        pooled[polarity].append(delta)
        cells.setdefault((polarity, half_of(row["entry_date"])), []).append(delta)
        first_order_counter[row["first_order_ticker"]] += 1

    def stats(vals: list[float]) -> dict[str, Any]:
        return {
            "rows": len(vals),
            "median_delta_bp": round(1e4 * median(vals), 1) if vals else None,
            "mean_delta_bp": round(1e4 * sum(vals) / len(vals), 1) if vals else None,
            "positive_share": round(sum(1 for v in vals if v > 0) / len(vals), 3)
            if vals
            else None,
        }

    pooled_stats = {p: stats(v) for p, v in pooled.items()}
    half_stats = {
        f"{polarity}_{half}": stats(cells.get((polarity, half), []))
        for polarity in ("positive", "negative")
        for half in ("h1", "h2")
    }

    def sep(pos_key: str, neg_key: str, source: dict) -> float | None:
        pos = source[pos_key]["median_delta_bp"]
        neg = source[neg_key]["median_delta_bp"]
        if pos is None or neg is None:
            return None
        return round(pos - neg, 1)

    pooled_sep = sep("positive", "negative", pooled_stats)
    h1_sep = sep("positive_h1", "negative_h1", half_stats)
    h2_sep = sep("positive_h2", "negative_h2", half_stats)

    rows_ok = all(
        pooled_stats[p]["rows"] >= MIN_ROWS_PER_POLARITY
        for p in ("positive", "negative")
    )
    sep_ok = pooled_sep is not None and abs(pooled_sep) >= MIN_SEPARATION_BP
    direction_consistent = (
        pooled_sep is not None
        and h1_sep is not None
        and h2_sep is not None
        and (
            (pooled_sep > 0 and h1_sep > 0 and h2_sep > 0)
            or (pooled_sep < 0 and h1_sep < 0 and h2_sep < 0)
        )
    )
    lead = bool(rows_ok and sep_ok and direction_consistent)

    top_first, top_first_n = first_order_counter.most_common(1)[0]
    total_attributed = sum(first_order_counter.values())
    return {
        "ledger_rows": len(rows),
        "closed_rows": len(closed),
        "deduped_rows": len(deduped),
        "skipped_no_baseline": skipped_no_baseline,
        "baseline_tickers": len(baselines),
        "pooled": pooled_stats,
        "half_spans": half_stats,
        "pooled_separation_bp": pooled_sep,
        "h1_separation_bp": h1_sep,
        "h2_separation_bp": h2_sep,
        "rows_threshold_ok": rows_ok,
        "separation_threshold_ok": sep_ok,
        "direction_consistent_across_halves": direction_consistent,
        "observed_only_lead": lead,
        "lead_direction": (
            None
            if not lead
            else ("normal_pos_over_neg" if pooled_sep > 0 else "inverted_neg_over_pos")
        ),
        "top_first_order_ticker": top_first,
        "top_first_order_share": round(top_first_n / total_attributed, 3),
        "verdict_rule": (
            f"lead iff |pos-neg median delta| >= {MIN_SEPARATION_BP}bp, same "
            f"direction in both half-spans, >= {MIN_ROWS_PER_POLARITY} rows "
            "per polarity"
        ),
    }


def build_payload(report: dict[str, Any]) -> dict[str, Any]:
    lead = report["observed_only_lead"]
    decision = (
        "observed_only_positive_news_second_order_polarity_lead_not_promoted"
        if lead
        else "observed_only_no_news_second_order_polarity_edge"
    )
    why = (
        (
            "Baseline-controlled second-order deltas separated by event "
            "polarity with a consistent direction in both half-spans; this "
            "is an observed-only lead, not a promoted helper."
        )
        if lead
        else (
            "After removing each exposure ticker's unconditional same-span "
            "baseline, second-order 10d SPY-excess did not separate by "
            "first-order event polarity with the predeclared magnitude and "
            "half-span consistency; overnight repricing appears to absorb "
            "the tradable part of first-order news impact for second-order "
            "names on this surface."
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "hypothesis": (
            "Baseline-controlled second-order exposure deltas separate by "
            "first-order news event polarity across the 2026-01..06 span "
            "with >= 25bp separation and half-span direction consistency."
        ),
        "alpha_hypothesis": (
            "If a stable polarity separation exists, a later shared-paper "
            "experiment can express it as a default-off tilt on exposure "
            "names in the 10 sessions after qualified first-order events."
        ),
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_diagnostic",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "news_event_second_order_exposure_attribution",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": (
            "news_second_order_polarity_propagation_10d_baseline_controlled_v1"
        ),
        "changed_variable": "none_read_only",
        "causal_components": [
            "closed_rows_only",
            "pooled_by_polarity_no_relation_slicing",
            "same_ticker_unconditional_baseline_median",
            "unique_ticker_entrydate_polarity_dedup",
            "25bp_separation_rule",
            "two_half_span_consistency",
            "either_direction_predeclared",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-020",
            "exp-20260702-017",
            "exp-20260630-005",
            "exp-20260630-017",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "first_read_of_new_second_order_exposure_ledger",
        "new_evidence_axis": (
            "first attribution read of the exp-20260702-020 second-order "
            "exposure ledger; no prior probe on this population"
        ),
        "audit": report,
        "gate1": {"note": "read-only; canonical baseline unchanged"},
        "gate2": {
            "fields": ["excess_10d", "event_polarity", "entry_date", "warehouse bars"],
            "note": "all inputs PIT; ledger settled from warehouse",
        },
        "gate3": {"note": "no filters changed; diagnostic only"},
        "gate4": {
            "mode": "observed_only_attribution",
            "passed": False,
            "observed_only_lead": lead,
            "failed_reasons": []
            if lead
            else [
                key
                for key, ok in (
                    ("rows_below_threshold", report["rows_threshold_ok"]),
                    ("separation_below_threshold", report["separation_threshold_ok"]),
                    (
                        "direction_not_consistent_across_halves",
                        report["direction_consistent_across_halves"],
                    ),
                )
                if not ok
            ],
        },
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_exits": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "backtester_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "live_ready": False,
            "paper_orders_changed": False,
            "parity_note": "read-only attribution; nothing wired into any order path",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "This population is now under the same-population saturation "
                "rule: do not re-slice these 3.5k closed rows by relation "
                "type, theme, horizon, magnitude flag, first-order ticker, "
                "or half-span to manufacture a lead. Reopen condition: "
                "materially more closed rows from CURRENT (non-replay) "
                "events accumulated by the daily observer, or an intraday "
                "timestamped entry (same-day execution) surface that tests the "
                "faster horizon this read cannot see."
            ),
            "new_evidence_required": (
                "Forward accumulation of current-event second-order rows, or "
                "intraday-entry settlement semantics; not another cut of the "
                "replay rows."
            ),
        },
        "related_files": [
            "data/non_ohlcv/news_event_exposure_observations/rows.jsonl",
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    report = payload["audit"]
    lines = [
        f"# {EXPERIMENT_ID}: second-order news propagation read",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- deduped rows: `{report['deduped_rows']}` from closed "
        f"`{report['closed_rows']}`",
        f"- pooled: pos `{report['pooled']['positive']}` | neg "
        f"`{report['pooled']['negative']}`",
        f"- separation: pooled `{report['pooled_separation_bp']}bp`, halves "
        f"`{report['h1_separation_bp']}` / `{report['h2_separation_bp']}bp`",
        f"- verdict: lead=`{report['observed_only_lead']}` "
        f"direction=`{report['lead_direction']}`",
        f"- concentration: top first-order `{report['top_first_order_ticker']}` "
        f"share `{report['top_first_order_share']}`",
        "",
        "## Rule",
        "",
        f"`{report['verdict_rule']}`",
        "",
        "## Repro",
        "",
    ]
    lines += [f"- `{cmd}`" for cmd in REPRO_COMMANDS]
    return "\n".join(lines) + "\n"


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "changed_files",
        "reproduction_commands",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/")
    record["audit_summary"] = {
        "deduped_rows": payload["audit"]["deduped_rows"],
        "pooled_separation_bp": payload["audit"]["pooled_separation_bp"],
        "observed_only_lead": payload["audit"]["observed_only_lead"],
    }
    return record


def upsert_experiment_log(record: dict[str, Any]) -> None:
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    atomic_write_text("\n".join(lines) + "\n", EXPERIMENT_LOG)


def main() -> int:
    report = run_read()
    payload = build_payload(report)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    atomic_write_json(log_record, LOG_JSON)
    atomic_write_text(build_card(payload), CARD_MD)
    upsert_experiment_log(log_record)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction={
            "success_probability": 0.2,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "raw hint already leans no-edge",
                "beta removal leaves no separation",
                "rows concentrated on few mega-cap first-order tickers",
                "half-span consistency fails",
            ],
            "confidence_reason": (
                "first read of a genuinely new surface, but every "
                "second-order relation read in this repo has closed no-edge"
            ),
        },
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": report["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status="observed_only",
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "card_file": str(CARD_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            str(p.relative_to(REPO_ROOT)).replace("\\", "/"): {
                "exists": p.exists(),
                "sha256": sha256(p),
            }
            for p in (REPO_ROOT / RUNNER, OUT_JSON, LOG_JSON, CARD_MD)
        },
        "updated_at": utc_now(),
    }
    atomic_write_json(manifest, MANIFEST_JSON)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "deduped_rows": report["deduped_rows"],
                "pooled": report["pooled"],
                "separation_bp": {
                    "pooled": report["pooled_separation_bp"],
                    "h1": report["h1_separation_bp"],
                    "h2": report["h2_separation_bp"],
                },
                "observed_only_lead": report["observed_only_lead"],
                "lead_direction": report["lead_direction"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
