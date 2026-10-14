"""Optuna (TPE) tuning of bread_winner (Zee 2026-10-14: "As long as i make $10 with a 100% winrate. I am happy. You can
change to as many settings as you want . Tune to any time frame any candle any EA").

Every trial = a real MT5 run (XAUUSD_TK real ticks + $4/lot, $500, 200 ms) on Jan 6 - Jun 30. Scored on DAYS:
  hit  = weekdays whose P&L >= $10 (no trade = a miss)
  red  = weekdays whose P&L < 0
  fit  = hit% - 1.5 x red%   (and a losing period scores -100)
`--validate N` runs the top N on the unseen Jul 1 - Oct 8. `--one '{json params}' --per julo` runs one setting."""
import argparse, datetime as dt, json, re, sys
from pathlib import Path
import optuna
import axi_rig

HERE = Path(__file__).parent
STORAGE = f"sqlite:///{(HERE / 'optuna_bread.db').as_posix()}"
STUDY = "bread_janjun"
LOG = HERE / "zee_optuna_bread.jsonl"
EA, SYM = "bread_winner", "XAUUSD_TK"
PER = {"tune": ("2026.01.06", "2026.07.01"), "julo": ("2026.07.01", "2026.10.08"), "full": ("2026.01.06", "2026.10.08")}
HOLIDAYS = {"2026.04.03"}                                    # Good Friday: gold closed
TFS = {1: 1, 5: 5, 15: 15}


def weekdays(frm, to):
    d, e, out = dt.datetime.strptime(frm, "%Y.%m.%d"), dt.datetime.strptime(to, "%Y.%m.%d"), []
    while d < e:
        s = d.strftime("%Y.%m.%d")
        if d.weekday() < 5 and s not in HOLIDAYS: out.append(s)
        d += dt.timedelta(days=1)
    return out


def day_stats(r, frm, to, bread=10.0):
    days = weekdays(frm, to)
    daily = r.get("daily") or {}
    v = [daily.get(d, 0.0) for d in days]
    n = len(v)
    hit = sum(x >= bread for x in v); red = sum(x < 0 for x in v)
    return {"weekdays": n, "hit": hit, "red": red, "flat": n - hit - red, "hit_pct": round(100 * hit / n, 1), "red_pct": round(100 * red / n, 1),
            "worst": round(min(v), 2) if v else 0, "net": round(sum(v), 2), "per_day": round(sum(v) / n, 2) if n else 0}


def to_inputs(p):
    s = {"InpUseSaad": "true" if p["saad"] else "false", "InpUseVsisa": "true" if p["vsisa"] else "false", "InpUseDia": "true" if p["dia"] else "false",
         "S_InpTF": p["s_tf"], "V_InpTF": p["v_tf"], "D_InpTF": 1,
         "S_InpLots": p["s_lots"], "V_InpLots": p["v_lots"], "D_InpLots": p["d_lots"], "D_InpStackMult": 1,
         "V_InpVerbose": "false", "V_InpMetaMode": 1 if p["v_tf"] == 5 else 0, "V_InpRegimeMode": 1 if p["v_tf"] == 5 else 0,
         "V_InpExhMode": 1 if p["v_tf"] == 5 else 0, "InpDiaLog": "false", "InpDiaMinER": p["d_er"],
         "InpBwTarget": p["target"], "InpBwMaxLoss": p["maxloss"], "InpBwFlatHour": p["flat"],
         "InpBwFromHour": p["from_h"], "InpBwToHour": min(24, p["from_h"] + p["len_h"])}
    return {k: (str(round(v, 4)) if isinstance(v, float) else str(v)) for k, v in s.items()}


def backtest(p, per, tag="optbw_"):
    frm, to = PER[per]
    for _ in range(3):
        try:
            r = axi_rig.run(EA, SYM, "M1", to_inputs(p), frm=frm, to=to, tag=tag + axi_rig.RIG.name, timeout=1800, exec_mode=200, deposit=500)
        except Exception as e:
            r = {"error": str(e)[:80]}; axi_rig.kill_rig()
        if r.get("trades", 0) > 0:
            break
    r["days"] = day_stats(r, frm, to)
    return r


def space(t):
    return {"saad": t.suggest_int("saad", 0, 1), "vsisa": t.suggest_int("vsisa", 0, 1), "dia": t.suggest_int("dia", 0, 1),
            "s_tf": t.suggest_categorical("s_tf", [5, 15]), "v_tf": t.suggest_categorical("v_tf", [1, 5]),
            "s_lots": t.suggest_float("s_lots", 0.01, 0.10, step=0.01), "v_lots": t.suggest_float("v_lots", 0.01, 0.10, step=0.01),
            "d_lots": t.suggest_float("d_lots", 0.01, 0.10, step=0.01), "d_er": t.suggest_float("d_er", 0.0, 0.6, step=0.05),
            "target": t.suggest_float("target", 10.0, 25.0, step=1.0), "maxloss": t.suggest_categorical("maxloss", [0, 10, 20, 30, 50, 80, 120]),
            "flat": t.suggest_categorical("flat", [24, 22, 20, 18]), "from_h": t.suggest_int("from_h", 0, 14),
            "len_h": t.suggest_int("len_h", 6, 24)}


def score(ds):
    return -100.0 if ds["net"] <= 0 else ds["hit_pct"] - 1.5 * ds["red_pct"]


def objective(trial):
    p = space(trial)
    if not (p["saad"] or p["vsisa"] or p["dia"]):
        raise optuna.TrialPruned()
    r = backtest(p, "tune")
    ds = r["days"]
    rec = {"trial": trial.number, "period": "tune", "params": p, "days": ds, "dd": r.get("dd"), "trades": r.get("trades"), "rig": axi_rig.RIG.name}
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    for k, v in ds.items(): trial.set_user_attr(k, v)
    f = score(ds)
    print(f"[t{trial.number:3d} {axi_rig.RIG.name}] fit {f:6.1f} | days>=10 {ds['hit']}/{ds['weekdays']} ({ds['hit_pct']}%) red {ds['red']} worst {ds['worst']} net {ds['net']}", flush=True)
    return f


def show(t_or_p, per, label):
    r = backtest(t_or_p, per, tag="optbwv_")
    ds = r["days"]
    rec = {"label": label, "period": per, "params": t_or_p, "days": ds, "dd": r.get("dd"), "trades": r.get("trades")}
    with LOG.open("a") as f: f.write(json.dumps(rec) + "\n")
    print(f"  {label} {per}: days>=10 {ds['hit']}/{ds['weekdays']} ({ds['hit_pct']}%) red {ds['red']} ({ds['red_pct']}%) flat {ds['flat']} "
          f"worst {ds['worst']} net {ds['net']} ({ds['per_day']}/day) dd {r.get('dd')}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default="axi"); ap.add_argument("--trials", type=int, default=50)
    ap.add_argument("--seed", type=int, default=None); ap.add_argument("--validate", type=int, default=0)
    ap.add_argument("--one"); ap.add_argument("--per", default="julo")
    a = ap.parse_args()
    axi_rig.use(a.rig)
    if a.one:
        show(json.loads(a.one), a.per, "one"); sys.exit()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(study_name=STUDY, storage=STORAGE, direction="maximize", load_if_exists=True,
                                sampler=optuna.samplers.TPESampler(seed=a.seed, n_startup_trials=20, multivariate=True, constant_liar=True))
    if a.validate:
        for t in sorted([t for t in study.trials if t.state.name == "COMPLETE"], key=lambda t: -t.value)[:a.validate]:
            print(f"t{t.number}: Jan-Jun days>=10 {t.user_attrs.get('hit')}/{t.user_attrs.get('weekdays')} red {t.user_attrs.get('red')} worst {t.user_attrs.get('worst')}")
            show(t.params, "julo", f"t{t.number}")
        sys.exit()
    if a.rig == "axi" and not study.trials:      # start from Trinity's defaults with a $15 target
        study.enqueue_trial({"saad": 1, "vsisa": 1, "dia": 1, "s_tf": 15, "v_tf": 5, "s_lots": 0.01, "v_lots": 0.01, "d_lots": 0.01, "d_er": 0.45,
                             "target": 15.0, "maxloss": 0, "flat": 24, "from_h": 0, "len_h": 24})
    study.optimize(objective, n_trials=a.trials)
