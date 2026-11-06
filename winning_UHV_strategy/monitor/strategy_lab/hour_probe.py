"""Server-hour bar counts per broker rig: py hour_probe.py rig symbol"""
import re, sys, axi_rig
rig, sym = sys.argv[1], sys.argv[2]
axi_rig.use(rig)
axi_rig.compile_ea("HourProbe")
axi_rig.run("HourProbe", sym, "M5", {}, tag="hourprobe", model=1, frm="2026.06.01")
txt = "".join(l.read_text(encoding="utf-16", errors="ignore") for l in (axi_rig.RIG / "Tester").glob("Agent-*/logs/*.log"))
print(rig, (re.findall(r"HOURPROBE [^\r\n]*", txt) or ["none"])[-1])
