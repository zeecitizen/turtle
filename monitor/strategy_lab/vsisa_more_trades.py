"""vsisa_more_trades.py - the "find more trades" court (Zee, 2026-10-09: "let's aggressively
find more trades"). Same VSISA, same window, Axi real ticks, random delay, $25k, fixed lots.
Arms: other symbols, other timeframes, the looser fade. Results append to vsisa_more_trades.jsonl.

    py vsisa_more_trades.py ARM [ARM ...]      (ARM names below; 'all' runs every arm)
"""
import json, sys
from pathlib import Path
import axi_rig

OUT = Path(__file__).with_name("vsisa_more_trades.jsonl")

# scale = market's avg M5 range / gold's (453.9 pts); lots set so one average M5 candle is
# worth the same dollars as gold at 0.28 lots (~$127). Measured by probe_ranges.py, 2026-10-09.
# Spread as % of an average candle: gold 2.8, US30 3.4, USTECH 3.2, US500 6.7, GER40 6.3,
# BTC 8.1, GBPUSD 10.5, USDJPY 10.6, USOIL 15.4, XAGUSD 25, XPTUSD >100 (last two not tested).
def mk(sym, per, scale, lots, **extra):
    d = {"InpPtsScale": f"{scale:.3f}", "InpLots": f"{lots:.2f}"}
    d.update({k: str(v) for k, v in extra.items()})
    return (sym, per, d)

ARMS = {
    # gold baseline must reproduce Zee's fixed-lot run (~+$16-17k, 163 trades)
    "gold_m5":      ("XAUUSD.pro", "M5", {}),
    "gold_m15":     mk("XAUUSD.pro", "M15", 1.73, 0.28),   # sqrt(3) wider candles
    "gold_m1":      mk("XAUUSD.pro", "M1", 0.45, 0.28),    # ~1/sqrt(5) candles
    "gold_fade65":  ("XAUUSD.pro", "M5", {"InpFadePct": "0.65", "InpFadeLook": "5"}),
    # the fade neighbourhood: is 0.65/look5 a ridge or a spike?
    **{f"fade{int(p*100)}_l{l}": ("XAUUSD.pro", "M5", {"InpFadePct": f"{p:.2f}", "InpFadeLook": str(l)})
       for p in (0.60, 0.65, 0.70, 0.75) for l in (4, 5, 6) if (p, l) not in ((0.60, 4), (0.65, 5))},
    # fade 0.65/5 with the fake-break sweep lifted, and with a wider sweep window
    "fade65_nofake":  ("XAUUSD.pro", "M5", {"InpFadePct": "0.65", "InpFadeLook": "5", "InpFakeBreak": "false"}),
    "fade65_sweep50": ("XAUUSD.pro", "M5", {"InpFadePct": "0.65", "InpFadeLook": "5", "InpSweepLook": "50"}),
    "fade65_sweep20": ("XAUUSD.pro", "M5", {"InpFadePct": "0.65", "InpFadeLook": "5", "InpSweepLook": "20"}),
    "us30_m5":     mk("US30", "M5", 6.473, 4.33),
    "ustech_m5":    mk("USTECH", "M5", 4.983, 5.62),
    "us500_m5":     mk("US500", "M5", 0.965, 29.0),
    "ger40_m5":     mk("GER40", "M5", 4.078, 6.12),
    "btc_m5":       mk("BTCUSD", "M5", 32.66, 0.85),
    "gbpusd_m5":    mk("GBPUSD.pro", "M5", 0.1005, 2.78),
    "usdjpy_m5":    mk("USDJPY.pro", "M5", 0.1333, 3.33),
    "usoil_m5":     mk("USOIL", "M5", 0.3232, 86.0),
}

if __name__ == "__main__":
    names = list(ARMS) if sys.argv[1:] == ["all"] else sys.argv[1:]
    axi_rig.compile_ea("VSISA")
    for n in names:
        sym, per, sets = ARMS[n]
        r = axi_rig.run("VSISA", sym, per, sets, tag=f"vsisa_{n}")
        r["arm"] = n
        with OUT.open("a") as f:
            f.write(json.dumps(r) + "\n")
        print(n, r.get("net"), r.get("trades"), r.get("pf"), r.get("dd"), r.get("error", ""),
              flush=True)
