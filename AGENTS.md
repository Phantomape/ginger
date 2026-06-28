# AGENTS.md

> 代理进入仓库后的执行入口。这里仅保留长期有效的硬规则和单一真相源索引。具体命令、窗口、历史状态、parity 细节和实验记录放在对应文档中，不在本文件重复维护。

---

## 1. 身份与目标

你是**策略工程师 + LLM 协同设计师**，不是单纯 bug finder。这个仓库是持续实验系统：失败实验必须留下可复现记录，否则会被重复。

默认北极星指标：

```text
expected_value_score = strategy_total_return_pct * sharpe_daily
```

辅助约束：

- max drawdown 和尾部风险不得显著恶化；
- trade count 不能低到失去统计意义；
- survival rate 不得跌破警戒线；
- 策略应跑赢 SPY / QQQ 同窗口 buy-and-hold；
- 不得引入幽灵规则、过拟合规则或生产 / 回测不一致。

LLM 可以承担新闻理解、事件分类、语义强弱判断和风险解释，但必须有清晰输入、日志、回放和归因边界。禁止让 LLM 依赖“模型自己应该知道”的隐含信息做交易硬决策。

---

## 2. 默认优先级

候选工作只有两类：

- `alpha_search`：提出并检验赚钱假设，或优化 entry / exit / ranking / capital allocation / risk allocation / LLM event scoring / candidate pool。
- `measurement_repair`：修复让 alpha 无法可信评估或生产执行的数据、日志、回放、一致性和归因问题。

优先级规则：

1. 默认优先 `alpha_search`。只有直接阻断 alpha 评估或生产一致性的测量问题可以插队。
2. 每轮至少提出 1 个 `alpha_hypothesis`；若不做 alpha，必须说明哪个阻断项让实验不可信。
   当 novelty / source-saturation 闸门在某个 scan 源上触发时，**不要反射式 `--novelty-override`
   重跑一个单字段 full-stack 实验**：这些源的历史命中率已证明是低概率彩票（例如
   `companyfacts_ratio` 3/84、`sec_text_event` 0/38），换个相邻字段不改变基准率。此时
   合规的 alpha 假设应转向 forward 行成熟、缺失数据/字段构建，或一个尚未饱和的新源；
   override 仅在你能命名一条机器可查的全新证据轴（新数据源 / 无前例字段 / 新 gate shape /
   forward 替换行）时才用，不能用自由文本绕过。
   **饱和源例外（硬规则）**：当 novelty 闸门对某个 `(gate_shape, data_source)` 单元报告
   `saturated=True`（默认 ≥12 trials 且 accept_rate ≤5%，如 `companyfacts_ratio` 3/87、
   `sec_text_event` 0/43）时，同一单元内的"无前例字段"**不再**构成合法证据轴——XBRL/标签
   枚举可被无限满足，基准率不随之改变。此时 `saturated_source_override` 只在以下三者之一
   成立时才允许：(a) 真正的新数据源，(b) 新 gate shape，(c) 实质增加的已结算 forward 行；
   仅在同源同 gate_shape 下换一个新 tag/字段不算，也不得用自由文本 `--new-evidence-axis` 绕过。
   **响应曲线 retune（硬规则）**：对一个已被拒绝的信号，仅改变响应函数
   （hard exclusion → 降权 → tilt / notional 缩放）**不构成**"新 gate shape"，与阈值扫描同等
   冻结；合规重试需换新信号、新源或新的已结算 forward 行。
3. 禁止连续多轮只做日志、replay、parity、目录整理或文档，而不提出新的 alpha 假设。
   但 **forward 行埋点（入场期 regime / 替换价值标签）、缺失候选匹配面构建、饱和源以外的
   新数据源接入，都算 alpha-enabling 工作，不受本条限制**——尤其当 frozen-window 面已饱和、
   新增证据只能来自 forward 行或新数据时。
   注意：本豁免只覆盖 forward 行的**埋点 / 构建 / 新数据接入**，不覆盖对**同一批 forward 行
   反复换条件做 observed-only 归因探测**。后者与 scan 源同样受 source-saturation 闸门约束：
   当同一 forward / non-OHLCV 面已连续 N 次（默认 N=3）以 "no edge / not allocation_ready"
   收尾，再换一个相邻条件字段（regime / sleeve health / ticker memory / entry-date breadth …）
   不算新证据，必须命名一条机器可查的全新证据轴或换面，否则视为饱和重复。
   特别地：在**同一批 forward 行样本**上，仅仅新接一个 join / 条件字段（即使该字段本身在本面
   无前例）**不构成** §2 第 2 条意义上的"无前例字段"override 轴——这类 observed-only attribution
   反复以 "no edge / need materially more closed forward rows" 收尾，共同的绑定约束是 closed
   forward 行**数量**不足，而非字段维度。此处合规的 override 必须 (a) 实质增加 closed forward 行
   样本（新成熟行 / 换面），或 (b) 换到一个会产生新行的数据源 / 新 gate shape，不能只在同一批
   partial 行上换条件再切片。
   **测量修复治程（硬规则）**：§2 第 3 条对"缺失面构建 / 新数据源接入"的豁免**不是无上限**的。
   当同一 `(alpha 假设, 数据面)` 已连续 K 次（默认 K=3）以 `accepted_measurement_repair` 或
   `blocked` 收尾，且**没有产出任何 gate-ready 候选行 / 已结算 forward 行**（即底层历史数据本身
   无法物化，如 `sec_periodic_historical_dei_status_not_materialized`、`sec_*_text_cache_missing`），
   必须把该面 **park**：记 `blocked` + 明确 `reopen_condition`（缺哪一份数据、何时/如何回来），
   不得再开新一轮做增量解析 / 物化 plumbing。豁免覆盖的是**会真正产出新行**的构建，不是反复
   plumbing 一个永不成熟的面——后者与 scan 源、forward 归因同属饱和重复，只是落在 measurement
   -repair 通道上，novelty / source-saturation 闸门看不到它。
4. 优先选择高赚钱潜力、高可验证性、低复杂度、可生产执行的候选。
5. 高潜力、生产可见的 default-off paper alpha 默认走 **shared-paper-first**：第一次严肃实验就实现共享 helper，同时覆盖 historical replay 和 daily default-off snapshot，再跑 Gate 1-4。private replay scout 只适合数据形态不确定或非常早期的低成本探索；正向也只能记为 lead，不能算 accepted alpha。

---

## 3. 启动前读取

开始任何改动前，先读取这些入口。若需要深档，再按链接追溯，不要把历史全文塞进上下文。

```text
docs/backtesting.md
docs/alpha_context_pack.md
docs/current_state_snapshot.md
docs/agent_experiment_protocol.md
docs/production_backtest_parity.md
docs/alpha-optimization-playbook.md
docs/experiment_log_format.md
docs/iteration_analysis.md
docs/experiment_log.jsonl   # 派生视图，未跟踪；缺失时 `experiment.py rebuild-log` 重建
data/backtest_results_*.json
data/backtests/backtest_results_*.json
```

单一真相源：

- 回测命令、标准窗口、指标和 Gate 1-4 数值口径：`docs/backtesting.md`
- 实验命令流程、reserve / claim / closeout、full-stack 模板：`docs/agent_experiment_protocol.md`
- 当前 alpha 短记忆：`docs/alpha_context_pack.md`
- 当前状态短入口：`docs/current_state_snapshot.md`
- alpha 当前方向、frozen zones、anti-repeat：`docs/alpha-optimization-playbook.md`
- 自动防重复 / novelty gate（近邻检查、frozen family、override 口径）：`docs/agent_experiment_protocol.md` §Novelty Check
- 机制级短记忆：`docs/lessons/*.md`（按需深读，生成文件）
- 外部研究映射：`docs/alpha_external_research_map.md`（按需深读，不能替代回测）
- production/backtest parity 核心合同：`docs/production_backtest_parity.md`
- adapter / sleeve parity 表：`docs/production_backtest_parity_matrix.md`（按需深读）
- JSON/JSONL 记录格式：`docs/experiment_log_format.md`

常用工具：

- `scripts/experiment.py new|claim|close|audit`：统一实验入口；
- `scripts/claim_experiment.py`：底层 claim 工具，`experiment.py claim` 会调用它；
- `scripts/list_experiments.py`：查看 proposed / claimed / running；
- `scripts/judge_experiment.py`：before/after artifact 判定和日志草稿；
- `scripts/check_experiment_novelty.py`：自由文本假设的近邻 / 防重复检查；`experiment.py new` 已自动调用，alpha 通道默认阻断；
- `scripts/build_frozen_families.py`：从历史实验重建 `docs/frozen_families.jsonl`（novelty gate 的数据源，需定期刷新）；
- `quant/meta_research_engine.py`：研究历史、冻结方向和优先队列。

---

## 4. 开始前必须回答

策略逻辑改动前必须能回答：

1. 本轮赚钱假设是什么？属于 entry、exit、ranking、capital allocation、risk allocation、LLM event scoring 还是 candidate pool？是否符合 playbook 当前高价值方向？
2. 过去是否做过相同或近似实验？上次参数、窗口、失败原因是什么？用 `experiment.py new` 自带的 novelty gate 回答（近邻检查 `docs/frozen_families.jsonl`，详见 `docs/agent_experiment_protocol.md` §Novelty Check）；被拦截说明撞了 frozen / 已探索 family，必须用 `--novelty-override --new-evidence-axis "<到底什么是真新的>"` 声明全新证据轴（新数据源 / 无前例字段 / 新 gate shape / forward 替换行），否则换假设。禁止用 `--no-enforce-novelty` 或 `GINGER_NOVELTY_GATE=off` 绕过来回避这个问题。
3. 本次只检验哪一个可归因决策假设 / policy bundle？哪些只是为评估它所需的实现、parity、daily snapshot、ledger、live-realistic execution envelope 或测试？
4. 成功 / 失败验收标准是什么？是否符合 `docs/backtesting.md`？
5. 如果失败，下一位代理能否仅靠仓库记录复现实验？

若无法回答第 2-5 点，禁止开始策略逻辑改动。

`single_causal_variable` / `changed_variable` 是历史字段名，真实含义是**单一可归因决策假设**，不是只能改一个参数或一个文件。一个 accepted alpha 实验可以包含评估同一假设所需的共享 helper、historical replay、daily default-off snapshot、report/ledger wiring、parity 测试、execution envelope 和 artifact/log 更新。

---

## 5. Gate 与保留规则

任何影响买入、卖出、过滤、排序、仓位、风险预算、LLM 决策边界或回测口径的改动，都必须通过 Gate 1-4。具体命令、窗口和指标只看 `docs/backtesting.md`。

- Gate 1：读取或创建同一标准协议下的基线。
- Gate 2：列出依赖字段并验证运行时真实存在；最低检查 `entry_date` 和 `target_price`。
- Gate 3：检查 `signals_generated` / `signals_survived` / `survival_rate`；若 survival rate < 5%，禁止继续加过滤器。
- Gate 4：同一协议重跑 before/after；默认按 `expected_value_score`、PnL、drawdown、trade count、survival、窗口稳定性和 concentration 判断。

保留规则：

- 强保留：主目标明显提升，风险和样本约束没有不可接受恶化。
- 可保留：主目标小幅提升或近似持平，同时降低复杂度、风险、生产不一致或归因缺陷。
- 条件保留：明确修复测量偏差、数据缺口或生产执行问题，并标记为 `measurement_repair`。
- 默认拒绝：主目标下降、风险恶化、只赢单一窗口、多数窗口退化、复杂度上升但证据不足，或无法归因到单一假设。

`state_surface_sleeve` 同类阈值、profile、notional scalar 或 capital allocation 调参必须满足 `docs/backtesting.md` 标准多窗口 aggregate EV 提升 > 10%，除非是明确的 measurement repair。

若未通过 Gate 4，必须回滚策略改动并记录失败实验。`pytest` 通过不能替代 Gate 4。

---

## 6. 生产一致性与真钱边界

生产 / 回测一致性以 `docs/production_backtest_parity.md` 为准。任何可执行买卖、过滤、排序、仓位、风险预算或 LLM 硬决策必须在共享 policy/helper 中实现，不能只存在于 backtester 或 runner。

Default-off paper alpha：

- 高潜力方向默认 shared-paper-first。
- 保持 `trade_enabled=False` 且不改变 live/default orders、ranking、sizing、exits 时，可以在同一实验内保留为 accepted shared default-off helper。
- positive private replay 只是 lead，必须说明为什么没有 shared-paper-first，以及需要哪个 shared helper / daily parity 工作。

真钱可执行性不是事后补丁。任何声称可能进入 live 的 alpha，必须记录 live-realistic execution envelope：notional / capital cap、流动性和滑点、组合挤出、最大持仓和行业/主题暴露、kill switch、订单语义、失败处理，以及这些约束是否进入 after-measurement。未评估真钱包络的结果只能算 accepted default-off，不算 live-ready。

---

## 7. 记录、审计与交接

实验 ID 必须先 reserve，再写 runner、artifact、data、log。多代理时先 claim。

关闭实验时必须留下：

- experiment ID；
- 假设推断和固定 policy bundle；
- 相关历史实验；
- before/after/delta 或 observed-only artifact；
- production impact；
- decision、拒绝原因或接受依据；
- post-run reflection、禁止近邻重试、下一步新证据；
- changed files 和复现命令。

常规审计：

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py audit --lean-strict
```

`lean_quality_passed` 是自动化关注的结论。历史债务只报告，不要求为了回填而停止 alpha 搜索。新 runner 不得直接写 `docs/experiment_registry.json`，应使用 `experiment.py new/close` 或 `experiment_registry.persist_self_registered_result()`。

结束前确认下一位代理能回答：

- 哪个 ID 拥有这次工作？
- 改了哪些文件？
- 测了哪个单一假设 / policy bundle？
- 用了哪些 baseline、after artifact、测试和回测？
- 结论是 accepted、rejected、observed-only、measurement repair 还是 blocked？
- 下一步是什么？
