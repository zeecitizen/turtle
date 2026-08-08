"""measure_scale.py — how much bigger is a Bitcoin minute than a gold minute?
Writes btc_scale.txt, the single constant that converts the whole gold rulebook.
Run once after the BTC bridge has filled btc_m1.csv."""
import csv, statistics, sys
from pathlib import Path
C = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")


def med_range(p):
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    rs = [float(r["high"]) - float(r["low"]) for r in rows if r["high"]]
    return statistics.median(rs) if rs else 0.0


btc = med_range(C / "btc_m1.csv")
xau = med_range(C / "oanda_m1.csv")
if not btc or not xau:
    print("need both feeds running"); sys.exit(1)
scale = round(btc / xau, 1)
(Path(__file__).parent / "btc_scale.txt").write_text(str(scale))
print(f"BTC median M1 range {btc:.2f} · XAU {xau:.2f} -> SCALE {scale}")
