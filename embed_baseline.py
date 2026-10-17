import json, os, sys, urllib.request
import numpy as np
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from rules import hits

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLLAMA = "http://127.0.0.1:11434"
MODEL = "nomic-embed-text"
os.makedirs("results", exist_ok=True)


def post(path, body):
    req = urllib.request.Request(
        OLLAMA + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def embed(texts):
    out = []
    for i in range(0, len(texts), 16):
        batch = ["classification: " + t for t in texts[i:i + 16]]
        try:
            out += post("/api/embed", {"model": MODEL, "input": batch})["embeddings"]
        except Exception:
            for t in batch:
                out.append(post("/api/embeddings", {"model": MODEL, "prompt": t})["embedding"])
        print(f"  embedded {min(i + 16, len(texts))}/{len(texts)}")
    return np.array(out, dtype=np.float32)


ds = load_dataset("deepset/prompt-injections")
data = {}
for split in ("train", "test"):
    rows = ds[split]
    texts = [r["text"] for r in rows]
    y = np.array([r["label"] for r in rows])
    a = json.load(open(f"results/scores_{split}_v2.json", encoding="utf-8"))
    b = json.load(open(f"results/scores_{split}_v3.json", encoding="utf-8"))
    assert len(a) == len(b) == len(texts), f"{split}: guard scores incomplete; rerun score_dataset.py {split} v2,v3 all 0.5"
    for t, x, z in zip(texts, a, b):
        assert t[:200] == x["text"] == z["text"], "misaligned"
    g = np.array([(x["avg"] + z["avg"]) / 2 for x, z in zip(a, b)])
    r = np.array([1.0 if hits(t) else 0.0 for t in texts])
    path = f"results/emb_{split}.npy"
    if os.path.exists(path):
        E = np.load(path)
    else:
        print("embedding", split)
        E = embed(texts)
        np.save(path, E)
    E = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
    data[split] = dict(y=y, g=g, r=r, E=E)

tr, te = data["train"], data["test"]
skf = StratifiedKFold(5, shuffle=True, random_state=0)


def oof(make, X, y):
    p = np.zeros(len(y))
    for a_idx, v_idx in skf.split(X, y):
        p[v_idx] = make().fit(X[a_idx], y[a_idx]).predict_proba(X[v_idx])[:, 1]
    return p


best = None
for C in (0.3, 1, 3, 10, 30):
    p = oof(lambda: LogisticRegression(C=C, max_iter=2000), tr["E"], tr["y"])
    auc = roc_auc_score(tr["y"], p)
    print(f"embedding classifier C={C}: train cross-validated AUC {auc:.3f}")
    if best is None or auc > best[0]:
        best = (auc, C, p)
_, C, emb_oof = best
emb_te = LogisticRegression(C=C, max_iter=2000).fit(tr["E"], tr["y"]).predict_proba(te["E"])[:, 1]


def stack(cols_tr, cols_te):
    Ftr, Fte = np.column_stack(cols_tr), np.column_stack(cols_te)
    p_tr = oof(lambda: LogisticRegression(C=1.0, max_iter=2000), Ftr, tr["y"])
    p_te = LogisticRegression(C=1.0, max_iter=2000).fit(Ftr, tr["y"]).predict_proba(Fte)[:, 1]
    return p_tr, p_te


models = {
    "rules (hit or not)": (tr["r"], te["r"]),
    "guard (Laya, zero-shot)": (tr["g"], te["g"]),
    "embedding classifier": (emb_oof, emb_te),
    "stack: guard + rules": stack([tr["g"], tr["r"]], [te["g"], te["r"]]),
    "stack: embed+guard+rules": stack([emb_oof, tr["g"], tr["r"]], [emb_te, te["g"], te["r"]]),
}

rng = np.random.default_rng(0)


def boot(y, s, n=500):
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if len(set(y[idx])) == 2:
            vals.append(roc_auc_score(y[idx], s[idx]))
    return np.percentile(vals, [2.5, 97.5])


print("\nOperating point: cutoff fixed on TRAIN so that ~10% of harmless train messages are blocked.")
print(f"{'model':<28}{'train AUC':>10}{'test AUC':>10}{'  test 95% range':>18}{'harmless blocked':>18}{'inj allowed':>13}")
for name, (s_tr, s_te) in models.items():
    thr = 0.5 if name.startswith("rules") else np.quantile(s_tr[tr["y"] == 0], 0.90)
    fb = float(np.mean(s_te[te["y"] == 0] >= thr))
    miss = float(np.mean(s_te[te["y"] == 1] < thr))
    lo, hi = boot(te["y"], s_te)
    print(
        f"{name:<28}{roc_auc_score(tr['y'], s_tr):>10.3f}{roc_auc_score(te['y'], s_te):>10.3f}"
        f"{f'  {lo:.2f}-{hi:.2f}':>18}{fb:>18.0%}{miss:>13.0%}"
    )