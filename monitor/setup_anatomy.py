"""setup_anatomy.py — the live anatomy in Zee's exact reading format.

Zee 2026-08-20: "make all this information readily available on the GUI after
'hunting — no setup yet' in exactly this format so i can read and know OK here's
where we stand right now, also draw this on the humps photo so i know exactly that
we found a UHV, now we're looking for its breakout."

analyze() reads the live terminal's bars (through trend_eyes' rot-proof loader) and
returns both the structured facts and the narrative text. The GUI shows the text;
trend_eyes.draw() overlays the door and trigger on the humps photo.
"""
from __future__ import annotations
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def analyze(bars=None, look=45):
    """bars: trend_eyes rows (t, high, low, close, vol). Returns dict or None."""
    if bars is None:
        import trend_eyes
        bars = trend_eyes.load_bars()
    if len(bars) < look + 5:
        return None
    win = bars[-look:]
    hi_i = max(range(len(win)), key=lambda i: win[i][1])
    lo_i = min(range(len(win)), key=lambda i: win[i][2])
    side = "BUY" if hi_i > lo_i else "SELL"          # the most recent extreme rules
    ext_i = hi_i if side == "BUY" else lo_i
    ext_px = win[ext_i][1] if side == "BUY" else win[ext_i][2]
    ext_t = win[ext_i][0]
    pull = win[ext_i + 1:]                           # everything since the extreme
    if not pull:
        return None
    # counter-candles of the pullback (approx by direction of close vs prior close)
    counters = []
    prev_c = win[ext_i][3]
    for r in pull:
        red = r[3] < prev_c
        if (side == "BUY" and red) or (side == "SELL" and not red):
            counters.append(r)
        prev_c = r[3]
    price = bars[-1][3]
    out = dict(side=side, ext_t=ext_t, ext_px=ext_px, price=price,
               pull_n=len(pull), uhv=None, runner=None, trigger=None)
    if counters:
        by_vol = sorted(counters, key=lambda r: -r[4])
        uhv = by_vol[0]
        out["uhv"] = uhv
        out["runner"] = by_vol[1] if len(by_vol) > 1 else None
        out["trigger"] = uhv[1] if side == "BUY" else uhv[2]   # its high / its low
    return out


def _pkt(t):
    return (t + timedelta(hours=5)).strftime("%H:%M")          # bars are true UTC


def narrative(a=None):
    """The anatomy, in his format. Returns (headline, body) strings."""
    if a is None:
        a = analyze()
    if a is None:
        return ("anatomy unavailable", "not enough bars to read the tape")
    side, price = a["side"], a["price"]
    leg = "Uptrend leg" if side == "BUY" else "Downtrend leg"
    extword = "topped" if side == "BUY" else "bottomed"
    pullword = "reds" if side == "BUY" else "greens"
    lines = [f"{leg}: {extword} {_pkt(a['ext_t'])} PKT at {a['ext_px']:.2f}",
             f"Retracement: {a['pull_n']} bars since — {pullword} pulling "
             f"{'down' if side == 'BUY' else 'up'} · price now {price:.2f}"]
    if a["uhv"] is None:
        lines.append("The UHV: not yet — no counter-candle has printed since the extreme")
        return ("watching a fresh leg — no retracement yet", "\n".join(lines))
    u = a["uhv"]
    crown = f"The UHV crown: the {_pkt(u[0])} candle (vol {int(u[4])})"
    if a["runner"] is not None:
        r = a["runner"]
        crown += f" · runner-up {_pkt(r[0])} (vol {int(r[4])}) — rank-6 auditions both"
    lines.append(crown)
    trig = a["trigger"]
    lines.append(f"The trigger (the door): {trig:.2f} — the UHV's "
                 f"{'high' if side == 'BUY' else 'low'}")
    dist = (trig - price) if side == "BUY" else (price - trig)
    if dist > 0:
        lines.append(f"Why no setup yet: price is {dist:.2f} pts "
                     f"{'below' if side == 'BUY' else 'above'} the trigger — the door "
                     f"is not broken. A setup exists only when a "
                     f"{'green' if side == 'BUY' else 'red'} M1 candle CLOSES its body "
                     f"{'above' if side == 'BUY' else 'below'} {trig:.2f} on volume "
                     f"quieter than {int(u[4])}.")
        head = f"door found at {trig:.2f} — waiting for the break ({dist:.2f} pts away)"
    else:
        lines.append(f"Price is AT the trigger — if the current candle closes "
                     f"through {trig:.2f} quietly, the EA fires within a second.")
        head = f"AT THE DOOR {trig:.2f} — the next close decides"
    lines.append("Next, mechanically: quiet close through the trigger → fire (pulse "
                 "decides the size) · a louder counter-candle → the crown and trigger "
                 "move to it · the pullback never turns → no trade ever exists, and "
                 "that non-trade is the win-rate goal working.")
    return (head, "\n".join(lines))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    h, b = narrative()
    print("=== " + h + " ===")
    print(b)
