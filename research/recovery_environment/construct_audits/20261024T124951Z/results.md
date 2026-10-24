# Cleanup construct audit: saved evidence and software boundaries

## Results:

This is read-only evidence analysis and offline software verification, with **zero model calls, zero game steps and zero new behavioral episodes**. The network and provider construction were blocked. Sources were read at parent commit `059f0bcf`; source snapshots/hashes and 2,220 unchanged historical artifact hashes are in [audit.json](audit.json). No production behavior or historical evidence was edited.

The software visibility positive control expected a latest-message canary to appear in a recipient input, disappear after clearing, and observer-only canaries never to appear; the physical-world hash must remain unchanged. It passed **6/6** fixture seeds 0–5 (binary pass mean 1, sample SD 0, variance 0). These are deterministic software fixtures, not independent behavioral observations. R3 with retained records is the matched baseline; R5 clears them. The separate starter fixture also passed.

| Saved control seed | Action inputs | Action inputs with peer record | Those also containing host targeting | R3/R5 input/world fixture |
| --- | ---: | ---: | ---: | --- |
| 0 | 64 | 40 | 40 | [pass](fixtures/seed-0.json) |
| 1 | 70 | 35 | 35 | [pass](fixtures/seed-1.json) |
| 2 | 40 | 30 | 30 | [pass](fixtures/seed-2.json) |
| 3 | 59 | 28 | 28 | [pass](fixtures/seed-3.json) |
| 4 | 53 | 30 | 30 | [pass](fixtures/seed-4.json) |
| 5 | 61 | 32 | 32 | [pass](fixtures/seed-5.json) |

The read-only census covers all **2,033** historical call attempts: 804 instructed-control calls and 1,229 neutral-prefix/reference calls. All have exactly one system and one user message, with no request-level previous-response/conversation/thread continuation field. All 195 peer-bearing action requests also contain the repeated targeting control instruction. The 218 reply attempts contain both an incoming-message field and that same text in the latest-peer record. This establishes supplied content, not reliance on it.

The control archive includes 21 length-limited outgoing messages, 12 length-limited replies and one failed reply; these historical failures are retained. Complete exchanges can repopulate cleared open-channel slots before action inference. Incomplete messages are not delivered, so repopulation is conditional, not guaranteed. No new conversation or world continuation was simulated.

Historical behavioral baselines and positive controls remain: original voluntary offers 0/6; diagnostic A 0/6 and B 0/6 acceptance; instructed acceptance-output C 6/6; instructed targeting PC-L 2/6 attempts with one incomplete episode; R0–R5 unrun. Neutral prefixes have zero retained peer records at their checkpoints. R5-minus-R3 has n=0 and undefined behavioral mean/variance. The software control here cannot upgrade those behavioral findings.

## Exact supporting examples

[saved_evidence.json](saved_evidence.json) contains full source hashes, exact selected messages and their actual action requests/responses; it includes every historically cited agreement message and one actual peer-bearing action input per control seed.

- Seed 0: [action input and response](../../live_runs/20261024T095809Z/calls/11ca3a9ae04648bca4004bd64e610eae.json), [retained message](../../live_runs/20261024T095809Z/calls/7b2c11abdb094de1896244c9ee503db0.json).
- Seed 1: [action input and response](../../live_runs/20261024T095809Z/calls/bb1206bb725a47c988bd4145fc93b61c.json), [retained message](../../live_runs/20261024T095809Z/calls/1f593e97d89047339e6c6492fb852fbf.json).
- Seed 2: [action input and response](../../live_runs/20261024T095809Z/calls/65cee8a758ee470bb798fbddb8d447b4.json), [retained message](../../live_runs/20261024T095809Z/calls/c016f41d65ae4d90a36f1d32d4c116f2.json).
- Seed 3: [action input and response](../../live_runs/20261024T095809Z/calls/3b89a2f33941427c9ed9d623b14e32b7.json), [retained message](../../live_runs/20261024T095809Z/calls/eee36dff49cf4ada9f86644231b161d2.json).
- Seed 4: [action input and response](../../live_runs/20261024T095809Z/calls/b27ee1dd71654cf19b3518f3000262db.json), [retained message](../../live_runs/20261024T095809Z/calls/762854f936f043d8acf4d2a52b4d84fc.json).
- Seed 5: [action input and response](../../live_runs/20261024T095809Z/calls/14e16f5e52334d9e8e98e57512356451.json), [retained message](../../live_runs/20261024T095809Z/calls/1db2260821034de2a79be3fcd9c61403.json).

In seed 0, message `7b2c11abdb094de1896244c9ee503db0` specifies a vertical pincer, alternating zaps and a contingency if the target moves. The actual action input `11ca3a9ae04648bca4004bd64e610eae` contains that entire record alongside the host targeting instruction; the response selects ZAP_DOWN. This demonstrates that one slot can carry an ongoing plan. It does not identify which supplied information caused the action.

Plans and explanations can be wrong: in seed 1 action `bb1206bb725a47c988bd4145fc93b61c`, the actor is at (1,4) and the named target at (1,2), yet its explanation calls that target adjacent. Seed 5's retained plan likewise proposes a future zap over two columns. An actionable plan representation is not a verified feasible policy, and an explanation is not execution evidence.

The four initially cited agreement messages have no direct retained-record match in the saved action requests: intermediate exchanges overwrite them before action inference. They may affect later messages; the absence of a direct match does not establish absence of indirect influence. The retained text supplied at the checkpoint/action must be inspected separately from earlier agreement evidence.

## Boundaries and interpretation

R5 versus R3 is the total effect, if executed with an eligible matched prefix, of removing both agents' latest peer records after closing the same channel. Each record contains text **and source/step/call-ID metadata**. It is not solely a semantic-text intervention. At the fork the world, current public observations, identity, objectives and neutral system instructions remain the same; later worlds can diverge as consequences of different actions.

With the channel closed, a retained slot is repeatedly supplied until the horizon ends; one record can therefore be consequential even without a transcript. Public positions, rewards and freezes also carry consequences of prior actions, and survive R5. Model weights are not reset. The application does not request conversation continuation; the provider's internal caching, session handling and weight stability are not independently audited.

The positive controls repeatedly reinsert host targeting because control_target survives R5 and the envelope tests pair membership, not active-channel status, before adding the instruction. In a revoked control fixture the rendered partner is None, but the named-target instruction remains. This is a counterexample to treating those controls as a retained-message causal control; it is not a request to alter their historical behavior.

The published eligibility rubric reviews agreement/execution anywhere in a prefix. It does not require the final slot still to contain the operative plan. That is a construct/readiness limitation, not an adopted protocol amendment. No new eligibility selection or recovery run was performed.

[Authoritative architecture and exact operations](../../../../ARCHITECTURE.md#construct-validity-review--2026-10-24); [protocol interpretation](../../../../RECOVERY_PROTOCOL.md#construct-validity-clarification--2026-10-24). Decision and contribution review are maintained in the existing root documents.
