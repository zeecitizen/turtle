"""read_opt.py — read an MT5 optimisation report and rank it honestly.

Written 2026-08-10 after parsing the same XML by hand four times and being caught out
by the encoding twice: MT5 writes some reports UTF-16 and some UTF-8, in the same
folder, from the same terminal. Detect it, do not assume it.

    py monitor/read_opt.py                     # newest report
    py monitor/read_opt.py --file X.xml --top 15

Ranks by the Custom column, which is our OnTester value: the win rate MT5 itself
measured, scored zero for any pass with fewer than InpMinTrades trades or a negative
net profit. That guard matters — without it a single lucky trade returns 100% and wins
the whole optimisation, which is the SL-30 trap Zee found by asking for a 100% config.
"""
import argparse
import glob
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load(path):
    raw = Path(path).read_bytes()
    # MT5 is inconsistent about this; sniff the BOM rather than trusting the extension
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        t = raw.decode("utf-16", errors="ignore")
    else:
        t = raw.decode("utf-8", errors="ignore")
    rows = re.findall(r"<Row[^>]*>(.*?)</Row>", t, re.S)
    cells = lambda r: [c.strip() for c in re.findall(r"<Data[^>]*>(.*?)</Data>", r, re.S)]
    if not rows:
        return [], []
    hdr = cells(rows[0])
    out = []
    for r in rows[1:]:
        c = cells(r)
        if len(c) < len(hdr):
            continue
        d = dict(zip(hdr, c))
        try:
            d["Custom"] = float(d["Custom"])
            d["Profit"] = float(d["Profit"])
            d["Trades"] = int(d["Trades"])
            for k in hdr:
                if not k.startswith("Inp"):
                    continue
                # a swept BOOL input arrives as "true"/"false" and float() throws,
                # which silently discarded every row of a 3,600-pass sweep until it was
                # noticed. Keep bools as 0/1 so they can still be grouped and printed.
                v = str(d[k]).strip().lower()
                d[k] = 1.0 if v == "true" else (0.0 if v == "false" else float(d[k]))
        except Exception:
            continue
        out.append(d)
    return hdr, out


def main(path=None, top=10, min_trades=15):
    if path is None:
        c = glob.glob("mt5/_tester_runs/headless/*.xml")
        if not c:
            print("no optimisation reports found")
            return
        path = max(c, key=os.path.getmtime)
    hdr, data = load(path)
    ins = [h for h in hdr if h.startswith("Inp")]
    print(f"{Path(path).name} — {len(data)} passes\n")
    if not data:
        return
    print(f"   highest win rate  : {max(d['Custom'] for d in data):.1f}%")
    print(f"   passes at 90%+    : {sum(1 for d in data if d['Custom'] >= 90)}")
    print(f"   profitable passes : {sum(1 for d in data if d['Profit'] > 0)} of {len(data)}\n")

    def show(title, rows):
        print(f"   {title}")
        print(f"   {'win%':>6s} {'profit':>9s} {'trd':>4s}  " +
              "  ".join(f"{i[3:]:>9s}" for i in ins))
        for d in rows:
            print(f"   {d['Custom']:6.1f} {d['Profit']:9.2f} {d['Trades']:4d}  " +
                  "  ".join(f"{d[i]:9.2f}" for i in ins))
        print()

    scored = [d for d in data if d["Custom"] > 0]
    show("BY WIN RATE (guarded: >=%d trades and green)" % min_trades,
         sorted(scored, key=lambda x: (-x["Custom"], -x["Profit"]))[:top])
    show("BY PROFIT",
         sorted([d for d in data if d["Trades"] >= min_trades], key=lambda x: -x["Profit"])[:top])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None)
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    main(a.file, a.top)
