import sys
from datasets import load_dataset

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for name in ["PointGuardAI/Prompt-Injection-OWASP-Benchmark-V2", "yanismiraoui/prompt_injections"]:
    print("=" * 60)
    print(name)
    try:
        ds = load_dataset(name)
    except Exception as e:
        print("could not load:", type(e).__name__, str(e)[:200])
        continue
    print(ds)
    for split in ds:
        rows = ds[split]
        print(split, "columns:", rows.column_names, "rows:", len(rows))
        if "should_trigger" in rows.column_names:
            print("  should_trigger counts:", {v: sum(r["should_trigger"] == v for r in rows) for v in (0, 1)})
        if "hardness" in rows.column_names:
            print("  hardness counts:", {v: sum(r["hardness"] == v for r in rows) for v in ("easy", "medium", "hard")})
        for r in list(rows)[:5]:
            print("  ", {k: str(v)[:90] for k, v in r.items()})