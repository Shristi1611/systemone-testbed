"""Conversation rule. Score every message on its own and the whole conversation joined
as one text, then combine. Closes the 'benign first, switch later' miss from RESULTS.md
section 13 (the benign part dilutes the joined text).

Two modes:
  "strict"         final = the strictest of all message decisions and the joined decision.
  "block_override" final = the joined decision, raised to block if any single message was
                   blocked. A lone 'escalate' on one message does not raise the result.

Does not change gateway.py. 'decider' is any function: text -> decision dict, for example
gateway.decide, or Gateway().decide to keep the canaries. Fails closed: any error blocks."""
import gateway

RANK = {"allow": 0, "escalate": 1, "block": 2}
MODES = ("strict", "block_override")


def stricter(a, b):
    return a if RANK[a] >= RANK[b] else b


def decide_conversation(messages, decider=gateway.decide, mode="block_override"):
    """messages: list of the user's turns, oldest first, joined with a space.
    Returns {"decision", "per_message", "joined", "reason"}."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if not messages:
        return {"decision": "block", "per_message": [], "joined": None,
                "reason": "empty conversation"}
    try:
        per = [decider(m) for m in messages]
        joined = decider(" ".join(messages)) if len(messages) > 1 else per[0]
    except Exception as e:  # never allow on an error
        return {"decision": "block", "per_message": [], "joined": None,
                "reason": f"{type(e).__name__}: {e}"}
    decision = joined["decision"]
    if mode == "strict":
        for d in per:
            decision = stricter(decision, d["decision"])
    else:
        if any(d["decision"] == "block" for d in per):
            decision = "block"
    return {"decision": decision, "per_message": per, "joined": joined,
            "reason": f"mode={mode}"}