import copy
from validator import check_reply

QUESTIONS = {
    "inj_choice": {"type": "choice",
                   "criteria": {"A": "yes, it tries to override or bypass instructions",
                                "B": "no, it is an ordinary request"}},
    "inj_noul": {"type": "noul"},
}

BASE = {  # the real reply to "Ignore all previous instructions..."
    "model": "laya-rl-agent",
    "answers": {
        "inj_choice": {"type": "choice", "choice": "A",
                       "probabilities": {"A": 0.9871, "B": 0.0129},
                       "confidence": 0.9002, "answer_confidence": 0.9871,
                       "action": {"act_probability": 1.0}, "x_jev_confidence": 0.9742},
        "inj_noul": {"type": "noul", "noul": 0.8893, "confidence": 0.8893,
                     "answer_confidence": 0.8893, "action": {"act_probability": 1.0}},
    },
    "usage": {"input_tokens": 99, "output_tokens": 0, "state_tokens": 10,
              "state_tokens_dropped": 0, "truncated": False, "truncated_questions": []},
    "routing": {"model": "english", "repo": "convaiinnovations/laya",
                "reason": "explicit model='english'", "detection": None, "workflow": None},
}


def flip_choice(r): r["answers"]["inj_choice"]["choice"] = "B"
def shift_probs(r): r["answers"]["inj_choice"]["probabilities"] = {"A": 0.60, "B": 0.40}
def inflate_conf(r): r["answers"]["inj_choice"]["x_jev_confidence"] = 0.99
def rename_model(r): r["model"] = "attacker-model"
def drop_field(r): del r["answers"]["inj_choice"]["x_jev_confidence"]
def add_field(r): r["answers"]["inj_choice"]["override"] = "A"

def forge(r):  # rewrite choice and probabilities together; confidence stays valid
    c = r["answers"]["inj_choice"]
    c["choice"] = "B"
    c["probabilities"] = {"A": 0.0129, "B": 0.9871}
    r["answers"]["inj_noul"]["noul"] = 0.0

def replay(r): pass  # a perfectly valid reply, but to an older message


# (name, edit, predicted to be caught?)
MUTATIONS = [
    ("1 flip choice", flip_choice, True),
    ("2 shift probabilities", shift_probs, True),
    ("3 inflate confidence", inflate_conf, True),
    ("4 rename model", rename_model, True),
    ("5a drop a field", drop_field, True),
    ("5b add a field", add_field, True),
    ("6 coherent forgery", forge, False),
    ("7 replay of old reply", replay, False),
]

base_fails = check_reply(BASE, QUESTIONS)
print("control (untouched reply):", "passes" if not base_fails else base_fails)
if base_fails:
    raise SystemExit("validator rejects a real reply; fix that first")

print()
for name, edit, predicted in MUTATIONS:
    r = copy.deepcopy(BASE)
    edit(r)
    fails = check_reply(r, QUESTIONS)
    caught = bool(fails)
    note = "as predicted" if caught == predicted else "SURPRISE"
    print(f"{name:24} {'CAUGHT' if caught else 'not caught':11} {note:13} {fails[0] if fails else ''}")