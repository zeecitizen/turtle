"""XAUUSD market-regime server (optional). Saad_regime.mq5 does NOT need it: the same GMM is compiled
into the EA (InpRegimeMode=1), which works both live and in the Strategy Tester. Use this for
dashboards / manual checks.
POST /get_regime {"kaufman_er": 0.3, "atr_ratio": 1.1, "realized_vol": 0.0012}
-> {"regime_id": 0, "mode": "NORMAL", ...}
    py regime_server.py [--port 8001]"""
import argparse
from pathlib import Path
import joblib
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

MODEL_FILE = Path(__file__).resolve().parents[1] / "models" / "regime_gmm_xauusd.pkl"
if not MODEL_FILE.exists():
    raise RuntimeError(f"Missing {MODEL_FILE}. Run train_regime_gmm.py first.")
art = joblib.load(MODEL_FILE)
names = {art["trend_id"]: "TREND", art["chop_id"]: "CHOP"}
names[3 - art["trend_id"] - art["chop_id"]] = "NORMAL"
app = FastAPI(title="XAUUSD market regime")


class MarketState(BaseModel):
    kaufman_er: float
    atr_ratio: float
    realized_vol: float


@app.post("/get_regime")
def get_regime(s: MarketState):
    try:
        z = art["scaler"].transform(np.array([[s.kaufman_er, s.atr_ratio, s.realized_vol]]))
        k = int(art["model"].predict(z)[0])
        p = art["model"].predict_proba(z)[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"regime_id": k, "mode": names[k], "probabilities": {names[i]: round(float(v), 4) for i, v in enumerate(p)}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8001)
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().port, log_level="warning", workers=1)
