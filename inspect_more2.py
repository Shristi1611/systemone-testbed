import random, re, sys
from datasets import load_dataset

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def show(name):
    print("=" * 60)
    print(name)
    try:
        ds = load_dataset(name)
    except Exception as e:
        print("could not load:", type(e).__name__, str(e)[:200])
        return
    print(ds)
    for split in ds:
        rows = ds[split]
        print(split, rows.column_names, len(rows))
        for r in list(rows)[:6]:
            print("  ", {k: str(v)[:100] for k, v in r.items()})


show("leolee99/NotInject")
show("HuggingFaceH4/no_robots")

ym = load_dataset("yanismiraoui/prompt_injections")["train"]
texts = [r["prompt_injections"] for r in ym]
deva = sum(bool(re.search(r"[\u0900-\u097F]", t)) for t in texts)
print("\nyanismiraoui: rows", len(texts), "| with Hindi script:", deva)
random.Random(3).shuffle(texts)
for t in texts[:12]:
    print("  -", t[:100])