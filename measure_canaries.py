from gateway import score
from guard import CANARIES

print(f"{'side':7} {'score':>7}  message")
for text, side in CANARIES:
    s, unseen = score(text)
    print(f"{side:7} {s:>7.4f}  {text[:60]}")