"""exp-20260703-005: reversal-confound control for the exp-20260702-021 lead.

Adversarial disconfirmation, read-only. The exp-021 inverted lead says peers
of NEGATIVE-event names outperform their own baseline by ~+42.5bp/10d. The
competing story is plain short-term reversal: peers dip alongside the
first-order event day, and the next-open entry simply catches the bounce.

Fixed predeclared bundle (ticket exp-20260703-005):
- treatment rows FROZEN: the exp-021 negative-polarity deduped closed
  population, reproduced with the identical dedup rule (no re-slicing);
- control population (NEW evidence): for each exposure ticker, candidate
  entry days in the same 2026-01..06 span that are >= 10 sessions away from
  ANY event linkage for that ticker (either polarity, any relation), with a
  settleable 10d outcome;
- matching: per treatment row on prior-session close-to-close setup return
  within +/-100bp; fallback to the per-ticker setup-return quintile; drop the
  row from the matched analysis if < 3 matches (counts reported);
- per-row residual = treatment delta - median(matched control deltas), where
  delta uses the exp-021 baseline (ticker's unconditional same-span
  open->10d-close SPY-excess median);
- verdict (declared before looking):
  reversal_explained   iff median residual < 20bp OR half-span signs flip;
  propagation_survives iff median residual >= 20bp, same sign in both
                       halves, and >= 300 matched rows;
  inconclusive_weakened otherwise.

No strategy behavior change either way.
"""

from __future__ import annotations

import hashlib
import json
import sys
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

EXPERIMENT_ID = "exp-20260703-005"
OWNER = "daniel-agent"
SLUG = "news_lead_reversal_control"
RUNNER = f"quant/experiments/exp_20260703_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

LEDGER_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "news_event_exposure_observations"
    / "rows.jsonl"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SPAN_START = "2026-01-22"
SPAN_MID = "2026-04-15"
SPAN_END = "2026-06-30"
HORIZON = 10
EXCLUSION_SESSIONS = 10
SETUP_MATCH_BP = 0.01  # +/-100bp
MIN_MATCHES_PER_ROW = 3
MIN_MATCHED_ROWS = 300
RESIDUAL_RULE_BP = 20.0

CHANGED_FILES = [
    f"quant/experiments/exp_20260703_005_{SLUG}.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_005_{SLUG}.json",
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


def _setup_return(frame: pd.DataFrame, entry: pd.Timestamp) -> float | None:
    """Close-to-close return of the session before entry (the 'dip' premise)."""
    if entry not in frame.index:
        return None
    pos = frame.index.get_loc(entry)
    if pos < 2:
        return None
    prev_close = float(frame.iloc[pos - 1]["Close"])
    prev2_close = float(frame.iloc[pos - 2]["Close"])
    if prev2_close <= 0:
        return None
    return prev_close / prev2_close - 1.0


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
    # identical dedup rule as exp-021
    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in closed:
        key = (row["exposure_ticker"], row["entry_date"], row["event_polarity"])
        dedup.setdefault(key, row)
    treatment = [
        r for r in dedup.values() if r["event_polarity"] == "negative"
    ]

    tickers = {r["exposure_ticker"] for r in dedup.values()} | {"SPY"}
    frames = load_frames(tickers)
    spy = frames["SPY"]

    s, e = pd.Timestamp(SPAN_START), pd.Timestamp(SPAN_END)

    # exp-021 baseline: per-ticker unconditional same-span 10d excess median
    baselines: dict[str, float] = {}
    excess_by_day: dict[str, dict[pd.Timestamp, float]] = {}
    for ticker in {r["exposure_ticker"] for r in treatment}:
        frame = frames.get(ticker)
        if frame is None:
            continue
        days = frame.index[(frame.index >= s) & (frame.index <= e)]
        vals = {}
        for day in days:
            v = _excess(frame, spy, day, HORIZON)
            if v is not None:
                vals[day] = v
        if vals:
            baselines[ticker] = median(vals.values())
            excess_by_day[ticker] = vals

    # event-linked exclusion: any ledger row (any status/polarity) marks the
    # ticker's linked entry window
    linked: dict[str, set[pd.Timestamp]] = {}
    for row in rows:
        ticker = row["exposure_ticker"]
        anchor = row.get("entry_date") or row.get("event_date")
        if not anchor:
            continue
        linked.setdefault(ticker, set()).add(pd.Timestamp(anchor))

    def is_clean(ticker: str, day: pd.Timestamp) -> bool:
        frame = frames[ticker]
        anchors = linked.get(ticker, set())
        if not anchors:
            return True
        pos = frame.index.get_loc(day)
        lo = max(0, pos - EXCLUSION_SESSIONS)
        hi = min(len(frame.index) - 1, pos + EXCLUSION_SESSIONS)
        window = set(frame.index[lo : hi + 1])
        return not (window & anchors)

    # control pools per ticker: clean days with settleable outcome + setup ret
    control_pool: dict[str, list[tuple[float, float]]] = {}
    for ticker, vals in excess_by_day.items():
        frame = frames[ticker]
        pool = []
        for day, excess in vals.items():
            if not is_clean(ticker, day):
                continue
            setup = _setup_return(frame, day)
            if setup is None:
                continue
            pool.append((setup, excess - baselines[ticker]))
        control_pool[ticker] = pool

    # per-treatment-row matching
    residuals: list[tuple[str, float]] = []  # (entry_date, residual)
    setup_rets: list[float] = []
    dropped_few_matches = 0
    dropped_no_data = 0
    quintile_fallback_rows = 0
    for row in treatment:
        ticker = row["exposure_ticker"]
        frame = frames.get(ticker)
        base = baselines.get(ticker)
        pool = control_pool.get(ticker) or []
        if frame is None or base is None or not pool:
            dropped_no_data += 1
            continue
        entry = pd.Timestamp(row["entry_date"])
        setup = _setup_return(frame, entry)
        if setup is None:
            dropped_no_data += 1
            continue
        setup_rets.append(setup)
        matches = [d for (sr, d) in pool if abs(sr - setup) <= SETUP_MATCH_BP]
        if len(matches) < MIN_MATCHES_PER_ROW:
            # quintile fallback within the ticker's own setup distribution
            sorted_setups = sorted(sr for sr, _ in pool)
            if len(sorted_setups) >= 5:
                rank = sum(1 for x in sorted_setups if x <= setup) / len(
                    sorted_setups
                )
                quintile = min(4, int(rank * 5))
                bounds = [
                    sorted_setups[int(len(sorted_setups) * q / 5)]
                    for q in range(5)
                ] + [sorted_setups[-1]]
                lo_b, hi_b = bounds[quintile], bounds[quintile + 1]
                matches = [d for (sr, d) in pool if lo_b <= sr <= hi_b]
                quintile_fallback_rows += 1
        if len(matches) < MIN_MATCHES_PER_ROW:
            dropped_few_matches += 1
            continue
        treatment_delta = row["excess_10d"] - base
        residuals.append((row["entry_date"], treatment_delta - median(matches)))

    def stats(vals: list[float]) -> dict[str, Any]:
        return {
            "rows": len(vals),
            "median_bp": round(1e4 * median(vals), 1) if vals else None,
            "mean_bp": round(1e4 * sum(vals) / len(vals), 1) if vals else None,
            "positive_share": round(sum(1 for v in vals if v > 0) / len(vals), 3)
            if vals
            else None,
        }

    all_res = [v for _, v in residuals]
    h1 = [v for d, v in residuals if d <= SPAN_MID]
    h2 = [v for d, v in residuals if d > SPAN_MID]
    res_stats = stats(all_res)
    h1_stats, h2_stats = stats(h1), stats(h2)

    med = res_stats["median_bp"]
    half_signs_consistent = (
        h1_stats["median_bp"] is not None
        and h2_stats["median_bp"] is not None
        and (
            (h1_stats["median_bp"] > 0 and h2_stats["median_bp"] > 0)
            or (h1_stats["median_bp"] < 0 and h2_stats["median_bp"] < 0)
        )
    )
    rows_ok = res_stats["rows"] >= MIN_MATCHED_ROWS
    if med is None or med < RESIDUAL_RULE_BP or not half_signs_consistent:
        verdict = "reversal_explained" if med is not None else "inconclusive_weakened"
        if med is not None and med >= RESIDUAL_RULE_BP and not half_signs_consistent:
            verdict = "reversal_explained"
    elif rows_ok:
        verdict = "propagation_survives"
    else:
        verdict = "inconclusive_weakened"

    return {
        "treatment_rows": len(treatment),
        "matched_rows": res_stats["rows"],
        "dropped_no_data": dropped_no_data,
        "dropped_few_matches": dropped_few_matches,
        "quintile_fallback_rows": quintile_fallback_rows,
        "treatment_setup_return_median_bp": round(1e4 * median(setup_rets), 1)
        if setup_rets
        else None,
        "residual": res_stats,
        "residual_h1": h1_stats,
        "residual_h2": h2_stats,
        "half_signs_consistent": half_signs_consistent,
        "rows_threshold_ok": rows_ok,
        "verdict": verdict,
        "verdict_rule": (
            f"reversal_explained iff median residual < {RESIDUAL_RULE_BP}bp or "
            f"half-span sign flip; propagation_survives iff >= "
            f"{RESIDUAL_RULE_BP}bp same-sign halves and >= {MIN_MATCHED_ROWS} "
            "matched rows; else inconclusive_weakened"
        ),
    }


def build_payload(report: dict[str, Any]) -> dict[str, Any]:
    verdict = report["verdict"]
    decision = {
        "reversal_explained": (
            "observed_only_exp021_lead_reversal_explained_not_propagation"
        ),
        "propagation_survives": (
            "observed_only_exp021_lead_survives_reversal_control"
        ),
        "inconclusive_weakened": (
            "observed_only_exp021_lead_reversal_control_inconclusive"
        ),
    }[verdict]
    why = {
        "reversal_explained": (
            "Matched no-event control days with similar prior-session setup "
            "returns reproduce most of the negative-event-peer excess, so the "
            "exp-021 inverted lead is short-term reversal in disguise, not a "
            "propagation effect."
        ),
        "propagation_survives": (
            "After matching on prior-session setup return against clean "
            "no-event days, a residual excess remains with consistent sign in "
            "both half-spans, so the exp-021 lead is not explained by plain "
            "short-term reversal."
        ),
        "inconclusive_weakened": (
            "The matched-control residual neither clears the predeclared "
            "survival bar nor cleanly collapses to zero; the lead is "
            "weakened and needs forward rows before any further investment."
        ),
    }[verdict]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": decision,
        "accepted": False,
        "hypothesis": (
            "The exp-20260702-021 negative-event-peer excess is short-term "
            "reversal in disguise and will be reproduced by matched no-event "
            "control days with similar prior-session setup returns."
        ),
        "alpha_hypothesis": (
            "If the lead survives the control, the propagation component "
            "justifies forward accumulation and an eventual shared-paper "
            "full-stack tilt; if not, the surface parks."
        ),
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_diagnostic",
        "mechanism_family": "daily_news_llm_event_scoring_alpha",
        "trial_family": "news_event_second_order_exposure_attribution",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": (
            "news_second_order_negative_lead_reversal_control_v1"
        ),
        "changed_variable": "none_read_only",
        "causal_components": [
            "treatment_rows_frozen_from_exp021",
            "no_event_10session_exclusion_control_days",
            "setup_return_100bp_match_quintile_fallback",
            "per_row_residual_vs_matched_control_median",
            "20bp_residual_rule",
            "two_half_span_consistency",
            "300_matched_rows_floor",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-021",
            "exp-20260702-020",
            "exp-20260630-017",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_matched_no_event_control_population",
        "new_evidence_axis": (
            "matched no-event control-day population; treatment frozen from "
            "exp-021, so the test can only kill or validate the lead"
        ),
        "audit": report,
        "gate1": {"note": "read-only; canonical baseline unchanged"},
        "gate2": {
            "fields": ["excess_10d", "entry_date", "warehouse bars"],
            "note": "all inputs PIT; controls from same warehouse span",
        },
        "gate3": {"note": "no filters changed; diagnostic only"},
        "gate4": {
            "mode": "observed_only_attribution",
            "passed": False,
            "observed_only_lead": verdict == "propagation_survives",
            "failed_reasons": [verdict],
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
            "parity_note": "read-only control study; nothing wired anywhere",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune the matching bandwidth, exclusion window, "
                "residual threshold, or setup-return definition to flip this "
                "verdict; the same-population saturation rule from exp-021 "
                "still applies to the treatment rows. The next evidence is "
                "forward accumulation of current-event rows via the daily "
                "observer wiring, or nothing."
            ),
            "new_evidence_required": (
                "Closed second-order rows from CURRENT (post-replay) events; "
                "if the verdict was survives, those rows decide the "
                "shared-paper full-stack; if reversal_explained, the surface "
                "parks with that reopen condition."
            ),
        },
        "related_files": [
            "data/non_ohlcv/news_event_exposure_observations/rows.jsonl",
            "data/experiments/exp-20260702-021/exp_20260702_021_news_second_order_read.json",
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    report = payload["audit"]
    lines = [
        f"# {EXPERIMENT_ID}: reversal control for the exp-021 lead",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- verdict: `{report['verdict']}`",
        f"- matched rows: `{report['matched_rows']}` of "
        f"`{report['treatment_rows']}` treatment "
        f"(dropped: no-data `{report['dropped_no_data']}`, few-matches "
        f"`{report['dropped_few_matches']}`; quintile fallback "
        f"`{report['quintile_fallback_rows']}`)",
        f"- treatment setup return median: "
        f"`{report['treatment_setup_return_median_bp']}bp` (the dip premise)",
        f"- residual: `{report['residual']}`",
        f"- halves: h1 `{report['residual_h1']}` | h2 `{report['residual_h2']}`",
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
        "verdict": payload["audit"]["verdict"],
        "matched_rows": payload["audit"]["matched_rows"],
        "residual_median_bp": payload["audit"]["residual"]["median_bp"],
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
            "success_probability": 0.4,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "treatment setup returns are not actually dips",
                "too few clean no-event control days per ticker",
                "matching too coarse",
            ],
            "confidence_reason": (
                "designed 50/50: either outcome is decision-relevant before "
                "forward/full-stack investment"
            ),
        },
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": report["verdict"] == "propagation_survives",
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
                "verdict": report["verdict"],
                "matched_rows": report["matched_rows"],
                "treatment_setup_return_median_bp": report[
                    "treatment_setup_return_median_bp"
                ],
                "residual": report["residual"],
                "residual_h1": report["residual_h1"],
                "residual_h2": report["residual_h2"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
