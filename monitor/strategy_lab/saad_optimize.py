"""saad_optimize.py - MT5's own genetic optimizer on Saad_strategy_1min, Blueberry real ticks, with a forward test.

Zee 2026-10-17: "we can use the MT5's own strategy optimizer to find the best settings over the year" /
"the first thing i need you to optimize for is the settings for Entry position in the range" /
"optimize specifically for the highest win rate" (OnTester, InpOptScore 1).

    py saad_optimize.py boxes            # run (hours) -> reports/opt_boxes.xml + opt_boxes.forward.xml in the rig
    py saad_optimize.py boxes --read     # only read the finished results

* Model 4 (real ticks) only: "1 minute OHLC" gave -$2.14M / WR 51% where real ticks gave -$437k / WR 71% on the same
  settings - the EA's stops live inside a minute and OHLC invents those prices.
* Optimised on Jan 1 - Jun 30; MT5 then runs the results on Jul 1 - Oct 17 (ForwardMode 4), months the optimizer never saw.
  A setting is only interesting if the forward months agree.
* Base settings = Zee's TradingView chart (zee_sets.json), InpBarSource 0 (MT5's own candles), deposit $10M so no pass is
  cut short by a blown account (the score is a ratio, the deposit does not change it).
* Execution delay 0 while searching (same numbers every pass); the winners are confirmed afterwards with random delay.
"""
import json
import re
import subprocess
import sys
import time
import html as htmlmod
from pathlib import Path

import axi_rig

RIG = "axi"                     # C:/mt5_rig_axi - one terminal, its own tester agents use every core
SETS = Path(__file__).with_name("saad_opt_base_sets.json")
EA = "Saad_strategy_1min"
FROM, FORWARD, TO = "2026.01.01", "2026.07.01", "2026.10.18"

# what each job optimises: input -> (start, step, stop); bools -> None (true/false)
JOBS = {
    # Zee 2026-10-17: "on whole year 2026 optimize for what is the best combination to use for EMAs. currently set at 9/50"
    # every combination (Optimization 1 = complete), whole Jan 1 - Oct 17, his 15-min chart settings otherwise
    "ema": {
        "sets": "saad_opt_base_sets_m15.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100"},
        "opt": {"InpEmaFast": (3, 1, 20), "InpEmaSlow": (20, 5, 100)},
    },
    # Zee 2026-10-17: "InpWickMin. i want you to run the optimizer for this single setting." (chart settings with EMA 14/70)
    "wick": {
        "sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100"},
        "opt": {"InpWickMin": (0.10, 0.05, 0.90)},
    },
    # Zee 2026-10-17: "ok next inpbodymax"
    "body": {
        "sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100"},
        "opt": {"InpBodyMax": (0.20, 0.05, 1.00)},
    },
    # Zee 2026-10-17: "ok now inpnosemax"
    "nose": {
        "sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100"},
        "opt": {"InpNoseMax": (0.0, 0.025, 0.50)},
    },
    # Zee 2026-10-17: the BUY range lookback ("BUY · how many recent candles make the range")
    "lookb": {
        "sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100"},
        "opt": {"InpRangeLook": (3, 1, 30)},
    },
    # Zee 2026-10-17: the SELL range lookback ("SELL · how many recent candles make the range")
    "looks": {
        "sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100"},
        "opt": {"InpRangeLookS": (3, 1, 30)},
    },
    # Zee 2026-10-17: "next test diff take profits/methods" - each TP1 method over its own range
    "tp_fib": {"sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100", "InpTpMode": "2"},
        "opt": {"InpTpFibPct": (100, 10, 300)}},
    "tp_fix": {"sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100", "InpTpMode": "1"},
        "opt": {"InpTpFixUsdB": (1, 1, 10), "InpTpFixUsdS": (1, 1, 10)}},
    "tp_part": {"sets": "saad_opt_base_sets_now.json", "period": "M15", "algo": 1, "forward": False,
        "fixed": {"InpOptScore": "0", "InpOptMinTrades": "100", "InpTpMode": "3", "InpTpPartPct": "0.5"},
        "opt": {"InpTpFixUsdB": (1, 1, 5), "InpTpFixUsdS": (1, 1, 5), "InpTpPartTrailUsd": (1, 1, 4)}},
    "boxes": {
        "fixed": {"InpBoxInputs": "true", "InpOptScore": "1", "InpOptMinTrades": "3000"},
        "opt": {**{f"InpB{i:02d}": None for i in range(21)}, **{f"InpS{i:02d}": None for i in range(21)},
                "InpRangeLook": (3, 2, 15), "InpRangeLookS": (3, 2, 15), "InpBandPauseBars": (0, 1, 5)},
    },
}


def tester_inputs(base, job):
    lines = []
    for k, v in base.items():
        if k in job["opt"]:
            rng = job["opt"][k]
            if rng is None:
                lines.append(f"{k}={v}||false||0||true||Y\r\n")
            else:
                lines.append(f"{k}={v}||{rng[0]}||{rng[1]}||{rng[2]}||Y\r\n")
        else:
            lines.append(axi_rig.ini_input(k, v))
    return "".join(lines)


def start(name):
    job = JOBS[name]
    base = axi_rig.ea_defaults(EA)
    base.update(json.loads(Path(__file__).with_name(job.get("sets", SETS.name)).read_text(encoding="utf-8")))
    base.update(job["fixed"])
    for i in range(21):                     # the boxes start from Zee's own ticks (the genetic search starts random anyway)
        base[f"InpB{i:02d}"] = "true" if base["InpBandsB"][i] == "1" else "false"
        base[f"InpS{i:02d}"] = "true" if base["InpBandsS"][i] == "1" else "false"
    R = axi_rig._R(RIG)
    axi_rig.kill_rig(RIG)
    axi_rig.compile_ea(EA, rig=RIG)
    fwd = f"ForwardMode=4\r\nForwardDate={FORWARD}\r\n" if job.get("forward", True) else "ForwardMode=0\r\n"
    ini = (f"[Tester]\r\nExpert={EA}\r\nSymbol=XAUUSD_BB\r\nPeriod={job.get('period', 'M1')}\r\nModel=4\r\n"
           f"FromDate={FROM}\r\nToDate={TO}\r\n{fwd}"
           f"Deposit=10000000\r\nCurrency=USD\r\nLeverage=1:400\r\nExecutionMode=0\r\n"
           f"Optimization={job.get('algo', 2)}\r\nOptimizationCriterion=6\r\n"
           f"Report=reports\\opt_{name}\r\nReplaceReport=1\r\nShutdownTerminal=1\r\nVisual=0\r\n"
           f"[TesterInputs]\r\n{tester_inputs(base, job)}")
    (R / "reports").mkdir(exist_ok=True)
    (R / f"opt_{name}.ini").write_text(ini, encoding="utf-16")
    axi_rig.prune_logs(rig=R)
    t0 = time.time()
    print(f"[opt] {name}: {len(job['opt'])} inputs, {FROM} - {FORWARD} optimise, forward to {TO} - started {time.strftime('%H:%M')}", flush=True)
    subprocess.run([str(R / "terminal64.exe"), "/portable", f"/config:{R / f'opt_{name}.ini'}"], startupinfo=axi_rig._quiet())
    print(f"[opt] finished in {(time.time() - t0) / 60:.0f} min", flush=True)


def _rows(path):
    """Rows of an MT5 optimisation XML (Excel 2003 XML) as dicts."""
    t = Path(path).read_text(encoding="utf-8", errors="ignore")
    rows = []
    for r in re.findall(r"<Row[^>]*>(.*?)</Row>", t, re.S):
        rows.append([htmlmod.unescape(x) for x in re.findall(r"<Data[^>]*>(.*?)</Data>", r, re.S)])
    head, out = rows[0], []
    for r in rows[1:]:
        out.append(dict(zip(head, r)))
    return out


def read(name, top=25):
    R = axi_rig._R(RIG)
    back = {r["Pass"]: r for r in _rows(R / "reports" / f"opt_{name}.xml")}
    ff = R / "reports" / f"opt_{name}.forward.xml"
    fwd = _rows(ff) if ff.exists() else list(back.values())
    print(f"[opt] {len(back)} passes optimised, {len(fwd)} forward")
    keys = list(JOBS[name]["opt"])
    out = []
    for f in fwd:
        b = back.get(f["Pass"], {})
        out.append({"pass": f["Pass"], "fwd": f, "back": b,
                    "inputs": {k: f.get(k, b.get(k)) for k in keys}})
    Path(__file__).with_name(f"opt_{name}_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    name = sys.argv[1]
    if "--read" not in sys.argv:
        start(name)
    for r in read(name)[:25]:
        print(r["pass"], {k: r["fwd"].get(k) for k in ("Forward Result", "Back Result", "Profit", "Trades", "Equity DD %")})
