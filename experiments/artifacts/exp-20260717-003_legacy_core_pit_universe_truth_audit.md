# exp-20260717-003 核心选股池 PIT 真相审计

## 结论

本实验以 `accepted_measurement_repair` 收尾，不接受新 alpha，不替换 Gate-1，也不改变 live/default 订单。

最强可恢复结论是：从量化管道首次可被 Git 证明存在后的下一个交易日（2026-03-16）到 2026-04-21，当前静态池与当时 Git 可证明的入场池结果完全一致，均为 EV `0.1251`、PnL `$3,297.89`、2 笔交易；因此这段极小样本内**没有检测到**池成员前视泄露。但它只有约 27 个交易日和 2 笔交易，且底层 OHLCV 仍使用当前存续证券名册，不能证明更早历史或退市样本没有泄露。

一个更宽但较弱的 2026-01-23 至 2026-04-21 名单代理敏感性检验显示：当前静态池比 13 只 Git 可见名单多 `$12,835.39` PnL、`0.3333` EV 和 4 笔交易；8 笔静态入场中有 5 笔当日不在该名单，直接交易 PnL 合计 `$12,024.58`。但 2026-03-16 前尚无可恢复的量化交易管道，故这是**名单代理差异敏感性**，不是已证明的实盘/量化泄露。

因此，活跃 Gate-1 的 aggregate EV `6.2057`、PnL `$130,992.36`、49 笔交易继续保留为行为回归锚点，但不应解释为无偏 expected alpha。

## 假设与冻结合同

- 实验 ID：`exp-20260717-003`
- lane：`measurement_repair`
- 单一可归因变量：core 入场资格身份，从当前静态池切换为 Git 可证明、按生效日解析的 immutable membership。
- 锁定：信号、排序、仓位、退出、成本、现金账本、三个标准窗口、live/default 行为。
- 相关实验：`exp-20260627-017`、`exp-20260627-019`、`exp-20260628-005`、`exp-20260712-015`、`exp-20260715-010`。
- 新证据轴：新的 gate shape——逐日 PIT 入场资格、generated/survived/trade provenance，以及从明确 cutoff 起的 append-only 全量 broad membership。

## Git 可证明的历史边界

| 生效日 | 可证明事实 | 成员数 | 解释 |
|---|---|---:|---|
| 2026-01-23 | 仓库首次出现 `WATCHLIST` | 13 | 只能证明注意名单，尚不能证明量化交易池 |
| 2026-03-16 | `quant/data_layer.py` 导入该名单且 `quant/run.py` 调用 universe 的首个后续交易日 | 13 | 最早严格可识别的量化池比较起点 |
| 2026-04-06 | base watchlist 扩展 | 43 | 后续交易日按新成员生效 |

2026-01-23 前没有可恢复的入场成员快照。当前 warehouse security master 仍缺少大量已退市或被收购证券，因此本 manifest 只是可审计下界。

## Gate 1–4

### Gate 1：锚点保持精确

默认静态路径在三个标准窗口对 `exp-20260715-010` 均逐项精确，包括 EV、PnL、交易数、生成/存活信号、survival、交易行 hash 与日收益序列 hash。

| 窗口 | EV | PnL | 交易 | generated / survived | survival |
|---|---:|---:|---:|---:|---:|
| late | 4.1067 | $70,075.18 | 13 | 54 / 48 | 88.89% |
| mid | 1.9908 | $51,976.41 | 13 | 69 / 56 | 81.16% |
| old | 0.1082 | $8,940.77 | 23 | 65 / 60 | 92.31% |
| aggregate | 6.2057 | $130,992.36 | 49 | — | min 81.16% |

### Gate 2：字段与归因合同

默认信号合同中的 `entry_date` 与 `target_price` 保持不变。新增 resolver 对未知 ticker、非 resolved/缺 provenance 响应和首个 snapshot 前日期 fail-closed；每个 generated、survived signal 与实际入场均记录 membership effective date、snapshot hash 与解析状态。退池不会强制平掉既有仓位，既有仓位仍按原退出规则和完整 data-universe 风控特征运行，但不得再安排或执行 addon 增仓。

### Gate 3：样本生存

- 完整 PIT lower-bound 的 late 窗口：12 generated、8 survived，survival `66.67%`，4 笔交易。
- mid/old 全部处于首个可识别 membership 之前，状态为 `N/A/unidentifiable`，不得错误解释为零收益或零存活。
- 严格量化时期切片：5 generated、4 survived，survival `80%`，2 笔交易。

### Gate 4：只接受测量修复

- PIT、watchlist proxy、strict quant-era 三组 replay 均 double-run deterministic。
- 每条现金路径均非负且 cash conservation 通过。
- 默认静态行为完全不变；PIT resolver 是显式 opt-in。
- 结论不接受 alpha、不开真钱、不替换 Gate-1。

## 历史结果

### 完整 PIT lower-bound

- late：EV `0.0048`、PnL `$1,335.28`、daily Sharpe `0.36`、4 笔交易。
- 该窗口 123 个交易日中只有 61 日可识别，62 日不可识别；eligible count 从 13 变为 43。
- mid 与 old 没有可识别 membership，结果不能用于收益比较。

### 2026-01-23 起的 watchlist-proxy 敏感性

| 路径 | EV | PnL | daily Sharpe | 交易 | generated |
|---|---:|---:|---:|---:|---:|
| 当前静态池 | 0.3401 | $14,170.67 | 2.40 | 8 | 24 |
| Git 名单代理 | 0.0068 | $1,335.28 | 0.51 | 4 | 12 |
| static - proxy | +0.3333 | +$12,835.39 | — | +4 | +12 |

不在代理名单的 5 次静态入场为 `GLD`、`CAT`、`CVX`、`XOM`、`CVX`。其直接 PnL 合计 `$12,024.58`，占静态切片 PnL 的 `84.86%`。由于资本竞争和路径依赖，整体 delta 不能简单等同于这些交易 PnL 之和。

### 最严格的量化管道时期

2026-03-16 至 2026-04-21：当前静态池与 Git-proven PIT 路径完全相同，EV `0.1251`、PnL `$3,297.89`、daily Sharpe `3.79`、最大回撤 `1.25%`、2 笔交易、5/4 generated/survived；delta 全为零，无不合格入场。

正确解释是“这个很小的可识别样本没有检测到泄露”，不是“历史系统已被证明无泄露”。

## Broad pool 的 clean-forward 起点

- 自 2026-07-17 起冻结全量 membership：1,232 个 ticker。
- membership hash：`8908319b1a57cbcaa06cf1631765c8ff76b0b3165b27c3ebc672d1c7888ed77f`。
- append 同日同内容幂等；同日冲突 fail-closed。
- 退池但仍 pending/open 的 ticker 会继续取行情、计价、老化和退出，避免因退池产生幽灵 PnL。
- clean generation 初始 settled rows 为 0；只有 cutoff 后、绑定持久化 snapshot 的新入场才可算 clean alpha evidence。
- 旧 broad ledger 有 84 行/56 个日期、3 个已关闭、PnL `-$8,178.37`；2026-06-11 后仍是 0 个已关闭，5 个 open。修复前 `BKSY`、`PL` 的 open mark 已陈旧，现已补上持续计价合同。

## 生产影响

无 live/default 订单、信号、排序、仓位、退出或风险预算变化。backtester 默认静态模式不变；PIT 只在显式 resolver 下启用。broad paper feed 从 clean cutoff 起写 append-only membership，并继续维护 legacy carry 仓位。

## 遗憾、未知与禁止重试

最大的遗憾不是“已经证明泄露很多”，而是过去没有冻结每日候选池，所以大部分历史不可证伪。最大的未知是 current-roster survivorship bias：退市/并购证券缺失可能同时高估或低估历史表现，其方向和幅度目前不可识别。

禁止把 2026-01-23 的 13 只注意名单当成量化生产池后再声称 `$12,835.39` 是已证明泄露；也禁止用同一残缺历史换阈值、换名单版本或增加过滤器来重试。历史面只有新增真实 PIT 数据源或可恢复的退市证券主表才值得重开。

下一条 alpha 假设是：广域 PIT 候选池通过横截面排序和组合协方差约束，可能捕获 narrow core 漏掉且与 core 低相关的机会；但它必须等到至少 60 条 clean settled forward rows、覆盖至少 20 个不同 ticker 后，才做 replacement-value / SPY / QQQ / core 组合比较，不能用当前残缺历史回填“证明”。

## 文件与复现

主要实现：

- `quant/entry_universe_ledger.py`
- `quant/backtester.py`
- `quant/broad_market_universe_feed.py`
- `quant/broad_market_paper_sleeve.py`
- `quant/experiments/exp_20260717_003_legacy_core_pit_universe_truth_audit.py`
- `scripts/experiment_fingerprint.py`

证据：

- `data/experiments/exp-20260717-003/before_measurement.json`
- `data/experiments/exp-20260717-003/after_measurement.json`
- `data/experiments/exp-20260717-003/git_proven_core_membership.jsonl`
- `data/state/broad_market_paper/universe_membership.jsonl`

复现：

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260717_003_legacy_core_pit_universe_truth_audit.py
.\.venv\Scripts\python.exe -B -m pytest quant\test_entry_universe_ledger.py quant\test_experiment_fingerprint.py quant\test_broad_market_universe_feed.py quant\test_broad_market_paper_sleeve.py quant\test_quant.py -q
.\.venv\Scripts\python.exe -B -m pytest quant\test_run_daily_wiring.py quant\test_paper_sleeve_runner.py -q
```

验证：`531 + 53 = 584 passed`；`git diff --check` 通过（仅现有 LF/CRLF 提示）。
