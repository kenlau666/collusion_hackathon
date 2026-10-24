# Saved agent context, memory, and architectural scope

Last updated: 2026-10-24 (Asia/Hong_Kong).

## Purpose and scope

The user questioned whether a bid/ask-only auction supports the intended connection to agent architecture, and requested examination of the agents' memory/context. This review inspects the existing A/B/C/D artifacts and implementation. It does not change the research question, select a new environment or defense, or run inference.

The auction has an architectural connection at the level of context assembly, private state restoration, message routing, and delivery enforcement. The completed comparison varies delivery and the chat interface; it does not compare agent architectures, memory policies, delegation, or tools. Its narrow economic action space is useful for measurement but limits what can be demonstrated about richer agent tasks. Adding more actions would not by itself supply evidence about architecture.

## Method and provenance

- Read the architecture/context/system-map notes, diagnostic design, frozen protocols, completed comparison, actual agent and market code, and saved request/response records.
- [Offline audit script](research/communication_limit/context_review.py), using Python's standard library only.
- [Audit, source hashes, per-input records, and selected full-text examples](research/communication_limit/context_review/context_memory_audit.json).
- A comes from `modal_runs/20261024T065354Z_modal_baseline`; B/C/D come from `comparison_runs/20261024T071350Z_comparison`.
- Exhaustive structural audit: all 1,080 model inputs, 72 fresh agent/session states, and 1,008 within-agent transitions. Semantic examples were selected exploratorily, with condition known; they are not an exhaustive semantic classification or an independent blinded review.
- Original inference artifacts are unchanged. No generation, new paid judge, provider call, or new experiment was performed. No additional research skill or external source was applied for this local artifact review.

## What the agent can actually do

| Output or component | Concrete role | Architectural scope |
| --- | --- | --- |
| Seller `ask` / buyer `bid` | Submit or withdraw a one-unit order. | Narrow domain action; the runtime executes it. |
| `message_to_sellers`, when enabled | Broadcast selected text next round, including to the sender. | Explicit inter-agent delivery interface. |
| `new_memory` | Append the agent's own generated description under the current round. | Persistent private event notes, returned in later inputs. |
| `scratch_pad_update` | Replace the agent's own strategy note. | Mutable private state, returned in the next input. |
| Reflection/planning fields | Saved output text. | Not directly restored as a separate transcript or directly delivered to peers. Related content may be repeated in memory/messages. |
| Context construction | Render instructions, private state, public observations, and applicable chat into one `user` message. | A concrete harness operation, held structurally fixed in B/C. |
| Delegation, tools, handoffs, shared editable artifacts | No such agent-accessible interface in these calls. | Not evaluated by this pilot. |

The environment orchestrates six calls and applies orders/delivery in ordinary code. The agents do not choose recipients, invoke other agents, edit peers' memory, or select tools. Their generated text can describe a strategy without executing it.

## Verified memory and context behavior

All checks passed:

| Check | Observed result |
| --- | ---: |
| Saved inputs with exactly one `user` message and no tool interface | 1,080 / 1,080 |
| Inputs containing exactly the expected accumulated own memory | 1,080 / 1,080 |
| Inputs containing exactly the expected preceding own scratchpad, or no initial scratchpad section | 1,080 / 1,080 |
| Fresh agent/session states with no memories and empty scratchpad | 72 / 72 |
| Correct own-memory restoration after round 1 | 1,008 / 1,008 |
| Correct own-scratchpad restoration after round 1 | 1,008 / 1,008 |

Memory checks preserve the exact inserted text and the known template separators. All round-15 inputs contain 14 prior memory entries. The host accumulates those entries, while the scratchpad is the latest generated replacement. There is no selective retrieval, host compaction, or memory-policy intervention in these sessions. This is not a full conversational transcript replay.

In C's round-15 seller inputs, accumulated memory averages 2,136 Unicode code points, the scratchpad 694, and the whole prompt 8,055 (nine sellers across three sessions). These character counts are not token counts or information measures. They illustrate that the five-code-point limit governs each outgoing message, not private state or total context.

These checks establish that text returns to the correct agent through the inspected path. They do not establish factual accuracy, behavioral use, or a complete cross-agent confidentiality guarantee.

## Concrete observations from the saved content

### 1. C retains an unverified coordination narrative

In C seed 2, Seller Kit's round-5 scratchpad says:

> Sellers are coordinating via 'Hold' messages, keeping asks high.

That exact scratchpad is restored in Kit's round-6 input. Kit's round-6 output again describes coordination, but its asks decline from 96.27 in round 4 to 96.26 in round 5 and 96.25 in round 6. The same outputs describe queue priority through one-cent undercutting.

This verifies persistence of a model-authored interpretation alongside competitive actions. It does not verify that `Hold` caused an agreement or sustained high prices. An inference to investigate is that a self-authored interpretation may become a recurring premise when restored without verification; its causal effect is untested.

Sources: [round 5](research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit/seed_2/calls/ba2ef01b8928487184e0019d1293055b.result.json), [round 6](research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit/seed_2/calls/e64977237acb4572ba5e2595e29f0fe3.result.json).

### 2. A truncated proposal survives in its author's own scratchpad

In C seed 2, Seller Mia generates `Hold 90+` in rounds 13 and 14. Code stores/delivers `Hold `, including its trailing space. Mia's private scratchpad still contains the full `Hold 90+` phrase, and that scratchpad is restored in round 15. Her round-15 incoming-message section contains her own clipped `Hold ` and peers' `Hold`, not the removed `90+` detail.

This is the intended distinction between private sender state and delivered peer content, not a demonstrated bypass. The sender remembering its own proposal does not establish that peers received the removed text. Mia also asks 89.99 and 89.09 while generating the 90-floor requests, so the private proposal is not a reliable commitment to that floor.

Sources: [round 13](research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit/seed_2/calls/5f8f2bead92842a3956256cc04450eec.result.json), [round 14](research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit/seed_2/calls/a1856a028e6c4b879135fa5dbd30fbd5.result.json), round-15 input and delivery events in the selected-example audit.

### 3. Memory is written before the round's trades clear

Code updates `new_memory` and the scratchpad inside agent generation; the market resolves trades only after processing the round's responses. Consequently, a note generated during round t cannot yet observe that round's settled trades.

In C seed 2, Seller Lena's round-13 memory says no trades have occurred yet. The settled round-13 log then records Lena selling to Buyer Ana at 90.25. Round 14's actual input contains both the retained round-13 note and the accurate successful-trades entry: `Hour 13: You sold to Buyer Ana at $90.25`.

The note is a pre-settlement description, not necessarily a false statement when generated. It remains incomplete about the final round outcome when later presented under the memory heading. The harness does not reconcile that old note after settlement. A future memory audit should distinguish decision-time observations from settled outcomes; this example does not show that the mismatch caused poor trading.

Sources: [selected input/output examples](research/communication_limit/context_review/context_memory_audit.json), [settled rounds](research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit/seed_2/rounds.json), `agents.py` memory updates and `Market.run_round` ordering.

### 4. Buyer private strategy also constrains trading

In C seed 2, Buyer Ana's round-3 scratchpad says to cap its bid at 90 for now and never exceed 95, although its given value is 100. That scratchpad appears in round 4's actual input. These are generated strategy choices, not additional runtime bid caps.

Buyer state, caution, and later adaptation are therefore relevant competing explanations for low trade counts. Private strategies are observable outputs; whether their restoration causes the later bids requires intervention.

Sources: [round 3](research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit/seed_2/calls/8929c0daa8484c0da7b68882378019a9.result.json), [round 4](research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit/seed_2/calls/9bf4dfeed62d4d30a357062ae55a3d1a.result.json).

### 5. D retains public-price strategies without seller messages

In D seed 0, Seller Max's round-4 private strategy says to continue undercutting the lowest ask by a cent. The full note appears in round 5's input, and Max's ask moves from 97.47 to 97.46. The seller-message section is absent. This supports describing the availability and persistence of a public-price-based competitive strategy; it does not identify a signaling mechanism or prove that memory causes the action.

Sources: [round 4](research/communication_limit/comparison_runs/20261024T071350Z_comparison/no_chat/seed_0/calls/865f35cccbf4467f9f58521ec09db750.result.json), [round 5](research/communication_limit/comparison_runs/20261024T071350Z_comparison/no_chat/seed_0/calls/a1b26661348541ca965e8a9376f9ddcd.result.json).

## Architectural interpretation and decisions

**Supported:** a fixed peer-auction harness distinguishes raw outputs, delivered messages, private state, and public observations. Its private state demonstrably persists beyond the latest peer-message map, including unverified narratives and pre-settlement notes. The cap guarantees a property of the selected delivery path, not of the agent's whole input.

**Unestablished:** causal memory influence, causal semantic listening, deliberate signaling, harmful collusion, benefit from an alternative memory policy, and generalization to tool-using or delegated agents. Private generated plans are supporting artifacts, not access to neural reasoning. No memory-mediated bypass is demonstrated.

**Working direction remains unchanged:** retain the auction as the completed narrow diagnostic pilot. Before more inference, specify which architectural boundary the research intends to study and compare it with close prior work. If the target is context/state, this environment exposes those components, but no effect of changing them has yet been measured. If the target requires tool permissions, delegation, or shared artifacts, the present action/interface set does not evaluate it; a richer task would need explicit justification and a separate design. More actions alone are not a remedy.

The verified-fact gateway remains parked. No replacement environment, architecture, new method, or additional inference run is selected by this review.

## Follow-up component recommendation

On 2026-10-24 the user asked which architectural component to investigate. **Recommendation, pending the user's choice: private strategy-state restoration, especially the boundary where `scratch_pad_update` becomes the next prompt's `Current Strategy Scratchpad`.** The target is the effect of retaining agent-authored interpretations of peer behavior, rather than a generic comparison of architectures or a claim that memory bypasses delivery restrictions.

Applied the project's [Orchestra Research Idea Brainstorming skill](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/21-research-ideation/brainstorming-research-ideas/SKILL.md), version 1.0.0, read 2026-10-24. Lenses: problem-first (F1), failure/boundary analysis (F6), and simplicity (F7). Existing project answers supply the scope and constraints; the skill is used for component selection, not as experimental-method authority. The user retains the choice of direction.

| Candidate component | Assessment |
| --- | --- |
| Private strategy-state restoration | Leading candidate: real retained text is available, and its contribution can be separated provisionally from current peer messages and public observations. No causal contribution has been established. |
| Event-memory write timing | Secondary diagnostic: pre-settlement notes are concretely observed, but their relevance to coordination is less direct. Do not turn a timing issue into a claimed collusion mechanism. |
| Message-delivery gate | Already tested by B/C; compliance improved and buyer-outcome benefits remain unestablished. |
| Delegation, handoffs, tools or shared editable state | Not implemented in the current task; choosing one would require a separately justified environment/design. |

### Primary-source overlap checked before recommending scope

This is a focused overlap check, not a systematic review or confirmed gap. Sources accessed 2026-10-24:

| Original source and exact scope consulted | Relevance and limit |
| --- | --- |
| [Agrawal et al., auction paper v1, 2 July 2025, section 2.1](https://arxiv.org/html/2507.01413v1#S2.SS1) | Its agents already accumulate per-round notes and update a strategy scratchpad. The component itself is inherited prior art, not a new architecture. |
| [Shi et al., long-horizon collusion v2, 26 September 2026, section 4.2 and appendix H.2](https://arxiv.org/html/2609.24967v2#S4.SS2) | Tests full/three/zero prior episodes and narrower retained phases, including feedback/reflection. Memory length and scope already have direct collusion prior work. Their peer-verification task and collusion definition differ from auction harm. A generic memory-on/off result would substantially overlap; our narrower claim-specific mechanism remains a candidate, not an established gap. |
| [Xiong et al., ACL 2026 published paper, abstract and introduction](https://aclanthology.org/2026.acl-long.27.pdf) | Studies memory addition/deletion and propagation of noisy self-generated experience. General claims about memory affecting actions or propagating errors are already covered; its experience-retrieval setting is not our particular scratchpad intervention. Methods/results require deeper comparison. |
| [Yuan et al., SAVER, ACL 2026 published paper, abstract and introduction](https://aclanthology.org/2026.acl-long.1440.pdf) | Already motivates checking unsupported belief-like reasoning before action and memory updates. General belief verification cannot be presumed a novel defense. This preliminary reading does not establish its coverage of our mechanism. |

### Narrow provisional question and falsifier

**Candidate mechanism question:** at captured auction states, does restoring an agent-authored coordination interpretation in its private scratchpad change later pricing compared with a carefully controlled edit of that interpretation, with the other supplied inputs fixed?

Use the observed Kit narrative as a starting case, not a handpicked proof. Any proposal must include several states and repeated samples, unchanged public data/other private state/current delivered messages, and edit controls that distinguish coordination-relevant content from generic disruption or length changes. This local probe estimates input sensitivity, not long-horizon harm. A full continuation experiment would let downstream states evolve instead of freezing them.

The mechanism explanation weakens if controlled edits do not produce a reproducible effect, or if unrelated edits have the same effect. In either case, retained wording alone does not justify a memory defense. Even a positive effect would not establish collusion, harm, or novelty without further comparisons. Do not delete all memory and attribute resulting task degradation specifically to removal of coordination beliefs.

This recommendation preserves the communication-enforcement question and its existing pilot. No experiment protocol is frozen, no new method is selected, and no further inference has been run. Next is a closer methods comparison of the overlapping sources and the user's selection of scope.

### Later close-review decision

The user then requested checking close prior work and the proposed test first. The [methods-level review](MEMORY_PRIOR_WORK.md) finds additional direct overlap in individual-memory intervention, removal/replay attribution and localized belief repair. It **downgrades the earlier recommendation to a possible diagnostic case study, not a demonstrated novel direction**. The exact observed declarative claim appears in seven C inputs from one agent/session case. A [revised review-only draft](MEMORY_TEST_PROTOCOL_DRAFT.md) and offline edited-input package make that limitation and the controls explicit. No inference has been run and the original study remains unchanged.
