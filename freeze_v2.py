"""Write FROZEN_v2.txt: a fingerprint of the v2 model, its thresholds, and the code it runs with."""
import datetime, hashlib, subprocess
import joblib

m = joblib.load("results/v2_final.joblib")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


lines = [
    "Gateway v2 frozen before any sealed pool was scored.",
    f"Frozen on: {datetime.date.today().isoformat()}  (git HEAD before this file: {git_head()})",
    "Laya, not Jev: all numbers come from the Laya server, not the real Jev model.",
    "",
    f"results/v2_final.joblib  sha256 {sha('results/v2_final.joblib')}",
    f"gateway_v2.py            sha256 {sha('gateway_v2.py')}",
    f"gateway.py               sha256 {sha('gateway.py')}",
    f"rules.py                 sha256 {sha('rules.py')}",
    "",
    f"block above {m['t_block']:.4f} (budget {m['block_budget']:.0%} of harmless training messages)",
    f"allow below {m['t_allow']:.4f}, or guard < {m['guard_lo']} + no rule hit + nothing unseen + score below {m['q_path']:.4f}",
    "escalate otherwise; unseen text is never allowed; any error blocks",
    f"inputs: {', '.join(m['features'])}",
    "",
    "Public injection detector tested on the wild training pool: gain +0.014 AUC, below the 0.02 bar, not adopted.",
    "Rules for judging v2 on sealed pools: PREREGISTRATION_v2.md (Amendments 1 and 2).",
]
open("FROZEN_v2.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))