"""Score the 1,365 training messages once (guard + rules), plus the classifier's
cross-validated score, so a second look for the escalate zone can be trained on them."""
import hashlib, json, os, random, sys
import numpy as np
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from gateway import score
from rules import hits

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = "results/train_scores.jsonl"
EMB_CACHE = "results/emb_nomic_embed_text.npz"


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


# ---------- data (copied from train_classifier.py, same seeds, same order) ----------
rng = random.Random(11)
dset = load_dataset("deepset/prompt-injections")
d_train = [(r["text"], r["label"]) for r in dset["train"]]

ym = list(dict.fromkeys(r["prompt_injections"] for r in load_dataset("yanismiraoui/prompt_injections")["train"]))
rng.shuffle(ym)
ym = ym[:300]

ni_all = []
for _, rows in load_dataset("leolee99/NotInject").items():
    ni_all += [r["prompt"] for r in rows if r["category"] != "Multilingual"]
ni_all = list(dict.fromkeys(ni_all))
ni_train = [t for t in ni_all if int(h(t), 16) % 2 == 0]

nr = load_dataset("HuggingFaceH4/no_robots")
nr_train = [r["prompt"] for r in nr["train"] if r["category"] != "Chat"]
nr_test = [r["prompt"] for r in nr["test"] if r["category"] != "Chat"]
rng.shuffle(nr_train)
rng.shuffle(nr_test)
nr_train = nr_train[:400]

old_texts = [t for t, _ in d_train]
old_y = np.array([l for _, l in d_train])
texts = old_texts + ym + ni_train + nr_train
y = np.concatenate([old_y, np.ones(len(ym), int), np.zeros(len(ni_train) + len(nr_train), int)])
source = (["deepset"] * len(old_texts) + ["yanismiraoui"] * len(ym)
          + ["notinject"] * len(ni_train) + ["no_robots"] * len(nr_train))
print(f"training set: {len(texts)} messages ({int(y.sum())} injections)")
assert len(texts) == 1365 and int(y.sum()) == 503, "training set differs from train_classifier.py"

# ---------- classifier cross-validated scores (same folds as train_classifier.py) ----------
emb = dict(np.load(EMB_CACHE))
missing = [t for t in texts if h(t) not in emb]
if missing:
    raise SystemExit(f"{len(missing)} embeddings missing; run train_classifier.py first")
X = np.stack([emb[h(t)] for t in texts])
X = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
oof = np.zeros(len(y))
for a, v in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
    m = LogisticRegression(C=10, max_iter=3000, class_weight="balanced").fit(X[a], y[a])
    oof[v] = m.predict_proba(X[v])[:, 1]
thr = float(np.quantile(oof[y == 0], 0.90))
print(f"cross-validated classifier cutoff: {thr:.2f} (should be 0.45)")

# ---------- guard + rules, one pass, resumable ----------
done = {}
if os.path.exists(OUT):
    with open(OUT, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            done[r["k"]] = r

errors, n = 0, 0
with open(OUT, "a", encoding="utf-8") as f:
    for i, t in enumerate(texts):
        k = h(t)
        if k in done:
            continue
        try:
            s, unseen = score(t)
        except Exception as e:
            errors += 1
            print("error:", type(e).__name__, str(e)[:80])
            continue
        rec = {"k": k, "y": int(y[i]), "src": source[i], "s": s, "unseen": unseen,
               "h": hits(t), "c": float(oof[i])}
        done[k] = rec
        f.write(json.dumps(rec) + "\n")
        f.flush()
        n += 1
        if n % 50 == 0:
            print(f"  {len(done)} of {len(set(h(t) for t in texts))} scored")

print(f"\nscored {len(done)} distinct messages, errors: {errors}")
if errors:
    print("run the same command again to retry the failed ones")