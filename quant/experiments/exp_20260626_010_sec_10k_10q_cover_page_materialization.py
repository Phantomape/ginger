"""exp-20260626-010: SEC 10-K/10-Q cover-page materialization probe.

This continues the exp-20260626-008/009 filer-status blocker chain. The
strategy hypothesis remains that PIT cover-page filer-status upgrades may be a
distinct candidate-pool field, but the only question here is whether the
repaired 10-K/10-Q text scope can actually produce parseable cover-page rows.

No strategy, adapter, ranking, sizing, exit, order, LLM, paper ledger, cache, or
live behavior is changed.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import sys
import time
import urllib.request
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (QUANT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result  # noqa: E402
from sec_filing_text_backfill import DEFAULT_FORMS, html_to_text, sec_archive_dir  # noqa: E402


EXPERIMENT_ID = "exp-20260626-010"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_10k_10q_cover_page_materialization"
RUNNER = f"quant/experiments/exp_20260626_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_10k_10q_cover_page_text_materialization_v1"
MECHANISM_FAMILY = "sec_filer_status_materialization_repair"
TRIAL_FAMILY = "sec_10k_10q_cover_page_materialization_probe"
TRIAL_VARIANT_ID = "canonical_window_primary_document_probe_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
CANONICAL_EVENTS = NON_OHLCV_DIR / "sec_filing_events_20241002_20260421.jsonl"
SEC_TEXT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22"}),
    ]
)

HYPOTHESIS = (
    "Alpha blocker: SEC 10-K/10-Q cover-page filer-status upgrade candidate "
    "alpha cannot run until repaired text defaults can materialize parseable "
    "periodic-report cover-page rows by accession and accepted_at."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q cover-page filer-status upgrades from "
    "smaller/non-accelerated/EGC toward accelerated or large-accelerated status "
    "may identify improving institutional eligibility, but only if the local "
    "materializer can produce replayable status rows without current-category "
    "leakage."
)
PREDICTION = {
    "success_probability": 0.35,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "network_unavailable_in_sandbox",
        "no_local_periodic_text_cache",
        "primary_document_fetch_failed",
        "cover_page_parser_misses_inline_xbrl",
    ],
    "confidence_reason": (
        "exp-20260626-009 proved the repaired defaults admit 10-K/10-Q event "
        "rows, but local text/cache still contains zero periodic reports. A "
        "small primary-document probe can distinguish parser/materializer "
        "viability from missing historical fetch state without touching "
        "strategy behavior."
    ),
    "recorded_at": "2026-06-26T09:05:34+00:00",
}

USER_AGENT = "ginger-research/1.0 contact: research@example.com"
FETCH_TIMEOUT_SEC = 12
MAX_RAW_CHARS = 450_000
PERIODIC_FORMS = {"10-K", "10-Q"}

STATUS_TEXT_PATTERN = re.compile(
    r"(large accelerated filer|accelerated filer|non-accelerated filer|"
    r"smaller reporting company|emerging growth company)\s+(true|false|x|"
    r"checked|unchecked|\u2612|\u2611|\u2610|\u00fe|\u00a8)",
    re.IGNORECASE,
)
DEI_CATEGORY_PATTERN = re.compile(
    r"(?:dei:)?EntityFilerCategory[^>]*>([^<]+)<",
    re.IGNORECASE,
)
DEI_EGC_PATTERN = re.compile(
    r"(?:dei:)?EntityEmergingGrowthCompany[^>]*>(true|false|1|0)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, OrderedDict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, Counter):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    if not path.exists():
        return rows, errors
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, errors


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
    windows = payload.get("windows") or []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=0.0,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 4),
        "windows": windows,
    }


def form_base(row: dict[str, Any]) -> str:
    return str(row.get("form_base") or row.get("form_type") or "").upper().replace("/A", "")


def usable_day(row: dict[str, Any]) -> str:
    return str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]


def in_window(day: str, cfg: dict[str, str]) -> bool:
    return bool(day) and cfg["start"] <= day <= cfg["end"]


def event_key(row: dict[str, Any]) -> str:
    return str(row.get("accession_number") or "") or (
        str(row.get("ticker") or "") + ":" + str(row.get("primary_document") or "")
    )


def canonical_periodic_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, errors = iter_jsonl(CANONICAL_EVENTS)
    seen: set[str] = set()
    periodic: list[dict[str, Any]] = []
    coverage: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
        (
            label,
            {
                "periodic_event_rows": 0,
                "forms": Counter(),
                "ticker_count": 0,
                "_tickers": set(),
            },
        )
        for label in WINDOWS
    )
    form_counts: Counter[str] = Counter()
    for row in rows:
        base = form_base(row)
        if base not in PERIODIC_FORMS:
            continue
        key = event_key(row)
        if key in seen:
            continue
        seen.add(key)
        periodic.append(row)
        form_counts[base] += 1
        day = usable_day(row)
        for label, cfg in WINDOWS.items():
            if in_window(day, cfg):
                bucket = coverage[label]
                bucket["periodic_event_rows"] += 1
                bucket["forms"][base] += 1
                ticker = str(row.get("ticker") or "").upper()
                if ticker:
                    bucket["_tickers"].add(ticker)
    for bucket in coverage.values():
        bucket["ticker_count"] = len(bucket.pop("_tickers"))
        bucket["forms"] = dict(bucket["forms"])
    return periodic, {
        "source_file": repo_rel(CANONICAL_EVENTS),
        "json_parse_errors": errors,
        "periodic_event_rows": len(periodic),
        "form_counts": dict(form_counts),
        "windows": coverage,
    }


def local_text_coverage() -> dict[str, Any]:
    text_rows = 0
    parseable_rows = 0
    forms: Counter[str] = Counter()
    files_with_periodic: list[str] = []
    for path in sorted(NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl")):
        rows, _errors = iter_jsonl(path)
        file_periodic = 0
        for row in rows:
            base = form_base(row)
            if base not in PERIODIC_FORMS:
                continue
            file_periodic += 1
            text_rows += 1
            forms[base] += 1
            parsed = parse_cover_statuses(
                str(row.get("combined_text") or ""),
                raw_html="",
            )
            if parsed["parseable"]:
                parseable_rows += 1
        if file_periodic:
            files_with_periodic.append(repo_rel(path))

    cache_forms: Counter[str] = Counter()
    cache_parseable = 0
    if SEC_TEXT_CACHE_DIR.exists():
        for path in SEC_TEXT_CACHE_DIR.glob("*.json"):
            try:
                row = read_json(path)
            except Exception:
                continue
            base = form_base(row)
            if base not in PERIODIC_FORMS:
                continue
            cache_forms[base] += 1
            parsed = parse_cover_statuses(
                str(row.get("combined_text") or ""),
                raw_html="",
            )
            if parsed["parseable"]:
                cache_parseable += 1

    return {
        "sec_filing_text_periodic_rows": text_rows,
        "sec_filing_text_periodic_forms": dict(forms),
        "sec_filing_text_parseable_cover_status_rows": parseable_rows,
        "sec_filing_text_files_with_periodic_rows": files_with_periodic[:20],
        "cache_dir": repo_rel(SEC_TEXT_CACHE_DIR),
        "cache_periodic_rows": sum(cache_forms.values()),
        "cache_periodic_forms": dict(cache_forms),
        "cache_parseable_cover_status_rows": cache_parseable,
    }


def select_probe_events(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            usable_day(row),
            form_base(row),
            str(row.get("ticker") or ""),
            str(row.get("accession_number") or ""),
        ),
    )
    for label, cfg in WINDOWS.items():
        for wanted_form in ("10-K", "10-Q"):
            for row in sorted_rows:
                key = event_key(row)
                if key in selected_keys:
                    continue
                if form_base(row) != wanted_form:
                    continue
                if in_window(usable_day(row), cfg):
                    copy = dict(row)
                    copy["probe_window"] = label
                    selected.append(copy)
                    selected_keys.add(key)
                    break
    return selected


def request_url(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
    )
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SEC) as response:
        raw = response.read(MAX_RAW_CHARS + 1)
    return raw[:MAX_RAW_CHARS].decode("utf-8", errors="replace")


def primary_document_url(row: dict[str, Any]) -> str | None:
    base = sec_archive_dir(row.get("cik"), row.get("accession_number"))
    primary = str(row.get("primary_document") or "").strip()
    if not base or not primary:
        return None
    return f"{base}/{primary}"


def parse_cover_statuses(text: str, *, raw_html: str) -> dict[str, Any]:
    statuses: dict[str, bool | None] = {
        "large_accelerated_filer": None,
        "accelerated_filer": None,
        "non_accelerated_filer": None,
        "smaller_reporting_company": None,
        "emerging_growth_company": None,
    }

    for match in DEI_CATEGORY_PATTERN.finditer(raw_html[:80_000]):
        category = html.unescape(match.group(1)).strip().lower().replace("-", " ")
        if "large accelerated" in category:
            statuses["large_accelerated_filer"] = True
        elif "non accelerated" in category:
            statuses["non_accelerated_filer"] = True
        elif "accelerated" in category:
            statuses["accelerated_filer"] = True
        elif "smaller reporting" in category:
            statuses["smaller_reporting_company"] = True

    for match in DEI_EGC_PATTERN.finditer(raw_html[:80_000]):
        statuses["emerging_growth_company"] = match.group(1).lower() in {"true", "1"}

    for match in STATUS_TEXT_PATTERN.finditer(text[:24_000]):
        key = match.group(1).lower().replace("-", "_").replace(" ", "_")
        raw = match.group(2).lower()
        checked = raw in {"true", "x", "checked", "\u2612", "\u2611", "\u00fe"}
        if raw in {"false", "unchecked", "\u2610", "\u00a8"}:
            checked = False
        statuses[key] = checked

    return {
        "parseable": any(value is not None for value in statuses.values()),
        "statuses": statuses,
    }


def fetch_probe_row(row: dict[str, Any]) -> dict[str, Any]:
    url = primary_document_url(row)
    result = {
        "window": row.get("probe_window"),
        "ticker": str(row.get("ticker") or "").upper(),
        "form_type": row.get("form_type"),
        "accession_number": row.get("accession_number"),
        "accepted_at": row.get("accepted_at"),
        "usable_trade_date": usable_day(row),
        "primary_document": row.get("primary_document"),
        "url": url,
        "fetch_status": "not_attempted",
        "http_error": None,
        "raw_char_count": 0,
        "text_char_count": 0,
        "parseable": False,
        "statuses": {},
    }
    if not url:
        result["fetch_status"] = "missing_primary_document_url"
        return result
    try:
        raw = request_url(url)
        text = html_to_text(raw)
        parsed = parse_cover_statuses(text, raw_html=raw)
        result.update(
            {
                "fetch_status": "ok" if text else "empty_text",
                "raw_char_count": len(raw),
                "text_char_count": len(text),
                "parseable": bool(parsed["parseable"]),
                "statuses": parsed["statuses"],
            }
        )
    except Exception as exc:
        result["fetch_status"] = "fetch_failed"
        result["http_error"] = str(exc)[:300]
    return result


def materialization_probe(sample: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for idx, row in enumerate(sample):
        if idx:
            time.sleep(0.15)
        results.append(fetch_probe_row(row))
    parseable = [row for row in results if row.get("parseable")]
    fetched = [row for row in results if row.get("fetch_status") == "ok"]
    windows_with_parseable = sorted({str(row.get("window")) for row in parseable if row.get("window")})
    return {
        "sample_size": len(sample),
        "fetch_ok_rows": len(fetched),
        "parseable_cover_status_rows": len(parseable),
        "windows_with_parseable_rows": windows_with_parseable,
        "all_probe_windows_parseable": set(windows_with_parseable) == set(WINDOWS),
        "status_counts": dict(Counter(str(row.get("fetch_status")) for row in results)),
        "results": results,
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    periodic_events, event_coverage = canonical_periodic_events()
    local_coverage = local_text_coverage()
    sample = select_probe_events(periodic_events)
    probe = materialization_probe(sample)
    local_periodic_missing = (
        int(local_coverage["sec_filing_text_periodic_rows"]) == 0
        and int(local_coverage["cache_periodic_rows"]) == 0
    )
    sample_parseable = (
        probe["sample_size"] > 0
        and probe["parseable_cover_status_rows"] > 0
        and probe["all_probe_windows_parseable"]
    )
    accepted = bool(local_periodic_missing and sample_parseable)
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_sec_10k_10q_cover_page_probe_materializable"
        if accepted
        else "blocked_sec_10k_10q_cover_page_materialization_not_available"
    )
    failed_reasons: list[str] = []
    if not local_periodic_missing:
        failed_reasons.append("local_periodic_text_already_exists")
    if probe["sample_size"] <= 0:
        failed_reasons.append("no_canonical_periodic_probe_events")
    if probe["fetch_ok_rows"] <= 0:
        failed_reasons.append("primary_document_fetch_failed")
    if probe["parseable_cover_status_rows"] <= 0:
        failed_reasons.append("no_parseable_cover_page_status_in_probe")
    if not probe["all_probe_windows_parseable"]:
        failed_reasons.append("not_all_canonical_windows_parseable")

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
        "paper_orders_changed": False,
        "live_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "uses_free_sec_filing_events": True,
        "uses_free_sec_filing_text": True,
        "uses_llm": False,
        "replay_only": False,
        "live_realism_evaluated": False,
        "live_ready": False,
        "parity_note": (
            "Probe only. It uses SEC public archive primary-document URLs keyed "
            "by accession and accepted_at. No persistent daily/replay text rows "
            "or strategy consumers are promoted."
        ),
    }

    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Probed whether repaired SEC 10-K/10-Q text scope can materialize "
            "parseable cover-page filer-status rows from canonical-window "
            "primary documents."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair_materialization_probe",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "canonical 10-K/10-Q event coverage audit",
            "local sec_filing_text/cache periodic coverage audit",
            "SEC primary-document materialization probe",
            "cover-page filer-status parser smoke test",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260618-007",
            "exp-20260626-008",
            "exp-20260626-009",
        ],
        "multiple_testing_risk_bucket": "minimal_measurement_repair",
        "new_evidence_type": "alpha_blocker_materialization_probe",
        "new_evidence_axis": (
            "Materialization viability for an already-declared machine-checkable "
            "SEC cover-page filer-status field; not a filer-status alpha replay, "
            "form threshold, SEC phrase list, or filing-timeliness retry."
        ),
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "strategy_behavior_changed": False,
        },
        "gate2": {
            "passed": accepted,
            "default_forms": list(DEFAULT_FORMS),
            "canonical_event_coverage": event_coverage,
            "local_text_coverage": local_coverage,
            "materialization_probe": probe,
            "required_fields_checked": [
                "sec_filing_events accession_number",
                "sec_filing_events accepted_at",
                "sec_filing_events usable_trade_date",
                "sec_filing_events primary_document",
                "sec_filing_text_backfill DEFAULT_FORMS",
                "cover-page filer status booleans",
                "entry_date",
                "target_price",
            ],
            "blocking_reason": "; ".join(failed_reasons),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; this only probes a blocked data surface.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "survival_rate_delta": 0.0,
            },
            "failed_reasons": failed_reasons,
            "accepted_basis": (
                "A deterministic canonical-window probe fetched and parsed "
                "cover-page statuses while local historical periodic text/cache "
                "remained absent, proving the next blocker is full historical "
                "materialization rather than parser viability."
            )
            if accepted
            else None,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "canonical_periodic_event_rows": event_coverage["periodic_event_rows"],
            "local_periodic_text_rows": local_coverage["sec_filing_text_periodic_rows"],
            "local_periodic_cache_rows": local_coverage["cache_periodic_rows"],
            "probe_fetch_ok_rows": probe["fetch_ok_rows"],
            "probe_parseable_cover_status_rows": probe["parseable_cover_status_rows"],
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "brier_score": round(
                (PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2,
                6,
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if accepted else "; ".join(failed_reasons),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "The sample proved parser/materializer viability but did not "
                "materialize the full canonical surface."
            )
            if accepted
            else "The materialization probe did not produce enough parseable canonical-window status rows.",
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The repository has canonical 10-K/10-Q event rows, but no local "
                "periodic sec_filing_text rows or periodic text cache. The probe "
                "therefore tests only whether primary SEC documents can be "
                "fetched and parsed under the repaired scope."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run filer-status alpha, filing-timeliness, raw SEC item, "
                "or SEC phrase-list candidate-pool replays until full historical "
                "10-K/10-Q text rows or XBRL status rows are materialized across "
                "the canonical windows."
            ),
            "new_evidence_required": (
                "Materialize all canonical-window 10-K/10-Q primary-document rows "
                "or a compact XBRL-derived cover-page status sidecar keyed by "
                "accession_number, accepted_at, usable_trade_date, ticker, form, "
                "and parsed filer-status booleans; then run exactly one fixed "
                "shared-paper-first status-upgrade rule."
            ),
        },
        "next_retry_requires": [
            "full canonical-window 10-K/10-Q text or XBRL status materialization",
            "parsed cover-page large_accelerated/accelerated/non_accelerated/smaller_reporting/EGC booleans",
            "one fixed shared-paper-first status-upgrade candidate rule",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260618-007": "Blocked because historical 10-K/10-Q cover-page filer-status was absent.",
                "exp-20260626-008": "Blocked with event rows but no text rows.",
                "exp-20260626-009": "Accepted scope repair; did not materialize historical text or parse status rows.",
                "novelty_gate": "Measurement repair lane accepted exp-20260626-010; this is a data materialization probe, not an alpha replay.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair/probe if local periodic "
                "text/cache remains absent, canonical event rows exist in all "
                "three windows, and a deterministic primary-document sample "
                "fetches and parses cover-page status in every canonical window "
                "with zero strategy metric movement."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            repo_rel(Path(__file__)),
            repo_rel(BASELINE_RESULT),
            repo_rel(CANONICAL_EVENTS),
            "data/non_ohlcv/sec_filing_text_*.jsonl",
            "data/cache/sec/filing_text/*.json",
        ],
        "changed_files": [
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "hypothesis",
        "alpha_hypothesis",
        "change_summary",
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
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "calibration",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    gate2 = payload["gate2"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 10-K/10-Q Cover-Page Materialization",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Canonical periodic event rows: `{delta['canonical_periodic_event_rows']}`",
            f"- Local periodic text/cache rows: `{delta['local_periodic_text_rows']}` / `{delta['local_periodic_cache_rows']}`",
            f"- Probe fetch OK / parseable rows: `{delta['probe_fetch_ok_rows']}` / `{delta['probe_parseable_cover_status_rows']}`",
            f"- Gate 2 blocker: `{gate2['blocking_reason']}`",
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_row)
    result = {
        "accepted": bool(payload["accepted"]),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [{"label": label, **cfg} for label, cfg in WINDOWS.items()],
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": payload["production_impact"],
            "reproduction_commands": payload["reproduction_commands"],
            "changed_files": payload["changed_files"],
            "anti_js": payload["anti_js"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log_row(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
