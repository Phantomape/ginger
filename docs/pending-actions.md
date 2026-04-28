# Pending Actions 操作说明

## 这是什么

`pending_actions` 是执行记忆层，不是新的 alpha 规则。

它解决的问题是：某天系统已经建议 `REDUCE` / `EXIT`，但你没有实际下单，或者下单后没有更新 `data/open_positions.json`。如果第二天技术规则重新计算成 `HOLD`，旧系统会忘记昨天的减仓建议；现在系统会继续提醒，直到持仓股数真的对上。

当前例子：

- `2026-04-14`：MCD 曾被建议 `REDUCE 11`，触发规则是 `TRAILING_STOP`
- 当前 `data/open_positions.json` 仍显示 MCD `shares=22`
- 因此 `data/pending_actions.json` 里保留一条 open pending action
- 之后每日建议里，如果 MCD 被 fresh rule 写成 `HOLD`，保存层会改回 `REDUCE 11`

## 日常怎么用

照常运行每日 pipeline：

```powershell
cd D:\Github\ginger
python quant\run.py
```

如果没有 `OPENAI_API_KEY`，系统会生成：

```text
data\llm_prompt_YYYYMMDD.txt
```

把 prompt 复制给 ChatGPT / Claude，拿到 JSON 回复后导入：

```powershell
python quant\import_advice.py --date YYYY-MM-DD --input response.txt
```

导入后重点看两个文件：

```text
data\investment_advice_YYYYMMDD.json
data\pending_actions.json
```

## 系统会自动做什么

生成 prompt 时，`quant/llm_advisor.py` 会把未执行动作注入第 4 节：

```json
"pending_unexecuted_actions": [
  {
    "ticker": "MCD",
    "action": "REDUCE",
    "shares_to_sell": 11,
    "first_advice_date": "20260414",
    "exit_rule_triggered": "TRAILING_STOP"
  }
]
```

保存 advice 时，如果 LLM 输出：

```json
{
  "ticker": "MCD",
  "action": "HOLD"
}
```

但 `pending_actions.json` 里仍有未执行的 MCD REDUCE，代码会把 parsed advice 修正成：

```json
{
  "ticker": "MCD",
  "action": "REDUCE",
  "shares_to_sell": 11,
  "exit_rule_triggered": "TRAILING_STOP",
  "decision_mode": "pending_unexecuted_action",
  "reason": "Previous REDUCE from 20260414 was not reflected in open_positions; original trigger=TRAILING_STOP. Repeating until shares reconcile."
}
```

## 怎么让 pending action 关闭

执行交易后，更新 `data/open_positions.json`。

例如 MCD 当前是 22 股，如果你卖出 11 股，就把 MCD 改成：

```json
{
  "ticker": "MCD",
  "shares": 11
}
```

下一次运行或导入 advice 时，系统会发现当前股数已经小于等于 `expected_remaining_shares=11`，这条 pending action 就不会再出现在 open pending 列表里。

如果是 `EXIT`，则当该 ticker 不在 `open_positions.json`，或 `shares <= 0` 时视为完成。

## 什么时候手动编辑 pending_actions.json

只有三种情况建议手动改：

- 你明确决定不执行某条建议：把对应记录的 `status` 改成 `ignored`，并补 `close_reason`
- 你已经执行了交易，但暂时不想改 `open_positions.json`：可以临时把 `status` 改成 `executed`
- 你发现历史 advice 文件缺失，但确实有一条未执行建议：手动新增一条 open record

建议记录格式：

```json
{
  "id": "YYYYMMDD:TICKER:ACTION:RULE",
  "status": "open",
  "first_advice_date": "YYYYMMDD",
  "last_seen_date": "YYYYMMDD",
  "ticker": "MCD",
  "action": "REDUCE",
  "shares_to_sell": 11,
  "original_shares": 22.0,
  "expected_remaining_shares": 11.0,
  "exit_rule_triggered": "TRAILING_STOP",
  "original_reason": "TRAILING_STOP triggered; code advised reducing position",
  "decision_mode": "forced_rule",
  "source_file": "llm_prompt_resp_20260414.json"
}
```

## 注意事项

- 这个机制只重复已经存在的 `REDUCE` / `EXIT`，不会创造新的交易信号。
- `shares_to_sell=0` 的 REDUCE 不会进入 pending，避免 MU 这种小仓位被反复提醒。
- 如果 `open_positions.json` 没有及时更新，系统会认为建议未执行，这是刻意设计。
- 如果你主观 override 某条建议，最好显式写进 `pending_actions.json`，不要让系统靠沉默猜测。

## 验证命令

```powershell
python -m pytest quant\test_pending_actions.py -q
python -m pytest quant\test_quant.py -q -k "pending_action or prompt or no_shares or shares_to_sell or llm_advisor"
```
