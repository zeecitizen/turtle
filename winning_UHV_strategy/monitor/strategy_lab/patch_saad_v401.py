p=r'C:\Users\zeesh\turtle\mt5\Saad_strategy.mq5'; s=open(p,encoding='utf-8').read()
def rep(a,b):
    global s
    assert a in s, a[:60]; s=s.replace(a,b,1)
rep("""//--- tuning: more trades / daily guard""","""//--- v4.01 tuning: geometry
input double InpLockAtUsd   = 0;      // InpLockAtUsd — once price moved this $ the trade's way... (0 = off; VSISA's one-lock ratchet)
input double InpLockUsd     = 0;      // InpLockUsd — ...lock the stop this $ beyond the entry
input double InpFixTpPips   = 0;      // InpFixTpPips — fixed take profit for both sides, no ride (0 = the rules' targets)
input int    InpMaxBars     = 0;      // InpMaxBars — close a trade still open after this many candles (0 = off)
input int    InpCoolBars    = 0;      // InpCoolBars — after a losing trade, no new setups for this many candles (0 = off)

//--- tuning: more trades / daily guard""")
# lock at $X tick-level + time exit in ManageTick
rep("""   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (g_pos[i].ride) continue;""","""   double ask0 = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for (int i = ArraySize(g_pos) - 1; i >= 0; i--) {
      if (InpLockAtUsd > 0 && PositionSelectByTicket(g_pos[i].ticket)) {
         double moved = g_pos[i].side > 0 ? bid - g_pos[i].entry : g_pos[i].entry - ask0;
         double want = g_pos[i].entry + g_pos[i].side * InpLockUsd, cur = PositionGetDouble(POSITION_SL);
         if (moved >= InpLockAtUsd && (g_pos[i].side > 0 ? want > cur + _Point : (cur == 0 || want < cur - _Point))) ModifySl(g_pos[i].ticket, want);
      }
      if (InpMaxBars > 0 && TimeCurrent() - g_pos[i].entryTime >= InpMaxBars * PeriodSeconds()) { trade.PositionClose(g_pos[i].ticket); continue; }
      if (InpFixTpPips > 0) continue;
      if (g_pos[i].ride) continue;""")
# fixed TP at entry
rep("""   bool rideShort = side < 0 && TrailOn(-1) && InpRide;""","""   bool rideShort = side < 0 && TrailOn(-1) && InpRide && InpFixTpPips <= 0;
   if (InpFixTpPips > 0) { tp = side > 0 ? en + InpFixTpPips * pip : en - InpFixTpPips * pip; noTp = false; }""")
rep("""   bool ok = side > 0 ? trade.Buy(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), 0, "saad_long")""",
    """   bool ok = side > 0 ? trade.Buy(InpLots, _Symbol, 0, NormalizeDouble(sl, _Digits), InpFixTpPips > 0 ? NormalizeDouble(tp, _Digits) : 0, "saad_long")""")
rep("""   p.exitE = g_pExit; p.noTp = noTp; p.ride = side > 0 && noTp && TrailOn(1);""",
    """   p.exitE = g_pExit; p.noTp = noTp; p.ride = side > 0 && noTp && TrailOn(1) && InpFixTpPips <= 0;""")
# ManageBar: skip rules exits when fixed TP; trailing only if ride/started (fixed TP + trail without ride allowed)
rep("""      if (side > 0 && !g_pos[i].ride) {""","""      if (side > 0 && !g_pos[i].ride && InpFixTpPips <= 0) {""")
# cooldown: track last losing close time
rep("""void DetectSetup()
{
""","""datetime g_coolUntil = 0;
void CheckCooldown()
{
   static int seen = 0;
   if (InpCoolBars <= 0) return;
   if (!HistorySelect(TimeCurrent() - 86400 * 3, TimeCurrent() + 60)) return;
   int n = HistoryDealsTotal();
   if (n == seen) return;
   seen = n;
   for (int i = n - 1; i >= 0; i--) {
      ulong k = HistoryDealGetTicket(i);
      if (HistoryDealGetInteger(k, DEAL_MAGIC) != InpMagicNumber || HistoryDealGetInteger(k, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      if (HistoryDealGetDouble(k, DEAL_PROFIT) < 0) g_coolUntil = MathMax(g_coolUntil, (datetime)HistoryDealGetInteger(k, DEAL_TIME) + InpCoolBars * PeriodSeconds());
      break;
   }
}

void DetectSetup()
{
   CheckCooldown();
   if (TimeCurrent() < g_coolUntil) return;
""")
s=s.replace('#property version   "4.00"','#property version   "4.01"').replace("Saad_strategy.mq5  v4.00","Saad_strategy.mq5  v4.01").replace('"[SAAD] v4.00 ','"[SAAD] v4.01 ')
open(p,'w',encoding='utf-8').write(s); print('patched')
