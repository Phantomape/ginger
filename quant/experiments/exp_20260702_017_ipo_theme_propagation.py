"""exp-20260702-017: IPO theme-peer propagation attribution (read-only).

Alpha-lane observed-only read. Tests whether fresh S-1/F-1 IPO registrations
by PRIVATE primary entities (unresolved ticker, non-blank-check) propagate
measurable forward price impact to theme-peer listed tickers mapped by the
entity_exposure_map v1 theme overlay.

Fixed predeclared bundle (ticket exp-20260702-017):
- events: fresh non-amendment S-1/F-1 rows (exp-20260702-008) whose primary
  entity has no listed ticker and is not a blank-check SPAC;
- edges: theme_peer only (sic_peer is deliberately out of scope);
- entry: peer next warehouse open strictly after filed_date; exit: close of
  the 10th trading session (5d secondary);
- metric: SPY-excess return; control: the same ticker's unconditional
  same-window open->10d-close SPY-excess median over all entry days;
- dedup: unique (ticker, entry_date);
- verdict: observed-only lead only if the median event-minus-baseline delta
  has the SAME sign in all three canonical windows and pooled |delta| >= 25bp
  with >= 30 deduped settled rows per window; otherwise no edge.

Direction is NOT predeclared. No strategy behavior change either way.
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
from entity_exposure_map import map_event_to_exposures  # noqa: E402
from ohlcv_warehouse import load_warehouse_ohlcv_frames  # noqa: E402

EXPERIMENT_ID = "exp-20260702-017"
OWNER = "daniel-agent"
SLUG = "ipo_theme_propagation"
RUNNER = f"quant/experiments/exp_20260702_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

MAP_DIR = REPO_ROOT / "data" / "non_ohlcv" / "entity_exposure_map"
EVENT_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream" / "rows.jsonl"
)
COLD_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
HOT_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_017_{SLUG}.json"
ROWS_OUT = DATA_DIR / "propagation_rows.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
HORIZON_PRIMARY = 10
HORIZON_SECONDARY = 5
MIN_ROWS_PER_WINDOW = 30
MIN_POOLED_DELTA_BP = 25.0

CHANGED_FILES = [
    f"quant/experiments/exp_20260702_017_{SLUG}.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_017_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/propagation_rows.jsonl",
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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_frames(tickers: set[str]) -> dict[str, pd.DataFrame]:
    cold = load_warehouse_ohlcv_frames(
        COLD_DB, tickers, "2024-09-02", "2026-07-02"
    )
    hot = {}
    if HOT_DB.exists():
        hot = load_warehouse_ohlcv_frames(
            HOT_DB, tickers, "2024-09-02", "2026-07-02"
        )
    frames = {}
    for ticker in tickers:
        parts = [f for f in (cold.get(ticker), hot.get(ticker)) if f is not None]
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
    """Open(entry) -> Close(entry + horizon-1 sessions), minus SPY same span."""
    if entry_date not in frame.index or entry_date not in spy.index:
        return None
    pos = frame.index.get_loc(entry_date)
    spy_pos = spy.index.get_loc(entry_date)
    exit_pos = pos + horizon - 1
    spy_exit_pos = spy_pos + horizon - 1
    if exit_pos >= len(frame.index) or spy_exit_pos >= len(spy.index):
        return None
    if frame.index[exit_pos] != spy.index[spy_exit_pos]:
        # calendar mismatch (per-ticker data gap) -> treat as unsettled
        return None
    entry_open = float(frame.iloc[pos]["Open"])
    exit_close = float(frame.iloc[exit_pos]["Close"])
    spy_open = float(spy.iloc[spy_pos]["Open"])
    spy_close = float(spy.iloc[spy_exit_pos]["Close"])
    if entry_open <= 0 or spy_open <= 0:
        return None
    return (exit_close / entry_open - 1.0) - (spy_close / spy_open - 1.0)


def build_event_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = load_jsonl(EVENT_ROWS)
    entities = {
        e["cik"]: e
        for e in load_jsonl(MAP_DIR / "entities.jsonl")
        if e.get("cik")
    }
    sic_index = json.loads(
        (MAP_DIR / "sic_peer_index.json").read_text(encoding="utf-8")
    )
    overlay = json.loads(
        (MAP_DIR / "theme_overlay.json").read_text(encoding="utf-8")
    )

    fresh = [
        e
        for e in events
        if e["event_class"] == "ipo_registration"
        and not e["is_amendment"]
        and e.get("ticker_status") == "unresolved"
    ]
    stats = {"fresh_private_events": len(fresh), "blank_check_skipped": 0}
    edges = []
    for event in fresh:
        entity = entities.get(event["cik"])
        if entity and entity.get("is_blank_check"):
            stats["blank_check_skipped"] += 1
            continue
        # private check again on entity record: no listed ticker
        if entity and entity.get("tickers"):
            continue
        for edge in map_event_to_exposures(event, entity, sic_index, overlay):
            if edge["relation_type"] == "theme_peer":
                edges.append(edge)
    stats["theme_edges"] = len(edges)
    return edges, stats


def run_attribution() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    edges, stats = build_event_rows()
    tickers = {e["ticker"] for e in edges} | {"SPY"}
    frames = load_frames(tickers)
    spy = frames.get("SPY")
    if spy is None:
        raise SystemExit("SPY missing from warehouse")

    # dedup: unique (ticker, entry_date)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    missing_frame = 0
    for edge in edges:
        frame = frames.get(edge["ticker"])
        if frame is None:
            missing_frame += 1
            continue
        after = frame.index[frame.index > pd.Timestamp(edge["filed_date"])]
        if not len(after):
            continue
        entry_date = after[0]
        key = (edge["ticker"], str(entry_date.date()))
        row = rows.get(key)
        if row is None:
            rows[key] = {
                "ticker": edge["ticker"],
                "entry_date": str(entry_date.date()),
                "themes": [edge["theme"]],
                "event_accessions": [edge["event_accession"]],
                "primary_entities": [edge["primary_entity_name"]],
            }
        else:
            row["themes"].append(edge["theme"])
            row["event_accessions"].append(edge["event_accession"])
            row["primary_entities"].append(edge["primary_entity_name"])

    settled_rows = []
    unsettled = 0
    for row in rows.values():
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
                "themes": sorted(set(row["themes"])),
                "event_count": len(set(row["event_accessions"])),
                "excess_10d": round(ex10, 6),
                "excess_5d": round(ex5, 6) if ex5 is not None else None,
            }
        )

    # unconditional per-(ticker, window) baseline medians
    baselines: dict[tuple[str, str], dict[str, float]] = {}
    for name, start, end in WINDOWS:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        for ticker in {r["ticker"] for r in settled_rows}:
            frame = frames[ticker]
            days = frame.index[(frame.index >= s) & (frame.index <= e)]
            vals10, vals5 = [], []
            for day in days:
                v10 = excess_return(frame, spy, day, HORIZON_PRIMARY)
                if v10 is not None:
                    vals10.append(v10)
                v5 = excess_return(frame, spy, day, HORIZON_SECONDARY)
                if v5 is not None:
                    vals5.append(v5)
            if vals10:
                baselines[(ticker, name)] = {
                    "b10": median(vals10),
                    "b5": median(vals5) if vals5 else None,
                }

    def window_of(date_text: str) -> str | None:
        for name, start, end in WINDOWS:
            if start <= date_text <= end:
                return name
        return None

    per_window: dict[str, Any] = {}
    pooled_deltas: list[float] = []
    for name, start, end in WINDOWS:
        w_rows = [r for r in settled_rows if window_of(r["entry_date"]) == name]
        deltas10, deltas5, raws = [], [], []
        for row in w_rows:
            base = baselines.get((row["ticker"], name))
            if base is None:
                continue
            delta10 = row["excess_10d"] - base["b10"]
            row[f"delta_10d_{name}"] = round(delta10, 6)
            deltas10.append(delta10)
            raws.append(row["excess_10d"])
            if row["excess_5d"] is not None and base["b5"] is not None:
                deltas5.append(row["excess_5d"] - base["b5"])
        pooled_deltas.extend(deltas10)
        ticker_counter = Counter(r["ticker"] for r in w_rows)
        top_ticker, top_n = (
            ticker_counter.most_common(1)[0] if ticker_counter else (None, 0)
        )
        per_window[name] = {
            "rows": len(deltas10),
            "median_event_excess_10d_bp": round(1e4 * median(raws), 1) if raws else None,
            "median_delta_10d_bp": round(1e4 * median(deltas10), 1) if deltas10 else None,
            "mean_delta_10d_bp": round(1e4 * sum(deltas10) / len(deltas10), 1)
            if deltas10
            else None,
            "median_delta_5d_bp": round(1e4 * median(deltas5), 1) if deltas5 else None,
            "positive_share": round(
                sum(1 for d in deltas10 if d > 0) / len(deltas10), 3
            )
            if deltas10
            else None,
            "top_ticker": top_ticker,
            "top_ticker_share": round(top_n / len(w_rows), 3) if w_rows else None,
        }

    signs = [
        per_window[name]["median_delta_10d_bp"]
        for name, _, _ in WINDOWS
        if per_window[name]["median_delta_10d_bp"] is not None
    ]
    sign_consistent = len(signs) == 3 and (
        all(s > 0 for s in signs) or all(s < 0 for s in signs)
    )
    rows_ok = all(per_window[name]["rows"] >= MIN_ROWS_PER_WINDOW for name, _, _ in WINDOWS)
    pooled_median_bp = round(1e4 * median(pooled_deltas), 1) if pooled_deltas else None
    pooled_ok = (
        pooled_median_bp is not None and abs(pooled_median_bp) >= MIN_POOLED_DELTA_BP
    )
    lead = bool(sign_consistent and rows_ok and pooled_ok)

    report = {
        **stats,
        "edges_missing_frame": missing_frame,
        "deduped_rows": len(rows),
        "settled_rows": len(settled_rows),
        "unsettled_rows": unsettled,
        "per_window": per_window,
        "pooled_median_delta_10d_bp": pooled_median_bp,
        "pooled_rows": len(pooled_deltas),
        "sign_consistent": sign_consistent,
        "rows_threshold_ok": rows_ok,
        "pooled_delta_threshold_ok": pooled_ok,
        "observed_only_lead": lead,
        "verdict_rule": (
            f"lead iff same-sign median delta in all 3 windows and pooled "
            f"|delta| >= {MIN_POOLED_DELTA_BP}bp and >= {MIN_ROWS_PER_WINDOW} "
            "rows per window"
        ),
    }
    return report, settled_rows


def build_payload(report: dict[str, Any]) -> dict[str, Any]:
    lead = report["observed_only_lead"]
    decision = (
        "observed_only_positive_ipo_theme_peer_propagation_lead_not_promoted"
        if lead
        else "observed_only_no_ipo_theme_peer_propagation_edge"
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
            "Fresh private-entity S-1/F-1 IPO registrations propagate 10d "
            "SPY-excess impact to theme-peer listed tickers versus the peers' "
            "unconditional same-window baseline, with consistent sign across "
            "all three canonical windows."
        ),
        "alpha_hypothesis": (
            "If a stable sign exists, a later shared-paper-first full-stack "
            "experiment can turn theme-peer propagation into a default-off "
            "candidate source or de-allocation context."
        ),
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_diagnostic",
        "mechanism_family": "production_visible_sec_corporate_event_stream",
        "trial_family": "ipo_theme_peer_propagation_attribution",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": "ipo_theme_peer_propagation_10d_spy_excess_v1",
        "changed_variable": "none_read_only",
        "causal_components": [
            "fresh_nonamendment_s1_f1_only",
            "private_unresolved_primary_only",
            "blank_check_excluded",
            "theme_peer_edges_only",
            "next_open_entry",
            "10d_close_exit_5d_secondary",
            "spy_excess_metric",
            "unique_ticker_entrydate_dedup",
            "unconditional_same_window_baseline_control",
        ],
        "nearby_prior_experiments": [
            "exp-20260702-008",
            "exp-20260702-009",
            "exp-20260630-017",
            "exp-20260622-006",
            "exp-20260618-016",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_data_source_event_relation_join",
        "new_evidence_axis": (
            "first relation surface keyed on non-tradable primary entities "
            "(private IPO registrants) joined to listed theme peers"
        ),
        "audit": report,
        "gate1": {"note": "read-only; canonical baseline unchanged"},
        "gate2": {
            "fields": [
                "filed_date",
                "theme",
                "ticker",
                "Open/Close warehouse bars",
            ],
            "note": "all inputs PIT: filing date from EDGAR index, bars from warehouse",
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
                    ("sign_not_consistent", report["sign_consistent"]),
                    ("rows_below_threshold", report["rows_threshold_ok"]),
                    ("pooled_delta_below_threshold", report["pooled_delta_threshold_ok"]),
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
            "why_result_happened": "",  # filled in main() after seeing report
            "forbidden_near_neighbor_retry": (
                "Do not re-slice this same event population by theme subset, "
                "keyword tweak, horizon, entry lag, density cut, or SIC-peer "
                "edges to manufacture a lead. A valid retry needs a new event "
                "class (425 merger side), amendment/withdrawal trajectory, "
                "priced-deal terms (S-1/A pricing range), or closed forward "
                "rows under a shared helper."
            ),
            "new_evidence_required": (
                "Either a stable sign here (then shared-paper-first full "
                "stack), or richer event provenance: pricing-range "
                "amendments, deal size vs theme float, first-trade dates."
            ),
        },
        "related_files": [
            "data/non_ohlcv/sec_corporate_event_stream/rows.jsonl",
            "data/non_ohlcv/entity_exposure_map/theme_overlay.json",
        ],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    report = payload["audit"]
    lines = [
        f"# {EXPERIMENT_ID}: IPO theme-peer propagation attribution",
        "",
        f"- status: `{payload['status']}` / decision: `{payload['decision']}`",
        f"- settled rows: `{report['settled_rows']}` "
        f"(deduped `{report['deduped_rows']}`, unsettled `{report['unsettled_rows']}`)",
        f"- pooled median delta 10d: `{report['pooled_median_delta_10d_bp']}bp` "
        f"over `{report['pooled_rows']}` rows",
        f"- verdict: lead=`{report['observed_only_lead']}` "
        f"(sign_consistent=`{report['sign_consistent']}`)",
        "",
        "## Per window (delta vs unconditional same-ticker baseline)",
        "",
    ]
    for name, window in report["per_window"].items():
        lines.append(
            f"- `{name}`: n={window['rows']}, median delta "
            f"{window['median_delta_10d_bp']}bp, mean {window['mean_delta_10d_bp']}bp, "
            f"5d {window['median_delta_5d_bp']}bp, pos share "
            f"{window['positive_share']}, top {window['top_ticker']} "
            f"({window['top_ticker_share']})"
        )
    lines += [
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
        "settled_rows": payload["audit"]["settled_rows"],
        "pooled_median_delta_10d_bp": payload["audit"]["pooled_median_delta_10d_bp"],
        "observed_only_lead": payload["audit"]["observed_only_lead"],
        "per_window": {
            name: {
                "rows": w["rows"],
                "median_delta_10d_bp": w["median_delta_10d_bp"],
            }
            for name, w in payload["audit"]["per_window"].items()
        },
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
    report, settled_rows = run_attribution()
    payload = build_payload(report)
    lead = report["observed_only_lead"]
    payload["post_run_reflection"]["why_result_happened"] = (
        (
            "Theme-peer tickers showed a same-sign median 10d SPY-excess delta "
            "vs their unconditional baseline in all three canonical windows; "
            "this is an observed-only lead, not a promoted helper."
        )
        if lead
        else (
            "The event-conditioned 10d SPY-excess of theme peers did not "
            "separate from the same tickers' unconditional baseline with a "
            "stable sign across the three canonical windows, so fresh private "
            "IPO registration flow, as mapped by theme overlay v1, is not a "
            "tradable propagation signal on its own."
        )
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, OUT_JSON)
    atomic_write_text(
        "\n".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) for r in settled_rows
        )
        + "\n",
        ROWS_OUT,
    )
    log_record = compact_log_record(payload)
    atomic_write_json(log_record, LOG_JSON)
    atomic_write_text(build_card(payload), CARD_MD)
    upsert_experiment_log(log_record)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction={
            "success_probability": 0.3,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "peer moves already priced by next open",
                "theme edges dominated by biotech beta",
                "per-window N too thin outside biotech",
                "sign flips across windows",
            ],
            "confidence_reason": (
                "new relation axis with dense rows, but relation-alpha base "
                "rate is low and characteristic-similarity peers just failed"
            ),
        },
        result={
            "accepted": False,
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": lead,
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
            for p in (REPO_ROOT / RUNNER, OUT_JSON, ROWS_OUT, LOG_JSON, CARD_MD)
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
                "settled_rows": report["settled_rows"],
                "pooled_median_delta_10d_bp": report["pooled_median_delta_10d_bp"],
                "per_window": {
                    name: {
                        "rows": w["rows"],
                        "median_delta_10d_bp": w["median_delta_10d_bp"],
                        "positive_share": w["positive_share"],
                    }
                    for name, w in report["per_window"].items()
                },
                "observed_only_lead": report["observed_only_lead"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
