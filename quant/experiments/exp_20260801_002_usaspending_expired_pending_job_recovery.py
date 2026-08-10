"""exp-20260801-002: USAspending expired pending job recovery proof."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from usaspending_obligation_observer import (  # noqa: E402
    DOWNLOAD_TRANSACTIONS_URL,
    PENDING_JOB_JOURNAL_NAME,
    build_daily_transaction_download_request,
    fetch_daily_transaction_snapshot,
)


EXPERIMENT_ID = "exp-20260801-002"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT = OUT_DIR / "exp_20260801_002_usaspending_expired_pending_job_recovery.json"
BASELINE = (
    ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json"
)

HEADER = [
    "contract_transaction_unique_key",
    "award_id_piid",
    "modification_number",
    "action_date",
    "initial_report_date",
    "last_modified_date",
    "federal_action_obligation",
    "base_and_all_options_value",
    "base_and_exercised_options_value",
    "current_total_value_of_award",
    "potential_total_value_of_award",
    "recipient_name",
    "recipient_uei",
    "recipient_parent_name",
    "recipient_parent_uei",
    "awarding_agency_name",
    "awarding_sub_agency_name",
    "awarding_office_name",
    "naics_code",
    "naics_description",
    "transaction_description",
    "action_type_code",
    "action_type",
]


def _zip_payload(key: str) -> bytes:
    row = [
        key,
        f"AWARD-{key}",
        "P00001",
        "2026-07-10",
        "2026-07-10 18:00:00+00",
        "2026-07-10 19:00:00+00",
        "100.00",
        "0.00",
        "0.00",
        "1000.00",
        "2000.00",
        "PUBLIC COMPANY INC.",
        "UEI123",
        "PUBLIC PARENT CORPORATION",
        "PARENTUEI123",
        "National Aeronautics and Space Administration",
        "",
        "OFFICE",
        "541715",
        "R&D",
        "TEST TRANSACTION",
        "C",
        "FUNDING ONLY ACTION",
    ]
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(HEADER)
    writer.writerow(row)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contracts_Subawards.csv", "ignored\n")
        archive.writestr(
            "Contracts_PrimeTransactions_1.csv",
            text.getvalue().encode("utf-8-sig"),
        )
    return output.getvalue()


class _FakeProducerHttp:
    def __init__(self, *, key: str, statuses: list[dict] | None = None) -> None:
        self.status_url = (
            "https://api.usaspending.gov/api/v2/download/status?file=test.zip"
        )
        self.file_url = "https://files.usaspending.gov/generated_downloads/test.zip"
        self.zip_payload = _zip_payload(key)
        self.statuses = list(statuses or [{"status": "finished"}])
        self.post_calls: list[tuple[str, dict, float]] = []
        self.get_calls: list[tuple[str, float]] = []

    def post(self, url: str, payload: dict, *, timeout: float) -> dict:
        self.post_calls.append((url, payload, timeout))
        return {
            "status_url": self.status_url,
            "file_name": "test.zip",
            "file_url": self.file_url,
        }

    def get(self, url: str, *, timeout: float):
        self.get_calls.append((url, timeout))
        if url == self.status_url:
            return self.statuses.pop(0)
        if url == self.file_url:
            return self.zip_payload
        raise AssertionError(f"unexpected URL: {url}")


def _clock(*values: str):
    timestamps = iter(
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        for value in values
    )
    last = None

    def now() -> datetime:
        nonlocal last
        try:
            last = next(timestamps)
        except StopIteration:
            if last is None:
                last = datetime.now(timezone.utc)
        return last

    return now


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="usaspending-expired-", dir=OUT_DIR) as tmp:
        output = Path(tmp) / "observer"
        first_http = _FakeProducerHttp(key="A", statuses=[{"status": "running"}])
        pending = fetch_daily_transaction_snapshot(
            "2026-07-27",
            output,
            http_post=first_http.post,
            http_get=first_http.get,
            now_fn=_clock("2026-07-27T00:00:00Z"),
            max_status_polls=1,
        )
        fresh_http = _FakeProducerHttp(key="B", statuses=[{"status": "finished"}])
        recovered = fetch_daily_transaction_snapshot(
            "2026-07-27",
            output,
            http_post=fresh_http.post,
            http_get=fresh_http.get,
            now_fn=_clock("2026-07-28T00:00:01Z", "2026-07-28T00:00:02Z"),
        )
        failed_calls: list[str] = []

        def failed_post(*_args, **_kwargs):
            failed_calls.append("post")
            return {}

        output_stale = Path(tmp) / "stale"
        stale_http = _FakeProducerHttp(key="C", statuses=[{"status": "running"}])
        fetch_daily_transaction_snapshot(
            "2026-07-27",
            output_stale,
            http_post=stale_http.post,
            http_get=stale_http.get,
            now_fn=_clock("2026-07-27T00:00:00Z"),
            max_status_polls=1,
        )
        stale = fetch_daily_transaction_snapshot(
            "2026-07-27",
            output_stale,
            http_post=failed_post,
            http_get=failed_post,
            now_fn=_clock("2026-07-28T00:00:01Z"),
        )
        journal = json.loads(
            (output / PENDING_JOB_JOURNAL_NAME).read_text(encoding="utf-8")
        )

    checks = {
        "pending_before_recovery": pending["status"] == "pending",
        "recovered_after_expiry": recovered["status"] == "ok",
        "fresh_post_used_after_expiry": fresh_http.post_calls
        == [
            (
                DOWNLOAD_TRANSACTIONS_URL,
                build_daily_transaction_download_request("2026-07-27"),
                30.0,
            )
        ],
        "recovery_did_not_mark_resume": recovered["resumed_pending_job"] is False,
        "failed_fresh_post_stays_stale": stale["status"] == "stale"
        and stale["pending_job_validation_status"] == "expired",
        "completed_journal_retired_receipt": journal["state"] == "completed",
    }
    result = {
        "experiment_id": EXPERIMENT_ID,
        "artifact_type": "usaspending_expired_pending_job_recovery",
        "status": "accepted" if all(checks.values()) else "rejected",
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "orders_changed": False,
        "entry_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "exits_changed": False,
        "checks": checks,
        "producer_before": {
            "status": pending["status"],
            "run_date": pending["run_date"],
            "pending_job_validation_status": pending["pending_job_validation_status"],
        },
        "producer_after_recovered": {
            "status": recovered["status"],
            "run_date": recovered["run_date"],
            "resumed_pending_job": recovered["resumed_pending_job"],
            "pending_job_validation_status": recovered[
                "pending_job_validation_status"
            ],
            "status_poll_count": recovered["status_poll_count"],
            "attempt_poll_count": recovered["attempt_poll_count"],
        },
        "producer_after_failed_repost": {
            "status": stale["status"],
            "pending_job_validation_status": stale["pending_job_validation_status"],
            "fresh_post_attempted": failed_calls == ["post"],
        },
        "baseline_sha256": _sha256(BASELINE),
        "acceptance_tests": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest -q quant\\test_usaspending_obligation_observer.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest -q quant\\test_run_daily_wiring.py -k usaspending",
        ],
    }
    ARTIFACT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
