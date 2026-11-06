"""replicate.py - DIAGNOSTIC ONLY (selects nothing): does a condition's train risk carry over to test AT ALL?
For every base condition of beam.py (support >= 1% of train): train O/E (losses / feed-regime-expected losses) and test lift (test loss rate /
test base). Reports the Spearman correlation across conditions, and the test lift of the conditions that looked riskiest on train.
Also the same within train: Mar-Apr O/E vs May-Jun9 (old feed only), to separate noise from the feed change.
Run: cd .../pockets && py method_b_beam/replicate.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXCL = set(sys.argv[sys.argv.index("--exclude") + 1].split(",")) if "--exclude" in sys.argv else set()
src = open(os.path.join(HERE, "beam.py"), encoding="utf-8").read()
head = src.split("# ----------------------------------------------------------------------------------------------------------------------------- search")[0]
sys.argv = [sys.argv[0]]
g = {"__file__": os.path.join(HERE, "beam.py"), "__name__": "beam_head"}
exec(compile(head, "beam_head", "exec"), g)
np, D, conds, C_all, TR, TE, Y, REG, ctext = (g[k] for k in ("np", "D", "conds", "C_all", "TR", "TE", "Y", "REG", "ctext"))


def rank(a):
    o = np.argsort(a, kind="stable")
    r = np.empty(len(a))
    r[o] = np.arange(len(a))
    # average ties
    u, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
    s = np.bincount(inv, weights=r) / cnt
    return s[inv]


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def oe(mask_half, cm):
    """O/E with feed-regime expected rates computed inside the half."""
    y = Y[mask_half]
    reg = REG[mask_half]
    pe = np.zeros(len(y))
    for r in (0, 1):
        if (reg == r).any():
            pe[reg == r] = y[reg == r].mean()
    m = cm[:, mask_half].astype(np.float32)
    O = m @ y.astype(np.float32)
    E = m @ pe.astype(np.float32)
    n = m.sum(1)
    return O, E, n


O_tr, E_tr, n_tr = oe(TR, C_all)
O_te, E_te, n_te = oe(TE, C_all)
FOK = np.array([c["f"] not in EXCL for c in conds])
if EXCL:
    print(f"EXCLUDING conditions on: {sorted(EXCL)}")
ok = (n_tr >= 34) & (n_te >= 34) & FOK
r_tr, r_te = O_tr / np.maximum(E_tr, 1e-9), O_te / np.maximum(E_te, 1e-9)
print(f"{ok.sum()} conditions with >= 34 trades in both halves")
print(f"Spearman(train O/E, test O/E) across conditions = {spearman(r_tr[ok], r_te[ok]):+.3f}")
for top in (10, 25, 50, 100, 200):
    idx = np.flatnonzero(ok)[np.argsort(-r_tr[ok], kind="stable")[:top]]
    # weight by test trades: pooled test lift of each condition, averaged
    print(f"  top {top:3d} train-riskiest conditions: mean train O/E {r_tr[idx].mean():.2f} -> mean test O/E {r_te[idx].mean():.2f} "
          f"(share of them with test O/E > 1: {100*(r_te[idx] > 1).mean():.0f}%)")
idx = np.flatnonzero(ok)[np.argsort(-r_tr[ok], kind="stable")[:15]]
print("\n  the 15 train-riskiest single conditions (train O/E, n | test O/E, n):")
for i in idx:
    print(f"    {ctext(conds[i]):48s} train {r_tr[i]:4.2f} ({int(O_tr[i])}/{int(n_tr[i])}) | test {r_te[i]:4.2f} ({int(O_te[i])}/{int(n_te[i])})")

# within train, old feed only: Mar-Apr vs May 1 - Jun 9
A = TR & (D.id < "0501").to_numpy()
Bm = TR & (D.id >= "0501").to_numpy() & (REG == 0)
O_a, E_a, n_a = oe(A, C_all)
O_b, E_b, n_b = oe(Bm, C_all)
ok2 = (n_a >= 20) & (n_b >= 20) & FOK
ra, rb = O_a / np.maximum(E_a, 1e-9), O_b / np.maximum(E_b, 1e-9)
print(f"\nWITHIN OLD FEED: Spearman(Mar-Apr O/E, May-Jun9 O/E) across {ok2.sum()} conditions = {spearman(ra[ok2], rb[ok2]):+.3f}")
for top in (25, 100):
    idx = np.flatnonzero(ok2)[np.argsort(-ra[ok2], kind="stable")[:top]]
    print(f"  top {top:3d} Mar-Apr riskiest: mean O/E {ra[idx].mean():.2f} -> May-Jun9 {rb[idx].mean():.2f}")
# null for the Spearman: circular shift of test labels
rng = np.random.default_rng(7)
yte = Y[TE].copy()
null = []
m_te = C_all[:, TE].astype(np.float32)
for _ in range(200):
    s = int(rng.integers(int(0.1 * len(yte)), int(0.9 * len(yte))))
    yp = np.roll(yte, s).astype(np.float32)
    rt = (m_te @ yp) / np.maximum(m_te.sum(1) * yp.mean(), 1e-9)
    null.append(spearman(r_tr[ok], rt[ok]))
null = np.array(null)
print(f"\nnull (test outcomes circularly shifted, 200x): Spearman mean {null.mean():+.3f}, 2.5-97.5% [{np.quantile(null,.025):+.3f}, "
      f"{np.quantile(null,.975):+.3f}]")
