"""zee_tick_detector_realistic_medium.py — same state-machine as
zee_tick_detector_realistic.py BUT with MEDIUM filters:
  RNG_N_MIN = 0.8 (vs aggressive 0.5)
  RNG_MIN = 0.8 (vs aggressive 0.5)
  COOLDOWN_SEC = 30 (vs 10)
  CHECK_EVERY = 10 (vs 3)

Does stricter filters give PF >= 1.25?
"""
import sys, glob, importlib.util
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

spec = importlib.util.spec_from_file_location(
    "realistic", str(Path(__file__).parent / "zee_tick_detector_realistic.py"))
real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(real)

# Override to MEDIUM
real.RNG_N_MIN = 0.8
real.RNG_MIN = 0.8
real.COOLDOWN_SEC = 30
real.CHECK_EVERY = 10

# Now run main_with_metrics — it'll use these new constants
print("MEDIUM config (0.8 / 0.8 / 30s / 10 ticks) under state-machine")
real.main()
real.main_with_metrics()
