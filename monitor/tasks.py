"""tasks.py - numbered task tracker for Zee's assignments.

Per Rule #10 (startup.bat) — every task Zee assigns gets a number, is tracked,
and is only closed when Zee says so.

Storage: tasks.md at project root (markdown, human-readable, append-only).
State: monitor/.tasks_state.json (next_number counter).

USAGE:
  python tasks.py open "Build mobile chat-app"
      → assigns TASK-NNN, appends to tasks.md, prints number

  python tasks.py list
      → shows all open tasks with numbers

  python tasks.py list --all
      → shows all tasks including closed

  python tasks.py close 042 "shipped + verified"
      → marks TASK-042 closed with reason

  python tasks.py note 042 "blocked because broker rejected order"
      → appends an in-progress note WITHOUT closing

  python tasks.py show 042
      → full history of TASK-042
"""
import sys, json, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc
PKT = timezone(timedelta(hours=5))  # Pakistan Standard Time, no DST

ROOT   = Path(__file__).resolve().parent.parent
TASKS  = ROOT / "tasks.md"
STATE  = ROOT / "monitor" / ".tasks_state.json"

HEADER = """# tasks.md — Zee's assigned tasks, numbered & tracked

Per Rule #10 (startup.bat). Append-only. Numbers are global across sessions.
A task is OPEN until Zee explicitly says it's complete.

| # | Status |
|---|---|
| (the rest is event log) | |

"""


def now_pkt():
    return datetime.now(tz=UTC).astimezone(PKT)


def stamp():
    return now_pkt().strftime("%Y-%m-%d %H:%M PKT")


def load_state():
    if STATE.exists():
        try: return json.loads(STATE.read_text())
        except: pass
    return {"next_number": 1}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))


def append(line):
    TASKS.parent.mkdir(parents=True, exist_ok=True)
    if not TASKS.exists():
        TASKS.write_text(HEADER, encoding="utf-8")
    with open(TASKS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_all():
    if not TASKS.exists(): return []
    return TASKS.read_text(encoding="utf-8").splitlines()


def parse_tasks():
    """Return dict {number_int: {'desc': str, 'status': 'open'|'closed', 'events': [lines]}}.

    Close events are tagged "**CLOSED TASK-NNN**" so the parser can attribute
    them to the correct task even when appended at file end (append-only)."""
    tasks = {}
    cur_block = None
    import re
    closed_re = re.compile(r"\*\*CLOSED TASK-(\d+)\*\*", re.IGNORECASE)
    reopen_re = re.compile(r"\*\*REOPEN TASK-(\d+)\*\*", re.IGNORECASE)
    legacy_close_re = re.compile(r"\*\*CLOSED\*\*", re.IGNORECASE)
    for line in read_all():
        if line.startswith("## TASK-"):
            try:
                n = int(line.split("TASK-")[1].split(" ")[0].split(":")[0])
                desc = line.split("—", 1)[1].strip() if "—" in line else ""
                tasks[n] = {"desc": desc, "status": "open", "events": [line]}
                cur_block = n
            except Exception:
                pass
        elif line.startswith("- "):
            # First: tagged-close event applies to the named task regardless of position
            m = closed_re.search(line)
            if m:
                target_n = int(m.group(1))
                if target_n in tasks:
                    tasks[target_n]["events"].append(line)
                    tasks[target_n]["status"] = "closed"
                continue
            # REOPEN tag
            mr = reopen_re.search(line)
            if mr:
                target_n = int(mr.group(1))
                if target_n in tasks:
                    tasks[target_n]["events"].append(line)
                    tasks[target_n]["status"] = "open"
                continue
            # Legacy untagged **CLOSED** → assume current block
            if legacy_close_re.search(line) and cur_block is not None:
                tasks[cur_block]["events"].append(line)
                tasks[cur_block]["status"] = "closed"
                continue
            # Normal note → current block
            if cur_block is not None:
                tasks[cur_block]["events"].append(line)
    return tasks


def cmd_open(desc):
    state = load_state()
    n = state["next_number"]
    state["next_number"] = n + 1
    save_state(state)
    line = f"\n## TASK-{n:03d}  opened {stamp()} — {desc}"
    append(line)
    print(f"Opened TASK-{n:03d}: {desc}")
    return n


def cmd_note(num, text):
    n = int(num)
    line = f"- {stamp()} — {text}"
    append(line)
    print(f"Noted on TASK-{n:03d}: {text}")


def cmd_close(num, reason):
    """Close event is tagged with the task number explicitly so the parser
    matches even when the event is appended at file end (append-only)."""
    n = int(num)
    line = f"- {stamp()} — **CLOSED TASK-{n:03d}**  ({reason})"
    append(line)
    print(f"Closed TASK-{n:03d}: {reason}")


def cmd_list(show_all=False):
    tasks = parse_tasks()
    if not tasks:
        print("(no tasks yet)"); return
    for n in sorted(tasks.keys()):
        t = tasks[n]
        if not show_all and t["status"] == "closed": continue
        flag = "[CLOSED]" if t["status"] == "closed" else "[OPEN]  "
        print(f"  {flag} TASK-{n:03d}  {t['desc']}")
    state = load_state()
    print(f"\n  next number: TASK-{state['next_number']:03d}")


def cmd_show(num):
    n = int(num)
    tasks = parse_tasks()
    if n not in tasks:
        print(f"TASK-{n:03d} not found"); return
    t = tasks[n]
    print(f"TASK-{n:03d} ({t['status']}) — {t['desc']}")
    print("Events:")
    for e in t["events"]:
        print("  " + e)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_o = sub.add_parser("open"); p_o.add_argument("desc", nargs="+")
    p_n = sub.add_parser("note"); p_n.add_argument("num"); p_n.add_argument("text", nargs="+")
    p_c = sub.add_parser("close"); p_c.add_argument("num"); p_c.add_argument("reason", nargs="*", default=[])
    p_l = sub.add_parser("list"); p_l.add_argument("--all", action="store_true")
    p_s = sub.add_parser("show"); p_s.add_argument("num")
    args = ap.parse_args()
    if args.cmd == "open":  cmd_open(" ".join(args.desc))
    elif args.cmd == "note": cmd_note(args.num, " ".join(args.text))
    elif args.cmd == "close": cmd_close(args.num, " ".join(args.reason) or "complete")
    elif args.cmd == "list": cmd_list(args.all)
    elif args.cmd == "show": cmd_show(args.num)


if __name__ == "__main__":
    main()
