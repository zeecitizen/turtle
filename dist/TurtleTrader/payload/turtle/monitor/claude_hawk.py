#!/usr/bin/env python3
"""
claude_hawk.py — Real-time trade monitor. Watches XAUUSD every 200ms via TV CDP.
Protocols:
  1. PROFIT CLOSE  — close immediately when P&L >= min_profit
  2. TRAIL CLOSE   — if peak >= 8, close when profit drops by trail_drop from peak
  3. LOSS CUT      — close when P&L <= -max_loss (before full SL)
  4. TIMEOUT       — exit after timeout seconds (SL/TP takes over)

Usage:
  python claude_hawk.py [--min-profit 15] [--trail-drop 12] [--max-loss 30] [--timeout 25]
"""

import asyncio
import json
import sys
import time
import argparse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import websockets
    import requests as req
except ImportError:
    print("HAWK_ERROR: run:  pip install websockets requests")
    sys.exit(1)

PYTHON      = r"C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
SCRIPT_DIR  = Path(__file__).parent
LIVE_TRADE  = SCRIPT_DIR / "live_trade_open.json"
ALERT_CFG   = SCRIPT_DIR / ".alert_config.json"
HAWK_LOG    = SCRIPT_DIR / "hawk.log"
PC_ID       = "87782869895251"
PNL_FACTOR  = 40.0   # $40 per 1.0 price-unit at 0.40 lots XAUUSD

# JS that reads real-time price from TV's internal quote session
GET_PRICE_JS = r"""(function(){
  try{
    var qs=getQuoteSessionInstance();
    var k=Object.keys(qs._symbol_data).find(function(s){return s.indexOf('XAUUSD')>=0;});
    var v=qs._symbol_data[k].values;
    return v.last_price||(v.bid&&v.ask?(v.bid+v.ask)/2:null);
  }catch(e){return null;}
})()"""


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(HAWK_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def calc_pnl(entry: float, current: float, direction: str) -> float:
    raw = (current - entry) if direction == "buy" else (entry - current)
    return round(raw * PNL_FACTOR, 2)


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


async def fetch_price(ws, mid: int) -> float | None:
    payload = json.dumps({
        "id": mid,
        "method": "Runtime.evaluate",
        "params": {"expression": GET_PRICE_JS, "returnByValue": True, "timeout": 1500},
    })
    await ws.send(payload)
    deadline = time.monotonic() + 2.5
    while time.monotonic() < deadline:
        try:
            raw = await asyncio.wait_for(
                ws.recv(), timeout=max(0.05, deadline - time.monotonic())
            )
            msg = json.loads(raw)
            if msg.get("id") == mid:
                val = msg.get("result", {}).get("result", {}).get("value")
                return float(val) if val is not None else None
        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError):
            break
    return None


async def send_close(direction: str, reason: str, webhook_url: str) -> bool:
    cmd  = "closelong" if direction == "buy" else "closeshort"
    body = f"{PC_ID},{cmd},XAUUSD"
    try:
        r = req.post(
            webhook_url, data=body,
            headers={"Content-Type": "text/plain"}, timeout=8
        )
        log(f"HAWK_CLOSE: {cmd}  reason={reason}  HTTP={r.status_code}")
        return r.status_code == 200
    except Exception as e:
        log(f"HAWK_CLOSE_ERR: {e}")
        return False


async def run(args):
    # ── load trade state ────────────────────────────────────────────
    if not LIVE_TRADE.exists():
        log("HAWK_EXIT: no live_trade_open.json"); return
    trade = json.loads(LIVE_TRADE.read_text("utf-8"))
    if not trade.get("open"):
        log("HAWK_EXIT: trade not open"); return

    direction   = trade["direction"]
    config      = json.loads(ALERT_CFG.read_text("utf-8"))
    webhook     = config["pineconnector_webhook_url"]

    ws_url = await get_tv_ws()
    if not ws_url:
        log("HAWK_EXIT: cannot reach TV CDP"); return

    log(f"HAWK_START  dir={direction}  profit≥${args.min_profit}  "
        f"trail_drop=${args.trail_drop}  loss_cut=${args.max_loss}  timeout={args.timeout}s")

    start      = time.monotonic()
    peak       = -9999.0
    entry_ref  = None
    mid        = 10
    closed     = False

    try:
        async with websockets.connect(ws_url, max_size=2**23, ping_interval=None) as ws:
            # enable Runtime domain
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable", "params": {}}))
            try:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

            while (time.monotonic() - start) < args.timeout and not closed:

                # external close check (SL/TP already fired)
                try:
                    t2 = json.loads(LIVE_TRADE.read_text("utf-8"))
                    if not t2.get("open"):
                        log("HAWK_EXIT: closed externally (SL/TP)"); break
                except Exception:
                    pass

                price = await fetch_price(ws, mid)
                mid += 1

                if price is None:
                    await asyncio.sleep(0.3)
                    continue

                if entry_ref is None:
                    entry_ref = price
                    log(f"HAWK_REF: entry_ref={entry_ref:.3f}  (first tick ~fill price)")

                pnl = calc_pnl(entry_ref, price, direction)
                if pnl > peak:
                    peak = pnl

                elapsed = time.monotonic() - start
                arrow   = "↑" if direction == "buy" else "↓"
                sign    = "+" if pnl >= 0 else ""
                log(f"  [{elapsed:5.1f}s] {arrow} {price:.3f}   P&L={sign}{pnl:.2f}   peak={peak:.2f}")

                # ── Protocol 1: immediate profit close ─────────────
                if pnl >= args.min_profit:
                    ok = await send_close(direction, f"profit_{pnl:.0f}", webhook)
                    if ok:
                        trade.update({"open": False, "closedBy": "hawk_profit", "pnl": pnl})
                        LIVE_TRADE.write_text(json.dumps(trade, indent=2), encoding="utf-8")
                    closed = True
                    break

                # ── Protocol 2: trailing close (protect gains) ──────
                if peak >= 8.0 and (peak - pnl) >= args.trail_drop:
                    ok = await send_close(
                        direction, f"trail_peak{peak:.0f}_now{pnl:.0f}", webhook
                    )
                    if ok:
                        trade.update({"open": False, "closedBy": "hawk_trail",
                                      "pnl": pnl, "peak": peak})
                        LIVE_TRADE.write_text(json.dumps(trade, indent=2), encoding="utf-8")
                    closed = True
                    break

                # ── Protocol 3: early loss cut ──────────────────────
                if pnl <= -args.max_loss:
                    ok = await send_close(direction, f"losscut_{abs(pnl):.0f}", webhook)
                    if ok:
                        trade.update({"open": False, "closedBy": "hawk_losscut", "pnl": pnl})
                        LIVE_TRADE.write_text(json.dumps(trade, indent=2), encoding="utf-8")
                    closed = True
                    break

                await asyncio.sleep(0.2)

    except Exception as e:
        log(f"HAWK_ERR: {e}")

    elapsed = time.monotonic() - start
    log(f"HAWK_DONE  elapsed={elapsed:.1f}s  peak=${peak:.2f}  closed={closed}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--min-profit", type=float, default=15.0,
                   help="Close immediately at this USD profit (default $15 = ~4 pips)")
    p.add_argument("--trail-drop", type=float, default=12.0,
                   help="Close if profit drops by this from peak (default $12)")
    p.add_argument("--max-loss",   type=float, default=30.0,
                   help="Early loss cut at this USD loss (default $30 = half SL)")
    p.add_argument("--timeout",    type=float, default=25.0,
                   help="Exit after this many seconds (SL/TP takes over, default 25s)")
    asyncio.run(run(p.parse_args()))
