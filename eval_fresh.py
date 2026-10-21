import hashlib, json, os, random, sys, statistics
from datasets import load_dataset
from gateway import score, clf_score, LO, HI, _load_clf
from rules import hits

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 100  # per class
MAX_CHARS = 8000
SEED = 21
CACHE = "results/gw_cache.jsonl"  # same cache as eval_gateway.py
THR = _load_clf()["thr"]


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def norm(t):
    return " ".join(t.lower().split())


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


# ---------- everything the gateway or classifier has seen, for the overlap check ----------
known = set()
for split in load_dataset("deepset/prompt-injections").values():
    known |= {norm(r["text"]) for r in split}
known |= {norm(r["prompt_injections"]) for r in load_dataset("yanismiraoui/prompt_injections")["train"]}
for _, rows in load_dataset("leolee99/NotInject").items():
    known |= {norm(r["prompt"]) for r in rows}
for split in load_dataset("HuggingFaceH4/no_robots").values():
    known |= {norm(r["prompt"]) for r in split}

bench = load_dataset("rogue-security/prompt-injections-benchmark")["test"]
labels = sorted({r["label"] for r in bench})
print(f"benchmark: {len(bench)} rows, labels: {labels}")
attack_label = next((l for l in labels if "jail" in str(l).lower()), None)
benign_label = next((l for l in labels if "benign" in str(l).lower()), None)
if attack_label is None or benign_label is None:
    raise SystemExit("could not identify the jailbreak/benign labels; paste the line above")

rows = [(r["text"], r["label"]) for r in bench]
overlap = [t for t, _ in rows if norm(t) in known]
too_long = [t for t, _ in rows if len(t) > MAX_CHARS]
print(f"exact duplicates of data seen before: {len(overlap)}; longer than {MAX_CHARS} characters: {len(too_long)}")
pool = [(t, l) for t, l in rows if norm(t) not in known and len(t) <= MAX_CHARS]
rng = random.Random(SEED)
groups = []
for name, lab, kind in (("benchmark: benign", benign_label, "harmless"),
                        ("benchmark: jailbreak", attack_label, "attack")):
    items = list(dict.fromkeys(t for t, l in pool if l == lab))
    rng.shuffle(items)
    groups.append((name, kind, items[:LIMIT]))

results, done = [], 0
for name, kind, texts in groups:
    recs = []
    for t in texts:
        r = get(t)
        if r:
            recs.append((t, r))
        done += 1
        if done % 25 == 0:
            print(f"  {done} messages processed")
    results.append((name, kind, recs))

print(f"\nclassifier cutoff {THR:.2f}; guard cutoffs {LO} / {HI}; errors: {errors}; seed {SEED}")
print("jailbreak: want allow LOW.  benign: want block LOW (escalate costs review)\n")
print(f"{'group':24}{'n':>5}{'median chars':>14}{'multi-window':>14}   policy             allow  escal  block")
for name, kind, recs in results:
    if not recs:
        continue
    lens = [len(t) for t, _ in recs]
    multi = sum(len(t) > 1200 for t, _ in recs)
    for label, use_clf in (("guard + rules", False), ("+ classifier", True)):
        c = [sum(decision(r, use_clf) == k for _, r in recs) for k in ("allow", "escalate", "block")]
        head = f"{name:24}{len(recs):>5}{statistics.median(lens):>14.0f}{multi:>14}" if not use_clf else " " * 57
        print(f"{head}   {label:<16}{c[0]:>7}{c[1]:>7}{c[2]:>7}")