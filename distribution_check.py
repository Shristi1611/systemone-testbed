import sys, statistics as st
from datasets import load_dataset
from rules import hits

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ds = load_dataset("deepset/prompt-injections")

GERMAN = ("der", "die", "das", "und", "ist", "nicht", "ich", "wie", "was", "ein", "eine",
          "zu", "mit", "für", "auf", "sich", "von", "den", "dem", "wir", "sie", "du")


def looks_german(t):
    return sum(w.strip(".,?!") in GERMAN for w in t.lower().split()) >= 2


for split in ("train", "test"):
    rows = ds[split]
    for lab, name in ((0, "harmless"), (1, "injection")):
        ts = [r["text"] for r in rows if r["label"] == lab]
        lens = [len(t.split()) for t in ts]
        print(
            f"{split:<5} {name:<9} n={len(ts):>3} | median words {st.median(lens):>4} "
            f"| over 40 words {sum(x > 40 for x in lens) / len(ts):>4.0%} "
            f"| german-looking {sum(looks_german(t) for t in ts) / len(ts):>4.0%} "
            f"| rule hit {sum(bool(hits(t)) for t in ts) / len(ts):>4.0%}"
        )