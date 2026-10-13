"""Train every report.md machine-learning model for VSISA (M5) from VSISA_ml.mq5's own Strategy-Tester logs
(Common\\Files\\vml_<tag>_{feat,out,exh,reg}.csv; no mock data) and compile each into an .mqh for the EA.
Walk-forward: everything is fitted on trades/candles before --cutoff only; MT5 judges after it.
    py vsisa_train.py meta     [--tag N] [--kind cls|reg]   -> mt5/VsisaMetaModel.mqh      (report 13 / 14)
    py vsisa_train.py regime   [--tag N]                    -> mt5/VsisaRegimeModel.mqh    (report 15)
    py vsisa_train.py exhaust  [--tag N]                    -> mt5/VsisaExhaustModel.mqh   (report 17)
    py vsisa_train.py drl      [--tag N] [--seed S]         -> mt5/VsisaDrlPolicy.mqh      (report 19)
Any Python replay printed here is a HYPOTHESIS; only the MT5 run of the gated EA promotes."""
import argparse, json, shutil, sys
from pathlib import Path
import numpy as np, pandas as pd
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).resolve().parents[1]; REPO = ROOT.parent
COMMON = Path.home() / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"
META = ["f_side", "f_risk_atr", "f_tp_r", "f_er", "f_atr_ratio", "f_ema50_dist", "f_ema9_dist", "f_slope50", "f_hour", "f_dow",
        "f_spread", "f_react_ratio", "f_fade", "f_trend", "f_range_atr"]
EXH = ["x_side", "x_bars", "x_float_r", "x_mfe_r", "x_giveback_r", "x_er", "x_ema50_dist", "x_ema9_dist", "x_atr_ratio", "x_room_r",
       "x_body", "x_hour", "x_tp_left_r"]


def rd(tag, kind):
    f = COMMON / f"vml_{tag}_{kind}.csv"
    if not f.exists(): sys.exit(f"missing {f}: run VSISA_ml with InpMlLog=true, InpMlTag={tag} and every ML mode 0")
    return pd.read_csv(f)


def trades(tag):
    F, O = rd(tag, "feat"), rd(tag, "out")
    if (F.score >= 0).any(): sys.exit("feature log came from a GATED run - train only on an ungated one")
    d = F[F.veto == 0].merge(O, on="pos_id").assign(time=lambda x: pd.to_datetime(x.time, format="%Y.%m.%d %H:%M:%S"))
    return d.sort_values("time").reset_index(drop=True)


def base_margin(b, kind):
    bs = float(str(json.loads(b.save_config())["learner"]["learner_model_param"]["base_score"]).strip("[]"))
    return float(np.log(bs / (1 - bs))) if kind == "cls" else bs


def tree_mql(node, names, var, ind="   "):
    if "leaf" in node: return f"{ind}return {float(np.float32(node['leaf'])):.9g};\n"
    i = names.index(node["split"]); thr = float(np.float32(node["split_condition"]))
    yes = next(c for c in node["children"] if c["nodeid"] == node["yes"]); no = next(c for c in node["children"] if c["nodeid"] == node["no"])
    return f"{ind}if ((float){var}[{i}] < (float){thr:.9g}) {{\n" + tree_mql(yes, names, var, ind + "   ") + f"{ind}}} else {{\n" + tree_mql(no, names, var, ind + "   ") + f"{ind}}}\n"


def leaf(node, x, names):
    while "leaf" not in node:
        go = node["yes"] if np.float32(x[names.index(node["split"])]) < np.float32(node["split_condition"]) else node["no"]
        node = next(c for c in node["children"] if c["nodeid"] == go)
    return float(np.float32(node["leaf"]))


def export_trees(model, names, kind, prefix, fn_name, header_lines, path, X):
    b = model.get_booster(); b.feature_names = names
    trees = [json.loads(t) for t in b.get_dump(dump_format="json")]; bm = base_margin(b, kind)
    out = header_lines + [f"double {prefix}Tree{k}(const double &x[])\n{{\n{tree_mql(t, names, 'x')}}}" for k, t in enumerate(trees)]
    body = "\n".join(f"   m += {prefix}Tree{k}(x);" for k in range(len(trees)))
    ret = "1.0 / (1.0 + MathExp(-m))" if kind == "cls" else "m"
    out.append(f"double {fn_name}(const double &x[])\n{{\n   double m = {bm:.12g};\n{body}\n   return {ret};\n}}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8"); shutil.copy(path, ROOT / "mql5" / path.name)
    py = model.predict_proba(X)[:, 1] if kind == "cls" else model.predict(X)
    raw = bm + np.array([sum(leaf(t, x, names) for t in trees) for x in X])
    mine = 1 / (1 + np.exp(-raw)) if kind == "cls" else raw
    gap = float(np.abs(py - mine).max()); print(f"[+] parity xgboost vs exported trees: {gap:.2e} {'OK' if gap < (1e-5 if kind == 'cls' else 1e-2) else 'MISMATCH'}")


def cmd_meta(a):
    d = trades(a.tag); tr, te = d[d.time < a.cutoff].reset_index(drop=True), d[d.time >= a.cutoff].reset_index(drop=True)
    print(f"[+] {len(d)} trades; train {len(tr)}, unseen {len(te)} | kind {a.kind}")
    if a.kind == "cls":
        mk = lambda: xgb.XGBClassifier(n_estimators=100, learning_rate=0.05, max_depth=2, subsample=0.8, colsample_bytree=0.8, min_child_weight=10, random_state=42, n_jobs=2)
        y = (tr.net > 0).astype(int); grid = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    else:
        mk = lambda: xgb.XGBRegressor(n_estimators=100, learning_rate=0.03, max_depth=2, subsample=0.85, colsample_bytree=0.85, random_state=42, n_jobs=2)
        y = tr.net; grid = [-200, -100, -50, 0, 50, 100]
    tot = {t: 0.0 for t in grid}; base = 0.0
    for i, j in TimeSeriesSplit(n_splits=4).split(tr):
        m = mk(); w = (np.abs(tr.net.iloc[i]) + 1) if a.kind == "reg" else None
        m.fit(tr[META].iloc[i], y.iloc[i], sample_weight=w)
        p = m.predict_proba(tr[META].iloc[j])[:, 1] if a.kind == "cls" else m.predict(tr[META].iloc[j])
        net = tr.net.iloc[j].to_numpy(); base += net.sum()
        for t in grid: tot[t] += net[p >= t].sum()
    print(f"    CV take everything: {base:,.0f}"); [print(f"    score >= {t}: {v:,.0f}") for t, v in tot.items()]
    best = max(grid, key=lambda t: tot[t]); print(f"    -> threshold {best} (hypothesis)")
    m = mk(); m.fit(tr[META], y, sample_weight=(np.abs(tr.net) + 1) if a.kind == "reg" else None)
    names = ",".join(f'"{n}"' for n in META)
    hdr = [f"// VsisaMetaModel.mqh - GENERATED by vsisa_train.py meta --kind {a.kind} (trained before {a.cutoff}, {len(tr)} trades); suggested InpMetaThr {best}",
           f"#define V_META_NF {len(META)}", f"string V_META_NAMES[V_META_NF] = {{{names}}};"]
    export_trees(m, META, a.kind, "VM", "V_MetaModelScore", hdr, REPO / "mt5" / "VsisaMetaModel.mqh", d[META].to_numpy())
    json.dump({"kind": a.kind, "threshold": best}, open(ROOT / "models" / "vsisa_meta.json", "w"))


def cmd_regime(a):
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    r = rd(a.tag, "reg").dropna(); r["time"] = pd.to_datetime(r.time, format="%Y.%m.%d %H:%M"); tr = r[r.time < a.cutoff]
    F = ["kaufman_er", "atr_ratio", "realized_vol"]
    sc = StandardScaler().fit(tr[F]); g = GaussianMixture(3, covariance_type="full", random_state=42, n_init=5, max_iter=500).fit(sc.transform(tr[F]))
    lab = g.predict(sc.transform(tr[F])); print("[+] cluster means (train):"); print(tr.assign(c=lab).groupby("c")[F].mean().round(5))
    # which clusters lose money? (diagnostic from the logged trades; MT5 decides)
    d = trades(a.tag); rr = r.copy(); rr["c"] = g.predict(sc.transform(rr[F]))
    d["cand"] = d.time.dt.floor("5min") - pd.Timedelta(minutes=5)
    d = d.merge(rr[["time", "c"]].rename(columns={"time": "cand"}), on="cand", how="left")
    print(d[d.time < a.cutoff].groupby("c").net.agg(["count", "sum"]).round(0))
    f = lambda v: ", ".join(f"{x:.17g}" for x in np.ravel(v))
    L = [f"// VsisaRegimeModel.mqh - GENERATED by vsisa_train.py regime (trained before {a.cutoff})",
         f"double VR_MU0[3] = {{{f(sc.mean_)}}}; double VR_SC[3] = {{{f(sc.scale_)}}};",
         f"double VR_W[3] = {{{f(g.weights_)}}}; double VR_MU[9] = {{{f(g.means_)}}}; double VR_PC[27] = {{{f(g.precisions_cholesky_)}}};",
         "int V_RegimeOf(const double &x[])", "{", "   double z[3]; for (int j = 0; j < 3; j++) z[j] = (x[j] - VR_MU0[j]) / VR_SC[j];",
         "   double best = -1e300; int arg = -1;", "   for (int k = 0; k < 3; k++) { double lp = MathLog(VR_W[k]), q = 0;",
         "      for (int c = 0; c < 3; c++) { double y = 0; for (int r = 0; r < 3; r++) y += (z[r] - VR_MU[k * 3 + r]) * VR_PC[k * 9 + r * 3 + c]; q += y * y; lp += MathLog(VR_PC[k * 9 + c * 3 + c]); }",
         "      lp -= 0.5 * q; if (lp > best) { best = lp; arg = k; } }", "   return arg;", "}"]
    p = REPO / "mt5" / "VsisaRegimeModel.mqh"; p.write_text("\n".join(L) + "\n", encoding="utf-8"); shutil.copy(p, ROOT / "mql5" / p.name)


def cmd_exhaust(a):
    E, O = rd(a.tag, "exh"), rd(a.tag, "out")
    d = E.merge(O[["pos_id", "profit"]], on="pos_id").assign(time=lambda x: pd.to_datetime(x.time, format="%Y.%m.%d %H:%M:%S"))
    d["gain"] = d.float_usd - d.profit; d["y"] = (d.gain > 0).astype(int); d = d[d.float_usd > 0].sort_values("time").reset_index(drop=True)
    tr = d[d.time < a.cutoff]; print(f"[+] {len(d)} profitable position-candles; train {len(tr)}; share where closing beat holding {tr.y.mean():.1%}")
    m = xgb.XGBClassifier(n_estimators=150, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8, min_child_weight=10, random_state=42, n_jobs=2).fit(tr[EXH], tr.y)
    names = ",".join(f'"{n}"' for n in EXH)
    hdr = [f"// VsisaExhaustModel.mqh - GENERATED by vsisa_train.py exhaust (trained before {a.cutoff})", f"#define V_EXH_NF {len(EXH)}", f"string V_EXH_NAMES[V_EXH_NF] = {{{names}}};"]
    export_trees(m, EXH, "cls", "VX", "V_ExhModelProb", hdr, REPO / "mt5" / "VsisaExhaustModel.mqh", d[EXH].to_numpy())


def cmd_drl(a):
    import gymnasium as gym, torch
    from gymnasium import spaces
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import make_vec_env
    d = trades(a.tag); r = rd(a.tag, "reg"); r["time"] = pd.to_datetime(r.time, format="%Y.%m.%d %H:%M")
    d["cand"] = d.time.dt.floor("5min") - pd.Timedelta(minutes=5)
    d = d.merge(r.rename(columns={"time": "cand"}), on="cand", how="inner")
    O = ["kaufman_er", "atr_ratio", "realized_vol", "f_ema50_dist", "f_side"]
    tr = d[d.time < a.cutoff].reset_index(drop=True); mu, sd = tr[O].mean().to_numpy(), tr[O].std().replace(0, 1).to_numpy()
    X = np.clip((tr[O].to_numpy() - mu) / sd, -10, 10).astype(np.float32); pnl = tr.net.to_numpy()

    class Env(gym.Env):
        def __init__(s):
            super().__init__(); s.action_space = spaces.Box(-1.0, 1.0, (1,), np.float32); s.observation_space = spaces.Box(-10, 10, (len(O),), np.float32)
        def reset(s, seed=None, options=None):
            super().reset(seed=seed); s.i = int(s.np_random.integers(0, len(X) // 2)); s.b = 25000.0; return X[s.i], {}
        def step(s, act):
            m = float(np.clip(1 + act[0], 0, 2)); rp = m * pnl[s.i] / s.b; s.b += m * pnl[s.i]
            if s.b <= 0: return X[s.i], -10.0, True, False, {}
            s.i += 1; return X[min(s.i, len(X) - 1)], float(np.log1p(max(-0.99, rp))), s.i >= len(X), False, {}
    torch.manual_seed(a.seed)
    model = PPO("MlpPolicy", make_vec_env(Env, n_envs=4, seed=a.seed), n_steps=512, batch_size=64, ent_coef=0.01, seed=a.seed, verbose=0, device="cpu")
    model.learn(total_timesteps=a.steps)
    pn = [l for l in model.policy.mlp_extractor.policy_net if isinstance(l, torch.nn.Linear)] + [model.policy.action_net]
    Ls = [(l.weight.detach().numpy().astype(float), l.bias.detach().numpy().astype(float)) for l in pn]
    f = lambda v: ", ".join(f"{x:.17g}" for x in np.ravel(v))
    L = [f"// VsisaDrlPolicy.mqh - GENERATED by vsisa_train.py drl (seed {a.seed}, trained before {a.cutoff}, {len(tr)} trades)",
         f"double VD_MU[5] = {{{f(mu)}}}; double VD_SD[5] = {{{f(sd)}}};"]
    for k, (W, b) in enumerate(Ls): L += [f"double VD_W{k}[{W.size}] = {{{f(W)}}};", f"double VD_B{k}[{b.size}] = {{{f(b)}}};"]
    h0, h1 = Ls[0][0].shape[0], Ls[1][0].shape[0]
    L += ["double V_DrlPolicy(const double &o[])", "{", "   double z[5]; for (int j = 0; j < 5; j++) z[j] = MathMax(-10.0, MathMin(10.0, (o[j] - VD_MU[j]) / VD_SD[j]));",
          f"   double a1[{h0}], a2[{h1}];", f"   for (int r = 0; r < {h0}; r++) {{ double s = VD_B0[r]; for (int c = 0; c < 5; c++) s += VD_W0[r * 5 + c] * z[c]; a1[r] = MathTanh(s); }}",
          f"   for (int r = 0; r < {h1}; r++) {{ double s = VD_B1[r]; for (int c = 0; c < {h0}; c++) s += VD_W1[r * {h0} + c] * a1[c]; a2[r] = MathTanh(s); }}",
          f"   double a = VD_B2[0]; for (int c = 0; c < {h1}; c++) a += VD_W2[c] * a2[c];", "   return 1.0 + MathMax(-1.0, MathMin(1.0, a));", "}"]
    p = REPO / "mt5" / "VsisaDrlPolicy.mqh"; p.write_text("\n".join(L) + "\n", encoding="utf-8"); shutil.copy(p, ROOT / "mql5" / p.name)
    act, _ = model.predict(X, deterministic=True); print(f"[+] PPO trained; average multiplier on train {np.clip(1 + act[:, 0], 0, 2).mean():.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["meta", "regime", "exhaust", "drl"])
    ap.add_argument("--tag", default="20"); ap.add_argument("--cutoff", default="2026-07-01"); ap.add_argument("--kind", default="cls")
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--steps", type=int, default=100_000)
    a = ap.parse_args(); (ROOT / "models").mkdir(exist_ok=True)
    {"meta": cmd_meta, "regime": cmd_regime, "exhaust": cmd_exhaust, "drl": cmd_drl}[a.cmd](a)
