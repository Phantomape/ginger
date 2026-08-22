# Repository-external Append Anchor Decision Packet

> 状态：`ready_for_user_selection`。本文件冻结目标无关的安全合同；尚未选择或接入任何外部服务。

## 本轮结论

当前 segmented store 的 `HEAD.json` 有完整 self-hash，但攻击者或误操作仍可把它整体换回一份更旧、内部仍合法的
`HEAD.json`。仓库内再多一层 hash、Git commit 或本地签名文件都无法可靠证明“这是不是最新状态”。因此，任何
canonical 候选消费前，都必须把每一次成功的 `HEAD.json` 迁移追加到仓库外、不可覆盖的序列中。

机器可验的待选择合同在
`data/v2/repository_external_append_anchor_decision_packet.json`。它保持
`external_append_anchor_status=absent`、`canonical_eligibility=false` 和 `trade_enabled=false`，不会把决策包冒充部署。
该 packet 在本轮随 durable decision 固定后不可原地回填或覆盖。用户授权后必须新建 content-addressed、append-only 的
`v2_repository_external_append_anchor_selected_contract`，用 `decision_packet_contract_sha256` 引用本 packet；selected contract
自己的 `anchor_contract_sha256` 按排除自身字段的规则计算，避免自引用。它必须在 sequence-1 外部 append 前冻结，只保存授权、
target/retention/IAM、requested window 和 cutover HEAD。外部 commit/read-back 后再新建另一份不可变
`v2_repository_external_append_anchor_genesis_activation_receipt`，绑定独立 read principal、批准 target/locator、原始读回证据、
exact anchor-object hash、运行时生成的时钟与 anchor-gate 状态；两者不能混写。

## 推荐目标类别

首选是位于独立管理边界内的 managed compliance/WORM object store，前提是它同时提供锁定 retention、create-only
writer、强一致 latest/read-after-write、可证明的单调 latest 协议和独立读回 receipt；只有 WORM 而没有 ordered append
或 predecessor compare-and-append 仍不够。managed append-only ledger 也可接受，但必须机器证明
sequence/predecessor、幂等 append 和 immutable retention。自建 append log 只有在独立主机/账号、独立 owner、备份和
retention 运维都明确后才考虑。

以下都不合格：同一个 Git 仓库或普通 Git remote、同机文件或可更新数据库行、只有 versioning 而没有锁定 retention
的 bucket，以及 signing key 与 ledger writer 共存的本地签名文件。

## 固定合同

每个外部 anchor 至少绑定：environment、稳定 `store_id/ledger_stream_id`、严格递增的 `anchor_sequence`、前一 anchor
与前一 HEAD 的 SHA-256、已提交
`HEAD.json` 的 exact-byte SHA-256、`head_hash`、storage contract、checkpoint/tail、tip manifest、event/manifest count、
transition kind、idempotency key、提交时刻和 writer principal。外部 receipt 另绑定 immutable locator/version-or-offset、
service commit time、retention receipt 与 receipt hash。semantic record hash 使用现有 `quant.v2_contracts.canonical_json`
规则（sorted keys、无空格分隔、`ensure_ascii=true`、拒绝 NaN、UTF-8、无 LF）；完整 immutable object 则在含 semantic hash 的
canonical JSON 后恰好加一个 LF，再计算 exact hash。provider receipt hash 只对保存的原始响应字节计算，不做解码或规范化。
compact rotation 即使 event/manifest count 不变，也必须因 exact HEAD 改变而追加新序列。

写路径固定为：

```text
immutable local records -> atomic HEAD -> external create-only append
-> independent read-back verification -> anchor-gate-satisfied-only
```

外部 sequence 连续本身不证明 HEAD 合法延伸。append/zero-event 必须证明新 segment/tip 从前一 external anchor 精确延伸；
rotation 必须证明 compact checkpoint 的 `compacted_from_head.head_hash` 等于前一锚，且 counts/tip 不变。否则“回滚旧 HEAD
→ 从旧分支追加 → 重新锚定”仍可能绕过只看 sequence 的检查。stream 内禁止 reset；新 genesis 必须使用另一个获批的
`ledger_stream_id` 和 cutover contract。

如果本地 `HEAD.json` 已发布而外部 append 或读回失败，该 root 只能保持 research-only，并在当前 HEAD 被成功锚定或 root
被 quarantine 前阻止下一次 HEAD 迁移。丢失成功响应只能做 exact idempotent retry，不能跳 sequence。

canonical reader 必须直接查询外部 target，验证连续序列和最新 record，再把 `head_exact_sha256` 及所有复制的 HEAD
身份与本地 strict load 对齐。外部 receipt 还必须绑定获批的 anchor contract/target 以及 provider 返回的 locked retention
mode、policy version 和 `retain_until`。本地 cache、receipt 或 Git 历史不能替代外部查询。target outage、retention 到期、
序列缺口/分叉、remote one-behind/one-ahead、跨 environment/stream replay、最新身份不符或本地旧 HEAD 回滚都 fail closed。

## 权限边界

- Append principal：pre-cutover contract 冻结 non-secret IAM principal ID/reference 与 owner；只能 create/append，不能
  overwrite、delete、缩短 retention 或管理 policy。
- Read principal：冻结另一份 IAM principal ID/reference 与 owner；只能读取和发现 latest sequence，不能 append。
- Retention administrator：冻结第三份 IAM principal ID/reference 与 owner，不进入 runtime；三类 principal ID 必须互异。
- Deployment owner：负责 namespace、secret-store reference、网络出口、告警、恢复演练和变更审批。tracked packet 只允许
  保存 non-secret locator/reference，禁止 token、private key、client secret、password 或任何原始 credential bytes。

本合同抵御的是已锚定后仓库本地的有效旧 HEAD 回滚，以及 anchor 序列缺失/分叉；它不声称抵御 append principal 与
retention administrator 同时失陷，也不授予 source authorization、canonical PIT、市场覆盖、Engine-0、paper/live 或交易资格。

## 上线前验收

机器 packet 中的 A1-A14 必须全部通过，关键包括：create-only 冲突、writer 无 delete/retention 权限、强一致读回、lost-ack
幂等、旧 HEAD 回滚拦截、sequence gap/fork、target outage fail-closed、principal separation，以及 count 不变的 compact
rotation 仍追加新 anchor。还必须覆盖 rollback-then-append 分支、anchor-genesis cutover 身份以及错误 target/retention receipt。

anchor genesis 只能把获批 cutover contract 中的当前 research-only HEAD 作为 sequence 1；它与 ledger bootstrap 是两件事，
pre-cutover selected contract 必须冻结 environment、store/stream、exact HEAD 和 requested cutover window。sequence-1 必须绑定
这份 contract hash；外部 service commit 与独立 read-back 后，post-cutover activation receipt 才记录实际
`cutover_verified_at`，且不能早于二者。独立读回必须由获批 read principal 完成并与 writer 分离，冻结 exact provider response
和 anchor-object hash，不能只自报时间戳；`anchor_gate_eligibility_started_at` 不能早于 verified cutover，而
`canonical_forward_eligibility_started_at` 在另一次 canonical review 前必须仍为 `null`。它不能追溯升级任何既有来源或证据，
也不是 bounded scout 的前置条件。随后先 shadow 运行并演练
outage/rollback，再单独做 canonical eligibility review。应用回滚不得回到不理解 anchor contract 的 binary；存储恢复必须在
新 root 重建、验证并与外部 latest anchor 对齐，不能原地 rewind。

## 新 selected-target contract 需要冻结

1. 目标类别及具体 provider/product、account/tenant 和 namespace，以及 single/multi-writer topology；
2. 锁定 retention mode 与 period，以及 strong latest/read-after-write 的证据；
3. append、read、retention-admin 三个互异的 non-secret IAM principal ID/reference、各自 owner 与 secret-store reference；
4. deployment owner、威胁模型、网络出口许可、成本批准，以及明确的 implementation authorization reference/批准人/时间；
5. pre-cutover selected contract 的 environment、store/stream identity、exact HEAD 与 requested cutover window；运行时产生的
   sequence-1 service/read-back/verified 时钟另写 post-cutover activation receipt。

这些字段未在一份新 artifact 中冻结并明确授权前，不实现 connector、不创建账号/namespace、不写凭据，也不改变任何 parity、
canonical 或交易状态；禁止覆盖本 decision packet。
