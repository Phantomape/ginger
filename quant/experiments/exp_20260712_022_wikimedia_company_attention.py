"""exp-20260712-022: Wikimedia issuer-page attention attribution.

Read-only scout on accepted post-MTM common-stock trades.  The source is
frozen and hashed, but historical API load timestamps are unavailable, so a
three-calendar-day lag is used and even a positive result is only a lead.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import ssl
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_fingerprint import infer_fingerprint  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260712-022"
OWNER = "alpha-explore"
RUNNER = "quant/experiments/exp_20260712_022_wikimedia_company_attention.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
BASELINE = REPO_ROOT / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
OUT_DIR = REPO_ROOT / "data/experiments" / EXPERIMENT_ID
RAW_DIR = OUT_DIR / "raw_pageviews"
OUT_JSON = OUT_DIR / "exp_20260712_022_wikimedia_company_attention.json"
NORMALIZED_JSON = OUT_DIR / "wikimedia_attention_features.json"
SOURCE_MANIFEST_JSON = OUT_DIR / "source_manifest.json"
METADATA_JSON = OUT_DIR / "mediawiki_page_metadata.json"
LOG_JSON = REPO_ROOT / "experiments/logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments/cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments/manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments/tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs/experiment_registry.json"

START_DAY = dt.date(2024, 8, 1)
END_DAY = dt.date(2026, 4, 21)
EXPECTED_DAYS = 629
AVAILABILITY_LAG_DAYS = 3
SAME_WEEKDAY_OBSERVATIONS = 8
ETF_OR_TRUST_TICKERS = {"GLD", "IAU", "IWM", "SLV", "SPY", "QQQ", "TQQQ"}

# Exact current canonical issuer pages established before outcome inspection.
# Page IDs are stable identity checks; titles are the only Pageviews API key.
PAGES: dict[str, dict[str, Any]] = {
    "AAPL": {"title": "Apple Inc.", "pageid": 856},
    "AMD": {"title": "AMD", "pageid": 2400},
    "AMZN": {"title": "Amazon (company)", "pageid": 90451},
    "APP": {"title": "AppLovin", "pageid": 51759510},
    "BKNG": {"title": "Booking Holdings", "pageid": 44829655},
    "CAT": {"title": "Caterpillar Inc.", "pageid": 668125},
    "COIN": {"title": "Coinbase", "pageid": 39596725},
    "CVX": {"title": "Chevron Corporation", "pageid": 284749},
    "DDOG": {"title": "Datadog", "pageid": 40075229},
    "DIS": {"title": "The Walt Disney Company", "pageid": 37398},
    "GOOG": {"title": "Alphabet Inc.", "pageid": 47489893},
    "GS": {"title": "Goldman Sachs", "pageid": 335244},
    "ISRG": {"title": "Intuitive Surgical", "pageid": 3828482},
    "JPM": {"title": "JPMorgan Chase", "pageid": 231001},
    "LLY": {"title": "Eli Lilly and Company", "pageid": 758905},
    "MCD": {"title": "McDonald's", "pageid": 2480627},
    "META": {"title": "Meta Platforms", "pageid": 62420226},
    "MU": {"title": "Micron Technology", "pageid": 487445},
    "NFLX": {"title": "Netflix", "pageid": 175537},
    "NOW": {"title": "ServiceNow", "pageid": 31830044},
    "PLTR": {"title": "Palantir", "pageid": 27197818},
    "SNOW": {"title": "Snowflake Inc.", "pageid": 47443042},
    "SPOT": {"title": "Spotify", "pageid": 20148343},
    "TSM": {"title": "TSMC", "pageid": 463574},
    "V": {"title": "Visa Inc.", "pageid": 246920},
    "XOM": {"title": "ExxonMobil", "pageid": 18848197},
}

HYPOTHESIS = (
    "Observed-only ticker-level attention attribution: among the 26 common-stock "
    "issuers appearing in the accepted post-MTM core trades, a strictly lagged "
    "Wikimedia Analytics API canonical-company-page attention surprise should "
    "identify stronger information persistence; trades with positive log pageview "
    "surprise should earn higher pnl_pct_net than non-positive surprise trades, "
    "and the continuous surprise should be positively monotonic across all three "
    "canonical windows."
)
PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "attention is contemporaneous not predictive",
        "negative news drives pageviews",
        "window sign instability",
        "page title history breaks canonical series",
        "API availability is not historically auditable",
        "small selected trade sample",
    ],
    "confidence_reason": (
        "The source is independent with complete preflight coverage, but pageviews "
        "are direction agnostic and historical API load timestamps are absent."
    ),
    "recorded_at": "2026-07-13T03:42:08Z",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_json(url: str, cache_path: Path, *, throttle: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    if cache_path.exists():
        body = cache_path.read_bytes()
        return json.loads(body.decode("utf-8")), {
            "url": url,
            "path": repo_rel(cache_path),
            "sha256": sha256_bytes(body),
            "bytes": len(body),
            "cache_hit": True,
        }
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ginger-alpha-research/1.0 (Codex local experiment)"},
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60, context=ssl_context()) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(body)
    if throttle:
        time.sleep(1.0)
    return json.loads(body.decode("utf-8")), {
        "url": url,
        "path": repo_rel(cache_path),
        "sha256": sha256_bytes(body),
        "bytes": len(body),
        "cache_hit": False,
    }


def load_page_metadata() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    parameters = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "prop": "info|pageprops",
            "titles": "|".join(page["title"] for page in PAGES.values()),
        }
    )
    url = "https://en.wikipedia.org/w/api.php?" + parameters
    payload, source = fetch_json(url, METADATA_JSON)
    query = payload.get("query") or {}
    if query.get("redirects") or query.get("normalized"):
        raise RuntimeError("predeclared titles are not current canonical titles")
    actual_by_id = {int(page.get("pageid", -1)): page for page in query.get("pages", [])}
    result: dict[str, dict[str, Any]] = {}
    for ticker, expected in PAGES.items():
        page = actual_by_id.get(int(expected["pageid"]))
        if not page or page.get("missing"):
            raise RuntimeError(f"missing canonical page for {ticker}")
        if page.get("title") != expected["title"]:
            raise RuntimeError(f"canonical title drift for {ticker}: {page.get('title')}")
        pageprops = page.get("pageprops") or {}
        if "disambiguation" in pageprops or not pageprops.get("wikibase_item"):
            raise RuntimeError(f"ambiguous or entity-unbound page for {ticker}")
        result[ticker] = {
            "title": page["title"],
            "pageid": int(page["pageid"]),
            "wikidata_qid": pageprops["wikibase_item"],
        }
    if len(result) != 26:
        raise RuntimeError(f"expected 26 canonical pages, got {len(result)}")
    return result, source


def load_pageviews(metadata: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[dt.date, int]], list[dict[str, Any]]]:
    series: dict[str, dict[dt.date, int]] = {}
    sources: list[dict[str, Any]] = []
    for ticker in sorted(metadata):
        title = metadata[ticker]["title"]
        article = urllib.parse.quote(title.replace(" ", "_"), safe="")
        url = (
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia.org/all-access/user/{article}/daily/"
            f"{START_DAY:%Y%m%d}/{END_DAY:%Y%m%d}"
        )
        payload, source = fetch_json(url, RAW_DIR / f"{ticker}.json", throttle=True)
        rows: dict[dt.date, int] = {}
        for item in payload.get("items") or []:
            day = dt.datetime.strptime(str(item["timestamp"])[:8], "%Y%m%d").date()
            rows[day] = int(item["views"])
        expected_dates = {START_DAY + dt.timedelta(days=offset) for offset in range(EXPECTED_DAYS)}
        if set(rows) != expected_dates:
            missing = sorted(expected_dates - set(rows))
            raise RuntimeError(f"incomplete pageview series for {ticker}: {len(rows)} rows, missing {missing[:5]}")
        if any(value < 0 for value in rows.values()):
            raise RuntimeError(f"negative pageviews for {ticker}")
        series[ticker] = rows
        sources.append(
            {
                **source,
                "ticker": ticker,
                "title": title,
                "pageid": metadata[ticker]["pageid"],
                "wikidata_qid": metadata[ticker]["wikidata_qid"],
                "rows": len(rows),
                "first_date": min(rows).isoformat(),
                "last_date": max(rows).isoformat(),
            }
        )
    return series, sources


def build_features(series: dict[str, dict[dt.date, int]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in series.items():
        histories: dict[int, list[float]] = {weekday: [] for weekday in range(7)}
        ticker_rows: list[dict[str, Any]] = []
        for day in sorted(rows):
            log_views = math.log1p(rows[day])
            history = histories[day.weekday()][-SAME_WEEKDAY_OBSERVATIONS:]
            if len(history) == SAME_WEEKDAY_OBSERVATIONS:
                ticker_rows.append(
                    {
                        "view_date": day.isoformat(),
                        "available_from": (day + dt.timedelta(days=AVAILABILITY_LAG_DAYS)).isoformat(),
                        "views": rows[day],
                        "log_views": round(log_views, 10),
                        "prior8_same_weekday_log_median": round(statistics.median(history), 10),
                        "attention_surprise": round(log_views - statistics.median(history), 10),
                    }
                )
            histories[day.weekday()].append(log_views)
        result[ticker] = ticker_rows
    return result


def rank_average(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = rank
        cursor = end
    return ranks


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    ranked_left, ranked_right = rank_average(left), rank_average(right)
    left_mean, right_mean = statistics.fmean(ranked_left), statistics.fmean(ranked_right)
    left_ss = sum((value - left_mean) ** 2 for value in ranked_left)
    right_ss = sum((value - right_mean) ** 2 for value in ranked_right)
    if left_ss <= 0.0 or right_ss <= 0.0:
        return None
    covariance = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(ranked_left, ranked_right)
    )
    return covariance / math.sqrt(left_ss * right_ss)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        "positive": [row for row in rows if row["attention_surprise"] > 0.0],
        "non_positive": [row for row in rows if row["attention_surprise"] <= 0.0],
    }
    result: dict[str, Any] = {}
    for name, items in groups.items():
        result[name] = {
            "count": len(items),
            "mean_pnl_pct_net": round(statistics.fmean(item["pnl_pct_net"] for item in items), 8) if items else None,
            "median_pnl_pct_net": round(statistics.median(item["pnl_pct_net"] for item in items), 8) if items else None,
            "win_rate": round(sum(item["pnl"] > 0.0 for item in items) / len(items), 6) if items else None,
        }
    positive_mean = result["positive"]["mean_pnl_pct_net"]
    non_positive_mean = result["non_positive"]["mean_pnl_pct_net"]
    result["positive_minus_non_positive_mean_pnl_pct_net"] = (
        round(positive_mean - non_positive_mean, 8)
        if positive_mean is not None and non_positive_mean is not None
        else None
    )
    result["spearman_surprise_vs_pnl_pct_net"] = spearman(
        [float(row["attention_surprise"]) for row in rows],
        [float(row["pnl_pct_net"]) for row in rows],
    )
    return result


def baseline_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary_path": repo_rel(BASELINE),
        "summary_sha256": sha256_file(BASELINE),
        "aggregate": summary["aggregate"],
        "windows": [
            {
                key: window.get(key)
                for key in (
                    "label", "start", "end", "expected_value_score", "total_pnl",
                    "trade_count", "signals_generated", "signals_survived", "survival_rate",
                    "max_drawdown_pct", "trade_rows_sha256",
                )
            }
            for window in summary["windows"]
        ],
    }


def build_result() -> dict[str, Any]:
    baseline = read_json(BASELINE)
    metadata, metadata_source = load_page_metadata()
    series, page_sources = load_pageviews(metadata)
    features = build_features(series)
    write_json(
        NORMALIZED_JSON,
        {
            "schema": "wikimedia_company_attention_features_v1",
            "project": "en.wikipedia.org",
            "access": "all-access",
            "agent": "user",
            "start": START_DAY.isoformat(),
            "end": END_DAY.isoformat(),
            "availability_lag_days": AVAILABILITY_LAG_DAYS,
            "same_weekday_observations": SAME_WEEKDAY_OBSERVATIONS,
            "metadata": metadata,
            "features": features,
        },
    )
    source_manifest = {
        "schema": "wikimedia_company_attention_source_manifest_v1",
        "metadata_source": metadata_source,
        "page_sources": page_sources,
        "page_count": len(page_sources),
        "all_pages_complete": all(source["rows"] == EXPECTED_DAYS for source in page_sources),
        "historical_availability_limit": (
            "The API documents normal next-period loading but exposes no historical per-day load timestamps. "
            "The three-day lag is conservative, not audit-grade proof."
        ),
        "title_history_limit": (
            "Current canonical pageid/title/QID are frozen. The per-title Pageviews API does not provide a "
            "page-move-adjusted historical series; aliases and brand pages are intentionally not aggregated."
        ),
    }
    write_json(SOURCE_MANIFEST_JSON, source_manifest)

    joined: list[dict[str, Any]] = []
    raw_common_by_window: dict[str, int] = {}
    entry_date_complete = 0
    artifact_checks: list[dict[str, Any]] = []
    for window in baseline["windows"]:
        artifact_path = REPO_ROOT / window["path"]
        actual_hash = sha256_file(artifact_path)
        if actual_hash != window["artifact_sha256"]:
            raise RuntimeError(f"baseline artifact drift: {window['label']}")
        artifact = read_json(artifact_path)
        trades = [trade for trade in artifact.get("trades") or [] if trade.get("ticker") not in ETF_OR_TRUST_TICKERS]
        raw_common_by_window[window["label"]] = len(trades)
        artifact_checks.append({"label": window["label"], "path": window["path"], "sha256": actual_hash, "passed": True})
        for trade in trades:
            ticker = str(trade.get("ticker") or "")
            entry_date = str(trade.get("entry_date") or "")
            entry_date_complete += bool(entry_date)
            eligible = [row for row in features.get(ticker, []) if row["available_from"] <= entry_date]
            if not entry_date or not eligible:
                continue
            feature = eligible[-1]
            joined.append(
                {
                    "window": window["label"],
                    "trade_key": trade.get("trade_key"),
                    "ticker": ticker,
                    "strategy": trade.get("strategy"),
                    "entry_date": entry_date,
                    "exit_date": trade.get("exit_date"),
                    "pnl": round(float(trade.get("pnl") or 0.0), 2),
                    "pnl_pct_net": round(float(trade.get("pnl_pct_net") or 0.0), 8),
                    "page_title": metadata[ticker]["title"],
                    "pageid": metadata[ticker]["pageid"],
                    "wikidata_qid": metadata[ticker]["wikidata_qid"],
                    **feature,
                    "attention_state": "positive" if feature["attention_surprise"] > 0.0 else "non_positive",
                }
            )

    total_common = sum(raw_common_by_window.values())
    by_window: dict[str, Any] = {}
    for label, raw_count in raw_common_by_window.items():
        rows = [row for row in joined if row["window"] == label]
        by_window[label] = {
            "eligible_common_stock_trades": raw_count,
            "joined_trades": len(rows),
            "coverage": round(len(rows) / raw_count, 6) if raw_count else 0.0,
            **summarize(rows),
        }
    aggregate = summarize(joined)
    positive_windows = [
        label
        for label, value in by_window.items()
        if value["positive_minus_non_positive_mean_pnl_pct_net"] is not None
        and value["positive_minus_non_positive_mean_pnl_pct_net"] > 0.0
    ]
    failed: list[str] = []
    if len(metadata) != 26 or any(len(rows) != EXPECTED_DAYS for rows in series.values()):
        failed.append("canonical_page_or_daily_coverage_incomplete")
    if total_common != 50 or len(joined) != 50 or any(value["coverage"] != 1.0 for value in by_window.values()):
        failed.append("eligible_trade_join_not_50_of_50")
    if aggregate["positive"]["count"] < 10 or aggregate["non_positive"]["count"] < 10:
        failed.append("pooled_group_below_10_trades")
    if any(
        value[group]["count"] < 3
        for value in by_window.values()
        for group in ("positive", "non_positive")
    ):
        failed.append("window_group_below_3_trades")
    if aggregate["positive_minus_non_positive_mean_pnl_pct_net"] is None or aggregate["positive_minus_non_positive_mean_pnl_pct_net"] <= 0.0:
        failed.append("pooled_positive_minus_non_positive_not_positive")
    if aggregate["spearman_surprise_vs_pnl_pct_net"] is None or aggregate["spearman_surprise_vs_pnl_pct_net"] <= 0.0:
        failed.append("pooled_spearman_not_positive")
    if len(positive_windows) < 2:
        failed.append("fewer_than_two_positive_windows")
    positive = not failed
    status = "observed_only_positive_lead_not_promoted" if positive else "observed_only_rejected"
    decision = (
        "observed_only_positive_wikimedia_attention_lead_not_promoted"
        if positive
        else "observed_only_rejected_wikimedia_attention"
    )
    now = utc_now()
    baseline_values = baseline_metrics(baseline)
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(NORMALIZED_JSON),
        repo_rel(SOURCE_MANIFEST_JSON),
        repo_rel(METADATA_JSON),
        *[source["path"] for source in page_sources],
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        "scripts/experiment_fingerprint.py",
        "quant/test_experiment_fingerprint.py",
        "docs/experiment_registry.json",
        "docs/frozen_families.jsonl",
    ]
    probability = float(PREDICTION["success_probability"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": positive,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "wikimedia_pageviews_company_attention_surprise_observed_only",
        "mechanism_family": "wikimedia_company_attention_information_persistence",
        "trial_family": "wikimedia_pageviews_canonical_issuer_attention_surprise",
        "trial_variant_id": "prior8_same_weekday_log_surprise_sign_observed_only_v1",
        "changed_variable": "wikimedia_company_page_log_surprise_prior8_same_weekday_three_day_lag_sign_v1",
        "single_causal_variable": "wikimedia_company_page_log_surprise_prior8_same_weekday_three_day_lag_sign_v1",
        "causal_components": [
            "26 fixed common-stock issuer pages", "enwiki all-access user pageviews",
            "log1p daily views", "median prior eight same-weekday observations",
            "three-calendar-day conservative availability lag", "positive versus non-positive sign",
            "continuous Spearman", "accepted baseline trade pnl_pct_net",
        ],
        "new_evidence_type": "new_data_source",
        "new_evidence_axis": "Wikimedia human-user issuer-page attention is a new repository source with a dedicated fingerprint key.",
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": positive,
            "predicted_success_probability": probability,
            "brier_score": round((probability - (1.0 if positive else 0.0)) ** 2, 6),
            "realized_failure_modes": failed,
        },
        "fingerprint_caveat": {
            "reservation_data_source": "revision_expectation",
            "misclassification_reason": "The generic word surprise matched revision_expectation before the first-build source key existed.",
            "real_data_source": "wikimedia_pageviews",
            "post_implementation": infer_fingerprint(HYPOTHESIS),
            "required_post_close_check": "docs/frozen_families.jsonl must classify this family as wikimedia_pageviews after rebuild",
        },
        "parameters": {
            "pages": metadata,
            "excluded_ticker_types": sorted(ETF_OR_TRUST_TICKERS),
            "project": "en.wikipedia.org",
            "access": "all-access",
            "agent": "user",
            "availability_lag_days": AVAILABILITY_LAG_DAYS,
            "same_weekday_observations": SAME_WEEKDAY_OBSERVATIONS,
            "formula": "log1p(current views) - median(log1p(previous 8 same-weekday views))",
            "split": "attention_surprise > 0 versus <= 0",
            "no_alias_threshold_field_lag_or_response_sweep": True,
        },
        "source_manifest": {**source_manifest, "path": repo_rel(SOURCE_MANIFEST_JSON), "sha256": sha256_file(SOURCE_MANIFEST_JSON)},
        "gate1": {"passed": True, **baseline_values, "artifact_identity_checks": artifact_checks},
        "gate2": {
            "passed": entry_date_complete == total_common,
            "entry_date_complete": entry_date_complete,
            "entry_date_expected": total_common,
            "page_identity_fields": ["title", "pageid", "wikidata_qid"],
            "target_price_note": "Closed-trade artifacts omit target_price; the unchanged accepted signal engine owns that sentinel.",
        },
        "gate3": {
            "passed": len(joined) / total_common >= 0.05 if total_common else False,
            "new_filter_added": False,
            "signals_generated": total_common,
            "signals_survived": len(joined),
            "survival_rate": round(len(joined) / total_common, 6) if total_common else 0.0,
        },
        "gate4": {
            "applicable": False,
            "passed": False,
            "accepted_alpha": False,
            "observed_only_lead": positive,
            "decision": decision,
            "failed_reasons": failed,
            "acceptance_rule": read_json(TICKET_JSON)["acceptance_rule"],
            "promotion_boundary": "A positive scout requires timestamped daily snapshots and new settled forward rows before a policy test.",
        },
        "before_metrics": baseline_values,
        "after_metrics": baseline_values,
        "delta_metrics": {"expected_value_score_delta": 0.0, "total_pnl_delta": 0.0, "trade_count_delta": 0, "strategy_behavior_changed": False},
        "attribution": {
            "aggregate": {"eligible_common_stock_trades": total_common, "joined_trades": len(joined), "coverage": round(len(joined) / total_common, 6), **aggregate},
            "by_window": by_window,
            "positive_windows": positive_windows,
            "trade_rows": joined,
        },
        "production_impact": {
            "shared_policy_changed": False, "backtester_adapter_changed": False,
            "run_adapter_changed": False, "entry_rules_changed": False,
            "ranking_changed": False, "sizing_changed": False, "exit_rules_changed": False,
            "orders_changed": False, "trade_enabled": False,
            "scope": "read_only_saved_trade_attribution",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The fixed issuer-page attention surprise separated accepted common-stock trade returns consistently enough to justify forward timestamping."
                if positive
                else "Reader attention was direction agnostic or contemporaneous and did not separate accepted trade returns with stable pooled and cross-window direction."
            ),
            "forbidden_near_neighbor_retry": "Do not retry 1/2/4-day lags, other weekday spans, mean or z-score baselines, thresholds or quantiles, all-agents, redirect/brand/product aggregation, ticker/strategy/window slices, reverse sign, soft scalar, or full replay on these frozen rows.",
            "new_evidence_required": "Only a pre-entry daily snapshot with fetch_at/hash/last_complete_day and at least +50% and 10 new settled forward rows, or a genuinely new data source/gate shape, can reopen this surface.",
        },
        "rejection_reason": None if positive else ";".join(failed),
        "next_retry_requires": [
            "timestamped daily snapshots and materially more settled forward rows if positive",
            "new data source or gate shape if rejected",
        ],
        "changed_files": changed_files,
        "related_files": [repo_rel(BASELINE), repo_rel(SOURCE_MANIFEST_JSON), repo_rel(NORMALIZED_JSON)],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    log = {key: value for key, value in payload.items() if key != "attribution"}
    if "attribution" in payload:
        log["attribution"] = {
            "aggregate": payload["attribution"]["aggregate"],
            "by_window": payload["attribution"]["by_window"],
            "positive_windows": payload["attribution"]["positive_windows"],
        }
    return log


def build_card(payload: dict[str, Any]) -> str:
    if payload["status"] == "blocked":
        return "\n".join(
            [
                f"# {EXPERIMENT_ID} Wikimedia company-page attention",
                "",
                "- Status: `blocked`",
                f"- Decision: `{payload['decision']}`",
                f"- Blocker: `{payload['blocking_condition']}`",
                "",
                "No external request ran and no alpha result was inferred from preflight output.",
                "",
                "## Reopen",
                "",
                payload["post_run_reflection"]["new_evidence_required"],
            ]
        ) + "\n"
    aggregate = payload["attribution"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Wikimedia company-page attention",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Page coverage: `26/26 x {EXPECTED_DAYS} days`",
            f"- Trade coverage: `{aggregate['joined_trades']}/{aggregate['eligible_common_stock_trades']}`",
            f"- Positive / non-positive trades: `{aggregate['positive']['count']}` / `{aggregate['non_positive']['count']}`",
            f"- Mean net-return difference: `{aggregate['positive_minus_non_positive_mean_pnl_pct_net']}`",
            f"- Spearman: `{aggregate['spearman_surprise_vs_pnl_pct_net']}`",
            f"- Positive windows: `{', '.join(payload['attribution']['positive_windows']) or 'none'}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "No strategy, sizing, ranking, order, exit, paper sleeve, or LLM behavior changed.",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    CARD_MD.write_text(build_card(payload), encoding="utf-8")
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": repo_rel(OUT_JSON),
            "source_manifest": repo_rel(SOURCE_MANIFEST_JSON),
            "normalized_source": repo_rel(NORMALIZED_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
            "files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
        },
    )
    ticket = read_json(TICKET_JSON)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": (payload.get("attribution") or {}).get("aggregate", {}),
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{key: value for key, value in build_log(payload).items() if key not in {"experiment_id", "status", "prediction"}},
            "owner": OWNER,
        },
    )


def build_blocked_result() -> dict[str, Any]:
    baseline = read_json(BASELINE)
    now = utc_now()
    blocking_condition = (
        "The official Wikimedia freeze command was rejected before process start because "
        "the automatic escalation-review model was at capacity; no external request or data write occurred."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "blocked",
        "decision": "blocked_external_wikimedia_freeze_approval_service_capacity",
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "wikimedia_pageviews_company_attention_surprise_observed_only",
        "mechanism_family": "wikimedia_company_attention_information_persistence",
        "trial_family": "wikimedia_pageviews_canonical_issuer_attention_surprise",
        "trial_variant_id": "prior8_same_weekday_log_surprise_sign_observed_only_v1",
        "changed_variable": "wikimedia_company_page_log_surprise_prior8_same_weekday_three_day_lag_sign_v1",
        "single_causal_variable": "wikimedia_company_page_log_surprise_prior8_same_weekday_three_day_lag_sign_v1",
        "new_evidence_type": "new_data_source",
        "new_evidence_axis": "Wikimedia human-user issuer-page attention is a new repository source with a dedicated fingerprint key.",
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": False,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": None,
            "realized_failure_modes": ["external_approval_service_capacity"],
            "not_scored_reason": "The hypothesis was not evaluated.",
        },
        "blocking_condition": blocking_condition,
        "fingerprint_caveat": {
            "reservation_data_source": "revision_expectation",
            "misclassification_reason": "The generic word surprise matched revision_expectation before the first-build source key existed.",
            "real_data_source": "wikimedia_pageviews",
            "post_implementation": infer_fingerprint(HYPOTHESIS),
            "required_post_close_check": "docs/frozen_families.jsonl must classify this family as wikimedia_pageviews after rebuild",
        },
        "gate1": {"passed": True, **baseline_metrics(baseline)},
        "gate2": {"applicable": False, "passed": False, "reason": blocking_condition},
        "gate3": {"applicable": False, "passed": False, "new_filter_added": False},
        "gate4": {
            "applicable": False,
            "passed": False,
            "accepted_alpha": False,
            "observed_only_lead": False,
            "decision": "not_run",
            "failed_reasons": ["external_source_not_frozen"],
        },
        "before_metrics": baseline_metrics(baseline),
        "after_metrics": {},
        "delta_metrics": {},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "no external execution; blocked before source freeze",
        },
        "post_run_reflection": {
            "why_result_happened": "The experiment was not run; approval infrastructure capacity blocked the official source freeze.",
            "forbidden_near_neighbor_retry": "Do not treat preflight coverage as an alpha result, change the feature, or reserve another ID for the same source while this exact ticket can be reopened.",
            "new_evidence_required": "Reopen this ticket only after explicit approval allows the existing runner to freeze the 26 official Wikimedia series; then execute the unchanged policy bundle and acceptance rule.",
        },
        "rejection_reason": None,
        "next_retry_requires": ["explicit approval for the existing official Wikimedia source-freeze command"],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "scripts/experiment_fingerprint.py",
            "quant/test_experiment_fingerprint.py",
            "docs/experiment_registry.json",
            "docs/frozen_families.jsonl",
        ],
        "related_files": [repo_rel(BASELINE)],
        "reproduction_commands": [
            RUNNER_COMMAND,
            RUNNER_COMMAND + " --close-blocked",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }


def main() -> None:
    if "--close-blocked" in sys.argv:
        payload = build_blocked_result()
        persist(payload)
        print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": "blocked", "decision": payload["decision"]}, indent=2))
        return
    payload = build_result()
    persist(payload)
    aggregate = payload["attribution"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "page_count": 26,
                "page_days": EXPECTED_DAYS,
                "trade_coverage": aggregate["coverage"],
                "positive_count": aggregate["positive"]["count"],
                "non_positive_count": aggregate["non_positive"]["count"],
                "mean_return_difference": aggregate["positive_minus_non_positive_mean_pnl_pct_net"],
                "spearman": aggregate["spearman_surprise_vs_pnl_pct_net"],
                "positive_windows": payload["attribution"]["positive_windows"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
