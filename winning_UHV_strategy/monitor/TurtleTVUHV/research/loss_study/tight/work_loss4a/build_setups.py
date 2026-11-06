"""every instant UHV breakout (decision tick) the engine sees, stack-independent: t, side, level -> setups.npz (loss4a)"""
import json, os, sys
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, ROOT)
import numpy as np
import uhv_engine as U
inp = json.load(open(os.path.join(ROOT, 'settings', 'saved', '2026-11-06 09-00-00.json'), encoding='utf-8'))['inputs']
S, TK = U._setups(U.det_file(inp))
S = U._instant_setups(TK, 0.0, U.det_file(inp))
t = np.array([s['t'] for s in S]); side = np.array([s['side'] for s in S]); lvl = np.array([s['level'] for s in S])
np.savez(os.path.join(HERE, 'setups.npz'), t=t, side=side, level=lvl)
print(len(S), 'setups')
