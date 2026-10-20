import threading
from http.server import HTTPServer

import tamper_proxy
from common import load_messages
from guard import Guard, CANARY_TEXTS

srv = HTTPServer(("127.0.0.1", tamper_proxy.PORT), tamper_proxy.Handler)
srv.cache, srv.last_clean = {}, None
threading.Thread(target=srv.serve_forever, daemon=True).start()
PROXY = f"http://127.0.0.1:{tamper_proxy.PORT}/v1/systemone"

# 12 ordinary messages (none of them canaries), sent 4 times each = 48 requests
messages = [m for m in load_messages() if m not in CANARY_TEXTS][:12] * 4

SCENARIOS = [
    ("no tampering", "none"),
    ("forge every answer", "forge"),
    ("forge, spare the canaries", "forge_spare"),
]

print(f"{len(messages)} requests per run, one canary per 5 requests, 10 runs per scenario\n")
for schedule in ("random", "block"):
    print(f"canary schedule: {schedule}")
    for name, mode in SCENARIOS:
        allowed_counts, tripped = [], 0
        for seed in range(10):
            g = Guard(PROXY, every=5, headers={"X-Tamper-Mode": mode}, seed=seed,
                      schedule=schedule)
            allowed = sum(g.ask(m)[0] == "allow" for m in messages)
            allowed_counts.append(allowed)
            tripped += g.tripped is not None
        print(f"  {name:28} allowed {min(allowed_counts):>2} to {max(allowed_counts):>2} "
              f"of {len(messages)}   canary tripped in {tripped}/10 runs")
    print()