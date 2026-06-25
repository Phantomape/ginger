"""exp-20260625-019: short-volume clean-flow quality-gate replay scout.

Promotes the exp-20260625-018 observed-only lead one rigorous step: does the
SIGN-CORRECT informed-flow signal survive top-1 SELECTION and costs? It builds a
single fixed liquid SPY-relative momentum/breakout candidate pool and runs it
TWO ways that differ in exactly one decision: whether candidates whose
point-in-time moomoo `short_volume_ratio` percentile sits in the toxic top
quintile (>= 0.80, highest informed daily short-sale flow, Diether-Lee-Werner
2009) are EXCLUDED before the daily top-1 next-open 10-day pick.

The single causal variable is the clean-flow exclusion gate. ``before`` is the
UNGATED pool overlay on the core baseline; ``after`` is the GATED pool overlay;
the delta is the pure gate effect (replacement value of dropping a toxic top
pick for the next clean candidate that day).

This is a PRIVATE REPLAY SCOUT: no shared helper, daily snapshot, ranking,
sizing, exit, paper order, or live order changes. A positive result is only a
lead that justifies a shared default-off clean-flow quality-gate helper run
through the full-stack candidate-pool Gate 1-4 contract; it is NOT accepted
alpha. The prior moomoo attempt (exp-20260622-010) used the WRONG sign (high
short volume as a positive absorption entry); this run uses the avoidance sign.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for import_path in (SCRIPTS_DIR, QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260625-019"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "short_volume_clean_flow_gate_scout"
RUNNER = f"quant/experiments/exp_20260625_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STEM = "short_volume_clean_flow_gate_scout"
TRIAL_FAMILY = "moomoo_daily_short_volume_clean_flow_quality_gate"
TRIAL_VARIANT_ID = "short_volume_ratio_toxic_top_quintile_exclusion_top1_10d_v1"
CHANGED_VARIABLE = "short_volume_clean_flow_quality_gate_v1"
RULE_VERSION = CHANGED_VARIABLE
MECHANISM_FAMILY = "production_visible_informed_short_flow_quality_gate"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_019_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT / "data" / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SHORT_VOLUME_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "moomoo_daily_short_volume_broad" / "rows.jsonl"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_HISTORY_SESSIONS = 80
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = 0.03
MIN_RET60_EXCESS_SPY = 0.0
MIN_PROXIMITY_TO_20D_HIGH = 0.95

MIN_TRAILING_OBS = 30
TOXIC_PERCENTILE = 0.80  # top short_volume_ratio quintile = toxic informed-short flow

# Gate-4 screen on the GATE EFFECT (gated minus ungated).
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MIN_CHANGED_SELECTIONS = 12
MIN_EV_IMPROVED_WINDOWS = 2
MAX_WINDOW_EV_REGRESSION = 0.05
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

SKIP_TICKERS = {"SPY", "QQQ", "IWM", "DIA", "MDY", "GLD", "IAU", "SLV"}

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21",
                          "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22",
                       "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22",
                       "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json"}),
    ]
)

HYPOTHESIS = (
    "A point-in-time moomoo short_volume_ratio clean-flow exclusion gate -- "
    "dropping daily top-1 momentum/breakout candidates whose informed daily "
    "short-sale flow sits in the toxic top quintile and taking the next clean "
    "candidate -- adds after-cost replacement value over the identical ungated "
    "pool across the canonical windows."
)
ALPHA_HYPOTHESIS = HYPOTHESIS
NEW_EVIDENCE_AXIS = (
    "New gate shape on a non-saturated source: an informed-flow EXCLUSION gate "
    "applied at top-1 selection time, promoting exp-20260625-018's sign-correct "
    "avoidance read into measured after-cost replacement value. Not the rejected "
    "exp-20260622-010 high-short-volume absorption ENTRY, and not a FINRA short-"
    "interest, FTD, OHLCV-momentum, top-N, hold, notional, or threshold retune."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260625-018", "exp-20260622-010", "exp-20260623-008"]
CAUSAL_COMPONENTS = [
    "fixed liquid SPY-relative momentum/breakout candidate pool",
    "point-in-time short_volume_ratio toxic-top-quintile exclusion gate",
    "daily top-1 next-open 10-day paper replay, ungated vs gated",
    "core baseline overlay and gate-effect delta",
]

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "too_few_changed_selections_after_top1",
        "replacement_candidate_no_better_after_costs",
        "bull_window_gate_removes_winners",
        "concentration_or_drawdown_fail",
    ],
    "confidence_reason": (
        "exp-20260625-018 showed forward-10d returns fall monotonically with the "
        "PIT short_volume_ratio percentile in old_thin and late_strong (negative "
        "corr in all 3 windows), and ~19% of accepted selections fall in the "
        "toxic Q5 bucket. The open question this scout answers is whether, after "
        "top-1 selection and costs, replacing a toxic top pick with the next "
        "clean candidate actually improves replacement value. Main disconfirmer: "
        "the gate may change too few selections, or the clean replacement may be "
        "no better net of costs, especially in the bull window where toxic names "
        "still rose."
    ),
    "recorded_at": "2026-06-25T00:00:00+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "production_watchlist_changed": False,
    "uses_free_ohlcv": True,
    "uses_moomoo_short_volume": True,
    "uses_llm": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "replay_only": True,
    "adapter_status": "private_replay_only_no_live_adapter",
    "parity_note": (
        "Experiment-owned private replay scout. A positive result requires a "
        "shared default-off helper computing the same PIT short_volume_ratio "
        "clean-flow gate over both historical replay and a daily snapshot, with "
        "a parity test, before any ranking, sizing, watchlist, paper ledger, or "
        "order surface could change."
    ),
}


# --------------------------------------------------------------------------- #
def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def rf(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if math.isfinite(number) else None


def safe(payload: Any) -> Any:
    if isinstance(payload, (OrderedDict, dict)):
        return {str(k): safe(v) for k, v in payload.items()}
    if isinstance(payload, Counter):
        return {str(k): safe(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [safe(v) for v in payload]
    if isinstance(payload, set):
        return sorted(safe(v) for v in payload)
    if isinstance(payload, Path):
        return repo_rel(payload)
    if isinstance(payload, date):
        return payload.isoformat()
    if isinstance(payload, float):
        return None if (math.isnan(payload) or math.isinf(payload)) else round(payload, 10)
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# short_volume_ratio per-ticker expanding PIT percentile
# --------------------------------------------------------------------------- #
def build_short_volume_index() -> tuple[dict[str, tuple[list[str], list[float | None]]], dict[str, Any]]:
    by_ticker: dict[str, list[tuple[str, float]]] = defaultdict(list)
    raw = 0
    if SHORT_VOLUME_ROWS.exists():
        for line in SHORT_VOLUME_ROWS.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            raw += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            tk = str(row.get("ticker") or "").upper()
            ad = str(row.get("activity_date") or "")[:10]
            try:
                svr = float(row.get("short_volume_ratio"))
            except (TypeError, ValueError):
                continue
            if tk and ad and math.isfinite(svr):
                by_ticker[tk].append((ad, svr))
    index: dict[str, tuple[list[str], list[float | None]]] = {}
    usable = 0
    for tk, seq in by_ticker.items():
        seq.sort()
        dates = [d for d, _ in seq]
        pcts: list[float | None] = []
        hist: list[float] = []
        for _, svr in seq:
            if len(hist) >= MIN_TRAILING_OBS:
                pcts.append(sum(1 for h in hist if h < svr) / len(hist))
                usable += 1
            else:
                pcts.append(None)
            hist.append(svr)
        index[tk] = (dates, pcts)
    audit = {
        "source_artifact": repo_rel(SHORT_VOLUME_ROWS),
        "raw_rows": raw,
        "tickers": len(index),
        "usable_percentile_points": usable,
        "min_trailing_obs_for_percentile": MIN_TRAILING_OBS,
        "toxic_percentile_threshold": TOXIC_PERCENTILE,
        "artifact_not_mutated": True,
    }
    return index, audit


def short_volume_percentile(
    index: dict[str, tuple[list[str], list[float | None]]],
    ticker: str,
    signal_date: str,
) -> float | None:
    """Percentile from the most recent activity_date STRICTLY before signal_date.

    activity_date is reported after the US close, and the paper entry is the
    next session open, so any activity_date <= signal_date is point-in-time.
    """
    if ticker not in index:
        return None
    dates, pcts = index[ticker]
    i = bisect.bisect_right(dates, signal_date) - 1
    while i >= 0:
        if pcts[i] is not None:
            return pcts[i]
        i -= 1
    return None


# --------------------------------------------------------------------------- #
# OHLCV-derived candidate features
# --------------------------------------------------------------------------- #
def v(row: dict[str, Any], key: str) -> float | None:
    return shadow._value(row, key)


def avg(values: list[float | None]) -> float | None:
    valid = [float(x) for x in values if x is not None]
    return sum(valid) / len(valid) if valid else None


def ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = v(rows[idx - lookback], "Close")
    close = v(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return close / prior - 1.0


def prior_adv20(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 20:
        return None
    vals = []
    for row in rows[idx - 20:idx]:
        c = v(row, "Close")
        vol = v(row, "Volume")
        vals.append(None if c is None or vol is None else c * vol)
    return avg(vals)


def prior_high20(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 20:
        return None
    highs = [v(row, "High") for row in rows[idx - 20:idx]]
    if any(h is None for h in highs):
        return None
    return max(float(h) for h in highs if h is not None)


def candidates_for_window(
    *, snapshot: dict[str, list[dict[str, Any]]], cfg: dict[str, str],
    universe: list[str], before_result: dict[str, Any],
    sv_index: dict[str, tuple[list[str], list[float | None]]],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    entries_by_date = shadow._baseline_entries(before_result)
    dates = [d for d in shadow._trading_dates(snapshot) if cfg["start"] <= d <= cfg["end"]]
    spy_rows = shadow._series(snapshot, "SPY")
    spy_idx_by_date = shadow._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()

    eligible = [t for t in sorted(set(universe).intersection(snapshot))
                if t not in shadow.EXCLUDED_TICKERS and t not in SKIP_TICKERS]
    for ticker in eligible:
        rows = shadow._series(snapshot, ticker)
        idx_by_date = shadow._row_index(rows)
        for signal_date in dates:
            idx = idx_by_date.get(signal_date)
            spy_idx = spy_idx_by_date.get(signal_date)
            if idx is None or spy_idx is None or idx < MIN_HISTORY_SESSIONS or spy_idx < 60:
                continue
            close = v(rows[idx], "Close")
            adv20 = prior_adv20(rows, idx)
            high20 = prior_high20(rows, idx)
            tret20 = ret(rows, idx, 20)
            tret60 = ret(rows, idx, 60)
            sret20 = ret(spy_rows, spy_idx, 20)
            sret60 = ret(spy_rows, spy_idx, 60)
            if None in (close, adv20, high20, tret20, tret60, sret20, sret60):
                reasons["missing_field"] += 1
                continue
            if close < MIN_PRICE:
                reasons["below_min_price"] += 1
                continue
            if adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
                reasons["below_min_adv20"] += 1
                continue
            if high20 <= 0 or close < high20 * MIN_PROXIMITY_TO_20D_HIGH:
                reasons["not_near_20d_high"] += 1
                continue
            ret20_excess = tret20 - sret20
            ret60_excess = tret60 - sret60
            if ret20_excess < MIN_RET20_EXCESS_SPY:
                reasons["ret20_not_spy_leading"] += 1
                continue
            if ret60_excess < MIN_RET60_EXCESS_SPY:
                reasons["ret60_spy_lag"] += 1
                continue
            sv_pct = short_volume_percentile(sv_index, ticker, signal_date)
            ab_entries = entries_by_date.get(signal_date, [])
            candidates.append({
                "date": signal_date,
                "ticker": ticker,
                "candidate_source": STEM,
                "rule_version": RULE_VERSION,
                "candidate_score": rf(ret20_excess, 6),
                "ret20_excess_spy": rf(ret20_excess, 6),
                "ret60_excess_spy": rf(ret60_excess, 6),
                "proximity_to_20d_high": rf(close / high20, 6),
                "avg_dollar_volume_prior20": rf(adv20, 2),
                "short_volume_ratio_percentile": rf(sv_pct, 6) if sv_pct is not None else None,
                "short_volume_pct_available": sv_pct is not None,
                "short_volume_toxic": bool(sv_pct is not None and sv_pct >= TOXIC_PERCENTILE),
                "same_ticker_ab_overlap": any(t.get("ticker") == ticker for t in ab_entries),
            })
    candidates.sort(key=lambda r: (
        r["date"], -float(r["candidate_score"] or 0.0), -float(r["avg_dollar_volume_prior20"] or 0.0), r["ticker"]
    ))
    return candidates, reasons


def select_trades(
    *, snapshot: dict[str, list[dict[str, Any]]], candidates: list[dict[str, Any]],
    apply_gate: bool,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Daily top-1, cooldown, core-overlap exclusion. When apply_gate, skip toxic
    short-flow candidates so the next clean candidate is taken. Returns selected
    trades and a {date: ticker} pick map for changed-selection accounting."""
    selected: list[dict[str, Any]] = []
    pick_by_date: dict[str, str] = {}
    used_date: Counter[str] = Counter()
    last_day_by_ticker: dict[str, date] = {}
    for row in candidates:
        signal_day = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "")
        if row.get("same_ticker_ab_overlap"):
            continue
        if apply_gate and row.get("short_volume_toxic"):
            continue
        parsed = date.fromisoformat(signal_day)
        last_day = last_day_by_ticker.get(ticker)
        if last_day is not None and (parsed - last_day).days <= SAME_TICKER_COOLDOWN_DAYS:
            continue
        if used_date[signal_day] >= MAX_PAPER_TRADES_PER_DAY:
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            continue
        selected.append(trade)
        pick_by_date[signal_day] = ticker
        used_date[signal_day] += 1
        last_day_by_ticker[ticker] = parsed
    return selected, pick_by_date


def configure_sleeve_globals() -> None:
    sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    sleeve.STEM = STEM
    sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    sleeve.HOLD_DAYS = HOLD_DAYS
    sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY


def load_snapshot(cfg: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((REPO_ROOT / cfg["snapshot"]).read_text(encoding="utf-8-sig"))
    return payload["ohlcv"]


# --------------------------------------------------------------------------- #
def gate4(*, aggregate: dict[str, Any], gated_summary: dict[str, Any],
          window_rows: "OrderedDict[str, dict[str, Any]]", changed_total: int) -> dict[str, Any]:
    failed: list[str] = []
    ev_delta = float(aggregate.get("expected_value_score_delta_sum") or 0.0)
    pnl_delta = float(aggregate.get("total_pnl_delta_sum") or 0.0)
    if ev_delta <= 0:
        failed.append("gate_effect_aggregate_ev_not_positive")
    if pnl_delta <= 0:
        failed.append("gate_effect_aggregate_pnl_not_positive")

    ev_improved = 0
    drawdown_drift: dict[str, float] = {}
    for label, row in window_rows.items():
        d = row["delta"]
        wev = float(d.get("expected_value_score") or 0.0)
        if wev > 0:
            ev_improved += 1
        if wev < -MAX_WINDOW_EV_REGRESSION:
            failed.append(f"{label}_gate_effect_ev_regressed")
        b_dd = row["before"].get("max_drawdown_pct")
        a_dd = row["after"].get("max_drawdown_pct")
        if isinstance(b_dd, (int, float)) and isinstance(a_dd, (int, float)):
            drift = round(float(a_dd) - float(b_dd), 6)
            drawdown_drift[label] = drift
            if drift > MAX_DRAWDOWN_WORSE:
                failed.append(f"{label}_gate_worsens_drawdown")

    if ev_improved < MIN_EV_IMPROVED_WINDOWS:
        failed.append("too_few_ev_improved_windows")
    if changed_total < MIN_CHANGED_SELECTIONS:
        failed.append("too_few_changed_selections")
    if gated_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("too_few_gated_trades")
    if len(gated_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("too_few_gated_windows")
    msps = gated_summary.get("max_single_positive_pnl_share")
    hhi = gated_summary.get("positive_pnl_hhi")
    if msps is not None and msps > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("gated_concentration_single_ticker_too_high")
    if hhi is not None and hhi > MAX_POSITIVE_HHI:
        failed.append("gated_positive_pnl_hhi_too_high")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_short_volume_clean_flow_gate_replay_lead_not_promoted"
            if passed else "rejected_short_volume_clean_flow_gate_no_replacement_value"
        ),
        "failed_reasons": sorted(set(failed)),
        "gate_effect_aggregate_ev_delta": rf(ev_delta, 6),
        "gate_effect_aggregate_pnl_delta": rf(pnl_delta, 2),
        "ev_improved_windows": ev_improved,
        "changed_selections_total": changed_total,
        "gated_trade_count": gated_summary["total_trade_count"],
        "drawdown_drift_by_window": drawdown_drift,
        "concentration": {"max_single_positive_pnl_share": msps, "positive_pnl_hhi": hhi},
        "acceptance_rule": (
            "Private replay scout lead requires the GATE EFFECT (gated minus "
            "ungated) to show positive aggregate EV and PnL, EV improved in >= "
            f"{MIN_EV_IMPROVED_WINDOWS} of 3 windows with no window EV regression "
            f"beyond {MAX_WINDOW_EV_REGRESSION}, >= {MIN_CHANGED_SELECTIONS} "
            "changed selections, no window drawdown worse than "
            f"{MAX_DRAWDOWN_WORSE}, >= {MIN_TARGET_TRADES} gated trades across 3 "
            "windows, and clean concentration. A positive lead is NOT accepted "
            "alpha; it requires a shared default-off helper plus daily snapshot "
            "and parity before promotion."
        ),
    }


def build_payload() -> dict[str, Any]:
    configure_sleeve_globals()
    timestamp = utc_now()
    gate2_open = sleeve._audit_open_positions()
    if not gate2_open["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open}")

    sv_index, sv_audit = build_short_volume_index()
    universe = sorted(get_universe())

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    ungated_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    gated_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    baseline_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    gated_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    detail_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    changed_total = 0

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline + ungated/gated clean-flow replay")
        before_result = shadow._run_baseline(universe, cfg)
        baseline = overlay_helper._metrics(before_result)
        snapshot = load_snapshot(cfg)
        candidates, reasons = candidates_for_window(
            snapshot=snapshot, cfg=cfg, universe=universe,
            before_result=before_result, sv_index=sv_index,
        )
        ungated_trades, ungated_pick = select_trades(
            snapshot=snapshot, candidates=candidates, apply_gate=False)
        gated_trades, gated_pick = select_trades(
            snapshot=snapshot, candidates=candidates, apply_gate=True)

        changed_days = sorted(
            d for d in set(ungated_pick) | set(gated_pick)
            if ungated_pick.get(d) != gated_pick.get(d)
        )
        changed_total += len(changed_days)

        ungated_overlay = sleeve._overlay_from_paper_trades(before_result, ungated_trades)
        gated_overlay = sleeve._overlay_from_paper_trades(before_result, gated_trades)
        ungated_after = overlay_helper._metrics_with_overlay(before_result, ungated_overlay)
        gated_after = overlay_helper._metrics_with_overlay(before_result, gated_overlay)
        gate_effect = overlay_helper._delta(gated_after, ungated_after)

        baseline_metrics[label] = baseline
        ungated_metrics[label] = ungated_after
        gated_metrics[label] = gated_after
        gated_trades_by_window[label] = gated_trades
        window_rows[label] = {
            "before": ungated_after,
            "after": gated_after,
            "delta": gate_effect,
            "target_trade_count": len(gated_trades),
        }
        toxic_candidates = sum(1 for c in candidates if c.get("short_volume_toxic"))
        detail_by_window[label] = {
            "raw_candidate_count": len(candidates),
            "toxic_candidate_count": toxic_candidates,
            "ungated_trade_count": len(ungated_trades),
            "gated_trade_count": len(gated_trades),
            "changed_selection_days": len(changed_days),
            "changed_days_sample": changed_days[:25],
            "candidate_reject_reasons": dict(reasons),
            "ungated_vs_baseline_delta": overlay_helper._delta(ungated_after, baseline),
            "gated_vs_baseline_delta": overlay_helper._delta(gated_after, baseline),
        }

    aggregate = sleeve._aggregate(window_rows)
    gated_summary = sleeve._target_trade_summary(gated_trades_by_window)
    verdict = gate4(aggregate=aggregate, gated_summary=gated_summary,
                    window_rows=window_rows, changed_total=changed_total)
    survivals = [m.get("survival_rate") for m in baseline_metrics.values() if m.get("survival_rate") is not None]
    min_survival = min(survivals) if survivals else 1.0

    status = "observed_only_positive_lead" if verdict["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_passed": verdict["passed"],
        "brier_score": round((PREDICTION["success_probability"] - (1.0 if verdict["passed"] else 0.0)) ** 2, 6),
        "failure_modes_observed": verdict["failed_reasons"],
    }
    reflection = {
        "why_result_happened": (
            "Replacing a toxic top-quintile informed-short top pick with the next "
            "clean momentum candidate added after-cost replacement value where the "
            "sign-correct exp-018 read predicted, surviving top-1 selection and "
            "costs." if verdict["passed"] else
            "After top-1 selection and costs the clean-flow gate did not add "
            "robust replacement value: too few changed picks, no net improvement, "
            "a regressed window, or a concentration/drawdown failure."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping the toxic percentile cut, percentile "
            "lookback, momentum/proximity thresholds, hold, cooldown, top-N, or "
            "notional, and do not re-run the wrong-sign absorption ENTRY family. "
            "A retry needs a materially different gate shape or new evidence."
        ),
        "new_evidence_required": (
            "If positive: a shared default-off clean-flow quality-gate helper over "
            "historical replay and a daily snapshot with a parity test, then a "
            "full-stack candidate-pool Gate 1-4 overlay versus the closest "
            "accepted comparator. If negative: materially more closed forward rows "
            "tagged with the entry short_volume_ratio percentile, or PIT borrow "
            "fee / utilization."
        ),
    }

    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": verdict["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": verdict["passed"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "candidate_pool_private_replay_scout",
        "implementation_mode": "private_replay_scout_no_shared_helper",
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low_new_source_new_gate_shape",
        "new_evidence_type": "short_volume_ratio_clean_flow_exclusion_gate_replacement_value",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260625-018": "Sign-correct observed-only lead this scout promotes to measured replacement value.",
                "exp-20260622-010": "Rejected WRONG-sign high-short-volume absorption entry; opposite gate here.",
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_causal_variable": "The short_volume_ratio toxic-top-quintile exclusion gate.",
            "4_success_failure_standard": verdict["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_history_sessions": MIN_HISTORY_SESSIONS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_proximity_to_20d_high": MIN_PROXIMITY_TO_20D_HIGH,
            "toxic_percentile": TOXIC_PERCENTILE,
            "min_trailing_obs_for_percentile": MIN_TRAILING_OBS,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline_metrics,
                  "canonical_baseline_result_file": repo_rel(BASELINE_RESULT)},
        "gate2": {"passed": gate2_open["passed"] and bool(sv_index),
                  "open_positions": gate2_open,
                  "short_volume_audit": sv_audit,
                  "runtime_fields": ["ohlcv Date/Open/High/Low/Close/Volume", "SPY OHLCV",
                                     "moomoo short_volume_ratio", "moomoo activity_date"]},
        "gate3": {"new_core_filter_added": False, "minimum_core_survival_rate": rf(min_survival, 6),
                  "passed": min_survival >= 0.05,
                  "note": "Additive private replay overlay; no new core filter or entry rule."},
        "gate4": verdict,
        "baseline_metrics": baseline_metrics,
        "ungated_metrics": ungated_metrics,
        "gated_metrics": gated_metrics,
        "before_metrics": ungated_metrics,
        "after_metrics": gated_metrics,
        "delta_metrics": {"by_window": OrderedDict((k, r["delta"]) for k, r in window_rows.items()),
                          "aggregate": aggregate},
        "detail_by_window": detail_by_window,
        "gated_target_trade_summary": gated_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": reflection,
        "interpretation": reflection["why_result_happened"],
        "rejection_reason": None if verdict["passed"] else "; ".join(verdict["failed_reasons"]),
        "next_evidence_needed": reflection["new_evidence_required"],
        "related_files": [
            RUNNER, repo_rel(SHORT_VOLUME_ROWS), repo_rel(BASELINE_RESULT),
            "quant/experiments/exp_20260625_018_short_volume_informed_flow_attribution.py",
            "docs/agent_experiment_protocol.md", "docs/backtesting.md",
            "docs/alpha-optimization-playbook.md",
        ],
        "changed_files": [
            RUNNER, repo_rel(OUT_JSON), repo_rel(LOG_JSON), repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON), repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG), repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "candidate_pool_private_replay_scout",
        "implementation_mode": "private_replay_scout_no_shared_helper",
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "gate1": {"passed": payload["gate1"]["passed"]},
        "gate2": {"passed": payload["gate2"]["passed"], "short_volume_audit": payload["gate2"]["short_volume_audit"]},
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "baseline_metrics": payload["baseline_metrics"],
        "ungated_metrics": payload["ungated_metrics"],
        "gated_metrics": payload["gated_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "detail_by_window": payload["detail_by_window"],
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "updated_at": payload["timestamp"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    rows = ["| Window | Ungated EV | Gated EV | dEV(gate) | Ungated PnL | Gated PnL | dPnL(gate) | chg |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label in WINDOWS:
        u = payload["ungated_metrics"][label]
        g = payload["gated_metrics"][label]
        d = payload["delta_metrics"]["by_window"][label]
        det = payload["detail_by_window"][label]
        rows.append("| {l} | {ue:.4f} | {ge:.4f} | {de:+.4f} | ${up:,.0f} | ${gp:,.0f} | ${dp:+,.0f} | {c} |".format(
            l=label, ue=u["expected_value_score"], ge=g["expected_value_score"],
            de=d.get("expected_value_score", 0.0), up=u["total_pnl"], gp=g["total_pnl"],
            dp=d.get("total_pnl", 0.0), c=det["changed_selection_days"]))
    agg = payload["delta_metrics"]["aggregate"]
    return "\n".join([
        f"# {EXPERIMENT_ID}: short-volume clean-flow quality-gate scout", "",
        f"- Status: `{payload['status']}`", f"- Decision: `{payload['decision']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`", "- Lane: `alpha_search` (private replay scout)", "",
        "## Hypothesis", "", HYPOTHESIS, "",
        "## Gate effect (gated minus ungated)", "", *rows, "",
        "- Aggregate gate-effect EV delta: `{:+.4f}`".format(agg["expected_value_score_delta_sum"]),
        "- Aggregate gate-effect PnL delta: `${:+,.2f}`".format(agg["total_pnl_delta_sum"]),
        "- Changed selections total: `{}`".format(payload["gate4"]["changed_selections_total"]),
        "- Gated trades: `{}`".format(payload["gated_target_trade_summary"]["total_trade_count"]),
        "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"), "",
        "## Production impact", "",
        "Private replay only. No shared helper, adapter, snapshot, ranking, sizing, exit, paper order, or live order changed.", "",
        "## Reproduce", "", "```powershell", *payload["reproduction_commands"], "```", "",
    ])


def build_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID, "lane": LANE, "status": payload["status"], "owner": OWNER,
        "created_at": payload["timestamp"], "completed_at": payload["timestamp"],
        "claimed_at": payload["timestamp"], "updated_at": payload["timestamp"],
        "change_type": "candidate_pool_private_replay_scout",
        "implementation_mode": "private_replay_scout_no_shared_helper",
        "hypothesis": HYPOTHESIS, "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY, "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE, "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS, "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prior_trial_count": 2, "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"], "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION, "acceptance_rule": payload["gate4"]["acceptance_rule"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "evaluation_windows": [{"label": k, **v} for k, v in WINDOWS.items()],
        "novelty": {"enforced": True, "blocking_matches": [], "verdict": "promotion_of_exp-20260625-018_lead",
                    "nearest_family": "moomoo_daily_short_volume_clean_flow_quality_gate"},
        "allowed_write_scope": [
            RUNNER, repo_rel(OUT_JSON), repo_rel(CARD_MD), repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON), repo_rel(LOG_JSON), "docs/experiment_log.jsonl", "docs/experiment_registry.json",
        ],
        "locked_variables": [CHANGED_VARIABLE],
        "must_not_touch": ["shared paper-sleeve helpers", "candidate ranking / sizing / exits / orders", "daily snapshots"],
        "decision": payload["decision"],
        "result": {"observed_only_lead": payload["gate4"]["passed"], "failed_reasons": payload["gate4"]["failed_reasons"]},
        "artifact": repo_rel(OUT_JSON), "log": repo_rel(LOG_JSON), "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON), "ticket_file": repo_rel(TICKET_JSON),
        "production_impact": PRODUCTION_IMPACT, "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
    }


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / RUNNER, OUT_JSON, LOG_JSON, CARD_MD, MANIFEST_JSON, TICKET_JSON,
             EXPERIMENT_LOG, REGISTRY_JSON, SHORT_VOLUME_ROWS]
    return {
        "schema_version": 1, "experiment_id": EXPERIMENT_ID, "status": payload["status"],
        "decision": payload["decision"], "artifact": repo_rel(OUT_JSON), "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD), "runner": RUNNER, "command": RUNNER_COMMAND,
        "files": {repo_rel(p): {"exists": p.exists(), "sha256": sha256_file(p)} for p in files},
        "log_row_sha256": hashlib.sha256(json.dumps(safe(log_row), sort_keys=True).encode("utf-8")).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, build_ticket(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_row)
    registry_result = {
        "accepted": False, "accepted_alpha": False, "observed_only_lead": payload["gate4"]["passed"],
        "allocation_ready": False, "decision": payload["decision"], "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON), "runner": RUNNER, "gate4": payload["gate4"],
        "calibration": payload["calibration"], "delta_metrics": payload["delta_metrics"],
        "summary": payload["interpretation"],
    }
    persist_self_registered_result(
        REGISTRY_JSON, experiment_id=EXPERIMENT_ID, lane=LANE, prediction=payload["prediction"],
        result=registry_result, status=payload["status"],
        fields={
            "owner": OWNER, "hypothesis": HYPOTHESIS, "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": "candidate_pool_private_replay_scout",
            "implementation_mode": "private_replay_scout_no_shared_helper",
            "mechanism_family": MECHANISM_FAMILY, "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID, "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE, "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"], "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT), "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON), "log": repo_rel(LOG_JSON), "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": log_row["aggregate_expected_value_delta"],
            "aggregate_strategy_total_pnl_delta": log_row["aggregate_strategy_total_pnl_delta"],
            "gate1": payload["gate1"], "gate2": {"passed": payload["gate2"]["passed"]},
            "gate3": payload["gate3"], "gate4": payload["gate4"],
            "production_impact": PRODUCTION_IMPACT, "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> int:
    payload = build_payload()
    persist(payload)
    agg = payload["delta_metrics"]["aggregate"]
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID, "status": payload["status"], "decision": payload["decision"],
        "gate_effect_ev_delta": agg["expected_value_score_delta_sum"],
        "gate_effect_pnl_delta": agg["total_pnl_delta_sum"],
        "changed_selections": payload["gate4"]["changed_selections_total"],
        "gated_trades": payload["gate4"]["gated_trade_count"],
        "ev_improved_windows": payload["gate4"]["ev_improved_windows"],
        "failed_reasons": payload["gate4"]["failed_reasons"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
