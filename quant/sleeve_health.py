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


RULE_VERSION = "sleeve_health_report_v3"
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
    for key in ("asof_date", "date", "updated_at", "generated_at"):
        value = str(row.get(key) or "")[:10]
        if value:
            return value
    return None


def _latest_summary_surface(sleeve_dir: Path) -> tuple[str | None, str | None]:
    """Return the freshest summary-style date for non-snapshot surfaces."""
    latest_date: str | None = None
    latest_name: str | None = None
    for path in sorted(sleeve_dir.glob("*summary.json")):
        date = _json_surface_date(path)
        if not date:
            continue
        if latest_date is None or date > latest_date:
            latest_date = date
            latest_name = path.name
    return latest_date, latest_name


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
            if last_date is None:
                summary_date, summary_name = _latest_summary_surface(sleeve_dir)
                if summary_date is None:
                    entry: dict[str, Any] = {"status": "never_persisted", "last_snapshot": None}
                    stalled.append(sleeve_dir.name)
                else:
                    staleness = sessions_between(summary_date, as_of_date)
                    entry = {
                        "status": "stale_summary" if staleness > int(stale_session_threshold) else "fresh_summary",
                        "last_snapshot": None,
                        "last_summary": summary_date,
                        "summary_file": summary_name,
                        "staleness_sessions": staleness,
                    }
                    if entry["status"] == "stale_summary":
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
    report = {
        "rule_version": RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "build_status": build_status,
        "failing_builds": failing_builds,
        "disk_status": disk_status,
        "stalled_sleeves": sorted(stalled),
        "stale_session_threshold": int(stale_session_threshold),
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
