"""p0_roundtrip.py - the P0 round trip on PXTrader 2.0 (authorised by Zee 2026-11-03: live account, 0.01 oz):
BUY 0.01 oz XAU/USD at market with TP = ask + 1.20 and SL = ask - 1.00 attached, time the fill, then close that position and time the close.
Writes games/gold_runner/rounds/p0_<ts>.json with every frame that mattered."""
import json, time, re, sys
from pathlib import Path
from cdp import *

OZ = "0.01"; TP_D = 1.20; SL_D = 1.00
c = CDP(pxbt_page())
log = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
def step(msg, **kw): kw["t"] = round(time.time(), 3); kw["msg"] = msg; log["steps"].append(kw); print(f"[{time.strftime('%H:%M:%S')}] {msg} {json.dumps({k: v for k, v in kw.items() if k not in ('t', 'msg')}, default=str)[:300]}", flush=True)
def frames(ev, action=None):
    out = []
    for e in ev:
        if e["method"] != "Network.webSocketFrameReceived": continue
        d = e["params"]["response"]["payloadData"]
        if not d.startswith("{"): continue
        try: f = json.loads(d)
        except ValueError: continue
        if action is None or f.get("action") == action: out.append((e["params"].get("timestamp"), f))
    return out
def setval(sel, val):
    return c.js(f"""(()=>{{const el=document.querySelector('{sel}'); const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; s.call(el,'{val}'); el.dispatchEvent(new Event('input',{{bubbles:true}})); el.dispatchEvent(new Event('change',{{bubbles:true}})); el.blur(); return el.value}})()""")
def overlay():
    return c.js(r"""(()=>{const o=document.querySelector('.cdk-overlay-container'); return o? o.innerText.trim().slice(0,600):''})()""")
def click_overlay_button(pattern):
    return c.js(f"""(()=>{{const o=document.querySelector('.cdk-overlay-container'); if(!o) return 'no overlay'; const b=[...o.querySelectorAll('button')].find(x=>/{pattern}/i.test(x.innerText||'')); if(!b) return 'no button '+[...o.querySelectorAll('button')].map(x=>x.innerText.trim()).join('|'); b.click(); return 'clicked '+b.innerText.trim()}})()""")

c.call("Network.enable")
ev = c.listen(3)
q = [f for _, f in frames(ev, "fx/market")][-1]["body"]; ask, bid = q["a"], q["b"]
imp = [f for _, f in frames(ev, "orders/buySell/impact")]
step("quote", ask=ask, bid=bid, spread=q["s"], impact=imp[-1]["body"].get("buyImpact") if imp else None)
if imp and (imp[-1]["body"].get("buyImpact") or {}).get("resolution") not in (None, "OK", "ok", ""):
    step("ABORT: the panel says the buy would be refused", resolution=imp[-1]["body"]["buyImpact"].get("resolution")); sys.exit(1)
step("set amount", v=setval("#mat-input-0", OZ))
if not c.js("document.querySelector('#mat-mdc-checkbox-1-input').checked"): c.js("document.querySelector('#mat-mdc-checkbox-1-input').click()"); time.sleep(0.7)
tp, sl = round(ask + TP_D, 2), round(ask - SL_D, 2)
step("set tp/sl", tp=setval("#mat-input-2", f"{tp:.2f}"), sl=setval("#mat-input-3", f"{sl:.2f}"))
time.sleep(1)
step("panel says", text=c.js(r"""(()=>{const t=document.body.innerText; const i=t.indexOf('Take profit / Stop loss'); return t.slice(i,i+260).replace(/\s+/g,' ')})()"""))
# ---- BUY
t_click = time.time()
r = c.js(r"""(()=>{const b=[...document.querySelectorAll('button')].find(x=>/\bBuy\b/.test(x.innerText||'') && x.getBoundingClientRect().x>1700 && x.getBoundingClientRect().y>480 && x.getBoundingClientRect().y<560); if(!b) return 'no buy button'; b.click(); return 'clicked: '+b.innerText.replace(/\s+/g,' ')})()""")
step("click BUY", r=r)
time.sleep(1.2)
ov = overlay(); step("overlay after click", text=ov[:300])
if ov and re.search(r"confirm|buy|place|open", ov, re.I):
    step("confirm", r=click_overlay_button("confirm|^buy|place order|open"))
ev = c.listen(8)
pos = [(ts, f["body"]["data"]) for ts, f in frames(ev, "positions")]
fill = None
for ts, data in pos:
    for d in data:
        if d.get("side") == "BUY" and d.get("symbol") == "XAU/USD":
            fill = (ts, d); break
    if fill: break
if not fill:
    step("NO BUY POSITION SEEN", overlay=overlay()[:300], last_positions=pos[-1][1] if pos else None, impact=[f["body"] for _, f in frames(ev, "orders/buySell/impact")][-1:]);
    Path("rounds").mkdir(exist_ok=True); json.dump(log, open(f"rounds/p0_{int(t_click)}.json", "w"), indent=1); sys.exit(1)
t_fill = time.time() - (8 - 0)  # approximate: use the event ordering below instead
# better timing: the first positions frame with the BUY, relative to listen start
idx = [i for i, e in enumerate(ev) if e["method"] == "Network.webSocketFrameReceived" and '"BUY"' in e["params"]["response"]["payloadData"] and '"positions"' in e["params"]["response"]["payloadData"]]
step("FILLED", position={k: fill[1].get(k) for k in ("id", "side", "qty", "openPrice", "sl", "tp", "upl", "openTime")}, ask_at_click=ask, slippage=round(fill[1].get("openPrice", 0) - ask, 2), latency_s="see frame ts", frame_ts=fill[0], click_ts=t_click)
# ---- CLOSE that position (hedge mode: pick the Buy row)
time.sleep(3)
t_close_click = time.time()
r = c.js(r"""(()=>{const rows=[...document.querySelectorAll('tr,[role=row]')].filter(r=>/XAU\/USD/.test(r.innerText||'') && /\bBuy\b/.test(r.innerText||'')); if(!rows.length) return 'no buy row'; const b=[...rows[0].querySelectorAll('button')].find(x=>/^Close$/.test((x.innerText||'').trim())); if(!b) return 'no close button in row: '+rows[0].innerText.replace(/\s+/g,' ').slice(0,200); b.click(); return 'clicked Close on: '+rows[0].innerText.replace(/\s+/g,' ').slice(0,160)})()""")
step("click CLOSE", r=r)
time.sleep(1.2)
ov = overlay(); step("overlay after close click", text=ov[:300])
if ov and re.search(r"confirm|close", ov, re.I):
    step("confirm close", r=click_overlay_button("confirm|^close"))
ev = c.listen(8)
pos = [(ts, f["body"]["data"]) for ts, f in frames(ev, "positions")]
gone = [ts for ts, data in pos if not any(d.get("side") == "BUY" and d.get("symbol") == "XAU/USD" for d in data)]
met = [f["body"] for _, f in frames(ev, "metrics")]
step("CLOSED" if gone else "BUY STILL OPEN", first_frame_without_buy=gone[0] if gone else None, click_ts=t_close_click, metrics_after={k: met[-1].get(k) for k in ("balance", "equity", "upl")} if met else None)
Path("rounds").mkdir(exist_ok=True); out = f"rounds/p0_{int(t_click)}.json"; json.dump(log, open(out, "w"), indent=1); print("saved", out)
