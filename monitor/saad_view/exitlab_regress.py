"""exitlab_regress.py - the engine must not move while the Exit Lab is off.

   py monitor/saad_view/exitlab_regress.py save     -> fingerprints of a set of runs (before an engine change)
   py monitor/saad_view/exitlab_regress.py check    -> the same runs again: every trade must be identical (columns 0-14)

Configs cover both datasets, every exit mode, the entry modes, stand-aside, the chart's rules and TradingView's candles."""
import os
import sys
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402
import sim  # noqa: E402

OUT = Path(__file__).parent / "simdata" / "exitlab_regress.npz"
ALL_ON = "1" * 21
CONFIGS = [
    ("year", "ea", {}),
    ("m15", "ea", {}),
    ("year", "ea", {"InpExitMode": "2"}),
    ("m15", "ea", {"InpExitMode": "2"}),
    ("year", "ea", {"InpExitMode": "0"}),
    ("m15", "ea", {"InpExitMode": "0", "InpBandOff": "0"}),
    ("year", "ea", {"InpExitMode": "0", "InpBandsB": ALL_ON, "InpBandsS": ALL_ON, "InpAdxMin": "0"}),
    ("year", "ea", {"InpEntryMode": "1"}),
    ("year", "ea", {"InpEntryMode": "2"}),
    ("year", "ea", {"InpMaxPos": "3"}),
    ("year", "ea", {"InpBandOff": "0"}),
    ("year", "chart", {}),
    ("tv", "chart_blind", {}),
    ("year", "ea", {"InpCoolBars": "4", "InpDayLossUsd": "3000"}),
    ("year", "ea", {"InpSlMode": "0", "InpSlPips": "15", "InpMaxRiskUsd": "0"}),
]


def runs():
    res = {}
    for i, (ds, mode, sets) in enumerate(CONFIGS):
        tr = sim.simulate(server.full_inputs(sets), ds=ds, **server.MODES[mode])[0]
        res[f"c{i}"] = tr[:, :15].copy()
    return res


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "check"
    r = runs()
    if what == "save":
        np.savez_compressed(OUT, **r)
        for i, c in enumerate(CONFIGS):
            t = r[f"c{i}"]
            print(f"saved {c}: {int((t[:, 10] == 0).sum())} trades, net {t[t[:, 10] == 0, 6].sum():,.2f}")
    else:
        old = np.load(OUT)
        bad = 0
        for i, c in enumerate(CONFIGS):
            a, b = old[f"c{i}"], r[f"c{i}"]
            same = a.shape == b.shape and np.array_equal(a, b)
            bad += not same
            print(("SAME   " if same else "CHANGED"), c, f"{int((b[:, 10] == 0).sum())} trades, net {b[b[:, 10] == 0, 6].sum():,.2f}",
                  "" if same else f"(was {int((a[:, 10] == 0).sum())} trades, net {a[a[:, 10] == 0, 6].sum():,.2f})")
        print("ALL IDENTICAL" if not bad else f"{bad} CONFIG(S) CHANGED")
        sys.exit(1 if bad else 0)
