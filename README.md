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
| Padding, split payloads | Not tested |
| Fail-open (guard errors or times out) | Not tested |
| Tampered replies (changed choice, score or confidence) | Not tested |
| Model version drift, key theft, cache poisoning | Not tested |

## Important limits

- **Everything was run on Laya, not on Jev.** Laya is an open model that copies Jev's API. Calling real Jev needs paid credits, and `smoke_test.py` is written but has never been run. Results about Laya do not transfer to Jev; cutoffs and error rates would have to be measured again.
- The sealed test split has 116 messages, so numbers are indicative, not precise.
- Several hand-written test messages and the rules were written after reading earlier errors. See `RESULTS.md` for what that means for each number.

## Setup (Windows, as used in development)

The Laya server runs in its own virtual environment, separate from this project's.

```bat
:: terminal 1: the local server
mkdir laya-server && cd laya-server
python -m venv .venv
.venv\Scripts\activate
pip install "laya[serve]"
set LAYA_API_KEY=<a long random string you generate>
set LAYA_DEVICE=cpu
set USE_TF=0
set LAYA_PRELOAD=0
laya-serve
```

The server binds to all network interfaces and has no authentication unless `LAYA_API_KEY` is set. Always set it, and decline firewall prompts.

```bat
:: terminal 2: this project
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (it is git-ignored) containing `LAYA_API_KEY=<the same string>`.

## Scripts

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

Datasets are downloaded by the scripts, not stored here. Check each dataset's license before reuse.

## Development note

All numbers in `RESULTS.md` come from running these scripts locally.