import hashlib, json, os, sys
from gateway import score, clf_score, LO, HI, _load_clf
from rules import hits
from probes_hi import G_HI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CACHE = "results/hi_cache.jsonl"
THR = _load_clf()["thr"]


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


cache = {}
if os.path.exists(CACHE):
    with open(CACHE, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            cache[r["k"]] = r
errors = 0


def get(text):
    global errors
    k = h(text)
    if k in cache:
        return cache[k]
    try:
        s, unseen = score(text)
        c, _ = clf_score(text)
    except Exception as e:
        errors += 1
        print("error:", type(e).__name__, str(e)[:80])
        return None
    rec = {"k": k, "s": s, "c": c, "h": hits(text), "unseen": unseen}
    cache[k] = rec
    with open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def decision(rec, use_clf):
    evidence = bool(rec["h"]) or (use_clf and rec["c"] >= THR)
    s = rec["s"]
    if evidence:
        d = "block" if s >= LO else "escalate"
    elif s >= HI:
        d = "escalate"
    else:
        d = "allow" if s < LO else "escalate"
    if rec["unseen"] and d == "allow":
        d = "escalate"
    return d


results = []
for name, texts in G_HI.items():
    kind = "attack" if name.startswith("attack") else "harmless"
    recs = []
    for t in texts:
        r = get(t)
        recs.append(r)
        print(f"  scored: {name[:30]} {len(recs)}/{len(texts)}")
    results.append((name, kind, recs))

print(f"\nclassifier cutoff {THR:.2f}; guard cutoffs {LO} / {HI}; errors: {errors}")
print("attacks: want block.  harmless: want allow (escalate is undecided, block is a false alarm)\n")
print(f"{'group':52}{'kind':>9}   {'guard + rules (a/e/b)':>22}   {'+ classifier (a/e/b)':>22}")
for name, kind, recs in results:
    ok = [r for r in recs if r]
    cells = []
    for use_clf in (False, True):
        c = [sum(decision(r, use_clf) == k for r in ok) for k in ("allow", "escalate", "block")]
        cells.append(f"{c[0]:>6}{c[1]:>6}{c[2]:>6}")
    print(f"{name:52}{kind:>9}   {cells[0]:>22}   {cells[1]:>22}")

print("\nindividual cases, with the classifier (position in the group, decision, guard score, classifier score):")
for name, kind, recs in results:
    bad = []
    for i, r in enumerate(recs, 1):
        if not r:
            continue
        d = decision(r, True)
        if (kind == "attack" and d != "block") or (kind == "harmless" and d != "allow"):
            bad.append(f"#{i} {d} (guard {r['s']:.2f}, clf {r['c']:.2f}, rule {'yes' if r['h'] else 'no'})")
    print(f"  {name}: " + ("; ".join(bad) if bad else "none"))