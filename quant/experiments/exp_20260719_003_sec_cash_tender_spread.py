"""exp-20260719-003: SEC cash-tender spread-over-carry evaluator.

The runner owns source collection and measurement only.  The deterministic
offer policy and lifecycle parser live in ``sec_cash_tender_lifecycle``; the
funded cash/MTM state machine lives in
``sec_cash_tender_spread_paper_sleeve``.  This file never registers or closes
its own experiment and never enables an order.

Usage::

    python -B quant/experiments/exp_20260719_003_sec_cash_tender_spread.py collect-sec
    python -B quant/experiments/exp_20260719_003_sec_cash_tender_spread.py collect-prices
    python -B quant/experiments/exp_20260719_003_sec_cash_tender_spread.py collect-price-supplement
    python -B quant/experiments/exp_20260719_003_sec_cash_tender_spread.py evaluate
    python -B quant/experiments/exp_20260719_003_sec_cash_tender_spread.py all
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import requests


EXPERIMENT_ID = "exp-20260719-003"
REPO_ROOT = Path(__file__).resolve().parents[2]
for import_path in (REPO_ROOT, REPO_ROOT / "quant"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import sec_cash_tender_lifecycle as lifecycle  # noqa: E402
import sec_cash_tender_spread_paper_sleeve as sleeve  # noqa: E402
import sec_tender_price_history as tender_prices  # noqa: E402
from data_paths import atomic_write_json  # noqa: E402
from portfolio_contribution_batch import core_calendar_and_returns  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
CONTRACTS_PATH = OUT_DIR / "sec_cash_tender_contracts.json"
PRICES_PATH = OUT_DIR / "ortex_price_cache.json"
PRICE_SUPPLEMENT_PATH = OUT_DIR / "ortex_price_cache_no_data_supplement.json"
BEFORE_PATH = OUT_DIR / "before_measurement.json"
AFTER_PATH = OUT_DIR / "after_measurement.json"
SNAPSHOT_PATH = OUT_DIR / "daily_default_off_snapshot.json"
RESULT_PATH = OUT_DIR / "exp_20260719_003_sec_cash_tender_spread.json"

BASELINE_PATH = REPO_ROOT / "data" / "experiments" / "exp-20260715-010" / "after_measurement.json"
BASELINE_SHA256 = "4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731"
BASELINE_EV = 6.2057
BASELINE_PNL_USD = 130_992.36
BASELINE_TRADES = 49
BASELINE_WORST_DRAWDOWN = 0.0889
BASELINE_MIN_SURVIVAL = 0.8116
BASELINE_RETURN_SUM = 1.3099

WINDOWS: dict[str, dict[str, str]] = {
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "replay": "data/experiments/exp-20260715-010/replay_default_old_thin.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "replay": "data/experiments/exp-20260715-010/replay_default_mid_weak.json",
    },
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "replay": "data/experiments/exp-20260715-010/replay_default_late_strong.json",
    },
}

EXPECTED_INITIAL_EPISODES = 81
SEC_USER_AGENT = "ginger-research/1.0 contact: research@example.com"
SEC_MIN_INTERVAL_SECONDS = 0.11
ORTEX_MIN_CREDITS_LEFT = 250.0
ORTEX_PER_EPISODE_CREDIT_BUDGET = 82.0
PRICE_PRE_ANNOUNCEMENT_CALENDAR_DAYS = 70
PRICE_POST_OUTCOME_CALENDAR_DAYS = 10
CORE_WEIGHT = 0.90
SLEEVE_WEIGHT = 0.10

MIN_SURVIVAL_RATE = 0.05
MIN_TOTAL_TRADES = 15
MIN_TRADES_PER_WINDOW = 4
MIN_POSITIVE_WINDOWS = 2
MAX_STANDALONE_DRAWDOWN = 0.08
MAX_SINGLE_DEAL_ABSOLUTE_PNL_SHARE = 0.25
MAX_PORTFOLIO_DRAWDOWN_DRIFT = 0.005


class EvaluationContractError(RuntimeError):
    """A preregistered source, replay, or accounting invariant failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=lambda item: item.isoformat() if isinstance(item, (date, datetime)) else str(item),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise EvaluationContractError(f"expected JSON object: {path}")
    return payload


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _as_bytes(value: Any) -> bytes | None:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, Mapping):
        for key in ("content", "body", "data", "text"):
            if key in value:
                return _as_bytes(value[key])
    if hasattr(value, "content"):
        return _as_bytes(value.content)
    return None


class SecArchiveFetcher:
    """Small SEC-compliant fetcher with a source audit and no raw persistence."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        min_interval_seconds: float = SEC_MIN_INTERVAL_SECONDS,
        timeout_seconds: float = 90.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.min_interval_seconds = float(min_interval_seconds)
        self.timeout_seconds = float(timeout_seconds)
        self.sleep_fn = sleep_fn
        self._last_request_at = 0.0
        self.records: list[dict[str, Any]] = []

    def __call__(self, url: str) -> bytes:
        if not str(url).startswith(("https://www.sec.gov/", "https://data.sec.gov/")):
            raise EvaluationContractError(f"unexpected SEC origin: {url}")
        delay = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
        if delay > 0:
            self.sleep_fn(delay)
        response = self.session.get(
            url,
            headers={
                "User-Agent": SEC_USER_AGENT,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
            },
            timeout=self.timeout_seconds,
        )
        self._last_request_at = time.monotonic()
        if response.status_code != 200:
            self.records.append({"url": url, "status": response.status_code, "ok": False})
            raise EvaluationContractError(f"SEC request failed with HTTP {response.status_code}: {url}")
        raw = bytes(response.content)
        self.records.append(
            {
                "url": url,
                "status": response.status_code,
                "ok": True,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        return raw


class RecordingFetcher:
    """Record immutable identity for an injected fixture/live fetcher."""

    def __init__(self, fetcher: Callable[[str], Any]) -> None:
        self.fetcher = fetcher
        self.records: list[dict[str, Any]] = []

    def __call__(self, url: str) -> Any:
        try:
            result = self.fetcher(url)
        except Exception as exc:
            self.records.append(
                {"url": url, "ok": False, "error_type": type(exc).__name__}
            )
            raise
        raw = _as_bytes(result)
        self.records.append(
            {
                "url": url,
                "ok": True,
                "bytes": len(raw) if raw is not None else None,
                "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
            }
        )
        return result


def collect_sec_contracts(
    *,
    fetcher: Callable[[str], Any] | None = None,
    enforce_expected_count: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    """Freeze the complete initial SC TO-T population and its amendments."""

    base_fetcher: Callable[[str], Any] = fetcher or SecArchiveFetcher()
    recorder = RecordingFetcher(base_fetcher)
    episodes = lifecycle.load_initial_sc_to_t_episodes(
        fetcher=recorder,
        windows=[(row["start"], row["end"]) for row in WINDOWS.values()],
        include_amendments=True,
        strict=False,
    )
    master_urls = lifecycle.canonical_master_index_urls(
        [(row["start"], row["end"]) for row in WINDOWS.values()]
    )
    successful_urls = {row["url"] for row in recorder.records if row.get("ok")}
    missing_master_urls = [url for url in master_urls if url not in successful_urls]
    if missing_master_urls:
        raise EvaluationContractError(
            f"canonical SEC master index coverage failed: {missing_master_urls}"
        )
    if enforce_expected_count and len(episodes) != EXPECTED_INITIAL_EPISODES:
        raise EvaluationContractError(
            f"initial SC TO-T count drift: expected {EXPECTED_INITIAL_EPISODES}, got {len(episodes)}"
        )

    for episode in episodes:
        eligibility = lifecycle.evaluate_locked_policy_eligibility(episode)
        episode["eligibility"] = eligibility
        episode["policy_eligible"] = bool(eligibility.get("eligible"))
        episode["document_policy_eligible"] = bool(
            eligibility.get("document_policy_eligible")
        )
    episodes.sort(
        key=lambda row: (
            str(row.get("filing_date") or ""),
            str(row.get("accession_number") or ""),
        )
    )
    rowset_sha = _canonical_sha(episodes)
    payload = {
        "schema": "exp_20260719_003_sec_cash_tender_contracts_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "rule_version": lifecycle.RULE_VERSION,
        "canonical_windows": WINDOWS,
        "initial_episode_count": len(episodes),
        "expected_initial_episode_count": EXPECTED_INITIAL_EPISODES,
        "parse_error_count": sum(bool(row.get("parse_error")) for row in episodes),
        "document_policy_eligible_count": sum(
            bool(row.get("document_policy_eligible")) for row in episodes
        ),
        "policy_eligible_count": sum(bool(row.get("policy_eligible")) for row in episodes),
        "amendment_count": sum(len(row.get("amendments") or []) for row in episodes),
        "target_event_filing_count": sum(
            len(row.get("target_event_filings") or []) for row in episodes
        ),
        "master_index_urls": master_urls,
        "master_index_coverage_complete": not missing_master_urls,
        "source_request_count": len(recorder.records),
        "source_requests": recorder.records,
        "episodes_rowset_sha256": rowset_sha,
        "episodes": episodes,
        "pit_contract": (
            "Historical public-availability proxy keyed by SEC accepted_at/filing_date; "
            "every semantic field is URL/hash/evidence-span bound and parsing fails closed."
        ),
    }
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(payload, CONTRACTS_PATH, indent=2, ensure_ascii=True)
    return payload


def ortex_exchange_symbol(value: Any) -> str:
    """Map SEC listing labels to an ORTEX path symbol (as-of ignores it for US)."""

    canonical = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if canonical in {"NASDAQ", "NASDAQ_GLOBAL", "NASDAQ_GLOBAL_SELECT", "NASDAQ_CAPITAL"}:
        return "nasdaq"
    if canonical in {"NYSE", "NEW_YORK_STOCK_EXCHANGE"}:
        return "nyse"
    if canonical in {"NYSE_AMERICAN", "AMEX", "AMERICAN_STOCK_EXCHANGE"}:
        return "amex"
    if canonical in {"CBOE", "BATS"}:
        return "us"
    raise EvaluationContractError(f"unsupported target exchange: {value!r}")


def _window_for_filing(filing_date: Any) -> tuple[str, dict[str, str]]:
    day = str(filing_date or "")[:10]
    for label, spec in WINDOWS.items():
        if spec["start"] <= day <= spec["end"]:
            return label, spec
    raise EvaluationContractError(f"filing is outside canonical windows: {filing_date!r}")


def price_request_range(episode: Mapping[str, Any]) -> tuple[str, str]:
    terms = episode.get("terms") if isinstance(episode.get("terms"), Mapping) else {}
    outcome = episode.get("outcome") if isinstance(episode.get("outcome"), Mapping) else {}
    filing = str(episode.get("filing_date") or "")[:10]
    announcement = str(
        terms.get("agreement_or_announcement_date")
        or terms.get("announcement_or_agreement_date")
        or filing
    )[:10]
    try:
        start = (
            date.fromisoformat(announcement)
            - timedelta(days=PRICE_PRE_ANNOUNCEMENT_CALENDAR_DAYS)
        ).isoformat()
    except ValueError as exc:
        raise EvaluationContractError("missing valid announcement/agreement date") from exc
    _, window = _window_for_filing(filing)
    status = str(outcome.get("outcome_type") or "pending")
    public_date = str(
        outcome.get("outcome_date") or outcome.get("amendment_filing_date") or ""
    )[:10]
    early_exit_statuses = {
        "completed",
        "terminated_negative",
        "terminated_higher_bid",
        "higher_bid_pending",
    }
    end = window["end"]
    if status in early_exit_statuses and public_date:
        try:
            end = min(
                end,
                (
                    date.fromisoformat(public_date)
                    + timedelta(days=PRICE_POST_OUTCOME_CALENDAR_DAYS)
                ).isoformat(),
            )
        except ValueError as exc:
            raise EvaluationContractError("invalid public outcome date") from exc
    if start > end:
        raise EvaluationContractError(f"invalid ORTEX request range: {start}..{end}")
    return start, end


def _fetch_ortex_episode_prices(
    episodes: Sequence[Mapping[str, Any]],
    provider: Callable[..., Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    for episode in episodes:
        accession = str(episode.get("accession_number") or "")
        terms = episode.get("terms") if isinstance(episode.get("terms"), Mapping) else {}
        ticker = str(terms.get("target_ticker") or "").upper()
        exchange = ortex_exchange_symbol(terms.get("target_exchange"))
        start, end = price_request_range(episode)
        try:
            result = provider(
                ticker,
                exchange,
                start,
                end,
                ticker_as_of_date=str(episode.get("filing_date") or "")[:10],
                credit_budget=ORTEX_PER_EPISODE_CREDIT_BUDGET,
                min_credits_left=ORTEX_MIN_CREDITS_LEFT,
            )
            if not isinstance(result, Mapping):
                raise EvaluationContractError("ORTEX adapter returned a non-object")
            results[accession] = dict(result)
        except Exception as exc:
            failures.append(
                {
                    "accession_number": accession,
                    "ticker": ticker,
                    "exchange": exchange,
                    "start_date": start,
                    "end_date": end,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    return results, failures


def collect_ortex_prices(
    contracts: Mapping[str, Any] | None = None,
    *,
    fetch_price: Callable[..., Mapping[str, Any]] | None = None,
    write: bool = True,
    reuse_existing: bool = True,
) -> dict[str, Any]:
    """Fetch every document-policy-eligible target under the hard credit floor."""

    contract_payload = dict(contracts or _read_json(CONTRACTS_PATH))
    rowset_sha = str(contract_payload.get("episodes_rowset_sha256") or "")
    if not rowset_sha:
        raise EvaluationContractError("contracts artifact has no episodes_rowset_sha256")
    if write and reuse_existing and PRICES_PATH.exists():
        existing = _read_json(PRICES_PATH)
        if existing.get("contracts_rowset_sha256") != rowset_sha:
            raise EvaluationContractError("immutable ORTEX cache belongs to another contract rowset")
        return existing

    episodes = [
        dict(row)
        for row in contract_payload.get("episodes") or []
        if isinstance(row, Mapping) and bool(row.get("policy_eligible"))
    ]
    provider = fetch_price or tender_prices.fetch_ortex_closing_price_history
    results, failures = _fetch_ortex_episode_prices(episodes, provider)
    payload = {
        "schema": "exp_20260719_003_ortex_price_cache_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "contracts_rowset_sha256": rowset_sha,
        "source": "ORTEX closing_prices with US ticker_as_of_date",
        "request_metadata": {
            "policy_eligible_episode_count": len(episodes),
            "successful_episode_count": len(results),
            "failed_episode_count": len(failures),
            "minimum_credits_left": ORTEX_MIN_CREDITS_LEFT,
            "per_episode_credit_budget": ORTEX_PER_EPISODE_CREDIT_BUDGET,
            "historical_delisting_consistency": "ticker_as_of_date_required",
            "sensitive_material_persisted": False,
        },
        "episodes": results,
        "failures": failures,
        "moomoo_execution_feasibility": {
            "status": "not_run_historical_replay_does_not_depend_on_current_symbol",
            "role": "current_symbol_and_live_execution_diagnostic_only",
            "replay_eligible": False,
            "manual_live_checks_required": [
                "broker tender cutoff before issuer expiration",
                "corporate-action event fee",
                "whole-share and odd-lot acceptance semantics",
            ],
        },
    }
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        tender_prices.write_immutable_price_cache(PRICES_PATH, payload)
    return payload


def collect_ortex_price_supplement(
    contracts: Mapping[str, Any] | None = None,
    base_prices: Mapping[str, Any] | None = None,
    *,
    fetch_price: Callable[..., Mapping[str, Any]] | None = None,
    write: bool = True,
    reuse_existing: bool = True,
) -> dict[str, Any]:
    """Retry only the base-cache rows affected by ORTEX's exact no-data envelope."""

    contract_payload = dict(contracts or _read_json(CONTRACTS_PATH))
    base_doc = dict(base_prices or _read_json(PRICES_PATH))
    rowset_sha = str(contract_payload.get("episodes_rowset_sha256") or "")
    if not rowset_sha or base_doc.get("contracts_rowset_sha256") != rowset_sha:
        raise EvaluationContractError("supplement inputs do not share a contract rowset")
    base_cache_sha = _sha256_file(PRICES_PATH) if base_prices is None else None
    if write and reuse_existing and PRICE_SUPPLEMENT_PATH.exists():
        existing = _read_json(PRICE_SUPPLEMENT_PATH)
        if existing.get("contracts_rowset_sha256") != rowset_sha:
            raise EvaluationContractError("price supplement belongs to another contract rowset")
        if base_cache_sha and existing.get("base_price_cache_sha256") != base_cache_sha:
            raise EvaluationContractError("price supplement belongs to another base cache")
        return existing

    retryable_accessions = {
        str(row.get("accession_number") or "")
        for row in base_doc.get("failures") or []
        if isinstance(row, Mapping)
        and row.get("error_type") == "OrtexPayloadError"
        and row.get("error") == "ORTEX data/rows must be a list of objects"
    }
    episodes = [
        dict(row)
        for row in contract_payload.get("episodes") or []
        if isinstance(row, Mapping)
        and str(row.get("accession_number") or "") in retryable_accessions
    ]
    if len(episodes) != len(retryable_accessions):
        raise EvaluationContractError("supplement retry population is not contract-exhaustive")
    provider = fetch_price or tender_prices.fetch_ortex_closing_price_history
    results, failures = _fetch_ortex_episode_prices(episodes, provider)
    payload = {
        "schema": "exp_20260719_003_ortex_no_data_supplement_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "contracts_rowset_sha256": rowset_sha,
        "base_price_cache_sha256": base_cache_sha,
        "source": "ORTEX closing_prices exact no-data envelope parser repair",
        "repair_contract": {
            "base_error_type": "OrtexPayloadError",
            "base_error": "ORTEX data/rows must be a list of objects",
            "accepted_empty_envelope": {
                "message": "No data returned for the given query parameters"
            },
            "retry_scope": "only matching failures from immutable base cache",
        },
        "request_metadata": {
            "retryable_episode_count": len(episodes),
            "successful_episode_count": len(results),
            "failed_episode_count": len(failures),
            "minimum_credits_left": ORTEX_MIN_CREDITS_LEFT,
            "per_episode_credit_budget": ORTEX_PER_EPISODE_CREDIT_BUDGET,
            "historical_delisting_consistency": "ticker_as_of_date_required",
            "sensitive_material_persisted": False,
        },
        "episodes": results,
        "failures": failures,
        "trade_enabled": False,
    }
    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        tender_prices.write_immutable_price_cache(PRICE_SUPPLEMENT_PATH, payload)
    return payload


def _merge_price_documents(
    base_prices: Mapping[str, Any],
    supplement: Mapping[str, Any] | None,
) -> dict[str, Any]:
    base_doc = dict(base_prices)
    if supplement is None:
        return base_doc
    supplement_doc = dict(supplement)
    rowset_sha = base_doc.get("contracts_rowset_sha256")
    if not rowset_sha or supplement_doc.get("contracts_rowset_sha256") != rowset_sha:
        raise EvaluationContractError("base and supplement price rowsets differ")
    base_episodes = base_doc.get("episodes") or {}
    supplement_episodes = supplement_doc.get("episodes") or {}
    if not isinstance(base_episodes, Mapping) or not isinstance(
        supplement_episodes, Mapping
    ):
        raise EvaluationContractError("price episodes must be objects")
    overlap = set(base_episodes) & set(supplement_episodes)
    if overlap:
        raise EvaluationContractError("price supplement overlaps immutable base cache")
    merged_episodes = {**dict(base_episodes), **dict(supplement_episodes)}
    retried = {
        str(row.get("accession_number") or "")
        for row in supplement_doc.get("failures") or []
        if isinstance(row, Mapping)
    } | set(supplement_episodes)
    merged_failures = [
        dict(row)
        for row in base_doc.get("failures") or []
        if isinstance(row, Mapping)
        and str(row.get("accession_number") or "") not in retried
    ] + [
        dict(row)
        for row in supplement_doc.get("failures") or []
        if isinstance(row, Mapping)
    ]
    return {
        **base_doc,
        "schema": "exp_20260719_003_ortex_price_cache_merged_v1",
        "episodes": merged_episodes,
        "failures": merged_failures,
        "request_metadata": {
            "successful_episode_count": len(merged_episodes),
            "failed_episode_count": len(merged_failures),
            "base": base_doc.get("request_metadata"),
            "supplement": supplement_doc.get("request_metadata"),
        },
        "supplement_identity": {
            "schema": supplement_doc.get("schema"),
            "base_price_cache_sha256": supplement_doc.get("base_price_cache_sha256"),
        },
    }


def _metrics(values: Sequence[float], *, capital: float) -> dict[str, Any]:
    returns = np.asarray(values, dtype=float)
    if returns.ndim != 1 or not len(returns):
        raise EvaluationContractError("return series is empty or not one-dimensional")
    if not np.all(np.isfinite(returns)) or np.any(returns <= -1.0):
        raise EvaluationContractError("return series contains invalid values")
    total_return = float(np.prod(1.0 + returns) - 1.0)
    volatility = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (
        float(np.mean(returns) / volatility * math.sqrt(252.0))
        if volatility > 0
        else 0.0
    )
    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns)))
    peaks = np.maximum.accumulate(equity)
    drawdown = float(np.max((peaks - equity) / peaks))
    public_return = round(total_return, 4)
    public_sharpe = round(sharpe, 2)
    return {
        "days": len(returns),
        "total_return_fraction": total_return,
        "strategy_total_return_public": public_return,
        "total_pnl_full_precision": capital * total_return,
        "total_pnl": round(capital * total_return, 2),
        "sharpe_daily_full_precision": sharpe,
        "sharpe_daily": public_sharpe,
        "expected_value_score_full_precision": total_return * abs(sharpe),
        "expected_value_score": round(public_return * abs(public_sharpe), 4),
        "max_drawdown_full_precision": drawdown,
        "max_drawdown_pct": round(drawdown, 4),
    }


def _load_baseline() -> dict[str, Any]:
    if _sha256_file(BASELINE_PATH) != BASELINE_SHA256:
        raise EvaluationContractError("active baseline hash drift")
    summary = _read_json(BASELINE_PATH)
    aggregate = summary.get("aggregate") or {}
    if not (
        summary.get("experiment_id") == "exp-20260715-010"
        and _finite(aggregate.get("expected_value_score_sum")) == BASELINE_EV
        and _finite(aggregate.get("total_pnl_sum")) == BASELINE_PNL_USD
    ):
        raise EvaluationContractError("active Gate-1 headline drift")
    declared = {
        str(row.get("label")): row
        for row in summary.get("windows") or []
        if isinstance(row, Mapping)
    }
    windows: dict[str, Any] = {}
    for label, spec in WINDOWS.items():
        artifact_path = REPO_ROOT / spec["replay"]
        artifact = _read_json(artifact_path)
        calendar, returns = core_calendar_and_returns(artifact)
        metrics = _metrics(returns, capital=100_000.0)
        expected = declared.get(label) or {}
        checks = {
            "ev_roundtrip": metrics["expected_value_score"]
            == _finite(expected.get("expected_value_score")),
            "pnl_within_2c": abs(
                metrics["total_pnl"] - float(expected.get("total_pnl") or 0.0)
            )
            <= 0.02,
            "sharpe_roundtrip": metrics["sharpe_daily"]
            == _finite(expected.get("sharpe_daily")),
            "drawdown_roundtrip": metrics["max_drawdown_pct"]
            == _finite(expected.get("max_drawdown_pct")),
        }
        if not all(checks.values()):
            raise EvaluationContractError(f"baseline curve drift {label}: {checks}")
        windows[label] = {
            "dates": calendar,
            "returns": np.asarray(returns, dtype=float),
            "metrics": metrics,
            "path": _repo_rel(artifact_path),
            "sha256": _sha256_file(artifact_path),
            "checks": checks,
            "declared": dict(expected),
        }
    return {"summary": summary, "windows": windows, "sha256": BASELINE_SHA256}


def _aligned_sleeve_returns(
    replay: Mapping[str, Any], calendar: Sequence[date]
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    rows = replay.get("daily_returns")
    if not isinstance(rows, list):
        raise EvaluationContractError("shared helper omitted daily_returns")
    by_date: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise EvaluationContractError("shared helper emitted a non-object return row")
        day = str(row.get("as_of") or row.get("date") or "")[:10]
        value = _finite(row.get("daily_return"))
        if not day or value is None or value <= -1.0 or day in by_date:
            raise EvaluationContractError(f"invalid or duplicate shared-helper return: {row}")
        by_date[day] = value
    ordered_dates = [value.isoformat() for value in calendar]
    missing = [day for day in ordered_dates if day not in by_date]
    if missing:
        raise EvaluationContractError(f"shared helper missed core dates: {missing[:5]}")
    values = np.asarray([by_date[day] for day in ordered_dates], dtype=float)
    return (
        values,
        [
            {"date": day, "return": float(value)}
            for day, value in zip(ordered_dates, values)
        ],
        {
            "core_calendar_count": len(ordered_dates),
            "helper_return_count": len(rows),
            "missing_dates": missing,
            "extra_dates_ignored": sorted(set(by_date) - set(ordered_dates)),
            "aligned_by_exact_date": True,
        },
    )


def capital_conserving_blend_returns(
    core_returns: Sequence[float], sleeve_returns: Sequence[float]
) -> np.ndarray:
    """Return a fully funded 90/10 daily mix, never a levered PnL overlay."""

    core = np.asarray(core_returns, dtype=float)
    candidate = np.asarray(sleeve_returns, dtype=float)
    if core.ndim != 1 or candidate.ndim != 1 or len(core) != len(candidate):
        raise EvaluationContractError("core and sleeve returns must be equal-length vectors")
    if not np.all(np.isfinite(core)) or not np.all(np.isfinite(candidate)):
        raise EvaluationContractError("core and sleeve returns must be finite")
    return CORE_WEIGHT * core + SLEEVE_WEIGHT * candidate


def _aggregate_window_metrics(
    windows: Mapping[str, Mapping[str, Any]], key: str
) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row[key]["expected_value_score"]) for row in windows.values()), 4
        ),
        "total_pnl_sum": round(
            sum(float(row[key]["total_pnl"]) for row in windows.values()), 2
        ),
        "worst_max_drawdown_pct": max(
            float(row[key]["max_drawdown_pct"]) for row in windows.values()
        ),
    }


def _trade_gate(
    trades: Sequence[Mapping[str, Any]], contracts: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    required = (
        "accession_number",
        "ticker",
        "entry_date",
        "entry_price",
        "target_price",
        "target_price_role",
        "net_pnl_usd",
        "valuation_date",
        "actual_close",
        "right_censored",
    )
    failures: list[str] = []
    for index, trade in enumerate(trades):
        accession = str(trade.get("accession_number") or "")
        trade_id = f"{accession or index}:{trade.get('entry_date')}"
        missing = [key for key in required if key not in trade or trade.get(key) is None]
        # A right-censored trade deliberately has no exit_date/exit_price, but
        # valuation_date and valuation_price remain mandatory.
        if missing:
            failures.append(f"missing_fields:{trade_id}:{','.join(missing)}")
        if trade.get("target_price_role") != "contract_cash_offer_price":
            failures.append(f"target_price_role:{trade_id}")
        contract = contracts.get(accession) or {}
        terms = contract.get("terms") if isinstance(contract.get("terms"), Mapping) else {}
        if not (
            contract.get("raw_submission_sha256")
            and (contract.get("primary_schedule_to") or {}).get("source_sha256")
            and (contract.get("offer_to_purchase_exhibit") or {}).get("source_sha256")
            and terms.get("evidence_spans")
        ):
            failures.append(f"sec_provenance:{trade_id}")
        if bool(trade.get("right_censored")):
            if trade.get("actual_close") or not trade.get("valuation_price"):
                failures.append(f"right_censor_contract:{trade_id}")
        elif not trade.get("exit_date"):
            failures.append(f"closed_trade_missing_exit_date:{trade_id}")
    return {
        "passed": not failures,
        "required_fields": list(required),
        "trade_count": len(trades),
        "failures": failures,
    }


def _absolute_pnl_concentration(
    rows: Sequence[Mapping[str, Any]], *, population: str
) -> dict[str, Any]:
    absolute_total = sum(abs(float(row.get("net_pnl_usd") or 0.0)) for row in rows)
    maximum_share = (
        max((abs(float(row.get("net_pnl_usd") or 0.0)) for row in rows), default=0.0)
        / absolute_total
        if absolute_total > 0
        else None
    )
    counts = Counter(str(row.get("ticker") or "") for row in rows)
    return {
        "population": population,
        "row_count": len(rows),
        "ticker_trade_counts": dict(sorted(counts.items())),
        "ticker_count": len([ticker for ticker in counts if ticker]),
        "absolute_pnl_total_usd": absolute_total,
        "maximum_single_deal_absolute_pnl_share": maximum_share,
    }


def _price_request_contract_failures(
    eligible_episodes: Sequence[Mapping[str, Any]],
    price_results: Mapping[str, Any],
) -> list[str]:
    """Bind replay prices to the SEC fields and calendar coverage actually consumed."""

    failures: list[str] = []
    for episode in eligible_episodes:
        accession = str(episode.get("accession_number") or "")
        result = price_results.get(accession)
        if not isinstance(result, Mapping):
            failures.append(f"missing_price_result:{accession}")
            continue
        terms = episode.get("terms") if isinstance(episode.get("terms"), Mapping) else {}
        ticker = str(terms.get("target_ticker") or "").upper()
        start, end = price_request_range(episode)
        exact_expected = {
            "ticker": ticker,
            "ticker_as_of_date": str(episode.get("filing_date") or "")[:10],
            "status": "complete",
        }
        for field, expected_value in exact_expected.items():
            if result.get(field) != expected_value:
                failures.append(
                    f"price_request_identity_mismatch:{accession}:{field}:"
                    f"{result.get(field)!r}:{expected_value!r}"
                )
        try:
            actual_start = date.fromisoformat(str(result.get("start_date") or ""))
            actual_end = date.fromisoformat(str(result.get("end_date") or ""))
            expected_start = date.fromisoformat(start)
            expected_end = date.fromisoformat(end)
        except ValueError:
            failures.append(f"invalid_price_request_dates:{accession}")
            continue
        if actual_start > expected_start:
            failures.append(
                f"price_request_start_does_not_cover:{accession}:"
                f"{actual_start.isoformat()}:{expected_start.isoformat()}"
            )
        if actual_end < expected_end:
            missing_days = []
            day = actual_end + timedelta(days=1)
            while day <= expected_end:
                missing_days.append(day)
                day += timedelta(days=1)
            if any(day.weekday() < 5 for day in missing_days):
                failures.append(
                    f"price_request_end_does_not_cover_sessions:{accession}:"
                    f"{actual_end.isoformat()}:{expected_end.isoformat()}"
                )
    return failures


def evaluate(
    contracts_payload: Mapping[str, Any] | None = None,
    prices_payload: Mapping[str, Any] | None = None,
    price_supplement_payload: Mapping[str, Any] | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    contracts_doc = dict(contracts_payload or _read_json(CONTRACTS_PATH))
    base_prices_doc = dict(prices_payload or _read_json(PRICES_PATH))
    supplement_doc: dict[str, Any] | None
    if price_supplement_payload is not None:
        supplement_doc = dict(price_supplement_payload)
    elif prices_payload is None and PRICE_SUPPLEMENT_PATH.exists():
        supplement_doc = _read_json(PRICE_SUPPLEMENT_PATH)
        expected_base_sha = supplement_doc.get("base_price_cache_sha256")
        if expected_base_sha and expected_base_sha != _sha256_file(PRICES_PATH):
            raise EvaluationContractError("price supplement base-cache identity mismatch")
    else:
        supplement_doc = None
    prices_doc = _merge_price_documents(base_prices_doc, supplement_doc)
    price_contract_rowset_match = prices_doc.get(
        "contracts_rowset_sha256"
    ) == contracts_doc.get("episodes_rowset_sha256")
    baseline = _load_baseline()
    episodes = [
        dict(row)
        for row in contracts_doc.get("episodes") or []
        if isinstance(row, Mapping)
    ]
    eligible = [row for row in episodes if bool(row.get("policy_eligible"))]
    contract_by_accession = {
        str(row.get("accession_number")): row for row in episodes
    }
    price_results = prices_doc.get("episodes") or {}
    if not isinstance(price_results, Mapping):
        raise EvaluationContractError("ORTEX cache episodes must be an object")
    price_request_contract_failures = _price_request_contract_failures(
        eligible, price_results
    )

    windows: dict[str, Any] = {}
    all_position_rows: list[dict[str, Any]] = []
    all_actual_closed_trades: list[dict[str, Any]] = []
    entered_trade_count = 0
    right_censored_position_count = 0
    gate2_failures: list[str] = list(price_request_contract_failures)
    signals_generated = 0
    signals_survived = 0
    positive_windows: list[str] = []
    for label, spec in WINDOWS.items():
        window_episodes = [
            row
            for row in eligible
            if spec["start"] <= str(row.get("filing_date") or "")[:10] <= spec["end"]
        ]
        calendar = baseline["windows"][label]["dates"]
        replay = sleeve.replay_sec_cash_tender_spread_sleeve(
            window_episodes,
            price_results,
            spec["start"],
            spec["end"],
            event_fee_usd=20.0,
            calendar_sessions=calendar,
        )
        candidate_returns, return_rows, alignment = _aligned_sleeve_returns(
            replay, calendar
        )
        core_returns = baseline["windows"][label]["returns"]
        if len(candidate_returns) != len(core_returns):
            raise EvaluationContractError(f"return length drift: {label}")
        after_returns = capital_conserving_blend_returns(
            core_returns, candidate_returns
        )
        cash_diagnostic_returns = CORE_WEIGHT * core_returns
        before_metrics = _metrics(core_returns, capital=100_000.0)
        candidate_metrics = _metrics(candidate_returns, capital=10_000.0)
        after_metrics = _metrics(after_returns, capital=100_000.0)
        cash_metrics = _metrics(cash_diagnostic_returns, capital=100_000.0)
        trades = [dict(row) for row in replay.get("trades") or []]
        actual_closed_trades = [
            dict(row) for row in replay.get("actual_closed_trades") or []
        ]
        window_entered_count = int(replay.get("entered_trade_count") or 0)
        window_right_censored_count = int(
            replay.get("right_censored_position_count") or 0
        )
        trade_gate = _trade_gate(trades, contract_by_accession)
        expected_accessions = {
            str(row.get("accession_number") or "") for row in window_episodes
        }
        evaluated_accessions = {
            str(row.get("accession_number") or "")
            for row in replay.get("candidate_evaluations") or []
        }
        window_failures = list(trade_gate["failures"])
        if expected_accessions != evaluated_accessions:
            window_failures.append(
                f"eligible_population_not_exhaustive:{len(expected_accessions)}:{len(evaluated_accessions)}"
            )
        if replay.get("measurement_failures"):
            window_failures.append("shared_helper_measurement_failures")
        helper_metrics = replay.get("metrics") or {}
        if not helper_metrics.get("cash_nonnegative"):
            window_failures.append("negative_sleeve_cash")
        if not helper_metrics.get("cash_conservation_passed"):
            window_failures.append("cash_conservation_failed")
        if window_failures:
            gate2_failures.extend(f"{label}:{reason}" for reason in window_failures)
        generated = int(replay.get("signals_generated") or 0)
        survived = int(replay.get("signals_survived") or 0)
        signals_generated += generated
        signals_survived += survived
        if (
            candidate_metrics["expected_value_score"] > 0
            and candidate_metrics["total_pnl"] > 0
        ):
            positive_windows.append(label)
        windows[label] = {
            "start": spec["start"],
            "end": spec["end"],
            "before": before_metrics,
            "candidate": candidate_metrics,
            "after": after_metrics,
            "diagnostic_90_core_10_cash": cash_metrics,
            "delta": {
                "expected_value_score": round(
                    after_metrics["expected_value_score"]
                    - before_metrics["expected_value_score"],
                    4,
                ),
                "total_pnl": round(
                    after_metrics["total_pnl"] - before_metrics["total_pnl"], 2
                ),
                "max_drawdown_pct": round(
                    after_metrics["max_drawdown_pct"]
                    - before_metrics["max_drawdown_pct"],
                    6,
                ),
            },
            "signals_generated": generated,
            "signals_survived": survived,
            "survival_rate": survived / generated if generated else None,
            "funded_trade_count": window_entered_count,
            "entered_trade_count": window_entered_count,
            "actual_closed_trade_count": len(actual_closed_trades),
            "right_censored_position_count": window_right_censored_count,
            "gate2": {"passed": not window_failures, "failures": window_failures},
            "return_alignment": alignment,
            "candidate_daily_returns": return_rows,
            "candidate_daily_equity": replay.get("daily_ledger"),
            "event_fee_sensitivity": replay.get("event_fee_sensitivity"),
            "candidate_evaluations": replay.get("candidate_evaluations"),
            "candidate_rejections": replay.get("candidate_rejections"),
            "trades": trades,
            "actual_closed_trades": actual_closed_trades,
            "helper_summary": replay.get("summary"),
            "measurement_failures": replay.get("measurement_failures"),
        }
        all_position_rows.extend(trades)
        all_actual_closed_trades.extend(actual_closed_trades)
        entered_trade_count += window_entered_count
        right_censored_position_count += window_right_censored_count

    before_aggregate = _aggregate_window_metrics(windows, "before")
    candidate_aggregate = _aggregate_window_metrics(windows, "candidate")
    after_aggregate = _aggregate_window_metrics(windows, "after")
    if not (
        before_aggregate["expected_value_score_sum"] == BASELINE_EV
        and abs(before_aggregate["total_pnl_sum"] - BASELINE_PNL_USD) <= 0.02
    ):
        raise EvaluationContractError(f"aggregate baseline roundtrip failed: {before_aggregate}")

    survival_rate = (
        signals_survived / signals_generated if signals_generated else None
    )
    price_eligible_accessions = {
        str(row.get("accession_number") or "") for row in eligible
    }
    price_success_accessions = set(str(key) for key in price_results)
    missing_price_accessions = sorted(
        price_eligible_accessions - price_success_accessions
    )
    ignored_price_accessions = sorted(
        price_success_accessions - price_eligible_accessions
    )
    trade_gate = _trade_gate(all_position_rows, contract_by_accession)
    gate2 = {
        "passed": not gate2_failures and not missing_price_accessions,
        "failures": gate2_failures,
        "master_index_coverage_complete": bool(
            contracts_doc.get("master_index_coverage_complete")
        ),
        "initial_episode_count": len(episodes),
        "parse_error_count": int(contracts_doc.get("parse_error_count") or 0),
        "policy_eligible_episode_count": len(eligible),
        "price_success_episode_count": len(
            price_success_accessions & price_eligible_accessions
        ),
        "missing_price_accessions": missing_price_accessions,
        "ignored_price_accessions_from_pre_repair_population": ignored_price_accessions,
        "price_contract_rowset_sha256_match": price_contract_rowset_match,
        "price_request_contract": {
            "passed": not price_request_contract_failures,
            "failures": price_request_contract_failures,
            "identity_fields": [
                "accession_number",
                "ticker",
                "ticker_as_of_date",
                "start_date_covers_required_lookback",
                "end_date_covers_required_sessions",
                "status",
            ],
            "rowset_mismatch_policy": (
                "allowed only when identity fields match and the immutable range "
                "covers every required trading session; full SEC rowset may change "
                "after a semantics-only parser repair"
            ),
        },
        "every_policy_eligible_episode_evaluated": signals_generated == len(eligible),
        "trade_contract": trade_gate,
        "right_censored_trade_count": sum(
            bool(row.get("right_censored")) for row in all_position_rows
        ),
        "entered_trade_count": entered_trade_count,
        "actual_closed_trade_count": len(all_actual_closed_trades),
        "entry_date_and_target_price_checked": True,
    }
    if not gate2["master_index_coverage_complete"]:
        gate2["failures"].append("master_index_coverage_incomplete")
        gate2["passed"] = False
    if signals_generated != len(eligible):
        gate2["failures"].append("policy_eligible_population_not_exhaustive")
        gate2["passed"] = False
    if not trade_gate["passed"]:
        gate2["passed"] = False
    gate3 = {
        "passed": (
            signals_generated > 0
            and survival_rate is not None
            and survival_rate >= MIN_SURVIVAL_RATE
        ),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": survival_rate,
        "minimum_survival_rate": MIN_SURVIVAL_RATE,
    }

    realized_concentration = _absolute_pnl_concentration(
        all_actual_closed_trades,
        population="actual_closed_realized_rows",
    )
    mtm_inclusive_concentration = _absolute_pnl_concentration(
        all_position_rows,
        population="entered_rows_including_right_censored_window_end_mtm",
    )
    realized_max_share = realized_concentration[
        "maximum_single_deal_absolute_pnl_share"
    ]
    mtm_inclusive_max_share = mtm_inclusive_concentration[
        "maximum_single_deal_absolute_pnl_share"
    ]
    standalone_checks = {
        "gate2_passed": gate2["passed"],
        "gate3_passed": gate3["passed"],
        "minimum_15_funded_trades": entered_trade_count >= MIN_TOTAL_TRADES,
        "minimum_4_funded_trades_each_window": all(
            int(row["funded_trade_count"]) >= MIN_TRADES_PER_WINDOW
            for row in windows.values()
        ),
        "aggregate_ev_positive": candidate_aggregate["expected_value_score_sum"] > 0,
        "aggregate_pnl_positive": candidate_aggregate["total_pnl_sum"] > 0,
        "at_least_two_positive_windows": len(positive_windows) >= MIN_POSITIVE_WINDOWS,
        "standalone_drawdown_lte_8pct": (
            candidate_aggregate["worst_max_drawdown_pct"] <= MAX_STANDALONE_DRAWDOWN
        ),
        "single_deal_absolute_pnl_share_lte_25pct": (
            realized_max_share is not None
            and realized_max_share <= MAX_SINGLE_DEAL_ABSOLUTE_PNL_SHARE
            and mtm_inclusive_max_share is not None
            and mtm_inclusive_max_share <= MAX_SINGLE_DEAL_ABSOLUTE_PNL_SHARE
        ),
        "all_policy_eligible_failures_and_right_censors_included": (
            signals_generated == len(eligible)
        ),
    }
    standalone_passed = all(standalone_checks.values())
    drawdown_drift = (
        after_aggregate["worst_max_drawdown_pct"]
        - before_aggregate["worst_max_drawdown_pct"]
    )
    portfolio_checks = {
        "standalone_passed": standalone_passed,
        "aggregate_ev_improved": (
            after_aggregate["expected_value_score_sum"]
            > before_aggregate["expected_value_score_sum"]
        ),
        "aggregate_pnl_improved": (
            after_aggregate["total_pnl_sum"] > before_aggregate["total_pnl_sum"]
        ),
        "drawdown_drift_lte_0_5pp": drawdown_drift
        <= MAX_PORTFOLIO_DRAWDOWN_DRIFT,
    }
    portfolio_passed = all(portfolio_checks.values())
    decision = (
        "accepted_capital_promoted_default_off_cash_tender_engine"
        if portfolio_passed
        else "rejected_cash_tender_spread_policy"
    )

    latest_label = "late_strong"
    latest_spec = WINDOWS[latest_label]
    latest_episodes = [
        row
        for row in eligible
        if latest_spec["start"]
        <= str(row.get("filing_date") or "")[:10]
        <= latest_spec["end"]
    ]
    snapshot = sleeve.build_sec_cash_tender_spread_paper_snapshot(
        latest_spec["end"],
        latest_episodes,
        price_results,
        start=latest_spec["start"],
        event_fee_usd=20.0,
        calendar_sessions=baseline["windows"][latest_label]["dates"],
    )
    snapshot["snapshot_role"] = "historical_end_of_latest_canonical_window_parity_proof"

    before_projection = {
        "schema": "exp_20260719_003_before_projection_v1",
        "experiment_id": EXPERIMENT_ID,
        "benchmarks": {"strategy_total_return_pct": BASELINE_RETURN_SUM},
        "expected_value_score": BASELINE_EV,
        "expected_value_score_formula": "strategy_total_return_pct * abs(sharpe_daily)",
        "total_pnl": BASELINE_PNL_USD,
        "max_drawdown_pct": BASELINE_WORST_DRAWDOWN,
        "total_trades": BASELINE_TRADES,
        "survival_rate": BASELINE_MIN_SURVIVAL,
        "source": _repo_rel(BASELINE_PATH),
        "source_sha256": BASELINE_SHA256,
    }
    headline_survival = (
        min(BASELINE_MIN_SURVIVAL, survival_rate)
        if survival_rate is not None
        else 0.0
    )
    payload = {
        "schema": "exp_20260719_003_sec_cash_tender_spread_v1",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "status": "completed",
        "decision": decision,
        "accepted_alpha": portfolio_passed,
        "independent_engine_counted": portfolio_passed,
        "live_ready": False,
        "expected_value_score": after_aggregate["expected_value_score_sum"],
        "total_pnl": after_aggregate["total_pnl_sum"],
        "max_drawdown_pct": after_aggregate["worst_max_drawdown_pct"],
        "total_trades": BASELINE_TRADES + len(all_actual_closed_trades),
        "survival_rate": headline_survival,
        "sharpe_daily": None,
        "benchmarks": {
            "strategy_total_return_pct": round(
                after_aggregate["total_pnl_sum"] / 100_000.0, 4
            )
        },
        "expected_value_score_formula": "per-window sum of total_return_fraction * abs(sharpe_daily)",
        "hypothesis": (
            "Board-recommended, fully financed all-cash SC TO-T target spreads "
            "converge to contractual cash value after carry, costs and failures."
        ),
        "policy_bundle": {
            "lifecycle_rule_version": lifecycle.RULE_VERSION,
            "sleeve_rule_version": sleeve.RULE_VERSION,
            "sizing": sleeve.execution_sizing_contract(),
            "entry": "first regular session open strictly after filing_date",
            "break_value": "mean of 20 strictly prior closes before agreement/announcement",
            "completion_probability_floor": 0.70,
            "carry_annual_rate": 0.05,
            "round_trip_cost_rate": 0.0035,
            "event_fee_usd": 20.0,
            "event_fee_sensitivity_usd": [0.0, 20.0, 40.0],
            "portfolio_weight": "90pct core plus separately funded 10pct tender sleeve",
            "llm_authority": "none; deterministic extraction only",
        },
        "source_identity": {
            "baseline": {"path": _repo_rel(BASELINE_PATH), "sha256": BASELINE_SHA256},
            "contracts": {
                "path": _repo_rel(CONTRACTS_PATH),
                "episodes_rowset_sha256": contracts_doc.get("episodes_rowset_sha256"),
                "initial_episode_count": len(episodes),
            },
            "prices": {
                "path": _repo_rel(PRICES_PATH),
                "contracts_rowset_sha256": prices_doc.get("contracts_rowset_sha256"),
                "current_contracts_rowset_sha256": contracts_doc.get(
                    "episodes_rowset_sha256"
                ),
                "full_rowset_sha256_match": price_contract_rowset_match,
                "request_metadata": prices_doc.get("request_metadata"),
                "supplement_path": (
                    _repo_rel(PRICE_SUPPLEMENT_PATH) if supplement_doc is not None else None
                ),
                "supplement_identity": prices_doc.get("supplement_identity"),
            },
            "core_windows": {
                label: {
                    "path": row["path"],
                    "sha256": row["sha256"],
                    "roundtrip_checks": row["checks"],
                }
                for label, row in baseline["windows"].items()
            },
        },
        "windows": windows,
        "aggregate": {
            "before": before_aggregate,
            "candidate": {
                **candidate_aggregate,
                "funded_trade_count": entered_trade_count,
                "entered_trade_count": entered_trade_count,
                "actual_closed_trade_count": len(all_actual_closed_trades),
                "right_censored_position_count": right_censored_position_count,
                "positive_windows": positive_windows,
                "signals_generated": signals_generated,
                "signals_survived": signals_survived,
                "survival_rate": survival_rate,
                "realized_concentration": realized_concentration,
                "mtm_inclusive_concentration": mtm_inclusive_concentration,
            },
            "after": after_aggregate,
            "delta": {
                "expected_value_score": round(
                    after_aggregate["expected_value_score_sum"]
                    - before_aggregate["expected_value_score_sum"],
                    4,
                ),
                "total_pnl": round(
                    after_aggregate["total_pnl_sum"]
                    - before_aggregate["total_pnl_sum"],
                    2,
                ),
                "worst_max_drawdown_drift": drawdown_drift,
            },
        },
        "gate1": {
            "passed": True,
            "baseline_experiment_id": "exp-20260715-010",
            "expected_value_score": BASELINE_EV,
            "total_pnl_usd": BASELINE_PNL_USD,
        },
        "gate2": gate2,
        "gate3": gate3,
        "standalone_acceptance": {
            "passed": standalone_passed,
            "checks": standalone_checks,
        },
        "portfolio_promotion": {
            "passed": portfolio_passed,
            "checks": portfolio_checks,
        },
        "prediction_calibration_input": {
            "success_probability": 0.32,
            "expected_ev_delta": 0.15,
            "expected_pnl_delta": 2_000.0,
            "realized_success": portfolio_passed,
            "realized_ev_delta": round(
                after_aggregate["expected_value_score_sum"] - BASELINE_EV, 4
            ),
            "realized_pnl_delta": round(
                after_aggregate["total_pnl_sum"] - BASELINE_PNL_USD, 2
            ),
        },
        "fingerprint_caveat": {
            "reservation_fingerprint_was_misclassified": True,
            "stored_source": "ortex_borrow",
            "stored_gate_shape": "portfolio_daily_equity_overlay",
            "corrected_source": "sec_text_event",
            "corrected_gate_shape": "corporate_action_cash_conversion",
            "classifier_tests_passed": True,
        },
        "external_best_practice_map": [
            "https://arxiv.org/pdf/2607.09921",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=246497",
            "https://www.nber.org/papers/w18914",
            "https://www.law.cornell.edu/cfr/text/17/240.14d-100",
            "https://www.law.cornell.edu/cfr/text/17/240.14e-1",
            "https://www.law.cornell.edu/cfr/text/17/240.14e-2",
            "https://www.sec.gov/about/reports-publications/investorpubsminitend",
            "https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/tender-offer-rules-schedules",
            "https://www.ftc.gov/advice-guidance/competition-guidance/guide-antitrust-laws/mergers/premerger-notification-merger-review-process",
            "https://www.andreisimonov.com/N4106/pdf/MitchellPulvinoJFDec2001.pdf",
            "https://docs.ortex.com/reference/stock_closing_prices_list",
            "https://www.moomoo.com/pricing?lang=en-us",
        ],
        "production_impact": {
            **sleeve.production_impact(),
            "run_py_changed": False,
            "default_off_snapshot_path": _repo_rel(SNAPSHOT_PATH),
            "live_blockers": [
                "Moomoo tender cutoff and event fee require broker confirmation",
                "broker corporate-action acceptance/whole-share semantics are not replayed",
                "forward paper settlements have not yet accrued",
                "no live locate issue because policy is long-only, but gap-to-break tail remains",
            ],
            "kill_switches_required_before_live": [
                "financing or board recommendation withdrawn",
                "offer expiration without extension evidence",
                "missing exact SEC amendment or price mark",
                "aggregate predicted break loss above funded sleeve budget",
            ],
        },
        "post_run_interpretation": {
            "engine_claim": "capital_promoted_default_off_engine" if portfolio_passed else "not_an_engine",
            "why_result_happened": (
                "By the first executable open after Schedule TO, most fixed-cash spreads "
                "were already too narrow to pay 5pct carry, 35bp round-trip cost and the "
                "20 USD corporate-action fee under the preregistered break-loss cap. Only "
                "HEES entered, so its positive higher-bid outcome remained statistically "
                "and economically concentrated; reserving 10pct cash displaced a much "
                "stronger core return."
            ),
            "primary_rejection_reason_counts": dict(
                sorted(
                    Counter(
                        str(row.get("primary_rejection_reason") or "none")
                        for window in windows.values()
                        for row in window.get("candidate_evaluations") or []
                        if row.get("status") == "rejected"
                    ).items()
                )
            ),
            "fee_sensitivity_role": (
                "0/20/40 USD runs are non-binding diagnostics except the locked 20 USD "
                "policy. Each sensitivity discloses measurement validity and failure "
                "reasons; invalid sensitivity EV/Sharpe/drawdown must not be promoted."
            ),
            "measurement_repairs_applied_before_final_gate": [
                "accepted exact ORTEX no-data envelopes as empty trailing chunks",
                "removed risk-factor termination false positives",
                "removed offeror-board approval as target-board recommendation",
                "used same-session open for premarket decisive events",
                "validated immutable prices by request-driving coverage after SEC semantic repairs",
            ],
            "parameter_retune_allowed": False,
            "forbidden_near_neighbor_retry": (
                "Do not sweep completion-probability, carry, fee, lookback, position, "
                "ADV, loss-budget or window thresholds on the same 81-offer surface."
            ),
            "reopen_condition": (
                "A new contractual corporate-action family, a new broker execution/fee "
                "source, or materially more settled forward cash-tender rows."
            ),
        },
        "reproduction": {
            "collect_sec": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260719_003_sec_cash_tender_spread.py collect-sec"
            ),
            "collect_prices": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260719_003_sec_cash_tender_spread.py collect-prices"
            ),
            "collect_price_supplement": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260719_003_sec_cash_tender_spread.py collect-price-supplement"
            ),
            "evaluate": (
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260719_003_sec_cash_tender_spread.py evaluate"
            ),
        },
    }
    after_projection = {
        key: payload[key]
        for key in (
            "schema",
            "experiment_id",
            "expected_value_score",
            "total_pnl",
            "max_drawdown_pct",
            "total_trades",
            "survival_rate",
            "sharpe_daily",
            "benchmarks",
            "expected_value_score_formula",
            "decision",
            "accepted_alpha",
        )
    }
    after_projection["aggregate"] = payload["aggregate"]
    after_projection["gate2"] = gate2
    after_projection["gate3"] = gate3
    after_projection["standalone_acceptance"] = payload["standalone_acceptance"]
    after_projection["portfolio_promotion"] = payload["portfolio_promotion"]

    if write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(before_projection, BEFORE_PATH, indent=2, ensure_ascii=True)
        atomic_write_json(after_projection, AFTER_PATH, indent=2, ensure_ascii=True)
        atomic_write_json(snapshot, SNAPSHOT_PATH, indent=2, ensure_ascii=True)
        atomic_write_json(payload, RESULT_PATH, indent=2, ensure_ascii=True)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=(
            "collect-sec",
            "collect-prices",
            "collect-price-supplement",
            "evaluate",
            "all",
        ),
        default="evaluate",
    )
    args = parser.parse_args()
    if args.command in {"collect-sec", "all"}:
        contracts = collect_sec_contracts()
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "stage": "collect-sec",
                    "initial_episode_count": contracts["initial_episode_count"],
                    "policy_eligible_count": contracts["policy_eligible_count"],
                    "parse_error_count": contracts["parse_error_count"],
                    "artifact": _repo_rel(CONTRACTS_PATH),
                },
                indent=2,
            )
        )
    if args.command in {"collect-prices", "all"}:
        prices = collect_ortex_prices()
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "stage": "collect-prices",
                    **dict(prices.get("request_metadata") or {}),
                    "artifact": _repo_rel(PRICES_PATH),
                },
                indent=2,
            )
        )
    if args.command in {"collect-price-supplement", "all"}:
        supplement = collect_ortex_price_supplement()
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "stage": "collect-price-supplement",
                    **dict(supplement.get("request_metadata") or {}),
                    "artifact": _repo_rel(PRICE_SUPPLEMENT_PATH),
                },
                indent=2,
            )
        )
    if args.command in {"evaluate", "all"}:
        result = evaluate()
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": result["decision"],
                    "candidate": result["aggregate"]["candidate"],
                    "after": result["aggregate"]["after"],
                    "delta": result["aggregate"]["delta"],
                    "artifact": _repo_rel(RESULT_PATH),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
