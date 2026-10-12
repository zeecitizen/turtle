"""Run an MQL5 script headless in the Axi rig: python run_script.py NAME TAG TIMEOUT  (prints the TAG lines)."""
import axi_rig, subprocess, time, sys
name, tag, tmo = sys.argv[1], sys.argv[2], int(sys.argv[3])
axi_rig.use('axi'); R = axi_rig.RIG
axi_rig.compile_ea(name)
src = R/'MQL5'/'Experts'/f'{name}.ex5'; dst = R/'MQL5'/'Scripts'/f'{name}.ex5'
dst.parent.mkdir(exist_ok=True); dst.write_bytes(src.read_bytes())
(R/'script.ini').write_text(f"[StartUp]\r\nScript={name}\r\nSymbol=XAUUSD.pro\r\nPeriod=M15\r\n", encoding='utf-16')
logd = R/'MQL5'/'Logs'
def txt():
    logs = sorted(logd.glob('*.log'), key=lambda f: f.stat().st_mtime)
    return logs[-1].read_bytes().decode('utf-16', errors='ignore') if logs else ''
base = txt().count(f'{tag} DONE'); t0 = time.time(); done = False; shown = 0
proc = subprocess.Popen([str(R/'terminal64.exe'), '/portable', f'/config:{R/"script.ini"}'])
while time.time() - t0 < tmo:
    time.sleep(10)
    t = txt(); ls = [l.split('\t')[-1] for l in t.splitlines() if tag in l]
    for l in ls[shown:]: print(l, flush=True)
    shown = len(ls)
    if t.count(f'{tag} DONE') > base: done = True; break
for _ in range(90):                     # let the terminal close itself (saves custom symbols)
    if proc.poll() is not None: break
    time.sleep(1)
print('terminal exited cleanly' if proc.poll() is not None else 'had to kill the terminal')
axi_rig.kill_rig()
print('FINISHED' if done else 'TIMEOUT', round(time.time() - t0), 's')
