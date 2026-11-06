import sys, json
sys.path.insert(0, '.'); sys.path.insert(0, 'agents/batch_2')
import api
from feats import feats2
R = json.load(open('agents/batch_2/feat_table.json'))
by = {r['id']: r for r in R}
for t in api.TRADES:
    by[t['id']].update(feats2(api._blind(t), api.A))
json.dump(R, open('agents/batch_2/feat_table.json', 'w'))
print('ok')
