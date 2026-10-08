"""One-off patch (2026-10-09): random-entry baseline for the breakout test, shown on the panel.

Every candle is also treated as a pretend entry, BUY and SELL, at its open (Instant) or close
(Candle Close), and judged by exactly the same rule. The panel shows that rate next to ours,
so a setting that only raises the win rate because the test got easier is visible at once.
"""
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "turtle.pine"
s = P.read_text(encoding="utf-8")
NL = "\\n"


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:80], s.count(old))
    s = s.replace(old, new)


rep("// BREAKOUT TEST JUDGE — runs on every closed candle after an entry candle\n",
    "// RANDOM BASELINE — every candle as a pretend BUY and SELL, judged by the same rule. Its window\n"
    "// closes now if it started scN candles ago: Instant enters at that candle's open and sees that\n"
    "// whole candle + scN more; Candle Close enters at its close and sees the next scN candles.\n"
    "var int _rbN = 0\n"
    "var int _rbW = 0\n"
    "float _rbHi = ta.highest(high, scN + 1)\n"
    "float _rbLo = ta.lowest(low, scN + 1)\n"
    "float _rbHi2 = scN > 0 ? ta.highest(high, math.max(scN, 1)) : na\n"
    "float _rbLo2 = scN > 0 ? ta.lowest(low, math.max(scN, 1)) : na\n"
    "if barstate.isconfirmed and bar_index > scN + 1\n"
    "    float _rbE = uOE == \"Instant at Breakout\" ? open[scN] : close[scN]\n"
    "    float _rbUp = uOE == \"Instant at Breakout\" ? _rbHi - _rbE : _rbHi2 - _rbE\n"
    "    float _rbDn = uOE == \"Instant at Breakout\" ? _rbE - _rbLo : _rbE - _rbLo2\n"
    "    if not na(_rbUp) and not na(_rbDn)\n"
    "        _rbN += 2\n"
    "        _rbW += (_rbUp - uSpread >= scMin / 10.0 ? 1 : 0) + (_rbDn - uSpread >= scMin / 10.0 ? 1 : 0)\n\n"
    "// BREAKOUT TEST JUDGE — runs on every closed candle after an entry candle\n")
rep("\"" + NL + "older half \" + fPct(_oW, _oN)",
    "\"" + NL + "a random entry scores \" + fPct(_rbW, _rbN) + \" on this same test  →  edge \" + (_sN > 0 and _rbN > 0 ? ((_sW * 100.0 / _sN - _rbW * 100.0 / _rbN) >= 0 ? \"+\" : \"\") + str.tostring(_sW * 100.0 / _sN - _rbW * 100.0 / _rbN, \"#.#\") + \" pts\" : \"—\") +\n"
    "         \"" + NL + "older half \" + fPct(_oW, _oN)")
P.write_text(s, encoding="utf-8", newline="")
print("baseline patched")
