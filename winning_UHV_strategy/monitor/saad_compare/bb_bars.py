"""bb_bars.py - the Blueberry 1-min candles for the compare page's chart (Jan 1 - Oct 17 2026).

Zee 2026-10-17: "would it be impossible to use the real ticks downloaded by blueberry to create a chart.. and then apply
all settings to that chart.. that would essentially mean recreating tradingview right? ... any shortcuts?"

The candles come from MT5's Strategy Tester itself: mt5/BbBarDump.mq5 runs on XAUUSD_BB (Blueberry real ticks) in the
compare page's rig and writes each closed M1 candle - the very candles the Saad EA judges in the 10-month view.

    py monitor/saad_compare/bb_bars.py            # all months not built yet
    py monitor/saad_compare/bb_bars.py 2026.10    # one month again

Times: the tester writes Blueberry server time (New York + 7 h); stored here in UTC like the TradingView chart.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "strategy_lab"))
import axi_rig  # noqa: E402

OUT = HERE / "why_out" / "bb_bars"
COMMON = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"
MONTHS = [f"2026.{m:02d}" for m in range(1, 11)]
RIG = "axi"                     # C:/mt5_rig_axi - the compare page's own rig (axi2-7 belong to the 10-month view)
NY, UTC = ZoneInfo("America/New_York"), ZoneInfo("UTC")


def srv_to_utc(s):
    """'2026.10.14 16:05[:33]' Blueberry server time -> datetime in UTC (server = New York local time + 7 h)."""
    s = s.strip().replace("-", ".")
    ny = datetime.strptime(s[:19], "%Y.%m.%d %H:%M:%S" if len(s) >= 19 else "%Y.%m.%d %H:%M") - timedelta(hours=7)
    return ny.replace(tzinfo=NY).astimezone(UTC).replace(tzinfo=None)


def _next(m):
    y, mo = int(m[:4]), int(m[5:])
    return f"{y + (mo == 12)}.{(mo % 12) + 1:02d}.01"


def build(m):
    name = f"bb_bars_{m.replace('.', '_')}.csv"
    (COMMON / name).unlink(missing_ok=True)
    r = axi_rig.run("BbBarDump", "XAUUSD_BB", "M1", {"InpOut": name}, frm=f"{m}.01", to=_next(m), deposit=100000,
                    rig=RIG, tag="bb_bars", exec_mode=0)
    src = COMMON / name
    if r.get("error") or not src.exists():
        return f"{m}: failed ({r.get('error') or 'no file'})"
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for line in src.read_text(encoding="utf-8", errors="ignore").splitlines():
        c = line.strip().split(",")
        if len(c) == 5 and c[0][:7] == m:
            rows.append(f"{srv_to_utc(c[0]).strftime('%Y-%m-%d %H:%M')},{c[1]},{c[2]},{c[3]},{c[4]}")
    (OUT / f"{m.replace('.', '-')}.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    src.unlink(missing_ok=True)
    return f"{m}: {len(rows)} candles"


def read_trades(path):
    """The Saad EA's per-trade CSV (v1.24 InpCsvName) -> list of dicts, times in UTC."""
    out = []
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines[1:]:
        c = line.split(",")
        if len(c) < 22:
            continue
        ts = lambda s: srv_to_utc(s).strftime("%Y-%m-%d %H:%M:%S") if s.strip() else ""
        f = lambda s: float(s) if s.strip() else None
        out.append({"num": int(c[0]), "side": c[2], "setup": c[3].replace(";", ","), "in": ts(c[4]), "en": f(c[5]),
                    "sl": f(c[6]), "risk": f(c[7]), "tp1": c[8].replace(";", ","), "tp1_at": ts(c[9]), "tps": c[10],
                    "ctc_at": ts(c[11]), "moves": int(c[12] or 0), "best": f(c[13]), "sl_last": f(c[14]),
                    "out": ts(c[15]), "ex": f(c[16]), "why": c[17], "net": f(c[21])})
    return out


def bars(day_from, day_to):
    """UTC candles from day_from 00:00 to day_to 23:59 (dates 'YYYY-MM-DD') as [[epoch, o, h, l, c], ...]."""
    out = []
    a, b = datetime.strptime(day_from, "%Y-%m-%d"), datetime.strptime(day_to, "%Y-%m-%d") + timedelta(days=1)
    months = sorted({(a + timedelta(days=i)).strftime("%Y-%m") for i in range((b - a).days + 1)})
    for mo in months:
        f = OUT / f"{mo}.csv"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            t = datetime.strptime(line[:16], "%Y-%m-%d %H:%M")
            if a <= t < b:
                o, h, l, c = (float(x) for x in line[17:].split(","))
                out.append([int((t - datetime(1970, 1, 1)).total_seconds()), o, h, l, c])
    out.sort()
    return out


if __name__ == "__main__":
    want = sys.argv[1:] or [m for m in MONTHS if not (OUT / f"{m.replace('.', '-')}.csv").exists()]
    axi_rig.compile_ea("BbBarDump", rig=RIG)
    for m in want:
        print(build(m), flush=True)
