"""Run TiltLab_EUR passes on rig axi4 (EURUSD_ZX real ticks). Usage: run.py NAME [NAME...]. MT5 tester only."""
import sys, json, time, shutil
sys.path.insert(0, r'C:\Users\zeesh\turtle\monitor\strategy_lab')
sys.path.insert(0, r'C:\Users\zeesh\turtle\games\gold_runner\research\diamond_eur_mt5')
import axi_rig
from batch import deals
from pathlib import Path
OUT = Path(__file__).parent / 'runs'
V_OFF = dict(V_InpMetaMode='0', V_InpRegimeMode='0', V_InpExhMode='0', V_InpMlLog='false', V_InpVerbose='false', V_InpDashboard='false')
RUNS = {
 'rnd':   dict(InpTilt='5'),
 'ha04':  dict(InpTilt='0', InpHaThr='0.4'), 'ha06': dict(InpTilt='0', InpHaThr='0.6'), 'ha08': dict(InpTilt='0', InpHaThr='0.8'),
 'vs5':   dict(InpTilt='1', V_InpTF='5'), 'vs1': dict(InpTilt='1', V_InpTF='1'),
 'rsik34': dict(InpTilt='3'), 'rsie21': dict(InpTilt='3', InpLineMode='1', InpLineLen='21'), 'rsik34b30': dict(InpTilt='3', InpBodyPct='0.3'),
 'rsie9': dict(InpTilt='3', InpLineMode='1', InpLineLen='9'),
 'dmibuy': dict(InpTilt='4', InpDmiSide='0'), 'dmisell': dict(InpTilt='4', InpDmiSide='1'),
}
for name in sys.argv[1:]:
    free = shutil.disk_usage('C:/').free / 2**20
    if free < 500: print('DISK LOW', free, 'MB - stop'); break
    sets = {**V_OFF, **RUNS[name]}
    tag = f'tilt_{name}'
    r = axi_rig.run('TiltLab_EUR', 'EURUSD_ZX', 'M1', sets, '2026.01.02', '2026.11.04', deposit=100000, exec_mode=-1, tag=tag, timeout=6*3600, model=4, leverage='1:400', rig='axi4')
    rep = Path(axi_rig.RIGS['axi4']) / 'reports' / f'{tag}.htm'
    r['deals'] = deals(rep) if rep.exists() else []
    r['sets'] = sets
    for f in Path(axi_rig.RIGS['axi4'], 'Tester').glob('Agent-*/logs/*.log'):
        if f.stat().st_mtime >= time.time() - r.get('secs', 0) - 120:
            r['log'] = [l for l in f.read_bytes().decode('utf-16', errors='ignore').splitlines() if '[TILT' in l or 'real ticks' in l or 'ticks,' in l][-20:]
    (OUT / f'{name}.json').write_text(json.dumps(r))
    for p in rep.parent.glob(f'{tag}*'): p.unlink()        # our own report files; deals are kept in the json
    print(name, r.get('error'), r.get('trades'), r.get('wr'), r.get('net'), r.get('secs'), 'deals', len(r['deals']), 'free MB', round(free), r.get('log', [])[-2:], flush=True)
