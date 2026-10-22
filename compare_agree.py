"""Test an agreement block on top of v2: block when rule hit + guard + classifier all agree.
The agreement block shares the 1% budget of harmless messages blocked (the combined-score block line moves up
to compensate). Training data only, cross-validated scores. No model calls."""
import sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = np.load("results/v2_train_arrays.npz")
y, grp, s, hit, unseen, c0 = d["y"], d["grp"], d["s"], d["hit"], d["unseen"], d["oof_c"]
c = np.clip(c0, 1e-4, 1 - 1e-4)
F = np.column_stack([np.log(c / (1 - c)), s, hit, unseen])
p = np.zeros(len(y))
for a, v in StratifiedKFold(5, shuffle=True, random_state=1).split(F, y):
    p[v] = make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, class_weight="balanced")).fit(F[a], y[a]).predict_proba(F[v])[:, 1]
guard_ok = (s < 0.25) & (hit == 0) & (unseen == 0)
t_allow, q = 0.203, 0.46   # from finalize_v2.py
n0 = int((y == 0).sum())
budget = int(np.floor(0.01 * n0))   # at most 14 harmless blocked overall


def zones(extra):
    """Returns zones, or None if the agreement rule alone already exceeds the budget."""
    spent = int((extra & (y == 0)).sum())
    left = budget - spent
    if left < 0:
        return None, None
    rest = np.sort(p[(y == 0) & ~extra])[::-1]
    t_block = rest[left] if left < len(rest) else -1.0   # exactly `left` remaining harmless are above it
    blk = (p > t_block) | extra
    allow = ((p < t_allow) | (guard_ok & (p < q))) & ~blk
    return np.where(blk, "block", np.where(allow, "allow", "escalate")), float(t_block)


def show(label, z):
    print(label)
    for gname, m in (("old ", grp == "old"), ("wild", grp == "wild")):
        out = f"   {gname}"
        for lab, ln in ((1, "attacks"), (0, "harmless")):
            sel = m & (y == lab)
            out += f"  {ln}: " + " ".join(f"{k[:3]} {(z[sel] == k).mean():4.0%}" for k in ("block", "escalate", "allow")) + "  |"
        print(out)
    print(f"   harmless blocked overall: {int((z[y == 0] == 'block').sum())} of {n0} ({(z[y == 0] == 'block').mean():.2%})"
          f"   attacks blocked overall: {(z[y == 1] == 'block').mean():.1%}   attacks allowed overall: {(z[y == 1] == 'allow').mean():.1%}")


z0, tb0 = zones(np.zeros(len(y), bool))
show(f"v2 without agreement block (block line {tb0:.3f}, budget {budget} harmless):", z0)

best = None
for need_hit in (True, False):
    for gmin in np.linspace(0.3, 0.95, 14):
        for cmin in np.linspace(0.3, 0.95, 14):
            extra = (s >= gmin) & (c0 >= cmin) & ((hit > 0) if need_hit else np.ones(len(y), bool))
            z, tb = zones(extra)
            if z is None:
                continue
            ab = (z[y == 1] == "block").mean()
            if best is None or ab > best[0]:
                best = (ab, need_hit, gmin, cmin, tb)
ab, need_hit, gmin, cmin, tb = best
extra = (s >= gmin) & (c0 >= cmin) & ((hit > 0) if need_hit else np.ones(len(y), bool))
z, _ = zones(extra)
show(f"with agreement block (rule hit required: {need_hit}, guard >= {gmin:.2f}, classifier >= {cmin:.2f}; "
     f"score block line moves to {tb:.3f}):", z)
textbook = (0.9029 >= gmin) and (0.938 >= cmin) and need_hit
print("\nthe textbook attack (hits override+marker, guard 0.90, classifier 0.94) would "
      + ("be blocked" if textbook else "still only be escalated"))