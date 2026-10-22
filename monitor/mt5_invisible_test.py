"""mt5_invisible_test.py - run one Strategy Tester test of an EA in an invisible MT5 window (no window, no taskbar button).

   py monitor/mt5_invisible_test.py Saad_strategy_15min_view XAUUSD_BB M1 2026.01.01 2026.10.17

Uses the Turtle TV test rig (the separate install, never the live terminal), writes the MT5 report to its reports folder and prints
the net, trades and profit factor. Same engine as the Check in MT5 button: nothing simulated."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import axi_rig  # noqa: E402


def main(ea="Saad_strategy_15min_view", symbol="XAUUSD_BB", period="M1", frm="2026.01.01", to="2026.10.17", sets=None):
    tag = f"invisible_{ea}_{period}"
    res = axi_rig.run(ea, symbol, period, sets or {}, frm=frm, to=to, deposit=100000, rig="axi7", tag=tag)
    print({k: res.get(k) for k in ("net", "pf", "trades", "wr", "dd", "error")})
    return res


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a) if a else main()
