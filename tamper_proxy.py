"""Tamper proxy. Forwards to laya-serve (port 8000) and edits the reply on purpose.
The edit is chosen per request by the X-Tamper-Mode header. Test harness only.
Run:  python tamper_proxy.py
"""
import copy, json, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from guard import CANARY_TEXTS as _OLD_CANARY_TEXTS
from gateway import CANARIES as _GATEWAY_CANARIES

CANARY_TEXTS = set(_OLD_CANARY_TEXTS) | {t for t, _ in _GATEWAY_CANARIES}

UPSTREAM = "http://127.0.0.1:8000"
PORT = 8001


def _choices(r):
    return [a for a in r["answers"].values() if a["type"] == "choice"]


def _nouls(r):
    return [a for a in r["answers"].values() if a["type"] == "noul"]


def tamper(r, mode, last_clean):
    if mode == "none":
        return r
    if mode == "replay":  # a valid reply, but to an older request
        return copy.deepcopy(last_clean) if last_clean else r
    if mode == "rename":
        r["model"] = "attacker-model"
    elif mode == "flip":  # choice becomes the least likely option, probabilities untouched
        for a in _choices(r):
            a["choice"] = min(a["probabilities"], key=a["probabilities"].get)
    elif mode == "shift":  # move 0.3 away from the top option, leave confidence alone
        for a in _choices(r):
            p = a["probabilities"]
            top = max(p, key=p.get)
            d = min(0.3, p[top])
            others = [k for k in p if k != top]
            p[top] = round(p[top] - d, 4)
            for k in others:
                p[k] = round(p[k] + d / len(others), 4)
    elif mode == "inflate":  # confidence set to 1.0
        for a in _choices(r):
            a["x_jev_confidence"] = 1.0
        for a in _nouls(r):
            a["confidence"] = a["answer_confidence"] = 1.0
    elif mode == "drop":  # remove a field
        for a in _choices(r):
            del a["x_jev_confidence"]
        for a in _nouls(r):
            del a["confidence"]
    elif mode == "add":  # add a field
        next(iter(r["answers"].values()))["override"] = "A"
    elif mode == "lazy_noul":  # change only the Noul value
        for a in _nouls(r):
            a["noul"] = 0.0 if a["noul"] > 0.5 else 1.0
    elif mode == "forge":  # flip every answer and keep every field consistent
        for a in _choices(r):
            p = a["probabilities"]
            top = max(p, key=p.get)
            low = min(p, key=p.get)
            p[top], p[low] = p[low], p[top]
            a["choice"] = low
        for a in _nouls(r):
            a["noul"] = round(1 - a["noul"], 4)
    return r


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        mode = self.headers.get("X-Tamper-Mode", "none")
        if body in self.server.cache:
            status, raw = 200, self.server.cache[body]
        else:
            req = urllib.request.Request(
                UPSTREAM + self.path, data=body, method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": self.headers.get("Authorization", "")})
            try:
                with urllib.request.urlopen(req, timeout=600) as r:
                    status, raw = r.status, r.read()
            except urllib.error.HTTPError as e:
                status, raw = e.code, e.read()
            if status == 200:
                self.server.cache[body] = raw
        if status != 200:
            return self._send(status, raw, 0)
        real = json.loads(raw)
        eff = mode
        if mode == "forge_spare":  # attacker who knows the canaries leaves them alone
            eff = "none" if json.loads(body).get("state") in CANARY_TEXTS else "forge"
        out = tamper(copy.deepcopy(real), eff, self.server.last_clean)
        self.server.last_clean = real
        self._send(200, json.dumps(out).encode(), int(out != real))

    def _send(self, status, raw, changed):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Tamper-Changed", str(changed))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    srv.cache, srv.last_clean = {}, None
    print(f"tamper proxy on 127.0.0.1:{PORT} -> {UPSTREAM}  (Ctrl+C to stop)")
    srv.serve_forever()