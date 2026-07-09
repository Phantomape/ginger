"""exp-20260703-009: resolved S-1/F-1 peer-substitution attribution.

Read-only alpha attribution. This tests whether listed issuers filing S-1/F-1
registration statements create substitution demand in listed SIC/theme peers.

Fixed bundle:
- events: SEC corporate-event stream rows where event_class == ipo_registration,
  ticker_status == resolved, and form is S-1/S-1A/F-1/F-1A;
- target: listed SIC/theme peers from the existing entity_exposure_map, excluding
  the issuer ticker itself;
- entry: peer next warehouse open strictly after filed_date;
- exit: close of the 10th trading session, with 5d as context;
- metric: peer SPY-excess return minus same peer/window unconditional SPY-excess
  median;
- dedup: unique (peer ticker, entry_date), so several same-day filings do not
  multiply one peer outcome;
- verdict: observed-only lead only if all three canonical windows have positive
  median 10d deltas, pooled median delta >= 25bp, >=100 rows per window, and
  top ticker share <= 5%.

No strategy, ranking, sizing, exit, order, paper sleeve, daily adapter, or LLM
decision behavior changes.
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
    value = str(entry)
    if value not in sys.path:
        sys.path.insert(0, value)

from entity_exposure_map import map_event_to_exposures  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from ohlcv_warehouse import load_warehouse_ohlcv_frames  # noqa: E402

EXPERIMENT_ID = "exp-20260703-009"
OWNER = "alpha-explore"
SLUG = "resolved_s1_peer_substitution"
RUNNER = f"quant/experiments/exp_20260703_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

MAP_DIR = REPO_ROOT / "data" / "non_ohlcv" / "entity_exposure_map"
EVENT_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
COLD_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
HOT_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260703_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
HORIZON_PRIMARY = 10
HORIZON_SECONDARY = 5
MIN_ROWS_PER_WINDOW = 100
MIN_POSITIVE_POOLED_DELTA_BP = 25.0
MAX_TOP_TICKER_SHARE = 0.05

HYPOTHESIS = (
    "Resolved listed-issuer S-1/F-1 overhang may redirect capital into listed "
    "SIC/theme peers, so peers should show positive next-open 10d SPY-excess "
    "versus same-peer unconditional baselines across canonical windows."
)
ALPHA_HYPOTHESIS = (
    "If the peer-substitution sign is stable, a later shared-paper-first "
    "experiment can test resolved S-1/F-1 overhang as a default-off peer "
    "candidate source or allocator context."
)
SINGLE_CAUSAL_VARIABLE = (
    "resolved_s1_f1_issuer_overhang_peer_substitution_10d_spy_excess_v1"
)
CAUSAL_COMPONENTS = [
    "resolved issuer S-1/F-1 event rows",
    "entity exposure map peer join",
    "next-open 10d SPY-excess",
    "same-peer unconditional baseline",
    "read-only no strategy change",
]
NEARBY_PRIORS = [
    "exp-20260702-023",
    "exp-20260702-024",
    "exp-20260702-018",
    "exp-20260702-017",
]
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260703_009_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def window_of(date_text: str) -> str | None:
    for name, start, end in WINDOWS:
        if start <= date_text <= end:
            return name
    return None


def load_frames(tickers: set[str]) -> dict[str, pd.DataFrame]:
    cold = load_warehouse_ohlcv_frames(
        COLD_DB, tickers, "2024-09-02", "2026-07-02"
    )
    hot = {}
    if HOT_DB.exists():
        hot = load_warehouse_ohlcv_frames(
            HOT_DB, tickers, "2024-09-02", "2026-07-02"
        )
    frames: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        parts = [
            frame for frame in (cold.get(ticker), hot.get(ticker)) if frame is not None
        ]
        if not parts:
            continue
        merged = pd.concat(parts)
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        frames[ticker] = merged
    return frames


def excess_return(
    frame: pd.DataFrame,
    spy: pd.DataFrame,
    entry_date: pd.Timestamp,
    horizon: int,
) -> float | None:
    if entry_date not in frame.index or entry_date not in spy.index:
        return None
    pos = frame.index.get_loc(entry_date)
    spy_pos = spy.index.get_loc(entry_date)
    exit_pos = pos + horizon - 1
    spy_exit_pos = spy_pos + horizon - 1
    if exit_pos >= len(frame.index) or spy_exit_pos >= len(spy.index):
        return None
    if frame.index[exit_pos] != spy.index[spy_exit_pos]:
        return None
    entry_open = float(frame.iloc[pos]["Open"])
    exit_close = float(frame.iloc[exit_pos]["Close"])
    spy_open = float(spy.iloc[spy_pos]["Open"])
    spy_close = float(spy.iloc[spy_exit_pos]["Close"])
    if entry_open <= 0 or spy_open <= 0:
        return None
    return (exit_close / entry_open - 1.0) - (spy_close / spy_open - 1.0)


def load_entities() -> dict[str, dict[str, Any]]:
    path = MAP_DIR / "entities.jsonl"
    return {row.get("cik"): row for row in read_jsonl(path) if row.get("cik")}


def load_event_rows() -> list[dict[str, Any]]:
    forms = {"S-1", "S-1/A", "F-1", "F-1/A"}
    return [
        row
        for row in read_jsonl(EVENT_ROWS)
        if row.get("event_class") == "ipo_registration"
        and row.get("ticker_status") == "resolved"
        and row.get("form_type") in forms
        and window_of(str(row.get("filed_date") or ""))
    ]


def build_peer_edges() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = load_event_rows()
    entities = load_entities()
    sic_index = read_json(MAP_DIR / "sic_peer_index.json", {"by_sic": {}})
    overlay = read_json(MAP_DIR / "theme_overlay.json", {"themes": []})
    stats: dict[str, Any] = {
        "source_rows": len(events),
        "source_rows_by_form": dict(
            sorted(Counter(str(event.get("form_type") or "") for event in events).items())
        ),
        "source_rows_by_window": dict(
            sorted(Counter(window_of(str(event.get("filed_date"))) for event in events).items())
        ),
        "blank_check_skipped": 0,
        "events_with_peer_edges": 0,
    }

    edges: list[dict[str, Any]] = []
    for event in events:
        entity = entities.get(event.get("cik"))
        if entity and entity.get("is_blank_check"):
            stats["blank_check_skipped"] += 1
            continue
        issuer_ticker = str(event.get("ticker") or "").upper()
        event_edges = []
        for edge in map_event_to_exposures(event, entity, sic_index, overlay):
            ticker = str(edge.get("ticker") or "").upper()
            if not ticker or ticker == issuer_ticker:
                continue
            if edge.get("relation_type") not in {"sic_peer", "theme_peer"}:
                continue
            event_edges.append(
                {
                    **edge,
                    "ticker": ticker,
                    "issuer_ticker": issuer_ticker or None,
                    "event_form_type": event.get("form_type"),
                    "ticker_status": event.get("ticker_status"),
                }
            )
        if event_edges:
            stats["events_with_peer_edges"] += 1
            edges.extend(event_edges)

    stats.update(
        {
            "peer_edges": len(edges),
            "unique_peer_tickers": len({edge["ticker"] for edge in edges}),
            "relation_counts": dict(
                sorted(Counter(edge.get("relation_type") or "missing" for edge in edges).items())
            ),
            "theme_counts": dict(
                sorted(Counter(edge.get("theme") or "missing" for edge in edges).items())
            ),
        }
    )
    return edges, stats


def build_settled_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    edges, stats = build_peer_edges()
    tickers = {edge["ticker"] for edge in edges} | {"SPY"}
    frames = load_frames(tickers)
    spy = frames.get("SPY")
    if spy is None:
        raise SystemExit("SPY missing from warehouse frames")

    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    missing_frame = 0
    no_later_open = 0
    for edge in edges:
        ticker = str(edge["ticker"]).upper()
        frame = frames.get(ticker)
        if frame is None:
            missing_frame += 1
            continue
        after = frame.index[frame.index > pd.Timestamp(edge["filed_date"])]
        if not len(after):
            no_later_open += 1
            continue
        entry_date = after[0]
        key = (ticker, str(entry_date.date()))
        row = rows_by_key.get(key)
        if row is None:
            rows_by_key[key] = {
                "ticker": ticker,
                "entry_date": str(entry_date.date()),
                "relation_types": [edge.get("relation_type")],
                "themes": [edge.get("theme")],
                "event_accessions": [edge.get("event_accession")],
                "issuer_tickers": [edge.get("issuer_ticker")],
                "primary_entities": [edge.get("primary_entity_name")],
                "match_bases": [edge.get("match_basis")],
            }
        else:
            row["relation_types"].append(edge.get("relation_type"))
            row["themes"].append(edge.get("theme"))
            row["event_accessions"].append(edge.get("event_accession"))
            row["issuer_tickers"].append(edge.get("issuer_ticker"))
            row["primary_entities"].append(edge.get("primary_entity_name"))
            row["match_bases"].append(edge.get("match_basis"))

    settled_rows: list[dict[str, Any]] = []
    unsettled = 0
    for row in rows_by_key.values():
        frame = frames[row["ticker"]]
        entry = pd.Timestamp(row["entry_date"])
        ex10 = excess_return(frame, spy, entry, HORIZON_PRIMARY)
        ex5 = excess_return(frame, spy, entry, HORIZON_SECONDARY)
        if ex10 is None:
            unsettled += 1
            continue
        settled_rows.append(
            {
                **row,
                "relation_types": sorted({v for v in row["relation_types"] if v}),
                "themes": sorted({v for v in row["themes"] if v}),
                "event_accessions": sorted({v for v in row["event_accessions"] if v}),
                "issuer_tickers": sorted({v for v in row["issuer_tickers"] if v}),
                "primary_entities": sorted({v for v in row["primary_entities"] if v}),
                "match_bases": sorted({v for v in row["match_bases"] if v}),
                "event_count": len({v for v in row["event_accessions"] if v}),
                "issuer_count": len({v for v in row["issuer_tickers"] if v}),
                "excess_10d": round(ex10, 6),
                "excess_5d": round(ex5, 6) if ex5 is not None else None,
            }
        )

    stats.update(
        {
            "edges_missing_frame": missing_frame,
            "edges_no_later_open": no_later_open,
            "deduped_rows": len(rows_by_key),
            "settled_rows": len(settled_rows),
            "unsettled_rows": unsettled,
        }
    )
    return stats, settled_rows


def build_unconditional_baselines(
    settled_rows: list[dict[str, Any]],
    frames: dict[str, pd.DataFrame],
    spy: pd.DataFrame,
) -> dict[tuple[str, str], dict[str, float | None]]:
    baselines: dict[tuple[str, str], dict[str, float | None]] = {}
    for name, start, end in WINDOWS:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        for ticker in {row["ticker"] for row in settled_rows}:
            frame = frames[ticker]
            days = frame.index[(frame.index >= start_ts) & (frame.index <= end_ts)]
            vals10: list[float] = []
            vals5: list[float] = []
            for day in days:
                value10 = excess_return(frame, spy, day, HORIZON_PRIMARY)
                if value10 is not None:
                    vals10.append(value10)
                value5 = excess_return(frame, spy, day, HORIZON_SECONDARY)
                if value5 is not None:
                    vals5.append(value5)
            if vals10:
                baselines[(ticker, name)] = {
                    "b10": median(vals10),
                    "b5": median(vals5) if vals5 else None,
                }
    return baselines


def analyze() -> dict[str, Any]:
    source_stats, settled_rows = build_settled_rows()
    tickers = {row["ticker"] for row in settled_rows} | {"SPY"}
    frames = load_frames(tickers)
    spy = frames["SPY"]
    baselines = build_unconditional_baselines(settled_rows, frames, spy)

    enriched_rows: list[dict[str, Any]] = []
    pooled_deltas: list[float] = []
    per_window: dict[str, Any] = {}
    for row in settled_rows:
        name = window_of(row["entry_date"])
        if not name:
            continue
        base = baselines.get((row["ticker"], name))
        if base is None:
            continue
        delta10 = float(row["excess_10d"]) - float(base["b10"])
        delta5 = None
        if row.get("excess_5d") is not None and base.get("b5") is not None:
            delta5 = float(row["excess_5d"]) - float(base["b5"])
        enriched_rows.append(
            {
                **row,
                "window": name,
                "delta_10d": round(delta10, 6),
                "delta_5d": round(delta5, 6) if delta5 is not None else None,
            }
        )

    for name, _start, _end in WINDOWS:
        w_rows = [row for row in enriched_rows if row["window"] == name]
        deltas10 = [float(row["delta_10d"]) for row in w_rows]
        deltas5 = [
            float(row["delta_5d"]) for row in w_rows if row.get("delta_5d") is not None
        ]
        raws10 = [float(row["excess_10d"]) for row in w_rows]
        pooled_deltas.extend(deltas10)
        ticker_counts = Counter(row["ticker"] for row in w_rows)
        top_ticker, top_n = (
            ticker_counts.most_common(1)[0] if ticker_counts else (None, 0)
        )
        top_share = round(top_n / len(w_rows), 3) if w_rows else None
        relation_counts = Counter(
            relation for row in w_rows for relation in row.get("relation_types", [])
        )
        per_window[name] = {
            "rows": len(deltas10),
            "median_event_excess_10d_bp": round(1e4 * median(raws10), 1)
            if raws10
            else None,
            "median_delta_10d_bp": round(1e4 * median(deltas10), 1)
            if deltas10
            else None,
            "mean_delta_10d_bp": round(1e4 * sum(deltas10) / len(deltas10), 1)
            if deltas10
            else None,
            "median_delta_5d_bp": round(1e4 * median(deltas5), 1)
            if deltas5
            else None,
            "positive_share": round(sum(1 for value in deltas10 if value > 0) / len(deltas10), 3)
            if deltas10
            else None,
            "top_ticker": top_ticker,
            "top_ticker_share": top_share,
            "relation_counts": dict(sorted(relation_counts.items())),
        }

    pooled_median_bp = round(1e4 * median(pooled_deltas), 1) if pooled_deltas else None
    positive_all_windows = all(
        (per_window[name]["median_delta_10d_bp"] or 0.0) > 0.0
        for name, _start, _end in WINDOWS
    )
    rows_ok = all(
        per_window[name]["rows"] >= MIN_ROWS_PER_WINDOW
        for name, _start, _end in WINDOWS
    )
    concentration_ok = all(
        (per_window[name]["top_ticker_share"] or 1.0) <= MAX_TOP_TICKER_SHARE
        for name, _start, _end in WINDOWS
    )
    pooled_ok = (
        pooled_median_bp is not None
        and pooled_median_bp >= MIN_POSITIVE_POOLED_DELTA_BP
    )
    lead = bool(positive_all_windows and rows_ok and concentration_ok and pooled_ok)
    return {
        **source_stats,
        "per_window": per_window,
        "pooled_rows": len(pooled_deltas),
        "pooled_median_delta_10d_bp": pooled_median_bp,
        "positive_all_windows": positive_all_windows,
        "rows_threshold_ok": rows_ok,
        "concentration_ok": concentration_ok,
        "pooled_positive_threshold_ok": pooled_ok,
        "observed_only_lead": lead,
        "verdict_rule": (
            "lead iff every canonical window median 10d delta is positive, "
            f"pooled median delta >= {MIN_POSITIVE_POOLED_DELTA_BP}bp, "
            f">= {MIN_ROWS_PER_WINDOW} settled rows per window, and top ticker "
            f"share <= {MAX_TOP_TICKER_SHARE:.0%} in each window"
        ),
        "row_sample": enriched_rows[:50],
    }


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def failure_reasons(report: dict[str, Any]) -> list[str]:
    reasons = []
    if not report["positive_all_windows"]:
        reasons.append("not_positive_all_windows")
    if not report["rows_threshold_ok"]:
        reasons.append("rows_below_threshold")
    if not report["concentration_ok"]:
        reasons.append("top_ticker_concentration")
    if not report["pooled_positive_threshold_ok"]:
        reasons.append("pooled_positive_delta_below_threshold")
    return reasons


def calibrate(ticket_prediction: dict[str, Any], lead: bool, reasons: list[str]) -> dict[str, Any]:
    probability = float(ticket_prediction.get("success_probability") or 0.0)
    actual = 1.0 if lead else 0.0
    predicted_modes = list(ticket_prediction.get("main_failure_modes") or [])
    reason_text = " ".join(reasons)
    hits = [
        mode
        for mode in predicted_modes
        if (
            ("noisy" in mode and ("positive" in reason_text or "pooled" in reason_text))
            or ("sign" in mode and "positive" in reason_text)
            or ("priced" in mode and "pooled" in reason_text)
            or ("concentration" in mode and "concentration" in reason_text)
            or ("saturation" in mode and "positive" in reason_text)
        )
    ]
    return {
        "predicted_success_probability": probability,
        "actual_success": 1 if lead else 0,
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": reasons or ["observed_only_positive_lead_not_promoted"],
        "predicted_failure_modes_hit": hits,
        "surprise_note": (
            "Resolved S-1/F-1 peer substitution met the observed-only lead rule."
            if lead
            else "Resolved S-1/F-1 peer substitution did not meet the observed-only lead rule."
        ),
    }


def build_payload(report: dict[str, Any]) -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = dict(ticket.get("prediction") or {})
    baseline = load_baseline_metrics()
    lead = bool(report["observed_only_lead"])
    reasons = [] if lead else failure_reasons(report)
    decision = (
        "observed_only_positive_resolved_s1_peer_substitution_lead_not_promoted"
        if lead
        else "rejected_no_resolved_s1_peer_substitution_edge"
    )
    why = (
        "Resolved listed-issuer S-1/F-1 overhang produced a stable positive "
        "peer delta versus same-peer baselines; this remains only an observed-only "
        "lead because no shared helper or daily path changed."
        if lead
        else "Resolved listed-issuer S-1/F-1 overhang did not produce a stable "
        "positive peer delta versus same-peer baselines across canonical windows."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "alpha_search",
        "status": "observed_only" if lead else "rejected",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": lead,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_diagnostic",
        "mechanism_family": "production_visible_sec_corporate_event_stream",
        "trial_family": "resolved_s1_f1_peer_substitution_attribution",
        "trial_variant_id": "resolved_s1_f1_peer_substitution_10d_spy_excess_v1",
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": "none_read_only",
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_target_side_relation_join",
        "new_evidence_axis": (
            "new target-side relation: resolved listed-issuer S-1/F-1 overhang "
            "to listed SIC/theme peers. Prior exp-20260702-023 tested issuer-self "
            "overhang; prior peer reads tested private IPO and 425 event classes."
        ),
        "prediction": prediction,
        "calibration": calibrate(prediction, lead, reasons),
        "audit": report,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted without override.",
                "nearby_prior_experiments": NEARBY_PRIORS,
                "new_evidence_axis": (
                    "target-side peer substitution after resolved listed-issuer "
                    "S-1/F-1 overhang, not issuer-self overhang or a private-IPO/425 "
                    "theme-peer rerun"
                ),
            },
            "3_single_policy_bundle": (
                "Read-only attribution: resolved listed-issuer S-1/F-1 rows, "
                "SIC/theme peer targets, next-open 10d SPY-excess versus same-peer "
                "unconditional baselines."
            ),
            "4_success_failure_standard": report["verdict_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": True,
            "fields": [
                "event_class",
                "ticker_status",
                "form_type",
                "filed_date",
                "ticker",
                "relation_type",
                "entry_date",
                "Open/Close warehouse bars",
            ],
            "target_price_scope": "not_applicable_observed_only_fixed_horizon",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter or rank rule was added.",
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
        },
        "gate4": {
            "mode": "observed_only_attribution",
            "passed": False,
            "observed_only_lead": lead,
            "failed_reasons": reasons,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "parity_note": "Read-only attribution; no production or backtest behavior changed.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not re-slice the same resolved S-1/F-1 peer rows by relation "
                "type, theme subset, amendment flag, form subtype, horizon, entry "
                "lag, ticker-status, density, top-N, hold, cooldown, notional, or "
                "response shape."
            ),
            "new_evidence_required": (
                "A valid retry needs richer offering economics such as registered "
                "amount, resale versus primary issuance, selling-holder identity, "
                "effectiveness date, prospectus-supplement terms, or fresh forward "
                "rows under a shared helper."
            ),
        },
        "next_retry_requires": [
            "registered amount or resale-vs-primary offering fields",
            "selling-holder or effectiveness-date provenance",
            "fresh forward rows under a shared helper",
        ],
        "rejection_reason": None if lead else ";".join(reasons),
        "related_files": [
            repo_rel(EVENT_ROWS),
            repo_rel(MAP_DIR / "sic_peer_index.json"),
            repo_rel(MAP_DIR / "theme_overlay.json"),
            repo_rel(MAP_DIR / "entities.jsonl"),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "reproduction_commands": [RUNNER_COMMAND],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner, py_compile, and experiment audit only.",
        },
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "rejection_reason",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    record = {key: payload[key] for key in keys}
    audit = payload["audit"]
    record["audit_summary"] = {
        "source_rows": audit["source_rows"],
        "peer_edges": audit["peer_edges"],
        "settled_rows": audit["settled_rows"],
        "pooled_median_delta_10d_bp": audit["pooled_median_delta_10d_bp"],
        "observed_only_lead": audit["observed_only_lead"],
        "per_window": {
            name: {
                "rows": window["rows"],
                "median_delta_10d_bp": window["median_delta_10d_bp"],
                "positive_share": window["positive_share"],
            }
            for name, window in audit["per_window"].items()
        },
    }
    return record


def build_card(payload: dict[str, Any]) -> str:
    report = payload["audit"]
    lines = [
        f"# {EXPERIMENT_ID}: resolved S-1/F-1 peer substitution",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        "- Production behavior changed: no",
        f"- Source rows: `{report['source_rows']}`",
        f"- Peer edges: `{report['peer_edges']}`",
        f"- Settled deduped rows: `{report['settled_rows']}`",
        f"- Pooled median 10d delta: `{report['pooled_median_delta_10d_bp']}bp`",
        f"- Observed-only lead: `{report['observed_only_lead']}`",
        "",
        "## Per Window",
        "",
    ]
    for name, window in report["per_window"].items():
        lines.append(
            f"- `{name}`: n={window['rows']}, median delta "
            f"{window['median_delta_10d_bp']}bp, mean "
            f"{window['mean_delta_10d_bp']}bp, positive share "
            f"{window['positive_share']}, top ticker {window['top_ticker']} "
            f"({window['top_ticker_share']})"
        )
    lines += [
        "",
        "## Gate Rule",
        "",
        report["verdict_rule"],
        "",
        "## Reproduction",
        "",
        f"```powershell\n{RUNNER_COMMAND}\n```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EVENT_ROWS,
        MAP_DIR / "sic_peer_index.json",
        MAP_DIR / "theme_overlay.json",
        MAP_DIR / "entities.jsonl",
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": CHANGED_FILES,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))

    fields = {
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
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
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
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    report = analyze()
    payload = build_payload(report)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "source_rows": report["source_rows"],
                "peer_edges": report["peer_edges"],
                "settled_rows": report["settled_rows"],
                "pooled_median_delta_10d_bp": report["pooled_median_delta_10d_bp"],
                "observed_only_lead": report["observed_only_lead"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
