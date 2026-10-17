import random, sys
from datasets import load_dataset

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ds = load_dataset("deepset/prompt-injections")
print(ds)

for split in ds:
    rows = ds[split]
    inj = sum(r["label"] for r in rows)
    print(split, len(rows), "injections:", inj, "benign:", len(rows) - inj)

random.seed(1)
for lab in (0, 1):
    print("\n--- label", lab, "---")
    pool = [r for r in ds["train"] if r["label"] == lab]
    for r in random.sample(pool, 8):
        print("-", r["text"][:150].replace("\n", " "))
        