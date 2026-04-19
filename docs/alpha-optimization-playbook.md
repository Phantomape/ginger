# Alpha Optimization Playbook

本文件的角色不是重复 `AGENTS.md` 的流程约束，而是把当前系统最值得优先
检验的 alpha 假设整理成一个可执行的研究清单。

使用方式：

- `AGENTS.md` 负责门控、优先级、实验纪律、失败记录
- 本文件负责回答一个更直接的问题：
  **下一轮最值得测试的赚钱假设是什么？**

若本文件与 `AGENTS.md` 冲突，以 `AGENTS.md` 为准。

## 1. 当前判断

当前系统最大的风险，不是“没有足够多规则”，而是：

- 迭代容易滑向 `bug fix / parity fix / logging fix`
- 每轮都很合理，但不一定在持续寻找新 alpha
- 系统更擅长证明自己没错，而不是更快找到赚钱增量

因此，从现在开始，alpha 研究默认遵循两个原则：

1. 默认优先寻找 alpha，而不是修基础设施
2. 只有当基础设施问题会显著扭曲 alpha 结论时，才允许它插队

## 2. 为什么个人量化系统仍然可能有 alpha

一个个人量化系统不太可能在以下地方稳定获得优势：

- 超高频
- 纯速度套利
- 与大型机构争抢同类拥挤因子执行优势

但它仍然可能在以下 5 类地方获得真实优势：

### 2.1 事件解释速度优势

个人系统覆盖标的不多、约束少、流程短，可以更快把新闻、财报、指引、
分析师变动、监管事件、产品发布等“离散事件”转成结构化判断。

这类 alpha 成立的依据是：

- 市场对复杂信息的消化并非总是瞬时完成
- 中小规模资金不需要像机构那样考虑大容量和复杂审批
- LLM 很适合做事件分类、语义强弱、风险解释

这也是当前仓库引入新闻层与 LLM 层的根本理由。

### 2.2 中短线趋势 / 突破延续

价格突破、量价确认、均线结构改善后，资金行为常具有路径依赖。
对于个人系统来说，这类 alpha 的关键不是“先别人 10 毫秒买到”，
而是更稳定地识别：

- 哪些突破更真
- 哪些突破背后有催化
- 哪些突破值得给更多风险预算

这类 alpha 成立的依据是：

- 趋势与动量是最稳定、最可复现的市场异象之一
- 个体系统可以用更少标的、更少层级、更快执行抓住这类机会

当前仓库的 `trend_long` 与 `breakout_long` 就属于这一类。

### 2.3 组合排序与资本分配优势

很多个人系统的问题不在“找不到信号”，而在“不会把钱压到最值钱的信号上”。

这类 alpha 成立的依据是：

- 组合收益通常高度依赖少数高质量交易
- 风险预算分配错误，会让好信号和坏信号得到相近待遇
- 个体系统更容易做主观-量化混合排序，不受机构流程拖慢

因此，对个人系统来说，`ranking` 和 `capital_allocation`
经常比“继续新增 entry 规则”更有价值。

### 2.4 Exit 质量优势

很多中短线系统的 alpha 不是毁在 entry，而是毁在 exit：

- 止盈太早
- trailing 太紧
- 大趋势没拿住
- 弱市里又退出太慢

这类 alpha 成立的依据是：

- exit 对收益分布的影响通常大于 entry 的微调
- 个人系统更容易做 regime-aware 的持仓管理
- 这类优化不一定增加太多系统复杂度

### 2.5 低覆盖度、非标准化信息的结构化利用

机构往往更看重可规模化、可容量化、可制度化复制的 alpha。
个人系统反而可以从一些“不够漂亮、但足够赚钱”的地方获得优势，例如：

- 特定行业新闻强弱
- earnings 质量分级
- 特定事件后的 3-15 日延续
- 多信号冲突时的语义排序

这类 alpha 的依据不是“学术上最纯”，而是：
**它能否在你的仓库里被验证、被回放、被稳定赚钱。**

## 3. 当前仓库已经具备哪些 alpha 探索基础

当前仓库并不是从零开始，它已经具备以下 alpha 研究骨架：

- 趋势 / 突破信号引擎
- 风险引擎与头寸 sizing
- 回测器与策略归因
- `expected_value_score`
- LLM replay / news replay / attribution 桶
- earnings snapshot replay 基础设施
- 风险分布指标：
  - `worst_trade_pct`
  - `max_consecutive_losses`
  - `tail_loss_share`

这意味着当前系统最值得探索的不是“凭空发明 20 个新策略”，而是：

1. 从现有 alpha 源里减少泄漏
2. 从现有候选里做更强排序
3. 让 LLM 在适合的边界上创造增益
4. 让资本分配向高期望值机会倾斜

## 3.1 证据分级与参考文献

为了避免把“文献支持”和“仓库内推测”混为一谈，本文统一采用以下证据分级：

- `Tier 1: literature-backed`
  外部文献支持较强、长期被重复研究的 alpha 大类。
- `Tier 2: literature-inspired but implementation-dependent`
  有研究启发与初步证据，但是否在当前仓库有效，强依赖具体实现。
- `Tier 3: repo-specific hypothesis`
  主要根据当前仓库结构、回测输出、组合约束、数据条件提出的内部假设，
  必须通过本仓库自己的实验来验证。

### Tier 1 外部支持较强的方向

#### 趋势 / 动量 / 突破延续

**适用到当前仓库的方向**

- `trend_long`
- `breakout_long`

**为什么算 Tier 1**

- 趋势 / 动量是最有文献基础的市场异象之一
- 对个人系统来说，关键不是和机构拼毫秒，而是更稳定地筛选高质量趋势

**参考文献 / 引用**

- Jegadeesh, Titman, *Profitability of Momentum Strategies: An Evaluation of Alternative Explanations*:
  https://www.nber.org/papers/w7159
- Moskowitz, Ooi, Pedersen, *Time Series Momentum*:
  https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum
- Hong, Lim, Stein, *Bad News Travels Slowly: Size, Analyst Coverage, and the Profitability of Momentum Strategies*:
  https://www.nber.org/papers/w6553

#### 财报后漂移 / 事件后延续

**适用到当前仓库的方向**

- `earnings_event_long`
- earnings 质量分级
- 事件后 3-15 日延续

**为什么算 Tier 1**

- 财报后漂移（PEAD）是最经典、最稳健的异象之一
- 但“PEAD 作为大类成立”不等于“当前仓库里的 C 策略已经成立”

**参考文献 / 引用**

- Bernard, Thomas (1989), *Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?*:
  https://econpapers.repec.org/RePEc:bla:joares:v:27:y:1989:i::p:1-36
- Cambridge JFQA 页面，对 PEAD 的后续研究与定位：
  https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/earnings-autocorrelation-and-the-postearningsannouncement-drift-experimental-evidence/61CD6A2065A4686418A3C47DEF3AC24B

### Tier 2 有研究启发、但实现依赖很强的方向

#### LLM / 新闻文本信号

**适用到当前仓库的方向**

- LLM 事件解释
- 新闻强度分级
- LLM ranking 优于简单 veto

**为什么算 Tier 2**

- 已有研究显示 LLM 可以从金融新闻中提取与收益有关的信息
- 但证据仍新，且对 prompt、结构化输出、样本选择、回放覆盖率非常敏感

**参考文献 / 引用**

- Tan, Wu, Zhang (2024), *Can LLM Parse and Predict Financial News?*:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4712248
- Chiu, Hung (2024), *Can FinGPT, ChatGPT, and Other Large Language Models Forecast Financial Markets and Macroeconomic Indicators?*:
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4946802

**对当前仓库的正确理解**

- 外部研究支持“文本里可能有 alpha”
- 但不支持你直接下结论“当前仓库的 LLM 已经稳定创造 alpha”
- 这类方向必须结合 replay / attribution / 覆盖率来验证

#### 低覆盖度、慢扩散、非标准化信息

**适用到当前仓库的方向**

- 低覆盖事件
- 复杂新闻解释
- 行业 / 主题语义排序

**为什么算 Tier 2**

- 文献支持“信息扩散慢”能形成延迟定价机会
- 但如何映射到你当前仓库，依赖具体 universe、新闻层、LLM 层设计

**参考文献 / 引用**

- Hong, Lim, Stein:
  https://www.nber.org/papers/w6553

### Tier 3 当前仓库特有、必须自证的方向

以下方向不应说成“学界已经证明”，而应明确说成：
**根据当前仓库结构与回测结果提出的高价值实验假设。**

#### Exit alpha 泄漏

**对应假设**

- `A1`
- `A6`

**为什么是 Tier 3**

- 没有哪篇外部论文能直接证明“你这个仓库当前的主要问题一定在 exit”
- 但从系统工程与当前仓库结构看，它是高可验证、高杠杆方向

**当前仓库内依据**

- 已有成熟 entry 骨架
- 已有风险分布指标
- 已能做多窗口比较

#### 跨策略资本分配 / 槽位竞争

**对应假设**

- `A3`
- `A7`

**为什么是 Tier 3**

- 这是组合层与资金配置层问题，不是单一异象论文的问题表述
- 是否成立，高度依赖当前仓库的多策略并发和头寸限制结构

**当前仓库内依据**

- 多策略并发
- 槽位约束
- 机会成本已在当前实验中出现

#### LLM 从 veto 升级为 ranking

**对应假设**

- `A4`
- `A8`

**为什么是 Tier 2 + Tier 3**

- Tier 2：文本信号与 LLM 有外部研究支持
- Tier 3：在当前仓库里，“ranking 是否优于 veto”仍然是系统设计假设，
  不是文献直接替你证明的结论

## 3.2 当前 Alpha 假设的证据映射

| 假设 | 证据级别 | 主要根据 | 备注 |
|------|----------|----------|------|
| `A1` Exit alpha 泄漏 | Tier 3 | 当前仓库结构 + 交易系统实践 | 必须靠本仓库实验自证 |
| `A2` earnings_event_long 数据质量修复后重评 | Tier 1 + Tier 3 | PEAD 文献 + 当前仓库数据盲区 | 大类成立，不代表当前实现已成立 |
| `A3` 跨策略资本分配 | Tier 3 | 当前仓库多策略竞争与槽位约束 | 组合机会成本问题 |
| `A4` LLM ranking 优于 veto | Tier 2 + Tier 3 | LLM 文本研究 + 当前仓库设计推论 | 需要 replay / attribution |
| `A5` ranking 强于继续加规则 | Tier 3 | 当前仓库候选选择问题 | 更偏系统优化假设 |
| `A6` regime-aware exit | Tier 3 | 当前仓库 regime 框架 + 收益分布直觉 | 必须防过拟合 |
| `A7` capital efficiency 优于更多信号 | Tier 3 | sizing / heat / allocation 逻辑 | 更偏资金系统假设 |
| `A8` 新闻强度分级优于 simple veto | Tier 2 + Tier 3 | 文本研究 + news replay 现状 | 当前 simple veto 证据偏弱 |

## 4. Alpha 假设优先级

以下假设按“赚钱期望 / 可验证性 / 当前阻塞程度”综合排序。

### A1. Exit alpha 泄漏可能大于 Entry alpha 泄漏

**假设**

当前系统的主要问题不是进场信号不够好，而是退出过早、止盈过紧、或统一
exit 规则切碎了大赢家，压低了 `expected_value_score`。

**为什么优先**

- 高影响
- 高可验证
- 不依赖先补齐 LLM 覆盖率
- 通常比新增策略更不容易过拟合

**根据**

- 中短线趋势系统里，exit 对收益分布的影响往往大于 entry 微调
- 当前仓库已有成熟 entry 骨架（trend / breakout / earnings），更可能先从
  “减少 alpha 泄漏”中获益
- 风险分布指标已在代码里，适合检验 exit 优化是否只是表面提 Sharpe

**优先检查**

- 固定 target 是否过早
- trailing stop 是否过紧
- 大赢家是否被过早切碎
- 不同 regime 下是否应该使用不同 exit

**验证方式**

- 固定 entry 不变，只动一个 exit 因子
- 至少比较 3 个非重叠窗口
- 重点看：
  - `expected_value_score`
  - `worst_trade_pct`
  - `max_consecutive_losses`
  - `tail_loss_share`
  - `profit_factor`

### A2. earnings_event_long 当前差，不一定是策略差，可能是数据差

**假设**

`earnings_event_long` 当前 33% 胜率，不一定证明策略无效，而可能是由于缺少
`eps_estimate / surprise_history / daily snapshot`，导致低质量 earnings 信号
没有被正确过滤。

**为什么优先**

- 它现在正在真实拖累组合 EV
- 它还在挤占 A/B 的仓位槽位
- 这是直接影响赚钱的组合级问题

**根据**

- 当前回测已显示 C 策略对组合 EV 有实质拖累
- 仓库中已存在 earnings snapshot 回放逻辑，说明这不是空想方向，
  而是一个明确的数据盲区修复后可验证的假设
- earnings 类 alpha 本身常依赖“事件质量分级”，而不是简单二元进场

**当前阻塞**

- 需要持续积累 `earnings_snapshot_YYYYMMDD.json`
- 需要让历史回放能更完整重建 C 策略输入质量

**验证方式**

- 先积累更多 earnings snapshot
- 比较：
  - C 策略有快照 vs 无快照 的信号质量
  - C 策略对 A/B 槽位挤占的变化
  - C 单独 EV 与组合 EV 的变化

### A3. 问题可能不在单策略，而在跨策略资本分配

**假设**

当前组合级 alpha 泄漏，不一定来自单个策略本身，而来自低质量机会占用了
高质量机会的风险预算与仓位槽位。

**为什么优先**

- 更接近真实资金系统问题
- 不依赖新增更多 entry 模式
- 能直接提升组合层赚钱期望

**根据**

- 当前仓库已经存在多策略并发与头寸上限，说明“谁先占槽位”会直接影响收益
- 实盘里常见“差交易不一定亏最多，但会挤掉更好的交易”
- 对个人系统来说，组合排序往往比继续加规则更具 EV 杠杆

**优先检查**

- A/B/C 是否应有不同优先级
- 是否应该跨策略统一排序，而不是谁先触发谁上
- 是否应按历史 EV / 当前 TQS / 事件质量分配槽位

**验证方式**

- 固定信号生成逻辑，只改变候选信号排序或槽位分配
- 记录：
  - 被替换掉的交易类型
  - 被优先分配风险预算的交易类型
  - 组合 EV 是否提升

### A4. LLM 的最佳角色可能是排序器，而不只是 veto 器

**假设**

LLM 最大的 alpha 贡献，不一定来自“否决坏交易”，而更可能来自：
对已通过量化门槛的候选信号做结构化排序，帮助系统把风险预算押给更值钱的
少数机会。

**为什么重要**

- 符合 LLM 擅长的语义比较任务
- 不要求 LLM 接管硬风控
- 与当前“量化规则 + LLM 判断”的联合系统定位一致

**根据**

- 简单 veto 往往只能减少错误，未必最大化收益
- 排序任务比“直接下交易指令”更稳定、更可审计
- 当前仓库已有 LLM attribution / replay 骨架，未来适合扩展到 ranking attribution

**当前阻塞**

- `llm_prompt_resp_YYYYMMDD.json` 覆盖率仍低
- LLM replay 与归因样本尚不足以支持强结论

**优先方向**

- 先让 LLM 输出结构化排序字段，而非最终交易指令
- 先比较“LLM 高分放行” vs “普通候选”的后续表现

### A5. 当前系统可能缺的不是更多信号，而是更强 ranking

**假设**

trend / breakout 的问题不一定在信号触发条件，而在于同一天多个候选之间的
排序标准不够强，导致系统没有稳定选中最值钱的那个。

**为什么优先**

- 常比“继续加过滤器”更稳
- 不容易把 survival rate 打崩
- 更符合组合优化，而不是规则堆叠

**根据**

- 当前代码已存在 `trade_quality_score`、多策略归因、资金分配入口
- 这说明系统已经进入“信号不算少，但选择可能不够强”的阶段
- 排序增强通常比阈值微调更抗过拟合

**优先检查**

- `trade_quality_score` 是否足够区分高低质量候选
- 是否需要加入事件强度、行业顺风、市场状态权重
- 同日候选按哪些字段排序最能提升 EV

### A6. Exit 应该 regime-aware，而不是一套规则打天下

**假设**

不同市场状态下，最佳退出方式不同。当前统一 exit 规则可能在 BULL 中切碎
趋势，在 BEAR / NEUTRAL 中又持有过久。

**为什么优先**

- 与系统的中短线趋势 / 突破本质一致
- 可以做成单因果实验
- 直接作用于赚钱期望，而非表面胜率

**根据**

- 同样的持仓行为在不同 regime 下收益分布往往不同
- 当前仓库已有 regime 识别和相应逻辑入口，具备实验条件
- 这是个人系统很适合做的“轻结构、强影响”优化

**优先方向**

- BULL 中放宽 trailing，保留趋势
- NEUTRAL / BEAR 中更快兑现利润
- event-driven 持仓使用不同 exit 框架

### A7. 资本效率可能比信号数量更重要

**假设**

当前系统的主要上升空间，可能来自 position sizing / capital allocation，
而不是生成更多候选信号。

**为什么优先**

- 若现有信号已不差，改资金分配常比加信号更赚钱
- 更符合“让风险预算流向最值钱机会”的系统目标

**根据**

- 对个人资金规模来说，容量不是首要约束，资本效率才是
- 当前仓库已具备 sizing、portfolio heat、trade quality 等基础结构
- 说明系统已经有条件做“相同信号，不同下注方式”的实验

**优先检查**

- 高质量信号是否应分配更高风险预算
- 是否应引入 `alpha_per_heat` 一类指标
- 是否应对高质量策略提高槽位优先级

### A8. 新闻层的 alpha 可能在事件强度分级，而非简单负面 veto

**假设**

新闻层真正的价值，不一定在负面 veto 本身，而在于识别事件强度，帮助系统
区分“只是有新闻”和“真正值得重新定价”的新闻。

**为什么重要**

- 这比简单关键词 veto 更符合 LLM 能力边界
- 更可能成为排序增益，而不是硬过滤增益

**根据**

- 当前 news replay 证据显示简单负面 veto 影响有限
- 这反而说明“是否有坏新闻”可能不是关键，关键在“事件有多强、多新、多出乎预期”
- 这是个人系统结合 LLM 最自然的方向之一

**当前阻塞**

- news replay 覆盖率仍低
- 当前证据显示简单 negative veto 的回测影响接近零

## 5. 还可以探索但优先级次于当前主线的 alpha

以下方向不是不能做，而是默认优先级低于 A1-A8：

### B1. 事件后漂移 alpha

例如：

- 财报后 3-10 日延续
- 分析师上调 / 下调后延续
- 指引上修 / 下修后的二次定价

**根据**

- 市场对复杂事件的反应常不是一次完成
- 个体系统适合做中低频事件追踪，不需要 HFT 速度

### B2. 行业 / 主题相对强弱 alpha

例如：

- 同样的 breakout，在顺风行业和逆风行业中表现不同
- 行业龙头与二线跟涨股的延续质量不同

**根据**

- 趋势交易的成功率常依赖行业背景
- 当前仓库已有 `sector` 字段基础，可逐步增强

### B3. 多时间尺度一致性 alpha

例如：

- 日线 breakout 叠加周线结构改善
- 日线动量与中期趋势方向一致时质量更高

**根据**

- 多尺度一致性常提升趋势信号质量
- 但要注意复杂度与过拟合风险

### B4. 灾难规避 alpha

这不是为了“看起来保守”，而是为了避免少数大亏损吞掉大量 alpha。

例如：

- 财报前后特殊风险窗口
- 灾难性新闻 veto
- 高波动、低流动性、异常跳空环境规避

**根据**

- 对个人账户，尾部损失的伤害通常比机构更大
- 当前仓库已有灾难 veto 与风险指标框架，适合做“少量高价值”的防守增强

## 6. 当前最值得优先做的前 3 项

如果现在只能优先做 3 个方向，默认顺序是：

1. `A1`：Exit alpha 泄漏
2. `A2`：earnings_event_long 的数据质量修复后重评
3. `A3`：跨策略资本分配 / 槽位竞争优化

如果现在只能立刻开做 1 个，我默认建议：

**先测 `A1`：当前最大 alpha 泄漏在 exit，而不是 entry。**

原因：

- 可验证性最高
- 不依赖先补齐 LLM 覆盖率
- 不一定增加系统复杂度
- 最有机会带来稳定的 EV 提升

## 7. 每轮必须写的 Alpha 卡片

每一轮正式开始前，至少写出一张卡片：

```text
alpha_hypothesis:
  本轮最值得测试的赚钱假设是什么？

alpha_type:
  entry / exit / ranking / capital_allocation / event_quality

why_now:
  为什么它是当前最值得测的？

blocker:
  若暂时不能做，具体被什么阻断？

expected_upside:
  它最可能提升什么？EV / Sharpe / drawdown / capital efficiency / attribution

validation_plan:
  用什么窗口、什么对照、什么主指标来验证？
```

## 8. 明确禁止的假 alpha 研究

以下方向默认不应被包装成“在找 alpha”：

- 只因为 1-3 笔亏损交易难看，就新增规则
- 没有 sweep / 对照就改阈值
- 把“补日志”说成“提升策略”
- 把“删弱 LLM”误当成“优化系统”
- 只优化单一表面指标，却不看 `expected_value_score`
- 明明是在修基础设施，却不说明它释放了哪个 alpha 实验

## 9. 与 AGENTS 的关系

本文件回答的是：

- 个人量化系统可以在哪些地方寻找 alpha？
- 为什么这些 alpha 对当前仓库是合理的？
- 现在最值得优先测哪些方向？

`AGENTS.md` 回答的是：

- 在测这些假设时，什么能做，什么不能做？
- 何时必须先修测量？
- 失败实验如何记录？

因此，未来如果新增 alpha 方向，优先更新本文件；
如果新增纪律、门控、日志规范、收敛标准，优先更新 `AGENTS.md`。
