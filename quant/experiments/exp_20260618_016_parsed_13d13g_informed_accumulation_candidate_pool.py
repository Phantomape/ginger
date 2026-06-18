"""exp-20260618-016: parsed Schedule 13D/13G informed-accumulation diagnostic.

Hypothesis (candidate_pool): newly ingested *parsed structured* 13D/13G
``primary_doc.xml`` holder/stake/intent fields can separate informed
concentrated accumulation from stale index-fund passive filings; fresh
active-intent 13D or large non-Big3 13G crossings should predict positive
~10-day drift on the broad warehouse universe.

Prior raw metadata-only 13D/13G event gates were rejected (exp-20260612-015 13D,
exp-20260612-016 13G) and several June-18 readiness audits (012/013/014)
concluded the missing piece was exactly this parsed holder/stake/intent surface.
This runner builds that surface (via ``quant/sec_13d13g_ingest.py``) and runs a
PIT, read-only forward-return diagnostic to decide whether any clean tradable
subset deserves a shared-paper-first candidate-pool sleeve. No trading policy,
ranking, sizing, exits, live orders, or default trade settings are changed. No
JavaScript is used.

PIT contract: entry is the next trading session OPEN strictly after the SEC
``filing_date``; forward returns hold to the close N sessions later; SPY-excess
strips market beta over the identical calendar span.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant import sec_13d13g_ingest as ingest  # noqa: E402
from quant.ohlcv_warehouse import load_warehouse_ohlcv_frames  # noqa: E402

EXPERIMENT_ID = "exp-20260618-016"
STEM = "parsed_13d13g_informed_accumulation_candidate_pool"
CHANGED_VARIABLE = "parsed_13d13g_informed_accumulation_candidate_pool"
OWNER = "alpha-search-automation"

WAREHOUSE_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_016_{STEM}.json"
BEFORE_JSON = OUT_DIR / "before_baseline.json"
AFTER_JSON = OUT_DIR / "after_no_strategy_change.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = ingest.WINDOWS
HORIZONS = (5, 10, 20)
# Insider/control reporting-person types (not outside accumulation):
# IN = individual, HC = parent holding co, CO = corporation are often the
# issuer's own control persons in a 13D; we tag rather than hard-drop.
INSIDER_TYPES = {"IN", "HC", "CO"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    return
            except json.JSONDecodeError:
                continue
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


# --------------------------------------------------------------------------
# Baseline (Gate 1) - unchanged; this is a read-only diagnostic.
# --------------------------------------------------------------------------
def build_baseline() -> dict[str, Any]:
    raw = read_json(BASELINE_PATH, {})
    windows: dict[str, dict[str, Any]] = {}
    agg_ev = total_pnl = 0.0
    total_trades = 0
    min_surv = 1.0
    max_dd = 0.0
    for row in raw.get("windows", []):
        label = row["label"]
        windows[label] = {
            "expected_value_score": row.get("expected_value_score"),
            "total_pnl": row.get("total_pnl"),
            "max_drawdown_pct": row.get("max_drawdown_pct"),
            "survival_rate": row.get("survival_rate"),
            "trade_count": row.get("trade_count"),
        }
        agg_ev += float(row.get("expected_value_score") or 0.0)
        total_pnl += float(row.get("total_pnl") or 0.0)
        total_trades += int(row.get("trade_count") or 0)
        min_surv = min(min_surv, float(row.get("survival_rate") or 0.0))
        max_dd = max(max_dd, float(row.get("max_drawdown_pct") or 0.0))
    return {
        "source": repo_rel(BASELINE_PATH),
        "status": "passed",
        "windows": windows,
        "aggregate": {
            "aggregate_expected_value_score": round(agg_ev, 4),
            "aggregate_total_pnl": round(total_pnl, 2),
            "total_trade_count": total_trades,
            "min_survival_rate": round(min_surv, 4),
            "max_window_drawdown_pct": round(max_dd, 4),
        },
    }


# --------------------------------------------------------------------------
# Parsed 13D/13G surface (from EDGAR XML cache).
# --------------------------------------------------------------------------
def build_surface() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the combined parsed row set: 13D (init+amend) + 13G (init)."""
    d13d = ingest.iter_ownership_filings(families=("13D",), include_amendments=True)
    g13_init = [
        ev
        for ev in ingest.iter_ownership_filings(families=("13G",), include_amendments=True)
        if not ev["is_amendment"]
    ]
    events = d13d + g13_init
    built = ingest.build_parsed_rows(events, fetch=False, refresh=False)
    rows = built["rows"]

    coverage: dict[str, Any] = {"by_window": {}, "fetch_status": built["fetch_status"]}
    for label in WINDOWS:
        win_events = [e for e in events if e["window"] == label]
        win_rows = [r for r in rows if r["window"] == label]
        coverage["by_window"][label] = {
            "enumerated": len(win_events),
            "parsed": len(win_rows),
            "parse_fraction": round(len(win_rows) / len(win_events), 4) if win_events else 0.0,
            "by_family": dict(Counter((r["family"], "amend" if r["is_amendment"] else "init") for r in win_rows).most_common()),
        }
    coverage["total_enumerated"] = len(events)
    coverage["total_parsed"] = len(rows)
    return rows, coverage


# --------------------------------------------------------------------------
# Forward returns over the broad warehouse (PIT next-open entry).
# --------------------------------------------------------------------------
def _forward_returns(frame, spy, filing_date: str) -> dict[int, dict[str, float]] | None:
    import pandas as pd  # local import; pandas available via warehouse loader

    fdate = pd.Timestamp(filing_date)
    idx = frame.index
    after = idx[idx > fdate]
    if len(after) == 0:
        return None
    entry_date = after[0]
    entry_pos = idx.get_loc(entry_date)
    entry_open = float(frame.iloc[entry_pos]["Open"])
    if not math.isfinite(entry_open) or entry_open <= 0:
        return None
    out: dict[int, dict[str, float]] = {}
    for h in HORIZONS:
        exit_pos = entry_pos + h
        if exit_pos >= len(frame):
            continue
        exit_date = idx[exit_pos]
        exit_close = float(frame.iloc[exit_pos]["Close"])
        ret = exit_close / entry_open - 1.0
        excess = ret
        # SPY-relative excess over identical span.
        if spy is not None and entry_date in spy.index and exit_date in spy.index:
            s_open = float(spy.loc[entry_date, "Open"])
            s_close = float(spy.loc[exit_date, "Close"])
            if s_open > 0:
                excess = ret - (s_close / s_open - 1.0)
        out[h] = {"ret": ret, "excess": excess}
    return out or None


def attach_forward_returns(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tickers = sorted({r["ticker"] for r in rows if r["ticker"]})
    frames = load_warehouse_ohlcv_frames(
        WAREHOUSE_DB, tickers + ["SPY"], "2024-09-01", "2026-06-15"
    )
    spy = frames.get("SPY")
    enriched: list[dict[str, Any]] = []
    no_bars = 0
    no_forward = 0
    for r in rows:
        frame = frames.get(r["ticker"]) if r["ticker"] else None
        if frame is None or frame.empty:
            no_bars += 1
            continue
        fr = _forward_returns(frame, spy, r["filing_date"])
        if not fr:
            no_forward += 1
            continue
        rr = dict(r)
        rr["forward"] = fr
        enriched.append(rr)
    return enriched, {
        "rows_with_forward": len(enriched),
        "rows_missing_bars": no_bars,
        "rows_missing_forward": no_forward,
        "spy_available": spy is not None,
    }


# --------------------------------------------------------------------------
# Bucketed diagnostic.
# --------------------------------------------------------------------------
def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean_pct": round(100 * statistics.fmean(values), 3),
        "median_pct": round(100 * statistics.median(values), 3),
        "win_rate": round(sum(1 for v in values if v > 0) / len(values), 3),
    }


def _outside_activist(row: dict[str, Any]) -> bool:
    """13D where reporting persons are NOT pure issuer-control insiders.

    Heuristic: at least one non-insider type (IA/PN/OO/II/FI) present and not
    Big-3, with a non-extreme stake (<50%, i.e. a stake-building activist rather
    than a founder/control holder).
    """
    if row["family"] != "13D":
        return False
    types = set(row.get("reporting_person_types") or [])
    has_outside = bool(types - INSIDER_TYPES)
    pct = row.get("max_class_percent")
    moderate = pct is not None and pct < 50.0
    return has_outside and moderate and not row.get("is_big3")


def _fresh_concentrated_13g(row: dict[str, Any]) -> bool:
    """13G initial crossing by a non-Big3 holder with a meaningful new stake."""
    if row["family"] != "13G" or row["is_amendment"]:
        return False
    pct = row.get("max_class_percent")
    return (not row.get("is_big3")) and pct is not None and pct >= 5.0


def run_diagnostic(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def bucket_stats(subset: list[dict[str, Any]], h: int, key: str = "excess") -> dict[str, Any]:
        return _stats([r["forward"][h][key] for r in rows_in(subset) if h in r["forward"]])

    def rows_in(subset):
        return subset

    diag: dict[str, Any] = {"horizons": list(HORIZONS)}

    # Primary contrasts on forward-10d SPY-excess.
    families = {
        "13D_init": [r for r in rows if r["family"] == "13D" and not r["is_amendment"]],
        "13D_amend": [r for r in rows if r["family"] == "13D" and r["is_amendment"]],
        "13G_init": [r for r in rows if r["family"] == "13G" and not r["is_amendment"]],
        "13G_init_big3": [r for r in rows if r["family"] == "13G" and not r["is_amendment"] and r["is_big3"]],
        "13G_init_non_big3": [r for r in rows if r["family"] == "13G" and not r["is_amendment"] and not r["is_big3"]],
        "outside_activist_13d": [r for r in rows if _outside_activist(r)],
        "fresh_concentrated_13g": [r for r in rows if _fresh_concentrated_13g(r)],
    }
    diag["by_family_subset"] = {
        name: {f"h{h}_excess": bucket_stats(subset, h) for h in HORIZONS}
        for name, subset in families.items()
    }

    # Stake-size buckets (max_class_percent) for non-Big3 fresh holders.
    nb = [r for r in rows if not r["is_big3"] and r.get("max_class_percent") is not None]
    stake_buckets = {
        "5_to_7.5pct": [r for r in nb if 5.0 <= r["max_class_percent"] < 7.5],
        "7.5_to_10pct": [r for r in nb if 7.5 <= r["max_class_percent"] < 10.0],
        "10_to_20pct": [r for r in nb if 10.0 <= r["max_class_percent"] < 20.0],
        "ge_20pct": [r for r in nb if r["max_class_percent"] >= 20.0],
    }
    diag["by_stake_bucket_non_big3"] = {
        name: {f"h{h}_excess": bucket_stats(subset, h) for h in HORIZONS}
        for name, subset in stake_buckets.items()
    }

    # The two candidate-pool hypotheses, split by window (robustness check).
    for key, predicate in (
        ("outside_activist_13d_by_window", _outside_activist),
        ("fresh_concentrated_13g_by_window", _fresh_concentrated_13g),
    ):
        by_win: dict[str, Any] = {}
        for label in WINDOWS:
            subset = [r for r in rows if predicate(r) and r["window"] == label]
            by_win[label] = bucket_stats(subset, 10)
        diag[key] = by_win

    return diag, families


def assess_verdict(diag: dict[str, Any], families: dict[str, list]) -> dict[str, Any]:
    """A subset is a tradable lead only if forward-10d SPY-excess is positive
    in all three windows with adequate per-window sample (>= 8)."""
    leads = []
    for key in ("outside_activist_13d_by_window", "fresh_concentrated_13g_by_window"):
        by_win = diag[key]
        ok = all(
            by_win[label].get("n", 0) >= 8 and by_win[label].get("mean_pct", -1) > 0
            for label in WINDOWS
        )
        leads.append({"subset": key, "all_windows_positive_min8": ok, "by_window": by_win})
    any_lead = any(l["all_windows_positive_min8"] for l in leads)
    return {"leads": leads, "any_clean_tradable_lead": any_lead}


# --------------------------------------------------------------------------
# Persist.
# --------------------------------------------------------------------------
def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = build_baseline()
    rows, coverage = build_surface()
    enriched, fwd_meta = attach_forward_returns(rows)
    diag, families = run_diagnostic(enriched)
    verdict = assess_verdict(diag, families)

    decision = (
        "observed_lead_for_shared_paper_first"
        if verdict["any_clean_tradable_lead"]
        else "observed_no_clean_tradable_edge"
    )
    status = "observed_only"

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": "production_visible_sec_ownership_holder_stake_candidate_pool",
        "trial_family": "sec_13d13g_holder_stake_candidate_pool",
        "trial_variant_id": "parsed_13d13g_informed_accumulation_diagnostic_v1",
        "hypothesis": (
            "Parsed structured 13D/13G holder/stake/intent fields can separate "
            "informed concentrated accumulation from stale index-fund passive "
            "filings; fresh active-intent 13D or large non-Big3 13G crossings "
            "predict positive ~10-day drift on the broad warehouse universe."
        ),
        "novelty": {
            "override_used": True,
            "new_evidence_axis": (
                "Newly ingested parsed structured 13D/13G primary_doc.xml holder "
                "identity, beneficial-ownership classPercent, reporting-person "
                "type, and active/passive intent joined to broad-warehouse OHLCV; "
                "not a metadata event gate or threshold sweep."
            ),
        },
        "nearby_prior_experiments": [
            "exp-20260612-015",
            "exp-20260612-016",
            "exp-20260618-012",
            "exp-20260618-014",
        ],
        "prediction": {
            "success_probability": 0.2,
            "expected_ev_delta": 0.3,
            "expected_pnl_delta": 4000.0,
            "main_failure_modes": [
                "large_cap_13g_index_fund_noise",
                "thin_active_13d_sample",
                "priced_before_next_open",
                "window_regression_or_drawdown_drift",
            ],
            "confidence_reason": (
                "Prior 13D/13G rejections used metadata-only events and a narrow "
                "declared universe; parsed classPercent/holder-type/intent plus "
                "the broad warehouse address both root causes, with 13D activist "
                "drift literature support (Brav 2008)."
            ),
        },
        "gate1_baseline": baseline,
        "gate2_field_availability": {
            "status": "passed",
            "note": (
                "Parsed structured 13D/13G holder/stake/intent surface built from "
                "EDGAR primary_doc.xml; joined to broad warehouse OHLCV for "
                "forward-return measurement. minimum position fields (entry_date, "
                "target_price) unchanged in baseline strategy."
            ),
            "surface_coverage": coverage,
            "forward_join_meta": fwd_meta,
        },
        "gate3_survival": {
            "status": "unchanged_no_new_filter",
            "min_survival_rate": baseline["aggregate"]["min_survival_rate"],
        },
        "gate4": {
            "status": "not_run_strategy_unchanged",
            "decision": decision,
            "before": {"aggregate": baseline["aggregate"], "windows": baseline["windows"]},
            "after": {"aggregate": baseline["aggregate"], "windows": baseline["windows"]},
            "delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "note": (
                "Read-only forward-return diagnostic; no strategy/helper changed. "
                "A shared-paper-first candidate-pool replay is warranted only if a "
                "clean tradable subset is found."
            ),
        },
        "diagnostic": diag,
        "verdict": verdict,
        "production_impact": {
            "shared_helper_changed": False,
            "daily_snapshot_changed": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "backtest_production_parity": (
                "No strategy or production helper changed. A new reusable parsed "
                "13D/13G PIT surface (quant/sec_13d13g_ingest.py + "
                "data/non_ohlcv/sec_13d13g_holdings/) now exists; any future alpha "
                "must drive both historical replay and daily default-off snapshot "
                "through the same parser."
            ),
            "live_realistic_execution_envelope": (
                "Not applicable; no executable alpha entered measurement. A future "
                "shared sleeve must record notional/capital cap, liquidity, "
                "slippage, concentration, kill switch, and order semantics."
            ),
        },
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -B quant\\sec_13d13g_ingest.py --families 13D --fetch; "
            ".\\.venv\\Scripts\\python.exe -B quant\\sec_13d13g_ingest.py --families 13G --no-amendments --fetch; "
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            f"exp_20260618_016_{STEM}.py"
        ),
        "anti_js": "No JavaScript was used.",
    }
    payload["post_run_reflection"] = build_reflection(payload)
    return payload


def build_reflection(payload: dict[str, Any]) -> dict[str, Any]:
    verdict = payload["verdict"]
    diag = payload["diagnostic"]
    fam = diag["by_family_subset"]
    why = (
        "Built the first parsed PIT 13D/13G holder/stake/intent surface and "
        "characterized forward-10d SPY-excess by family, stake size, holder "
        "type, and Big-3 status over the broad warehouse. "
    )
    if verdict["any_clean_tradable_lead"]:
        why += (
            "At least one subset showed positive forward-10d SPY-excess in all "
            "three windows with adequate sample, so a shared-paper-first "
            "candidate-pool replay is the sanctioned next step."
        )
    else:
        why += (
            "No subset cleared the all-three-windows positive-excess bar with "
            "adequate sample; on the large-cap broad universe the parsed fields "
            "do not yet isolate a clean drift, consistent with the prior "
            "metadata-only 13D/13G rejections, but now backed by holder/stake "
            "evidence rather than absence of data."
        )
    return {
        "why_result_happened": why,
        "key_numbers": {
            "13D_init_h10_excess": fam["13D_init"]["h10_excess"],
            "outside_activist_13d_h10_excess": fam["outside_activist_13d"]["h10_excess"],
            "13G_init_non_big3_h10_excess": fam["13G_init_non_big3"]["h10_excess"],
            "13G_init_big3_h10_excess": fam["13G_init_big3"]["h10_excess"],
        },
        "negative_reflection": (
            "Large-cap 13G filings are dominated by passive index complexes; many "
            "13D filings are issuer-control insiders with extreme stakes, not "
            "outside accumulators. Parsed fields let us separate these, but the "
            "tradable broad-universe overlap with genuine activist accumulation "
            "may still be thin or already priced by next-open."
        ),
        "do_not_retry_near_neighbors": [
            "raw metadata-only 13D/13G event gates",
            "13G/A index-fund amendment replays",
            "stake-percent threshold sweeps on the same frozen windows without a "
            "window-robust positive forward-excess subset",
        ],
        "next_evidence_needed": [
            "If a clean subset emerged: a shared-paper-first candidate-pool sleeve "
            "(historical replay + daily default-off snapshot) on that exact subset",
            "13G/A amendment ingestion for stake-change direction (adds vs trims)",
            "13D Item 4 purpose-text classification (activist vs passive intent)",
            "forward closed replacement-value rows under a live-realistic envelope",
        ],
        "best_next_alpha_direction": (
            "Use the parsed surface's strongest forward-excess subset as a "
            "shared-paper-first candidate pool; if none is window-robust, keep "
            "13D/13G as ownership/crowding context and ingest 13D purpose text "
            "or 13G/A stake-change direction before any further entry-timing test."
        ),
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "status": payload["status"],
                "artifact": repo_rel(OUT_JSON),
                "log": repo_rel(LOG_JSON),
            },
        }
    )
    write_json(TICKET_JSON, ticket)


def write_card(payload: dict[str, Any]) -> None:
    fam = payload["diagnostic"]["by_family_subset"]
    cov = payload["gate2_field_availability"]["surface_coverage"]
    lines = [
        f"# {EXPERIMENT_ID} Parsed 13D/13G Informed-Accumulation Diagnostic",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Parsed rows: {cov['total_parsed']} / {cov['total_enumerated']} enumerated",
        f"- Rows with forward returns: {payload['gate2_field_availability']['forward_join_meta']['rows_with_forward']}",
        "",
        "## Forward-10d SPY-excess by subset",
        "",
    ]
    for name, blk in fam.items():
        s = blk["h10_excess"]
        if s.get("n"):
            lines.append(
                f"- `{name}`: n={s['n']} mean={s['mean_pct']}% win={s['win_rate']}"
            )
        else:
            lines.append(f"- `{name}`: n=0")
    lines += [
        "",
        "## Verdict",
        "",
        f"any_clean_tradable_lead: `{payload['verdict']['any_clean_tradable_lead']}`",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
    ]
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(payload: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "owner": OWNER,
            "timestamp": payload["timestamp"],
            "runner": repo_rel(Path(__file__)),
            "artifacts": {
                "artifact": repo_rel(OUT_JSON),
                "before": repo_rel(BEFORE_JSON),
                "after": repo_rel(AFTER_JSON),
                "log": repo_rel(LOG_JSON),
                "card": repo_rel(CARD_MD),
                "ticket": repo_rel(TICKET_JSON),
                "parsed_surface": "data/non_ohlcv/sec_13d13g_holdings/rows.json",
                "ingest_module": "quant/sec_13d13g_ingest.py",
            },
            "no_strategy_change": True,
            "anti_js": payload["anti_js"],
        },
    )


def persist(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUT_JSON, payload)
    write_json(
        BEFORE_JSON,
        {"experiment_id": EXPERIMENT_ID, "kind": "before_baseline", "gate1_baseline": payload["gate1_baseline"]},
    )
    write_json(
        AFTER_JSON,
        {"experiment_id": EXPERIMENT_ID, "kind": "after_no_strategy_change", "gate4": payload["gate4"]},
    )
    write_json(LOG_JSON, payload)
    update_ticket(payload)
    write_card(payload)
    write_manifest(payload)
    append_jsonl_once(EXPERIMENT_LOG, payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "parsed_rows": payload["gate2_field_availability"]["surface_coverage"]["total_parsed"],
                "rows_with_forward": payload["gate2_field_availability"]["forward_join_meta"]["rows_with_forward"],
                "key_numbers": payload["post_run_reflection"]["key_numbers"],
                "any_clean_tradable_lead": payload["verdict"]["any_clean_tradable_lead"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
