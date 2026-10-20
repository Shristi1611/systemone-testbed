"""Train the mixed-data embedding classifier (same data and settings as build_v2.py)
and save it for the gateway."""
import hashlib, json, os, random, sys, urllib.request
import joblib
import numpy as np
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EMB = "nomic-embed-text"
OLLAMA = "http://127.0.0.1:11434"
PREFIX = "classification: "
os.makedirs("results", exist_ok=True)
CACHE = "results/emb_nomic_embed_text.npz"
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


# ---------- data (copied from build_v2.py, same seeds, same order) ----------
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
print(f"training set: {len(texts)} messages ({int(y.sum())} injections; harmless = deepset "
      f"{int((old_y == 0).sum())} + NotInject {len(ni_train)} + no_robots {len(nr_train)})")

embed_all(sorted(set(texts)))


def make():
    return LogisticRegression(C=10, max_iter=3000, class_weight="balanced")


X = vec(texts)
oof = np.zeros(len(y))
for a, v in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
    oof[v] = make().fit(X[a], y[a]).predict_proba(X[v])[:, 1]
thr = float(np.quantile(oof[y == 0], 0.90))  # 10% of train-harmless would be flagged
model = make().fit(X, y)

joblib.dump({"model": model, "thr": thr}, "results/clf_mixed.joblib")
print(f"cutoff fixed on train: {thr:.2f}")
print("saved results/clf_mixed.joblib")