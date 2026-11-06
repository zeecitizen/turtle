"""Build mt5/Saad_pyramid.mq5 = Saad_cut + anti-martingale scale-in pyramiding (Zee 2026-10-13 spec).
While the EA's base position is open and the price has moved InpPyramidSpacing pips beyond the LAST entry
(base or last add-on), add a position of InpPyramidMultiplier x the last one's volume, up to InpMaxTiers
positions in total. Add-ons carry comment "saad_pyr" and are NOT adopted as normal EA trades:
  * each add-on always has at least the base position's stop (the EA's own trail moves the base; add-ons follow)
  * InpPyrLockBe: when an add-on fills, every position's stop goes to the basket's volume-weighted average
    entry +/- InpPyrBeBufPts points, if that is better than its stop (the spec's "locked basket")
  * add-ons are closed when the base position is gone, and (like the base) shut 3 min before the daily
    close when in loss."""
src = r'C:\Users\zeesh\turtle\mt5\Saad_cut.mq5'
dst = r'C:\Users\zeesh\turtle\mt5\Saad_pyramid.mq5'
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("input int    InpFlatMode    = 0;",
    """input bool   InpEnablePyramid = false; // InpEnablePyramid — scale-in pyramiding (anti-martingale)
input double InpPyramidSpacing = 30;  // InpPyramidSpacing — pips beyond the last entry before the next add-on
input double InpPyramidMultiplier = 0.5; // InpPyramidMultiplier — add-on volume = this x the last position's volume
input int    InpMaxTiers    = 3;      // InpMaxTiers — positions in total (base + add-ons)
input bool   InpPyrLockBe   = true;   // InpPyrLockBe — on each add-on, move every stop to the basket's average entry (+ buffer) if better
input double InpPyrBeBufPts = 20;     // InpPyrBeBufPts — buffer beyond the average entry, points
input double InpPyrSpacingAtr = 0;    // InpPyrSpacingAtr — >0: spacing = this x ATR(14) instead of InpPyramidSpacing pips
input double InpPyrRiskPct = 0;       // InpPyrRiskPct — >0: add-on size = this % of equity / the $ risk to its stop (instead of the multiplier)
input double InpPyrMaxLots = 1.0;     // InpPyrMaxLots — cap for one add-on with InpPyrRiskPct
input double InpPyrTrailAtr = 0;      // InpPyrTrailAtr — >0: when an add-on fills, trail every stop to price -/+ this x ATR (if better)
input int    InpFlatMode    = 0;""")
# never adopt add-ons as normal EA trades
rep("      if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;",
    "      if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;\n"
    "      if (PositionGetString(POSITION_COMMENT) == \"saad_pyr\") continue;   // pyramiding add-on, managed by ManagePyramid()")
rep("int g_ctc = 0,", "int g_pyrAdds = 0, g_pyrLocks = 0; datetime g_pyrBlock = 0;\nint g_ctc = 0,")

rep("bool ModifySl(ulong t, double sl)", r'''//--- scale-in pyramiding ----------------------------------------------------------
bool IsAddOn() { return PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber && PositionGetString(POSITION_COMMENT) == "saad_pyr"; }
void ManagePyramid()
{
   if (!InpEnablePyramid) return;
   ulong tk[]; int n = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) { ulong t = PositionGetTicket(i); if (t > 0 && IsAddOn()) { ArrayResize(tk, n + 1); tk[n++] = t; } }
   if (ArraySize(g_pos) == 0 || !PositionSelectByTicket(g_pos[0].ticket)) {             // base gone: close the add-ons
      for (int k = 0; k < n; k++) trade.PositionClose(tk[k]);
      return;
   }
   int side = g_pos[0].side;
   double baseSl = PositionGetDouble(POSITION_SL), baseVol = PositionGetDouble(POSITION_VOLUME), baseEn = PositionGetDouble(POSITION_PRICE_OPEN);
   double lastPx = baseEn, lastVol = baseVol;
   bool dayEnd = InpCloseLossMins > 0 && MinsToClose() <= InpCloseLossMins;
   for (int k = 0; k < n; k++) {
      if (!PositionSelectByTicket(tk[k])) continue;
      double op = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL);
      if (side > 0 ? op > lastPx : op < lastPx) { lastPx = op; lastVol = PositionGetDouble(POSITION_VOLUME); }
      if (dayEnd && PositionGetDouble(POSITION_PROFIT) < 0) { trade.PositionClose(tk[k]); continue; }
      bool better = baseSl > 0 && (side > 0 ? baseSl > sl + _Point : (sl == 0 || baseSl < sl - _Point));
      if (better && TimeCurrent() >= g_pyrBlock && !trade.PositionModify(tk[k], baseSl, 0)) g_pyrBlock = TimeCurrent() + 3;
   }
   if (n + 1 >= InpMaxTiers || TimeCurrent() < g_pyrBlock || dayEnd) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double atr = Buf(hAtr, 1);
   double spacing = InpPyrSpacingAtr > 0 && atr > 0 ? InpPyrSpacingAtr * atr : InpPyramidSpacing * Pip();
   if ((side > 0 ? bid - lastPx : lastPx - ask) < spacing) return;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vol = NormalizeDouble(MathMax(mn, MathRound(lastVol * InpPyramidMultiplier / step) * step), 2);
   if (InpPyrRiskPct > 0) {                                   // volatility sizing: fixed % risk to the add-on's real stop
      double dist = baseSl > 0 ? (side > 0 ? ask - baseSl : baseSl - bid) : 2 * atr;
      if (dist < atr * 0.25) dist = atr * 0.25;
      double perLot = dist / SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE) * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      vol = perLot > 0 ? AccountInfoDouble(ACCOUNT_EQUITY) * InpPyrRiskPct / 100.0 / perLot : mn;
      vol = NormalizeDouble(MathMin(InpPyrMaxLots, MathMax(mn, MathFloor(vol / step) * step)), 2);
   }
   bool ok = side > 0 ? trade.Buy(vol, _Symbol, 0, baseSl, 0, "saad_pyr") : trade.Sell(vol, _Symbol, 0, baseSl, 0, "saad_pyr");
   if (!ok) { g_pyrBlock = TimeCurrent() + 60; return; }
   g_pyrAdds++;
   Log(StringFormat("PYRAMID add-on %d: %s %.2f lots at %s", n + 1, side > 0 ? "BUY" : "SELL", vol, Px(trade.ResultPrice())));
   if (InpPyrTrailAtr > 0 && atr > 0) {                      // trail the whole basket on each add-on
      double want = NormalizeDouble(side > 0 ? bid - InpPyrTrailAtr * atr : ask + InpPyrTrailAtr * atr, _Digits);
      for (int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong t = PositionGetTicket(i);
         if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
         double sl = PositionGetDouble(POSITION_SL);
         if (!(side > 0 ? want > sl + _Point : (sl == 0 || want < sl - _Point))) continue;
         if (t == g_pos[0].ticket) { if (ModifySl(t, want)) SlMoved(0, want, "basket ATR trail"); }
         else trade.PositionModify(t, want, 0);
      }
   }
   if (!InpPyrLockBe) return;
   // basket VWAP -> lock every stop at break-even + buffer (only if better)
   double cost = 0, tv = 0; ulong all[]; int m = 0;
   for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      double v = PositionGetDouble(POSITION_VOLUME); cost += v * PositionGetDouble(POSITION_PRICE_OPEN); tv += v;
      ArrayResize(all, m + 1); all[m++] = t;
   }
   if (tv <= 0) return;
   double lock = NormalizeDouble(cost / tv + side * InpPyrBeBufPts * _Point, _Digits);
   if ((side > 0 ? bid - lock : lock - ask) < (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point) return;   // too close to the price
   for (int k = 0; k < m; k++) {
      if (!PositionSelectByTicket(all[k])) continue;
      double sl = PositionGetDouble(POSITION_SL);
      if (!(side > 0 ? lock > sl + _Point : (sl == 0 || lock < sl - _Point))) continue;
      if (all[k] == g_pos[0].ticket) { if (ModifySl(all[k], lock)) SlMoved(0, lock, "basket break-even"); }
      else trade.PositionModify(all[k], lock, 0);
   }
   g_pyrLocks++;
}

bool ModifySl(ulong t, double sl)''')
rep("   ManageTick();\n", "   ManageTick();\n   ManagePyramid();\n")
rep('   PrintFormat("[SAAD] CTC breakevens %d',
    '   PrintFormat("[SAAD-PYR] add-ons %d, basket locks %d", g_pyrAdds, g_pyrLocks);\n   PrintFormat("[SAAD] CTC breakevens %d')
open(dst, 'w', encoding='utf-8').write(s)
print('wrote', dst)
