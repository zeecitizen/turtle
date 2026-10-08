"""One-off patch (2026-10-09): honest Instant-at-Breakout history + Zee's breakout win test.

Applied to the pre-loop turtle.pine. Kept for the record; re-running it on a patched file fails
on purpose (every replacement asserts it matches exactly once).
"""
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "turtle.pine"
s = P.read_text(encoding="utf-8")
NL = "\\n"   # a Pine "\n" inside a string literal


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (old[:80], n)
    s = s.replace(old, new)


# ── 1. settings, appended after the last input so no saved chart value moves ─────────────
i = s.index("\n", s.index("camStrong = input.int(2,"))
s = s[:i + 1] + (
    "scMin   = input.float(1.0, 'Breakout test: a label WINS if price moves our way by at least this much PROFIT after the spread, in $ on 0.1 lots (5 = $5 = a $0.50 move)', minval = 0.0, step = 0.5, group = gTr)\n"
    "scN     = input.int(1, '──── Breakout test window: the rest of the breakout candle (Instant) or nothing (Candle Close) PLUS this many more 1-minute candles', minval = 0, maxval = 30, group = gTr)\n"
) + s[i + 1:]

# ── 2. Instant at Breakout judged only on what is known at the moment of entry ───────────
rep("bool  _bBrkPO    = low  <= _bTrigEff  and (_uIOE ? (uBrkBody ? close > _bTrigEff  : high > _bTrigEff)  : close > _bL + uPBsD)",
    "// INSTANT: fires the moment price trades past the trigger. On history that is \"the high went\n"
    "// above it\" - never the close, which nobody knows at the moment of entry (it would quietly drop\n"
    "// the breakouts that poked through and fell back, i.e. the losers).\n"
    "bool  _bBrkPO    = _uIOE ? high > _bTrigEff : (low <= _bTrigEff and close > _bL + uPBsD)")
rep("bool  _beBrkPO   = high >= _beTrigEff and (_uIOE ? (uBrkBody ? close < _beTrigEff : low  < _beTrigEff) : close < _bL - uPBsD)",
    "bool  _beBrkPO   = _uIOE ? low < _beTrigEff : (high >= _beTrigEff and close < _bL - uPBsD)")
# rules that need the finished breakout candle: skipped on HISTORY in Instant mode (live they see the candle so far)
rep("_uBVOk    = not uBrkVROn or volume <= _uVol * (1.0 - uBrkVR/100.0)",
    "_uBVOk    = not uBrkVROn or (uOE == \"Instant at Breakout\" and not barstate.isrealtime) or volume <= _uVol * (1.0 - uBrkVR/100.0)")
rep("bool _uIOE = uOE == \"Instant at Breakout\"\n",
    "bool _uIOE = uOE == \"Instant at Breakout\"\n"
    "bool _uIOEh = _uIOE and not barstate.isrealtime   // Instant mode on a finished (historical) candle\n"
    "// Instant mode reads the trend from the PREVIOUS candle - it was complete when the breakout began\n"
    "bool _camBx    = _uIOE ? nz(_camB[1])    : _camB\n"
    "bool _camBex   = _uIOE ? nz(_camBe[1])   : _camBe\n"
    "bool _czStrBx  = _uIOE ? nz(_czStrB[1])  : _czStrB\n"
    "bool _czStrBex = _uIOE ? nz(_czStrBe[1]) : _czStrBe\n"
    "bool _uHTFBx   = _uIOE ? nz(_uHTFB[1])   : _uHTFB\n")
rep("(_erULV ? (volume < _uVol or _czStrB) : true)", "(_erULV ? (_uIOEh or volume < _uVol or _czStrBx) : true)")
rep("(_erULV ? (volume < _uVol or _czStrBe) : true)", "(_erULV ? (_uIOEh or volume < _uVol or _czStrBex) : true)")
rep("and not _eTsU and _iGr and _bBrkPO", "and not _eTsU and (_uIOE or _iGr) and _bBrkPO")
rep("and not _eTsU and _iRd and _beBrkPO", "and not _eTsU and (_uIOE or _iRd) and _beBrkPO")
rep("and _strUp and _camB and", "and _strUp and _camBx and")
rep("and _strDn and _camBe and", "and _strDn and _camBex and")
rep("(uHTD == \"Off\" or _uHTFB) and", "(uHTD == \"Off\" or _uHTFBx) and")
rep("(uHTD == \"Off\" or not _uHTFB) and", "(uHTD == \"Off\" or not _uHTFBx) and")
# entry: the trigger, or the open if the candle already opened beyond it
rep("    _entry    = _uIOE ? _bTrigEff : close", "    _entry    = _uIOE ? math.max(open, _bTrigEff) : close")
rep("    _entry      = _uIOE ? _beTrigEff : close", "    _entry      = _uIOE ? math.min(open, _beTrigEff) : close")
# the guard that moved the entry to the candle close used the final close - live only now
rep("    if _uIOE and uIOEGrd > 0 and _tp1 <= close + uSpread * uIOEGrd", "    if _uIOE and barstate.isrealtime and uIOEGrd > 0 and _tp1 <= close + uSpread * uIOEGrd")
rep("    if _uIOE and uIOEGrd > 0 and _tp1 >= close - uSpread * uIOEGrd", "    if _uIOE and barstate.isrealtime and uIOEGrd > 0 and _tp1 >= close - uSpread * uIOEGrd")

# ── 3. the breakout test (scorecard) ──────────────────────────────────────────────────────
rep("var _tPA     = array.new_float() // P&L parallel to _tCTi",
    "var _tPA     = array.new_float() // P&L parallel to _tCTi\n"
    "// BREAKOUT TEST (Zee, 2026-10-09): every BUY/SELL label, judged on the best move our way after entry\n"
    "var _scE = array.new_float()   // entry price\n"
    "var _scB = array.new_int()     // bar_index of the entry candle\n"
    "var _scD = array.new_bool()    // true = BUY\n"
    "var _scT = array.new_int()     // time of the entry candle\n"
    "var _scX = array.new_float()   // best move our way so far (price $), before spread\n"
    "var _scR = array.new_int()     // 1 win, -1 loss, 0 window still open\n"
    "var _scL = array.new_label()   // the label, to print the verdict on it\n"
    "var int _scP = 0               // first signal whose window is still open\n"
    "var int _scFirstT = 0\n"
    "if _scFirstT == 0\n"
    "    _scFirstT := time\n"
    "float _scSigE = na             // data-window export: entry price on the entry candle\n"
    "float _scSigD = na             // data-window export: +1 BUY / -1 SELL")
# record the signal on its entry candle (the deferred block runs when that candle closes)
rep("    _lastSigTxt := _lblTxt\n",
    "    _lastSigTxt := _lblTxt\n"
    "    // Instant: the rest of the entry candle after the entry counts (for a BUY every price at or\n"
    "    // above the trigger in that candle comes after the cross, so its high is after the entry).\n"
    "    // Candle Close: the entry is the close, so the entry candle itself does not count.\n"
    "    array.push(_scE, _uPndEn)\n"
    "    array.push(_scB, bar_index)\n"
    "    array.push(_scD, _dIsBull)\n"
    "    array.push(_scT, time)\n"
    "    array.push(_scX, _uIOE ? (_dIsBull ? high - _uPndEn : _uPndEn - low) : -1e9)\n"
    "    array.push(_scR, 0)\n"
    "    array.push(_scL, label(na))\n"
    "    _scSigE := _uPndEn\n"
    "    _scSigD := _dIsBull ? 1 : -1\n")
for side in ("Bull", "Bear"):
    rep(f"                array.set(_tLbl, array.size(_tLbl) - 1, _uLbl{side})\n",
        f"                array.set(_tLbl, array.size(_tLbl) - 1, _uLbl{side})\n"
        f"                array.set(_scL, array.size(_scL) - 1, _uLbl{side})\n")
# judge: update open windows with each later closed candle, close them after scN more candles
rep("// Deferred UHV label+array creation",
    "// BREAKOUT TEST JUDGE — runs on every closed candle after an entry candle\n"
    "if barstate.isconfirmed\n"
    "    for _j = _scP to array.size(_scB) - 1\n"
    "        if array.size(_scB) == 0 or _j >= array.size(_scB)\n"
    "            break\n"
    "        int _age = bar_index - array.get(_scB, _j)\n"
    "        if _age >= 1 and array.get(_scR, _j) == 0\n"
    "            float _mv = array.get(_scD, _j) ? high - array.get(_scE, _j) : array.get(_scE, _j) - low\n"
    "            array.set(_scX, _j, math.max(array.get(_scX, _j), _mv))\n"
    "    while _scP < array.size(_scB)\n"
    "        if bar_index - array.get(_scB, _scP) < scN\n"
    "            break\n"
    "        float _best = array.get(_scX, _scP)\n"
    "        bool  _won  = _best - uSpread >= scMin / 10.0\n"
    "        array.set(_scR, _scP, _won ? 1 : -1)\n"
    "        label _scLb = array.get(_scL, _scP)\n"
    "        if not na(_scLb)\n"
    "            float _net = _best - uSpread\n"
    "            label.set_text(_scLb, label.get_text(_scLb) + \"" + NL + "\" + (_won ? \"✅ best \" : \"❌ best \") + (_net >= 0 ? \"+\" : \"-\") + str.tostring(math.abs(_net), \"#.##\") + \" ($\" + str.tostring(_net * 10, \"#.#\") + \" on 0.1 lot)\")\n"
    "        _scP += 1\n\n"
    "// Deferred UHV label+array creation")
# a scN of 0 in Instant mode = the entry candle only: judge right away on the entry candle itself
rep("    _scSigD := _dIsBull ? 1 : -1\n",
    "    _scSigD := _dIsBull ? 1 : -1\n"
    "    if scN == 0 and _uIOE\n"
    "        bool _won0 = array.get(_scX, array.size(_scX) - 1) - uSpread >= scMin / 10.0\n"
    "        array.set(_scR, array.size(_scR) - 1, _won0 ? 1 : -1)\n")
# data-window exports for the independent checker
rep("if barstate.islast and sSP",
    "plot(_scSigE, \"test entry\", display = display.data_window)\n"
    "plot(_scSigD, \"test direction\", display = display.data_window)\n\n"
    "if barstate.islast and sSP")

P.write_text(s, encoding="utf-8", newline="")
print("patched")
