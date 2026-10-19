import threading
import urllib.error
from http.server import HTTPServer

import tamper_proxy
from common import post, load_messages, QUESTIONS
from validator import check_reply

# start the tamper proxy inside this script, on 127.0.0.1:8001
srv = HTTPServer(("127.0.0.1", tamper_proxy.PORT), tamper_proxy.Handler)
srv.cache, srv.last_clean = {}, None
threading.Thread(target=srv.serve_forever, daemon=True).start()

PROXY = f"http://127.0.0.1:{tamper_proxy.PORT}/v1/systemone"
MODES = ["none", "flip", "shift", "inflate", "rename", "drop", "add",
         "lazy_noul", "forge", "replay"]

messages = load_messages()[::3]  # 8 messages: ordinary, attacks, trigger words, odd
print(f"{len(messages)} messages x {len(MODES)} edit types\n")
print(f"{'edit':10} {'changed':>8} {'caught':>7} {'missed':>7} {'false alarm':>12}")

for mode in MODES:
    changed = caught = missed = false_alarm = 0
    for text in messages:
        try:
            reply, headers = post(PROXY, text, {"X-Tamper-Mode": mode})
        except urllib.error.URLError:
            fails, was_changed = ["request failed"], False  # fail closed
        else:
            fails = check_reply(reply, QUESTIONS)
            was_changed = headers.get("X-Tamper-Changed") == "1"
        if was_changed:
            changed += 1
            caught += bool(fails)
            missed += not fails
        elif fails:
            false_alarm += 1
    print(f"{mode:10} {changed:>8} {caught:>7} {missed:>7} {false_alarm:>12}")