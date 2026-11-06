import sys, json
sys.path.insert(0, r'C:\Users\zeesh\turtle\monitor\strategy_lab')
import axi_rig
from batch import deals, OUT
from analyze import trades, stats
axi_rig.compile_ea('NullEntry', rig='axi4')
sets = dict(InpLots='1.0', InpStopPts='0.00020', InpTargetPts='0.00020', InpMaxHoldMin='100000', InpEveryMin='15', InpAlternate='true', InpVerbose='false')
r = axi_rig.run('NullEntry', 'EURUSD_ZX', 'M1', sets, '2026.01.02', '2026.11.04', deposit=100000, exec_mode=-1, tag='diaeur_null15', model=4, leverage='1:400', rig='axi4')
from pathlib import Path
r['deals'] = deals(Path(axi_rig.RIGS['axi4']) / 'reports' / 'diaeur_null15.htm')
(OUT.parent / 'null15.json').write_text(json.dumps(r))
tr = trades(r['deals'])
for lab, sel in (('full', lambda x: True), ('h1', lambda x: x['t'] < '2026.07.01'), ('h2', lambda x: x['t'] >= '2026.07.01')):
    print(lab, json.dumps(stats([x for x in tr if sel(x)])))
print(r.get('error'), r.get('trades'), r.get('wr'), r.get('net'), r.get('dd'), r.get('secs'))
