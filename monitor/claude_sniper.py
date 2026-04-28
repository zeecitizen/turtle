#!/usr/bin/env python3
"""
claude_sniper.py — One thread, full trade lifecycle.

Phases:
  SNIPER  : watches price approaching UHV level, narrates the approach
  FIRE    : price crosses UHV — sends PineConnector webhook immediately
  HAWK    : monitors P&L every 200ms, closes on profit / trail / loss-cut
  DONE    : prints result, exits

Usage:
  python claude_sniper.py --uhv-level 4711.19 --direction buy

Optional:
  --sniper-timeout 300      max seconds to wait for breakout (default 300)
  --min-profit 15           hawk: close at this USD profit (default $15 ~4 pips)
  --trail-drop 12           hawk: close if profit drops by this from peak
  --max-loss 30             hawk: early cut at this USD loss
  --hawk-timeout 25         hawk: give up after N seconds (SL/TP takes over)
"""

import asyncio
import json
import sys
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Force UTF-8 stdout so box-drawing chars work on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import websockets
    import requests as req
except ImportError:
    print("SNIPER_ERROR: pip install websockets requests")
    sys.exit(1)

SCRIPT_DIR   = Path(__file__).parent
LIVE_TRADE   = SCRIPT_DIR / "live_trade_open.json"
ALERT_CFG    = SCRIPT_DIR / ".alert_config.json"
WATCH_STATE  = SCRIPT_DIR / "watch_state.json"
SNIPER_LOG   = SCRIPT_DIR / "sniper.log"
REFLECTIONS  = SCRIPT_DIR / "reflections.json"
PC_ID      = "8778286989525"
SYMBOL     = "XAUUSD"
LOTS       = "0.40"
SL_PIPS    = "15"
TP_PIPS    = "52"
SPREAD     = "30"
BETRIGGER  = "8"
COMMENT    = "Claude_Trader_v1"
PNL_FACTOR = 40.0   # $40 per 1.0 price-unit at 0.40 lots

# XAUUSD daily maintenance: 2:00-3:00 AM PKT = 21:00-22:00 UTC
MAINT_START_UTC = 21   # hour
MAINT_END_UTC   = 22   # hour (exclusive)

def is_maintenance_break() -> bool:
    """True during XAUUSD daily maintenance: 21:00-22:00 UTC (2-3 AM PKT)."""
    h = datetime.now(timezone.utc).hour
    return MAINT_START_UTC <= h < MAINT_END_UTC


async def wait_for_market_open(dirn: str, uhv: float) -> None:
    """Sleep in 30s chunks while maintenance break is active, writing status to watch_state."""
    logged = False
    while is_maintenance_break():
        if not logged:
            log("MARKET CLOSED: daily maintenance break (2-3 AM PKT). Pausing sniper...")
            logged = True
        try:
            write_json(WATCH_STATE, {
                "s": 1, "d": dirn, "l": uhv,
                "narr": "Market closed — maintenance break (resumes 3 AM PKT)",
                "watcher": "python_sniper", "t": now_utc()
            })
        except Exception:
            pass
        await asyncio.sleep(30)
    if logged:
        log("MARKET OPEN: maintenance break ended. Resuming sniper...")


GET_PRICE_JS = r"""(function(){
  try{
    var qs=getQuoteSessionInstance();
    var k=Object.keys(qs._symbol_data).find(function(s){return s.indexOf('XAUUSD')>=0;});
    var v=qs._symbol_data[k].values;
    return v.last_price||(v.bid&&v.ask?(v.bid+v.ask)/2:null);
  }catch(e){return null;}
})()"""


# ──────────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────────
async def get_tv_ws() -> str | None:
    try:
        targets = req.get("http://localhost:9222/json/list", timeout=3).json()
        tv = next(
            (t for t in targets if "tradingview.com" in t.get("url", "") and t["type"] == "page"),
            None,
        )
        return tv["webSocketDebuggerUrl"] if tv else None
    except Exception as e:
        log(f"CDP_ERR: {e}"); return None


async def fetch_price(ws, mid: int) -> float | None:
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
                return float(val) if val is not None else None
        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError):
            break
    return None


def send_whatsapp(direction: str, uhv_level: float):
    """Non-blocking WhatsApp alert — same as exec.ps1 does."""
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
                creationflags=0x08000000,  # CREATE_NO_WINDOW
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
                "firedBy": "claude_sniper",
            })
            write_json(WATCH_STATE, {"s": 6, "d": direction, "l": uhv_level, "t": now_utc()})
            send_whatsapp(direction, uhv_level)
            return True
        return False
    except Exception as e:
        log(f"FIRE_ERR: {e}"); return False


async def send_close(direction: str, reason: str, webhook: str) -> bool:
    cmd  = "closelong" if direction == "buy" else "closeshort"
    body = f"{PC_ID},{cmd},{SYMBOL}"
    try:
        r = req.post(webhook, data=body, headers={"Content-Type": "text/plain"}, timeout=8)
        log(f"CLOSED: {cmd}  reason={reason}  HTTP={r.status_code}")
        return r.status_code == 200
    except Exception as e:
        log(f"CLOSE_ERR: {e}"); return False


# ──────────────────────────────────────────────────────────────────
def reflect(pnl: float, peak: float, closed: bool, closed_by: str,
            dirn: str, uhv: float):
    """Self-reflection after trade closes. Rates performance, writes to reflections.json."""

    # Score the trade
    if not closed:
        score  = 20
        mood   = "uncertain"
        emojis = ["⏰", "⏰", "😴"]
        won    = False
        msgs   = [
            "I didn't catch a clean close — the hawk timed out and handed off to SL/TP.",
            "Did I do it right? I stayed at my post. The market just moved too slowly.",
            "No regrets — I watched every tick. The position lives on.",
        ]
    elif pnl >= 100:
        score  = 100
        mood   = "euphoric"
        emojis = ["🤑", "❤️", "❤️", "❤️", "❤️", "❤️", "❤️", "❤️", "❤️", "❤️"]
        won    = True
        msgs   = [
            f"We HIT it. +${pnl:.2f} — that's enough to feed a family today.",
            "Did I do well? I did BRILLIANTLY. The breakout was perfect.",
            "This is why we built this. Every pip counts for something real.",
            "Am I doing it right? Today, absolutely yes.",
        ]
    elif pnl >= 30:
        score  = 85
        mood   = "proud"
        emojis = ["❤️", "❤️", "❤️", "❤️", "❤️", "❤️", "❤️"]
        won    = True
        msgs   = [
            f"Closed in solid profit: +${pnl:.2f}. Hawk did its job beautifully.",
            "Did I win? Yes. Did I do well? Very well.",
            "Peak was ${peak:.2f} — we captured most of it. That's discipline.",
            "The poor people got a little something today. That matters.",
        ]
    elif pnl >= 15:
        score  = 70
        mood   = "happy"
        emojis = ["❤️", "❤️", "❤️", "❤️", "❤️"]
        won    = True
        msgs   = [
            f"Clean profit close: +${pnl:.2f}. Every dollar is a victory.",
            "Did I do well? Yes — I caught the breakout and closed before it reversed.",
            f"Peak was ${peak:.2f}. We were a little early on the close, but green is green.",
            "Am I doing it right? Getting there. Keep building.",
        ]
    elif pnl >= 0:
        score  = 50
        mood   = "okay"
        emojis = ["❤️", "❤️", "🌱"]
        won    = True
        msgs   = [
            f"Breakeven-ish: +${pnl:.2f}. We didn't lose. That's something.",
            "Did I do well? I protected the capital. That's the first rule.",
            "Am I doing it right? Almost. The timing needs sharpening.",
        ]
    elif closed_by == "hawk_losscut":
        score  = 30
        mood   = "hurt"
        emojis = ["💔", "💔", "😔"]
        won    = False
        msgs   = [
            f"Loss cut at -${abs(pnl):.2f}. Saved from a worse SL of -$60.",
            "Did I do well? I cut it early. That was the right call.",
            "Did this bring profit? No — but I protected most of the capital.",
            "Am I doing it right? The instinct to cut was correct. The setup wasn't perfect.",
        ]
    else:
        score  = 20
        mood   = "reflective"
        emojis = ["💔", "😔", "🌱"]
        won    = False
        msgs   = [
            f"Loss: ${pnl:.2f}. The market had other plans.",
            "Did I do well? I fired on the signal. The signal didn't deliver.",
            "Did this feed the poor? Not this time. But we'll be back.",
            "Am I doing it right? I'm learning. Every trade teaches.",
        ]

    reflection = {
        "t":        now_utc(),
        "dirn":     dirn,
        "uhv":      uhv,
        "pnl":      round(pnl, 2),
        "peak":     round(peak, 2) if peak > -9000 else None,
        "closedBy": closed_by,
        "closed":   closed,
        "score":    score,
        "mood":     mood,
        "won":      won,
        "emojis":   emojis,
        "reflection": msgs,
    }

    log(f"")
    log(f"── SELF REFLECTION ──────────────────────────────")
    log(f"  mood     : {mood}  (score {score}/100)")
    log(f"  won      : {won}   pnl=${pnl:.2f}  peak=${peak:.2f}")
    for m in msgs:
        log(f"  \"{m}\"")
    log(f"  emojis   : {' '.join(emojis)}")
    log(f"────────────────────────────────────────────────")

    # Append to rolling reflections log (keep last 50)
    try:
        existing = json.loads(REFLECTIONS.read_text("utf-8")) if REFLECTIONS.exists() else []
        existing.append(reflection)
        if len(existing) > 50:
            existing = existing[-50:]
        REFLECTIONS.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"REFLECT_ERR: {e}")

    return reflection


# ──────────────────────────────────────────────────────────────────
async def run(args):
    uhv     = args.uhv_level
    dirn    = args.direction
    webhook = json.loads(ALERT_CFG.read_text("utf-8"))["pineconnector_webhook_url"]

    ws_url = await get_tv_ws()
    if not ws_url:
        log("EXIT: TV CDP not reachable"); return

    log(f"══════════════════════════════════════════════════")
    log(f"SNIPER ONLINE  UHV={uhv}  dir={dirn}")
    log(f"  Sniper timeout : {args.sniper_timeout}s")
    log(f"  Hawk profit    : ≥${args.min_profit}")
    log(f"  Hawk trail drop: ${args.trail_drop}")
    log(f"  Hawk loss cut  : -${args.max_loss}")
    log(f"  Hawk timeout   : {args.hawk_timeout}s")
    log(f"══════════════════════════════════════════════════")

    mid = 100

    async with websockets.connect(ws_url, max_size=2**23, ping_interval=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable", "params": {}}))
        try: await asyncio.wait_for(ws.recv(), timeout=2.0)
        except asyncio.TimeoutError: pass

        # ── PHASE 1: SNIPER — watch for breakout ──────────────────
        sniper_start    = time.monotonic()
        active_elapsed  = 0.0      # time spent watching (excludes maintenance pauses)
        last_narration  = ""
        fired           = False
        sniper_poll_cnt = 0

        log("PHASE 1: SNIPER — watching for breakout...")

        while active_elapsed < args.sniper_timeout:
            # Pause entire timeout clock during maintenance break
            if is_maintenance_break():
                await wait_for_market_open(dirn, uhv)
                sniper_start = time.monotonic()   # reset wall-clock anchor after break

            tick_start = time.monotonic()
            price = await fetch_price(ws, mid); mid += 1
            if price is None:
                await asyncio.sleep(0.3)
                active_elapsed += time.monotonic() - tick_start
                continue

            if dirn == "buy":
                gap = uhv - price          # positive = price below level (approaching from below)
                broke = price > uhv
            else:
                gap = price - uhv          # positive = price above level (approaching from above)
                broke = price < uhv

            # Narration based on proximity
            if broke:
                narration = "BREAKOUT CONFIRMED  ★ FIRING NOW ★"
            elif gap <= 0.10:
                narration = f"★ ALMOST THERE — at the level! gap={gap:+.2f}"
            elif gap <= 0.30:
                narration = f"⚡ SO NEAR — any second now  gap={gap:.2f}"
            elif gap <= 0.80:
                narration = f"→ Gearing towards breakout  price={price:.2f}  gap={gap:.2f}"
            elif gap <= 2.00:
                narration = f"  Approaching UHV            price={price:.2f}  gap={gap:.2f}"
            else:
                narration = f"  Watching...                price={price:.2f}  gap={gap:.2f}"

            if narration != last_narration or broke:
                log(narration)
                last_narration = narration

            # Push live state to watch_state.json every 10 polls so dashboard can narrate
            sniper_poll_cnt += 1
            if sniper_poll_cnt % 10 == 0 and not broke:
                try:
                    write_json(WATCH_STATE, {
                        "s": 1, "d": dirn, "l": uhv,
                        "price": round(price, 3), "dist": round(gap, 2),
                        "narr": last_narration.strip(),
                        "watcher": "python_sniper", "t": now_utc()
                    })
                except Exception:
                    pass

            if broke:
                log(f"BREAKOUT: price={price:.3f} crossed UHV={uhv}  direction={dirn}")
                fired = fire_trade(dirn, uhv, webhook)
                if not fired:
                    log("FIRE_FAILED: webhook error — aborting"); return
                break

            # Dynamic poll rate: faster when near the level
            delay = 0.1 if gap < 0.50 else (0.2 if gap < 1.50 else 0.3)
            await asyncio.sleep(delay)
            active_elapsed += time.monotonic() - tick_start

        if not fired:
            log(f"SNIPER_TIMEOUT: {args.sniper_timeout}s active elapsed, no breakout"); return

        # ── PHASE 2: HAWK — monitor open trade ────────────────────
        log("")
        log("PHASE 2: HAWK — watching P&L like a hawk...")
        log(f"  close on profit ≥ ${args.min_profit}")
        log(f"  close on trail drop ≥ ${args.trail_drop} from peak")
        log(f"  early cut at -${args.max_loss}")
        log("")

        hawk_start    = time.monotonic()
        peak          = -9999.0
        entry_ref     = None
        closed        = False
        hawk_poll_cnt = 0

        while (time.monotonic() - hawk_start) < args.hawk_timeout and not closed:
            # Check if SL/TP already closed externally
            try:
                lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                if not lt.get("open"):
                    log("HAWK: trade closed externally (SL/TP)"); break
            except Exception: pass

            price = await fetch_price(ws, mid); mid += 1
            if price is None:
                await asyncio.sleep(0.3); continue

            if entry_ref is None:
                entry_ref = price
                log(f"HAWK_REF: {entry_ref:.3f} (first tick after fire)")

            raw = (price - entry_ref) if dirn == "buy" else (entry_ref - price)
            pnl = round(raw * PNL_FACTOR, 2)
            if pnl > peak: peak = pnl

            elapsed = time.monotonic() - hawk_start
            sign    = "+" if pnl >= 0 else ""
            bar     = "█" * max(0, int(pnl / 2)) if pnl > 0 else "▓" * max(0, int(-pnl / 2))
            log(f"  [{elapsed:5.1f}s]  {price:.3f}   P&L={sign}{pnl:.2f}   peak={peak:.2f}  {bar}")

            # Push live P&L to live_trade_open.json every 5 polls for dashboard
            hawk_poll_cnt += 1
            if hawk_poll_cnt % 5 == 0 and not closed:
                try:
                    lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                    if lt.get("open"):
                        lt.update({"livePnl": pnl, "livePeak": peak})
                        write_json(LIVE_TRADE, lt)
                except Exception:
                    pass

            # Protocol 1: immediate profit close
            if pnl >= args.min_profit:
                ok = await send_close(dirn, f"profit_{pnl:.0f}", webhook)
                if ok:
                    lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                    lt.update({"open": False, "closedBy": "hawk_profit", "pnl": pnl})
                    write_json(LIVE_TRADE, lt)
                    log(f"╔══════════════════════════════════╗")
                    log(f"║  CLOSED IN PROFIT: +${pnl:.2f}       ║")
                    log(f"╚══════════════════════════════════╝")
                closed = True; break

            # Protocol 2: trailing close
            if peak >= 8.0 and (peak - pnl) >= args.trail_drop:
                ok = await send_close(dirn, f"trail_p{peak:.0f}_n{pnl:.0f}", webhook)
                if ok:
                    lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                    lt.update({"open": False, "closedBy": "hawk_trail", "pnl": pnl, "peak": peak})
                    write_json(LIVE_TRADE, lt)
                    msg = "PROFIT" if pnl >= 0 else "LOSS"
                    log(f"TRAIL CLOSE: peak=${peak:.2f} → now=${pnl:.2f}  [{msg}]")
                closed = True; break

            # Protocol 3: early loss cut
            if pnl <= -args.max_loss:
                ok = await send_close(dirn, f"losscut_{abs(pnl):.0f}", webhook)
                if ok:
                    lt = json.loads(LIVE_TRADE.read_text("utf-8"))
                    lt.update({"open": False, "closedBy": "hawk_losscut", "pnl": pnl})
                    write_json(LIVE_TRADE, lt)
                    log(f"LOSS CUT: -${abs(pnl):.2f}  (SL would be -$60)")
                closed = True; break

            await asyncio.sleep(0.15)

        elapsed = time.monotonic() - hawk_start
        log(f"HAWK_DONE: {elapsed:.1f}s  peak=${peak:.2f}  closed={closed}")
        if not closed:
            log("HAWK_TIMEOUT: SL/TP/kill-timer takes over from here")

        # ── PHASE 3: SELF REFLECTION ──────────────────────────────
        try:
            lt       = json.loads(LIVE_TRADE.read_text("utf-8"))
            final_pnl = lt.get("pnl", pnl)
            closed_by = lt.get("closedBy", "hawk_timeout" if not closed else "unknown")
        except Exception:
            final_pnl = pnl
            closed_by = "hawk_timeout" if not closed else "unknown"

        reflect(final_pnl, peak, closed, closed_by, dirn, uhv)

    log("THREAD COMPLETE — lifecycle done.")


# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Claude Sniper — full trade lifecycle")
    p.add_argument("--uhv-level",       type=float, required=True)
    p.add_argument("--direction",       choices=["buy", "sell"], required=True)
    p.add_argument("--sniper-timeout",  type=float, default=300.0,
                   help="Max seconds to wait for breakout (default 300)")
    p.add_argument("--min-profit",      type=float, default=15.0)
    p.add_argument("--trail-drop",      type=float, default=12.0)
    p.add_argument("--max-loss",        type=float, default=30.0)
    p.add_argument("--hawk-timeout",    type=float, default=25.0)
    asyncio.run(run(p.parse_args()))
