# Meta-labeling for Saad_strategy_15min

An XGBoost "second opinion" on each trade the 15-minute EA is about to take: it estimates the
trade's chance of finishing in profit and skips it when that chance is too low. Built 2026-10-13
from Zee's two Meta-Labeling PDFs.

## Changes from the PDFs

| PDF | Here | Why |
|---|---|---|
| WebRequest to a Python server is the only gate | **Mode 1: the trees compiled into the EA** (`mt5/SaadMetaModel.mqh`). Mode 2 is the PDF's server. | MT5's Strategy Tester cannot make WebRequest calls, so a server gate can never be backtested. Our rule: only the tester (or live fills) can promote a change. |
| Mock data if no log exists | **No mock data.** No real log means no model. | A model trained on invented trades could get shipped by accident. |
| Label = reached 1.5R | **Label = the trade's final net $ > 0**, summed over the 50% partial, the runner, swap and $4/lot | The EA closes half at TP1 and moves the rest to breakeven, so "1.5R" does not describe a win. |
| `tick_accel` feature | **Dropped** | The tester rewrites tick volume, so it would differ live. |
| Features computed in Python | **The EA computes them** (`MetaFeatures()`) and Python only reads the log | A Python port of EA logic has its own bugs. |
| Pick a threshold by precision | **Pick it by the net $ of approved trades** (time-series CV inside the training window) | Precision ignores how big each win and loss is. |

## Features (all stationary, from closed candles + the live quote)

side · setup shape · 9/50 EMA line · stop distance in ATRs · TP1 distance in R · Kaufman ER ·
ATR14/ATR200 · distance to 50 EMA · distance to 9 EMA · 9–50 EMA gap · setup range in ATRs ·
hour · weekday · spread · 50 EMA slope.

## How to use

1. **Log** (Strategy Tester): run `Saad_meta` with `InpMetaLog=true, InpMetaTag=1, InpMetaMode=0`.
   This writes `Common\Files\saad_meta_1_feat.csv` and `saad_meta_1_out.csv`.
2. **Train**: `py src\train_metalabel.py --tag 1 --cutoff 2026-07-01`.
   - Trains only on trades before the cutoff.
   - Writes `models\meta_model_xauusd.pkl` and `mt5\SaadMetaModel.mqh`.
   - Checks that xgboost and the exported MQL5 trees agree (parity).
3. **Judge** (Strategy Tester, unseen period): compile `Saad_meta`, then run it with `InpMetaMode=1` at
   several `InpMetaThr` values against `InpMetaMode=0` on the same dates.
4. **Live, optional**:
   - double-click `run_server.bat`
   - add `http://127.0.0.1:8000` under Tools > Options > Expert Advisors > WebRequest
   - set `InpMetaMode=2`

   `InpApiFailPass=false` means a dead server blocks every trade.

## Result

See `report.md` §13.
