"""One-off patch (2026-10-09): Instant at Breakout fires from a trigger ARMED at the previous close.

History used to update the setup with the finished breakout candle (a failed, loud breakout
candle became the new UHV and erased its own signal) BEFORE checking the breakout. Live, the
trade is already open by then. Now, in Instant mode:
  * at each candle's close the setup is "armed": every rule that does not depend on the
    breakout candle, judged on finished candles, and the trigger price;
  * on the next candle the signal fires if it was armed and price passes the armed trigger.
Candle Close mode is unchanged.
"""
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "turtle.pine"
s = P.read_text(encoding="utf-8")


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:80], s.count(old))
    s = s.replace(old, new)


def armed_from(line, side):
    expr = line.split(" = ", 1)[1]
    if side == "bull":
        cuts = [(" and (_erULV ? (_uIOEh or volume < _uVol or _czStrBx) : true)", ""),
                (" and (_uIOE or _iGr) and _bBrkPO", ""),
                (" and _camBx", " and _camB"),
                ("(uHTD == \"Off\" or _uHTFBx)", "(uHTD == \"Off\" or _uHTFB)"),
                (" and _uMomBOk and _uBVOk and _uPBMok and _uVelOk", ""),
                (" and (_uIOE or barstate.isconfirmed)", ""),
                ("(bar_index - _luSB) >= _euCd", "(bar_index + 1 - _luSB) >= _euCd"),
                ("(bar_index - _uBar) >= uSB", "(bar_index + 1 - _uBar) >= uSB")]
    else:
        cuts = [(" and (_erULV ? (_uIOEh or volume < _uVol or _czStrBex) : true)", ""),
                (" and (_uIOE or _iRd) and _beBrkPO", ""),
                (" and _camBex", " and _camBe"),
                ("(uHTD == \"Off\" or not _uHTFBx)", "(uHTD == \"Off\" or not _uHTFB)"),
                (" and _uMomBeOk and _uBVOk and _uPBMbok and _uVelOk", ""),
                (" and (_uIOE or barstate.isconfirmed)", ""),
                ("(bar_index - _luSB) >= _euCd", "(bar_index + 1 - _luSB) >= _euCd"),
                ("(bar_index - _uBar) >= uSB", "(bar_index + 1 - _uBar) >= uSB")]
    for a, b in cuts:
        assert expr.count(a) == 1, (side, a, expr.count(a))
        expr = expr.replace(a, b)
    return expr


lines = s.split("\n")
ib = next(i for i, l in enumerate(lines) if l.startswith("_bBrk = "))
ie = next(i for i, l in enumerate(lines) if l.startswith("_beBrk = "))
bull_arm, bear_arm = armed_from(lines[ib], "bull"), armed_from(lines[ie], "bear")
orig_b, orig_e = lines[ib].split(" = ", 1)[1], lines[ie].split(" = ", 1)[1]
lines[ib] = ("// Instant mode: armed at the previous close, fires when price passes the armed trigger\n"
             "_armB  = " + bull_arm + "\n"
             "_armTB = _bTrigEff\n"
             "_bBrk = _uIOE ? (nz(_armB[1]) and not _uF and high > nz(_armTB[1]) and _uMomBOk and _uBVOk and _uVelOk and (bar_index - _luSB) >= _euCd) : (" + orig_b + ")")
lines[ie] = ("_armE  = " + bear_arm + "\n"
             "_armTE = _beTrigEff\n"
             "_beBrk = _uIOE ? (nz(_armE[1]) and not _uF and low < nz(_armTE[1]) and _uMomBeOk and _uBVOk and _uVelOk and (bar_index - _luSB) >= _euCd) : (" + orig_e + ")")
s = "\n".join(lines)
rep("    _entry    = _uIOE ? math.max(open, _bTrigEff) : close", "    _entry    = _uIOE ? math.max(open, nz(_armTB[1])) : close")
rep("    _entry      = _uIOE ? math.min(open, _beTrigEff) : close", "    _entry      = _uIOE ? math.min(open, nz(_armTE[1])) : close")
P.write_text(s, encoding="utf-8", newline="")
print("armed trigger patched")
