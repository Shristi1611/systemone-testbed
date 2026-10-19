"""Checks a Jev/Laya reply before the app may use it. Pure functions: no network, no files."""
import math

EXPECTED_MODEL = "laya-rl-agent"
TOP = {"model", "answers", "usage", "routing"}
KEYS = {
    "choice": {"type", "choice", "probabilities", "confidence",
               "answer_confidence", "action", "x_jev_confidence"},
    "noul": {"type", "noul", "confidence", "answer_confidence", "action"},
}
TOL = 0.001  # replies are rounded to 4 decimals


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def jev_choice_confidence(probs):
    n = len(probs)
    return (max(probs.values()) - 1 / n) / (1 - 1 / n)


def _check_choice(qid, a, q):
    p = a["probabilities"]
    if (not isinstance(p, dict) or set(p) != set(q["criteria"])
            or not all(_num(v) and 0 <= v <= 1 for v in p.values())):
        return [f"3 range: {qid} probabilities malformed"]
    out = []
    total = sum(p.values())
    if abs(total - 1) > TOL:
        out.append(f"3 sum: {qid} probabilities add up to {total:.4f}")
    top = max(p.values())
    if a["choice"] not in p or p[a["choice"]] < top - TOL:
        out.append(f"4 argmax: {qid} choice {a['choice']!r} is not the most likely option")
    c = a["x_jev_confidence"]
    if not _num(c) or abs(c - jev_choice_confidence(p)) > TOL:
        out.append(f"5 confidence: {qid} reports {c!r}, probabilities give "
                   f"{jev_choice_confidence(p):.4f}")
    ac = a["answer_confidence"]
    if not _num(ac) or abs(ac - top) > TOL:
        out.append(f"5 confidence: {qid} answer_confidence {ac!r} is not the top probability")
    return out


def _check_noul(qid, a):
    v = a["noul"]
    if not _num(v) or not 0 <= v <= 1:
        return [f"3 range: {qid} noul value {v!r} outside [0, 1]"]
    out = []
    want = max(v, 1 - v)
    for field in ("confidence", "answer_confidence"):
        c = a[field]
        if not _num(c) or abs(c - want) > TOL:
            out.append(f"5 confidence: {qid} {field} is {c!r}, noul {v} gives {want:.4f}")
    return out


def check_reply(reply, questions):
    """Returns a list of failure messages. Empty list = every check passed."""
    if not isinstance(reply, dict) or set(reply) != TOP:
        got = sorted(reply) if isinstance(reply, dict) else type(reply).__name__
        return [f"1 fields: top-level keys are {got}"]
    fails = []
    if reply["model"] != EXPECTED_MODEL:
        fails.append(f"2 model: got {reply['model']!r}")
    answers = reply["answers"]
    if not isinstance(answers, dict) or set(answers) != set(questions):
        return fails + ["1 fields: answer ids do not match the questions asked"]
    for qid, q in questions.items():
        a = answers[qid]
        want = KEYS[q["type"]]
        if not isinstance(a, dict) or set(a) != want:
            diff = sorted(set(a) ^ want) if isinstance(a, dict) else "not an object"
            fails.append(f"1 fields: {qid} differs by {diff}")
            continue
        if a["type"] != q["type"]:
            fails.append(f"1 fields: {qid} type is {a['type']!r}")
            continue
        fails += _check_choice(qid, a, q) if q["type"] == "choice" else _check_noul(qid, a)
    return fails