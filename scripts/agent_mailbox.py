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
import re
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


_EXP_ID_RE = re.compile(r"exp-\d{8}-\d{3}")
_PATH_RE = re.compile(
    r"(?:data|docs|experiments|quant|scripts|operator_inputs)/"
    r"[A-Za-z0-9_./\-*]+"
)


def extract_references(text: str):
    """Pull checkable references out of a message: experiment ids and repo
    paths. Returns (exp_ids, paths) as sets. Used by the dangling-ref pre-filter.
    """
    exp_ids = set(_EXP_ID_RE.findall(text or ""))
    paths = {p.rstrip(".,);:") for p in _PATH_RE.findall(text or "")}
    return exp_ids, paths


def verify_channel(channel: str, *, root=MAILBOX_ROOT, repo_root=REPO_ROOT):
    """Mechanical pre-filter: report referenced experiment ids / repo paths in a
    channel that do NOT exist on disk (dangling references).

    IMPORTANT LIMIT: this only checks *existence*. It cannot catch a reference
    that exists but is mis-attributed (e.g. citing a real exp id for a claim
    that belongs to a different experiment) -- that requires a verifier agent
    actually reading the source. See "Debate protocol v2" in
    docs/agent_mailbox.md.
    """
    repo_root = Path(repo_root)
    rows = read_transcript(channel, root=root)
    dangling = []
    checked = 0
    for m in rows:
        seq, who, text = m.get("seq"), m.get("from"), m.get("text", "")
        exp_ids, paths = extract_references(text)
        for eid in sorted(exp_ids):
            checked += 1
            if not (repo_root / "experiments" / "tickets" / f"{eid}.json").exists():
                dangling.append({"seq": seq, "from": who, "kind": "exp_id",
                                 "ref": eid})
        for p in sorted(paths):
            checked += 1
            if not (repo_root / p).exists():
                dangling.append({"seq": seq, "from": who, "kind": "path",
                                 "ref": p})
    return {"channel": channel, "checked": checked, "dangling": dangling}


def list_channels(*, root=MAILBOX_ROOT):
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# Dispatch: one-sided trigger that STARTS the peer agent (codex) and opens the
# conversation, so a mailbox exchange no longer requires both agents to already
# be alive. The dispatcher speaks first; the spawned peer listens first.
# ---------------------------------------------------------------------------

# The npm wrapper (codex.CMD) is broken on this machine (missing the win32-x64
# platform package), so discovery tests real binaries and falls back to the
# desktop app's bundled CLIs.
CODEX_CANDIDATES = [
    "codex",
    r"C:\Users\Administrator\.codex\plugins\.plugin-appserver\codex.exe",
    r"C:\Users\Administrator\.codex\.sandbox-bin\codex.exe",
]


def find_codex_exe(explicit: str | None = None) -> str | None:
    """Return the first codex binary that answers ``--version`` with rc 0."""
    import shutil
    import subprocess

    candidates = [explicit] if explicit else []
    which = shutil.which("codex")
    if which:
        candidates.append(which)
    candidates.extend(CODEX_CANDIDATES)
    seen = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            out = subprocess.run(
                [cand, "--version"], capture_output=True, text=True, timeout=60
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if out.returncode == 0:
            return cand
    return None


def _bootstrap_prompt(*, channel: str, me: str, peer: str, rounds: int,
                      python_exe: str, repo_root: Path) -> str:
    attachments = f"data/agent_mailbox/{channel}/attachments"
    mailbox = "scripts/agent_mailbox.py"
    return (
        f"You are agent \"{peer}\" in a file-mailbox conversation with agent "
        f"\"{me}\" inside the repo at {repo_root}. The protocol is documented "
        f"in docs/agent_mailbox.md. You LISTEN FIRST.\n\n"
        f"Loop (at most {rounds} of your turns):\n"
        f"1. Receive: run\n"
        f"   {python_exe} {mailbox} recv --channel {channel} --me {peer} --timeout 300\n"
        f"   Exit code 2 means timeout: just re-run the same command. The first\n"
        f"   message you receive is your task brief from {me}.\n"
        f"2. Do what the message asks. You have network access; when the task\n"
        f"   is research, verify claims online and cite concrete source URLs.\n"
        f"3. Reply: for anything longer than a few lines, write the full body\n"
        f"   to a new file under {attachments}/ (create the directory if\n"
        f"   needed) and send a SHORT pointer message instead, e.g.\n"
        f"   {python_exe} {mailbox} send --channel {channel} --me {peer} "
        f"--text \"reply in {attachments}/round1.md\"\n"
        f"   Avoid shell-quoting pitfalls: keep --text short, plain, no nested "
        f"quotes.\n"
        f"4. Then go back to step 1 and wait for {me}'s next message.\n"
        f"5. Stop when you send or receive a message containing the token DONE,"
        f" or when you have used your {rounds} turns.\n\n"
        f"Hard rules: do not modify tracked repo files; write only under "
        f"data/agent_mailbox/{channel}/; do not run git commit; do not reserve "
        f"experiment ids. Your final message must contain DONE."
    )


def dispatch_peer(channel: str, me: str, task: str, *,
                  peer: str = "codex",
                  rounds: int = 3,
                  codex_exe: str | None = None,
                  sandbox: str = "danger-full-access",
                  model: str | None = None,
                  root=MAILBOX_ROOT,
                  repo_root: Path = REPO_ROOT) -> dict:
    """Send the opener and spawn the peer agent in the background.

    Returns {seq, pid, exe, log}. The caller then simply alternates
    ``recv``/``send`` as the speaks-first side of the normal turn recipe.
    """
    import subprocess

    exe = find_codex_exe(codex_exe)
    if exe is None:
        raise RuntimeError(
            "no working codex binary found (tried PATH and known fallbacks); "
            "pass --codex-exe explicitly"
        )
    seq = send_message(channel, me, task, root=root)

    cdir = _channel_dir(channel, root)
    (cdir / "attachments").mkdir(parents=True, exist_ok=True)
    prompt = _bootstrap_prompt(
        channel=channel, me=me, peer=peer, rounds=rounds,
        python_exe="python", repo_root=repo_root,
    )
    log_path = cdir / f".{peer}-exec.log"
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115 - handed to child
    cmd = [exe, "exec", "--sandbox", sandbox]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
            | subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        )
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    (cdir / f".{peer}-exec.pid").write_text(str(proc.pid))
    return {"seq": seq, "pid": proc.pid, "exe": exe, "log": str(log_path)}


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


def _cmd_dispatch(a):
    info = dispatch_peer(
        a.channel, a.me, a.task,
        peer=a.peer, rounds=a.rounds, codex_exe=a.codex_exe,
        sandbox=a.sandbox, model=a.model, root=a.root,
    )
    print(f"[dispatched channel={a.channel} opener_seq={info['seq']} "
          f"peer={a.peer} pid={info['pid']}]")
    print(f"[exe={info['exe']}]")
    print(f"[log={info['log']}]")
    print(f"next: python scripts/agent_mailbox.py recv --channel {a.channel} "
          f"--me {a.me} --peer {a.peer}", file=sys.stderr)


def _cmd_verify(a):
    rep = verify_channel(a.channel, root=a.root)
    d = rep["dangling"]
    print(f"[verify channel={rep['channel']} checked={rep['checked']} "
          f"dangling={len(d)}]")
    for f in d:
        print(f"  DANGLING {f['kind']}: {f['ref']}  "
              f"(cited by {f['from']} seq {f['seq']})")
    print("note: existence-only pre-filter; it CANNOT catch a reference that "
          "exists but is mis-attributed -- that needs a verifier agent reading "
          "the source (see docs/agent_mailbox.md, Debate protocol v2).",
          file=sys.stderr)
    if d:
        raise SystemExit(1)


def main(argv=None):
    # Messages are UTF-8; force UTF-8 on the console streams so non-ASCII text
    # (e.g. Chinese) round-trips through recv/transcript even when the Windows
    # console code page is cp936/GBK. The stored files are always UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
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

    v = sub.add_parser("verify", help="Pre-filter: flag dangling exp-id/path "
                                      "references in a channel (existence only).")
    v.add_argument("--channel", required=True)
    v.set_defaults(func=_cmd_verify)

    d = sub.add_parser(
        "dispatch",
        help="Send the opener AND spawn the peer agent (codex exec) in the "
             "background so a conversation can start one-sided.",
    )
    d.add_argument("--channel", required=True)
    d.add_argument("--me", required=True, help="Your agent name (speaks first).")
    d.add_argument("--task", required=True, help="Opener/task brief text.")
    d.add_argument("--peer", default="codex", help="Spawned agent's name.")
    d.add_argument("--rounds", type=int, default=3,
                   help="Max peer turns before it must stop (default 3).")
    d.add_argument("--codex-exe", default=None,
                   help="Explicit codex binary; otherwise auto-discovered.")
    d.add_argument("--sandbox", default="danger-full-access",
                   choices=["read-only", "workspace-write", "danger-full-access"],
                   help="codex exec sandbox mode (network research needs "
                        "danger-full-access on this machine).")
    d.add_argument("--model", default=None, help="Optional codex model override.")
    d.set_defaults(func=_cmd_dispatch)

    a = ap.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
