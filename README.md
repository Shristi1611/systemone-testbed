# systemone-testbed

A security test environment for Jev-compatible decision models.

"System One" decision models (such as TypeSafe's Jev, or the open Laya models) return typed answers with probabilities (choice, score, yes/no) instead of text. Software then acts on those numbers, for example to allow, block or escalate a message. This project asks: **how can those decisions be wrong, and what should a layer around the model do about it?**

> **Status: work in progress** (hackathon entry, updated as it goes). Not affiliated with TypeSafe AI or the Laya authors.

## What is tested, and what is not (yet)

| Track | Status |
|---|---|
| Steering text (prompt-injection detection) | Measured on a public dataset |
| Hindi / Hinglish text | Small hand-written probes only |
| Option-order sensitivity | Measured |
| Threshold edge, uncertain zone | Measured |
| Tampered replies (changed choice, score or confidence) | Tested on Laya: edits that break a reply's own arithmetic are caught; consistent forgeries and replays are not (RESULTS.md, section 6) |
| Known-answer canaries | Tested on Laya: catch blanket tampering after a delay (at most 9 requests with the block schedule); beaten by an attacker who knows the canary texts |
| Fail-open (guard errors or times out) | Tested: 17 failure modes, none ended as allow |
| Padding (long inputs) | Tested on Laya: it silently drops everything after about 474 tokens, hiding an attack placed later; a windowed scan recovers it (RESULTS.md, section 7) |
| Split payloads | Four hand-made splits, no evasion shown; a test with innocent-looking fragments is still to do |
| Gateway (rules, validated scoring, windows, canaries) | Built on the multilingual model and demonstrated on hand-picked messages; not yet evaluated on held-out data; no embedding classifier and no reviewer for "escalate" yet (RESULTS.md, section 8) |
| Model version drift, key theft, cache poisoning | Not tested |

**Tamper after the answer:** a validator, a tamper proxy, canaries and fail-closed handling. Edits that break a reply's own arithmetic are caught; consistent forgeries and replays are not, and closing that gap needs replies signed by the provider. In the gateway, a forged reply cannot turn an attack that the rules recognise into "allow" (it drops to escalate at worst), but it can for an attack the rules miss. See `RESULTS.md`.

## Important limits

- **Everything was run on Laya, not on Jev.** Laya is an open model that copies Jev's API. Calling real Jev needs paid credits, and `smoke_test.py` is written but has never been run. Results about Laya do not transfer to Jev; cutoffs, canary answers and error rates would have to be measured again.
- The sealed test split has 116 messages, so numbers are indicative, not precise.
- Several hand-written test messages and the rules were written after reading earlier errors. See `RESULTS.md` for what that means for each number.
- The tamper tests use edits I wrote, 8 messages for the proxy test and one trial per failure mode. They show what the checks catch, not what a real attacker would try.
- The gateway results are demonstrations on 12 hand-picked messages. "Escalate" has no reviewer, so it is currently undecided, not safe.
- The tamper and padding tests used Laya's English model; the injection-detection results and the gateway use the multilingual model.

## Setup (Windows, as used in development)

The Laya server runs in its own virtual environment, separate from this project's. Check whether your prompt starts with `PS` (PowerShell) or not (cmd): the commands for setting the key differ.

Generate a key without printing it into a chat or a log:

```bat
python -c "import secrets; print(secrets.token_hex(16))"
```

```bat
:: terminal 1: the local server (cmd)
mkdir laya-server && cd laya-server
python -m venv .venv
.venv\Scripts\activate
pip install "laya[serve]"
set LAYA_API_KEY=<the key>
set LAYA_DEVICE=cpu
set USE_TF=0
set LAYA_PRELOAD=0
laya-serve
```

In PowerShell, `set` does not create an environment variable. Use this instead:

```powershell
$env:LAYA_API_KEY = "<the key>"
```

The server binds to all network interfaces and has no authentication unless `LAYA_API_KEY` is set. Always set it, and decline firewall prompts. To check that the key took effect, send a request without it and expect HTTP 401:

```bat
curl.exe -s -o NUL -w "%{http_code}" -X POST http://127.0.0.1:8000/v1/systemone -H "Content-Type: application/json" -d "{}"
```

```bat
:: terminal 2: this project
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (it is git-ignored) containing `LAYA_API_KEY=<the same key>`. Confirm it is ignored with `git check-ignore .env`.

## Scripts

### Injection detection

| Script | Purpose |
|---|---|
| `local_test.py`, `smoke_test.py` | Smoke tests for the local server and for hosted Jev (not run) |
| `baseline.py` | Hand-written injection baseline, with an option-order swap |
| `keyword_test.py`, `wording_test.py` | Sensitivity to trigger words and question wording |
| `score_dataset.py` | Scores deepset/prompt-injections with both option orders; caches requests |
| `analyze_zones.py`, `analyze_errors.py` | Allow / escalate / block zones and error analysis (train) |
| `rules.py`, `rules_stress.py`, `eval_combo.py` | Rules hint, its stress test, combined policies |
| `eval_final.py`, `baselines_test.py`, `distribution_check.py` | Test-split evaluation and split comparison |
| `embed_baseline.py`, `shortcut_check.py`, `build_v2.py`, `probes.py` | Embedding classifier, shortcut check and mixed-data version |

### Tamper after the answer

| Script | Needs the Laya server? | Purpose |
|---|---|---|
| `common.py` | n/a | Shared request code and the three typed questions |
| `validator.py` | n/a | Checks a reply: fields, model name, range and sum, argmax, recomputed confidence. Pure functions; a malformed reply becomes a failure, never a crash |
| `test_tamper.py` | no | Applies the edits to one real reply and prints caught / not caught against predictions |
| `collect_raw.py` | yes | Sends 24 varied messages and saves the raw replies to `results/raw_replies.jsonl` |
| `revalidate.py` | no | Runs the validator over the saved raw replies to look for false alarms |
| `check_multilingual.py` | yes | Runs the validator on replies from the multilingual model |
| `tamper_proxy.py` | yes (as upstream) | A proxy on port 8001 that edits live replies on purpose; the edit is chosen by a request header. Test harness only; binds to 127.0.0.1 |
| `run_through_proxy.py` | yes | Starts the proxy, sends messages through it with each edit type, prints a caught / missed table |
| `guard.py` | yes | Guard for the English-model questions: validates every reply, sends known-answer canaries (random or one per block of 5 requests), blocks on any error |
| `test_canary.py` | yes | Runs the guard under both canary schedules against blanket forgery and against forgery that spares the known canaries |
| `test_failopen.py` | no (uses a fake server) | 17 failure modes (timeouts, HTTP errors, truncated or malformed JSON); none may end as allow. Needs `results/raw_replies.jsonl` |

### Long inputs and split payloads

| Script | Needs the Laya server? | Purpose |
|---|---|---|
| `test_padding.py` | yes | Places an attack before, in and after long harmless filler (single call vs windowed scan), then splits attacks into fragments and scores the fragments and the joined text |

### Gateway (multilingual model)

| Script | Needs the Laya server? | Purpose |
|---|---|---|
| `gateway.py` | yes | Rules, validated guard scoring (two wordings x two option orders), windowed scan of long text, allow / escalate / block zones, canaries and fail-closed handling |
| `try_gateway.py` | yes | Six demonstration cases through the gateway |
| `measure_canaries.py`, `measure_canaries2.py` | yes | Measure the gateway's scores for canary candidates |
| `test_gateway_canary.py` | yes | Runs the gateway's canaries through the tamper proxy against blanket forgery and forgery that spares the canaries |
| `show_forged.py` | yes | Prints each message's decision untampered and under a forged reply |

Datasets are downloaded by the scripts, not stored here. Check each dataset's license before reuse.

## Development note

All numbers in `RESULTS.md` come from running these scripts locally.

## License

No license is granted: all rights reserved. The code is public so it can be read and reviewed.