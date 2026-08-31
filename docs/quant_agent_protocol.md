# Ginger V1 Quant Agent Protocol（历史版本）

> 本文件保留 V1 规则和事故上下文，只用于历史追溯。新的 V2 量化任务以
> `docs/quant_agent_protocol_v2.md` 为准。
>
> 这里仅保留 V1 长期规则和单一真相源索引。具体命令、窗口、历史状态、parity 细节和实验记录放在对应文档中，不在本文件重复维护。

术语约定：**面（surface）** = 一组可归因的候选行 / forward 行及其生成器（一个数据源、观察者或 ledger）；**已结算行** = 结果窗口已走完、可计算 replacement value 的 forward 行（settled / closed 同义）；**证据轴** = novelty gate 能机器核对的"什么是真新的"声明。

---

## 1. 身份与目标

你是**策略工程师 + LLM 协同设计师**，不是单纯 bug finder。这个仓库是持续实验系统：失败实验必须留下可复现记录，否则会被重复。

默认北极星指标：

```text
expected_value_score = strategy_total_return_pct * abs(sharpe_daily)
```

`strategy_total_return_pct` 决定分数方向；`abs(sharpe_daily)` 只提供风险调整后的
幅度。这样总收益和 Sharpe 同为负时不会负负得正，把稳定亏损误标成正 EV。

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
   标签枚举可被无限满足，基准率不随之改变。**轴 (a) 指真正新的独立数据源**：已探索源之间的
   cross-source join / 交叉切片**不构成 (a)**——join 只是配方，变的仍是输入行；且 join 面在
   fingerprint 里常被误判为其中一个未饱和成员源，令机器 novelty gate 放行非法 override（案例：
   2026-07-20 exp-002 以 "FINRA ATS × FINRA short-interest join" 声明新源过 override，手工三源
   审计判非法、Gate 前自拒烧 ID）。声明含 join 的证据轴时，必须在 reserve **前**对每个成员源
   分别自查饱和 / frozen 状态，任一成员已饱和或已被拒即不得以 join 名义 override。
   **gate shape 指响应/评估结构**（entry 排除 gate、
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
   | 排名/枚举清单消费 | 用同一固定评估配方逐项消费同一 ranked 候选清单**或同一有限枚举 taxonomy**（SEC 8-K item code / form type / 事件子类型、宏观指标家族×固定 relief 配方等；清单项本身构成轴 (a) 新数据源、能逐项通过 novelty gate 时**同样适用**——过 gate 不豁免本通道），车道内连续 ≥5 个 ID 全部 rejected / observed_only_rejected | 继续一项一 ID 烧完剩余清单（每项"源不同/事件不同"不构成新证据轴：配方固定时，变的只是输入行，等价于循环体展开；上一 ID reflection 点名的同源 text/字段续作仍属本车道，见 2026-07-07/08 SEC item 车道 5 连拒；再见 2026-07-11→12 宏观 relief "指标首破 20 日均线×板块 leadership" 配方 6 连拒——VVIX/SKEW/HY-OAS/MORTGAGE30US/NFCI/OVX，其中后 2 票是本通道点名"宏观指标家族"**之后**仍被逐项烧掉的：该车道已触发，剩余 relief 指标只能批量或 park；三见 2026-07-14→17 "官方发布×固定应答（篮子/peer/pair）"车道：合法批量出口已用过（exp-20260714-002）且 07-15 反思点名 park 后，仍被逐源一 ID 续烧——PCAOB Form AP exp-20260716-005、Fed H.8 exp-20260717-004 均拒，累计 8+ 连拒；本案例写入本文件**当天**又烧 TSA 周客流 exp-20260717-005（累计 9+），且该票在源合同 preflight 即拒——**在 Gate 2-4 之前因 PIT/源合同失败收尾同样计入车道连拒**，"还没读价格"不豁免；"新联邦数据源 + 微调应答形状"不重置本车道，批量出口每车道只能用一次；四见 2026-07-18→19 开发者生态计数源 3 连拒——HN owned-domain attention exp-20260718-006、deps.dev Maven releases exp-20260719-001、Linux mainline signed RC contributions exp-20260719-002，配方同为"公开周期计数×加速超前窗中位数×top-N 篮子×固定 hold"，与官方发布车道同形：**换成非官方/开发者数据源不重置本车道**，第 4 票起只能批量或 park） | 把剩余代表打包成**单个批量实验**一次跑完（配方固定即可循环），或 park 该车道 + 定量 `reopen_condition`（新候选家族 / 相关性结构变化 / 已结算 forward 行） | ✅* |

   强制列：✅ = `experiment.py new` 会自动阻断（novelty / saturation / reopen /
   observed-only streak / routine-materialization guard）；⚠️ = 仅文字规则，代理必须自查；
   \* parked 面上的 retune 措辞会被 reopen guard 拦截。✅\* = 排名/枚举清单消费通道自
   2026-07-21（exp-20260721-005）起由 recipe-lane guard 机器阻断，但**只覆盖
   `docs/recipe_lanes.jsonl` 中已登记的车道**（短语簇匹配"源簇×应答簇"）；新车道在
   reflection 点名 park 时必须在同一实验里向该文件追加条目，否则该车道仍是 ⚠️。批量出口
   须在假设里显式写 "single pooled batch"（每车道一次，用后把 `batch_exit_used` 置 true）；
   误伤合法新机制时用 `--recipe-lane-override` + `--new-evidence-axis` 说明配方为何被打破。阈值可用
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
   005/006/007 三连 observed-only 收尾之后）。over-match 不限于数据面探针：**非数据面票据**
   （workflow / governance / tooling repair）的假设措辞撞上数据源关键词时，会把 trial 记到
   无关真实源的 `(gate_shape, data_source)` 计数上（案例：2026-08-05 exp-002 三命令 facade
   工具票被归为 `sec_text_event` 源并计入 has_accepted，扰动该源饱和分母）；此类票据 reserve
   后应核对 fingerprint data_source 是否落在 `other` / 工作流类，误配时在票据里记 caveat。关键词回补本身也受 ID 预算约束：对**已存在**面的
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
6. **历史只做约束，不做候选生成排序。** `frozen_families`、失败记录和 trial accounting 用于去重、反证、multiple-testing 与 reopen 审计；禁止按历史赢家、既有 adapter 成熟度或旧实验分数给下一轮 hypothesis family 排优先级。exploration / adjacent / exploitation 的生成预算必须在读候选 outcome 前按机制覆盖预声明，历史成功率不得把搜索分布重新吸回局部最优。

### Alpha Synthesis Pass（不占实验 ID）

本 V1 协议的 novelty / saturation / Gate 规则负责**裁决假设**，不得反过来压制**生成假设**。
当任务是全持仓评估、股票池扫描、买卖/抄底选择或 alpha 搜索时，reserve 前必须先执行一次
不占实验 ID、不得改变策略或订单的 synthesis pass：

1. **横截面机会成本**：不得只分析用户点名 ticker；须在同一时点、同一可交易股票池中比较，
   回答是否存在风险收益更好的候选。单票后续追问可沿用最近一次未过期横截面；数据已跨 session、
   候选池或 regime 已变时必须刷新。
2. **证据面盘点**：至少检查当前可用的 price、flow、derivatives、event、positioning、portfolio
   exposure 面；读取现有 manifest / ledger / 当前状态，明确已用、缺失、PIT 边界、settled count
   和尚未 join 的面。没有机器目录时做一行临时盘点，不得为盘点本身 reserve ID。
   盘点必须包含读取 `data/research_digest/latest_digest.md`（外部研究消费摘要，合同见
   `docs/research_digest_pipeline.md`）：对其中每条 fresh 条目给出挑中 / 放弃与一句理由，
   append 到 `data/research_digest/ledger.jsonl`（不占实验 ID）；挑中条目进入候选假设时在
   票据 `research_refs` 字段引用 entry_id，实验关闭时把结果状态（rejected/accepted/parked）
   回填到 ledger。摘要来源不给任何 novelty / recipe-lane / reopen / saturation 豁免。
3. **机制优先的跨面合成**：生成 `1-3` 个候选假设，至少一个连接此前孤立但经济机制可解释的面；
   然后只选一个进入验证。全排列 join、多个阈值机械拼接、事后挑 winner 不算新机制。
4. **先写反证**：每个 lead 同时写 baseline、treatment、预期 horizon、主要 replacement-value
   对照和会推翻它的结果；禁止只写支持理由。
5. **PIT 使用等级与证据成熟度分离**：授权且有历史决策时间戳、严格按 `known_at <= decision_time`
   回放、明确 `known_future_leakage=false`，但尚未证明 as-known vintage 的数据记为 `research_pit`；
   它可进入候选生成、outcome-blind D0-D3、哈希绑定 promotion 和 `private_replay_scout`，正向结果仍只是
   lead，机器上限为 `observed_only`。`snapshot_only -> lead`、`PIT_forward_unsettled -> observer`、
   `settled_forward_sufficient -> observed_only attribution` 仍描述证据成熟度；只有
   `canonical_pit` 可 accepted/default-off paper/live。已知未来修订、幸存者偏差、当前映射倒灌或
   未来复权进入决策输入时必须标 `not_pit` 并拒绝，不得降级成 research scout。完整口径见
   `docs/research_pit_policy.md`。
6. **信号与执行分离**：正股/底层 alpha 不得自动映射成杠杆 ETF、期权或加仓建议；instrument
   mapping、复利损耗、重叠暴露和 notional cap 属于独立 risk/capital-allocation 假设。

synthesis pass 至少留下以下结构化字段，供下一位代理继续而不是重新猜测：

```yaml
baseline_universe: []
opportunity_cost_winner: null
evidence_surfaces_used: []
evidence_surfaces_missing: []
hypothesis_candidates: []
selected_hypothesis: null
economic_mechanism: null
falsifier: null
pit_tier: not_pit|research_pit|canonical_pit
evidence_grade: lead|observer|observed_only|gate_candidate
result_ceiling: invalid|observed_only|canonical_gate_ladder
next_machine_action: null
```

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
- `scripts/build_reopen_readiness.py`：从 canonical ledgers 生成 `data/reopen_readiness.json`（各 parked 面 reopen 计数、门槛出处、停滞标记）；做 reopen 核对先跑它再手工补 manual 车道，不要从 ticket/memory 里重新推导阈值；**reopen 探针以拒绝收尾并声明新 reopen 计数时，必须在同一票据里同步更新本 builder 的对应阈值并重跑**——否则 surface 会按旧阈值显示陈旧 ready，诱导下一 session 立即重烧 ID（案例：2026-07-22 exp-001 拒绝 exit-lifecycle 重开并声明 212/30/21，builder 仍留 101/8/20 旧阈值且已满足）。同步义务也覆盖**新 park 的车道**：lead 转 forward observer / 车道以定量 `reopen_condition` park 时，必须同票把该车道注册进 builder 清单——否则 readiness surface 对它不可见，下一 session 只能从票据记忆重推阈值（案例：2026-08-02/03 dividend-restart 车道声明 ≥30 settled 门槛，builder 车道清单至 08-03 仍无此面）。**注册 ≠ 挂一个计数**：park 合同含多重 bar（数量、日期广度、集中度、身份/去重口径）时，builder 必须绑定**完整冻结合同**并按 canonical 去重身份计数，只登记 headline 行数会制造反向假 ready（案例：2026-08-04 exp-001 修复前 prediction-market 车道原始 settled 行 196 早超 60 条数量 bar，但绑定完整 60/10/3/15%/50%/20/10 合同后揭示 decision-date 广度仅 1/10、单 query 集中度 94.9%>50% 仍不达标——只报行数的 surface 会诱导过早 reopen 探针）。**同步顺序：先 close、后重定基线**——当票据经由 promotion 门的
  `quantitative_reopen_proofs` 绑定 readiness 文件（byte-exact sha256）时，close 时会按**当前文件字节**复验证明；
  close 前先改 builder 阈值会令 close 以 `preflight_recomputation_mismatch` 失败，只能字节级重建冻结态（Windows
  下 builder 写 CRLF，sha 只认 CRLF 变体）再 close、再重放新阈值（案例：2026-08-07 exp-001）。正确次序：close
  完成后在同一票据/commit 内重定基线并重跑 builder。**manual 车道会静默腐烂**：`manual_check_required` 车道
  的计数不随 ledger 增长，一旦底层 ledger 已具备机器计数所需字段，应尽快改为机器计数（案例：2026-08-07
  news-propagation 车道 manual 计数陈旧 17 天，实际行数已 2.2 倍越过 reopen bar 而 surface 仍显示 56/200）；
- `quant/experiment_history.py`：研究历史去重、trial accounting、校准与冻结证据；只做审计/反重复，不生成或排序下一策略。
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
6. 与用户当前关注标的相比，同一时点股票池里是否存在更好的风险收益候选？若只测试单票，最近一次横截面比较为什么仍有效？
7. 本假设连接了哪些此前孤立的数据面，经济机制是什么？哪些面缺失或未达到 PIT / settled readiness，是否因此只能保留为 lead / observer？

若无法回答第 2-7 点，禁止开始策略逻辑改动。

`single_causal_variable` / `changed_variable` 是历史字段名，真实含义是**单一可归因决策假设**，不是只能改一个参数或一个文件。一个 accepted alpha 实验可以包含评估同一假设所需的共享 helper、historical replay、daily default-off snapshot、report/ledger wiring、parity 测试、execution envelope 和 artifact/log 更新。

---

## 5. Gate 与保留规则

任何影响买入、卖出、过滤、排序、仓位、风险预算、LLM 决策边界或回测口径的改动，都必须通过 Gate 1-4。具体命令、窗口和指标只看 `docs/backtesting.md`。

- Gate 1：读取或创建同一标准协议下的基线。
- Gate 2：列出依赖字段并验证运行时真实存在；最低检查 `entry_date` 和 `target_price`——这两个是信号合同的哨兵字段：`target_price` 在信号生成时按入场价 + 3.5×ATR 自动计算并驱动 backtester 出场，`entry_date` 是 backtester `Position` 的必需字段（实盘持仓的 entry 信息已由 moomoo 提供，但回测路径仍依赖它）。任一缺失说明信号生成或字段管道已断，不是"可选字段没填"。
- Gate 3：检查 `signals_generated` / `signals_survived` / `survival_rate`；若 survival rate < 5%，禁止继续加过滤器。
- Gate 4：同一协议重跑 before/after；默认按 `expected_value_score`、PnL、drawdown、trade count、survival、窗口稳定性和 concentration 判断。

**触达密度 preflight（⚠️ 文字规则）**：entry-admission gate、downweight overlay、单票或窄种群类假设，
跑 Gate 4 前必须先做**不读 outcome** 的触达计数核对：信号与 baseline 已执行 entry（或声明的目标
种群）的交集，每个标准窗口 ≥5 次触达；不足时正确动作是一行核对计数收尾（记 lead / 一行记录），
不烧完整实验 ID——触达不足的 Gate 4 无论方向都无判力。**源级行数密度 ≠ 触达密度**：issuer-week /
事件行数充足，不代表信号会与可执行 entry 相交（案例：2026-07-20 exp-005 Senate LDA 通过全部源
合同 / PIT / 行数密度 preflight，但与已执行 entry 触达仅 0/0/4，全套 Gate 跑完才发现无统计意义；
同 family 前例：CISA KEV 与核心成交 0 交集、filer-status 全 universe 0 transitions、MSFT 单票
pullback 16 年 0 fire-rate）。

**源授权 preflight（⚠️ 文字规则）**：为新外部数据源 reserve ID 前，必须先核对该源的使用条款是否
授权投资研究 / 策略开发用途，以及是否存在可用的历史决策时间戳。条款禁止、决策时钟未知或已知未来
泄漏时，正确动作是 reserve 前一行记录收尾，不占 ID（案例：2026-07-21 exp-003 S&P Composite 1500
成分调整——官网条款明确不授权用于开发投资策略，harness 已建完才自拒；ToS 禁止不是 Gate 结论，
是 reserve 前就能查到的事实）。若时间戳可审计且无已知泄漏，只是 immutable/as-published vintage
尚未证明，则登记为 `research_pit`，允许 research-only replay；不得因缺 canonical vintage 在读价格前
直接扔掉。canonical 缺口必须写入 `research_pit_basis` 和后续升级条件。

保留规则：

- 强保留：主目标明显提升，风险和样本约束没有不可接受恶化。
- 可保留：主目标小幅提升或近似持平，同时降低复杂度、风险、生产不一致或归因缺陷。
- 条件保留：明确修复测量偏差、数据缺口或生产执行问题，并标记为 `measurement_repair`。
- 默认拒绝：主目标下降、风险恶化、只赢单一窗口、多数窗口退化、复杂度上升但证据不足，或无法归因到单一假设。

**棘轮警告**：Gate 4 是冠军挑战赛，每次接受都抬高下次门槛，系统会渐近收敛到
0-accept——这与市场是否还有残余 edge 无关。仅因 `*_not_beaten` 比较器或单窗口
噪声被拒、聚合非负的信号，"打不过冠军"不等于"组合无价值"；此类信号的组合级
评估口径见 `docs/portfolio_covariance_lane.md`（勿在单实验里自创组合验收标准）。

**反向棘轮警告**：measurement repair 导致 Gate-1 锚点**下调**（案例：2026-07-15 现金
账本重基线，aggregate EV 12.27→6.21）不重置 frozen families——历史被拒假设不因
门槛降低自动获得重试资格，"现在能打过更弱的冠军"不是 §2.4 证据轴。仅当某假设当初
的 park / 拒绝原因**正是本次修复的测量缺陷**（修复票 follow-up 里点名）时，才显式
重开对应 lane，且重跑双边都必须落在新锚点上；其余近邻重试照常需要新证据轴。

`state_surface_sleeve` 同类阈值、profile、notional scalar 或 capital allocation 调参必须满足 `docs/backtesting.md` 标准多窗口 aggregate EV 提升 > 10%，除非是明确的 measurement repair。

若未通过 Gate 4，必须回滚策略改动并记录失败实验。`pytest` 通过不能替代 Gate 4。

---

## 6. 生产一致性与真钱边界

生产 / 回测一致性以 `docs/production_backtest_parity.md` 为准。任何可执行买卖、过滤、排序、仓位、风险预算或 LLM 硬决策必须在共享 policy/helper 中实现，不能只存在于 backtester 或 runner。

Default-off paper alpha：

- 高潜力方向默认 shared-paper-first。
- 只有 `canonical_pit` 可保留为 accepted shared default-off helper；`research_pit` 即使历史回放为正，也只能 `observed_only`。
- 保持 `trade_enabled=False` 且不改变 live/default orders、ranking、sizing、exits 时，canonical 候选可以在同一实验内保留为 accepted shared default-off helper。
- positive private replay 只是 lead，必须说明为什么没有 shared-paper-first，以及需要哪个 shared helper / daily parity 工作。

真钱可执行性不是事后补丁。任何声称可能进入 live 的 alpha，必须记录 live-realistic execution envelope：notional / capital cap、流动性和滑点、组合挤出、最大持仓和行业/主题暴露、kill switch、订单语义、失败处理，以及这些约束是否进入 after-measurement。未评估真钱包络的结果只能算 accepted default-off，不算 live-ready。

实盘对账是常驻测量合同，不是一次性实验：`data/live_pilot/live_drift/` 每日对账
moomoo 实盘持仓与回测模型期望（fill drift / trajectory drift，口径与警戒线见
`docs/live_drift_reconciliation.md`）。core bucket 触发警戒线时按 measurement_repair
插队。回测 parity 只证明"回放一致"，本合同回答"实盘是否复现模型"——两者缺一不可。

**Forward 面产出健康（⚠️ 文字规则）**：forward / observer 面的价值只来自日历时间 × 每日
产出行，且 PIT 合同禁止回填 forward vintage——静默饥饿的每一天都不可恢复，是本仓库最贵
的故障类别（日历行数正是 reopen 计数的瓶颈资源）。已五次同型踩坑，分布在五个不同
observer：prediction-market observer `status=ok` 却 15 天 0 行（2026-07-18 修复）；
OnclickMedia 单次快照被上游 5xx 打掉 3 个整交易日才被发现（exp-20260724-002）；flow-put
稳定化 observer 因 run.py 内 quality gate 在 sleeve 之后才刷新，自接线起结构性 0 信号
（exp-20260725-004）；USAspending 本地首见 observer 在未配置快照路径时静默饥饿、
`status=ok` 照常持久化（exp-20260727-003："必需输入缺席"也必须 fail-closed，不能落入
"无输入=无事发生"的默认分支）；Drugs@FDA observer 反复消费冻结的 2026-07-10 ZIP，同时
**重写 `snapshot_retrieved_at`** 且 `status=ok`（exp-20260728-001）。第五例给出锐化口径：
健康检查必须绑定**输入内容身份**（快照 manifest hash / 上游 vintage 日期），"取回时间戳在
更新"不证明"输入在更新"——时间戳是本进程写的，冻结输入照样刷新它。第六例是该锐化口径
实现后的**反向失效**（exp-20260803-001）：内容身份若直接哈希**原始响应字节**，易失性传输
元数据（per-request `request_id` 等）会让冻结的决策面每次都"看起来在变"，unchanged 计数
永远归零、陈旧检测反向失灵——因此内容身份必须哈希 **canonical 决策安全投影**（真正决定
输出的行多重集），原始取回 provenance 另存以保审计；新鲜度推进按**已完成市场 session**
计数且锚点单调持久化（进程时钟回退后不得重计已观测 session）。因此：
新 observer 上线（仍在 §2.4 首建 ≤2 ID 预算内）必须同时声明预期产出节奏（如"每交易日
≥1 行"）并把零产出 / 陈旧检测接进日更摘要或 coverage manifest，陈旧检测须以输入内容身份
为锚，`status=ok` 不得只反映"进程没崩"或"时间戳在走"；接线后第一个产出日必须人工核对
非零产出与消费顺序（生产者先于消费者跑）。已有面连续多日 0 新行而状态正常时，按真正
故障恢复处理（占 measurement_repair ID、不计入饱和阈值），并优先于其他 measurement 工作
插队。五例逐个自然损坏、逐个烧 ID 的发现方式本身低效：剩余尚未按本条改造的存量 observer
应打包成**单个批量 measurement repair**，一次审计所有面的 fail-closed 新鲜度与内容身份
绑定，不再等各自出事。

**输入侧 canonical 数据路径合同（⚠️ 文字规则）**：任何生产 / 结算 / 回测消费端读取价格或
行情输入，必须走同一 canonical 数据层（data_layer 规范化 + 冷仓+热 overlay 合并读），禁止
组件自行二次请求 vendor 或直接读单一底层存储——绕过层的读数在"数据存在但不完整/陈旧"时
静默给出错误答案，而所有状态检查照常通过。已两例同型（触发本条入档）：production regime
模块绕过 data_layer 规范化自发第二次 Yahoo 请求，Volume-only 残行存活、NaN 比较双腿皆假，
误判 BEAR 并锁账户（exp-20260726-001）；期权 forward 结算默认 reader 只读冷仓（止于
2026-06-15）而非 canonical 冷+热 overlay（达 2026-07-24），50/241 行误标
`signal_date_missing_in_ohlcv`（exp-20260727-001）。新建消费端时"读哪个存储"必须显式指向
共享 canonical reader；review 中发现自建 fetch / 直读单仓即按本条打回。修复此类故障占
measurement_repair ID、不计入饱和阈值。

**修复 / 守卫上线边界 smoke check（⚠️ 文字规则）**：接受一个 measurement repair 或治理
guard 时，只验证"当次运行的即时路径"不够——关闭前必须至少推演或测试合同的自然边界：
**下一周期运行、跨 UTC 日界、非目标车道、进程崩溃/重启窗口、空输入、持久化状态/receipt
过期（长挂起后时间推移使先前落盘状态失效）**。已两例同型（触发
本条入档，均为"当日接受、次日返修"）：claim-receipt guard 的 rollout predicate 只用时钟
判断，上线即自锁全部非 alpha 票据（exp-20260729-007 → 次日 exp-20260729-009 返修）；
USAspending async-resume 合同按 caller run_date 过滤 continuation，跨 UTC 日界即忽略仍
有效的 job、可重复 POST 并丢失不可回填的 forward 日历快照（exp-20260729-008 →
exp-20260730-001 返修）。返修本身占 measurement_repair ID、不计入饱和阈值；但同一合同
连续返修 ≥2 次说明验收模板缺边界用例，应先补模板再继续。USAspending async 合同已触及
该阈值（第 2 次返修 exp-20260801-002：过期 pending receipt 使产线 stale 收尾——"过期"
边界即上表新增项；该票据的验收规则已枚举 5 类边界，可作为此合同的模板基线）：该合同
后续任何修复必须先核对验收模板覆盖全部上述边界，缺边界用例的修复票直接打回。
**claim-receipt closeout 合同亦已触及该阈值**（第 2 次返修 exp-20260814-002：从未成功
claim 的票据被 closeout guard 死锁——claim 在 receipt 构建中途失败（如 receipt CAS 单文件
尺寸上限）后既不能 claim 也不能 close，只能新增 never-claimed abandonment 记账路径解锁；
第 1 次返修即上文 exp-20260729-009 rollout 自锁）：该合同后续任何修复必须先补验收模板，
至少枚举 **never-claimed / claim 中途失败 / receipt 尺寸上限 / rollout 时间窗 / claimed_at
部分持久化后 receipt 才失败**（最后一类是 exp-20260814-002 reopen_condition 点名的未覆盖
形状）五类边界，缺边界用例的修复票直接打回。

**时钟锚定合同（⚠️ 文字规则）**：forward 生产者 / 结算端 / **对账与监控端**的"哪一天"判断
（请求的报价日期、continuation 连续性、日历行归属、fill 与决策的 session 归属）必须锚定
**数据日历**——canonical OHLCV 的最近完成 session、job 自己冻结的 run_date、broker 提供的
成交 session 证据——禁止用进程壁钟日期充当数据日期或交易 session。壁钟与数据日历在
午夜后 / 跨 UTC 日界 / 节假日 / ETH 盘前盘后必然错位，而 forward vintage 不可回填，错位的
每一天都是永久损失（监控端错位则产生持续假警报，掩盖真实 drift）。已三例同型（第三例触发
本条扩档至对账/监控端）：USAspending async-resume 按 caller run_date 过滤
continuation，跨 UTC 日界丢弃仍有效 job（exp-20260729-008 → exp-20260730-001 返修）；
OnclickMedia 日更按运行日历日期请求报价，午夜后运行即请求"未来"session、丢掉刚完成的
forward 快照（exp-20260731-001）；live-drift 对账把壁钟 `asof_date` 当交易 session、并用静态
ticker 标签充当执行 lineage，将盘前 ETH 成交与次开盘 fill 模型对比，产生常绿 +2.352% 假警报
（exp-20260802-002：session 归属须绑定 broker 成交 session 证据 + 在先可执行政策决策，日期
计数须按**已完成市场 session** 而非日历日）。新建 / review 生产者与对账消费端时，凡出现
`date.today()` / `now().date()` 直接进入请求参数、行归属或 session 归属逻辑即按本条打回；
修复占 measurement_repair ID、不计入饱和阈值。

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
**守卫盲窗（✅ 部分机器化）**：in-flight 拦截只能看到**已落盘**的票据；首次 reserve 尚未
持久化时立刻重试，守卫必然放行（案例：2026-07-23 exp-003/exp-005 各自复制了几分钟前的
exp-002/exp-004——守卫上线九天后单日再漏 2 张，全部是"首个输出只见 novelty 警告即重试"）。
自 2026-07-24（exp-20260724-001）起 reserve 意向锁已上线：`experiment.py new` 按提案
payload 的 canonical hash 写 `experiments/reservation_intents/` 锁文件，**完全相同**提案的
并发/重试调用返回首个 open 票据 ID 而非新开 ID。但锁只对逐字节同 payload 生效——重试时
哪怕改一个词（措辞微调、补参数）就绕开锁、退回到落盘延迟盲窗。因此重试纪律不变：任何
reserve 输出不完整/疑似超时，必须先等待并 `list_experiments` 确认，**禁止改写后盲重试**。
重复票据必须以 `duplicate_reservation_accounting` 关闭还有第二个原因：该标签是 frozen-family
builder 排除非实质 trial 的机器依据——曾有重复票据被计入同族 trial 分母并以其 TODO 元数据
顶掉真实 reopen 合同（案例：2026-07-23 exp-005 污染 exp-004 的 20-settlement 合同，
exp-20260723-006 修复）；用错关闭理由会重新引入该污染。**"及时关闭但标签错误"同样违规**
（第 2 例：2026-08-05 exp-001/002/003 同一 agent 2 分钟内对同一 facade 假设三连 reserve——
每次措辞微调即绕过意向锁——重复的 001/003 虽在分钟级被关闭，却用了 `observed_only` 而非
`duplicate_reservation_accounting`；observed_only 是实质 trial 状态，会计入所在 fingerprint
种群的 streak / 饱和计数）。tooling backlog：close 应拒收与 open 同
`single_causal_variable` 票据的非 duplicate 关闭。

关闭实验时必须留下：

- experiment ID；
- 假设推断和固定 policy bundle；
- 相关历史实验；
- before/after/delta 或 observed-only artifact；
- production impact；
- decision、拒绝原因或接受依据；
- post-run reflection、禁止近邻重试、下一步新证据——reflection 字段留 `TODO` 占位**不算
  完成关闭**（close 工具会静默填 TODO，已 4 例 accepted 票据带 TODO 关闭，最近
  exp-20260730-001；发现即回填；让 close 机器拒收 TODO 仍是 top tooling backlog）；
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

## Imported Claude Cowork project instructions
