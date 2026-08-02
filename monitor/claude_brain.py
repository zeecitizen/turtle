"""claude_brain.py - persistent searchable memory across all Claude sessions.

Claude Code already writes every session as a JSONL file at
  C:/Users/zeesh/.claude/projects/c--Users-zeesh-Documents-GitHub-turtle/*.jsonl

This script indexes those files into a SQLite FTS5 database so any future
Claude session can search the entire history — "every word, nothing forgotten."

USAGE:
  python claude_brain.py index               # re-index all sessions
  python claude_brain.py index --watch       # re-index every 60s (daemon)
  python claude_brain.py search "query"      # full-text search
  python claude_brain.py recent --hours 24   # recent turns
  python claude_brain.py session <session_id># dump full session
  python claude_brain.py claims              # extract all my "X is Y" claims
  python claude_brain.py session-start       # write summary for new Claude session

The DB lives at:
  C:/Users/zeesh/Documents/GitHub/turtle/monitor/.claude_brain.db
"""
import sys, json, os, time, argparse, glob, sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc

ROOT       = Path(r"C:\Users\zeesh\Documents\GitHub\turtle")
SESSIONS_DIR = Path(r"C:\Users\zeesh\.claude\projects\c--Users-zeesh-Documents-GitHub-turtle")
DB_PATH    = ROOT / "monitor" / ".claude_brain.db"


# ── Schema ──
SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    seq           INTEGER NOT NULL,        -- ordering within session
    ts_ms         INTEGER,                  -- best-effort wall time
    role          TEXT NOT NULL,            -- 'user' | 'assistant' | 'system' | 'tool_use' | 'tool_result'
    content       TEXT NOT NULL,            -- the text body (extracted from message)
    tool_name     TEXT,                     -- for tool_use/tool_result
    file_paths    TEXT,                     -- pipe-separated file paths mentioned
    UNIQUE(session_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_ts ON turns(ts_ms);
CREATE INDEX IF NOT EXISTS idx_turns_role ON turns(role);

CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5(
    content,
    role UNINDEXED,
    session_id UNINDEXED,
    seq UNINDEXED,
    ts_ms UNINDEXED,
    tool_name,
    content='turns',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS turns_ai AFTER INSERT ON turns BEGIN
  INSERT INTO turns_fts(rowid, content, role, session_id, seq, ts_ms, tool_name)
  VALUES (new.id, new.content, new.role, new.session_id, new.seq, new.ts_ms, new.tool_name);
END;
CREATE TRIGGER IF NOT EXISTS turns_ad AFTER DELETE ON turns BEGIN
  INSERT INTO turns_fts(turns_fts, rowid, content, role, session_id, seq, ts_ms, tool_name)
  VALUES('delete', old.id, old.content, old.role, old.session_id, old.seq, old.ts_ms, old.tool_name);
END;
CREATE TRIGGER IF NOT EXISTS turns_au AFTER UPDATE ON turns BEGIN
  INSERT INTO turns_fts(turns_fts, rowid, content, role, session_id, seq, ts_ms, tool_name)
  VALUES('delete', old.id, old.content, old.role, old.session_id, old.seq, old.ts_ms, old.tool_name);
  INSERT INTO turns_fts(rowid, content, role, session_id, seq, ts_ms, tool_name)
  VALUES (new.id, new.content, new.role, new.session_id, new.seq, new.ts_ms, new.tool_name);
END;

CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    indexed_at   INTEGER NOT NULL,
    last_mtime   REAL NOT NULL,
    turn_count   INTEGER NOT NULL,
    file_size    INTEGER NOT NULL
);
"""


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


# ── Content extraction from Claude Code JSONL records ──

def extract_text(content):
    """Claude Code message.content is either str OR list of {type, text|input|content...}.
    Flatten to plain text for FTS indexing. Tool I/O is verbose; keep first 4k of each."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)[:4000]
    parts = []
    for item in content:
        if not isinstance(item, dict):
            parts.append(str(item)[:1000]); continue
        t = item.get("type")
        if t == "text":
            parts.append(item.get("text", ""))
        elif t == "tool_use":
            tool = item.get("name", "?")
            inp  = item.get("input", {})
            parts.append(f"[TOOL_USE {tool}] " + json.dumps(inp, ensure_ascii=False)[:3000])
        elif t == "tool_result":
            res = item.get("content", "")
            if isinstance(res, list):
                res = " ".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in res)
            parts.append(f"[TOOL_RESULT] {str(res)[:3000]}")
        elif t == "thinking":
            parts.append(f"[THINKING] {item.get('thinking', '')[:2000]}")
        else:
            parts.append(json.dumps(item, ensure_ascii=False)[:1000])
    return "\n".join(parts)


def extract_file_paths(text):
    """Best-effort: pick out file-like tokens that contain a slash or backslash."""
    import re
    pat = re.compile(r"[A-Za-z]:\\[A-Za-z0-9_\-\\\./]+|/[A-Za-z0-9_\-/\.]+\.[a-zA-Z0-9]{1,5}|\b[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-/\.]+\.[a-zA-Z0-9]{1,5}")
    return list(dict.fromkeys(pat.findall(text)))


def tool_name_from_content(content):
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                return item.get("name")
    return None


# ── Indexing ──

def index_one_session(conn, jsonl_path):
    """Idempotent: re-indexes only if file size or mtime changed."""
    stat = jsonl_path.stat()
    session_id = jsonl_path.stem
    row = conn.execute(
        "SELECT last_mtime, file_size FROM sessions WHERE session_id = ?",
        (session_id,)).fetchone()
    if row and row[0] == stat.st_mtime and row[1] == stat.st_size:
        return 0   # already up to date

    # Re-index: clear existing then re-read
    conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
    seq = 0
    inserted = 0
    with open(jsonl_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            # Claude Code JSONL records: {type, message: {role, content}, timestamp, ...}
            msg = rec.get("message") or {}
            if not msg:
                # could be a system event, skip
                continue
            role = msg.get("role") or rec.get("type") or "?"
            content = msg.get("content", "")
            text = extract_text(content)
            if not text or not text.strip():
                continue
            # Best-effort timestamp
            ts_ms = None
            ts_str = rec.get("timestamp") or rec.get("created_at")
            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    ts_ms = int(dt.timestamp() * 1000)
                except Exception: pass
            tool_name = tool_name_from_content(content) if role == "assistant" else None
            files = "|".join(extract_file_paths(text)[:20])
            conn.execute(
                "INSERT INTO turns (session_id, seq, ts_ms, role, content, tool_name, file_paths) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, seq, ts_ms, role, text, tool_name, files))
            seq += 1
            inserted += 1

    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, indexed_at, last_mtime, turn_count, file_size) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, int(time.time()), stat.st_mtime, seq, stat.st_size))
    conn.commit()
    return inserted


def index_all(verbose=True):
    if not SESSIONS_DIR.exists():
        print(f"[brain] sessions dir not found: {SESSIONS_DIR}")
        return 0
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = db()
    total = 0
    files = sorted(SESSIONS_DIR.glob("*.jsonl"))
    for p in files:
        n = index_one_session(conn, p)
        if n > 0 and verbose:
            print(f"  + {p.name}: {n} turns")
        total += n
    if verbose:
        n_sess = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        n_turns = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        print(f"[brain] index complete: {n_sess} sessions, {n_turns} turns indexed. (+{total} new this run)")
    conn.close()
    return total


# ── Queries ──

def search(query, limit=20, role=None, since_hours=None):
    conn = db()
    where = []
    params = [query]
    if role: where.append("turns.role = ?"); params.append(role)
    if since_hours:
        cutoff_ms = int((time.time() - since_hours * 3600) * 1000)
        where.append("turns.ts_ms >= ?"); params.append(cutoff_ms)
    where_sql = (" AND " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT turns.session_id, turns.seq, turns.ts_ms, turns.role, turns.tool_name, "
        "       snippet(turns_fts, 0, '[[', ']]', '...', 30) as snip "
        "FROM turns_fts JOIN turns ON turns.id = turns_fts.rowid "
        "WHERE turns_fts MATCH ?" + where_sql +
        " ORDER BY bm25(turns_fts) LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    print(f"[brain] {len(rows)} hits for: {query}")
    for sid, seq, ts, role, tool, snip in rows:
        ts_str = ""
        if ts:
            ts_str = datetime.fromtimestamp(ts/1000, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        tool_str = f" [{tool}]" if tool else ""
        print(f"\n--- {sid[:8]}:{seq} {role}{tool_str} @ {ts_str} ---")
        print(f"  {snip}")
    conn.close()


def recent(hours=24, role=None, limit=50):
    conn = db()
    cutoff_ms = int((time.time() - hours * 3600) * 1000)
    where = ["ts_ms >= ?"]; params = [cutoff_ms]
    if role: where.append("role = ?"); params.append(role)
    sql = "SELECT session_id, seq, ts_ms, role, tool_name, substr(content, 1, 300) FROM turns " \
          f"WHERE {' AND '.join(where)} ORDER BY ts_ms DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    print(f"[brain] {len(rows)} turns in last {hours}h:")
    for sid, seq, ts, role, tool, body in rows:
        ts_str = datetime.fromtimestamp(ts/1000, tz=UTC).strftime("%Y-%m-%d %H:%M UTC") if ts else ""
        tool_str = f" [{tool}]" if tool else ""
        print(f"\n  {ts_str} {sid[:8]}:{seq} {role}{tool_str}")
        print(f"    {body.replace(chr(10), ' / ')}")
    conn.close()


def dump_session(session_id):
    conn = db()
    rows = conn.execute(
        "SELECT seq, ts_ms, role, tool_name, content FROM turns WHERE session_id LIKE ? ORDER BY seq",
        (session_id + "%",)).fetchall()
    if not rows:
        print(f"[brain] no session matching {session_id}"); return
    for seq, ts, role, tool, body in rows:
        ts_str = datetime.fromtimestamp(ts/1000, tz=UTC).strftime("%H:%M:%S") if ts else "??:??:??"
        tool_str = f" [{tool}]" if tool else ""
        print(f"\n=== {seq:04d} {ts_str} {role}{tool_str} ===")
        print(body[:5000])
    conn.close()


def session_start_brief():
    """Print a session-start brief: what was being worked on recently."""
    conn = db()
    # Recent assistant + user turns from last 6 hours
    cutoff_ms = int((time.time() - 6 * 3600) * 1000)
    rows = conn.execute(
        "SELECT ts_ms, role, tool_name, substr(content, 1, 200) FROM turns "
        "WHERE ts_ms >= ? AND role IN ('user','assistant') AND tool_name IS NULL "
        "ORDER BY ts_ms DESC LIMIT 20",
        (cutoff_ms,)).fetchall()
    print("=" * 60)
    print("CLAUDE BRAIN — last 6 hours of human/assistant turns")
    print("=" * 60)
    for ts, role, tool, body in reversed(rows):
        ts_str = datetime.fromtimestamp(ts/1000, tz=UTC).strftime("%H:%M") if ts else "??:??"
        print(f"\n[{ts_str} {role}] {body.replace(chr(10), ' ')}")
    # Wall-of-shame ref
    print("\n" + "=" * 60)
    print("(See memory.md wall of shame for the longer-term context.)")
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_index = sub.add_parser("index"); p_index.add_argument("--watch", action="store_true")
    p_search = sub.add_parser("search"); p_search.add_argument("query"); p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--role", default=None); p_search.add_argument("--since-hours", type=float, default=None)
    p_recent = sub.add_parser("recent"); p_recent.add_argument("--hours", type=float, default=24)
    p_recent.add_argument("--role", default=None); p_recent.add_argument("--limit", type=int, default=50)
    p_sess = sub.add_parser("session"); p_sess.add_argument("session_id")
    sub.add_parser("session-start")
    p_zee = sub.add_parser("zee-said", help="Search ONLY Zee's verbatim user messages")
    p_zee.add_argument("query"); p_zee.add_argument("--limit", type=int, default=30)
    p_zee.add_argument("--since-hours", type=float, default=None)
    args = ap.parse_args()
    if args.cmd == "index":
        if args.watch:
            print("[brain] watching, re-indexing every 60s...")
            while True:
                index_all()
                time.sleep(60)
        else:
            index_all()
    elif args.cmd == "search":
        search(args.query, args.limit, args.role, args.since_hours)
    elif args.cmd == "recent":
        recent(args.hours, args.role, args.limit)
    elif args.cmd == "session":
        dump_session(args.session_id)
    elif args.cmd == "session-start":
        session_start_brief()
    elif args.cmd == "zee-said":
        # Every word Zee types is gold. This recovers his verbatim user messages.
        search(args.query, args.limit, role="user", since_hours=args.since_hours)


if __name__ == "__main__":
    main()
