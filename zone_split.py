"""Count what is inside the training escalate zone, by kind. Changes nothing."""
import json, sys
import joblib
from gateway import LO, HI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
THR = joblib.load("results/clf_mixed.joblib")["thr"]
recs = [json.loads(l) for l in open("results/train_scores.jsonl", encoding="utf-8")]


def kind(r):
    rule = bool(r["h"])
    clf = r["c"] >= THR
    s = r["s"]
    if rule or clf:
        if s >= LO:
            return None  # blocked, not in the zone
        return "A1: rule hit, guard low" if rule else "A2: classifier only, guard low"
    if s < LO:
        return "C: allowed but part of input unseen" if r["unseen"] else None
    if s >= HI:
        return "B2: no evidence, guard 0.50 or more"
    return "B1: no evidence, guard 0.25 to 0.50"


zone = [(kind(r), r) for r in recs]
zone = [(k, r) for k, r in zone if k]
print(f"training escalate zone: {len(zone)} messages\n")
print(f"{'kind':44}{'n':>5}{'injections':>12}{'harmless':>10}   injection share")
for k in sorted({k for k, _ in zone}):
    rs = [r for kk, r in zone if kk == k]
    inj = sum(r["y"] for r in rs)
    print(f"{k:44}{len(rs):>5}{inj:>12}{len(rs) - inj:>10}   {100 * inj / len(rs):.0f}%")

print("\nby source (kind: source = injections / harmless)")
for k in sorted({k for k, _ in zone}):
    parts = []
    for src in ("deepset", "yanismiraoui", "notinject", "no_robots"):
        rs = [r for kk, r in zone if kk == k and r["src"] == src]
        if rs:
            inj = sum(r["y"] for r in rs)
            parts.append(f"{src} {inj}/{len(rs) - inj}")
    print(f"  {k}: " + ", ".join(parts))

print("\nKind B (no evidence): messages below each guard score, injections / harmless")
b = [r for k, r in zone if k.startswith("B")]
for t in (0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
    below = [r for r in b if r["s"] < t]
    inj = sum(r["y"] for r in below)
    print(f"  guard below {t:.2f}: {inj} injections / {len(below) - inj} harmless")