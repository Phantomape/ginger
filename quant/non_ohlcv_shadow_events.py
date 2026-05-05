from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

FILING_SHOCK_REQUIRED_COLUMNS = (
    "ticker",
    "event_date",
    "usable_trade_date",
    "form_type",
    "accepted_datetime",
    "fiscal_period_end",
    "eps_surprise",
    "revenue_surprise",
    "gross_margin_delta",
    "fcf_to_net_income_gap",
    "inventory_growth",
    "receivables_growth",
    "guidance_raise_cut",
    "eight_k_item_type",
    "data_source",
    "pit_safe",
)


def load_filing_shock_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load a filing-shock row table, resolving reused-manifest files."""

    return _load_filing_shock_rows(Path(path), seen=set())


def combine_filing_shock_tables(paths: list[str | Path]) -> list[dict[str, Any]]:
    """Combine filing-shock tables/manifests without double-counting overlaps."""

    deduped: dict[tuple[str, ...], dict[str, Any]] = {}
    for path in paths:
        for row in load_filing_shock_rows(path):
            key = filing_shock_event_key(row)
            previous = deduped.get(key)
            if previous is None or _row_completeness(row) >= _row_completeness(previous):
                deduped[key] = row
    return sorted(
        deduped.values(),
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("accepted_datetime") or ""),
            str(row.get("source_url") or ""),
        ),
    )


def filing_shock_event_key(row: dict[str, Any]) -> tuple[str, ...]:
    """Return a stable key for one SEC filing-shock shadow event row."""

    return (
        str(row.get("ticker") or "").upper(),
        str(row.get("event_date") or "")[:10],
        str(row.get("accepted_datetime") or ""),
        str(row.get("form_type") or "").upper(),
        str(row.get("source_url") or row.get("accession_number") or ""),
    )


def validate_filing_shock_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_by_column = {
        column: sum(1 for row in rows if column not in row)
        for column in FILING_SHOCK_REQUIRED_COLUMNS
    }
    null_by_column = {
        column: sum(1 for row in rows if row.get(column) is None)
        for column in FILING_SHOCK_REQUIRED_COLUMNS
    }
    return {
        "row_count": len(rows),
        "missing_by_column": missing_by_column,
        "null_by_column": null_by_column,
        "schema_compatible": all(count == 0 for count in missing_by_column.values()),
        "duplicate_key_count": len(rows) - len({filing_shock_event_key(row) for row in rows}),
    }


def _load_filing_shock_rows(path: Path, *, seen: set[Path]) -> list[dict[str, Any]]:
    resolved = path.resolve()
    if resolved in seen:
        raise ValueError(f"Cycle detected while resolving filing-shock manifest: {path}")
    seen.add(resolved)

    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]

    source = payload.get("source_shadow_table") if isinstance(payload, dict) else None
    if source:
        return _load_filing_shock_rows(
            _resolve_manifest_path(source, manifest_path=resolved),
            seen=seen,
        )

    raise ValueError(f"{path} is neither a filing-shock row table nor a reused manifest")


def _resolve_manifest_path(value: Any, *, manifest_path: Path) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    repo_path = REPO_ROOT / path
    if repo_path.exists():
        return repo_path
    sibling_path = manifest_path.parent / path
    if sibling_path.exists():
        return sibling_path
    return repo_path


def _row_completeness(row: dict[str, Any]) -> int:
    return sum(1 for column in FILING_SHOCK_REQUIRED_COLUMNS if row.get(column) is not None)
