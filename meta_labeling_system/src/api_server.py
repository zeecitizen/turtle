"""Meta-labeling inference server for LIVE trading (Saad_meta.mq5, InpMetaMode=2).

The Strategy Tester cannot make WebRequest calls, so this server is for live charts only;
backtests use InpMetaMode=1 (the same trees compiled into the EA).

POST /predict   {"features": [15 numbers, in META_NAMES order]}   (what the EA sends)
            or  {"f_side": 1, "f_shape": 2, ...}                    (named, for manual tests)
-> {"execute": true, "probability": 0.6123, "threshold_used": 0.55}
    py api_server.py [--port 8000] [--threshold 0.55]"""
import argparse
from pathlib import Path
import joblib
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request

MODEL_FILE = Path(__file__).resolve().parents[1] / "models" / "meta_model_xauusd.pkl"
if not MODEL_FILE.exists():
    raise RuntimeError(f"Missing {MODEL_FILE}. Run train_metalabel.py first.")
art = joblib.load(MODEL_FILE)
model, names, threshold = art["model"], art["features"], float(art["threshold"])
app = FastAPI(title="Saad meta-labeling API")


@app.get("/health")
def health():
    return {"ok": True, "features": names, "threshold": threshold, "trained": art.get("trained")}


@app.post("/predict")
async def predict(req: Request):
    body = await req.json()
    try:
        x = body["features"] if "features" in body else [body[n] for n in names]
        if len(x) != len(names):
            raise ValueError(f"expected {len(names)} features, got {len(x)}")
        prob = float(model.predict_proba(np.asarray([x], dtype=float))[0, 1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"execute": prob >= threshold, "probability": round(prob, 6), "threshold_used": threshold}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8000); ap.add_argument("--threshold", type=float)
    a = ap.parse_args()
    if a.threshold is not None: threshold = a.threshold
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning", workers=1)
