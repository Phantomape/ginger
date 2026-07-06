"""Central daily health report for default-off paper sleeve accumulation.

exp-20260612-004: sleeve builders that early-return an empty snapshot persist
nothing and leave no skip record, so a dead accumulation surface looks exactly
like a quiet one (the SEC FTD+FINRA sleeve was silent for six days; six
accepted helpers never persisted state). This module is read-side only: after
the daily run has built every sleeve payload, it records one health row per
sleeve - build status straight from the payload plus on-disk snapshot
staleness measured in US equity sessions - and appends a single JSONL line per
day so stalls become visible the day they start.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

try:
    from data_paths import DATA_ROOT
    from us_market_calendar import is_us_equity_session
except ImportError:  # pragma: no cover - package-style import fallback
    from quant.data_paths import DATA_ROOT
    from quant.us_market_calendar import is_us_equity_session


RULE_VERSION = "sleeve_health_report_v4"
HEALTH_LOG_RELPATH = Path("paper_sleeves") / "sleeve_health.jsonl"

# Snapshot payload keys in the daily run that describe sleeve-like surfaces.
PAYLOAD_KEY_SUFFIXES = ("_sleeve", "_paper_sleeve", "_overlay")

# A sleeve whose snapshots.jsonl has not gained a row for more than this many
# completed US equity sessions is flagged stale.
DEFAULT_STALE_SESSION_THRESHOLD = 3
NON_FAILING_BUILD_STATUSES = {
    "non_us_equity_session",
    "retired_default_off_paper_disabled",
}

# ── Admission fire-rate contract (exp-20260704-025) ─────────────────────────
# Staleness catches dead surfaces; this catches ALIVE-BUT-STARVING ones:
# fresh snapshots, near-zero admissions. Each accepted default-off sleeve
# carries its replay-implied daily admission rate (accepted-experiment
# provenance) so the daily report can compare expectation against the actual
# new-pending rate. Rates come from machine-checked replay artifacts, not
# hand tuning; extend the table only with a verifiable replay source.
FIRE_RATE_RULE_VERSION = "sleeve_admission_fire_rate_watch_v1"
FIRE_RATE_WINDOW_UNIQUE_DAYS = 42
FIRE_RATE_MIN_OBSERVED_DAYS = 5
# Poisson zero-fire test: P(X=0 | lam>=3.0) < 5%.
FIRE_RATE_ALERT_MIN_EXPECTED = 3.0
FIRE_RATE_WARN_MIN_EXPECTED = 1.5
FIRE_RATE_SEVERE_UNDERFIRE_RATIO = 0.25
FIRE_RATE_SEVERE_UNDERFIRE_MIN_EXPECTED = 4.0

FIRE_RATE_CONTRACTS: dict[str, dict[str, Any]] = {
    "volatility_relief_leadership": {
        "replay_daily_fire_rate": 0.232804,
        "replay_trades": 88,
        "replay_trading_days": 378,
        "accepted_experiment": "exp-20260607-019",
        "rate_source": "exp-20260704-006",
        "parity_note": "exp-20260704-007 representative-day parity clean; regime-sparse zero spans possible",
    },
    "turn_of_month_liquid_leadership": {
        "replay_daily_fire_rate": 0.193122,
        "replay_trades": 73,
        "replay_trading_days": 378,
        "accepted_experiment": "exp-20260609-027",
        "rate_source": "exp-20260704-006",
        "parity_note": "daily calendar parity repaired exp-20260704-009",
    },
    "industry_stable_core_flow": {
        "replay_daily_fire_rate": 0.124339,
        "replay_trades": 47,
        "replay_trading_days": 378,
        "accepted_experiment": "exp-20260608-008",
        "rate_source": "exp-20260704-006",
        "parity_note": "exp-20260704-010 parity clean; admissions require same-day core-flow days",
    },
    "narrow_range_compression_breakout": {
        "replay_daily_fire_rate": 0.116402,
        "replay_trades": 44,
        "replay_trading_days": 378,
        "accepted_experiment": "exp-20260608-013",
        "rate_source": "exp-20260704-006",
        "parity_note": None,
    },
    "post_earnings_underpriced_drift": {
        "replay_daily_fire_rate": 0.05291,
        "replay_trades": 20,
        "replay_trading_days": 378,
        "accepted_experiment": "exp-20260602-026",
        "rate_source": "exp-20260704-006",
        "parity_note": None,
    },
    "sec_ftd_finra": {
        "replay_daily_fire_rate": 0.058201,
        "replay_trades": 22,
        "replay_trading_days": 378,
        "accepted_experiment": "exp-20260603-007",
        "rate_source": "exp-20260704-006",
        "parity_note": "2026-07-03 verdict: binding guard not_20d_breakout; representative-day probe still open",
    },
    "sec_financial_report": {
        "replay_daily_fire_rate": 0.150943,
        "replay_trades": 8,
        "replay_trading_days": 53,
        "accepted_experiment": "exp-20260614-004",
        "rate_source": "exp-20260704-015",
        "parity_note": "cohort derivation parity repaired exp-20260704-016; rate is post-repair archive-replay measured",
    },
}


def sessions_between(start: str, end: str) -> int:
    """Completed US equity sessions strictly after ``start`` up to ``end``."""
    try:
        day = datetime.date.fromisoformat(str(start)[:10])
        last = datetime.date.fromisoformat(str(end)[:10])
    except ValueError:
        return 0
    count = 0
    while day < last:
        day += datetime.timedelta(days=1)
        if is_us_equity_session(day):
            count += 1
    return count


def _payload_status(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if error:
        return str(error)
    status = payload.get("status")
    if status and str(status) not in ("ok", "None"):
        return str(status)
    return "ok"


def _last_snapshot_date(snapshot_path: Path) -> str | None:
    if not snapshot_path.exists():
        return None
    last = None
    try:
        with snapshot_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
    except OSError:
        return None
    if not last:
        return None
    try:
        row = json.loads(last)
    except json.JSONDecodeError:
        return None
    return str(row.get("asof_date") or row.get("as_of") or row.get("date") or "")[:10] or None


def _json_surface_date(path: Path) -> str | None:
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(row, dict):
        return None
    for key in ("asof_date", "as_of", "last_run_as_of", "date", "updated_at", "generated_at"):
        value = str(row.get(key) or "")[:10]
        if value:
            return value
    return None


def _is_heartbeat_state(path: Path) -> bool:
    if path.name != "state.json":
        return False
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(row, dict):
        return False
    return row.get("surface_contract") == "forward_observation_heartbeat"


def _latest_summary_surface(sleeve_dir: Path) -> tuple[str | None, str | None]:
    """Return the freshest summary-style date for non-snapshot surfaces."""
    latest_date: str | None = None
    latest_name: str | None = None
    candidates = list(sleeve_dir.glob("*summary.json"))
    state_path = sleeve_dir / "state.json"
    if state_path.exists() and _is_heartbeat_state(state_path):
        candidates.append(state_path)
    for path in sorted(candidates):
        date = _json_surface_date(path)
        if not date:
            continue
        if latest_date is None or date > latest_date:
            latest_date = date
            latest_name = path.name
    return latest_date, latest_name


def _admissions_by_asof(snapshot_path: Path) -> dict[str, int]:
    """Per-asof admission counts (max ``new_pending_count`` per date).

    Mirrors the exp-20260704-006 dedupe policy: same-day re-runs count once,
    using the largest observed value for the field on that date.
    """
    admissions: dict[str, int] = {}
    if not snapshot_path.exists():
        return admissions
    try:
        with snapshot_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                asof = str(row.get("asof_date") or row.get("as_of") or "")[:10]
                if not asof:
                    continue
                try:
                    count = int(float(row.get("new_pending_count") or 0))
                except (TypeError, ValueError):
                    count = 0
                admissions[asof] = max(admissions.get(asof, 0), count)
    except OSError:
        return admissions
    return admissions


def _fire_rate_status(actual: int, expected: float, observed_days: int) -> str:
    if observed_days < FIRE_RATE_MIN_OBSERVED_DAYS:
        return "insufficient_history"
    if actual == 0:
        if expected >= FIRE_RATE_ALERT_MIN_EXPECTED:
            return "alert_zero_fire"
        if expected >= FIRE_RATE_WARN_MIN_EXPECTED:
            return "warn_zero_fire"
        return "ok_sparse_window"
    if (
        expected >= FIRE_RATE_SEVERE_UNDERFIRE_MIN_EXPECTED
        and actual < expected * FIRE_RATE_SEVERE_UNDERFIRE_RATIO
    ):
        return "warn_severe_underfire"
    return "ok"


def build_fire_rate_watch(
    as_of: str,
    *,
    sleeves_root: str | Path | None = None,
    window_unique_days: int = FIRE_RATE_WINDOW_UNIQUE_DAYS,
    contracts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare each contracted sleeve's actual admissions to its replay rate.

    Read-side only. Counts admissions over the trailing ``window_unique_days``
    unique snapshot dates at or before ``as_of``; expected admissions are
    ``replay_daily_fire_rate * observed_days``. A sleeve is flagged when a
    zero-admission window is Poisson-improbable under its own accepted replay
    rate, or when it severely underfires a large expectation.
    """
    root = Path(sleeves_root) if sleeves_root else DATA_ROOT / "paper_sleeves"
    as_of_date = str(as_of)[:10]
    rows: dict[str, dict[str, Any]] = {}
    for sleeve_name, contract in sorted((contracts or FIRE_RATE_CONTRACTS).items()):
        rate = float(contract.get("replay_daily_fire_rate") or 0.0)
        admissions = _admissions_by_asof(root / sleeve_name / "snapshots.jsonl")
        window_dates = sorted(d for d in admissions if d <= as_of_date)[
            -int(window_unique_days):
        ]
        actual = sum(admissions[d] for d in window_dates)
        observed_days = len(window_dates)
        expected = round(rate * observed_days, 4)
        if not admissions:
            status = "no_snapshots"
        else:
            status = _fire_rate_status(actual, expected, observed_days)
        rows[sleeve_name] = {
            "status": status,
            "actual_admissions": actual,
            "expected_admissions": expected,
            "observed_days": observed_days,
            "window_first_asof": window_dates[0] if window_dates else None,
            "window_last_asof": window_dates[-1] if window_dates else None,
            "replay_daily_fire_rate": rate,
            "accepted_experiment": contract.get("accepted_experiment"),
            "rate_source": contract.get("rate_source"),
            "parity_note": contract.get("parity_note"),
        }
    return {
        "rule_version": FIRE_RATE_RULE_VERSION,
        "asof_date": as_of_date,
        "window_unique_days": int(window_unique_days),
        "alert_min_expected": FIRE_RATE_ALERT_MIN_EXPECTED,
        "warn_min_expected": FIRE_RATE_WARN_MIN_EXPECTED,
        "severe_underfire_ratio": FIRE_RATE_SEVERE_UNDERFIRE_RATIO,
        "sleeves": rows,
        "read_only": True,
    }


def build_sleeve_health_report(
    as_of: str,
    sleeve_payloads: dict[str, Any],
    *,
    sleeves_root: str | Path | None = None,
    health_log_path: str | Path | None = None,
    stale_session_threshold: int = DEFAULT_STALE_SESSION_THRESHOLD,
    persist: bool = True,
) -> dict[str, Any]:
    """Build (and append) the daily sleeve accumulation health report.

    ``sleeve_payloads`` is typically the daily ``trend_signals_dict``; any
    mapping value whose key ends with a sleeve-like suffix is summarized.
    Read-side only: never mutates sleeve state and never blocks the run.
    """
    root = Path(sleeves_root) if sleeves_root else DATA_ROOT / "paper_sleeves"
    log_path = Path(health_log_path) if health_log_path else DATA_ROOT / HEALTH_LOG_RELPATH
    as_of_date = str(as_of)[:10]

    build_status: dict[str, str] = {}
    for key, payload in (sleeve_payloads or {}).items():
        if not isinstance(payload, dict):
            continue
        if not str(key).endswith(PAYLOAD_KEY_SUFFIXES):
            continue
        build_status[str(key)] = _payload_status(payload)

    disk_status: dict[str, dict[str, Any]] = {}
    stalled: list[str] = []
    if root.is_dir():
        for sleeve_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            last_date = _last_snapshot_date(sleeve_dir / "snapshots.jsonl")
            summary_date, summary_name = _latest_summary_surface(sleeve_dir)
            if summary_date is not None and (last_date is None or summary_date > last_date):
                staleness = sessions_between(summary_date, as_of_date)
                entry = {
                    "status": "stale_summary" if staleness > int(stale_session_threshold) else "fresh_summary",
                    "last_snapshot": last_date,
                    "last_summary": summary_date,
                    "summary_file": summary_name,
                    "staleness_sessions": staleness,
                }
                if entry["status"] == "stale_summary":
                    stalled.append(sleeve_dir.name)
            elif last_date is None:
                entry = {"status": "never_persisted", "last_snapshot": None}
                stalled.append(sleeve_dir.name)
            else:
                staleness = sessions_between(last_date, as_of_date)
                entry = {
                    "status": "stale" if staleness > int(stale_session_threshold) else "fresh",
                    "last_snapshot": last_date,
                    "staleness_sessions": staleness,
                }
                if entry["status"] == "stale":
                    stalled.append(sleeve_dir.name)
            disk_status[sleeve_dir.name] = entry

    failing_builds = sorted(
        k
        for k, v in build_status.items()
        if v != "ok" and v not in NON_FAILING_BUILD_STATUSES
    )
    fire_rate_watch = build_fire_rate_watch(as_of_date, sleeves_root=root)
    starving = sorted(
        name
        for name, row in fire_rate_watch["sleeves"].items()
        if str(row.get("status", "")).startswith(("alert_", "warn_"))
    )
    report = {
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "build_status": build_status,
        "failing_builds": failing_builds,
        "disk_status": disk_status,
        "stalled_sleeves": sorted(stalled),
        "stale_session_threshold": int(stale_session_threshold),
        "fire_rate_watch": fire_rate_watch,
        "starving_sleeves": starving,
        "read_only": True,
    }

    if persist:
        already = False
        if log_path.exists():
            try:
                with log_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if (
                            str(row.get("asof_date")) == as_of_date
                            and str(row.get("rule_version") or "") == RULE_VERSION
                        ):
                            already = True
                            break
            except OSError:
                already = False
        if not already:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(report, sort_keys=True) + chr(10))
        report["persisted"] = not already
    return report
