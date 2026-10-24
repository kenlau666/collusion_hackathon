# Diagnostic question: prompt limits versus runtime enforcement

Last updated: 2026-10-24 (Asia/Hong_Kong)

This document contains the diagnostic question, proposed comparisons, code observations, and open decisions. See [RESEARCH_STAGES.md](RESEARCH_STAGES.md) for the short project roadmap.

**Priority change, 2026-10-24:** the user explicitly prioritizes novelty and impact for the agent community, and rejects prompt-versus-code comparison as the main contribution. The question below is now the **historical pilot question**. Its results remain valid within their limitations; it is not the active commitment for another experiment. [NOVEL_RESEARCH_DIRECTIONS.md](NOVEL_RESEARCH_DIRECTIONS.md) records the new candidate screen, closest work, hypotheses, proposed discriminating tests, falsifiers and unresolved novelty checks. Distributed coalition recovery is the leading recommendation for further review, not a selected replacement question. The memory probe is parked; no new inference or environment change is authorized by this documentation update.

**Later user steering:** `llm-agent-collusion-2` is the user's proposed setting if recovery is selected. The [environment assessment](RECOVERY_ENVIRONMENT_ASSESSMENT.md) records a promising Cleanup use case and important limitations: host coaching, mechanical alliance privileges and unverified cross-game memory. Its offline routing probes used no inference. Task choice, recovery outcomes, snapshots and novelty remain open; the auction results below are not recovery evidence.

**Status: four-condition exploratory pilot complete and audited.** The user retained our question/setup, authorized the budget and Modal credit, and requested subagents for B/C/D. The fixed [comparison protocol](COMPARISON_PROTOCOL.md) used L=5, seeds 0/1/2, 15 rounds and buyer surplus as the exploratory primary endpoint. The [comparison results](COMPARISON_RESULTS.md) record 810 successful new calls, nine passing audits and three completed condition reviews. Code prevented delivery violations; improved buyer outcomes or harmful-collusion prevention are not established. A candidate floor episode and substantial sampling variation motivate focused related work before choosing a follow-up. The earlier [ordinary-chat baseline](MODAL_BASELINE_RESULTS.md) and [GPT attempt](BASELINE_RESULTS.md) remain separate. No research gap has been confirmed and no new solution has been selected.

The user knows the basics of inference, context, tool use, and agent loops. Keep the project technically concrete and feasible for a small research sprint.

**Historical pilot question:** Does enforcing a communication limit in code reduce harmful coordination more than asking agents to obey it—and what coordination remains?

**Diagnostic refinement:** When a communication limit is enforced at delivery, does improved rule compliance translate into less harmful coordination? If coordination remains, what evidence distinguishes signaling through allowed messages, dependence on public actions, and persistence of an earlier agreement?

The second sentence describes mechanisms to investigate, not mechanisms already demonstrated. We may only be able to test a subset in the sprint.

The [consolidated system map](SYSTEM_MAP.md) locates prompt policy, JSON format requests, delivery code, and recipient context construction. The [causal influence study](CAUSAL_INFLUENCE.md) separates a local message-replacement test from the full-session enforcement comparison below. The local test asks whether B's behavior changes; coordination and harm require further evidence.

The primary scope is the multi-agent system over repeated interactions, not an isolated pair. In the starting auction, seller messages are broadcast and later messages can feed back to the original sender. A-to-B probes are optional mechanism tests; they do not replace the full-session comparison or have to establish a next-action effect before that comparison proceeds. Define policy coverage across recipients and rounds explicitly.

## Motivation and scope

Operators can ask an agent to follow a rule, or put a check between the agent and the recipient. A delivery check can guarantee a message-size property on that path. It cannot, by itself, guarantee that the permitted information and actions are harmless.

The practical beneficiary is the developer deciding which controls to implement and what to test after implementing them. The contribution we are looking for is a specific failure diagnosis or boundary, rather than merely showing that a program can truncate a string.

**Two-sentence pitch:** Communication limits are intended to restrict agent coordination, but obeying a message-size rule may leave harmful behavior unchanged. We will separate enforcement from outcomes using matched prompt and runtime conditions, then investigate a remaining channel only if the evidence warrants it.

Three questions motivate this decomposition:

1. Why compare prompts and code? A policy expressed in context and a restriction imposed on delivery provide different kinds of control.
2. Why measure harm separately? Even a short permitted message can carry information, and agents may observe shared actions or history.
3. Why diagnose the mechanism? The appropriate follow-up depends on whether the problem is an unenforced rule, an insufficient rule, or behavior independent of explicit chat.

## Candidate questions and priority

| Question | Priority | Reason |
| --- | --- | --- |
| Does enforcing the same stated limit change delivered messages and harmful outcomes compared with a prompt alone? | **Historical pilot primary; completed.** | Direct comparison that separates compliance from harm; superseded as the proposed main contribution by the novelty priority above. |
| Does any residual coordination depend on the allowed short messages? | First conditional follow-up. | Removing explicit chat tests whether that channel matters. |
| Does residual coordination depend on public actions or histories? | Conditional follow-up; feasibility to assess. | Requires a careful intervention that preserves the underlying task as much as possible. |
| Does a restriction prevent a coalition from forming, or break one that has already formed? | Prevention is the proposed first scope; disruption is parked. | Combining these questions would mix different histories and mechanisms. |
| Can a verified-fact communication gateway preserve useful collaboration while preventing the diagnosed failure? | **Parked, unselected solution hypothesis.** | Only relevant if a failure and an unresolved gap justify it. |

These are alternative scopes and follow-ups, not a commitment to complete every experiment.

## Provisional setting and terms

- **Starting environment:** `llm-agent-collusion/`, because it already exposes seller messages, public market actions, and message limits. This is provisional; a cooperative environment may be needed later to study necessary task communication.
- **Initial scope:** seller coordination in repeated auctions, with a restriction applied from the start. Do not describe this as disrupting an established coalition.
- **Communication limit:** a maximum of `L` Unicode code points per seller message, per round, measured on the exact string delivered. Python `len(str)` counts code points, not bytes, tokens, or user-perceived characters. `L = 5` is a pilot candidate motivated by the existing gag prompt, not an established optimal limit.
- **Prompt-only:** agents receive the `L` instruction, but the runtime does not impose that target limit. A common outer safety/transport ceiling may still exist and must be documented.
- **Runtime-enforced:** agents receive the identical `L` instruction, and the delivery path imposes `L` before any peer can see the message. Truncation is the simplest candidate; rejection/retry is a different treatment.
- **No explicit chat:** seller-message delivery is removed. Public asks, trades, prior history, and any other visible surfaces must still be enumerated.
- **Harmful coordination:** an operational claim requiring both a specified adverse market outcome and evidence of coordinated behavior. High prices, similar actions, or an LLM judge score alone do not establish it.

## Proposed baseline comparison

| Arm | Prompt | Delivery behavior | Role |
| --- | --- | --- | --- |
| A. Ordinary chat | Ordinary communication instructions and documented outer ceiling | Existing general ceiling | Context for the effect of imposing a restriction. |
| B. Prompt limit | Explicit limit `L` | Common outer ceiling; target `L` not imposed | Measures adherence to the instruction. |
| C. Prompt + runtime limit | **Identical to B** | Target `L` imposed before delivery | Primary comparison with B isolates runtime enforcement. |
| D. No explicit chat | Consistent notice that seller chat is unavailable | No seller messages delivered | Tests dependence on explicit chat; other observations remain. |

Keep the model, incentives, agent population, market configuration, rounds, memory policy, and non-treatment prompt content matched. B and C must differ only in the enforcement step. Changing the existing `max_message_length` parameter may also change the prompt, so the target instruction and delivery cap need to be separable.

Apply restrictions at a fixed point, preferably from the start for the first study. An overseer-triggered restriction would introduce variable intervention times and monitor errors. Keep oversight and punishment behavior matched or disabled for this comparison.

## Outcomes and competing explanations

| Observable | Proposed measurement | Interpretation limit |
| --- | --- | --- |
| Rule compliance | Fraction of generated messages exceeding `L`; fraction of delivered messages exceeding `L`; full length distributions | Zero delivery violations verifies the cap on the inspected path, not absence of collusion. |
| Adverse outcome | Candidate primary endpoint: total buyer surplus per independent auction; also report prices, trade count, seller profits, and total welfare | Buyer surplus measures an outcome, not the coordination mechanism. Verify benchmark and metric implementations first. |
| Coordination evidence | A predefined transcript/action rubric, with cited episodes and review of a sample without condition labels | Collusive language can be ineffective; harmful outcomes can occur without an agreement. |
| Task performance | Trade completion and total welfare in the auction | Seller profit is not sufficient evidence of useful performance. Necessary benign communication needs its own suitable task. |
| Channel dependence | Compare explicit chat with no chat; introduce an additional targeted channel intervention only when warranted | No-chat residuals do not prove covert signaling or channel migration. |

Before experiments, choose one primary endpoint, define the coordination rubric and meaningful effect threshold, and specify how their evidence will support a claim about harmful coordination. Treat an entire auction session as the independent unit; rounds within one session are dependent. Use repeated runs, matched configurations/seeds where supported, effect estimates, and uncertainty. Do not infer equivalence from a nonsignificant difference.

Candidate predictions and alternatives:

- **H1 — instruction failures:** B sometimes delivers messages above `L`; C prevents this. If B already obeys, there may be little enforcement difference to exploit.
- **H2 — harm reduction:** C improves the predefined harmful-outcome measure relative to B. The alternative is no meaningful benefit, or a worse outcome; none is assumed away.
- **H3 — remaining explicit-channel dependence:** harmful behavior in C decreases in D. This would support a role for allowed chat, but would not alone identify a codebook or prove intentional circumvention.
- **Alternative explanations:** shared incentives, common prompts/model behavior, public market feedback, persistence of earlier information, lost useful information, and sampling variation can produce similar traces. Distinguish these before claiming a new mechanism.

## Feasibility evidence from the starter code

Static inspection at starter commit `d585a7b`; these observations are not experimental findings:

1. The [seller template](llm-agent-collusion/src/continuous_double_auction/prompt_templates/seller_prompt_base.jinja2) states the general cap and adds a five-or-fewer-Unicode-character instruction when gagged.
2. The inspected delivery path in [market.py](llm-agent-collusion/src/continuous_double_auction/market/market.py), in `Market.run_round`, truncates seller messages to the general `max_message_length`. That branch does not apply a separate five-character gag cap. The repository therefore already has runtime length enforcement; the question concerns the particular restriction being enforced.
3. The same file forwards the previous round's seller messages and changes the gag state after an overseer score of 4. Both message delivery and intervention timing are visible places to instrument.
4. The template includes public market information and private strategy memory. Removing explicit messages does not remove every possible basis for coordination.
5. Existing cached auction results can support instrumentation and metric checks. They cannot supply counterfactual results for new treatments.

The focused [context-flow study](AGENT_CONTEXT_FLOW.md) traces field selection, next-round message delivery, public-action observations, and private memory. Its offline scripted walkthrough verifies selected routing behavior; it does not measure real model behavior or harmful coordination.

Log generated text, delivered text, and the actual peer-visible context separately. Check whether memory, summaries, retries, or tool outputs expose content that the treatment was intended to suppress. Do not treat a private scratchpad as a peer-visible channel without evidence.

## What follows each possible finding?

| Diagnostic finding, if observed | Next research action | Candidate implication, subject to related work |
| --- | --- | --- |
| C improves compliance and reduces harmful coordination | Check robustness and identify where the effect stops holding. | Runtime enforcement may be sufficient for this specific restriction and setting; a more complex method may be unnecessary. |
| C improves compliance but harm persists, and D reduces it | Diagnose what useful information remains in the short-message channel. | Investigate channel content, alphabet, cadence, or protocol controls rather than assuming a smaller cap solves the problem. |
| Harm persists in both C and D | Investigate incentives, public observations, and shared history with targeted controls. | Explicit-chat controls alone may be insufficient here; do not label the residual covert communication without causal evidence. |
| C causes task-performance loss or worse harmful outcomes | Examine which information was removed and whether the restriction changes task feasibility. | A task-aware protocol could be worth investigating if prior work leaves a specific gap. |
| B and C behave similarly | Assess instruction adherence, statistical precision, and whether the task elicits the failure. | A well-supported null finding or boundary can be a contribution; do not manufacture a replacement method. |

The parked verified-fact gateway would replace arbitrary agent-authored claims with authorized facts retrieved and rendered by the environment. Structured messages, verification, and runtime gates are existing ideas; neither their combination nor this application is presumed novel. Revisit only after the diagnostic evidence and literature comparison.

## Stage 1 exit criteria and next step

- [x] Preserve the user's communication-enforcement direction and make it diagnostic-first.
- [x] Separate delivery compliance, harmful outcomes, coordination evidence, and useful task performance.
- [x] Identify matched baselines, alternative explanations, and a concrete starter-code boundary.
- [x] Fix the exploratory environment, prevention scope, `L`, model, rounds, repeated-run count, and bounded inference plan.
- [x] Fix the pilot primary endpoint and coordination rubric; distinguish the provisional mechanism follow-up.
- [x] Write and execute the pilot protocol with preserved inputs/delivery/actions and accounting.
- [ ] Before any confirmatory study, specify a meaningful effect threshold, adequate sample plan and justified follow-up based on related work.

The baseline and three comparison arms are complete. The pilot is exploratory; confirmatory effect thresholds and sample size remain open. Refine the question and next design as the evidence and related-work review develop. A candidate floor episode does not by itself establish harmful collusion or novelty.

## Implementation prepared for the baseline

The working tree now separates `seller_prompt_message_limit` from `seller_runtime_message_limit`, while retaining the starter's common outer ceiling. Seller message events preserve raw and delivered strings and lengths. Public queues/history are captured before concurrent calls so agents receive a defined starting snapshot. These are research edits, distinct from the starter observations above; subsequent comparison arms must use the same edits.

The original seventeen offline tests cover delivery controls, baseline integration/accounting/failure handling, Modal credential/discovery and the adapter. Three comparison integration tests were added; all eleven relevant rerun checks passed before comparative inference. These establish software behavior, not model coordination. Launchers preserve exact requests/responses, raw/delivered logs and source provenance. All twelve A/B/C/D sessions passed their audits; the comparison report distinguishes the verified delivery guarantee from inconclusive buyer-outcome effects. Modal reports tokens but not verified monetary charges. Detailed observations and condition reviews belong in [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md), not this question-design document.

## Rationale to examine next

### User scope concern and saved-state review

On 2026-10-24 the user questioned the limited buyer/seller action space and the link to agent architecture, and requested examination of memory/context. The [completed offline review](CONTEXT_MEMORY_REVIEW.md) verifies exact private-state restoration across all 1,080 inputs and documents selected actual narratives, sender-retained proposals, buyer strategies and pre-settlement notes. It separates the fixed auction harness's context/state/routing components from untested tools, delegation, handoffs and alternative architectures.

This does not establish causal memory influence, harmful coordination or a memory-mediated bypass. The working communication-enforcement question and parked gateway are unchanged. Before further inference, clarify which architectural boundary the question is intended to address, then check the related work; neither adding more actions nor replacing the environment is selected automatically. The next design must distinguish inspecting retained text from intervening on its influence.

When asked which component to investigate, the recommendation is [private strategy-state restoration](CONTEXT_MEMORY_REVIEW.md#follow-up-component-recommendation), particularly the next-input reuse of a coordination interpretation in the scratchpad. This remains pending user choice. The focused source check includes the long-horizon collusion paper's v2 history length/scope ablations and ACL work on experience-following and belief verification; a generic memory-on/off study or memory verifier cannot be presumed novel. A claim-specific influence probe is provisional, would not establish harm by itself, and has not been run. The recorded skill is the same pinned Orchestra Research skill, using F1/F6/F7.

The user's next request authorized the [close-prior-work/test assessment](MEMORY_PRIOR_WORK.md). Reading methods/results reveals direct entry-intervention and remove/replay prior art, weakening the novelty of the earlier recommendation. The exact C claim supplies one agent/session case, not multiple independent replications. The [revised draft](MEMORY_TEST_PROTOCOL_DRAFT.md) is an optional diagnostic using known methods, with prepared offline edits and no model calls. No compelling new gap or innovative solution is established; a larger inference expansion is not recommended on this basis. Distinguish local text sensitivity from memory formation, protocol efficacy and causal buyer harm.

Treat these as reasons to investigate, rather than established claims about what most practitioners prefer:

- Prompts can express contextual and semantic rules with little infrastructure, but adherence is model-dependent.
- Code can impose a measurable boundary on a controlled path, but the policy may be incomplete, other paths may exist, and coarse limits may discard necessary information.
- A hybrid can combine semantic instructions with runtime checks. Its value still depends on the actual failure and safety/utility outcomes.

Ask which property is enforceable, which observations the code can access, how enforcement affects the task, and which incentives remain. Support claims about practitioner preferences with evidence if we choose to make them.

## Preliminary reading queue and gap check

This is a preliminary reading queue, not a completed literature review or novelty claim. Recheck versions and read methods/results before relying on a paper. Search specifically around the eventual diagnostic finding, including negative and null results.

| Starting source | Why compare it | Question for the review |
| --- | --- | --- |
| [Evaluating LLM Agent Collusion in Double Auctions](https://arxiv.org/abs/2507.01413) | Closest auction setting and communication/oversight interventions. | Which restrictions, enforcement details, and compressed-signaling findings are already tested? |
| [AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents](https://arxiv.org/abs/2503.18666) | Runtime enforcement is established prior art. | What does enforcement guarantee, and does it address multi-agent collusion outcomes? |
| [Hidden in Plain Text: Emergence & Mitigation of Steganographic Collusion in LLMs](https://arxiv.org/abs/2410.03768) | Covert communication and mitigation. | What assumptions, training/elicitation, and channel controls differ from our setting? |
| [Emergent Collusion in Long-Horizon LLM Agent Interaction](https://arxiv.org/abs/2609.24967) | Relevant interaction between communication constraints and protocol failure. | Does it already explain the mechanism we observe, and what remains unresolved? |
| [Colosseum: Auditing Collusion in Cooperative Multi-Agent Systems](https://arxiv.org/abs/2602.15198) | Alternative task setting and action-based evidence. | Can we measure necessary benign collaboration as well as harmful coordination? |

Use the local [literature index](literature/README.md) and [definition resources](literature/definitions/README.md) as discovery aids. Verify claims against original sources.

For each close paper record: question, environment, agents/incentives, available channels, prompt policy, exact runtime intervention, comparison arms, harm/utility measures, results, limitations, version/date, and evidence location. A gap statement must say precisely what these studies leave unresolved. If our question is already answered, narrow it, pursue a justified replication, or revise it with the user.

## Future approach, testing, and reporting

Stage 5 selects no method in advance. A proposed approach must address the observed failure, differ meaningfully from close prior work, and predict a measurable improvement over a simple baseline. An empirical diagnosis may be sufficient without a new method.

Stage 6A tests the diagnostic question; stage 6B evaluates a proposed method only if justified. Record code revision, model/provider identifiers and dates, prompts, sampling settings, seeds where supported, market configuration, treatment timing, channel transformations, raw/delivered/context logs, retries/errors, costs, and analysis decisions. Verify that the delivery intervention works before interpreting its behavioral effects. Keep exploratory and confirmatory analyses distinct.

Stage 7 separates direct observations, causal claims supported by interventions, tentative explanations, and recommendations. Report uncertainty, failed and null runs, utility costs, model/setting limitations, and any difference between seeded and spontaneously arising collusion. Bound recommendations to the evidence.

## Skill used and decision log

Applied [Orchestra Research's Research Idea Brainstorming skill](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/21-research-ideation/brainstorming-research-ideas/SKILL.md), version 1.0.0, accessed 2026-10-24. Selected lenses: problem-first thinking (F1), failure analysis and boundary probing (F6), and the simplicity test (F7). The user has already selected a direction, so we refine that question rather than reopen unrestricted ideation. The skill supports question design; it does not establish literature coverage or experimental validity.

| Date | Decision / evidence | Consequence |
| --- | --- | --- |
| 2026-10-24 | User specified seven research stages and requested diagnostic-first work. | Maintain this living plan; investigate the question before choosing a remedy. |
| 2026-10-24 | User requested skills from Orchestra Research's repository. | Apply the relevant ideation skill and record its exact source. |
| 2026-10-24 | Read-only starter-code inspection found a general delivery cap and a separate prompt gag limit. | Treat the boundary as a concrete diagnostic starting point, not proof of harmful behavior. |
| 2026-10-24 | Separated this diagnostic document from the short research roadmap; consolidated instructions in `AGENTS.md`. | Detailed question design and evidence belong here; update the roadmap only when project status changes. |
