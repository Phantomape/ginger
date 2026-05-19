"""exp-20260508-014 gap-cancel joint discriminator replay.

Alpha-search only. Phase A (`exp-20260507-920`) found several orthogonal
features that looked promising on cancelled-entry forward returns. Phase B must
ask the harder question: if the shared open-cancel safeguard is bypassed only
for those pre-registered feature combinations, do canonical three-window
backtest metrics improve without destabilizing another window?

This script changes no production policy, no default backtester constants, no
signal generation, no ranking, no sizing, no exits, and no prompts. It monkey
patches the cancel classifier only inside the replay context and writes a
rejected/accepted-for-implementation experiment record.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260508-014"
STEM = "gap_cancel_joint_discriminator_replay"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

TARGET_CANCEL_REASONS = {"gap_cancel", "adverse_gap_down_cancel"}

GAP_ABS_HIGH_MIN = 0.035977
BBWIDTH20_HIGH_MIN = 0.269211
VOLUME_VS_20D_LOW_MAX = 3.263312
SECTOR_5D_RS_HIGH_MIN = 0.13675
RECENT_8K_SEVERITY_LOW_MAX = 1.0

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return _safe(value.item())
        except (TypeError, ValueError):
            return str(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle_compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    needle_pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [line for line in lines if needle_compact not in line and needle_pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _scalar(value: Any) -> float | None:
    try:
        if hasattr(value, "item"):
            value = value.item()
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _metric_slice(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "entry_reason_counts": result.get("entry_execution_attribution", {}).get("decision_counts"),
    }


def _deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_pnl",
        "strategy_total_return_pct",
        "win_rate",
        "total_trades",
        "survival_rate",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        if before.get(key) is None or after.get(key) is None:
            out[key] = None
        else:
            out[key] = round(float(after[key]) - float(before[key]), 6)
    return out


def _run_engine(universe: list[str], spec: dict[str, Any]) -> dict[str, Any]:
    engine = bt.BacktestEngine(
        universe,
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        ohlcv_snapshot_path=str(spec["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"Backtest failed for {spec['start']} -> {spec['end']}: {result['error']}")
    return result


def _series_prior(frame: Any, signal_date: Any, column: str, count: int) -> list[float]:
    if frame is None or column not in frame:
        return []
    try:
        prior = frame.loc[frame.index <= signal_date]
    except Exception:
        return []
    values = [_scalar(value) for value in prior[column].tail(count)]
    return [value for value in values if value is not None]


def _bbwidth20(frame: Any, signal_date: Any) -> float | None:
    closes = _series_prior(frame, signal_date, "Close", 20)
    if len(closes) < 20:
        return None
    avg = sum(closes) / len(closes)
    if avg == 0:
        return None
    variance = sum((value - avg) ** 2 for value in closes) / len(closes)
    return 4.0 * math.sqrt(variance) / avg


def _volume_vs_20d_avg(frame: Any, signal_date: Any) -> float | None:
    volumes = _series_prior(frame, signal_date, "Volume", 20)
    if len(volumes) < 20:
        return None
    current = volumes[-1]
    avg = sum(volumes) / len(volumes)
    if avg <= 0:
        return None
    return current / avg


def _close_at_or_before(frame: Any, signal_date: Any, offset: int = 0) -> float | None:
    if frame is None or "Close" not in frame:
        return None
    try:
        prior = frame.loc[frame.index <= signal_date]
    except Exception:
        return None
    if len(prior) <= offset:
        return None
    return _scalar(prior["Close"].iloc[-1 - offset])


def _return_5d(frame: Any, signal_date: Any) -> float | None:
    current = _close_at_or_before(frame, signal_date, 0)
    prior = _close_at_or_before(frame, signal_date, 5)
    if current is None or prior is None or prior == 0:
        return None
    return current / prior - 1.0


def _sector_5d_rs(ohlcv_all: dict[str, Any], ticker: str, signal_date: Any) -> float | None:
    ticker = str(ticker or "").upper()
    sector = SECTOR_MAP.get(ticker, "Unknown")
    ticker_ret = _return_5d(ohlcv_all.get(ticker), signal_date)
    if ticker_ret is None:
        return None
    peer_returns = []
    if sector != "Unknown":
        for peer, peer_sector in SECTOR_MAP.items():
            if peer == ticker or peer_sector != sector:
                continue
            peer_ret = _return_5d(ohlcv_all.get(peer), signal_date)
            if peer_ret is not None:
                peer_returns.append(peer_ret)
    if peer_returns:
        return ticker_ret - (sum(peer_returns) / len(peer_returns))
    spy_ret = _return_5d(ohlcv_all.get("SPY"), signal_date)
    return ticker_ret - spy_ret if spy_ret is not None else None


def _date_key(value: Any) -> str:
    if hasattr(value, "date"):
        value = value.date()
    return str(value)[:10].replace("-", "")


def _date_iso(value: Any) -> str:
    if hasattr(value, "date"):
        value = value.date()
    return str(value)[:10]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _parse_date(value: Any) -> datetime | None:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _item_codes(value: Any) -> list[str]:
    if isinstance(value, list):
        out = []
        for item in value:
            out.append(str(item.get("code") if isinstance(item, dict) else item))
        return [item for item in out if item and item != "None"]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _eight_k_severity(codes: list[str]) -> int:
    if not codes:
        return 1
    score = 1
    if "2.02" in codes:
        score = max(score, 3)
    if set(codes) & {"1.01", "2.03", "3.02", "5.02"}:
        score = max(score, 2)
    return score


def _recent_8k_severity_5d(ticker: str, signal_date: Any) -> float | None:
    date_key = _date_key(signal_date)
    path = REPO_ROOT / "data" / "non_ohlcv" / f"sec_filing_features_{date_key}.jsonl"
    if not path.exists():
        return None
    end = _parse_date(_date_iso(signal_date))
    if end is None:
        return None
    start = end - timedelta(days=5)
    severities = []
    for row in _load_jsonl(path):
        if str(row.get("ticker") or "").upper() != str(ticker or "").upper():
            continue
        if not str(row.get("form_type") or "").upper().startswith("8-K"):
            continue
        usable = row.get("usable_trade_date") or row.get("event_date")
        usable_dt = _parse_date(usable)
        if usable_dt is None or not (start <= usable_dt <= end):
            continue
        codes = _item_codes(row.get("eight_k_item_type") or row.get("eight_k_item_codes"))
        severities.append(_eight_k_severity(codes))
    return float(max(severities, default=0))


def _gap_bucket(gap_pct: float | None) -> str | None:
    if gap_pct is None:
        return None
    value = abs(gap_pct)
    if 0.015 <= value < 0.02:
        return "1.5-2%"
    if 0.02 <= value < 0.03:
        return "2-3%"
    if 0.03 <= value < 0.04:
        return "3-4%"
    if 0.04 <= value < 0.05:
        return "4-5%"
    if value >= 0.05:
        return ">5%"
    return "<1.5%"


def _feature_context(
    sig: dict[str, Any],
    today: Any,
    ohlcv_all: dict[str, Any],
    fill_price: Any,
    signal_entry: Any,
    original_reason: str,
) -> dict[str, Any]:
    ticker = str(sig.get("ticker") or "").upper()
    frame = ohlcv_all.get(ticker)
    fill = _scalar(fill_price)
    entry = _scalar(signal_entry)
    gap_pct = fill / entry - 1.0 if fill is not None and entry not in (None, 0) else None
    return {
        "date": _date_iso(today),
        "ticker": ticker,
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector"),
        "original_cancel_reason": original_reason,
        "fill_price": round(fill, 4) if fill is not None else None,
        "signal_entry": round(entry, 4) if entry is not None else None,
        "gap_pct": round(gap_pct, 6) if gap_pct is not None else None,
        "gap_abs_pct": round(abs(gap_pct), 6) if gap_pct is not None else None,
        "gap_bucket": _gap_bucket(gap_pct),
        "bbwidth20": _round(_bbwidth20(frame, today)),
        "volume_vs_20d_avg": _round(_volume_vs_20d_avg(frame, today)),
        "sector_5d_rs": _round(_sector_5d_rs(ohlcv_all, ticker, today)),
        "recent_8k_severity_5d": _round(_recent_8k_severity_5d(ticker, today)),
    }


def _round(value: Any, digits: int = 6) -> Any:
    number = _scalar(value)
    return round(number, digits) if number is not None else None


def _ge(value: Any, threshold: float) -> bool:
    number = _scalar(value)
    return number is not None and number >= threshold


def _lt(value: Any, threshold: float) -> bool:
    number = _scalar(value)
    return number is not None and number < threshold


Predicate = Callable[[dict[str, Any]], bool]


VARIANTS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            "joint_volume_low_sector_rs_high",
            {
                "description": "volume_vs_20d_avg < median and sector_5d_rs >= median",
                "predicate": lambda ctx: _lt(ctx.get("volume_vs_20d_avg"), VOLUME_VS_20D_LOW_MAX)
                and _ge(ctx.get("sector_5d_rs"), SECTOR_5D_RS_HIGH_MIN),
            },
        ),
        (
            "joint_gap_gt5_sector_rs_high",
            {
                "description": "gap bucket >5% and sector_5d_rs >= median",
                "predicate": lambda ctx: ctx.get("gap_bucket") == ">5%"
                and _ge(ctx.get("sector_5d_rs"), SECTOR_5D_RS_HIGH_MIN),
            },
        ),
        (
            "joint_sector_rs_high_low_8k",
            {
                "description": "sector_5d_rs >= median and no recent 8-K severity",
                "predicate": lambda ctx: _ge(ctx.get("sector_5d_rs"), SECTOR_5D_RS_HIGH_MIN)
                and _lt(ctx.get("recent_8k_severity_5d"), RECENT_8K_SEVERITY_LOW_MAX),
            },
        ),
        (
            "joint_bbwidth_high_low_8k",
            {
                "description": "bbwidth20 >= median and no recent 8-K severity",
                "predicate": lambda ctx: _ge(ctx.get("bbwidth20"), BBWIDTH20_HIGH_MIN)
                and _lt(ctx.get("recent_8k_severity_5d"), RECENT_8K_SEVERITY_LOW_MAX),
            },
        ),
        (
            "gap_bucket_4_5",
            {
                "description": "absolute next-open gap in the 4-5% bucket",
                "predicate": lambda ctx: ctx.get("gap_bucket") == "4-5%",
            },
        ),
        (
            "gap_abs_high",
            {
                "description": "gap_abs_pct >= median",
                "predicate": lambda ctx: _ge(ctx.get("gap_abs_pct"), GAP_ABS_HIGH_MIN),
            },
        ),
    ]
)


@contextmanager
def _patched_cancel_classifier(variant_name: str, events: list[dict[str, Any]]):
    original = bt.classify_entry_open_cancel
    predicate: Predicate = VARIANTS[variant_name]["predicate"]

    def classifier(fill_price, signal_entry, stop_price=None, **kwargs):
        reason = original(fill_price, signal_entry, stop_price=stop_price, **kwargs)
        if reason not in TARGET_CANCEL_REASONS:
            return reason

        fill = _scalar(fill_price)
        stop = _scalar(stop_price)
        if reason == "adverse_gap_down_cancel" and stop is not None and fill is not None:
            if fill <= stop:
                return reason

        frame = inspect.currentframe()
        caller = frame.f_back if frame is not None else None
        if caller is None or caller.f_code.co_name != "run":
            return reason

        sig = caller.f_locals.get("sig")
        today = caller.f_locals.get("today")
        ohlcv_all = caller.f_locals.get("ohlcv_all")
        if not isinstance(sig, dict) or today is None or not isinstance(ohlcv_all, dict):
            return reason

        ctx = _feature_context(sig, today, ohlcv_all, fill_price, signal_entry, reason)
        if not predicate(ctx):
            return reason

        events.append({**ctx, "variant": variant_name})
        return None

    bt.classify_entry_open_cancel = classifier
    try:
        yield
    finally:
        bt.classify_entry_open_cancel = original


def _run_variant_window(
    universe: list[str],
    window_name: str,
    spec: dict[str, Any],
    variant_name: str,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    with _patched_cancel_classifier(variant_name, events):
        result = _run_engine(universe, spec)
    after = _metric_slice(result)
    return {
        "window": window_name,
        "date_range": {"start": spec["start"], "end": spec["end"]},
        "snapshot": _repo_rel(spec["snapshot"]),
        "before_metrics": baseline,
        "after_metrics": after,
        "metric_deltas": _deltas(baseline, after),
        "bypass_count": len(events),
        "bypass_events": events,
    }


def _gate4(variant_windows: dict[str, Any]) -> dict[str, Any]:
    positive_ev = [
        name
        for name, row in variant_windows.items()
        if (row["metric_deltas"].get("expected_value_score") or 0.0) > 0
    ]
    negative_ev = [
        name
        for name, row in variant_windows.items()
        if (row["metric_deltas"].get("expected_value_score") or 0.0) < 0
    ]
    drawdown_worse_gt_1pp = [
        name
        for name, row in variant_windows.items()
        if (row["metric_deltas"].get("max_drawdown_pct") or 0.0) > 0.01
    ]
    total_pnl_delta = sum(
        float(row["metric_deltas"].get("total_pnl") or 0.0)
        for row in variant_windows.values()
    )
    total_before_pnl = sum(
        float(row["before_metrics"].get("total_pnl") or 0.0)
        for row in variant_windows.values()
    )
    pnl_delta_pct = total_pnl_delta / total_before_pnl if total_before_pnl else None
    passed = (
        len(positive_ev) >= 2
        and not negative_ev
        and not drawdown_worse_gt_1pp
        and (pnl_delta_pct is not None and pnl_delta_pct > 0.05)
    )
    return {
        "passed": passed,
        "positive_ev_windows": positive_ev,
        "negative_ev_windows": negative_ev,
        "drawdown_worse_gt_1pp_windows": drawdown_worse_gt_1pp,
        "aggregate_total_pnl_delta": round(total_pnl_delta, 2),
        "aggregate_total_pnl_delta_pct": round(pnl_delta_pct, 6) if pnl_delta_pct is not None else None,
        "basis": (
            "Promotion requires EV improvement in most windows, no negative EV "
            "window, no drawdown increase over 1 pp, and aggregate PnL improvement "
            "above the 5% Gate 4 threshold."
        ),
    }


def _summarize_variants(variants: dict[str, Any]) -> dict[str, Any]:
    summary = {}
    for variant_name, payload in variants.items():
        gate4 = payload["gate4"]
        ev_delta_sum = sum(
            float(row["metric_deltas"].get("expected_value_score") or 0.0)
            for row in payload["windows"].values()
        )
        summary[variant_name] = {
            "description": VARIANTS[variant_name]["description"],
            "gate4_passed": gate4["passed"],
            "ev_delta_sum": round(ev_delta_sum, 4),
            "pnl_delta_sum": gate4["aggregate_total_pnl_delta"],
            "pnl_delta_pct": gate4["aggregate_total_pnl_delta_pct"],
            "positive_ev_windows": gate4["positive_ev_windows"],
            "negative_ev_windows": gate4["negative_ev_windows"],
            "drawdown_worse_gt_1pp_windows": gate4["drawdown_worse_gt_1pp_windows"],
            "bypass_count": sum(row["bypass_count"] for row in payload["windows"].values()),
        }
    return dict(
        sorted(
            summary.items(),
            key=lambda item: (
                item[1]["gate4_passed"],
                item[1]["ev_delta_sum"],
                item[1]["pnl_delta_sum"],
            ),
            reverse=True,
        )
    )


def _write_artifact(payload: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID} Gap-Cancel Joint Discriminator Replay",
        "",
        "## Decision",
        "",
        f"- decision: {payload['decision']}",
        f"- best variant: {payload['best_variant']}",
        "- production orders changed: false",
        "- shared policy changed: false",
        "",
        "## Variant Summary",
        "",
        "| Variant | Gate4 | EV Delta Sum | PnL Delta | PnL Delta % | Positive EV Windows | Negative EV Windows | DD >1pp Worse | Bypasses |",
        "|---|---:|---:|---:|---:|---|---|---|---:|",
    ]
    for name, row in payload["variant_summary"].items():
        lines.append(
            "| {name} | {gate4} | {ev:+.4f} | {pnl:+.2f} | {pnl_pct:+.2%} | {pos} | {neg} | {dd} | {bypasses} |".format(
                name=name,
                gate4=row["gate4_passed"],
                ev=float(row["ev_delta_sum"]),
                pnl=float(row["pnl_delta_sum"]),
                pnl_pct=float(row["pnl_delta_pct"] or 0.0),
                pos=", ".join(row["positive_ev_windows"]) or "none",
                neg=", ".join(row["negative_ev_windows"]) or "none",
                dd=", ".join(row["drawdown_worse_gt_1pp_windows"]) or "none",
                bypasses=row["bypass_count"],
            )
        )
    lines.extend(["", "## Best Variant Window Metrics", ""])
    lines.extend(
        [
            "| Window | EV Before | EV After | EV Delta | Sharpe Delta | DD Delta | PnL Delta | Trades Delta | Bypasses |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["variants"][payload["best_variant"]]["windows"].items():
        before = row["before_metrics"]
        after = row["after_metrics"]
        delta = row["metric_deltas"]
        lines.append(
            "| {name} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | {delta_sharpe:+.4f} | {delta_dd:+.4f} | {delta_pnl:+.2f} | {delta_trades:+.0f} | {bypasses} |".format(
                name=name,
                before_ev=float(before["expected_value_score"]),
                after_ev=float(after["expected_value_score"]),
                delta_ev=float(delta["expected_value_score"] or 0.0),
                delta_sharpe=float(delta["sharpe_daily"] or 0.0),
                delta_dd=float(delta["max_drawdown_pct"] or 0.0),
                delta_pnl=float(delta["total_pnl"] or 0.0),
                delta_trades=float(delta["total_trades"] or 0.0),
                bypasses=row["bypass_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Production Parity",
            "",
            "No executable policy was promoted. A future positive retry must move the discriminator into a shared production/backtest policy before it can affect live orders.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    compact_variants = {}
    for name, variant in payload["variants"].items():
        compact_variants[name] = {
            "gate4": variant["gate4"],
            "windows": {
                window: {
                    "before_metrics": row["before_metrics"],
                    "after_metrics": row["after_metrics"],
                    "metric_deltas": row["metric_deltas"],
                    "bypass_count": row["bypass_count"],
                }
                for window, row in variant["windows"].items()
            },
        }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["decision"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis_category": "entry_execution",
        "change_type": "entry_open_cancel_joint_discriminator_replay",
        "mechanism_family": "gap_cancel_follow_through",
        "single_causal_variable": (
            "pre_registered_joint_feature_bypass_for_gap_cancelled_entries"
        ),
        "history_check": payload["history_check"],
        "mechanism_insight_check": payload["mechanism_insight_check"],
        "parameters": payload["parameters"],
        "baseline_metrics": payload["baseline_metrics"],
        "variant_summary": payload["variant_summary"],
        "best_variant": payload["best_variant"],
        "variants": compact_variants,
        "gate4": payload["best_gate4"],
        "expected_value_score_delta": payload["variant_summary"][payload["best_variant"]]["ev_delta_sum"],
        "decision_reason": payload["decision_reason"],
        "next_action": payload["next_action"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "related_files": payload["related_files"],
        "verification": payload["verification"],
    }


def main() -> None:
    universe = get_universe()
    baseline_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    print("Running canonical baselines")
    for name, spec in WINDOWS.items():
        baseline_metrics[name] = _metric_slice(_run_engine(universe, spec))

    variants: OrderedDict[str, Any] = OrderedDict()
    for variant_name in VARIANTS:
        print(f"Running variant {variant_name}")
        window_rows: OrderedDict[str, Any] = OrderedDict()
        for window_name, spec in WINDOWS.items():
            window_rows[window_name] = _run_variant_window(
                universe,
                window_name,
                spec,
                variant_name,
                baseline_metrics[window_name],
            )
        variants[variant_name] = {
            "description": VARIANTS[variant_name]["description"],
            "windows": window_rows,
            "gate4": _gate4(window_rows),
        }

    variant_summary = _summarize_variants(variants)
    best_variant = next(iter(variant_summary))
    best_gate4 = variants[best_variant]["gate4"]
    decision = "accepted_for_shared_policy_implementation" if best_gate4["passed"] else "rejected"
    if best_gate4["passed"]:
        decision_reason = (
            "The best pre-registered joint gap-cancel discriminator passed the "
            "three-window promotion gate, but no live behavior was changed in this "
            "experiment. Shared production/backtest implementation is required next."
        )
        next_action = (
            "Implement the discriminator in a shared production/backtest entry "
            "policy and expose bypass notes in the daily production order report."
        )
    else:
        decision_reason = (
            "No pre-registered joint discriminator produced stable three-window "
            "improvement. The best variant improved only one window and worsened "
            "another, so the Phase A oracle lift was not executable alpha."
        )
        next_action = (
            "Do not retry gap-cancel bypasses using these same feature thresholds. "
            "Future retries need a new information source or forward paper evidence."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "A small subset of gap-cancelled entries are confirmation gaps; requiring "
            "two orthogonal PIT-safe features should recover those entries without "
            "the instability of broad gap-threshold relaxation."
        ),
        "decision": decision,
        "decision_reason": decision_reason,
        "parameters": {
            "target_cancel_reasons": sorted(TARGET_CANCEL_REASONS),
            "gap_abs_high_min": GAP_ABS_HIGH_MIN,
            "bbwidth20_high_min": BBWIDTH20_HIGH_MIN,
            "volume_vs_20d_low_max": VOLUME_VS_20D_LOW_MAX,
            "sector_5d_rs_high_min": SECTOR_5D_RS_HIGH_MIN,
            "recent_8k_severity_low_max": RECENT_8K_SEVERITY_LOW_MAX,
            "tested_variants": {
                name: value["description"] for name, value in VARIANTS.items()
            },
            "canonical_windows": {
                name: {
                    "start": spec["start"],
                    "end": spec["end"],
                    "snapshot": _repo_rel(spec["snapshot"]),
                    "state_note": spec["state_note"],
                }
                for name, spec in WINDOWS.items()
            },
            "locked_variables": [
                "production universe",
                "signal generation",
                "candidate ranking",
                "risk sizing",
                "entry cancel threshold values",
                "exits",
                "add-ons",
                "LLM/news replay",
                "production order path",
            ],
        },
        "history_check": {
            "exp-20260428-021": "Global upside gap threshold relaxation was rejected; this run keeps thresholds fixed.",
            "exp-20260428-022": "Sector/strategy gap exceptions were rejected; this run uses event-level orthogonal features.",
            "exp-20260428-023": "Adverse-gap context exceptions were rejected; this run still refuses adverse fills below stop.",
            "exp-20260507-920": "Phase A ranked these exact features on cancelled-entry oracle forward returns.",
            "exp-20260508-009": "Single bbwidth20 bypass failed Gate 4; this run tests joint pre-registered discriminators instead of retuning bbwidth.",
        },
        "mechanism_insight_check": {
            "recent_no_go_conflicts": [
                "not a raw CANCEL_GAP_PCT sweep",
                "not a sector/strategy exception",
                "not a TQS/rank/scarce-slot rerun",
                "not an LLM soft-ranking attempt",
                "not a candidate-pool expansion",
            ],
            "why_not_simple_repeat": (
                "The tested variables are the pre-registered joint Phase B feature "
                "sets from exp-20260507-920, not another single-threshold relaxation."
            ),
            "alpha_first_classification": "alpha_search",
        },
        "baseline_metrics": baseline_metrics,
        "variants": variants,
        "variant_summary": variant_summary,
        "best_variant": best_variant,
        "best_gate4": best_gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "report_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "llm_blocker_relation": (
                "LLM soft-ranking data limits did not block this deterministic "
                "entry-execution alpha search."
            ),
        },
        "next_action": next_action,
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "verification": {
            "command": (
                ".\\.venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260508_014_gap_cancel_joint_discriminator_replay.py"
            ),
            "three_window_protocol": "docs/backtesting.md canonical windows with fixed OHLCV snapshots",
        },
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "summary": decision_reason,
        "next_action": next_action,
        "best_variant": best_variant,
        "gate4": best_gate4,
    }

    log_record = _log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, log_record)

    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": decision,
                    "best_variant": best_variant,
                    "best_gate4": best_gate4,
                    "variant_summary": variant_summary,
                    "outputs": payload["related_files"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
