"""compare_signals.py - EA signals vs the indicator's signals, candle by candle.

    python pine/compare_signals.py INDICATOR_CSV [EA_CSV] [--from "YYYY-MM-DD HH:MM"]
Both files: entry_candle_utc, dir, uhv_candle_utc, entry. Prints matches and every difference.
"""
import datetime as dt
import os
import sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
frm = None
if "--from" in sys.argv:
    frm = int(dt.datetime.strptime(sys.argv[sys.argv.index("--from") + 1], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp())
    args = [a for a in args if a != sys.argv[sys.argv.index("--from") + 1]]
ea_file = args[1] if len(args) > 1 else os.path.join(os.environ["APPDATA"], "MetaQuotes", "Terminal", "Common", "Files", "ea_signals.csv")
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")


def load(p):
    out = {}
    for line in open(p):
        a = line.strip().split(",")
        if len(a) >= 4 and a[0].lstrip("-").isdigit():
            out[int(a[0])] = (int(a[1]), int(a[2]), float(a[3]))
    return out


tv, ea = load(args[0]), load(ea_file)
hi = max(ea) if ea else 0
lo = frm or 0
tv = {t: v for t, v in tv.items() if lo <= t <= hi}
ea = {t: v for t, v in ea.items() if lo <= t <= hi}
both = set(tv) & set(ea)
same = [t for t in both if tv[t][0] == ea[t][0] and tv[t][1] == ea[t][1] and abs(tv[t][2] - ea[t][2]) < 0.006]
print(f"window {f(lo) if lo else 'all'} -> {f(hi)} | indicator {len(tv)} | EA {len(ea)} | identical {len(same)} "
      f"| same candle, different details {len(both) - len(same)} | only indicator {len(set(tv) - set(ea))} | only EA {len(set(ea) - set(tv))}")
for t in sorted(set(tv) | set(ea)):
    if t in same:
        continue
    print(f"  {f(t)}  indicator {tv.get(t)}  EA {ea.get(t)}")
