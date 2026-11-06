"""mlx - the Machine Learning tab's data side (Zee 2026-11-01: Triple Barrier labels on XAUUSD M15, purged K-fold, SHAP, stacked classifier,
ONNX into the EA). This package owns the FEATURES (features.py, FEATURE_SPEC.md verbatim), the LABELS (labels.py) and the dataset files
(data.py -> simdata/mlx_dataset.npz, mlx_entries.npz, mlx_features.json). The model / page / EA sides read those files.

CLAUDE.md holds here too: every number this produces is a HYPOTHESIS; only MT5's Strategy Tester promotes one."""
import os
import sys
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")   # this laptop's ARM CPU crashes LLVM's scheduler unless numba targets a generic CPU (sim.py)

HERE = Path(__file__).resolve().parent               # monitor/saad_view/mlx
VIEW = HERE.parent                                   # monitor/saad_view (sim.py, server.py)
SIMDATA = VIEW / "simdata"
if str(VIEW) not in sys.path:
    sys.path.insert(0, str(VIEW))

__version__ = "1.0"
