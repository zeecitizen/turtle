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
#property version   "1.03"
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

    // Timer drives the live open-positions snapshot (covers EVERY magic incl.
    // manual/Human trades — the per-EA heartbeats only see their own magic).
    EventSetTimer(InpPosRefresh > 0 ? InpPosRefresh : 2);

    PrintFormat("TurtleTradeLogger v1.02 ready → fills=%s, positions=%s every %ds",
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

    // Pull deal details from history
    if (!HistoryDealSelect(trans.deal))
        return;

    long deal_entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);

    // Decide which entries to log
    bool is_close   = (deal_entry == DEAL_ENTRY_OUT || deal_entry == DEAL_ENTRY_INOUT);
    bool is_open    = (deal_entry == DEAL_ENTRY_IN);
    bool should_log = is_close || (InpLogOpens && is_open);

    if (!should_log)
        return;

    // --- Read deal fields ---
    datetime deal_time   = (datetime)HistoryDealGetInteger(trans.deal, DEAL_TIME);
    ulong    deal_ticket = trans.deal;
    ulong    pos_ticket  = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
    string   symbol      = HistoryDealGetString(trans.deal,  DEAL_SYMBOL);
    long     deal_type   = HistoryDealGetInteger(trans.deal, DEAL_TYPE);
    double   volume      = HistoryDealGetDouble(trans.deal,  DEAL_VOLUME);
    double   price       = HistoryDealGetDouble(trans.deal,  DEAL_PRICE);
    double   profit      = HistoryDealGetDouble(trans.deal,  DEAL_PROFIT);
    double   commission  = HistoryDealGetDouble(trans.deal,  DEAL_COMMISSION);
    double   swap        = HistoryDealGetDouble(trans.deal,  DEAL_SWAP);
    string   comment     = HistoryDealGetString(trans.deal,  DEAL_COMMENT);
    long     magic       = HistoryDealGetInteger(trans.deal,  DEAL_MAGIC);
    string   ea_name     = EaNameForMagic(magic);

    // Direction: closing deal type is OPPOSITE to the position direction
    // DEAL_TYPE_BUY = buying back a short (closing short) → position was SELL
    // DEAL_TYPE_SELL = selling a long (closing long) → position was BUY
    string close_direction = (deal_type == DEAL_TYPE_SELL) ? "BUY_closed" : "SELL_closed";
    if (is_open)
        close_direction = (deal_type == DEAL_TYPE_BUY) ? "BUY_open" : "SELL_open";

    double net_pnl = profit + commission + swap;

    // Sanitise comment: remove commas and newlines
    StringReplace(comment, ",", ";");
    StringReplace(comment, "\n", " ");
    StringReplace(comment, "\r", "");

    // Format time string (broker server time — not UTC; adjust +3h for UTC if Moscow broker)
    string time_str = TimeToString(deal_time, TIME_DATE|TIME_SECONDS);

    // Build CSV line
    string line = StringFormat("%s,%I64u,%I64u,%s,%s,%.2f,%.5f,%.2f,%.2f,%.2f,%.2f,%s,%I64d,%s\n",
                               time_str,
                               deal_ticket,
                               pos_ticket,
                               symbol,
                               close_direction,
                               volume,
                               price,
                               profit,
                               commission,
                               swap,
                               net_pnl,
                               comment,
                               magic,
                               ea_name);

    // Append to CSV (open, seek to end, write, close)
    int h = FileOpen(InpFileName, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
    if (h == INVALID_HANDLE)
    {
        PrintFormat("TurtleTradeLogger: ERROR opening file err=%d", GetLastError());
        return;
    }
    FileSeek(h, 0, SEEK_END);
    FileWriteString(h, line);
    FileClose(h);

    // Log to MT5 journal tab as well
    PrintFormat("TurtleTradeLogger: deal=%I64u pos=%I64u %s %s %.2f lots  net=$%.2f",
                deal_ticket, pos_ticket, close_direction, symbol, volume, net_pnl);
}

//+------------------------------------------------------------------+
//| Unused but required for EA compilation                           |
//+------------------------------------------------------------------+
void OnTick() {}
//+------------------------------------------------------------------+
