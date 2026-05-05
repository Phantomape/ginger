from __future__ import annotations

import json
from pathlib import Path

from non_ohlcv_shadow_events import (
    combine_filing_shock_tables,
    load_filing_shock_rows,
    validate_filing_shock_rows,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")


def _row(**overrides):
    row = {
        "ticker": "ABC",
        "event_date": "2026-05-01",
        "usable_trade_date": "2026-05-04",
        "form_type": "8-K",
        "accepted_datetime": "2026-05-01T17:00:00-04:00",
        "fiscal_period_end": None,
        "eps_surprise": None,
        "revenue_surprise": None,
        "gross_margin_delta": None,
        "fcf_to_net_income_gap": None,
        "inventory_growth": None,
        "receivables_growth": None,
        "guidance_raise_cut": None,
        "eight_k_item_type": [{"code": "2.02"}],
        "data_source": "data/news_20260502.json",
        "pit_safe": True,
        "source_url": "https://www.sec.gov/Archives/edgar/data/1/0001-index.htm",
    }
    row.update(overrides)
    return row


def test_reused_manifest_resolves_source_shadow_table(tmp_path: Path):
    source = tmp_path / "source.json"
    manifest = tmp_path / "manifest.json"
    _write_json(source, {"schema_version": 1, "rows": [_row()]})
    _write_json(
        manifest,
        {
            "schema_version": 1,
            "table_mode": "reused_manifest",
            "source_shadow_table": str(source),
            "row_count": 1,
        },
    )

    rows = load_filing_shock_rows(manifest)

    assert len(rows) == 1
    assert rows[0]["ticker"] == "ABC"


def test_combine_dedupes_manifest_and_source_table(tmp_path: Path):
    source = tmp_path / "source.json"
    manifest = tmp_path / "manifest.json"
    _write_json(source, {"schema_version": 1, "rows": [_row()]})
    _write_json(manifest, {"schema_version": 1, "source_shadow_table": str(source)})

    rows = combine_filing_shock_tables([source, manifest])
    validation = validate_filing_shock_rows(rows)

    assert len(rows) == 1
    assert validation["schema_compatible"] is True
    assert validation["duplicate_key_count"] == 0


def test_combine_prefers_more_complete_duplicate(tmp_path: Path):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    _write_json(old, {"schema_version": 1, "rows": [_row(revenue_surprise=None)]})
    _write_json(new, {"schema_version": 1, "rows": [_row(revenue_surprise=0.12)]})

    rows = combine_filing_shock_tables([old, new])

    assert len(rows) == 1
    assert rows[0]["revenue_surprise"] == 0.12


def test_loader_accepts_utf8_bom_row_table(tmp_path: Path):
    source = tmp_path / "bom.json"
    source.write_text(
        "\ufeff" + json.dumps({"schema_version": 1, "rows": [_row()]}) + "\n",
        encoding="utf-8",
    )

    rows = load_filing_shock_rows(source)

    assert len(rows) == 1
    assert rows[0]["ticker"] == "ABC"
