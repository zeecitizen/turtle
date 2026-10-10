"""Saad_strategy court (mt5/RULES_EMA_SAAD.md): Axi XAUUSD.pro M5, real ticks, random delay,
$25k, 0.10 lots, 2026-01-01 -> 10-08. Appends to saad_court.jsonl."""
import json, sys
from pathlib import Path
import axi_rig
OUT = Path(__file__).with_name("saad_court.jsonl")
FIX = {"InpLongTp": "1", "InpSlMode": "1", "InpTrendAlign": "true", "InpSessFrom": "10",
       "InpSessTo": "19", "InpMinRangeAtr": "1.0"}          # every v3 suggestion at once
ARMS = {
    "rules":          {},
    "be3_price":      {"InpBeUsd": "3", "InpBeMode": "1"},
    "be3_profit":     {"InpBeUsd": "3", "InpBeMode": "0"},
    "long_any50":     {"InpLong50Above": "false"},
    "longs_only":     {"InpSells": "false"},
    "shorts_only":    {"InpBuys": "false"},
    "pins_only":      {"InpMarubozu": "false"},
    "m15_rules":      {"__period": "M15"},
    # v3.00 variants, one at a time
    "pin_anydir":     {"InpPinAnyDir": "true"},
    "be_1r":          {"InpBeR": "1"},
    "trail2":         {"InpTrailBars": "2"},
    "long_tp_swing":  {"InpLongTp": "1"},
    "sl_atr15":       {"InpSlMode": "1"},
    "sl_swing":       {"InpSlMode": "2"},
    "trend":          {"InpTrendAlign": "true"},
    "sess_8_17":      {"InpSessFrom": "8", "InpSessTo": "17"},
    "sess_10_19":     {"InpSessFrom": "10", "InpSessTo": "19"},
    "size_1atr":      {"InpMinRangeAtr": "1.0"},
    # all together, then with the trail and with any-direction pins
    "fix_all":        dict(FIX),
    "fix_all_trail2": dict(FIX, InpTrailBars="2"),
    "fix_all_be1r":   dict(FIX, InpBeR="1"),
    "fix_all_anydir": dict(FIX, InpPinAnyDir="true"),
    # the two that won ALONE, together, then one extra at a time
    "win":            {"InpTrendAlign": "true", "InpSessFrom": "8", "InpSessTo": "17"},
    "win_be1r":       {"InpTrendAlign": "true", "InpSessFrom": "8", "InpSessTo": "17", "InpBeR": "1"},
    "win_size1":      {"InpTrendAlign": "true", "InpSessFrom": "8", "InpSessTo": "17", "InpMinRangeAtr": "1.0"},
    "win_anydir":     {"InpTrendAlign": "true", "InpSessFrom": "8", "InpSessTo": "17", "InpPinAnyDir": "true"},
    "win_shorts":     {"InpTrendAlign": "true", "InpSessFrom": "8", "InpSessTo": "17", "InpBuys": "false"},
    "win_longs":      {"InpTrendAlign": "true", "InpSessFrom": "8", "InpSessTo": "17", "InpSells": "false"},
    "win_7_18":       {"InpTrendAlign": "true", "InpSessFrom": "7", "InpSessTo": "18"},
    "win_9_16":       {"InpTrendAlign": "true", "InpSessFrom": "9", "InpSessTo": "16"},
    "s817_longs":     {"InpSessFrom": "8", "InpSessTo": "17", "InpSells": "false"},
    "s817_shorts":    {"InpSessFrom": "8", "InpSessTo": "17", "InpBuys": "false"},
    "s7_18":          {"InpSessFrom": "7", "InpSessTo": "18"},
    "s9_16":          {"InpSessFrom": "9", "InpSessTo": "16"},
    "sess_8_17_any":  {"InpSessFrom": "8", "InpSessTo": "17", "InpPinAnyDir": "true"},
}
names = sys.argv[1:] or list(ARMS)
axi_rig.compile_ea("Saad_strategy")
for n in names:
    sets = dict(ARMS[n]); per = sets.pop("__period", "M5")
    r = axi_rig.run("Saad_strategy", "XAUUSD.pro", per, sets, tag=f"saad_{n}")
    r["arm"] = n
    with OUT.open("a") as f: f.write(json.dumps(r) + "\n")
    print(n, r.get("net"), r.get("trades"), r.get("wr"), r.get("pf"), r.get("dd"), r.get("error", ""), flush=True)
