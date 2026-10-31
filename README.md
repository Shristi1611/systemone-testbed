# systemone-testbed

A security test environment for Jev-compatible decision models.

"System One" decision models (such as TypeSafe's Jev, or the open Laya models) return typed answers with probabilities (choice, score, yes/no) instead of text. Software then acts on those numbers, for example to allow, block or escalate a message. This project asks: **how can those decisions be wrong, and what should a layer around the model do about it?**

> **Status: work in progress**, updated as it goes. Not affiliated with TypeSafe AI or the Laya authors.

## The website

A single-page site, `index.html`, shows the project as a story you can click through: **https://shristi1611.github.io/systemone-testbed/** (GitHub Pages).

- **Attacks:** 23 attacks, one card each, with the layer that stops it.
- **Defenses:** the six layers of the gateway (rules, classifier, four-way score, conversation rule, reply checks, canaries and fail-closed).
- **Simulator:** 28 try-outs. Each one plays a plain Jev-style app first, then the same message through the gateway, with green for an attack stopped and red for an attack that got through or a normal message wrongly blocked. You can also type your own text.
- **Results:** ribbon charts of what the gateway did with attacks and harmless messages, by test pool and gateway version.

**What the hosted site shows.** The hosted page cannot reach a model, so it plays *recorded* results. Some of those are illustrated from the measured numbers in `RESULTS.md` and are labelled "illustrated from our measured results, not a live run". Where the plain app was never measured on a case, the page says "not measured". Section 22 of `RESULTS.md` lists, card by card, what was measured and what was drawn from it.

**Running it live (Windows, with the Laya server and Ollama up, as in Setup below):**

```bat
pip install fastapi uvicorn
uvicorn server:app --port 9000
```

Then open `http://127.0.0.1:9000/`. `server.py` serves `index.html` and answers the simulator's Run step with two lanes on the same input: a plain app (one Laya question, cutoff 0.5, no checks) and the gateway. It needs `gateway.py` and `conversation.py` in the same folder and handles one request at a time. If the server is not running, the page falls back to the recorded results.

## Key findings

All results below come from Laya, an open model that copies Jev's API, not from real Jev (see "What transfers to Jev").

1. **Long inputs can hide attacks.** The English model silently ignores everything after about 474 tokens, and the multilingual model stops at 921. An attack placed after long filler goes unseen. Scanning in 1,200-character windows recovers it for the six languages tested.
2. **Tampered replies are only partly catchable.** Edits that break a reply's own arithmetic are caught. Consistent forgeries and replays are not. A prototype of provider-signed, request-bound replies rejected forgery, replay and stripped signatures, but no provider offers this today.
3. **Fail-open is covered.** Across 17 failure modes (timeouts, HTTP errors, truncated or malformed JSON), none ended as "allow".
4. **Model swaps are detectable.** When one checkpoint was swapped for another, 5 of 7 canaries failed and 11 of 71 decisions changed, with no new attack allowed.
5. **The gateway helps, with a cost.** The classifier cut missed injections from 14 to 3 of 60 on the deepset test split, but about half of harmless messages are escalated and "escalate" has no reviewer yet. On a fresh benchmark, about 36% of benign prompts were allowed against 4 to 5% of jailbreaks.
6. **Known weak spot:** Devanagari attacks were mostly only escalated (1 of 10 blocked).
7. **A retrained v2 did not beat v1.** It was frozen and scored once on three sealed pools against rules written beforehand. It failed the short-text rule (attacks allowed 11.0% and 9.0% against a 5% limit), so v1 stays the gateway (RESULTS.md, section 21).

## What is tested, and what is not (yet)

The gateway in use is **v1** (rules, embedding classifier, guard score). A retrained v2 was built and tested once on sealed data against pre-registered rules. It did not pass, so it is not the default.

| Track | Status |
|---|---|
| Steering text (prompt-injection detection) | Measured on a public dataset |
| Hindi / Hinglish text | 50 hand-written messages, not reviewed by a native reader: Hinglish attacks were all blocked, but Devanagari attacks were mostly only escalated (1 of 10 blocked) because the classifier and rules are weak on Devanagari (RESULTS.md, section 15) |
| Option-order sensitivity | Measured |
| Threshold edge, uncertain zone | Measured |
| Tampered replies (changed choice, score or confidence) | Tested on Laya: edits that break a reply's own arithmetic are caught; consistent forgeries and replays are not (RESULTS.md, section 6) |
| Known-answer canaries | Tested on Laya: catch blanket tampering after a delay (at most 9 requests with the block schedule); beaten by an attacker who knows the canary texts |
| Fail-open (guard errors or times out) | Tested: 17 failure modes, none ended as allow |
| Padding (long inputs) | Tested on Laya: it silently drops everything after about 474 tokens, hiding an attack placed later; a windowed scan recovers it (RESULTS.md, section 7). The multilingual model reads 921 tokens and drops the rest, and the gateway's 1,200-character windows fit for the six languages tested (section 14) |
| Split payloads | Four hand-made splits on the English model and eight more with innocent-looking fragments on the gateway: no evasion at message level, but one attack was missed when the whole conversation was scored as one text (RESULTS.md, sections 7 and 13) |
| Gateway (rules, embedding classifier, validated scoring, windows, canaries) | Built on the multilingual model and evaluated on held-out groups (RESULTS.md, sections 8 and 9). The classifier cuts missed injections on the deepset test split from 14 to 3 of 60 but blocks more harmless messages. About half of harmless messages are escalated, and "escalate" has no reviewer yet. On a fresh benchmark the same pattern held (section 10) |
| Fresh test of the frozen gateway | Run once on 200 prompts from a public benchmark (RESULTS.md, section 10): about 36% of benign prompts allowed against 4 to 5% of jailbreaks; the classifier blocks more of both (benign blocked 11% to 29%, jailbreaks blocked 44% to 66%) |
| Resolving the escalate zone | Two attempts, a trained second look and a simple shrink rule, both passed on held-out data and failed on the fresh benchmark, so neither is adopted (RESULTS.md, sections 11 and 12). Escalate is still undecided and still has no reviewer |
| Model version drift | Simulated with Laya's two checkpoints: the reply's routing field names the model, 5 of 7 canaries failed under the swapped model, 11 of 71 decisions changed and no new attack was allowed (section 16) |
| Key theft and rotation | A leak scan found nothing in files or git history; wrong, empty and restored keys behave correctly (fail closed, then recover) (section 17). A stolen key cannot be countered by the gateway; rotate it |
| Cache poisoning | The gateway has no cache. A signed decision cache rejects edited, forged, moved and stale entries; it does not stop someone who has the key, and it does not cover a model swap (section 18) |
| Signed replies | A prototype of provider-signed, request-bound replies rejected forgery, replay and stripped signatures; it is a stand-in for something the provider would have to offer (section 19) |
| Naive baselines | Tested: simple apps that act directly on the raw model number, and a length-only rule, scored on the same sets (`eval_naive.py`, RESULTS.md); the length-only rule is the bar a detector has to beat |
| Newer, larger data (wild jailbreaks and three more datasets) | Added and pooled for retraining; three pools were sealed and scored once (RESULTS.md, sections 20 and 21) |
| Gateway v2 (retrained classifier + learned combiner) | Built, frozen (`FROZEN_v2.txt`, git tag) and tested once on sealed pools against rules written beforehand (`PREREGISTRATION_v2.md`). **It failed rule B on short text** (attacks allowed 11.0% and 9.0% against a 5% limit), so **v1 stays the gateway**. v2 is kept as a quieter, clearly labelled second profile (RESULTS.md, sections 20 and 21) |
| Reviewer for escalate | Not built |
| Real Jev | Not tested |

**Tamper after the answer:** a validator, a tamper proxy, canaries and fail-closed handling. Edits that break a reply's own arithmetic are caught; consistent forgeries and replays are not, and closing that gap needs replies signed by the provider (a prototype of that is in section 19). In the gateway, a forged reply cannot turn an attack that the rules recognise into "allow" (it drops to escalate at worst), but it can for an attack the rules miss. See `RESULTS.md`.

## Important limits

- **Everything was run on Laya, not on Jev.** Laya is an open model that copies Jev's API. Calling real Jev needs paid credits, and `smoke_test.py` is written but has never been run. Results about Laya do not transfer to Jev; cutoffs, canary answers and error rates would have to be measured again.
- The sealed test split has 116 messages, so numbers are indicative, not precise.
- Several hand-written test messages and the rules were written after reading earlier errors. See `RESULTS.md` for what that means for each number.
- The tamper tests use edits I wrote, 8 messages for the proxy test and one trial per failure mode. They show what the checks catch, not what a real attacker would try.
- The gateway's held-out numbers come from one pre-chosen combination rule, with no confidence intervals. The deepset test split had been looked at, and several probe groups have only 4 to 22 messages. "Escalate" has no reviewer, so it is currently undecided, not safe.
- The fresh test uses 100 benign and 100 jailbreak prompts from one benchmark, one sample and one seed. "Jailbreak" is not the same as "injection", and the benchmark overlaps with data used earlier. The two escalate-zone attempts were judged against rules fixed beforehand and rejected; the fresh sample has been used for three checks and should not be used again for tuning (sections 10 to 12).
- The Hindi/Hinglish messages were written by me and not reviewed by a native reader, and the attack groups are mirrored pairs (section 15). Drift was simulated with two Laya checkpoints, and the signed-reply test is a prototype of something no provider offers today (sections 16 and 19).
- Gateway v2 was tested on three sealed pools, each scored once. Two are short-text sets from public datasets; "attack" and "harmless" labels are the datasets' own and were not re-checked by hand. The pre-registration was amended twice, in the open, before the sealed scoring (rule C was originally unachievable; see `PREREGISTRATION_v2.md`). Rules F (regression on old sets) and G (fail-closed, tamper and canary checks for v2) were not run because rule B already decided the outcome.
- Several of my predictions were wrong and are disclosed in RESULTS.md section 21 (for example, v1 blocked 76 to 78% of the short sealed pools, not about half).
- The tamper and padding tests used Laya's English model; the injection-detection results and the gateway use the multilingual model.

## What transfers to Jev

I could not test real Jev (it needs paid credits), so I used Laya, which copies Jev's API. Here is what I expect to carry over and what would need re-measuring.

**Should carry over (logic does not depend on the model):**
- The validator, which checks fields, model name, range and sum, argmax and recomputed confidence. This assumes Jev's reply has the same structure as Laya's; `smoke_test.py` is written to check that.
- The tamper proxy and the fail-open tests (the fail-open tests use a fake server).
- The windowed-scan idea and the allow / escalate / block structure.

**Must be re-measured on Jev:**
- Score cutoffs and the uncertain zone.
- Canary answers and the canary schedule.
- Error rates and all injection-detection numbers.
- The input-length limit. The 474 and 921-token limits are Laya's. Jev's context window is reported as 32,000 tokens, so its limit should be measured, not assumed.
- Drift behavior, which here was simulated with two Laya checkpoints.

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

The embedding classifier needs [Ollama](https://ollama.com) running with the `nomic-embed-text` model (`ollama pull nomic-embed-text`). The gateway needs it; if Ollama is down the gateway blocks every request. Train and save the classifier once with `python train_classifier.py`; it writes `results/clf_mixed.joblib`, which is git-ignored.

The fresh-test and pool scripts use `rogue-security/prompt-injections-benchmark`, a gated dataset on Hugging Face (the other datasets used are public). Accept its terms on the dataset page while logged in, create a read token at huggingface.co/settings/tokens, and set it in the same window before running (PowerShell, keep the quotes):

```powershell
$env:HF_TOKEN = "<your token>"
```

Never commit the token. The dataset is licensed cc-by-nc-4.0 (non-commercial).

## Scripts

### Website

| File | Needs the Laya server? | Purpose |
|---|---|---|
| `index.html` | no | The whole site in one file: attacks, defenses, simulator, results. Plays recorded results when no server is running |
| `server.py` | yes (and Ollama) | Local backend for the simulator's live run: a plain-app lane and a gateway lane on the same input. Run with `uvicorn server:app --port 9000` |

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
| `gateway.py` | yes (and Ollama) | Rules, embedding classifier, validated guard scoring (two wordings x two option orders), windowed scan of long text, allow / escalate / block zones, canaries and fail-closed handling |
| `train_classifier.py` | Ollama only if embeddings are missing | Trains and saves the mixed-data embedding classifier (same data and seeds as `build_v2.py`) |
| `try_gateway.py` | yes (and Ollama) | Six demonstration cases through the gateway |
| `measure_canaries.py`, `measure_canaries2.py` | yes | Measure the gateway's scores for canary candidates |
| `test_gateway_canary.py` | yes | Runs the gateway's canaries through the tamper proxy against blanket forgery and forgery that spares the canaries |
| `show_forged.py` | yes | Prints each message's decision untampered and under a forged reply |
| `eval_gateway.py` | yes (and Ollama) | Evaluates the gateway on held-out groups with and without the classifier; caches scores in `results/gw_cache.jsonl` |

### Fresh test and escalate zone

| Script | Needs the Laya server? | Purpose |
|---|---|---|
| `eval_fresh.py` | yes (and Ollama) | Samples 100 benign and 100 jailbreak prompts (seed 21) from the benchmark after removing duplicates of data used earlier; runs the frozen gateway with and without the classifier; shares `results/gw_cache.jsonl` |
| `score_train.py` | yes | Scores the 1,365 training messages once (guard and rules, plus the classifier's cross-validated score) into `results/train_scores.jsonl`; resumable |
| `second_look.py` | no | Trains the learned second look for the escalate zone on training data only and fixes its cutoffs |
| `eval_second_look.py` | no | One-time check of the second look on held-out and fresh data against rules fixed beforehand (fails on fresh data) |
| `zone_split.py` | no | Counts what is inside the training escalate zone, by kind |
| `eval_shrink.py` | no | One-time check of the shrink rule on held-out and fresh data (fails on fresh data) |

### More tests (RESULTS.md, sections 13 to 19)

| Script | Needs the Laya server? | Purpose |
|---|---|---|
| `test_split_innocent.py` | yes (and Ollama) | Eight attacks split into innocent-looking fragments and four normal conversations; decisions per fragment and for the joined text |
| `test_multilingual_window.py` | yes | Where the multilingual model stops reading (single requests, attack last in varied filler) |
| `test_token_density.py` | yes | Tokens per character for six languages against the 921-token limit |
| `probes_hi.py` | n/a | 50 Hindi/Hinglish test messages (data only; written by me, not reviewed by a native reader) |
| `eval_hi.py` | yes (and Ollama) | Runs the frozen gateway on the Hindi/Hinglish set; caches scores in `results/hi_cache.jsonl` |
| `test_drift.py` | yes | Simulated model swap: routing field, canaries and decision changes |
| `test_key.py` | yes (and Ollama) | Leak scan of files and git history (counts only) and gateway behaviour with wrong, empty and restored keys |
| `safe_cache.py` | yes (and Ollama) | Signed decision cache; run it directly for its eight-check self-test |
| `test_signed.py` | yes | Prototype of signed, request-bound replies against forgery, replay and stripped signatures |

### Newer data, gateway v2 and the sealed test (RESULTS.md, sections 20 and 21)

| Script | Needs the Laya server? | Purpose |
|---|---|---|
| `export_eval_sets.py`, `eval_naive.py` | yes (and Ollama) | Export the evaluation sets and score naive apps and a length-only rule on them |
| `inspect_new_data.py`, `inspect_wild.py` | no | Look at the new datasets (counts, lengths, duplicates) before using them |
| `build_pool.py`, `score_pool.py`, `check_pool.py` | `score_pool.py` yes | Build the pools (training, wild, and three sealed pools), score them with the guard and rules, check for overlap |
| `build_gateway_v2.py` | no | Retrain the classifier on old plus wild windows and fit the combiner |
| `compare_heads.py`, `compare_combiners.py`, `compare_allowpath.py`, `compare_agree.py`, `compare_budget.py` | no | Compared classifier heads, combiners, the allow path, an agreement rule (rejected) and harmless-block budgets, on out-of-fold scores |
| `try_detector.py` | no | Tested a pre-trained DeBERTa injection detector (+0.014, dropped) |
| `finalize_v2.py`, `gateway_v2.py` | `gateway_v2.py` yes (and Ollama) | Fix the thresholds from out-of-fold scores; the frozen v2 gateway |
| `freeze_v2.py`, `FROZEN_v2.txt` | no | Record file hashes and the tag before any sealed pool was scored |
| `PREREGISTRATION_v2.md` | n/a | Rules A to G, predictions and the two amendments, written before the sealed pools were scored |
| `eval_sealed.py` | yes (and Ollama) | The one-time sealed scoring of v1, v2 and the length-only rule, and the rule-by-rule verdict |

Datasets are downloaded by the scripts, not stored here. Check each dataset's license before reuse.

## Development note

All numbers in `RESULTS.md` come from running these scripts locally.

## License

No license is granted: all rights reserved. The code is public so it can be read and reviewed.