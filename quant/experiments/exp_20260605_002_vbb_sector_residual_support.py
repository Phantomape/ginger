"""exp-20260605-002: VBB sector-residual notional support scout.

Replay-only alpha scout. Single causal variable: apply a 1.05x default-off
paper notional scalar to already-selected VOLUME_BREADTH_BREAKOUT_PAPER
candidates whose signal-date 20-day ticker return exceeds the public-sector
median by at least 3pp (with at least 5 same-sector return observations).

BEFORE: accepted VBB paper trades from exp-20260529-004 chain (with all
accepted scalars: breadth-intensity, high-close, cost-liquidity applied).
AFTER: same trades with sector-residual 1.05x scalar additionally applied
to qualifying candidates.

Mechanism is analogous to the accepted exp-20260602-010 FGRS sector-residual
support, applied to the VBB sleeve using only public sector classification
and signal-day OHLCV data. Core signals, baseline ordering, sizing, exits,
LLM/news, watchlists, and live orders are unchanged. No JavaScript used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median as stat_median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT, ROOT / "quant", ROOT / "quant" / "experiments", ROOT / "quant" / "experiments" / "legacy"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
from quant import broad_market_sector_map  # noqa: E402


EXPERIMENT_ID = "exp-20260605-002"
STEM = "vbb_sector_residual_support"
TRIAL_FAMILY = "volume_breadth_breakout_sector_residual_strength_support"
CHANGED_VARIABLE = "vbb_sector_residual_strength_support_scalar_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = "exp-20260529-004"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260529_004_vbb_cost_liquidity_support.json"
)

RET20_EXCESS_SECTOR_MIN = 0.03
MIN_SECTOR_MEMBER_RETURNS = 5
SUPPORT_SCALAR = 1.05
COST_LIQ_SCALAR = 1.05

MIN_TARGET_TRADES = 10
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

WINDOW_SNAPSHOTS: dict[str, str] = {
    "late_strong": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    "mid_weak": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    "old_thin": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _date_str(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _load_snapshot(path: str) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    raw = payload.get("ohlcv") if isinstance(payload, dict) else payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw or {}).items():
        clean = sorted(
            [r for r in rows or [] if _date_str(r)],
            key=_date_str,
        )
        out[str(ticker).upper()] = clean
    return out


class SectorResidualIndex:
    def __init__(
        self,
        snapshot: dict[str, list[dict[str, Any]]],
        sector_cache: dict[str, Any],
    ) -> None:
        self.snapshot = snapshot
        self.sector_cache = sector_cache
        self.row_index: dict[str, dict[str, int]] = {
            ticker: {_date_str(row): idx for idx, row in enumerate(rows)}
            for ticker, rows in snapshot.items()
        }
        self._ret20_cache: dict[tuple[str, str], float | None] = {}
        self._sector_cache: dict[tuple[str, str], list[float]] = {}
        self._lookup_cache: dict[str, dict[str, Any]] = {}

    def _lookup(self, ticker: str) -> dict[str, Any]:
        norm = str(ticker or "").upper()
        if norm not in self._lookup_cache:
            self._lookup_cache[norm] = broad_market_sector_map.lookup_sector(
                norm, self.sector_cache
            )
        return self._lookup_cache[norm]

    def _ret20(self, ticker: str, date: str) -> float | None:
        norm = str(ticker or "").upper()
        key = (norm, date)
        if key in self._ret20_cache:
            return self._ret20_cache[key]
        rows = self.snapshot.get(norm) or []
        idx = (self.row_index.get(norm) or {}).get(date)
        if idx is None or idx < 20:
            self._ret20_cache[key] = None
            return None
        c_now = _as_float(rows[idx].get("Close") or rows[idx].get("close"))
        c_20 = _as_float(rows[idx - 20].get("Close") or rows[idx - 20].get("close"))
        if c_now is None or c_20 is None or c_20 <= 0.0:
            self._ret20_cache[key] = None
            return None
        result = (c_now / c_20) - 1.0
        self._ret20_cache[key] = result
        return result

    def _sector_returns(self, sector: str, date: str) -> list[float]:
        key = (sector, date)
        if key in self._sector_cache:
            return self._sector_cache[key]
        values: list[float] = []
        for ticker in self.snapshot:
            lk = self._lookup(ticker)
            if lk.get("status") != broad_market_sector_map.OK_STATUS:
                continue
            if lk.get("sector") != sector:
                continue
            ret = self._ret20(ticker, date)
            if ret is not None and math.isfinite(ret):
                values.append(float(ret))
        self._sector_cache[key] = values
        return values

    def context(self, ticker: str, signal_date: str) -> dict[str, Any]:
        lk = self._lookup(ticker)
        sector = lk.get("sector")
        stock_ret20 = self._ret20(ticker, signal_date)
        base_ctx: dict[str, Any] = {
            "vbb_sector_residual_rule_version": RULE_VERSION,
            "vbb_sector_residual_known_at": (
                "signal-day close plus persisted public sector cache"
            ),
            "vbb_sector_residual_trade_enabled": False,
            "vbb_sector_residual_alters_orders": False,
            "vbb_sector_residual_min_ret20_excess_sector": RET20_EXCESS_SECTOR_MIN,
            "vbb_sector_residual_min_sector_members": MIN_SECTOR_MEMBER_RETURNS,
            "sector_lookup_status": lk.get("status"),
            "sector": sector,
        }
        if lk.get("status") != broad_market_sector_map.OK_STATUS or not sector:
            return {
                **base_ctx,
                "vbb_sector_residual_status": "missing_sector",
                "vbb_sector_residual_pass_v1": False,
                "vbb_sector_residual_support_scalar": 1.0,
                "ret20_excess_sector": None,
                "sector_member_return_count": 0,
            }
        if stock_ret20 is None:
            return {
                **base_ctx,
                "vbb_sector_residual_status": "missing_stock_ret20",
                "vbb_sector_residual_pass_v1": False,
                "vbb_sector_residual_support_scalar": 1.0,
                "stock_ret20": None,
                "ret20_excess_sector": None,
                "sector_member_return_count": 0,
            }
        sector_values = self._sector_returns(str(sector), signal_date)
        if len(sector_values) < MIN_SECTOR_MEMBER_RETURNS:
            return {
                **base_ctx,
                "vbb_sector_residual_status": "insufficient_sector_members",
                "vbb_sector_residual_pass_v1": False,
                "vbb_sector_residual_support_scalar": 1.0,
                "stock_ret20": _round(stock_ret20, 6),
                "ret20_excess_sector": None,
                "sector_member_return_count": len(sector_values),
            }
        sector_median = stat_median(sector_values)
        excess = float(stock_ret20) - float(sector_median)
        passed = excess >= RET20_EXCESS_SECTOR_MIN
        return {
            **base_ctx,
            "vbb_sector_residual_status": "ok" if passed else "ret20_excess_below_floor",
            "vbb_sector_residual_pass_v1": passed,
            "vbb_sector_residual_support_scalar": SUPPORT_SCALAR if passed else 1.0,
            "stock_ret20": _round(stock_ret20, 6),
            "sector_median_ret20": _round(sector_median, 6),
            "ret20_excess_sector": _round(excess, 6),
            "sector_member_return_count": len(sector_values),
        }


def _load_source_rows_by_window() -> OrderedDict[str, list[dict[str, Any]]]:
    payload = json.loads(SOURCE_ARTIFACT.read_text(encoding="utf-8"))
    raw = payload.get("before_vbb_trades_by_window") or {}
    rows: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for label in base.WINDOWS:
        window_rows = raw.get(label) or []
        rows[label] = [dict(row) for row in window_rows if isinstance(row, dict)]
    return rows


def _apply_accepted_cost_liq(row: dict[str, Any]) -> dict[str, Any]:
    """Apply 1.05x cost-liquidity scalar if cost_liquidity_support_pass_v1."""
    pnl = _as_float(row.get("pnl"))
    notional = _as_float(row.get("paper_notional_usd"))
    if pnl is None:
        return row
    passes = bool(row.get("cost_liquidity_support_pass_v1"))
    if passes:
        scalar = COST_LIQ_SCALAR
        row = dict(row)
        row["pnl"] = _round(pnl * scalar, 2)
        if notional is not None:
            row["paper_notional_usd"] = _round(notional * scalar, 2)
        row["cost_liquidity_applied_in_sector_residual_exp"] = True
    return row


def _build_sector_residual_indexes() -> OrderedDict[str, SectorResidualIndex]:
    sector_cache = broad_market_sector_map.load_cache()
    indexes: OrderedDict[str, SectorResidualIndex] = OrderedDict()
    for label in base.WINDOWS:
        snap_path = WINDOW_SNAPSHOTS.get(label)
        if not snap_path:
            raise ValueError(f"No OHLCV snapshot configured for window {label!r}")
        indexes[label] = SectorResidualIndex(_load_snapshot(snap_path), sector_cache)
    return indexes


def _select_supported_trades(
    source_rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    indexes: OrderedDict[str, SectorResidualIndex],
) -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    before_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    after_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts: OrderedDict[str, dict[str, int]] = OrderedDict()
    supported_counts: OrderedDict[str, int] = OrderedDict()
    supported_samples: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for label, rows in source_rows_by_window.items():
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        incremental_rows: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        samples: list[dict[str, Any]] = []
        index = indexes[label]

        for raw_row in rows:
            # Reconstruct the full accepted VBB state (with cost-liquidity).
            row = _apply_accepted_cost_liq(dict(raw_row))
            base_pnl = _as_float(row.get("pnl"))
            if base_pnl is None:
                continue
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            ctx = index.context(ticker, signal_date)
            status = str(ctx.get("vbb_sector_residual_status") or "unknown")
            counts[status] += 1

            before_trade = {
                **row,
                **ctx,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "strategy": "volume_breadth_breakout_paper",
                "pnl": _round(base_pnl, 2),
                "paper_pnl": _round(base_pnl, 2),
                "pnl_without_vbb_sector_residual": _round(base_pnl, 2),
                "paper_pnl_source": "pnl_with_all_prior_scalars_without_sector_residual",
                "trade_enabled": False,
                "alters_orders": False,
            }

            scalar = SUPPORT_SCALAR if ctx["vbb_sector_residual_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_vbb_sector_residual_support",
            }

            before_rows.append(before_trade)
            after_rows.append(after_trade)

            if ctx["vbb_sector_residual_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental_rows.append({
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "vbb_sector_residual_incremental_support",
                })
                if len(samples) < 10:
                    samples.append(after_trade)

        before_by_window[label] = before_rows
        after_by_window[label] = after_rows
        incremental_by_window[label] = incremental_rows
        status_counts[label] = dict(sorted(counts.items()))
        supported_counts[label] = len(incremental_rows)
        supported_samples[label] = samples

    diagnostics = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "source_artifact": _repo_rel(SOURCE_ARTIFACT),
        "supported_trade_count_by_window": dict(supported_counts),
        "sector_residual_status_counts_by_window": dict(status_counts),
        "supported_trade_sample_by_window": dict(supported_samples),
    }
    return before_by_window, after_by_window, incremental_by_window, diagnostics


def _load_baselines() -> OrderedDict[str, dict[str, Any]]:
    baselines: OrderedDict[str, dict[str, Any]] = OrderedDict()
    universe = sorted(base.get_universe())
    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] running baseline")
        result = base.shadow._run_baseline(universe, cfg)
        baselines[label] = {
            "result": result,
            "metrics": base.overlay_helper._metrics(result),
        }
    return baselines


def _run_windows(
    baselines: OrderedDict[str, dict[str, Any]],
    before_by_window: OrderedDict[str, list[dict[str, Any]]],
    after_by_window: OrderedDict[str, list[dict[str, Any]]],
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label in base.WINDOWS:
        baseline_result = baselines[label]["result"]
        before_trades = before_by_window[label]
        after_trades = after_by_window[label]
        incremental_trades = incremental_by_window[label]

        overlay_before = base._overlay_from_paper_trades(baseline_result, before_trades)
        overlay_after = base._overlay_from_paper_trades(baseline_result, after_trades)

        metrics_before = base.overlay_helper._metrics_with_overlay(baseline_result, overlay_before)
        metrics_after = base.overlay_helper._metrics_with_overlay(baseline_result, overlay_after)
        delta = base.overlay_helper._delta(metrics_after, metrics_before)

        rows[label] = {
            "label": label,
            "before": metrics_before,
            "after": metrics_after,
            "delta": delta,
            "before_trade_count": len(before_trades),
            "after_trade_count": len(after_trades),
            "incremental_trade_count": len(incremental_trades),
            "target_trade_count": len(incremental_trades),
            "before_pnl_usd": _round(
                sum(_as_float(r.get("pnl") or 0.0) for r in before_trades), 2
            ),
            "after_pnl_usd": _round(
                sum(_as_float(r.get("pnl") or 0.0) for r in after_trades), 2
            ),
            "incremental_pnl_usd": _round(
                sum(_as_float(r.get("pnl") or 0.0) for r in incremental_trades), 2
            ),
        }
    return rows


def _aggregate(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(r["before"]["expected_value_score"] or 0.0) for r in window_rows.values())
    after_ev = sum(float(r["after"]["expected_value_score"] or 0.0) for r in window_rows.values())
    before_pnl = sum(float(r["before"]["total_pnl"] or 0.0) for r in window_rows.values())
    after_pnl = sum(float(r["after"]["total_pnl"] or 0.0) for r in window_rows.values())
    dd_before = max(float(r["before"]["max_drawdown_pct"] or 0.0) for r in window_rows.values())
    dd_after = max(float(r["after"]["max_drawdown_pct"] or 0.0) for r in window_rows.values())
    return {
        "before": {
            "expected_value_score": _round(before_ev, 6),
            "total_pnl": _round(before_pnl, 2),
            "max_drawdown_pct": _round(dd_before, 6),
        },
        "after": {
            "expected_value_score": _round(after_ev, 6),
            "total_pnl": _round(after_pnl, 2),
            "max_drawdown_pct": _round(dd_after, 6),
        },
        "delta": {
            "expected_value_score": _round(after_ev - before_ev, 6),
            "expected_value_score_pct": _round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
            "total_pnl": _round(after_pnl - before_pnl, 2),
            "max_drawdown_pct": _round(dd_after - dd_before, 6),
        },
    }


def _target_summary(
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    all_incremental = [r for rows in incremental_by_window.values() for r in rows]
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    trades_by_window = {label: len(rows) for label, rows in incremental_by_window.items()}
    for trade in all_incremental:
        ticker = str(trade.get("ticker") or "").upper()
        pnl = _as_float(trade.get("pnl") or 0.0) or 0.0
        by_ticker_count[ticker] += 1
        by_ticker_pnl[ticker] += pnl
    positive = {t: p for t, p in by_ticker_pnl.items() if p > 0}
    positive_total = sum(positive.values())
    max_single = (
        _round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    pnl_hhi = (
        _round(sum((p / positive_total) ** 2 for p in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    ticker_rows = sorted(
        [
            {
                "ticker": t,
                "trade_count": by_ticker_count[t],
                "incremental_pnl_usd": _round(by_ticker_pnl[t], 2),
                "positive_pnl_share": _round(positive.get(t, 0.0) / positive_total, 6)
                if positive_total > 0
                else None,
            }
            for t in by_ticker_count
        ],
        key=lambda r: -(float(r["incremental_pnl_usd"] or 0.0)),
    )
    return {
        "target_trade_count": len(all_incremental),
        "trades_by_window": trades_by_window,
        "incremental_pnl_by_window": {
            label: _round(sum(_as_float(r.get("pnl") or 0.0) for r in rows), 2)
            for label, rows in incremental_by_window.items()
        },
        "total_incremental_pnl_usd": _round(sum(_as_float(r.get("pnl") or 0.0) for r in all_incremental), 2),
        "positive_incremental_pnl_usd": _round(positive_total, 2),
        "max_single_positive_share": max_single,
        "positive_pnl_hhi": pnl_hhi,
        "ticker_rows": ticker_rows,
    }


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    current_ev = float(aggregate["before"]["expected_value_score"])
    current_pnl = float(aggregate["before"]["total_pnl"])
    ev_delta = current_ev - CANONICAL_DOC_EV
    pnl_delta = current_pnl - CANONICAL_DOC_PNL
    # The "before" includes VBB paper overlay so will be higher than bare baseline.
    matches = abs(ev_delta) <= 3.0 and abs(pnl_delta) <= 30_000.0
    return {
        "baseline_matches_docs": matches,
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_before_ev": _round(current_ev, 6),
        "current_before_pnl": _round(current_pnl, 2),
        "ev_delta_vs_docs": _round(ev_delta, 6),
        "pnl_delta_vs_docs": _round(pnl_delta, 2),
        "note": (
            "The 'before' metric includes the VBB paper overlay on top of the "
            "core baseline, so it will be higher than the bare canonical "
            "docs/backtesting.md baseline. The before/after comparison uses one "
            "consistent code path."
        ),
    }


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_improved = [
        label for label, r in window_rows.items()
        if float(r["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_improved = [
        label for label, r in window_rows.items()
        if float(r["delta"].get("total_pnl") or 0.0) > 0.0
    ]
    max_dd_delta = max(
        float(r["delta"].get("max_drawdown_pct") or 0.0) for r in window_rows.values()
    )
    min_survival = min(
        float(r["after"].get("survival_rate") or 0.0) for r in window_rows.values()
    )
    target_count = int(target_summary["target_trade_count"])
    target_windows = sum(1 for v in target_summary["trades_by_window"].values() if v > 0)
    concentration_passed = (
        target_summary["max_single_positive_share"] is not None
        and float(target_summary["max_single_positive_share"]) <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and float(target_summary["positive_pnl_hhi"]) <= MAX_POSITIVE_HHI
    )
    gates: OrderedDict[str, bool] = OrderedDict([
        ("aggregate_expected_value_positive", float(aggregate["delta"]["expected_value_score"]) > 0.0),
        ("aggregate_pnl_positive", float(aggregate["delta"]["total_pnl"]) > 0.0),
        ("all_windows_expected_value_improved", len(ev_improved) == len(window_rows)),
        ("all_windows_pnl_improved", len(pnl_improved) == len(window_rows)),
        ("target_trade_count_passed", target_count >= MIN_TARGET_TRADES),
        ("target_window_count_passed", target_windows >= MIN_TARGET_WINDOWS),
        ("drawdown_drift_passed", max_dd_delta <= MAX_DRAWDOWN_WORSE),
        ("survival_floor_passed", min_survival >= 0.05),
        ("concentration_guard_passed", concentration_passed),
    ])
    failed = [name for name, passed in gates.items() if not passed]
    gate_passed = not failed
    if gate_passed:
        decision = "positive_replay_lead_vbb_sector_residual"
        rationale = (
            "VBB sector-residual support passed the three-window alpha gate as a replay-only lead; "
            "a shared adapter and parity tests are required before retention."
        )
    else:
        decision = "rejected_vbb_sector_residual_support"
        rationale = (
            "VBB sector-residual support failed Gate 4; no production, shared adapter, "
            "or strategy behavior is retained."
        )
    return {
        "passed": gate_passed,
        "alpha_passed": gate_passed,
        "promotable_now": False,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_improved,
        "pnl_windows_improved": pnl_improved,
        "max_drawdown_delta": _round(max_dd_delta, 6),
        "min_survival_rate": _round(min_survival, 6),
        "requires_shared_adapter_before_promotion": gate_passed,
        "requires_parity_before_promotion": gate_passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: VBB Sector-Residual Support",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- incremental target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | incremental trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['incremental_trade_count']} |"
        )
    lines.extend([
        "",
        "## Baseline Context",
        "",
        payload["baseline_context"]["note"],
        "",
        "## Production Parity",
        "",
        "Replay-only and default-off paper only. Uses persisted "
        "`broad_market_sector_map` cache plus fixed OHLCV snapshots. "
        "No live orders, shared production adapter, core ranking, sizing, "
        "exits, LLM, or news behavior changed.",
        "",
        "## Conclusion",
        "",
        payload["gate4"]["rationale"],
        "",
    ])
    return "\n".join(lines)


def _card(payload: dict[str, Any]) -> str:
    return "\n".join([
        f"# {EXPERIMENT_ID} VBB sector-residual support",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['decision']}`",
        f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
        f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
        f"- Incremental target trades: {payload['target_trade_summary']['target_trade_count']}",
        "- Production impact: replay-only default-off paper; no live orders changed.",
        "",
    ])


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "failed_gates": payload["gate4"]["failed_gates"],
        "metrics": {
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments") or []
    updated = False
    for exp in experiments:
        if exp.get("experiment_id") == EXPERIMENT_ID:
            exp["status"] = "completed"
            exp["decision"] = payload["decision"]
            updated = True
            break
    if updated:
        _write_json(REGISTRY_JSON, registry)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_now()
    print(f"[{EXPERIMENT_ID}] loading VBB source rows")
    source_rows_by_window = _load_source_rows_by_window()
    for label, rows in source_rows_by_window.items():
        print(f"  {label}: {len(rows)} source trades")

    print(f"[{EXPERIMENT_ID}] building sector-residual indexes")
    indexes = _build_sector_residual_indexes()

    print(f"[{EXPERIMENT_ID}] selecting supported trades")
    before_by_window, after_by_window, incremental_by_window, diagnostics = _select_supported_trades(
        source_rows_by_window, indexes
    )
    for label in before_by_window:
        n_inc = len(incremental_by_window[label])
        print(f"  {label}: {len(before_by_window[label])} before, {n_inc} incremental (sector-residual passes)")

    print(f"[{EXPERIMENT_ID}] loading baselines")
    baselines = _load_baselines()

    print(f"[{EXPERIMENT_ID}] running window comparisons")
    window_rows = _run_windows(baselines, before_by_window, after_by_window, incremental_by_window)

    aggregate = _aggregate(window_rows)
    target_summary = _target_summary(incremental_by_window)
    baseline_context = _baseline_caveat(aggregate)
    gate4 = _gate4(aggregate, window_rows, target_summary)

    print(f"[{EXPERIMENT_ID}] aggregate EV delta: {aggregate['delta']['expected_value_score']:+.4f}")
    print(f"[{EXPERIMENT_ID}] aggregate PnL delta: ${aggregate['delta']['total_pnl']:+,.2f}")
    print(f"[{EXPERIMENT_ID}] decision: {gate4['decision']}")

    ticket = _load_ticket()
    accepted = bool(gate4["alpha_passed"] and gate4["promotable_now"])

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "decision": gate4["decision"],
        "accepted": accepted,
        "lane": "alpha_search",
        "change_type": "paper_notional_support_scout",
        "mechanism_family": TRIAL_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Already-selected VOLUME_BREADTH_BREAKOUT_PAPER candidates whose "
            "signal-date 20-day return exceeds the public-sector median by at "
            "least 3pp (with at least 5 sector members) receive a 1.05x paper "
            "notional scalar to concentrate notional in regime-leading sector breakouts."
        ),
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "before_state": "accepted VBB overlay (breadth-intensity + high-close + cost-liquidity scalars)",
            "ret20_excess_sector_min": RET20_EXCESS_SECTOR_MIN,
            "min_sector_member_returns": MIN_SECTOR_MEMBER_RETURNS,
            "support_scalar": SUPPORT_SCALAR,
            "cost_liquidity_scalar_applied": COST_LIQ_SCALAR,
        },
        "anti_js": True,
        "aggregate": aggregate,
        "baseline_context": baseline_context,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "selection_diagnostics": diagnostics,
        "gate4": gate4,
        "production_impact": {
            "replay_only": True,
            "default_off_paper_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "llm_or_news_changed": False,
        },
        "ticket": ticket,
    }

    _write_json(OUT_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))
    _write_text(CARD_MD, _card(payload))

    log_entry = {
        "experiment_id": EXPERIMENT_ID,
        "decision": gate4["decision"],
        "accepted": accepted,
        "alpha_passed": gate4["alpha_passed"],
        "aggregate_ev_before": aggregate["before"]["expected_value_score"],
        "aggregate_ev_after": aggregate["after"]["expected_value_score"],
        "aggregate_ev_delta": aggregate["delta"]["expected_value_score"],
        "aggregate_pnl_delta": aggregate["delta"]["total_pnl"],
        "target_trade_count": target_summary["target_trade_count"],
        "failed_gates": gate4["failed_gates"],
        "changed_variable": CHANGED_VARIABLE,
        "timestamp": timestamp,
    }
    _write_json(LOG_JSON, log_entry)
    _upsert_jsonl(EXPERIMENT_LOG, log_entry)

    _update_ticket(payload)
    _update_registry(payload)

    print(f"[{EXPERIMENT_ID}] wrote artifacts to {_repo_rel(OUT_JSON)}")


if __name__ == "__main__":
    main()
