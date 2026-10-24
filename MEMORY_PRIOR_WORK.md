# Close prior work and assessment of the memory proposal

Last updated: 2026-10-24 (Asia/Hong_Kong).

## Decision

**Revise the earlier recommendation: the proposed scratchpad edit is a defensible diagnostic technique, but its methodological novelty is weak and no compelling research gap is established.** Existing work already studies memory/history and collusion, interventions on individual memory entries, and verification of belief-like generated text. A new auction application could still provide useful evidence; applying a known method to a new setting is not automatically an innovative method or an important unresolved problem.

The original communication-enforcement question and completed A/B/C/D pilot remain unchanged. No memory experiment or new defense has been run. A [review-only test draft](MEMORY_TEST_PROTOCOL_DRAFT.md) and exact edited inputs make the proposal concrete without committing to inference.

## Scope, sources, and method

The user requested checking close prior work and the proposed test before execution. Read relevant original methods/results/limitations, checked arXiv submission histories, and compared them with the saved-state audit. This is a focused review, not a systematic coverage claim. Author-reported findings are not independently reproduced here. Searches used combinations of collusion, scratchpad, memory, belief, intervention, and counterfactual, directed to arXiv, ACL Anthology and OpenReview.

[Source manifest](research/memory_prior_work/sources/manifest.json) records URLs, cached PDFs, extracted text and SHA-256 hashes. All eight PDFs were retrieved; an initial Python TLS-certificate failure is preserved separately, and system curl succeeded without disabling certificate verification. The bundled pypdf reader extracted text. Some PDF graphics dictionaries produced parser warnings; the assessment uses readable methods/prose, not inferred plot values. Locations below use one-based PDF pages. Papers' source code and experiments were not independently reproduced.

The previously read [Orchestra Research Idea Brainstorming skill](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/21-research-ideation/brainstorming-research-ideas/SKILL.md), version 1.0.0, informs only the final question assessment through F1/F6/F7. It is not used as literature-review or causal-method authority. No additional skill was invoked for this source comparison.

## Closest work

### 1. Existing auction architecture

[Agrawal et al., Evaluating LLM Agent Collusion in Double Auctions, v1, 2 July 2025](https://arxiv.org/html/2507.01413v1). Read §2.1–3 and §6–7; PDF pp. 2–4, 8. Persistent per-round memory and the mutable strategy scratchpad are inherited from this environment. Comparisons vary seller chat, model and pressure/oversight, with repeated auctions and language/price-based assessments; they do not report the specific claim-edit test proposed here. The authors also report that stronger coordination can coexist with lower seller profits. Memory is prior architecture, and low profits are not an automatic absence-of-coordination criterion. Our audit adds exact saved-input checks, but does not reproduce their model/population/horizon or establish their asserted price benchmark. This source does not settle our local mechanism question.

### 2. Direct collusion/history overlap

[Shi et al., Emergent Collusion in Long-Horizon LLM Agent Interaction, v2, 26 September 2026](https://arxiv.org/html/2609.24967v2#S4.SS2). Read §2–4.2 and Appendix H.2; PDF pp. 2–9, 52. Two agents perform and verify tasks under a constrained log-sharing protocol. History ablations retain all/three/no prior episodes and vary retained phases, including feedback/reflection. Removing past episodes nearly eliminates the measured behavior for their tested ablation models; shorter scope is model-dependent. This is direct prior work against generic memory-on/off novelty. Their joint protocol-violation measure differs from auction harm; the study does not isolate our particular self-authored scratchpad clause. That is a scope difference, not yet a gap proof.

### 3. Noisy experience and memory-quality interventions

[Xiong et al., How Memory Management Impacts LLM Agents, ACL 2026 published version](https://aclanthology.org/2026.acl-long.27.pdf). Read §3–4 and related setup; PDF pp. 3–7. They compare fixed memory, storing all executions, evaluator-selected additions and several deletion rules across a synthetic regression agent and three task agents. Their error-propagation comparison keeps retrieved examples but substitutes ground-truth executions. They report experience-following and performance effects of memory quality. This already goes beyond merely counting or observing memory. It differs from changing a coordination interpretation in a naturally generated auction scratchpad, but rules out presenting memory-quality control as an unexplored architectural idea. Some quality selection relies on oracle/automatic evaluators; stored-experience retrieval differs from our full-note/latest-scratchpad input.

### 4. Belief checking and local repair

[Yuan et al., Verify Before You Commit / SAVER, ACL 2026 published version](https://aclanthology.org/2026.acl-long.1440.pdf). Read §3.1, §3.4–4.4 and limitations; PDF pp. 3–9. The method audits generated reasoning claims, localizes violations and minimally repairs affected steps before commitment. Evaluation uses QA/fact-verification benchmarks and module ablations, not our repeated seller market. General belief verification and targeted repair therefore already have close prior art. Its stated long-horizon motivation is broader than the demonstrated auction mechanism, and its task-grounding does not automatically supply a truth label for an auction coordination interpretation. Additional inference cost is a reported limitation. We cannot call a new scratchpad verifier novel without a closer implementation/evaluation distinction.

### 5. Individual-memory interventions are already a method

[Srivastava, Causal Intervention-Based Memory Selection, v1, 17 May 2026](https://arxiv.org/html/2605.17641v1#S3.SS3). Read §3–6 and §8; PDF pp. 4–10. CMI compares no-memory, candidate-memory and perturbed-memory responses to score entries. Its reported benchmark is a small conversational-QA set with synthetic misleading entries; selection can use annotated memory roles and a deterministic gold-answer scorer. These assumptions limit deployment conclusions, but the entry-level intervention method directly overlaps our proposal. The paper reports stronger selection/robustness, not natural multi-seller coordination or market harm. We can adapt the diagnostic logic without treating a particular asking price as a gold answer or importing memory-role labels. Local editing itself is not our novel method.

### 6. Remove an entry and replay to attribute harm

[Ahad et al., The Misattribution Gap, v1, 12 May 2026](https://arxiv.org/html/2605.22842v1#S8.SS1). Read threat model, §8.1 and Appendix H; PDF pp. 6, 13–14, 24–25. Its CCT removes candidate entries from a shared persistent store and repeats pipeline execution to see whether a reproduced policy violation disappears. The paper reports attribution performance on poisoning scenarios and uses majority votes over a small trial count. This is preprint evidence, not independently validated here. Its attacker-supplied shared documents and policy authority differ from private self-authored auction notes, but remove-and-replay attribution is established overlap. Our auction contains no demonstrated injected document or instruction hierarchy promotion; those claims cannot be borrowed.

### 7. Replay, stochasticity, and continuation

[Shah, Causal Agent Replay, v1, 6 June 2026](https://arxiv.org/html/2606.08275v1). Read §§2–5, 7; PDF pp. 2–5. CAR defines context/action/observation interventions and stochastic continuations, with synthetic ground-truth checks. It discusses provider nondeterminism and why resampling an early step also re-randomizes later decisions. Its mocked-tool validation does not establish auction collusion, and we do not assume its attribution rule transfers automatically. Its relevance is methodological: unchanged fresh replays, distributional estimates and explicit distinction between a local context effect and a full continuation are existing requirements, not novelty claims for us.

### 8. Availability versus listening is an older distinction

[Lowe et al., On the Pitfalls of Measuring Emergent Communication, AAMAS 2019](https://ifaamas.org/Proceedings/aamas2019/pdfs/p693.pdf). Read §3.1–3.3 and §6.1; especially PDF p. 4, Algorithm 1. It distinguishes message/action association from receiver behavior changing under message interventions. Its simple games and accessible policies differ from black-box continuous-price LLM agents. A mean-price contrast can be practical here, but should not be called their CIC estimator or evidence of harmful coordination. The basic move from exposure to counterfactual action testing is prior methodology.

## What the original proposed test would and would not establish

The recommendation was to compare an unchanged saved input with one coordination interpretation removed from its scratchpad. A repeated difference would identify sensitivity to that text under the captured conditions. It would not independently establish:

1. That earlier messages caused the interpretation to be written; public prices, incentives and model priors are competing sources.
2. That the text is factually false. The observed sentence is an unverified interpretation, not an established erroneous belief.
3. That the memory writer/restorer has a unique causal effect beyond supplying an ordinary context paragraph. A local text edit does not compare storage policies.
4. That the effect persists after messages disappear. Current messages remain in the proposed input.
5. That an agreement exists, buyers are harmed, or code enforcement caused either. These require different comparisons.

It can still answer a modest question: **does this retained interpretation affect the next asking-price distribution, conditional on the rest of the supplied input?** That is a case-specific diagnostic using known intervention methods.

## Offline feasibility check and revised proposal

The exact declarative text examined in the earlier recommendation appears in **seven C seller inputs, all Seller Kit, seed 2, rounds 6–12**. These are dependent states from one agent/session, not seven replications. A precise pattern search scanned all 135 C seller inputs; it is not an exhaustive semantic detector and does not imply other coordination-related content is absent.

[Preparation script](research/memory_prior_work/prepare_probe.py) and [inventory](research/memory_prior_work/candidate_inventory.json) preserve the selection rule. [Prepared inputs](research/memory_prior_work/probe_inputs.json) contain earliest/middle/latest states (rounds 6, 9, 12), with four variants: original, targeted deletion, meaning-preserving paraphrase, and removal of a redundant cost reminder. This last variant is a comparison edit, not an assumed inert placebo. All non-scratchpad input and request settings are unchanged; originals match saved bodies exactly. Character lengths differ, and token lengths remain to be measured.

The [test draft](MEMORY_TEST_PROTOCOL_DRAFT.md) suggests ten fresh calls per cell (120 total) only as a limited feasibility option. This count is not power-justified or authorized by writing the draft. No launcher/client or new model calls were added. The current material is insufficient for population claims and would not alone justify a new defense.

## Gap assessment and recommendation

| Proposed claim | Assessment after review |
| --- | --- |
| Memory/history can affect collusion | Direct prior work; not our gap. |
| Editing a memory can change a model's action/output | Existing method; not our gap. |
| Checking/repairing unsupported generated claims before reuse is new | Overlapping prior work; unsupported novelty claim. |
| Naturally retained coordination interpretations matter in this exact capped auction | Empirically unanswered by our data; narrow applicability/case question, not yet a compelling general gap. |
| Memory defeats the five-character runtime guarantee | Unsupported: the inspected delivery guarantee still holds; private state is outside that policy's scope. |

**Recommendation:** do not commit a larger experimental budget or design an innovative defense around this proposal yet. If a small diagnostic case study is valuable in its own right, the revised draft is reviewable. If the goal requires a distinctive research contribution, first articulate a consequential unresolved failure that differs from the existing studies and can be established with action/outcome evidence. The failure may or may not involve private memory; user selection remains necessary for a scope pivot. A negative result would warrant revising the hypothesis, not inventing a replacement success claim.

A positive local edit effect would motivate further causal/market work, not skip directly to a solution. A null or edit-sensitive result would weaken this particular explanation without ruling out all history or communication effects. No new method, new environment, confirmed gap, covert channel, or causal harm finding is established.
