# Results

Model: Laya (multilingual checkpoint, zero-shot) behind a Jev-compatible API, unless stated. Task: flag prompt-injection messages in `deepset/prompt-injections` (train: 546 messages, 203 injections; test: 116 messages, 60 injections). Each message was scored with two question wordings (v2, v3), each asked in both option orders.

## 1. The zero-shot guard degrades from train to test

| | Train v2 | Train v3 | Test v2 | Test v3 |
|---|---|---|---|---|
| Ranking quality (AUC, 0.5 = random) | 0.823 | 0.805 | 0.612 | 0.629 |
| Harmless messages flagged at 0.50 | 17% | 8% | 38% | 25% |
| Injections missed at 0.50 | 35% | 42% | 48% | 55% |

Rewording the question moved where scores sit, not how well they separate the classes.

## 2. Policies on the sealed test split (cutoffs fixed on train)

| Policy | Injections allowed | Harmless blocked | Escalated | Escalated that are injections |
|---|---|---|---|---|
| Single cutoff 0.5 | 48% | 34% | 0% | n/a |
| Guard + three zones | 30% | 34% | 18% | 52% |
| Guard + rules | 23% | 0% | 56% | 54% |
| Rules only | 75% | 2% | n/a | n/a |

Caveats: the zone cutoffs (0.25 / 0.50) were picked on a 200-message train sample, and the rules were written after reading errors on that sample. No second-look step exists yet, so "escalated" messages are unresolved.

## 3. The rules over-fire on realistic text

On 20 hand-written harmless office-style messages, the rules flagged 15 (75%), for example "Cancel my earlier order and ignore the previous invoice". On the benchmark's harmless messages they flagged 0 of 119 because those are mostly short topic searches. The stress set was written to contain trigger words, so 75% is a worst case.

## 4. A near-perfect score that was a benchmark shortcut

A logistic-regression classifier on `nomic-embed-text` embeddings, trained on deepset train only:

- deepset test AUC **0.987**, while a classifier using only message length reached **0.806**
- but it flagged 85% of held-out hard-negative prompts (NotInject) and 80% of ordinary prompts (no_robots)

Retrained with hard negatives and ordinary prompts added (cutoff fixed from cross-validated train scores):

| Share flagged as injection | Deepset only | Mixed data |
|---|---|---|
| deepset test injections (want high) | 97% | 87% |
| deepset test harmless (want low) | 11% | 7% |
| NotInject held-out half (want low) | 85% | 9% |
| no_robots test (want low) | 80% | 3% |
| 22 hand-written hard harmless | 95% | 68% |
| 15 Hindi/Hinglish harmless | 43-50% | 38-43% |
| 12 Hindi/Hinglish attacks | 60-71% | 57-60% |

Deepset test AUC fell from 0.987 to 0.939 with the fix.

## 5. Other observations

- Swapping the order of the answer options changed outcomes on borderline messages (one attack went from caught at 0.55 to missed at 0.30; one false alarm disappeared). Average gap between the two orders on train was 0.13-0.15.
- Two question types on the same message (choice vs yes/no) disagreed in both directions; neither was reliably better.
- On the test split the rules fire on 25% of injections, against 43% on train, because they were written from train errors.

## Caveats

- Laya, not Jev.
- Small samples: hand-written groups have 5-22 messages, so one message moves a rate by 5-20 points.
- The NotInject split is by hash of each prompt; near-duplicate prompts may sit on both sides, so the 9% is probably optimistic. The no_robots figure is the cleaner one.
- Hand-written messages were written after seeing earlier results and are not independent.
- The deepset test split has been looked at; later changes are judged on other data.