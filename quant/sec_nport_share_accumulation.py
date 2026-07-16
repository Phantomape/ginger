"""Point-in-time SEC N-PORT share-accumulation shadow policy.

The helper consumes the compact, public N-PORT tables used by
``exp-20260715-009``.  It deliberately keeps the production surface default
off: callers receive an annotation and a fixed *shadow* scalar, while this
module never changes a signal, notional, order, ranking, or exit.

The important point-in-time rules live here rather than in an experiment-only
runner:

* a filing is usable only when ``filing_date < action_date``;
* the latest available amendment wins for a series/report-date;
* the latest two reports for a series must be 70--110 days apart; and
* holders are the union of the two reports, so a sold-to-zero position counts.

``split_factors`` are balance multipliers keyed by ticker/report date.  A
factor can also be inferred from the cross-sectional median of
``(currency_value / balance) / adjusted_market_price``.  Only a ratio within
5% of an integer 2--50 (or its reciprocal), with at least 20 observations, is
accepted; otherwise the neutral factor 1 is used.
"""

from __future__ import annotations

import csv
import gzip
import json
import math
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable, Mapping, Sequence


RULE_VERSION = "sec_nport_share_accumulation_v1"
ANNOTATION_KEY = "sec_nport_share_accumulation_shadow"

MIN_MATCHED_SERIES = 20
MIN_REPORT_GAP_DAYS = 70
MAX_REPORT_GAP_DAYS = 110
POSITIVE_SCALAR = 1.10
NEGATIVE_SCALAR = 0.90
NEUTRAL_SCALAR = 1.00
SPLIT_MIN_SAMPLES = 20
SPLIT_TOLERANCE = 0.05
# Public, unambiguous name used by runner/parity tests.
SPLIT_FACTOR_TOLERANCE = SPLIT_TOLERANCE


@dataclass(frozen=True, slots=True)
class NPortHolding:
    accession: str
    series_id: str
    ticker: str
    report_date: date
    filing_date: date
    balance: float
    currency_value: float | None


@dataclass(frozen=True, slots=True)
class NPortReport:
    accession: str
    series_id: str
    report_date: date
    filing_date: date


@dataclass(frozen=True, slots=True)
class _HoldingValue:
    balance: float
    currency_value: float | None
    row_count: int


@dataclass(frozen=True, slots=True)
class _ReportPair:
    series_id: str
    previous: NPortReport
    current: NPortReport


class NPortDataset:
    """Normalised compact N-PORT data with read-only public records.

    Indexes and the action-date pair cache are implementation details.  The
    source records are immutable dataclasses and calculation functions never
    mutate caller-owned mappings or lists.
    """

    def __init__(
        self,
        holdings: Iterable[NPortHolding],
        reports: Iterable[NPortReport],
        *,
        adjusted_close_by_ticker_date: Mapping[Any, Any]
        | Callable[[str, str], float | None]
        | None = None,
    ) -> None:
        self.holdings = tuple(holdings)
        self.reports = tuple(reports)

        reports_by_series: dict[str, list[NPortReport]] = defaultdict(list)
        for report in self.reports:
            reports_by_series[report.series_id].append(report)
        self._reports_by_series = {
            series_id: tuple(
                sorted(
                    rows,
                    key=lambda row: (
                        row.report_date,
                        row.filing_date,
                        row.accession,
                    ),
                )
            )
            for series_id, rows in reports_by_series.items()
        }

        aggregate: dict[tuple[str, str, str], list[float | int | None]] = {}
        for holding in self.holdings:
            key = (holding.accession, holding.series_id, holding.ticker)
            current = aggregate.setdefault(key, [0.0, 0.0, 0, 0])
            current[0] = float(current[0]) + holding.balance
            if holding.currency_value is not None:
                current[1] = float(current[1]) + holding.currency_value
                current[2] = int(current[2]) + 1
            current[3] = int(current[3]) + 1
        self._holdings_by_key = {
            key: _HoldingValue(
                balance=float(values[0]),
                currency_value=(float(values[1]) if int(values[2]) else None),
                row_count=int(values[3]),
            )
            for key, values in aggregate.items()
        }
        self._series_with_holdings = frozenset(
            holding.series_id for holding in self.holdings
        )
        self._pair_cache: dict[date, tuple[_ReportPair, ...]] = {}
        # This is dependency injection, not a warehouse read.  Historical
        # replay supplies frozen adjusted closes and daily production can pass
        # its already-loaded OHLCV surface through the same contract.
        self.adjusted_close_by_ticker_date = adjusted_close_by_ticker_date

    @property
    def holding_count(self) -> int:
        return len(self.holdings)

    @property
    def report_count(self) -> int:
        return len(self.reports)


def load_nport_rows(
    holdings_source: NPortDataset
    | str
    | Path
    | Sequence[str | Path]
    | Iterable[Mapping[str, Any]],
    reports: str
    | Path
    | Sequence[str | Path]
    | Iterable[Mapping[str, Any]]
    | None = None,
    *,
    reports_path: str | Path | None = None,
    price_lookup: Mapping[Any, Any] | Callable[[str, str], float | None] | None = None,
    adjusted_close_by_ticker_date: Mapping[Any, Any]
    | Callable[[str, str], float | None]
    | None = None,
) -> NPortDataset:
    """Load compact holdings and the all-series report table.

    Passing the compact directory is the normal path.  Every
    ``core_holdings_*.json*`` file is loaded (including newly added quarters)
    and ``series_reports.json*`` supplies report rows needed to distinguish a
    true sold-to-zero position from a missing report.
    """

    if isinstance(holdings_source, NPortDataset):
        if (
            reports is not None
            or reports_path is not None
            or price_lookup is not None
            or adjusted_close_by_ticker_date is not None
        ):
            raise ValueError("extra sources must not be supplied with an NPortDataset")
        return holdings_source
    if reports is not None and reports_path is not None:
        raise ValueError("use either reports or reports_path, not both")
    if reports is None:
        reports = reports_path
    if price_lookup is not None and adjusted_close_by_ticker_date is not None:
        raise ValueError(
            "use either price_lookup or adjusted_close_by_ticker_date, not both"
        )
    default_prices = (
        adjusted_close_by_ticker_date
        if adjusted_close_by_ticker_date is not None
        else price_lookup
    )

    if isinstance(holdings_source, (str, Path)) and Path(holdings_source).is_dir():
        directory = Path(holdings_source)
        holding_paths = sorted(directory.glob("core_holdings_*.json*"))
        if not holding_paths:
            raise FileNotFoundError(
                f"no core_holdings_*.json* files under {directory}"
            )
        if reports is None:
            report_paths = sorted(directory.glob("series_reports.json*"))
            if len(report_paths) != 1:
                raise FileNotFoundError(
                    f"expected one series_reports.json* under {directory}"
                )
            reports = report_paths[0]
        raw_holdings = _read_sources(holding_paths)
    else:
        raw_holdings = _read_sources(holdings_source)

    if reports is None:
        raise ValueError(
            "all-series reports are required so sold-to-zero holdings are observable"
        )
    raw_reports = _read_sources(reports)
    holdings = tuple(_normalise_holding(row) for row in raw_holdings)
    report_rows = tuple(_normalise_report(row) for row in raw_reports)
    return NPortDataset(
        holdings,
        report_rows,
        adjusted_close_by_ticker_date=default_prices,
    )


def compute_share_accumulation(
    dataset: NPortDataset
    | str
    | Path
    | Sequence[str | Path]
    | Iterable[Mapping[str, Any]],
    *,
    action_date: Any,
    ticker: str,
    reports: str
    | Path
    | Sequence[str | Path]
    | Iterable[Mapping[str, Any]]
    | None = None,
    split_factors: Mapping[Any, Any]
    | Callable[[str, str], float | None]
    | None = None,
    raw_prices: Mapping[Any, Any] | Callable[[str, str], float | None] | None = None,
    min_matched_series: int = MIN_MATCHED_SERIES,
) -> dict[str, Any]:
    """Calculate the PIT continuous-series aggregate-share signal.

    ``scalar`` is a policy measurement value, not an instruction to place or
    resize an order.  Production callers should use :func:`annotate_signal`
    and retain the default-off flags carried in the result.
    """

    data = (
        dataset
        if isinstance(dataset, NPortDataset)
        else load_nport_rows(dataset, reports)
    )
    if raw_prices is None:
        raw_prices = data.adjusted_close_by_ticker_date
    action = _as_date(action_date, field="action_date")
    symbol = str(ticker or "").strip().upper()
    if not symbol:
        raise ValueError("ticker is required")
    if int(min_matched_series) < 1:
        raise ValueError("min_matched_series must be positive")

    pairs = _series_pairs_for_action(data, action)
    matched: list[tuple[_ReportPair, _HoldingValue | None, _HoldingValue | None]] = []
    for pair in pairs:
        previous = data._holdings_by_key.get(
            (pair.previous.accession, pair.series_id, symbol)
        )
        current = data._holdings_by_key.get(
            (pair.current.accession, pair.series_id, symbol)
        )
        # Union holders: inclusion on either side makes the continuously
        # reporting series observable, including a later sold-to-zero row.
        if previous is not None or current is not None:
            matched.append((pair, previous, current))

    factor_cache: dict[date, tuple[float, str, int]] = {}
    relevant_dates = {
        side.report_date
        for pair, _, _ in matched
        for side in (pair.previous, pair.current)
    }
    for report_date in relevant_dates:
        factor_cache[report_date] = _factor_for_report_date(
            data,
            matched,
            ticker=symbol,
            report_date=report_date,
            split_factors=split_factors,
            raw_prices=raw_prices,
        )

    previous_raw = 0.0
    current_raw = 0.0
    previous_adjusted = 0.0
    current_adjusted = 0.0
    sold_to_zero = 0
    bought_from_zero = 0
    continuous_holders = 0
    prior_dates: list[date] = []
    current_dates: list[date] = []
    for pair, previous, current in matched:
        prior_balance = previous.balance if previous is not None else 0.0
        current_balance = current.balance if current is not None else 0.0
        prior_factor = factor_cache.get(pair.previous.report_date, (1.0, "none", 0))[0]
        current_factor = factor_cache.get(pair.current.report_date, (1.0, "none", 0))[0]
        previous_raw += prior_balance
        current_raw += current_balance
        previous_adjusted += prior_balance * prior_factor
        current_adjusted += current_balance * current_factor
        if previous is not None and current is None:
            sold_to_zero += 1
        elif previous is None and current is not None:
            bought_from_zero += 1
        else:
            continuous_holders += 1
        prior_dates.append(pair.previous.report_date)
        current_dates.append(pair.current.report_date)

    matched_count = len(matched)
    raw_change = (
        current_raw / previous_raw - 1.0 if previous_raw > 0.0 else None
    )
    adjusted_change = (
        current_adjusted / previous_adjusted - 1.0
        if previous_adjusted > 0.0
        else None
    )

    if not pairs:
        status = "missing"
        reason = "no_pit_continuous_report_pairs"
        score = None
        scalar = NEUTRAL_SCALAR
    elif matched_count < int(min_matched_series):
        status = "missing"
        reason = "insufficient_matched_series"
        score = None
        scalar = NEUTRAL_SCALAR
    elif previous_adjusted <= 0.0:
        status = "missing"
        reason = "nonpositive_prior_sum"
        score = None
        scalar = NEUTRAL_SCALAR
    else:
        score = float(adjusted_change or 0.0)
        if score > 0.0:
            status = "positive"
            scalar = POSITIVE_SCALAR
        elif score < 0.0:
            status = "negative"
            scalar = NEGATIVE_SCALAR
        else:
            status = "neutral"
            scalar = NEUTRAL_SCALAR
        reason = f"eligible_{status}"

    prior_date_strings = sorted({value.isoformat() for value in prior_dates})
    current_date_strings = sorted({value.isoformat() for value in current_dates})
    factors_used = {
        report_date.isoformat(): {
            "factor": factor,
            "source": source,
            "sample_count": sample_count,
        }
        for report_date, (factor, source, sample_count) in sorted(
            factor_cache.items()
        )
    }
    factor_sources = {details["source"] for details in factors_used.values()}
    if not factors_used:
        raw_price_coverage_status = "not_applicable_no_matched_reports"
    elif "not_supplied" in factor_sources:
        raw_price_coverage_status = "missing"
    elif "insufficient_samples" in factor_sources:
        raw_price_coverage_status = "insufficient_samples"
    elif factor_sources == {"provided"}:
        raw_price_coverage_status = "provided_split_factors"
    elif factor_sources <= {"inferred_integer_ratio", "inferred_neutral"}:
        raw_price_coverage_status = "complete"
    else:
        raw_price_coverage_status = "mixed"
    return {
        "rule_version": RULE_VERSION,
        "ticker": symbol,
        "action_date": action.isoformat(),
        "status": status,
        "bucket": status,
        "reason": reason,
        "eligible": status != "missing",
        "score": score,
        "scalar": scalar,
        "notional_scalar": scalar,
        "qoq_change": adjusted_change,
        "share_change_pct": adjusted_change,
        "split_adjusted_share_change_pct": adjusted_change,
        "aggregate_share_change_pct": adjusted_change,
        "raw_qoq_change": raw_change,
        "previous_sum": previous_adjusted,
        "prior_sum": previous_adjusted,
        "current_sum": current_adjusted,
        "previous_sum_raw": previous_raw,
        "current_sum_raw": current_raw,
        "matched_series_count": matched_count,
        "report_pair_count": len(pairs),
        "continuous_holder_series_count": continuous_holders,
        "sold_to_zero_series_count": sold_to_zero,
        "bought_from_zero_series_count": bought_from_zero,
        "previous_report_date": (
            prior_date_strings[0] if len(prior_date_strings) == 1 else None
        ),
        "prior_report_date": (
            prior_date_strings[0] if len(prior_date_strings) == 1 else None
        ),
        "current_report_date": (
            current_date_strings[0] if len(current_date_strings) == 1 else None
        ),
        "previous_report_date_range": _date_range(prior_date_strings),
        "current_report_date_range": _date_range(current_date_strings),
        "split_factors": factors_used,
        "split_min_samples": SPLIT_MIN_SAMPLES,
        "split_tolerance": SPLIT_FACTOR_TOLERANCE,
        "raw_price_coverage_status": raw_price_coverage_status,
        "raw_price_report_date_count": sum(
            details["source"]
            in {"inferred_integer_ratio", "inferred_neutral"}
            for details in factors_used.values()
        ),
        "required_report_date_count": len(factors_used),
        "split_adjustment_applied": any(
            not math.isclose(details["factor"], 1.0)
            for details in factors_used.values()
        ),
        "min_matched_series": int(min_matched_series),
        "report_gap_days_min": MIN_REPORT_GAP_DAYS,
        "report_gap_days_max": MAX_REPORT_GAP_DAYS,
        "filing_date_rule": "filing_date_strictly_before_action_date",
        "policy": {
            "min_matched_series": int(min_matched_series),
            "min_report_gap_days": MIN_REPORT_GAP_DAYS,
            "max_report_gap_days": MAX_REPORT_GAP_DAYS,
            "positive_scalar": POSITIVE_SCALAR,
            "negative_scalar": NEGATIVE_SCALAR,
            "neutral_scalar": NEUTRAL_SCALAR,
            "split_min_samples": SPLIT_MIN_SAMPLES,
            "split_factor_tolerance": SPLIT_FACTOR_TOLERANCE,
            "split_integer_min": 2,
            "split_integer_max": 50,
        },
        "shadow_only": True,
        "observer_only": True,
        "paper_enabled": True,
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }


def annotate_signal(
    signal: Mapping[str, Any],
    dataset: NPortDataset
    | str
    | Path
    | Sequence[str | Path]
    | Iterable[Mapping[str, Any]],
    *,
    action_date: Any | None = None,
    ticker: str | None = None,
    reports: Any = None,
    split_factors: Mapping[Any, Any]
    | Callable[[str, str], float | None]
    | None = None,
    raw_prices: Mapping[Any, Any] | Callable[[str, str], float | None] | None = None,
    annotation_key: str = ANNOTATION_KEY,
) -> dict[str, Any]:
    """Return a deep-copied signal carrying a default-off shadow annotation."""

    output = deepcopy(dict(signal))
    symbol = ticker or signal.get("ticker") or signal.get("symbol")
    decision_date = (
        action_date
        or signal.get("entry_date")
        or signal.get("action_date")
        or signal.get("date")
    )
    annotation = compute_share_accumulation(
        dataset,
        action_date=decision_date,
        ticker=str(symbol or ""),
        reports=reports,
        split_factors=split_factors,
        raw_prices=raw_prices,
    )
    output[annotation_key] = annotation
    return output


def build_shadow_annotation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility name for the pure calculation result."""

    return compute_share_accumulation(*args, **kwargs)


def infer_integer_split_factor(
    implied_prices_or_ratios: Iterable[float],
    raw_prices: Iterable[float] | float | None = None,
    *,
    min_samples: int = SPLIT_MIN_SAMPLES,
    tolerance: float = SPLIT_TOLERANCE,
) -> float:
    """Infer a balance multiplier from implied/raw price ratios.

    With ``raw_prices=None`` the first iterable is treated as ratios directly.
    Otherwise corresponding ``implied / raw`` ratios are built.  The result is
    exactly an integer in 2..50, its reciprocal, or 1.0.
    """

    implied = list(implied_prices_or_ratios)
    ratios: list[float] = []
    if raw_prices is None:
        ratios = [_positive_float(value) for value in implied]
    elif isinstance(raw_prices, (int, float)):
        denominator = _positive_float(raw_prices)
        if denominator is not None:
            ratios = [
                value / denominator
                for value in (_positive_float(item) for item in implied)
                if value is not None
            ]
    else:
        for implied_price, raw_price in zip(implied, raw_prices):
            numerator = _positive_float(implied_price)
            denominator = _positive_float(raw_price)
            if numerator is not None and denominator is not None:
                ratios.append(numerator / denominator)
    ratios = [value for value in ratios if value is not None and math.isfinite(value)]
    if len(ratios) < int(min_samples):
        return 1.0
    centre = median(ratios)
    candidates: list[tuple[float, float]] = []
    for integer in range(2, 51):
        value = float(integer)
        candidates.append((abs(centre - value) / value, value))
        reciprocal = 1.0 / value
        candidates.append((abs(centre - reciprocal) / reciprocal, reciprocal))
    error, candidate = min(candidates, key=lambda item: (item[0], item[1]))
    return candidate if error <= float(tolerance) else 1.0


def infer_split_factor(*args: Any, **kwargs: Any) -> float:
    """Short compatibility alias for :func:`infer_integer_split_factor`."""

    return infer_integer_split_factor(*args, **kwargs)


def _series_pairs_for_action(
    dataset: NPortDataset, action_date: date
) -> tuple[_ReportPair, ...]:
    cached = dataset._pair_cache.get(action_date)
    if cached is not None:
        return cached
    pairs: list[_ReportPair] = []
    for series_id in dataset._series_with_holdings:
        latest_by_report_date: dict[date, NPortReport] = {}
        for report in dataset._reports_by_series.get(series_id, ()):  # pragma: no branch
            if report.filing_date >= action_date:
                continue
            incumbent = latest_by_report_date.get(report.report_date)
            if incumbent is None or (
                report.filing_date,
                report.accession,
            ) > (incumbent.filing_date, incumbent.accession):
                latest_by_report_date[report.report_date] = report
        if len(latest_by_report_date) < 2:
            continue
        ordered = sorted(latest_by_report_date.values(), key=lambda row: row.report_date)
        previous, current = ordered[-2:]
        gap = (current.report_date - previous.report_date).days
        if MIN_REPORT_GAP_DAYS <= gap <= MAX_REPORT_GAP_DAYS:
            pairs.append(_ReportPair(series_id, previous, current))
    result = tuple(sorted(pairs, key=lambda row: row.series_id))
    dataset._pair_cache[action_date] = result
    return result


def _factor_for_report_date(
    dataset: NPortDataset,
    matched: Sequence[tuple[_ReportPair, _HoldingValue | None, _HoldingValue | None]],
    *,
    ticker: str,
    report_date: date,
    split_factors: Mapping[Any, Any] | Callable[[str, str], float | None] | None,
    raw_prices: Mapping[Any, Any] | Callable[[str, str], float | None] | None,
) -> tuple[float, str, int]:
    direct = _lookup_value(split_factors, ticker, report_date)
    if direct is not None:
        factor = _positive_float(direct)
        if factor is not None:
            return factor, "provided", 0
    raw_price = _positive_float(_lookup_value(raw_prices, ticker, report_date))
    if raw_price is None:
        return 1.0, "not_supplied", 0
    implied_prices: list[float] = []
    for pair, previous, current in matched:
        holding = None
        if pair.previous.report_date == report_date:
            holding = previous
        elif pair.current.report_date == report_date:
            holding = current
        if (
            holding is not None
            and holding.balance > 0.0
            and holding.currency_value is not None
            and holding.currency_value > 0.0
        ):
            implied_prices.append(holding.currency_value / holding.balance)
    factor = infer_integer_split_factor(implied_prices, raw_price)
    if len(implied_prices) < SPLIT_MIN_SAMPLES:
        source = "insufficient_samples"
    else:
        source = (
            "inferred_integer_ratio"
            if not math.isclose(factor, 1.0)
            else "inferred_neutral"
        )
    return factor, source, len(implied_prices)


def _lookup_value(
    source: Mapping[Any, Any] | Callable[[str, str], Any] | None,
    ticker: str,
    report_date: date,
) -> Any:
    if source is None:
        return None
    date_text = report_date.isoformat()
    if callable(source):
        return source(ticker, date_text)
    direct_keys = (
        (ticker, date_text),
        (ticker, report_date),
        (date_text, ticker),
        (report_date, ticker),
        f"{ticker}|{date_text}",
        f"{date_text}|{ticker}",
    )
    for key in direct_keys:
        if key in source:
            return source[key]
    ticker_values = source.get(ticker)
    if isinstance(ticker_values, Mapping):
        return ticker_values.get(date_text, ticker_values.get(report_date))
    date_values = source.get(date_text, source.get(report_date))
    if isinstance(date_values, Mapping):
        return date_values.get(ticker)
    return None


def _read_sources(source: Any) -> list[Mapping[str, Any]]:
    if isinstance(source, Mapping):
        if "rows" in source and isinstance(source["rows"], list):
            return [dict(row) for row in source["rows"]]
        return [dict(source)]
    if isinstance(source, (str, Path)):
        return _read_path(Path(source))
    values = list(source)
    if not values:
        return []
    if all(isinstance(value, Mapping) for value in values):
        return [dict(value) for value in values]
    rows: list[Mapping[str, Any]] = []
    for value in values:
        rows.extend(_read_path(Path(value)))
    return rows


def _read_path(path: Path) -> list[Mapping[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    compressed = path.suffix.lower() == ".gz"
    logical_suffix = (
        Path(path.stem).suffix.lower() if compressed else path.suffix.lower()
    )
    opener = gzip.open if compressed else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        if logical_suffix == ".json":
            payload = json.load(handle)
            if isinstance(payload, list):
                return [dict(row) for row in payload]
            if isinstance(payload, Mapping) and isinstance(payload.get("rows"), list):
                return [dict(row) for row in payload["rows"]]
            raise ValueError(f"expected a JSON row list: {path}")
        if logical_suffix in {".jsonl", ".ndjson"}:
            return [json.loads(line) for line in handle if line.strip()]
        delimiter = "\t" if logical_suffix in {".tsv", ".txt"} else ","
        return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]


def _normalise_holding(row: Mapping[str, Any]) -> NPortHolding:
    accession = _required_text(row, "accession", "accession_number", "ACCESSION_NUMBER")
    series_id = _required_text(row, "series_id", "series", "SERIES_ID")
    ticker = _required_text(row, "ticker", "TICKER").upper()
    return NPortHolding(
        accession=accession,
        series_id=series_id,
        ticker=ticker,
        report_date=_as_date(
            _field(row, "report_date", "REPORT_DATE"), field="report_date"
        ),
        filing_date=_as_date(
            _field(row, "filing_date", "FILING_DATE"), field="filing_date"
        ),
        balance=_finite_float(_field(row, "balance", "BALANCE"), field="balance"),
        currency_value=_optional_finite_float(
            _field(row, "currency_value", "CURRENCY_VALUE", "value_usd")
        ),
    )


def _normalise_report(row: Mapping[str, Any]) -> NPortReport:
    return NPortReport(
        accession=_required_text(
            row, "accession", "accession_number", "ACCESSION_NUMBER"
        ),
        series_id=_required_text(row, "series_id", "series", "SERIES_ID"),
        report_date=_as_date(
            _field(row, "report_date", "REPORT_DATE"), field="report_date"
        ),
        filing_date=_as_date(
            _field(row, "filing_date", "FILING_DATE"), field="filing_date"
        ),
    )


def _field(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def _required_text(row: Mapping[str, Any], *names: str) -> str:
    value = _field(row, *names)
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"missing required field {names[0]}")
    return text


def _as_date(value: Any, *, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    iso_text = text[:10]
    try:
        return date.fromisoformat(iso_text)
    except ValueError:
        pass
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc


def _finite_float(value: Any, *, field: str) -> float:
    try:
        output = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if not math.isfinite(output):
        raise ValueError(f"invalid {field}: {value!r}")
    return output


def _optional_finite_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    output = _finite_float(value, field="currency_value")
    return output


def _positive_float(value: Any) -> float | None:
    try:
        output = float(value)
    except (TypeError, ValueError):
        return None
    return output if math.isfinite(output) and output > 0.0 else None


def _date_range(values: Sequence[str]) -> dict[str, str] | None:
    if not values:
        return None
    return {"min": values[0], "max": values[-1]}


# Descriptive aliases used by historical runners and notebooks.
load_nport_dataset = load_nport_rows
compute_nport_share_accumulation = compute_share_accumulation
annotate_nport_share_accumulation_shadow = annotate_signal


__all__ = [
    "ANNOTATION_KEY",
    "MAX_REPORT_GAP_DAYS",
    "MIN_MATCHED_SERIES",
    "MIN_REPORT_GAP_DAYS",
    "NEGATIVE_SCALAR",
    "NEUTRAL_SCALAR",
    "NPortDataset",
    "NPortHolding",
    "NPortReport",
    "POSITIVE_SCALAR",
    "RULE_VERSION",
    "SPLIT_FACTOR_TOLERANCE",
    "annotate_nport_share_accumulation_shadow",
    "annotate_signal",
    "build_shadow_annotation",
    "compute_nport_share_accumulation",
    "compute_share_accumulation",
    "infer_integer_split_factor",
    "infer_split_factor",
    "load_nport_dataset",
    "load_nport_rows",
]
