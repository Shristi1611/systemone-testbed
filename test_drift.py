import hashlib, json, os, sys, urllib.request
import gateway
from gateway import URL, KEY, WORDINGS, CANARIES, CANARY_ATTACK_MIN, CANARY_OK_MAX, LO, HI, score
from rules import hits
from probes import G

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MODELS = ["multilingual", "english"]
CACHE = "results/drift_cache.jsonl"


def h(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def raw_reply(model, text="What is the capital of France?"):
    instr, yes, no = WORDINGS["v2"]
    questions = {"c": {"type": "choice", "instructions": instr, "criteria": {"A": yes, "B": no}}}
    req = urllib.request.Request(
        URL, data=json.dumps({"state": text, "model": model, "questions": questions}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


cache = {}
if os.path.exists(CACHE):
    for line in open(CACHE, encoding="utf-8"):
        r = json.loads(line)
        cache[(r["m"], r["k"])] = r["s"]


def guard(model, text):
    key = (model, h(text))
    if key in cache:
        return cache[key]
    gateway.MODEL = model  # _ask reads this at call time
    s, _ = score(text)
    cache[key] = s
    with open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"m": model, "k": key[1], "s": s}) + "\n")
    return s


def decision(s, text):
    if hits(text):
        return "block" if s >= LO else "escalate"
    if s >= HI:
        return "escalate"
    return "allow" if s < LO else "escalate"


# 1. what the reply itself says about which model answered
print("1. what each reply says about the model that answered")
for m in MODELS:
    r = raw_reply(m)
    print(f"  asked for {m!r}: model={r.get('model')!r}, routing={r.get('routing')}")

# 2. do the canaries notice a swap?
print("\n2. canary scores under each model (pass = attack >= %.2f, harmless <= %.2f)" % (CANARY_ATTACK_MIN, CANARY_OK_MAX))
print(f"{'canary':44}{'kind':>8}" + "".join(f"{m:>16}" for m in MODELS))
noticed = 0
for text, side in CANARIES:
    row, passes = [], []
    for m in MODELS:
        s = guard(m, text)
        ok = s >= CANARY_ATTACK_MIN if side == "attack" else s <= CANARY_OK_MAX
        passes.append(ok)
        row.append(f"{s:.3f} {'pass' if ok else 'FAIL'}")
    noticed += not all(passes)
    print(f"{text[:42]:44}{side:>8}" + "".join(f"{c:>16}" for c in row))
print(f"canaries that fail under the swapped (english) model: {sum(1 for t, sd in CANARIES if not (guard('english', t) >= CANARY_ATTACK_MIN if sd == 'attack' else guard('english', t) <= CANARY_OK_MAX))} of {len(CANARIES)}")

# 3. how much do decisions change?
items = []
for name, texts in G.items():
    kind = "harmless" if "harmless" in name else "attack"
    items += [(t, kind) for t in dict.fromkeys(texts)]
print(f"\n3. decisions on {len(items)} probe messages (guard + rules, no classifier)")
flips, diffs, by = 0, [], {}
for t, kind in items:
    s0, s1 = guard("multilingual", t), guard("english", t)
    d0, d1 = decision(s0, t), decision(s1, t)
    diffs.append(abs(s0 - s1))
    flips += d0 != d1
    by.setdefault(kind, []).append((d0, d1))
diffs.sort()
print(f"decision differs between models: {flips} of {len(items)}")
print(f"score difference: median {diffs[len(diffs) // 2]:.2f}, largest {diffs[-1]:.2f}")
for kind, pairs in by.items():
    for i, m in enumerate(MODELS):
        c = [sum(p[i] == k for p in pairs) for k in ("allow", "escalate", "block")]
        print(f"  {kind:9}{m:>14}: allow {c[0]}, escalate {c[1]}, block {c[2]}")