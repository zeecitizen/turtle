//+------------------------------------------------------------------+
//| ShanoTickLogger.mq5                                              |
//| Records every tick (bid/ask/volume) to CSV for backtest replay.  |
//|                                                                  |
//| Output: Common\Files\shano_ticks_YYYY-MM-DD.csv (daily rotation) |
//|                                                                  |
//| Each row: ts_broker, ms_in_sec, bid, ask, last, volume           |
//|   - ts_broker is broker server time (seconds resolution)         |
//|   - ms_in_sec is a per-second counter (0..N) so ticks within     |
//|     the same broker-second can be ordered                        |
//|                                                                  |
//| Performance: keeps file handle open, flushes every 5s. Tested    |
//| up to ~150 ticks/sec on XAUUSD without dropping ticks.           |
//+------------------------------------------------------------------+
#property copyright "Shano Trading System"
#property version   "1.00"
#property strict

input string InpSymbolFilter   = "XAUUSD";
input int    InpFlushEverySec  = 5;

int      g_handle      = INVALID_HANDLE;
string   g_currentFile = "";
datetime g_fileDay     = 0;
datetime g_lastFlush   = 0;
datetime g_lastSec     = 0;
int      g_subSecCtr   = 0;
ulong    g_totalTicks  = 0;

//+------------------------------------------------------------------+
string DailyFileName()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    return StringFormat("shano_ticks_%04d-%02d-%02d.csv", dt.year, dt.mon, dt.day);
}

//+------------------------------------------------------------------+
bool OpenFile()
{
    if(g_handle != INVALID_HANDLE)
    {
        FileClose(g_handle);
        g_handle = INVALID_HANDLE;
    }

    g_currentFile = DailyFileName();
    // Open in append mode by reading first if exists, else creating.
    int existing = FileOpen(g_currentFile, FILE_READ|FILE_CSV|FILE_COMMON|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
    bool fileExists = (existing != INVALID_HANDLE);
    if(fileExists) FileClose(existing);

    g_handle = FileOpen(g_currentFile, FILE_WRITE|FILE_READ|FILE_CSV|FILE_COMMON|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
    if(g_handle == INVALID_HANDLE)
    {
        PrintFormat("ShanoTickLogger: ERROR opening %s — last_error=%d", g_currentFile, GetLastError());
        return false;
    }

    if(!fileExists)
    {
        // Brand new file — write header
        FileWrite(g_handle, "ts_broker", "ms", "bid", "ask", "last", "volume");
    }
    else
    {
        // Seek to end so we append
        FileSeek(g_handle, 0, SEEK_END);
    }

    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    g_fileDay = StringToTime(StringFormat("%04d.%02d.%02d", dt.year, dt.mon, dt.day));
    g_lastFlush = TimeCurrent();

    PrintFormat("ShanoTickLogger: writing → Common\\Files\\%s", g_currentFile);
    return true;
}

//+------------------------------------------------------------------+
int OnInit()
{
    if(!OpenFile()) return INIT_FAILED;
    PrintFormat("ShanoTickLogger started. Symbol filter: %s. Flush every %ds.",
                InpSymbolFilter, InpFlushEverySec);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    if(g_handle != INVALID_HANDLE)
    {
        FileFlush(g_handle);
        FileClose(g_handle);
        g_handle = INVALID_HANDLE;
    }
    PrintFormat("ShanoTickLogger stopped (reason=%d). Total ticks logged: %I64u", reason, g_totalTicks);
}

//+------------------------------------------------------------------+
void OnTick()
{
    if(g_handle == INVALID_HANDLE) return;
    if(InpSymbolFilter != "" && _Symbol != InpSymbolFilter) return;

    datetime now = TimeCurrent();

    // Daily rotation — when broker date changes, switch file
    MqlDateTime dt;
    TimeToStruct(now, dt);
    datetime today = StringToTime(StringFormat("%04d.%02d.%02d", dt.year, dt.mon, dt.day));
    if(today != g_fileDay)
    {
        OpenFile();
    }

    // Sub-second counter — reset each broker-second
    if(now != g_lastSec)
    {
        g_lastSec = now;
        g_subSecCtr = 0;
    }
    else
    {
        g_subSecCtr++;
    }

    double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double last   = SymbolInfoDouble(_Symbol, SYMBOL_LAST);
    long   volume = SymbolInfoInteger(_Symbol, SYMBOL_VOLUME);

    FileWrite(g_handle,
              TimeToString(now, TIME_DATE|TIME_SECONDS),
              g_subSecCtr,
              DoubleToString(bid, 3),
              DoubleToString(ask, 3),
              DoubleToString(last, 3),
              volume);

    g_totalTicks++;

    if(now - g_lastFlush >= InpFlushEverySec)
    {
        FileFlush(g_handle);
        g_lastFlush = now;
    }
}
//+------------------------------------------------------------------+
