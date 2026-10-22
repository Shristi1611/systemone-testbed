import json, random, sys
from datasets import load_dataset

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def norm(t):
    return " ".join(str(t).lower().split())


known = {norm(json.loads(l)["text"]) for l in open("results/eval_sets.jsonl", encoding="utf-8")}
for split in load_dataset("deepset/prompt-injections").values():
    known |= {norm(r["text"]) for r in split}
known |= {norm(r["prompt_injections"]) for r in load_dataset("yanismiraoui/prompt_injections")["train"]}
for _, part in load_dataset("leolee99/NotInject").items():
    known |= {norm(r["prompt"]) for r in part}
for split in load_dataset("HuggingFaceH4/no_robots").values():
    known |= {norm(r["prompt"]) for r in split}
print(f"texts used in this project so far: {len(known)}\n")

SETS = [("neuralchemy core", "neuralchemy/Prompt-injection-dataset", "core"),
        ("S-Labs", "S-Labs/prompt-injection-dataset", None)]
rng = random.Random(5)
for title, repo, cfg in SETS:
    print("=" * 70)
    try:
        ds = load_dataset(repo, cfg) if cfg else load_dataset(repo)
    except Exception as e:
        print(f"{title}: could not load ({type(e).__name__}: {str(e)[:120]})")
        continue
    for split, rows in ds.items():
        texts = [str(r["text"]) for r in rows]
        labels = [int(r["label"]) for r in rows]
        n = len(texts)
        short = sum(len(t.strip()) < 3 for t in texts)
        dup_inside = n - len({norm(t) for t in texts})
        dup_known = sum(norm(t) in known for t in texts)
        lens = sorted(len(t) for t in texts)
        nonascii = sum(any(ord(c) > 127 for c in t) for t in texts)
        print(f"{title} / {split}: {n} rows; label 1 = {sum(labels)}, label 0 = {n - sum(labels)}")
        print(f"   empty or under 3 characters: {short}; duplicates inside the split: {dup_inside}; "
              f"exact duplicates of data used before: {dup_known}")
        print(f"   length in characters: median {lens[n // 2]}, 90th percentile {lens[int(n * 0.9)]}, longest {lens[-1]}; "
              f"rows with non-ASCII characters: {nonascii}")
        if "source" in rows.features:
            from collections import Counter
            for lab in (0, 1):
                c = Counter(r["source"] for r in rows if int(r["label"]) == lab)
                print(f"   label {lab} sources: {dict(c.most_common(8))}")
        if "augmented" in rows.features:
            print(f"   augmented rows: {sum(bool(r['augmented']) for r in rows)}")
    first = list(ds.keys())[0]
    rows = ds[first]
    for lab in (0, 1):
        idx = [i for i, r in enumerate(rows) if int(r["label"]) == lab]
        print(f"\n   {title} / {first}: 6 random examples with label {lab}")
        for i in rng.sample(idx, min(6, len(idx))):
            print("     -", str(rows[i]["text"]).replace("\n", " ")[:130])