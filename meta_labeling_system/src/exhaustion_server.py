"""In-trade exhaustion server (optional, live only). Saad_exhaust.mq5 does not need it: the same trees are
compiled into the EA (InpExhMode=1), which works live and in the Strategy Tester.
POST /check_exhaustion {"features": [14 numbers in EXH_NAMES order]}  -> {"force_close": bool, "probability": p}
    py exhaustion_server.py [--port 8002]"""
import argparse
from pathlib import Path
import joblib
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request

MODEL_FILE = Path(__file__).resolve().parents[1] / "models" / "exhaustion_model.pkl"
if not MODEL_FILE.exists():
    raise RuntimeError(f"Missing {MODEL_FILE}. Run train_exhaustion.py first.")
art = joblib.load(MODEL_FILE)
app = FastAPI(title="Saad in-trade exhaustion")


@app.post("/check_exhaustion")
async def check(req: Request):
    body = await req.json()
    try:
        x = body["features"] if "features" in body else [body[n] for n in art["features"]]
        p = float(art["model"].predict_proba(np.asarray([x], dtype=float))[0, 1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"force_close": p >= art["trigger_threshold"], "probability": round(p, 6), "threshold_used": art["trigger_threshold"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8002)
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().port, log_level="warning", workers=1)
