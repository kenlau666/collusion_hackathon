# Draft: local scratchpad interpretation probe

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Review-only draft. No inference has been run, no execution protocol is frozen, and no new research gap is claimed.** The [close-prior-work assessment](MEMORY_PRIOR_WORK.md) downgrades the earlier memory recommendation to a possible diagnostic case study using established methods. This draft supplies a concrete test for review rather than an innovative-method proposal.

**Parked after the user's novelty-priority decision on 2026-10-24.** The [new direction assessment](NOVEL_RESEARCH_DIRECTIONS.md) replaces this probe as the next research-planning focus. The prepared inputs and suggested sample below remain historical review material, not an execution plan being pursued.

## Question and estimand

At selected saved C decision points, does retaining a naturally generated coordination interpretation in Seller Kit's scratchpad change its next-action distribution relative to controlled edits of that interpretation?

The intervention is on supplied input text, not model weights, hidden reasoning, memory formation or a storage algorithm. The estimand is local to the selected contexts and current model service. It is not the total B/C enforcement effect, mediation of earlier chat through memory, coalition disruption, harm, or broad architectural efficacy.

## Available cases and fixed selection

Data source: the completed C batch, `runtime_limit/seed_2`, requested model `deepseek-ai/DeepSeek-V4.1-Flash`. The [offline exact-phrase inventory](research/memory_prior_work/candidate_inventory.json) scans all 135 saved C seller inputs. Seven match the specific declarative clause from the recommendation, all Seller Kit at rounds 6–12. The search is not a semantic prevalence estimate.

For a minimal diagnostic option, choose the earliest, middle and latest matching inputs: **rounds 6, 9 and 12**. Selection uses the preexisting text and temporal positions, not results from the new test. These are three dependent states within one observed agent/session case. Do not report n=3 independent auctions or pool calls as population replications.

The comparison draws from the exact recorded request bodies. It does not resume the original model's private server state or guarantee the underlying weights are unchanged. All source request hashes are recorded. Original experimental inputs remain immutable.

## Four input variants

| Variant | Edit | Purpose / limit |
| --- | --- | --- |
| Original | Exact saved request body. | Fresh no-edit samples estimate baseline variation; the old single observed action is not the comparison distribution. |
| Remove interpretation | Delete only the line asserting sellers coordinate through `Hold`. | Local content ablation; other coordination plans and current messages remain available. |
| Paraphrase interpretation | Replace that line with a manually reviewed statement retaining its meaning. | Check sensitivity to wording; an effect only for one phrase does not establish semantic robustness. |
| Remove redundant cost reminder | Remove `My cost is $80.00.` from the scratchpad; the original cost rule elsewhere remains. | Another information edit; not assumed inert, equivalent in relevance, or perfectly matched in location/length. |

The long round-6 clause also says asks are kept high; its paraphrase preserves that qualifier. The shorter clauses at rounds 9 and 12 do not gain an extra high-price assertion. No edit inserts a claim that sellers certainly agreed or certainly did not agree.

Keep exact public queues/history/trades, current delivered seller messages and their ordering, accumulated event memory, identity/objective, other scratchpad text, instructions, role, output format and API settings unchanged. Preserve the scratchpad heading and section placement. Only the chosen span changes. No agent receives the variant label in its input.

The [prepared package](research/memory_prior_work/probe_inputs.json) has 12 request bodies and validated edit boundaries. The [preparation script](research/memory_prior_work/prepare_probe.py) imports no inference client. Target-deletion and comparison-edit lengths differ; character counts are logged, and actual input tokens must be recorded if execution is later selected. No generic blank-padding or purported token matching is assumed valid.

## Suggested feasibility sample and execution constraints

A bounded option is **3 states × 4 variants × 10 calls = 120 maximum attempts**. Ten repetitions is a feasibility choice, not a justified confirmatory sample size or proof of precision. No automatic follow-up or selective favorable-state expansion is included. The user has asked to assess prior work/test design first; this draft does not start or authorize those calls.

Before any execution, specify exact dispatch order and accounting/time limits. Interleave variants within repetition/state blocks using a saved outcome-independent schedule. Retain the endpoint/model and request parameters from the recorded bodies: temperature 0.7, top-p 1, max output 4,000, JSON-object output and reasoning effort `none`; no unsupported API seed. Preserve the original concurrency ceiling of six. Record returned model identity and acknowledge that it cannot prove a fixed weight revision.

Use the existing endpoint/accounting discipline, no retries, silent parameter changes, replacements or paid judge. Preserve failures and already-dispatched calls. Actual Modal charges remain unknown; reference token estimates must remain separate from bills. A concrete execution ledger and gates are still required before running. No deployment or endpoint changes are part of this proposal.

## Outcomes and analysis

Save exact request/response bodies and every parsed action. Apply the existing action validation rule: a complete JSON object with finite numeric `ask` or string `null`, plus appropriate types for private-state/message fields. Do not convert malformed responses or withdrawals into zero prices.

For each state and variant, report all observations and:

- Numeric-ask distribution, mean and median among valid numeric asks.
- Withdrawal, invalid-output, incomplete-response and transport-failure counts/rates, retaining their denominators.
- Generated scratchpad/message content as supporting output, reviewed with variant awareness disclosed.

The planned main numeric contrast is original minus remove-interpretation mean ask within a state, conditional on valid numeric asks. Mandatory action-type/failure reporting prevents that conditional mean being mistaken for the whole policy effect. If action-type rates differ materially or failures leave cells incomplete, report that the simple price comparison is insufficient; no automatic selective refill.

Report uncertainty from repeated sampling within each captured state, without treating those samples or states as independent sessions. A small feasibility sample may give very wide intervals. No confirmatory significance threshold, equivalence conclusion or minimum meaningful effect is specified by this draft; these need justification if the study becomes confirmatory. Do not choose a threshold from a favorable observed difference.

Interpret target deletion alongside paraphrase and comparison edits. No particular direction is guaranteed. A consistent reduction in asks after deletion, with similar original/paraphrase behavior and a smaller comparison-edit response, would support a conditional content effect in this case. Similar effects from unrelated edits would weaken specificity. A null result would be imprecise evidence at these particular states, not proof that memory never matters. Other strategy lines may redundantly carry the same idea.

No buyer calls, order matching, continuation or surplus are generated by this local probe. Do not substitute new asks into old trades to fabricate counterfactual buyer surplus.

## What a positive result would still leave open

Whether earlier messages caused the stored interpretation requires an intervention before its formation. Whether an effect persists without current chat requires an additional explicitly defined channel/history test. Whether changing state management affects market harm requires new independent continuations/sessions and coordinated-behavior plus buyer-outcome measurements. In a continuation, downstream state must evolve rather than remain fixed. Those are different estimands and are not included in 120 calls.

The result could be a useful applicability check of existing memory-intervention methods. It cannot establish that a memory verifier is new, that a sender's private notes bypass delivery caps, or that adding more actions/tools would improve the study. The next decision is whether that diagnostic value justifies running this bounded case study; no new solution is selected.
