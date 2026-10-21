"""Train a second look for the escalate zone, on training messages only.
Cutoffs are fixed here from cross-validated training scores and saved for one later check."""
import json, sys
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from gateway import LO, HI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
THR = joblib.load("results/clf_mixed.joblib")["thr"]
ALLOW_MAX_INJ = 0.03   # fixed before running: at most 3% injections among those allowed
BLOCK_MAX_HARM = 0.05  # fixed before running: at most 5% harmless among those blocked

recs = [json.loads(l) for l in open("results/train_scores.jsonl", encoding="utf-8")]
print(f"scored training messages: {len(recs)}")


def decision(r):
    evidence = bool(r["h"]) or r["c"] >= THR
    s = r["s"]
    if evidence:
        d = "block" if s >= LO else "escalate"
    elif s >= HI:
        d = "escalate"
    else:
        d = "allow" if s < LO else "escalate"
    if r["unseen"] and d == "allow":
        d = "escalate"
    return d


def feats(r):
    return [r["s"], r["c"], 1.0 if r["h"] else 0.0]


zone = [r for r in recs if decision(r) == "escalate"]
y = np.array([r["y"] for r in zone])
X = np.array([feats(r) for r in zone])
print(f"\nfrozen gateway on training data: " + ", ".join(
    f"{k} {sum(decision(r) == k for r in recs)}" for k in ("allow", "escalate", "block")))
print(f"escalate zone: {len(zone)} messages, {int(y.sum())} injections, {len(y) - int(y.sum())} harmless")
for src in sorted({r["src"] for r in zone}):
    z = [r for r in zone if r["src"] == src]
    print(f"  {src:14}{len(z):>5} messages, {sum(r['y'] for r in z):>4} injections")

if y.sum() < 20 or len(y) - y.sum() < 20:
    raise SystemExit("too few messages of one class in the zone to train a second look")

oof = cross_val_predict(LogisticRegression(max_iter=1000), X, y,
                        cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
print("\nhow well each score ranks injections above harmless inside the zone (AUC, 0.5 = random):")
print(f"  guard score alone        {roc_auc_score(y, X[:, 0]):.3f}")
print(f"  classifier score alone   {roc_auc_score(y, X[:, 1]):.3f}")
print(f"  second look (cross-val)  {roc_auc_score(y, oof):.3f}")

# cutoffs from cross-validated training scores only
order = np.argsort(oof)
ys = y[order]
lo = 0.0
for i in range(20, len(ys) + 1):
    if ys[:i].mean() <= ALLOW_MAX_INJ:
        lo = float(oof[order][i - 1])
hi = 1.0
for i in range(20, len(ys) + 1):
    if (1 - ys[::-1][:i]).mean() <= BLOCK_MAX_HARM:
        hi = float(oof[order][::-1][i - 1])
hi = max(hi, lo)
print(f"\nfixed cutoffs: allow below {lo:.3f}, block above {hi:.3f}, in between stays escalate")

d = np.where(oof < lo, "allow", np.where(oof > hi, "block", "escalate"))
print("\nwhat the second look does to the training escalate zone (cross-validated):")
print(f"{'':12}{'allow':>8}{'escalate':>10}{'block':>8}")
for name, lab in (("injections", 1), ("harmless", 0)):
    m = y == lab
    print(f"{name:12}{(d[m] == 'allow').sum():>8}{(d[m] == 'escalate').sum():>10}{(d[m] == 'block').sum():>8}")
rest = (d == "escalate").mean()
print(f"still escalated: {100 * rest:.0f}% of the zone")

model = LogisticRegression(max_iter=1000).fit(X, y)
joblib.dump({"model": model, "lo": lo, "hi": hi, "thr": THR}, "results/second_look.joblib")
print("coefficients (guard, classifier, rule hit):", np.round(model.coef_[0], 2).tolist())
print("saved results/second_look.joblib")