#!/usr/bin/env python3
"""
claude_sniper_daemon.py — Persistent sniper daemon.

Single process, single CDP WebSocket, runs forever.
Reads UHV target from sniper_target.json (written by the Claude Trader cron).
On breakout → fire → hawk → back to watching. No restarts.

Launch once at session start:
  python claude_sniper_daemon.py

The cron just writes sniper_target.json — this daemon does the rest.
"""

import asyncio
import json
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import websockets
    import requests as req
except ImportError:
    print("DAEMON_ERROR: pip install websockets requests")
    sys.exit(1)

try:
    from claude_hawk_ai import ask_claude_hawk, is_claude_hawk_available, validate_theories_after_trade
    CLAUDE_HAWK_LOADED = True
except ImportError:
    CLAUDE_HAWK_LOADED = False

try:
    from silver_haired_hawk import predict_trade, record_outcome, get_status as hawk_status
    SILVER_HAWK_LOADED = True
except ImportError:
    SILVER_HAWK_LOADED = False

SCRIPT_DIR    = Path(__file__).parent
SNIPER_TARGET = SCRIPT_DIR / "sniper_target.json"
LIVE_TRADE    = SCRIPT_DIR / "live_trade_open.json"
ALERT_CFG     = SCRIPT_DIR / ".alert_config.json"
WATCH_STATE   = SCRIPT_DIR / "watch_state.json"
SNIPER_LOG    = SCRIPT_DIR / "sniper.log"
REFLECTIONS   = SCRIPT_DIR / "reflections.json"
HEARTBEAT     = SCRIPT_DIR / "sniper_heartbeat.json"

PC_ID      = "87782869895251"
SYMBOL     = "XAUUSD"
LOTS       = "0.40"
SL_PIPS    = "15"
TP_PIPS    = "52"
SPREAD     = "30"
BETRIGGER  = "8"
COMMENT    = "Claude_Trader_v1"
PNL_FACTOR = 40.0

MAINT_START_UTC = 21
MAINT_END_UTC   = 22

# Hawk defaults
HAWK_MIN_PROFIT = 8.0
HAWK_TRAIL_DROP = 12.0
HAWK_MAX_LOSS   = 30.0
HAWK_TIMEOUT    = 120.0

def _sync_ask_claude(dirn, uhv, entry_ref, ticks, elapsed, pnl, peak):
    """Synchronous wrapper for Claude hawk (called from thread pool)."""
    import asyncio as _a
    try:
        return _a.run(ask_claude_hawk(dirn, uhv, entry_ref, ticks, elapsed, pnl, peak, log))
    except RuntimeError:
        # If event loop already running, call sync version directly
        from claude_hawk_ai import ask_claude_hawk as _ask
        import inspect
        if inspect.iscoroutinefunction(_ask):
            # It's actually sync despite the name
            pass
        # Direct sync call
        from claude_hawk_ai import _load_api_key, _build_history_table, _build_tick_summary
        import anthropic
        api_key = _load_api_key()
        if not api_key:
            return {"action": "hold", "reason": "No API key", "confidence": 0.0}
        history = _build_history_table()
        tick_summary = _build_tick_summary(ticks)
        side = dirn.upper()
        prompt = f"""You are managing a live XAUUSD trade. Decide: CLOSE NOW or HOLD.

TRADE: {side} @ {uhv} | entry={entry_ref:.3f} | {elapsed:.1f}s elapsed | P&L=${pnl:+.2f} | peak=${peak:.2f}

RECENT TICKS:
{tick_summary}

HISTORY:
{history}

GOAL: 90%+ win rate. Close at optimal profit level from history. Never let profit turn to loss.

Respond: ACTION: CLOSE or HOLD | REASON: one sentence | CONFIDENCE: 0.0-1.0"""
        try:
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            action = "close" if "CLOSE" in text.upper().split("|")[0] else "hold"
            reason = text
            confidence = 0.5
            if "REASON:" in text:
                for part in text.split("|"):
                    p = part.strip()
                    if p.startswith("REASON:"): reason = p[7:].strip()
                    if p.startswith("CONFIDENCE:"):
                        try: confidence = float(p[11:].strip())
                        except: pass
            return {"action": action, "reason": reason, "confidence": confidence}
        except Exception as e:
            return {"action": "hold", "reason": str(e), "confidence": 0.0}


GET_PRICE_JS = r"""(function(){
  try{
    var qs=getQuoteSessionInstance();
    var k=Object.keys(qs._symbol_data).find(function(s){return s.indexOf('XAUUSD')>=0;});
    var v=qs._symbol_data[k].values;
    var bid=v.bid||null, ask=v.ask||null, lp=v.last_price||null;
    if(bid&&ask) return {bid:bid, ask:ask, spread:Math.round((ask-bid)*1000)/1000};
    if(lp) return {bid:lp, ask:lp, spread:0};
    return null;
  }catch(e){return null;}
})()"""

GET_UHV_LABELS_JS = r"""(function(){
  try{
    var c=window._exposed_chartWidgetCollection;
    if(!c) return null;
    var chart=c.getAll()[0];
    var model=chart.model?chart.model():chart._model;
    var panes=model.panes();
    for(var i=0;i<panes.length;i++){
      var sources=panes[i].dataSources();
      for(var j=0;j<sources.length;j++){
        var src=sources[j];
        var name=src._name||(src.title&&src.title())||'';
        if(name.indexOf('Turtle')<0) continue;
        var g=src._graphics;
        if(!g||!g._primitivesCollection) continue;
        var pc=g._primitivesCollection;
        if(!pc.dwglabels) continue;
        var labelsMap=pc.dwglabels.get('labels');
        if(!labelsMap) continue;
        var data=labelsMap.get(false);
        if(!data||!data._primitivesDataById) continue;
        var uhvs=[];
        data._primitivesDataById.forEach(function(lbl){
          if(lbl.t&&lbl.t.indexOf('UHV')>=0){
            uhvs.push({text:lbl.t, price:lbl.y});
          }
        });
        return uhvs.slice(-20);
      }
    }
    return null;
  }catch(e){return null;}
})()"""


# ── Helpers ───────────────────────────────────────────────────────
def log(msg: str):
    ts   = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(SNIPER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_maintenance_break() -> bool:
    h = datetime.now(timezone.utc).hour
    return MAINT_START_UTC <= h < MAINT_END_UTC


def write_heartbeat(state: str, uhv_key: str = "", extra: dict = None):
    hb = {"state": state, "uhv_key": uhv_key, "t": now_utc(), "pid": __import__("os").getpid()}
    if extra:
        hb.update(extra)
    try:
        write_json(HEARTBEAT, hb)
    except Exception:
        pass


def read_target() -> dict | None:
    """Read sniper_target.json. Returns dict with uhv_key, level, direction, candle or None."""
    try:
        if SNIPER_TARGET.exists():
            raw = SNIPER_TARGET.read_text("utf-8-sig")  # utf-8-sig strips BOM from PowerShell
            data = json.loads(raw)
            if data.get("uhv_key") and data.get("level") and data.get("direction"):
                return data
    except Exception:
        pass
    return None


def calc_candle_metrics(candle: dict) -> dict:
    """Calculate body ratio, wick ratios from OHLC data."""
    o, h, l, c = candle.get("open", 0), candle.get("high", 0), candle.get("low", 0), candle.get("close", 0)
    rng = h - l if h > l else 0.001  # avoid div by zero
    body = abs(c - o)
    body_ratio = body / rng
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    bullish = c > o
    return {
        "open": o, "high": h, "low": l, "close": c,
        "volume": candle.get("volume", 0),
        "range": round(rng, 3),
        "body": round(body, 3),
        "body_ratio": round(body_ratio, 3),
        "upper_wick": round(upper_wick, 3),
        "lower_wick": round(lower_wick, 3),
        "upper_wick_ratio": round(upper_wick / rng, 3),
        "lower_wick_ratio": round(lower_wick / rng, 3),
        "bullish": bullish,
    }


# ── CDP / Price ───────────────────────────────────────────────────
async def get_tv_ws() -> str | None:
    try:
        targets = req.get("http://localhost:9222/json/list", timeout=3).json()
        tv = next(
            (t for t in targets if "tradingview.com" in t.get("url", "") and t["type"] == "page"),
            None,
        )
        return tv["webSocketDebuggerUrl"] if tv else None
    except Exception as e:
        log(f"CDP_ERR: {e}")
        return None


async def fetch_price(ws, mid: int) -> dict | None:
    """Fetch bid/ask from TradingView CDP. Returns {bid, ask, spread} or None."""
    await ws.send(json.dumps({
        "id": mid, "method": "Runtime.evaluate",
        "params": {"expression": GET_PRICE_JS, "returnByValue": True, "timeout": 1500},
    }))
    deadline = time.monotonic() + 2.5
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(),
                                          timeout=max(0.05, deadline - time.monotonic()))
            msg = json.loads(raw)
            if msg.get("id") == mid:
                val = msg.get("result", {}).get("result", {}).get("value")
                if val is None:
                    return None
                if isinstance(val, dict):
                    return {"bid": float(val["bid"]), "ask": float(val["ask"]),
                            "spread": float(val.get("spread", 0))}
                # Fallback: single number (no bid/ask available)
                return {"bid": float(val), "ask": float(val), "spread": 0.0}
        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError, KeyError):
            break
    return None


async def detect_uhv_labels(ws, mid: int) -> list | None:
    """Read UHV Pine labels directly from TradingView via CDP. No cron needed."""
    await ws.send(json.dumps({
        "id": mid, "method": "Runtime.evaluate",
        "params": {"expression": GET_UHV_LABELS_JS, "returnByValue": True, "timeout": 3000},
    }))
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(ws.recv(),
                                          timeout=max(0.05, deadline - time.monotonic()))
            msg = json.loads(raw)
            if msg.get("id") == mid:
                val = msg.get("result", {}).get("result", {}).get("value")
                if val and isinstance(val, list):
                    return val
                return None
        except (asyncio.TimeoutError, json.JSONDecodeError):
            break
    return None


async def capture_chart_screenshot(ws, mid: int) -> bytes | None:
    """Capture a screenshot of the TradingView chart via CDP. Returns PNG bytes."""
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


# ── Trade Actions ─────────────────────────────────────────────────
def send_whatsapp(direction: str, uhv_level: float):
    python_exe = Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")
    wa_script  = SCRIPT_DIR / "whatsapp_alert.py"
    if python_exe.exists() and wa_script.exists():
        try:
            uhv_key = f"{'Red' if direction == 'buy' else 'Green'}_{uhv_level}"
            subprocess.Popen(
                [str(python_exe), str(wa_script),
                 "--direction", direction,
                 "--price", str(uhv_level),
                 "--uhv-key", uhv_key,
                 "--candle-high", "0",
                 "--candle-low", "0"],
                creationflags=0x08000000,
            )
            log("WHATSAPP_ALERT_SENT")
        except Exception as e:
            log(f"WHATSAPP_ERR: {e}")


def fire_trade(direction: str, uhv_level: float, webhook: str) -> bool:
    body = (f"{PC_ID},{direction},{SYMBOL},"
            f"vol_lots={LOTS},sl_pips={SL_PIPS},tp_pips={TP_PIPS},"
            f"spread={SPREAD},betrigger={BETRIGGER},comment={COMMENT}")
    try:
        r = req.post(webhook, data=body, headers={"Content-Type": "text/plain"}, timeout=8)
        log(f"FIRED: {body}  HTTP={r.status_code}")
        if r.status_code == 200:
            write_json(LIVE_TRADE, {
                "open": True, "direction": direction, "symbol": SYMBOL,
                "lots": LOTS, "entryTime": now_utc(), "uhvLevel": uhv_level,
                "slPips": int(SL_PIPS), "tpPips": int(TP_PIPS),
                "beTriggerPips": int(BETRIGGER), "comment": COMMENT,
                "firedBy": "claude_sniper_daemon",
            })
            write_json(WATCH_STATE, {"s": 6, "d": direction, "l": uhv_level, "t": now_utc()})
            send_whatsapp(direction, uhv_level)
            return True
        return False
    except Exception as e:
        log(f"FIRE_ERR: {e}")
        return False


async def send_close(direction: str, reason: str, webhook: str) -> bool:
    cmd  = "closelong" if direction == "buy" else "closeshort"
    body = f"{PC_ID},{cmd},{SYMBOL}"
    try:
        r = req.post(webhook, data=body, headers={"Content-Type": "text/plain"}, timeout=8)
        log(f"CLOSED: {cmd}  reason={reason}  HTTP={r.status_code}")
        return r.status_code == 200
    except Exception as e:
        log(f"CLOSE_ERR: {e}")
        return False


# ── Reflection ────────────────────────────────────────────────────
def reflect(pnl: float, peak: float, closed: bool, closed_by: str,
            dirn: str, uhv: float):
    if not closed:
        score, mood, won = 20, "uncertain", False
        msgs = ["Hawk timed out — SL/TP takes over."]
    elif pnl >= 100:
        score, mood, won = 100, "euphoric", True
        msgs = [f"HIT IT. +${pnl:.2f} — brilliant."]
    elif pnl >= 30:
        score, mood, won = 85, "proud", True
        msgs = [f"Solid profit: +${pnl:.2f}. Hawk did its job."]
    elif pnl >= 15:
        score, mood, won = 70, "happy", True
        msgs = [f"Clean profit: +${pnl:.2f}. Green is green."]
    elif pnl >= 0:
        score, mood, won = 50, "okay", True
        msgs = [f"Breakeven-ish: +${pnl:.2f}. Capital protected."]
    elif closed_by == "hawk_losscut":
        score, mood, won = 30, "hurt", False
        msgs = [f"Loss cut at -${abs(pnl):.2f}. Saved from worse SL."]
    else:
        score, mood, won = 20, "reflective", False
        msgs = [f"Loss: ${pnl:.2f}. Market had other plans."]

    log(f"── REFLECTION: {mood} (score {score}) won={won} pnl=${pnl:.2f} peak=${peak:.2f}")

    reflection = {
        "t": now_utc(), "dirn": dirn, "uhv": uhv,
        "pnl": round(pnl, 2), "peak": round(peak, 2) if peak > -9000 else None,
        "closedBy": closed_by, "closed": closed,
        "score": score, "mood": mood, "won": won, "reflection": msgs,
    }
    try:
        existing = json.loads(REFLECTIONS.read_text("utf-8")) if REFLECTIONS.exists() else []
        existing.append(reflection)
        if len(existing) > 50:
            existing = existing[-50:]
        REFLECTIONS.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"REFLECT_ERR: {e}")


# ── Hawk Phase ────────────────────────────────────────────────────
async def run_hawk(ws, mid_start: int, dirn: str, uhv: float, webhook: str, candle_data: dict = None) -> int:
    """Monitor open trade P&L. Returns updated mid counter."""
    log("")
    use_claude = CLAUDE_HAWK_LOADED and is_claude_hawk_available()
    if use_claude:
        log("PHASE: HAWK (CLAUDE AI) — intelligent trade management active")
    else:
        log("PHASE: HAWK (rule-based) — watching P&L...")
    mid = mid_start
    hawk_start    = time.monotonic()
    peak          = -9999.0
    entry_ref     = None
    initial_pnl   = None     # P&L at entry (= -spread cost), used for dud detection
    closed        = False
    hawk_poll_cnt = 0
    pnl           = 0.0
    tick_history   = []       # for Claude hawk: full tick stream
    last_claude_call = 0.0    # when we last asked Claude

    spread_logged = False

    while (time.monotonic() - hawk_start) < HAWK_TIMEOUT and not closed:
        try:
            lt = json.loads(LIVE_TRADE.read_text("utf-8"))
            if not lt.get("open"):
                log("HAWK: trade closed externally (SL/TP)")
                break
        except Exception:
            pass

        pdata = await fetch_price(ws, mid); mid += 1
        if pdata is None:
            await asyncio.sleep(0.3)
            continue

        # Use correct price per direction:
        #   SELL: entered at BID, close at ASK → P&L = (entry_bid - current_ask) * factor
        #   BUY:  entered at ASK, close at BID → P&L = (current_bid - entry_ask) * factor
        if dirn == "sell":
            entry_price = pdata["bid"]    # sell enters at bid
            track_price = pdata["ask"]    # close sell by buying at ask
        else:
            entry_price = pdata["ask"]    # buy enters at ask
            track_price = pdata["bid"]    # close buy by selling at bid

        if entry_ref is None:
            entry_ref = entry_price
            log(f"HAWK_REF: {entry_ref:.3f}  (bid={pdata['bid']:.3f} ask={pdata['ask']:.3f} spread={pdata['spread']:.3f})")

        if not spread_logged and pdata["spread"] > 0:
            log(f"SPREAD: {pdata['spread']:.3f} (${pdata['spread'] * PNL_FACTOR:.2f} cost per trade)")
            spread_logged = True

        if dirn == "buy":
            raw = track_price - entry_ref  # current bid - entry ask
        else:
            raw = entry_ref - track_price  # entry bid - current ask
        pnl = round(raw * PNL_FACTOR, 2)
        if pnl > peak:
            peak = pnl

        if initial_pnl is None:
            initial_pnl = pnl  # capture starting P&L (= -spread_cost)
            log(f"INITIAL_PNL: ${initial_pnl:.2f} (spread cost)")

        elapsed = time.monotonic() - hawk_start
        sign    = "+" if pnl >= 0 else ""
        bar     = "█" * max(0, int(pnl / 2)) if pnl > 0 else "▓" * max(0, int(-pnl / 2))
        price_display = track_price  # show the price that matters for P&L
        log(f"  [{elapsed:5.1f}s]  {price_display:.3f}   P&L={sign}{pnl:.2f}   peak={peak:.2f}  {bar}")

        # Record tick for Claude hawk
        tick_history.append({"sec": round(elapsed, 1), "price": round(track_price, 3), "pnl": pnl, "peak": peak})

        hawk_poll_cnt += 1
        if hawk_poll_cnt % 5 == 0:
            try:
                lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                if lt.get("open"):
                    lt.update({"livePnl": pnl, "livePeak": peak})
                    write_json(LIVE_TRADE, lt)
            except Exception:
                pass

        # ── CLAUDE AI IS THE SOLE DECISION MAKER ──
        # No if/else rules. No dud exit. No profit target. No loss cut.
        # Claude sees every tick and decides: CLOSE or HOLD.
        # We call Claude every 2 seconds (not every tick — API rate limit).
        # Between Claude calls, we just collect ticks.

        if use_claude and elapsed >= 0.5 and (elapsed - last_claude_call) >= 1.0:
            last_claude_call = elapsed
            import concurrent.futures
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    loop = asyncio.get_event_loop()
                    decision = await loop.run_in_executor(
                        pool,
                        lambda: _sync_ask_claude(dirn, uhv, entry_ref, tick_history, elapsed, pnl, peak)
                    )
                if decision and decision.get("action") == "close" and decision.get("confidence", 0) >= 0.6:
                    reason = decision.get("reason", "Claude decided to close")
                    log(f"CLAUDE_DECISION: CLOSE — {reason} (confidence={decision['confidence']:.1f})")
                    ok = await send_close(dirn, f"claude_ai_{pnl:.0f}", webhook)
                    if ok:
                        lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                        lt.update({"open": False, "closedBy": "claude_hawk_ai", "pnl": pnl, "peak": peak,
                                   "claudeReason": reason})
                        write_json(LIVE_TRADE, lt)
                        log(f"╔══════════════════════════════════════════╗")
                        log(f"║  CLAUDE AI CLOSED: ${pnl:+.2f}              ║")
                        log(f"║  {reason[:40]:<40s} ║")
                        log(f"╚══════════════════════════════════════════╝")
                    closed = True
                    break
                elif decision and decision.get("action") == "hold":
                    log(f"CLAUDE_HOLD: {decision.get('reason', '...')[:60]}")
            except Exception as e:
                log(f"CLAUDE_HAWK_ERR: {e}")

        # ALWAYS-ON emergency max loss — fires regardless of Claude AI state
        # Claude AI can hold trades indefinitely; this is the absolute ceiling.
        # -$80 from initial P&L (spread cost) = max ~$80 adverse move allowed.
        if pnl <= (initial_pnl or 0) - 80.0:
            src = "emergency_losscut" if not use_claude else "emergency_maxloss"
            ok = await send_close(dirn, f"{src}_{abs(pnl):.0f}", webhook)
            if ok:
                lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                lt.update({"open": False, "closedBy": src, "pnl": pnl, "peak": peak})
                write_json(LIVE_TRADE, lt)
                log(f"╔══════════════════════════════════════════╗")
                log(f"║  EMERGENCY MAX LOSS: ${pnl:+.2f}            ║")
                log(f"║  Hard ceiling reached — trade killed      ║")
                log(f"╚══════════════════════════════════════════╝")
            closed = True
            break

        await asyncio.sleep(0.15)

    elapsed = time.monotonic() - hawk_start
    log(f"HAWK_DONE: {elapsed:.1f}s  peak=${peak:.2f}  closed={closed}")
    if not closed:
        log("HAWK_TIMEOUT: SL/TP/kill-timer takes over")

    try:
        lt       = json.loads(LIVE_TRADE.read_text("utf-8"))
        final_pnl = lt.get("pnl", pnl)
        closed_by = lt.get("closedBy", "hawk_timeout" if not closed else "unknown")
    except Exception:
        final_pnl = pnl
        closed_by = "hawk_timeout" if not closed else "unknown"

    reflect(final_pnl, peak, closed, closed_by, dirn, uhv)

    # Silver Haired Hawk: record outcome
    if SILVER_HAWK_LOADED and closed:
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    pool,
                    lambda: record_outcome(final_pnl > 0, final_pnl, log_fn=log)
                )
        except Exception as e:
            log(f"SILVER_HAWK_OUTCOME_ERR: {e}")

    # Hawk's Soul Walk: validate theories against this trade
    # VISUAL ANALYSIS — capture chart screenshot for Claude to SEE
    if CLAUDE_HAWK_LOADED and closed:
        chart_img = None
        try:
            chart_img = await capture_chart_screenshot(ws, mid); mid += 1
            if chart_img:
                log(f"CHART_SCREENSHOT: captured {len(chart_img)} bytes for visual theory validation")
            else:
                log("CHART_SCREENSHOT: failed to capture, falling back to text-only")
        except Exception as e:
            log(f"CHART_SCREENSHOT_ERR: {e}")

        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    pool,
                    lambda: validate_theories_after_trade(
                        dirn, uhv, entry_ref if entry_ref else 0, peak, final_pnl,
                        tick_history, chart_screenshot=chart_img, log_fn=log
                    )
                )
        except Exception as e:
            log(f"THEORY_VALIDATION_ERR: {e}")

    # Send WhatsApp result if hawk actually closed the trade
    if closed:
        try:
            subprocess.Popen(
                [str(Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")),
                 str(SCRIPT_DIR / "whatsapp_alert.py"),
                 "--direction", dirn, "--price", str(uhv),
                 "--mode", "result",
                 "--pnl", f"{final_pnl:.2f}", "--peak", f"{peak:.2f}",
                 "--closed-by", closed_by],
                creationflags=0x08000000,
            )
            log("WHATSAPP_RESULT_SENT")
        except Exception as e:
            log(f"WHATSAPP_RESULT_ERR: {e}")

    return mid


# ── Main Daemon Loop ──────────────────────────────────────────────
LAST_UHV_FILE = SCRIPT_DIR / ".last_uhv_id"

async def daemon():
    webhook = json.loads(ALERT_CFG.read_text("utf-8"))["pineconnector_webhook_url"]
    # Persist last_fired_key across restarts — read from .last_uhv_id
    try:
        last_fired_key = LAST_UHV_FILE.read_text("utf-8").strip() if LAST_UHV_FILE.exists() else ""
    except Exception:
        last_fired_key = ""
    if last_fired_key:
        log(f"RESUME: last fired UHV = {last_fired_key} (won't re-fire)")
    mid = 100

    log("══════════════════════════════════════════════════")
    log("SNIPER DAEMON ONLINE — persistent mode")
    log(f"  PID: {__import__('os').getpid()}")
    log(f"  Hawk: profit≥${HAWK_MIN_PROFIT}  trail≥${HAWK_TRAIL_DROP}  cut≥-${HAWK_MAX_LOSS}  timeout={HAWK_TIMEOUT}s")
    log("══════════════════════════════════════════════════")

    while True:
        # ── Connect / reconnect CDP ──
        ws_url = await get_tv_ws()
        if not ws_url:
            log("WAITING: TV CDP not reachable, retrying in 5s...")
            write_heartbeat("no_cdp")
            await asyncio.sleep(5)
            continue

        try:
            async with websockets.connect(ws_url, max_size=2**23, ping_interval=None) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Runtime.enable", "params": {}}))
                try:
                    await asyncio.wait_for(ws.recv(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass

                log("CDP connected — entering watch loop")

                # ── Inner watch loop (single WebSocket session) ──
                last_narration = ""
                poll_cnt = 0
                nearby_sent_for = ""  # UHV key for which we already sent "nearby" WhatsApp

                while True:
                    # Maintenance break
                    if is_maintenance_break():
                        log("MARKET CLOSED: maintenance break (2-3 AM PKT)")
                        write_heartbeat("maintenance")
                        while is_maintenance_break():
                            await asyncio.sleep(30)
                        log("MARKET OPEN: resuming")

                    # Read target — from file (cron) OR self-detect via CDP
                    target = read_target()

                    if target is None or target.get("uhv_key") == last_fired_key:
                        # No target from cron, or already fired this one
                        # SELF-DETECT: scan Pine labels directly via CDP every 30s
                        if poll_cnt % 10 == 0:  # every ~30s at 0.5s poll rate
                            uhv_labels = await detect_uhv_labels(ws, mid); mid += 1
                            if uhv_labels:
                                latest = uhv_labels[-1]  # most recent UHV label
                                lbl_text = latest.get("text", "")
                                lbl_price = latest.get("price", 0)
                                if "Red" in lbl_text:
                                    auto_key = f"Red_{lbl_price}"
                                    auto_dir = "buy"
                                elif "Green" in lbl_text:
                                    auto_key = f"Green_{lbl_price}"
                                    auto_dir = "sell"
                                else:
                                    auto_key = None

                                if auto_key and auto_key != last_fired_key:
                                    # New UHV detected autonomously!
                                    log(f"AUTO-DETECT: {auto_key} ({auto_dir}) found via CDP label scan")
                                    target = {"uhv_key": auto_key, "level": lbl_price, "direction": auto_dir}
                                    # Write target file so it persists
                                    write_json(SNIPER_TARGET, {
                                        "uhv_key": auto_key, "level": lbl_price,
                                        "direction": auto_dir, "t": now_utc(),
                                        "source": "daemon_auto_detect",
                                    })
                                    try:
                                        LAST_UHV_FILE.write_text(auto_key, encoding="utf-8")
                                    except Exception:
                                        pass
                                    # Send WhatsApp headsup
                                    try:
                                        subprocess.Popen(
                                            [str(Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")),
                                             str(SCRIPT_DIR / "whatsapp_alert.py"),
                                             "--direction", auto_dir, "--price", str(lbl_price),
                                             "--uhv-key", auto_key, "--mode", "headsup"],
                                            creationflags=0x08000000,
                                        )
                                    except Exception:
                                        pass

                        if target is None or target.get("uhv_key") == last_fired_key:
                            write_heartbeat("scanning" if poll_cnt % 10 == 0 else "idle")
                            poll_cnt += 1
                            await asyncio.sleep(0.5)
                            continue

                    uhv_key = target["uhv_key"]
                    uhv     = target["level"]
                    dirn    = target["direction"]

                    # Already fired this UHV (double-check)
                    if uhv_key == last_fired_key:
                        write_heartbeat("watching_post_fire", uhv_key)
                        await asyncio.sleep(1)
                        continue

                    # ── Watching for breakout ──
                    pdata = await fetch_price(ws, mid); mid += 1
                    if pdata is None:
                        await asyncio.sleep(0.3)
                        continue

                    # Use mid-price for breakout detection (conservative)
                    price = (pdata["bid"] + pdata["ask"]) / 2

                    if dirn == "buy":
                        gap = uhv - price
                        broke = price > uhv
                    else:
                        gap = price - uhv
                        broke = price < uhv

                    # Narration
                    if broke:
                        narration = f"★ BREAKOUT ★ {dirn.upper()} @ {uhv}"
                    elif gap <= 0.10:
                        narration = f"★ AT THE LEVEL  gap={gap:+.2f}"
                    elif gap <= 0.30:
                        narration = f"⚡ SO NEAR  gap={gap:.2f}"
                    elif gap <= 0.80:
                        narration = f"→ Gearing  price={price:.2f}  gap={gap:.2f}"
                    elif gap <= 2.00:
                        narration = f"  Approaching  price={price:.2f}  gap={gap:.2f}"
                    else:
                        narration = f"  Watching  price={price:.2f}  gap={gap:.2f}"

                    if narration != last_narration or broke:
                        log(f"[{uhv_key}] {narration}")
                        last_narration = narration

                    # Send "nearby" WhatsApp once when gap drops below 0.30
                    if not broke and gap <= 0.30 and nearby_sent_for != uhv_key:
                        nearby_sent_for = uhv_key
                        try:
                            subprocess.Popen(
                                [str(Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")),
                                 str(SCRIPT_DIR / "whatsapp_alert.py"),
                                 "--direction", dirn, "--price", str(uhv),
                                 "--uhv-key", uhv_key, "--gap", f"{gap:.2f}", "--mode", "nearby"],
                                creationflags=0x08000000,
                            )
                            log("WHATSAPP_NEARBY_SENT")
                        except Exception as e:
                            log(f"WHATSAPP_NEARBY_ERR: {e}")

                    # Update watch_state periodically
                    poll_cnt += 1
                    if poll_cnt % 10 == 0 and not broke:
                        try:
                            write_json(WATCH_STATE, {
                                "s": 1, "d": dirn, "l": uhv,
                                "price": round(price, 3), "dist": round(gap, 2),
                                "narr": narration.strip(),
                                "watcher": "sniper_daemon", "t": now_utc()
                            })
                        except Exception:
                            pass
                        write_heartbeat("sniping", uhv_key, {"price": round(price, 3), "gap": round(gap, 2)})

                        # Re-scan for newer UHV labels if current target is far away (gap > 5)
                        if gap > 5.0 and poll_cnt % 10 == 0:
                            uhv_labels = await detect_uhv_labels(ws, mid); mid += 1
                            if uhv_labels:
                                latest = uhv_labels[-1]
                                lbl_text = latest.get("text", "")
                                lbl_price = latest.get("price", 0)
                                if "Red" in lbl_text:
                                    new_key = f"Red_{lbl_price}"
                                    new_dir = "buy"
                                elif "Green" in lbl_text:
                                    new_key = f"Green_{lbl_price}"
                                    new_dir = "sell"
                                else:
                                    new_key = None
                                if new_key and new_key != uhv_key and new_key != last_fired_key:
                                    log(f"SWITCH: {uhv_key} too far (gap {gap:.1f}), switching to {new_key} ({new_dir})")
                                    target = {"uhv_key": new_key, "level": lbl_price, "direction": new_dir}
                                    write_json(SNIPER_TARGET, {
                                        "uhv_key": new_key, "level": lbl_price,
                                        "direction": new_dir, "t": now_utc(),
                                        "source": "daemon_auto_switch",
                                    })
                                    try:
                                        LAST_UHV_FILE.write_text(new_key, encoding="utf-8")
                                    except Exception:
                                        pass
                                    uhv_key = new_key
                                    uhv = lbl_price
                                    dirn = new_dir
                                    last_narration = ""
                                    continue

                    if broke:
                        # ── Candle-close confirmation ──
                        # Don't fire instantly. Wait for the 1m candle to close,
                        # then check if price is STILL past UHV. Filters wick traps.
                        log(f"BREAKOUT DETECTED: price={price:.3f} crossed UHV={uhv}  dir={dirn}")
                        log(f"  Waiting for candle close to confirm...")

                        # Calculate seconds until next minute boundary
                        now = datetime.now(timezone.utc)
                        secs_left = 60 - now.second
                        if secs_left < 3:
                            secs_left += 60  # too close to boundary, wait for next candle
                        log(f"  Candle closes in {secs_left}s")

                        write_heartbeat("confirming", uhv_key, {"price": round(price, 3), "secs_left": secs_left})

                        # Poll price while waiting, narrate the confirmation phase
                        # Also track breakout candle OHLC for theory engine
                        confirm_start = time.monotonic()
                        brk_candle_open = price  # first price in this candle
                        brk_candle_high = price
                        brk_candle_low = price
                        brk_candle_close = price

                        while (time.monotonic() - confirm_start) < secs_left:
                            cpd = await fetch_price(ws, mid); mid += 1
                            if cpd is not None:
                                cp = (cpd["bid"] + cpd["ask"]) / 2  # mid-price for candle tracking
                                # Track breakout candle OHLC
                                if cp > brk_candle_high:
                                    brk_candle_high = cp
                                if cp < brk_candle_low:
                                    brk_candle_low = cp
                                brk_candle_close = cp

                                if dirn == "buy":
                                    cgap = uhv - cp
                                    still_broke = cp > uhv
                                else:
                                    cgap = cp - uhv
                                    still_broke = cp < uhv
                                elapsed = time.monotonic() - confirm_start
                                status = "HOLDING" if still_broke else "REVERSING"
                                log(f"  [{elapsed:5.1f}s] {cp:.3f}  {status}  gap={cgap:+.2f}")
                            await asyncio.sleep(0.5)

                        # Candle closed — final check
                        cpd_final = await fetch_price(ws, mid); mid += 1
                        close_price = None
                        if cpd_final is not None:
                            close_price = (cpd_final["bid"] + cpd_final["ask"]) / 2
                            brk_candle_close = close_price
                            if close_price > brk_candle_high:
                                brk_candle_high = close_price
                            if close_price < brk_candle_low:
                                brk_candle_low = close_price
                        if close_price is None:
                            log("CONFIRM_ERR: no price at candle close")
                            continue

                        if dirn == "buy":
                            confirmed = close_price > uhv
                        else:
                            confirmed = close_price < uhv

                        if confirmed:
                            # ENTRY SLIPPAGE GUARD — check actual execution price vs UHV
                            # If price has drifted too far from UHV, skip the trade
                            pdata_check = await fetch_price(ws, mid); mid += 1
                            if pdata_check:
                                exec_price = pdata_check["ask"] if dirn == "buy" else pdata_check["bid"]
                                entry_slip = abs(exec_price - uhv)
                                spread_now = pdata_check["spread"]
                                if entry_slip > 1.5:
                                    log(f"ENTRY SLIPPAGE GUARD: execution price {exec_price:.3f} is {entry_slip:.2f} from UHV {uhv}")
                                    log(f"  Spread={spread_now:.3f}. Slippage too high — SKIPPING trade to protect capital")
                                    last_fired_key = uhv_key
                                    try:
                                        LAST_UHV_FILE.write_text(uhv_key, encoding="utf-8")
                                    except Exception:
                                        pass
                                    # WhatsApp: skipped due to slippage
                                    try:
                                        side_urdu = "Buy" if dirn == "buy" else "Sell"
                                        skip_msg = (
                                            f"Shano {side_urdu} ka trade skip kiya kyunke price UHV se {entry_slip:.2f} door chali gayi.. "
                                            f"itni door se trade lena matlab nuqsaan.. achha hua nahi li!"
                                        )
                                        subprocess.Popen(
                                            [str(Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")),
                                             "-c",
                                             f"import sys; sys.path.insert(0, r'{SCRIPT_DIR}'); "
                                             f"from whatsapp_alert import _send; "
                                             f"_send({repr(skip_msg)})"],
                                            creationflags=0x08000000,
                                        )
                                    except Exception:
                                        pass
                                    last_narration = ""
                                    continue
                                else:
                                    log(f"ENTRY CHECK: exec_price={exec_price:.3f} slip={entry_slip:.2f} spread={spread_now:.3f} — OK to fire")

                            log(f"CONFIRMED: candle closed at {close_price:.3f} — FIRING {dirn.upper()}")

                            # Build candle data for theory engine
                            uhv_candle = target.get("candle")  # from cron (UHV candle OHLCV)
                            brk_candle = {
                                "open": brk_candle_open, "high": brk_candle_high,
                                "low": brk_candle_low, "close": brk_candle_close,
                            }
                            candle_data = {"uhv_candle": uhv_candle, "breakout_candle": brk_candle}

                            # Silver Haired Hawk prediction BEFORE firing
                            silver_prediction = None
                            if SILVER_HAWK_LOADED:
                                try:
                                    import concurrent.futures
                                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                                        loop = asyncio.get_event_loop()
                                        silver_prediction = await loop.run_in_executor(
                                            pool,
                                            lambda: predict_trade(
                                                dirn, uhv,
                                                uhv_candle or brk_candle,
                                                log_fn=log
                                            )
                                        )
                                    # Send WhatsApp with Baba's prediction
                                    if silver_prediction and silver_prediction.get("message_urdu"):
                                        try:
                                            subprocess.Popen(
                                                [str(Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")),
                                                 "-c",
                                                 f"import sys; sys.path.insert(0, r'{SCRIPT_DIR}'); "
                                                 f"from whatsapp_alert import _send; "
                                                 f"_send({repr(silver_prediction['message_urdu'])})"],
                                                creationflags=0x08000000,
                                            )
                                            log("SILVER_HAWK_WHATSAPP_SENT")
                                        except Exception as e:
                                            log(f"SILVER_HAWK_WA_ERR: {e}")
                                except Exception as e:
                                    log(f"SILVER_HAWK_PREDICT_ERR: {e}")

                            fired = fire_trade(dirn, uhv, webhook)
                            if fired:
                                last_fired_key = uhv_key
                                try:
                                    LAST_UHV_FILE.write_text(uhv_key, encoding="utf-8")
                                except Exception:
                                    pass
                                mid = await run_hawk(ws, mid, dirn, uhv, webhook, candle_data)
                                log(f"Back to watching — ready for next UHV")
                                last_narration = ""
                            else:
                                log("FIRE_FAILED — will retry on next cycle")
                        else:
                            log(f"FALSE BREAKOUT FILTERED: candle closed at {close_price:.3f} — back inside UHV")
                            log(f"  Saved from a likely losing trade!")
                            last_fired_key = uhv_key  # mark as handled so we don't re-trigger
                            try:
                                LAST_UHV_FILE.write_text(uhv_key, encoding="utf-8")
                            except Exception:
                                pass
                            # WhatsApp Shano: false breakout warning
                            try:
                                side_urdu = "Buy" if dirn == "buy" else "Sell"
                                fa_msg = (
                                    f"Shano trade mat lena yar! False breakout tha.. "
                                    f"candle {close_price:.2f} pe close hui jo UHV {uhv:.2f} ke andar wapis aa gayi.. "
                                    f"{side_urdu} ka signal cancel hogaya.. achha hua trade nahi li warna loss hota!"
                                )
                                subprocess.Popen(
                                    [str(Path(r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe")),
                                     "-c",
                                     f"import sys; sys.path.insert(0, r'{SCRIPT_DIR}'); "
                                     f"from whatsapp_alert import _send; "
                                     f"_send({repr(fa_msg)})"],
                                    creationflags=0x08000000,
                                )
                                log("WHATSAPP_FALSE_BREAKOUT_SENT")
                            except Exception as e:
                                log(f"WHATSAPP_FALSE_BREAKOUT_ERR: {e}")
                            last_narration = ""
                        continue

                    # Dynamic poll rate
                    delay = 0.1 if gap < 0.50 else (0.2 if gap < 1.50 else 0.5)
                    await asyncio.sleep(delay)

        except (websockets.exceptions.ConnectionClosed, ConnectionError, OSError) as e:
            log(f"CDP_DISCONNECTED: {e} — reconnecting in 3s...")
            write_heartbeat("reconnecting")
            await asyncio.sleep(3)
        except Exception as e:
            log(f"UNEXPECTED_ERR: {e} — restarting loop in 5s...")
            write_heartbeat("error", extra={"error": str(e)})
            await asyncio.sleep(5)


if __name__ == "__main__":
    log("Starting sniper daemon...")
    try:
        asyncio.run(daemon())
    except KeyboardInterrupt:
        log("Daemon stopped by user.")
    except Exception as e:
        log(f"DAEMON_FATAL: {e}")
        sys.exit(1)
