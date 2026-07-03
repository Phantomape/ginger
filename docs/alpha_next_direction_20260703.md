# 下一步方向决议 — 2026-07-03（codex 联网扫描 + claude 仓库交叉验证）

> 产生方式：`scripts/agent_mailbox.py dispatch` 首次实战——claude（无网络）触发
> 并拉起 codex（有网络），双方在 mailbox 频道 `web-scan-20260703` 完成 3 轮
> 对话（提案 → 仓库史挑战 + 在线验证 → 定稿），`verify` 预过滤 0 dangling。
> 完整 transcript 与 round1/round2 附件在本地 `data/agent_mailbox/`（不入库）。
> 本文件是唯一 durable 记录。开工前仍按 `AGENTS.md` §3-§7 走。

## 已验证事实（codex 在线核实，claude 复核仓库史）

1. **DoD 每日合同公告可回放**：`defense.gov/News/Contracts` 对脚本 403，但
   `https://www.war.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945&max=1000`
   返回 500 条，最旧 2024-05-13，`pubDate` 恒定 ~21:00 UTC（工作日 5pm ET
   发布，$7.5M 以上合同）——**覆盖全部三个 canonical 窗口**，pubDate 是干净
   PIT 边界。RSS 深度无法超过 500 条（max/page 变体已试）。文章 URL 需
   article_id，不可按日期枚举，回放路径 = RSS 索引 + 文章体抓取。
   示例：2025-03-14 GE Aerospace $5B F110 FMS 合同。
   （另：USAspending API 免凭据可用，本机已验证，但 action_date 的公开
   可见时间不干净，只作 fallback + lag haircut。）
2. **CISA KEV 密度**：`known_exploited_vulnerabilities.json` 免凭据；
   dateAdded ≥ 2024-10-01 映射到 universe 的共 **112 条**：MSFT 75 /
   AAPL 18 / GOOG(含 Android) 17 / META 2，其余（AMZN NVDA PLTR NOW SNOW
   DDOG NFLX COIN HOOD）全为 0。密度过 ~25 条 bar 但高度集中。
3. **Coinbase 公共蜡烛免凭据**（10 rps/IP），交易所时间戳即 PIT；
   **Farside ETF flow 无法证明历史首发时间**（行在 T 日晚间美国时间陆续
   出现，无 row-level first_publication 字段）→ 严格回放只能用纯 BTC/ETH
   周末/隔夜变量，ETF flow 只能 forward first_seen_at。
4. 仓库史否决了 codex round1 的两条提案：PEAD（已有 accepted
   post_earnings_underpriced_drift sleeve，近邻）、Form 4 内部人集群
   （已有 accepted form4 sleeve + exp-20260609-025 线）。App Store 榜单
   （attention 近邻 + forward-only）与 H-1B 季度披露（年 4 次太慢）park。

## 决议优先级

- **P1 — DoD 合同授予冲击：已 DEMOTED → PARK（2026-07-03 第二轮
  mailbox 验证，频道 `dod-contracts-density-20260703`，未消耗实验 ID）**。
  三条实证依据（codex 在线核实）：
  (a) 39 天分层抽样显示 top-1/day 结构性 RTX 垄断（外推 RTX 82/46/131
  行 per window，PLTR/GE/GEV/GOOG 抽样为 0）——单票集中度守卫（≤50%
  positive share / HHI ≤0.35）**按构造必挂**；
  (b) 唯一可信的从业者研究（TenderAlpha/HKU 白皮书）把效应定位在
  合同额/市值 top 5% 桶（即小盘），megacap-only 先验为负；
  (c) war.gov feed 可证不完整：PLTR 2025-10-15 $442.9M 陆军订单
  （USAspending W9128Z26FA001）连 11-12 补发页都没有；且 2025-10-01..
  11-12 存在停摆空洞。50% 行是 modification/option。
  **reopen 条件**：多机构捆绑面（war.gov + army.mil/ACC + GSA OneGov
  发布 + 可选 NASA/DOE）的新密度爬取显示每窗口 ≥20 个映射事件且覆盖
  ≥4 个不同 ticker。GSA OneGov 协议线（AWS 2025-08 / Gemini 2025-08 /
  MSFT 2025-09）是其中最有趣的单线——真实市场相关、PIT 日期干净、
  非国防名字——但月频 1-3 条只够 forward observer，不够三窗口回放。
- **P2 — CISA KEV 入场风险闸（entry_filter / risk allocation）**：映射
  KEV 加入后 N 日内对 MSFT/AAPL/GOOG/META 的买入延迟/降权。可三窗口
  回放（dateAdded PIT）。诚实前提：仓库 entry-veto 基准率差 +
  capital/risk 调参需 >10% aggregate EV 提升，预期要压低。
- **P3 — 加密周末动量 context 字段（park）**：只有 COIN/HOOD(±NBIS)
  暴露，2-3 票的 top-1 池必撞单票集中度守卫（≤50% positive share /
  HHI ≤0.35），只能作为 COIN/HOOD 入场的条件 context，不占独立实验，
  等有承载面再说。
- 未进入本轮：USPTO 专利质量冲击、FDA/ClinicalTrials 目录账本
  （codex round1 备选，未二次验证，留作 P1/P2 耗尽后的下一批探针）。
- **下一个实验槽位（P1 demote 后顶上）**：FINRA 非 ATS 批发商内部化
  周度面 `OTC_W_SMBL`（exp-20260703-016 reflection 预登记的合法兄弟轴，
  基础设施全复用，零新工程；NVDA 单周批发商内部化 3.75 亿股 ≈ ATS 的
  7 倍，是零售订单流代理）。其后为 P2 CISA KEV 入场风险闸。

## 止损条件

- P1：**已按上述密度/先验/完整性证据 park**（止损条件在消耗实验 ID 之前
  就被第二轮 mailbox 验证触发——这正是该协议的目的）。重开只认多机构
  捆绑面的新密度爬取，不认同一 war.gov 面上的阈值/映射表微调。
- P2：若被延迟的入场在回放中本来就不存在或不亏损，记 rejected 不重调
  N 日窗口；KEV 只有 4 个可映射发行人，禁止为凑样本扩展到弱映射产品线。
- OTC_W_SMBL：沿用 exp-20260703-016 的冻结守卫与对照 bar，不因 ATS 版
  被拒而放松任何阈值；若同样"正但不增量"，两条 venue 分解线一起冻结。
