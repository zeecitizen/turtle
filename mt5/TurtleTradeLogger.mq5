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
#property version   "1.01"
#property description "Logs every closed trade fill to Common/Files/turtle_fills.csv"
#property strict

//--- inputs
input string InpFileName    = "turtle_fills.csv";   // Output filename (in Common\Files)
input bool   InpLogOpens    = false;                // Also log trade opens (DEAL_ENTRY_IN)

//--- CSV header
const string HEADER = "broker_time,deal_ticket,position_ticket,symbol,direction,volume,close_price,profit,commission,swap,net_pnl,comment,magic,ea\n";

// Map a deal's magic number to the EA that opened it (magic 0 = manual/Human).
string EaNameForMagic(long m) {
   if (m == 88003) return "S3";
   if (m == 88004) return "S1";
   if (m == 88005) return "BTC_S3";
   if (m == 88006) return "NSND";
   if (m == 88007) return "S4";
   if (m == 88010) return "BTC_S4b";
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

    PrintFormat("TurtleTradeLogger v1.01 ready → Common\\Files\\%s", InpFileName);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| EA deinit                                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
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
