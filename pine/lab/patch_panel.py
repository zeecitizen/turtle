"""One-off patch (2026-10-09): fix the pre-loop stats panel and put the breakout test at its top."""
import re
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "turtle.pine"
s = P.read_text(encoding="utf-8")
NL = "\\n"


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (old[:90], n)
    s = s.replace(old, new)


a = s.index("fDP() =>")
b = s.index("plot(_scSigE")
f = s[a:b]


def frep(old, new, count=1):
    global f
    n = f.count(old)
    assert n == count, (old[:90], n)
    f = f.replace(old, new)


# 1. one "today": midnight Pakistan time, for every today-number on the panel
frep("    _todayStartMs         = timenow - (timenow % 86400000)\n",
     "    _todayStartMs         = timestamp(\"Asia/Karachi\", year(timenow, \"Asia/Karachi\"), month(timenow, \"Asia/Karachi\"), dayofmonth(timenow, \"Asia/Karachi\"), 0, 0)\n"
     "    _simPnLToday          = 0.0   // simulated P&L of trades closed today (same day boundary as the counts)\n")
frep("                _tradesCompletedToday += 1\n",
     "                _tradesCompletedToday += 1\n"
     "                _simPnLToday += array.get(_tPA, _ict)\n")
frep("    _bestPnL      = _liveClosedToday > 0 ? _livePnLToday : _uPT\n",
     "    _bestPnL      = _liveClosedToday > 0 ? _livePnLToday : _simPnLToday\n")
# 2. one way of counting wins everywhere: a trade wins if it made money, everything else is a loss
frep("                else if _p < 0\n", "                else\n")
# 3. alerts no longer exist
frep("         str.tostring(_sigT) + \" labels  |  \" + str.tostring(_alT) + \" alerts\" + (_gated > 0 ? \"  |  ⚠️ \" + str.tostring(_gated) + \" gated\" : \"\") +\n",
     "         str.tostring(_sigT) + \" labels today\" +\n")
frep("         \"" + NL + "Labels/hr: \" + str.tostring(math.round(_trueNextHrSigs * 10) / 10) + \"  |  Alerts/hr: \" + str.tostring(math.round(_trueAlHrSigs * 10) / 10) + \"  (\" + _alBasisLbl + \")\" +\n",
     "         \"" + NL + "Labels/hr: \" + str.tostring(math.round(_trueNextHrSigs * 10) / 10) +\n")
# 4. header: what the panel is computed on
frep("         \"TURTLE TRADER DESK  |  \" + syminfo.ticker + \"  |  \" + str.tostring(tFm) + \"m  |  \" + _session + \"  |  Exness Std \" + str.tostring(uLev) + \":1\" + _integrityStr,\n",
     "         \"TURTLE TRADER DESK  |  \" + syminfo.ticker + \"  |  \" + str.tostring(tFm) + \"m  |  \" + _session +\n"
     "         \"" + NL + "history: \" + str.format_time(_scFirstT, \"yyyy-MM-dd HH:mm\", \"Asia/Karachi\") + \" PKT → now  (\" + str.tostring(bar_index + 1) + \" candles)\",\n")
# 5. trend row: the camel decides the trend now, not the old moving-average engine
frep("    _tDir       = _lb ? \"BULLISH\" : \"BEARISH\"\n    _tColor     = _lb ? _txtGreen : _txtRed\n",
     "    _tDir       = _czTr == 1 ? \"🐪 UPTREND — buys only\" : _czTr == -1 ? \"🐪 DOWNTREND — sells only\" : \"🐪 NO TREND — no trades\"\n"
     "    _tColor     = _czTr == 1 ? _txtGreen : _czTr == -1 ? _txtRed : _txtDim\n")
frep("         _tDir + \"  |  \" + _tBar + \"  \" + _tStL + \" (\" + str.tostring(_tS) + \")\" +\n",
     "         _tDir + (_czStk != 0 ? \"  (\" + str.tostring(math.abs(_czStk)) + \" hump\" + (math.abs(_czStk) > 1 ? \"s\" : \"\") + \" in a row\" + ((camStrong > 0 and math.abs(_czStk) >= camStrong) ? \", strong\" : \"\") + \")\" : \"\") +\n")

# 6. breakout test rows at the top: shift every row from 2 down by 3, add rows 2-4
f = re.sub(r"table\.cell\(statsPanel, 0, (\d+),",
           lambda m: f"table.cell(statsPanel, 0, {int(m.group(1)) + 3 if int(m.group(1)) >= 2 else m.group(1)},", f)
frep("    table statsPanel = table.new(position.bottom_right, 1, 16,",
     "    table statsPanel = table.new(position.bottom_right, 1, 19,")
test_rows = '''
    // BREAKOUT TEST (Zee's win definition) — rows 2-4
    int _sN = 0
    int _sW = 0
    int _bN = 0
    int _bW = 0
    int _eN = 0
    int _eW = 0
    int _tdN = 0
    int _tdW = 0
    float _sBest = 0.0
    for _i = 0 to math.max(array.size(_scR) - 1, 0)
        if array.size(_scR) == 0
            break
        int _r = array.get(_scR, _i)
        if _r != 0
            _sN += 1
            _sW += _r == 1 ? 1 : 0
            _sBest += array.get(_scX, _i) - uSpread
            if array.get(_scD, _i)
                _bN += 1
                _bW += _r == 1 ? 1 : 0
            else
                _eN += 1
                _eW += _r == 1 ? 1 : 0
            if array.get(_scT, _i) >= _todayStartMs
                _tdN += 1
                _tdW += _r == 1 ? 1 : 0
    int _hN = int(_sN / 2)
    int _oN = 0
    int _oW = 0
    int _k = 0
    for _i = 0 to math.max(array.size(_scR) - 1, 0)
        if array.size(_scR) == 0
            break
        int _r = array.get(_scR, _i)
        if _r != 0
            if _k < _hN
                _oN += 1
                _oW += _r == 1 ? 1 : 0
            _k += 1
    string _win = uOE == "Instant at Breakout" ? "rest of the breakout candle" + (scN > 0 ? " + " + str.tostring(scN) + " min" : "") : "the next " + str.tostring(scN) + " min"
    table.cell(statsPanel, 0, 2, "BREAKOUT TEST — a label WINS if price moved our way by $" + str.tostring(scMin, "#.##") + "+ profit on 0.1 lot (after $" + str.tostring(uSpread, "#.##") + " spread) within the " + _win + "  |  entry: " + (uOE == "Instant at Breakout" ? "instant, at the trigger" : "breakout candle close"),
         text_color = _txtDim, text_size = size.tiny, bgcolor = color.new(color.black, 5))
    float _wrp = _sN > 0 ? _sW * 100.0 / _sN : 0.0
    table.cell(statsPanel, 0, 3, str.tostring(_sW) + " / " + str.tostring(_sN) + " labels won  =  " + fPct(_sW, _sN),
         text_color = _wrp >= 90 ? _txtGreen : _wrp >= 60 ? _txtYellow : _txtOrange, text_size = size.large, bgcolor = color.new(color.navy, 40))
    table.cell(statsPanel, 0, 4, "BUY " + str.tostring(_bW) + "/" + str.tostring(_bN) + " (" + fPct(_bW, _bN) + ")   SELL " + str.tostring(_eW) + "/" + str.tostring(_eN) + " (" + fPct(_eW, _eN) + ")   today " + str.tostring(_tdW) + "/" + str.tostring(_tdN) + " (" + fPct(_tdW, _tdN) + ")" +
         "NLolder half " + fPct(_oW, _oN) + "  |  newer half " + fPct(_sW - _oW, _sN - _oN) + "  |  avg best move after spread: $" + str.tostring(_sN > 0 ? _sBest / _sN : 0.0, "#.##") + " ($" + str.tostring(_sN > 0 ? _sBest / _sN * 10 : 0.0, "#.#") + " on 0.1 lot)",
         text_color = color.white, text_size = size.small, bgcolor = _bgDark)
'''.replace("NL", NL)
anchor = "    // ROW 0 — HEADER\n"
assert f.count(anchor) == 1
f = f.replace(anchor, test_rows + anchor)
f = "fPct(int _w, int _n) => _n > 0 ? str.tostring(math.round(_w * 100.0 / _n)) + \"%\" : \"—\"\n\n" + f
s = s[:a] + f + s[b:]
P.write_text(s, encoding="utf-8", newline="")
print("panel patched")
