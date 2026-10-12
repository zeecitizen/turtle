"""Run mt5/TickBarProbe as a headless script in the Axi rig and print its [probe] lines."""
import axi_rig, subprocess, time, sys
axi_rig.use('axi'); R = axi_rig.RIG
axi_rig.compile_ea('TickBarProbe')
src = R/'MQL5'/'Experts'/'TickBarProbe.ex5'; dst = R/'MQL5'/'Scripts'/'TickBarProbe.ex5'
dst.parent.mkdir(exist_ok=True); dst.write_bytes(src.read_bytes())
(R/'probe.ini').write_text("[StartUp]\r\nScript=TickBarProbe\r\nSymbol=XAUUSD.pro\r\nPeriod=M1\r\n", encoding='utf-16')
t0 = time.time(); start = None
subprocess.Popen([str(R/'terminal64.exe'), '/portable', f'/config:{R/"probe.ini"}'])
logd = R/'MQL5'/'Logs'; done = False
while time.time() - t0 < int(sys.argv[1]) if len(sys.argv) > 1 else 1800:
    time.sleep(5)
    logs = sorted(logd.glob('*.log'), key=lambda f: f.stat().st_mtime)
    txt = logs[-1].read_bytes().decode('utf-16', errors='ignore') if logs else ''
    if start is None: start = txt.count('[probe] DONE')
    if txt.count('[probe] DONE') > start: done = True; break
axi_rig.kill_rig()
txt = sorted(logd.glob('*.log'), key=lambda f: f.stat().st_mtime)[-1].read_bytes().decode('utf-16', errors='ignore')
lines = [l.split('\t')[-1] for l in txt.splitlines() if '[probe]' in l]
k = max(i for i, l in enumerate(lines) if 'DONE' in l) if done else len(lines)
seg = lines[:k]; j = max([i for i, l in enumerate(seg) if 'DONE' in l] + [-1])
print('done' if done else 'NOT DONE'); print('\n'.join(l for l in seg[j + 1:] if 'shift    +0s' in l or 'bars -1' in l or 'e.g.' in l))
