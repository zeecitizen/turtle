"""Watch turtle_fills.csv for new fills; emit one event per new fill with
running day P&L. Hard alert if day P&L crosses -$250 (the halt line) or
gets within $100 of the -$400 daily limit."""
import csv, time, sys
from pathlib import Path

FILLS = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")
TODAY = "2026.06.03"
POLL = 15  # seconds

def read_today():
    if not FILLS.exists(): return []
    out = []
    with open(FILLS, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        next(rdr, None)
        for r in rdr:
            if not r: continue
            if r[0].startswith(TODAY):
                try: pnl = float(r[7])
                except: continue
                out.append({"t": r[0], "side": r[4], "vol": r[5],
                            "pnl": pnl, "ticket": r[1]})
    return out

def main():
    seen = {x["ticket"] for x in read_today()}
    day_pnl = sum(x["pnl"] for x in read_today())
    sys.stdout.write(f"[atmos-watch] armed. baseline today: {len(seen)} fills, "
                     f"day P&L ${day_pnl:+.2f}\n")
    sys.stdout.flush()
    while True:
        time.sleep(POLL)
        try:
            fills = read_today()
        except Exception as e:
            sys.stdout.write(f"[atmos-watch] read-err: {e}\n"); sys.stdout.flush()
            continue
        new = [f for f in fills if f["ticket"] not in seen]
        if not new: continue
        for f in new: seen.add(f["ticket"])
        day_pnl = sum(x["pnl"] for x in fills)
        for f in new:
            tag = "WIN" if f["pnl"] > 0 else "LOSS"
            sys.stdout.write(f"FILL {f['t']} {f['side']} vol={f['vol']} "
                             f"pnl=${f['pnl']:+.2f} [{tag}]  DAY=${day_pnl:+.2f}\n")
        if day_pnl <= -250:
            sys.stdout.write(f"ALERT halt line crossed: ${day_pnl:+.2f} <= -$250\n")
        if day_pnl <= -300:
            sys.stdout.write(f"ALERT severe DD: ${day_pnl:+.2f}, $100 from -$400 limit\n")
        sys.stdout.flush()

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
