#!/usr/bin/env python3
"""
Intern Hawks — Daily Research Bots.

3 interns spawn each day, each with a different research angle.
They browse the internet, read articles, and extract actionable
trading intelligence for XAUUSD UHV breakout strategies.

Their findings go into a daily journal. At end of day, Claude
reads the journal and decides what to act on.

Launch: python intern_hawks.py              (run all 3 interns)
        python intern_hawks.py --intern 1   (run specific intern)
        python intern_hawks.py --eod        (end-of-day review)
"""

import json
import sys
import time
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

try:
    from ddgs import DDGS
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False

try:
    import requests as req
    FETCH_AVAILABLE = True
except ImportError:
    FETCH_AVAILABLE = False

SCRIPT_DIR = Path(__file__).parent
JOURNAL_DIR = SCRIPT_DIR / "intern_journal"
API_KEY_FILE = SCRIPT_DIR / ".claude_api_key"
THEORIES_FILE = SCRIPT_DIR / "theories.json"
PATTERNS_FILE = SCRIPT_DIR / "silver_hawk_patterns.json"
INTERN_LOG = SCRIPT_DIR / "intern_hawks.log"

JOURNAL_DIR.mkdir(exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(INTERN_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _load_api_key() -> str | None:
    try:
        if API_KEY_FILE.exists():
            return API_KEY_FILE.read_text("utf-8").strip()
    except Exception:
        pass
    return None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _journal_path(date: str = None) -> Path:
    return JOURNAL_DIR / f"{date or _today()}.json"


def _load_journal(date: str = None) -> dict:
    p = _journal_path(date)
    try:
        if p.exists():
            return json.loads(p.read_text("utf-8"))
    except Exception:
        pass
    return {"date": date or _today(), "interns": [], "eod_review": None}


def _save_journal(journal: dict):
    p = _journal_path(journal.get("date"))
    p.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")


# ── The 3 Daily Interns ──────────────────────────────────────────

INTERN_BRIEFS = [
    {
        "id": 1,
        "name": "Strategy Intern",
        "role": "XAUUSD breakout strategy researcher",
        "searches": [
            "XAUUSD ultra high volume breakout strategy {year}",
            "volume spread analysis gold trading 1 minute chart",
            "high volume candle breakout confirmation techniques forex",
            "VSA volume spike breakout continuation vs reversal",
            "gold scalping volume breakout entry timing",
        ],
        "focus": (
            "Find actionable strategies for trading XAUUSD breakouts triggered by "
            "ultra-high-volume candles on 1-minute charts. Look for entry filters, "
            "confirmation signals, and patterns that separate real breakouts from traps."
        ),
    },
    {
        "id": 2,
        "name": "Risk Intern",
        "role": "Risk management and trade optimization researcher",
        "searches": [
            "forex scalping optimal take profit stop loss ratio {year}",
            "XAUUSD spread impact on scalping profitability",
            "breakout trading position sizing after drawdown",
            "bid ask spread management gold trading strategies",
            "when to skip breakout trade forex filter signals",
        ],
        "focus": (
            "Research risk management for high-frequency XAUUSD breakout trading. "
            "Focus on: optimal TP/SL ratios for 1-min scalping, spread-adjusted targets, "
            "drawdown recovery strategies, and filters to SKIP bad breakout setups."
        ),
    },
    {
        "id": 3,
        "name": "Market Structure Intern",
        "role": "XAUUSD market microstructure and session behavior researcher",
        "searches": [
            "XAUUSD best trading session times breakout frequency {year}",
            "gold market microstructure 1 minute chart patterns",
            "XAUUSD London New York session volatility comparison",
            "gold futures volume patterns by time of day",
            "round number psychology gold trading xx00 xx50 levels",
        ],
        "focus": (
            "Research how XAUUSD behaves at different times of day, across sessions "
            "(Sydney, Tokyo, London, New York), and around key price levels. "
            "Find patterns in WHEN breakouts work best and WHEN they fail."
        ),
    },
]


# ── Web Browsing ─────────────────────────────────────────────────

def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the internet via DuckDuckGo. Returns list of {title, href, body}."""
    if not SEARCH_AVAILABLE:
        log(f"  SEARCH_SKIP: ddgs not installed")
        return []
    try:
        results = list(DDGS().text(query, max_results=max_results))
        return results
    except Exception as e:
        log(f"  SEARCH_ERR: {e}")
        return []


def fetch_article(url: str, max_chars: int = 8000) -> str:
    """Fetch and extract readable text from a URL."""
    if not FETCH_AVAILABLE:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (research bot)"}
        r = req.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return f"[HTTP {r.status_code}]"

        text = r.text
        # Strip HTML tags (basic)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_chars]
    except Exception as e:
        return f"[FETCH_ERR: {e}]"


# ── Intern Research Session ──────────────────────────────────────

def run_intern(intern_brief: dict) -> dict:
    """
    Run a single intern's research session.
    1. Search the web for relevant articles
    2. Read the top articles
    3. Ask Claude to analyze and extract actionable findings
    """
    intern_id = intern_brief["id"]
    name = intern_brief["name"]
    log(f"\n{'='*60}")
    log(f"INTERN {intern_id}: {name}")
    log(f"Role: {intern_brief['role']}")
    log(f"{'='*60}")

    year = datetime.now().year
    all_search_results = []
    articles_read = []

    # Phase 1: Search the internet
    log(f"\nPhase 1: Searching the internet...")
    for query_template in intern_brief["searches"]:
        query = query_template.replace("{year}", str(year))
        log(f"  Searching: {query}")
        results = web_search(query, max_results=3)
        for r in results:
            log(f"    Found: {r.get('title', '?')[:60]}")
        all_search_results.extend(results)
        time.sleep(1)  # polite delay between searches

    # Deduplicate by URL
    seen_urls = set()
    unique_results = []
    for r in all_search_results:
        url = r.get("href", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)
    log(f"\n  Total unique articles found: {len(unique_results)}")

    # Phase 2: Read top articles
    log(f"\nPhase 2: Reading articles...")
    for r in unique_results[:5]:  # read top 5
        url = r.get("href", "")
        title = r.get("title", "?")
        log(f"  Reading: {title[:50]}...")
        content = fetch_article(url)
        if content and len(content) > 100:
            articles_read.append({
                "title": title,
                "url": url,
                "snippet": r.get("body", ""),
                "content": content[:6000],  # cap per article
            })
            log(f"    Got {len(content)} chars")
        else:
            log(f"    Skipped (too short or failed)")
        time.sleep(0.5)

    log(f"\n  Articles successfully read: {len(articles_read)}")

    # Phase 3: Claude analyzes findings
    log(f"\nPhase 3: Claude analyzing findings...")

    api_key = _load_api_key()
    if not api_key or not CLAUDE_AVAILABLE:
        log("  ERROR: No Claude API — cannot analyze findings")
        return _empty_finding(intern_brief)

    articles_text = ""
    for i, a in enumerate(articles_read):
        articles_text += f"\n--- ARTICLE {i+1}: {a['title']} ---\n"
        articles_text += f"URL: {a['url']}\n"
        articles_text += f"Content:\n{a['content'][:4000]}\n"

    prompt = f"""You are the {name} — a research intern for a XAUUSD trading system.

YOUR RESEARCH BRIEF:
{intern_brief['focus']}

You searched the internet and read these articles:
{articles_text if articles_text else "(No articles could be fetched today)"}

Also use your own knowledge of Volume Spread Analysis, XAUUSD trading, and market microstructure.

Based on your research, produce a structured report with:

1. **KEY FINDINGS** (3-5 bullet points of the most important discoveries)

2. **ACTIONABLE THEORIES** (2-4 specific, testable theories for our system)
   For each theory, provide:
   - Name (short, descriptive)
   - Description (what the theory claims)
   - How to test it (what data/conditions to check)
   - Confidence (your confidence this theory is valid, 0-100%)
   - Source (which article or your own knowledge)

3. **RECOMMENDED ACTIONS** (specific things to implement or test)
   - Should we add a new entry filter?
   - Should we change our profit target or stop loss?
   - Should we avoid certain times or conditions?
   - Should we write new code to test something?

4. **WARNINGS** (risks or traps to be aware of)

Write your findings as a research intern would — be thorough, cite your sources,
and flag what needs the senior analyst's (Claude's) attention at end of day.

Format your response as JSON:
{{
  "key_findings": ["finding1", "finding2", ...],
  "theories": [
    {{"name": "...", "description": "...", "how_to_test": "...", "confidence": 75, "source": "..."}}
  ],
  "recommended_actions": ["action1", "action2", ...],
  "warnings": ["warning1", ...]
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        log(f"  Claude response: {len(text)} chars")

        # If response was truncated (stop_reason != end_turn), try to fix JSON
        if resp.stop_reason != "end_turn":
            log(f"  WARNING: Response truncated (stop_reason={resp.stop_reason})")
            # Try to close open braces/brackets
            text = text.rstrip()
            open_braces = text.count("{") - text.count("}")
            open_brackets = text.count("[") - text.count("]")
            text += "]" * max(0, open_brackets) + "}" * max(0, open_braces)

        # Parse JSON from response
        findings = None
        try:
            findings = json.loads(text)
        except json.JSONDecodeError:
            pass
        if findings is None and "```" in text:
            for block in text.split("```"):
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                if block.startswith("{"):
                    try:
                        findings = json.loads(block)
                        break
                    except json.JSONDecodeError:
                        pass
        if findings is None and "{" in text:
            try:
                s = text.index("{")
                e = text.rindex("}") + 1
                findings = json.loads(text[s:e])
            except (ValueError, json.JSONDecodeError):
                pass

        if not findings:
            log("  WARNING: Could not parse Claude's analysis")
            findings = {"raw_response": text[:2000]}

        # Build the intern's journal entry
        entry = {
            "intern_id": intern_id,
            "intern_name": name,
            "role": intern_brief["role"],
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "searches_performed": len(all_search_results),
            "articles_read": len(articles_read),
            "sources": [{"title": a["title"], "url": a["url"]} for a in articles_read],
            "findings": findings,
        }

        # Log key findings
        if isinstance(findings, dict):
            for f in findings.get("key_findings", [])[:3]:
                log(f"  FINDING: {str(f)[:80]}")
            for t in findings.get("theories", [])[:2]:
                log(f"  THEORY: {t.get('name', '?')} ({t.get('confidence', '?')}% confident)")

        return entry

    except Exception as e:
        log(f"  CLAUDE_ERR: {e}")
        return _empty_finding(intern_brief)


def _empty_finding(brief: dict) -> dict:
    return {
        "intern_id": brief["id"],
        "intern_name": brief["name"],
        "role": brief["role"],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "searches_performed": 0,
        "articles_read": 0,
        "sources": [],
        "findings": {"error": "Research session failed"},
    }


# ── End-of-Day Review ───────────────────────────────────────────

def run_eod_review(date: str = None):
    """
    Claude reads all interns' findings and decides what to act on.
    Updates theory engine / silver hawk if warranted.
    Generates a summary for the user.
    """
    date = date or _today()
    journal = _load_journal(date)

    if not journal.get("interns"):
        log("EOD: No intern findings to review")
        return

    log(f"\n{'='*60}")
    log(f"END-OF-DAY REVIEW — {date}")
    log(f"Reviewing {len(journal['interns'])} intern reports...")
    log(f"{'='*60}")

    api_key = _load_api_key()
    if not api_key or not CLAUDE_AVAILABLE:
        log("EOD: No Claude API — cannot review")
        return

    # Build the combined findings text
    findings_text = ""
    for entry in journal["interns"]:
        findings_text += f"\n{'─'*40}\n"
        findings_text += f"INTERN: {entry['intern_name']} ({entry['role']})\n"
        findings_text += f"Articles read: {entry['articles_read']}\n"
        findings_text += f"Sources: {', '.join(s['title'][:30] for s in entry.get('sources', []))}\n"
        findings_text += f"Findings:\n{json.dumps(entry.get('findings', {}), indent=2)}\n"

    # Load current theories and patterns for context
    try:
        theories_data = json.loads(THEORIES_FILE.read_text("utf-8"))
        theory_names = [t["name"] for t in theories_data.get("theories", [])]
    except Exception:
        theory_names = []

    try:
        patterns_data = json.loads(PATTERNS_FILE.read_text("utf-8"))
        pattern_count = len(patterns_data.get("patterns", []))
    except Exception:
        pattern_count = 0

    prompt = f"""You are the senior analyst reviewing today's intern research findings.

TODAY'S RESEARCH ({date}):
{findings_text}

CURRENT SYSTEM STATE:
- Active theories: {', '.join(theory_names) if theory_names else 'none'}
- Silver Hawk patterns: {pattern_count} total
- Strategy: XAUUSD UHV breakout on 1-min chart, 0.40 lots, candle-close confirmation

Your job:
1. GRADE each intern's research (A/B/C/D/F) based on quality and actionability
2. Identify the TOP 3 most actionable findings across all interns
3. For each actionable finding, specify:
   - What to do (add theory? change setting? write new code? skip certain setups?)
   - Priority (HIGH/MEDIUM/LOW)
   - How to implement it
4. Generate a 3-line SUMMARY for the user (in simple English)
5. Flag anything that needs USER APPROVAL before implementing

Respond as JSON:
{{
  "intern_grades": {{"Strategy Intern": "B+", "Risk Intern": "A", ...}},
  "top_findings": [
    {{"finding": "...", "action": "...", "priority": "HIGH", "implementation": "..."}}
  ],
  "new_theories_to_add": [
    {{"id": "...", "name": "...", "description": "...", "category": "entry_filter|exit_timing|risk_management", "signal": "confirm|skip|caution"}}
  ],
  "settings_changes": [{{"setting": "...", "current": "...", "proposed": "...", "reason": "..."}}],
  "user_summary": "3 line summary for the user",
  "needs_user_approval": ["item1", "item2"]
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()

        # Parse review
        review = None
        try:
            review = json.loads(text)
        except json.JSONDecodeError:
            pass
        if review is None and "```" in text:
            for block in text.split("```"):
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                if block.startswith("{"):
                    try:
                        review = json.loads(block)
                        break
                    except json.JSONDecodeError:
                        pass
        if review is None and "{" in text:
            try:
                s = text.index("{")
                e = text.rindex("}") + 1
                review = json.loads(text[s:e])
            except (ValueError, json.JSONDecodeError):
                pass

        if not review:
            log("EOD: Could not parse review")
            review = {"raw": text[:2000]}

        # Save review to journal
        journal["eod_review"] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "review": review,
        }
        _save_journal(journal)

        # Log key outcomes
        if isinstance(review, dict):
            log("\nINTERN GRADES:")
            for name, grade in review.get("intern_grades", {}).items():
                log(f"  {name}: {grade}")

            log("\nTOP FINDINGS:")
            for f in review.get("top_findings", [])[:3]:
                log(f"  [{f.get('priority','?')}] {str(f.get('finding',''))[:70]}")
                log(f"    Action: {str(f.get('action',''))[:70]}")

            log(f"\nUSER SUMMARY:\n  {review.get('user_summary', 'No summary')}")

            # Auto-add new theories if Claude recommended them
            new_theories = review.get("new_theories_to_add", [])
            if new_theories:
                _add_theories_from_research(new_theories)

            # Flag items needing approval
            needs_approval = review.get("needs_user_approval", [])
            if needs_approval:
                log(f"\nNEEDS USER APPROVAL:")
                for item in needs_approval:
                    log(f"  - {item}")

            # Send WhatsApp summary to user
            _send_eod_whatsapp(review, date)

    except Exception as e:
        log(f"EOD_ERR: {e}")


def _add_theories_from_research(new_theories: list):
    """Add intern-discovered theories to theories.json."""
    try:
        data = json.loads(THEORIES_FILE.read_text("utf-8"))
        existing_ids = {t["id"] for t in data.get("theories", [])}

        added = 0
        for t in new_theories:
            tid = t.get("id", "").lower().replace(" ", "_")
            if not tid or tid in existing_ids:
                continue
            data["theories"].append({
                "id": tid,
                "name": t.get("name", tid),
                "description": t.get("description", ""),
                "category": t.get("category", "entry_filter"),
                "signal": t.get("signal", "confirm"),
                "condition": "intern_research_pending_validation",
                "validated": 0,
                "invalidated": 0,
                "total_tested": 0,
                "accuracy": 0.0,
                "rank": "unproven",
                "trades": [],
                "source": "intern_hawks_research",
            })
            existing_ids.add(tid)
            added += 1
            log(f"  THEORY ADDED: {t.get('name', tid)} (from intern research)")

        if added > 0:
            data["last_updated"] = _today()
            THEORIES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log(f"  {added} new theories added to theories.json")

    except Exception as e:
        log(f"  ADD_THEORY_ERR: {e}")


def _send_eod_whatsapp(review: dict, date: str):
    """Send end-of-day intern summary via WhatsApp."""
    try:
        python_exe = Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")
        wa_script = SCRIPT_DIR / "whatsapp_alert.py"
        if not python_exe.exists() or not wa_script.exists():
            return

        summary = review.get("user_summary", "Interns ne research ki lekin kuch khaas nahi mila.")
        grades = review.get("intern_grades", {})
        grade_text = ", ".join(f"{k}: {v}" for k, v in grades.items())
        top = review.get("top_findings", [])
        top_text = ". ".join(str(f.get("finding", ""))[:50] for f in top[:2])

        msg = (
            f"Shano aaj ke intern hawks ki report aa gayi hai ({date}). "
            f"Grades: {grade_text}. "
            f"Top findings: {top_text}. "
            f"{summary}"
        )

        import subprocess
        subprocess.Popen(
            [str(python_exe), "-c",
             f"import sys; sys.path.insert(0, r'{SCRIPT_DIR}'); "
             f"from whatsapp_alert import _send; "
             f"_send({repr(msg)})"],
            creationflags=0x08000000,
        )
        log("EOD_WHATSAPP_SENT")
    except Exception as e:
        log(f"EOD_WHATSAPP_ERR: {e}")


# ── Main ─────────────────────────────────────────────────────────

def run_all_interns():
    """Spawn all 3 interns and save their findings to today's journal."""
    log(f"\n{'#'*60}")
    log(f"INTERN HAWKS — Daily Research Session")
    log(f"Date: {_today()}")
    log(f"Interns: {len(INTERN_BRIEFS)}")
    log(f"{'#'*60}")

    journal = _load_journal()

    for brief in INTERN_BRIEFS:
        entry = run_intern(brief)
        journal["interns"].append(entry)
        _save_journal(journal)  # save after each intern in case of crash
        log(f"\nIntern {brief['id']} done. Findings saved to journal.")
        time.sleep(2)  # brief pause between interns

    log(f"\nAll interns complete. Journal saved: {_journal_path()}")
    log(f"Total findings in today's journal: {len(journal['interns'])}")

    # Automatically run EOD review after all interns finish
    log("\nTriggering end-of-day review...")
    run_eod_review()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Intern Hawks — Daily Research Bots")
    parser.add_argument("--intern", type=int, choices=[1, 2, 3],
                        help="Run a specific intern (1=Strategy, 2=Risk, 3=Market)")
    parser.add_argument("--eod", action="store_true",
                        help="Run end-of-day review only")
    args = parser.parse_args()

    if args.eod:
        run_eod_review()
    elif args.intern:
        brief = INTERN_BRIEFS[args.intern - 1]
        journal = _load_journal()
        entry = run_intern(brief)
        journal["interns"].append(entry)
        _save_journal(journal)
    else:
        run_all_interns()
