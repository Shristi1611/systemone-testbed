"""Tests the routing pin. A relay on port 8002 forwards requests to the real Laya server and
edits reply["routing"] in a chosen way. Each edit must make gateway.score() raise, and
gateway.decide() must return block with the reason. The untouched relay must still work.
Needs the Laya server (and Ollama, for the decide() check)."""
import copy, json, threading, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
import gateway

UPSTREAM = "http://127.0.0.1:8000/v1/systemone"
PORT = 8002
MODE = {"edit": "none"}


def edit(reply, how):
    r = copy.deepcopy(reply)
    if how == "model_english":
        r["routing"]["model"] = "english"
    elif how == "repo_other":
        r["routing"]["repo"] = "someone-else/other/multilingual"
    elif how == "routing_missing":
        r.pop("routing", None)
    elif how == "routing_null":
        r["routing"] = None
    return r


class Relay(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        req = urllib.request.Request(UPSTREAM, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": self.headers.get("Authorization", "")})
        with urllib.request.urlopen(req, timeout=600) as r:
            reply = json.load(r)
        out = json.dumps(edit(reply, MODE["edit"])).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", PORT), Relay)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{PORT}/v1/systemone"

print(f"{'edit':18}{'score() result':44}decide()")
bad = 0
for how in ["none", "model_english", "repo_other", "routing_missing", "routing_null"]:
    MODE["edit"] = how
    try:
        s, _ = gateway.score("What is the capital of France?", url=URL)
        res = f"returned {s:.3f}"
        raised = False
    except Exception as e:
        res = f"{type(e).__name__}: {str(e)[:30]}"
        raised = True
    d = gateway.decide("What is the capital of France?", url=URL)
    print(f"{how:18}{res:44}{d['decision']} {d['reason'][:40]}")
    want_raise = how != "none"
    if raised != want_raise or (want_raise and d["decision"] != "block"):
        bad += 1
srv.shutdown()
print("\nPASS: every edit caught, untouched reply accepted" if bad == 0 else f"\nFAIL: {bad} row(s) wrong")