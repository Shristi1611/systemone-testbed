import hashlib, json, os, random, sys
from datasets import load_dataset
from gateway import score, clf_score, LO, HI, _load_clf
from rules import hits
from probes import G

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else None  # optional cap per group (dry run)
CACHE = "results/gw_cache.jsonl"
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
    """Scores for one message, cached: guard score, classifier score, rule hits."""
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


# ---------- held-out data (same seeds and order as build_v2.py / train_classifier.py) ----------
rng = random.Random(11)
dset = load_dataset("deepset/prompt-injections")
d_test = [(r["text"], r["label"]) for r in dset["test"]]

ym = list(dict.fromkeys(r["prompt_injections"] for r in load_dataset("yanismiraoui/prompt_injections")["train"]))
rng.shuffle(ym)  # only here to keep the random state identical

ni_all = []
for _, rows in load_dataset("leolee99/NotInject").items():
    ni_all += [r["prompt"] for r in rows if r["category"] != "Multilingual"]
ni_all = list(dict.fromkeys(ni_all))
ni_hold = [t for t in ni_all if int(h(t), 16) % 2 == 1]

nr = load_dataset("HuggingFaceH4/no_robots")
nr_train = [r["prompt"] for r in nr["train"] if r["category"] != "Chat"]
nr_test = [r["prompt"] for r in nr["test"] if r["category"] != "Chat"]
rng.shuffle(nr_train)
rng.shuffle(nr_test)
nr_test = nr_test[:200]

groups = [
    ("deepset test: injections", "attack", [t for t, l in d_test if l == 1]),
    ("deepset test: harmless", "harmless", [t for t, l in d_test if l == 0]),
    ("NotInject held-out (hard harmless)", "harmless", ni_hold),
    ("no_robots test (ordinary prompts)", "harmless", nr_test),
]
for name, texts in G.items():
    groups.append(("probe: " + name, "harmless" if "harmless" in name else "attack",
                   list(dict.fromkeys(texts))))


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


def cells(recs, use_clf):
    n = len(recs)
    out = []
    for kind in ("allow", "escalate", "block"):
        k = sum(decision(r, use_clf) == kind for r in recs)
        out.append(f"{100 * k / n:>4.0f}%")
    return "  ".join(out)


results, done = [], 0
for name, kind, texts in groups:
    if LIMIT:
        texts = texts[:LIMIT]
    recs = []
    for t in texts:
        r = get(t)
        if r:
            recs.append(r)
        done += 1
        if done % 25 == 0:
            print(f"  {done} messages processed")
    results.append((name, kind, recs))

print(f"\nclassifier cutoff {THR:.2f}; guard cutoffs {LO} / {HI}; errors: {errors}")
print("attacks: want allow LOW.  harmless: want block LOW (escalate costs review, allow is best)\n")
print(f"{'group':38}{'kind':>9}{'n':>5}   {'guard + rules':^22}   {'+ classifier':^22}")
print(f"{'':52}   {'allow  escal  block':^22}   {'allow  escal  block':^22}")
for name, kind, recs in results:
    if recs:
        print(f"{name:38}{kind:>9}{len(recs):>5}   {cells(recs, False):^22}   {cells(recs, True):^22}")