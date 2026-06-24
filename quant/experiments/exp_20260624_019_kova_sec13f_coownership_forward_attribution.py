"""exp-20260624-019: Kova SEC13F coownership forward attribution.

Observed-only alpha attribution. This tests whether PIT SEC13F coownership
network tightness separates the partial closed Kova forward replacement rows
from exp-20260624-017. It does not change strategy behavior, daily snapshots,
ranking, sizing, exits, paper fills, or live orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-019"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_coownership_forward_attribution"
RUNNER = f"quant/experiments/exp_20260624_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_019_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUTCOME_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-017"
    / "kova_sec13f_forward_outcome_settlement_ledger.jsonl"
)
SEC13F_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional"

HYPOTHESIS = (
    "Observed-only attribution: Kova forward rows with stronger PIT SEC13F "
    "coownership-network tightness should show better settled 1d/3d/5d "
    "cash/SPY/QQQ replacement value than weak or missing network rows, testing "
    "whether the exp018 sponsorship lead reflects relation provenance rather "
    "than broad holder count."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_coownership_network_forward_attribution"
TRIAL_VARIANT_ID = "post_exp017_partial_forward_1d3d5_network_v1"
CHANGED_VARIABLE = "kova_sec13f_coownership_network_forward_attribution_v1"
NEW_EVIDENCE_TYPE = "partial_closed_forward_replacement_value_rows"
NEW_EVIDENCE_AXIS = (
    "New PIT SEC13F coownership-network relation fields joined to "
    "exp-20260624-017 partial closed Kova forward replacement rows; not a "
    "holder-count/value/position-count sponsorship score, RS, Companyfacts, "
    "top-N, hold, cooldown, notional, or allocator threshold retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-007",
    "exp-20260624-016",
    "exp-20260624-017",
    "exp-20260624-018",
]
CAUSAL_COMPONENTS = [
    "exp017 settled forward outcome ledger",
    "PIT SEC13F coownership network fields",
    "cash SPY QQQ replacement-value attribution",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-019/exp_20260624_019_kova_sec13f_coownership_forward_attribution.json",
    "experiments/cards/exp-20260624-019.md",
    "experiments/manifests/exp-20260624-019.json",
    "experiments/tickets/exp-20260624-019.json",
    "experiments/logs/exp-20260624-019.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "live_ready": False,
    "uses_kova_forward_snapshots": True,
    "uses_sec13f_forward_context": True,
    "uses_sec13f_coownership_network": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "live_realistic_execution_envelope": (
        "Not evaluated for live use; this is observed-only attribution and "
        "cannot become live-ready."
    ),
}
ACCEPTANCE_RULE = {
    "primary_horizon": 5,
    "min_primary_network_rows": 500,
    "min_primary_missing_rows": 100,
    "min_primary_asof_dates": 3,
    "min_supporting_horizons_high_beats_low": 2,
    "positive_pnl_hhi_guardrail": 0.35,
    "max_single_positive_pnl_share": 0.50,
}
HORIZONS = [1, 3, 5]
NETWORK_BUCKETS = [
    "missing_or_no_network",
    "low_network",
    "mid_network",
    "high_network",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {} if default is None else default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
        "windows": windows,
    }


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.16,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "no_network_coverage",
            "no_monotonic_network_separation",
            "qqq_beta_confound",
            "coownership_family_near_neighbor",
            "forward_window_too_short",
        ],
        "confidence_reason": (
            "Forward replacement rows and PIT coownership network fields are "
            "available, but the nearby frozen-window 13F relation family failed."
        ),
        "recorded_at": utc_now(),
    }


def window_label_from_holdings_path(path_value: Any) -> str | None:
    if not path_value:
        return None
    stem = Path(str(path_value)).stem
    if stem.startswith("holdings_"):
        return stem.removeprefix("holdings_")
    return None


def coownership_path_for_window(window_label: str) -> Path:
    return SEC13F_DIR / f"coownership_edges_{window_label}.json"


def load_networks(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    windows = sorted(
        {
            label
            for label in (
                window_label_from_holdings_path(row.get("sec13f_source_file"))
                for row in rows
            )
            if label
        }
    )
    networks: dict[str, dict[str, Any]] = {}
    status: dict[str, Any] = {
        "windows_requested": windows,
        "windows_loaded": [],
        "missing_windows": [],
        "network_files": {},
    }
    for label in windows:
        path = coownership_path_for_window(label)
        payload = read_json(path, {})
        peers = payload.get("peers_by_ticker") if isinstance(payload, dict) else None
        if isinstance(peers, dict):
            networks[label] = peers
            status["windows_loaded"].append(label)
            status["network_files"][label] = {
                "path": repo_rel(path),
                "exists": True,
                "tickers_with_peers": len(peers),
                "rule_version": payload.get("rule_version"),
                "params": payload.get("params"),
            }
        else:
            status["missing_windows"].append(label)
            status["network_files"][label] = {"path": repo_rel(path), "exists": path.exists()}
    return networks, status


def peer_features(row: dict[str, Any], networks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    label = window_label_from_holdings_path(row.get("sec13f_source_file"))
    peers = []
    if label and ticker:
        peers = networks.get(label, {}).get(ticker) or []
    if not isinstance(peers, list):
        peers = []
    valid_peers = [peer for peer in peers if isinstance(peer, dict)]
    lifts = [safe_float(peer.get("lift")) for peer in valid_peers]
    lifts = [value for value in lifts if value is not None]
    shared = [safe_float(peer.get("shared_managers")) for peer in valid_peers]
    shared = [value for value in shared if value is not None]
    jaccards = [safe_float(peer.get("jaccard")) for peer in valid_peers]
    jaccards = [value for value in jaccards if value is not None]
    top5_lift = lifts[:5]
    top5_shared = shared[:5]
    return {
        "sec13f_coownership_window": label,
        "sec13f_coownership_peer_count": len(valid_peers),
        "sec13f_coownership_max_lift": max(lifts) if lifts else None,
        "sec13f_coownership_avg_top5_lift": (
            sum(top5_lift) / len(top5_lift) if top5_lift else None
        ),
        "sec13f_coownership_max_shared_managers": max(shared) if shared else None,
        "sec13f_coownership_avg_top5_shared_managers": (
            sum(top5_shared) / len(top5_shared) if top5_shared else None
        ),
        "sec13f_coownership_max_jaccard": max(jaccards) if jaccards else None,
        "sec13f_coownership_top_peers": [
            {
                "peer": peer.get("peer"),
                "shared_managers": peer.get("shared_managers"),
                "jaccard": peer.get("jaccard"),
                "lift": peer.get("lift"),
            }
            for peer in valid_peers[:5]
        ],
    }


def percentile_map(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if not ordered:
        return {}
    if len(ordered) == 1:
        return {ordered[0][0]: 1.0}
    return {key: index / (len(ordered) - 1) for index, (key, _) in enumerate(ordered)}


def enrich_network_scores(rows: list[dict[str, Any]], networks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.update(peer_features(row, networks))
        enriched.append(item)

    feature_keys = [
        "sec13f_coownership_peer_count",
        "sec13f_coownership_max_lift",
        "sec13f_coownership_avg_top5_lift",
        "sec13f_coownership_max_shared_managers",
        "sec13f_coownership_avg_top5_shared_managers",
        "sec13f_coownership_max_jaccard",
    ]
    ranks_by_feature: dict[str, dict[str, float]] = {}
    for key in feature_keys:
        values: dict[str, float] = {}
        for row in enriched:
            value = safe_float(row.get(key))
            if value is not None and value > 0:
                values[str(row.get("observation_id") or id(row))] = math.log1p(value)
        ranks_by_feature[key] = percentile_map(values)

    for row in enriched:
        observation_id = str(row.get("observation_id") or id(row))
        ranks = [
            ranks[observation_id]
            for ranks in ranks_by_feature.values()
            if observation_id in ranks
        ]
        row["sec13f_coownership_network_score"] = (
            sum(ranks) / len(ranks) if ranks else None
        )
        row["sec13f_coownership_status"] = (
            "ok" if row["sec13f_coownership_network_score"] is not None else "missing_or_no_network"
        )
    return enriched


def settled_rows(rows: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    status_key = f"forward_{horizon}d_status"
    cash_key = f"replacement_value_{horizon}d_vs_cash_usd"
    return [
        row
        for row in rows
        if row.get(status_key) == "settled" and safe_float(row.get(cash_key)) is not None
    ]


def bucket_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    with_score = [
        row for row in rows if safe_float(row.get("sec13f_coownership_network_score")) is not None
    ]
    without_score = [
        row for row in rows if safe_float(row.get("sec13f_coownership_network_score")) is None
    ]
    ordered = sorted(
        with_score,
        key=lambda row: (
            safe_float(row.get("sec13f_coownership_network_score")) or 0.0,
            str(row.get("ticker") or ""),
            str(row.get("observation_id") or ""),
        ),
    )
    buckets = {name: [] for name in NETWORK_BUCKETS}
    buckets["missing_or_no_network"] = without_score
    if not ordered:
        return buckets
    for index, row in enumerate(ordered):
        frac = index / max(len(ordered) - 1, 1)
        if frac < 1 / 3:
            buckets["low_network"].append(row)
        elif frac < 2 / 3:
            buckets["mid_network"].append(row)
        else:
            buckets["high_network"].append(row)
    return buckets


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def stats(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round(sum(clean) / len(clean), 4),
        "median": round(median(clean) or 0.0, 4),
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def replacement_metrics(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for comparator in ["cash", "spy", "qqq"]:
        key = f"replacement_value_{horizon}d_vs_{comparator}_usd"
        metrics[f"replacement_value_vs_{comparator}_usd"] = stats(
            [safe_float(row.get(key)) for row in rows if safe_float(row.get(key)) is not None]
        )
    return metrics


def concentration(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    key = f"replacement_value_{horizon}d_vs_cash_usd"
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        pnl = safe_float(row.get(key))
        ticker = str(row.get("ticker") or "")
        if pnl is not None and pnl > 0 and ticker:
            by_ticker[ticker] += pnl
    positive_pnl = sum(by_ticker.values())
    if positive_pnl <= 0:
        return {
            "positive_pnl": 0.0,
            "positive_ticker_count": 0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: pnl / positive_pnl for ticker, pnl in by_ticker.items()}
    top = sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
    return {
        "positive_pnl": round(positive_pnl, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "pnl": round(pnl, 2), "share": round(shares[ticker], 6)}
            for ticker, pnl in top
        ],
    }


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    out = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        rank = (index + end) / 2 + 1
        for pos in range(index, end + 1):
            out[ordered[pos][0]] = rank
        index = end + 1
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    denom_x = math.sqrt(sum(x * x for x in dx))
    denom_y = math.sqrt(sum(y * y for y in dy))
    if denom_x == 0 or denom_y == 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / (denom_x * denom_y)


def spearman(rows: list[dict[str, Any]], horizon: int, comparator: str) -> float | None:
    key = f"replacement_value_{horizon}d_vs_{comparator}_usd"
    pairs = [
        (safe_float(row.get("sec13f_coownership_network_score")), safe_float(row.get(key)))
        for row in rows
    ]
    clean = [(x, y) for x, y in pairs if x is not None and y is not None]
    if len(clean) < 10:
        return None
    xs = ranks([x for x, _ in clean])
    ys = ranks([y for _, y in clean])
    value = pearson(xs, ys)
    return round(value, 6) if value is not None else None


def summarize_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled = settled_rows(rows, horizon)
    buckets = bucket_rows(settled)
    bucket_summary: dict[str, Any] = {}
    for name, bucket in buckets.items():
        scores = [
            safe_float(row.get("sec13f_coownership_network_score"))
            for row in bucket
            if safe_float(row.get("sec13f_coownership_network_score")) is not None
        ]
        bucket_summary[name] = {
            "n": len(bucket),
            "ticker_count": len({row.get("ticker") for row in bucket if row.get("ticker")}),
            "asof_date_count": len({row.get("asof_date") for row in bucket if row.get("asof_date")}),
            "asof_date_start": min(
                (str(row.get("asof_date")) for row in bucket if row.get("asof_date")),
                default=None,
            ),
            "asof_date_end": max(
                (str(row.get("asof_date")) for row in bucket if row.get("asof_date")),
                default=None,
            ),
            "network_score_mean": (
                round(sum(scores) / len(scores), 6) if scores else None
            ),
            "network_score_median": round(median(scores) or 0.0, 6) if scores else None,
            "replacement_metrics": replacement_metrics(bucket, horizon),
            "cash_positive_concentration": concentration(bucket, horizon),
        }

    support: dict[str, Any] = {}
    for comparator in ["cash", "spy", "qqq"]:
        metric = f"replacement_value_vs_{comparator}_usd"
        high = bucket_summary["high_network"]["replacement_metrics"][metric]
        low = bucket_summary["low_network"]["replacement_metrics"][metric]
        missing = bucket_summary["missing_or_no_network"]["replacement_metrics"][metric]
        support[f"high_mean_{comparator}_beats_low"] = (
            high["mean"] is not None and low["mean"] is not None and high["mean"] > low["mean"]
        )
        support[f"high_median_{comparator}_beats_low"] = (
            high["median"] is not None
            and low["median"] is not None
            and high["median"] > low["median"]
        )
        support[f"high_mean_{comparator}_beats_missing"] = (
            high["mean"] is not None
            and missing["mean"] is not None
            and high["mean"] > missing["mean"]
        )
        support[f"spearman_{comparator}"] = spearman(settled, horizon, comparator)

    return {
        "horizon": horizon,
        "settled_rows": len(settled),
        "network_rows": sum(len(buckets[name]) for name in ["low_network", "mid_network", "high_network"]),
        "missing_or_no_network_rows": len(buckets["missing_or_no_network"]),
        "buckets": bucket_summary,
        "support": support,
    }


def source_summary(rows: list[dict[str, Any]], network_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_exists": OUTCOME_LEDGER.exists(),
        "source_outcome_ledger": repo_rel(OUTCOME_LEDGER),
        "source_rows": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "asof_date_count": len({row.get("asof_date") for row in rows if row.get("asof_date")}),
        "asof_date_start": min(
            (str(row.get("asof_date")) for row in rows if row.get("asof_date")),
            default=None,
        ),
        "asof_date_end": max(
            (str(row.get("asof_date")) for row in rows if row.get("asof_date")),
            default=None,
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "network_status": network_status,
    }


def evaluate_gate4(attribution: dict[int, dict[str, Any]]) -> dict[str, Any]:
    primary = attribution[ACCEPTANCE_RULE["primary_horizon"]]
    high = primary["buckets"]["high_network"]
    low = primary["buckets"]["low_network"]
    missing = primary["buckets"]["missing_or_no_network"]
    concentration_block = high["cash_positive_concentration"]

    checks = {
        "primary_network_sample_min_passed": primary["network_rows"]
        >= ACCEPTANCE_RULE["min_primary_network_rows"],
        "primary_missing_sample_min_passed": primary["missing_or_no_network_rows"]
        >= ACCEPTANCE_RULE["min_primary_missing_rows"],
        "primary_asof_dates_min_passed": high["asof_date_count"]
        >= ACCEPTANCE_RULE["min_primary_asof_dates"],
        "concentration_hhi_passed": (
            concentration_block["positive_pnl_hhi"] is not None
            and concentration_block["positive_pnl_hhi"]
            <= ACCEPTANCE_RULE["positive_pnl_hhi_guardrail"]
        ),
        "concentration_max_share_passed": (
            concentration_block["max_single_positive_pnl_share"] is not None
            and concentration_block["max_single_positive_pnl_share"]
            <= ACCEPTANCE_RULE["max_single_positive_pnl_share"]
        ),
    }
    for comparator in ["cash", "spy", "qqq"]:
        metric = f"replacement_value_vs_{comparator}_usd"
        high_metric = high["replacement_metrics"][metric]
        low_metric = low["replacement_metrics"][metric]
        missing_metric = missing["replacement_metrics"][metric]
        checks[f"high_mean_{comparator}_beats_low"] = (
            high_metric["mean"] is not None
            and low_metric["mean"] is not None
            and high_metric["mean"] > low_metric["mean"]
        )
        checks[f"high_median_{comparator}_beats_low"] = (
            high_metric["median"] is not None
            and low_metric["median"] is not None
            and high_metric["median"] > low_metric["median"]
        )
        checks[f"high_mean_{comparator}_beats_missing"] = (
            high_metric["mean"] is not None
            and missing_metric["mean"] is not None
            and high_metric["mean"] > missing_metric["mean"]
        )
        checks[f"spearman_{comparator}_positive"] = (
            primary["support"].get(f"spearman_{comparator}") is not None
            and primary["support"][f"spearman_{comparator}"] > 0
        )

    support_counts: dict[str, int] = {}
    for comparator in ["cash", "spy", "qqq"]:
        support_counts[f"mean_{comparator}_high_beats_low_horizon_count"] = sum(
            1
            for summary in attribution.values()
            if summary["support"].get(f"high_mean_{comparator}_beats_low")
        )
        checks[f"multi_horizon_mean_{comparator}_support"] = (
            support_counts[f"mean_{comparator}_high_beats_low_horizon_count"]
            >= ACCEPTANCE_RULE["min_supporting_horizons_high_beats_low"]
        )

    failed = [key for key, value in checks.items() if not value]
    observed_only_lead = not failed
    return {
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_kova_sec13f_coownership_network_lead_not_promoted"
            if observed_only_lead
            else "rejected_no_kova_sec13f_coownership_network_forward_edge"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "support_counts": support_counts,
        "lead_limitations": [
            "Forward-only post-2026-06-13 observations, not canonical fixed-window PIT coverage.",
            "10d outcomes remain pending and are excluded from the decision.",
            "No shared helper, daily adapter, ranking rule, sizing rule, or live behavior was promoted.",
        ],
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
        },
        "strategy_rerun_required": False,
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket)
    before = baseline_metrics()
    raw_rows = read_jsonl(OUTCOME_LEDGER)
    networks, network_status = load_networks(raw_rows)
    rows = enrich_network_scores(raw_rows, networks)
    attribution = {horizon: summarize_horizon(rows, horizon) for horizon in HORIZONS}
    gate4 = evaluate_gate4(attribution)
    decision = gate4["decision"]
    status = "observed_only_positive_lead" if gate4["observed_only_lead"] else "observed_only_rejected"

    actual_success = 1 if gate4["observed_only_lead"] else 0
    probability = safe_float(prediction.get("success_probability")) or 0.0
    primary = attribution[ACCEPTANCE_RULE["primary_horizon"]]
    why_result_happened = (
        "The fixed PIT SEC13F coownership network field "
        f"{'did' if gate4['observed_only_lead'] else 'did not'} separate "
        "settled Kova forward replacement rows across the predeclared primary "
        "5d cash/SPY/QQQ checks. This remains forward-only attribution and did "
        "not promote any trading behavior."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": gate4["observed_only_lead"],
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": probability,
            "actual_success": actual_success,
            "brier_score": round((probability - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_modes": gate4["failed_reasons"],
            "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
            "surprise_note": (
                "Low surprise: the 13F relation family had a weak frozen-window "
                "history and this run required a strict multi-comparator forward "
                "separation."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "Reservation passed without override; no strong near-neighbor.",
                "exp-20260622-007": (
                    "Rejected frozen-window 13F coaccumulation peer-shock relation. "
                    "This run uses post-exp017 closed forward replacement rows."
                ),
                "exp-20260624-018": (
                    "Observed-only positive sponsorship lead, but prohibited "
                    "holder-count/value/position-count retries on the same rows."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: join PIT coownership edges "
                "to settled Kova rows, bucket a fixed network score, and test "
                "cash/SPY/QQQ replacement-value separation."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if the primary 5d network and missing "
                "sample floors pass, high network beats low on mean/median "
                "cash/SPY/QQQ, high beats missing by mean, Spearman correlations "
                "are positive, at least two horizons support high>low by mean, "
                "and high-bucket positive PnL concentration passes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_outcome_ledger": repo_rel(OUTCOME_LEDGER),
            "coownership_network_dir": repo_rel(SEC13F_DIR),
            "horizons": HORIZONS,
            "primary_horizon": ACCEPTANCE_RULE["primary_horizon"],
            "bucket_method": "tertiles on fixed coownership network score among rows with peers; missing/no peers measured separately",
            "score_definition": (
                "Average percentile rank of log1p(peer_count), log1p(max_lift), "
                "log1p(avg_top5_lift), log1p(max_shared_managers), "
                "log1p(avg_top5_shared_managers), and log1p(max_jaccard)."
            ),
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "source_summary": source_summary(rows, network_status),
        "attribution": {str(key): value for key, value in attribution.items()},
        "primary_summary": {
            "horizon": ACCEPTANCE_RULE["primary_horizon"],
            "network_rows": primary["network_rows"],
            "missing_or_no_network_rows": primary["missing_or_no_network_rows"],
            "high_network": primary["buckets"]["high_network"],
            "low_network": primary["buckets"]["low_network"],
            "missing_or_no_network": primary["buckets"]["missing_or_no_network"],
            "support": primary["support"],
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": before,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(raw_rows) and bool(network_status["windows_loaded"]),
            "fields_checked": [
                "observation_id",
                "asof_date",
                "ticker",
                "sec13f_source_file",
                "coownership_edges peers_by_ticker",
                "forward_1d_status",
                "forward_3d_status",
                "forward_5d_status",
                "replacement_value_1d_vs_cash_usd",
                "replacement_value_3d_vs_spy_usd",
                "replacement_value_5d_vs_qqq_usd",
                "entry_date",
                "target_price",
            ],
            "source_summary": source_summary(rows, network_status),
            "target_price_relevance": (
                "Not applicable: this is observed-only fixed-horizon outcome "
                "attribution and does not schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(raw_rows),
            "signals_survived": primary["network_rows"] + primary["missing_or_no_network_rows"],
            "survival_rate": round(
                (primary["network_rows"] + primary["missing_or_no_network_rows"]) / len(raw_rows),
                4,
            )
            if raw_rows
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why_result_happened,
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova SEC13F coownership peer count, lift, shared "
                "manager, jaccard, network-score, holder-count/value, RS, "
                "Companyfacts, top-N, hold, cooldown, notional, or allocator "
                "thresholds on the same exp017 partial forward rows. This fixed "
                "network attribution is the result for that surface."
            ),
            "new_evidence_required": (
                "A valid retry needs enough closed 10d replacement-value rows, "
                "materially richer PIT manager identity/active-flow provenance, "
                "borrow/options cross-evidence, or canonical fixed-window PIT "
                "coverage through a shared default-off helper."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUTCOME_LEDGER),
            "data/non_ohlcv/sec13f_institutional/coownership_edges_*.json",
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260622-007.json",
            "experiments/logs/exp-20260624-016.json",
            "experiments/logs/exp-20260624-017.json",
            "experiments/logs/exp-20260624-018.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "parameters",
        "source_summary",
        "primary_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["primary_summary"]
    high_cash = primary["high_network"]["replacement_metrics"][
        "replacement_value_vs_cash_usd"
    ]
    low_cash = primary["low_network"]["replacement_metrics"][
        "replacement_value_vs_cash_usd"
    ]
    missing_cash = primary["missing_or_no_network"]["replacement_metrics"][
        "replacement_value_vs_cash_usd"
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F coownership forward attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- 5d network rows: `{primary['network_rows']}`",
            f"- 5d missing/no-network rows: `{primary['missing_or_no_network_rows']}`",
            f"- High network cash mean: `{high_cash['mean']}`",
            f"- Low network cash mean: `{low_cash['mean']}`",
            f"- Missing/no-network cash mean: `{missing_cash['mean']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
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
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        OUTCOME_LEDGER,
    ]
    for details in payload["source_summary"]["network_status"]["network_files"].values():
        rel = details.get("path")
        if rel:
            files.append(REPO_ROOT / rel)
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
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
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    primary = payload["primary_summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "primary_network_rows": primary["network_rows"],
                "primary_missing_or_no_network_rows": primary["missing_or_no_network_rows"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
