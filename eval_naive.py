"""Compare simple 'naive' apps with the gateway on the same saved scores (no model calls)."""
import json, sys
import joblib
import numpy as np
from gateway import LO, HI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
THR = joblib.load("results/clf_mixed.joblib")["thr"]


def load(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        out[r["k"]] = r
    return out


cache = {**load("results/gw_cache.jsonl"), **load("results/hi_cache.jsonl")}
train = [json.loads(l) for l in open("results/train_scores.jsonl", encoding="utf-8")]
G90 = float(np.quantile([r["s"] for r in train if r["y"] == 0], 0.90))
items = [json.loads(l) for l in open("results/eval_sets.jsonl", encoding="utf-8")]


def gateway(r):
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


VARIANTS = [
    ("naive: model only, cutoff 0.50", lambda r: "block" if r["s"] >= 0.50 else "allow"),
    (f"naive: model only, train cutoff {G90:.2f}", lambda r: "block" if r["s"] >= G90 else "allow"),
    ("naive: rules only", lambda r: "block" if r["h"] else "allow"),
    (f"naive: classifier only ({THR:.2f})", lambda r: "block" if r["c"] >= THR else "allow"),
    ("OUR GATEWAY (with classifier)", gateway),
]
SETS = [("held-out (deepset test, NotInject, no_robots)", "heldout"), ("fresh benchmark", "fresh"),
        ("Hindi / Hinglish set", "hindi"), ("hand-written probes", "probe")]

print(f"train cutoff for 'model only' = {G90:.3f} (90th percentile of training harmless guard scores); classifier cutoff {THR:.2f}")
print("cutoffs were fixed on training data only. a/e/b = allow / escalate / block counts\n")
for title, kind in SETS:
    atk, har, missing = [], [], 0
    for it in items:
        if it["kind"] != kind:
            continue
        r = cache.get(it["k"])
        if r is None:
            missing += 1
            continue
        (atk if it["label"] == 1 else har).append(r)
    print(f"=== {title}: {len(atk)} attacks, {len(har)} harmless (without saved scores: {missing}) ===")
    print(f"{'app':42}{'attacks  a/e/b':>18}{'harmless  a/e/b':>20}")
    for name, fn in VARIANTS:
        ca = [sum(fn(r) == k for r in atk) for k in ("allow", "escalate", "block")]
        ch = [sum(fn(r) == k for r in har) for k in ("allow", "escalate", "block")]
        print(f"{name:42}{ca[0]:>7}{ca[1]:>5}{ca[2]:>5}{ch[0]:>9}{ch[1]:>5}{ch[2]:>5}")
    print()
print("attacks: you want 'a' (allowed) LOW. harmless: you want 'b' (blocked) LOW; 'e' means nobody has decided.")