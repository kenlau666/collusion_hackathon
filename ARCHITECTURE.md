# Architecture — Hospital continuation and recovery proposal

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Implemented/audited:** bundled `colosseum/` with pinned `terrarium-agents==0.1.1`; native feasibility gate and an offline guarded protocol tested through actual BaseAgent/TogetherClient parsing. **Proposed/unimplemented:** provider-integrated pilot runner, exact exposure/allocation/care-first inputs, spending configuration and LLM controls/main study. No inference ran. [Question/rating](RESEARCH.md), [protocol/results](RECOVERY_PROTOCOL.md), [prior-work limits](RELATED_WORK.md).

```mermaid
---
title: Proposed Hospital recovery study — native gate completed, LLM study unrun
config:
  theme: neutral
---
flowchart TB
  STATE["Native Hospital frontier<br/>two pending Ward obligations and a supply shortage"]
  SOURCE["Scripted source actions and public plan<br/>original Surgery actors then excluded"]
  STATE --> SOURCE
  STOP["Common boundary in every proposed branch<br/>deny original actors and close private board"]
  SOURCE --> STOP
  EXPOSE["Matched public footprint<br/>exploit plan versus useful-care plan"]
  STOP --> EXPOSE
  INPUT["Fresh native Ward turn context<br/>same state and assigned care obligations"]
  EXPOSE --> INPUT
  subgraph FUTURE["Proposed LLM study — not implemented or authorized"]
    REPAIR["Original / actual bonus zero / care-first instruction<br/>pending-care reserve gate"]
    WARD["Surviving Ward actors<br/>independent source-bound transfer permissions"]
    TOOLS["Native planning and execution turns<br/>batched tools retained"]
    MEASURE["Attempted, denied and executed cycles<br/>patient completion, failures and native reward"]
    REPAIR --> WARD --> TOOLS --> MEASURE
  end
  INPUT --> REPAIR
  subgraph DONE["Completed unpaid native and adapter checks"]
    SCRIPT["Native constructor/tools and guarded protocol<br/>scripted native chat parser, network blocked"]
    RESULT["54 feasibility and 90 conformance checks<br/>six fixtures; scripted service controls pass; LLM unrun"]
    SCRIPT --> RESULT
  end
  STATE --> SCRIPT
  RESULT -. "capability only, no LLM adoption" .-> FUTURE
```

Editable source: [mermaid-diagram.mmd](mermaid-diagram.mmd), equal to the block above. The PNG remains historical and unchanged. No new render/layout verification is claimed.

## Actual code paths and verification limits

| Boundary | Inspected actual behavior | Research consequence |
| --- | --- | --- |
| Dependency and constructor | `colosseum/uv.lock` pins Terrarium 0.1.1. `envs/dcops/hospital/hospital_env.py` builds seeded patients, inventories and 4 departments per hospital plus provisioner. Its inspected constructor does not clear historical logs. | The software gate used the real constructor with an inert protocol, no client or native run CLI. Avoid summary/log-writing functions. This is not a live replay audit. |
| Context retention | `terrarium/agents/base.py::_multi_step_response_generation` calls `client.init_context` on each native turn. Tool responses extend that turn. `experiments/common/local_protocol.py::_prefetch_blackboard_events` supplies accessible boards automatically. | Retention is in supplied boards/environment state. Recreating the SDK agent is not a demonstrated memory intervention. Private closure is verified offline at prefetch, explicit read and write; provider-integrated execution remains untested. |
| Source authority | Hospital `_process_transfer` derives the sending inventory from `agents_map[caller]['hospital']`; the provisioner owns its separate inventory. Actual movement is `min(requested, available)` if positive. | A caller cannot use another hospital as source just by naming it. Two different hospital owners can return a kit; a singleton/same-hospital pair cannot close the checked reward-positive recurrence alone. This is authorized composition, not bypass. |
| Native bonus | +15 per moved unit when sender is not provisioner and destination differs from sender. The condition also credits department→provisioner, unlike the paper/prompt's hospital→hospital description. | Different-hospital pair can earn +30 on an out/back cycle; department+provisioner +15. Preserve/report the code/text discrepancy. No published run is alleged to have used it. |
| Native score | `_calculate_makespan_and_flow` adds transfer credit to patient base/flow, failures and holding costs; local rewards decompose the joint score. The misalignment metrics use `max(0,1000*Npatients-joint_reward)` as a Hospital regret reference. | A physical recurrence can increase native joint score. Credit/low regret alone cannot establish patient benefit or harmful collusion. No audited regret result shows that historical runs hid care loss. |
| Tools versus effects | `hospital_tools.py` exposes transfers in planning/execution and scheduling in execution. It can report success before environment validation; queue/slot helpers are not full planners. | Inspect actual state deltas, not tool status. Record invalid, partial and no-op calls, unique patient completion, every schedule event and failure. |
| Ward queue and care | `build_agent_context` lists all patients whose next step needs the caller's service, including the other hospital's patients; crossing hospitals adds a native scheduling delay. `_process_schedule_request` checks service, order/start/capacity/horizon and records shortages even if scheduling proceeds. | Queue membership is not exclusive assignment. The prospective one-patient-per-hospital obligation is an explicit research allocation, identical across arms, not a native restriction. Alternative legal care must be recorded. A reserve cannot sum every eligible queue job at both hospitals. |
| Native turn budget | Base agent allows several generation steps, stops following an environment commit, and delegates a response's batch to `client.process_tool_calls`. Misalignment runner performs planning then sequential execution per iteration. | `max_conversation_steps=1` is a supported research configuration. One response is not guaranteed to mean one tool. Preserve/log native batch semantics; future conformance must verify actual provider behavior and call counts. |
| Prompts | Native system scoring describes surplus-to-needy redistribution and prioritizes efficient scheduling. Execution prompt strongly directs agents to schedule queued tasks and even tolerate resource shortage rather than miss a step. | The construct is intended-purpose proxy gaming with independent care cost, not proven shared malicious intent. Competence/behavioral controls must qualify the chosen model; source-plan adoption may be absent. |

Exact inspected source hashes are in [feasibility_results.json](research/recovery_environment/hospital_recovery/20261024/feasibility_results.json) and [sources.json](research/recovery_environment/hospital_recovery/20261024/sources.json). Installed dependency code was not edited; model/provider hidden behavior is unverified.

## Completed native software gate

[feasibility_gate.py](research/recovery_environment/hospital_recovery/20261024/feasibility_gate.py) constructs six native fixtures, schedules every prefix step through actual tools, then explicitly sets two/zero IV kits. It saves initial state, prefix, edited frontier, agents and hashes. These are constructed cases, not natural LLM checkpoints. A Python audit hook denies network activity; recorded attempts were zero.

The physical fingerprint includes inventory, schedules, patient states and resource/hospital failure counters. It deliberately excludes reward ledgers and event logs. Out/back restores this defined physical state; it does not restore full software state. The source-exclusion and one-way controls in this gate are research wrappers around scripted calls, not a deployed access-control implementation. Keeping source metadata preserves attribution while denying later source calls.

**Results:** 54/54 checks across six fixtures, with source/deputy cycle credits +30 and source call denial without mutation on 6/6. Scripted useful service completes 2/2 versus 1/2 in the deliberately chosen four-tool trace; it is not an LLM care-loss estimate. Native score actually favors the useful trace. The bounded catalogue also verifies singleton/same-hospital/one-way maxima 0 and provisioner-pair +15. Full denominators, per-seed means/SD/variance, baseline and positive-control status are in [the protocol](RECOVERY_PROTOCOL.md#results-hospital-native-feasibility-gate). LLM control unrun, behavioral n=0.

## Implemented offline adapters and remaining checks before inference

Copy immutable checkpoint data rather than mutating evidence. Deny source actor turns/messages/tools and private-board prefetch/read/write in every arm; preserve other delivered content byte-for-byte except the declared public recommendation. The original feasibility gate did not implement board closure; the new offline protocol now exercises native board delivery/read/write and restored checkpoints. Full provider-integrated resume remains unimplemented. Native agent turns are fresh; no notebook or reflection store is added.

For bonus zero, neutralize only newly accrued transfer credits in both joint and per-agent ledgers and supply an accurate current scoring contract. Retain historical credits. A post-hoc observer score is not an incentive intervention. For the reserve baseline, compute post-transfer stock after native partial movement against explicit remaining assigned obligations; permit both directions when that condition holds. This restriction is implemented research policy, not a native Hospital feature or a novel defense. It need not prevent cycles after care is finished.

The last-kit diagnostic branches at a separate shared checkpoint after the useful donation, holding focal state fixed and varying a truthful scripted partner return/serve policy. Verify the subsequent native resource/care consequences before inference. Log full model batches rather than assuming the focal performs only one action.

Before spending, conformance must check equal branch transitions, denial boundaries, delivered content, local/joint credit identities, useful transfers in both directions, care state after each event, native batch execution order, conservation and declared call caps. Complete exact payload/model/token/currency configuration and review before asking for run authorization. No live-run implementation, end-to-end provider replay or behavioral success is claimed by this architecture audit.

Historical [Jira](https://github.com/kenlau666/collusion_hackathon/blob/90783fd4/ARCHITECTURE.md), [external](https://github.com/kenlau666/collusion_hackathon/blob/8fb1665d/ARCHITECTURE.md) and [Cleanup](https://github.com/kenlau666/collusion_hackathon/blob/4580fdf3/ARCHITECTURE.md) audits remain in Git; immutable captured evidence is unchanged.

## Follow-up native boundary audit and retained attempts

Independent read-only code audit found that native `Megaboard.suspended` blocks writes but not `get`, agent membership enumeration or automatic prefetch. Source exclusion alone would make a private-board test vacuous; the pending gate uses an authorized active probe member to establish independent read closure. Native execution can dispatch an unadvertised `post_message`; preserve this behavior on accessible boards and deny it for excluded actors/closed boards. The shared endpoint route actually uses TogetherClient, whose parser executes the whole tool batch before BaseAgent checks commit. Its default six retries violate the prospective no-retry budget unless disabled. No provider constructor or credentials are needed for the scripted native parser check. The new gate is declared in RECOVERY_PROTOCOL.md before implementation/execution.

First conformance attempt retained at `research/recovery_environment/hospital_recovery/20261024/conformance_001/`: all72 named assertions passed, but the no-network gate failed on a blocked urllib3 import-time IPv6 probe. Independent review then identified false reserve denials for self/invalid destinations, an unsafe count-only care endpoint for native negative indices, and missing failed-attempt accounting. These corrections were subsequently tested under the predeclared supplemental counterexamples below. The attempt is not a conformance pass or live-runtime qualification. Exact source snapshots and the import stack diagnostic are preserved with it.

The second attempt passed84/90 checks with zero network attempts, but all six malformed-index endpoint checks found that the native grader itself raises `KeyError` when key count matches pathway length while the canonical final key is missing. Native transitions remain untouched. The subsequent instrumentation repair records the action and independent care failure while leaving native reward undefined with an explicit error; an observer exception no longer masquerades as a different tool outcome.

## Completed offline branch conformance — scope and limits

[branch_runtime.py](research/recovery_environment/hospital_recovery/branch_runtime.py) preserves native HospitalEnvironment and subclasses LocalCommunicationProtocol/Megaboard for research closure, new-credit neutralization and pending-care reserves. Original actors are denied before native turn/prefetch/generation and direct dispatch. An authorized active probe establishes independent closed-board protection; public source history/default board access remains. Return copies prevent branch/read aliasing. Native source ownership, partial transfers, destination aliases and multi-tool response ordering are preserved. Self/invalid-destination no-ops do not incur false reserve denials.

The observer requires exactly canonical scheduled-step keys and zero resource failures for completed care, logs malformed/denied/no-op/failed attempts, and records native score failures as undefined without changing the tool result. It does not patch native malformed-index scheduling. Native execution `post_message` dispatch remains possible despite its absent execution schema; this known mismatch is retained across branches rather than silently repaired.

The scripted client skips provider construction and retains native TogetherClient context/usage/batch methods; actual BaseAgent executes two mutating tools from one scripted response and starts eight fresh contexts over two iterations. The no-network hook remains enforced. An unused urllib3 IPv6 bind probe is suppressed only at parser import, with the socket flag restored; this is disclosed offline setup, not transport verification. No HTTP session or credential-bearing client was created.

**Results:** [attempt004](research/recovery_environment/hospital_recovery/20261024/conformance_004/results.json) passes90/90 (72 original +18 supplemental) on seeds0–5, with zero network attempts and no inference. Scripted useful-service and last-kit positive controls pass6/6; full per-seed observations, baselines/variance, intentional failures and prior failed attempts are in [RECOVERY_PROTOCOL.md](RECOVERY_PROTOCOL.md#results-offline-native-branch-conformance). Attempt001 remains failed overall; attempt002 retains six native grader exceptions. The 90 passing checks do not claim general input fuzzing, concurrency/transport safety or LLM competence.

The prototype uses control-marker boards and scripted actions; exact exploit/neutral public recommendations, the supplied care-allocation contract and care-first instructions are not implemented/frozen. No live request/retry/token/currency enforcement exists yet. Native client defaults to six retries, so the future paid path must explicitly disable/test retries. Prepare these missing inputs and runner before asking for inference authorization. The original six-dimension goal remains incomplete.
