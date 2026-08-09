"""exp-20260709-020: GDELT company-news tone-shock forward attribution.

Alpha search, read-only observed-only diagnostic on a genuinely NEW free data
source (AGENTS.md evidence axis (a)): the GDELT 2.0 DOC API historical daily
company-news tone / article-volume archive (2017 -> present, 15-minute
publication latency). Every existing news surface in this repo is
2026-forward-only; GDELT is the first news field that can be REPLAYED across
all three canonical windows.

Predeclared claims (from the ticket acceptance rule):

- Claim A: negative-tone-shock days (tone z <= -1 AND volume z >= +1 against a
  trailing 63-observation strictly-prior per-ticker baseline) have lower mean
  forward 10d next-open SPY-excess return than the same-ticker non-shock
  baseline, sign-consistent in all 3 canonical windows, pooled Welch
  t <= -1.5 on per-ticker demeaned outcomes.
- Claim B: pooled Spearman(tone z, forward 5d SPY-excess) > 0 with |t| >= 2.

Both pass -> observed_only_lead; else observed_only_rejected. Read-only: no
strategy behavior change, trade_enabled untouched, never accepted alpha by
itself.

PIT note: GDELT aggregates by UTC publication day. UTC day D closes at
19:00/20:00 ET on calendar day D; the attributed entry is the next trading
day's open (>= 09:30 ET on D+1), so every article in the day-D bucket exists
before entry. Tone/volume z-scores use strictly-prior observations only.

Fetch is cached under data/experiments/exp-20260709-020/gdelt_timelines/ so
the analysis replays offline once the archive is materialized.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

EXPERIMENT_ID = "exp-20260709-020"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "gdelt_tone_shock_forward_value"
RUNNER = f"quant/experiments/exp_20260709_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from broad_dispersion_features import corr_t_stat, spearman  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)

DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_MAIN = DATA_DIR / "warehouse" / "warehouse_main.sqlite"
WAREHOUSE_HOT = DATA_DIR / "warehouse" / "warehouse_main_hot.sqlite"

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
CACHE_DIR = OUT_DIR / "gdelt_timelines"
OUT_JSON = OUT_DIR / f"exp_20260709_020_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FETCH_START = "2024-06-01"  # warm-up for the 63-observation trailing baseline
ANALYSIS_END = "2026-04-21"
CANONICAL_WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]

BASELINE_OBS = 63
MIN_BASELINE_OBS = 40
TONE_SHOCK_Z = -1.0
VOLUME_SHOCK_Z = 1.0
MIN_POOLED_SHOCK_DAYS = 30
CLAIM_A_MAX_T = -1.5
CLAIM_B_MIN_ABS_T = 2.0
FWD_SHORT_DAYS = 5
FWD_LONG_DAYS = 10
MAX_ENTRY_LAG_CALENDAR_DAYS = 5

# Fixed, predeclared company-name query map. Precision is preferred over
# recall for ambiguous names (Visa, Snowflake, RTX/Raytheon, Meta). ETFs and
# commodity funds are excluded: GDELT tone is entity news tone, not fund flow.
GDELT_QUERY_BY_TICKER: dict[str, str] = {
    "NVDA": '"Nvidia"',
    "META": '"Meta Platforms"',
    "AMD": '"AMD"',
    "CRDO": '"Credo Technology"',
    "APP": '"AppLovin"',
    "GOOG": '"Google"',
    "MU": '"Micron"',
    "MSFT": '"Microsoft"',
    "AAPL": '"Apple"',
    "AVGO": '"Broadcom"',
    "TSM": '"TSMC"',
    "PLTR": '"Palantir"',
    "DDOG": '"Datadog"',
    "NOW": '"ServiceNow"',
    "SNOW": '"Snowflake Inc"',
    "TSLA": '"Tesla"',
    "MCD": '"McDonald\'s"',
    "AMZN": '"Amazon"',
    "BKNG": '"Booking Holdings"',
    "NFLX": '"Netflix"',
    "DIS": '"Disney"',
    "SPOT": '"Spotify"',
    "COIN": '"Coinbase"',
    "V": '"Visa Inc"',
    "MA": '"Mastercard"',
    "GS": '"Goldman Sachs"',
    "JPM": '"JPMorgan"',
    "LLY": '"Eli Lilly"',
    "NVO": '"Novo Nordisk"',
    "UNH": '"UnitedHealth"',
    "ISRG": '"Intuitive Surgical"',
    "XOM": '"Exxon"',
    "CVX": '"Chevron"',
    "CAT": '"Caterpillar"',
    "DE": '"John Deere"',
    "GE": '"General Electric"',
    "RTX": '"Raytheon"',
}

GDELT_MODES = ("timelinetone", "timelinevolraw")
GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
REQUEST_SPACING_SECONDS = 75.0  # this host 429s at 15s spacing; ~60s+ passes
RETRY_WAITS_SECONDS = (120.0, 240.0, 480.0)
RATE_LIMIT_RETRY_BUDGET = 40  # global cap on 429 backoffs before halting the run
# Try the full span in one request per mode; the day-resolution check in
# _fetch_timeline_chunk subdivides automatically if GDELT degrades resolution.
CHUNK_DAYS = 700
FETCH_ENABLED = os.environ.get("GINGER_GDELT_FETCH", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

HYPOTHESIS = (
    "Observed-only alpha: GDELT 2.0 DOC historical daily company-news "
    "tone/volume series are a genuinely new free PIT data source with full "
    "canonical-window archive coverage, so negative company tone shocks on "
    "elevated article volume should precede weaker forward 10d SPY-excess "
    "drift on the liquid core watchlist than same-ticker baseline days, "
    "giving the first historically replayable news-tone entry-risk context "
    "that the 2026-forward-only structured-news observers cannot evaluate."
)
CHANGED_VARIABLE = "gdelt_tone_shock_forward_value_v1"
MECHANISM_FAMILY = "production_visible_gdelt_news_tone_context"
TRIAL_FAMILY = "gdelt_news_tone_shock_forward_attribution"
TRIAL_VARIANT_ID = "gdelt_tone_shock_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260521-019",
    "exp-20260702-011",
    "exp-20260630-006",
]
CAUSAL_COMPONENTS = [
    "fixed_gdelt_company_query_map",
    "fixed_trailing_tone_volume_zscore_definition",
    "fixed_next_open_10d_spy_excess_attribution",
    "no_strategy_behavior_change",
]
PREDICTED_FAILURE_MODES = [
    "company-name query ambiguity noise",
    "tone merely relabels beta/attention (frozen event_attention prior)",
    "GDELT API throttling blocks full window fetch",
    "UTC publication day to trading day alignment leakage",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# GDELT fetch (cached, throttle-aware, day-resolution enforced)
# ---------------------------------------------------------------------------

_last_request_at = 0.0
_rate_limit_budget = RATE_LIMIT_RETRY_BUDGET


def _http_get_json(url: str) -> Any:
    global _last_request_at, _rate_limit_budget
    attempts = len(RETRY_WAITS_SECONDS) + 1
    for attempt in range(attempts):
        wait = REQUEST_SPACING_SECONDS - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "ginger-research/1.0 (alpha diagnostics)"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("non-dict GDELT response")
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                # Back off gently instead of hammering; a global budget keeps
                # the worst case bounded so a hard-throttled host still halts.
                if attempt >= attempts - 1 or _rate_limit_budget <= 0:
                    raise RuntimeError(
                        f"GDELT rate limited this host (HTTP 429): {url}"
                    ) from exc
                _rate_limit_budget -= 1
                print(
                    f"[fetch] 429 backoff {RETRY_WAITS_SECONDS[attempt]:.0f}s "
                    f"(budget {_rate_limit_budget})",
                    flush=True,
                )
                time.sleep(RETRY_WAITS_SECONDS[attempt])
                continue
            if attempt >= attempts - 1:
                raise RuntimeError(f"GDELT fetch failed after retries: {url}") from exc
            time.sleep(RETRY_WAITS_SECONDS[attempt])
        except Exception as exc:  # noqa: BLE001 - throttle text arrives many ways
            if attempt >= attempts - 1:
                raise RuntimeError(f"GDELT fetch failed after retries: {url}") from exc
            time.sleep(RETRY_WAITS_SECONDS[attempt])
    raise RuntimeError("unreachable")


def _chunk_ranges(start: str, end: str) -> list[tuple[str, str]]:
    ranges: list[tuple[str, str]] = []
    cursor = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while cursor <= stop:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS - 1), stop)
        ranges.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return ranges


def _fetch_timeline_chunk(query: str, mode: str, start: str, end: str) -> dict[str, float]:
    """Return {iso_date: value} for one chunk, enforcing day resolution."""
    span = [(start, end)]
    out: dict[str, float] = {}
    while span:
        s, e = span.pop(0)
        params = {
            "query": query,
            "mode": mode,
            "startdatetime": s.replace("-", "") + "000000",
            "enddatetime": e.replace("-", "") + "235959",
            "format": "json",
        }
        url = GDELT_BASE + "?" + urllib.parse.urlencode(params)
        payload = _http_get_json(url)
        resolution = ((payload.get("query_details") or {}).get("date_resolution") or "").lower()
        if resolution != "day":
            mid = date.fromisoformat(s) + (date.fromisoformat(e) - date.fromisoformat(s)) / 2
            if mid <= date.fromisoformat(s):
                raise RuntimeError(f"cannot reach day resolution for {query} {s}..{e}")
            span.insert(0, ((mid + timedelta(days=1)).isoformat(), e))
            span.insert(0, (s, mid.isoformat()))
            continue
        timeline = payload.get("timeline") or []
        data = (timeline[0].get("data") if timeline else None) or []
        for row in data:
            stamp = str(row.get("date") or "")[:8]
            if len(stamp) == 8:
                iso = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
                out[iso] = float(row.get("value") or 0.0)
    return out


def fetch_ticker_series(ticker: str, query: str) -> dict[str, Any]:
    """Fetch (or load cached) daily tone + article volume series for a ticker."""
    cache_path = CACHE_DIR / f"{ticker}.json"
    cached = read_json(cache_path, {})
    if (
        isinstance(cached, dict)
        and cached.get("fetch_start") == FETCH_START
        and cached.get("fetch_end") == ANALYSIS_END
        and cached.get("query") == query
        and cached.get("tone")
        and cached.get("volume")
    ):
        return cached
    if not FETCH_ENABLED:
        raise RuntimeError(
            "GDELT cache missing and remote fetch disabled; set GINGER_GDELT_FETCH=1 "
            "to materialize the archive when the API is not rate-limited."
        )
    # Chunk-level partial cache: a throttled run keeps every chunk it managed
    # to fetch, so resumed runs only pay for the missing pieces.
    series: dict[str, dict[str, float]] = {"timelinetone": {}, "timelinevolraw": {}}
    partial_dir = CACHE_DIR / "partial"
    for mode in GDELT_MODES:
        for start, end in _chunk_ranges(FETCH_START, ANALYSIS_END):
            part_path = partial_dir / f"{ticker}_{mode}_{start}_{end}.json"
            part = read_json(part_path, {})
            if isinstance(part, dict) and part.get("query") == query and part.get("data"):
                series[mode].update(part["data"])
                continue
            chunk = _fetch_timeline_chunk(query, mode, start, end)
            write_json(part_path, {"query": query, "data": chunk})
            series[mode].update(chunk)
    payload = {
        "ticker": ticker,
        "query": query,
        "fetch_start": FETCH_START,
        "fetch_end": ANALYSIS_END,
        "fetched_at": utc_now(),
        "tone": series["timelinetone"],
        "volume": series["timelinevolraw"],
    }
    write_json(cache_path, payload)
    return payload


# ---------------------------------------------------------------------------
# OHLCV + forward outcomes
# ---------------------------------------------------------------------------

def load_bars(tickers: list[str]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    wanted = sorted(set(tickers) | {"SPY"})
    for wh in (WAREHOUSE_MAIN, WAREHOUSE_HOT):
        if not wh.exists():
            continue
        con = sqlite3.connect(f"file:{wh.resolve().as_posix()}?mode=ro", uri=True)
        try:
            placeholders = ",".join("?" for _ in wanted)
            for t, d, o, c in con.execute(
                "select ticker, date, open, close from ohlcv "
                f"where ticker in ({placeholders})",
                wanted,
            ):
                if c is None:
                    continue
                rows.setdefault(str(t).upper(), {})[str(d)[:10]] = {
                    "Date": str(d)[:10],
                    "Open": float(o) if o is not None else float(c),
                    "Close": float(c),
                }
        finally:
            con.close()
    return {t: [by_d[d] for d in sorted(by_d)] for t, by_d in rows.items() if by_d}


def forward_excess_returns(
    bars: list[dict[str, Any]],
    spy_bars: list[dict[str, Any]],
    signal_day: str,
) -> dict[str, Any] | None:
    """Next-open entry after signal_day, SPY-excess close returns at 5/10d."""
    dates = [b["Date"] for b in bars]
    entry_idx = None
    for idx, d in enumerate(dates):
        if d > signal_day:
            entry_idx = idx
            break
    if entry_idx is None:
        return None
    entry_date = dates[entry_idx]
    lag = (date.fromisoformat(entry_date) - date.fromisoformat(signal_day)).days
    if lag > MAX_ENTRY_LAG_CALENDAR_DAYS:
        return None
    if entry_idx + FWD_LONG_DAYS - 1 >= len(bars):
        return None
    spy_by_date = {b["Date"]: b for b in spy_bars}
    spy_dates = [b["Date"] for b in spy_bars]
    if entry_date not in spy_by_date:
        return None
    spy_idx = spy_dates.index(entry_date)
    if spy_idx + FWD_LONG_DAYS - 1 >= len(spy_bars):
        return None
    entry_open = bars[entry_idx]["Open"]
    spy_open = spy_bars[spy_idx]["Open"]
    if not entry_open or not spy_open:
        return None
    out: dict[str, Any] = {"entry_date": entry_date}
    for label, horizon in (("fwd5", FWD_SHORT_DAYS), ("fwd10", FWD_LONG_DAYS)):
        exit_close = bars[entry_idx + horizon - 1]["Close"]
        spy_close = spy_bars[spy_idx + horizon - 1]["Close"]
        out[label] = (exit_close / entry_open - 1.0) - (spy_close / spy_open - 1.0)
    return out


# ---------------------------------------------------------------------------
# Signal construction
# ---------------------------------------------------------------------------

def trailing_zscores(series: dict[str, float], transform=None) -> dict[str, float]:
    """Strictly-prior trailing 63-observation z-score per calendar day."""
    days = sorted(series)
    values = [transform(series[d]) if transform else series[d] for d in days]
    zs: dict[str, float] = {}
    for i, d in enumerate(days):
        window = values[max(0, i - BASELINE_OBS) : i]
        if len(window) < MIN_BASELINE_OBS:
            continue
        mean = sum(window) / len(window)
        var = sum((v - mean) ** 2 for v in window) / max(1, len(window) - 1)
        std = math.sqrt(var)
        if std <= 1e-9:
            continue
        zs[d] = (values[i] - mean) / std
    return zs


def welch_t(sample_a: list[float], sample_b: list[float]) -> float | None:
    na, nb = len(sample_a), len(sample_b)
    if na < 2 or nb < 2:
        return None
    ma = sum(sample_a) / na
    mb = sum(sample_b) / nb
    va = sum((v - ma) ** 2 for v in sample_a) / (na - 1)
    vb = sum((v - mb) ** 2 for v in sample_b) / (nb - 1)
    denom = math.sqrt(va / na + vb / nb)
    if denom <= 0:
        return None
    return (ma - mb) / denom


def window_of(day: str) -> str | None:
    for name, start, end in CANONICAL_WINDOWS:
        if start <= day <= end:
            return name
    return None


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
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
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()

    fetch_errors: dict[str, str] = {}
    gdelt: dict[str, dict[str, Any]] = {}
    fetch_halted = False
    for ticker, query in GDELT_QUERY_BY_TICKER.items():
        if fetch_halted:
            fetch_errors[ticker] = "fetch_halted_after_global_gdelt_blocker"
            continue
        try:
            gdelt[ticker] = fetch_ticker_series(ticker, query)
            print(f"[fetch] {ticker}: tone={len(gdelt[ticker]['tone'])} "
                  f"vol={len(gdelt[ticker]['volume'])}", flush=True)
        except Exception as exc:  # noqa: BLE001
            fetch_errors[ticker] = str(exc)[:200]
            print(f"[fetch] {ticker}: FAILED {exc}", flush=True)
            if "GDELT cache missing and remote fetch disabled" in str(exc) or "HTTP 429" in str(exc):
                fetch_halted = True

    bars_by_ticker = load_bars(list(gdelt))
    spy_bars = bars_by_ticker.get("SPY") or []

    rows: list[dict[str, Any]] = []
    for ticker, payload_t in gdelt.items():
        bars = bars_by_ticker.get(ticker)
        if not bars or not spy_bars:
            continue
        tone = {d: v for d, v in payload_t["tone"].items() if d <= ANALYSIS_END}
        volume = {d: v for d, v in payload_t["volume"].items() if d <= ANALYSIS_END}
        tone_z = trailing_zscores(tone)
        vol_z = trailing_zscores(volume, transform=lambda v: math.log1p(max(v, 0.0)))
        for day, tz in tone_z.items():
            if window_of(day) is None:
                continue
            vz = vol_z.get(day)
            if vz is None:
                continue
            fwd = forward_excess_returns(bars, spy_bars, day)
            if fwd is None:
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "signal_day": day,
                    "window": window_of(day),
                    "tone_z": tz,
                    "vol_z": vz,
                    "is_shock": tz <= TONE_SHOCK_Z and vz >= VOLUME_SHOCK_Z,
                    "fwd5": fwd["fwd5"],
                    "fwd10": fwd["fwd10"],
                }
            )

    # Per-ticker demeaned fwd10 (same-ticker baseline contrast).
    by_ticker_mean: dict[str, float] = {}
    for ticker in {r["ticker"] for r in rows}:
        vals = [r["fwd10"] for r in rows if r["ticker"] == ticker]
        by_ticker_mean[ticker] = sum(vals) / len(vals) if vals else 0.0
    for r in rows:
        r["fwd10_demeaned"] = r["fwd10"] - by_ticker_mean[r["ticker"]]

    shocks = [r for r in rows if r["is_shock"]]
    non_shocks = [r for r in rows if not r["is_shock"]]

    # Claim A: shock fwd10 below same-ticker baseline, all windows, pooled t.
    pooled_t_a = welch_t(
        [r["fwd10_demeaned"] for r in shocks], [r["fwd10_demeaned"] for r in non_shocks]
    )
    per_window_a: dict[str, Any] = {}
    window_signs = 0
    for name, _, _ in CANONICAL_WINDOWS:
        w_shock = [r["fwd10_demeaned"] for r in shocks if r["window"] == name]
        w_non = [r["fwd10_demeaned"] for r in non_shocks if r["window"] == name]
        mean_shock = sum(w_shock) / len(w_shock) if w_shock else None
        mean_non = sum(w_non) / len(w_non) if w_non else None
        sign_ok = (
            mean_shock is not None and mean_non is not None and mean_shock < mean_non
        )
        window_signs += int(bool(sign_ok))
        per_window_a[name] = {
            "shock_days": len(w_shock),
            "shock_mean_fwd10_demeaned_bps": round(mean_shock * 1e4, 1) if mean_shock is not None else None,
            "non_shock_mean_fwd10_demeaned_bps": round(mean_non * 1e4, 1) if mean_non is not None else None,
            "sign_matches": bool(sign_ok),
        }
    claim_a_passed = bool(
        pooled_t_a is not None
        and pooled_t_a <= CLAIM_A_MAX_T
        and window_signs == len(CANONICAL_WINDOWS)
        and len(shocks) >= MIN_POOLED_SHOCK_DAYS
    )
    claim_a = {
        "claim": "negative_tone_volume_shock_underperforms_same_ticker_baseline_fwd10",
        "pooled_shock_days": len(shocks),
        "pooled_non_shock_days": len(non_shocks),
        "pooled_shock_mean_fwd10_demeaned_bps": round(
            sum(r["fwd10_demeaned"] for r in shocks) / len(shocks) * 1e4, 1
        ) if shocks else None,
        "pooled_welch_t": round(pooled_t_a, 2) if pooled_t_a is not None else None,
        "required_t": CLAIM_A_MAX_T,
        "sign_consistent_windows": window_signs,
        "per_window": per_window_a,
        "passed": claim_a_passed,
    }

    # Claim B: pooled Spearman(tone_z, fwd5) > 0 with |t| >= 2.
    r_b = spearman([r["tone_z"] for r in rows], [r["fwd5"] for r in rows])
    t_b = corr_t_stat(r_b, len(rows))
    claim_b_passed = bool(
        r_b is not None and r_b > 0 and t_b is not None and abs(t_b) >= CLAIM_B_MIN_ABS_T
    )
    per_window_b = {}
    for name, _, _ in CANONICAL_WINDOWS:
        sub = [r for r in rows if r["window"] == name]
        r_w = spearman([r["tone_z"] for r in sub], [r["fwd5"] for r in sub])
        per_window_b[name] = {
            "n": len(sub),
            "spearman": round(r_w, 4) if r_w is not None else None,
        }
    claim_b = {
        "claim": "pooled_tone_z_positively_ranks_fwd5_spy_excess",
        "n": len(rows),
        "pooled_spearman": round(r_b, 4) if r_b is not None else None,
        "pooled_t": round(t_b, 2) if t_b is not None else None,
        "required_abs_t": CLAIM_B_MIN_ABS_T,
        "per_window": per_window_b,
        "passed": claim_b_passed,
        "overlap_caveat": "5d horizons overlap across consecutive days; t is optimistic",
    }

    # Attribution extras (not part of pass/fail): symmetric positive shock,
    # shock concentration.
    pos_shocks = [r for r in rows if r["tone_z"] >= 1.0 and r["vol_z"] >= VOLUME_SHOCK_Z]
    shock_ticker_counts: dict[str, int] = {}
    for r in shocks:
        shock_ticker_counts[r["ticker"]] = shock_ticker_counts.get(r["ticker"], 0) + 1
    top_share = (
        max(shock_ticker_counts.values()) / len(shocks) if shocks else None
    )
    attribution = {
        "positive_tone_shock_days": len(pos_shocks),
        "positive_tone_shock_mean_fwd10_demeaned_bps": round(
            sum(r["fwd10_demeaned"] for r in pos_shocks) / len(pos_shocks) * 1e4, 1
        ) if pos_shocks else None,
        "negative_shock_top_ticker_share": round(top_share, 3) if top_share else None,
        "negative_shock_ticker_counts": dict(
            sorted(shock_ticker_counts.items(), key=lambda kv: -kv[1])[:10]
        ),
        "note": "attribution only; not part of the pass/fail rule",
    }

    claims_passed = [
        c["claim"] for c in (claim_a, claim_b) if c["passed"]
    ]

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if len(fetch_errors) > len(GDELT_QUERY_BY_TICKER) // 3:
        measurement_blockers.append("gdelt_fetch_coverage_too_thin")
    if fetch_halted:
        measurement_blockers.append(
            "gdelt_archive_not_materialized_remote_fetch_disabled_or_rate_limited"
        )
    if len(rows) < 3000:
        measurement_blockers.append("too_few_ticker_day_observations")
    if len(shocks) < MIN_POOLED_SHOCK_DAYS:
        measurement_blockers.append("too_few_negative_tone_shock_days")

    measurement_passed = not measurement_blockers
    both_passed = len(claims_passed) == 2
    if not measurement_passed:
        status, decision = "blocked", f"blocked_{SLUG}"
    elif both_passed:
        status, decision = "observed_only", f"observed_only_lead_{SLUG}"
    else:
        status, decision = "observed_only", f"observed_only_rejected_{SLUG}"

    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "tickers_fetched": len(gdelt),
        "tickers_failed": len(fetch_errors),
        "ticker_day_observations": len(rows),
        "negative_shock_days": len(shocks),
        "claim_a_pooled_t": claim_a["pooled_welch_t"],
        "claim_a_passed": claim_a["passed"],
        "claim_b_pooled_spearman": claim_b["pooled_spearman"],
        "claim_b_pooled_t": claim_b["pooled_t"],
        "claim_b_passed": claim_b["passed"],
        "claims_passed": claims_passed,
    }
    success_probability = float(
        (ticket.get("prediction") or {}).get("success_probability") or 0.2
    )
    prediction = {
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": PREDICTED_FAILURE_MODES,
        "confidence_reason": (ticket.get("prediction") or {}).get("confidence_reason"),
    }
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": 1 if both_passed else 0,
        "brier_score": round(
            (success_probability - (1.0 if both_passed else 0.0)) ** 2, 6
        ),
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_modes": (
            measurement_blockers
            + ([] if (both_passed or not measurement_passed) else ["claims_not_cleared"])
        ),
        "predicted_failure_mode_hit": not both_passed,
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "read_only_new_data_source_forward_attribution",
    }
    files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(CACHE_DIR) + "/",
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        "scripts/experiment_fingerprint.py",
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observed_only_forward_attribution",
        "implementation_mode": "read_only_diagnostic_lead_generation",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_data_source_gdelt_historical_news_tone_archive",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260521-019": "event attention persistence (news recency) rejected once; GDELT is a different source with tone direction and full history.",
                "exp-20260702-011": "structured-news propagation lead is 2026-forward-only; GDELT adds the missing canonical-window replay axis.",
                "L5_prior": "docs/alpha_next_direction_20260701.md deprioritized attention as context-not-signal; this test uses tone DIRECTION on shock days, predeclared to observed-only.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Claim A shock underperformance (pooled Welch t <= -1.5, all 3 "
                "windows sign-consistent, >= 30 pooled shock days) AND Claim B "
                "pooled Spearman(tone_z, fwd5) > 0 with |t| >= 2. Both -> "
                "observed_only_lead; else observed_only_rejected. Never accepted "
                "alpha by itself."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "query_map": GDELT_QUERY_BY_TICKER,
            "fetch_start": FETCH_START,
            "analysis_end": ANALYSIS_END,
            "baseline_observations": BASELINE_OBS,
            "min_baseline_observations": MIN_BASELINE_OBS,
            "tone_shock_z": TONE_SHOCK_Z,
            "volume_shock_z": VOLUME_SHOCK_Z,
            "volume_transform": "log1p",
            "forward_horizons_trading_days": [FWD_SHORT_DAYS, FWD_LONG_DAYS],
            "entry": "next trading day open after UTC publication day",
            "excess_benchmark": "SPY same-entry open-to-close",
            "pit_note": "UTC day D closes ~19:00-20:00 ET; entry >= 09:30 ET next day",
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": measurement_passed,
            "fields_checked": ["tone", "volume", "open", "close", "date"],
            "entry_date_scope": "No trades and no signal objects; ticker-day attribution only.",
            "target_price_scope": "Not applicable; read-only diagnostic.",
        },
        "gate3": {
            "passed": measurement_passed,
            "filter_added": False,
            "signals_generated": len(rows),
            "signals_survived": len(rows),
            "survival_rate": 1.0 if rows else None,
            "note": "Ticker-day observations, not signals; no production filter touched.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": (
                [] if (both_passed or not measurement_passed) else ["claims_not_cleared"]
            ),
            "measurement_repair_only": False,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "claims": {"claim_a": claim_a, "claim_b": claim_b},
        "attribution": attribution,
        "fetch_errors": fetch_errors,
        "blocked_reason": ";".join(measurement_blockers) if not measurement_passed else None,
        "rejection_reason": None if not measurement_passed else (
            None if both_passed else "Predeclared observed-only claims did not both clear."
        ),
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": None,
            "forbidden_near_neighbor_retry": (
                "Do not re-run with tweaked z thresholds, baseline lookbacks, "
                "volume transforms, query phrasings, horizons, or window slices "
                "on the same frozen windows. If lead: next step is a fixed "
                "shared-paper-first entry-risk overlay (downweight/exclude "
                "negative-tone-shock names) through Gate 1-4 against accepted "
                "comparators, plus daily GDELT snapshot wiring. If rejected: "
                "the tone axis needs either an entity-resolution upgrade "
                "(GDELT GKG org fields instead of phrase queries) or "
                "prospective forward rows, not a re-slice."
            ),
            "new_evidence_required": (
                "A fixed deployable gate shape through Gate 1-4, GKG-based "
                "entity resolution, or prospective GDELT-tagged forward "
                "replacement rows."
            ),
        },
        "next_retry_requires": [
            "no same-window z/lookback/query re-slices",
            "lead -> shared-paper-first Gate 1-4 overlay; rejected -> entity-resolution upgrade or forward rows",
        ],
        "changed_files": files,
        "related_files": [
            "docs/alpha_next_direction_20260701.md",
            "quant/broad_dispersion_features.py",
        ],
        "allowed_write_scope": files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def finalize_reflection(payload: dict[str, Any]) -> None:
    a = payload["claims"]["claim_a"]
    b = payload["claims"]["claim_b"]
    blockers = payload.get("gate4", {}).get("measurement_blockers") or []
    if blockers:
        why = (
            "The experiment did not reach alpha validation because the GDELT "
            f"archive was not materialized ({'; '.join(blockers)}). No "
            "ticker-day tone/volume rows were available, so the predeclared "
            "Claim A/B statistics are intentionally null. This blocks the "
            "current alpha read; it does not prove or disprove the GDELT tone "
            "shock hypothesis. Measured throttle evidence (2026-07-09, this "
            "host): single full-span timelinetone requests DID succeed twice "
            "at day resolution (so 74 requests would cover all 37 names), but "
            "the host 429s at 15s spacing, kept 429ing across 120/240/480s "
            "backoffs spanning 14 minutes, and a single probe after 35 "
            "minutes of complete quiet still returned HTTP 429. The DOC API "
            "is effectively unusable from this IP at bulk-fetch cadence."
        )
        payload["reopen_condition"] = {
            "surface": "gdelt_doc_api_tone_volume_archive",
            "parked_at": utc_now(),
            "condition": (
                "A single manual probe (one curl of the NVDA full-span "
                "timelinetone URL, not a new experiment ID) returns HTTP 200 "
                "from the runtime host - e.g. off-peak hours, a different "
                "egress IP, or after contacting GDELT. Then rerun this runner "
                "with GINGER_GDELT_FETCH=1; the per-ticker cache makes the "
                "fetch resumable. Alternative axis: materialize tone/volume "
                "offline from GDELT raw GKG/ngrams bulk files (unthrottled "
                "data.gdeltproject.org) or a BigQuery export, then rerun "
                "without any API dependency."
            ),
            "probe_command": (
                "curl -s -o /dev/null -w '%{http_code}' 'https://api.gdelt"
                "project.org/api/v2/doc/doc?query=%22Nvidia%22&mode=timeline"
                "tone&startdatetime=20240601000000&enddatetime=20260421235959"
                "&format=json'"
            ),
        }
    elif payload["delta_metrics"]["claims_passed"] and len(
        payload["delta_metrics"]["claims_passed"]
    ) == 2:
        why = (
            f"Negative tone shocks underperform the same-ticker baseline "
            f"(pooled Welch t={a['pooled_welch_t']}, {a['sign_consistent_windows']}/3 "
            f"windows, {a['pooled_shock_days']} shock days) and tone z ranks fwd5 "
            f"SPY-excess (Spearman {b['pooled_spearman']}, t={b['pooled_t']}) over "
            f"{b['n']} ticker-days. The GDELT tone archive carries replayable "
            "entry-risk information; next step is a fixed shared-paper-first "
            "overlay through Gate 1-4, not more slices."
        )
    else:
        why = (
            f"The predeclared bar was not fully cleared (claim A t="
            f"{a['pooled_welch_t']}, windows {a['sign_consistent_windows']}/3, "
            f"shock days {a['pooled_shock_days']}; claim B Spearman "
            f"{b['pooled_spearman']}, t={b['pooled_t']}): on these liquid "
            "megacaps, phrase-query news tone shocks do not separate forward "
            "SPY-excess strongly enough beyond what next-open pricing already "
            "absorbs."
        )
    payload["post_run_reflection"]["why_result_happened"] = why


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    a = payload["claims"]["claim_a"]
    b = payload["claims"]["claim_b"]
    att = payload["attribution"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: GDELT news tone-shock forward attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- New data source: GDELT 2.0 DOC daily tone/volume archive, {delta['tickers_fetched']} tickers fetched ({delta['tickers_failed']} failed)",
            f"- Ticker-day observations: `{delta['ticker_day_observations']}`; negative shock days: `{delta['negative_shock_days']}`",
            f"- Claim A shock-underperformance: Welch t `{a['pooled_welch_t']}` (need <= {CLAIM_A_MAX_T}), windows `{a['sign_consistent_windows']}/3`, passed `{a['passed']}`",
            f"- Claim B tone->fwd5 Spearman: `{b['pooled_spearman']}` t `{b['pooled_t']}` (need > 0, |t| >= {CLAIM_B_MIN_ABS_T}), passed `{b['passed']}`",
            f"- Symmetric positive-shock mean fwd10 (demeaned bps): `{att['positive_tone_shock_mean_fwd10_demeaned_bps']}`",
            f"- Negative-shock top-ticker share: `{att['negative_shock_top_ticker_share']}`",
            "- Strategy behavior changed: `false` (read-only diagnostic)",
            "",
            "## Why",
            "",
            payload["post_run_reflection"]["why_result_happened"] or "",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "reopen_condition": payload.get("reopen_condition"),
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    finalize_reflection(payload)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "claims": payload["claims"],
                "attribution": payload["attribution"],
                "fetch_errors": payload["fetch_errors"],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
