"""
Claude-Powered Intelligent Hawk — AI trade management.

Instead of if/else rules, this hawk calls Claude API every few seconds
during a live trade, sending it the full tick stream, historical performance,
and asking: "should I close now, or hold?"

Claude sees:
  - Live P&L trajectory (every tick since entry)
  - Historical trade performance (last 20 trades, optimal target table)
  - Current market context (direction, UHV level, session)
  - And makes a human-judgment-level decision

Falls back to rule-based hawk if Claude API is unavailable.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timezone

try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

SCRIPT_DIR = Path(__file__).parent
REFLECTIONS = SCRIPT_DIR / "reflections.json"
THEORIES_FILE = SCRIPT_DIR / "theories.json"
API_KEY_FILE = SCRIPT_DIR / ".claude_api_key"
PNL_FACTOR = 40.0  # $40 per 1.0 price-unit at 0.40 lots


def _load_api_key() -> str | None:
    """Load API key from file."""
    try:
        if API_KEY_FILE.exists():
            return API_KEY_FILE.read_text("utf-8").strip()
    except Exception:
        pass
    return None


def _build_history_table() -> str:
    """Build actionable history for Claude — focus on peak targets, not demoralizing stats."""
    try:
        if not REFLECTIONS.exists():
            return "No historical data available yet."
        trades = json.loads(REFLECTIONS.read_text("utf-8"))
        recent = trades[-20:] if len(trades) >= 20 else trades

        if not recent:
            return "No trades recorded yet."

        peaks = [t.get("peak", 0) for t in recent if t.get("peak") is not None]
        pnls = [t.get("pnl", 0) for t in recent]
        wins = [t for t in recent if t.get("pnl", 0) > 0]

        if not peaks:
            return "No peak data in trade history."

        n = len(peaks)
        pos_peaks = [p for p in peaks if p > 0]

        lines = ["Peak profit analysis (what price CAN reach):"]
        if pos_peaks:
            lines.append(f"  Avg favorable peak: ${sum(pos_peaks)/len(pos_peaks):.2f}")
            lines.append(f"  Best peak: ${max(pos_peaks):.2f}")
            lines.append(f"  {len(pos_peaks)}/{n} trades reached positive P&L territory")
        lines.append("")
        lines.append("Optimal take-profit targets:")
        lines.append("Target | Trades reaching it")
        for t in [5, 10, 15, 20, 30, 50]:
            hits = sum(1 for p in peaks if p >= t)
            if hits > 0:
                lines.append(f"  ${t:2d}   | {hits}/{n}")

        if wins:
            lines.append("")
            lines.append(f"Last {len(wins)} winning trades:")
            for w in wins[-5:]:
                lines.append(f"  {w.get('dirn','?').upper()} +${w['pnl']:.2f} (peak ${w.get('peak',0):.2f})")

        return "\n".join(lines)
    except Exception as e:
        return f"Error loading history: {e}"


def _build_tick_summary(ticks: list[dict]) -> str:
    """Build a compact tick summary for Claude."""
    if not ticks:
        return "No ticks yet."

    lines = []
    # Show every tick for first 5s, then every ~2s after
    for t in ticks:
        s = t["sec"]
        if s <= 5.0 or (s % 2.0 < 0.3) or t == ticks[-1]:
            lines.append(f"  {s:5.1f}s  price={t['price']:.3f}  P&L=${t['pnl']:+.2f}  peak=${t['peak']:.2f}")

    return "\n".join(lines[-30:])  # max 30 lines to keep token count reasonable


async def ask_claude_hawk(
    dirn: str,
    uhv: float,
    entry_ref: float,
    ticks: list[dict],
    elapsed: float,
    current_pnl: float,
    peak_pnl: float,
    log_fn=None,
) -> dict:
    """
    Ask Claude whether to close the trade now or hold.

    Returns: {"action": "close"|"hold", "reason": "...", "confidence": 0.0-1.0}
    """
    if not CLAUDE_AVAILABLE:
        return {"action": "hold", "reason": "Claude SDK not available", "confidence": 0.0}

    api_key = _load_api_key()
    if not api_key:
        return {"action": "hold", "reason": "No API key configured", "confidence": 0.0}

    history = _build_history_table()
    tick_summary = _build_tick_summary(ticks)
    theories = _load_theories()

    prompt = f"""You are the Hawk's Soul Walk — the SOLE decision maker for a live XAUUSD trade.
YOU decide when to close. There is a hard emergency ceiling at -$80 beyond spread, but
your job is to make SMART decisions well before that limit.

TRADE CONTEXT:
- Direction: {dirn.upper()}
- UHV breakout level: {uhv}
- Entry price: {entry_ref:.3f}
- Time in trade: {elapsed:.1f} seconds
- Current P&L: ${current_pnl:+.2f}
- Peak P&L: ${peak_pnl:.2f}
- Lot size: 0.40 (each $1.00 price move = $40 P&L)
- Spread cost at entry: the starting negative P&L is the spread — this is NORMAL, not a loss

LIVE TICK STREAM (most recent):
{tick_summary}

{history}

TRADING THEORIES:
{theories}

THE STRATEGY WORKS — TRUST THE BREAKOUT:
- The UHV indicator has a proven 65% win rate with +$31/trade in simulation.
- The breakout direction IS statistically correct. Your job is to ride it.
- Trades start NEGATIVE because of spread (~$15-30). This is normal, NOT a loss.
- A trade at -$25 with $25 spread means ZERO price movement. DON'T PANIC.
- Good breakouts take 15-60 seconds to develop. Be PATIENT.
- The spread cost is the cost of entry — wait for price to move past it.

YOUR DECISION FRAMEWORK:
1. FIRST 15 SECONDS: Almost always HOLD. Price needs time to move.
2. 15-30 SECONDS: Only close if price is moving AGAINST us consistently (3+ ticks same direction).
3. 30-60 SECONDS: Lock profit if P&L > +$15. Close if price clearly reversed.
4. 60+ SECONDS: If still near spread cost with no movement, the breakout failed — close.
5. AT ANY TIME: If P&L goes positive and reaches +$20 or more, STRONGLY consider locking profit.
6. NEVER let a +$20 peak turn into a loss. If peak was +$20 and current is +$5, close NOW.

WHAT "AGAINST US" MEANS:
- BUY trade: price dropping (3+ consecutive lower ticks)
- SELL trade: price rising (3+ consecutive higher ticks)
- A single tick against us is noise. 3+ consecutive is a reversal signal.

Respond with EXACTLY one line:
ACTION: CLOSE or HOLD | REASON: your one-sentence reasoning | CONFIDENCE: 0.0 to 1.0"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if log_fn:
            log_fn(f"CLAUDE_HAWK: {text}")

        # Parse response
        action = "hold"
        reason = text
        confidence = 0.5

        if "ACTION:" in text:
            parts = text.split("|")
            for part in parts:
                part = part.strip()
                if part.startswith("ACTION:"):
                    val = part.replace("ACTION:", "").strip().upper()
                    action = "close" if "CLOSE" in val else "hold"
                elif part.startswith("REASON:"):
                    reason = part.replace("REASON:", "").strip()
                elif part.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(part.replace("CONFIDENCE:", "").strip())
                    except ValueError:
                        confidence = 0.5

        return {"action": action, "reason": reason, "confidence": confidence}

    except anthropic.APIError as e:
        if log_fn:
            log_fn(f"CLAUDE_HAWK_API_ERR: {e}")
        return {"action": "hold", "reason": f"API error: {e}", "confidence": 0.0}
    except Exception as e:
        if log_fn:
            log_fn(f"CLAUDE_HAWK_ERR: {e}")
        return {"action": "hold", "reason": f"Error: {e}", "confidence": 0.0}


def _load_theories() -> str:
    """Load active theories for Claude's context."""
    try:
        if not THEORIES_FILE.exists():
            return "No theories loaded yet."
        data = json.loads(THEORIES_FILE.read_text("utf-8"))
        theories = data.get("theories", [])
        if not theories:
            return "No theories defined."

        # Sort by accuracy (proven first), then by total_tested (most tested first)
        ranked = sorted(theories, key=lambda t: (-t.get("accuracy", 0), -t.get("total_tested", 0)))

        lines = ["ACTIVE THEORIES (ranked by accuracy):"]
        for t in ranked:
            acc = t.get("accuracy", 0) * 100
            tested = t.get("total_tested", 0)
            rank = t.get("rank", "unproven")
            if tested > 0:
                lines.append(f"  [{rank}] {t['name']}: {acc:.0f}% accurate ({t['validated']}/{tested} validated)")
                lines.append(f"    → {t['description'][:80]}")
            else:
                lines.append(f"  [unproven] {t['name']}: untested")
                lines.append(f"    → {t['description'][:80]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Theory load error: {e}"


def validate_theories_after_trade(
    dirn: str, uhv: float, entry_ref: float, peak: float, final_pnl: float,
    ticks: list[dict], uhv_ohlcv: dict | None = None,
    chart_screenshot: bytes | None = None, log_fn=None
):
    """
    After a trade closes, ask Claude to LOOK AT THE CHART and classify against theories.
    Uses Claude's vision to analyze the actual chart screenshot — not pre-computed metrics.
    Falls back to text-only if no screenshot available.
    """
    if not CLAUDE_AVAILABLE:
        return
    api_key = _load_api_key()
    if not api_key:
        return

    try:
        data = json.loads(THEORIES_FILE.read_text("utf-8"))
    except Exception:
        return

    theories = data.get("theories", [])
    if not theories:
        return

    theory_list = "\n".join([f"  {i+1}. [{t['id']}] {t['name']}: {t['description']}" for i, t in enumerate(theories)])

    tick_summary = _build_tick_summary(ticks[-20:]) if ticks else "No ticks"
    won = "WIN" if final_pnl > 0 else "LOSS"
    entry_slip = abs(entry_ref - uhv) if entry_ref else 0

    prompt = f"""You are the Hawk's Soul Walk — a visual chart analyst. A trade just completed.

LOOK AT THE CHART SCREENSHOT and analyze what you SEE:
- What does the UHV candle look like? Strong body? Doji? Wick rejection?
- What does the breakout candle look like? Clean break or messy?
- What's the volume pattern? Spike? Declining? Normal?
- Any visible patterns? Engulfing? Pin bar? Inside bar?
- Where is price relative to round numbers (xx00, xx50)?
- How does the candle structure before the breakout look?

TRADE CONTEXT:
- Direction: {dirn.upper()} @ UHV {uhv}
- Entry: {entry_ref:.3f} (slippage: {entry_slip:.3f})
- Peak P&L: ${peak:.2f} | Final P&L: ${final_pnl:+.2f} ({won})

P&L TRAJECTORY:
{tick_summary}

THEORIES TO VALIDATE (use what you SEE in the chart):
{theory_list}

For each theory, look at the chart and determine: VALIDATED, INVALIDATED, or N/A.
Use YOUR OWN visual analysis — describe what you actually see in the candles.

Respond with one line per theory:
THEORY_ID: VALIDATED|INVALIDATED|N/A | what you see in the chart that supports/contradicts this"""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Build message — with chart screenshot (vision) or text-only fallback
        if chart_screenshot:
            import base64
            b64_img = base64.b64encode(chart_screenshot).decode("utf-8")
            message_content = [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64_img}},
                {"type": "text", "text": prompt},
            ]
            if log_fn:
                log_fn(f"THEORY_VALIDATION: using chart screenshot ({len(chart_screenshot)} bytes)")
        else:
            message_content = prompt
            if log_fn:
                log_fn("THEORY_VALIDATION: no screenshot available, text-only analysis")

        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": message_content}],
        )
        text = resp.content[0].text.strip()
        if log_fn:
            log_fn(f"THEORY_VALIDATION:\n{text}")

        # Parse and update theories
        for line in text.split("\n"):
            line = line.strip()
            if ":" not in line:
                continue
            parts = line.split(":", 1)
            tid = parts[0].strip().lower()
            rest = parts[1].strip() if len(parts) > 1 else ""

            for t in theories:
                if t["id"] == tid:
                    t["total_tested"] = t.get("total_tested", 0) + 1
                    if "VALIDATED" in rest.upper():
                        t["validated"] = t.get("validated", 0) + 1
                    elif "INVALIDATED" in rest.upper():
                        t["invalidated"] = t.get("invalidated", 0) + 1
                    # Update accuracy
                    if t["total_tested"] > 0:
                        t["accuracy"] = t["validated"] / t["total_tested"]
                    # Update rank
                    if t["total_tested"] >= 10:
                        if t["accuracy"] >= 0.80:
                            t["rank"] = "proven"
                        elif t["accuracy"] >= 0.60:
                            t["rank"] = "promising"
                        elif t["accuracy"] < 0.40:
                            t["rank"] = "disproven"
                        else:
                            t["rank"] = "mixed"
                    elif t["total_tested"] >= 3:
                        t["rank"] = "testing"
                    # Store trade ref
                    t["trades"] = t.get("trades", [])[-19:]  # keep last 20
                    t["trades"].append({"uhv": uhv, "pnl": final_pnl, "result": rest[:50]})
                    break

        data["theories"] = theories
        data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        THEORIES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if log_fn:
            log_fn("THEORIES_UPDATED")

    except Exception as e:
        if log_fn:
            log_fn(f"THEORY_VALIDATION_ERR: {e}")


def get_daily_theory_report() -> str:
    """Generate end-of-day theory ranking report."""
    try:
        data = json.loads(THEORIES_FILE.read_text("utf-8"))
        theories = data.get("theories", [])
        ranked = sorted(theories, key=lambda t: (-t.get("accuracy", 0), -t.get("total_tested", 0)))

        lines = ["DAILY THEORY REPORT", "=" * 50]
        for t in ranked:
            tested = t.get("total_tested", 0)
            if tested == 0:
                lines.append(f"  {t['name']}: untested")
            else:
                acc = t.get("accuracy", 0) * 100
                lines.append(f"  [{t['rank']}] {t['name']}: {acc:.0f}% ({t['validated']}/{tested})")
        return "\n".join(lines)
    except Exception:
        return "No theory data available."


def is_claude_hawk_available() -> bool:
    """Check if Claude hawk can be used (SDK + API key present)."""
    if not CLAUDE_AVAILABLE:
        return False
    key = _load_api_key()
    return key is not None and len(key) > 10
