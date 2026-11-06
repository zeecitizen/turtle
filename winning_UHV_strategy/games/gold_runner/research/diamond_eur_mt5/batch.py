"""Run DiamondEUR_lab passes on Axi rigs (custom symbol EURUSD_ZX = Zee's real EUR ticks). Usage: batch.py RIG NAME [NAME...]"""
import sys, json, re, time, subprocess
sys.path.insert(0, r'C:\Users\zeesh\turtle\monitor\strategy_lab')
import axi_rig
from pathlib import Path
OUT = Path(__file__).parent / 'runs'; OUT.mkdir(exist_ok=True)
EA = 'DiamondEUR_lab'; SYM = 'EURUSD_ZX'
COMMON = dict(InpUseSaad='false', InpUseVsisa='false', InpUseDia='true', D_InpLots='1.0', D_InpUseDiamonds='false',
              D_InpStackLots='false', D_InpMaxOpen='1', D_InpCooldownBar='3', D_InpOandaVolume='0', D_InpOandaColour='false',
              D_InpOandaPrice='false', D_InpTargetR='0', D_InpBreakEvenR='0', D_InpBailSec='0', D_InpBailAt='0',
              D_InpFailCandles='0', D_InpJuryMode='0', D_InpReqLaws='0', D_InpVerbose='false', InpDiaLog='false',
              D_InpNyOnly='false', D_InpLabFromFill='false', D_InpSpaceSec='0', D_InpOneOrder='false', D_InpMaxRisk='0', D_InpBeBufferPts='0',
              InpDiaVsNoOpp='false', InpDiaVsSame='0', InpDiaSaadSame='false', InpDiaRegSkip='0', InpDiaHourFrom='0', InpDiaHourTo='0')
GEO = {'nat': dict(D_InpStructStop='0.00003', D_InpTargetPts='0.00006', D_InpStopPts='0.00114', D_InpMaxHoldMin='20'),
       'game': dict(D_InpStructStop='0', D_InpStopPts='0.00020', D_InpTargetPts='0.00020', D_InpMaxHoldMin='0', D_InpLabFromFill='true'),
       'gameq': dict(D_InpStructStop='0', D_InpStopPts='0.00020', D_InpTargetPts='0.00020', D_InpMaxHoldMin='0', D_InpLabFromFill='false')}
FIL = {'off': dict(InpDiaMinER='0', InpDiaTrend='0'), 'er45': dict(InpDiaMinER='0.45', InpDiaTrend='0'),
       'er38t2': dict(InpDiaMinER='0.38', InpDiaTrend='2'), 'er38t3': dict(InpDiaMinER='0.38', InpDiaTrend='3')}
SPECIAL = {'parity': ('game', 'off', dict(D_InpMaxOpen='99', D_InpCooldownBar='0'), '2026.10.26', '2026.10.31'),
           'parity_traded': ('game', 'off', {}, '2026.10.26', '2026.10.31'),
           'parity_oct': ('game', 'off', dict(D_InpMaxOpen='99', D_InpCooldownBar='0'), '2026.10.01', '2026.11.01')}

def deals(path):
    t = Path(path).read_text(encoding='utf-16', errors='ignore').replace('\xa0', ' ')
    rows = re.findall(r'<tr[^>]*><td>(\d{4}\.\d\d\.\d\d [\d:]+)</td><td>\d+</td><td>[^<]+</td><td>(buy|sell)</td><td>(in|out)</td>'
                      r'<td>([\d.]+)</td><td>([\d.]+)</td><td>\d+</td><td>([-\d. ]+)</td><td>([-\d. ]+)</td><td>([-\d. ]+)</td><td>[-\d. ]+</td><td>([^<]*)</td>', t)
    f = lambda s: float(s.replace(' ', ''))
    return [dict(time=r[0], type=r[1], io=r[2], vol=f(r[3]), price=f(r[4]), comm=f(r[5]), swap=f(r[6]), profit=f(r[7]), comment=r[8]) for r in rows]

def agent_lines(R, since):
    out = []
    for f in (R / 'Tester').glob('Agent-*/logs/*.log'):
        if f.stat().st_mtime < since: continue
        txt = f.read_bytes().decode('utf-16', errors='ignore').splitlines()
        idx = [i for i, l in enumerate(txt) if 'testing of Experts' in l and EA in l]
        seg = txt[idx[-1]:] if idx else txt
        out += [l for l in seg if any(k in l for k in ('[DIAFIRE]', '[DIAFAIL]', 'real ticks', 'bars', 'ticks,', 'TRINITY', 'discard', 'generat', 'final balance', 'Test passed', 'error', 'failed'))]
    return out

def go(rig, name):
    if name in SPECIAL: g, fl, extra, frm, to = SPECIAL[name]
    else:
        g, fl = name.split('-')[0].split('_'); extra = {}; frm, to = '2026.01.02', '2026.11.04'
        if '-h0' in name: extra['D_InpMaxHumps'] = '0'
    sets = {**COMMON, **GEO[g], **FIL[fl], **extra}
    R = Path(axi_rig.RIGS[rig])
    busy = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Process terminal64,metatester64 -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{R}\\*' }} | Measure-Object).Count"], capture_output=True, text=True).stdout.strip()
    if busy != '0': print(rig, 'BUSY, skipping', name); return
    t0 = time.time()
    r = axi_rig.run(EA, SYM, 'M1', sets, frm, to, deposit=100000, exec_mode=(0 if name.endswith('-d0') else -1), tag=f'diaeur_{name}', timeout=6 * 3600, model=4, leverage='1:400', rig=rig)
    rep = R / 'reports' / f'diaeur_{name}.htm'
    r['deals'] = deals(rep) if rep.exists() else []
    r['log'] = agent_lines(R, t0)
    r['geo'], r['filter'], r['from'], r['to'], r['rig'] = g, fl, frm, to, rig
    (OUT / f'{name}.json').write_text(json.dumps(r, indent=1))
    print(name, rig, r.get('error'), r.get('trades'), r.get('wr'), r.get('net'), r.get('secs'), 'deals', len(r['deals']), 'fires', sum('[DIAFIRE]' in l for l in r['log']), flush=True)

if __name__ == '__main__':
    rig = sys.argv[1]
    axi_rig.compile_ea(EA, rig=rig)
    for n in sys.argv[2:]: go(rig, n)
