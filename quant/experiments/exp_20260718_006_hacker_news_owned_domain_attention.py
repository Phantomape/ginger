"""exp-20260718-006: Hacker News owned-domain attention full-stack replay.

The runner freezes an outcome-blind, exact-host slice of the public HN Algolia
search index, then evaluates the preregistered shared helper on the three
canonical windows.  The formal comparison is capital conserving: 24% of the
accepted core return stream is replaced by the fully funded HN sleeve return;
paper PnL is never added on top of a fully invested core curve.

Algolia is a current search index rather than an immutable as-published archive.
The retrieved bytes are hash-bound for reproducibility and the revision/deletion
risk is a live blocker.  Append-only forward snapshots are the stronger PIT
evidence.  This runner never emits orders and never changes live configuration.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260718-006"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_fingerprint import infer_fingerprint  # noqa: E402
from hacker_news_attention_paper_sleeve import (  # noqa: E402
    HOLD_SESSIONS,
    ISSUER_DOMAIN_MAP_EFFECTIVE_FROM,
    ISSUER_OWNED_DOMAINS,
    MAX_ACTIVE_POSITIONS,
    PAPER_NOTIONAL_USD,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_hacker_news_attention_historical_trades,
    build_hacker_news_attention_snapshot,
    match_hacker_news_owned_domain,
    normalise_hacker_news_story_rows,
)
from quant.constants import ROUND_TRIP_COST_PCT  # noqa: E402
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.fill_model import (  # noqa: E402
    SLIPPAGE_BPS_ENTRY,
    SLIPPAGE_BPS_TARGET,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


WINDOWS = OrderedDict(
    (
        ("old_thin", ("2024-10-02", "2025-04-22")),
        ("mid_weak", ("2025-04-23", "2025-10-22")),
        ("late_strong", ("2025-10-23", "2026-04-21")),
    )
)
SOURCE_QUERY_START = "2024-08-26"
SOURCE_QUERY_END_EXCLUSIVE = "2026-04-22"
OHLCV_QUERY_START = "2024-08-01"
OHLCV_QUERY_END = "2026-05-15"

HN_API_URL = "https://hn.algolia.com/api/v1/search_by_date"
HN_API_HOST = "hn.algolia.com"
HTTP_TIMEOUT_SECONDS = 30
HTTP_ATTEMPTS = 4
HTTP_WORKERS = 8
HITS_PER_PAGE = 1000
USER_AGENT = "ginger-alpha/exp-20260718-006 (default-off research)"

SOURCE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "hacker_news_attention"
STORIES_PATH = SOURCE_DIR / "stories.jsonl"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"
ISSUER_MAP_PATH = SOURCE_DIR / "issuer_domain_map.json"
WAREHOUSE_PATH = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
BASELINE_SUMMARY_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
RESULT_PATH = OUT_DIR / "result.json"
BEFORE_PATH = OUT_DIR / "before.json"
AFTER_PATH = OUT_DIR / "after.json"
VERDICT_PATH = OUT_DIR / "full_stack_verdict.json"
DAILY_SNAPSHOT_PATH = OUT_DIR / "daily_default_off_snapshot.json"

CORE_WEIGHT = 0.76
SLEEVE_WEIGHT = 0.24
SLEEVE_CAPITAL_USD = PAPER_NOTIONAL_USD * MAX_ACTIVE_POSITIONS
MIN_SETTLED_PER_WINDOW = 20
MIN_TICKERS_PER_WINDOW = 10
MAX_TOP1_COUNT_SHARE = 0.30
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_TOP5_POSITIVE_SHARE = 0.60
MAX_POSITIVE_HHI = 0.35
ACCEPTED_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10_432.91,
}
EXPECTED_FINGERPRINT = {
    "data_source": "hacker_news_owned_domain_attention",
    "gate_shape": "candidate_pool_top3_10d",
}


class EvaluationContractError(RuntimeError):
    """A source, identity, market, or evaluation invariant failed closed."""


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: Any) -> None:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    _atomic_write_bytes(path, raw)


def _atomic_write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    raw = b"".join(
        json.dumps(
            dict(row),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
        for row in rows
    )
    _atomic_write_bytes(path, raw)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value + "T00:00:00+00:00")


def _http_json(params: Mapping[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    url = HN_API_URL + "?" + urllib.parse.urlencode(params)
    last_error: Exception | None = None
    for attempt in range(HTTP_ATTEMPTS):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                final_url = str(response.geturl())
                host = (urllib.parse.urlsplit(final_url).hostname or "").lower()
                if host != HN_API_HOST:
                    raise EvaluationContractError(
                        f"unexpected HN API redirect host: {final_url}"
                    )
                raw = response.read()
                if not raw:
                    raise EvaluationContractError("empty HN API response")
                payload = json.loads(raw.decode("utf-8"))
                return payload, {
                    "url": url,
                    "final_url": final_url,
                    "status": int(getattr(response, "status", 200)),
                    "bytes": len(raw),
                    "attempts": attempt + 1,
                    "response_sha256": hashlib.sha256(raw).hexdigest(),
                }
        except Exception as error:  # network errors are retried, contracts fail later
            last_error = error
            if attempt + 1 < HTTP_ATTEMPTS:
                time.sleep(0.5 * (attempt + 1))
    raise EvaluationContractError(f"HN API fetch failed: {last_error}") from last_error


def _exact_host(url: Any, domain: str) -> bool:
    try:
        host = (urllib.parse.urlsplit(str(url or "")).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return host == domain or host.endswith("." + domain)


def _fetch_domain_interval(
    domain: str,
    start: datetime,
    end: datetime,
    audits: list[dict[str, Any]],
    audit_lock: threading.Lock,
) -> list[dict[str, Any]]:
    params = {
        "query": domain,
        "tags": "story",
        "restrictSearchableAttributes": "url",
        "numericFilters": (
            f"created_at_i>={int(start.timestamp())},"
            f"created_at_i<{int(end.timestamp())}"
        ),
        "attributesToRetrieve": "objectID,created_at_i,url",
        "hitsPerPage": str(HITS_PER_PAGE),
        "page": "0",
    }
    payload, response_audit = _http_json(params)
    hits = payload.get("hits") or []
    if not isinstance(hits, list):
        raise EvaluationContractError(f"HN hits schema drift for {domain}")
    nb_hits = int(payload.get("nbHits", len(hits)))
    audit = {
        **response_audit,
        "domain": domain,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "nb_hits": nb_hits,
        "returned_hits": len(hits),
    }
    with audit_lock:
        audits.append(audit)
    if nb_hits > len(hits):
        span = end - start
        if span <= timedelta(days=1):
            raise EvaluationContractError(
                f"HN interval remains truncated at one day: {domain} {start.date()}"
            )
        midpoint = start + span / 2
        return _fetch_domain_interval(domain, start, midpoint, audits, audit_lock) + (
            _fetch_domain_interval(domain, midpoint, end, audits, audit_lock)
        )
    return [dict(hit) for hit in hits if _exact_host(hit.get("url"), domain)]


def _issuer_map_payload() -> dict[str, Any]:
    rows = [
        {
            "ticker": ticker,
            "owned_domain": domain,
            "valid_from": ISSUER_DOMAIN_MAP_EFFECTIVE_FROM,
            "valid_to": None,
            "relation_type": "issuer_owned_or_controlled_platform_domain",
            "evidence_basis": (
                "predeclared exact-domain map; ownership effective before all "
                "three evaluation windows"
            ),
        }
        for ticker, domains in sorted(ISSUER_OWNED_DOMAINS.items())
        for domain in domains
    ]
    return {
        "schema": "hacker_news_issuer_owned_domain_map_v1",
        "rule_version": SOURCE_RULE_VERSION,
        "effective_from": ISSUER_DOMAIN_MAP_EFFECTIVE_FROM,
        "ticker_count": len(ISSUER_OWNED_DOMAINS),
        "domain_count": len(rows),
        "rows": rows,
    }


def materialize_source() -> dict[str, Any]:
    if RESULT_PATH.exists():
        raise EvaluationContractError(
            "immutable evaluation already exists; refusing source refresh"
        )
    start = _parse_utc(SOURCE_QUERY_START)
    end = _parse_utc(SOURCE_QUERY_END_EXCLUSIVE)
    domains = sorted(domain for values in ISSUER_OWNED_DOMAINS.values() for domain in values)
    audits: list[dict[str, Any]] = []
    audit_lock = threading.Lock()
    raw_rows: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=HTTP_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_domain_interval, domain, start, end, audits, audit_lock): domain
            for domain in domains
        }
        for future in concurrent.futures.as_completed(futures):
            raw_rows.extend(future.result())
    canonical = normalise_hacker_news_story_rows(raw_rows)
    if len(canonical) < 1_000:
        raise EvaluationContractError(f"implausibly sparse HN archive: {len(canonical)}")
    map_payload = _issuer_map_payload()
    if map_payload["ticker_count"] != 38 or map_payload["domain_count"] != 43:
        raise EvaluationContractError("issuer map identity drift")
    _atomic_write_json(ISSUER_MAP_PATH, map_payload)
    _atomic_write_jsonl(STORIES_PATH, canonical)

    by_ticker = Counter(str(row["ticker"]) for row in canonical)
    by_window: dict[str, dict[str, Any]] = {}
    for label, (window_start, window_end) in WINDOWS.items():
        selected = [
            row
            for row in canonical
            if window_start <= str(row["created_date"]) <= window_end
        ]
        counts = Counter(str(row["ticker"]) for row in selected)
        by_window[label] = {
            "story_count": len(selected),
            "ticker_count": len(counts),
            "top_tickers": counts.most_common(10),
        }
    manifest = {
        "schema": "hacker_news_algolia_exact_host_source_manifest_v1",
        "experiment_id": EXPERIMENT_ID,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider": "HN Search API powered by Algolia",
            "api": HN_API_URL,
            "query_contract": (
                "tags=story; restrictSearchableAttributes=url; exact host or "
                "dot-subdomain post-filter; objectID dedupe"
            ),
            "historical_index_immutable": False,
            "revision_risk": (
                "Algolia is a current search index; deletions and index rebuilds may "
                "create historical survivorship. This frozen snapshot is reproducible "
                "but not an as-published archive."
            ),
        },
        "coverage": {
            "start": SOURCE_QUERY_START,
            "end_exclusive": SOURCE_QUERY_END_EXCLUSIVE,
            "story_count": len(canonical),
            "ticker_count": len(by_ticker),
            "domain_count": len(domains),
            "by_window": by_window,
        },
        "files": {
            "stories": _repo_rel(STORIES_PATH),
            "stories_sha256": _file_sha(STORIES_PATH),
            "issuer_map": _repo_rel(ISSUER_MAP_PATH),
            "issuer_map_sha256": _file_sha(ISSUER_MAP_PATH),
        },
        "queries": sorted(audits, key=lambda row: (row["domain"], row["start"])),
        "truncation_warning_count": 0,
        "canonical_story_set_sha256": _canonical_sha(canonical),
    }
    _atomic_write_json(SOURCE_MANIFEST_PATH, manifest)
    return manifest


def load_source() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    missing = [
        _repo_rel(path)
        for path in (STORIES_PATH, SOURCE_MANIFEST_PATH, ISSUER_MAP_PATH)
        if not path.exists()
    ]
    if missing:
        raise EvaluationContractError(f"source bundle missing: {missing}")
    manifest = _read_json(SOURCE_MANIFEST_PATH)
    issuer_map = _read_json(ISSUER_MAP_PATH)
    failures: list[str] = []
    if _file_sha(STORIES_PATH) != manifest.get("files", {}).get("stories_sha256"):
        failures.append("stories_file_hash_mismatch")
    if _file_sha(ISSUER_MAP_PATH) != manifest.get("files", {}).get("issuer_map_sha256"):
        failures.append("issuer_map_file_hash_mismatch")
    expected_map = _issuer_map_payload()
    if issuer_map != expected_map:
        failures.append("issuer_domain_map_policy_drift")
    rows: list[dict[str, Any]] = []
    with STORIES_PATH.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise EvaluationContractError(
                    f"stories JSONL invalid at line {line_number}"
                ) from error
    canonical = normalise_hacker_news_story_rows(rows)
    if len(canonical) != len(rows):
        failures.append("stories_not_canonical_or_duplicate")
    if _canonical_sha(canonical) != manifest.get("canonical_story_set_sha256"):
        failures.append("canonical_story_set_hash_mismatch")
    if manifest.get("truncation_warning_count") != 0:
        failures.append("source_query_truncation")
    if failures:
        raise EvaluationContractError("source contract failed: " + ", ".join(failures))
    audit = {
        "passed": True,
        "hard_failures": [],
        "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
        "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
        "stories": _repo_rel(STORIES_PATH),
        "stories_sha256": _file_sha(STORIES_PATH),
        "canonical_story_count": len(canonical),
        "canonical_story_set_sha256": _canonical_sha(canonical),
        "historical_index_revision_risk": True,
        "forward_append_only_evidence_preferred": True,
    }
    return canonical, manifest, audit


def _load_ohlcv() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    tickers = sorted(set(ISSUER_OWNED_DOMAINS) | {"SPY", "QQQ"})
    placeholders = ",".join("?" for _ in tickers)
    sql = (
        "select ticker, date, open, high, low, close, volume from ohlcv "
        f"where ticker in ({placeholders}) and date >= ? and date <= ? "
        "order by ticker, date"
    )
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(WAREHOUSE_PATH) as connection:
        for ticker, day, open_, high, low, close, volume in connection.execute(
            sql, [*tickers, OHLCV_QUERY_START, OHLCV_QUERY_END]
        ):
            rows_by_ticker[str(ticker)].append(
                {
                    "date": str(day)[:10],
                    "open": float(open_),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume or 0.0),
                }
            )
    rows_by_ticker = {ticker: rows for ticker, rows in rows_by_ticker.items() if rows}
    if "SPY" not in rows_by_ticker or "QQQ" not in rows_by_ticker:
        raise EvaluationContractError("warehouse lacks SPY/QQQ calendar rows")
    identity_rows = [
        [ticker, row["date"], row["open"], row["high"], row["low"], row["close"]]
        for ticker, rows in sorted(rows_by_ticker.items())
        for row in rows
    ]
    return rows_by_ticker, {
        "warehouse": _repo_rel(WAREHOUSE_PATH),
        "query_start": OHLCV_QUERY_START,
        "query_end": OHLCV_QUERY_END,
        "ticker_count": len(rows_by_ticker),
        "row_count": len(identity_rows),
        "canonical_rowset_sha256": _canonical_sha(identity_rows),
    }


def _baseline_window_map(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["label"]): dict(row) for row in summary.get("windows") or []}


def _baseline_returns(window: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifact = _read_json(REPO_ROOT / str(window["path"]))
    series = artifact.get("sharpe_inference", {}).get("return_series") or []
    output = [
        {"date": str(row["date"])[:10], "return": float(row["return"])}
        for row in series
    ]
    if not output:
        raise EvaluationContractError(f"baseline return series missing: {window['label']}")
    equity = 100_000.0
    for row in output:
        equity *= 1.0 + row["return"]
    expected = 100_000.0 + float(window["total_pnl"])
    if abs(equity - expected) > 0.02:
        raise EvaluationContractError(f"baseline curve drift: {window['label']}")
    return output


def _bar_indices(
    ohlcv: Mapping[str, list[dict[str, Any]]]
) -> tuple[dict[str, dict[str, dict[str, float]]], dict[str, list[str]]]:
    exact: dict[str, dict[str, dict[str, float]]] = {}
    dates: dict[str, list[str]] = {}
    for ticker, rows in ohlcv.items():
        exact[ticker] = {
            str(row["date"]): {
                "open": float(row["open"]),
                "close": float(row["close"]),
            }
            for row in rows
        }
        dates[ticker] = sorted(exact[ticker])
    return exact, dates


def _close_on_or_before(
    exact: Mapping[str, Mapping[str, Mapping[str, float]]],
    dates: Mapping[str, list[str]],
    ticker: str,
    day: str,
) -> float:
    row = exact.get(ticker, {}).get(day)
    if row is not None:
        return float(row["close"])
    prior = [value for value in dates.get(ticker, []) if value <= day]
    if not prior:
        raise EvaluationContractError(f"missing MTM close for {ticker} on {day}")
    return float(exact[ticker][prior[-1]]["close"])


def _sleeve_marks(
    trades: list[dict[str, Any]],
    core_dates: list[str],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> list[float]:
    exact, dates = _bar_indices(ohlcv)
    marks: list[float] = []
    for day in core_dates:
        cumulative = 0.0
        for trade in trades:
            if day < str(trade["entry_date"]):
                continue
            if day >= str(trade["exit_date"]):
                cumulative += float(trade["pnl"])
                continue
            close = _close_on_or_before(exact, dates, str(trade["ticker"]), day)
            gross = close / float(trade["entry_price"]) - 1.0
            cumulative += float(trade["paper_notional_usd"]) * (
                gross - ROUND_TRIP_COST_PCT / 2.0
            )
        marks.append(cumulative)
    return marks


def _curve_metrics(
    dated_returns: list[dict[str, Any]], *, trade_count: int
) -> dict[str, Any]:
    equity = 100_000.0
    peak = equity
    max_drawdown = 0.0
    samples: list[float] = []
    curve: list[dict[str, Any]] = []
    for row in dated_returns:
        value = float(row["return"])
        samples.append(value)
        equity *= 1.0 + value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
        curve.append({"date": str(row["date"]), "return": value, "equity": equity})
    sharpe = None
    if len(samples) >= 2:
        mean = sum(samples) / len(samples)
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        if variance > 0:
            sharpe = mean / math.sqrt(variance) * math.sqrt(252)
    total_pnl = equity - 100_000.0
    public_return = round(total_pnl / 100_000.0, 4)
    public_sharpe = round(sharpe, 2) if sharpe is not None else None
    return {
        "total_pnl": round(total_pnl, 2),
        "benchmarks": {"strategy_total_return_pct": public_return},
        "sharpe_daily": public_sharpe,
        "sharpe_daily_full_precision": sharpe,
        "expected_value_score": (
            round(public_return * public_sharpe, 4)
            if public_sharpe is not None
            else None
        ),
        "max_drawdown_pct": round(max_drawdown, 4),
        "total_trades": int(trade_count),
        "return_series": [
            {"date": row["date"], "return": row["return"]} for row in curve
        ],
        "return_series_sha256": _canonical_sha(
            [{"date": row["date"], "return": row["return"]} for row in curve]
        ),
    }


def _capital_neutral_window(
    baseline_window: Mapping[str, Any],
    trades: list[dict[str, Any]],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    core_returns = _baseline_returns(baseline_window)
    dates = [row["date"] for row in core_returns]
    marks = _sleeve_marks(trades, dates, ohlcv)
    sleeve_returns: list[float] = []
    previous_equity = SLEEVE_CAPITAL_USD
    for mark in marks:
        equity = SLEEVE_CAPITAL_USD + mark
        if equity <= 0:
            raise EvaluationContractError("funded HN sleeve equity became non-positive")
        sleeve_returns.append(equity / previous_equity - 1.0)
        previous_equity = equity
    combined_returns = [
        {
            "date": row["date"],
            "return": CORE_WEIGHT * float(row["return"]) + SLEEVE_WEIGHT * sleeve_return,
        }
        for row, sleeve_return in zip(core_returns, sleeve_returns)
    ]
    before = _curve_metrics(core_returns, trade_count=int(baseline_window["trade_count"]))
    after = _curve_metrics(
        combined_returns,
        trade_count=int(baseline_window["trade_count"]) + len(trades),
    )
    sleeve = {
        "initial_capital": SLEEVE_CAPITAL_USD,
        "ending_equity": round(previous_equity, 2),
        "total_pnl": round(previous_equity - SLEEVE_CAPITAL_USD, 2),
        "return_series": [
            {"date": day, "return": value}
            for day, value in zip(dates, sleeve_returns)
        ],
        "return_series_sha256": _canonical_sha(
            [{"date": day, "return": value} for day, value in zip(dates, sleeve_returns)]
        ),
        "capital_conserving": True,
        "core_weight": CORE_WEIGHT,
        "sleeve_weight": SLEEVE_WEIGHT,
    }
    return before, after, sleeve


def _aggregate_windows(windows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "before_expected_value_score_sum": round(
            sum(float(row["before"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "after_expected_value_score_sum": round(
            sum(float(row["after"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "expected_value_score_delta_sum": round(
            sum(float(row["delta"]["expected_value_score"]) for row in windows.values()), 4
        ),
        "before_total_pnl_sum": round(
            sum(float(row["before"]["total_pnl"]) for row in windows.values()), 2
        ),
        "after_total_pnl_sum": round(
            sum(float(row["after"]["total_pnl"]) for row in windows.values()), 2
        ),
        "total_pnl_delta_sum": round(
            sum(float(row["delta"]["total_pnl"]) for row in windows.values()), 2
        ),
        "windows_ev_improved": sum(
            float(row["delta"]["expected_value_score"]) > 0 for row in windows.values()
        ),
        "windows_ev_regressed": sum(
            float(row["delta"]["expected_value_score"]) < 0 for row in windows.values()
        ),
        "windows_pnl_improved": sum(
            float(row["delta"]["total_pnl"]) > 0 for row in windows.values()
        ),
        "windows_pnl_regressed": sum(
            float(row["delta"]["total_pnl"]) < 0 for row in windows.values()
        ),
        "max_drawdown_worse_max": max(
            float(row["delta"]["max_drawdown_pct"]) for row in windows.values()
        ),
    }


def _trade_summary(trades_by_window: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    count_by_ticker: Counter[str] = Counter()
    pnl_by_ticker: Counter[str] = Counter()
    for trades in trades_by_window.values():
        for trade in trades:
            ticker = str(trade["ticker"])
            count_by_ticker[ticker] += 1
            pnl_by_ticker[ticker] += float(trade["pnl"])
    positive = {ticker: pnl for ticker, pnl in pnl_by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    shares = sorted(
        (pnl / positive_total for pnl in positive.values()), reverse=True
    ) if positive_total > 0 else []
    return {
        "settled_trade_count": sum(len(rows) for rows in trades_by_window.values()),
        "by_window": {label: len(trades_by_window[label]) for label in WINDOWS},
        "ticker_count": len(count_by_ticker),
        "by_ticker_count": dict(sorted(count_by_ticker.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(pnl_by_ticker.items())
        },
        "single_ticker_positive_share": round(shares[0], 6) if shares else None,
        "top_5_positive_pnl_share": round(sum(shares[:5]), 6) if shares else None,
        "hhi_positive_pnl": round(sum(share * share for share in shares), 6) if shares else None,
    }


def _benchmark_diagnostics(
    trades: list[dict[str, Any]],
    ohlcv: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    exact, _ = _bar_indices(ohlcv)
    target_pnl = sum(float(trade["pnl"]) for trade in trades)
    result: dict[str, Any] = {
        "target_pnl": round(target_pnl, 2),
        "cash_pnl": 0.0,
        "cash_replacement_value": round(target_pnl, 2),
    }
    passed = bool(trades) and target_pnl > 0
    for benchmark in ("SPY", "QQQ"):
        benchmark_pnl = 0.0
        missing: list[str] = []
        for trade in trades:
            entry = exact.get(benchmark, {}).get(str(trade["entry_date"]))
            exit_row = exact.get(benchmark, {}).get(str(trade["exit_date"]))
            if entry is None or exit_row is None:
                missing.append(str(trade["decision_id"]))
                continue
            entry_price = float(entry["open"]) * (1.0 + SLIPPAGE_BPS_ENTRY / 10_000.0)
            exit_price = float(exit_row["close"]) * (1.0 - SLIPPAGE_BPS_TARGET / 10_000.0)
            net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
            benchmark_pnl += PAPER_NOTIONAL_USD * net_return
        value = round(benchmark_pnl, 2) if not missing else None
        replacement = round(target_pnl - benchmark_pnl, 2) if not missing else None
        result[benchmark.lower() + "_pnl"] = value
        result[benchmark.lower() + "_replacement_value"] = replacement
        result[benchmark.lower() + "_missing_decision_ids"] = missing
        passed = passed and not missing and replacement is not None and replacement > 0
    result["passed"] = bool(passed)
    return result


def _fingerprint_audit() -> dict[str, Any]:
    fingerprint = infer_fingerprint(
        "Hacker News owned-domain attention acceleration ranks the top three "
        "liquid issuers by weekly count for a next-open ten-session candidate pool.",
        "hacker_news_owned_domain_attention_acceleration",
        "hn_owned_domain_weekly_attention_top3_candidate_pool_v1",
        "exact_host_current_ge2_above_prior4w_top3_next_open_h10_v1",
    )
    failures = [
        f"fingerprint_{key}_mismatch"
        for key, expected in EXPECTED_FINGERPRINT.items()
        if fingerprint.get(key) != expected
    ]
    return {
        "passed": not failures,
        "hard_failures": failures,
        "expected": EXPECTED_FINGERPRINT,
        "actual": fingerprint,
    }


def build_evaluation() -> dict[str, Any]:
    stories, source_manifest, source_audit = load_source()
    fingerprint = _fingerprint_audit()
    if not fingerprint["passed"]:
        raise EvaluationContractError(
            "fingerprint contract failed: " + ", ".join(fingerprint["hard_failures"])
        )
    ohlcv, market_identity = _load_ohlcv()
    calendar = [row["date"] for row in ohlcv["SPY"]]
    baseline_summary = _read_json(BASELINE_SUMMARY_PATH)
    baseline_windows = _baseline_window_map(baseline_summary)
    if set(baseline_windows) != set(WINDOWS):
        raise EvaluationContractError("active Gate-1 window labels drifted")

    windows: dict[str, dict[str, Any]] = {}
    trades_by_window: dict[str, list[dict[str, Any]]] = {}
    generated_total = 0
    survived_total = 0
    for label, (start, end) in WINDOWS.items():
        replay = build_hacker_news_attention_historical_trades(
            story_rows=stories,
            ohlcv_by_ticker=ohlcv,
            start=start,
            end=end,
            as_of=end,
            trading_dates=calendar,
            archive_start=SOURCE_QUERY_START,
        )
        trades = [dict(row, window=label) for row in replay["trades"]]
        before, after, sleeve = _capital_neutral_window(
            baseline_windows[label], trades, ohlcv
        )
        count_by_ticker = Counter(str(row["ticker"]) for row in trades)
        top1_share = (
            count_by_ticker.most_common(1)[0][1] / len(trades) if trades else None
        )
        benchmarks = _benchmark_diagnostics(trades, ohlcv)
        generated_total += int(replay["signals_generated"])
        survived_total += int(replay["signals_survived"])
        trades_by_window[label] = trades
        windows[label] = {
            "start": start,
            "end": end,
            "before": before,
            "after": after,
            "delta": {
                "expected_value_score": round(
                    float(after["expected_value_score"])
                    - float(before["expected_value_score"]),
                    4,
                ),
                "total_pnl": round(
                    float(after["total_pnl"]) - float(before["total_pnl"]), 2
                ),
                "max_drawdown_pct": round(
                    float(after["max_drawdown_pct"])
                    - float(before["max_drawdown_pct"]),
                    4,
                ),
            },
            "signals_generated": replay["signals_generated"],
            "signals_survived": replay["signals_survived"],
            "survival_rate": replay["survival_rate"],
            "eligible_weekly_rows": replay.get("window_eligible_rows") or [],
            "selected_decisions": replay["window_decisions"],
            "trades": trades,
            "unsettled": replay["unsettled"],
            "reject_totals": replay["reject_totals"],
            "settled_trade_count": len(trades),
            "settled_ticker_count": len(count_by_ticker),
            "settled_top1_count_share": round(top1_share, 6) if top1_share is not None else None,
            "matched_benchmarks": benchmarks,
            "funded_sleeve": sleeve,
            "orders": [],
        }

    aggregate = _aggregate_windows(windows)
    trade_summary = _trade_summary(trades_by_window)
    all_trades = [trade for label in WINDOWS for trade in trades_by_window[label]]
    sentinel_fields = ("entry_date", "target_price", "entry_price", "exit_date", "exit_price")
    missing_sentinels = [
        str(trade.get("decision_id"))
        for trade in all_trades
        if any(trade.get(field) in (None, "") for field in sentinel_fields)
    ]
    gate2_failures: list[str] = []
    if not all_trades:
        gate2_failures.append("no_settled_shared_helper_trades")
    if missing_sentinels:
        gate2_failures.append("signal_contract_sentinel_missing")
    if any(trade.get("trade_enabled") is not False for trade in all_trades):
        gate2_failures.append("shared_helper_trade_enabled_drift")
    gate2 = {
        "passed": not gate2_failures,
        "hard_failures": gate2_failures,
        "sentinel_fields": list(sentinel_fields),
        "missing_sentinel_decision_ids": missing_sentinels,
        "orders": [],
    }
    survival_rate = survived_total / generated_total if generated_total else 0.0
    gate3 = {
        "passed": generated_total > 0 and survival_rate >= 0.05,
        "unit": "eligible positive-attention-acceleration issuer-week",
        "signals_generated": generated_total,
        "signals_survived": survived_total,
        "survival_rate": round(survival_rate, 6),
    }
    gate_metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "adjusted_trade_count": trade_summary["settled_trade_count"],
        "adjusted_windows": list(WINDOWS),
        "adjusted_window_count": len(WINDOWS),
        "max_drawdown_worse_max": aggregate["max_drawdown_worse_max"],
        "single_ticker_positive_share": trade_summary["single_ticker_positive_share"],
        "top_5_contribution_pct": trade_summary["top_5_positive_pnl_share"],
        "hhi_concentration": trade_summary["hhi_positive_pnl"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / trade_summary["settled_trade_count"]
            if trade_summary["settled_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(
        min_adjusted_trades=MIN_SETTLED_PER_WINDOW * len(WINDOWS),
        min_adjusted_windows=len(WINDOWS),
        min_ev_improved_windows=len(WINDOWS),
        max_ev_regressed_windows=0,
        max_drawdown_worse=MAX_DRAWDOWN_WORSE,
        max_single_ticker_positive_share=1.0,
        max_top_5_contribution_pct=1.0,
        max_hhi_concentration=1.0,
        require_tail_concentration_evidence=False,
        require_tail_concentration_not_worse=False,
    )
    canonical_gate = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=False
    )
    strict_gate = evaluate_gate4(
        gate_metrics, thresholds=thresholds, check_materiality=True
    )
    failures = list(canonical_gate["hard_failures"])
    failures.extend(gate2["hard_failures"])
    if not gate3["passed"]:
        failures.append("gate3_survival_below_5pct")
    for label in WINDOWS:
        row = windows[label]
        if row["settled_trade_count"] < MIN_SETTLED_PER_WINDOW:
            failures.append(f"settled_trade_count_below_20:{label}")
        if row["settled_ticker_count"] < MIN_TICKERS_PER_WINDOW:
            failures.append(f"settled_ticker_count_below_10:{label}")
        top1 = row["settled_top1_count_share"]
        if top1 is None or top1 > MAX_TOP1_COUNT_SHARE:
            failures.append(f"settled_top1_share_above_30pct:{label}")
        if row["delta"]["total_pnl"] <= 0:
            failures.append(f"window_pnl_not_improved:{label}")
        if not row["matched_benchmarks"]["passed"]:
            failures.append(f"cash_spy_qqq_replacement_failed:{label}")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        failures.append("accepted_candidate_pool_ev_comparator_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPARATOR["total_pnl_delta_sum"]:
        failures.append("accepted_candidate_pool_pnl_comparator_not_beaten")
    if (
        trade_summary["single_ticker_positive_share"] is None
        or trade_summary["single_ticker_positive_share"] > MAX_SINGLE_POSITIVE_SHARE
    ):
        failures.append("single_ticker_positive_pnl_concentration")
    if (
        trade_summary["top_5_positive_pnl_share"] is None
        or trade_summary["top_5_positive_pnl_share"] > MAX_TOP5_POSITIVE_SHARE
    ):
        failures.append("top5_positive_pnl_concentration")
    if (
        trade_summary["hhi_positive_pnl"] is None
        or trade_summary["hhi_positive_pnl"] > MAX_POSITIVE_HHI
    ):
        failures.append("positive_pnl_hhi_concentration")
    failures = list(dict.fromkeys(failures))
    gate4 = {
        "passed": not failures,
        "status": "passed" if not failures else "blocked",
        "hard_failures": failures,
        "canonical_candidate_pool_gate": canonical_gate,
        "strict_materiality_diagnostic_nonbinding": strict_gate,
        "metrics": gate_metrics,
        "accepted_candidate_comparator": ACCEPTED_COMPARATOR,
        "capital_accounting": {
            "passed": True,
            "core_weight": CORE_WEIGHT,
            "sleeve_weight": SLEEVE_WEIGHT,
            "sleeve_capital_usd": SLEEVE_CAPITAL_USD,
            "paper_pnl_overlay_on_full_core": False,
        },
        "source_contract": source_audit,
        "fingerprint_contract": fingerprint,
    }
    envelope = ExecutionEnvelope(
        base_notional=PAPER_NOTIONAL_USD,
        max_capital_pct=SLEEVE_WEIGHT,
        min_dollar_volume=0.0,
        slippage_bps=float(SLIPPAGE_BPS_ENTRY + SLIPPAGE_BPS_TARGET),
        max_displacement=0,
        max_concurrent=MAX_ACTIVE_POSITIONS,
        order_semantics="default_off_next_regular_open_then_session10_close",
        kill_switch_drawdown_pct=0.08,
        sleeve_drawdown_stop_pct=0.05,
        notes=(
            "One active position per ticker; six positions x $4,000 = $24,000. "
            "Formal Gate4 is a 24% funded sleeve replacing core capital. Algolia "
            "historical revision risk and prospective rows block live eligibility."
        ),
    )
    live = evaluate_live_readiness(
        envelope=envelope,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
        dsr_report=None,
    )
    verdict = full_stack_verdict(gate4=gate4, live_readiness=live, envelope=envelope)
    snapshot = build_hacker_news_attention_snapshot(
        story_rows=stories,
        ohlcv_by_ticker=ohlcv,
        as_of=WINDOWS["late_strong"][1],
        start=SOURCE_QUERY_START,
        trading_dates=calendar,
        archive_start=SOURCE_QUERY_START,
        persist=False,
    )
    if snapshot.get("trade_enabled") is not False or snapshot.get("orders") != []:
        raise EvaluationContractError("daily snapshot default-off contract failed")

    accepted = bool(gate4["passed"])
    result = {
        "schema": "hacker_news_owned_domain_attention_full_stack_result_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "status": "accepted_paper_pending_forward" if accepted else "rejected",
        "decision": (
            "accepted_paper_pending_forward_hacker_news_owned_domain_attention"
            if accepted
            else "rejected_hacker_news_owned_domain_attention"
        ),
        "accepted_alpha": accepted,
        "hypothesis": (
            "Weekly acceleration in HN story links to issuer-owned domains is a "
            "PIT proxy for developer adoption and product demand."
        ),
        "locked_policy": {
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "complete_utc_week": True,
            "minimum_current_story_count": 2,
            "prior_complete_weeks": 4,
            "strict_positive_acceleration": True,
            "weekly_top_n": 3,
            "entry": "first regular-session open after completed Sunday",
            "exit": "tenth session close",
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "one_active_position_per_ticker": True,
            "max_active_positions": MAX_ACTIVE_POSITIONS,
            "entry_slippage_bps": SLIPPAGE_BPS_ENTRY,
            "exit_slippage_bps": SLIPPAGE_BPS_TARGET,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "formal_core_weight": CORE_WEIGHT,
            "formal_sleeve_weight": SLEEVE_WEIGHT,
            "trade_enabled": False,
            "retunes": [],
        },
        "source": {
            "audit": source_audit,
            "manifest_coverage": source_manifest["coverage"],
            "revision_risk_disclosed": True,
        },
        "market_data": market_identity,
        "baseline": {
            "path": _repo_rel(BASELINE_SUMMARY_PATH),
            "sha256": _file_sha(BASELINE_SUMMARY_PATH),
            "experiment_id": baseline_summary.get("experiment_id"),
        },
        "windows": windows,
        "aggregate": aggregate,
        "trade_summary": trade_summary,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "gate5": live,
        "full_stack_verdict": verdict,
        "daily_snapshot_parity": {
            "passed": True,
            "rule_version": snapshot["rule_version"],
            "source_rule_version": snapshot["source_rule_version"],
            "trade_enabled": snapshot["trade_enabled"],
            "orders": snapshot["orders"],
        },
        "production_impact": {
            "shared_helper_used": True,
            "daily_default_off_snapshot_written": True,
            "daily_run_wiring_retained": False,
            "live_orders_changed": False,
            "core_ranking_changed": False,
            "core_sizing_changed": False,
            "trade_enabled": False,
            "historical_index_revision_risk_live_blocker": True,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed capital-neutral HN attention sleeve passed every binding "
                "Gate4 and comparator condition."
                if accepted
                else "The fixed capital-neutral HN attention sleeve failed one or more preregistered Gate4 conditions."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune current-count, prior-week span, acceleration threshold, "
                "top-N, domain subset, hold, costs, or capital weight on these windows."
            ),
            "new_evidence_required": (
                "At least 30 closed append-only forward HN decisions with positive "
                "cash/SPY/QQQ replacement value, or a genuinely immutable historical "
                "HN archive that removes Algolia index-revision survivorship."
            ),
        },
    }
    _atomic_write_json(DAILY_SNAPSHOT_PATH, snapshot)
    return result


def _aggregate_artifact(result: Mapping[str, Any], *, after: bool) -> dict[str, Any]:
    aggregate = result["aggregate"]
    metric_rows = [result["windows"][label]["after" if after else "before"] for label in WINDOWS]
    pnl_key = "after_total_pnl_sum" if after else "before_total_pnl_sum"
    ev_key = "after_expected_value_score_sum" if after else "before_expected_value_score_sum"
    return {
        "schema": "hacker_news_attention_gate_artifact_v1",
        "experiment_id": EXPERIMENT_ID,
        "side": "after" if after else "before",
        "expected_value_score": aggregate[ev_key],
        "total_pnl": aggregate[pnl_key],
        "sharpe_daily": None,
        "benchmarks": {
            "strategy_total_return_pct": round(aggregate[pnl_key] / 300_000.0, 6)
        },
        "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in metric_rows),
        "total_trades": sum(int(row["total_trades"]) for row in metric_rows),
        "survival_rate": min(
            float(result["windows"][label]["survival_rate"]) for label in WINDOWS
        ) if after else min(
            float(_baseline_window_map(_read_json(BASELINE_SUMMARY_PATH))[label]["survival_rate"])
            for label in WINDOWS
        ),
        "windows": {
            label: result["windows"][label]["after" if after else "before"]
            for label in WINDOWS
        },
        "full_stack_gate4": result["gate4"],
    }


def write_evaluation(result: dict[str, Any]) -> None:
    if RESULT_PATH.exists():
        raise EvaluationContractError("result commit marker exists; refusing overwrite")
    before = _aggregate_artifact(result, after=False)
    after = _aggregate_artifact(result, after=True)
    verdict = {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "accepted_alpha": result["accepted_alpha"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "gate5": result["gate5"],
        "full_stack_verdict": result["full_stack_verdict"],
    }
    result["output_bundle"] = {
        "before": _repo_rel(BEFORE_PATH),
        "after": _repo_rel(AFTER_PATH),
        "verdict": _repo_rel(VERDICT_PATH),
        "daily_snapshot": _repo_rel(DAILY_SNAPSHOT_PATH),
    }
    _atomic_write_json(BEFORE_PATH, before)
    _atomic_write_json(AFTER_PATH, after)
    _atomic_write_json(VERDICT_PATH, verdict)
    _atomic_write_json(RESULT_PATH, result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Fetch and hash-bind the outcome-blind exact-host HN source bundle.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Evaluate only from the frozen source and warehouse; never fetch.",
    )
    args = parser.parse_args()
    try:
        if args.source_only:
            manifest = materialize_source()
            print(
                json.dumps(
                    {
                        "experiment_id": EXPERIMENT_ID,
                        "mode": "source_only",
                        "story_count": manifest["coverage"]["story_count"],
                        "ticker_count": manifest["coverage"]["ticker_count"],
                        "manifest": _repo_rel(SOURCE_MANIFEST_PATH),
                        "manifest_sha256": _file_sha(SOURCE_MANIFEST_PATH),
                    },
                    indent=2,
                )
            )
            return 0
        if not args.offline:
            raise EvaluationContractError(
                "evaluation is offline-only; run --source-only once, then --offline"
            )
        result = build_evaluation()
        write_evaluation(result)
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": result["status"],
                    "gate4_passed": result["gate4"]["passed"],
                    "aggregate_ev_delta": result["aggregate"]["expected_value_score_delta_sum"],
                    "aggregate_pnl_delta": result["aggregate"]["total_pnl_delta_sum"],
                    "hard_failures": result["gate4"]["hard_failures"],
                    "result": _repo_rel(RESULT_PATH),
                },
                indent=2,
            )
        )
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": "failed_closed",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
