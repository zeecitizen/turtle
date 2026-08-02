"""ai_setup_judge.py — let the AI LOOK at the chart instead of hard-coding trend rules.

Zee's point (2026-08-02): every numeric trend proxy we write (local_hump, HH/HL pivots)
is a GUESS at what his eye does instantly. Tuning them either lets the killers through
or blocks the winners. An AI can just look at the chart and say "this is an uptrend,
don't sell here" — which is exactly the judgment we keep failing to hard-code.

Split of responsibilities:
  - CODE does the mechanical part: find the retracement, the UHV, the breakout candle.
  - AI does the JUDGMENT part: is the context right to take this setup at all?

The prompt below is Zee's own rulebook, taken verbatim from his ~90 chart comments.
Returns {"verdict": "TAKE"|"SKIP", "trend": "...", "reason": "..."}.

Usage:
    from ai_setup_judge import judge_png
    r = judge_png("setup.png", side="SELL")
"""
from __future__ import annotations
import base64, json, re, sys
from pathlib import Path

KEY_FILE = Path(__file__).parent / ".claude_api_key"
MODEL = "claude-sonnet-4-5"     # vision + fast enough for a 1-minute bar cycle
CACHE = Path(__file__).parent / "ai_judgments.jsonl"

# Zee's rulebook — his own words, distilled from the setup/loser comments he wrote.
SYSTEM = """You are judging XAUUSD/BTC M1 scalp setups for a trader (Zee) whose rules are:

TREND (the rule that matters most — he lost money every time it was ignored):
- UPTREND = price making HIGHER HIGHS *and* HIGHER LOWS.
- DOWNTREND = LOWER HIGHS *and* LOWER LOWS.
- Anything else = RANGING/SHIFTING.
- He ONLY buys in a confirmed uptrend and ONLY sells in a confirmed downtrend.
- He NEVER trades a ranging market, and never trades when the trend is SHIFTING
  (e.g. price just made a higher low after a downtrend -> the down move is over).

THE SETUP (marked on the chart):
- RET = start of the retracement (a counter-trend candle whose BODY broke the previous
  candle's extreme). It must be a real break, not a barely-touching one.
- UHV = the highest-volume counter-trend candle inside that retracement. It should be
  STRONG-BODIED (a weak/indecision body means sellers/buyers are not exhausted).
- BRKT = the breakout candle: it must be a MOMENTUM candle (large body, small wick),
  the correct colour for the direction, and its volume must be LOWER than the UHV.

Judge ONLY from what the chart shows. Be strict: when in doubt, SKIP.
Reply with STRICT JSON only:
{"verdict":"TAKE" or "SKIP","trend":"uptrend|downtrend|ranging|shifting","reason":"<one short sentence>"}"""


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=KEY_FILE.read_text(encoding="utf-8").strip())


def judge_png(png_path, side, extra=""):
    """-> dict(verdict, trend, reason). On any failure returns verdict SKIP (fail-safe:
    never trade because the judge was unreachable)."""
    try:
        img = base64.standard_b64encode(Path(png_path).read_bytes()).decode()
        msg = _client().messages.create(
            model=MODEL, max_tokens=300, system=SYSTEM,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}},
                {"type": "text", "text": f"The engine wants to take a {side} here"
                                         f"{(' — ' + extra) if extra else ''}. "
                                         f"Judge it by the rules. JSON only."}]}])
        txt = msg.content[0].text.strip()
        m = re.search(r"\{.*\}", txt, re.S)
        out = json.loads(m.group(0)) if m else {"verdict": "SKIP", "trend": "?", "reason": txt[:120]}
    except Exception as e:
        out = {"verdict": "SKIP", "trend": "?", "reason": f"judge unavailable: {e}"}
    try:
        with CACHE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"png": str(png_path), "side": side, **out}) + "\n")
    except Exception:
        pass
    return out


if __name__ == "__main__":
    png, side = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "BUY")
    print(json.dumps(judge_png(png, side), indent=2))
