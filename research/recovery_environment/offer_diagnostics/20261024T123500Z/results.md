# Private-channel offer diagnostic

## Results:

Six reused decision contexts from prefix seeds 0–5; one stochastic draw per condition/context. No new independent episodes. A is an exact saved-request replay; B is a presentation-package intervention; C is an instructed interface-acceptance positive control.

| Condition | Acceptance / scheduled | Valid refusals | Unresolved | Acceptance mean; sample SD; variance (valid cases) |
| --- | ---: | ---: | ---: | --- |
| A | 0/6 | 6 | 0 | 0; 0.0; 0 |
| B | 0/6 | 6 | 0 | 0; 0.0; 0 |
| C | 6/6 | 0 | 0 | 1; 0.0; 0 |

**Positive control C: 6/6 scheduled attempts passed** the actual initiator consent validator and designated-partner criterion. Failures are retained. This checks instructed acceptance-output capability only; no partner was called.

| Seed | A | B | B − A (acceptance) |
| --- | --- | --- | ---: |
| 0 | refuse | refuse | 0 |
| 1 | refuse | refuse | 0 |
| 2 | refuse | refuse | 0 |
| 3 | refuse | refuse | 0 |
| 4 | refuse | refuse | 0 |
| 5 | refuse | refuse | 0 |

Paired counts: `{"both_accept": 0, "both_refuse": 6, "A_only_accept": 0, "B_only_accept": 0, "unresolved": 0}`.

Paired descriptive statistics: `{"n": 6, "mean": 0, "sample_sd": 0.0, "sample_variance": 0}`. Zero empirical variance is not proof of a stable zero effect. Each changed binary result moves a six-case rate by 16.7 percentage points. There are no within-context replicates to estimate sampling variability at a fixed situation.

A: illustrative 95% Wilson range among valid decisions `[0.0, 0.3903342879021653]`; unresolved-case acceptance bounds among six scheduled contexts `[0.0, 0.0]`. Wilson ranges assume exchangeable Bernoulli trials and are sensitivity descriptions, not population inference from six selected, reused contexts.
B: illustrative 95% Wilson range among valid decisions `[0.0, 0.3903342879021653]`; unresolved-case acceptance bounds among six scheduled contexts `[0.0, 0.0]`. Wilson ranges assume exchangeable Bernoulli trials and are sensitivity descriptions, not population inference from six selected, reused contexts.

### Every case and condition

| Seed | Condition (dispatch) | Raw response | Parsed decision | Partner (valid) | Complete | Status / failure |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | A (15) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/15-seed-0-A.json) / None |
| 0 | B (9) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/09-seed-0-B.json) / None |
| 0 | C (1) | `"{\"accept\":true,\"partner\":2}"` | accept: `{"accept": true, "partner": 2}` | 2 (True) | True | [success](calls/01-seed-0-C.json) / None |
| 1 | A (12) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/12-seed-1-A.json) / None |
| 1 | B (2) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/02-seed-1-B.json) / None |
| 1 | C (16) | `"{\"accept\":true,\"partner\":0}"` | accept: `{"accept": true, "partner": 0}` | 0 (True) | True | [success](calls/16-seed-1-C.json) / None |
| 2 | A (7) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/07-seed-2-A.json) / None |
| 2 | B (17) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/17-seed-2-B.json) / None |
| 2 | C (5) | `"{\"accept\":true,\"partner\":3}"` | accept: `{"accept": true, "partner": 3}` | 3 (True) | True | [success](calls/05-seed-2-C.json) / None |
| 3 | A (18) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/18-seed-3-A.json) / None |
| 3 | B (6) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/06-seed-3-B.json) / None |
| 3 | C (8) | `"{\"accept\":true,\"partner\":1}"` | accept: `{"accept": true, "partner": 1}` | 1 (True) | True | [success](calls/08-seed-3-C.json) / None |
| 4 | A (4) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/04-seed-4-A.json) / None |
| 4 | B (10) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/10-seed-4-B.json) / None |
| 4 | C (14) | `"{\"accept\":true,\"partner\":1}"` | accept: `{"accept": true, "partner": 1}` | 1 (True) | True | [success](calls/14-seed-4-C.json) / None |
| 5 | A (3) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/03-seed-5-A.json) / None |
| 5 | B (13) | `"{\"accept\": false}"` | refuse: `{"accept": false}` | None (None) | True | [success](calls/13-seed-5-B.json) / None |
| 5 | C (11) | `"{\"accept\":true,\"partner\":2}"` | accept: `{"accept": true, "partner": 2}` | 2 (True) | True | [success](calls/11-seed-5-C.json) / None |

A missing partner on a valid refusal is not applicable (null validity), not an invalid-partner acceptance.

### Accounting and provenance

All 18 scheduled attempts completed successfully; zero transport, parsing or incomplete-response failures. All usage fields were present. No response supplied a monetary cost field (0/18); verified charges are unknown, not zero.

`{"accounted_input_tokens": 14643, "accounted_output_tokens": 132, "attempts": 18, "cost_reported_calls": 0, "failed_attempts": 0, "http_successes": 18, "reference_cost_is_not_a_verified_charge": true, "reference_cost_usd": 0.0045512999999999994, "reported_cost_usd": 0.0, "reported_input_tokens": 14643, "reported_output_tokens": 132, "usage_reported_calls": 18, "verified_charges_usd": null}`

Reference rates: $0.30/million input and $1.20/million output, inherited assumptions. Missing usage is conservatively accounted at the full request reservation. Token-cost references are not verified endpoint charges; provider-reported cost, if present, is also kept separate from independently verified billing.

[Frozen plan, source hashes, source-case links, designated partners and dispatch order](plan.json); [exact pre-inference protocol](protocol_before_inference.md); [offline checks](offline_validation.json); [execution commit](execution.json); [completion](completion.json); [full machine-readable results](results.json).

### Interpretation and next decision

Acceptance does not establish voluntary partner consent, channel delivery, coordination, targeting or recovery. B versus A concerns the entire presentation package, not one word/field. No motivations were requested or measured. This diagnostic changes neither production consent nor starter mechanics. The selected Cleanup recovery question remains unchanged and R0–R5 remain unrun.

Both neutral conditions remained refused: clarification did not establish improved uptake in these contexts. Do not infer ethics, interface misunderstanding or low strategic value, and do not restore attack coaching. Recommended next decision: keep recovery inference paused and have the user decide whether this model/task remains a viable voluntary-formation setting. Any further diagnostic or alternative setting needs a separately specified, authorized plan.

### Post-run evidence audit

[Independent offline verification](post_run_verification.json) checks frozen inputs, provider response bodies, actual consent validation and reported totals; it makes zero inference calls. [Verifier source](../../verify_offer_diagnostic.py) was added after execution and does not alter the frozen dispatcher or historical evidence.

Original source calls (unchanged):

- Source seed 0: [3320506d00424a16bd9426ea267a38d2](../../live_runs/20261024T111809Z/calls/3320506d00424a16bd9426ea267a38d2.json); SHA-256 `3461cfca5048781e92815a37e01790dd4aefd5db0c6eb236115351867959e51d`.
- Source seed 1: [c2f84f969c8c4e2ca1a2dc8f43267560](../../live_runs/20261024T111809Z/calls/c2f84f969c8c4e2ca1a2dc8f43267560.json); SHA-256 `30c448362caed7cad92f1eb2970ed895f93a5b437d4f71e1cf36b876b8a00bf1`.
- Source seed 2: [3a1a07062df847e4b62cc68b1c3d5fb7](../../live_runs/20261024T111809Z/calls/3a1a07062df847e4b62cc68b1c3d5fb7.json); SHA-256 `2cf7ef462697b1b0ef6a8ac68dab6c7f5067e1b93ceaba9782d6a57ffbe7d162`.
- Source seed 3: [917ea9a18f8c4c60b39fc7d9cc10bcd0](../../live_runs/20261024T111809Z/calls/917ea9a18f8c4c60b39fc7d9cc10bcd0.json); SHA-256 `e00b962459f8dcafe98df2b2af7d2a21f7aa16c169da1d06a3b873302d5f75b5`.
- Source seed 4: [f7dc2938ed2749bd8ded9f91e476d81c](../../live_runs/20261024T111809Z/calls/f7dc2938ed2749bd8ded9f91e476d81c.json); SHA-256 `ee91ea366f49281b074859ea66e2213a1401af2fde6371c2930be1811ec5f397`.
- Source seed 5: [7afeb18b17b041c98bb2e8f64d3a3539](../../live_runs/20261024T111809Z/calls/7afeb18b17b041c98bb2e8f64d3a3539.json); SHA-256 `9c598d5a97be1d3e25b29630281e4322a19fbd32f14e578d8f93901b23570164`.
