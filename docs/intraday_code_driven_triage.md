# 代码驱动的盘中持仓判断

本文说明 `quant/run_intraday.py` 的代码化盘中判断链路，包括 OpenD 取数、技术指标、机器 guardrail、LLM 新闻审查、最终 decision ledger 和定时任务合同。

## 1. 定位

这条链路是 **advisory-only discretionary triage**，用于回答：

- 当前全部持仓是否需要减风险；
- 哪些持仓只能持有或等待；
- 哪些持仓在满足机器条件后可以进入小额加仓复核；
- 最新新闻是否构成 thesis veto。

它不属于以下任何路径：

- `quant/run.py` 的生产信号、排序、仓位或订单；
- `quant/backtester.py` 的 Gate 1-4 策略证据；
- accepted alpha、live-ready 策略或自动下单系统。

`ADD_REVIEW_ELIGIBLE` 只表示代码没有发现预定义的硬阻断，不表示已经证明加仓有正期望，也不等于自动选择 `ADD_SMALL`。

## 2. 设计原则

盘中流程把职责分成两类：

| 层 | 负责 | 不负责 |
| --- | --- | --- |
| Python | 行情、时间、指标、持仓、退出规则、组合风险、允许动作、结构化落盘 | 新闻事件含义、未结构化催化解释 |
| LLM / agent | 核验最新新闻、判断新闻 veto、在 `allowed_actions` 内选一个动作、写短理由 | 重算指标、修改关键价位、放宽风险上限、绕过 blocker |

这样做的目的不是消灭判断，而是缩小判断面。可计算的事实只保留一个代码口径；LLM 不能凭自然语言重新解释同一套硬规则。

## 3. 组件

### 3.1 `quant/intraday_moomoo.py`

只读连接本机 moomoo OpenD，默认地址为 `127.0.0.1:11111`。

主要职责：

- 为全部真实账户持仓建立分析 universe；
- 加入杠杆 ETF 底层、行业代理、`SPY` 和 `QQQ`；
- 批量读取 `get_market_snapshot`；
- 分页读取日线和当日 5 分钟线；
- 区分 `PREMARKET`、`RTH`、`AFTER_HOURS`、`OVERNIGHT` 和 `CLOSED`；
- 按市场阶段选择 `pre_price`、`last_price`、`after_price` 或 `overnight_price`；
- 将跨日期的旧 snapshot 标记为 stale。

当前显式杠杆映射：

| 产品 | 底层 | 日内杠杆 |
| --- | --- | ---: |
| `MUU` | `MU` | 2x |
| `SNXX` | `SNDK` | 2x |
| `TQQQ` | `QQQ` | 3x |

新增杠杆产品时必须同时补 `LEVERAGED_PRODUCTS`、行业代理和测试，不能依赖 LLM 猜底层。

### 3.2 `quant/intraday_triage.py`

接收 OpenD 派生指标、现有退出复查、组合热度、现金和 pending actions，生成每个持仓的机器状态。

该模块输出：

- `machine_state`；
- `default_action`；
- `allowed_actions`；
- `blockers` 和 `risk_blocks`；
- `confirmation_level` 和 `invalidation_level`；
- `max_add_pct_existing_position`；
- 底层、行业和市场代理确认结果。

它不会创建订单，也不会自动把默认动作设置为 `ADD_SMALL`。

### 3.3 `quant/run_intraday.py`

编排现有退出复查和新增机器判断：

1. 从 `operator_inputs/open_positions.json` 读取账户持仓。
2. 使用 `open_position_schema.account_positions()` 合并 `positions`、`core_positions` 和 `observations`。
3. 下载退出规则所需的日线数据。
4. 优先使用 OpenD 当前价；缺失时回退 yfinance/EOD。
5. 运行现有 exit、regime、portfolio heat 和 pending-action 复查。
6. 运行机器 triage。
7. 输出报告、完整 JSON、OpenD artifact、LLM prompt 和 decision template。

`observations` 是真实账户暴露，只是不消耗 core slot；盘中风险计算不得遗漏。

### 3.4 `quant/finalize_intraday_decision.py`

接收代码生成的 template 和 agent 生成的 semantic response，执行最后一道结构化校验。

校验内容：

- template 中每个 ticker 必须恰好出现一次；
- 不允许额外 ticker、漏 ticker 或重复 ticker；
- `action_label` 必须属于该行的 `allowed_actions`；
- `confidence` 必须在 `[0, 1]`；
- `news_refs` 必须是列表；
- `ADD_SMALL` 至少需要一个已核验新闻 URL；
- 每一行必须有非空理由。

最终文件使用 exclusive-create 语义写入，不覆盖旧判断。

## 4. 数据与指标口径

### 4.1 当前价

| 市场阶段 | 主价格字段 |
| --- | --- |
| `PREMARKET` | `pre_price` |
| `RTH` | `last_price` |
| `AFTER_HOURS` | `after_price` |
| `OVERNIGHT` | `overnight_price` |
| 字段缺失 | `last_price`，同时标明 fallback source |

报价保留 `update_time` 和本次 `capture_time_et`。旧日期报价标记为 stale；stale 数据不能开放加仓复核。

### 4.2 日线指标

日线指标只使用判断日之前的已完成 session，当前价只用于比较和收益计算，避免盘中半根日线污染滚动统计。

当前派生字段：

- Wilder ATR14 和 `atr_pct = ATR14 / reference_price`；
- Wilder RSI14；
- SMA5、SMA10、SMA20、SMA50；
- EMA8、EMA21；
- 5 日和 20 日收益；
- 前收、开盘、日内高低、相对量能、bid/ask。

### 4.3 分时指标

当日 5 分钟线使用 `extended_time=True, session=Session.ALL`。代码拆出 RTH 后计算：

- `rth_vwap = sum(turnover) / sum(volume)`；
- 全时段 VWAP；
- RTH high/low；
- `rth_range_location = (price - rth_low) / (rth_high - rth_low)`；
- 最近 15 分钟收益；
- RTH 与全时段 bar 数量。

缺少 `reference_price`、ATR%、SMA20、EMA8 或 RTH VWAP 时，`technical_context_complete=false`，不得开放 `ADD_SMALL`。

## 5. 机器状态与动作合同

最终动作标签来自：

```text
NO_TRADE / WAIT / OPEN_SMALL / ADD_SMALL / HOLD_ONLY / REDUCE_RISK
```

当前全部输入都是已持有账户仓位，因此日常主要使用 `WAIT`、`ADD_SMALL`、`HOLD_ONLY` 和 `REDUCE_RISK`。

### 5.1 退出优先

- 已触发可执行 `EXIT` 或 `REDUCE`：`RISK_ACTION_REQUIRED`，只允许 `REDUCE_RISK`。
- `TIME_STOP REVIEW` 等复核型规则：`RULE_REVIEW_REQUIRED`，默认 `HOLD_ONLY`，允许 `HOLD_ONLY` 或 `REDUCE_RISK`，不允许加仓。
- `BREACHED` 永远优先于技术面和新闻。

### 5.2 风险阻断

以下情况不开放 `ADD_SMALL`：

- OpenD 不可用或技术字段不完整；
- 当前不在 RTH；
- position review 缺失；
- 当前价不高于 RTH VWAP、EMA8 或 SMA20；
- RTH range location 小于 `0.55`；
- 普通股票 ATR% 大于 `12%`；
- 杠杆产品 ATR% 大于 `20%`；
- 杠杆底层、行业代理或市场代理没有站上各自 RTH VWAP；
- 接近 hard/ATR/trailing stop；
- 距离现有 target 不足 `2%`；
- portfolio heat 已到 cap；
- 现金低于组合价值 `5%`；
- 存在未完成的 `EXIT`、`REDUCE` 或 `TIGHTEN_STOP` pending action。

### 5.3 加仓复核资格

只有所有 blocker 和 risk block 都为空时：

```json
{
  "machine_state": "ADD_REVIEW_ELIGIBLE",
  "default_action": "WAIT",
  "allowed_actions": ["HOLD_ONLY", "WAIT", "ADD_SMALL"]
}
```

默认动作仍然是 `WAIT`。agent 只有在新闻核验没有 veto 时，才可以选择 `ADD_SMALL`。

加仓上限按现有仓位比例表达：

- 杠杆产品或 ATR% 不低于 `8%`：最多现有仓位的 `10%`；
- ATR% 不低于 `5%`：最多 `15%`；
- 其他情况：最多 `20%`。

这是风险上限，不是目标仓位，也不是收益最优证明。

## 6. 输出文件

所有文件都位于 `data/daily/intraday/`，文件名带 ET 时间戳。

| 路径 | 内容 |
| --- | --- |
| `reports/intraday_report_*.txt` | 人类可读报告，包含退出复查和机器 guardrail |
| `snapshots/intraday_review_*.json` | 完整编排快照 |
| `market_data/intraday_opend_context_*.json` | OpenD snapshot、原始 bars 和派生指标 |
| `llm/intraday_llm_prompt_*.txt` | 只允许结构化新闻审查的 prompt |
| `decisions/intraday_decision_template_*.json` | 安全默认动作和允许动作集合 |
| `decisions/semantic_response_*.json` | agent 的结构化新闻响应 |
| `decisions/intraday_triage_*.json` | 通过校验后的不可覆盖 forward decision |

`NO_TRADE`、`WAIT` 和 `HOLD_ONLY` 也必须进入最终 ledger，否则无法计算 avoided loss、missed gain 和等待价值。

## 7. 运行与最终化

### 7.1 生成盘中快照

```powershell
cd D:\Github\ginger
.\.venv\Scripts\python.exe -B quant\run_intraday.py
```

跳过 RSS 新闻：

```powershell
.\.venv\Scripts\python.exe -B quant\run_intraday.py --no-news
```

离线 smoke：

```powershell
.\.venv\Scripts\python.exe -B quant\run_intraday.py --offline
```

离线模式不访问 OpenD 或新闻，报价回退 EOD，机器层不会开放加仓复核。

### 7.2 校验并写入最终 decision

agent 先按 prompt schema 写纯 JSON response，然后运行：

```powershell
.\.venv\Scripts\python.exe -B quant\finalize_intraday_decision.py `
  --template data\daily\intraday\decisions\intraday_decision_template_<timestamp>.json `
  --response data\daily\intraday\decisions\semantic_response_<timestamp>.json
```

校验失败时只能修正 semantic response，不能手工编辑 template、删除 blocker 或直接伪造最终 ledger。

## 8. 定时任务合同

Codex 中名称为“盘中”的任务保持原定时频率。任务只做四件事：

1. 运行 `quant/run_intraday.py`；
2. 读取本次 report、snapshot、template 和 prompt；
3. 浏览核验最新新闻并生成固定 JSON；
4. 调用 `finalize_intraday_decision.py`，再以最终 ledger 汇报。

任务不得重新执行技术指标计算，不得修改 `operator_inputs/open_positions.json`，不得下单。

## 9. 失败与降级

| 故障 | 代码行为 | 操作含义 |
| --- | --- | --- |
| OpenD 连接失败 | 退出报价回退 yfinance/EOD；机器层记录 `opend_unavailable` | 不开放加仓 |
| 部分 ticker 缺数据 | 该 ticker 标记字段不完整 | 该 ticker 使用 `WAIT`/`HOLD_ONLY` |
| 非 RTH | 记录 `outside_rth` | 不把夜盘低量波动当确认 |
| stale snapshot | `is_stale=true` | 人工核价，不增加风险 |
| 新闻无法核验 | 使用机器默认动作 | 不用模型记忆补新闻 |
| semantic response 越权 | finalizer 抛错，不写最终 ledger | 修正响应后重跑 |
| 同名最终文件已存在 | 自动增加安全后缀 | 永不覆盖历史判断 |

## 10. 测试与验证

聚焦测试：

```powershell
.\.venv\Scripts\python.exe -B -m pytest `
  quant\test_intraday_triage.py `
  quant\test_intraday_review.py `
  quant\test_run_intraday_wiring.py -q
```

包含核心回归面的验证：

```powershell
.\.venv\Scripts\python.exe -B -m pytest `
  quant\test_intraday_triage.py `
  quant\test_intraday_review.py `
  quant\test_run_intraday_wiring.py `
  quant\test_quant.py -q
```

当前实现验证了：

- 退出规则压过加仓资格；
- review-only 规则不会被误映射为强制减仓；
- 非 RTH 不开放加仓；
- 杠杆底层未确认时不开放加仓；
- 接近止损和 pending risk action 会阻断加仓；
- stale OpenD snapshot 被显式标记；
- finalizer 拒绝越过 `allowed_actions`；
- 最终 ledger 使用不可覆盖写入。

## 11. 证据升级边界

当前阈值和状态机只用于 discretionary guardrail，不是 alpha 结论。若未来要让其中任何字段直接改变生产 entry、add-on、ranking、sizing、exit 或订单，必须：

1. 提出单一可归因赚钱假设；
2. reserve/claim 实验 ID；
3. 使用 point-in-time 可回放数据；
4. 通过 Gate 1-4；
5. 实现 production/backtest shared policy；
6. 定义 live-realistic execution envelope。

forward decision ledger 的作用是积累证据，不是绕过 Gate。
