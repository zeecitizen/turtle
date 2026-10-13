"""Meta-labeling inference server for LIVE trading (Saad_meta.mq5, InpMetaMode=2).

The Strategy Tester cannot make WebRequest calls, so this server is for live charts only;
backtests use InpMetaMode=1 (the same trees compiled into the EA).

POST /predict   {"features": [15 numbers, in META_NAMES order]}   (what the EA sends)
            or  {"f_side": 1, "f_shape": 2, ...}                    (named, for manual tests)
-> {"execute": true, "probability": 0.6123, "threshold_used": 0.55}
   regression model (--model meta_model_xauusd_reg_abs_d3.pkl): "probability" carries the PREDICTED NET $
   (the EA reads that field either way; also returned as "predicted_pnl"), threshold in $.
    py api_server.py [--port 8000] [--threshold 0.55] [--model meta_model_xauusd.pkl]"""
import argparse, sys
from pathlib import Path
import joblib
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request

_m = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "meta_model_xauusd.pkl"
MODEL_FILE = Path(__file__).resolve().parents[1] / "models" / _m
if not MODEL_FILE.exists():
    raise RuntimeError(f"Missing {MODEL_FILE}. Run train_metalabel.py first.")
art = joblib.load(MODEL_FILE)
model, names, threshold = art["model"], art["features"], float(art["threshold"])
REG = art.get("kind") == "reg"
app = FastAPI(title="Saad meta-labeling API")


@app.get("/health")
def health():
    return {"ok": True, "kind": "regression ($)" if REG else "classifier (probability)", "features": names, "threshold": threshold, "trained": art.get("trained")}


@app.post("/predict")
async def predict(req: Request):
    body = await req.json()
    try:
        x = body["features"] if "features" in body else [body[n] for n in names]
        if len(x) != len(names):
            raise ValueError(f"expected {len(names)} features, got {len(x)}")
        X = np.asarray([x], dtype=float)
        prob = float(model.predict(X)[0]) if REG else float(model.predict_proba(X)[0, 1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = {"execute": prob >= threshold, "probability": round(prob, 6), "threshold_used": threshold}
    if REG: out["predicted_pnl"] = round(prob, 2)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8000); ap.add_argument("--threshold", type=float); ap.add_argument("--model")
    a = ap.parse_args()
    if a.threshold is not None: threshold = a.threshold
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning", workers=1)
