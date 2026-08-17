//+------------------------------------------------------------------+
//|  TurtleTradeLogger.mq5                                           |
//|  Appends every closed trade fill to turtle_fills.csv             |
//|                                                                  |
//|  INSTALL:                                                        |
//|  1. Copy to MT5 data folder: File > Open Data Folder            |
//|     then MQL5 > Experts > TurtleTradeLogger.mq5                 |
//|  2. Open MetaEditor (F4), find the file, press F7 to compile    |
//|  3. Drag "TurtleTradeLogger" onto ANY chart (e.g. XAUUSD M5)   |
//|     -- do NOT put on same chart as PineConnector                |
//|  4. Allow "AutoTrading" button to be ON                         |
//|                                                                  |
//|  OUTPUT FILE:                                                    |
//|  C:\Users\...\AppData\Roaming\MetaQuotes\Terminal\Common\Files\ |
//|  turtle_fills.csv                                                |
//|                                                                  |
//|  Claude reads this file every 5 minutes for actual P&L.         |
//+------------------------------------------------------------------+
#property copyright "Turtle Trader by M. Zeeshan"
#property version   "1.04"
// v1.04 (2026-08-17): BACKFILL. The logger was purely event-driven — OnTradeTransaction
//   was its ONLY source, so any deal that closed while the terminal was off (a server-side
//   SL, a restart, a reload) was lost forever. Found by reconciling against the broker's
//   own ReportHistory export: 96 positions missing since Aug 3, including all six −$50
//   stop-outs of the 17 Aug 10:21 basket (−$501.40 of that day's true −$561.90 was
//   invisible). OnInit now replays broker history since the last logged row and appends
//   every closed deal the file does not already contain, deduped by deal_ticket.
// v1.03 (2026-06-09): magic 88005 re-mapped BTC_S3 → S1_M1 (S1Trader M1 scalp instance).
//   Magic 88005 was originally for BtcS3M30Trader but that EA is dead; we re-used 88005
//   for S1Trader's M1 instance. CSV labels were misleading (showed "BTC_S3" for XAUUSD
//   trades). Also clarified 88004 → "S1_M5" for symmetry.
#property description "Logs every closed trade fill to Common/Files/turtle_fills.csv"
#property strict

//--- inputs
input string InpFileName    = "turtle_fills.csv";   // Output filename (in Common\Files)
input bool   InpLogOpens    = false;                // Also log trade opens (DEAL_ENTRY_IN)
input string InpPosFile     = "open_positions.json";// Live open-positions snapshot (in Common\Files)
input int    InpPosRefresh  = 2;                    // How often to refresh that snapshot (seconds)

//--- CSV header
const string HEADER = "broker_time,deal_ticket,position_ticket,symbol,direction,volume,close_price,profit,commission,swap,net_pnl,comment,magic,ea\n";

// Map a deal's magic number to the EA that opened it (magic 0 = manual/Human).
string EaNameForMagic(long m) {
   if (m == 88003) return "S3";
   if (m == 88004) return "S1_M5";    // S1Trader on M5 chart
   if (m == 88005) return "S1_M1";    // 2026-06-09: re-purposed from BTC_S3 → S1Trader M1 instance (scalp)
   if (m == 88006) return "NSND";
   if (m == 88007) return "S4";
   if (m == 88009) return "Feb11_AGG";    // Feb11TickTrader (aggressive)
   if (m == 88010) return "BTC_S4b";
   if (m == 88011) return "Feb11_MED";    // Feb11TickMedium on FTMO DEMO (paper validation)
   if (m == 88012) return "Feb11_LIVE";   // Feb11TickMedium on AtmosGlobal LIVE (real prop firm)
   if (m == 0)     return "Human";
   return "EA_" + IntegerToString(m);
}

// Deal tickets already present in the CSV — the dedup key for backfill AND for live
// writes, so a deal can never be logged twice even across restarts.
ulong  g_known[];
int    g_known_n = 0;

bool KnownDeal(ulong deal)
{
   for (int i = 0; i < g_known_n; i++) if (g_known[i] == deal) return true;
   return false;
}

void RememberDeal(ulong deal)
{
   ArrayResize(g_known, g_known_n + 1);
   g_known[g_known_n++] = deal;
}

// Write one closed (or open, if enabled) deal to the CSV. Used by the live event
// handler and by the backfill alike — one writer, one format.
bool LogDeal(ulong deal)
{
    if (!HistoryDealSelect(deal)) return false;

    long deal_entry = HistoryDealGetInteger(deal, DEAL_ENTRY);
    bool is_close   = (deal_entry == DEAL_ENTRY_OUT || deal_entry == DEAL_ENTRY_INOUT);
    bool is_open    = (deal_entry == DEAL_ENTRY_IN);
    if (!(is_close || (InpLogOpens && is_open))) return false;
    if (KnownDeal(deal)) return false;

    datetime deal_time   = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
    ulong    pos_ticket  = HistoryDealGetInteger(deal, DEAL_POSITION_ID);
    string   symbol      = HistoryDealGetString(deal,  DEAL_SYMBOL);
    long     deal_type   = HistoryDealGetInteger(deal, DEAL_TYPE);
    double   volume      = HistoryDealGetDouble(deal,  DEAL_VOLUME);
    double   price       = HistoryDealGetDouble(deal,  DEAL_PRICE);
    double   profit      = HistoryDealGetDouble(deal,  DEAL_PROFIT);
    double   commission  = HistoryDealGetDouble(deal,  DEAL_COMMISSION);
    double   swap        = HistoryDealGetDouble(deal,  DEAL_SWAP);
    string   comment     = HistoryDealGetString(deal,  DEAL_COMMENT);
    long     magic       = HistoryDealGetInteger(deal, DEAL_MAGIC);

    string close_direction = (deal_type == DEAL_TYPE_SELL) ? "BUY_closed" : "SELL_closed";
    if (is_open)
        close_direction = (deal_type == DEAL_TYPE_BUY) ? "BUY_open" : "SELL_open";

    double net_pnl = profit + commission + swap;
    StringReplace(comment, ",", ";");
    StringReplace(comment, "\n", " ");
    StringReplace(comment, "\r", "");

    string line = StringFormat("%s,%I64u,%I64u,%s,%s,%.2f,%.5f,%.2f,%.2f,%.2f,%.2f,%s,%I64d,%s\n",
                               TimeToString(deal_time, TIME_DATE|TIME_SECONDS),
                               deal, pos_ticket, symbol, close_direction, volume, price,
                               profit, commission, swap, net_pnl, comment,
                               magic, EaNameForMagic(magic));

    int h = FileOpen(InpFileName, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
    if (h == INVALID_HANDLE)
    {
        PrintFormat("TurtleTradeLogger: ERROR opening file err=%d", GetLastError());
        return false;
    }
    FileSeek(h, 0, SEEK_END);
    FileWriteString(h, line);
    FileClose(h);
    RememberDeal(deal);
    return true;
}

// Replay broker history and append every closed deal the CSV does not already hold.
// Runs at init — so a restart HEALS the file instead of leaving a silent hole.
void BackfillMissedDeals()
{
    // 1. what the file already knows, and when its record ends
    datetime last = 0;
    int h = FileOpen(InpFileName, FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI);
    if (h != INVALID_HANDLE)
    {
        while (!FileIsEnding(h))
        {
            string parts[];
            if (StringSplit(FileReadString(h), ',', parts) < 3) continue;
            ulong dt = (ulong)StringToInteger(parts[1]);
            if (dt == 0) continue;                       // header or malformed
            if (!KnownDeal(dt)) RememberDeal(dt);
            datetime t = StringToTime(parts[0]);
            if (t > last) last = t;
        }
        FileClose(h);
    }

    // 2. replay at least the last 14 days, and further back if the file's record ends
    //    earlier than that — the dedup set makes a wide window safe, only slower.
    datetime from = TimeCurrent() - 14 * 86400;
    if (last > 0 && last - 86400 < from) from = last - 86400;
    if (!HistorySelect(from, TimeCurrent() + 3600))
    {
        Print("TurtleTradeLogger: backfill HistorySelect failed");
        return;
    }
    int added = 0;
    int total = HistoryDealsTotal();
    for (int i = 0; i < total; i++)
    {
        ulong deal = HistoryDealGetTicket(i);
        if (deal != 0 && LogDeal(deal)) added++;
    }
    PrintFormat("TurtleTradeLogger: backfill scanned %d deals since %s — appended %d missed",
                total, TimeToString(from, TIME_DATE|TIME_SECONDS), added);
}

//+------------------------------------------------------------------+
//| EA init — write header if file is new                            |
//+------------------------------------------------------------------+
int OnInit()
{
    // Open file to check if empty; write header if so
    int h = FileOpen(InpFileName, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
    if (h != INVALID_HANDLE)
    {
        if (FileSize(h) == 0)
        {
            FileWriteString(h, HEADER);
            Print("TurtleTradeLogger: created new file with header");
        }
        FileClose(h);
    }
    else
    {
        PrintFormat("TurtleTradeLogger: WARNING - could not open %s (err=%d)",
                    InpFileName, GetLastError());
    }

    // Heal any hole left by downtime BEFORE resuming live logging.
    BackfillMissedDeals();

    // Timer drives the live open-positions snapshot (covers EVERY magic incl.
    // manual/Human trades — the per-EA heartbeats only see their own magic).
    EventSetTimer(InpPosRefresh > 0 ? InpPosRefresh : 2);

    PrintFormat("TurtleTradeLogger v1.04 ready → fills=%s, positions=%s every %ds",
                InpFileName, InpPosFile, InpPosRefresh);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Timer — write ALL open positions (any magic) to a JSON snapshot  |
//| so the dashboard's LIVE panel can show EA + manual trades alike. |
//+------------------------------------------------------------------+
void OnTimer()
{
    string arr = "[";
    int n = 0;
    for (int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong tk = PositionGetTicket(i);
        if (tk == 0 || !PositionSelectByTicket(tk)) continue;

        long   magic = PositionGetInteger(POSITION_MAGIC);
        bool   buy   = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
        string sym   = PositionGetString(POSITION_SYMBOL);
        double pnl   = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);

        if (n > 0) arr += ",";
        arr += StringFormat(
            "{\"ticket\":%I64u,\"symbol\":\"%s\",\"side\":\"%s\",\"lots\":%.2f,\"entry\":%.5f,\"cur\":%.5f,\"pnl\":%.2f,\"sl\":%.5f,\"tp\":%.5f,\"magic\":%I64d,\"ea\":\"%s\"}",
            tk, sym, buy ? "BUY" : "SELL",
            PositionGetDouble(POSITION_VOLUME),
            PositionGetDouble(POSITION_PRICE_OPEN),
            PositionGetDouble(POSITION_PRICE_CURRENT),
            pnl,
            PositionGetDouble(POSITION_SL),
            PositionGetDouble(POSITION_TP),
            magic, EaNameForMagic(magic));
        n++;
    }
    arr += "]";

    string out = StringFormat("{\"ts\":\"%s\",\"positions\":%s}",
                              TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), arr);

    int h = FileOpen(InpPosFile, FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
    if (h != INVALID_HANDLE)
    {
        FileWriteString(h, out);
        FileClose(h);
    }
}

//+------------------------------------------------------------------+
//| EA deinit                                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    EventKillTimer();
    PrintFormat("TurtleTradeLogger: stopped (reason=%d)", reason);
}

//+------------------------------------------------------------------+
//| Every trade event on this account fires here                     |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest     &request,
                        const MqlTradeResult      &result)
{
    // Only care about newly added deals
    if (trans.type != TRADE_TRANSACTION_DEAL_ADD)
        return;

    if (!LogDeal(trans.deal))
        return;

    // Log to MT5 journal tab as well
    PrintFormat("TurtleTradeLogger: logged deal=%I64u", trans.deal);
}

//+------------------------------------------------------------------+
//| Unused but required for EA compilation                           |
//+------------------------------------------------------------------+
void OnTick() {}
//+------------------------------------------------------------------+
