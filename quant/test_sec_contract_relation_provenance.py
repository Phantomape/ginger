import json
from pathlib import Path

from sec_contract_relation_provenance import (
    build_rows_from_record,
    build_surface_from_paths,
    extract_contract_economics,
    persist_sec_contract_relation_provenance,
    relation_evidence,
    write_full_surface,
)


def _record(text, *, accession="0000000000-26-000001", codes=None):
    return {
        "ticker": "EXM",
        "cik": "0000000001",
        "accession_number": accession,
        "form_type": "8-K",
        "form_base": "8-K",
        "filing_date": "2026-07-02",
        "usable_trade_date": "2026-07-03",
        "accepted_at": "2026-07-02T16:30:00",
        "eight_k_item_codes": codes or ["1.01", "9.01"],
        "primary_document": "example-8k.htm",
        "combined_text": text,
        "text_char_count": len(text),
        "text_word_count": len(text.split()),
    }


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_relation_evidence_extracts_specific_buckets_and_counterparty():
    evidence = relation_evidence(
        "Item 1.01 Entry into a Material Definitive Agreement. "
        "The Company entered into a Master Supply Agreement with CoreWeave, Inc. "
        "for data center capacity and related services."
    )

    assert "supplier_or_supply_contract" in evidence
    assert "general_material_agreement" not in evidence
    snippets = evidence["supplier_or_supply_contract"]
    assert any("Master Supply Agreement" in item["snippet"] for item in snippets)
    assert any(
        "CoreWeave" in candidate
        for item in snippets
        for candidate in item["counterparty_candidates"]
    )


def test_build_rows_filters_item_101_and_records_observer_only_contract():
    rows = build_rows_from_record(
        _record(
            "Item 1.01. The registrant entered into a Customer Agreement with "
            "Acme Cloud LLC for $120 million. The agreement has a term of 5 years. "
            "Item 9.01 Financial Statements and Exhibits."
        ),
        source_path=Path("data/non_ohlcv/sec_filing_text_20260702.jsonl"),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["relation_bucket"] == "customer_or_revenue_contract"
    assert row["relation_quality"] == "specific_relation_phrase"
    assert row["observer_only"] is True
    assert row["strategy_behavior_changed"] is False
    assert row["trade_enabled"] is False
    assert row["alters_orders"] is False
    assert row["usable_trade_date"] == "2026-07-03"
    assert row["counterparty_candidates"]
    assert row["economic_terms_bucket"] == "amount_or_duration"
    assert row["economic_terms_detail_bucket"] == "amount_and_duration"
    assert row["contract_amount_count"] == 1
    assert row["contract_duration_count"] == 1
    assert row["normalized_counterparty_count"] >= 1


def test_build_rows_keeps_generic_only_when_no_specific_phrase():
    rows = build_rows_from_record(
        _record(
            "Item 1.01 Entry into a Material Definitive Agreement. "
            "On July 2, the Company entered into an agreement."
        )
    )

    assert [row["relation_bucket"] for row in rows] == ["general_material_agreement"]
    assert rows[0]["relation_quality"] == "generic_agreement_only"


def test_contract_economics_labels_named_counterparty_without_amount_or_duration():
    rows = build_rows_from_record(
        _record(
            "Item 1.01. The Company signed a Supply Agreement with Vendor Inc."
        )
    )

    economics = extract_contract_economics(rows[0])
    assert economics["economic_terms_bucket"] == "no_amount_or_duration"
    assert economics["economic_terms_detail_bucket"] == "named_counterparty_only"
    assert economics["has_named_counterparty"] is True
    assert economics["has_contract_amount"] is False
    assert economics["has_contract_duration"] is False


def test_build_surface_and_full_write_are_deterministic(tmp_path):
    source = tmp_path / "data" / "non_ohlcv" / "sec_filing_text_20260702.jsonl"
    _write_jsonl(
        source,
        [
            _record(
                "Item 1.01. The Company signed a Supply Agreement with Vendor Inc. "
                "The purchase commitment is USD 75 million.",
                accession="0000000000-26-000001",
            ),
            _record(
                "Item 5.02. Compensation only.",
                accession="0000000000-26-000002",
                codes=["5.02"],
            ),
        ],
    )

    rows, summary = build_surface_from_paths([source])
    assert summary["input_row_count"] == 2
    assert summary["item_101_input_row_count"] == 1
    assert summary["provenance_row_count"] == 1
    assert summary["specific_relation_row_count"] == 1

    manifest = write_full_surface(rows, summary, data_dir=tmp_path / "data")
    rows_path = tmp_path / "data" / "non_ohlcv" / "sec_contract_relation_provenance" / "rows.jsonl"
    assert rows_path.exists()
    assert manifest["provenance_row_count"] == 1
    row = json.loads(rows_path.read_text(encoding="utf-8").strip())
    assert row["relation_bucket"] == "supplier_or_supply_contract"
    assert row["economic_terms_bucket"] == "amount_or_duration"
    assert manifest["contract_amount_row_count"] == 1
    assert manifest["economic_terms_bucket_counts"] == {"amount_or_duration": 1}


def test_persist_daily_appends_idempotently_and_writes_fail_soft_manifest(tmp_path):
    data_dir = tmp_path / "data"
    source = data_dir / "non_ohlcv" / "sec_filing_text_20260703.jsonl"
    _write_jsonl(
        source,
        [
            _record(
                "Item 1.01. The Company entered into a Credit Agreement with Big Bank N.A. "
                "The facility provides $50 million and expires on July 1, 2028.",
                accession="0000000000-26-000003",
            )
        ],
    )

    summary = persist_sec_contract_relation_provenance("20260703", data_dir=data_dir)
    assert summary["status"] == "ok"
    assert summary["rows_appended"] == 1
    assert summary["provenance_row_count"] == 1
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
    assert summary["contract_amount_row_count"] == 1
    assert summary["contract_duration_row_count"] == 1
    assert summary["economic_terms_bucket_counts"] == {"amount_or_duration": 1}

    second = persist_sec_contract_relation_provenance("20260703", data_dir=data_dir)
    assert second["rows_appended"] == 0

    base = data_dir / "non_ohlcv" / "sec_contract_relation_provenance"
    assert (base / "rows.jsonl").exists()
    assert (base / "manifest.json").exists()
    assert (base / "daily" / "sec_contract_relation_provenance_20260703.jsonl").exists()
    assert (
        base / "daily" / "sec_contract_relation_provenance_summary_20260703.json"
    ).exists()
    daily_row = json.loads(
        (base / "daily" / "sec_contract_relation_provenance_20260703.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert daily_row["economic_terms_detail_bucket"] == "amount_and_duration"


def test_persist_daily_missing_source_is_observer_only(tmp_path):
    summary = persist_sec_contract_relation_provenance("20260703", data_dir=tmp_path / "data")

    assert summary["status"] == "missing_source"
    assert summary["provenance_row_count"] == 0
    assert summary["strategy_behavior_changed"] is False
    assert summary["trade_enabled"] is False
