"""Compare classifier heads on identical folds (training data only, no model calls, no sealed data)."""
import sys, time
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.neural_network import MLPClassifier

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = np.load("results/v2_train_arrays.npz")
X, idx, y, grp = d["X"], d["idx"], d["y"], d["grp"]
M = len(y)
rows_of = [np.where(idx == i)[0] for i in range(M)]
wmask, omask = grp == "wild", grp == "old"

HEADS = {
    "logistic C=1": lambda: LogisticRegression(C=1, max_iter=3000, class_weight="balanced"),
    "logistic C=10 (v2 now)": lambda: LogisticRegression(C=10, max_iter=3000, class_weight="balanced"),
    "logistic C=100": lambda: LogisticRegression(C=100, max_iter=5000, class_weight="balanced"),
    "small neural net": lambda: MLPClassifier(hidden_layer_sizes=(128,), alpha=1e-2, early_stopping=True,
                                              max_iter=300, random_state=0),
    "gradient boosting": lambda: HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08,
                                                                class_weight="balanced", random_state=0),
}

print(f"{M} messages, {len(X)} windows; same folds as build_gateway_v2.py (seed 0)\n")
print(f"{'head':26}{'all':>8}{'old':>8}{'wild':>8}{'minutes':>9}")
results = {}
for name, make in HEADS.items():
    t0 = time.time()
    oof = np.zeros(M)
    for a, v in StratifiedKFold(5, shuffle=True, random_state=0).split(np.zeros(M), y):
        tr = np.concatenate([rows_of[i] for i in a])
        ytr = y[idx[tr]]
        m = make().fit(X[tr], ytr)
        for i in v:
            oof[i] = m.predict_proba(X[rows_of[i]])[:, 1].max()
    results[name] = (roc_auc_score(y, oof), roc_auc_score(y[omask], oof[omask]), roc_auc_score(y[wmask], oof[wmask]))
    print(f"{name:26}{results[name][0]:8.3f}{results[name][1]:8.3f}{results[name][2]:8.3f}{(time.time() - t0) / 60:9.1f}")

base = results["logistic C=10 (v2 now)"][2]
best = max(results.items(), key=lambda kv: kv[1][2])
print(f"\nrule: a head must beat the current logistic regression by 0.02 AUC on wild ({base:.3f} -> {base + 0.02:.3f})")
print(f"best on wild: {best[0]} at {best[1][2]:.3f} -> {'beats the rule' if best[1][2] >= base + 0.02 else 'does NOT beat the rule, keep logistic regression'}")