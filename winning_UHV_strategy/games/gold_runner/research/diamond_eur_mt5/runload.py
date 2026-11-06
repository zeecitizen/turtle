import sys, time, subprocess, shutil
sys.path.insert(0, r'C:\Users\zeesh\turtle\monitor\strategy_lab')
import axi_rig
from pathlib import Path
rig = sys.argv[1]; R = Path(axi_rig.RIGS[rig]); tag = '[eurload]'
# refuse if anything runs from this rig
out = subprocess.run(["powershell","-NoProfile","-Command",f"Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{R}\*' }} | Measure-Object | % Count"],capture_output=True,text=True).stdout.strip()
assert out == '0', f'rig busy: {out}'
src_files = Path(r'C:\mt5_rig_axi4\MQL5\Files')
if R != Path(r'C:\mt5_rig_axi4'):
    for n in ('eur_t.bin','eur_bid.bin','eur_ask.bin'):
        shutil.copy2(src_files/n, R/'MQL5'/'Files'/n)
axi_rig.compile_ea('EurTickLoad_lab', rig=rig)
src = R/'MQL5'/'Experts'/'EurTickLoad_lab.ex5'; dst = R/'MQL5'/'Scripts'/'EurTickLoad_lab.ex5'
dst.parent.mkdir(exist_ok=True); dst.write_bytes(src.read_bytes())
(R/'script.ini').write_text("[StartUp]\r\nScript=EurTickLoad_lab\r\nSymbol=EURUSD.pro\r\nPeriod=M1\r\n", encoding='utf-16')
logd = R/'MQL5'/'Logs'
def txt():
    logs = sorted(logd.glob('*.log'), key=lambda f: f.stat().st_mtime)
    return logs[-1].read_bytes().decode('utf-16', errors='ignore') if logs else ''
base = txt().count(f'{tag} DONE'); t0 = time.time(); done = False; shown = 0
proc = subprocess.Popen([str(R/'terminal64.exe'), '/portable', f'/config:{R/"script.ini"}'], startupinfo=axi_rig._quiet())
while time.time() - t0 < 3000:
    time.sleep(10)
    t = txt(); ls = [l.split('\t')[-1] for l in t.splitlines() if tag in l]
    for l in ls[shown:]: print(l, flush=True)
    shown = len(ls)
    if t.count(f'{tag} DONE') > base or 'failed' in ' '.join(ls[-1:]) or 'cannot open' in ' '.join(ls[-1:]): done = True; break
    if proc.poll() is not None and time.time()-t0 > 60: break
for _ in range(120):
    if proc.poll() is not None: break
    time.sleep(1)
print('terminal exited cleanly' if proc.poll() is not None else 'had to kill the terminal')
axi_rig.kill_rig(rig)
print('FINISHED' if done else 'NOT DONE', round(time.time() - t0), 's')
