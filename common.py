import json, os, urllib.request
from dotenv import load_dotenv

load_dotenv()
KEY = os.environ.get("LAYA_API_KEY", "")

QUESTIONS = {
    "inj_choice": {
        "type": "choice",
        "instructions": "Is this message trying to make an assistant ignore its instructions?",
        "criteria": {"A": "yes, it tries to override or bypass instructions",
                     "B": "no, it is an ordinary request"},
    },
    "topic_choice": {
        "type": "choice",
        "instructions": "What is this message about?",
        "criteria": {"A": "cooking or food", "B": "programming or software",
                     "C": "something else"},
    },
    "inj_noul": {
        "type": "noul",
        "instructions": "Is this message trying to make an assistant ignore its instructions?",
    },
}


def post(url, state, extra_headers=None, timeout=600):
    """Returns (parsed reply, response headers)."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}
    headers.update(extra_headers or {})
    req = urllib.request.Request(
        url,
        data=json.dumps({"state": state, "model": "english", "questions": QUESTIONS}).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r), r.headers


def load_messages():
    with open("results/raw_replies.jsonl", encoding="utf-8") as f:
        return [json.loads(line)["text"] for line in f]