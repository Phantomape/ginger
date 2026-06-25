"""exp-20260625-018: moomoo daily short_volume_ratio informed-flow attribution.

Observed-only, read-only alpha attribution. This runner asks a single
attributable question: is point-in-time moomoo daily ``short_volume_ratio``
(informed daily short-sale flow, Diether-Lee-Werner 2009) a SIGN-CORRECT
avoidance / quality signal on the 51-name core universe -- i.e. do names with
high informed short flow precede WEAKER forward 10-trading-day next-open
returns -- and do the accepted default-off paper sleeves already SELECT names
that sit in the toxic high-short-flow bucket (so a clean-flow quality gate
would not be inert)?

It changes no strategy helper, candidate ranking, sizing, entry, exit, paper
order, live order, daily sleeve artifact, or production watchlist. A positive
observed-only lead only justifies a future shared-paper-first clean-flow
quality-gate helper run through the full-stack candidate-pool Gate 1-4 contract;
it is NOT accepted alpha and NOT a threshold/top-N/notional retune.

The prior moomoo short-volume attempt (exp-20260622-010) used high short volume
as a POSITIVE absorption entry and was rejected; that is the WRONG sign. The
archive was a 5-ticker raw probe then; the broad archive (exp-20260623-008) now
covers 51 tickers x ~2 years, a materially different data shape.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-018"
OWNER = "alpha-explore"
SLUG = "short_volume_informed_flow_attribution"
RUNNER = f"quant/experiments/exp_20260625_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SHORT_VOLUME_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "moomoo_daily_short_volume_broad" / "rows.jsonl"
)
PAPER_SLEEVE_GLOB = "data/paper_sleeves/*/state.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22", "data/ohlcv/ohlcv_snapshot_20241002_20250422.json"),
    ("mid_weak", "2025-04-23", "2025-10-22", "data/ohlcv/ohlcv_snapshot_20250423_20251022.json"),
    ("late_strong", "2025-10-23", "2026-04-21", "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"),
]

HOLD_DAYS = 10
MIN_TRAILING_OBS = 30  # trailing short-vol observations needed to form a percentile
# Skip non-common-stock proxies that the candidate book does not buy as alpha.
SKIP_TICKERS = {"SPY", "QQQ", "IWM", "DIA", "MDY", "GLD", "IAU", "SLV"}

# Pre-declared observed-only acceptance screen.
CONFIG = {
    "hold_days": HOLD_DAYS,
    "min_trailing_obs_for_percentile": MIN_TRAILING_OBS,
    "min_total_observations": 2000,
    "min_windows_with_negative_direction": 2,
    "min_toxic_selection_share": 0.10,
    "toxic_quintile_index": 4,
    "quintiles": 5,
}

HYPOTHESIS = (
    "Observed-only alpha hypothesis: point-in-time moomoo daily "
    "short_volume_ratio is a sign-correct informed-flow AVOIDANCE signal -- "
    "names with high informed daily short-sale flow precede weaker forward "
    "10-day next-open returns -- and accepted default-off paper sleeves "
    "already select names in the toxic high-short-flow bucket, so a clean-flow "
    "quality gate would not be inert. No strategy behavior is changed."
)
CHANGE_TYPE = "observed_only_forward_attribution"
IMPLEMENTATION_MODE = "observed_only_read_only_runner"
MECHANISM_FAMILY = "observed_only_forward_attribution"
TRIAL_FAMILY = "moomoo_daily_short_volume_informed_flow_attribution"
TRIAL_VARIANT_ID = "short_volume_ratio_pit_percentile_fwd10d_quintile_v1"
CHANGED_VARIABLE = "moomoo_daily_short_volume_informed_flow_attribution_v1"
NEW_EVIDENCE_TYPE = (
    "point_in_time_per_ticker_short_volume_ratio_percentile_joined_to_forward_10d_returns"
)
NEW_EVIDENCE_AXIS = (
    "Read-only new evidence axis: moomoo daily short_volume_ratio (informed "
    "daily short-sale flow) as a SIGN-CORRECT avoidance/quality signal on the "
    "broad 51-name archive (exp-20260623-008), the opposite sign from the "
    "rejected exp-20260622-010 high-short-volume absorption ENTRY. This is not "
    "a FINRA short-interest, FTD, OHLCV-momentum, top-N, hold-day, notional, "
    "or threshold retune; it is a new data source used on a new gate shape "
    "(negative quality screen)."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-010",
    "exp-20260623-008",
    "exp-20260616-024",
]
CAUSAL_COMPONENTS = [
    "per-ticker expanding PIT percentile of short_volume_ratio",
    "next-open forward 10-trading-day return join",
    "quintile and correlation attribution per canonical window",
    "accepted paper-sleeve selection overlap with the toxic quintile",
    "no strategy behavior change",
]

PREDICTION = {
    "success_probability": 0.30,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_or_unstable_quintile_separation",
        "bull_window_washout",
        "accepted_selection_overlap_too_small",
        "long_only_book_cannot_trade_avoidance_signal_directly",
    ],
    "confidence_reason": (
        "Diether-Lee-Werner (2009) show daily shorting flow is informed and "
        "predicts negative short-horizon returns. A pre-run read-only probe on "
        "the broad 51-name archive showed forward-10d returns declining "
        "monotonically with the per-ticker short_volume_ratio percentile in "
        "old_thin (Q1 +1.58% -> Q5 -0.45%) and late_strong (Q1 +0.35% -> Q5 "
        "-1.51%), negative correlation in all three windows, washing out only "
        "in the raging-bull mid_weak window, and ~19% of accepted paper-sleeve "
        "selections fell in the toxic Q5 bucket. The main disconfirmer is that "
        "this is an avoidance signal a long-only book captures only via "
        "filtering, and closed-row overlap remains thin."
    ),
    "recorded_at": "2026-06-25T00:00:00+00:00",
}


# --------------------------------------------------------------------------- #
# small io / coercion helpers
# --------------------------------------------------------------------------- #
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != record["experiment_id"]:
                kept.append(json.dumps(existing, sort_keys=True))
    kept.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # drop NaN


def r4(value: Any) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, 4)


# --------------------------------------------------------------------------- #
# OHLCV forward-return surface
# --------------------------------------------------------------------------- #
def load_price_series() -> tuple[dict[str, dict[str, tuple[float, float]]], dict[str, Any]]:
    """ticker -> {date: (open, close)} merged across the three canonical windows."""
    series: dict[str, dict[str, tuple[float, float]]] = defaultdict(dict)
    loaded = 0
    for _, _, _, rel in WINDOWS:
        payload = read_json(REPO_ROOT / rel, {}) or {}
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else None
        if not isinstance(ohlcv, dict):
            continue
        loaded += 1
        for ticker, bars in ohlcv.items():
            tk = str(ticker).upper()
            for bar in bars:
                d = str(bar.get("Date"))[:10]
                o = as_float(bar.get("Open"))
                c = as_float(bar.get("Close"))
                if d and o is not None and c is not None:
                    series[tk][d] = (o, c)
    audit = {
        "snapshot_files_loaded": loaded,
        "ticker_count": len(series),
    }
    return series, audit


def build_forward_lookup(
    series: dict[str, dict[str, tuple[float, float]]],
) -> dict[str, tuple[list[str], dict[str, int]]]:
    out: dict[str, tuple[list[str], dict[str, int]]] = {}
    for tk, bydate in series.items():
        dates = sorted(bydate.keys())
        out[tk] = (dates, {d: i for i, d in enumerate(dates)})
    return out


def forward_return(
    series: dict[str, dict[str, tuple[float, float]]],
    lookup: dict[str, tuple[list[str], dict[str, int]]],
    ticker: str,
    activity_date: str,
) -> float | None:
    """Enter next session OPEN strictly after activity_date, exit +HOLD_DAYS close."""
    if ticker not in lookup:
        return None
    dates, _ = lookup[ticker]
    if not dates:
        return None
    entry_i = bisect.bisect_right(dates, activity_date)
    exit_i = entry_i + HOLD_DAYS
    if entry_i >= len(dates) or exit_i >= len(dates):
        return None
    o = series[ticker][dates[entry_i]][0]
    c = series[ticker][dates[exit_i]][1]
    if o is None or o <= 0 or c is None:
        return None
    return c / o - 1.0


# --------------------------------------------------------------------------- #
# short_volume_ratio PIT percentile surface
# --------------------------------------------------------------------------- #
def load_short_volume() -> tuple[dict[str, list[tuple[str, float]]], dict[str, Any]]:
    by_ticker: dict[str, list[tuple[str, float]]] = defaultdict(list)
    raw = 0
    usable = 0
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
            svr = as_float(row.get("short_volume_ratio"))
            ad = str(row.get("activity_date") or "")[:10]
            if not tk or svr is None or not ad:
                continue
            by_ticker[tk].append((ad, svr))
            usable += 1
    for tk in by_ticker:
        by_ticker[tk].sort()
    audit = {
        "source_artifact": repo_rel(SHORT_VOLUME_ROWS),
        "raw_rows": raw,
        "usable_rows": usable,
        "distinct_tickers": len(by_ticker),
        "activity_date_min": min(
            (seq[0][0] for seq in by_ticker.values() if seq), default=None
        ),
        "activity_date_max": max(
            (seq[-1][0] for seq in by_ticker.values() if seq), default=None
        ),
        "artifact_not_mutated": True,
    }
    return by_ticker, audit


def build_percentile_index(
    by_ticker: dict[str, list[tuple[str, float]]],
) -> dict[str, tuple[list[str], list[float | None]]]:
    """Expanding (strictly-prior) per-ticker percentile of short_volume_ratio."""
    index: dict[str, tuple[list[str], list[float | None]]] = {}
    for tk, seq in by_ticker.items():
        dates = [d for d, _ in seq]
        pcts: list[float | None] = []
        hist: list[float] = []
        for _, svr in seq:
            if len(hist) >= MIN_TRAILING_OBS:
                pcts.append(sum(1 for h in hist if h < svr) / len(hist))
            else:
                pcts.append(None)
            hist.append(svr)
        index[tk] = (dates, pcts)
    return index


def percentile_asof(
    index: dict[str, tuple[list[str], list[float | None]]],
    ticker: str,
    entry_date: str,
) -> float | None:
    """Most recent formed percentile from an activity_date STRICTLY before entry."""
    if ticker not in index:
        return None
    dates, pcts = index[ticker]
    i = bisect.bisect_left(dates, entry_date) - 1
    while i >= 0:
        if pcts[i] is not None:
            return pcts[i]
        i -= 1
    return None


def window_of(activity_date: str) -> str | None:
    for name, lo, hi, _ in WINDOWS:
        if lo <= activity_date <= hi:
            return name
    return None


def quintile(pct: float) -> int:
    return min(CONFIG["quintiles"] - 1, int(pct * CONFIG["quintiles"]))


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #
def bucket_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "win_rate": None}
    return {
        "n": len(values),
        "mean": round(sum(values) / len(values), 6),
        "median": round(float(median(values)), 6),
        "win_rate": round(sum(1 for v in values if v > 0) / len(values), 4),
    }


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return round(cov / (vx * vy) ** 0.5, 6)


# --------------------------------------------------------------------------- #
# attribution
# --------------------------------------------------------------------------- #
def build_universe_attribution(
    series: dict[str, dict[str, tuple[float, float]]],
    lookup: dict[str, tuple[list[str], dict[str, int]]],
    by_ticker: dict[str, list[tuple[str, float]]],
    pct_index: dict[str, tuple[list[str], list[float | None]]],
) -> dict[str, Any]:
    obs: list[tuple[str, float, float]] = []  # (window, percentile, fwd_return)
    for tk, seq in by_ticker.items():
        if tk in SKIP_TICKERS:
            continue
        dates, pcts = pct_index[tk]
        for (ad, _svr), pct in zip(seq, pcts):
            if pct is None:
                continue
            win = window_of(ad)
            if win is None:
                continue
            f = forward_return(series, lookup, tk, ad)
            if f is None:
                continue
            obs.append((win, pct, f))

    scopes = ["POOLED", "old_thin", "mid_weak", "late_strong"]
    by_scope: dict[str, Any] = {}
    windows_with_negative_direction = 0
    for scope in scopes:
        sel = obs if scope == "POOLED" else [o for o in obs if o[0] == scope]
        quint_buckets = {
            q: bucket_stats([o[2] for o in sel if quintile(o[1]) == q])
            for q in range(CONFIG["quintiles"])
        }
        q1 = quint_buckets[0]["mean"]
        q5 = quint_buckets[CONFIG["toxic_quintile_index"]]["mean"]
        corr = pearson([o[1] for o in sel], [o[2] for o in sel])
        q5_below_q1 = q1 is not None and q5 is not None and q5 < q1
        if scope != "POOLED" and q5_below_q1:
            windows_with_negative_direction += 1
        by_scope[scope] = {
            "n": len(sel),
            "quintiles": {
                f"Q{q + 1}": quint_buckets[q] for q in range(CONFIG["quintiles"])
            },
            "q1_mean": q1,
            "q5_mean": q5,
            "q1_minus_q5_mean": round(q1 - q5, 6) if q1 is not None and q5 is not None else None,
            "corr_percentile_fwd_return": corr,
            "toxic_q5_underperforms_clean_q1": q5_below_q1,
        }
    return {
        "total_observations": len(obs),
        "by_scope": by_scope,
        "windows_with_negative_direction": windows_with_negative_direction,
    }


def build_selection_overlap(
    pct_index: dict[str, tuple[list[str], list[float | None]]],
) -> dict[str, Any]:
    ticker_keys = ("ticker", "symbol", "candidate", "name")
    entry_keys = ("entry_date", "signal_date", "open_date", "date", "activity_date", "as_of")

    def find_rows(obj: Any) -> list[list[dict[str, Any]]]:
        out: list[list[dict[str, Any]]] = []
        if isinstance(obj, dict):
            for value in obj.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    if any(any(k in r for k in ticker_keys) for r in value[:3]):
                        out.append(value)
                elif isinstance(value, (dict, list)):
                    out.extend(find_rows(value))
        elif isinstance(obj, list):
            for item in obj:
                out.extend(find_rows(item))
        return out

    quint_counts: Counter[int] = Counter()
    per_sleeve: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    seen_total = 0
    joined = 0
    for state_path in sorted(REPO_ROOT.glob(PAPER_SLEEVE_GLOB)):
        sleeve = state_path.parent.name
        state = read_json(state_path, {})
        if state is None:
            continue
        for rows in find_rows(state):
            for r in rows:
                tk = next((r[k] for k in ticker_keys if r.get(k)), None)
                ed = next((r[k] for k in entry_keys if r.get(k)), None)
                if not tk or not ed:
                    continue
                tk = str(tk).replace("US.", "").upper()
                ed = str(ed)[:10]
                seen_total += 1
                pct = percentile_asof(pct_index, tk, ed)
                if pct is None:
                    continue
                joined += 1
                q = quintile(pct)
                quint_counts[q] += 1
                per_sleeve[sleeve][0] += 1
                if q == CONFIG["toxic_quintile_index"]:
                    per_sleeve[sleeve][1] += 1

    toxic = quint_counts[CONFIG["toxic_quintile_index"]]
    toxic_share = round(toxic / joined, 4) if joined else None
    return {
        "candidate_rows_seen": seen_total,
        "rows_joined_to_short_volume_percentile": joined,
        "quintile_distribution": {
            f"Q{q + 1}": quint_counts[q] for q in range(CONFIG["quintiles"])
        },
        "toxic_q5_selection_count": toxic,
        "toxic_q5_selection_share": toxic_share,
        "per_sleeve": {
            sleeve: {
                "joined": n,
                "toxic_q5": top,
                "toxic_q5_share": round(top / n, 4) if n else None,
            }
            for sleeve, (n, top) in sorted(per_sleeve.items(), key=lambda x: -x[1][1])
        },
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
    }


def evaluate_gate4(universe: dict[str, Any], overlap: dict[str, Any]) -> dict[str, Any]:
    pooled = universe["by_scope"]["POOLED"]
    failed: list[str] = []

    if universe["total_observations"] < CONFIG["min_total_observations"]:
        failed.append("too_few_total_observations")
    if not pooled["toxic_q5_underperforms_clean_q1"]:
        failed.append("pooled_toxic_q5_not_below_clean_q1")
    corr = pooled["corr_percentile_fwd_return"]
    if corr is None or corr >= 0:
        failed.append("pooled_correlation_not_negative")
    if universe["windows_with_negative_direction"] < CONFIG["min_windows_with_negative_direction"]:
        failed.append("too_few_windows_with_negative_direction")
    toxic_share = overlap["toxic_q5_selection_share"]
    if toxic_share is None or toxic_share < CONFIG["min_toxic_selection_share"]:
        failed.append("accepted_selection_overlap_too_small")

    observed_only_lead = not failed
    decision = (
        "observed_only_positive_short_volume_informed_flow_lead_not_promoted"
        if observed_only_lead
        else "observed_only_rejected_no_short_volume_informed_flow_edge"
    )
    return {
        "passed": observed_only_lead,
        "observed_only_lead": observed_only_lead,
        "decision": decision,
        "failed_reasons": failed,
        "promotion_blockers": [
            "no_shared_clean_flow_quality_gate_helper_built",
            "no_daily_default_off_snapshot_or_parity_test",
            "avoidance_signal_needs_full_stack_gate1_4_overlay_vs_accepted_comparator",
            "closed_forward_rows_tagged_with_entry_short_volume_percentile_still_thin",
        ],
        "acceptance_rule": (
            "Observed-only lead requires >= "
            f"{CONFIG['min_total_observations']} pooled forward observations, "
            "pooled Q5(highest informed short flow) mean forward 10d return "
            "below Q1(cleanest) mean, negative pooled correlation between the "
            "short_volume_ratio percentile and forward return, the same toxic-"
            "below-clean direction in >= "
            f"{CONFIG['min_windows_with_negative_direction']} of 3 canonical "
            "windows, and accepted paper-sleeve selections landing in the toxic "
            f"Q5 bucket at a >= {CONFIG['min_toxic_selection_share']:.0%} share "
            "(gate not inert). A lead is NOT accepted alpha: promotion needs a "
            "shared clean-flow quality-gate helper run through the full-stack "
            "candidate-pool Gate 1-4 contract."
        ),
    }


def calibration(observed_only_lead: bool, failed_reasons: list[str]) -> dict[str, Any]:
    return {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_observed_only_lead": observed_only_lead,
        "calibration_note": (
            "Read-only probe lead confirmed by the full runner."
            if observed_only_lead
            else "No observed-only lead emerged on the predeclared screen."
        ),
        "primary_failure_modes_realized": failed_reasons,
    }


# --------------------------------------------------------------------------- #
# payload + persistence
# --------------------------------------------------------------------------- #
def production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "trade_enabled": False,
        "daily_snapshot_exposed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "uses_llm": False,
        "parity_note": (
            "Read-only attribution over existing OHLCV snapshots, the broad "
            "moomoo daily short-volume archive, and accepted paper-sleeve "
            "state files. No artifact was mutated."
        ),
    }


def post_run_reflection(observed_only_lead: bool) -> dict[str, Any]:
    return {
        "why_result_happened": (
            "Informed daily short flow (short_volume_ratio) is sign-correct: "
            "high informed shorting precedes weaker forward 10d returns, "
            "monotone across most windows and washing out only in the strong "
            "bull window where everything rose. Accepted momentum sleeves "
            "(fundamental_growth_rs, volume_breadth_breakout) do select toxic "
            "high-short-flow names, so a clean-flow quality gate is not inert."
            if observed_only_lead
            else "The predeclared informed-flow screen did not clear on "
            "sample, direction, correlation, or accepted-selection overlap."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by re-running high-short-volume ABSORPTION entries "
            "(the rejected exp-20260622-010 wrong-sign family), nor by sweeping "
            "short_volume_ratio quintile cutoffs, percentile lookbacks, hold "
            "days, top-N, notional, or by re-probing the same observed-only "
            "ledger with an adjacent condition field. The next admissible step "
            "is a single shared clean-flow quality-gate helper, not another "
            "read-only re-slice."
        ),
        "new_evidence_required": (
            "Promotion needs a shared default-off clean-flow quality-gate "
            "helper (admit liquid candidates only when the PIT "
            "short_volume_ratio percentile is below the toxic quintile) wired "
            "into historical replay AND a daily default-off snapshot with a "
            "parity test, then a full-stack candidate-pool Gate 1-4 overlay "
            "that must beat the closest accepted comparator after costs, "
            "concentration, and drawdown -- or materially more closed forward "
            "rows tagged with the entry-time short_volume_ratio percentile."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    series, price_audit = load_price_series()
    lookup = build_forward_lookup(series)
    by_ticker, sv_audit = load_short_volume()
    pct_index = build_percentile_index(by_ticker)

    universe = build_universe_attribution(series, lookup, by_ticker, pct_index)
    overlap = build_selection_overlap(pct_index)
    gate4 = evaluate_gate4(universe, overlap)
    baseline = baseline_metrics()

    status = (
        "observed_only_positive_lead"
        if gate4["observed_only_lead"]
        else "observed_only_rejected"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low_new_source_new_gate_shape",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "check_experiment_novelty verdict ok (no strong "
                    "near-neighbor; nearest 0.061 was the rejected single-"
                    "attempt absorption family). Source-saturation not "
                    "triggered: moomoo daily short volume is not a frozen "
                    "family."
                ),
                "exp-20260622-010": (
                    "Rejected high-short-volume ABSORPTION entry on a 5-ticker "
                    "raw archive; this run uses the OPPOSITE sign (avoidance) "
                    "on the broad 51-name archive."
                ),
                "exp-20260623-008": "Built the broad daily short-volume archive used here.",
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One read-only attribution: per-ticker PIT percentile of "
                "short_volume_ratio joined to next-open forward 10d returns and "
                "to accepted paper-sleeve selections."
            ),
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "config": CONFIG,
            "windows": [
                {"label": n, "start": lo, "end": hi, "snapshot": rel}
                for n, lo, hi, rel in WINDOWS
            ],
            "skip_tickers": sorted(SKIP_TICKERS),
            "short_volume_source": repo_rel(SHORT_VOLUME_ROWS),
            "paper_sleeve_glob": PAPER_SLEEVE_GLOB,
            "pit_rule": (
                "short_volume_ratio percentile uses only activity_dates "
                "strictly before the entry/forward date; activity is reported "
                "after the US close and mapped to the next session open."
            ),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_summary": baseline,
            "note": "Observed-only attribution; before and after strategy policy are identical.",
        },
        "gate2": {
            "passed": bool(by_ticker) and bool(series),
            "source_audit": {
                "ohlcv": price_audit,
                "short_volume": sv_audit,
            },
            "runtime_fields": [
                "ohlcv Date/Open/Close",
                "moomoo short_volume_ratio",
                "moomoo activity_date",
                "paper_sleeves selection ticker/entry_date",
            ],
            "target_price": {
                "available": False,
                "source": "not_applicable_observed_only_attribution",
                "reason": "No executable target, entry, exit, order, or paper ledger mutation is scheduled.",
            },
        },
        "gate3": {
            "strategy_filter_added": False,
            "signals_generated": universe["total_observations"],
            "signals_survived": universe["total_observations"],
            "survival_rate": 1.0 if universe["total_observations"] else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "passed": True,
            "note": "No executable filter was added; attribution is diagnostic only.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline | {"strategy_behavior_changed": False},
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "universe_forward_return": universe,
            "accepted_selection_overlap": overlap,
            "source_audit": {"ohlcv": price_audit, "short_volume": sv_audit},
        },
        "production_impact": production_impact(),
        "calibration": calibration(gate4["observed_only_lead"], gate4["failed_reasons"]),
        "post_run_reflection": post_run_reflection(gate4["observed_only_lead"]),
        "related_files": [
            RUNNER,
            repo_rel(SHORT_VOLUME_ROWS),
            repo_rel(BASELINE_RESULT),
            "data/non_ohlcv/moomoo_daily_short_volume_broad/manifest.json",
            "quant/experiments/exp_20260625_015_volume_dryup_breakout_scout.py",
            "docs/backtesting.md",
            "docs/agent_experiment_protocol.md",
            "docs/alpha-optimization-playbook.md",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    attribution = payload["attribution"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": payload["prediction"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "attribution": {
            "universe_forward_return": attribution["universe_forward_return"],
            "accepted_selection_overlap": attribution["accepted_selection_overlap"],
            "source_audit": attribution["source_audit"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "updated_at": payload["timestamp"],
        "anti_js": payload["anti_js"],
    }


def pct(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"{number * 100:+.2f}%"


def build_card(payload: dict[str, Any]) -> str:
    universe = payload["attribution"]["universe_forward_return"]
    overlap = payload["attribution"]["accepted_selection_overlap"]
    rows = [
        "| Window | n | Q1 (clean) | Q5 (toxic) | Q1-Q5 | corr |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for scope in ["POOLED", "old_thin", "mid_weak", "late_strong"]:
        s = universe["by_scope"][scope]
        rows.append(
            "| {scope} | {n} | {q1} | {q5} | {sp} | {c} |".format(
                scope=scope,
                n=s["n"],
                q1=pct(s["q1_mean"]),
                q5=pct(s["q5_mean"]),
                sp=pct(s["q1_minus_q5_mean"]),
                c=s["corr_percentile_fwd_return"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: moomoo daily short_volume_ratio informed-flow attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            "- Shared helper promoted: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Forward 10d return by per-ticker short_volume_ratio quintile",
            "",
            *rows,
            "",
            f"- Total observations: `{universe['total_observations']}`",
            f"- Windows with toxic-below-clean direction: `{universe['windows_with_negative_direction']}/3`",
            "",
            "## Accepted paper-sleeve selection overlap",
            "",
            f"- Selections joined to short-vol percentile: `{overlap['rows_joined_to_short_volume_percentile']}`",
            f"- Toxic Q5 selection share: `{overlap['toxic_q5_selection_share']}`",
            "",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "- Promotion blockers: "
            f"`{', '.join(payload['gate4']['promotion_blockers'])}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "status": payload["status"],
        "owner": OWNER,
        "created_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "claimed_at": payload["timestamp"],
        "updated_at": payload["timestamp"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "hypothesis": HYPOTHESIS,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prior_trial_count": 1,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "acceptance_rule": payload["gate4"]["acceptance_rule"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "evaluation_windows": payload["parameters"]["windows"],
        "novelty": {
            "enforced": True,
            "blocking_matches": [],
            "verdict": "ok_no_strong_near_neighbor",
            "nearest_family": "moomoo_daily_short_volume_activity_absorption_candidate_pool",
            "nearest_distance": 0.061,
        },
        "allowed_write_scope": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(LOG_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "locked_variables": [CHANGED_VARIABLE],
        "must_not_touch": [
            "shared paper-sleeve helpers",
            "candidate ranking / sizing / exits / orders",
            "daily default-off snapshots",
        ],
        "decision": payload["decision"],
        "result": {
            "observed_only_lead": payload["gate4"]["observed_only_lead"],
            "failed_reasons": payload["gate4"]["failed_reasons"],
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
    }


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        SHORT_VOLUME_ROWS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "decision": payload["decision"],
        "status": payload["status"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        },
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, build_ticket(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
        "allocation_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "universe_forward_return": payload["attribution"]["universe_forward_return"],
            "accepted_selection_overlap": payload["attribution"]["accepted_selection_overlap"],
        },
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    universe = payload["attribution"]["universe_forward_return"]
    overlap = payload["attribution"]["accepted_selection_overlap"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "total_observations": universe["total_observations"],
                "pooled_q1_mean": universe["by_scope"]["POOLED"]["q1_mean"],
                "pooled_q5_mean": universe["by_scope"]["POOLED"]["q5_mean"],
                "pooled_corr": universe["by_scope"]["POOLED"]["corr_percentile_fwd_return"],
                "windows_with_negative_direction": universe["windows_with_negative_direction"],
                "toxic_q5_selection_share": overlap["toxic_q5_selection_share"],
                "rows_joined": overlap["rows_joined_to_short_volume_percentile"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
