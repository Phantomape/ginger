"""exp-20260605-007: Broad 1446-universe SEC Companyfacts realized-fundamentals
data asset + coverage audit.

Lane: measurement_repair (read-only data asset build).
Change type: read_only_broad_universe_companyfacts_data_asset_build.

Why this experiment exists
--------------------------
yfinance ``eps_estimate`` is sparse (~50 curated names, ~0 on the broad
universe) and quality-contaminated (annual/quarterly mixup, backfilled
history). SEC Companyfacts realized fundamentals are free, PIT-safe
(filing-date), and -- verified via a 6/6 POC on non-curated small/mid caps
-- available with rich XBRL history across the broad universe. This builds
the broad asset that the existing FUNDAMENTAL_GROWTH_RS line only runs on
~40 names.

What it does (read-only)
------------------------
For the 1,446 ``all_windows_full_liquid`` tickers in the
``exp-20260519-030`` warehouse:
1. fetch each CIK's Companyfacts (cached, SEC-compliant 0.11s sleep) and
   map XBRL concepts to canonical revenue / eps_basic / eps_diluted /
   net_income facts (``sec_companyfacts_backfill.iter_selected_fact_rows``);
2. derive PIT-safe YoY growth rows
   (``kova_data_sidecar.derive_companyfacts_growth_rows``) as of the run
   date;
3. write the dataset jsonl + a coverage-audit json (per-ticker usable
   metrics, growth_status counts, the tickers with no usable fundamentals).

It changes no entries, exits, ranking, sizing, paper sleeves, or orders.
It only produces a data asset and an audit, documented in
``docs/data_inventory.md``.

No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT / "quant"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sec_companyfacts_backfill import (  # noqa: E402
    DEFAULT_FORMS,
    DEFAULT_USER_AGENT,
    fetch_companyfacts,
    iter_selected_fact_rows,
)
from kova_data_sidecar import derive_companyfacts_growth_rows  # noqa: E402
from sec_ticker_map import normalize_cik  # noqa: E402

WAREHOUSE = REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"
OUT_DIR = REPO_ROOT / "data" / "kova" / "fundamentals"
EXP_DIR = REPO_ROOT / "data" / "experiments" / "exp-20260605-007"

EXPERIMENT_ID = "exp-20260605-007"
MIN_PERIOD_END = "2023-01-01"   # gather >= ~2 fiscal years for YoY
FUNDAMENTAL_CANONICALS = ("revenue", "eps_basic", "eps_diluted", "net_income")


def load_universe(db_path: Path = WAREHOUSE) -> list[tuple[str, str]]:
    """Return [(ticker, cik)] for the all_windows_full_liquid universe."""
    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "select tu.ticker, tu.cik from coverage_summary cs "
        "join ticker_universe tu on cs.ticker = tu.ticker "
        "where cs.all_windows_full_liquid = 1"
    ).fetchall()
    con.close()
    out = []
    for ticker, cik in rows:
        cik_norm = normalize_cik(cik)
        if ticker and cik_norm:
            out.append((str(ticker).upper(), cik_norm))
    return sorted(set(out))


def run(
    *,
    output: Path | None = None,
    audit_output: Path | None = None,
    asof: str | None = None,
    limit: int | None = None,
    sleep_seconds: float = 0.11,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    asof = asof or date.today().isoformat()
    tag = asof.replace("-", "")
    output = output or (OUT_DIR / f"companyfacts_growth_broad_universe_{tag}.jsonl")
    audit_output = audit_output or (EXP_DIR / "broad_universe_companyfacts_coverage_audit.json")

    universe = load_universe()
    if limit:
        universe = universe[:limit]

    t0 = time.time()
    all_fact_rows: list[dict[str, Any]] = []
    per_ticker_facts: dict[str, int] = {}
    errors: list[dict[str, str]] = []
    for ticker, cik in universe:
        try:
            payload = fetch_companyfacts(
                cik, user_agent=user_agent, sleep_seconds=sleep_seconds
            )
            rows = iter_selected_fact_rows(
                payload,
                ticker=ticker,
                cik=cik,
                forms=DEFAULT_FORMS,
                min_period_end=MIN_PERIOD_END,
                max_filed=asof,
            )
        except Exception as exc:  # network / parse failures
            errors.append({"ticker": ticker, "cik": cik, "error": str(exc)[:200]})
            continue
        per_ticker_facts[ticker] = len(rows)
        all_fact_rows.extend(rows)

    fetch_secs = round(time.time() - t0, 1)

    # derive PIT-safe growth rows as of `asof`
    growth_rows = derive_companyfacts_growth_rows(
        all_fact_rows, asof_date=asof, tickers=[t for t, _ in universe]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for row in growth_rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    # ---- coverage audit ----
    requested = {t for t, _ in universe}
    canon_by_ticker: dict[str, set[str]] = {}
    ok_growth_by_ticker: dict[str, set[str]] = {}
    growth_status_counts: Counter[str] = Counter()
    canonical_row_counts: Counter[str] = Counter()
    for row in growth_rows:
        t = str(row.get("ticker") or "").upper()
        c = str(row.get("canonical") or "")
        canonical_row_counts[c] += 1
        growth_status_counts[row.get("growth_status")] += 1
        canon_by_ticker.setdefault(t, set()).add(c)
        if row.get("growth_status") == "ok" and row.get("yoy_growth") is not None:
            ok_growth_by_ticker.setdefault(t, set()).add(c)

    tickers_with_any_fundamental = {
        t for t, n in per_ticker_facts.items() if n > 0
    }
    tickers_with_revenue = {t for t, cs in canon_by_ticker.items() if "revenue" in cs}
    tickers_with_eps = {
        t for t, cs in canon_by_ticker.items() if cs & {"eps_basic", "eps_diluted"}
    }
    tickers_with_ok_revenue_growth = {
        t for t, cs in ok_growth_by_ticker.items() if "revenue" in cs
    }
    tickers_with_ok_eps_growth = {
        t for t, cs in ok_growth_by_ticker.items() if cs & {"eps_basic", "eps_diluted"}
    }
    no_usable = sorted(requested - tickers_with_any_fundamental)

    def _share(s: set) -> float:
        return round(len(s) / len(requested), 4) if requested else 0.0

    audit = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "asof": asof,
        "universe": "exp-20260519-030 warehouse all_windows_full_liquid",
        "tickers_requested": len(requested),
        "tickers_with_cik": len(universe),
        "fetch_seconds": fetch_secs,
        "fetch_errors": len(errors),
        "fetch_error_sample": errors[:10],
        "raw_fact_rows": len(all_fact_rows),
        "growth_rows_written": len(growth_rows),
        "growth_status_counts": dict(growth_status_counts),
        "canonical_growth_row_counts": dict(canonical_row_counts),
        "coverage": {
            "tickers_with_any_fundamental_facts": len(tickers_with_any_fundamental),
            "tickers_with_any_fundamental_facts_share": _share(tickers_with_any_fundamental),
            "tickers_with_revenue_facts": len(tickers_with_revenue),
            "tickers_with_revenue_facts_share": _share(tickers_with_revenue),
            "tickers_with_eps_facts": len(tickers_with_eps),
            "tickers_with_eps_facts_share": _share(tickers_with_eps),
            "tickers_with_ok_revenue_yoy_growth": len(tickers_with_ok_revenue_growth),
            "tickers_with_ok_revenue_yoy_growth_share": _share(tickers_with_ok_revenue_growth),
            "tickers_with_ok_eps_yoy_growth": len(tickers_with_ok_eps_growth),
            "tickers_with_ok_eps_yoy_growth_share": _share(tickers_with_ok_eps_growth),
        },
        "tickers_with_no_usable_fundamentals_count": len(no_usable),
        "tickers_with_no_usable_fundamentals_sample": no_usable[:40],
        "dataset_output": str(output.relative_to(REPO_ROOT)),
        "pit_note": (
            "growth rows are PIT-safe: derive_companyfacts_growth_rows drops any "
            "fact with filed > asof; consume only rows with asof_date <= signal_date."
        ),
    }
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    with audit_output.open("w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")

    audit["audit_output"] = str(audit_output.relative_to(REPO_ROOT))
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asof", default=None)
    parser.add_argument("--limit", type=int, default=None, help="cap tickers (debug)")
    parser.add_argument("--sleep-seconds", type=float, default=0.11)
    args = parser.parse_args()
    audit = run(asof=args.asof, limit=args.limit, sleep_seconds=args.sleep_seconds)
    print(json.dumps({
        k: audit[k] for k in (
            "experiment_id", "tickers_requested", "tickers_with_cik",
            "fetch_seconds", "fetch_errors", "growth_rows_written",
            "coverage", "tickers_with_no_usable_fundamentals_count",
            "dataset_output", "audit_output",
        )
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
