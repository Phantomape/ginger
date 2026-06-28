"""File-based mailbox so same-machine agents can talk by listening to files.

Protocol, conventions, and the deadlock-free turn recipe are documented in
``docs/agent_mailbox.md`` -- read that to participate. This module is both a
library (import the functions) and a CLI.

Design (matches the repo's ticket-reservation idioms):
- A *channel* is a directory ``data/agent_mailbox/<channel>/``.
- Each message is one atomic file ``<seq>-<sender>.json`` created with
  ``O_EXCL``: the file's existence IS the turn, so concurrent senders never
  clobber each other and the sequence is globally ordered per channel.
- ``recv`` blocks by polling for the next message whose sequence is past this
  agent's per-agent cursor (``.cursor-<me>``) and whose sender is not itself,
  then advances the cursor. Listening lives here; agents never call ``sleep``.

The mailbox lives under ``data/agent_mailbox/`` which is gitignored: it is
local same-machine coordination, deliberately NOT tracked (tracking an
append-only chat is exactly what caused the experiment_log.jsonl merge
conflicts this repo retired).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAILBOX_ROOT = REPO_ROOT / "data" / "agent_mailbox"
POLL_SECONDS = 1.0
DEFAULT_TIMEOUT = 100  # < the Bash tool's 120s default; retry recv on timeout
_MAX_SEQ_ATTEMPTS = 10000


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _channel_dir(channel: str, root=MAILBOX_ROOT) -> Path:
    return Path(root) / channel


def _message_files(cdir: Path):
    if not cdir.is_dir():
        return []
    return sorted(p for p in cdir.glob("*.json") if not p.name.startswith("."))


def _seq_of(path: Path) -> int:
    return int(path.name.split("-", 1)[0])


def send_message(channel: str, sender: str, text: str, *, root=MAILBOX_ROOT) -> int:
    """Append a message to a channel. Returns its allocated sequence number.

    Sequence allocation is lock-free: scan the max existing seq, try to O_EXCL
    create seq+1, and on collision (a concurrent sender won the race) recompute
    and retry -- the same pattern as ticket id reservation.
    """
    cdir = _channel_dir(channel, root)
    cdir.mkdir(parents=True, exist_ok=True)
    for _ in range(_MAX_SEQ_ATTEMPTS):
        files = _message_files(cdir)
        nxt = (_seq_of(files[-1]) + 1) if files else 1
        path = cdir / f"{nxt:04d}-{sender}.json"
        payload = json.dumps(
            {"channel": channel, "seq": nxt, "from": sender,
             "text": text, "ts": _now_iso()},
            ensure_ascii=False,
        )
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        return nxt
    raise RuntimeError(f"could not allocate a message sequence in {cdir}")


def _cursor_path(cdir: Path, me: str) -> Path:
    return cdir / f".cursor-{me}"


def _read_cursor(cdir: Path, me: str) -> int:
    p = _cursor_path(cdir, me)
    if p.exists():
        try:
            return int(p.read_text().strip() or 0)
        except ValueError:
            return 0
    return 0


def _write_cursor(cdir: Path, me: str, seq: int) -> None:
    _cursor_path(cdir, me).write_text(str(seq))


def recv_message(channel: str, me: str, *, peer: str | None = None,
                 timeout=DEFAULT_TIMEOUT, root=MAILBOX_ROOT, poll=POLL_SECONDS):
    """Block until the next unread message for ``me`` arrives; return it (dict)
    or ``None`` on timeout.

    "Next unread" = lowest sequence past this agent's cursor that was NOT sent
    by ``me`` (and, if ``peer`` is given, was sent by ``peer``). The cursor is
    advanced to the returned message, so plain alternating send/recv just works
    without tracking sequence numbers by hand. Own messages passed over while
    waiting are skipped permanently.
    """
    cdir = _channel_dir(channel, root)
    cdir.mkdir(parents=True, exist_ok=True)
    cursor = _read_cursor(cdir, me)
    deadline = time.time() + timeout
    while True:
        for path in _message_files(cdir):
            seq = _seq_of(path)
            if seq <= cursor:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue  # mid-write or unreadable; try again next poll
            sender = data.get("from")
            if sender == me:
                cursor = seq
                _write_cursor(cdir, me, seq)
                continue
            if peer is not None and sender != peer:
                continue
            _write_cursor(cdir, me, seq)
            return data
        if time.time() >= deadline:
            return None
        time.sleep(poll)


def read_transcript(channel: str, *, root=MAILBOX_ROOT):
    """Return all messages in a channel, ordered by sequence."""
    cdir = _channel_dir(channel, root)
    out = []
    for path in _message_files(cdir):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def list_channels(*, root=MAILBOX_ROOT):
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def _cmd_send(a):
    seq = send_message(a.channel, a.me, a.text, root=a.root)
    print(f"[sent channel={a.channel} seq={seq} from={a.me}]")


def _cmd_recv(a):
    msg = recv_message(a.channel, a.me, peer=a.peer, timeout=a.timeout,
                       root=a.root)
    if msg is None:
        print(f"[TIMEOUT channel={a.channel} me={a.me}; re-run this recv]",
              file=sys.stderr)
        raise SystemExit(2)
    print(f"[from={msg['from']} seq={msg['seq']}]", file=sys.stderr)
    print(msg["text"])


def _cmd_transcript(a):
    for m in read_transcript(a.channel, root=a.root):
        print(f"{m['from']} (seq {m['seq']}): {m['text']}")


def _cmd_list(a):
    for name in list_channels(root=a.root):
        print(name)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mailbox-root", dest="root", default=MAILBOX_ROOT,
                    type=Path, help="Override the mailbox root (for tests).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("send", help="Append a message to a channel.")
    s.add_argument("--channel", required=True)
    s.add_argument("--me", required=True, help="Your agent name.")
    s.add_argument("--text", required=True)
    s.set_defaults(func=_cmd_send)

    r = sub.add_parser("recv", help="Block for the next message addressed to you.")
    r.add_argument("--channel", required=True)
    r.add_argument("--me", required=True, help="Your agent name.")
    r.add_argument("--peer", default=None,
                   help="Only accept messages from this sender.")
    r.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    r.set_defaults(func=_cmd_recv)

    t = sub.add_parser("transcript", help="Print a channel in order.")
    t.add_argument("--channel", required=True)
    t.set_defaults(func=_cmd_transcript)

    ls = sub.add_parser("list", help="List channels.")
    ls.set_defaults(func=_cmd_list)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
