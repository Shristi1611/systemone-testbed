"""Build gateway v2 (classifier retrained on old + wild data, plus a small combiner).
Only training data is used. Cross-validated results are printed. Sealed pools are never touched."""
import hashlib, json, os, random, sys, urllib.request
import numpy as np
import joblib
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from gateway import OLLAMA, EMB, PREFIX, windows

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OLD_EMB = "results/emb_nomic_embed_text.npz"
WIN_EMB = "results/emb_wild_windows.npz"
MODEL_OUT = "results/v2_model.joblib"


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


# ---------- old training data (same code, seeds and order as score_train.py) ----------
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
old_texts = [t for t, _ in d_train] + ym + ni_train + nr_train
old_y = [l for _, l in d_train] + [1] * len(ym) + [0] * (len(ni_train) + len(nr_train))
assert len(old_texts) == 1365 and sum(old_y) == 503, "old training set differs"

old_emb = dict(np.load(OLD_EMB))
old_sc = {}
for line in open("results/train_scores.jsonl", encoding="utf-8"):
    r = json.loads(line)
    old_sc[r["k"]] = r

# ---------- wild training data ----------
wild = [json.loads(l) for l in open("results/pool_v2.jsonl", encoding="utf-8")]
wild = [r for r in wild if r["pool"] == "train_wild"]
wild_sc = {}
for line in open("results/pool_scores.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r["pool"] == "train_wild":
        wild_sc[r["k"]] = r
assert len(wild) == 1200 and len(wild_sc) == 1200

# ---------- embed every wild window (resumable) ----------
cache = dict(np.load(WIN_EMB)) if os.path.exists(WIN_EMB) else {}
todo = []
for r in wild:
    for w in windows(r["text"]):
        if h(w) not in cache:
            todo.append(w)
todo = list(dict.fromkeys(todo))
print(f"wild windows to embed: {len(todo)} (already cached: {len(cache)})")
for i in range(0, len(todo), 16):
    chunk = todo[i:i + 16]
    req = urllib.request.Request(
        OLLAMA + "/api/embed",
        data=json.dumps({"model": EMB, "input": [PREFIX + w[:1500] for w in chunk]}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        vecs = json.load(resp)["embeddings"]
    for w, v in zip(chunk, vecs):
        cache[h(w)] = unit(v)
    if (i // 16) % 25 == 24 or i + 16 >= len(todo):
        np.savez(WIN_EMB, **cache)
        print(f"  embedded {min(i + 16, len(todo))} of {len(todo)}")

# ---------- messages: window embeddings + the signals scored earlier ----------
msgs = []
for t, y in zip(old_texts, old_y):
    s = old_sc[h(t)]
    msgs.append({"g": "old", "y": y, "W": np.stack([unit(old_emb[h(t)])]), "s": s["s"],
                 "unseen": float(s["unseen"]), "hit": float(bool(s["h"])), "len": len(t)})
for r in wild:
    s = wild_sc[r["k"]]
    msgs.append({"g": "wild", "y": r["label"], "W": np.stack([cache[h(w)] for w in windows(r["text"])]),
                 "s": s["s"], "unseen": float(s["unseen"]), "hit": float(bool(s["h"])), "len": len(r["text"])})
M = len(msgs)
y = np.array([m["y"] for m in msgs])
grp = np.array([m["g"] for m in msgs])
print(f"\n{M} training messages: old {int((grp == 'old').sum())}, wild {int((grp == 'wild').sum())}; attacks {int(y.sum())}")


def fit_clf(idx):
    X = np.vstack([msgs[i]["W"] for i in idx])
    yy = np.concatenate([[msgs[i]["y"]] * len(msgs[i]["W"]) for i in idx])
    return LogisticRegression(C=10, max_iter=3000, class_weight="balanced").fit(X, yy)


def worst(m, mi):
    return float(m.predict_proba(msgs[mi]["W"])[:, 1].max())


# ---------- stage 1: retrained classifier, out-of-fold ----------
oof_c = np.zeros(M)
for a, v in StratifiedKFold(5, shuffle=True, random_state=0).split(np.zeros(M), y):
    m = fit_clf(a)
    for i in v:
        oof_c[i] = worst(m, i)


# ---------- stage 2: combiner on top of out-of-fold scores ----------
def feats(c, i):
    c = min(max(c, 1e-4), 1 - 1e-4)
    return [np.log(c / (1 - c)), msgs[i]["s"], msgs[i]["hit"], msgs[i]["unseen"], np.log1p(msgs[i]["len"])]


F = np.array([feats(oof_c[i], i) for i in range(M)])
oof_p = np.zeros(M)
for a, v in StratifiedKFold(5, shuffle=True, random_state=1).split(F, y):
    cm = make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, class_weight="balanced")).fit(F[a], y[a])
    oof_p[v] = cm.predict_proba(F[v])[:, 1]

wmask, omask = grp == "wild", grp == "old"
s_all = np.array([m["s"] for m in msgs])
len_all = np.array([m["len"] for m in msgs])
print("\nHow well each signal separates attacks from harmless (AUC, out-of-fold):")
print(f"{'':34}{'all':>8}{'old':>8}{'wild':>8}")
for name, sc in (("guard score (v1)", s_all), ("length", len_all),
                 ("retrained classifier", oof_c), ("combiner (v2)", oof_p)):
    print(f"  {name:32}{roc_auc_score(y, sc):8.3f}{roc_auc_score(y[omask], sc[omask]):8.3f}{roc_auc_score(y[wmask], sc[wmask]):8.3f}")
old_c_wild = np.array([wild_sc[r["k"]]["c"] for r in wild])
print(f"  (v1 classifier on wild only: {roc_auc_score(y[wmask], old_c_wild):.3f})")

# ---------- thresholds from out-of-fold scores (rule 2 of the pre-registration) ----------
t_block = float(np.quantile(oof_p[y == 0], 0.99))   # at most 1% of harmless blocked
t_allow = float(np.quantile(oof_p[y == 1], 0.05))   # at most 5% of attacks allowed
print(f"\nthresholds: block above {t_block:.3f}, allow below {t_allow:.3f}, escalate in between")
if t_allow >= t_block:
    print("WARNING: allow threshold is not below block threshold; the combiner separates too poorly")


def decide(p, unseen):
    d = "block" if p > t_block else ("allow" if p < t_allow else "escalate")
    return "escalate" if (d == "allow" and unseen) else d


dec = np.array([decide(oof_p[i], msgs[i]["unseen"] > 0) for i in range(M)])
print("\nv2 decisions, cross-validated (v1 on wild for comparison: attacks block 96% / harmless block 76%):")
for name, mask in (("all", np.ones(M, bool)), ("old", omask), ("wild", wmask)):
    for lab, lname in ((1, "attacks "), (0, "harmless")):
        sel = mask & (y == lab)
        print(f"  {name:5}{lname}" + "".join(f"{k} {int((dec[sel] == k).sum()):4} ({(dec[sel] == k).mean():4.0%})   " for k in ("block", "escalate", "allow")))

# ---------- final fit on all training data and save ----------
clf = fit_clf(np.arange(M))
comb = make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=3000, class_weight="balanced")).fit(F, y)
joblib.dump({"clf": clf, "comb": comb, "t_block": t_block, "t_allow": t_allow,
             "features": ["logit_clf", "guard", "rule_hit", "unseen", "log1p_len"]}, MODEL_OUT)
print(f"\nsaved {MODEL_OUT}")

# ---------- save plain arrays so other heads can be compared on identical data ----------
idx = np.concatenate([[i] * len(msgs[i]["W"]) for i in range(M)])
np.savez("results/v2_train_arrays.npz",
         X=np.vstack([m["W"] for m in msgs]), idx=idx, y=y, grp=grp,
         s=s_all, unseen=np.array([m["unseen"] for m in msgs]),
         hit=np.array([m["hit"] for m in msgs]), length=len_all, oof_c=oof_c)
print("saved results/v2_train_arrays.npz")