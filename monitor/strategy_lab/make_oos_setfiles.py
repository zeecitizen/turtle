"""make_oos_setfiles.py — write the two .set files Zee needs to run the out-of-sample test
himself, in his own terminal, where the Sept 17-28 tick history already lives.

WHY HE HAS TO RUN IT. The rig's demo login is dead, so the rig cannot download tick history and
its bar archive stops at 2026-09-16. Its September TICK archive was extended from the live
terminal's copy, but MT5 also needs the BAR archive (.hcc) to cover the range - the out-of-sample
run saw 32 bars - and replacing the rig's 2026.hcc would destroy Feb-Jul, which is irreversible
and was correctly refused. His live terminal has both, for XAUUSD.pi, already downloaded.

WHAT THE TWO FILES ARE. Identical in every one of ~50 inputs except InpRetraceFix. That is the
whole experiment: the same machine, the same unseen days, with and without the one repair.
Running only the candidate would be worthless - if Sept 17-28 is simply easy tape, the control
wins there too, and without it in the same table that is invisible.

  ZeeUHV_Diamond_OOS_FIXED.set    InpRetraceFix = true   <- the candidate
  ZeeUHV_Diamond_OOS_CONTROL.set  InpRetraceFix = false  <- the control, run BOTH
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import diamond_lab as D

CAMEL = {"InpTrendMode": "1", "InpHighTest": "1"}
LIVE_TESTER = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal"
                   r"/DBE9B8B347D025DD139E103EE3B63FD8/MQL5/Profiles/Tester")
REPO = Path(__file__).parent.parent.parent / "mt5"


def write(name: str, fix: str) -> Path:
    cfg = dict(D.SHIPPED)
    cfg.update(CAMEL)
    cfg["InpRetraceFix"] = fix
    # 0.10 lots and a well-funded deposit: the question is a RATE, and a run that blows the
    # account stops early and reports a net censored at the balance.
    cfg["InpLots"] = "0.10"
    lines = []
    for k, v in cfg.items():
        lines.append("%s=%s" % (k, v))
        lines.append("%s,F=0" % k)          # F=0: not part of an optimisation sweep
    p = REPO / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-16")
    return p


def main() -> None:
    made = []
    for name, fix in (("ZeeUHV_Diamond_OOS_FIXED.set", "true"),
                      ("ZeeUHV_Diamond_OOS_CONTROL.set", "false")):
        p = write(name, fix)
        made.append(p)
        print("wrote %s" % p)
        if LIVE_TESTER.is_dir():
            try:
                shutil.copy2(p, LIVE_TESTER / name)
                print("   and into his Tester profile: %s" % (LIVE_TESTER / name))
            except Exception as e:
                print("   could not place it in the Tester profile (%s) - load it by path" % e)

    print("""
HOW TO RUN IT (about two minutes of clicks, twice)

  1. In MT5, Ctrl+R to open the Strategy Tester.
  2. Expert:   ZeeUHV_Diamond          <- must read v1.24 in the Journal when it starts
     Symbol:   XAUUSD.pi
     Period:   M1
     Modelling: "Every tick based on real ticks"      <- NOT "1 minute OHLC"
     Dates:    2026.09.17  ->  2026.09.28
     Deposit:  200000        Leverage: 1:500
     Delay:    163 ms  (or "Random delay")
  3. Inputs tab -> Load -> ZeeUHV_Diamond_OOS_FIXED.set -> Start.
  4. When it finishes: Inputs tab -> Load -> ZeeUHV_Diamond_OOS_CONTROL.set -> Start again.
  5. Send me both results, or just the two lines: Total Net Profit, Total Trades, Profit Trades.

WHAT DECIDES IT. The fix must beat the control ON THOSE DAYS. If both win, Sept 17-28 was easy
tape and the fix is unproven. If the control loses and the fix wins, the repair is real.
""")


if __name__ == "__main__":
    main()
