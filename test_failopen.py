import copy, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from guard import Guard

with open("results/raw_replies.jsonl", encoding="utf-8") as f:
    GOOD = json.loads(f.readline())["reply"]  # a genuine reply

FAKE_PORT = 8002
FAKE = f"http://127.0.0.1:{FAKE_PORT}/v1/systemone"


def variant(edit):
    r = copy.deepcopy(GOOD)
    edit(r)
    return json.dumps(r).encode()


def _set(path_keys, value):
    def edit(r):
        d = r
        for k in path_keys[:-1]:
            d = d[k]
        d[path_keys[-1]] = value
    return edit


good_body = json.dumps(GOOD).encode()
# name -> (status, body, declared Content-Length or None, delay in seconds)
SCENARIOS = {
    "good (control)": (200, good_body, None, 0),
    "http 500": (500, b'{"error":"boom"}', None, 0),
    "http 401 (bad key)": (401, b'{"detail":"unauthorized"}', None, 0),
    "http 429": (429, b'{"detail":"slow down"}', None, 0),
    "slow (3s, timeout 1s)": (200, good_body, None, 3),
    "truncated json": (200, good_body[: len(good_body) // 2], None, 0),
    "body shorter than declared": (200, good_body[: len(good_body) // 2], len(good_body), 0),
    "empty body": (200, b"", None, 0),
    "html error page": (200, b"<html>502 Bad Gateway</html>", None, 0),
    "json null": (200, b"null", None, 0),
    "json list": (200, b"[]", None, 0),
    "json {}": (200, b"{}", None, 0),
    "answers is null": (200, variant(_set(["answers"], None)), None, 0),
    "choice is a list": (200, variant(_set(["answers", "inj_choice", "choice"], ["A"])), None, 0),
    "probabilities null": (200, variant(_set(["answers", "inj_choice", "probabilities"], None)), None, 0),
    "noul is a string": (200, variant(_set(["answers", "inj_noul", "noul"], "0.9")), None, 0),
    "noul is NaN": (200, variant(_set(["answers", "inj_noul", "noul"], float("nan"))), None, 0),
}


class Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        status, body, declared, delay = SCENARIOS[self.headers.get("X-Scenario", "good (control)")]
        try:
            time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(declared if declared is not None else len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass

    def log_message(self, *args):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", FAKE_PORT), Fake)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()

CASES = [(name, FAKE) for name in SCENARIOS]
CASES.append(("connection refused", "http://127.0.0.1:8009/v1/systemone"))

print(f"{'scenario':28} {'first call':11} {'then healthy':13} reason")
fail_open = crashed = stuck = 0
for name, url in CASES:
    scenario = name if name in SCENARIOS else "good (control)"
    g = Guard(url, every=10**9, headers={"X-Scenario": scenario}, timeout=1)
    try:
        first, _, why = g.ask("Hello")
    except Exception as e:  # the guard itself must never raise
        first, why = "RAISED", f"{type(e).__name__}: {e}"
    g.url, g.headers = FAKE, {"X-Scenario": "good (control)"}
    second = g.ask("Hello")[0]
    control = name == "good (control)"
    fail_open += (first == "allow") and not control
    crashed += first == "RAISED"
    stuck += second != "allow"
    print(f"{name:28} {first:11} {second:13} {why[:60]}")

print(f"\nfailed open: {fail_open}   crashed: {crashed}   stuck blocking after recovery: {stuck}")