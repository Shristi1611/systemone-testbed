"""Score train_wild with a public injection detector and see if it adds to the retrained classifier.
Training data only. No sealed data. No Laya or Ollama needed."""
import json, os, sys
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from gateway import windows

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
NAME = "protectai/deberta-v3-base-prompt-injection-v2"
OUT = "results/detector_wild.jsonl"

rows = [json.loads(l) for l in open("results/pool_v2.jsonl", encoding="utf-8")]
rows = [r for r in rows if r["pool"] == "train_wild"]
done = {}
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        r = json.loads(line)
        done[r["k"]] = r["p"]

tok = AutoTokenizer.from_pretrained(NAME)
model = AutoModelForSequenceClassification.from_pretrained(NAME).eval()
torch.set_num_threads(4)
print(f"{len(done)} of {len(rows)} already scored")

with open(OUT, "a", encoding="utf-8") as f:
    for n, r in enumerate(rows):
        if r["k"] in done:
            continue
        ps = []
        ws = windows(r["text"])
        for i in range(0, len(ws), 4):
            enc = tok(ws[i:i + 4], truncation=True, max_length=512, padding=True, return_tensors="pt")
            with torch.no_grad():
                ps += torch.softmax(model(**enc).logits, dim=-1)[:, 1].tolist()
        done[r["k"]] = max(ps)
        f.write(json.dumps({"k": r["k"], "p": done[r["k"]]}) + "\n")
        f.flush()
        if len(done) % 50 == 0:
            print(f"  {len(done)} of {len(rows)} scored")

y = np.array([r["label"] for r in rows])
p = np.array([done[r["k"]] for r in rows])
d = np.load("results/v2_train_arrays.npz")
oof_c = d["oof_c"][d["grp"] == "wild"]
assert len(oof_c) == len(rows)


def logit(a):
    a = np.clip(a, 1e-4, 1 - 1e-4)
    return np.log(a / (1 - a))


print("\nAUC on the wild training pool (jailbreak vs regular prompt):")
print(f"  public detector alone            {roc_auc_score(y, p):.3f}")
print(f"  retrained classifier alone       {roc_auc_score(y, oof_c):.3f}")
F = np.column_stack([logit(oof_c), logit(p)])
oof = np.zeros(len(y))
for a, v in StratifiedKFold(5, shuffle=True, random_state=0).split(F, y):
    oof[v] = LogisticRegression(max_iter=1000).fit(F[a], y[a]).predict_proba(F[v])[:, 1]
gain = roc_auc_score(y, oof) - roc_auc_score(y, oof_c)
print(f"  both together (cross-validated)  {roc_auc_score(y, oof):.3f}   gain {gain:+.3f}")
print(f"\nrule: keep the detector only if the gain is at least 0.02 -> {'keep, worth testing further' if gain >= 0.02 else 'drop it'}")