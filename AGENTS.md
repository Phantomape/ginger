# AGENTS.md

> 代理进入仓库后的执行入口。这里仅保留长期有效的硬规则和单一真相源索引。具体命令、窗口、历史状态、parity 细节和实验记录放在对应文档中，不在本文件重复维护。

术语约定：**面（surface）** = 一组可归因的候选行 / forward 行及其生成器（一个数据源、观察者或 ledger）；**已结算行** = 结果窗口已走完、可计算 replacement value 的 forward 行（settled / closed 同义）；**证据轴** = novelty gate 能机器核对的"什么是真新的"声明。

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
- survival rate 不得跌破警戒线（Gate 3 口径：< 5% 时禁止继续加过滤器，见 §5）；
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
3. 禁止连续多轮只做日志、replay、parity、目录整理或文档，而不提出新的 alpha 假设。
   forward 行埋点、缺失候选匹配面构建、未饱和新数据源接入算 **alpha-enabling 工作**，不受本条
   限制——尤其当 frozen-window 面已饱和、新增证据只能来自 forward 行或新数据时。但这类工作
   同样受 §2.4 饱和治理约束：豁免覆盖"会真正产出新行"的构建，不覆盖对同一面的反复摆弄。
4. **饱和治理（硬规则）**。统一原理：**在同一证据面上重复动作不产生新证据。** 任何新实验 ID
   必须指向至少一条机器可查的新证据轴：**(a) 新数据源，(b) 新 gate shape，(c) 实质新增的已结
   算 forward 行**（相对同面上次探针，已结算行数须明显增长——默认 ≥+50% **且绝对新增 ≥10 条**，
   或达到 park 时声明的 reopen 计数；同一天的刷新不算新增。小样本翻倍不满足本轴：3→6 行满足
   +50% 但无判力，2026-07-08 同日 3 个 readiness 重审全部 rejected 即此；行数不够时正确动作是
   一行核对计数、不占 ID）；在**未饱和**源上 **(d) 无前例字段**也可作轴，但源一旦饱和即失效——XBRL /
   标签枚举可被无限满足，基准率不随之改变。**gate shape 指响应/评估结构**（entry 排除 gate、
   降权 overlay、candidate pool、notional scalar、kill switch 等）；同一源同一配方下换事件子类
   型 / item code / form type 只是换输入行，**不构成 (b)**。换阈值、换响应函数（hard exclusion →
   降权 → tilt / notional 缩放）、换切片条件、复述"还没成熟"，都**不算**。各通道的触发阈值与合法出路：

   | 通道 | 触发条件（默认阈值） | 禁止 | 合法下一步 | 强制 |
   |---|---|---|---|---|
   | 扫描源饱和 | 同 `(gate_shape, data_source)` ≥12 trials 且 accept ≤5% | 同源换字段/tag 后 override | (a)/(b)/(c) 之一 | ✅ |
   | 被拒信号 retune | 信号已被 Gate 4 拒绝 | 仅改响应函数或阈值再试 | 换信号 / (a)/(c) | ⚠️* |
   | forward 行归因 | 同一 data_source 种群连续 3 次 observed-only 收尾 | 再接一个 join / 条件字段再切片（字段"无前例"也不算轴：绑定约束是行数不是维度） | (c) 或换面 / (a)/(b)；override 用 `--observed-only-override` + 合法证据轴 | ✅ |
   | 测量修复 plumbing | 同一 `(假设, 数据面)` 连续 3 次 `accepted_measurement_repair` / `blocked` 且 0 条 gate-ready 行 | 再开一轮增量解析 / 物化 | park：记 `blocked` + 定量 `reopen_condition` | ⚠️ |
   | parked 面重开 | `reopen_condition` 计数未相对 park 时推进 | reserve ID 做 "readiness audit" | 启动前一行核对计数（不占 ID）；计数推进后重开 | ✅ |
   | 例行 delta 物化 | 已接受 observer / default-off sleeve forward ledger 的例行 delta 物化（当日行 append、outcome refresh、结算行 replacement/context enrichment）同面 ≥3 个 ID，或近 7 天跨面同形 ≥3 个 ID | 继续为日更 / 每批新结算行 reserve ID 手工物化 | 一次性接入 run.py / 结算管道（票据写明 wiring 即放行），此后例行物化不占 ID、不记 log；故障恢复豁免 | ✅ |
   | 观察者首建 | 新 observer 首建拆分超预算且首批已结算行未出现 | 把采集面 / daily wiring / 结算 ledger / 结算 wiring 拆成 >2 个 ID | 打包 ≤2 个 ID（采集面+日更一个；结算合同+结算日更一个），与 §2.5 shared-paper-first 同精神 | ⚠️ |
   | 排名/枚举清单消费 | 用同一固定评估配方逐项消费同一 ranked 候选清单**或同一有限枚举 taxonomy**（SEC 8-K item code / form type / 事件子类型、宏观指标家族×固定 relief 配方等；清单项本身构成轴 (a) 新数据源、能逐项通过 novelty gate 时**同样适用**——过 gate 不豁免本通道），车道内连续 ≥5 个 ID 全部 rejected / observed_only_rejected | 继续一项一 ID 烧完剩余清单（每项"源不同/事件不同"不构成新证据轴：配方固定时，变的只是输入行，等价于循环体展开；上一 ID reflection 点名的同源 text/字段续作仍属本车道，见 2026-07-07/08 SEC item 车道 5 连拒；再见 2026-07-11→12 宏观 relief "指标首破 20 日均线×板块 leadership" 配方 6 连拒——VVIX/SKEW/HY-OAS/MORTGAGE30US/NFCI/OVX，其中后 2 票是本通道点名"宏观指标家族"**之后**仍被逐项烧掉的：该车道已触发，剩余 relief 指标只能批量或 park） | 把剩余代表打包成**单个批量实验**一次跑完（配方固定即可循环），或 park 该车道 + 定量 `reopen_condition`（新候选家族 / 相关性结构变化 / 已结算 forward 行） | ⚠️ |

   强制列：✅ = `experiment.py new` 会自动阻断（novelty / saturation / reopen /
   observed-only streak / routine-materialization guard）；⚠️ = 仅文字规则，代理必须自查；
   \* parked 面上的 retune 措辞会被 reopen guard 拦截。阈值可用
   `GINGER_OBSERVED_ONLY_MAX_PROBES`、`GINGER_ROUTINE_MATERIALIZATION_MAX_IDS`、
   `GINGER_ROUTINE_MATERIALIZATION_WINDOW_DAYS` 调整。
   **分类器覆盖警告**：✅ guard 以 `scripts/experiment_fingerprint.py` 的 data_source 关键词
   分类为键；未收录的新种群会落到 `other` 并被 guard 直接放行——新建数据面 / observer /
   种群时必须在同一实验里给 `_DATA_SOURCE_KEYWORDS` 补关键词，否则该面的 ✅ 实际是 ⚠️
   （案例：2026-07-05/06 deep-drawdown 5 连发与 entity-theme 11 小时 3 连发均因 `other` 逃逸）。
   反向误配同样失效：关键词碰撞会把探针路由进**错误种群**（over-match），令该面的 streak /
   saturation 计数悄然错位——当 fingerprint 的 data_source 与真实证据面不符时，必须按**真实面**
   自查各通道阈值，并在 log 里记 fingerprint caveat（案例：2026-07-09 exp-016 的
   forward_replacement_value 探针因假设含 "dead-chop" 被记为 chop_forward_observer，恰逢该面
   005/006/007 三连 observed-only 收尾之后）。关键词回补本身也受 ID 预算约束：对**已存在**面的
   fingerprint 覆盖回补是同形修复，应把已知缺口打包成单个批量 measurement repair ID，禁止一面
   一 ID 地连开（案例：2026-07-07→07-10 共 14 个单面 fingerprint_coverage ID，其中 07-09/10
   窗口 5 个）。且回补只有在 `docs/frozen_families.jsonl` 用新关键词表重建后才对 guard 生效——
   close 的自动重建是 best-effort、失败只打 stderr，会静默停摆（案例：2026-07-09 09:18 起约
   24h 未重建，期间 5 个 fingerprint 修复对 novelty gate 完全 inert）；fingerprint 修复票关闭前
   必须核对输出文件已含新 key，怀疑停摆时手跑 `scripts/build_frozen_families.py`。
   **共同例外**：真正的故障恢复（orphan temp、上游格式变更、污染快照、语义相关性缺陷、发布
   异常）按 measurement repair 占 ID，不计入以上任何阈值。
   各规则的来历案例见 `docs/lessons/*.md` 与实验记录；各源实时命中率查
   `docs/frozen_families.jsonl`，不在本文件内联维护快照数字。
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
- 同机 agent 间文件对话（信箱协议、参与方式、无死锁轮次）：`docs/agent_mailbox.md`

常用工具：

- `scripts/experiment.py new|claim|close|audit`：统一实验入口；
- `scripts/claim_experiment.py`：底层 claim 工具，`experiment.py claim` 会调用它；
- `scripts/list_experiments.py`：查看 proposed / claimed / running；
- `scripts/judge_experiment.py`：before/after artifact 判定和日志草稿；
- `scripts/check_experiment_novelty.py`：自由文本假设的近邻 / 防重复检查；`experiment.py new` 已自动调用，alpha 通道默认阻断；
- `scripts/build_frozen_families.py`：从历史实验重建 `docs/frozen_families.jsonl`（novelty gate 的数据源，需定期刷新）；
- `quant/meta_research_engine.py`：研究历史、冻结方向和优先队列。
- `scripts/agent_mailbox.py send|recv|transcript|list`：同机并发 agent 间文件对话（本地、未跟踪；参与方式见 `docs/agent_mailbox.md`）。

---

## 4. 开始前必须回答

策略逻辑改动前必须能回答：

1. 本轮赚钱假设是什么？属于 entry、exit、ranking、capital allocation、risk allocation、LLM event scoring 还是 candidate pool？是否符合 playbook 当前高价值方向？
2. 过去是否做过相同或近似实验？上次参数、窗口、失败原因是什么？
   - 用 `experiment.py new` 自带的 novelty gate 回答（近邻数据 `docs/frozen_families.jsonl`，详见 `docs/agent_experiment_protocol.md` §Novelty Check）。
   - 被拦截说明撞了 frozen / 已探索 family，默认动作是**换假设**。
   - 坚持重试必须 `--novelty-override --new-evidence-axis "<到底什么是真新的>"`，且证据轴须满足 §2.4 白名单（新数据源 / 新 gate shape / 实质新增已结算行；未饱和源上还可用无前例字段）。
   - 禁止用 `--no-enforce-novelty` 或 `GINGER_NOVELTY_GATE=off` 绕过来回避这个问题。
3. 本次只检验哪一个可归因决策假设 / policy bundle？哪些只是为评估它所需的实现、parity、daily snapshot、ledger、live-realistic execution envelope 或测试？
4. 成功 / 失败验收标准是什么？是否符合 `docs/backtesting.md`？
5. 如果失败，下一位代理能否仅靠仓库记录复现实验？

若无法回答第 2-5 点，禁止开始策略逻辑改动。

`single_causal_variable` / `changed_variable` 是历史字段名，真实含义是**单一可归因决策假设**，不是只能改一个参数或一个文件。一个 accepted alpha 实验可以包含评估同一假设所需的共享 helper、historical replay、daily default-off snapshot、report/ledger wiring、parity 测试、execution envelope 和 artifact/log 更新。

---

## 5. Gate 与保留规则

任何影响买入、卖出、过滤、排序、仓位、风险预算、LLM 决策边界或回测口径的改动，都必须通过 Gate 1-4。具体命令、窗口和指标只看 `docs/backtesting.md`。

- Gate 1：读取或创建同一标准协议下的基线。
- Gate 2：列出依赖字段并验证运行时真实存在；最低检查 `entry_date` 和 `target_price`——这两个是信号合同的哨兵字段：`target_price` 在信号生成时按入场价 + 3.5×ATR 自动计算并驱动 backtester 出场，`entry_date` 是 backtester `Position` 的必需字段（实盘持仓的 entry 信息已由 moomoo 提供，但回测路径仍依赖它）。任一缺失说明信号生成或字段管道已断，不是"可选字段没填"。
- Gate 3：检查 `signals_generated` / `signals_survived` / `survival_rate`；若 survival rate < 5%，禁止继续加过滤器。
- Gate 4：同一协议重跑 before/after；默认按 `expected_value_score`、PnL、drawdown、trade count、survival、窗口稳定性和 concentration 判断。

保留规则：

- 强保留：主目标明显提升，风险和样本约束没有不可接受恶化。
- 可保留：主目标小幅提升或近似持平，同时降低复杂度、风险、生产不一致或归因缺陷。
- 条件保留：明确修复测量偏差、数据缺口或生产执行问题，并标记为 `measurement_repair`。
- 默认拒绝：主目标下降、风险恶化、只赢单一窗口、多数窗口退化、复杂度上升但证据不足，或无法归因到单一假设。

**棘轮警告**：Gate 4 是冠军挑战赛，每次接受都抬高下次门槛，系统会渐近收敛到
0-accept——这与市场是否还有残余 edge 无关。仅因 `*_not_beaten` 比较器或单窗口
噪声被拒、聚合非负的信号，"打不过冠军"不等于"组合无价值"；此类信号的组合级
评估口径见 `docs/portfolio_covariance_lane.md`（勿在单实验里自创组合验收标准）。

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

实盘对账是常驻测量合同，不是一次性实验：`data/live_pilot/live_drift/` 每日对账
moomoo 实盘持仓与回测模型期望（fill drift / trajectory drift，口径与警戒线见
`docs/live_drift_reconciliation.md`）。core bucket 触发警戒线时按 measurement_repair
插队。回测 parity 只证明"回放一致"，本合同回答"实盘是否复现模型"——两者缺一不可。

---

## 7. 记录、审计与交接

实验 ID 必须先 reserve，再写 runner、artifact、data、log。多代理时先 claim。

**并发重复 reserve（reserve 前自查）**：novelty gate 的近邻数据只来自已关闭实验
（`docs/frozen_families.jsonl`），**看不见 in-flight 票据**；并发 agent 会对同一假设各自
reserve，输家只能以 `duplicate_reservation_accounting` 收尾、白烧 ID（案例：2026-07-10/11
窗口 7 个重复票据，占当窗 26 个 ID 的 27%）。reserve 前先用 `scripts/list_experiments.py`
核对 proposed / claimed 中是否已有同假设票据；确认有并发 agent 在场时用
`scripts/agent_mailbox.py` 分工，而不是各自抢跑。**自我重试是同等祸源**：reserve 是异步
完成的，首个输出/警告之后票据仍可能落盘；调用看似超时或只回显部分输出时，重试前必须先
`list_experiments` 核对首次 reserve 是否已成功（案例：2026-07-13/14 窗口全部 4 张重复票据
exp-20260713-002/005/009、exp-20260714-001 均为单 agent 自我重试竞态，而非双 agent 抢跑）。
发现自己是输家时必须**立刻**把票据以
`duplicate_reservation_accounting` 关闭，不得悬挂在 proposed——悬挂的重复票据会污染
pre-reserve 检查面 `list_experiments` 本身（案例：2026-07-11 exp-021 与已接受的 exp-022
同假设，至 07-12 仍 proposed）。本条已机器强制（exp-20260714-007）：`experiment.py new`
对近 7 天内 open（proposed/claimed/running）票据做指纹近邻拦截，全部 lane 适用，得分
≥0.65 即阻断（校准：真重复对 0.75–0.95，同族合法邻居 ≤0.51；阈值/窗口可用
`GINGER_IN_FLIGHT_DUP_THRESHOLD` / `GINGER_IN_FLIGHT_WINDOW_DAYS` 调整）；确认 open
票据确属不同工作时用 `--in-flight-duplicate-override`。7 天窗口外的陈旧 proposed
票据不参与拦截；mailbox 分工与"输家立刻关闭"仍是 ⚠️ 自查。

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
