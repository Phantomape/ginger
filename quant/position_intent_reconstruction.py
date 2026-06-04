"""Reconstruct intended entry shares from saved production archives.

This is an audit tool, not a trading rule.  It looks for evidence that can
explain the original entry size of current non-legacy positions, so the
operator can decide whether to populate original_shares/intended_shares in
open_positions.json.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from data_paths import daily_artifact_glob
from open_position_schema import account_positions
from position_intent import INTENDED_SHARE_FIELDS, resolve_intended_shares


DATE_RE = re.compile(r"(20\d{6})")
ADVICE_KINDS = ("llm_prompt_resp", "investment_advice")


def _safe_load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _date_from_path(path: Path) -> str | None:
    match = DATE_RE.search(path.name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _days_between(left: str | None, right: str | None) -> int | None:
    left_date = _parse_date(left)
    right_date = _parse_date(right)
    if not left_date or not right_date:
        return None
    return (left_date - right_date).days


def _as_positive_int(value: Any) -> int | None:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _unwrap_advice(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        return None
    parsed = payload.get("advice_parsed", payload)
    return parsed if isinstance(parsed, dict) else None


def _ticker(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.upper().strip()
    return normalized or None


def _current_nonlegacy_positions(open_positions: dict | None) -> list[dict]:
    rows = []
    for pos in account_positions(open_positions, positive_only=True):
        ticker = _ticker(pos.get("ticker"))
        if not ticker:
            continue
        try:
            shares = float(pos.get("shares") or 0)
        except (TypeError, ValueError):
            shares = 0.0
        opened_by = str(pos.get("opened_by_strategy") or "").lower().strip()
        if opened_by == "legacy":
            continue
        row = dict(pos)
        row["ticker"] = ticker
        row["_section"] = row.get("position_group")
        row["_current_shares"] = shares
        rows.append(row)
    return rows


def _evidence(
    *,
    ticker: str,
    evidence_type: str,
    source_file: Path,
    source_date: str | None,
    shares: int | None = None,
    original_shares: int | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "evidence_type": evidence_type,
        "source_file": str(source_file).replace("\\", "/"),
        "source_date": source_date,
        "shares": shares,
        "original_shares": original_shares,
        "details": details or {},
    }


def _collect_advice_evidence(data_dir: Path, target_tickers: set[str]) -> tuple[dict, dict]:
    evidence_by_ticker: dict[str, list[dict]] = defaultdict(list)
    actions_by_ticker: dict[str, list[dict]] = defaultdict(list)

    for kind in ADVICE_KINDS:
        for path in daily_artifact_glob(kind, data_dir):
            source_date = _date_from_path(path)
            parsed = _unwrap_advice(_safe_load_json(path))
            if not parsed:
                continue

            new_trade = parsed.get("new_trade")
            if isinstance(new_trade, dict):
                ticker = _ticker(new_trade.get("ticker"))
                if ticker in target_tickers:
                    evidence_by_ticker[ticker].append(
                        _evidence(
                            ticker=ticker,
                            evidence_type="advice_new_trade",
                            source_file=path,
                            source_date=source_date,
                            shares=_as_positive_int(new_trade.get("shares_to_buy")),
                            details={
                                "entry_price": new_trade.get("entry_price"),
                                "stop_price": new_trade.get("stop_price"),
                                "target_price": new_trade.get("target_price"),
                                "strategy": new_trade.get("strategy")
                                    or new_trade.get("signal_source"),
                            },
                        )
                    )

            for addon in parsed.get("add_on_trades", []) or []:
                if not isinstance(addon, dict):
                    continue
                ticker = _ticker(addon.get("ticker"))
                if ticker in target_tickers:
                    evidence_by_ticker[ticker].append(
                        _evidence(
                            ticker=ticker,
                            evidence_type="advice_add_on",
                            source_file=path,
                            source_date=source_date,
                            shares=_as_positive_int(addon.get("shares_to_buy")),
                            original_shares=_as_positive_int(addon.get("original_shares")),
                            details={
                                "decision_mode": addon.get("decision_mode"),
                                "reason": addon.get("reason"),
                            },
                        )
                    )

            for action in parsed.get("position_actions", []) or []:
                if not isinstance(action, dict):
                    continue
                ticker = _ticker(action.get("ticker"))
                if ticker in target_tickers:
                    actions_by_ticker[ticker].append({
                        "source_file": str(path).replace("\\", "/"),
                        "source_date": source_date,
                        "action": str(action.get("action") or "").upper(),
                        "shares_to_sell": action.get("shares_to_sell"),
                        "exit_rule_triggered": action.get("exit_rule_triggered"),
                        "decision_mode": action.get("decision_mode"),
                    })

    return dict(evidence_by_ticker), dict(actions_by_ticker)


def _collect_quant_signal_evidence(data_dir: Path, target_tickers: set[str]) -> dict:
    evidence_by_ticker: dict[str, list[dict]] = defaultdict(list)
    for path in daily_artifact_glob("quant_signals", data_dir):
        source_date = _date_from_path(path)
        payload = _safe_load_json(path)
        if not isinstance(payload, dict):
            continue

        for signal in payload.get("signals", []) or []:
            if not isinstance(signal, dict):
                continue
            ticker = _ticker(signal.get("ticker"))
            if ticker not in target_tickers:
                continue
            sizing = signal.get("sizing") or {}
            evidence_by_ticker[ticker].append(
                _evidence(
                    ticker=ticker,
                    evidence_type="quant_signal_candidate",
                    source_file=path,
                    source_date=source_date,
                    shares=_as_positive_int(
                        sizing.get("shares_to_buy") or signal.get("shares_to_buy")
                    ),
                    details={
                        "strategy": signal.get("strategy"),
                        "entry_price": signal.get("entry_price"),
                        "stop_price": signal.get("stop_price"),
                        "target_price": signal.get("target_price"),
                    },
                )
            )

        for section in ("addon_actions", "addon_audit"):
            for addon in payload.get(section, []) or []:
                if not isinstance(addon, dict):
                    continue
                ticker = _ticker(addon.get("ticker"))
                if ticker not in target_tickers:
                    continue
                evidence_by_ticker[ticker].append(
                    _evidence(
                        ticker=ticker,
                        evidence_type=f"quant_{section}",
                        source_file=path,
                        source_date=source_date,
                        shares=_as_positive_int(addon.get("shares_to_buy")),
                        original_shares=_as_positive_int(addon.get("original_shares")),
                        details={
                            "status": addon.get("status"),
                            "reason": addon.get("reason"),
                            "current_shares": addon.get("current_shares"),
                            "days_since_entry": addon.get("days_since_entry"),
                            "checkpoint_days": addon.get("checkpoint_days"),
                        },
                    )
                )

    return dict(evidence_by_ticker)


def _collect_manual_trades(path: Path, target_tickers: set[str]) -> dict:
    trades_by_ticker: dict[str, list[dict]] = defaultdict(list)
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            trade = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(trade, dict):
            continue
        ticker = _ticker(trade.get("ticker"))
        if ticker in target_tickers:
            trades_by_ticker[ticker].append(trade)
    return dict(trades_by_ticker)


def _score_evidence(evidence: dict, entry_date: str | None) -> tuple[int, str, int | None]:
    evidence_type = evidence.get("evidence_type")
    source_date = evidence.get("source_date")
    days_from_entry = _days_between(source_date, entry_date)

    if evidence_type in {"quant_addon_actions", "quant_addon_audit"}:
        original = _as_positive_int(evidence.get("original_shares"))
        if original:
            days_since_entry = evidence.get("details", {}).get("days_since_entry")
            if days_since_entry in (1, 2, 3):
                return 98, "high", original
            return 90, "high", original

    if evidence_type == "advice_new_trade":
        shares = _as_positive_int(evidence.get("shares"))
        if shares:
            if days_from_entry is not None and -4 <= days_from_entry <= 1:
                return 92, "high", shares
            return 70, "medium", shares

    if evidence_type == "quant_signal_candidate":
        shares = _as_positive_int(evidence.get("shares"))
        if shares:
            if days_from_entry is not None and -4 <= days_from_entry <= 1:
                return 80, "medium", shares
            return 55, "low", shares

    return 0, "none", None


def reconstruct_entry_intents(
    open_positions: dict,
    data_dir: str | Path = "data",
    manual_trades_path: str | Path = "operator_inputs/manual_trades.jsonl",
) -> dict:
    data_path = Path(data_dir)
    positions = _current_nonlegacy_positions(open_positions)
    target_tickers = {pos["ticker"] for pos in positions}

    advice_evidence, archived_actions = _collect_advice_evidence(data_path, target_tickers)
    quant_evidence = _collect_quant_signal_evidence(data_path, target_tickers)
    manual_trades = _collect_manual_trades(Path(manual_trades_path), target_tickers)

    rows = []
    high_confidence_count = 0
    ready_for_confirmation_count = 0
    recommended_count = 0
    missing_count = 0
    needs_confirmation_count = 0

    for pos in positions:
        ticker = pos["ticker"]
        entry_date = pos.get("entry_date")
        current_shares = pos["_current_shares"]
        existing_shares, existing_source = resolve_intended_shares(pos)
        raw_evidence = []
        raw_evidence.extend(advice_evidence.get(ticker, []))
        raw_evidence.extend(quant_evidence.get(ticker, []))

        scored = []
        for item in raw_evidence:
            score, confidence, candidate = _score_evidence(item, entry_date)
            enriched = dict(item)
            enriched["score"] = score
            enriched["confidence"] = confidence
            enriched["candidate_intended_shares"] = candidate
            if candidate:
                scored.append(enriched)
        scored.sort(key=lambda e: (e["score"], e.get("source_date") or ""), reverse=True)

        unique_candidates = sorted({
            e["candidate_intended_shares"]
            for e in scored
            if e.get("candidate_intended_shares")
        })
        top = scored[0] if scored else None
        recommended_value = existing_shares or (top or {}).get("candidate_intended_shares")
        confidence = "existing_metadata" if existing_shares else ((top or {}).get("confidence") or "none")

        post_actions = []
        for action in archived_actions.get(ticker, []):
            delta_days = _days_between(action.get("source_date"), entry_date)
            if delta_days is None or delta_days >= 0:
                post_actions.append(action)
        reduce_exit_actions = [
            a for a in post_actions
            if a.get("action") in {"REDUCE", "EXIT"}
        ]
        trades_after_entry = []
        for trade in manual_trades.get(ticker, []):
            delta_days = _days_between(trade.get("trade_date"), entry_date)
            if delta_days is None or delta_days >= 0:
                trades_after_entry.append(trade)

        if top and top.get("score", 0) >= 90:
            high_confidence_count += 1

        if existing_shares:
            write_recommendation = "already_has_intended_share_metadata"
            recommended_count += 1
        elif not recommended_value:
            write_recommendation = "needs_user_confirmation_no_candidate"
            missing_count += 1
            needs_confirmation_count += 1
        elif top and top.get("score", 0) >= 90 and not reduce_exit_actions:
            write_recommendation = "candidate_ready_for_user_confirmation"
            ready_for_confirmation_count += 1
            recommended_count += 1
            needs_confirmation_count += 1
        else:
            write_recommendation = "needs_user_confirmation_conflict_or_low_confidence"
            needs_confirmation_count += 1

        rows.append({
            "ticker": ticker,
            "section": pos.get("_section"),
            "opened_by_strategy": pos.get("opened_by_strategy"),
            "entry_date": entry_date,
            "current_shares": current_shares,
            "existing_intended_shares": existing_shares,
            "existing_intended_source": existing_source,
            "recommended_intended_shares": recommended_value,
            "confidence": confidence,
            "write_recommendation": write_recommendation,
            "unique_candidate_values": unique_candidates,
            "current_vs_recommended_shortfall": (
                recommended_value - current_shares
                if recommended_value is not None and current_shares < recommended_value
                else 0
            ),
            "top_evidence": top,
            "evidence_count": len(raw_evidence),
            "post_entry_action_count": len(post_actions),
            "post_entry_reduce_exit_count": len(reduce_exit_actions),
            "post_entry_actions": post_actions,
            "manual_trades_after_entry": trades_after_entry,
        })

    return {
        "generated_at": datetime.now().isoformat(),
        "purpose": "entry_intent_reconstruction_audit",
        "policy": {
            "does_not_modify_open_positions": True,
            "does_not_create_orders": True,
            "requires_user_confirmation_before_writing_fields": True,
        },
        "summary": {
            "positions_audited": len(rows),
            "tickers": [row["ticker"] for row in rows],
            "high_confidence_candidates": high_confidence_count,
            "candidate_ready_for_user_confirmation_count": ready_for_confirmation_count,
            "recommended_or_existing_count": recommended_count,
            "missing_candidate_count": missing_count,
            "needs_user_confirmation_count": needs_confirmation_count,
        },
        "positions": rows,
    }


def render_markdown(report: dict) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Entry Intent Reconstruction Audit",
        "",
        f"Generated at: `{report.get('generated_at')}`",
        "",
        "This report is read-only. It does not modify `open_positions.json` and does not create orders.",
        "",
        "## Summary",
        "",
        f"- Positions audited: `{summary.get('positions_audited')}`",
        f"- High-confidence candidates: `{summary.get('high_confidence_candidates')}`",
        f"- Ready for user confirmation: `{summary.get('candidate_ready_for_user_confirmation_count')}`",
        f"- Missing candidates: `{summary.get('missing_candidate_count')}`",
        f"- Needs user confirmation: `{summary.get('needs_user_confirmation_count')}`",
        "",
        "## Candidate Table",
        "",
        "| Ticker | Current | Candidate | Confidence | Recommendation | Source | Notes |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for row in report.get("positions", []):
        top = row.get("top_evidence") or {}
        source = top.get("source_file") or ""
        notes = []
        shortfall = row.get("current_vs_recommended_shortfall")
        if shortfall:
            notes.append(f"shortfall {shortfall:g} shares")
        if row.get("post_entry_reduce_exit_count"):
            notes.append(f"{row['post_entry_reduce_exit_count']} reduce/exit actions after entry")
        if row.get("manual_trades_after_entry"):
            notes.append(f"{len(row['manual_trades_after_entry'])} manual trades after entry")
        if row.get("unique_candidate_values") and len(row["unique_candidate_values"]) > 1:
            notes.append(f"candidate conflict {row['unique_candidate_values']}")
        lines.append(
            "| {ticker} | {current:g} | {candidate} | {confidence} | {recommendation} | {source} | {notes} |".format(
                ticker=row.get("ticker"),
                current=row.get("current_shares") or 0,
                candidate=row.get("recommended_intended_shares") or "",
                confidence=row.get("confidence"),
                recommendation=row.get("write_recommendation"),
                source=source,
                notes="; ".join(notes),
            )
        )
    lines.extend([
        "",
        "## Next Step",
        "",
        "Populate `original_shares` only after reviewing the rows marked `candidate_ready_for_user_confirmation`.",
        "Rows without a candidate need an external broker/order note or explicit user confirmation.",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open-positions", default="operator_inputs/open_positions.json")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--manual-trades", default="operator_inputs/manual_trades.jsonl")
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    args = parser.parse_args(argv)

    open_positions = _safe_load_json(Path(args.open_positions))
    if not isinstance(open_positions, dict):
        raise SystemExit(f"Could not load open positions: {args.open_positions}")

    report = reconstruct_entry_intents(open_positions, args.data_dir, args.manual_trades)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        out = Path(args.markdown_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
