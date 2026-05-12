"""Pull XAUUSD real ticks from running Blueberry MT5 and cache to parquet.

Run once per session — incremental fetch picks up newest ticks since last cache.
Output: monitor/strategy_lab/_xauusd_ticks.parquet  (cols: time_msc, bid, ask, flags, volume_real)
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
LOG   = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_fetch_real_ticks.log")
SYMBOL = "XAUUSD"
DAYS_BACK = 120

LOGF = open(LOG, "w", encoding="utf-8")
def log(msg):
    print(msg, flush=True)
    LOGF.write(msg + "\n"); LOGF.flush()

if not mt5.initialize(timeout=15000):
    log(f"[FAIL] mt5.initialize: {mt5.last_error()}"); sys.exit(1)

now = datetime.now(timezone.utc)
start = now - timedelta(days=DAYS_BACK)

if CACHE.exists():
    cached = pd.read_parquet(CACHE)
    last_msc = int(cached["time_msc"].max())
    fetch_from = datetime.fromtimestamp(last_msc / 1000, tz=timezone.utc) - timedelta(seconds=2)
    log(f"[CACHE] {len(cached):,} ticks | last={fetch_from.isoformat()}")
else:
    cached = None
    fetch_from = start
    log(f"[FRESH] no cache, pulling {DAYS_BACK}d from {fetch_from.isoformat()}")

log(f"[PULL] {fetch_from.isoformat()} -> {now.isoformat()} (chunked by day)")
all_chunks = []
chunk_start = fetch_from
import time
while chunk_start < now:
    chunk_end = min(chunk_start + timedelta(days=1), now)
    ticks = None
    for attempt in range(3):
        ticks = mt5.copy_ticks_range(SYMBOL, chunk_start, chunk_end, mt5.COPY_TICKS_ALL)
        if ticks is not None:
            break
        time.sleep(1.0)
    if ticks is None:
        log(f"  [FAIL3x] {chunk_start.date()}: {mt5.last_error()}")
    else:
        n = len(ticks)
        if n:
            all_chunks.append(pd.DataFrame(ticks))
        log(f"  {chunk_start.strftime('%Y-%m-%d')}: {n:>6,} ticks")
    chunk_start = chunk_end

if not all_chunks and cached is None:
    log("[ERR] no ticks pulled and no cache"); mt5.shutdown(); sys.exit(1)

df_new = pd.concat(all_chunks, ignore_index=True) if all_chunks else pd.DataFrame()
if len(df_new):
    df_new = df_new[["time_msc", "bid", "ask", "flags", "volume_real"]]
log(f"[OK] total new: {len(df_new):,} ticks across {len(all_chunks)} days")

if cached is not None and len(df_new):
    combined = pd.concat([cached, df_new], ignore_index=True)
    combined = combined.drop_duplicates(subset=["time_msc"]).sort_values("time_msc").reset_index(drop=True)
elif cached is not None:
    combined = cached
else:
    combined = df_new.sort_values("time_msc").reset_index(drop=True)

combined.to_parquet(CACHE, index=False)

t_first = datetime.fromtimestamp(combined["time_msc"].min() / 1000, tz=timezone.utc)
t_last  = datetime.fromtimestamp(combined["time_msc"].max() / 1000, tz=timezone.utc)
spread_pts = ((combined["ask"] - combined["bid"]) * 100).astype(int)
log(f"[DONE] {len(combined):,} ticks @ {CACHE.name}")
log(f"       span: {t_first.isoformat()} -> {t_last.isoformat()}")
log(f"       spread (pts): min={spread_pts.min()} median={int(spread_pts.median())} max={spread_pts.max()}")
log(f"       file size: {CACHE.stat().st_size / 1024 / 1024:.1f} MB")
mt5.shutdown()
LOGF.close()
