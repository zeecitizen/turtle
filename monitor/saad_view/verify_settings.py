"""verify_settings.py - Zee 2026-10-20: "verify that each setting is implemented correctly on the turtle tv and that it works and will be carried
forward to MT5. basically proof reading". Every EA input moved one step: (1) the Turtle TV Tester's result vs the base, (2) the value read back
from MT5's own report (it arrived), (3) MT5's result for the same change. Old-exit inputs are moved on top of InpExitMode 0 (where they act).
6 rigs in parallel (axi2-axi7). Writes simdata/verify_settings.json."""
import json, queue, re, sys, threading, time, html
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
sys.stdout.reconfigure(encoding="utf-8")
import sim, sim_full, axi_rig
EA = "Saad_strategy_15min"
dfl = axi_rig.ea_defaults(EA)
V123 = {"InpExitMode": "0", "InpBandsB": "1" * 21, "InpBandsS": "1" * 21, "InpAdxMin": "0"}
EXIT0 = {"InpLongExit", "InpLongTpPips", "InpSwingPivot", "InpSwingLook", "InpShortTpPips", "InpMinTpPips", "InpMaxTpPips", "InpLongTouch",
         "InpLongTrailUsd", "InpLongResTp", "InpLongResTp1", "InpResTp1Ride", "InpShortTouch", "InpTrailStepUsd", "InpShortTrailUsd", "InpBeTpPct",
         "InpTrail", "InpTrailSide", "InpRide", "InpTrailMode", "InpTrailN", "InpTrailPips", "InpTrailAtr", "InpTrailStart", "InpRideLock", "InpLockPips",
         "InpPartialPct", "InpTp1Be", "InpFixTpPips", "InpLockAtUsd", "InpLockUsd", "InpMaxBars"}
SKIP = {"InpMagicNumber", "InpVerbose", "InpDraw", "InpLog", "InpLogCsv", "InpShowEmas", "InpDrawSkips", "InpOptScore", "InpOptMinTrades", "InpPipPts",
        "InpModBackoffSec"}
TEST = {"InpEmaFast": "14", "InpEmaSlow": "36", "InpWickMin": "0.4", "InpBodyMax": "0.5", "InpNoseMax": "0.25", "InpPinDir": "true", "InpPinColor": "true",
        "InpUsePin": "false", "InpMarubozu": "false", "InpMaruBody": "0.6", "InpHammer": "false", "InpStar": "false", "InpHamRatio": "3", "InpHamNose": "0.4",
        "InpMinRangeAtr": "0.7", "InpLongRule": "0", "InpShortLine": "2", "InpTouchMode": "1", "InpTouchPips": "2", "InpLongExitAbove": "true",
        "InpBreakBars": "2", "InpBreakPips": "2", "InpTrigBid": "false", "InpSlPips": "40", "InpSlMode": "0", "InpSlAtrMult": "1.3", "InpSlUsd": "6",
        "InpMaxRiskUsd": "15", "InpSessFrom": "8", "InpSessTo": "22", "InpAdxMin": "25", "InpAdxPeriod": "20", "InpAtrMinUsd": "4", "InpAtrMaxUsd": "12",
        "InpRangeLook": "10", "InpRangeLookS": "10", "InpBandOff": "0", "InpExitMode": "2", "InpCloseLossMins": "0", "InpLots": "1", "InpBuys": "false",
        "InpSells": "false", "InpGapCancel": "false", "InpBandsB": "1" * 21, "InpBandsS": "1" * 21,
        "InpLongExit": "0", "InpLongTpPips": "10", "InpSwingPivot": "2", "InpSwingLook": "60", "InpShortTpPips": "10", "InpMinTpPips": "15", "InpMaxTpPips": "150",
        "InpBeUsd": "5", "InpNoNewMins": "60", "InpLongTouch": "0", "InpLongTrailUsd": "4", "InpLongResTp": "false", "InpLongResTp1": "true",
        "InpResTp1Ride": "false", "InpShortTouch": "0", "InpTrailStepUsd": "1", "InpShortTrailUsd": "4", "InpBeTpPct": "0.5", "InpTrail": "false",
        "InpTrailSide": "0", "InpRide": "false", "InpTrailMode": "0", "InpTrailN": "4", "InpTrailPips": "40", "InpTrailAtr": "3", "InpTrailStart": "50",
        "InpRideLock": "1", "InpLockPips": "5", "InpChopEr": "0.15", "InpChopErLook": "10", "InpHtfMin": "60", "InpHtfEma": "50", "InpTrendAlign": "true",
        "InpPriceSide": "true", "InpSlopePips": "5", "InpSlopeLook": "8", "InpEmaGapPips": "20", "InpMaxSpreadPts": "25", "InpSkipDow": "5",
        "InpLockAtUsd": "8", "InpLockUsd": "2", "InpFixTpPips": "60", "InpMaxBars": "8", "InpCoolBars": "4", "InpMaxPos": "2", "InpReplace": "true",
        "InpExtraDir": "1", "InpDayLossUsd": "3000", "InpDayTargetUsd": "5000", "InpEntryMode": "1", "InpRetestFrac": "0.3", "InpRetestBars": "3",
        "InpSweepPips": "3", "InpSweepBars": "4", "InpSweepEntry": "1", "InpSweepSlPips": "15", "InpPartialPct": "0", "InpTp1Be": "false", "InpRiskPct": "1",
        "InpMinLotRiskPct": "0.5", "InpMaxLots": "1", "InpDayLossPct": "2"}
NEED = {"InpRetestFrac": {"InpEntryMode": "1"}, "InpRetestBars": {"InpEntryMode": "1"}, "InpSweepPips": {"InpEntryMode": "2"}, "InpSweepBars": {"InpEntryMode": "2"},
        "InpSweepEntry": {"InpEntryMode": "2"}, "InpSweepSlPips": {"InpEntryMode": "2"}, "InpSlPips": {"InpSlMode": "0"}, "InpSlUsd": {"InpSlMode": "2"},
        "InpHtfEma": {"InpHtfMin": "60"}, "InpChopErLook": {"InpChopEr": "0.11"}, "InpSlopeLook": {"InpSlopePips": "5"}, "InpLockUsd": {"InpLockAtUsd": "8"},
        "InpMinLotRiskPct": {"InpRiskPct": "0.2"}, "InpMaxLots": {"InpRiskPct": "1"}, "InpExtraDir": {"InpMaxPos": "2"}, "InpTrailN": {"InpTrailMode": "0"},
        "InpTrailPips": {"InpTrailMode": "1"}, "InpTrailStart": {"InpRide": "false"}, "InpLockPips": {"InpLongTouch": "0", "InpShortTouch": "0", "InpLongExit": "0"}}
jobs = []
for name in [n for n in dfl if n not in SKIP and n.startswith("Inp")]:
    if name not in TEST:
        continue
    base = dict(V123) if name in EXIT0 else {}
    base.update(NEED.get(name, {}))
    jobs.append((name, base, dict(base, **{name: TEST[name]})))
print(len(jobs), "settings to check")
sim_rows = {}
for name, base, chg in jobs:
    a = sim.score(sim.simulate(dict(dfl, **base))[0], 1); b = sim.score(sim.simulate(dict(dfl, **chg))[0], 1)
    sim_rows[name] = (a, b)
RIGS = ["axi2", "axi3", "axi4", "axi5", "axi6", "axi7"]
q = queue.Queue()
for j in jobs:
    q.put(j)
mt5_base, res, lock = {}, {}, threading.Lock()


def mrun(rig, sets, tag):
    for _ in range(3):
        r = axi_rig.run(EA, "XAUUSD_BB", "M15", dict(sets, InpLogCsv="false"), frm="2026.01.01", to="2026.10.17", deposit=100000, rig=rig, tag=tag, exec_mode=0)
        if r.get("error") not in ("authorization failed", "no report"):
            return r
        axi_rig.kill_rig(rig); time.sleep(4)
    return r


def echoed(rig, tag, name):
    t = (Path(axi_rig._R(rig)) / "reports" / f"{tag}.htm").read_text(encoding="utf-16", errors="ignore")
    m = re.search(rf"{name}=([^<\s]*)", html.unescape(t))
    return m.group(1) if m else None


def worker(rig):
    axi_rig.kill_rig(rig); axi_rig.compile_ea(EA, rig=rig)
    while True:
        try:
            name, base, chg = q.get_nowait()
        except queue.Empty:
            return
        key = json.dumps(base, sort_keys=True)
        with lock:
            need_base = key not in mt5_base
            if need_base:
                mt5_base[key] = None
        if need_base:
            rb = mrun(rig, base, f"vs_{rig}")
            with lock:
                mt5_base[key] = rb
        while mt5_base[key] is None:
            time.sleep(2)
        r = mrun(rig, chg, f"vs_{rig}")
        ec = echoed(rig, f"vs_{rig}", name)
        with lock:
            res[name] = {"base": base, "value": TEST[name], "mt5": {k: r.get(k) for k in ("net", "pf", "trades")}, "mt5_base": {k: mt5_base[key].get(k) for k in ("net", "pf", "trades")},
                         "echo": ec, "sim": sim_rows[name][1], "sim_base": sim_rows[name][0]}
            print(f"{name:20} -> {TEST[name][:8]:8} MT5 got '{ec}' | sim {sim_rows[name][0]['net']:+10,.0f} -> {sim_rows[name][1]['net']:+10,.0f} | "
                  f"MT5 {mt5_base[key].get('net'):+10,.0f} -> {r.get('net'):+10,.0f}", flush=True)


ths = [threading.Thread(target=worker, args=(g,)) for g in RIGS]
for th in ths:
    th.start(); time.sleep(6)
for th in ths:
    th.join()
(HERE / "simdata" / "verify_settings.json").write_text(json.dumps(res, indent=1))
print("DONE")
