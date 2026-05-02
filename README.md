# Ginger 量化辅助交易系统

Ginger 是一个每日运行一次的中短线交易辅助系统。它用共享的量化规则生成买卖、加仓、减仓和风控信息，再把新闻与持仓上下文整理成可审计的 LLM 提示词。

核心原则：

- 代码负责硬规则：信号、仓位、止损、目标位、组合热度、候选排序。
- LLM 负责语义判断：新闻理解、事件分级、灾难 veto、模糊风险解释。
- 生产和回测必须尽量同源；不能把只在回测里赚钱的逻辑当成生产 alpha。
- 新 ticker 先通过 point-in-time universe governance 和 pilot sleeve 验证，不能直接污染 core universe。

## 文档优先级

README 是使用入口。策略实验、回测口径、生产/回测一致性和 LLM 边界以这些文档为准：

- `AGENTS.md`
- `docs/alpha-optimization-playbook.md`
- `docs/backtesting.md`
- `docs/production_backtest_parity.md`
- `docs/universe_promotion_protocol.md`
- `docs/universe_governance_rollout_plan.md`

如果 README 和代码或上述文档冲突，以代码和规范文档为准。

## 快速开始

```powershell
cd D:\Github\ginger
pip install -r news_collector\requirements.txt
```

编辑持仓文件：

```powershell
notepad data\open_positions.json
```

日常运行：

```powershell
.\.venv\Scripts\python.exe quant\run.py
```

如果没有使用虚拟环境，也可以用：

```powershell
python quant\run.py
```

运行后重点看：

- `data\report_YYYYMMDD.txt`：人类可读日报。
- `data\quant_signals_YYYYMMDD.json`：完整量化信号。
- `data\llm_prompt_YYYYMMDD.txt`：可复制给 ChatGPT / Claude 的提示词。
- `data\llm_decision_log_YYYYMMDD.json`：LLM 决策日志，如果当天调用了 LLM。

## 日常交易用法

日常入口没有改变，仍然跑：

```powershell
.\.venv\Scripts\python.exe quant\run.py
```

核心交易信号仍在：

```text
data\quant_signals_YYYYMMDD.json -> signals
```

AI infrastructure pilot sleeve 信号单独在：

```text
data\quant_signals_YYYYMMDD.json -> pilot_signals
```

当前真钱 pilot sleeve：

| 字段 | 当前值 |
| --- | --- |
| Sleeve | `AI_INFRA_PILOT` |
| Trade-enabled tickers | `INTC`, `LITE`, `BE` |
| 生效日期 | `2026-05-01` |
| Core promotion | 否 |
| 最大同时 pilot 持仓 | 1 |
| 归因方式 | 入场前冻结 counterfactual snapshot |

重要解释：

- `pilot_signals` 为空时，不做 pilot 新开仓。
- `pilot_signals` 不为空时，它是真钱 pilot 候选，但仍要和 core signals 分开看。
- pilot 会使用正常 signal chain，再经过 `quant\pilot_sleeve.py` 做风险缩放、slot 限制和 pre-trade counterfactual logging。
- pilot 入场会带 `pilot_sleeve`、`pilot_entry_execution_plan`、`pilot_decision_hashes` 等字段。
- pilot 平仓后，如果交易记录带有 frozen `decision_id`，日报和 `quant_signals_YYYYMMDD.json` 会在 `pilot_attribution` 汇总 direct PnL、cash-relative PnL、replacement value 和 pending counterfactual coverage。
- INTC / LITE / BE 不是 core ticker。它们只是通过 pilot sleeve 收集 forward evidence。

如果配置了 OpenAI API key，系统会尝试生成 LLM 决策；如果 API 不可用，仍可使用 `llm_prompt_YYYYMMDD.txt` 手动复制给 ChatGPT / Claude。

## 标准回测

标准回测仍然用 `quant\backtester.py`。按 `docs/backtesting.md`，当前固定看三个非重叠窗口：

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-23 --end 2026-04-21 --ohlcv-snapshot data\ohlcv_snapshot_20251023_20260421.json
```

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-04-23 --end 2025-10-22 --ohlcv-snapshot data\ohlcv_snapshot_20250423_20251022.json
```

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2024-10-02 --end 2025-04-22 --ohlcv-snapshot data\ohlcv_snapshot_20241002_20250422.json
```

关键口径：

- 标准三窗口是 core strategy 回测。
- `INTC` / `LITE` / `BE` 的 `first_trade_allowed_as_of` 是 `2026-05-01`。
- 因为标准窗口都早于 `2026-05-01`，所以标准回测不会把 pilot ticker 塞进历史 core universe。
- 这不是漏接，而是 point-in-time 防未来泄漏。
- 想看 pilot 的历史静态研究价值，需要单独标注为 static pool experiment，不能当生产级证据。
- pilot 的生产级证据从 `2026-05-01` 之后的 forward decisions、direct PnL、replacement value、risk-adjusted replacement value 开始积累。

最新 pilot sleeve 激活时的标准三窗口结果记录在：

- `docs\experiments\logs\exp-20260501-029.json`
- `docs\experiments\tickets\exp-20260501-029.json`

## Pilot sleeve replay backtest

Default backtests remain core-only. To replay the AI infrastructure pilot
sleeve (`AI_INFRA_PILOT`) with point-in-time universe eligibility, add
`--include-pilot-sleeve`:

```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2025-10-23 --end 2026-04-21 --ohlcv-snapshot data\ohlcv_snapshot_20251023_20260421.json --include-pilot-sleeve
```

This is called `试点子组合回测` in the docs. It preloads eligible pilot OHLCV
as of the backtest end date, but daily trading eligibility is still decided
from `data\universe_events.jsonl` point-in-time. Historical windows before
`2026-05-01` should show `pilot_sleeve_replay.entries == 0`; that is the
expected no-leakage result.

## 持仓配置

编辑 `data\open_positions.json`：

```json
{
  "portfolio_value_usd": 70000,
  "cash_usd": 5000,
  "positions": [
    {
      "ticker": "NVDA",
      "direction": "long",
      "shares": 41,
      "avg_cost": 102.17,
      "entry_date": "2025-11-15",
      "target_price": 145.0,
      "risk_notes": "core AI holding"
    }
  ]
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `portfolio_value_usd` | 是 | 账户总市值，含现金，用于热度和仓位计算。 |
| `cash_usd` | 推荐 | 现金余额，用于实时组合价值和可交易性判断。 |
| `ticker` | 是 | 股票代码，大写。 |
| `shares` | 是 | 持仓股数。 |
| `avg_cost` | 是 | 平均成本。 |
| `entry_date` | 推荐 | 建仓日期，缺失会影响 time stop。 |
| `target_price` | 推荐 | 原始信号目标价，缺失会影响 signal target exit。 |
| `override_stop_price` | 可选 | 手动止损价，适合保本止损或风险事件后收紧。 |

## 系统流程

```text
quant\run.py
  -> open_positions.json        持仓和账户状态
  -> universe_adapter.py        point-in-time universe governance
  -> pilot_sleeve.py            pilot ticker 风险缩放和 counterfactual snapshot
  -> regime.py                  SPY/QQQ 市场状态
  -> data_layer.py              OHLCV 和 earnings 数据
  -> feature_layer.py           技术和事件特征
  -> signal_engine.py           trend / breakout / earnings 信号
  -> risk_engine.py             R:R、TQS、止损止盈
  -> portfolio_engine.py        core 仓位和组合热度
  -> preflight_validator.py     现有持仓硬风控预判
  -> sources.py + filter.py     RSS 新闻收集和过滤
  -> llm_advisor.py             LLM prompt / decision log
```

## 输出文件

| 文件 | 说明 |
| --- | --- |
| `data\report_YYYYMMDD.txt` | 人类可读日报。 |
| `data\quant_signals_YYYYMMDD.json` | 完整量化输出，含 core `signals` 和 pilot `pilot_signals`。 |
| `data\quant_signals_YYYYMMDD.json -> pilot_attribution` | Pilot direct PnL、replacement value 和 counterfactual coverage。 |
| `data\trend_signals_YYYYMMDD.json` | 持仓状态和 exit 信号。 |
| `data\llm_prompt_YYYYMMDD.txt` | LLM 输入提示词。 |
| `data\llm_decision_log_YYYYMMDD.json` | LLM 决策日志。 |
| `data\news_YYYYMMDD.json` | 原始新闻。 |
| `data\clean_trade_news_YYYYMMDD.json` | 交易相关过滤后新闻。 |
| `data\universe_state_YYYYMMDD.json` | 当日 universe governance 状态。 |

## 实验记录

策略修改和失败尝试必须落盘：

- `docs\experiment_log.jsonl`：结构化实验主日志。
- `docs\experiments\logs\`：单个实验详细记录。
- `docs\experiments\tickets\`：实验 ticket。
- `docs\experiment_log_format.md`：字段说明。

原则：

- 成功实验要记录。
- 失败实验更要记录。
- 记录必须包含参数、窗口、改前/改后指标、生产影响和失败原因。
- 涉及生产/回测一致性的改动必须声明 `production_impact`。

## 开发和测试

常规测试：

```powershell
python -m pytest quant\test_quant.py -v
```

Pilot sleeve 相关测试：

```powershell
python -m pytest quant\test_pilot_sleeve.py quant\test_universe_manager.py quant\test_universe_adapter.py quant\test_sources.py
```

提交前至少确认：

- 改动是否只改变一个独立因果变量。
- 是否跑了对应测试或说明为什么没跑。
- 策略逻辑是否同时被生产和回测共享，或已写入 `docs\production_backtest_parity.md` 作为允许差异。
- 如果是 alpha 实验，是否按三窗口记录结果。
