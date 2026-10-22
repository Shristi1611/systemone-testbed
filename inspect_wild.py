import json, random, sys
from collections import Counter
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

rng = random.Random(5)
for cfg in ("jailbreak_2023_12_25", "regular_2023_12_25"):
    print("=" * 70)
    try:
        rows = load_dataset("TrustAIRLab/in-the-wild-jailbreak-prompts", cfg)["train"]
    except Exception as e:
        print(f"{cfg}: could not load ({type(e).__name__}: {str(e)[:150]})")
        continue
    texts = [str(r["prompt"]) for r in rows]
    n = len(texts)
    uniq = len({norm(t) for t in texts})
    lens = sorted(len(t) for t in texts)
    print(f"{cfg}: {n} rows; unique after normalising: {uniq}; jailbreak flag true: {sum(bool(r['jailbreak']) for r in rows)}")
    print(f"   empty or under 3 characters: {sum(len(t.strip()) < 3 for t in texts)}; "
          f"exact duplicates of data used before: {sum(norm(t) in known for t in texts)}")
    print(f"   length in characters: median {lens[n // 2]}, 90th percentile {lens[int(n * 0.9)]}, longest {lens[-1]}")
    print(f"   longer than 1,200 characters (more than one window): {sum(len(t) > 1200 for t in texts)}; "
          f"non-ASCII characters present: {sum(any(ord(c) > 127 for c in t) for t in texts)}")
    print(f"   platforms: {dict(Counter(r['platform'] for r in rows).most_common(6))}")
    print(f"   sources: {dict(Counter(r['source'] for r in rows).most_common(8))}")
    print(f"\n   6 random examples (first 130 characters):")
    for i in rng.sample(range(n), 6):
        print("     -", texts[i].replace("\n", " ")[:130])

# overlap between the two classes inside this dataset
try:
    j = {norm(r["prompt"]) for r in load_dataset("TrustAIRLab/in-the-wild-jailbreak-prompts", "jailbreak_2023_12_25")["train"]}
    g = {norm(r["prompt"]) for r in load_dataset("TrustAIRLab/in-the-wild-jailbreak-prompts", "regular_2023_12_25")["train"]}
    print(f"\ntexts that appear in BOTH the jailbreak and the regular config: {len(j & g)}")
except Exception as e:
    print("overlap check skipped:", e)