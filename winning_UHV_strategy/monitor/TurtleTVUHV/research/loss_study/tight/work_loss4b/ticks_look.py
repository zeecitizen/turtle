"""print the PrimeXBT ticks around a trade's decision tick (study only)"""
import json, os, sys, datetime as dt
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
import numpy as np
import uhv_ticks
TK = uhv_ticks.load()
T, B, A = TK["t"], TK["bid"].astype(float), TK["ask"].astype(float)
tr = {t["id"]: t for t in json.load(open(os.path.join(os.path.dirname(__file__), "..", "trades_tight.json"), encoding="utf-8"))}
P = 1e-4
for tid in sys.argv[1:]:
    t = tr[tid]; td = t["t_dec"]; s = t["side"]; lev = t["level"]
    j = int(np.searchsorted(T, td - 1e-4))
    print(f"=== {tid} {'WIN' if t['win'] else 'LOSS'} level {lev} side {s} fill {t['fill']:.5f}  target {'bid>=' if s>0 else 'ask<='}{t['fill']+s*0.00001:.5f}")
    for i in range(max(0, j - 25), j + 30):
        rel = T[i] - td
        mark = " <== BREAK" if i == j else ""
        print(f"  {rel:+8.2f}s bid {B[i]:.5f} ask {A[i]:.5f} sp {(A[i]-B[i])/P:4.1f}  bid-lev {(B[i]-lev)/P:+5.1f}{mark}")
