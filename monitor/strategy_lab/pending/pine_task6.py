"""Task 6: the EXIT LAB as its own sorted panel (bottom left) with drawdown + vs-now, and the EXIT · quick pick setting."""
from pathlib import Path
p = Path(r"C:\Users\zeesh\turtle\pine\saad_15min.pine"); t = p.read_text(encoding="utf-8")
def rep(o, n, c=1):
    global t
    assert t.count(o) == c, (o[:80], t.count(o)); t = t.replace(o, n)

PICKS = ['Off - use the TP1 METHOD and AFTER TP1 settings below', 'Normal: EMA touch (BUY) / last swing low (SELL)',
         'Fixed target +$1 (close all)', 'Fixed target +$2 (close all)', 'Fixed target +$3 (close all)', 'Fixed target +$5 (close all)',
         'Fibonacci 161.8% of the setup candle (close all)', 'Fibonacci 200% of the setup candle (close all)', 'Partial: half at +$2, the rest trails $2']
opts = ", ".join(f'"{x}"' for x in PICKS)

# 1. the quick pick, LAST among the inputs (no setting moves)
rep('''reBars = input.int(60, "...re-arm window: candles after the stop-out", minval = 1, group = GSL, tooltip = "EA: InpReEntryBars.", display = display.none)
''', f'''reBars = input.int(60, "...re-arm window: candles after the stop-out", minval = 1, group = GSL, tooltip = "EA: InpReEntryBars.", display = display.none)
// Zee 2026-10-18 (Task 6): "simplify exit settings on the indicator so one can easily try them one by one". One click picks a whole exit;
// it overrides the TP1 METHOD (+ its $ / Fibonacci / partial values) and the AFTER TP1 share. The EXIT LAB marks these rows with a star.
xPick = input.string("{PICKS[0]}", "EXIT · quick pick (one click = a whole exit; overrides the TP1 METHOD and the AFTER TP1 share)", options = [{opts}], group = GTP,
     tooltip = "Try them one by one and compare with the EXIT LAB panel (bottom left; the starred rows). Fixed / Fibonacci close the whole trade at the target; Partial closes half at +$2 and trails the rest $2. EA: InpExitPreset (same numbers), so every pick can be tested in MT5.", display = display.none)
''')

# 2. the settings in force
rep('''// TP1 METHOD (Zee 2026-10-16): the Partial method brings its own share and trail
xPart = tpMode == "Partial: close a share at a fixed $ target, trail the rest" ? tpPart : iPartial
xTrL = tpMode == "Partial: close a share at a fixed $ target, trail the rest" ? tpPartTr : iLTrail
xTrS = tpMode == "Partial: close a share at a fixed $ target, trail the rest" ? tpPartTr : iSTrail''',
f'''// EXIT · quick pick (Task 6): the TP settings in force - the inputs, or the picked exit (EA: InpExitPreset, same mapping)
pickN = xPick == "{PICKS[1]}" ? 1 : xPick == "{PICKS[2]}" ? 2 : xPick == "{PICKS[3]}" ? 3 : xPick == "{PICKS[4]}" ? 4 : xPick == "{PICKS[5]}" ? 5 : xPick == "{PICKS[6]}" ? 6 : xPick == "{PICKS[7]}" ? 7 : xPick == "{PICKS[8]}" ? 8 : 0
eTpMode = pickN == 1 ? "Normal: BUY = touch of the other EMA · SELL = last swing low" : pickN >= 2 and pickN <= 5 ? "Fixed $ target" : pickN == 6 or pickN == 7 ? "Fibonacci extension of the setup candle" : pickN == 8 ? "Partial: close a share at a fixed $ target, trail the rest" : tpMode
eFixB = pickN >= 2 and pickN <= 5 ? array.get(array.from(1.0, 2.0, 3.0, 5.0), pickN - 2) : pickN == 8 ? 2.0 : tpFixB
eFixS = pickN >= 2 and pickN <= 5 ? array.get(array.from(1.0, 2.0, 3.0, 5.0), pickN - 2) : pickN == 8 ? 2.0 : tpFixS
eTpFib = pickN == 6 ? 161.8 : pickN == 7 ? 200.0 : tpFib
eTpPart = pickN == 8 ? 0.5 : tpPart
eTpPartTr = pickN == 8 ? 2.0 : tpPartTr
ePartial = pickN >= 2 and pickN <= 7 ? 1.0 : iPartial
// the EXIT LAB row of the pick (1-4 fixed, 14-15 Fibonacci, 17 partial), -1 none
pickRow = pickN >= 2 and pickN <= 5 ? pickN - 1 : pickN == 6 ? 14 : pickN == 7 ? 15 : pickN == 8 ? 17 : -1
isPickable(int m) => m == 1 or m == 2 or m == 3 or m == 4 or m == 14 or m == 15 or m == 17
// TP1 METHOD (Zee 2026-10-16): the Partial method brings its own share and trail
xPart = eTpMode == "Partial: close a share at a fixed $ target, trail the rest" ? eTpPart : ePartial
xTrL = eTpMode == "Partial: close a share at a fixed $ target, trail the rest" ? eTpPartTr : iLTrail
xTrS = eTpMode == "Partial: close a share at a fixed $ target, trail the rest" ? eTpPartTr : iSTrail''')

# 3. every later use of the TP settings -> the ones in force
head, tail = t.split("xTrS = eTpMode ==", 1)
import re
for a, b in (("tpMode", "eTpMode"), ("tpFib", "eTpFib"), ("tpFixB", "eFixB"), ("tpFixS", "eFixS")):
    tail = re.sub(rf"(?<![\w.]){a}(?!\w)", b, tail)
t = head + "xTrS = eTpMode ==" + tail

# 4. drawdown per row + BUY / SELL / both (60 cells: m, m + XM, m + 2 XM)
rep('''var array<int>   xN = array.new<int>(40, 0)     // this month: row m BUY = m, SELL = m + 20
var array<int>   xW = array.new<int>(40, 0)
var array<float> xP = array.new<float>(40, 0.0)''', '''var array<int>   xN = array.new<int>(60, 0)     // this month: row m BUY = m, SELL = m + 20, both = m + 40 (Task 6)
var array<int>   xW = array.new<int>(60, 0)
var array<float> xP = array.new<float>(60, 0.0)
var array<float> xEq = array.new<float>(60, 0.0)  // Task 6: running net, its peak and the worst drop from a peak (max drawdown)
var array<float> xPk = array.new<float>(60, 0.0)
var array<float> xDD = array.new<float>(60, 0.0)
xAdd1(int k, float pnl) =>
    array.set(xN, k, array.get(xN, k) + 1)
    array.set(xP, k, array.get(xP, k) + pnl)
    if pnl > 0
        array.set(xW, k, array.get(xW, k) + 1)
    float eq = array.get(xEq, k) + pnl
    array.set(xEq, k, eq)
    array.set(xPk, k, math.max(array.get(xPk, k), eq))
    array.set(xDD, k, math.max(array.get(xDD, k), array.get(xPk, k) - eq))
xAdd(int m, int s, float pnl) =>
    xAdd1(m + (s > 0 ? 0 : XM), pnl)
    xAdd1(m + 2 * XM, pnl)''')
rep('''    array.fill(xN, 0), array.fill(xW, 0), array.fill(xP, 0.0)''', '''    array.fill(xN, 0), array.fill(xW, 0), array.fill(xP, 0.0), array.fill(xEq, 0.0), array.fill(xPk, 0.0), array.fill(xDD, 0.0)''')
rep('''        int xk = sSide > 0 ? 0 : XM            // EXIT LAB row 0 = the real exits
        array.set(xN, xk, array.get(xN, xk) + 1), array.set(xP, xk, array.get(xP, xk) + pnl)
        if pnl > 0
            array.set(xW, xk, array.get(xW, xk) + 1)''', '''        xAdd(0, sSide, pnl)                     // EXIT LAB row 0 = the real exits''')
rep('''                else
                    int k = m + (s > 0 ? 0 : XM)
                    array.set(xN, k, array.get(xN, k) + 1), array.set(xP, k, array.get(xP, k) + pnl)
                    if pnl > 0
                        array.set(xW, k, array.get(xW, k) + 1)''', '''                else
                    xAdd(m, s, pnl)''')

# 5. the old EXIT LAB block inside the range table goes; the new panel is its own table at the bottom left
rep('''if barstate.islast and (rpDiag or xDiag)''', '''if barstate.islast and rpDiag''')
a = t.index('''    if xDiag
        table.cell(dg, 0, r0, "EXIT LAB - the same entries''')
b = t.index('''// ── EVENT EXPORT (top centre''')
t = t[:a] + '''
// ── EXIT LAB (Task 6, bottom left): every exit on the SAME entries this month, best first, with drawdown and the change vs your exits ──
if barstate.islast and xDiag
    var table xl = table.new(position.bottom_left, 8, XM + 4, bgcolor = color.new(color.black, 12), border_color = color.new(color.gray, 70), border_width = 1)
    table.clear(xl, 0, 0, 7, XM + 3)
    table.cell(xl, 0, 0, "EXIT LAB · this month · the same entries, only the exit changes", text_color = color.yellow, text_size = size.normal,
         tooltip = "Every real trade this month is also run with each exit below, from the same entry and with its first stop. A sketch on the chart's candles: when the stop and the target fall in the same 1-minute candle the STOP counts; no breakeven / day close; an exit that never fires closes after 4 hours. Prove a winner in MT5.")
    table.merge_cells(xl, 0, 0, 7, 0)
    hdr = array.from("exit method (best first)", "trades", "win rate", "net", "vs now", "max DD", "BUY net", "SELL net")
    for c = 0 to 7
        table.cell(xl, c, 1, array.get(hdr, c), text_color = color.silver, text_size = size.small, text_halign = c == 0 ? text.align_left : text.align_center)
    nets = array.new<float>(XM, 0.0)
    for m = 0 to XM - 1
        array.set(nets, m, array.get(xN, m + 2 * XM) > 0 ? array.get(xP, m + 2 * XM) : -1e12)
    ord = array.sort_indices(nets, order.descending)
    float now = array.get(xP, 2 * XM)
    for i = 0 to XM - 1
        int m = array.get(ord, i)
        int k = m + 2 * XM
        int n = array.get(xN, k)
        float pn = array.get(xP, k)
        bool cur = pickRow >= 0 ? m == pickRow : m == 0
        color bg = i == 0 and n > 0 ? color.new(color.green, 70) : cur ? color.new(color.blue, 65) : na
        string nm = (m == 0 ? "your exits now" : xName(m)) + (isPickable(m) ? "  ★" : "") + (cur ? "  ◀ in use" : "")
        table.cell(xl, 0, i + 2, nm, text_color = m == 0 ? color.aqua : color.white, text_size = size.small, text_halign = text.align_left, bgcolor = bg)
        table.cell(xl, 1, i + 2, str.tostring(n), text_color = color.white, text_size = size.small, bgcolor = bg)
        table.cell(xl, 2, i + 2, n > 0 ? str.tostring(100.0 * array.get(xW, k) / n, "#") + "%" : "-", text_color = color.white, text_size = size.small, bgcolor = bg)
        table.cell(xl, 3, i + 2, n > 0 ? fm(pn) : "-", text_color = pn >= 0 ? color.lime : color.red, text_size = size.small, bgcolor = bg)
        table.cell(xl, 4, i + 2, m == 0 or n == 0 ? "" : fm(pn - now), text_color = pn - now >= 0 ? color.lime : color.red, text_size = size.small, bgcolor = bg)
        table.cell(xl, 5, i + 2, n > 0 ? "-$" + str.tostring(array.get(xDD, k), "#,##0") : "-", text_color = color.orange, text_size = size.small, bgcolor = bg)
        table.cell(xl, 6, i + 2, array.get(xN, m) > 0 ? fm(array.get(xP, m)) : "-", text_color = color.aqua, text_size = size.small, bgcolor = bg)
        table.cell(xl, 7, i + 2, array.get(xN, m + XM) > 0 ? fm(array.get(xP, m + XM)) : "-", text_color = color.fuchsia, text_size = size.small, bgcolor = bg)
    table.cell(xl, 0, XM + 2, "★ = one click in TP1 › 'EXIT · quick pick' (the EA has it too: InpExitPreset). Green = best this month. Blue = the exit in use.",
         text_color = color.silver, text_size = size.tiny, text_halign = text.align_left)
    table.merge_cells(xl, 0, XM + 2, 7, XM + 2)

''' + t[b:]
p.write_text(t, encoding="utf-8")
print("pine patched")
