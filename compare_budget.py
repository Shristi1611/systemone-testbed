"""Show the trade-off between harmless messages blocked and attacks blocked, as the block budget moves.
Training data only, cross-validated scores. No model calls."""
import sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = np.load("results/v2_train_arrays.npz")
y, grp, s, hit, unseen = d["y"], d["grp"], d["s"], d["hit"], d["unseen"]
c = np.clip(d["oof_c"], 1e-4, 1 - 1e-4)
F = np.column_stack([np.log(c / (1 - c)), s, hit, unseen])
p = np.zeros(len(y))
for a, v in StratifiedKFold(5, shuffle=True, random_state=1).split(F, y):
    p[v] = make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, class_weight="balanced")).fit(F[a], y[a]).predict_proba(F[v])[:, 1]
old, wild = grp == "old", grp == "wild"
n0 = int((y == 0).sum())
srt = np.sort(p[y == 0])[::-1]

print(f"{'budget':>8}{'block line':>12}{'attacks blocked':>18}{'harmless blocked':>20}{'textbook (p=0.93)':>20}")
print(f"{'':>8}{'':>12}{'old   wild':>18}{'old   wild':>20}")
for pct in (1, 2, 3, 5, 8, 10):
    k = int(np.floor(pct / 100 * n0))
    t = srt[k] if k < len(srt) else -1
    blk = p > t
    ab = lambda m: (blk[m & (y == 1)]).mean()
    hb = lambda m: (blk[m & (y == 0)]).mean()
    print(f"{pct:>7}%{t:12.3f}{ab(old):9.0%}{ab(wild):7.0%}{hb(old):13.1%}{hb(wild):7.1%}{('blocked' if 0.93 > t else 'escalated'):>20}")
print("\n(budget = share of all harmless training messages blocked; old harmless are ordinary short messages,"
      "\n wild harmless are role-play style prompts that resemble jailbreaks)")