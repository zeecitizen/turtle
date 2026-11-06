"""make_final_setfiles.py — the three candidates that need OUT-OF-SAMPLE proof, 2026-09-29.

Zee: "can u compile something concrete so i can run on blueberry the final tests u want? at the
best config you have?"

WHY THREE AND NOT ONE. All three scored well on 2026.08.06-09.16 — but that is the window every
one of today's ~40 configurations was tuned on, so all three are in-sample only. Today already
showed once what that is worth: the retracement fix scored 89% in-sample and 66.7% on unseen
tape. Running only the best-looking one would repeat exactly that mistake, because the
best-looking one is also the most likely to be the luckiest.

The three differ in ONE dimension - how much they open the two gates the funnel exposed:

  A  humps 3, no sweep   97% / +$1,881 / 244   the highest win rate, his own stated hump model
  B  humps 0, no sweep   94% / +$2,490 / 374   the most money and the most trades
  C  humps 3, sweep ON   96% / +$1,460 / 210   conservative: keeps the sweep law we added in v1.12

Every other input is identical across all three, and identical to what he trades today: his
5-pip structural stop (InpStructStop 0.50), his $1 target, his 20-minute clock, OANDA volume
strict, CamelTrend. NO GEOMETRY WAS CHANGED ANYWHERE TODAY - the entire gain is detection and
gating.

THE CONTROL IS ALREADY RUN. ReportTester-5116967_d.html is the shipped configuration on the
same unseen days: 63.6%, -$534.10, 22 setups. Every candidate below must beat that, on those
days, or it does not ship.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import diamond_lab as D

CAMEL = {"InpTrendMode": "1", "InpHighTest": "1"}
BASE = {"InpRetraceFix": "true", "InpPivot": "3", "InpLots": "0.10"}
LIVE = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
            r"/DBE9B8B347D025DD139E103EE3B63FD8/MQL5/Profiles/Tester")
REPO = Path(__file__).parent.parent.parent / "mt5"

CANDIDATES = [
    ("A", {"InpMaxHumps": "3", "InpReqLaws": "0"}, "97% / +$1,881 / 244 tr", "highest win rate"),
    ("B", {"InpMaxHumps": "0", "InpReqLaws": "0"}, "94% / +$2,490 / 374 tr", "most money, most trades"),
    ("C", {"InpMaxHumps": "3", "InpReqLaws": "4"}, "96% / +$1,460 / 210 tr", "keeps the sweep law"),
]


def main() -> None:
    print("Written into your Tester profile (%s):\n" % LIVE)
    for tag, over, insample, why in CANDIDATES:
        cfg = dict(D.SHIPPED)
        cfg.update(CAMEL)
        cfg.update(BASE)
        cfg.update(over)
        lines = []
        for k, v in cfg.items():
            lines.append("%s=%s" % (k, v))
            lines.append("%s,F=0" % k)
        name = "ZeeUHV_Diamond_FINAL_%s.set" % tag
        p = REPO / name
        p.write_text("\n".join(lines) + "\n", encoding="utf-16")
        try:
            shutil.copy2(p, LIVE / name)
        except Exception as e:
            print("  could not place %s in the Tester profile (%s)" % (name, e))
        print("  %-34s humps=%-2s sweep=%-3s   in-sample %-24s %s"
              % (name, over["InpMaxHumps"],
                 "ON" if over["InpReqLaws"] == "4" else "off", insample, why))

    print("""
RUN EACH ONE EXACTLY LIKE THIS
------------------------------
  Expert     ZeeUHV_Diamond        (Journal must say v1.26)
  Symbol     XAUUSD.pi
  Period     M1
  Modelling  Every tick based on real ticks      <- NOT "1 minute OHLC"
  Dates      2026.09.17  ->  2026.09.28          <- the UNSEEN days
  Deposit    200000     Leverage 1:500     Delay 163 ms
  Optimization  OFF

  Inputs -> Load -> ZeeUHV_Diamond_FINAL_A.set -> Start   -> save report as _A
  Inputs -> Load -> ZeeUHV_Diamond_FINAL_B.set -> Start   -> save report as _B
  Inputs -> Load -> ZeeUHV_Diamond_FINAL_C.set -> Start   -> save report as _C

  Save all three into mt5/_tester_runs/reports/29 sept/

THE BAR THEY MUST CLEAR
-----------------------
  The control on those same days is already measured: report _d, the shipped configuration,
  63.6% win rate and -$534.10 over 22 setups. A candidate that cannot beat THAT on THOSE days
  has not earned a live chart, whatever it scored in-sample.

  Deposit 200000 is not optional: at $5,000 the 10% gold margin rate blocks whole setups
  (6 taken instead of 12), so a small deposit measures the account, not the strategy.
""")


if __name__ == "__main__":
    main()
