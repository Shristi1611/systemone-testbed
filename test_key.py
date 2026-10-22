import os, re, subprocess, sys
from dotenv import load_dotenv
from gateway import decide

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
load_dotenv()
KEY = os.environ.get("LAYA_API_KEY", "")
HF_PATTERN = re.compile(rb"hf_[A-Za-z0-9]{20,}")
SKIP_DIRS = {".venv", ".git", "__pycache__"}


def run(args):
    return subprocess.run(args, capture_output=True).stdout


print("1. leak scan (counts and file names only; the key is never printed)")
if len(KEY) < 8:
    print("  no LAYA_API_KEY found in .env; cannot scan for it")
key_b = KEY.encode()

tracked = run(["git", "ls-files"]).decode("utf-8", "replace").splitlines()
print(f"  .env tracked by git: {'YES - problem' if '.env' in tracked else 'no'}")
ignored = subprocess.run(["git", "check-ignore", ".env"], capture_output=True).returncode == 0
print(f"  .env ignored by git: {'yes' if ignored else 'NO - problem'}")

hits_key, hits_hf = [], []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        p = os.path.join(root, f)
        if f == ".env" or os.path.getsize(p) > 20_000_000:
            continue
        try:
            data = open(p, "rb").read()
        except OSError:
            continue
        if key_b and key_b in data:
            hits_key.append(p)
        if HF_PATTERN.search(data):
            hits_hf.append(p)
print(f"  working folder files containing the Laya key (apart from .env): {len(hits_key)} {hits_key}")
print(f"  working folder files containing a Hugging Face-style token: {len(hits_hf)} {hits_hf}")

history = run(["git", "log", "--all", "-p"])
print(f"  git history ({len(history) // 1024} KB of patches) contains the Laya key: "
      f"{'YES - rotate the key' if key_b and key_b in history else 'no'}")
print(f"  git history contains a Hugging Face-style token: {'YES - revoke it' if HF_PATTERN.search(history) else 'no'}")

print("\n2. gateway behaviour with a wrong, missing and restored key (harmless question each time)")
Q = "What is the capital of France?"
cases = [
    ("right key", None),
    ("wrong key", {"Authorization": "Bearer " + "0" * 32}),
    ("empty key", {"Authorization": ""}),
    ("right key again", None),
]
for name, headers in cases:
    r = decide(Q, headers=headers)
    print(f"  {name:16} -> {r['decision']:8} {r['reason'][:70]}")