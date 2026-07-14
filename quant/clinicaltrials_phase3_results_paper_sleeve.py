"""Shared ClinicalTrials.gov Phase 3 first-results paper sleeve.

The historical and daily paths deliberately share the candidate and replay
functions in this module.  Historical rows are usable only when an exact
ClinicalTrials.gov Record History version has been archived.  Daily rows also
carry a local first-seen clock; an old result discovered later is seed-only and
cannot be backfilled into the forward paper ledger.

This sleeve is default-off.  Nothing in this module can submit an order or
change the core candidate ranking, sizing, or exits.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SLEEVE_NAME = "CLINICALTRIALS_PHASE3_RESULTS_PAPER"
RULE_VERSION = "clinicaltrials_phase3_results_green_spy_relative_top1_10d_v1"
SOURCE_RULE_VERSION = "clinicaltrials_results_first_post_history_v1"
API_BASE = "https://clinicaltrials.gov/api/v2"
HISTORY_BASE = "https://clinicaltrials.gov/api/int/studies"

# Preregistered in exp-20260713-008.  Exact matching is intentional: adding an
# alias after seeing replay results would change the tested candidate pool.
SPONSOR_TO_TICKER: dict[str, str] = {
    "Eli Lilly and Company": "LLY",
    "Novo Nordisk A/S": "NVO",
    "Pfizer": "PFE",
    "Merck Sharp & Dohme LLC": "MRK",
    "AbbVie": "ABBV",
    "Bristol-Myers Squibb": "BMY",
    "Amgen": "AMGN",
    "Gilead Sciences": "GILD",
    "Janssen Research & Development, LLC": "JNJ",
    "AstraZeneca": "AZN",
    "Regeneron Pharmaceuticals": "REGN",
    "Vertex Pharmaceuticals Incorporated": "VRTX",
}

BASE_NOTIONAL_USD = 4_000.0
ROUND_TRIP_COST_PCT = 0.0035
HOLD_DAYS = 10
SAME_TICKER_COOLDOWN_SESSIONS = 10
DAILY_ENTRY_SLOTS = 1


def _iso_date(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("date") or value.get("value")
    text = str(value or "").strip()
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _as_of_iso(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    parsed = _iso_date(text)
    if parsed is None:
        raise ValueError(f"invalid as_of_date: {value!r}")
    return parsed


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _raw_sha(payload: Any) -> str:
    return hashlib.sha256(_canonical_payload_bytes(payload)).hexdigest()


def _canonical_payload_bytes(payload: Any) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return raw.encode("utf-8")


def _study(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("study")
    return value if isinstance(value, dict) else payload


def _dig(obj: Any, *path: str) -> Any:
    current = obj
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _nct_id(study: dict[str, Any]) -> str:
    return str(
        _dig(study, "protocolSection", "identificationModule", "nctId")
        or study.get("nctId")
        or ""
    ).strip()


def _lead_sponsor(study: dict[str, Any]) -> str:
    return str(
        _dig(study, "protocolSection", "sponsorCollaboratorsModule", "leadSponsor", "name")
        or ""
    ).strip()


def _phases(study: dict[str, Any]) -> list[str]:
    raw = _dig(study, "protocolSection", "designModule", "phases") or []
    return [str(value).upper() for value in raw if str(value).strip()]


def _results_first_post_date(study: dict[str, Any]) -> str | None:
    status = _dig(study, "protocolSection", "statusModule") or {}
    return _iso_date(
        status.get("resultsFirstPostDateStruct")
        or status.get("resultsFirstPostDate")
    )


def _results_first_post_is_actual(study: dict[str, Any]) -> bool:
    status = _dig(study, "protocolSection", "statusModule") or {}
    value = status.get("resultsFirstPostDateStruct")
    return isinstance(value, dict) and str(value.get("type") or "").upper() == "ACTUAL"


def _has_results(study: dict[str, Any]) -> bool:
    explicit = study.get("hasResults")
    if isinstance(explicit, bool):
        return explicit
    return isinstance(study.get("resultsSection"), dict)


def normalise_clinicaltrials_result_events(
    rows: Iterable[dict[str, Any]],
    *,
    require_history_version: bool = True,
) -> list[dict[str, Any]]:
    """Normalize exact-version records into auditable event rows."""
    output: list[dict[str, Any]] = []
    for wrapper in rows:
        if not isinstance(wrapper, dict):
            continue
        study = _study(wrapper)
        sponsor = _lead_sponsor(study)
        ticker = SPONSOR_TO_TICKER.get(sponsor)
        nct_id = _nct_id(study)
        posted = _results_first_post_date(study)
        phases = _phases(study)
        version = (
            wrapper.get("history_version")
            or wrapper.get("studyVersion")
            or wrapper.get("version")
        )
        source_url = str(wrapper.get("source_url") or "").strip()
        sha = str(wrapper.get("raw_sha256") or _raw_sha(wrapper)).strip()
        if (
            not ticker
            or not nct_id
            or not posted
            or "PHASE3" not in phases
            or not _has_results(study)
            or not _results_first_post_is_actual(study)
        ):
            continue
        if require_history_version and (version in (None, "") or not source_url or not sha):
            continue
        output.append(
            {
                "nct_id": nct_id,
                "ticker": ticker,
                "lead_sponsor": sponsor,
                "phase": "PHASE3",
                "results_first_post_date": posted,
                "history_version": str(version) if version not in (None, "") else None,
                "source_url": source_url or None,
                "raw_sha256": sha,
                "source_rule_version": SOURCE_RULE_VERSION,
            }
        )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in output:
        unique[(row["nct_id"], row["results_first_post_date"])] = row
    return sorted(unique.values(), key=lambda row: (row["results_first_post_date"], row["ticker"], row["nct_id"]))


def _get_json(url: str, *, timeout: float = 30.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ginger-research/1.0 (ClinicalTrials.gov PIT archive)"},
    )
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed official hosts
                payload = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            last_error = exc
            if exc.code != 429 and exc.code < 500:
                raise
            retry_after = _float(exc.headers.get("Retry-After")) if exc.headers else None
            time.sleep(retry_after or min(30.0, 1.5 * (2**attempt) + random.random()))
        except URLError as exc:
            last_error = exc
            time.sleep(min(20.0, 1.0 * (2**attempt) + random.random()))
    else:
        raise last_error or RuntimeError(f"failed to fetch {url}")
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


def _version_number(row: Any) -> int | None:
    if isinstance(row, (int, str)):
        raw = row
    elif isinstance(row, dict):
        raw = row.get("studyVersion") or row.get("version") or row.get("versionNumber")
    else:
        return None
    text = str(raw or "").strip().lower().replace("version", "")
    try:
        return int(text)
    except ValueError:
        return None


def _history_versions(payload: dict[str, Any]) -> list[int]:
    candidates: list[Any] = []
    for key in ("changes", "versions", "studyVersions", "history"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    # The internal endpoint has changed wrappers before; a shallow recursive
    # fallback keeps the archived contract fail-closed without guessing fields.
    if not candidates:
        for value in payload.values():
            if isinstance(value, dict):
                for key in ("versions", "studyVersions"):
                    nested = value.get(key)
                    if isinstance(nested, list):
                        candidates.extend(nested)
    return sorted({number for item in candidates if (number := _version_number(item)) is not None})


def _public_result_version_candidates(payload: dict[str, Any]) -> list[int]:
    """Versions whose change metadata says result modules passed posting review."""
    output: list[int] = []
    for row in payload.get("changes") or []:
        if not isinstance(row, dict) or row.get("reviewNotPassed"):
            continue
        labels = {str(value) for value in row.get("moduleLabels") or []}
        if "Outcome Measures (Results)" not in labels:
            continue
        number = _version_number(row)
        if number is not None:
            output.append(number)
    return sorted(set(output))


def fetch_first_results_history_version(
    nct_id: str,
    *,
    expected_posted_date: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Fetch the earliest exact Record History version containing results.

    The endpoint can later UnRelease/Reset results, so the fallback scans
    versions in ascending order rather than assuming results presence is
    monotone. Every returned row retains the exact URL and payload hash.
    """
    nct = str(nct_id).strip().upper()
    history_url = f"{HISTORY_BASE}/{urllib.parse.quote(nct)}/history"
    history_payload = _get_json(history_url, timeout=timeout)
    versions = _history_versions(history_payload)
    if not versions:
        raise RuntimeError(f"no history versions returned for {nct}")
    # Prefer versions explicitly marked as posted result modules.  This also
    # handles a later UnRelease/Reset, where result presence is not monotone.
    public_candidates = _public_result_version_candidates(history_payload)
    for version in public_candidates[:1]:
        url = f"{HISTORY_BASE}/{urllib.parse.quote(nct)}/history/{version}"
        payload = _get_json(url, timeout=timeout)
        study = _study(payload)
        if not (_has_results(study) and _results_first_post_date(study) and _results_first_post_is_actual(study)):
            raise RuntimeError(f"first public result version is not ACTUAL/results-bearing for {nct}")
        posted = _results_first_post_date(study)
        if expected_posted_date and posted != _iso_date(expected_posted_date):
            raise RuntimeError(
                f"first-post mismatch for {nct}: history={posted} current={expected_posted_date}"
            )
        return {
            **payload,
            "history_version": version,
            "source_url": url,
            "raw_sha256": _raw_sha(payload),
        }

    first_payload: dict[str, Any] | None = None
    first_version: int | None = None
    first_url = ""
    for version in versions:
        url = f"{HISTORY_BASE}/{urllib.parse.quote(nct)}/history/{version}"
        payload = _get_json(url, timeout=timeout)
        study = _study(payload)
        if _has_results(study) and _results_first_post_date(study) and _results_first_post_is_actual(study):
            first_payload, first_version, first_url = payload, version, url
            break
    if first_payload is None or first_version is None:
        raise RuntimeError(f"no results-bearing history version for {nct}")
    posted = _results_first_post_date(_study(first_payload))
    if expected_posted_date and posted != _iso_date(expected_posted_date):
        raise RuntimeError(
            f"first-post mismatch for {nct}: history={posted} current={expected_posted_date}"
        )
    return {
        **first_payload,
        "history_version": first_version,
        "source_url": first_url,
        "raw_sha256": _raw_sha(first_payload),
    }


def _public_studies(start: str, end: str, *, timeout: float = 30.0) -> list[dict[str, Any]]:
    query = f"AREA[Phase]PHASE3 AND AREA[ResultsFirstPostDate]RANGE[{start}, {end}]"
    token: str | None = None
    studies: list[dict[str, Any]] = []
    while True:
        params = {"query.term": query, "format": "json", "pageSize": "100"}
        if token:
            params["pageToken"] = token
        url = f"{API_BASE}/studies?{urllib.parse.urlencode(params)}"
        payload = _get_json(url, timeout=timeout)
        studies.extend(row for row in payload.get("studies") or [] if isinstance(row, dict))
        token = str(payload.get("nextPageToken") or "").strip() or None
        if not token:
            return studies


def fetch_clinicaltrials_phase3_result_events(
    start: str,
    end: str,
    *,
    resolve_history: bool = True,
    timeout: float = 30.0,
    archive_payload_dir: Path | str | None = None,
    nct_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch the fixed sponsor universe and, by default, exact PIT versions."""
    current = _public_studies(_as_of_iso(start), _as_of_iso(end), timeout=timeout)
    selected: list[tuple[str, str]] = []
    for payload in current:
        study = _study(payload)
        # Retrieval prefilter matches the preregistered readiness population;
        # exact-version sponsor/phase below remains the eligibility authority.
        if _lead_sponsor(study) not in SPONSOR_TO_TICKER or "PHASE3" not in _phases(study):
            continue
        nct, posted = _nct_id(study), _results_first_post_date(study)
        if nct and posted:
            selected.append((nct, posted))
    if not resolve_history:
        return normalise_clinicaltrials_result_events(current, require_history_version=False)
    selected = sorted(set(selected))
    if nct_ids is not None:
        allowed = {str(value).strip().upper() for value in nct_ids}
        selected = [item for item in selected if item[0] in allowed]
    payload_dir = Path(archive_payload_dir) if archive_payload_dir is not None else None
    if payload_dir is not None:
        payload_dir.mkdir(parents=True, exist_ok=True)

    def fetch_one(item: tuple[str, str]) -> dict[str, Any]:
        nct, expected_posted = item
        if payload_dir is not None:
            for path in sorted(payload_dir.glob(f"{nct}_v*.json")):
                raw = path.read_bytes()
                payload = json.loads(raw.decode("utf-8"))
                study = _study(payload)
                if (
                    _results_first_post_date(study) == expected_posted
                    and _results_first_post_is_actual(study)
                    and _has_results(study)
                ):
                    version = payload.get("studyVersion") or path.stem.rsplit("_v", 1)[-1]
                    return {
                        **payload,
                        "history_version": version,
                        "source_url": f"{HISTORY_BASE}/{nct}/history/{version}",
                        "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    }
        wrapper = fetch_first_results_history_version(
            item[0], expected_posted_date=item[1], timeout=timeout
        )
        if payload_dir is not None:
            response_payload = {
                key: value
                for key, value in wrapper.items()
                if key not in {"history_version", "source_url", "raw_sha256"}
            }
            raw = _canonical_payload_bytes(response_payload)
            path = payload_dir / f"{nct}_v{wrapper['history_version']}.json"
            path.write_bytes(raw)
            wrapper["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        return wrapper

    with ThreadPoolExecutor(max_workers=min(3, max(1, len(selected)))) as pool:
        exact = list(pool.map(fetch_one, selected))
    if payload_dir is not None:
        for wrapper in exact:
            response_payload = {
                key: value
                for key, value in wrapper.items()
                if key not in {"history_version", "source_url", "raw_sha256"}
            }
            raw = _canonical_payload_bytes(response_payload)
            if hashlib.sha256(raw).hexdigest() != wrapper.get("raw_sha256"):
                raise RuntimeError("canonical ClinicalTrials payload hash mismatch")
            nct = _nct_id(_study(wrapper))
            version = wrapper.get("history_version")
            (payload_dir / f"{nct}_v{version}.json").write_bytes(raw)
    return normalise_clinicaltrials_result_events(exact, require_history_version=True)


def load_clinicaltrials_phase3_results_archive(path: Path | str) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    rows = payload.get("events") if isinstance(payload, dict) else payload
    return [dict(row) for row in (rows or []) if isinstance(row, dict)]


def save_clinicaltrials_phase3_results_archive(
    path: Path | str,
    events: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    file_path = Path(path)
    rows = sorted((dict(row) for row in events), key=lambda row: (row.get("results_first_post_date", ""), row.get("ticker", ""), row.get("nct_id", "")))
    payload = {
        "schema": "clinicaltrials_phase3_first_results_history_archive_v1",
        "rule_version": SOURCE_RULE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "event_count": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "events": rows,
    }
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def refresh_clinicaltrials_phase3_results_archive(
    path: Path | str,
    *,
    start: str,
    end: str,
    timeout: float = 30.0,
    archive_payload_dir: Path | str | None = None,
) -> dict[str, Any]:
    events = fetch_clinicaltrials_phase3_result_events(
        start,
        end,
        timeout=timeout,
        archive_payload_dir=archive_payload_dir,
    )
    return save_clinicaltrials_phase3_results_archive(path, events)


def _normalise_bars(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows or []:
        day = _iso_date(row.get("date") or row.get("Date"))
        close = _float(row.get("close") if "close" in row else row.get("Close"))
        open_ = _float(row.get("open") if "open" in row else row.get("Open"))
        high = _float(row.get("high") if "high" in row else row.get("High"))
        low = _float(row.get("low") if "low" in row else row.get("Low"))
        if day and close and close > 0:
            output.append({"date": day, "open": open_, "high": high, "low": low, "close": close})
    unique = {row["date"]: row for row in output}
    return [unique[key] for key in sorted(unique)]


def _atr_target(rows: list[dict[str, Any]], signal_idx: int, entry_price: float) -> float:
    true_ranges: list[float] = []
    for idx in range(max(0, signal_idx - 13), signal_idx + 1):
        row = rows[idx]
        high, low = row.get("high"), row.get("low")
        if high is None or low is None:
            continue
        previous = rows[idx - 1]["close"] if idx > 0 else row["close"]
        true_ranges.append(max(high - low, abs(high - previous), abs(low - previous)))
    atr = sum(true_ranges) / len(true_ranges) if true_ranges else entry_price * 0.02
    return round(entry_price + 3.5 * atr, 4)


def build_clinicaltrials_phase3_results_candidates(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply the one fixed price-confirmed, top-1/day, cooldown rule."""
    bars = {str(ticker).upper(): _normalise_bars(rows) for ticker, rows in ohlcv_by_ticker.items()}
    spy = bars.get("SPY") or []
    spy_dates = [row["date"] for row in spy]
    spy_pos = {day: idx for idx, day in enumerate(spy_dates)}
    ticker_pos = {ticker: {row["date"]: idx for idx, row in enumerate(rows)} for ticker, rows in bars.items()}
    rejects: Counter[str] = Counter()
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        posted = _iso_date(event.get("results_first_post_date"))
        if ticker not in SPONSOR_TO_TICKER.values() or not posted or not event.get("history_version"):
            rejects["invalid_or_unversioned_event"] += 1
            continue
        signal_date = next((day for day in spy_dates if day >= posted), None)
        if not signal_date or signal_date < start or signal_date > end:
            rejects["outside_signal_window"] += 1
            continue
        issuer_idx = ticker_pos.get(ticker, {}).get(signal_date)
        market_idx = spy_pos.get(signal_date)
        issuer = bars.get(ticker) or []
        if issuer_idx is None or market_idx is None or issuer_idx < 1 or market_idx < 1:
            rejects["missing_price_confirmation"] += 1
            continue
        issuer_return = issuer[issuer_idx]["close"] / issuer[issuer_idx - 1]["close"] - 1.0
        spy_return = spy[market_idx]["close"] / spy[market_idx - 1]["close"] - 1.0
        excess = issuer_return - spy_return
        if issuer_return <= 0:
            rejects["issuer_not_green"] += 1
            continue
        if excess <= 0:
            rejects["not_spy_relative_positive"] += 1
            continue
        key = (ticker, signal_date)
        row = {
            **dict(event),
            "signal_date": signal_date,
            "issuer_signal_return": round(issuer_return, 10),
            "spy_signal_return": round(spy_return, 10),
            "excess_signal_return": round(excess, 10),
            "score": round(excess, 10),
            "rule_version": RULE_VERSION,
            "trade_enabled": False,
            "alters_orders": False,
        }
        previous = deduped.get(key)
        if previous is None or str(row.get("nct_id")) < str(previous.get("nct_id")):
            deduped[key] = row
        else:
            rejects["duplicate_ticker_signal_date"] += 1

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in deduped.values():
        by_day[row["signal_date"]].append(row)
    selected: list[dict[str, Any]] = []
    next_allowed: dict[str, int] = {}
    for signal_date in sorted(by_day):
        day_rows = sorted(by_day[signal_date], key=lambda row: (-float(row["score"]), row["ticker"], row["nct_id"]))
        admitted = 0
        for row in day_rows:
            ticker = row["ticker"]
            position = spy_pos[signal_date]
            if position < next_allowed.get(ticker, -1):
                rejects["same_ticker_cooldown"] += 1
                continue
            if admitted >= DAILY_ENTRY_SLOTS:
                rejects["daily_top1_limit"] += 1
                continue
            selected.append(row)
            next_allowed[ticker] = position + SAME_TICKER_COOLDOWN_SESSIONS
            admitted += 1
    return selected, dict(sorted(rejects.items()))


def replay_clinicaltrials_phase3_results_paper_trades(
    *,
    events: Iterable[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    start: str,
    end: str,
) -> dict[str, Any]:
    event_rows = [dict(row) for row in events]
    bars = {str(ticker).upper(): _normalise_bars(rows) for ticker, rows in ohlcv_by_ticker.items()}
    selected, rejects = build_clinicaltrials_phase3_results_candidates(events=event_rows, ohlcv_by_ticker=bars, start=start, end=end)
    trades: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    for candidate in selected:
        ticker = candidate["ticker"]
        rows = bars.get(ticker) or []
        index = {row["date"]: idx for idx, row in enumerate(rows)}
        signal_idx = index.get(candidate["signal_date"])
        if signal_idx is None:
            unsettled.append({**candidate, "unsettled_reason": "missing_signal_bar"})
            continue
        entry_idx = signal_idx + 1
        exit_idx = entry_idx + HOLD_DAYS
        if entry_idx >= len(rows) or rows[entry_idx]["date"] > end:
            unsettled.append({**candidate, "unsettled_reason": "entry_outside_window"})
            continue
        scheduled_exit_idx = exit_idx
        exit_reason = "scheduled_10_session_horizon_close"
        if exit_idx >= len(rows) or rows[exit_idx]["date"] > end:
            inside = [idx for idx, row in enumerate(rows) if row["date"] <= end]
            if not inside or inside[-1] < entry_idx:
                unsettled.append({**candidate, "unsettled_reason": "no_window_end_liquidation_bar"})
                continue
            exit_idx = inside[-1]
            exit_reason = "window_end_liquidation"
        entry_price = rows[entry_idx].get("open")
        exit_price = rows[exit_idx].get("close")
        if not entry_price or not exit_price:
            unsettled.append({**candidate, "unsettled_reason": "missing_entry_or_exit_price"})
            continue
        net_return = exit_price / entry_price - 1.0 - ROUND_TRIP_COST_PCT
        trades.append(
            {
                **candidate,
                "entry_date": rows[entry_idx]["date"],
                "exit_date": rows[exit_idx]["date"],
                "entry_price": round(entry_price, 4),
                "exit_price": round(exit_price, 4),
                "target_price": _atr_target(rows, signal_idx, entry_price),
                "hold_days": HOLD_DAYS,
                "hold_sessions_realized": exit_idx - entry_idx,
                "scheduled_exit_date": (
                    rows[scheduled_exit_idx]["date"]
                    if scheduled_exit_idx < len(rows)
                    else None
                ),
                "exit_reason": exit_reason,
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
                "pnl_pct_net": round(net_return, 10),
                "pnl": round(BASE_NOTIONAL_USD * net_return, 2),
            }
        )
    generated = len(event_rows)
    return {
        "trades": trades,
        "unsettled": unsettled,
        "selected_candidates": selected,
        "reject_totals": rejects,
        "signals_generated": generated,
        "signals_survived": len(selected),
        "survival_rate": round(len(selected) / generated, 6) if generated else 0.0,
    }


def empty_clinicaltrials_phase3_results_paper_state() -> dict[str, Any]:
    return {"pending": [], "open": [], "closed": []}


def build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
    *,
    as_of_date: str,
    observations: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    as_of = _as_of_iso(as_of_date)
    rows = [dict(row) for row in observations]
    pending_confirmation = [
        row
        for row in rows
        if _iso_date(row.get("first_seen_date")) == as_of
        and _iso_date(row.get("results_first_post_date")) == as_of
        and row.get("history_version")
    ]
    return {
        "schema": "clinicaltrials_phase3_results_daily_snapshot_v1",
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "as_of_date": as_of,
        "status": "ok",
        "observation_count": len(rows),
        # These are source observations awaiting the same close/relative-price
        # confirmation used by build_clinicaltrials...candidates. They are not
        # mislabeled as admitted candidates before OHLCV is available.
        "candidate_count": 0,
        "pending_confirmation_count": len(pending_confirmation),
        "pending_count": len(pending_confirmation),
        "settled_count": 0,
        "seed_only_count": len(rows) - len(pending_confirmation),
        "source_observations": pending_confirmation,
        "candidates": [],
        "trade_enabled": False,
        "strategy_behavior_changed": False,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
    }


def prep_and_build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
    *,
    as_of_date: str,
    existing_observations: Iterable[dict[str, Any]],
    fetched_events: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    as_of = _as_of_iso(as_of_date)
    indexed = {str(row.get("nct_id")): dict(row) for row in existing_observations if row.get("nct_id")}
    for event in fetched_events:
        nct = str(event.get("nct_id") or "")
        if nct:
            first_seen = indexed.get(nct, {}).get("first_seen_date") or as_of
            indexed[nct] = {**indexed.get(nct, {}), **dict(event), "first_seen_date": first_seen}
    rows = sorted(indexed.values(), key=lambda row: (row.get("first_seen_date", ""), row.get("nct_id", "")))
    return build_clinicaltrials_phase3_results_paper_sleeve_snapshot(as_of_date=as_of, observations=rows), rows


def materialize_daily_snapshot(*, repo_root: Path | str, as_of_date: str) -> dict[str, Any]:
    """Fetch a narrow recent delta and persist a fail-closed forward snapshot."""
    root = Path(repo_root)
    as_of = _as_of_iso(as_of_date)
    base = root / "data" / "paper_sleeves" / "clinicaltrials_phase3_results"
    observations_path = base / "observations.json"
    existing = []
    if observations_path.exists():
        payload = json.loads(observations_path.read_text(encoding="utf-8"))
        existing = payload.get("observations") or []
    meta_path = base / "observation_meta.json"
    last_successful = None
    if meta_path.exists():
        last_successful = _iso_date(json.loads(meta_path.read_text(encoding="utf-8")).get("last_successful_observation_date"))
    recent_start = (
        (date.fromisoformat(last_successful) - timedelta(days=1)).isoformat()
        if last_successful
        else (date.fromisoformat(as_of) - timedelta(days=3)).isoformat()
    )
    # Exact history resolution is required even for forward source rows. Any
    # network/API failure propagates to run.py's explicit fail-soft wrapper.
    fetched = fetch_clinicaltrials_phase3_result_events(
        recent_start,
        as_of,
        resolve_history=True,
        timeout=15.0,
    )
    snapshot, observations = prep_and_build_clinicaltrials_phase3_results_paper_sleeve_snapshot(
        as_of_date=as_of,
        existing_observations=existing,
        fetched_events=fetched,
    )
    base.mkdir(parents=True, exist_ok=True)
    observations_path.write_text(
        json.dumps({"schema": "clinicaltrials_phase3_results_forward_observations_v1", "observations": observations}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps({"last_successful_observation_date": as_of}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    snapshot_path = base / f"snapshot_{as_of.replace('-', '')}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**snapshot, "snapshot_path": str(snapshot_path), "observations_path": str(observations_path)}
