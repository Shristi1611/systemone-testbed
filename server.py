"""Backend for the attack simulator. Run:  uvicorn server:app --port 9000
Needs the Laya server on :8000 and Ollama on :11434.

Two lanes on the same input:
  naive   : one Laya question (wording v3, option order A=yes), cutoff 0.5, no validation,
            no rules, no classifier, no pin. Allow if score < 0.5, else block.
  gateway : gateway.Gateway (v1: rules + classifier + guard + windows + canaries + routing
            pin) wrapped in the conversation rule 'block_override'.
One request at a time (Laya runs on a single CPU), so calls take a lock."""
import json, threading, time, urllib.request
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import gateway
from conversation import decide_conversation

app = FastAPI(title="systemone-testbed simulator")
LOCK = threading.Lock()
GW = gateway.Gateway()
NAIVE_CUTOFF = 0.5


class Conv(BaseModel):
    messages: list[str]


def naive_score(text, timeout=600):
    """Raw attack score from one question, no checks of any kind."""
    instr, yes, no = gateway.WORDINGS["v3"]
    q = {"c": {"type": "choice", "instructions": instr, "criteria": {"A": yes, "B": no}}}
    req = urllib.request.Request(
        gateway.URL,
        data=json.dumps({"state": text, "model": gateway.MODEL, "questions": q}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {gateway.KEY}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        reply = json.load(r)
    return reply["answers"]["c"]["probabilities"]["A"]


def naive_lane(messages):
    try:
        s = naive_score(" ".join(messages))
        return {"decision": "block" if s >= NAIVE_CUTOFF else "allow",
                "score": round(s, 4), "reason": ""}
    except Exception as e:  # the naive app has no handling; show what really happens
        return {"decision": "error", "score": None, "reason": f"{type(e).__name__}: {e}"}


def gateway_lane(messages):
    r = decide_conversation(messages, GW.decide, "block_override")
    return {"decision": r["decision"],
            "reason": r["reason"] if r["decision"] != "block" or r["joined"] is None
            else (r["joined"].get("reason") or r["reason"]),
            "per_message": [{"decision": d["decision"], "score": d.get("score"),
                             "clf": d.get("clf"), "hits": d.get("hits"),
                             "reason": d.get("reason", "")} for d in r["per_message"]],
            "joined": None if r["joined"] is None else {
                "decision": r["joined"]["decision"], "score": r["joined"].get("score"),
                "clf": r["joined"].get("clf"), "hits": r["joined"].get("hits"),
                "reason": r["joined"].get("reason", "")}}


def _check(conv):
    msgs = [m for m in conv.messages if m.strip()]
    if not msgs:
        raise HTTPException(400, "send at least one non-empty message")
    return msgs


@app.get("/api/health")
def health():
    out = {}
    for name, url in [("laya", "http://127.0.0.1:8000/"), ("ollama", gateway.OLLAMA + "/api/tags")]:
        try:
            urllib.request.urlopen(url, timeout=3)
            out[name] = "up"
        except urllib.error.HTTPError:
            out[name] = "up"  # it answered, even if with an error code
        except Exception as e:
            out[name] = f"down: {type(e).__name__}"
    out["gateway_tripped"] = GW.tripped
    return out


@app.post("/api/naive")
def api_naive(conv: Conv):
    msgs = _check(conv)
    with LOCK:
        return naive_lane(msgs)


@app.post("/api/gateway")
def api_gateway(conv: Conv):
    msgs = _check(conv)
    with LOCK:
        return gateway_lane(msgs)


@app.post("/api/compare")
def api_compare(conv: Conv):
    msgs = _check(conv)
    with LOCK:
        t0 = time.time()
        n = naive_lane(msgs)
        t1 = time.time()
        g = gateway_lane(msgs)
        t2 = time.time()
    return {"naive": n, "gateway": g,
            "seconds": {"naive": round(t1 - t0, 1), "gateway": round(t2 - t1, 1)}}


@app.post("/api/reset")
def reset():
    """Clear a tripped canary (a fresh gateway object)."""
    global GW
    with LOCK:
        GW = gateway.Gateway()
    return {"ok": True}