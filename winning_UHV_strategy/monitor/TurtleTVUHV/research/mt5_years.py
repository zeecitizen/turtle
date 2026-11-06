"""mt5_years.py - run the 93.8% save (2026-10-25 05-58-25) with and without the v1.38 gates in MT5 on Blueberry's 2023, 2024, 2025 ticks (and 2026 on XAUUSD_BB)
(custom symbol XAUUSD_BB3, built by monitor/strategy_lab/bb3_install.py). Same settings as Turtle TV's Dexter's Lab runs (view EA) but on an M15 chart (MT5_PERIOD; the saves were tuned on 15-minute data),
$100,000, 2 lots, delay none / random. Two rigs in parallel. Results -> research/mt5_years.json (appended, one row per pass).

    py mt5_years.py axi6,axi5 base,vpin 2023,2024,2025 none,random
    py mt5_years.py axi5,axi6 "save:<saved name>" 2023,2024,2025,2026 none,random      # a saved setting (settings/saved/<name>.json)
    py mt5_years.py axi5,axi6 "file:C:/path/to/setting.json" 2026 random             # a saved-setting JSON anywhere (no commas in the path)
"""
import json, os, re, sys, threading, queue, time
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\strategy_lab"); sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import axi_rig

EA = "Saad_strategy_15min_view"
HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved\2026-10-25 05-58-25.json"))
GATES = {
    "base": {},
    "vpin": {"InpMicroVpin": "true", "InpVpinMin": "0.081", "InpVpinFlow": "0.05"},
    "vpin2": {"InpMicroVpin": "true", "InpVpinMin": "0.074", "InpVpinFlow": "0"},
    "hmm4": {"InpMicroHmm": "true", "InpHmmThresh": "0.75"},          # file per held-out year: saad_hmm4_loyo<Y>.csv
    "dtw20": {"InpMicroDtw": "true", "InpDtwThresh": "0.2"},
    "log": {"InpMicroLog": "true", "InpHmmFile": "saad_hmm3.csv"},       # no gate: every entry's scores and boxes -> Common Files saad_micro_log.csv (parity)          # file per held-out year: saad_dtw_loyo<Y>.csv
}
OUT = os.path.join(HERE, "mt5_years.json")
SAVED = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved"
LOCK = threading.Lock()


PERIOD = os.environ.get("MT5_PERIOD", "M15")          # the saved settings were tuned on the 15-minute data: test on an M15 chart
def TAG(g, y, d):                                     # report file name (a ':' made Windows write it as a hidden stream; a file: gate is a whole path)
    g = "file_" + os.path.splitext(os.path.basename(g[5:]))[0] if g.startswith("file:") else g
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", f"yrs_{g}_{y}_{d}_{PERIOD}")[:120]


def job(rig, gate, year, delay):
    dfl = axi_rig.ea_defaults(EA)
    # "save:<name>" = a saved setting; "file:<path>" = a saved-setting JSON anywhere (Research page candidates; no commas in the path);
    # "mlx<thr>+<name>" = that saved setting with the v1.39 ONNX gate (model MLX_loyo<year> in Common Files)
    src_name = gate[5:] if gate.startswith("save:") else (gate.split("+", 1)[1] if gate.startswith("mlx") and "+" in gate else None)
    if gate.startswith("file:"):
        src = json.load(open(gate[5:], encoding="utf-8"))["inputs"]
    else:
        src = json.load(open(os.path.join(SAVED, src_name + ".json"), encoding="utf-8"))["inputs"] if src_name else S["inputs"]
    sets = {k: str(v) for k, v in src.items() if k in dfl}
    sets.update(GATES.get(gate, {})); sets["InpLogCsv"] = "false"
    if gate.startswith("mlx"):
        sets.update({"InpMlFilter": "true", "InpMlThresh": gate[3:].split("+")[0], "InpMlDir": f"MLX_loyo{year}"})
    if gate == "hmm4": sets["InpHmmFile"] = "saad_hmm4.csv" if year == 2026 else f"saad_hmm4_loyo{year}.csv"     # 2026: trained on 2023-25
    if gate == "dtw20": sets["InpDtwFile"] = "saad_dtw_paths.csv" if year == 2026 else f"saad_dtw_loyo{year}.csv"
    sym, to = ("XAUUSD_BB", "2026.10.17") if year == 2026 else ("XAUUSD_BB3", f"{year + 1}.01.01")
    r = axi_rig.run(EA, sym, PERIOD, sets, frm=f"{year}.01.01", to=to, deposit=100000, rig=rig,
                    exec_mode=0 if delay == "none" else -1, tag=TAG(gate, year, delay))
    for _ in range(2):
        if r.get("error") not in ("authorization failed", "no report") and not (not r.get("trades") and (r.get("secs") or 99) < 30):
            break                                     # (an agent "authorization failed (Invalid parameters)" can also come back as an empty report in seconds)
        axi_rig.kill_rig(rig); time.sleep(5)
        r = axi_rig.run(EA, sym, PERIOD, sets, frm=f"{year}.01.01", to=to, deposit=100000, rig=rig,
                        exec_mode=0 if delay == "none" else -1, tag=TAG(gate, year, delay))
    row = {"gate": gate, "year": year, "delay": delay, "period": PERIOD, **{k: r.get(k) for k in ("net", "trades", "pf", "dd", "error", "trade_stats", "secs", "trade_days", "wr")}}
    with LOCK:
        rows = json.load(open(OUT)) if os.path.exists(OUT) else []
        rows = [x for x in rows if not (x["gate"] == gate and x["year"] == year and x["delay"] == delay and x.get("period", "M1") == PERIOD)] + [row]
        json.dump(rows, open(OUT, "w"), indent=1)
    ts = row.get("trade_stats") or {}
    print(json.dumps({**{k: row.get(k) for k in ("gate", "year", "delay", "period", "net", "trades", "pf", "dd", "error", "secs")}, "wins": ts.get("wins"), "n": ts.get("n")}), flush=True)


if __name__ == "__main__":
    rigs, gates, years, delays = (a.split(",") for a in sys.argv[1:5])
    q = queue.Queue()
    for y in years:
        for d in delays:
            for g in gates:
                q.put((g, int(y), d))
    for rig in rigs:
        axi_rig.compile_ea(EA, rig=rig)

    def worker(rig):
        while True:
            try:
                g, y, d = q.get_nowait()
            except queue.Empty:
                return
            job(rig, g, y, d)
    th = [threading.Thread(target=worker, args=(r,)) for r in rigs]
    [t.start() for t in th]; [t.join() for t in th]
