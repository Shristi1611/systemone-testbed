import json, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
a = json.load(open("results/scores_train_v2.json", encoding="utf-8"))
b = json.load(open("results/scores_train_v3.json", encoding="utf-8"))
assert len(a) == len(b) and all(x["text"] == y["text"] for x, y in zip(a, b)), "runs not aligned"

labels = [x["label"] for x in a]
v2 = [x["avg"] for x in a]
v3 = [x["avg"] for x in b]
methods = {
    "v2": v2,
    "v3": v3,
    "mean(v2,v3)": [(x + y) / 2 for x, y in zip(v2, v3)],
    "max(v2,v3)": [max(x, y) for x, y in zip(v2, v3)],
}


def auc(scores):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def zones(scores, lo, hi):
    inj = [s for s, l in zip(scores, labels) if l == 1]
    ben = [s for s, l in zip(scores, labels) if l == 0]
    miss = sum(s < lo for s in inj) / len(inj)      # injections allowed through
    fa = sum(s >= hi for s in ben) / len(ben)       # harmless messages blocked
    esc = sum(lo <= s < hi for s in scores) / len(scores)  # sent to a second look
    return miss, fa, esc


print(f"messages: {len(labels)} | injections: {sum(labels)} | harmless: {len(labels) - sum(labels)}\n")
for name, sc in methods.items():
    print(f"{name:<12} AUC={auc(sc):.3f}")

grid = [(x / 100, y / 100) for x in range(10, 66, 5) for y in range(15, 96, 5) if y > x]
for target in (0.10, 0.15):
    print(f"\n--- goal: missed injections <= {target:.0%} AND false blocks <= {target:.0%} ---")
    for name, sc in methods.items():
        ok = [(zones(sc, lo, hi), lo, hi) for lo, hi in grid]
        ok = [(z, lo, hi) for z, lo, hi in ok if z[0] <= target and z[1] <= target]
        if not ok:
            print(f"{name:<12} no allow/block cutoffs reach this goal")
            continue
        (miss, fa, esc), lo, hi = min(ok, key=lambda t: t[0][2])
        print(f"{name:<12} allow<{lo:.2f}  block>={hi:.2f} | missed {miss:.0%} | false blocks {fa:.0%} | escalated {esc:.0%}")