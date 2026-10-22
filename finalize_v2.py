"""Fit the final v2 combiner (no length, guard-confirmed allow path, 3% block budget) on training data only.
Writes results/v2_final.joblib. No model calls, no sealed data."""
import sys
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
GUARD_LO = 0.25
BLOCK_BUDGET = 0.03   # Amendment 2: at most 3% of all harmless training messages blocked
d = np.load("results/v2_train_arrays.npz")
y, grp, s, hit, unseen = d["y"], d["grp"], d["s"], d["hit"], d["unseen"]
c = np.clip(d["oof_c"], 1e-4, 1 - 1e-4)
F = np.column_stack([np.log(c / (1 - c)), s, hit, unseen])


def make():
    return make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, class_weight="balanced"))


p = np.zeros(len(y))
for a, v in StratifiedKFold(5, shuffle=True, random_state=1).split(F, y):
    p[v] = make().fit(F[a], y[a]).predict_proba(F[v])[:, 1]

n0 = int((y == 0).sum())
srt = np.sort(p[y == 0])[::-1]
t_block = float(srt[int(np.floor(BLOCK_BUDGET * n0))])   # about 3% of harmless are above this
t_allow0 = float(np.quantile(p[y == 1], 0.05))
guard_ok = (s < GUARD_LO) & (hit == 0) & (unseen == 0)


def allowed(ta, q):
    return (p < ta) | (guard_ok & (p < q))


best = None
for q in np.linspace(0.05, 0.9, 86):
    for ta in np.linspace(0.0, t_allow0, 21):
        al = allowed(ta, q) & ~(p > t_block)
        miss = al[y == 1].mean()
        if miss <= 0.05:
            ok = al[y == 0].mean()
            if best is None or ok > best[0]:
                best = (ok, float(ta), float(q))
ok, t_allow, q_path = best
print(f"thresholds: block above {t_block:.3f}; allow below {t_allow:.3f}; "
      f"or guard < {GUARD_LO} + no rule hit + score below {q_path:.2f}")

blk = p > t_block
al = allowed(t_allow, q_path) & ~blk
print("\ntraining, cross-validated:")
for name, m in (("old ", grp == "old"), ("wild", grp == "wild")):
    out = f"   {name}"
    for lab, ln in ((1, "attacks"), (0, "harmless")):
        sel = m & (y == lab)
        esc = ~blk & ~al
        out += f"  {ln}: block {blk[sel].mean():4.0%} escalate {esc[sel].mean():4.0%} allow {al[sel].mean():4.0%}  |"
    print(out)
print(f"   attacks allowed overall {al[y == 1].mean():.1%}; harmless blocked overall {blk[y == 0].mean():.1%}")

src = joblib.load("results/v2_model.joblib")
comb = make().fit(F, y)
joblib.dump({"clf": src["clf"], "comb": comb, "t_block": t_block, "t_allow": t_allow, "q_path": q_path,
             "guard_lo": GUARD_LO, "block_budget": BLOCK_BUDGET,
             "features": ["logit_clf", "guard", "rule_hit", "unseen"]}, "results/v2_final.joblib")
print("\nsaved results/v2_final.joblib")