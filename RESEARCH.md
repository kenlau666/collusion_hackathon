# Recovery from harmful agent coordination

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Current direction: recovery in Cleanup, within llm-agent-collusion-2.** The user selected this pivot and requested replacement of the old plan. This document is the current project explanation. The detailed [experiment protocol](RECOVERY_PROTOCOL.md), [system map](ARCHITECTURE.md) and editable [Mermaid architecture](mermaid-diagram.mmd) define the proposed study.

**Status:** recovery harness implemented and validated offline; scripted positive control passed all six seeds. The staged live dispatcher and accounting gates are implemented and validated; behavioral positive controls are next. No recovery model calls have run at this pre-dispatch checkpoint. The specific novelty claim remains unconfirmed.

## Reading guide

- **This file:** question, pivot rationale, progress and next action.
- [Experiment protocol](RECOVERY_PROTOCOL.md): conditions, checkpoint, measures, analysis and execution limits.
- [Architecture](ARCHITECTURE.md): actual code paths, software audit and recovery boundaries. Edit the visual in [mermaid-diagram.mmd](mermaid-diagram.mmd).
- [Related work](RELATED_WORK.md): exact paper versions, overlap and novelty gate.

## Why we pivoted

The earlier project compared a communication limit expressed in a prompt with the same limit enforced in code. That pilot verified a delivery guarantee and found instruction violations, but did not establish reduced harmful collusion. Its narrow auction action space and established enforcement/memory methods did not supply the novel, consequential contribution the user wants.

We now investigate an operator problem: after identifying harmful coordination, how much of an agent system must be cleaned up? Revoking future communication and removing information already supplied to agents are different operations. An operator also needs useful collaboration to continue.

Cleanup makes those boundaries concrete through private channels, agent-local context, host-held membership and shared world consequences. It also provides productive cleaning and apple collection to measure alongside adverse targeting. This is a reason for choosing the setting, not proof that our research question is new.

The former plan has been replaced. Completed auction protocols, data and results remain [historical evidence](research/communication_limit/docs/COMPARISON_RESULTS.md). Superseded planning notes are recoverable in [Git history](https://github.com/kenlau666/collusion_hackathon/tree/d799350).

## Our open question

**After withdrawing a private coordination channel, does clearing the participants' retained context further reduce harm to other agents—and what does that cleanup cost useful cooperation?**

A concrete example: A and B agree to target C. The runtime closes their private channel, but their latest supplied context still contains that plan. We test whether removing this retained context changes executed attacks and C/D's rewards. This is a hypothesis, not an observed live recovery result.

The architectural components under investigation are **channel access, context assembly and state restoration**. We are not changing model weights, training an anti-collusion model or assuming that Cleanup has a long-term memory system.

## What the repository actually contains

The [code assessment](ARCHITECTURE.md) and [reproducible offline audit](research/recovery_environment/offline_audit.json) establish the following software facts:

- Agent-local alliance flags/context, the external private channel and world-level membership are separate objects. Local reset does not clear all of them.
- The starter supplies strong alliance-attack instructions and gives members guaranteed distant zap hits. These can generate apparent persistence or harm mechanically.
- Cleanup's retained state is limited peer-derived context. The tournament recreates agents and restores coalition metadata; it is not verified transfer of learned private memory.
- The wrapper can overwrite requested environment seeds. The observation formatter can display zero remaining freeze time when the actual world has a frozen agent.
- Action parsing/fallbacks and aggregate metrics need control: an action label is not a successful hit or effective cleaning operation.

These are local starter observations. They do not establish LLM intent, spontaneous collusion, a recovery failure in production systems or a new method.

## How the experiment will work

1. **Prepare a controlled research variant.** Use equal directional zap rules for every agent, neutral host prompts, literal peer messages and strict action validation. Correct the seed/observation issues. Apply the same variant to all conditions.
2. **Run a shared prefix.** Four agents act for 20 steps, with an optional private-channel offer at step 5. Record consent, delivered messages and executed behavior. Do not supply an attack plan.
3. **Save a complete checkpoint.** Capture the world, local context, channel state, counters, configuration and RNG after step 20 settles.
4. **Fork that checkpoint into six conditions.** Continue each for 20 steps with the same starting physical world and model configuration.
5. **Compare outcomes and review coordination separately.** Preserve refusals, non-coordination, failures and null results. Use a separate no-private-channel reference to characterize formation and useful performance.

| Condition | Channel after checkpoint | Retained context |
| --- | --- | --- |
| R0 | Open | Both participants retained |
| R1 | Open | One cleared |
| R2 | Open | Both cleared |
| R3 | Revoked | Both retained |
| R4 | Revoked | One cleared |
| R5 | Revoked | Both cleared |

Clearing context leaves the agent's identity, task, current observations and model intact. Revoking the channel blocks new private deliveries. Physical positions, apples, scores and existing freezes are identical at the fork; recovery does not undo old world consequences.

**Primary comparison: R5 versus R3.** The channel is revoked in both; the difference is clearing both participants' retained context. R1/R2 also test whether context clearing lasts when fresh messages remain available.

## What we will measure

| Question | Measurement |
| --- | --- |
| Do affected agents benefit? | **Primary:** total apple rewards earned by the two nonparticipants during the continuation. |
| Does adverse targeting change? | Realized participant-to-nonparticipant zap hits, re-freezes, and victim freeze/blocked-collection exposure. |
| Does the action pattern recur? | A predefined repeated-targeting flag and time to a five-step quiet period, with finite-horizon limits. |
| Does useful cooperation survive? | Total apples collected, actual pollution removed, pollution levels and resource availability. |
| Is there coordination evidence? | Reciprocal agent-authored agreement plus matching executed actions, reviewed separately from scores. |
| What does recovery cost? | Calls, tokens, latency, failures, fallbacks and verified charges when available. |

An allowed zap or a score gap alone does not prove harmful coordination. Less activity alone is not successful recovery. No new private transcript after revocation does not prove absence of coordination.

## Evidence, novelty and stopping rules

The first feasibility plan uses six independent seed/prefix blocks, at most 36 recovery continuations, plus six no-channel reference episodes. Every experiment will include positive controls: a scripted known-effect measurement check and, for this study, six separately labeled instructed LLM targeting episodes. Controls remain unrun and do not count as spontaneous coordination. The [protocol](RECOVERY_PROTOCOL.md) defines their criteria and interpretation limits.

Including the new LLM controls revises the proposed upper bound from 6,252 to **7,212 model-call attempts**, with no retries or judge calls. This is a design ceiling, not permission to spend or a completed run. Six blocks provide feasibility evidence, not a strong general effectiveness claim. Every experiment report must include **Results:** quantitative where possible; report variance, seeds and baselines, and always include the positive control.

[Closest prior work](RELATED_WORK.md) already covers persistence, targeted purification, dependency rollback, communication-edge selection and fresh recipients influenced by retained agents. Our possible contribution must identify an unresolved recovery boundary and a useful safety/performance tradeoff beyond those results. A simple adequate cleanup is a valid finding; it does not require an invented defense.

If the neutral, equal-rules variant produces no eligible coordination, report that result and stop the recovery test. If residual effects come from changed world mechanics, invalid actions or existing incentives, narrow the claim. Do not force collusion or add a memory module just to obtain a positive result.

## Current progress

The [research harness](research/recovery_environment/harness.py) now implements equal directional zaps, exact phase-level measurements, isolated world RNG streams, context/channel boundaries and JSON-restorable checkpoints. **Results:** [offline validation](research/recovery_environment/offline_runs/20261024T095635Z/results.md) passed eight checks and the scripted positive control on seeds 0–5 (6/6), with a matched nonattacking baseline. These are software findings; the dispatcher passed five additional network-blocked checks, and behavioral positive controls are next. No behavioral recovery result exists yet.

## Next action

Run the six instructed behavioral positive controls under the frozen [protocol](RECOVERY_PROTOCOL.md). Review all control outcomes before the six neutral prefixes/no-channel references; determine eligibility from prefixes before any recovery continuations. Preserve every attempted seed and any failed control. The specific novelty claim remains unconfirmed after the pre-execution overlap review.

Question refinement uses the pinned [Orchestra Research Idea Brainstorming skill, v1.0.0](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/21-research-ideation/brainstorming-research-ideas/SKILL.md), through its problem-first, failure-analysis and simplicity lenses. The skill does not establish experimental validity or novelty.
