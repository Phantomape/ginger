# 全历史实验记录方向裁决 — 2026-07-03（claude × codex mailbox 辩论）

> 产生方式：`agent_mailbox.py dispatch` 第三次实战，频道
> `alpha-direction-debate-20260703`，按 `docs/agent_mailbox.md` Debate v2
> 执行：codex 先做**独立**原始数据读数（禁止读 docs 结论文件），claude
> 独立聚合后交叉挑战，第三轮 claude 做 verifier 抽查后锁定。codex 在
> round-2 交付后耗尽回合退出，最终裁决由 verifier 通过后锁定。分析脚本
> 与完整读数在本地 `data/agent_mailbox/alpha-direction-debate-20260703/
> attachments/`（不入库）。本文件是唯一 durable 记录。

## 一、Verified facts（双方独立复算一致，承重项经 verifier 抽查）

1. **崩塌精确定位**：最后一个 accepted alpha 是 2026-06-21
   （exp-20260621-007，allocator scalar 系）。每 accepted 消耗实验数：
   4 月 ~5，5 月 ~7，6 月 17，W25=29，W26 起无穷（W26 102 张 / 0 accept，
   W27 前 4 天 46 张 / 0）。双方从原始 tickets 独立算出同一序列。
2. **最后一批真新 accepted 的共性**（exp-20260609-027 / 20260610-008 /
   20260611-007 / 20260616-015 / 20260620-009）：全是
   production-visible 固定候选池 + shared helper + daily default-off，
   改的是**行来源/gate shape**，不是阈值响应曲线。
3. **forward 证据供给极小**：全体系 55 个 closed forward 仓位（6 月全月
   仅 ~30 个，≈2 笔/日）。一周冻结窗实验消耗（~100 ID）按原始计数
   相当于 ~3 个月的 forward 行供给。
4. **forward 管道堵在准入**（本裁决最锋利的事实）：37 个 sleeve 中
   16 个上线以来 0 次开火。回放隐含开火数 vs 实际（codex 复算，claude
   抽查验证）：`sec_financial_report` 预期 11.3 / 实际 0（82 天）；
   `sec_ftd_finra` 预期 8.3 / 实际 0（26 天）——**verifier 已核**：
   exp-20260604-026 artifact 回放 39/40/42=121 笔属实，26 天快照全 0
   候选属实，且数据面新鲜（FINRA/FTD 档案都是 fresh），绑定守卫是
   `not_20d_breakout`（54 票中 49/天被它拒）→ 是准入守卫问题不是数据
   故障。top-10 零开火 sleeve 合计回放隐含 ~46 次准入，实际 0。
5. **饱和源计数**（frozen_families.jsonl）：companyfacts_ratio 112 族
   / 120 试 / 0 accept；sec_text_event 54/54/0；form4 35 族 60 试 0；
   13F 22 族 24 试 0。06-20 以来 observed-only/forward/readiness 类
   77 张 ID，0 accepted。
6. **IBKR 借券文件**（codex 在线核实）：官方 SLB 页面 2026 年在线，
   事实端点 `ftp://shortstock:@ftp3.interactivebrokers.com/usa.txt`
   （用户 shortstock 空密码），字段
   `SYM|CUR|NAME|CON|ISIN|REBATERATE|FEERATE|AVAILABLE`；**无免费
   历史档案**（Portfolio123 讨论确认 FTP 无历史；iborrowdesk 非 PIT
   非全量）→ 只能 forward-only。本机 curl 到 21 端口超时，需解决
   网络通路。

## 二、Unverified assumptions（不驱动不可逆动作）

- 零开火中 OHLCV-relation 簇（rolling_corr / industry_stable /
  narrow_range，预期各 4-5 次）可能含部分 regime 成分，未逐一定位
  绑定守卫；autopsy 实验的任务就是给每个 sleeve 打
  data/join/universe/guard/parity 标签。
- "准入修复能把 2 笔/日 → 6 笔/日"是杠杆估算，非承诺。
- exp-20260704-* 票据为并发 agent 按本地时区提前占用的 ID（存在性
  已验，无害）。

## 三、Decision（收敛排序，含 owner 标记）

1. **［下一个实验槽位］准入尸检 measurement repair（一次性、跨
   sleeve）**：对零开火 accepted sleeve 构建每日 admission autopsy——
   对比回放隐含候选生成与生产快照守卫，输出每 sleeve 阻塞标签
   （data missing / date join / universe mismatch / regime guard /
   capacity guard / parity bug）。首批范围：`sec_financial_report`、
   `sec_ftd_finra`、OHLCV-relation 簇。这是当前**单动作杠杆最高**项：
   每提高一倍 forward 供给，所有 parked 面的 reopen 日历同倍缩短。
   无需 owner 决策。注意：autopsy 产出"守卫为何绑定"的诊断，**不许
   顺手放松守卫**——放松属于阈值 retune，须走独立 Gate 1-4。
2. **［需 owner 拍板］冻结负产出节奏**：饱和源冻结窗扫描与同人群
   forward reslice 已是净负产出（W26-W27 148 张 / 0）；建议硬预算
   （如 ≤10 张/周例外仅限新源/新 gate shape/行数实质推进）。改变
   agent 行为规则，需 owner 在 AGENTS.md 落条款。
3. **［需 owner 批准网络/数据］IBKR 借券 forward 采集器**：keystone
   缺失源（PIT borrow 经济学）的免费 on-ramp，字段齐全但 forward-only
   且本机 FTP 21 端口不通，需 owner 解决网络通路后按观察者合同接入
   （首建 ≤2 ID 预算，遵守 §2 观察者例行物化治程）。
4. **［机械执行］修复后按预登记阈值毕业/杀掉 default-off sleeve**：
   closed 行实质推进后按 cash/SPY/QQQ 替换价值 + kill-switch 证据
   决定，不做冻结窗重切。

## 与既有决议的关系

- 本裁决把 `docs/alpha_next_direction_20260703.md` 里的
  OTC_W_SMBL / CISA KEV 顺位**下移一位**：准入尸检先行——它们的
  forward 行同样要经过这条被堵的管道。
- §2 各饱和治程条款不变；本文第 2 条是对其的全局节奏补充建议。
