"""side_tags.py - not look-ahead: instant setups are built with laws=0, ea=False, royal=False, er=None (uhv_engine._instant_setups), so the
UHV Mode 1/2, MinLaws > 0 and MinEr > 0 settings remove every instant trade. Confirm in the engine."""
import json
from _common import *          # noqa: F401,F403
import uhv_engine
base = base_inputs()
out = {}
for extra in ({}, {"InpUhvMode": "1"}, {"InpUhvMode": "2"}, {"InpUhvMinLaws": "1"}, {"InpUhvMinEr": "0.1"}):
    r, su, cnt = uhv_engine.simulate(dict(base, **extra))
    real = r[r[:, 10] == 0]
    out[json.dumps(extra) or "base"] = {"trades": int(len(real)), "losses": int((real[:, 6] < 0).sum())}
print(out)
json.dump(out, open(os.path.join(HERE, "out_side_tags.json"), "w"), indent=1)
