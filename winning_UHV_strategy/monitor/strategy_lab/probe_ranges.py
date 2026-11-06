"""Average M5 range per market on Axi (1-minute OHLC model, no tick download), to set
VSISA InpPtsScale = market range / gold range. Appends to probe_ranges.txt."""
import re, sys, axi_rig
syms = sys.argv[1:]
axi_rig.compile_ea("RangeProbe")
for s in syms:
    axi_rig.run("RangeProbe", s, "M5", {}, tag="probe_" + re.sub(r"\W", "_", s), model=1)
    txt = ""
    for log in (axi_rig.RIG / "Tester").glob("Agent-*/logs/*.log"):
        txt += log.read_text(encoding="utf-16", errors="ignore")
    hits = [h for h in re.findall(r"RANGEPROBE [^\r\n]*", txt) if f" {s} " in h]
    line = hits[-1] if hits else f"RANGEPROBE {s} none"
    open("probe_ranges.txt", "a").write(line + "\n")
    print(line, flush=True)
