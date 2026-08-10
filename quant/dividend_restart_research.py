from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
FIXED_WINDOWS = {
    "late_strong": ("2025-10-23", "2026-04-21"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "old_thin": ("2024-10-02", "2025-04-22"),
}

_RECURRING_RE = re.compile(
    r"quarterly\s+(?:cash\s+)?dividend|"
    r"(?:cash\s+)?dividend\s+program|"
    r"regular\s+cash\s+dividend|"
    r"recurring\s+quarterly\s+dividend",
    re.IGNORECASE,
)
_INITIATION_RE = re.compile(
    r"(?:initiat\w*|inaugural|first[- ]ever|first\s+cash|initial)"
    r".{0,180}(?:quarterly|regular|recurring).{0,80}dividend|"
    r"(?:quarterly|regular|recurring).{0,80}dividend"
    r".{0,180}(?:initiat\w*|inaugural|first[- ]ever|first\s+cash|initial)",
    re.IGNORECASE | re.DOTALL,
)
_RESUMPTION_RE = re.compile(
    r"(?:resum\w*|reinstat\w*|restor\w*)"
    r".{0,180}(?:quarterly|regular|recurring)?.{0,80}dividend|"
    r"(?:quarterly|regular|recurring)?.{0,80}dividend"
    r".{0,180}(?:resum\w*|reinstat\w*|restor\w*)",
    re.IGNORECASE | re.DOTALL,
)
_EARNINGS_RE = re.compile(
    r"financial\s+results|earnings\s+release|"
    r"results\s+for\s+the\s+(?:first|second|third|fourth|quarter|year)|"
    r"quarter\s+ended|fiscal\s+(?:first|second|third|fourth)\s+quarter",
    re.IGNORECASE,
)
_GUIDANCE_RE = re.compile(
    r"(?:raises?|updates?|provides?)\s+(?:full[- ]year\s+)?(?:outlook|guidance)|"
    r"(?:outlook|guidance)\s+(?:raised|updated)",
    re.IGNORECASE,
)
_STRATEGIC_RE = re.compile(
    r"(?:announc\w*|enter\w*)\s+.{0,100}(?:partnership|collaboration)|"
    r"(?:acquir\w*|acquisition|merger|spin[- ]off|separation)\s+.{0,120}|"
    r"(?:appoint\w*|promot\w*|resign\w*|retir\w*)"
    r".{0,100}(?:chief|president|officer|director)",
    re.IGNORECASE | re.DOTALL,
)
_REPURCHASE_RE = re.compile(
    r"(?:new|increase\w*|authoriz\w*)\s+.{0,100}"
    r"(?:share|stock)\s+repurchase\s+(?:program|plan|authorization)",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class FilingAssessment:
    lifecycle_class: str | None
    amount_match: bool
    confounds: tuple[str, ...]

    @property
    def strict_clean(self) -> bool:
        return bool(self.lifecycle_class and self.amount_match and not self.confounds)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _amount_pattern(cash_amount: str) -> re.Pattern[str] | None:
    try:
        amount = Decimal(str(cash_amount))
    except InvalidOperation:
        return None
    tokens = {
        format(amount, "f"),
        f"{amount:.2f}",
        f"{amount:.3f}",
        f"{amount:.4f}",
    }
    alternatives = "|".join(
        sorted((re.escape(token) for token in tokens), key=len, reverse=True)
    )
    return re.compile(
        rf"(?:us\s*)?\$\s*(?:{alternatives})(?:0*)\s*"
        rf"(?:per|a)\s+(?:common\s+)?share",
        re.IGNORECASE,
    )


def assess_filing(
    *,
    text: str,
    cash_amount: str,
    form_type: str,
    item_codes: Iterable[str] = (),
) -> FilingAssessment:
    normalized = str(text or "")
    if not _RECURRING_RE.search(normalized):
        return FilingAssessment(None, False, ())
    lifecycle_class: str | None = None
    if _INITIATION_RE.search(normalized):
        lifecycle_class = "recurring_initiation"
    elif _RESUMPTION_RE.search(normalized):
        lifecycle_class = "recurring_resumption"

    amount_re = _amount_pattern(cash_amount)
    amount_match = bool(amount_re and amount_re.search(normalized))
    prefix = normalized[:20_000]
    codes = {str(value).strip() for value in item_codes}
    confounds: list[str] = []
    form_base = str(form_type or "").upper().replace("/A", "")
    if form_base in {"10-Q", "10-K"} or "2.02" in codes:
        confounds.append("earnings_filing")
    elif _EARNINGS_RE.search(prefix):
        confounds.append("earnings_release_text")
    if _GUIDANCE_RE.search(prefix):
        confounds.append("guidance_update")
    if _STRATEGIC_RE.search(prefix):
        confounds.append("strategic_or_management_event")
    if _REPURCHASE_RE.search(prefix):
        confounds.append("new_repurchase_program")
    return FilingAssessment(
        lifecycle_class=lifecycle_class,
        amount_match=amount_match,
        confounds=tuple(sorted(set(confounds))),
    )


def parse_sec_accepted_at(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def first_trade_session_after_publication(
    accepted_at: dt.datetime,
    sessions: Iterable[str],
) -> str | None:
    accepted_utc = accepted_at.astimezone(UTC)
    for value in sorted(set(str(session)[:10] for session in sessions)):
        session_date = dt.date.fromisoformat(value)
        market_open = dt.datetime.combine(
            session_date, dt.time(9, 30), tzinfo=NY
        ).astimezone(UTC)
        if accepted_utc < market_open:
            return value
    return None


def decision_ready_at(
    accepted_at: dt.datetime, declaration_date: str
) -> dt.datetime:
    declaration_close = dt.datetime.combine(
        dt.date.fromisoformat(declaration_date), dt.time(16, 0), tzinfo=NY
    ).astimezone(UTC)
    return max(accepted_at.astimezone(UTC), declaration_close)


def _window_for(declaration_date: str) -> str | None:
    return next(
        (
            name
            for name, (start, end) in FIXED_WINDOWS.items()
            if start <= declaration_date <= end
        ),
        None,
    )


def _pure_recurring_rows(
    conn: sqlite3.Connection,
    endpoint_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    selected: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    for endpoint in endpoint_rows:
        ticker, declaration_date = str(endpoint["decision_key"]).split(":", 1)
        rows = conn.execute(
            "SELECT cash_amount,currency,raw_json,provider_id FROM stock_dividends "
            "WHERE ticker=? AND declaration_date=? AND CAST(cash_amount AS REAL)>0 "
            "AND lower(currency)='usd' ORDER BY provider_id",
            (ticker, declaration_date),
        ).fetchall()
        parsed = [
            {
                "cash_amount": row[0],
                "currency": row[1],
                "raw": json.loads(row[2]),
                "provider_id": row[3],
            }
            for row in rows
        ]
        recurring = [
            row
            for row in parsed
            if str(row["raw"].get("distribution_type") or "").lower()
            == "recurring"
            and int(row["raw"].get("frequency") or 0) > 0
        ]
        if not recurring:
            exclusions["not_recurring"] += 1
            continue
        if len(recurring) != len(parsed):
            exclusions["mixed_distribution_types_same_ticker_date"] += 1
            continue
        amounts = {str(row["cash_amount"]) for row in recurring}
        if len(amounts) != 1:
            exclusions["ambiguous_recurring_cash_amount"] += 1
            continue
        selected.append(
            {
                "decision_key": endpoint["decision_key"],
                "ticker": ticker,
                "declaration_date": declaration_date,
                "provider_entry_session": endpoint.get("entry_session"),
                "provider_exit_session": endpoint.get("exit_session"),
                "cash_amount": next(iter(amounts)),
                "provider_ids": [row["provider_id"] for row in recurring],
                "frequency": int(recurring[0]["raw"].get("frequency") or 0),
                "window": _window_for(declaration_date),
            }
        )
    return selected, exclusions


def build_preflight(
    *,
    database: Path,
    endpoint_preflight: Path,
    sec_text: Path,
) -> dict[str, Any]:
    endpoint_payload = json.loads(endpoint_preflight.read_text(encoding="utf-8"))
    endpoint_rows = [
        row for row in endpoint_payload.get("rows", []) if bool(row.get("eligible"))
    ]
    texts = _jsonl(sec_text)
    texts_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in texts:
        if row.get("ticker"):
            texts_by_ticker[str(row["ticker"]).upper()].append(row)

    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as conn:
        recurring_rows, exclusions = _pure_recurring_rows(conn, endpoint_rows)
        accepted: list[dict[str, Any]] = []
        timestamp_verified_bundles: list[dict[str, Any]] = []
        assessments: list[dict[str, Any]] = []
        for candidate in recurring_rows:
            filings = texts_by_ticker.get(candidate["ticker"], [])
            if not filings:
                exclusions["no_near_declaration_sec_filing"] += 1
                continue
            valid_assessments: list[tuple[dt.datetime, dict[str, Any], FilingAssessment]] = []
            for filing in filings:
                assessment = assess_filing(
                    text=str(filing.get("combined_text") or ""),
                    cash_amount=candidate["cash_amount"],
                    form_type=str(filing.get("form_type") or ""),
                    item_codes=filing.get("eight_k_item_codes") or [],
                )
                assessment_row = {
                    "decision_key": candidate["decision_key"],
                    "ticker": candidate["ticker"],
                    "accession_number": filing.get("accession_number"),
                    "accepted_at": filing.get("accepted_at"),
                    "form_type": filing.get("form_type"),
                    "lifecycle_class": assessment.lifecycle_class,
                    "amount_match": assessment.amount_match,
                    "confounds": list(assessment.confounds),
                    "archive_url": (
                        next(
                            (
                                doc.get("url")
                                for doc in filing.get("documents", [])
                                if doc.get("url")
                            ),
                            None,
                        )
                    ),
                }
                assessments.append(assessment_row)
                if not assessment.lifecycle_class or not assessment.amount_match:
                    continue
                try:
                    accepted_at = parse_sec_accepted_at(filing["accepted_at"])
                except (KeyError, TypeError, ValueError):
                    continue
                valid_assessments.append((accepted_at, filing, assessment))

            if not valid_assessments:
                exclusions["no_explicit_lifecycle_amount_match"] += 1
                continue
            valid_assessments.sort(key=lambda item: item[0])
            accepted_at, filing, assessment = valid_assessments[0]
            ready_at = decision_ready_at(accepted_at, candidate["declaration_date"])
            sessions = [
                str(row[0])
                for row in conn.execute(
                    "SELECT trade_date FROM daily_bars WHERE ticker=? "
                    "AND trade_date>=? ORDER BY trade_date LIMIT 20",
                    (candidate["ticker"], ready_at.astimezone(NY).date().isoformat()),
                ).fetchall()
            ]
            entry_session = first_trade_session_after_publication(ready_at, sessions)
            if entry_session is None:
                exclusions["no_entry_session_after_publication"] += 1
                continue
            entry_index = sessions.index(entry_session)
            if entry_index + 9 >= len(sessions):
                exclusions["h10_session_missing"] += 1
                continue
            row = {
                **candidate,
                "lifecycle_class": assessment.lifecycle_class,
                "public_known_at": accepted_at.isoformat().replace("+00:00", "Z"),
                "decision_ready_at": ready_at.isoformat().replace("+00:00", "Z"),
                "entry_session": entry_session,
                "exit_session": sessions[entry_index + 9],
                "sec_accession_number": filing.get("accession_number"),
                "sec_form_type": filing.get("form_type"),
                "sec_item_codes": filing.get("eight_k_item_codes") or [],
                "source_url": next(
                    (
                        doc.get("url")
                        for doc in filing.get("documents", [])
                        if doc.get("url")
                    ),
                    None,
                ),
                "coannouncement_confounds": list(assessment.confounds),
            }
            timestamp_verified_bundles.append(row)
            if assessment.confounds:
                exclusions["coannouncement_bundle"] += 1
                continue
            accepted.append(row)

    strict_counts = Counter(row["window"] for row in accepted)
    bundle_counts = Counter(row["window"] for row in timestamp_verified_bundles)
    lifecycle_counts = Counter(row["lifecycle_class"] for row in accepted)
    touch_floor_pass = all(strict_counts[name] >= 5 for name in FIXED_WINDOWS)
    return {
        "schema_version": 1,
        "record_type": "dividend_recurring_public_timestamp_preflight",
        "generated_at": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "outcome_blind": True,
        "outcome_fields_read": [],
        "post_entry_price_values_read": False,
        "calendar_only_after_publication": True,
        "source_candidate_count": len(endpoint_rows),
        "pure_recurring_count": len(recurring_rows),
        "timestamp_verified_bundle_count": len(timestamp_verified_bundles),
        "strict_clean_count": len(accepted),
        "strict_counts_by_window": dict(sorted(strict_counts.items())),
        "timestamp_verified_bundle_counts_by_window": dict(sorted(bundle_counts.items())),
        "strict_lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "touch_floor": 5,
        "all_fixed_window_touch_floors_pass": touch_floor_pass,
        "exclusion_counts": dict(sorted(exclusions.items())),
        "policy": {
            "distribution": "pure recurring, positive USD cash, frequency > 0",
            "lifecycle": "explicit recurring initiation or resumption in SEC public text",
            "clock": (
                "first regular-session open strictly after both SEC accepted_at "
                "and declaration-date New York close"
            ),
            "coannouncement": (
                "exclude earnings, guidance, strategic/management actions and new repurchase programs"
            ),
            "horizon": "entry open through tenth session close",
            "trade_enabled": False,
            "live_ready": False,
        },
        "strict_clean_rows": accepted,
        "timestamp_verified_bundle_rows": timestamp_verified_bundles,
        "filing_assessments": assessments,
        "next_machine_action": (
            "build_d0_d3_candidate" if touch_floor_pass else "park_strict_clean_lane"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an outcome-blind, SEC-timestamped recurring-dividend preflight."
    )
    parser.add_argument(
        "--database",
        default=str(REPO_ROOT / "data" / "warehouse" / "massive_history.sqlite"),
    )
    parser.add_argument(
        "--endpoint-preflight",
        default=str(
            REPO_ROOT
            / "data"
            / "alpha_search"
            / "massive_dividend_restart_endpoint_preflight_v1_20260731.json"
        ),
    )
    parser.add_argument(
        "--sec-text",
        default=str(
            REPO_ROOT
            / "data"
            / "alpha_search"
            / "dividend_recurring_sec_text_near_declaration_20260801.jsonl"
        ),
    )
    parser.add_argument(
        "--output",
        default=str(
            REPO_ROOT
            / "data"
            / "alpha_search"
            / "dividend_recurring_public_timestamp_preflight_20260801.json"
        ),
    )
    args = parser.parse_args(argv)
    output = Path(args.output)
    payload = build_preflight(
        database=Path(args.database),
        endpoint_preflight=Path(args.endpoint_preflight),
        sec_text=Path(args.sec_text),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "all_fixed_window_touch_floors_pass": payload[
                    "all_fixed_window_touch_floors_pass"
                ],
                "next_machine_action": payload["next_machine_action"],
                "pure_recurring_count": payload["pure_recurring_count"],
                "strict_clean_count": payload["strict_clean_count"],
                "strict_counts_by_window": payload["strict_counts_by_window"],
                "timestamp_verified_bundle_count": payload[
                    "timestamp_verified_bundle_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
