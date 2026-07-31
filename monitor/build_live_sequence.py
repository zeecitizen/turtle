"""build_live_sequence.py — LIVE trade-sequence view (setup steps) for the dashboard.

Renders the most recent OANDA fast-scalp setup as a step-by-step sequence:
  1 Trend  ->  2 Retracement (RET)  ->  3 UHV (vol)  ->  4 Breakout (BRKT)
  ->  5 Signal (side/entry/strength/lot)  ->  6 Outcome
so Zee can watch a trade form live. Writes:
  - setup_labels/sequence.html   (self-contained, served on :8765)
  - <dashboard>/live_sequence.json (compact state the home dashboard can also read)
Run --loop to keep it live (page auto-refreshes 15s).
"""
from __future__ import annotations
import argparse, csv, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import build_entry_review_m5 as B
from case_engine import extract_features
from setup_strength import strength, lot_for

OUT = Path(__file__).parent / "setup_labels"
DASH_JSON = Path(__file__).parent.parent / "dashboard" / "claude_trader" / "live_sequence.json"
CF = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/oanda_m1.csv")
FILLS = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/caseexec_fills.csv")


def real_fill(side, entry):
    """The EA logs REAL fills to caseexec_fills.csv: time,side,entry,exit,lots,pts,usd,reason.
    OANDA (detector) and MT5 (broker) prices differ, so exact entry-matching is unreliable;
    we show the MOST RECENT real EA trade of the SAME SIDE as the live outcome."""
    if not FILLS.exists(): return None
    last = None
    try:
        for r in csv.reader(FILLS.open(encoding="utf-8", errors="ignore")):
            if len(r) < 8 or r[1] != side: continue
            try: usd = float(r[6]); lots = float(r[4])
            except Exception: continue
            last = (usd, r[7], lots)   # most recent same-side fill
    except Exception:
        return None
    return last
TZ = 2   # Munich display
CFG = dict(UHV_BODY_MIN=0.0, MIN_ORIGIN_BREAK=0.0, ER_MIN=0.0, TREND_MIN_HUMP=0.5, TREND_DOM=1.2)  # TREND FILTER ON (Zee: "selling in an uptrend" caused all 3 big losses)
EXIT = dict(arm=0.3, give=0.2, tp=3.0, cap=3.0)

HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15"><title>Live Trade Sequence</title><style>
body{font-family:system-ui,Segoe UI,Arial;margin:0;background:#0b0f14;color:#e6edf3}
.wrap{max-width:820px;margin:0 auto;padding:16px}
h1{font-size:18px;margin:0 0 4px}.sub{color:#8b97a3;font-size:12px;margin-bottom:14px}
.hd{background:#111826;border:1px solid #223;border-radius:12px;padding:14px 16px;margin-bottom:14px}
.hd .big{font-size:20px;font-weight:700}.pos{color:#4ade80}.neg{color:#f87171}.pend{color:#fbbf24}
.buy{color:#4ade80}.sell{color:#f87171}
.steps{list-style:none;padding:0;margin:0}
.step{display:flex;gap:12px;padding:11px 0;border-bottom:1px solid #1c2733}
.num{flex:0 0 30px;height:30px;border-radius:50%;background:#1d2733;color:#7dd3fc;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:14px}
.num.done{background:#14532d;color:#4ade80}.num.now{background:#0369a1;color:#fff;animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.body{flex:1}.body .t{font-weight:600;font-size:15px}.body .d{color:#9aa7b4;font-size:13px;margin-top:2px}
.chart{margin-top:14px}.chart img{width:100%;border-radius:10px;background:#fff;display:block}
.empty{color:#8b97a3;padding:20px}
</style></head><body><div class="wrap">
<h1>🎬 Live Trade Sequence — XAUUSD (OANDA)</h1><div class="sub">__SUB__</div>
__BODY__
</div></body></html>"""


def load_bars():
    bars = []
    if not CF.exists(): return bars
    with CF.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromtimestamp(int(r["time_unix"]), tz=timezone.utc).replace(tzinfo=None)
            bars.append(B.Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"])))
    bars.sort(key=lambda b: b.t)
    return bars


def outcome(bars, i, side, entry):
    if i + 2 >= len(bars): return None, "forming"
    peak = 0.0
    for k in range(i + 1, min(i + 60, len(bars))):
        bb = bars[k]; favx = (entry - bb.l) if side == "SELL" else (bb.h - entry); peak = max(peak, favx)
        advc = (bb.c - entry) if side == "SELL" else (entry - bb.c)
        if favx >= EXIT["tp"]: return EXIT["tp"], "hit target"
        if advc >= EXIT["cap"]: return -EXIT["cap"], "hit stop"
        favc = (entry - bb.c) if side == "SELL" else (bb.c - entry)
        if peak >= EXIT["arm"] and (peak - favc) >= EXIT["give"]: return peak - EXIT["give"], "harvested"
    if i + 60 >= len(bars): return None, "running"
    bb = bars[min(i + 60, len(bars)) - 1]
    return ((entry - bb.c) if side == "SELL" else (bb.c - entry)), "closed"


def hm(t): return f"{(t.hour + TZ) % 24:02d}:{t.minute:02d}"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--loop", type=int, default=0); args = ap.parse_args()
    for k, v in CFG.items(): setattr(B, k, v)
    while True:
        bars = load_bars()
        body = '<div class="empty">Abhi koi live setup nahi. Naye bante hi yahan step-by-step dikhega.</div>'
        state = {"status": "idle"}
        if len(bars) > 30:
            tmap = {b.t: i for i, b in enumerate(bars)}
            setups = B.detect_full(bars)
            if setups:
                s = setups[-1]
                f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
                st = strength(f); lots, tier = lot_for(st)
                bi = tmap.get(s["open_t"]); usd, how = outcome(bars, bi, s["side"], s["entry"]) if bi is not None else (None, "forming")
                sidecls = "buy" if s["side"] == "BUY" else "sell"
                rf = real_fill(s["side"], s["entry"])
                if rf is not None:
                    r_usd, r_reason, r_lots = rf
                    ocls_pos = "pos" if r_usd >= 0 else "neg"
                    outc = f'<span class="{ocls_pos}">${r_usd:+.1f} REAL ({r_reason}, {r_lots} lot)</span>'; onum = "✓"; ocls = "done"
                    usd = r_usd / max(lots, 0.01) / 100   # for state json consistency
                elif usd is None:
                    outc = f'<span class="pend">⏳ {how}…</span>'; onum = "6"; ocls = "now"
                else:
                    ocls_pos = "pos" if usd >= 0 else "neg"
                    outc = f'<span class="{ocls_pos}">${usd * lots * 100:+.1f} <span style="color:#8b97a3">~ theoretical (sim, no spread)</span> ({how})</span>'; onum = "✓"; ocls = "done"
                png = OUT / "sequence.png"
                render_ok = B.render(dict(s), bars, png)
                up, dn = B.local_hump(bars, s["o"], s["side"])
                # trade phase: resolved (real fill exists) vs still live
                resolved = rf is not None
                out_cls = "done" if resolved else "now"
                NOW = ' <span style="color:#38bdf8;font-weight:700;">● LIVE — you are here</span>'
                steps = [
                    ("1", "done", "Trend", f"{'Uptrend' if s['side']=='BUY' else 'Downtrend'} — hump {max(up,dn):.1f}pt", ""),
                    ("2", "done", "Retracement started (RET)", f"{hm(bars[s['o']].t)} — counter-trend origin", ""),
                    ("3", "done", f"UHV found — vol {bars[s['u']].v}", f"{hm(bars[s['u']].t)} — highest-volume candle", ""),
                    ("4", "done", "Breakout (BRKT)", f"{hm(bars[s['i']].t)} — {'green' if s['side']=='BUY' else 'red'} body crosses UHV", ""),
                    ("5", "done", f"Signal — {s['side']} @ {s['entry']:.2f}", f"💪 {tier} · {lots} lot · strength {st:.2f}", ""),
                    (("✓" if resolved else "6"), out_cls, "Outcome", outc, NOW),
                ]
                li = "".join(
                    f'<li class="step"><div class="num {c}">{n}</div>'
                    f'<div class="body"><div class="t">{t}{marker}</div><div class="d">{d}</div></div></li>'
                    for (n, c, t, d, marker) in steps)
                hd = (f'<div class="hd"><div class="big"><span class="{sidecls}">{s["side"]}</span> '
                      f'@ {s["entry"]:.2f} &nbsp;·&nbsp; {tier} ({lots} lot)</div>'
                      f'<div class="sub">setup @ {hm(s["open_t"])} Munich · strength {st:.2f} · {outc}</div></div>')
                chart = f'<div class="chart"><img src="sequence.png?v={int(time.time())}"></div>' if render_ok else ""
                body = hd + f'<ul class="steps">{li}</ul>' + chart
                state = {"status": "active", "side": s["side"], "entry": round(s["entry"], 2),
                         "tier": tier, "lots": lots, "strength": round(st, 2),
                         "ret": hm(bars[s["o"]].t), "uhv_vol": bars[s["u"]].v, "uhv": hm(bars[s["u"]].t),
                         "brkt": hm(bars[s["i"]].t), "outcome": how,
                         "usd": (round(usd * lots * 100, 1) if usd is not None else None),
                         "updated": datetime.now().strftime("%H:%M")}
        sub = f"OANDA fast-scalp · updated {datetime.now().strftime('%H:%M')} · auto-refresh 15s"
        (OUT / "sequence.html").write_text(HTML.replace("__BODY__", body).replace("__SUB__", sub), encoding="utf-8")
        try: DASH_JSON.write_text(json.dumps(state), encoding="utf-8")
        except Exception: pass
        print(f"sequence.html updated ({state.get('status')})")
        if args.loop <= 0: break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
