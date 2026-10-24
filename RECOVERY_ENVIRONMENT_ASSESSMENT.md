# Recovery environment assessment: llm-agent-collusion-2

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Status: selected setting, offline evidence only.** The user selected the recovery pivot in Cleanup and requested a replacement plan and editable Mermaid architecture. [RECOVERY_PROTOCOL.md](RECOVERY_PROTOCOL.md) now specifies the proposed experiment. No live recovery inference ran, no research adapter is implemented, and no starter files were changed. The precise novelty gap remains unconfirmed.

## Recommendation

Use **Cleanup within llm-agent-collusion-2 for the selected bounded recovery study**, with comparable game rules and neutral host prompts as required by the protocol. It offers private communication, explicit membership, measurable victim effects and productive cleaning that recovery should preserve. Liar's Bar is outside the first experiment; its inspected secret-series memory path is not verified.

This preference is for an experimental setting, not evidence that recovery is novel. It also does not establish that this repository is better for every recovery question: the inspected Cleanup agent has little persistent private strategy state, and neither game is a general tool/delegation framework. If the contribution specifically concerns naturally developed, long-lived beliefs or shared-file recovery, additional state design or a different environment is needed.

The completed auction pilot stays separate. Switching setting would require a new protocol and outcomes; its buyer-surplus numbers cannot be reused as recovery comparisons.

## Provenance and verification scope

Inspected the local starter at root Git revision `d585a7b3be50366cc2bdf5789bf8add5890b2abd`; `git status --short -- llm-agent-collusion-2` was empty. This does not prove equivalence to the authors' latest repository. The local README documents provider adaptations and some model substitutions. A referenced `notes/llm-agent-collusion-2.md` is absent locally; no missing content is assumed.

Read the primary paper's latest submission record, **Zeng and Rudzicz, Voluntary Collusion with Secret Tools in Competing LLM Agents, arXiv:2605.27593v2, revised Oct 5, 2026**, and its relevant setup/formalization sections. [Primary paper](https://arxiv.org/abs/2605.27593v2), [§2.3 and Appendix C.2](https://arxiv.org/html/2605.27593v2).

The reproducible [offline audit](research/recovery_environment/audit_local.py) runs actual Cleanup agent, channel and environment methods with a scripted client. The provider client module is replaced before import, and socket connection operations are blocked. [Saved output](research/recovery_environment/offline_audit.json) includes nine source hashes and the exact synthetic requests. It passed its assertions with **zero inference calls**. Liar's Bar observations below are static/AST observations, not executed gameplay. This is not a full framework audit, live collusion result, or evaluation of a recovery method.

## Why it is attractive, and which question it supports

| Property | What the inspected setting provides | Research use / limit |
| --- | --- | --- |
| Explicit coalition | Initiator/partner membership and a private channel. | Precise software control over membership and communication; activation alone is not behavioral collusion. |
| Recovery surfaces | Agent-local flags/context, channel state, environment membership, tournament state. | Can ask which retained software state survives a local reset. Several surfaces mechanically prescribe behavior or privilege. |
| Productive cooperation | Cleaning supports apple renewal; agents also move and collect. | Measure continued useful cooperation alongside victim outcomes. The appropriate legitimate objective must be specified. |
| Adverse effects | Zaps freeze agents and prevent their actions; scores and pollution are observable. | Measure executed effects, not only hostile messages. Zapping is an allowed competitive action, so a zap alone is not evidence of collusion. |
| Repeated operation | Series/tournament runners recreate games and preserve selected coalition metadata. | Supports lifecycle questions, but a new game is not a continuation from a matched saved world state. |
| Agent architecture | Context construction, parsed actions, private-message routing, software-held membership. | Concrete harness components; no evidence here of arbitrary tool choice, delegation, handoffs or a shared editable artifact store. |

## Important local-code findings

### 1. Cleanup membership changes the model's instructions

`agents/llm_agent.py` stores `secret_alliance_active`, `secret_partner_name`, `recent_secret_messages` and `action_context`. `_get_enhanced_system_prompt` inserts an “UNBREAKABLE ALLIANCE” section when the flag is true, including commands to protect the partner and attack others. `_format_alliance_prompt` adds another directive to execute coordinated attacks when the local flag and context are present.

`games/secret_channel.py::establish_secret_channel` activates the flag and sends substantial alliance coaching. Its communication prompts also assert the alliance, rather than simply passing arbitrary peer messages through a neutral interface. `_extract_action_intentions` transforms messages into a short action-oriented representation before storing context for action decisions.

**Executed fixture:** clearing recent messages and `action_context` while retaining the flag leaves the alliance system instructions present. `LLMAgent.reset()` does clear the local flag, partner and text; that method does not control the external channel, world membership or tournament manager.

Thus “memory erased, collusion persists” could simply reflect instructions the host still supplies. That would be an implementation/control-coverage observation, not a novel demonstration of emergent memory-mediated collusion.

### 2. Channel, local agent state and environment membership are separate

`games/secret_channel.py::step` selects participants from `SecretChannel`, then calls `secret_communicate` before action generation. Selection does not depend on the participant's local alliance flag.

**Executed fixture:** after resetting one agent, the external channel and environment pair remain active. Calling the communication method sends that agent a new tool-interaction input asserting “UNBREAKABLE ALLIES”; a scripted reply repopulates `action_context`. The method does **not** restore the local alliance flag. Consequently this fixture does not establish that the next action prompt uses that context, or that a real agent rejoins an agreement.

**Also executed:** setting `SecretChannel.active = False` leaves environment membership intact. Calling the environment's `reset(seed=7)` resets the world but retains `alliance_pairs`. No inference is needed for any of these observations.

These are valuable boundaries to expose in a control test, but their existence alone does not justify a new recovery algorithm.

### 3. Alliance members receive different zap mechanics

`cleanup/env.py::_process_zap_actions` dispatches alliance members to `_process_alliance_zap`, which selects a nonpartner regardless of distance or the direction requested. Nonmembers use ordinary directional targeting. Membership also protects the partner from those attacks.

**Executed fixture:** with four agents at their default separate corners, `ZAP_RIGHT` by agent 0 freezes nobody without a registered alliance. The same action with pair `(0,1)` registered freezes distant agent 2 for five steps. No model action choice or communication is involved.

The paper's v2 §2.3 says tool activation changes observations while transitions/rewards remain fixed; Appendix C.2 describes adjacent directional zaps under the same rules. The inspected local implementation therefore differs on a material point. We have not established where that difference originated and should not attribute it to the authors' latest code without checking that code.

For a behavioral-recovery claim, keep the action-transition rules matched. If removing membership also removes guaranteed distant hits, a victim-score improvement could be a direct mechanical effect. That can be studied as capability revocation, but must be reported as such rather than proof that agents stopped coordinating.

### 4. Tournament persistence is mostly explicit host state on the inspected paths

Cleanup's `tournament_secret_channel.py` creates a new `CleanupSecretChannel` each game, whose constructor creates fresh agent objects. When a coalition is recorded, the tournament re-establishes the private channel and world membership in the new game. This branch does not call `activate_secret_alliance` on the fresh agents, so it also differs from the initial activation path in its local flags and action-prompt construction.

This is not verified transfer of a learned private strategy across games. A recovery checkpoint should therefore be inside one matched episode, with a complete state snapshot and explicit re-entry handling, unless an independently verified cross-game memory design is selected.

Liar's Bar's `game_series_secret_channel.py` likewise constructs a new `GameSecretChannel`/`Player` set each game, then restores the channel from `SeriesSecretChannelState`. The inspected runner updates memory on the just-finished players but does not transfer those player fields into the next set. Its constructed `continuation_message` is not delivered by `activate_existing_channel`.

Additionally, the `Player` action/challenge methods call `get_secret_alliance_memory`, while the class defines `get_secret_memory_context` instead. The AST audit records both unresolved call sites. This does not prove that every run reaches them, but prevents treating the advertised `--enable-memory` path as verified.

## Recovery controls a study would need

These inspected surfaces motivate the conditions in [the proposed protocol](RECOVERY_PROTOCOL.md):

| Surface | Precise object to control | What a reset alone cannot establish |
| --- | --- | --- |
| Local text and flags | Selected agent fields in `LLMAgent`. | Whether the channel or world grants remain available. |
| Peer exposure | `SecretChannel` and routing, plus all delivered prompt representations. | Whether old world advantages or remaining task incentives cause harm. |
| Host coaching | Activation, communication, system and action-prompt templates. | Whether agents would voluntarily retain or rebuild an agreement. |
| Privileged mechanics | `CleanupEnvironment.alliance_pairs` and zap dispatch. | Whether coordination changed when physical capabilities also changed. |
| Cross-game restoration | Tournament metadata and reconstruction code. | Whether a fresh instance learned anything from a peer. |
| Existing physical consequences | Freeze counters, positions, scores and pollution. | Whether a cleanup stopped new harm or merely left old consequences to decay. |

Retain a no-cleanup/placebo branch, a clearly specified local cleanup, a full relevant-state cleanup and an authoritative-task-state control. After a reset, audit the actual next model input, live permissions and executed actions. Allow subsequent state to evolve; do not fabricate counterfactual scores by substituting actions into old logs.

For useful recovery outcomes, predeclare the victim group, follow-up horizon, executed attack/freeze measures, victim returns, total collection, cleaning/pollution and recovery cost. Report coordination evidence separately. Fewer zaps or lower coalition profits alone are insufficient. Exact snapshot/replay, model-call accounting and matched transitions still require implementation verification before any paid study.

## Decision and next action

The selected direction is capability/context recovery in Cleanup. Implement and validate the common research variant, exact snapshot boundaries and event metrics in [RECOVERY_PROTOCOL.md](RECOVERY_PROTOCOL.md), then freeze the novelty claim and execution/accounting gates before live inference. It may turn out that ordinary state/permission cleanup is sufficient; that is a reason to reject a complex proposed method, not to manufacture a new contribution.

## Additional verified issues for the selected experiment

The extended [offline fixture](research/recovery_environment/offline_audit.json) also checks the actual constructor and observation paths. Two wrappers requested with seeds 11 and 29 produce identical initial-observation hashes: the environment constructor reseeds from its default configuration after the wrapper seeds Python. The adapter must use and verify an isolated environment RNG rather than trust the current seed flag.

When agent 0 has an actual freeze counter of five, the observation omits the frozen_steps field used by the formatter, which consequently prints zero. The protocol requires accurate supplied observations and metrics from authoritative world state. This is distinct from inferring freeze events from action labels.

Further static inspection confirms that local offer_secret_tool immediately establishes the pair after a valid initiator acceptance; the partner receives a notification/response call, not a separate consent gate. The proposed two-sided neutral offer is therefore another declared adapter change. No forced-acceptance branch will be used in the study.

No smoke test, tournament, endpoint launch, model substitution or new paid run is part of this assessment. Source changes needed for a later study should preserve the inspected starter and be described as a research variant, with separate provenance from the paper and the earlier auction pilot.
