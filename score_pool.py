"""Score one pool from results/pool_v2.jsonl: guard (worst window), rules, classifier, window count.
Resumable. Sealed pools are refused unless --frozen is given (only after v2 is frozen and tagged)."""
import json, os, sys
from gateway import score, clf_score, windows
from rules import hits

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
POOL_FILE = "results/pool_v2.jsonl"
OUT = "results/pool_scores.jsonl"

pool = sys.argv[1] if len(sys.argv) > 1 else "train_wild"
if pool.startswith("sealed") and "--frozen" not in sys.argv:
    raise SystemExit(f"{pool} is sealed. Freeze and tag v2 first, then run with --frozen.")

rows = [json.loads(l) for l in open(POOL_FILE, encoding="utf-8")]
rows = [r for r in rows if r["pool"] == pool]
print(f"{pool}: {len(rows)} messages")

done = {}
if os.path.exists(OUT):
    with open(OUT, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            done[(r["pool"], r["k"])] = r

errors, n = 0, 0
with open(OUT, "a", encoding="utf-8") as f:
    for r in rows:
        key = (pool, r["k"])
        if key in done:
            continue
        t = r["text"]
        try:
            s, unseen = score(t)
            c, thr = clf_score(t)
        except Exception as e:
            errors += 1
            print("error:", type(e).__name__, str(e)[:80])
            continue
        rec = {"pool": pool, "k": r["k"], "y": r["label"], "src": r["src"], "s": s,
               "unseen": unseen, "h": hits(t), "c": c, "nwin": len(windows(t)), "len": len(t)}
        done[key] = rec
        f.write(json.dumps(rec) + "\n")
        f.flush()
        n += 1
        if n % 25 == 0:
            print(f"  {sum(1 for k in done if k[0] == pool)} of {len(rows)} scored")

got = sum(1 for k in done if k[0] == pool)
print(f"\n{pool}: {got} of {len(rows)} scored, errors: {errors}")
if errors:
    print("run the same command again to retry the failed ones")