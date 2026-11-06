import sys, json, numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, 'agents/batch_2')
import api
from feats import feats
rows = []
for t in api.TRADES:
    f = feats(api._blind(t), api.A)
    f["win"] = t["win"]; f["train"] = t["t_in"] < api.SPLIT; f["id"] = t["id"]
    rows.append(f)
json.dump(rows, open('agents/batch_2/feat_table.json', 'w'))
print(len(rows))
