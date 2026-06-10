"""Auto-refresh of the macro event calendar from official schedules.

Called from the daily pipelines (run.py / run_intraday.py) so NFP / CPI /
FOMC dates accumulate with normal production runs instead of relying on a
hand-maintained list that silently goes stale.

Safety contract (enforced here and in macro_events.load_overlay_events):
  - append-only: writes ONLY to the overlay file
    (data/reference/macro_events_overlay.json), never to the seed list in
    quant/macro_events.py;
  - future-only: only dates strictly after both today and
    macro_events.OVERLAY_MIN_DATE are accepted — automation can never alter
    hand-verified history that replay/experiments depend on;
  - fail-quiet: any fetch/parse failure leaves the overlay unchanged; the
    calendar_audit findings in the intraday report remain the alarm.

Sources (per family, first success wins):
  NFP   FRED release/dates API (release_id 50, needs FRED_API_KEY) ->
        bls.gov/schedule/news_release/empsit.htm
  CPI   FRED release/dates API (release_id 10) ->
        bls.gov/schedule/news_release/cpi.htm
  FOMC  federalreserve.gov/monetarypolicy/fomccalendars.htm
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    import macro_events
    from data_paths import atomic_write_json
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import macro_events
    from quant.data_paths import atomic_write_json

logger = logging.getLogger(__name__)

BLS_SCHEDULE_URLS = {
    "NFP": "https://www.bls.gov/schedule/news_release/empsit.htm",
    "CPI": "https://www.bls.gov/schedule/news_release/cpi.htm",
}
FED_FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FRED_RELEASE_IDS = {"NFP": 50, "CPI": 10}
FRED_DATES_URL = (
    "https://api.stlouisfed.org/fred/release/dates"
    "?release_id={release_id}&api_key={api_key}&file_type=json"
    "&include_release_dates_with_no_data=true&realtime_start={start}"
)

FAMILY_LABELS = {
    "NFP": "Employment Situation (official schedule, auto-fetched)",
    "CPI": "CPI (official schedule, auto-fetched)",
    "FOMC": "FOMC decision (official calendar, auto-fetched)",
}

# Ignore parsed dates beyond this horizon (schedule pages list ~1 year ahead;
# anything further is likely parse noise).
MAX_AHEAD_DAYS = 550

_MONTHS = {
    name[:3].lower(): num
    for num, name in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], start=1)
}
_MONTH_RE = (
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_RE = re.compile(_MONTH_RE + r"\.?\s+(\d{1,2}),\s+(20\d{2})")
_FOMC_YEAR_RE = re.compile(r"(20\d{2})\s+FOMC\s+Meetings", re.IGNORECASE)
_FOMC_SPAN_RE = re.compile(
    _MONTH_RE + r"\.?\s+(\d{1,2})\s*[-–]\s*(?:" + _MONTH_RE + r"\.?\s+)?(\d{1,2})"
)


def _http_get(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "ginger-research/1.0 calendar refresh"
            ),
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html,
                  flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"<[^>]+>", " ", text)


def _to_iso(month_token: str, day: str, year: str) -> str | None:
    month = _MONTHS.get(month_token[:3].lower())
    if not month:
        return None
    try:
        return date(int(year), month, int(day)).isoformat()
    except ValueError:
        return None


def parse_bls_schedule_dates(html: str) -> list[str]:
    """All 'Month DD, YYYY' dates on a BLS release-schedule page.

    Every date on these single-indicator schedule pages is a release date,
    except footer noise like 'Last Modified Date: ...' which is excluded by
    proximity to the word 'Modified'.
    """
    text = _strip_html(html)
    results = []
    for match in _DATE_RE.finditer(text):
        prefix = text[max(0, match.start() - 60):match.start()]
        if re.search(r"modified", prefix, re.IGNORECASE):
            continue
        iso = _to_iso(match.group(1), match.group(2), match.group(3))
        if iso:
            results.append(iso)
    return sorted(set(results))


def parse_fomc_decision_days(html: str) -> list[str]:
    """Decision days (last day of each meeting) from the Fed calendar page."""
    text = _strip_html(html)
    sections = list(_FOMC_YEAR_RE.finditer(text))
    results = []
    for index, section in enumerate(sections):
        year = section.group(1)
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        chunk = text[section.end():end]
        for match in _FOMC_SPAN_RE.finditer(chunk):
            start_month, _, end_month, end_day = match.groups()
            iso = _to_iso(end_month or start_month, end_day, year)
            if iso:
                results.append(iso)
    return sorted(set(results))


def _fetch_fred_release_dates(family: str, today_iso: str, http_get) -> list[str]:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise LookupError("FRED_API_KEY not set")
    url = FRED_DATES_URL.format(
        release_id=FRED_RELEASE_IDS[family], api_key=api_key, start=today_iso
    )
    payload = json.loads(http_get(url))
    rows = payload.get("release_dates")
    if not isinstance(rows, list):
        raise ValueError("unexpected FRED response shape")
    return sorted({
        row["date"] for row in rows
        if isinstance(row, dict) and isinstance(row.get("date"), str)
    })


def fetch_official_macro_dates(today_iso: str, http_get=_http_get) -> dict:
    """{family: {"dates": [iso...]} or {"error": str}} from official sources."""
    out: dict[str, dict] = {}
    for family, url in BLS_SCHEDULE_URLS.items():
        try:
            dates = _fetch_fred_release_dates(family, today_iso, http_get)
            out[family] = {"dates": dates, "source": "fred_api"}
            continue
        except Exception as e:
            fred_error = str(e)
        try:
            out[family] = {
                "dates": parse_bls_schedule_dates(http_get(url)),
                "source": "bls_schedule_page",
            }
        except Exception as e:
            out[family] = {"error": f"fred: {fred_error}; bls: {e}"}
    try:
        out["FOMC"] = {
            "dates": parse_fomc_decision_days(http_get(FED_FOMC_URL)),
            "source": "fed_calendar_page",
        }
    except Exception as e:
        out["FOMC"] = {"error": str(e)}
    return out


def _load_overlay_payload(path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return payload
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("overlay payload unreadable (%s) — starting fresh", e)
    return {"schema_version": 1, "fetched_at": None, "events": []}


def refresh_macro_events_overlay(
    today_iso: str | None = None,
    *,
    ttl_days: int = 7,
    force: bool = False,
    path=None,
    http_get=_http_get,
) -> dict:
    """Fetch official schedules and append new FUTURE dates to the overlay.

    Designed to be called unconditionally from daily runs: throttled via the
    overlay's fetched_at (default: refetch weekly), and a total failure leaves
    everything unchanged.
    """
    today_iso = today_iso or date.today().isoformat()
    target = path if path is not None else macro_events.overlay_path()
    payload = _load_overlay_payload(target)

    fetched_at = payload.get("fetched_at")
    if fetched_at and not force:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)
            if age < timedelta(days=ttl_days):
                return {"status": "fresh", "added": 0,
                        "fetched_at": fetched_at}
        except ValueError:
            pass

    results = fetch_official_macro_dates(today_iso, http_get=http_get)

    known = {(e["date"], e["family"]) for e in macro_events.MACRO_EVENTS}
    known |= {
        (e.get("date"), e.get("family")) for e in payload.get("events", [])
    }
    horizon = (date.fromisoformat(today_iso)
               + timedelta(days=MAX_AHEAD_DAYS)).isoformat()
    floor = max(today_iso, macro_events.OVERLAY_MIN_DATE)

    added: list[dict] = []
    per_family: dict[str, int] = {}
    errors: dict[str, str] = {}
    for family, result in results.items():
        if "error" in result:
            errors[family] = result["error"]
            continue
        count = 0
        for iso in result["dates"]:
            if not (floor < iso <= horizon):
                continue
            if (iso, family) in known:
                continue
            added.append({"date": iso, "family": family,
                          "label": FAMILY_LABELS[family]})
            known.add((iso, family))
            count += 1
        per_family[family] = count

    if not per_family:
        # every source failed — change nothing, retry on the next run
        logger.warning("macro calendar refresh: all sources failed: %s", errors)
        return {"status": "failed", "added": 0, "errors": errors}

    payload["events"] = sorted(
        payload.get("events", []) + added,
        key=lambda r: (r.get("date", ""), r.get("family", "")),
    )
    payload["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["source_status"] = {
        family: result.get("source", result.get("error"))
        for family, result in results.items()
    }
    atomic_write_json(payload, target)
    synced = macro_events.attach_overlay(target)

    summary = {
        "status": "refreshed",
        "added": len(added),
        "attached_in_memory": synced,
        "per_family": per_family,
        "errors": errors,
    }
    if added:
        logger.info("macro calendar refresh: appended %d future date(s): %s",
                    len(added), [(r["date"], r["family"]) for r in added])
    return summary
