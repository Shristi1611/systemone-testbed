import json
from validator import check_reply

n = bad = 0
for line in open("results/raw_replies.jsonl", encoding="utf-8"):
    row = json.loads(line)
    reply = row["reply"]
    # rebuild the question shapes from the reply itself (option letters, types)
    q = {qid: ({"type": "choice", "criteria": a["probabilities"]} if a["type"] == "choice"
               else {"type": "noul"})
         for qid, a in reply["answers"].items()}
    fails = check_reply(reply, q)
    n += 1
    if fails:
        bad += 1
        print(repr(row["text"][:40]), fails)
print(f"{n} replies, {bad} rejected")