#!/usr/bin/env python3
"""
Silver Hawk Background Learner — runs continuously, studies candles.

Fetches historical candles from TradingView via CDP every 15 minutes,
sends them to the Silver Haired Hawk to learn patterns.

Launch at startup and leave running:
  python silver_hawk_learner.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import websockets
    import requests as req
except ImportError:
    print("LEARNER_ERROR: pip install websockets requests")
    sys.exit(1)

from silver_haired_hawk import learn_from_candles, get_status

SCRIPT_DIR = Path(__file__).parent
LEARNER_LOG = SCRIPT_DIR / "silver_hawk_learner.log"
LEARN_INTERVAL = 900  # 15 minutes between learning cycles

# CDP JS to get OHLCV bars from TradingView
GET_BARS_JS = r"""(function(){
  try{
    var s=tvWidget.activeChart().getSeries();
    var bars=s.data().bars().toArray();
    var result=[];
    var count=Math.min(bars.length, 500);
    for(var i=bars.length-count; i<bars.length; i++){
      var b=bars[i];
      result.push({t:b.time,o:b.open,h:b.high,l:b.low,c:b.close,v:b.volume||0});
    }
    return result;
  }catch(e){
    try{
      var c=window._exposed_chartWidgetCollection;
      if(!c) return null;
      var ch=c.getAll()[0];
      var ds=ch.model().mainSeries().bars();
      var result=[];
      var size=ds.size();
      var count=Math.min(size, 500);
      for(var i=size-count; i<size; i++){
        var b=ds.valueAt(i);
        if(b) result.push({t:b[0],o:b[1],h:b[2],l:b[3],c:b[4],v:b[5]||0});
      }
      return result;
    }catch(e2){return null;}
  }
})()"""


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LEARNER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


async def get_tv_ws() -> str | None:
    try:
        targets = req.get("http://localhost:9222/json/list", timeout=3).json()
        tv = next(
            (t for t in targets if "tradingview.com" in t.get("url", "") and t["type"] == "page"),
            None,
        )
        return tv["webSocketDebuggerUrl"] if tv else None
    except Exception:
        return None


async def fetch_bars(ws, mid: int) -> list | None:
    """Fetch OHLCV bars from TradingView via CDP."""
    await ws.send(json.dumps({
        "id": mid, "method": "Runtime.evaluate",
        "params": {"expression": GET_BARS_JS, "returnByValue": True, "timeout": 5000},
    }))
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(),
                                          timeout=max(0.1, deadline - time.monotonic()))
            msg = json.loads(raw)
            if msg.get("id") == mid:
                val = msg.get("result", {}).get("result", {}).get("value")
                if val and isinstance(val, list):
                    # Convert to standard format
                    candles = []
                    for b in val:
                        candles.append({
                            "time": b.get("t", 0),
                            "open": b.get("o", 0),
                            "high": b.get("h", 0),
                            "low": b.get("l", 0),
                            "close": b.get("c", 0),
                            "volume": b.get("v", 0),
                        })
                    return candles
                return None
        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError):
            break
    return None


async def capture_screenshot(ws, mid: int) -> bytes | None:
    """Capture chart screenshot via CDP for visual learning."""
    await ws.send(json.dumps({
        "id": mid, "method": "Page.captureScreenshot",
        "params": {"format": "png", "quality": 80},
    }))
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(),
                                          timeout=max(0.1, deadline - time.monotonic()))
            msg = json.loads(raw)
            if msg.get("id") == mid:
                b64 = msg.get("result", {}).get("data")
                if b64:
                    import base64
                    return base64.b64decode(b64)
                return None
        except (asyncio.TimeoutError, json.JSONDecodeError):
            break
    return None


def research_vsa_theories(log_fn=None) -> str:
    """Search the internet for VSA / UHV breakout trading theories."""
    try:
        from silver_haired_hawk import _load_api_key
        import anthropic
        api_key = _load_api_key()
        if not api_key:
            return ""

        # Use Claude to generate search-worthy concepts about VSA
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": """You are a Volume Spread Analysis (VSA) expert.
Share 5 actionable trading theories about Ultra High Volume (UHV) candle breakouts on XAUUSD 1-minute charts.

For each theory, explain:
1. The setup conditions (what the chart looks like before entry)
2. Whether the breakout will likely succeed or fail
3. Your confidence level based on VSA principles

Focus on patterns that a visual chart reader would notice:
- Candle body size relative to range
- Wick patterns and their meaning
- Volume bar height compared to recent bars
- Multi-candle sequences before breakouts
- Price rejection at key levels

Format each as a JSON object:
{"name": "...", "conditions": {"visual_description": "..."}, "outcome": "WIN"|"LOSS", "reliability": 0.0-1.0, "sample_size": N, "source": "VSA_research"}

Return ONLY a JSON array."""}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        if log_fn:
            log_fn(f"VSA_RESEARCH_ERR: {e}")
        return ""


def visual_learn_from_screenshot(screenshot: bytes, log_fn=None) -> int:
    """Ask Claude to look at a chart screenshot and identify patterns visually."""
    try:
        from silver_haired_hawk import _load_api_key, _load_patterns, PATTERNS_FILE
        import anthropic, base64
        api_key = _load_api_key()
        if not api_key:
            return 0

        b64_img = base64.b64encode(screenshot).decode("utf-8")

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64_img}},
                {"type": "text", "text": """LOOK at this XAUUSD 1-minute chart screenshot.

You are training yourself to predict breakout outcomes. Study the candles you see:

1. Find candles with visually large volume bars — these are potential UHV candles
2. Look at what happened AFTER those high-volume candles:
   - Did price break out and continue? (bullish sign)
   - Did price reverse? (trap/rejection)
   - Was the breakout candle strong-bodied or doji-like?

3. Identify VISUAL patterns that predict breakout success or failure:
   - Candle shapes (strong body vs doji vs hammer)
   - Wick patterns (long wicks = rejection)
   - Volume relationship to price movement
   - Pre-breakout consolidation or trend

For each pattern you identify, return a JSON object:
{"name": "...", "conditions": {"visual": "what it looks like on chart"}, "outcome": "WIN"|"LOSS", "reliability": 0.0-1.0, "sample_size": N, "source": "visual_chart_analysis"}

Return ONLY a JSON array of patterns. Base everything on what you actually SEE."""}
            ]}]
        )
        text = resp.content[0].text.strip()
        if log_fn:
            log_fn(f"VISUAL_LEARN_RESPONSE ({len(text)} chars)")

        # Parse patterns
        import json as _json
        patterns = None
        try:
            patterns = _json.loads(text)
        except _json.JSONDecodeError:
            pass
        if patterns is None and "```" in text:
            for block in text.split("```"):
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                if block.startswith("["):
                    try:
                        patterns = _json.loads(block)
                        break
                    except _json.JSONDecodeError:
                        pass
        if patterns is None and "[" in text and "]" in text:
            try:
                s = text.index("[")
                e = text.rindex("]") + 1
                patterns = _json.loads(text[s:e])
            except (ValueError, _json.JSONDecodeError):
                pass

        if not patterns or not isinstance(patterns, list):
            if log_fn:
                log_fn("VISUAL_LEARN: could not parse patterns from visual analysis")
            return 0

        # Merge with existing
        existing = _load_patterns()
        existing_names = {p.get("name") for p in existing}
        added = 0
        for p in patterns:
            if p.get("name") and p.get("name") not in existing_names:
                p["source"] = "visual_chart_analysis"
                existing.append(p)
                added += 1

        PATTERNS_FILE.write_text(_json.dumps({
            "patterns": existing,
            "last_learned": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_candles_analyzed": "visual",
        }, indent=2), encoding="utf-8")

        if log_fn:
            log_fn(f"VISUAL_LEARNED: {added} new patterns from chart screenshot, {len(existing)} total")
        return added

    except Exception as e:
        if log_fn:
            log_fn(f"VISUAL_LEARN_ERR: {e}")
        return 0


async def learner():
    """Main learner loop — visual chart analysis + internet research every 15 minutes."""
    log("=" * 50)
    log("SILVER HAWK LEARNER ONLINE — Visual + Research mode")
    log(f"  Learning interval: {LEARN_INTERVAL}s")
    log(f"  PID: {__import__('os').getpid()}")
    log("  Methods: chart screenshots, OHLCV analysis, VSA research")
    log("=" * 50)

    mid = 1000
    cycle = 0

    while True:
        cycle += 1
        log(f"\n--- Learning cycle {cycle} ---")

        ws_url = await get_tv_ws()
        if not ws_url:
            log("TV CDP not reachable, retrying in 60s...")
            await asyncio.sleep(60)
            continue

        try:
            async with websockets.connect(ws_url, max_size=2**23, ping_interval=None) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Runtime.enable", "params": {}}))
                try:
                    await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

                # ── METHOD 1: Visual learning from chart screenshot ──
                log("Step 1: Visual chart analysis...")
                screenshot = await capture_screenshot(ws, mid); mid += 1
                if screenshot:
                    log(f"  Captured chart screenshot ({len(screenshot)} bytes)")
                    visual_count = visual_learn_from_screenshot(screenshot, log_fn=log)
                    log(f"  Visual patterns learned: {visual_count}")
                else:
                    log("  No screenshot captured")

                # ── METHOD 2: OHLCV numerical analysis ──
                log("Step 2: OHLCV numerical analysis...")
                candles = await fetch_bars(ws, mid); mid += 1
                if candles and len(candles) > 20:
                    log(f"  Fetched {len(candles)} candles")
                    count = learn_from_candles(candles, log_fn=log)
                    log(f"  Numerical patterns learned: {count}")
                else:
                    log(f"  Not enough candles: {len(candles) if candles else 0}")

                # ── METHOD 3: VSA internet research (every 5th cycle) ──
                if cycle % 5 == 1:
                    log("Step 3: VSA internet research...")
                    research_text = research_vsa_theories(log_fn=log)
                    if research_text:
                        # Parse and add research-based patterns
                        import json as _json
                        try:
                            from silver_haired_hawk import _load_patterns, PATTERNS_FILE
                            patterns = None
                            try:
                                patterns = _json.loads(research_text)
                            except _json.JSONDecodeError:
                                if "```" in research_text:
                                    for block in research_text.split("```"):
                                        block = block.strip()
                                        if block.startswith("json"):
                                            block = block[4:].strip()
                                        if block.startswith("["):
                                            try:
                                                patterns = _json.loads(block)
                                                break
                                            except _json.JSONDecodeError:
                                                pass
                            if patterns and isinstance(patterns, list):
                                existing = _load_patterns()
                                existing_names = {p.get("name") for p in existing}
                                added = 0
                                for p in patterns:
                                    if p.get("name") and p.get("name") not in existing_names:
                                        p["source"] = "VSA_research"
                                        existing.append(p)
                                        added += 1
                                if added > 0:
                                    PATTERNS_FILE.write_text(_json.dumps({
                                        "patterns": existing,
                                        "last_learned": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    }, indent=2), encoding="utf-8")
                                    log(f"  VSA research: {added} new theories added")
                                else:
                                    log("  VSA research: no new theories (all already known)")
                        except Exception as e:
                            log(f"  VSA research parse err: {e}")
                    else:
                        log("  VSA research: no results")

                log(get_status())

        except Exception as e:
            log(f"LEARNER_ERR: {e}")

        log(f"Next learning cycle in {LEARN_INTERVAL}s...")
        await asyncio.sleep(LEARN_INTERVAL)


if __name__ == "__main__":
    log("Starting Silver Hawk Learner...")
    try:
        asyncio.run(learner())
    except KeyboardInterrupt:
        log("Learner stopped by user.")
    except Exception as e:
        log(f"LEARNER_FATAL: {e}")
        sys.exit(1)
