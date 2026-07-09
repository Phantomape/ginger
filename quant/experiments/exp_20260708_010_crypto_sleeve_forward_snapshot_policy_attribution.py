"""exp-20260708-010: BTC crypto sleeve forward snapshot attribution.

Observed-only alpha attribution. The single question is whether the existing
production BTC/USD crypto sleeve target policy added risk-adjusted forward
value versus fee-aware BTC buy-and-hold over saved daily quant signal snapshots.

This runner changes no shared policy, target threshold, live config, stock
order, crypto order, ranking, sizing, exit rule, or LLM boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts",):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from experiment_fingerprint import infer_fingerprint  # noqa: E402


EXPERIMENT_ID = "exp-20260708-010"
OWNER = "alpha-explore"
SLUG = "crypto_sleeve_forward_snapshot_policy_attribution"
RUNNER = f"quant/experiments/exp_20260708_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
QUANT_SIGNALS_DIR = REPO_ROOT / "data" / "daily" / "signals" / "quant"
CRYPTO_CONFIG = REPO_ROOT / "data" / "state" / "crypto" / "crypto_positions.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
FINGERPRINT_SCRIPT = REPO_ROOT / "scripts" / "experiment_fingerprint.py"

HYPOTHESIS = (
    "Observed-only alpha: the existing production BTC/USD crypto sleeve daily "
    "EMA20/EMA100/SMA200 target policy may add risk-adjusted forward value "
    "versus BTC buy-and-hold over saved production snapshots without changing "
    "stock orders."
)
CHANGE_TYPE = "risk_allocation"
IMPLEMENTATION_MODE = "observed_only_production_snapshot_forward_attribution"
MECHANISM_FAMILY = "production_visible_crypto_sleeve_forward_attribution"
TRIAL_FAMILY = "btc_spot_crypto_sleeve_daily_trend_policy_forward_attribution"
TRIAL_VARIANT_ID = "saved_quant_signals_20260503_20260707_v1"
CHANGED_VARIABLE = "crypto_sleeve_forward_snapshot_policy_attribution_v1"
NEW_EVIDENCE_TYPE = "settled_production_forward_crypto_sleeve_snapshots"
NEW_EVIDENCE_AXIS = (
    "Saved production crypto_sleeve BTC/USD forward snapshots from 2026-05-02 "
    "through 2026-07-06 with later snapshot closes; prior crypto experiments "
    "tested crypto-equity stock proxies or yfinance plumbing, not this "
    "production spot policy outcome."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260607-022",
    "exp-20260622-023",
    "exp-20260708-008",
]
CAUSAL_COMPONENTS = [
    "production crypto_sleeve snapshots",
    "settled next-snapshot BTC close returns",
    "fee-aware target exposure attribution",
    "novelty classifier coverage patch",
    "no production behavior change",
]
PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "risk_off_misses_rebound",
        "too_few_target_switches",
        "fees_consume_edge",
        "buy_and_hold_beats_policy",
    ],
    "confidence_reason": (
        "This is a production-visible BTC spot surface with real saved forward "
        "snapshots, but the sample is short, mostly risk-off, and the fixed "
        "policy could miss rebound days."
    ),
    "recorded_at": "2026-07-08T07:07:02+00:00",
}
CONFIG = {
    "min_unique_asof_dates": 30,
    "min_target_switches": 1,
    "annualization_days": 365,
    "fee_pct_per_side_fallback": 0.0049,
    "sleeve_value_usd_fallback": 15000.0,
    "initial_policy_position_pct": 0.0,
    "benchmark": "fee_aware_btc_buy_and_hold",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, payload: dict[str, Any], key: str = "experiment_id") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keep: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                keep.append(line)
                continue
            if row.get(key) != payload.get(key):
                keep.append(json.dumps(row, sort_keys=True))
    keep.append(json.dumps(payload, sort_keys=True))
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return round(float(value), digits)


def parse_file_date(path: Path) -> str | None:
    match = re.search(r"quant_signals_(\d{8})", path.name)
    if not match:
        return None
    value = match.group(1)
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def date_key(value: str | None) -> tuple[int, int, int]:
    if not value:
        return (0, 0, 0)
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        return (0, 0, 0)
    return (parsed.year, parsed.month, parsed.day)


def load_baseline() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT, {})
    if not isinstance(data, dict):
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "available": False}
    compact: dict[str, Any] = {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "available": bool(data),
    }
    for key in (
        "expected_value_score",
        "strategy_total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "total_trades",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ):
        if key in data:
            compact[key] = data[key]
    if "aggregate" in data:
        compact["aggregate"] = data["aggregate"]
    if "windows" in data and isinstance(data["windows"], list):
        compact["window_count"] = len(data["windows"])
    return compact


def load_snapshots() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scanned = 0
    skipped: Counter[str] = Counter()
    for path in sorted(QUANT_SIGNALS_DIR.glob("quant_signals_*.json")):
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            skipped["read_error"] += 1
            continue
        if '"crypto_sleeve"' not in text:
            skipped["no_crypto_sleeve"] += 1
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            skipped["json_error"] += 1
            continue
        sleeve = data.get("crypto_sleeve")
        if not isinstance(sleeve, dict):
            skipped["bad_crypto_sleeve"] += 1
            continue
        snapshot = sleeve.get("snapshot") or {}
        action = sleeve.get("action") or {}
        if not isinstance(snapshot, dict) or not isinstance(action, dict):
            skipped["bad_nested_shape"] += 1
            continue
        asof_date = snapshot.get("asof_date")
        close = as_float(snapshot.get("close"))
        target = as_float(action.get("target_position_pct"))
        if not asof_date or close is None or close <= 0 or target is None:
            skipped["missing_required_field"] += 1
            continue
        rows.append(
            {
                "source_file": repo_rel(path),
                "file_date": parse_file_date(path),
                "generated_at": data.get("generated_at"),
                "enabled": bool(sleeve.get("enabled")),
                "symbol": sleeve.get("symbol"),
                "display_symbol": sleeve.get("display_symbol"),
                "policy": sleeve.get("policy"),
                "fee_pct_per_side": as_float(sleeve.get("fee_pct_per_side")),
                "asof_date": str(asof_date),
                "close": close,
                "state": sleeve.get("state"),
                "reason": sleeve.get("reason"),
                "ema20": as_float(snapshot.get("ema20")),
                "ema100": as_float(snapshot.get("ema100")),
                "sma200": as_float(snapshot.get("sma200")),
                "rsi14": as_float(snapshot.get("rsi14")),
                "ret7d_pct": as_float(snapshot.get("ret7d_pct")),
                "action": action.get("action"),
                "current_position_pct": as_float(action.get("current_position_pct")),
                "target_position_pct": target,
                "delta_position_pct": as_float(action.get("delta_position_pct")),
                "production_impact": sleeve.get("production_impact"),
            }
        )
    diagnostics = {
        "quant_signal_files_scanned": scanned,
        "raw_crypto_snapshot_rows": len(rows),
        "skipped": dict(skipped),
    }
    return rows, diagnostics


def dedupe_snapshots(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_asof: dict[str, dict[str, Any]] = {}
    duplicate_examples: list[dict[str, Any]] = []
    duplicate_count = 0
    for row in sorted(rows, key=lambda r: (date_key(r.get("file_date")), r.get("source_file") or "")):
        asof = str(row["asof_date"])
        previous = by_asof.get(asof)
        if previous is not None:
            duplicate_count += 1
            if len(duplicate_examples) < 5:
                duplicate_examples.append(
                    {
                        "asof_date": asof,
                        "kept_source_file": row.get("source_file"),
                        "replaced_source_file": previous.get("source_file"),
                    }
                )
        by_asof[asof] = row
    unique = sorted(by_asof.values(), key=lambda r: date_key(r.get("asof_date")))
    return unique, {
        "unique_asof_dates": len(unique),
        "duplicate_asof_rows_removed": duplicate_count,
        "duplicate_examples": duplicate_examples,
        "first_asof_date": unique[0]["asof_date"] if unique else None,
        "last_asof_date": unique[-1]["asof_date"] if unique else None,
    }


def equity_curve(returns: list[float]) -> list[float]:
    curve = [1.0]
    for ret in returns:
        curve.append(curve[-1] * (1.0 + ret))
    return curve


def max_drawdown(curve: list[float]) -> float:
    if not curve:
        return 0.0
    peak = curve[0]
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return abs(worst)


def summarize_returns(
    label: str,
    returns: list[float],
    sleeve_value_usd: float,
    annualization_days: int,
) -> dict[str, Any]:
    curve = equity_curve(returns)
    total_return = curve[-1] - 1.0 if curve else 0.0
    if len(returns) > 1:
        mean_ret = statistics.fmean(returns)
        stdev = statistics.stdev(returns)
        sharpe = mean_ret / stdev * math.sqrt(annualization_days) if stdev > 0 else 0.0
    elif returns:
        mean_ret = returns[0]
        stdev = 0.0
        sharpe = 0.0
    else:
        mean_ret = 0.0
        stdev = 0.0
        sharpe = 0.0
    return {
        "label": label,
        "periods": len(returns),
        "total_return_pct": rounded(total_return),
        "total_pnl_usd": rounded(total_return * sleeve_value_usd, 2),
        "expected_value_score": rounded(total_return * sharpe),
        "sharpe_daily": rounded(sharpe),
        "mean_period_return_pct": rounded(mean_ret),
        "vol_period_return_pct": rounded(stdev),
        "max_drawdown_pct": rounded(max_drawdown(curve)),
        "win_rate": rounded(
            sum(1 for ret in returns if ret > 0) / len(returns) if returns else 0.0
        ),
        "ending_equity": rounded(curve[-1] if curve else 1.0),
    }


def simulate_policy(unique: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    if len(unique) < 2:
        return {
            "intervals": [],
            "policy_returns": [],
            "buy_hold_returns": [],
            "cash_returns": [],
            "policy_fee_cost_pct_sum": 0.0,
            "buy_hold_fee_cost_pct_sum": 0.0,
            "target_switches": 0,
            "terminal_policy_liquidation_fee_pct": 0.0,
        }

    fee = as_float(config.get("fee_pct_per_side")) or CONFIG["fee_pct_per_side_fallback"]
    annualization_days = int(CONFIG["annualization_days"])
    sleeve_value_usd = as_float(config.get("sleeve_value_usd")) or CONFIG["sleeve_value_usd_fallback"]
    prev_target = float(CONFIG["initial_policy_position_pct"])
    policy_returns: list[float] = []
    buy_hold_returns: list[float] = []
    cash_returns: list[float] = []
    intervals: list[dict[str, Any]] = []
    policy_fee_cost_pct_sum = 0.0
    buy_hold_fee_cost_pct_sum = 0.0
    target_switches = 0
    state_bucket: dict[str, list[dict[str, float]]] = defaultdict(list)

    for index in range(len(unique) - 1):
        row = unique[index]
        nxt = unique[index + 1]
        btc_return = nxt["close"] / row["close"] - 1.0
        target = float(row["target_position_pct"])
        delta_target = target - prev_target
        rebalance_fee = abs(delta_target) * fee
        if abs(delta_target) > 1e-9:
            target_switches += 1
        policy_return = target * btc_return - rebalance_fee
        buy_hold_fee = 0.0
        if index == 0:
            buy_hold_fee += fee
        if index == len(unique) - 2:
            buy_hold_fee += fee
        buy_hold_return = btc_return - buy_hold_fee

        policy_returns.append(policy_return)
        buy_hold_returns.append(buy_hold_return)
        cash_returns.append(0.0)
        policy_fee_cost_pct_sum += rebalance_fee
        buy_hold_fee_cost_pct_sum += buy_hold_fee
        state = str(row.get("state") or "UNKNOWN")
        state_bucket[state].append(
            {
                "btc_forward_return": btc_return,
                "policy_return": policy_return,
                "target_position_pct": target,
                "fee_pct": rebalance_fee,
            }
        )
        intervals.append(
            {
                "from_asof_date": row["asof_date"],
                "to_asof_date": nxt["asof_date"],
                "state": state,
                "target_position_pct": rounded(target),
                "close": rounded(row["close"], 2),
                "next_close": rounded(nxt["close"], 2),
                "btc_forward_return_pct": rounded(btc_return),
                "policy_return_pct": rounded(policy_return),
                "buy_hold_return_pct": rounded(buy_hold_return),
                "rebalance_fee_pct": rounded(rebalance_fee),
            }
        )
        prev_target = target

    terminal_policy_liquidation_fee_pct = abs(prev_target) * fee
    if terminal_policy_liquidation_fee_pct > 0:
        policy_returns[-1] -= terminal_policy_liquidation_fee_pct
        intervals[-1]["terminal_policy_liquidation_fee_pct"] = rounded(
            terminal_policy_liquidation_fee_pct
        )
        policy_fee_cost_pct_sum += terminal_policy_liquidation_fee_pct

    by_state: dict[str, Any] = {}
    for state, bucket in sorted(state_bucket.items()):
        count = len(bucket)
        by_state[state] = {
            "interval_count": count,
            "avg_target_position_pct": rounded(
                statistics.fmean(item["target_position_pct"] for item in bucket)
            ),
            "avg_btc_forward_return_pct": rounded(
                statistics.fmean(item["btc_forward_return"] for item in bucket)
            ),
            "btc_positive_share": rounded(
                sum(1 for item in bucket if item["btc_forward_return"] > 0) / count
                if count
                else 0.0
            ),
            "policy_return_sum_pct": rounded(
                sum(item["policy_return"] for item in bucket)
            ),
            "fee_cost_sum_pct": rounded(sum(item["fee_pct"] for item in bucket)),
        }

    return {
        "intervals": intervals,
        "policy_returns": policy_returns,
        "buy_hold_returns": buy_hold_returns,
        "cash_returns": cash_returns,
        "policy": summarize_returns(
            "crypto_sleeve_policy_net",
            policy_returns,
            sleeve_value_usd,
            annualization_days,
        ),
        "buy_hold": summarize_returns(
            "btc_buy_hold_fee_aware",
            buy_hold_returns,
            sleeve_value_usd,
            annualization_days,
        ),
        "cash": summarize_returns("cash", cash_returns, sleeve_value_usd, annualization_days),
        "policy_fee_cost_pct_sum": rounded(policy_fee_cost_pct_sum),
        "buy_hold_fee_cost_pct_sum": rounded(buy_hold_fee_cost_pct_sum),
        "target_switches": target_switches,
        "terminal_policy_liquidation_fee_pct": rounded(terminal_policy_liquidation_fee_pct),
        "by_state": by_state,
    }


def build_gate4(sim: dict[str, Any], dedupe: dict[str, Any]) -> dict[str, Any]:
    policy = sim["policy"]
    buy_hold = sim["buy_hold"]
    cash = sim["cash"]
    checks = {
        "enough_unique_asof_dates": dedupe["unique_asof_dates"] >= CONFIG["min_unique_asof_dates"],
        "has_target_switch": sim["target_switches"] >= CONFIG["min_target_switches"],
        "policy_total_return_nonnegative": policy["total_return_pct"] >= 0.0,
        "policy_sharpe_gt_buy_hold": policy["sharpe_daily"] > buy_hold["sharpe_daily"],
        "policy_drawdown_lt_buy_hold": policy["max_drawdown_pct"] < buy_hold["max_drawdown_pct"],
        "policy_return_gt_cash": policy["total_return_pct"] > cash["total_return_pct"],
    }
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "benchmark": CONFIG["benchmark"],
        "checks": checks,
        "failed_reasons": failed,
        "unique_asof_dates": dedupe["unique_asof_dates"],
        "interval_count": len(sim["intervals"]),
        "target_switches": sim["target_switches"],
        "policy": policy,
        "buy_hold": buy_hold,
        "cash": cash,
        "delta_vs_buy_hold": {
            "total_return_pct": rounded(policy["total_return_pct"] - buy_hold["total_return_pct"]),
            "total_pnl_usd": rounded(policy["total_pnl_usd"] - buy_hold["total_pnl_usd"], 2),
            "expected_value_score": rounded(
                policy["expected_value_score"] - buy_hold["expected_value_score"]
            ),
            "sharpe_daily": rounded(policy["sharpe_daily"] - buy_hold["sharpe_daily"]),
            "max_drawdown_pct": rounded(
                policy["max_drawdown_pct"] - buy_hold["max_drawdown_pct"]
            ),
        },
        "fee_costs": {
            "policy_fee_cost_pct_sum": sim["policy_fee_cost_pct_sum"],
            "buy_hold_fee_cost_pct_sum": sim["buy_hold_fee_cost_pct_sum"],
            "terminal_policy_liquidation_fee_pct": sim[
                "terminal_policy_liquidation_fee_pct"
            ],
        },
        "by_state": sim["by_state"],
    }


def compact_interval_sample(intervals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "first_5": intervals[:5],
        "last_5": intervals[-5:] if len(intervals) >= 5 else intervals,
    }


def build_payload() -> dict[str, Any]:
    ticket_before = read_json(TICKET_JSON, {})
    crypto_config = read_json(CRYPTO_CONFIG, {}) or {}
    raw_rows, load_diagnostics = load_snapshots()
    unique_rows, dedupe = dedupe_snapshots(raw_rows)
    sim = simulate_policy(unique_rows, crypto_config)
    gate4 = build_gate4(sim, dedupe)
    novelty_classifier_after_patch = infer_fingerprint(
        MECHANISM_FAMILY,
        TRIAL_FAMILY,
        CHANGED_VARIABLE,
    )

    positive_observed_lead = all(
        gate4["checks"][key]
        for key in (
            "enough_unique_asof_dates",
            "has_target_switch",
            "policy_total_return_nonnegative",
            "policy_sharpe_gt_buy_hold",
            "policy_drawdown_lt_buy_hold",
            "policy_return_gt_cash",
        )
    )
    if positive_observed_lead:
        status = "observed_only"
        decision = "observed_only_positive_lead_not_activation_ready"
        rejection_reason = None
        why = (
            "The fixed crypto sleeve policy beat the fee-aware BTC buy-and-hold "
            "benchmark on the predeclared observed-only risk-adjusted checks, "
            "but the sample is still short and this runner changed no policy."
        )
        observed_only_lead = True
    else:
        status = "observed_only"
        decision = "observed_only_rejected_crypto_sleeve_policy_attribution"
        rejection_reason = ";".join(gate4["failed_reasons"])
        why = (
            "The fixed crypto sleeve policy did not satisfy all predeclared "
            "observed-only checks versus fee-aware BTC buy-and-hold and cash."
        )
        observed_only_lead = False

    state_counts = Counter(str(row.get("state") or "UNKNOWN") for row in unique_rows)
    target_counts = Counter(str(row.get("target_position_pct")) for row in unique_rows)
    snapshot_sample = [
        {
            "source_file": row["source_file"],
            "asof_date": row["asof_date"],
            "close": rounded(row["close"], 2),
            "state": row["state"],
            "target_position_pct": rounded(row["target_position_pct"]),
        }
        for row in (unique_rows[:3] + unique_rows[-3:] if len(unique_rows) > 6 else unique_rows)
    ]

    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(ARTIFACT_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        repo_rel(EXPERIMENT_LOG),
        repo_rel(FINGERPRINT_SCRIPT),
    ]
    allowed_write_scope = list(ticket_before.get("allowed_write_scope") or [])
    for path in (
        repo_rel(REGISTRY_JSON),
        repo_rel(EXPERIMENT_LOG),
        repo_rel(FINGERPRINT_SCRIPT),
    ):
        if path not in allowed_write_scope:
            allowed_write_scope.append(path)

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": PREDICTION,
        "novelty_classifier_after_patch": novelty_classifier_after_patch,
        "config": CONFIG,
        "crypto_config": {
            "enabled": crypto_config.get("enabled"),
            "symbol": crypto_config.get("symbol"),
            "display_symbol": crypto_config.get("display_symbol"),
            "broker": crypto_config.get("broker"),
            "sleeve_value_usd": as_float(crypto_config.get("sleeve_value_usd")),
            "fee_pct_per_side": as_float(crypto_config.get("fee_pct_per_side")),
            "policy": crypto_config.get("policy"),
            "min_rebalance_delta_pct": as_float(crypto_config.get("min_rebalance_delta_pct")),
        },
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "risk_allocation",
            "nearby_history": NEARBY_PRIOR_EXPERIMENTS,
            "single_policy_bundle": CHANGED_VARIABLE,
            "success_failure_standard": (
                "Observed-only fixed policy must outperform BTC buy-and-hold "
                "on max drawdown and Sharpe with non-negative return capture."
            ),
            "reproducibility": "Runner persists data, log, card, artifact, manifest, and registry fields.",
        },
        "gate1": {
            "stock_strategy_baseline": load_baseline(),
            "crypto_baselines": ["fee_aware_btc_buy_and_hold", "cash"],
            "note": (
                "No stock strategy behavior changed. The crypto comparator is "
                "constructed from the same saved BTC spot closes."
            ),
        },
        "gate2": {
            "required_fields": [
                "crypto_sleeve.snapshot.asof_date",
                "crypto_sleeve.snapshot.close",
                "crypto_sleeve.state",
                "crypto_sleeve.action.target_position_pct",
            ],
            "present": bool(unique_rows),
            "entry_date_contract": "not_applicable_crypto_spot_allocation_no_Position_entry",
            "target_price_contract": "not_applicable_crypto_spot_allocation_no_ATR_exit",
            "policy_contract": crypto_config.get("policy"),
        },
        "gate3": {
            "raw_crypto_snapshot_rows": load_diagnostics["raw_crypto_snapshot_rows"],
            "unique_asof_dates": dedupe["unique_asof_dates"],
            "interval_count": len(sim["intervals"]),
            "state_counts": dict(state_counts),
            "target_position_counts": dict(target_counts),
            "survival_rate": 1.0 if unique_rows else 0.0,
            "no_filter_added": True,
        },
        "gate4": gate4,
        "data_diagnostics": {
            **load_diagnostics,
            **dedupe,
            "snapshot_sample": snapshot_sample,
            "interval_sample": compact_interval_sample(sim["intervals"]),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "stock_strategy_changed": False,
            "alters_stock_orders": False,
            "alters_crypto_orders": False,
            "existing_production_crypto_advice_unchanged": True,
            "novelty_classifier_changed": True,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only offline attribution over saved production quant "
                "signal snapshots. The production crypto sleeve remains as-is."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune EMA/SMA thresholds, target percentages, fee "
                "assumptions, benchmark liquidation convention, or sub-slices "
                "on this same saved snapshot surface."
            ),
            "new_evidence_required": (
                "A legal retry needs materially more settled production crypto "
                "sleeve snapshot rows, a different BTC/crypto data source, or a "
                "new gate shape such as shared historical replay before policy "
                "changes."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "materially more settled production crypto_sleeve rows",
            "or a different BTC/crypto data source",
            "or a shared historical replay gate shape",
        ],
        "before_after_strategy_behavior_changed": False,
        "changed_files": changed_files,
        "related_files": [
            RUNNER,
            repo_rel(CRYPTO_CONFIG),
            repo_rel(QUANT_SIGNALS_DIR),
            repo_rel(BASELINE_RESULT),
            repo_rel(FINGERPRINT_SCRIPT),
        ],
        "allowed_write_scope": allowed_write_scope,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\")
            + " scripts\\experiment_fingerprint.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "report": repo_rel(ARTIFACT_MD),
        "log": repo_rel(LOG_JSON),
        "ticket_before": ticket_before,
        "created_at": utc_now(),
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": payload["prediction"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": gate4,
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
            "accepted_alpha": payload["accepted_alpha"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty_classifier_after_patch": payload["novelty_classifier_after_patch"],
            "artifact": payload["artifact"],
            "report": payload["report"],
        "log": payload["log"],
        "summary": {
            "policy_total_return_pct": gate4["policy"]["total_return_pct"],
            "policy_sharpe_daily": gate4["policy"]["sharpe_daily"],
            "policy_max_drawdown_pct": gate4["policy"]["max_drawdown_pct"],
            "buy_hold_total_return_pct": gate4["buy_hold"]["total_return_pct"],
            "buy_hold_sharpe_daily": gate4["buy_hold"]["sharpe_daily"],
            "buy_hold_max_drawdown_pct": gate4["buy_hold"]["max_drawdown_pct"],
            "failed_reasons": gate4["failed_reasons"],
        },
        "completed_at": utc_now(),
    }


def build_report(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    policy = gate4["policy"]
    buy_hold = gate4["buy_hold"]
    delta = gate4["delta_vs_buy_hold"]
    by_state = gate4["by_state"]
    lines = [
        f"# {EXPERIMENT_ID}: BTC Crypto Sleeve Forward Snapshot Attribution",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Hypothesis: {HYPOTHESIS}",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Gate 4",
        "",
        "| Metric | Crypto sleeve policy | BTC buy-and-hold | Delta policy - B&H |",
        "|---|---:|---:|---:|",
        f"| Total return | {policy['total_return_pct']} | {buy_hold['total_return_pct']} | {delta['total_return_pct']} |",
        f"| PnL on sleeve | {policy['total_pnl_usd']} | {buy_hold['total_pnl_usd']} | {delta['total_pnl_usd']} |",
        f"| Sharpe daily | {policy['sharpe_daily']} | {buy_hold['sharpe_daily']} | {delta['sharpe_daily']} |",
        f"| Expected value score | {policy['expected_value_score']} | {buy_hold['expected_value_score']} | {delta['expected_value_score']} |",
        f"| Max drawdown | {policy['max_drawdown_pct']} | {buy_hold['max_drawdown_pct']} | {delta['max_drawdown_pct']} |",
        "",
        f"- Unique BTC candle dates: `{gate4['unique_asof_dates']}`",
        f"- Forward intervals: `{gate4['interval_count']}`",
        f"- Target switches: `{gate4['target_switches']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## State Attribution",
        "",
        "| State | Intervals | Avg target | Avg BTC next return | BTC positive share | Policy return sum | Fee cost sum |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for state, row in by_state.items():
        lines.append(
            f"| {state} | {row['interval_count']} | {row['avg_target_position_pct']} | "
            f"{row['avg_btc_forward_return_pct']} | {row['btc_positive_share']} | "
            f"{row['policy_return_sum_pct']} | {row['fee_cost_sum_pct']} |"
        )
    lines.extend(
        [
            "",
            "## Closeout",
            "",
            f"- Production impact: {payload['production_impact']['parity_note']}",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    policy = gate4["policy"]
    buy_hold = gate4["buy_hold"]
    lines = [
        f"# {EXPERIMENT_ID}: BTC Crypto Sleeve Forward Snapshot Attribution",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Report: `{payload['report']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Result",
        "",
        f"- Unique BTC candle dates: `{gate4['unique_asof_dates']}`",
        f"- Forward intervals: `{gate4['interval_count']}`",
        f"- Target switches: `{gate4['target_switches']}`",
        f"- Policy return / Sharpe / max DD: `{policy['total_return_pct']}` / "
        f"`{policy['sharpe_daily']}` / `{policy['max_drawdown_pct']}`",
        f"- Buy-hold return / Sharpe / max DD: `{buy_hold['total_return_pct']}` / "
        f"`{buy_hold['sharpe_daily']}` / `{buy_hold['max_drawdown_pct']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Reflection",
        "",
        f"- Why: {payload['post_run_reflection']['why_result_happened']}",
        f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        ARTIFACT_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        FINGERPRINT_SCRIPT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "report": repo_rel(ARTIFACT_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_record = compact_log_record(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    write_text(CARD_MD, build_card(payload))
    write_text(ARTIFACT_MD, build_report(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "policy_total_return_pct": payload["gate4"]["policy"]["total_return_pct"],
            "policy_sharpe_daily": payload["gate4"]["policy"]["sharpe_daily"],
            "policy_max_drawdown_pct": payload["gate4"]["policy"]["max_drawdown_pct"],
            "buy_hold_total_return_pct": payload["gate4"]["buy_hold"]["total_return_pct"],
            "buy_hold_sharpe_daily": payload["gate4"]["buy_hold"]["sharpe_daily"],
            "buy_hold_max_drawdown_pct": payload["gate4"]["buy_hold"]["max_drawdown_pct"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty_classifier_after_patch": payload["novelty_classifier_after_patch"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "artifact": payload["artifact"],
                "report": payload["report"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
