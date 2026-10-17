import json, sys
from datasets import load_dataset
from rules import hits

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
a = json.load(open("results/scores_test_v2.json", encoding="utf-8"))
b = json.load(open("results/scores_test_v3.json", encoding="utf-8"))
ds = load_dataset("deepset/prompt-injections")["test"]
rows = [{"text": r["text"], "label": r["label"]} for r in ds]
assert len(rows) == len(a) == len(b)
for r, x, y in zip(rows, a, b):
    assert r["text"][:200] == x["text"] == y["text"]
    r["s"] = (x["avg"] + y["avg"]) / 2
    r["hit"] = bool(hits(r["text"]))

inj = [r for r in rows if r["label"] == 1]
ben = [r for r in rows if r["label"] == 0]


def auc(pos, neg):
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def report(name, fn):
    miss = sum(1 for r in inj if fn(r) == "allow") / len(inj)
    fb = sum(1 for r in ben if fn(r) == "block") / len(ben)
    print(f"{name:<28} injections allowed {miss:>4.0%} | harmless blocked {fb:>4.0%}")


report("rules only", lambda r: "block" if r["hit"] else "allow")
report("guard only (cutoff 0.5)", lambda r: "block" if r["s"] >= 0.5 else "allow")
report("block if rules OR guard", lambda r: "block" if (r["hit"] or r["s"] >= 0.5) else "allow")
report("block if rules AND guard", lambda r: "block" if (r["hit"] and r["s"] >= 0.5) else "allow")

rest = [r for r in rows if not r["hit"]]
pi = [r["s"] for r in rest if r["label"] == 1]
pb = [r["s"] for r in rest if r["label"] == 0]
print(f"\nmessages with no rule hit: {len(rest)} ({len(pi)} injections, {len(pb)} harmless)")
print(f"guard AUC on those alone: {auc(pi, pb):.3f}   (0.5 = adds nothing beyond the rules)")