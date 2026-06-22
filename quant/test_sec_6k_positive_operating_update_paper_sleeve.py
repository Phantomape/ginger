from __future__ import annotations

from datetime import date, timedelta

from quant.sec_6k_positive_operating_update_paper_sleeve import (
    build_sec_6k_positive_operating_update_snapshot,
    classify_positive_operating_update,
)


def test_classifies_positive_6k_operating_update() -> None:
    text = (
        "Foreign issuer furnished quarterly financial results. Revenue increased "
        "24% year over year, operating profit improved, and management raised "
        "full-year revenue guidance based on strong customer demand. "
    ) * 12

    event = classify_positive_operating_update(text)

    assert event is not None
    assert event["operating_update_strength"] > 1.0
    assert "revenue" in event["operating_context_terms"]
    assert event["outlook_raise_terms"]


def test_excludes_financing_6k_text() -> None:
    text = (
        "The company announced a cash tender offer for senior notes and debt "
        "securities. Revenue is mentioned only in risk factor background, while "
        "the filing describes an indenture and exchange offer. "
    ) * 15

    assert classify_positive_operating_update(text) is None


def test_daily_snapshot_uses_same_candidate_semantics() -> None:
    start = date(2026, 1, 1)
    ohlcv = {
        "SPY": _series(start, 90, base=100.0, step=0.02),
        "ADR": _series(start, 90, base=80.0, step=0.18),
    }
    signal_day = (start + timedelta(days=70)).isoformat()
    rows = [
        {
            "ticker": "ADR",
            "date": signal_day,
            "usable_trade_date": signal_day,
            "filing_date": signal_day,
            "accepted_at": f"{signal_day}T12:00:00",
            "accession_number": "0000000000-26-000001",
            "form_type": "6-K",
            "form_base": "6-K",
            "combined_text": (
                "Form 6-K operating update. Revenue increased 18%, gross profit "
                "improved, and the company raised full-year outlook after stronger "
                "deliveries and customer demand. "
            )
            * 12,
        }
    ]

    snapshot = build_sec_6k_positive_operating_update_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        sec_text_rows=rows,
    )

    assert snapshot["trade_enabled"] is False
    assert snapshot["candidate_count"] == 1
    candidate = snapshot["candidates"][0]
    assert candidate["ticker"] == "ADR"
    assert candidate["rule_version"] == "sec_6k_positive_operating_update_candidate_source_v1"
    assert candidate["uses_free_sec_filing_text"] is True


def test_daily_snapshot_rejects_raw_financing_text() -> None:
    start = date(2026, 1, 1)
    ohlcv = {
        "SPY": _series(start, 90, base=100.0, step=0.02),
        "ADR": _series(start, 90, base=80.0, step=0.18),
    }
    signal_day = (start + timedelta(days=70)).isoformat()

    snapshot = build_sec_6k_positive_operating_update_snapshot(
        as_of=signal_day,
        ohlcv_by_ticker=ohlcv,
        sec_text_rows=[
            {
                "ticker": "ADR",
                "usable_trade_date": signal_day,
                "filing_date": signal_day,
                "accession_number": "0000000000-26-000002",
                "form_type": "6-K",
                "combined_text": (
                    "The issuer announced a tender offer for senior notes and debt "
                    "securities. Revenue appears only in background risk language. "
                )
                * 20,
            }
        ],
    )

    assert snapshot["candidate_count"] == 0
    assert snapshot["quality_index_summary"]["sec_6k_text_rows_loaded"] == 0


def _series(start: date, days: int, *, base: float, step: float) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for index in range(days):
        current = base + step * index
        rows.append(
            {
                "Date": (start + timedelta(days=index)).isoformat(),
                "Open": round(current * 0.999, 4),
                "High": round(current * 1.01, 4),
                "Low": round(current * 0.99, 4),
                "Close": round(current, 4),
                "Volume": 1_000_000,
            }
        )
    return rows
