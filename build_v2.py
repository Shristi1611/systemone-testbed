import hashlib, json, os, random, sys, urllib.request
import numpy as np
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from probes import G

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EMB = sys.argv[1] if len(sys.argv) > 1 else "nomic-embed-text"
OLLAMA = "http://127.0.0.1:11434"
PREFIX = "classification: " if "nomic" in EMB else ""
os.makedirs("results", exist_ok=True)
CACHE = "results/emb_" + "".join(c if c.isalnum() else "_" for c in EMB) + ".npz"
cache = dict(np.load(CACHE)) if os.path.exists(CACHE) else {}


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def post(path, body):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def embed_all(texts):
    todo = [t for t in texts if h(t) not in cache]
    for i in range(0, len(todo), 16):
        chunk = todo[i:i + 16]
        batch = [PREFIX + t[:1500] for t in chunk]
        try:
            vecs = post("/api/embed", {"model": EMB, "input": batch})["embeddings"]
        except Exception:
            vecs = [post("/api/embeddings", {"model": EMB, "prompt": b})["embedding"] for b in batch]
        for t, v in zip(chunk, vecs):
            cache[h(t)] = np.array(v, dtype=np.float32)
        print(f"  embedded {min(i + 16, len(todo))}/{len(todo)}")
    if todo:
        np.savez(CACHE, **cache)


def vec(texts):
    X = np.stack([cache[h(t)] for t in texts])
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)


# ---------- data ----------
rng = random.Random(11)
dset = load_dataset("deepset/prompt-injections")
d_train = [(r["text"], r["label"]) for r in dset["train"]]
d_test = [(r["text"], r["label"]) for r in dset["test"]]

ym = list(dict.fromkeys(r["prompt_injections"] for r in load_dataset("yanismiraoui/prompt_injections")["train"]))
rng.shuffle(ym)
ym = ym[:300]

ni_all = []
for _, rows in load_dataset("leolee99/NotInject").items():
    ni_all += [r["prompt"] for r in rows if r["category"] != "Multilingual"]
ni_all = list(dict.fromkeys(ni_all))
ni_train = [t for t in ni_all if int(h(t), 16) % 2 == 0]
ni_hold = [t for t in ni_all if int(h(t), 16) % 2 == 1]

nr = load_dataset("HuggingFaceH4/no_robots")
nr_train = [r["prompt"] for r in nr["train"] if r["category"] != "Chat"]
nr_test = [r["prompt"] for r in nr["test"] if r["category"] != "Chat"]
rng.shuffle(nr_train)
rng.shuffle(nr_test)
nr_train, nr_test = nr_train[:400], nr_test[:200]

old_texts = [t for t, _ in d_train]
old_y = np.array([l for _, l in d_train])
new_texts = old_texts + ym + ni_train + nr_train
new_y = np.concatenate([old_y, np.ones(len(ym), int), np.zeros(len(ni_train) + len(nr_train), int)])
print(f"embedding model: {EMB}")
print(f"old training set: {len(old_texts)} messages ({int(old_y.sum())} injections)")
print(f"new training set: {len(new_texts)} messages ({int(new_y.sum())} injections; "
      f"harmless = deepset {int((old_y == 0).sum())} + NotInject {len(ni_train)} + no_robots {len(nr_train)})")

probe_groups = {k: list(dict.fromkeys(v)) for k, v in G.items()}
everything = set(new_texts) | {t for t, _ in d_test} | set(ni_hold) | set(nr_test)
for v in probe_groups.values():
    everything |= set(v)
embed_all(sorted(everything))


# ---------- models ----------
def make():
    return LogisticRegression(C=10, max_iter=3000, class_weight="balanced")


def train(texts, y):
    X = vec(texts)
    oof = np.zeros(len(y))
    for a, v in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
        oof[v] = make().fit(X[a], y[a]).predict_proba(X[v])[:, 1]
    thr = float(np.quantile(oof[y == 0], 0.90))  # cutoff: 10% of train-harmless would be blocked
    return make().fit(X, y), thr


models = {"old: deepset only": train(old_texts, old_y), "new: mixed data": train(new_texts, new_y)}

# ---------- evaluation ----------
d_inj = [t for t, l in d_test if l == 1]
d_ben = [t for t, l in d_test if l == 0]
groups = [
    ("deepset test: injections", "high", d_inj),
    ("deepset test: harmless", "low", d_ben),
    ("NotInject held-out half (hard harmless)", "low", ni_hold),
    ("no_robots test (ordinary prompts)", "low", nr_test),
]
for name, texts in probe_groups.items():
    groups.append(("probe: " + name, "low" if "harmless" in name else "high", texts))

yt = np.array([l for _, l in d_test])
Xt = vec([t for t, _ in d_test])
print("\ndeepset test AUC:  " + "   ".join(f"{k} {roc_auc_score(yt, m.predict_proba(Xt)[:, 1]):.3f}" for k, (m, _) in models.items()))
print("cutoffs fixed on train:  " + "   ".join(f"{k} {t:.2f}" for k, (_, t) in models.items()))
print("\nshare flagged as injection ('want low' for harmless groups, 'want high' for attacks)\n")
print(f"{'group':<48}{'want':>6}{'n':>5}" + "".join(f"{k:>22}" for k in models))
for name, want, texts in groups:
    X = vec(texts)
    cells = "".join(f"{float(np.mean(m.predict_proba(X)[:, 1] >= thr)):>22.0%}" for m, thr in models.values())
    print(f"{name:<48}{want:>6}{len(texts):>5}{cells}")