from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"


DATA_ARTIFACTS: dict[str, tuple[str, str]] = {
    "crypto_positions": ("state/crypto/crypto_positions.json", "crypto_positions.json"),
    "pending_actions": ("state/execution/pending_actions.json", "pending_actions.json"),
    "pilot_competition_decisions": (
        "ledgers/pilot_competition_decisions.jsonl",
        "pilot_competition_decisions.jsonl",
    ),
    "platform_rs20_no_gap_forward_watch": (
        "paper_sleeves/platform_rs20_no_gap/forward_watch.jsonl",
        "platform_rs20_no_gap_forward_watch.jsonl",
    ),
    "platform_rs20_no_gap_forward_watch_summary": (
        "paper_sleeves/platform_rs20_no_gap/summary.json",
        "platform_rs20_no_gap_forward_watch_summary.json",
    ),
    "sec_company_tickers": ("reference/sec_company_tickers.json", "sec_company_tickers.json"),
    "universe_events": ("state/universe/universe_events.jsonl", "universe_events.jsonl"),
    "universe_registry": ("state/universe/universe_registry.json", "universe_registry.json"),
    "form4_event_sleeve_paper_snapshots": (
        "paper_sleeves/form4/snapshots.jsonl",
        "form4_event_sleeve_paper_snapshots.jsonl",
    ),
    "form4_event_sleeve_paper_state": (
        "paper_sleeves/form4/state.json",
        "form4_event_sleeve_paper_state.json",
    ),
    "low_deployment_etf_overlay_snapshots": (
        "paper_sleeves/low_deployment_etf/snapshots.jsonl",
        "low_deployment_etf_overlay_snapshots.jsonl",
    ),
    "low_deployment_etf_overlay_state": (
        "paper_sleeves/low_deployment_etf/state.json",
        "low_deployment_etf_overlay_state.json",
    ),
    "core_misfit_paper_snapshots": (
        "paper_sleeves/core_misfit/snapshots.jsonl",
        "core_misfit_paper_snapshots.jsonl",
    ),
    "core_misfit_paper_state": (
        "paper_sleeves/core_misfit/state.json",
        "core_misfit_paper_state.json",
    ),
    "sec_10k_liquidity_forward_watch": (
        "paper_sleeves/sec_10k_liquidity/forward_watch.jsonl",
        "sec_10k_liquidity_forward_watch.jsonl",
    ),
    "sec_10k_liquidity_forward_watch_summary": (
        "paper_sleeves/sec_10k_liquidity/summary.json",
        "sec_10k_liquidity_forward_watch_summary.json",
    ),
    "sec_financial_report_event_sleeve_paper_snapshots": (
        "paper_sleeves/sec_financial_report/snapshots.jsonl",
        "sec_financial_report_event_sleeve_paper_snapshots.jsonl",
    ),
    "sec_financial_report_event_sleeve_paper_state": (
        "paper_sleeves/sec_financial_report/state.json",
        "sec_financial_report_event_sleeve_paper_state.json",
    ),
    "sec_governance_event_sleeve_paper_snapshots": (
        "paper_sleeves/sec_governance/snapshots.jsonl",
        "sec_governance_event_sleeve_paper_snapshots.jsonl",
    ),
    "sec_governance_event_sleeve_paper_state": (
        "paper_sleeves/sec_governance/state.json",
        "sec_governance_event_sleeve_paper_state.json",
    ),
    "sec_leadership_event_sleeve_paper_snapshots": (
        "paper_sleeves/sec_leadership/snapshots.jsonl",
        "sec_leadership_event_sleeve_paper_snapshots.jsonl",
    ),
    "sec_leadership_event_sleeve_paper_state": (
        "paper_sleeves/sec_leadership/state.json",
        "sec_leadership_event_sleeve_paper_state.json",
    ),
    "sec_negative_event_sleeve_paper_snapshots": (
        "paper_sleeves/sec_negative/snapshots.jsonl",
        "sec_negative_event_sleeve_paper_snapshots.jsonl",
    ),
    "sec_negative_event_sleeve_paper_state": (
        "paper_sleeves/sec_negative/state.json",
        "sec_negative_event_sleeve_paper_state.json",
    ),
    "space_catalyst_event_seeds": (
        "paper_sleeves/space_catalyst/event_seeds.jsonl",
        "space_catalyst_event_seeds.jsonl",
    ),
    "space_catalyst_event_state_shadow_ledger": (
        "paper_sleeves/space_catalyst/event_state_shadow_ledger.jsonl",
        "space_catalyst_event_state_shadow_ledger.jsonl",
    ),
    "space_catalyst_event_state_shadow_summary": (
        "paper_sleeves/space_catalyst/event_state_shadow_summary.json",
        "space_catalyst_event_state_shadow_summary.json",
    ),
    "space_catalyst_observation_slot_ledger": (
        "paper_sleeves/space_catalyst/observation_slot_ledger.jsonl",
        "space_catalyst_observation_slot_ledger.jsonl",
    ),
    "space_catalyst_observation_slot_summary": (
        "paper_sleeves/space_catalyst/observation_slot_summary.json",
        "space_catalyst_observation_slot_summary.json",
    ),
    "state_surface_sleeve_paper_snapshots": (
        "paper_sleeves/state_surface/snapshots.jsonl",
        "state_surface_sleeve_paper_snapshots.jsonl",
    ),
    "state_surface_sleeve_paper_state": (
        "paper_sleeves/state_surface/state.json",
        "state_surface_sleeve_paper_state.json",
    ),
}


DAILY_ARTIFACTS: dict[str, tuple[str, str]] = {
    "news": ("daily/news/raw", "news_{date}.json"),
    "news_source_stats": ("daily/news/source_stats", "news_source_stats_{date}.json"),
    "clean_news": ("daily/news/clean", "clean_news_{date}.json"),
    "clean_trade_news": ("daily/news/trade", "clean_trade_news_{date}.json"),
    "trend_signals": ("daily/signals/trend", "trend_signals_{date}.json"),
    "quant_signals": ("daily/signals/quant", "quant_signals_{date}.json"),
    "report": ("daily/reports", "report_{date}.txt"),
    "llm_prompt": ("daily/llm/prompts", "llm_prompt_{date}.txt"),
    "llm_prompt_resp": ("daily/llm/responses", "llm_prompt_resp_{date}.json"),
    "llm_decision_log": ("daily/llm/decisions", "llm_decision_log_{date}.json"),
    "llm_output": ("daily/llm/raw", "llm_output_{date}.json"),
    "investment_advice": ("daily/llm/advice", "investment_advice_{date}.json"),
    "earnings_snapshot": ("daily/snapshots/earnings", "earnings_snapshot_{date}.json"),
    "event_snapshot": ("daily/snapshots/events", "event_snapshot_{date}.json"),
    "universe_state": ("daily/universe", "universe_state_{date}.json"),
    "forward_test": ("daily/forward_tests", "forward_test_{date}.json"),
    "strategy_attribution": ("daily/forward_tests", "strategy_attribution_{date}.json"),
}


def _root(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir) if data_dir is not None else DATA_ROOT


def is_default_data_dir(data_dir: str | Path | None = None) -> bool:
    root = _root(data_dir)
    try:
        return root.resolve() == DATA_ROOT.resolve()
    except OSError:
        return False


def data_artifact_path(key: str, data_dir: str | Path | None = None) -> Path:
    """Return the organized path for a named durable data artifact.

    If a custom checkout still has the legacy root-level file and no organized
    file yet, the legacy path is returned for read/write compatibility.
    """
    organized_rel, legacy_name = DATA_ARTIFACTS[key]
    root = _root(data_dir)
    organized = root / organized_rel
    legacy = root / legacy_name
    if organized.exists() or not legacy.exists():
        return organized
    return legacy


def daily_artifact_path(
    kind: str,
    date: str,
    data_dir: str | Path | None = None,
) -> Path:
    subdir, pattern = DAILY_ARTIFACTS[kind]
    return _root(data_dir) / subdir / pattern.format(date=date)


def legacy_daily_artifact_path(
    kind: str,
    date: str,
    data_dir: str | Path | None = None,
) -> Path:
    _, pattern = DAILY_ARTIFACTS[kind]
    return _root(data_dir) / pattern.format(date=date)


def resolve_daily_artifact_path(
    kind: str,
    date: str,
    data_dir: str | Path | None = None,
) -> Path:
    path = daily_artifact_path(kind, date, data_dir)
    if path.exists():
        return path
    return legacy_daily_artifact_path(kind, date, data_dir)


def daily_artifact_glob(kind: str, data_dir: str | Path | None = None) -> list[Path]:
    root = _root(data_dir)
    subdir, pattern = DAILY_ARTIFACTS[kind]
    glob_pattern = pattern.format(date="*")
    paths = list((root / subdir).glob(glob_pattern))
    paths.extend(root.glob(glob_pattern))
    return sorted(set(paths))


def backtest_results_dir(data_dir: str | Path | None = None) -> Path:
    return _root(data_dir) / "backtests"


def backtest_result_path(date: str, data_dir: str | Path | None = None) -> Path:
    return backtest_results_dir(data_dir) / f"backtest_results_{date}.json"


def backtest_result_glob(data_dir: str | Path | None = None) -> list[Path]:
    root = _root(data_dir)
    paths = list((root / "backtests").glob("backtest_results_*.json"))
    paths.extend(root.glob("backtest_results_*.json"))
    return sorted(set(paths))


def ohlcv_snapshot_path(name: str | Path, data_dir: str | Path | None = None) -> Path:
    raw = Path(name)
    root = _root(data_dir)
    if raw.is_absolute():
        try:
            relative = raw.resolve(strict=False).relative_to(root.resolve(strict=False))
        except ValueError:
            return raw
        if relative.parts and relative.parts[0] == "ohlcv":
            return root / relative
        if raw.name.startswith("ohlcv_snapshot_"):
            candidate = root / "ohlcv" / raw.name
            if candidate.exists():
                return candidate
        return raw
    if raw.parts and raw.parts[0] == "data":
        raw = Path(*raw.parts[1:])
    if raw.parts and raw.parts[0] == "ohlcv":
        return root / raw
    if raw.name.startswith("ohlcv_snapshot_"):
        candidate = root / "ohlcv" / raw.name
        if candidate.exists():
            return candidate
    return root / raw
