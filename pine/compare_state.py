"""compare_state.py - first candles where the EA's state differs from the indicator's.

    python pine/compare_state.py TV_STATE_CSV [EA_STATE_CSV] [--from "YYYY-MM-DD HH:MM"] [--n 15]
Rows: candle_utc, flags, camel, uhv_utc, trigger. Flags bits: 1 retracement, 2 bull side,
4 rwb, 8 impulse phase, 16 fired, 32 breakout reached, 64 UHV body ok, 128 armed buy,
256 armed sell, 512 trend up, 1024 trend down.
"""
import datetime as dt
import os
import sys

NAMES = ["iR", "lb", "rwb", "ibT", "uF", "uWB", "uWSp", "armB", "armE", "ib", "ibr"]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {sys.argv[i]: sys.argv[i + 1] for i in range(len(sys.argv) - 1) if sys.argv[i].startswith("--")}
args = [a for a in args if a not in opt.values()]
ea_file = args[1] if len(args) > 1 else os.path.join(os.environ["APPDATA"], "MetaQuotes", "Terminal", "Common", "Files", "ea_state.csv")
frm = int(dt.datetime.strptime(opt["--from"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp()) if "--from" in opt else 0
n_show = int(opt.get("--n", 15))
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")


def load(p):
    out = {}
    for line in open(p):
        a = line.strip().split(",")
        if len(a) >= 5 and a[0].isdigit() and a[1] != "":
            out[int(a[0])] = (int(float(a[1])), int(float(a[2])), int(a[3] or 0), round(float(a[4]), 3) if a[4] else None)
    return out


tv, ea = load(args[0]), load(ea_file)
ts = sorted(t for t in set(tv) & set(ea) if t >= frm)
bad = 0
for t in ts:
    a, b = tv[t], ea[t]
    if a == b:
        continue
    bad += 1
    if bad <= n_show:
        fl = [NAMES[i] + ("=TV" if a[0] >> i & 1 else "=EA") for i in range(len(NAMES)) if (a[0] >> i & 1) != (b[0] >> i & 1)]
        extra = []
        if a[1] != b[1]: extra.append(f"camel TV {a[1]} EA {b[1]}")
        if a[2] != b[2]: extra.append(f"UHV TV {f(a[2]) if a[2] else '-'} EA {f(b[2]) if b[2] else '-'}")
        if a[3] != b[3]: extra.append(f"trigger TV {a[3]} EA {b[3]}")
        print(f"{f(t)}  flags only-in: {', '.join(fl) or '-'}  {' | '.join(extra)}")
print(f"compared {len(ts)} candles from {f(ts[0]) if ts else '-'}: {bad} differ")
