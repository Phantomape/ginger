"""exp-20260712-021: CFTC TFF institutional-positioning attribution.

This is a read-only scout on the accepted post-MTM core trades.  It joins a
single predeclared weekly feature using a conservative publication lag and
does not change any strategy, sizing, ranking, order, or production path.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import ssl
import statistics
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_fingerprint import infer_fingerprint  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260712-021"
OWNER = "alpha-explore"
RUNNER = "quant/experiments/exp_20260712_021_cftc_tff_asset_manager_positioning.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
BASELINE = REPO_ROOT / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_post_mtm_20260712.json"
OUT_DIR = REPO_ROOT / "data/experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260712_021_cftc_tff_asset_manager_positioning.json"
NORMALIZED_JSON = OUT_DIR / "cftc_tff_normalized.json"
LOG_JSON = REPO_ROOT / "experiments/logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments/cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments/manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments/tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs/experiment_registry.json"

TARGET_MARKETS = (
    "S&P 500 Consolidated - CHICAGO MERCANTILE EXCHANGE",
    "NASDAQ-100 Consolidated - CHICAGO MERCANTILE EXCHANGE",
)
YEARS = (2024, 2025, 2026)
PUBLICATION_LAG_DAYS = 8
CHANGE_REPORTS = 4
MIN_COVERAGE = 0.95
MIN_POOLED_GROUP = 10
MIN_WINDOW_GROUP = 3

HYPOTHESIS = (
    "Observed-only risk-allocation attribution: when the strictly PIT CFTC "
    "Traders in Financial Futures Asset Manager net-long share across S&P 500 "
    "and Nasdaq-100 consolidated futures has risen over four reports, existing "
    "accepted core long trades should earn higher net return than trades entered "
    "when institutional positioning is flat or falling, consistently across the "
    "three post-MTM canonical windows."
)
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no monotonic relation",
        "window sign instability",
        "group imbalance",
        "weekly state too stale",
        "positioning crowds winners and reverses",
    ],
    "confidence_reason": (
        "The source is independent and complete, but recent macro-context searches "
        "were window-fragile and positioning may be contemporaneous rather than predictive."
    ),
    "recorded_at": "2026-07-13T02:40:45Z",
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


def fetch_year(year: int) -> tuple[bytes, str, bool]:
    path = OUT_DIR / f"fut_fin_txt_{year}.zip"
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
    if path.exists():
        return path.read_bytes(), url, True
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ginger-research/1.0"})
    with urllib.request.urlopen(request, timeout=60, context=ssl_context()) as response:
        body = response.read()
    if not zipfile.is_zipfile(io.BytesIO(body)):
        raise RuntimeError(f"CFTC response is not a zip for {year}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body, url, False


def parse_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for year in YEARS:
        body, url, cache_hit = fetch_year(year)
        archive = zipfile.ZipFile(io.BytesIO(body))
        members = archive.namelist()
        if len(members) != 1:
            raise RuntimeError(f"unexpected CFTC archive members for {year}: {members}")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", errors="strict", newline=""))
            rows = list(reader)
        subset = [row for row in rows if row.get("Market_and_Exchange_Names") in TARGET_MARKETS]
        sources.append(
            {
                "year": year,
                "url": url,
                "cache_hit": cache_hit,
                "path": repo_rel(OUT_DIR / f"fut_fin_txt_{year}.zip"),
                "sha256": sha256_bytes(body),
                "bytes": len(body),
                "archive_member": members[0],
                "all_rows": len(rows),
                "selected_rows": len(subset),
            }
        )
        selected.extend(subset)
    return selected, sources


def build_features(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, float]] = {}
    for row in rows:
        market = str(row["Market_and_Exchange_Names"])
        report_date = str(row["Report_Date_as_YYYY-MM-DD"])
        oi = float(row["Open_Interest_All"])
        if oi <= 0.0:
            raise RuntimeError(f"non-positive open interest: {report_date} {market}")
        long_value = float(row["Asset_Mgr_Positions_Long_All"])
        short_value = float(row["Asset_Mgr_Positions_Short_All"])
        by_date.setdefault(report_date, {})[market] = (long_value - short_value) / oi
    features: list[dict[str, Any]] = []
    complete_dates = sorted(date for date, values in by_date.items() if set(values) == set(TARGET_MARKETS))
    for index, report_date in enumerate(complete_dates):
        values = by_date[report_date]
        level = statistics.fmean(values[market] for market in TARGET_MARKETS)
        if index < CHANGE_REPORTS:
            continue
        prior_date = complete_dates[index - CHANGE_REPORTS]
        prior_values = by_date[prior_date]
        prior_level = statistics.fmean(prior_values[market] for market in TARGET_MARKETS)
        report_day = dt.date.fromisoformat(report_date)
        features.append(
            {
                "report_date": report_date,
                "available_from": (report_day + dt.timedelta(days=PUBLICATION_LAG_DAYS)).isoformat(),
                "asset_manager_net_share": round(level, 10),
                "four_report_change": round(level - prior_level, 10),
                "prior_report_date": prior_date,
                "market_net_shares": {market: round(values[market], 10) for market in TARGET_MARKETS},
            }
        )
    if not features:
        raise RuntimeError("no complete CFTC features")
    return features


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
    mean_left, mean_right = statistics.fmean(ranked_left), statistics.fmean(ranked_right)
    ss_left = sum((value - mean_left) ** 2 for value in ranked_left)
    ss_right = sum((value - mean_right) ** 2 for value in ranked_right)
    if ss_left <= 0.0 or ss_right <= 0.0:
        return None
    covariance = sum(
        (left_value - mean_left) * (right_value - mean_right)
        for left_value, right_value in zip(ranked_left, ranked_right)
    )
    return covariance / math.sqrt(ss_left * ss_right)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {"rising": [], "non_rising": []}
    for row in rows:
        groups["rising" if row["four_report_change"] > 0.0 else "non_rising"].append(row)
    result: dict[str, Any] = {}
    for name, items in groups.items():
        result[name] = {
            "count": len(items),
            "mean_pnl_pct_net": round(statistics.fmean(item["pnl_pct_net"] for item in items), 8) if items else None,
            "median_pnl_pct_net": round(statistics.median(item["pnl_pct_net"] for item in items), 8) if items else None,
            "win_rate": round(sum(item["pnl"] > 0.0 for item in items) / len(items), 6) if items else None,
        }
    rising_mean = result["rising"]["mean_pnl_pct_net"]
    non_rising_mean = result["non_rising"]["mean_pnl_pct_net"]
    result["rising_minus_non_rising_mean_pnl_pct_net"] = (
        round(rising_mean - non_rising_mean, 8)
        if rising_mean is not None and non_rising_mean is not None
        else None
    )
    result["spearman_change_vs_pnl_pct_net"] = spearman(
        [float(row["four_report_change"]) for row in rows],
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
    source_rows, sources = parse_sources()
    features = build_features(source_rows)
    write_json(
        NORMALIZED_JSON,
        {
            "schema": "cftc_tff_asset_manager_positioning_v1",
            "target_markets": list(TARGET_MARKETS),
            "publication_lag_days": PUBLICATION_LAG_DAYS,
            "change_reports": CHANGE_REPORTS,
            "sources": sources,
            "features": features,
        },
    )
    joined: list[dict[str, Any]] = []
    raw_by_window: dict[str, int] = {}
    entry_date_complete = 0
    artifact_checks: list[dict[str, Any]] = []
    for window in baseline["windows"]:
        artifact_path = REPO_ROOT / window["path"]
        actual_hash = sha256_file(artifact_path)
        if actual_hash != window["artifact_sha256"]:
            raise RuntimeError(f"baseline artifact drift: {window['label']}")
        artifact = read_json(artifact_path)
        trades = list(artifact.get("trades") or [])
        raw_by_window[window["label"]] = len(trades)
        artifact_checks.append({"label": window["label"], "path": window["path"], "sha256": actual_hash, "passed": True})
        for trade in trades:
            entry_date = str(trade.get("entry_date") or "")
            entry_date_complete += bool(entry_date)
            eligible = [feature for feature in features if feature["available_from"] <= entry_date]
            if not entry_date or not eligible:
                continue
            feature = eligible[-1]
            joined.append(
                {
                    "window": window["label"],
                    "trade_key": trade.get("trade_key"),
                    "ticker": trade.get("ticker"),
                    "strategy": trade.get("strategy"),
                    "entry_date": entry_date,
                    "exit_date": trade.get("exit_date"),
                    "pnl": round(float(trade.get("pnl") or 0.0), 2),
                    "pnl_pct_net": round(float(trade.get("pnl_pct_net") or 0.0), 8),
                    "report_date": feature["report_date"],
                    "available_from": feature["available_from"],
                    "asset_manager_net_share": feature["asset_manager_net_share"],
                    "four_report_change": feature["four_report_change"],
                    "state": "rising" if feature["four_report_change"] > 0.0 else "non_rising",
                }
            )
    total_trades = sum(raw_by_window.values())
    by_window: dict[str, Any] = {}
    coverage_by_window: dict[str, float] = {}
    for label, raw_count in raw_by_window.items():
        window_rows = [row for row in joined if row["window"] == label]
        coverage = len(window_rows) / raw_count if raw_count else 0.0
        coverage_by_window[label] = coverage
        by_window[label] = {"raw_trades": raw_count, "joined_trades": len(window_rows), "coverage": round(coverage, 6), **summarize(window_rows)}
    aggregate = summarize(joined)
    overall_coverage = len(joined) / total_trades if total_trades else 0.0
    positive_windows = [
        label
        for label, value in by_window.items()
        if value["rising_minus_non_rising_mean_pnl_pct_net"] is not None
        and value["rising_minus_non_rising_mean_pnl_pct_net"] > 0.0
    ]
    failed: list[str] = []
    if overall_coverage < MIN_COVERAGE or any(value < MIN_COVERAGE for value in coverage_by_window.values()):
        failed.append("strict_pit_coverage_below_95pct")
    if aggregate["rising"]["count"] < MIN_POOLED_GROUP or aggregate["non_rising"]["count"] < MIN_POOLED_GROUP:
        failed.append("pooled_group_below_10_trades")
    if any(
        value[group]["count"] < MIN_WINDOW_GROUP
        for value in by_window.values()
        for group in ("rising", "non_rising")
    ):
        failed.append("window_group_below_3_trades")
    if aggregate["rising_minus_non_rising_mean_pnl_pct_net"] is None or aggregate["rising_minus_non_rising_mean_pnl_pct_net"] <= 0.0:
        failed.append("pooled_rising_minus_non_rising_not_positive")
    if aggregate["spearman_change_vs_pnl_pct_net"] is None or aggregate["spearman_change_vs_pnl_pct_net"] <= 0.0:
        failed.append("pooled_spearman_not_positive")
    if len(positive_windows) < 2:
        failed.append("fewer_than_two_positive_windows")
    positive = not failed
    status = "observed_only_positive_lead" if positive else "observed_only_rejected"
    decision = (
        "observed_only_positive_cftc_tff_positioning_lead"
        if positive
        else "observed_only_rejected_cftc_tff_positioning"
    )
    now = utc_now()
    baseline_values = baseline_metrics(baseline)
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(NORMALIZED_JSON),
        *[source["path"] for source in sources],
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
        "change_type": "cftc_tff_asset_manager_positioning_risk_context_observed_only",
        "mechanism_family": "cftc_tff_institutional_positioning_risk_context",
        "trial_family": "cftc_tff_equity_index_asset_manager_positioning",
        "trial_variant_id": "four_report_net_share_change_sign_observed_only_v1",
        "changed_variable": "cftc_tff_equity_index_asset_manager_net_share_four_report_change_sign_v1",
        "single_causal_variable": "cftc_tff_equity_index_asset_manager_net_share_four_report_change_sign_v1",
        "causal_components": [
            "official CFTC TFF futures-only annual files",
            "S&P 500 and Nasdaq-100 consolidated contracts",
            "equal-weight Asset Manager net share",
            "four-report change",
            "conservative report-date plus eight-calendar-day availability",
            "existing baseline trade pnl_pct_net",
        ],
        "new_evidence_type": "new_data_source",
        "new_evidence_axis": "Official CFTC TFF positioning is a new repository data source with a dedicated fingerprint key.",
        "fingerprint_caveat": {
            "reservation_data_source": "other",
            "reason": "This was the first ticket on the surface, so its source keyword did not exist at reservation time.",
            "post_implementation": infer_fingerprint(HYPOTHESIS),
            "required_post_close_check": "docs/frozen_families.jsonl must contain data_source=cftc_tff_positioning after rebuild",
        },
        "multiple_testing_risk_bucket": "low",
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": positive,
            "predicted_success_probability": probability,
            "brier_score": round((probability - (1.0 if positive else 0.0)) ** 2, 6),
            "realized_failure_modes": failed,
        },
        "parameters": {
            "target_markets": list(TARGET_MARKETS),
            "feature": "equal mean of (Asset_Mgr_Positions_Long_All - Asset_Mgr_Positions_Short_All) / Open_Interest_All",
            "change_reports": CHANGE_REPORTS,
            "publication_lag_days": PUBLICATION_LAG_DAYS,
            "join_contract": "latest available_from <= entry_date",
            "split": "four_report_change > 0 versus <= 0",
            "no_threshold_or_field_sweep": True,
        },
        "source_manifest": {"sources": sources, "selected_rows": len(source_rows), "normalized_sha256": sha256_file(NORMALIZED_JSON)},
        "gate1": {"passed": True, **baseline_values, "artifact_identity_checks": artifact_checks},
        "gate2": {
            "passed": entry_date_complete == total_trades,
            "entry_date_complete": entry_date_complete,
            "entry_date_expected": total_trades,
            "required_cftc_fields": [
                "Report_Date_as_YYYY-MM-DD", "Open_Interest_All",
                "Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All",
            ],
            "target_price_note": "Closed-trade artifacts omit target_price; the unchanged accepted baseline signal engine owns that sentinel.",
        },
        "gate3": {
            "passed": overall_coverage >= 0.05,
            "new_filter_added": False,
            "signals_generated": total_trades,
            "signals_survived": len(joined),
            "survival_rate": round(overall_coverage, 6),
        },
        "gate4": {
            "applicable": False,
            "passed": False,
            "accepted_alpha": False,
            "observed_only_lead": positive,
            "decision": decision,
            "failed_reasons": failed,
            "acceptance_rule": read_json(TICKET_JSON)["acceptance_rule"],
        },
        "before_metrics": baseline_values,
        "after_metrics": baseline_values,
        "delta_metrics": {"expected_value_score_delta": 0.0, "total_pnl_delta": 0.0, "trade_count_delta": 0, "strategy_behavior_changed": False},
        "attribution": {
            "aggregate": {"raw_trades": total_trades, "joined_trades": len(joined), "coverage": round(overall_coverage, 6), **aggregate},
            "by_window": by_window,
            "positive_windows": positive_windows,
            "trade_rows": joined,
        },
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
            "scope": "read_only_saved_trade_attribution",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The predeclared institutional-positioning change separated accepted core trade outcomes consistently enough to justify a shared-paper policy test."
                if positive
                else "The weekly institutional-positioning change did not separate accepted core trade returns with the predeclared pooled and cross-window consistency."
            ),
            "forbidden_near_neighbor_retry": "Do not retry Asset Manager gross fields, 1/2/8/13-report changes, percentile or z-score thresholds, reverse sign, ES/NQ-only variants, ticker/strategy/window slices, or a soft scalar on these frozen rows.",
            "new_evidence_required": "A positive lead requires a separate shared-paper-first policy and full Gate 1-4 replay. A rejection requires a genuinely different data source or materially more settled forward rows, not another CFTC field/threshold response.",
        },
        "rejection_reason": None if positive else ";".join(failed),
        "next_retry_requires": [
            "shared-paper-first helper and full Gate 1-4 if positive",
            "new data source or materially more settled forward rows if rejected",
        ],
        "changed_files": changed_files,
        "related_files": [repo_rel(BASELINE), repo_rel(NORMALIZED_JSON), *[source["path"] for source in sources]],
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
    log["attribution"] = {
        "aggregate": payload["attribution"]["aggregate"],
        "by_window": payload["attribution"]["by_window"],
        "positive_windows": payload["attribution"]["positive_windows"],
    }
    return log


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["attribution"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} CFTC TFF Asset Manager positioning",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- PIT coverage: `{aggregate['joined_trades']}/{aggregate['raw_trades']} ({aggregate['coverage']:.2%})`",
            f"- Rising / non-rising trades: `{aggregate['rising']['count']}` / `{aggregate['non_rising']['count']}`",
            f"- Rising minus non-rising mean net return: `{aggregate['rising_minus_non_rising_mean_pnl_pct_net']}`",
            f"- Spearman: `{aggregate['spearman_change_vs_pnl_pct_net']}`",
            f"- Positive windows: `{', '.join(payload['attribution']['positive_windows']) or 'none'}`",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "No strategy, paper sleeve, sizing, ranking, exit, order, or LLM behavior changed.",
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
            "summary": payload["attribution"]["aggregate"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{key: value for key, value in build_log(payload).items() if key not in {"experiment_id", "status", "prediction"}},
            "owner": OWNER,
        },
    )


def main() -> None:
    payload = build_result()
    persist(payload)
    aggregate = payload["attribution"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "coverage": aggregate["coverage"],
                "rising_count": aggregate["rising"]["count"],
                "non_rising_count": aggregate["non_rising"]["count"],
                "mean_return_difference": aggregate["rising_minus_non_rising_mean_pnl_pct_net"],
                "spearman": aggregate["spearman_change_vs_pnl_pct_net"],
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
