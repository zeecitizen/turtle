"""DRL position sizing (PPO, Stable-Baselines3) for Saad_strategy_15min (Zee 2026-10-13).

Data = ONLY what Saad_drl.mq5 logged in the MT5 Strategy Tester (InpDrlLog + InpMetaLog), no mock data:
    Common\\Files\\saad_drl_<tag>.csv        observation at each entry [ER14, ATR14/ATR200, realized vol, EMA50 dist, side]
    Common\\Files\\saad_meta_<tag>_out.csv   the trade's final net $ at 1 lot (partial + runner + swap + $4/lot)
Environment: the agent walks through the Jan-Jun trades in order; action a in [-1, 1] -> lot multiplier
m = 1 + a (0..2; Zee: up to 2 lots); reward = log(1 + m x net / equity) (Kelly log-wealth).
Observations are z-scored with Jan-Jun statistics (baked into the EA too).
Writes models/ppo_sizing_agent.zip and mt5/SaadDrlPolicy.mqh (the policy network as MQL5, so the
Strategy Tester can judge it). The replay here is a HYPOTHESIS; only MT5 promotes.
    py drl_train.py [--tag 8] [--cutoff 2026-07-01] [--steps 100000] [--seed 0]"""
import argparse, shutil, sys
from pathlib import Path
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env

ROOT = Path(__file__).resolve().parents[1]; REPO = ROOT.parent
COMMON = Path.home() / "AppData/Roaming/MetaQuotes/Terminal/Common/Files"
OBS = ["o_er", "o_atr_ratio", "o_rvol", "o_ema50_dist", "o_side"]


def load(tag):
    fd, fo = COMMON / f"saad_drl_{tag}.csv", COMMON / f"saad_meta_{tag}_out.csv"
    for f in (fd, fo):
        if not f.exists(): sys.exit(f"missing {f}: run Saad_drl with InpDrlLog=true, InpMetaLog=true, InpMetaTag={tag}, InpDrlMode=0")
    D, O = pd.read_csv(fd), pd.read_csv(fo)
    if (D["mult"] >= 0).any(): sys.exit("log came from a SIZED run: train only on an InpDrlMode=0 run (1 lot every trade)")
    df = D.merge(O[["pos_id", "net"]], on="pos_id").assign(time=lambda d: pd.to_datetime(d.time, format="%Y.%m.%d %H:%M:%S"))
    shutil.copy(fd, ROOT / "data" / "drl_observations.csv")
    print(f"[+] {len(df)} trades with observation + outcome ({df.time.min():%Y-%m-%d} .. {df.time.max():%Y-%m-%d})")
    return df.sort_values("time").reset_index(drop=True)


class SizingEnv(gym.Env):
    def __init__(self, X, pnl, balance=25000.0, random_start=True):
        super().__init__()
        self.X, self.pnl, self.b0, self.rs = X.astype(np.float32), pnl.astype(np.float64), balance, random_start
        self.action_space = spaces.Box(-1.0, 1.0, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(-10.0, 10.0, shape=(X.shape[1],), dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.i = int(self.np_random.integers(0, len(self.X) // 2)) if self.rs else 0
        self.bal = self.b0
        return self.X[self.i], {}

    def step(self, action):
        m = float(np.clip(1.0 + action[0], 0.0, 2.0))
        r_pct = m * self.pnl[self.i] / self.bal
        self.bal += m * self.pnl[self.i]
        if self.bal <= 0:
            return self.X[self.i], -10.0, True, False, {}
        reward = float(np.log1p(max(-0.99, r_pct)))
        self.i += 1
        done = self.i >= len(self.X)
        return self.X[min(self.i, len(self.X) - 1)], reward, done, False, {}


def policy_mult(model, Xz):
    a, _ = model.predict(Xz.astype(np.float32), deterministic=True)
    return np.clip(1.0 + a[:, 0], 0.0, 2.0)


def manual_mult(layers, Xz):
    h = Xz.astype(np.float64)
    for k, (W, b) in enumerate(layers):
        h = h @ W.T + b
        if k < len(layers) - 1: h = np.tanh(h)
    return np.clip(1.0 + np.clip(h[:, 0], -1, 1), 0.0, 2.0)


def replay(m, pnl, b0=25000.0):
    eq = b0 + np.cumsum(m * pnl); peak = np.maximum.accumulate(np.r_[b0, eq])[1:]
    return float((m * pnl).sum()), float((peak - eq).max()), float(m.mean())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="8"); ap.add_argument("--cutoff", default="2026-07-01")
    ap.add_argument("--steps", type=int, default=100_000); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--name", default="")
    a = ap.parse_args()
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    df = load(a.tag)
    tr, te = df[df.time < a.cutoff].reset_index(drop=True), df[df.time >= a.cutoff].reset_index(drop=True)
    mu, sd = tr[OBS].mean().to_numpy(), tr[OBS].std().replace(0, 1).to_numpy()
    z = lambda d: np.clip((d[OBS].to_numpy() - mu) / sd, -10, 10)
    Xtr, Xte = z(tr), z(te)
    print(f"[+] train {len(tr)} trades, unseen {len(te)}; PPO {a.steps:,} steps")
    env = make_vec_env(lambda: SizingEnv(Xtr, tr.net.to_numpy()), n_envs=4, seed=a.seed)
    model = PPO("MlpPolicy", env, learning_rate=3e-4, n_steps=512, batch_size=64, ent_coef=0.01, gamma=0.99,
                seed=a.seed, verbose=0, device="cpu")
    model.learn(total_timesteps=a.steps)
    (ROOT / "models").mkdir(exist_ok=True); model.save(ROOT / "models" / f"ppo_sizing_agent{a.name}")

    # export: policy_net (Linear, Tanh, Linear, Tanh) + action_net (Linear)
    pn = [l for l in model.policy.mlp_extractor.policy_net if isinstance(l, torch.nn.Linear)] + [model.policy.action_net]
    layers = [(l.weight.detach().numpy().astype(np.float64), l.bias.detach().numpy().astype(np.float64)) for l in pn]
    allX = np.vstack([Xtr, Xte])
    gap = float(np.abs(policy_mult(model, allX) - manual_mult(layers, allX)).max())
    print(f"[+] parity SB3 predict vs exported network: max |diff| {gap:.2e}  {'OK' if gap < 1e-5 else 'MISMATCH'}")
    arr = lambda v: ", ".join(f"{x:.17g}" for x in np.ravel(v))
    L = [f"// SaadDrlPolicy.mqh - GENERATED by meta_labeling_system/src/drl_train.py — do not edit.",
         f"// PPO (stable-baselines3) policy, trained on {tr.time.min():%Y-%m-%d}..{tr.time.max():%Y-%m-%d} ({len(tr)} trades), {a.steps} steps, seed {a.seed}",
         f"#define DRL_NOBS {len(OBS)}", f'#define DRL_TRAINED "{tr.time.min():%Y-%m-%d}..{tr.time.max():%Y-%m-%d}"',
         f"double DRL_MU[{len(OBS)}] = {{{arr(mu)}}};", f"double DRL_SD[{len(OBS)}] = {{{arr(sd)}}};"]
    for k, (W, b) in enumerate(layers):
        L += [f"double DRL_W{k}[{W.size}] = {{{arr(W)}}};   // {W.shape[0]} x {W.shape[1]}", f"double DRL_B{k}[{b.size}] = {{{arr(b)}}};"]
    sizes = [(W.shape[0], W.shape[1]) for W, _ in layers]
    L += ["double DrlPolicy(const double &o[])", "{",
          f"   double z[{len(OBS)}]; for (int j = 0; j < {len(OBS)}; j++) z[j] = MathMax(-10.0, MathMin(10.0, (o[j] - DRL_MU[j]) / DRL_SD[j]));",
          f"   double h1[{sizes[0][0]}], h2[{sizes[1][0]}];",
          f"   for (int r = 0; r < {sizes[0][0]}; r++) {{ double s = DRL_B0[r]; for (int c = 0; c < {sizes[0][1]}; c++) s += DRL_W0[r * {sizes[0][1]} + c] * z[c]; h1[r] = MathTanh(s); }}",
          f"   for (int r = 0; r < {sizes[1][0]}; r++) {{ double s = DRL_B1[r]; for (int c = 0; c < {sizes[1][1]}; c++) s += DRL_W1[r * {sizes[1][1]} + c] * h1[c]; h2[r] = MathTanh(s); }}",
          f"   double a = DRL_B2[0]; for (int c = 0; c < {sizes[2][1]}; c++) a += DRL_W2[c] * h2[c];",
          "   a = MathMax(-1.0, MathMin(1.0, a));",
          "   return 1.0 + a;                       // lot multiplier 0..2", "}"]
    mqh = REPO / "mt5" / f"SaadDrlPolicy{a.name}.mqh"; mqh.write_text("\n".join(L) + "\n", encoding="utf-8"); shutil.copy(mqh, ROOT / "mql5" / mqh.name)
    pd.DataFrame({"pos_id": df.pos_id, "time": df.time, "mult": policy_mult(model, allX)}).to_csv(ROOT / "data" / f"python_drl_mult{a.name}.csv", index=False)

    print("\n[+] Python replay (fixed trades, P&L scaled by the multiplier - a HYPOTHESIS, MT5 decides):")
    for name, d, X in (("Jan-Jun (trained on)", tr, Xtr), ("Jul-Oct (unseen)", te, Xte)):
        m = policy_mult(model, X); pnl = d.net.to_numpy()
        n1, dd1, _ = replay(np.ones(len(d)), pnl); nm, ddm, avg = replay(m, pnl); nc, ddc, _ = replay(np.full(len(d), avg), pnl)
        print(f"  {name:22s} 1 lot: net {n1:>9,.0f} DD {dd1:>7,.0f} | PPO (avg x{avg:.2f}, {int((m < 0.1).sum())} skipped): net {nm:>9,.0f} DD {ddm:>7,.0f} "
              f"| constant x{avg:.2f}: net {nc:>9,.0f} DD {ddc:>7,.0f}")
    print(f"[+] saved models/ppo_sizing_agent{a.name}.zip and {mqh}")
