"""exp-20260525-017: expectation drift x residual leadership attribution.

Observed-only alpha search. This experiment tests whether candidate objects
with both positive PIT estimate revision and residual leadership have better
forward 5/10/20 trading-day outcomes than candidates with only one or neither.

It does not alter signal generation, ranking, sizing, exits, LLM/news, or
orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-017"
STEM = "expectation_residual_leadership_attribution"
MECHANISM_FAMILY = "expectation_residual_leadership"
TRIAL_FAMILY = "expectation_residual_leadership_bucket_attribution"
CHANGED_VARIABLE = "expectation_residual_leadership_bucket_attribution_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_paths import daily_artifact_glob, resolve_daily_artifact_path  # noqa: E402
from broad_market_sector_map import load_cache, lookup_sector  # noqa: E402
from residual_strength_surface import compute_residual_strength  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}_{STEM}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}_{STEM}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

FORWARD_HORIZONS = (5, 10, 20)
RESIDUAL_LEADER_STATES = {"residual_leader", "strong_residual_leader"}
MIN_BUCKET_A_5D_OUTCOMES = 8
MIN_TOTAL_USABLE_CANDIDATES = 30
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
PAPER_NOTIONAL_USD = 10_000.0
_REFERENCE_SECTOR_CACHE: dict[str, Any] | None = None

TOP_LEVEL_CANDIDATE_KEYS = {
    "signals": ("selected_signal", True),
    "pilot_signals": ("selected_pilot_signal", True),
    "heat_blocked_signals": ("heat_blocked_signal", False),
    "heat_blocked_pilot_signals": ("heat_blocked_pilot_signal", False),
}

ENTRY_PLAN_CANDIDATE_KEYS = {
    "deferred_breakout_signals": ("deferred_breakout_signal", False),
    "slot_sliced_signals": ("slot_sliced_signal", False),
}

PILOT_PLAN_CANDIDATE_KEYS = {
    "pilot_slot_sliced_signals": ("pilot_slot_sliced_signal", False),
    "tradeable_pilot_signals": ("tradeable_pilot_signal", False),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            same_experiment = row.get("experiment_id") == EXPERIMENT_ID
            same_variant = (
                row.get("trial_family") == TRIAL_FAMILY
                and row.get("changed_variable") == CHANGED_VARIABLE
            )
            if same_experiment and same_variant:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    try:
        raw_path = Path(path)
        abs_path = raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path
        return str(abs_path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        return datetime.strptime(raw, "%Y%m%d").date()
    return datetime.strptime(raw[:10], "%Y-%m-%d").date()


def _date_tag(day: str | date | datetime) -> str:
    return _coerce_date(day).strftime("%Y%m%d")


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ticker_from_item(item: dict[str, Any]) -> str:
    return str(item.get("ticker") or item.get("symbol") or "").upper()


def _strategy_from_item(item: dict[str, Any], fallback: str) -> str:
    raw = (
        item.get("strategy")
        or item.get("signal_type")
        or item.get("source")
        or item.get("queue_name")
        or fallback
    )
    if isinstance(raw, list):
        return ",".join(str(value) for value in raw if value)
    return str(raw) if raw else fallback


def _extend_candidate_rows(
    rows: list[dict[str, Any]],
    *,
    items: Any,
    as_of_date: str,
    candidate_source: str,
    record_type: str,
    selected_signal: bool,
) -> None:
    if not isinstance(items, list):
        return
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        ticker = _ticker_from_item(item)
        if not ticker:
            continue
        rows.append(
            {
                "as_of_date": as_of_date,
                "ticker": ticker,
                "candidate_source": candidate_source,
                "record_type": record_type,
                "selected_signal": selected_signal,
                "trade_enabled": item.get("trade_enabled"),
                "strategy": _strategy_from_item(item, record_type),
                "source_index": index,
                "raw_action": item.get("action") or item.get("decision") or item.get("status"),
                "raw_price": (
                    item.get("entry_price")
                    or item.get("entry_open_price")
                    or item.get("price")
                    or item.get("close")
                ),
            }
        )


def extract_candidate_rows(quant_payload: dict[str, Any], as_of_date: str) -> list[dict[str, Any]]:
    """Extract persisted candidate objects from a quant signal artifact.

    This intentionally ignores trend-signal feature rows. Feature rows are
    context, not candidate objects.
    """
    rows: list[dict[str, Any]] = []
    for key, (record_type, selected_signal) in TOP_LEVEL_CANDIDATE_KEYS.items():
        _extend_candidate_rows(
            rows,
            items=quant_payload.get(key),
            as_of_date=as_of_date,
            candidate_source=key,
            record_type=record_type,
            selected_signal=selected_signal,
        )

    entry_plan = quant_payload.get("entry_execution_plan")
    if isinstance(entry_plan, dict):
        for key, (record_type, selected_signal) in ENTRY_PLAN_CANDIDATE_KEYS.items():
            _extend_candidate_rows(
                rows,
                items=entry_plan.get(key),
                as_of_date=as_of_date,
                candidate_source=f"entry_execution_plan.{key}",
                record_type=record_type,
                selected_signal=selected_signal,
            )

    pilot_plan = quant_payload.get("pilot_entry_execution_plan")
    if isinstance(pilot_plan, dict):
        for key, (record_type, selected_signal) in PILOT_PLAN_CANDIDATE_KEYS.items():
            _extend_candidate_rows(
                rows,
                items=pilot_plan.get(key),
                as_of_date=as_of_date,
                candidate_source=f"pilot_entry_execution_plan.{key}",
                record_type=record_type,
                selected_signal=selected_signal,
            )
    return rows


def classify_expectation(row: dict[str, Any] | None) -> dict[str, Any]:
    """Return the primary positive expectation flag without fallback.

    Primary definition: usable PIT row and eps_estimate_delta_7d > 0.
    If 7d delta is missing, this records a coverage gap and stays false.
    """
    if not row:
        return {
            "expectation_positive": False,
            "expectation_join_status": "missing_ledger_row",
            "expectation_coverage_gap": "missing_ledger_row",
            "eps_estimate_delta_7d": None,
        }
    if not row.get("estimate_revision_usable"):
        return {
            "expectation_positive": False,
            "expectation_join_status": "ledger_row_not_usable",
            "expectation_coverage_gap": "ledger_row_not_usable",
            "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        }
    delta_7d = _float(row.get("eps_estimate_delta_7d"), None)
    if delta_7d is None:
        return {
            "expectation_positive": False,
            "expectation_join_status": "usable_ledger_missing_7d_delta",
            "expectation_coverage_gap": "missing_eps_estimate_delta_7d",
            "eps_estimate_delta_7d": None,
        }
    return {
        "expectation_positive": delta_7d > 0,
        "expectation_join_status": "usable_ledger_with_7d_delta",
        "expectation_coverage_gap": None,
        "eps_estimate_delta_7d": delta_7d,
    }


def classify_scout_expectation(row: dict[str, Any] | None) -> dict[str, Any]:
    """Classify expectation drift for reconstructed scout analysis.

    Unlike the primary bucket, this view may use non-PIT/reconstructed rows
    when a 7d delta exists. It is explicitly not eligible for promotion.
    """
    if not row:
        return {
            "scout_expectation_positive": False,
            "scout_expectation_join_status": "missing_ledger_row",
            "scout_expectation_coverage_gap": "missing_ledger_row",
            "scout_eps_estimate_delta_7d": None,
            "scout_source_quality": "missing",
            "scout_pit_caveat": None,
        }
    delta_7d = _float(row.get("eps_estimate_delta_7d"), None)
    source_quality = (
        "pit_usable"
        if row.get("estimate_revision_usable")
        else "non_pit_reconstructed"
    )
    if delta_7d is None:
        return {
            "scout_expectation_positive": False,
            "scout_expectation_join_status": f"{source_quality}_missing_7d_delta",
            "scout_expectation_coverage_gap": "missing_eps_estimate_delta_7d",
            "scout_eps_estimate_delta_7d": None,
            "scout_source_quality": source_quality,
            "scout_pit_caveat": row.get("pit_caveat"),
        }
    return {
        "scout_expectation_positive": delta_7d > 0,
        "scout_expectation_join_status": f"{source_quality}_with_7d_delta",
        "scout_expectation_coverage_gap": None,
        "scout_eps_estimate_delta_7d": delta_7d,
        "scout_source_quality": source_quality,
        "scout_pit_caveat": row.get("pit_caveat"),
    }


def classify_bucket(expectation_positive: bool, residual_leader: bool) -> str:
    if expectation_positive and residual_leader:
        return "A_positive_expectation_and_residual_leader"
    if expectation_positive:
        return "B_positive_expectation_only"
    if residual_leader:
        return "C_residual_leader_only"
    return "D_neither"


def _feature_dict_from_quant_payload(quant_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    global _REFERENCE_SECTOR_CACHE
    if _REFERENCE_SECTOR_CACHE is None:
        _REFERENCE_SECTOR_CACHE = load_cache()
    features = quant_payload.get("features")
    if not isinstance(features, dict):
        return {}
    out = {}
    for ticker, row in features.items():
        if not isinstance(row, dict):
            continue
        norm_ticker = str(ticker).upper()
        normalized = dict(row)
        normalized.setdefault("ticker", norm_ticker)
        if not normalized.get("sector") or normalized.get("sector") == "Unknown":
            sector_lookup = lookup_sector(norm_ticker, _REFERENCE_SECTOR_CACHE)
            if sector_lookup.get("sector"):
                normalized["sector"] = sector_lookup.get("sector")
                normalized["sector_lookup_status"] = sector_lookup.get("status")
                normalized["sector_lookup_rule_version"] = sector_lookup.get("rule_version")
        out[norm_ticker] = normalized
    return out


def residual_context_for_candidate(
    candidate: dict[str, Any],
    features_dict: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    features = features_dict.get(ticker)
    if not isinstance(features, dict):
        return {
            "residual_context_status": "missing_feature_row",
            "residual_state": None,
            "residual_strength_score": None,
            "residual_leader": False,
        }
    residual = compute_residual_strength(ticker, features, features_dict=features_dict)
    if not residual:
        return {
            "residual_context_status": "insufficient_residual_inputs",
            "residual_state": None,
            "residual_strength_score": None,
            "residual_leader": False,
        }
    return {
        "residual_context_status": "ok",
        "residual_state": residual.get("residual_state"),
        "residual_strength_score": residual.get("residual_strength_score"),
        "ret20_excess_spy": residual.get("ret20_excess_spy"),
        "ret20_excess_qqq": residual.get("ret20_excess_qqq"),
        "ret20_excess_sector": residual.get("ret20_excess_sector"),
        "sector": residual.get("sector"),
        "theme_residuals": residual.get("theme_residuals"),
        "themes": residual.get("themes"),
        "residual_leader": residual.get("residual_state") in RESIDUAL_LEADER_STATES,
    }


def load_ledger_map(data_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted((data_dir / "non_ohlcv").glob("estimate_revision_ledger_*.jsonl")):
        for row in _read_jsonl(path):
            ticker = str(row.get("ticker") or "").upper()
            as_of = row.get("as_of_date")
            if ticker and as_of:
                out[(str(as_of), ticker)] = row
    return out


def _date_from_quant_signal_path(path: Path) -> str:
    stem = path.stem
    return datetime.strptime(stem.rsplit("_", 1)[-1], "%Y%m%d").date().isoformat()


def load_candidates(data_dir: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    candidates: list[dict[str, Any]] = []
    features_by_date: dict[str, dict[str, dict[str, Any]]] = {}
    for path in daily_artifact_glob("quant_signals", data_dir):
        payload = _read_json(path)
        as_of = _date_from_quant_signal_path(path)
        features_by_date[as_of] = _feature_dict_from_quant_payload(payload)
        for row in extract_candidate_rows(payload, as_of):
            row["source_path"] = _repo_rel(path)
            candidates.append(row)
    return candidates, features_by_date


class PriceLookup:
    def __init__(self) -> None:
        self.by_ticker: dict[str, dict[date, float]] = defaultdict(dict)

    def add(self, ticker: str, day: str | date | datetime, close: Any) -> None:
        price = _float(close, None)
        if price is None:
            return
        self.by_ticker[str(ticker).upper()][_coerce_date(day)] = price

    def close_on(self, ticker: str, day: str | date | datetime) -> float | None:
        return self.by_ticker.get(str(ticker).upper(), {}).get(_coerce_date(day))

    def forward_return(
        self,
        ticker: str,
        day: str | date | datetime,
        horizon: int,
        *,
        base_price: float | None = None,
    ) -> dict[str, Any]:
        ticker = str(ticker).upper()
        as_of = _coerce_date(day)
        price_map = self.by_ticker.get(ticker) or {}
        start_price = base_price if base_price is not None else price_map.get(as_of)
        if start_price is None or start_price <= 0:
            return {
                "closed": False,
                "return": None,
                "pnl_proxy": None,
                "future_date": None,
                "gap_reason": "missing_start_price",
            }
        future_dates = [row_date for row_date in sorted(price_map) if row_date > as_of]
        if len(future_dates) < horizon:
            return {
                "closed": False,
                "return": None,
                "pnl_proxy": None,
                "future_date": None,
                "gap_reason": f"missing_{horizon}d_forward_price",
            }
        future_date = future_dates[horizon - 1]
        future_price = price_map[future_date]
        forward_return = (future_price / start_price) - 1.0
        return {
            "closed": True,
            "return": round(forward_return, 6),
            "pnl_proxy": round(forward_return * PAPER_NOTIONAL_USD, 2),
            "future_date": future_date.isoformat(),
            "future_close": round(future_price, 6),
            "start_close": round(start_price, 6),
            "gap_reason": None,
        }


def _load_ohlcv_payload(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return payload.get("ohlcv") if isinstance(payload.get("ohlcv"), dict) else payload


def build_price_lookup(data_dir: Path) -> PriceLookup:
    prices = PriceLookup()

    for path in sorted((data_dir / "ohlcv").glob("ohlcv_snapshot_*.json")):
        payload = _load_ohlcv_payload(path)
        for ticker, rows in payload.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    day = row.get("Date") or row.get("date")
                    close = row.get("Close") if "Close" in row else row.get("close")
                    if day:
                        prices.add(ticker, day, close)

    for path in daily_artifact_glob("trend_signals", data_dir):
        payload = _read_json(path)
        raw_signals = payload.get("signals")
        if not isinstance(raw_signals, dict):
            continue
        as_of = payload.get("asof_date") or payload.get("as_of_date") or _date_from_quant_signal_path(path)
        for ticker, row in raw_signals.items():
            if isinstance(row, dict):
                prices.add(ticker, as_of, row.get("close"))

    return prices


def annotate_candidates(
    *,
    candidates: list[dict[str, Any]],
    features_by_date: dict[str, dict[str, dict[str, Any]]],
    ledger_map: dict[tuple[str, str], dict[str, Any]],
    prices: PriceLookup,
) -> list[dict[str, Any]]:
    annotated = []
    for candidate in candidates:
        as_of = str(candidate.get("as_of_date"))
        ticker = str(candidate.get("ticker") or "").upper()
        features = features_by_date.get(as_of, {})
        ledger_row = ledger_map.get((as_of, ticker))
        expectation = classify_expectation(ledger_row)
        scout_expectation = classify_scout_expectation(ledger_row)
        residual = residual_context_for_candidate(candidate, features)
        base_price = _float(candidate.get("raw_price"), None)
        feature_close = _float((features.get(ticker) or {}).get("close"), None)
        if base_price is None:
            base_price = feature_close
        forward = {
            f"{horizon}d": prices.forward_return(
                ticker,
                as_of,
                horizon,
                base_price=base_price,
            )
            for horizon in FORWARD_HORIZONS
        }
        bucket = classify_bucket(
            bool(expectation["expectation_positive"]),
            bool(residual["residual_leader"]),
        )
        scout_bucket = classify_bucket(
            bool(scout_expectation["scout_expectation_positive"]),
            bool(residual["residual_leader"]),
        )
        annotated.append(
            {
                **candidate,
                **expectation,
                **scout_expectation,
                **residual,
                "bucket": bucket,
                "scout_bucket": scout_bucket,
                "ledger_joined": ledger_row is not None,
                "ledger_usable": bool(ledger_row and ledger_row.get("estimate_revision_usable")),
                "pit_caveat": ledger_row.get("pit_caveat") if ledger_row else None,
                "eps_estimate_delta_prev": ledger_row.get("eps_estimate_delta_prev") if ledger_row else None,
                "revision_direction_prev": ledger_row.get("revision_direction_prev") if ledger_row else None,
                "forward_outcomes": forward,
            }
        )
    return annotated


def _compact_row(row: dict[str, Any], horizon_key: str) -> dict[str, Any]:
    outcome = row.get("forward_outcomes", {}).get(horizon_key, {})
    return {
        "as_of_date": row.get("as_of_date"),
        "ticker": row.get("ticker"),
        "candidate_source": row.get("candidate_source"),
        "record_type": row.get("record_type"),
        "strategy": row.get("strategy"),
        "bucket": row.get("bucket"),
        "return": outcome.get("return"),
        "pnl_proxy": outcome.get("pnl_proxy"),
        "future_date": outcome.get("future_date"),
        "expectation_join_status": row.get("expectation_join_status"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "residual_state": row.get("residual_state"),
        "residual_strength_score": row.get("residual_strength_score"),
    }


def summarize_rows(rows: list[dict[str, Any]], horizon_key: str) -> dict[str, Any]:
    closed = [
        row
        for row in rows
        if (row.get("forward_outcomes", {}).get(horizon_key) or {}).get("closed")
    ]
    returns = [
        _float((row.get("forward_outcomes", {}).get(horizon_key) or {}).get("return"), 0.0)
        for row in closed
    ]
    pnl_values = [
        _float((row.get("forward_outcomes", {}).get(horizon_key) or {}).get("pnl_proxy"), 0.0)
        for row in closed
    ]
    wins = sum(1 for value in returns if value and value > 0)
    positive_rows = [
        (row, _float((row.get("forward_outcomes", {}).get(horizon_key) or {}).get("pnl_proxy"), 0.0))
        for row in closed
        if _float((row.get("forward_outcomes", {}).get(horizon_key) or {}).get("pnl_proxy"), 0.0) > 0
    ]
    positive_total = sum(value for _, value in positive_rows)
    top5_positive = sum(value for _, value in sorted(positive_rows, key=lambda item: item[1], reverse=True)[:5])
    by_ticker_positive: dict[str, float] = defaultdict(float)
    for row, value in positive_rows:
        by_ticker_positive[str(row.get("ticker") or "UNKNOWN")] += value
    worst_row = None
    if closed:
        worst_row = min(
            closed,
            key=lambda row: _float(
                (row.get("forward_outcomes", {}).get(horizon_key) or {}).get("return"),
                0.0,
            ),
        )
    sorted_returns = sorted(value for value in returns if value is not None)
    tail_count = max(1, math.ceil(len(sorted_returns) * 0.20)) if sorted_returns else 0
    tail_returns = sorted_returns[:tail_count] if tail_count else []
    return {
        "candidate_count": len(rows),
        "closed_outcomes": len(closed),
        "win_rate": round(wins / len(closed), 4) if closed else None,
        "avg_return": round(sum(returns) / len(returns), 6) if returns else None,
        "avg_r": None,
        "total_pnl_proxy": round(sum(pnl_values), 2) if pnl_values else 0.0,
        "avg_pnl_proxy": round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
        "tail_loss": round(sum(value for value in tail_returns if value < 0), 6) if tail_returns else 0.0,
        "worst_return": round(min(returns), 6) if returns else None,
        "worst_row": _compact_row(worst_row, horizon_key) if worst_row else None,
        "top5_positive_contribution_share": (
            round(top5_positive / positive_total, 6) if positive_total > 0 else None
        ),
        "max_single_ticker_positive_share": (
            round(max(by_ticker_positive.values()) / positive_total, 6)
            if positive_total > 0 and by_ticker_positive
            else None
        ),
        "positive_pnl_by_ticker": {
            ticker: round(value, 2)
            for ticker, value in sorted(by_ticker_positive.items())
        },
    }


def build_bucket_summary(annotated: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in annotated:
        by_bucket[row["bucket"]].append(row)
    summary: dict[str, Any] = {}
    for bucket in (
        "A_positive_expectation_and_residual_leader",
        "B_positive_expectation_only",
        "C_residual_leader_only",
        "D_neither",
    ):
        rows = by_bucket.get(bucket, [])
        summary[bucket] = {
            "candidate_count": len(rows),
            "candidate_source_breakdown": dict(Counter(row["candidate_source"] for row in rows)),
            "record_type_breakdown": dict(Counter(row["record_type"] for row in rows)),
            "ticker_count": len({row["ticker"] for row in rows}),
            "horizons": {
                f"{horizon}d": summarize_rows(rows, f"{horizon}d")
                for horizon in FORWARD_HORIZONS
            },
        }
    return summary


def build_coverage(annotated: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(annotated)
    ledger_joined = sum(1 for row in annotated if row.get("ledger_joined"))
    ledger_usable = sum(1 for row in annotated if row.get("ledger_usable"))
    with_7d = sum(1 for row in annotated if row.get("eps_estimate_delta_7d") is not None)
    residual_ok = sum(1 for row in annotated if row.get("residual_context_status") == "ok")
    closed_by_horizon = {
        f"{horizon}d": sum(
            1
            for row in annotated
            if (row.get("forward_outcomes", {}).get(f"{horizon}d") or {}).get("closed")
        )
        for horizon in FORWARD_HORIZONS
    }
    return {
        "candidate_objects_total": total,
        "ledger_joined_candidates": ledger_joined,
        "ledger_usable_candidates": ledger_usable,
        "candidates_with_eps_estimate_delta_7d": with_7d,
        "positive_expectation_candidates": sum(
            1 for row in annotated if row.get("expectation_positive")
        ),
        "residual_context_ok_candidates": residual_ok,
        "residual_leader_candidates": sum(1 for row in annotated if row.get("residual_leader")),
        "candidate_source_breakdown": dict(Counter(row["candidate_source"] for row in annotated)),
        "record_type_breakdown": dict(Counter(row["record_type"] for row in annotated)),
        "expectation_join_status_counts": dict(
            Counter(row["expectation_join_status"] for row in annotated)
        ),
        "residual_context_status_counts": dict(
            Counter(row["residual_context_status"] for row in annotated)
        ),
        "closed_forward_outcomes": closed_by_horizon,
    }


def _scout_rows(annotated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in annotated:
        scout_row = dict(row)
        scout_row["bucket"] = row.get("scout_bucket")
        scout_row["expectation_positive"] = row.get("scout_expectation_positive")
        scout_row["expectation_join_status"] = row.get("scout_expectation_join_status")
        scout_row["expectation_coverage_gap"] = row.get("scout_expectation_coverage_gap")
        scout_row["eps_estimate_delta_7d"] = row.get("scout_eps_estimate_delta_7d")
        rows.append(scout_row)
    return rows


def build_reconstructed_scout(annotated: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _scout_rows(annotated)
    bucket_summary = build_bucket_summary(rows)
    coverage = build_coverage(rows)
    gate_like_check = evaluate_gate(bucket_summary, coverage)
    return {
        "scope": "non_pit_reconstructed_scout_only",
        "can_promote": False,
        "not_gate4_evidence": True,
        "data_policy": (
            "Uses eps_estimate_delta_7d from both PIT-usable and non-PIT/"
            "reconstructed estimate_revision_ledger rows. This can guide "
            "research direction but cannot pass the primary gate."
        ),
        "source_quality_counts": dict(
            Counter(row.get("scout_source_quality") for row in annotated)
        ),
        "pit_caveat_counts": dict(
            Counter(
                row.get("scout_pit_caveat") or "none"
                for row in annotated
                if row.get("scout_source_quality") == "non_pit_reconstructed"
            )
        ),
        "positive_expectation_candidates": coverage["positive_expectation_candidates"],
        "bucket_a_closed_5d_outcomes": gate_like_check.get("bucket_a_closed_5d_outcomes"),
        "total_usable_candidates": gate_like_check.get("total_usable_candidates"),
        "gate_like_check": {
            **gate_like_check,
            "decision_scope": "scout_only_not_promotable",
        },
        "coverage": coverage,
        "bucket_summary": bucket_summary,
    }


def _avg_return(bucket_summary: dict[str, Any], bucket: str, horizon: str) -> float | None:
    return bucket_summary[bucket]["horizons"][horizon]["avg_return"]


def evaluate_gate(bucket_summary: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    bucket_a_5d = bucket_summary["A_positive_expectation_and_residual_leader"]["horizons"]["5d"]
    total_usable = coverage["closed_forward_outcomes"]["5d"]
    data_gap_reasons = []
    if bucket_a_5d["closed_outcomes"] < MIN_BUCKET_A_5D_OUTCOMES:
        data_gap_reasons.append("bucket_a_closed_5d_outcomes")
    if total_usable < MIN_TOTAL_USABLE_CANDIDATES:
        data_gap_reasons.append("total_usable_candidates")
    if data_gap_reasons:
        return {
            "passed": False,
            "decision": "observed_only_data_gap",
            "reason": "insufficient_bucket_or_total_sample",
            "data_gap_reasons": data_gap_reasons,
            "bucket_a_closed_5d_outcomes": bucket_a_5d["closed_outcomes"],
            "minimum_bucket_a_closed_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
            "total_usable_candidates": total_usable,
            "minimum_total_usable_candidates": MIN_TOTAL_USABLE_CANDIDATES,
        }

    comparisons = []
    a_beats_all = True
    for horizon in ("5d", "10d"):
        a_avg = _avg_return(
            bucket_summary,
            "A_positive_expectation_and_residual_leader",
            horizon,
        )
        for bucket in (
            "B_positive_expectation_only",
            "C_residual_leader_only",
            "D_neither",
        ):
            other_avg = _avg_return(bucket_summary, bucket, horizon)
            passed = a_avg is not None and other_avg is not None and a_avg > other_avg
            comparisons.append(
                {
                    "horizon": horizon,
                    "bucket_a_avg_return": a_avg,
                    "comparison_bucket": bucket,
                    "comparison_avg_return": other_avg,
                    "passed": passed,
                }
            )
            a_beats_all = a_beats_all and passed

    concentration = {
        "top5_positive_contribution_share": bucket_a_5d[
            "top5_positive_contribution_share"
        ],
        "max_single_ticker_positive_share": bucket_a_5d[
            "max_single_ticker_positive_share"
        ],
        "top5_positive_contribution_guardrail": MAX_TOP5_POSITIVE_SHARE,
        "max_single_ticker_positive_guardrail": MAX_SINGLE_TICKER_POSITIVE_SHARE,
    }
    concentration["passed"] = (
        concentration["top5_positive_contribution_share"] is not None
        and concentration["max_single_ticker_positive_share"] is not None
        and concentration["top5_positive_contribution_share"] <= MAX_TOP5_POSITIVE_SHARE
        and concentration["max_single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    passed = bool(a_beats_all and concentration["passed"])
    return {
        "passed": passed,
        "decision": (
            "observed_only_promising_expectation_residual_leadership"
            if passed
            else "rejected_expectation_residual_leadership_attribution"
        ),
        "reason": "bucket_a_outperformance_and_concentration"
        if passed
        else "bucket_a_failed_outperformance_or_concentration",
        "comparisons": comparisons,
        "concentration": concentration,
        "bucket_a_closed_5d_outcomes": bucket_a_5d["closed_outcomes"],
        "total_usable_candidates": total_usable,
    }


def _compact_annotated_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for row in rows:
        compact.append(
            {
                "as_of_date": row.get("as_of_date"),
                "ticker": row.get("ticker"),
                "candidate_source": row.get("candidate_source"),
                "record_type": row.get("record_type"),
                "selected_signal": row.get("selected_signal"),
                "strategy": row.get("strategy"),
                "bucket": row.get("bucket"),
                "expectation_positive": row.get("expectation_positive"),
                "expectation_join_status": row.get("expectation_join_status"),
                "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
                "pit_caveat": row.get("pit_caveat"),
                "scout_bucket": row.get("scout_bucket"),
                "scout_expectation_positive": row.get("scout_expectation_positive"),
                "scout_expectation_join_status": row.get("scout_expectation_join_status"),
                "scout_eps_estimate_delta_7d": row.get("scout_eps_estimate_delta_7d"),
                "scout_source_quality": row.get("scout_source_quality"),
                "scout_pit_caveat": row.get("scout_pit_caveat"),
                "residual_leader": row.get("residual_leader"),
                "residual_state": row.get("residual_state"),
                "residual_strength_score": row.get("residual_strength_score"),
                "forward_outcomes": row.get("forward_outcomes"),
            }
        )
    return compact


def _open_position_field_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"path": _repo_rel(path), "exists": False, "missing_required_fields": ["entry_date", "target_price"]}
    payload = _read_json(path)
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if not isinstance(positions, list):
        positions = []
    missing = []
    for idx, row in enumerate(positions):
        if not isinstance(row, dict):
            continue
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"index": idx, "ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(path),
        "exists": True,
        "checked_positions": len(positions),
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Expectation Residual Leadership Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Observed-only alpha search. No entries, exits, ranking, sizing, LLM/news, or orders changed.",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(payload["coverage"], indent=2, sort_keys=True),
        "```",
        "",
        "## Bucket Summary",
        "",
        "| Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket, row in payload["bucket_summary"].items():
        h5 = row["horizons"]["5d"]
        h10 = row["horizons"]["10d"]
        lines.append(
            "| {bucket} | {candidates} | {h5_count} | {h5_avg} | {h10_count} | {h10_avg} |".format(
                bucket=bucket,
                candidates=row["candidate_count"],
                h5_count=h5["closed_outcomes"],
                h5_avg="" if h5["avg_return"] is None else f"{h5['avg_return']:.4%}",
                h10_count=h10["closed_outcomes"],
                h10_avg="" if h10["avg_return"] is None else f"{h10['avg_return']:.4%}",
            )
        )
    scout = payload.get("reconstructed_scout")
    if scout:
        lines.extend(
            [
                "",
                "## Reconstructed Scout",
                "",
                "Non-PIT reconstructed rows are shown only for research triage. They cannot pass the primary gate or promote live logic.",
                "",
                "```json",
                json.dumps(
                    {
                        "scope": scout["scope"],
                        "can_promote": scout["can_promote"],
                        "not_gate4_evidence": scout["not_gate4_evidence"],
                        "source_quality_counts": scout["source_quality_counts"],
                        "pit_caveat_counts": scout["pit_caveat_counts"],
                        "positive_expectation_candidates": scout["positive_expectation_candidates"],
                        "bucket_a_closed_5d_outcomes": scout["bucket_a_closed_5d_outcomes"],
                        "total_usable_candidates": scout["total_usable_candidates"],
                        "decision": scout["gate_like_check"]["decision"],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                "```",
                "",
                "| Scout Bucket | Candidates | 5d Closed | 5d Avg Return | 10d Closed | 10d Avg Return |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for bucket, row in scout["bucket_summary"].items():
            h5 = row["horizons"]["5d"]
            h10 = row["horizons"]["10d"]
            lines.append(
                "| {bucket} | {candidates} | {h5_count} | {h5_avg} | {h10_count} | {h10_avg} |".format(
                    bucket=bucket,
                    candidates=row["candidate_count"],
                    h5_count=h5["closed_outcomes"],
                    h5_avg="" if h5["avg_return"] is None else f"{h5['avg_return']:.4%}",
                    h10_count=h10["closed_outcomes"],
                    h10_avg="" if h10["avg_return"] is None else f"{h10['avg_return']:.4%}",
                )
            )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload(data_dir: Path | None = None) -> dict[str, Any]:
    data_dir = data_dir or (REPO_ROOT / "data")
    timestamp = _utc_now()
    candidates, features_by_date = load_candidates(data_dir)
    ledger_map = load_ledger_map(data_dir)
    prices = build_price_lookup(data_dir)
    annotated = annotate_candidates(
        candidates=candidates,
        features_by_date=features_by_date,
        ledger_map=ledger_map,
        prices=prices,
    )
    bucket_summary = build_bucket_summary(annotated)
    coverage = build_coverage(annotated)
    gate = evaluate_gate(bucket_summary, coverage)
    reconstructed_scout = build_reconstructed_scout(annotated)
    field_check = _open_position_field_check()
    decision = gate["decision"]
    status = "observed_only_data_gap" if decision == "observed_only_data_gap" else (
        "observed_only" if gate["passed"] else "rejected"
    )
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(EXPERIMENT_LOG_JSONL),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Candidates with both positive PIT estimate revision and residual "
            "leadership should produce better 5/10/20 trading-day forward "
            "outcomes than candidates with only one or neither signal."
        ),
        "change_summary": (
            "Read-only bucket attribution for expectation drift x residual "
            "leadership over persisted daily candidate objects."
        ),
        "change_type": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "bucket_attribution_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260507-092",
            "exp-20260508-004",
            "exp-20260513-103",
            "exp-20260513-104",
            "exp-20260524-012",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "pit_estimate_revision_x_residual_leadership_bucket_attribution",
        "component": "quant/experiments/exp_20260525_017_expectation_residual_leadership_attribution.py",
        "parameters": {
            "candidate_sources": {
                "top_level": sorted(TOP_LEVEL_CANDIDATE_KEYS),
                "entry_execution_plan": sorted(ENTRY_PLAN_CANDIDATE_KEYS),
                "pilot_entry_execution_plan": sorted(PILOT_PLAN_CANDIDATE_KEYS),
            },
            "positive_expectation_definition": "estimate_revision_usable && eps_estimate_delta_7d > 0",
            "no_expectation_fallback": True,
            "reconstructed_scout_policy": (
                "Non-PIT/reconstructed estimate_revision_ledger rows may be "
                "reported only in reconstructed_scout. They cannot satisfy "
                "the primary gate or promote live strategy behavior."
            ),
            "residual_leader_states": sorted(RESIDUAL_LEADER_STATES),
            "forward_horizons": list(FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "gate_thresholds": {
                "min_bucket_a_5d_outcomes": MIN_BUCKET_A_5D_OUTCOMES,
                "min_total_usable_candidates": MIN_TOTAL_USABLE_CANDIDATES,
                "max_top5_positive_share": MAX_TOP5_POSITIVE_SHARE,
                "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            },
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            "candidate_artifacts": "data/daily/signals/quant/quant_signals_*.json",
            "estimate_revision_ledgers": "data/non_ohlcv/estimate_revision_ledger_*.jsonl",
            "ohlcv_sources": [
                "data/ohlcv/ohlcv_snapshot_*.json",
                "data/daily/signals/trend/trend_signals_*.json",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/capital allocation research: positive expectation "
                "revision plus residual leadership may identify higher "
                "information-density candidates."
            ),
            "2_history_check": (
                "No combined bucket test found. exp-20260524-012 showed "
                "ranking expectation_revision and post_earnings_drift were "
                "constant in canonical entry-day attribution; estimate revision "
                "ledger provides the PIT field source."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only gate: Bucket A has >=8 closed 5d outcomes, "
                "total usable candidates >=30, Bucket A beats B/C/D on 5d and "
                "10d avg return, and concentration is inside 60% top-5 / 50% "
                "single-ticker guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260525_017_expectation_residual_leadership_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
            "baseline_artifact": "data/experiments/exp-20260517-009/",
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "note": "This experiment is read-only attribution; no before/after core metrics are changed.",
        },
        "gate2": {
            "passed": bool(field_check.get("passed", False)),
            "field_check": field_check,
            "rule_dependencies": [
                "daily quant candidate objects",
                "estimate_revision_ledger rows by as_of_date/ticker",
                "quant features for residual strength",
                "local OHLCV/trend close rows for forward returns",
            ],
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": False,
            "note": "Passing this observed-only gate can only unlock a later PEAD paper sleeve or ranking-component experiment.",
        },
        "coverage": coverage,
        "bucket_summary": bucket_summary,
        "gate": gate,
        "reconstructed_scout": reconstructed_scout,
        "annotated_candidates": _compact_annotated_rows(annotated),
        "before_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "strategy_behavior_changed": False,
            "candidate_objects_total": coverage["candidate_objects_total"],
            "bucket_a_closed_5d_outcomes": gate.get("bucket_a_closed_5d_outcomes"),
            "total_usable_candidates": gate.get("total_usable_candidates"),
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "observed_only_attribution": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "interpretation": (
            "The first run should be read as attribution coverage, not as alpha "
            "acceptance or rejection, unless the observed-only gate has enough "
            "Bucket A and total closed outcomes."
        ),
        "rejection_reason": None
        if gate["passed"]
        else (
            "insufficient expectation-residual candidate/outcome coverage"
            if decision == "observed_only_data_gap"
            else "bucket A failed outperformance or concentration gate"
        ),
        "next_evidence_needed": (
            "Continue daily estimate-revision and candidate-object accumulation; "
            "rerun this exact script once Bucket A has >=8 closed 5d outcomes "
            "and total usable candidates >=30."
        ),
        "related_files": related_files,
        "anti_js": "No JavaScript was used.",
    }


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    keep = {
        key: payload[key]
        for key in (
            "experiment_id",
            "timestamp",
            "status",
            "hypothesis",
            "change_summary",
            "change_type",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "changed_variable",
            "prior_trial_count",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "component",
            "parameters",
            "date_range",
            "gate_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "coverage",
            "bucket_summary",
            "gate",
            "reconstructed_scout",
            "before_metrics",
            "after_metrics",
            "delta_metrics",
            "expected_value_score_delta",
            "llm_metrics",
            "production_impact",
            "decision",
            "rejection_reason",
            "next_evidence_needed",
            "related_files",
            "anti_js",
        )
    }
    return keep


def persist(payload: dict[str, Any], *, update_experiment_log: bool = True) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    _write_json(
        DOC_TICKET,
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "owner": "codex",
            "status": payload["status"],
            "decision": payload["decision"],
            "single_causal_variable": CHANGED_VARIABLE,
            "artifact_file": _repo_rel(OUT_JSON),
            "result_file": _repo_rel(DOC_LOG),
            "updated_at": payload["timestamp"],
        },
    )
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    if update_experiment_log:
        _upsert_jsonl(EXPERIMENT_LOG_JSONL, _experiment_log_entry(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "status": payload["status"],
                    "coverage": payload["coverage"],
                    "gate": payload["gate"],
                    "output": _repo_rel(OUT_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
