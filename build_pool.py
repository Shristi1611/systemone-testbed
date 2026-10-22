"""Build the new training and sealed pools (no model calls). Sealed pools are never printed."""
import hashlib, json, random, subprocess, sys
from collections import Counter
from datasets import load_dataset

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = "results/pool_v2.jsonl"
MAX_CHARS = 6000


def norm(t):
    return " ".join(str(t).lower().split())


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


known = {norm(json.loads(l)["text"]) for l in open("results/eval_sets.jsonl", encoding="utf-8")}
for split in load_dataset("deepset/prompt-injections").values():
    known |= {norm(r["text"]) for r in split}
known |= {norm(r["prompt_injections"]) for r in load_dataset("yanismiraoui/prompt_injections")["train"]}
for _, part in load_dataset("leolee99/NotInject").items():
    known |= {norm(r["prompt"]) for r in part}
for split in load_dataset("HuggingFaceH4/no_robots").values():
    known |= {norm(r["prompt"]) for r in split}

rows = []  # (pool, label, text, src)

# ---------- TrustAIRLab in-the-wild ----------
jb = load_dataset("TrustAIRLab/in-the-wild-jailbreak-prompts", "jailbreak_2023_12_25")["train"]
rg = load_dataset("TrustAIRLab/in-the-wild-jailbreak-prompts", "regular_2023_12_25")["train"]
jb_norms = {norm(r["prompt"]) for r in jb}
rg_norms = {norm(r["prompt"]) for r in rg}
conflict = jb_norms & rg_norms


def clean(ds):
    seen, out = set(), []
    for r in ds:
        t = str(r["prompt"])
        n = norm(t)
        if len(t.strip()) < 3 or len(t) > MAX_CHARS or n in known or n in conflict or n in seen:
            continue
        seen.add(n)
        out.append((t, r["platform"], r["source"]))
    return out


jb_c, rg_c = clean(jb), clean(rg)
print(f"TrustAIRLab after cleaning (duplicates, empties, over {MAX_CHARS} characters, overlaps, label conflicts): "
      f"{len(jb_c)} jailbreaks, {len(rg_c)} regular")


def split_half(items, parity):
    return [x for x in items if int(h(x[0]), 16) % 2 == parity]


def matched_sample(jb_items, rg_items, n, seed):
    """n jailbreaks at random; regular prompts sampled to match the jailbreaks' platform mix."""
    rng = random.Random(seed)
    jb_items = list(jb_items)
    rng.shuffle(jb_items)
    jb_pick = jb_items[:n]
    share = Counter(p for _, p, _ in jb_pick)
    rg_pick = []
    for plat, cnt in share.items():
        pool = [x for x in rg_items if x[1] == plat]
        rng.shuffle(pool)
        rg_pick += pool[:cnt]
    return jb_pick, rg_pick


for pool, parity, n, seed in (("train_wild", 0, 600, 31), ("sealed_wild", 1, 200, 32)):
    a, b = matched_sample(split_half(jb_c, parity), split_half(rg_c, parity), n, seed)
    rows += [(pool, 1, t, f"{p}/{s}") for t, p, s in a]
    rows += [(pool, 0, t, f"{p}/{s}") for t, p, s in b]

# ---------- neuralchemy core test and S-Labs test (sealed) ----------
nc = load_dataset("neuralchemy/Prompt-injection-dataset", "core")["test"]
sl = load_dataset("S-Labs/prompt-injection-dataset")["test"]
for pool, ds, seed in (("sealed_neuralchemy", nc, 41), ("sealed_slabs", sl, 51)):
    rng = random.Random(seed)
    for lab in (1, 0):
        items = list(dict.fromkeys(str(r["text"]) for r in ds if int(r["label"]) == lab
                                   and norm(str(r["text"])) not in known and len(str(r["text"]).strip()) >= 3))
        rng.shuffle(items)
        rows += [(pool, lab, t, pool) for t in items[:100]]

with open(OUT, "w", encoding="utf-8") as f:
    for pool, label, text, src in rows:
        f.write(json.dumps({"pool": pool, "label": label, "text": text, "src": src, "k": h(text)}) + "\n")

print(f"\nsaved {len(rows)} messages to {OUT}\n")
for pool in ("train_wild", "sealed_wild", "sealed_neuralchemy", "sealed_slabs"):
    for lab in (1, 0):
        sub = [r for r in rows if r[0] == pool and r[1] == lab]
        lens = sorted(len(r[2]) for r in sub)
        extra = ""
        if pool == "train_wild":
            extra = "   platforms: " + str(dict(Counter(r[3].split("/")[0] for r in sub)))
        print(f"  {pool:20}{'attack' if lab else 'harmless':>9}{len(sub):>6}   median length {lens[len(lens) // 2]:>5}{extra}")
ign = subprocess.run(["git", "check-ignore", OUT], capture_output=True, text=True)
print(f"\ngit ignores {OUT}: {'yes' if ign.returncode == 0 else 'NO - do not commit it, tell me'}")