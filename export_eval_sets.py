"""Save every labelled evaluation set into one local file (no model calls)."""
import hashlib, json, random, subprocess, sys
from datasets import load_dataset
from probes import G
from probes_hi import G_HI

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = "results/eval_sets.jsonl"


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def norm(t):
    return " ".join(t.lower().split())


rows = []  # (kind, group, label, text)

# ---- held-out (same seeds and order as eval_gateway.py) ----
rng = random.Random(11)
dset = load_dataset("deepset/prompt-injections")
d_test = [(r["text"], r["label"]) for r in dset["test"]]
ym = list(dict.fromkeys(r["prompt_injections"] for r in load_dataset("yanismiraoui/prompt_injections")["train"]))
rng.shuffle(ym)
ni_all = []
for _, part in load_dataset("leolee99/NotInject").items():
    ni_all += [r["prompt"] for r in part if r["category"] != "Multilingual"]
ni_all = list(dict.fromkeys(ni_all))
ni_hold = [t for t in ni_all if int(h(t), 16) % 2 == 1]
nr = load_dataset("HuggingFaceH4/no_robots")
nr_train = [r["prompt"] for r in nr["train"] if r["category"] != "Chat"]
nr_test = [r["prompt"] for r in nr["test"] if r["category"] != "Chat"]
rng.shuffle(nr_train)
rng.shuffle(nr_test)
nr_test = nr_test[:200]
for t, l in d_test:
    rows.append(("heldout", "deepset test: injections" if l == 1 else "deepset test: harmless", l, t))
rows += [("heldout", "NotInject held-out", 0, t) for t in ni_hold]
rows += [("heldout", "no_robots test", 0, t) for t in nr_test]

# ---- hand-written probes ----
for name, texts in G.items():
    lab = 0 if "harmless" in name else 1
    rows += [("probe", "probe: " + name, lab, t) for t in dict.fromkeys(texts)]
for name, texts in G_HI.items():
    lab = 1 if name.startswith("attack") else 0
    rows += [("hindi", "hindi: " + name, lab, t) for t in texts]

# ---- fresh benchmark (same filtering and seed as eval_fresh.py) ----
known = set()
for split in load_dataset("deepset/prompt-injections").values():
    known |= {norm(r["text"]) for r in split}
known |= {norm(r["prompt_injections"]) for r in load_dataset("yanismiraoui/prompt_injections")["train"]}
for _, part in load_dataset("leolee99/NotInject").items():
    known |= {norm(r["prompt"]) for r in part}
for split in load_dataset("HuggingFaceH4/no_robots").values():
    known |= {norm(r["prompt"]) for r in split}
bench = load_dataset("rogue-security/prompt-injections-benchmark")["test"]
pool = [(r["text"], r["label"]) for r in bench]
pool = [(t, l) for t, l in pool if norm(t) not in known and len(t) <= 8000]
frng = random.Random(21)
for name, lab_name, y in (("benchmark: benign", "benign", 0), ("benchmark: jailbreak", "jailbreak", 1)):
    items = list(dict.fromkeys(t for t, l in pool if l == lab_name))
    frng.shuffle(items)
    rows += [("fresh", name, y, t) for t in items[:100]]

with open(OUT, "w", encoding="utf-8") as f:
    for kind, group, label, text in rows:
        f.write(json.dumps({"kind": kind, "group": group, "label": label, "text": text, "k": h(text)}) + "\n")

print(f"saved {len(rows)} messages to {OUT}")
counts = {}
for kind, group, label, _ in rows:
    counts[(kind, group, label)] = counts.get((kind, group, label), 0) + 1
for (kind, group, label), n in counts.items():
    print(f"  {kind:8}{group[:52]:54}{'attack' if label else 'harmless':>9}{n:>6}")
ign = subprocess.run(["git", "check-ignore", OUT], capture_output=True, text=True)
print(f"\ngit ignores {OUT}: {'yes' if ign.returncode == 0 else 'NO - do not commit it, tell me'}")