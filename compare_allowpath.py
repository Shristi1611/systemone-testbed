"""Test a guard-confirmed allow path on top of the 'no length' combiner. Training data only, cross-validated."""
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

t_block = np.quantile(p[y == 0], 0.99)
guard_ok = (s < 0.25) & (hit == 0) & (unseen == 0)


def zones(t_allow, q):
    allow = (p < t_allow) | (guard_ok & (p < q))
    z = np.where(p > t_block, "block", np.where(allow, "allow", "escalate"))
    return z


def show(label, z):
    print(label)
    for gname, m in (("old ", grp == "old"), ("wild", grp == "wild")):
        out = f"   {gname}"
        for lab, ln in ((1, "attacks"), (0, "harmless")):
            sel = m & (y == lab)
            out += f"  {ln}: " + " ".join(f"{k[:3]} {(z[sel] == k).mean():4.0%}" for k in ("block", "escalate", "allow")) + "  |"
        print(out)
    print(f"   attacks allowed overall: {(z[y == 1] == 'allow').mean():.1%}   harmless blocked overall: {(z[y == 0] == 'block').mean():.1%}")


t_allow = np.quantile(p[y == 1], 0.05)
show("current rule (allow below the 5th percentile of attack scores):", zones(t_allow, 0.0))

# allow path: pick q (largest) so that attacks allowed overall stay at or below 5%
# with the plain allow threshold lowered to keep the same total budget
best = None
for q in np.linspace(0.05, 0.9, 86):
    for ta in np.linspace(0.0, t_allow, 21):
        z = zones(ta, q)
        if (z[y == 1] == "allow").mean() <= 0.05:
            gain = (z[y == 0] == "allow").mean()
            if best is None or gain > best[0]:
                best = (gain, ta, q)
gain, ta, q = best
show(f"with guard-confirmed allow path (plain allow below {ta:.3f}, or guard<0.25 + no rule hit + score below {q:.2f}):", zones(ta, q))