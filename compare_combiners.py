"""Compare ways of combining the signals, on training data only (cross-validated).
Same thresholds rule for all: block above the 99th percentile of harmless scores (1% blocked),
allow below the 5th percentile of attack scores (5% missed). No model calls, no sealed data."""
import sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = np.load("results/v2_train_arrays.npz")
y, grp, s, hit, unseen = d["y"], d["grp"], d["s"], d["hit"], d["unseen"]
ln = np.log1p(d["length"])
c = np.clip(d["oof_c"], 1e-4, 1 - 1e-4)
lc = np.log(c / (1 - c))
wild, old = grp == "wild", grp == "old"

SETS = {
    "linear, all 5 signals (current v2)": np.column_stack([lc, s, hit, unseen, ln]),
    "linear, no length": np.column_stack([lc, s, hit, unseen]),
    "linear + guard x classifier": np.column_stack([lc, s, hit, unseen, ln, lc * s, (1 - s) * lc]),
}
HEADS = {
    "small boosted trees, 5 signals": (np.column_stack([lc, s, hit, unseen, ln]),
                                       lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05,
                                                                              class_weight="balanced", random_state=0)),
    "small boosted trees, no length": (np.column_stack([lc, s, hit, unseen]),
                                       lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05,
                                                                              class_weight="balanced", random_state=0)),
}
variants = {k: (F, lambda: make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, class_weight="balanced")))
            for k, F in SETS.items()}
variants.update(HEADS)


def zones(p, mask_attack_ref=None):
    tb = np.quantile(p[y == 0], 0.99)
    ta = np.quantile(p[y == 1], 0.05)
    z = np.where(p > tb, "block", np.where(p < ta, "allow", "escalate"))
    z = np.where((z == "allow") & (unseen > 0), "escalate", z)
    return z


def row(z, mask, lab):
    sel = mask & (y == lab)
    return "".join(f"{k[:3]} {(z[sel] == k).mean():4.0%}  " for k in ("block", "escalate", "allow"))


print(f"{'variant':38}{'AUC all':>8}{'wild':>7}   (zones: attacks | harmless)")
for name, (F, make) in variants.items():
    p = np.zeros(len(y))
    for a, v in StratifiedKFold(5, shuffle=True, random_state=1).split(F, y):
        p[v] = make().fit(F[a], y[a]).predict_proba(F[v])[:, 1]
    z = zones(p)
    print(f"{name:38}{roc_auc_score(y, p):8.3f}{roc_auc_score(y[wild], p[wild]):7.3f}")
    for gname, m in (("old ", old), ("wild", wild)):
        print(f"     {gname} attacks  {row(z, m, 1)}| harmless  {row(z, m, 0)}")

# the combiner the saved v2 model uses, for the record
m = make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, class_weight="balanced")).fit(SETS["linear, all 5 signals (current v2)"], y)
print("\ncurrent v2 combiner weights (standardised inputs):")
for n, w in zip(["classifier(logit)", "guard", "rule hit", "unseen", "log length"], m[-1].coef_[0]):
    print(f"  {n:18}{w:+.2f}")