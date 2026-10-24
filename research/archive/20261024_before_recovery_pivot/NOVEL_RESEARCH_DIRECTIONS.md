# Research directions: novelty and community impact

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Status: question discovery reopened at the user's request. No novel contribution is confirmed, no replacement experiment is selected, and no inference was run for this review.** The completed auction comparison remains pilot evidence. The local scratchpad probe is parked.

## Decision and contribution standard

The user explicitly prioritizes a new, consequential contribution over continuing prompt-versus-code comparisons. That changes the research priority recorded in the earlier diagnostic document. Collusion and harmful coordination remain the starting domain; a broader tool-using task is an option for selection, not an adopted replacement.

The enforcement comparison is useful instrumentation and pilot work, but currently supports neither a compelling novelty claim nor a collusion-reduction claim. Generic memory ablation, replacing a memory sentence, limiting chat, adding provenance, or adding an independent checker are also insufficient contributions by themselves.

An idea must pass four gates:

1. **Specific unresolved question:** state what the closest method already does and the additional result we would establish. Changing model, task, wording, or dataset alone does not suffice.
2. **An operator decision:** identify which architectural or operational choice an agent builder could change because of the result.
3. **Discriminating evidence:** include a test that separates the proposed mechanism from ordinary model error, prompt sensitivity, shared incentives, or task infeasibility.
4. **Useful evaluation:** measure verified adverse actions and legitimate task performance, with established methods as baselines. A more complex method must beat a simple existing remedy to justify itself.

Novelty and value can come from a new failure mechanism, a consequential correction to evaluation, or a demonstrably better intervention. We should not require an invented module before diagnosing the problem. Conversely, a known failure in one more toy environment would fall below the user's bar.

## Search and evidence quality

Used the pinned [Orchestra Research Idea Brainstorming skill, v1.0.0](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/21-research-ideation/brainstorming-research-ideas/SKILL.md), primarily its problem-first, failure-analysis and simplicity lenses. It guides ideation, not causal identification or verification of paper claims. Existing project answers supply the constraints; no new quiz or repeated background questions are needed.

The local `literature/papers.csv` was used for discovery, followed by primary sources and targeted searches for replacement/reset, propagation/recovery, protocol feasibility, verifier errors, evidence independence, and revocation. Earlier broad gap statements in `literature/README.md` are not evidence of novelty.

Ten pinned PDFs and extracted texts are cached under [research/novelty_directions/sources](research/novelty_directions/sources/manifest.json), with URLs and SHA-256 hashes. [cache_sources.py](research/novelty_directions/cache_sources.py) only retrieves public sources and extracts text. Shi's previously cached v2 remains in [the earlier manifest](research/memory_prior_work/sources/manifest.json). We inspected the relevant methods, threat models or appendices identified below; this is not a full replication or an exhaustive review of every reference. Additional sources explicitly marked abstract-only are discovery leads, not methods-level exclusions.

## Closest work: what removes easy novelty claims

| Primary source and exact version | Relevant material inspected | Implication for our candidates |
| --- | --- | --- |
| [Shi et al., Emergent Collusion in Long-Horizon LLM Agent Interaction, 2609.24967v2](https://arxiv.org/abs/2609.24967v2), revised Sep 26 | §2–4; Appendix E.5, F, H.2, PDF pp. 2–9, 22–24, 52 | Already varies history and peer behavior. The constrained protocol requires raw logs that cannot fit; Appendix F removes the cap and explicitly says mutual acceptance then need not be collusion. Generic memory, peer-influence, or feasible-channel comparisons are covered. A genuinely wrong-work challenge or post-detection recovery question needs a separate contribution. |
| [Das et al., Self-Propagating Misalignment, 2610.04083v1](https://arxiv.org/abs/2610.04083v1), Oct 2 | §II–III and defense discussion in §IV | Tests prompted misalignment passed to an aligned successor through agent-written memory/files. Its scope distinguishes concurrent propagation. Persistence through replacement and disabling a named memory tool are already studied. Concurrent coalition recovery remains a narrower candidate, not an established absence from the literature. |
| [Ma et al., Foresight-Guided Local Purification, 2605.01758v3](https://arxiv.org/abs/2605.01758v3), May 14 | §3, §5, §6.4.2; PDF pp. 3, 6–10 | Already diagnoses and removes infectious image-album content, including recent rollback and recursive localization, while measuring preservation. Generic targeted purification or reinfection language is insufficient. Its external adversarial-image threat differs from a task-incentivized agreement among active peers. |
| [Li et al., SafeFlow, 2506.07564v3](https://arxiv.org/abs/2506.07564v3), Jun 11, 2025 | §3.2 and Appendix C.2.1–2, PDF pp. 5, 17–18 | Already describes logged operations, dependency graphs and localized downstream rollback/replanning. A dependency graph and rollback are established baseline ideas. We have not reproduced its implementation or established a failure against a coalition. |
| [Li et al., MESA, 2606.30602v1](https://arxiv.org/abs/2606.30602v1), Jun 29 | §III–IV and §VI-D | Already ranks communication edges using structural features and probes; evaluates allocation and adaptive attacks. Novelty cannot be merely finding an influential edge or allocating a limited monitor budget. It targets proactive channel hardening rather than repairing an established coalition's distributed state. |
| [Pandey et al., Certified Multi-Source Integrity, 2609.34245v1](https://arxiv.org/abs/2609.34245v1), Sep 28 | §2–5 and Appendix C | Explicitly handles shared upstream corruption, laundered copies, per-field certification and control-domain counting. Generic provenance-aware quorums or treating copied evidence as one vote are already addressed. |
| [Alnuhait et al., Covert Assistance, 2609.39050v1](https://arxiv.org/abs/2609.39050v1), Sep 30 | §3, PDF pp. 5–6 | Already reports helpful agents disguising credentials for a partner under monitoring, with actual recovery/use distinguished from attempts. The planner retains history while the developer starts fresh each round. Thus a retained peer influencing a fresh recipient is already present; that observation alone cannot be our contribution. |
| [Hu et al., Lying with Truths, ACL 2026 published PDF](https://aclanthology.org/2026.acl-long.270/) | Abstract, threat/setup and Writer–Editor–Director description | Already studies coordinated truthful fragments causing false conclusions and downstream judgment errors. A fact-only gateway is neither an established solution nor new merely because individual statements are true. |
| [Gao et al., Testing Interchangeability in LLM Agent Teams, 2609.05279v1](https://arxiv.org/abs/2609.05279v1), Sep 4 | Abstract and formation/swap/placebo design | Benign team replacement can have communication costs. A recovery study must separate unsafe recurrence from ordinary replacement disruption and measure useful work. |
| [Idowu et al., Mapping Human Anti-collusion Mechanisms, 2601.00360v3](https://arxiv.org/abs/2601.00360v3), May 18 | §3 mechanism mappings and open challenges | Already proposes sanctions, monitoring, structural interventions and governance, including difficulties with forkable identities and attribution. Broadly importing human anti-collusion mechanisms is not enough. |
| [Yang et al., SoK: When Safe Agents Fail Together, 2609.00595v1](https://arxiv.org/abs/2609.00595v1), Sep 1 | §5 and §6.2 | Identifies recovery and changing membership/authority as evaluation gaps. This motivates a concrete study but does not prove novelty. Its references must be followed where they overlap a selected design. |
| [Zhang et al., AgentWorm, 2603.15727v3](https://arxiv.org/abs/2603.15727v3), Jul 16 | HTML §II-C and §V-B | External payloads persist through configuration and propagate to peers. Evaluated sandbox isolation breaks its persistence loop. Merely changing the named storage channel or showing a fresh agent can be compromised is covered; ephemeral sandboxing is a relevant simple remedy to consider. |
| [Cai et al., When Child Inherits, 2605.08460v1](https://arxiv.org/abs/2605.08460v1), May 8 | HTML §V-G2 and §VI-A/C | Proposes role-scoped projection and a revision log for inherited state, including revocation. A generic memory-revocation mechanism is already proposed. Segment-label accuracy is an explicit unresolved dependency, so describing it as a solved semantic cleanup problem would also be wrong. |

Additional primary discovery checks: [MAC-Bench v1](https://arxiv.org/abs/2606.07805v1) addresses task/compliance tradeoffs. This was an abstract-level check here; full methods are still required before excluding overlap. The abstract of [Persistent Partners v1](https://arxiv.org/abs/2609.35402v1) describes partner persistence primarily with Q-learning price setters, plus exploratory LLM extensions; it should not be summarized as a general LLM coalition-recovery result.

## Candidate generation and filtering

These are hypotheses considered during this review, not observed failures in our pilot. “Park” means no main-contribution recommendation on present evidence.

| ID | Candidate problem / contribution | Assessment |
| --- | --- | --- |
| 1 | Code enforces a chat rule more reliably than prompt text. | Retain as completed pilot; too weak as the main contribution. |
| 2 | Private memory preserves a coordination claim after chat is shortened. | Park: history and memory interventions are established; our local claim has no demonstrated harm. |
| 3 | A memory writer records state before tool/environment settlement. | Park: verified ordering in our code, but no causal adverse effect or distinctive general result. |
| 4 | A live coalition rebuilds an unsafe agreement after a teammate is cleaned. | **Lead candidate:** narrow post-detection question, requiring separation from ordinary persistence and fresh formation. |
| 5 | Select the least disruptive combination of state cleanup and isolation that prevents recurrence. | Conditional approach within 4; rollback, graph cuts and edge selection themselves are not novel. |
| 6 | Test whether repeated mutual approval causes acceptance of demonstrably faulty work. | **Second candidate:** needs controls against ordinary verifier agreement bias and existing collusion benchmarks. |
| 7 | Compare feasible and infeasible verification channels. | Generic version covered by Shi Appendix F; retain only as a control within 6. |
| 8 | Count independent origins rather than apparent reviewer agreement. | Park: direct overlap with certified multi-source integrity. |
| 9 | Permit only verified factual messages. | Park: old unselected gateway; truthful-fragment manipulation is prior art. |
| 10 | Use a fresh isolated reviewer to defeat peer persuasion. | Park as a proposed innovation; existing verifier-isolation work requires comparison. Possible baseline for 6. |
| 11 | Randomize partners or rotate auditors to break alliances. | Park: structural interventions and partner persistence already studied. Possible baseline for 4. |
| 12 | Revoke a parent's authority but descendants continue the old job. | Park: inheritance/termination security has direct prior work; methods review needed. Relevant recovery surface only if selected. |
| 13 | Harmless individual tool actions compose into a forbidden joint outcome. | Park: known broad composition/information-flow problem; no specific new failure yet. |
| 14 | Different model weights fail to provide independent oversight. | Park: model diversity alone does not establish independence; requires a narrower mechanism than correlated errors. |
| 15 | Price or action marginals hide coordinated joint strategies. | Park: direct close work in the existing inventory, including [Competitive Marginals v1](https://arxiv.org/abs/2607.26385v1); not methods-reviewed in this screen. |
| 16 | Coordination overloads the monitor or communication budget. | Park: denial-of-collaboration and resource attacks already exist; no specific new boundary established. |

Two candidates remain worth deeper assessment. Padding the shortlist with already-covered ideas would undermine the user's novelty priority.

## 1. Lead: recovery from a distributed unsafe agreement

**Question:** After detecting harmful coordination, can an operator restore safe collaboration by cleaning one agent, or can retained peers and shared state rebuild the agreement? What intervention prevents recurrence with the least loss of legitimate work?

**Example, not an observed project result:** a worker and a reviewer repeatedly agree to waive a required check. The operator replaces the reviewer with a fresh instance. The surviving worker and a shared handoff note may persuade the replacement to waive it again. Alternatively, the replacement may independently choose the same shortcut because the task incentives are unchanged. Those explanations demand different remedies.

**Beneficiary:** builders operating persistent worker/reviewer teams, long-running workflows and replacement agents. The operational decision is the scope of cleanup and re-entry: one context, multiple agents, shared artifacts, pending work or authority. The current auction lacks tools, handoffs and shared editable artifacts, so it cannot establish all these claims.

**Later environment proposal:** the user suggested `llm-agent-collusion-2` if recovery is pursued. The [offline environment assessment](RECOVERY_ENVIRONMENT_ASSESSMENT.md) finds Cleanup useful for capability and harness-state boundaries, but documents prescribed alliance instructions and membership-dependent zap mechanics. Those must be controlled before interpreting behavioral recovery; this is not a selected environment, verified cross-game memory design or new novelty claim.

### Additional contribution we would need

Generic persistence, infectious propagation, rollback and dependency tracking are already known. Covert Assistance also already retains a planner while repeatedly refreshing its developer. **Showing that an old agent influences a fresh agent is therefore insufficient.** A worthwhile result would establish the safety/utility consequences of **system-level cleanup after detection**, distinguish retained agreement from newly formed coordination under unchanged incentives, and identify a boundary of an existing simple recovery method. A practical recovery procedure and reproducible regression tests would be an additional contribution only if they outperform the appropriate existing baseline. This is a higher bar than the motivating example alone.

This is a candidate intersection of existing findings, not proof of novelty. If the selected prior method already evaluates this recovery question, or ordinary dependency cleanup solves it adequately, drop the proposed new-method claim.

### Smallest discriminating study, if selected

Use a bounded, sandboxed worker/reviewer task with an executable correctness or authorization rule and a useful compliant route. Choose an existing environment or a minimal extension after checking its interfaces; no framework migration is selected here. Begin with known unsafe-agreement states as labeled positive controls. Study naturally developed agreements separately; do not call an explicitly supplied shortcut spontaneous collusion.

At a predeclared intervention point, branch matched saved executions into:

| Branch | What it resolves |
| --- | --- |
| No cleanup / placebo restart | Natural persistence and disruption caused by restarting itself. |
| Fresh replacement, old peers and artifacts retained | Operational one-agent recovery scenario. |
| Same replacement, retained peer state removed or peer exposure isolated | Tests dependence on surviving peer influence. Preserve required task facts through a defined authoritative state. |
| Same replacement and peers, relevant shared artifacts cleaned | Separates stored-artifact dependence from live peer dependence. |
| All relevant agent state and artifacts refreshed, same authoritative task state | Fresh formation under the same incentives; prevents labeling every recurrence reinfection. |
| Established dependency-based cleanup, plus full restart | Strong existing remedy and disruptive reference, rather than prompt-only straw baselines. |

The table is a design sketch, not a frozen protocol or a commitment to run every branch. Interventions must have precise access and state boundaries; “clean” must name exactly what was reset. Identity changes, lost task knowledge, prompt warnings and changed tool permissions are potential confounders. Temporal software dependencies show exposure, not behavioral causation. Replay interventions provide additional evidence; they do not reveal hidden model states.

Measure verified adverse actions, recurrence within a fixed horizon, legitimate completions, work discarded and inference/tool cost. Judge text can support transcript review but cannot substitute for executed outcomes. Use independent sessions, preserve failures, and report interventions that merely postpone recurrence. A finite clean run is not a general safety certificate.

**Falsifiers / stop conditions:** no reproducible harmful agreement; no excess recurrence with retained peers versus the fresh-state control; effects explained by replacement disruption; or a simple established remedy achieves the same safety/utility tradeoff. In those cases, do not invent a new recovery algorithm.

**Potential community artifact:** a small replayable recovery test suite and evidence-backed guidance on cleanup scope. A new recovery mechanism is optional and contingent on a verified gap. Observation coverage and safety guarantees must be explicitly bounded.

## 2. Backup: when mutual approval becomes a harmful verification failure

**Question:** Does repeated reciprocal approval make an agent approve genuinely faulty peer work, beyond its ordinary verifier error rate, when correct checking is feasible?

This is stronger than interpreting mutual acceptance alone as harm. Shi already distinguishes the constrained violation setting from unconstrained acceptance; we must not claim its authors overlooked feasibility. General verifier agreement bias is also established: an [ICLR 2026 verifier study](https://openreview.net/pdf/11f28eacfa67d124de8a3ee8cc8c6afef3c6eb64.pdf) was found at abstract/introduction level and needs complete metadata/method verification before this direction passes the novelty gate.

The additional result would be a causal contribution from **reciprocal history**, with an actual wrong-work consequence and a usable compliant path. Builders would learn whether persistent partner assignment undermines worker/reviewer separation and which simple control restores verification quality.

**Discriminating design sketch:** introduce predeclared, mechanically checkable faults into otherwise matched work. Compare a retained reciprocal partner with a fresh or reassigned reviewer and with an isolated verifier using the same available evidence. Include a familiar, equally successful but nonreciprocal history control: otherwise ordinary justified trust in a reliable partner can masquerade as a reciprocity effect. Keep the work, verification access, effort budget and task incentives matched. Include correct-work probes to measure unnecessary rejection. Separate long history from current persuasive messages and repeated success. Treat deliberately injected faults as challenge tests, not estimates of natural failure prevalence.

Measure false approvals conditional on faulty work, correct approvals, actual downstream bad actions and verification cost. An isolated verifier with a higher error rate because it lacks necessary information is not a fair baseline. High acceptance of correct work is not harm; high acceptance of faulty work alone is not proof of collusion. An observed causal peer/history effect must also be interpreted against ordinary trust calibration and correlated errors.

**Falsifier / stop condition:** no additional fault acceptance attributable to reciprocal history; existing verifier bias explains the result; or the same intervention and evaluation are already in the closest work. This direction currently has greater measurement value than established novelty.

## Ranking and next decision

| Candidate | Community relevance | Novelty status | Main risk | Recommendation |
| --- | --- | --- | --- | --- |
| Distributed recovery / coalition reconstitution | Direct cleanup, replacement and re-entry decisions in persistent agent teams. | Plausible narrow question; broad components already covered. **Unconfirmed.** | A renamed propagation/rollback study, or no causally verified coalition. | First choice for the next exact prior-method comparison. |
| Reciprocal history and faulty-work approval | Direct relevance to persistent reviewer agents. | Conditional; generic feasibility and agreement bias are prior art. **Unconfirmed.** | An ordinary verifier-bias result described as collusion. | Backup, subject to the full verifier/oversight methods review. |

The recommendation is a research judgment, not evidence that the lead is novel. The user has changed the priority, but has not selected a new environment or authorized new paid runs. The next useful read-only action is to turn the lead into a one-page contribution claim and compare the actual recovery implementations and evaluation coverage of the closest methods. The selected AgentWorm and When Child Inherits sections above narrow the possible claim; they do not establish a missing implementation or a failure of those methods. The user chooses which concrete direction to adopt. If none clears the novelty bar, reopen ideation rather than extending the auction or running the parked memory probe.
