from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"


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
