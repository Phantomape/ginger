"""Version-aware measurement panel for the 41 registered paper surfaces.

The panel is research-only.  It consolidates historical trade paths that were
previously scattered across accepted artifacts, nested payloads, and replay
helpers.  It never mutates paper ledgers, daily snapshots, production policy,
or orders.

Two distinctions are deliberately explicit:

* ``classic_path_status`` says whether the *current paper rule* can be
  reconstructed on all three classic windows.
* ``current_paper_enabled`` / ``live_executable`` describe runtime state and
  are not used as aliases for historical data availability.

An unsupported surface is never represented by an all-zero return series.
All-zero windows are emitted only when a complete replay proves that the rule
had no triggers in that particular window.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sqlite3
import sys
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from quant import historical_current_contract_reassessment as reassess
from quant import portfolio_contribution_batch as pc
from quant.current_paper_core_allocator import (
    FORWARD_PATH,
    LEDGER_TO_SURFACE,
    OHLCV_PATH,
    OHLCV_SHA256,
    SNAPSHOT_PATH,
    SURFACE_SPECS,
    WINDOWS,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
LEGACY_EXPERIMENTS_DIR = EXPERIMENTS_DIR / "legacy"
RECONSTRUCTION_CAPITAL_USD = 10_000.0
BROADER_OHLCV_WAREHOUSE = Path(
    "data/experiments/exp-20260519-030/warehouse_main.sqlite"
)
BROAD_MARKET_FINAL_ARTIFACT = Path(
    "data/experiments/exp-20260520-004/broad_market_trend_persistence_notional.json"
)
BROAD_WAREHOUSE_LFS_OID = (
    "b98af8615dfca87e8d1d334ae0b7c7e389ccd8c6a998dc85c5e0336a19df2fda"
)
CLASSIC_SNAPSHOT_PATHS = (
    Path("data/ohlcv/ohlcv_snapshot_20241002_20250422.json"),
    Path("data/ohlcv/ohlcv_snapshot_20250423_20251022.json"),
    Path("data/ohlcv/ohlcv_snapshot_20251023_20260421.json"),
)
CLASSIC_PATH_STATUSES = {
    "canonical_current_exact",
    "canonical_current_replayed",
}


@dataclass(frozen=True)
class SourcePlan:
    mode: str
    provenance: tuple[str, ...]
    loader: str | None = None
    artifact: str | None = None
    json_path: tuple[str, ...] | None = None
    pit_tier: str = "canonical_pit"
    evidence_grade: str = "gate_candidate"
    note: str | None = None


CUSTOM_PLANS: dict[str, SourcePlan] = {
    "form4_event_sleeve": SourcePlan(
        mode="direct_nested",
        artifact="data/experiments/exp-20260504-009/form4_event_sleeve_replay.json",
        json_path=("event_sleeve_replay", "primary", "by_window", "{window}", "trades"),
        provenance=("exp-20260504-009", "quant/form4_event_queue.py", "quant/form4_event_sleeve.py"),
    ),
    "sec_negative_event_sleeve": SourcePlan(
        mode="bucket_flat",
        artifact="data/experiments/exp-20260504-010/sec_event_sleeve_backtest.json",
        json_path=("sleeve_metrics", "primary", "trades"),
        provenance=("exp-20260504-010", "quant/sec_event_queue.py", "quant/sec_negative_event_sleeve.py"),
        note="Fixed 10d/max-1 rule; rows are bucketed by entry date into the classic windows.",
    ),
    "sec_governance_event_sleeve": SourcePlan(
        mode="direct_nested",
        artifact="data/experiments/exp-20260504-039/sec_governance_procedural_overlay.json",
        json_path=("event_details", "{window}", "selected_trades"),
        provenance=("exp-20260504-039", "quant/sec_event_queue.py", "quant/sec_event_sleeve.py"),
    ),
    "sec_leadership_event_sleeve": SourcePlan(
        mode="group_field",
        artifact="data/experiments/exp-20260504-026/sec_leadership_event_sleeve.json",
        json_path=("sleeve_metrics", "trades"),
        provenance=("exp-20260504-026", "quant/sec_event_queue.py", "quant/sec_leadership_event_sleeve.py"),
        note="Faithful paper-rule replay path; the original alpha decision was rejected.",
    ),
    "sec_financial_report_event_sleeve": SourcePlan(
        mode="replay",
        loader="financial_report",
        provenance=(
            "exp-20260511-100",
            "exp-20260614-004",
            "quant/sec_financial_report_event_sleeve.py",
        ),
    ),
    "event_sleeve_bundle": SourcePlan(
        mode="replay",
        loader="event_bundle",
        provenance=(
            "exp-20260504-049",
            "exp-20260520-044",
            "exp-20260521-001",
            "exp-20260521-006",
            "exp-20260521-009",
            "exp-20260521-012",
            "exp-20260521-013",
            "exp-20260522-007",
            "quant/event_sleeve_bundle.py",
        ),
    ),
    "state_surface_sleeve": SourcePlan(
        mode="direct_nested",
        artifact="data/experiments/exp-20260520-001/state_surface_low_extension_support_notional.json",
        json_path=("surface_sleeve", "{window}", "selected_trades"),
        provenance=(
            "exp-20260517-014..exp-20260520-001 accepted state-surface rule chain",
            "quant/state_surface_sleeve.py",
        ),
        note="Final accepted rule-chain artifact, not the earlier exp-20260507-016 base replay.",
    ),
    "core_misfit_paper_sleeve": SourcePlan(
        mode="unsupported",
        provenance=("exp-20260518-022", "quant/core_misfit_paper_sleeve.py"),
        note=(
            "One registry surface carries three mutually opposite attribution tracks "
            "(fast_long, no_trade_avoided_value, inverse_short) and has no selected "
            "capital direction; a single portfolio return series would be invented."
        ),
    ),
    "broad_market_paper_sleeve": SourcePlan(
        mode="replay",
        loader="broad_market",
        artifact=str(BROAD_MARKET_FINAL_ARTIFACT).replace("\\", "/"),
        provenance=("exp-20260519-036", "exp-20260520-002/003/004", "quant/broad_market_paper_sleeve.py"),
    ),
    "accepted_helper_source_priority_allocator_paper_sleeve": SourcePlan(
        mode="replay",
        loader="accepted_helper_allocator",
        provenance=("exp-20260610-005/014", "exp-20260620-032", "exp-20260621-001/006/007"),
    ),
    "volatility_contraction_paper_sleeve": SourcePlan(
        mode="direct_nested",
        artifact="data/experiments/exp-20260526-007/vcp_rank_notional_profile.json",
        json_path=("profile_results", "rank2_125", "target_trades_by_window", "{window}"),
        provenance=("exp-20260525-022/037", "exp-20260526-007", "quant/volatility_contraction_paper_sleeve.py"),
        note="Final rank2_125 rows were nested and were missed by exp-20260817-001/002.",
    ),
    "fundamental_growth_rs_paper_sleeve": SourcePlan(
        mode="replay",
        loader="fundamental_growth",
        provenance=(
            "exp-20260528-008/015/016/017",
            "exp-20260601-026/027/030",
            "exp-20260602-009/010",
            "quant/fundamental_growth_rs_paper_sleeve.py",
        ),
    ),
    "core_drawdown_flow_put_stabilization_paper_sleeve": SourcePlan(
        mode="research_incomplete",
        artifact=(
            "data/experiments/exp-20260723-007/"
            "exp_20260723_007_owner_assumed_options_backfill_replay.json"
        ),
        provenance=("exp-20260723-004 canonical observer", "exp-20260723-007 owner-assumed backfill"),
        pit_tier="research_pit",
        evidence_grade="lead",
        note=(
            "Owner-assumed option history has no old_thin window and only a partial "
            "mid_weak window; it is retained as a diagnostic but cannot enter the "
            "canonical three-window allocator."
        ),
    ),
}


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _read_json(path: str | Path) -> Any:
    return json.loads(_repo_path(path).read_text(encoding="utf-8"))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _repo_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _broad_warehouse_path() -> Path:
    """Resolve the immutable 2026-05-19 warehouse without changing checkout state.

    The tracked experiment database was later replaced by a compact checkout
    artifact.  The exact 741 MB input used by the accepted replay remains a Git
    LFS object.  Reading the object directly preserves both the current worktree
    and the original experiment identity.
    """

    lfs_object = (
        REPO_ROOT
        / ".git"
        / "lfs"
        / "objects"
        / BROAD_WAREHOUSE_LFS_OID[:2]
        / BROAD_WAREHOUSE_LFS_OID[2:4]
        / BROAD_WAREHOUSE_LFS_OID
    )
    candidates = (lfs_object, _repo_path(BROADER_OHLCV_WAREHOUSE))
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            with sqlite3.connect(f"file:{candidate}?mode=ro", uri=True) as connection:
                row_count = int(connection.execute("select count(*) from ohlcv").fetchone()[0])
                derived_count = int(
                    connection.execute("select count(*) from ticker_universe").fetchone()[0]
                )
        except sqlite3.Error:
            continue
        if row_count > 0 and derived_count > 0:
            return candidate
    raise FileNotFoundError(
        "The immutable broad-market LFS warehouse is unavailable. Fetch commit "
        "5d5bb278ff2901ad58cd0d53d994c91346f50be5 for "
        f"{BROADER_OHLCV_WAREHOUSE}."
    )


def _nested(payload: Any, path: Sequence[str], *, window: str | None = None) -> Any:
    value = payload
    for key in path:
        actual = key.format(window=window) if window is not None else key
        if not isinstance(value, Mapping) or actual not in value:
            raise KeyError(".".join(path))
        value = value[actual]
    return value


def _exp_import(name: str) -> Any:
    for path in (EXPERIMENTS_DIR, LEGACY_EXPERIMENTS_DIR, REPO_ROOT / "quant"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    return importlib.import_module(name)


def _bucket_by_entry(rows: Sequence[Mapping[str, Any]], calendars: Mapping[str, Sequence[date]]) -> dict[str, list[dict[str, Any]]]:
    out = {window: [] for window in WINDOWS}
    for raw in rows:
        row = dict(raw)
        value = str(row.get("entry_date") or "")[:10]
        if not value:
            continue
        day = date.fromisoformat(value)
        for window in WINDOWS:
            if calendars[window][0] <= day <= calendars[window][-1]:
                out[window].append(row)
                break
    return out


def _plan_for(spec: Mapping[str, Any]) -> SourcePlan:
    surface = str(spec["surface"])
    if surface in CUSTOM_PLANS:
        return CUSTOM_PLANS[surface]
    artifact = spec.get("artifact")
    trade_key = spec.get("trade_key")
    if artifact and trade_key:
        return SourcePlan(
            mode="generic",
            artifact=str(artifact),
            json_path=(str(trade_key),),
            provenance=(str(artifact).split("/")[2],),
        )
    return SourcePlan(
        mode="unsupported",
        provenance=(),
        note="No version-bound historical trade path or replay helper is registered.",
    )


def _load_direct(plan: SourcePlan, calendars: Mapping[str, Sequence[date]]) -> dict[str, list[dict[str, Any]]]:
    if not plan.artifact or not plan.json_path:
        raise ValueError("direct plan is missing artifact/json_path")
    payload = _read_json(plan.artifact)
    if plan.mode == "direct_nested":
        return {
            window: [dict(row) for row in (_nested(payload, plan.json_path, window=window) or [])]
            for window in WINDOWS
        }
    if plan.mode == "bucket_flat":
        rows = _nested(payload, plan.json_path) or []
        return _bucket_by_entry(rows, calendars)
    if plan.mode == "group_field":
        rows = _nested(payload, plan.json_path) or []
        out = {window: [] for window in WINDOWS}
        for raw in rows:
            row = dict(raw)
            label = str(row.get("window") or "")
            if label in out:
                out[label].append(row)
        return out
    if plan.mode != "generic":
        raise ValueError(f"unsupported direct mode: {plan.mode}")
    key = plan.json_path[0]
    if key == "all_trades_by_entry_window":
        return _bucket_by_entry(payload.get("trades") or [], calendars)
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise KeyError(key)
    return {window: [dict(row) for row in (value.get(window) or [])] for window in WINDOWS}


def _replay_broad_market() -> dict[str, list[dict[str, Any]]]:
    module = _exp_import("exp_20260520_004_broad_market_trend_persistence_notional")
    module.p35.WAREHOUSE_SQLITE = _broad_warehouse_path()
    frozen_result = _read_json(BROAD_MARKET_FINAL_ARTIFACT)
    candidate_tickers = [
        str(ticker).upper()
        for ticker in frozen_result["candidate_universe"]["tickers"]
    ]
    if len(candidate_tickers) != int(frozen_result["candidate_universe"]["candidate_count"]):
        raise ValueError("broad-market frozen candidate identity is inconsistent")
    prices = module.p35._load_price_rows(candidate_tickers)
    indexes = module.p35._index_by_date(prices)
    threshold = float(module.DEFAULT_CONFIG["trend_persistence_positive_day_ratio_20_min"])
    scalar = float(module.DEFAULT_CONFIG["trend_persistence_notional_scalar"])
    result = {
        window: [dict(row) for row in module._simulate_window(
            label=window,
            positive_day_ratio_20_min=threshold,
            scalar=scalar,
            candidate_tickers=candidate_tickers,
            prices=prices,
            indexes=indexes,
        )["trades"]]
        for window in WINDOWS
    }
    for window in WINDOWS:
        frozen_window = frozen_result["broad_market_sleeve"][window]
        expected_count = int(frozen_window["trade_count"])
        expected_pnl = round(float(frozen_window["pnl"]), 2)
        actual_pnl = round(sum(float(row["pnl"]) for row in result[window]), 2)
        if len(result[window]) != expected_count or actual_pnl != expected_pnl:
            raise ValueError(
                f"broad-market identity mismatch in {window}: "
                f"{len(result[window])}/{actual_pnl} != {expected_count}/{expected_pnl}"
            )
        keys = {
            (
                str(row.get("ticker") or ""),
                str(row.get("entry_date") or "")[:10],
                str(row.get("exit_date") or "")[:10],
                round(float(row.get("pnl") or 0.0), 2),
            )
            for row in result[window]
        }
        sample_keys = {
            (
                str(row.get("ticker") or ""),
                str(row.get("entry_date") or "")[:10],
                str(row.get("exit_date") or "")[:10],
                round(float(row.get("pnl") or 0.0), 2),
            )
            for row in frozen_window["sample_trades"]
        }
        if not sample_keys.issubset(keys):
            raise ValueError(f"broad-market sample identity mismatch in {window}")
    return result


def _rebuild_broad_candidate_universe(module: Any, tradeable: set[str]) -> dict[str, Any]:
    """Rebuild the two missing derived warehouse tables from frozen raw rows.

    The exp-20260519-030 SQLite still contains the immutable OHLCV rows, but its
    ``ticker_universe`` and ``coverage_summary`` derived tables are absent in
    the checked-out artifact.  Recomputing the exact published filters in
    memory is a measurement repair; the source database is never modified.
    """

    warehouse_builder = _exp_import("exp_20260519_030_broad_market_ohlcv_warehouse")
    sec_rows = {
        str(row["ticker"]): row
        for row in warehouse_builder._load_sec_universe()
        if row.get("hygiene_pass")
    }
    expected: dict[str, set[str]] = {}
    for window, cfg in module.p35.WINDOWS.items():
        payload = _read_json(cfg["snapshot"])
        raw = payload.get("ohlcv") if isinstance(payload, Mapping) else payload
        benchmark = (raw or {}).get("SPY") or []
        expected[window] = {
            str(row.get("Date") or row.get("date") or "")[:10]
            for row in benchmark
            if cfg["start"] <= str(row.get("Date") or row.get("date") or "")[:10] <= cfg["end"]
        }

    grouped: defaultdict[str, list[tuple[str, float, float]]] = defaultdict(list)
    with sqlite3.connect(f"file:{_broad_warehouse_path()}?mode=ro", uri=True) as connection:
        for ticker, day, close, volume in connection.execute(
            "select ticker, date, close, volume from ohlcv order by ticker, date"
        ):
            grouped[str(ticker).upper()].append(
                (str(day)[:10], float(close), float(volume))
            )

    selected: list[str] = []
    excluded: list[dict[str, Any]] = []
    for ticker, rows in sorted(grouped.items()):
        reference = sec_rows.get(ticker)
        if reference is None:
            continue
        title = str(reference.get("title") or "")
        reasons: list[str] = []
        if ticker in tradeable:
            reasons.append("current_tradeable_universe")
        if ticker in {"SPY", "QQQ"}:
            reasons.append("benchmark")
        if module.p35._excluded_title(title):
            reasons.append("title_exclusion")
        full_liquid = True
        for window, cfg in module.p35.WINDOWS.items():
            window_rows = [
                value for value in rows if cfg["start"] <= value[0] <= cfg["end"]
            ]
            covered = {value[0] for value in window_rows}
            denominator = len(expected[window])
            coverage = len(covered & expected[window]) / denominator if denominator else 0.0
            closes = np.asarray([value[1] for value in window_rows], dtype=float)
            dollar_volumes = np.asarray(
                [value[1] * value[2] for value in window_rows], dtype=float
            )
            liquid = (
                coverage >= warehouse_builder.MIN_COVERAGE_FRACTION
                and closes.size > 0
                and float(np.median(closes)) >= warehouse_builder.MIN_MEDIAN_CLOSE
                and dollar_volumes.size > 0
                and float(np.median(dollar_volumes))
                >= warehouse_builder.MIN_MEDIAN_DOLLAR_VOLUME
            )
            full_liquid = full_liquid and liquid
        if not full_liquid:
            reasons.append("not_all_windows_full_liquid")
        if reasons:
            excluded.append({"ticker": ticker, "title": title, "exclusion_reasons": reasons})
        else:
            selected.append(ticker)
    return {
        "source": "in_memory_rebuild_of_exp_20260519_030_derived_tables",
        "candidate_count": len(selected),
        "excluded_count": len(excluded),
        "tickers": selected,
        "sample_excluded": excluded[:50],
    }


def _replay_accepted_helper_allocator() -> dict[str, list[dict[str, Any]]]:
    module = _exp_import("exp_20260621_007_accepted_allocator_lagged_consensus_notional")
    payload = module.template._run_allocator_pass("panel_current_rule", dict(module.AFTER_SCALARS))
    return {
        window: [dict(row) for row in payload["target_trades_by_window"][window]]
        for window in WINDOWS
    }


def _replay_fundamental_growth() -> dict[str, list[dict[str, Any]]]:
    module = _exp_import("exp_20260602_009_companyfacts_sector_residual_support")
    _before, after, _incremental, _diagnostics = module._select_supported_trades()
    return {window: [dict(row) for row in after[window]] for window in WINDOWS}


def _replay_event_bundle() -> dict[str, list[dict[str, Any]]]:
    module = _exp_import("exp_20260522_007_event_governance_503_haircut")
    module._configure_modules()
    parent = module._parent()
    raw, _coverage, _prices = parent.base._load_event_trades()
    enriched = parent.base._enrich_event_trades(raw)
    scalar = 0.25
    return {
        window: [
            module._scaled_trade(row, "panel_current_rule", {"governance_503_scalar": scalar})
            for row in enriched[window]
        ]
        for window in WINDOWS
    }


def _financial_state_from_snapshot(snapshot: Mapping[str, Any], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    module = _exp_import("exp_20260614_004_sec_financial_report_rs20_notional_support")
    return module._rebuild_sleeve_state(snapshot, skipped)


def _replay_financial_report() -> dict[str, list[dict[str, Any]]]:
    module = _exp_import("exp_20260614_004_sec_financial_report_rs20_notional_support")
    source = module._load_exp100()
    result: dict[str, list[dict[str, Any]]] = {}
    for window, cfg in module.WINDOWS.items():
        prices_by_date = module._load_snapshot_prices(cfg["snapshot"])
        prev_by_date = module._window_prev_date_map(prices_by_date)
        date_index = module._window_date_index(prices_by_date)
        candidates_by_t1 = module._rows_by_t1_date(source["windows"][window])
        state = module.empty_sec_financial_report_event_sleeve_state()
        skipped: list[dict[str, Any]] = []
        for as_of, prices in prices_by_date.items():
            candidates = [
                module._candidate_with_rs20_fields(row, prices_by_date, date_index)
                for row in candidates_by_t1.get(as_of, [])
            ]
            queue = {
                "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_PANEL_REPLAY",
                "rule_version": "current_shared_financial_report_rule",
                "enabled": False,
                "asof_date": as_of,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "data_source": {"status": "replay", "source_experiment": "exp-20260511-100"},
            }
            snapshot = module.build_sec_financial_report_event_sleeve_snapshot(
                sec_financial_report_t1_queue=queue,
                as_of=as_of,
                open_prices=prices["open"],
                current_prices=prices["close"],
                state=state,
                config={
                    "max_positions": module.DEFAULT_MAX_POSITIONS,
                    "event_notional_usd": module.DEFAULT_EVENT_NOTIONAL_USD,
                    "periodic_report_notional_scalar": module.DEFAULT_PERIODIC_REPORT_NOTIONAL_SCALAR,
                    "rs20_leader_notional_enabled": True,
                    "rs20_leader_notional_scalar": module.DEFAULT_RS20_LEADER_NOTIONAL_SCALAR,
                    "rs20_leader_min_excess_return": module.RS20_LEADER_MIN_EXCESS_RETURN,
                },
                persist=False,
            )
            skipped.extend(snapshot.get("skipped_entries_today") or [])
            state = _financial_state_from_snapshot(snapshot, skipped)
        result[window] = [
            module._adjust_closed_position(
                row,
                prices_by_date=prices_by_date,
                prev_by_date=prev_by_date,
                date_index=date_index,
                rs20_leader_scalar=module.DEFAULT_RS20_LEADER_NOTIONAL_SCALAR,
            )
            for row in state.get("closed_positions") or []
        ]
    return result


REPLAY_LOADERS: dict[str, Callable[[], dict[str, list[dict[str, Any]]]]] = {
    "broad_market": _replay_broad_market,
    "accepted_helper_allocator": _replay_accepted_helper_allocator,
    "fundamental_growth": _replay_fundamental_growth,
    "event_bundle": _replay_event_bundle,
    "financial_report": _replay_financial_report,
}


def _float(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(parsed):
            return parsed
    return None


def _price_value(price_map: Mapping[str, Mapping[date, Mapping[str, float]]], ticker: str, day_text: str, field: str) -> float | None:
    if not ticker or not day_text:
        return None
    try:
        day = date.fromisoformat(day_text[:10])
    except ValueError:
        return None
    row = (price_map.get(ticker) or {}).get(day) or {}
    value = row.get(field)
    return float(value) if value is not None else None


def _supplement_price_map(
    price_map: dict[str, dict[date, dict[str, float]]],
) -> dict[str, dict[date, dict[str, float]]]:
    """Add the three immutable classic snapshots without altering precedence."""

    for snapshot_path in CLASSIC_SNAPSHOT_PATHS:
        payload = _read_json(snapshot_path)
        raw = payload.get("ohlcv") if isinstance(payload, Mapping) else payload
        for ticker, rows in (raw or {}).items():
            target = price_map.setdefault(str(ticker).upper(), {})
            for row in rows or []:
                day_text = str(row.get("Date") or row.get("date") or "")[:10]
                try:
                    day = date.fromisoformat(day_text)
                except ValueError:
                    continue
                open_price = _float(row, "Open", "open")
                close_price = _float(row, "Close", "close")
                if open_price is None or close_price is None:
                    continue
                target.setdefault(day, {"open": open_price, "close": close_price})
    return price_map


def normalize_trade(row: Mapping[str, Any], price_map: Mapping[str, Mapping[date, Mapping[str, float]]]) -> dict[str, Any]:
    out = dict(row)
    ticker = str(out.get("ticker") or "").upper()
    entry_date = str(out.get("entry_date") or "")[:10]
    exit_date = str(out.get("exit_date") or "")[:10]
    entry_price = _float(out, "entry_price", "entry_open", "paper_entry_price")
    exit_price = _float(out, "exit_price", "exit_close", "paper_exit_price")
    if entry_price is None:
        entry_price = _price_value(price_map, ticker, entry_date, "open")
    if exit_price is None:
        exit_price = _price_value(price_map, ticker, exit_date, "close")
    notional = _float(
        out,
        "paper_notional_usd",
        "notional_usd",
        "notional",
        "entry_notional",
        "base_paper_notional_usd",
    )
    if notional is None:
        shares = _float(out, "shares")
        if shares is not None and entry_price is not None:
            notional = shares * entry_price
    pnl = _float(out, "pnl", "paper_pnl")
    net_pct = _float(out, "net_return_pct")
    net_fraction = _float(out, "pnl_pct_net")
    if pnl is None and notional is not None:
        if net_fraction is not None:
            pnl = notional * net_fraction
        elif net_pct is not None:
            pnl = notional * net_pct / 100.0
    out.update(
        {
            "ticker": ticker,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "paper_notional_usd": notional,
            "pnl": pnl,
        }
    )
    return out


def _reconstruct_returns(
    trades_by_window: Mapping[str, Sequence[Mapping[str, Any]]],
    calendars: Mapping[str, Sequence[date]],
    price_map: Mapping[str, Mapping[date, Mapping[str, float]]],
) -> tuple[dict[str, np.ndarray], dict[str, Any], list[tuple[str, float]]]:
    returns: dict[str, np.ndarray] = {}
    diagnostics: dict[str, Any] = {}
    contributions: list[tuple[str, float]] = []
    for window in WINDOWS:
        normalized = [normalize_trade(row, price_map) for row in trades_by_window[window]]
        if not normalized:
            returns[window] = np.zeros(len(calendars[window]), dtype=float)
            diagnostics[window] = {
                "source_trade_count": 0,
                "allocated_trade_count": 0,
                "usable_trade_count": 0,
                "true_zero_trigger_window": True,
                "min_cash_usd": RECONSTRUCTION_CAPITAL_USD,
                "cash_nonnegative": True,
                "ending_all_positions_settled": True,
            }
            continue
        allocation = pc.allocate_sleeve_capital(
            normalized,
            calendars[window],
            sleeve_capital=RECONSTRUCTION_CAPITAL_USD,
            price_map=price_map,
        )
        if not allocation.get("cash_nonnegative") or not allocation.get("ending_all_positions_settled"):
            raise ValueError(f"cash/settlement identity failed in {window}")
        pnl_by_day: defaultdict[date, float] = defaultdict(float)
        unusable: list[dict[str, Any]] = []
        usable = 0
        for trade in allocation["allocated_rows"]:
            daily, diagnostic = pc.reconstruct_trade_daily_pnl(trade, calendars[window], price_map)
            if not diagnostic.get("usable"):
                unusable.append(diagnostic)
                continue
            usable += 1
            contributions.append((str(diagnostic["ticker"]), float(diagnostic["net_pnl"])))
            for day, pnl in daily.items():
                pnl_by_day[day] += float(pnl)
        if unusable or usable != len(allocation["allocated_rows"]):
            raise ValueError(f"incomplete MTM in {window}: {unusable[:3]}")
        returns[window] = pc.pnl_to_returns(
            pnl_by_day,
            calendars[window],
            initial_capital=RECONSTRUCTION_CAPITAL_USD,
        )
        diagnostics[window] = {
            "source_trade_count": len(normalized),
            "allocated_trade_count": len(allocation["allocated_rows"]),
            "usable_trade_count": usable,
            "true_zero_trigger_window": False,
            "min_cash_usd": float(allocation["min_cash_usd"]),
            "cash_nonnegative": bool(allocation["cash_nonnegative"]),
            "ending_all_positions_settled": bool(allocation["ending_all_positions_settled"]),
            "partial_fill_count": int(allocation.get("partial_fill_count") or 0),
            "zero_fill_count": int(allocation.get("zero_fill_count") or 0),
        }
    return returns, diagnostics, contributions


def _research_options_diagnostic(plan: SourcePlan) -> dict[str, Any]:
    assert plan.artifact
    payload = _read_json(plan.artifact)
    windows: dict[str, Any] = {}
    for row in payload.get("window_results") or []:
        label = str(row.get("label") or "")
        equity = row.get("daily_equity") or []
        windows[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "daily_equity_count": len(equity),
            "trade_count": len(row.get("trades") or []),
            "metrics": row.get("metrics"),
        }
    return {
        "artifact": plan.artifact,
        "sha256": sha256_file(plan.artifact),
        "available_windows": windows,
        "classic_complete": False,
    }


def _recent_diagnostics() -> dict[str, Any]:
    path = _repo_path(FORWARD_PATH)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    totals: defaultdict[str, dict[str, float]] = defaultdict(
        lambda: {"rows": 0.0, "notional": 0.0, "cash": 0.0, "spy": 0.0, "qqq": 0.0}
    )
    dates: list[str] = []
    unknown: set[str] = set()
    for row in rows:
        key = str(row.get("sleeve_key") or "")
        surface = LEDGER_TO_SURFACE.get(key)
        if surface is None:
            unknown.add(key)
            continue
        target = totals[surface]
        target["rows"] += 1
        target["notional"] += float(row.get("notional_usd") or 0.0)
        target["cash"] += float(row.get("replacement_value_vs_cash_usd") or 0.0)
        target["spy"] += float(row.get("replacement_value_vs_spy_usd") or 0.0)
        target["qqq"] += float(row.get("replacement_value_vs_qqq_usd") or 0.0)
        dates.extend((str(row.get("entry_date") or ""), str(row.get("exit_date") or "")))
    surfaces: dict[str, Any] = {}
    for spec in SURFACE_SPECS:
        name = str(spec["surface"])
        value = totals.get(name) or {}
        notional = float(value.get("notional") or 0.0)
        surfaces[name] = {
            "settled_row_count": int(value.get("rows") or 0),
            "settled_notional_usd": notional,
            "return_vs_cash": float(value.get("cash") or 0.0) / notional if notional else None,
            "return_vs_spy": float(value.get("spy") or 0.0) / notional if notional else None,
            "return_vs_qqq": float(value.get("qqq") or 0.0) / notional if notional else None,
        }
    clean_dates = [value for value in dates if value]
    return {
        "path": str(FORWARD_PATH).replace("\\", "/"),
        "sha256": sha256_file(FORWARD_PATH),
        "row_count": len(rows),
        "unique_decision_count": len({str(row.get("decision_id")) for row in rows}),
        "covered_surface_count": len(totals),
        "period": {"start": min(clean_dates), "end": max(clean_dates)} if clean_dates else None,
        "unknown_sleeve_keys": sorted(unknown),
        "surfaces": surfaces,
    }


def build_panel() -> dict[str, Any]:
    contract = _read_json(SNAPSHOT_PATH)["paper_sleeve_execution_contract"]
    if len(contract["surfaces"]) != 41 or len(SURFACE_SPECS) != 41:
        raise ValueError("the frozen execution contract must contain exactly 41 surfaces")
    contract_by_surface = {str(row["surface"]): row for row in contract["surfaces"]}
    expected = [str(spec["surface"]) for spec in SURFACE_SPECS]
    if list(contract_by_surface) != expected:
        raise ValueError("surface identity/order differs from SURFACE_SPECS")

    core_payloads, calendars, core_returns, core_identity = reassess.load_active_core()
    ohlcv_rows, ohlcv_identity = reassess._load_ohlcv_snapshot(
        OHLCV_PATH,
        expected_experiment_id="exp-20260716-011",
        expected_gzip_sha256=OHLCV_SHA256,
    )
    price_map = _supplement_price_map(pc._price_map_from_rows(ohlcv_rows))
    inventory: list[dict[str, Any]] = []
    surface_returns: dict[str, dict[str, np.ndarray]] = {}
    surface_contributions: dict[str, list[tuple[str, float]]] = {}
    source_hashes: dict[str, str] = {}
    research_diagnostics: dict[str, Any] = {}

    for spec in SURFACE_SPECS:
        surface = str(spec["surface"])
        runtime = contract_by_surface[surface]
        plan = _plan_for(spec)
        row: dict[str, Any] = {
            "surface": surface,
            "sleeve": spec["sleeve"],
            "declared_rule_version": spec["rule_version"],
            "source_mode": plan.mode,
            "pit_tier": plan.pit_tier,
            "evidence_grade": plan.evidence_grade,
            "provenance": list(plan.provenance),
            "source_note": plan.note,
            "current_paper_enabled": bool(runtime.get("paper_enabled")),
            "live_executable": bool(runtime.get("trade_enabled")),
            "classic_path_status": "unsupported",
            "classic_complete": False,
            "research_combinable": False,
            "current_enabled_combinable": False,
            "classic_trade_counts": {window: 0 for window in WINDOWS},
            "classic_zero_trigger_windows": [],
            "blocker": None,
        }
        if plan.artifact and _repo_path(plan.artifact).exists():
            source_hashes[plan.artifact] = sha256_file(plan.artifact)
        if plan.mode == "unsupported":
            row["blocker"] = plan.note
            inventory.append(row)
            continue
        if plan.mode == "research_incomplete":
            row["classic_path_status"] = "research_pit_incomplete"
            row["blocker"] = plan.note
            research_diagnostics[surface] = _research_options_diagnostic(plan)
            inventory.append(row)
            continue
        try:
            if plan.mode == "replay":
                if plan.loader not in REPLAY_LOADERS:
                    raise KeyError(f"unregistered replay loader: {plan.loader}")
                trades = REPLAY_LOADERS[str(plan.loader)]()
                status = "canonical_current_replayed"
            else:
                trades = _load_direct(plan, calendars)
                status = "canonical_current_exact"
            if set(trades) != set(WINDOWS):
                raise ValueError("classic window keys are incomplete")
            reconstructed, diagnostics, contributions = _reconstruct_returns(
                trades, calendars, price_map
            )
            surface_returns[surface] = reconstructed
            surface_contributions[surface] = contributions
            counts = {window: len(trades[window]) for window in WINDOWS}
            zero_windows = [window for window, count in counts.items() if count == 0]
            row.update(
                {
                    "classic_path_status": status,
                    "classic_complete": True,
                    "research_combinable": True,
                    "current_enabled_combinable": bool(runtime.get("paper_enabled")),
                    "classic_trade_counts": counts,
                    "classic_zero_trigger_windows": zero_windows,
                    "reconstruction": diagnostics,
                    "blocker": None,
                }
            )
        except Exception as exc:
            row["classic_path_status"] = "replay_failed"
            row["blocker"] = f"{type(exc).__name__}:{exc}"
        inventory.append(row)

    classic_complete = [row["surface"] for row in inventory if row["classic_complete"]]
    enabled_complete = [row["surface"] for row in inventory if row["current_enabled_combinable"]]
    return {
        "schema_version": 1,
        "experiment_id": "exp-20260817-003",
        "contract": {
            "registered_surface_count": len(inventory),
            "surface_order": expected,
            "classic_windows": {
                window: {
                    "start": calendars[window][0].isoformat(),
                    "end": calendars[window][-1].isoformat(),
                    "session_count": len(calendars[window]),
                }
                for window in WINDOWS
            },
            "normalization_capital_usd": RECONSTRUCTION_CAPITAL_USD,
            "unsupported_is_zero": False,
            "zero_return_requires_complete_zero_trigger_window": True,
            "live_allocation_changed": False,
        },
        "summary": {
            "registered_surface_count": len(inventory),
            "classic_complete_surface_count": len(classic_complete),
            "current_enabled_classic_complete_count": len(enabled_complete),
            "research_combinable_surfaces": classic_complete,
            "current_enabled_combinable_surfaces": enabled_complete,
            "unsupported_or_incomplete_surfaces": [
                row["surface"] for row in inventory if not row["classic_complete"]
            ],
            "true_zero_trigger_surface_window_count": sum(
                len(row["classic_zero_trigger_windows"]) for row in inventory
            ),
        },
        "inventory": inventory,
        "core_payloads": core_payloads,
        "core_returns": core_returns,
        "surface_returns": surface_returns,
        "surface_contributions": surface_contributions,
        "calendars": calendars,
        "research_diagnostics": research_diagnostics,
        "recent_settled": _recent_diagnostics(),
        "input_identity": {
            "paper_contract_path": str(SNAPSHOT_PATH).replace("\\", "/"),
            "paper_contract_sha256": sha256_file(SNAPSHOT_PATH),
            "core": core_identity,
            "ohlcv": ohlcv_identity,
            "source_artifact_sha256": dict(sorted(source_hashes.items())),
            "broad_ohlcv_warehouse_path": str(_broad_warehouse_path()).replace("\\", "/"),
            "broad_ohlcv_warehouse_lfs_oid": BROAD_WAREHOUSE_LFS_OID,
            "broad_ohlcv_warehouse_sha256": sha256_file(_broad_warehouse_path()),
            "classic_snapshot_sha256": {
                str(path).replace("\\", "/"): sha256_file(path)
                for path in CLASSIC_SNAPSHOT_PATHS
            },
        },
    }


def serializable_panel(panel: Mapping[str, Any]) -> dict[str, Any]:
    calendars = panel["calendars"]
    return {
        key: value
        for key, value in panel.items()
        if key not in {"core_payloads", "core_returns", "surface_returns", "surface_contributions", "calendars"}
    } | {
        "classic_daily_return_panel": {
            "dates": {
                window: [day.isoformat() for day in calendars[window]] for window in WINDOWS
            },
            "core": {
                window: [round(float(value), 12) for value in panel["core_returns"][window]]
                for window in WINDOWS
            },
            "surfaces": {
                surface: {
                    window: [round(float(value), 12) for value in values[window]]
                    for window in WINDOWS
                }
                for surface, values in panel["surface_returns"].items()
            },
        },
        "surface_contributions": {
            surface: [[ticker, round(float(pnl), 6)] for ticker, pnl in rows]
            for surface, rows in panel["surface_contributions"].items()
        },
    }


def panel_identity(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
