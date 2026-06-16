"""Unified non-OHLCV backfill/catch-up orchestrator.

This CLI uses the same daily snapshot writers as production and records an
append-only coverage manifest. It is data-only: no trading advice, orders, LLM
decisions, sizing, or candidate ranking are executed here.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

try:
    from backfill_earnings_snapshots import backfill_earnings_snapshots
    from daily_non_ohlcv_snapshot import persist_daily_non_ohlcv_snapshots
    from data_paths import daily_artifact_path
    from data_layer import get_universe
    from event_shocks import build_event_snapshot
    from non_ohlcv_coverage import (
        append_manifest_record,
        build_coverage_record,
        build_coverage_report,
        build_finra_source_coverage_record,
        date_key,
        is_coverage_complete,
        iter_business_days,
        latest_complete_trade_date,
        next_business_day,
        parse_trade_date,
        previous_business_day,
        resolve_data_root,
        resolve_non_ohlcv_dir,
        write_backtest_coverage_report,
    )
    from sec_filing_features import build_daily_filing_features
except ImportError:  # pragma: no cover - package-style imports
    from quant.backfill_earnings_snapshots import backfill_earnings_snapshots
    from quant.daily_non_ohlcv_snapshot import persist_daily_non_ohlcv_snapshots
    from quant.data_paths import daily_artifact_path
    from quant.data_layer import get_universe
    from quant.event_shocks import build_event_snapshot
    from quant.non_ohlcv_coverage import (
        append_manifest_record,
        build_coverage_record,
        build_coverage_report,
        build_finra_source_coverage_record,
        date_key,
        is_coverage_complete,
        iter_business_days,
        latest_complete_trade_date,
        next_business_day,
        parse_trade_date,
        previous_business_day,
        resolve_data_root,
        resolve_non_ohlcv_dir,
        write_backtest_coverage_report,
    )
    from quant.sec_filing_features import build_daily_filing_features


logger = logging.getLogger(__name__)
VALID_PROFILES = {"daily", "catchup", "backtest"}


def ensure_non_ohlcv_coverage(
    *,
    start: str | date | datetime,
    end: str | date | datetime,
    profile: str,
    only_missing: bool = True,
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
    universe: list[str] | None = None,
    refresh_earnings: bool = True,
    refresh_sec_submissions: bool = True,
    refresh_sec_text: bool = False,
    refresh_form4_submissions: bool = True,
    refresh_form4_xml: bool = False,
    refresh_options: bool = False,
    options_tickers: list[str] | None = None,
    option_underlying_prices: dict[str, float] | None = None,
    options_max_expirations: int | None = 2,
    options_max_strikes_per_side: int | None = 12,
    options_max_tickers: int | None = None,
    build_filing_features: bool = True,
    companyfacts_path: str | Path | None = None,
    record_existing: bool = True,
    max_ciks: int | None = None,
    logger_obj: logging.Logger | None = None,
    earnings_backfill_fn: Callable[..., Any] = backfill_earnings_snapshots,
    daily_snapshot_fn: Callable[..., dict[str, Any]] = persist_daily_non_ohlcv_snapshots,
    event_snapshot_fn: Callable[..., dict[str, Any]] = build_event_snapshot,
    filing_features_fn: Callable[..., dict[str, Any]] = build_daily_filing_features,
) -> dict[str, Any]:
    if profile not in VALID_PROFILES:
        raise ValueError(f"profile must be one of {sorted(VALID_PROFILES)}")
    log = logger_obj or logger
    root = resolve_data_root(data_root)
    non_root = resolve_non_ohlcv_dir(non_ohlcv_dir, data_root=root)
    universe = universe or get_universe()

    summary: dict[str, Any] = {
        "schema_version": 1,
        "profile": profile,
        "start": parse_trade_date(start).isoformat(),
        "end": parse_trade_date(end).isoformat(),
        "data_root": _path_text(root),
        "non_ohlcv_dir": _path_text(non_root),
        "days_total": 0,
        "days_generated": 0,
        "days_recorded_existing": 0,
        "days_skipped_complete": 0,
        "days_failed": 0,
        "daily_snapshots": {},
        "records": [],
        "errors": [],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": profile == "backtest",
            "run_adapter_changed": profile in {"daily", "catchup"},
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
    }

    for day in iter_business_days(start, end):
        day_iso = day.isoformat()
        tag = date_key(day)
        summary["days_total"] += 1
        complete_before = is_coverage_complete(day, data_root=root, non_ohlcv_dir=non_root)
        if only_missing and complete_before:
            record = build_coverage_record(
                day,
                mode=profile,
                data_root=root,
                non_ohlcv_dir=non_root,
            )
            if record_existing:
                append_manifest_record(record, data_root=root, non_ohlcv_dir=non_root)
                summary["days_recorded_existing"] += 1
                summary["records"].append(record)
            else:
                summary["days_skipped_complete"] += 1
            continue

        errors: list[dict[str, Any]] = []
        try:
            if refresh_earnings:
                earnings_dir = daily_artifact_path("earnings_snapshot", tag, root).parent
                earnings_backfill_fn(
                    day_iso,
                    day_iso,
                    universe=universe,
                    data_dir=str(earnings_dir),
                )
        except Exception as exc:
            errors.append({"stage": "earnings_snapshot", "error": str(exc)})
            log.warning("non-OHLCV %s earnings snapshot failed for %s: %s", profile, day_iso, exc)

        try:
            snapshot = daily_snapshot_fn(
                as_of=day_iso,
                data_dir=non_root,
                logger=log,
                refresh_sec_submissions=refresh_sec_submissions,
                refresh_sec_text=refresh_sec_text,
                refresh_form4_submissions=refresh_form4_submissions,
                refresh_form4_xml=refresh_form4_xml,
                refresh_options=refresh_options,
                options_tickers=options_tickers,
                option_underlying_prices=option_underlying_prices,
                options_max_expirations=options_max_expirations,
                options_max_strikes_per_side=options_max_strikes_per_side,
                options_max_tickers=options_max_tickers,
                max_ciks=max_ciks,
            )
            summary["daily_snapshots"][day_iso] = snapshot
        except Exception as exc:
            errors.append({"stage": "daily_non_ohlcv_snapshot", "error": str(exc)})
            log.warning("non-OHLCV %s daily snapshot failed for %s: %s", profile, day_iso, exc)

        try:
            event_snapshot_fn(
                tag,
                data_dir=root,
                universe=universe,
                persist=True,
            )
        except Exception as exc:
            errors.append({"stage": "event_snapshot", "error": str(exc)})
            log.warning("non-OHLCV %s event snapshot failed for %s: %s", profile, day_iso, exc)

        if build_filing_features:
            try:
                filing_features_fn(
                    tag,
                    data_root=root,
                    non_ohlcv_dir=non_root,
                    companyfacts_path=companyfacts_path,
                )
            except Exception as exc:
                errors.append({"stage": "sec_filing_features", "error": str(exc)})
                log.warning("non-OHLCV %s filing features failed for %s: %s", profile, day_iso, exc)

        record = build_coverage_record(
            day,
            mode=profile,
            data_root=root,
            non_ohlcv_dir=non_root,
            errors=errors,
        )
        append_manifest_record(record, data_root=root, non_ohlcv_dir=non_root)
        summary["records"].append(record)
        if record["status"] == "failed":
            summary["days_failed"] += 1
        else:
            summary["days_generated"] += 1
        if errors:
            summary["errors"].append({"trade_date": day_iso, "errors": errors})

    # Data-source-level coverage: the FINRA short-interest archive is refreshed
    # forward by the daily sleeve path but is not a per-trade-date artifact, so
    # record its freshness once per daily/catchup run. This is excluded from
    # per-date completeness reads (record_type=data_source_coverage) and is
    # best-effort so it can never break the daily coverage flow.
    if profile in {"daily", "catchup"}:
        try:
            finra_record = build_finra_source_coverage_record(
                end,
                data_root=root,
                non_ohlcv_dir=non_root,
                mode=profile,
            )
            append_manifest_record(finra_record, data_root=root, non_ohlcv_dir=non_root)
            summary["finra_short_interest_coverage"] = {
                "status": finra_record["status"],
                "row_counts": finra_record["row_counts"],
                "source_watermarks": finra_record["source_watermarks"],
            }
        except Exception as exc:  # noqa: BLE001 - coverage monitoring is non-fatal.
            log.warning("FINRA short-interest coverage record failed: %s", exc)
            summary.setdefault("errors", []).append(
                {"stage": "finra_short_interest_coverage", "error": str(exc)}
            )

    if profile == "backtest":
        report = build_coverage_report(
            start,
            end,
            data_root=root,
            non_ohlcv_dir=non_root,
        )
        path = write_backtest_coverage_report(report, data_root=root, non_ohlcv_dir=non_root)
        summary["backtest_coverage_report"] = _path_text(path)
        summary["backtest_coverage"] = {
            "business_days": report["business_days"],
            "complete_days": report["complete_days"],
            "complete_fraction": report["complete_fraction"],
            "missing_by_artifact": report["missing_by_artifact"],
            "decision": report["decision"],
        }
    return summary


def catch_up_missing_non_ohlcv(
    *,
    as_of: str | date | datetime,
    universe: list[str] | None = None,
    data_root: str | Path | None = None,
    non_ohlcv_dir: str | Path | None = None,
    fallback_lookback_days: int | None = None,
    logger_obj: logging.Logger | None = None,
) -> dict[str, Any]:
    root = resolve_data_root(data_root)
    non_root = resolve_non_ohlcv_dir(non_ohlcv_dir, data_root=root)
    as_of_date = parse_trade_date(as_of)
    end = previous_business_day(as_of_date)
    if end >= as_of_date:
        return {"status": "skipped", "reason": "no_prior_business_day"}
    latest_complete = latest_complete_trade_date(data_root=root, non_ohlcv_dir=non_root)
    if latest_complete:
        start = next_business_day(latest_complete)
    else:
        lookback = fallback_lookback_days
        if lookback is None:
            lookback = int(os.environ.get("NON_OHLCV_CATCHUP_LOOKBACK_DAYS", "10"))
        start = as_of_date - timedelta(days=max(0, lookback))
        while start.weekday() >= 5:
            start += timedelta(days=1)
    if start > end:
        return {
            "status": "skipped",
            "reason": "coverage_current",
            "latest_complete_trade_date": latest_complete.isoformat() if latest_complete else None,
        }
    summary = ensure_non_ohlcv_coverage(
        start=start,
        end=end,
        profile="catchup",
        only_missing=True,
        data_root=root,
        non_ohlcv_dir=non_root,
        universe=universe,
        refresh_options=False,
        logger_obj=logger_obj,
    )
    summary["status"] = "ok" if summary["days_failed"] == 0 else "partial"
    summary["latest_complete_trade_date_before"] = (
        latest_complete.isoformat() if latest_complete else None
    )
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill/catch up non-OHLCV replay data.")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--profile", choices=sorted(VALID_PROFILES), default="backtest")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--non-ohlcv-dir", default=None)
    parser.add_argument("--only-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--record-existing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--refresh-earnings", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--refresh-sec-submissions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--refresh-sec-text", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--refresh-form4-submissions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--refresh-form4-xml", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--build-filing-features", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--companyfacts-path", default=None)
    parser.add_argument("--max-ciks", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    args = build_arg_parser().parse_args(argv)
    summary = ensure_non_ohlcv_coverage(
        start=args.start,
        end=args.end,
        profile=args.profile,
        only_missing=args.only_missing,
        data_root=args.data_root,
        non_ohlcv_dir=args.non_ohlcv_dir,
        refresh_earnings=args.refresh_earnings,
        refresh_sec_submissions=args.refresh_sec_submissions,
        refresh_sec_text=args.refresh_sec_text,
        refresh_form4_submissions=args.refresh_form4_submissions,
        refresh_form4_xml=args.refresh_form4_xml,
        build_filing_features=args.build_filing_features,
        companyfacts_path=args.companyfacts_path,
        record_existing=args.record_existing,
        max_ciks=args.max_ciks,
        logger_obj=logger,
    )
    print(json.dumps({
        "profile": summary["profile"],
        "start": summary["start"],
        "end": summary["end"],
        "days_total": summary["days_total"],
        "days_generated": summary["days_generated"],
        "days_recorded_existing": summary["days_recorded_existing"],
        "days_skipped_complete": summary["days_skipped_complete"],
        "days_failed": summary["days_failed"],
        "errors": summary["errors"][:10],
        "backtest_coverage": summary.get("backtest_coverage"),
        "backtest_coverage_report": summary.get("backtest_coverage_report"),
    }, indent=2, ensure_ascii=False))
    return 0 if summary["days_failed"] == 0 else 2


def _path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(__file__).resolve().parents[1])).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
