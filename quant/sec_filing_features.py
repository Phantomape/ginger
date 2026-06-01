"""SEC filing feature adapter for shadow filing-shock research.

This module derives replayable financial-shock fields from public SEC filing
metadata and selected Companyfacts rows. It never treats period_end_date as a
tradable date; PIT eligibility comes only from accepted_at/usable_trade_date.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = REPO_ROOT / "data"
DEFAULT_NON_OHLCV_DIR = DEFAULT_DATA_ROOT / "non_ohlcv"
DEFAULT_COMPANYFACTS_GLOB = "sec_companyfacts_selected_*.jsonl"


def build_daily_filing_features(
    date_key: str,
    *,
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
    companyfacts_path: str | Path | None = None,
) -> dict[str, Any]:
    data_root_path = Path(data_root or DEFAULT_DATA_ROOT)
    non_root = Path(non_ohlcv_dir or data_root_path / "non_ohlcv")
    if companyfacts_path is None:
        companyfacts_path = discover_companyfacts_path(data_root_path, non_root)
    filings_path = non_root / f"sec_filing_text_{date_key}.jsonl"
    if not filings_path.exists():
        filings_path = non_root / f"sec_filing_events_{date_key}.jsonl"
    output = non_root / f"sec_filing_features_{date_key}.jsonl"
    summary_output = non_root / f"sec_filing_features_summary_{date_key}.json"
    return build_filing_feature_file(
        filings_path=filings_path,
        companyfacts_path=companyfacts_path,
        output_path=output,
        summary_path=summary_output,
    )


def discover_companyfacts_path(
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
) -> Path | None:
    """Return the latest selected Companyfacts JSONL available in the repo."""
    data_root_path = Path(data_root or DEFAULT_DATA_ROOT)
    non_root = Path(non_ohlcv_dir or data_root_path / "non_ohlcv")
    candidates = [
        path for path in non_root.glob(DEFAULT_COMPANYFACTS_GLOB)
        if path.is_file() and path.stat().st_size > 0
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: (path.stat().st_mtime, path.name))[-1]


def build_filing_feature_file(
    *,
    filings_path: str | Path,
    companyfacts_path: str | Path | None,
    output_path: str | Path,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    filings = load_jsonl(filings_path)
    fact_rows = load_jsonl(companyfacts_path) if companyfacts_path else []
    rows = build_filing_feature_rows(filings, fact_rows)
    write_jsonl(output_path, rows)
    summary = {
        "schema_version": 1,
        "filings_path": _path_text(Path(filings_path)),
        "companyfacts_path": _path_text(Path(companyfacts_path)) if companyfacts_path else None,
        "output_path": _path_text(Path(output_path)),
        "rows_written": len(rows),
        "pit_safe_rows": sum(1 for row in rows if row.get("pit_safe")),
        "rows_with_same_accession_facts": sum(
            1 for row in rows
            if row.get("field_availability", {}).get("same_accession_facts") == "derived"
        ),
        "field_counts": _field_counts(rows),
        "pit_caveat": (
            "accepted_at/usable_trade_date gate event tradability; Companyfacts filed date "
            "is only a public-availability proxy for historical replay."
        ),
    }
    if summary_path:
        write_json(summary_path, summary)
    return summary


def build_filing_feature_rows(
    filings: list[dict[str, Any]],
    fact_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    facts_by_ticker = _facts_by_ticker(fact_rows)
    out = []
    for filing in filings:
        if not isinstance(filing, dict):
            continue
        ticker = str(filing.get("ticker") or "").upper()
        accepted_at = filing.get("accepted_at") or filing.get("accepted_datetime")
        usable_trade_date = filing.get("usable_trade_date")
        accession = filing.get("accession_number")
        ticker_facts = facts_by_ticker.get(ticker, [])
        accession_facts = [
            row for row in ticker_facts
            if accession and _same_accession(row.get("accession_number"), accession)
        ]
        current = _latest_values(accession_facts)
        prior = _prior_values(ticker_facts, current.get("fiscal_period_end"), accepted_at)

        gross_margin = _ratio(current.get("gross_profit"), current.get("revenue"))
        prior_gross_margin = _ratio(prior.get("gross_profit"), prior.get("revenue"))
        fcf = _fcf(current)
        fcf_to_net_income_gap = _ratio(
            None if fcf is None or current.get("net_income") is None else fcf - current.get("net_income"),
            abs(current.get("net_income")) if current.get("net_income") is not None else None,
        )

        pit_safe = bool(accepted_at and usable_trade_date)
        form_type = filing.get("form_type") or filing.get("form")
        eight_k_item = _eight_k_item_type(filing)
        source_credibility_bucket = _source_credibility_bucket(form_type, eight_k_item)
        text_direction = filing.get("text_direction") or filing.get("text_sentiment")
        price_direction = filing.get("price_direction") or filing.get("day_price_direction")
        text_direction_vs_price_bucket = _text_direction_vs_price_bucket(
            text_direction, price_direction
        )
        eps_surprise = filing.get("eps_surprise")
        volume_ratio = filing.get("volume_ratio") or filing.get("volume_ratio_20d")
        predictability_mosaic_bucket = _predictability_mosaic_bucket(
            eps_surprise=eps_surprise,
            gross_margin=gross_margin,
            volume_ratio=volume_ratio,
        )
        low_volume_predictability_bucket = _low_volume_predictability_bucket(volume_ratio)

        row = {
            "schema_version": 1,
            "ticker": ticker or None,
            "event_date": usable_trade_date,
            "usable_trade_date": usable_trade_date,
            "form_type": form_type,
            "accepted_datetime": accepted_at,
            "filing_date": filing.get("filing_date"),
            "source_accession": accession,
            "fiscal_period_end": current.get("fiscal_period_end") or filing.get("period_end_date"),
            "eps_surprise": None,
            "revenue_surprise": None,
            "gross_margin_delta": _diff(gross_margin, prior_gross_margin),
            "fcf_to_net_income_gap": fcf_to_net_income_gap,
            "inventory_growth": _growth(current.get("inventory"), prior.get("inventory")),
            "receivables_growth": _growth(current.get("receivables"), prior.get("receivables")),
            "guidance_raise_cut": None,
            "eight_k_item_type": eight_k_item,
            # --- Read-only attribution sidecars (exp-20260531-027) ---
            "source_credibility_bucket": source_credibility_bucket,
            "text_direction_vs_price_bucket": text_direction_vs_price_bucket,
            # --- Read-only attribution sidecars (exp-20260531-028) ---
            "predictability_mosaic_bucket": predictability_mosaic_bucket,
            "low_volume_predictability_bucket": low_volume_predictability_bucket,
            # --------------------------------------------------------
            "data_source": "sec_filing_text_plus_companyfacts",
            "pit_safe": pit_safe,
            "field_availability": {
                "accepted_datetime": "observed" if accepted_at else "missing",
                "usable_trade_date": "observed" if usable_trade_date else "missing",
                "same_accession_facts": "derived" if accession_facts else "missing",
                "eps_surprise": "missing_no_vendor_consensus",
                "revenue_surprise": "missing_no_vendor_consensus",
                "gross_margin_delta": _state(_diff(gross_margin, prior_gross_margin)),
                "fcf_to_net_income_gap": _state(fcf_to_net_income_gap),
                "inventory_growth": _state(_growth(current.get("inventory"), prior.get("inventory"))),
                "receivables_growth": _state(_growth(current.get("receivables"), prior.get("receivables"))),
                "guidance_raise_cut": "missing_no_structured_guidance_source",
                "source_credibility_bucket": "derived" if source_credibility_bucket else "missing",
                "text_direction_vs_price_bucket": "derived" if text_direction_vs_price_bucket else "missing",
                "predictability_mosaic_bucket": "derived" if predictability_mosaic_bucket else "missing",
                "low_volume_predictability_bucket": "derived" if low_volume_predictability_bucket else "missing",
            },
            "gap_reasons": _gap_reasons(
                accepted_at=accepted_at,
                usable_trade_date=usable_trade_date,
                accession_facts=accession_facts,
            ),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_orders": False,
            },
        }
        out.append(row)
    return sorted(
        out,
        key=lambda row: (
            row.get("usable_trade_date") or "",
            row.get("ticker") or "",
            row.get("source_accession") or "",
        ),
    )


def load_jsonl(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    source = Path(path)
    if not source.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _facts_by_ticker(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out.setdefault(ticker, []).append(row)
    for ticker in out:
        out[ticker] = sorted(
            out[ticker],
            key=lambda row: (
                str(row.get("filed") or ""),
                str(row.get("end") or ""),
                str(row.get("canonical") or ""),
            ),
        )
    return out


def _same_accession(left: Any, right: Any) -> bool:
    return str(left or "").replace("-", "") == str(right or "").replace("-", "")


def _latest_values(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    fiscal_period_end = None
    for row in sorted(rows, key=lambda item: str(item.get("end") or "")):
        canonical = row.get("canonical")
        if canonical:
            values[str(canonical)] = _float_or_none(row.get("value"))
        end = row.get("end")
        if end and (fiscal_period_end is None or str(end) > fiscal_period_end):
            fiscal_period_end = str(end)
    values["fiscal_period_end"] = fiscal_period_end
    return values


def _prior_values(
    rows: list[dict[str, Any]],
    current_period_end: Any,
    accepted_at: Any,
) -> dict[str, Any]:
    if not current_period_end:
        return {}
    accepted_date = str(accepted_at or "")[:10]
    candidates = [
        row for row in rows
        if str(row.get("end") or "") < str(current_period_end)
        and (not accepted_date or str(row.get("filed") or "") <= accepted_date)
    ]
    if not candidates:
        return {}
    latest_end = max(str(row.get("end") or "") for row in candidates)
    return _latest_values([row for row in candidates if str(row.get("end") or "") == latest_end])


def _fcf(values: dict[str, Any]) -> float | None:
    ocf = values.get("operating_cash_flow")
    capex = values.get("capex")
    if ocf is None or capex is None:
        return None
    return float(ocf) - abs(float(capex))


def _ratio(num: Any, den: Any) -> float | None:
    num_f = _float_or_none(num)
    den_f = _float_or_none(den)
    if num_f is None or den_f is None or den_f == 0:
        return None
    value = num_f / den_f
    return round(value, 6) if math.isfinite(value) else None


def _diff(current: Any, prior: Any) -> float | None:
    cur = _float_or_none(current)
    prev = _float_or_none(prior)
    if cur is None or prev is None:
        return None
    return round(cur - prev, 6)


def _growth(current: Any, prior: Any) -> float | None:
    cur = _float_or_none(current)
    prev = _float_or_none(prior)
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev), 6)


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = float(value)
        if math.isfinite(value):
            return value
    return None


def _state(value: Any) -> str:
    return "derived" if value is not None else "missing"


def _predictability_mosaic_bucket(
    *,
    eps_surprise: Any,
    gross_margin: Any,
    volume_ratio: Any,
) -> str | None:
    """Read-only attribution: composite earnings-quality predictability score.

    Combines three independently-observable signals (exp-20260531-028 sidecar):
      - Large earnings surprise (|eps_surprise| >= 0.10, i.e. >=10% beat/miss)
      - High earnings quality (gross_margin >= 0.40, proxy for pricing power)
      - Low relative volume (volume_ratio <= 0.80, quiet market = less noise)

    Buckets:
      high   - all three signals present
      medium - two of three signals present
      low    - one signal present
      none   - zero signals present or all inputs missing
      missing - not enough data to classify (eps_surprise and gross_margin both None)
    """
    if eps_surprise is None and gross_margin is None:
        return "missing"
    signals = 0
    eps_f = _float_or_none(eps_surprise)
    if eps_f is not None and abs(eps_f) >= 0.10:
        signals += 1
    gm_f = _float_or_none(gross_margin)
    if gm_f is not None and gm_f >= 0.40:
        signals += 1
    vr_f = _float_or_none(volume_ratio)
    if vr_f is not None and vr_f <= 0.80:
        signals += 1
    if signals == 3:
        return "high"
    if signals == 2:
        return "medium"
    if signals == 1:
        return "low"
    return "none"


def _low_volume_predictability_bucket(volume_ratio: Any) -> str | None:
    """Read-only attribution: low-volume regime predictability marker.

    Buckets (exp-20260531-028 sidecar — does not alter any trade logic):
      very_low  - volume_ratio <= 0.50 (unusually quiet)
      low       - volume_ratio <= 0.80
      normal    - volume_ratio <= 1.30
      elevated  - volume_ratio > 1.30
      missing   - volume_ratio not available
    """
    vr_f = _float_or_none(volume_ratio)
    if vr_f is None:
        return "missing"
    if vr_f <= 0.50:
        return "very_low"
    if vr_f <= 0.80:
        return "low"
    if vr_f <= 1.30:
        return "normal"
    return "elevated"


def _source_credibility_bucket(form_type: Any, eight_k_item_type: Any) -> str | None:
    """Read-only attribution: classify filing source credibility.

    Buckets (exp-20260531-027 sidecar — does not alter any trade logic):
      high    - 10-K, 10-Q (annual/quarterly reports with auditor review)
      medium  - 8-K with earnings item (2.02) or guidance (2.05)
      low     - 8-K other items, DEF 14A, S-1, other
      unknown - form_type unavailable
    """
    if not form_type:
        return "unknown"
    ft = str(form_type).upper().strip()
    if ft in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
        return "high"
    if ft in ("8-K", "8-K/A"):
        item = str(eight_k_item_type or "").strip()
        # Item 2.02 = results of operations (earnings); 2.05 = material charge/guidance
        if "2.02" in item or "2.05" in item:
            return "medium"
        # Item 7.01/8.01 = voluntary disclosure (press release)
        if "7.01" in item or "8.01" in item:
            return "low_voluntary"
        return "low"
    if ft in ("DEF 14A", "DEF14A", "S-1", "S-1/A", "424B4"):
        return "low"
    return "low"


def _text_direction_vs_price_bucket(
    text_direction: Any, price_direction: Any
) -> str | None:
    """Read-only attribution: classify agreement between SEC text direction and price direction.

    Buckets (exp-20260531-027 sidecar — does not alter any trade logic):
      agrees_positive   - text positive AND price positive
      agrees_negative   - text negative AND price negative
      disagrees_pos_neg - text positive but price negative (bearish divergence)
      disagrees_neg_pos - text negative but price positive (bullish divergence)
      neutral_text      - text neutral (no directional signal)
      missing           - one or both inputs unavailable
    """
    if not text_direction or not price_direction:
        return "missing"
    td = str(text_direction).lower().strip()
    pd = str(price_direction).lower().strip()

    text_pos = td in ("positive", "bullish", "pos", "up")
    text_neg = td in ("negative", "bearish", "neg", "down")
    price_pos = pd in ("positive", "up", "pos", "bullish")
    price_neg = pd in ("negative", "down", "neg", "bearish")

    if not text_pos and not text_neg:
        return "neutral_text"
    if text_pos and price_pos:
        return "agrees_positive"
    if text_neg and price_neg:
        return "agrees_negative"
    if text_pos and price_neg:
        return "disagrees_pos_neg"
    if text_neg and price_pos:
        return "disagrees_neg_pos"
    return "missing"


def _eight_k_item_type(filing: dict[str, Any]) -> str | None:
    codes = filing.get("eight_k_item_codes")
    if isinstance(codes, list) and codes:
        return ",".join(str(code) for code in codes)
    value = filing.get("eight_k_item_type") or filing.get("item_type")
    return str(value) if value else None


def _gap_reasons(
    *,
    accepted_at: Any,
    usable_trade_date: Any,
    accession_facts: list[dict[str, Any]],
) -> list[str]:
    reasons = []
    if not accepted_at:
        reasons.append("missing_accepted_datetime")
    if not usable_trade_date:
        reasons.append("missing_usable_trade_date")
    if not accession_facts:
        reasons.append("missing_same_accession_companyfacts")
    reasons.append("eps_and_revenue_surprise_require_pit_consensus_vendor")
    reasons.append("guidance_raise_cut_requires_structured_guidance_source")
    return reasons


def _field_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    fields = (
        "gross_margin_delta",
        "fcf_to_net_income_gap",
        "inventory_growth",
        "receivables_growth",
        "source_credibility_bucket",
        "text_direction_vs_price_bucket",
        "predictability_mosaic_bucket",
        "low_volume_predictability_bucket",
    )
    return {
        field: sum(1 for row in rows if row.get(field) is not None)
        for field in fields
    }


def _path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build SEC filing feature rows.")
    parser.add_argument("--filings", required=True)
    parser.add_argument("--companyfacts", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", default=None)
    args = parser.parse_args(argv)
    summary = build_filing_feature_file(
        filings_path=args.filings,
        companyfacts_path=args.companyfacts,
        output_path=args.output,
        summary_path=args.summary_output,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
