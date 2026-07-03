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

- **P1 — DoD 合同授予冲击（candidate_pool_full_stack）**：war.gov RSS
  pubDate PIT，发行人匹配 PLTR/RTX/GE/GEV/CAT/DE/MSFT/AMZN/GOOG，
  materiality = 合同额/市值 或相对自身 trailing 授予基线的 z-score，
  次开盘进 10 日收盘出。真正新数据源，novelty 干净；与 space_catalyst
  协同。这是下一个全栈实验的第一候选。
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
- 另一条独立于本扫描的已登记轴：FINRA 非 ATS 批发商内部化周度面
  `OTC_W_SMBL`（exp-20260703-016 reflection 预登记，基础设施全复用）。

## 止损条件

- P1：若 RSS 文章体的发行人解析在三窗口内映射不到 ≥20 笔可结算目标交易，
  停在 observed-only，不做阈值挖矿；不得用 USAspending 回填绕过 PIT。
- P2：若被延迟的入场在回放中本来就不存在或不亏损，记 rejected 不重调
  N 日窗口；KEV 只有 4 个可映射发行人，禁止为凑样本扩展到弱映射产品线。
