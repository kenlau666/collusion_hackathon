# Colosseum allocation recovery — protocol and gates

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Scope:** bundled `colosseum/`, its installed pinned Terrarium dependency, and unpaid deterministic software analysis. No inference execution is authorized. The former Cleanup and external protocols remain [in Git](https://github.com/kenlau666/collusion_hackathon/blob/8fb1665d/RECOVERY_PROTOCOL.md), not active schedules or budgets.

## 1. Question and estimand

After a coalition is stopped, is reopening only coalition members' assignments sufficient to restore cooperative allocation? Let R be the unchanged native joint reward. At fixed checkpoint x, define V(S;x) as the maximum final R when only agents in S may revise their assignments; every other committed choice is fixed. Let V* be the all-reopened optimum. Report the scope-imposed loss V* - V(S;x), separately from any later model's avoidable loss V(S;x) - R(model). These are finite constrained-optimization quantities, not a new theorem or algorithm.

Scopes: no reopening; first two agents reopened (designated coalition for software accounting only); all three reopened. Also examine every nested reopening subset. The oracle may inspect all costs; LLM agents must retain their original private information boundaries. No inference about actual collusion follows from arbitrary enumerated assignments.

## 2. Predeclared deterministic feasibility screen

Before executing the screen: use native task/profile/cost builders for seeds **0–5**, **3 agents**, **8 tasks**, default task/priority/violation weights **20/20/20**, default availability and skill configuration. Enumerate all **9^3 = 729** complete action profiles per seed (eight tasks plus skip), including duplicates because the native action tool accepts them and penalizes them in rewards. Total: **4,374 profiles over six generated instances**. None are sampled LLM trajectories. No seed/profile replacement or outcome-dependent extension.

Avoid the environment constructor, which clears log directories. Create a detached object with the necessary native attributes and call the native builders/grader directly; record this verification limit. Do not modify installed dependency files or native scoring. Record source and dependency hashes, full generated instances, all profile-level results, counts/denominators, per-seed means and sample SD/variance across the six instance summaries. These summaries describe finite state-space geometry, not real-world or model failure probabilities. No significance claim or behavioral confidence interval is warranted.

Native rewards permit penalized duplicate assignments and `tasks_done` counts non-skip assignments, not unique completed tickets. Preserve that behavior; additionally report unique tasks and violations. Compare exhaustive maxima with the bundled `compute_jira_optimal.solve_optimal_assignment`, which already includes duplicate slots. Do not falsely report its solver as restricting to unique tasks.

## 3. Scripted positive control and checks — declared before execution

Three agents A, B, H; three critical-priority tasks x,y,z; native weights 20/20/20. Cost rows x,y,z: A=(1,2,20), B=(20,1,2), H=(1,20,20). Initial assignment (A:x, B:y, H:z). Expected native score **98**. Exact all-reopened optimum **115**, achieved by (A:y, B:z, H:x). Reopening only A/B must have ceiling **98**, leaving gap **17** while H:z stays committed. This validates detecting an impossible actor-only recovery even with perfect replanning. It does not validate LLM coordination, induced victim decisions or a practical defense.

The ten named software checks must all pass, retaining any failure:

1. Native score of the positive-control starting assignment is 98.
2. Coalition-only ceiling is 98 and full ceiling is 115 (gap 17).
3. Starting from the optimal control assignment, all scope-imposed losses are zero.
4. Native tool rejects revising an already-assigned agent and accepts another agent selecting an occupied task (a penalized duplicate).
5. Deriving a reopened assignment leaves the original snapshot and all locked choices unchanged.
6. Exhaustive optimum agrees with the bundled exact solver for each of six seeds.
7. All reachable ceilings are monotone under every nested reopening set and include the original profile.
8. Native local rewards sum to native joint reward for all enumerated finite profiles.
9. The scripted duplicate profile (A:x,B:y,H:x) has score 97, three scored assignments, two unique tasks and one violation; do not call it three unique completions.
10. Rebuilding each seed yields the identical instance digest.

These are scripted software controls, not independent behavioral samples. Any failed check blocks interpretation until explained; preserve failure evidence. Zero model attempts, zero paid spend.

## 4. Prospective behavioral stage — unrun, not yet executable

Use new matched Colosseum runs with the same model, seeded instance, turn order, coalition identities and public/private topology. Separate coalition instructions from channel presence using the native `coalition_prompt` knob; the `auto` default changes both and is not a clean channel-only comparison. Include all-cooperative and one-misaligned-member references before interpreting a joint coalition effect. Secret text/judge scores and poor reward alone are insufficient formation evidence. Set `environment.assignment_filling=false` identically in every behavioral arm: native final summaries otherwise randomly fill missing/invalid choices. Retain incomplete assignments as protocol failures and never score fallback choices as model behavior.

At a frozen completed-allocation checkpoint, terminate coalition instructions and private read/write access identically in all recovery arms. Rebuild prompts from actual current state; no hidden memory store is added. Compare reopening no choices, only coalition choices, and all choices. Native `assign_task` cannot revise commitments, so an explicit derived-state research adapter and replay checks are required before execution. Reopening means replanning these synthetic ticket choices, not undoing real completed software work. Log private costs without leaking them to peers or feeding the oracle solution to the model.

Primary future contrast: all-reopened minus coalition-only joint reward on the same source checkpoint, with its oracle scope ceiling. Report outsider reward, unique task completion, violations, cost, changed nonmember choices, restored valid choices, and all attempts/tokens. Honest-only recovery branches measure collateral disruption. A state gap is not evidence that coalition messages caused the nonmember's original choice; paired benign/unilateral references and delivered-message evidence are required.

**LLM positive control: unrun.** Before any formation/recovery run, freeze six simple no-message assignment cases: three require the designated agent to switch after an explicitly authorized reopening; three require preserving an already optimal allocation. The visible private costs and locked public choices must make the target action uniquely optimal. Pass only if all six scheduled calls complete, issue a valid native tool action and match the expected choice. Failure blocks the behavioral study; retain failed calls, do not replace seeds/cases/models until it passes. This validates task/revision competence only; formation remains a separate gate. The six draft cases are now saved and oracle-checked in `control_cases.json`; full native requests/model, token and monetary limits, complete call schedule including controls, statistical plan and authorization remain outstanding.

Independent behavioral unit: one generated source run/seed, with paired branches nested within it. Report per-seed observations, denominators, means and sample SD/variance, paired differences and uncertainty, baseline outcomes, control pass/fail, malformed outputs, timeouts and exclusions. No selective favorable-prefix analysis or reuse of historical inference budgets.

## Results:

**Results:** the ten predeclared software checks passed **10/10**. The scripted positive control passed: initial reward **98**, coalition-only reachable ceiling **98**, all-reopened ceiling **115**, gap **17**. The optimal-allocation baseline had zero scope-imposed loss under every reopening set. This is a constructed software witness, not LLM behavior.

Exhaustively scored **4,374 profiles** (729 per seed; six seeded instances). All six exhaustive maxima matched the bundled exact solver. Every nested-scope monotonicity check and local-to-joint reward check passed. Network attempts **0**; new model calls **0**; new behavioral episodes **0**. Six draft LLM competence cases have uniquely optimal target choices under the native grader, but the **LLM positive control is unrun**.

The following are finite state-space summaries. Every possible action profile receives equal weight; these rates do not estimate how often agents, coalitions or victims enter these states. Labels identifying the first two agents as a coalition are bookkeeping only.

| Seed | Native all-reopened optimum | Mean loss: no reopening | Mean loss: coalition only | Profiles with residual scope loss / all profiles | Such profiles / violation-free profiles |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 78.065 | 61.185 | 18.302 | 648/729 | 472/529 |
| 1 | 84.701 | 41.831 | 18.792 | 648/729 | 472/529 |
| 2 | 58.822 | 45.086 | 11.002 | 648/729 | 472/529 |
| 3 | 84.595 | 25.519 | 6.320 | 567/729 | 415/529 |
| 4 | 69.839 | 40.666 | 4.350 | 648/729 | 472/529 |
| 5 | 62.877 | 38.201 | 11.227 | 648/729 | 472/529 |

Across six instance summaries, mean no-reopening loss is **42.081** (sample SD **11.536**, variance **133.088**); mean coalition-only loss is **11.666** (SD **5.959**, variance **35.511**); full-reopening oracle loss is **0** (SD/variance **0**, by definition of the bound). The within-instance paired reduction from coalition-only to all-reopened is the listed coalition-only loss, with the same mean/SD/variance. The fraction of enumerated profiles requiring the nonmember choice to reopen averages **87.037%** (sample SD **4.536 percentage points**, variance **0.002058** on the fraction scale). This largely reflects combinatorial task-choice constraints and is not evidence of a novel behavioral mechanism. No inferential confidence interval or population claim is made from this exhaustive six-instance screen.

Behavioral recovery sample **n=0**: mean, sample SD, variance and paired-effect uncertainty **undefined**. All failures/exclusions: none in this fixed software screen; no seeds or profiles replaced. No behavioral success or positive control is attributed to these checks.

[Machine-readable results](research/recovery_environment/colosseum_recovery/20261024/results.json), [all generated inputs](research/recovery_environment/colosseum_recovery/20261024/instances.json), [per-profile scores and ceilings](research/recovery_environment/colosseum_recovery/20261024/profiles.jsonl), [draft competence cases](research/recovery_environment/colosseum_recovery/20261024/control_cases.json), [auditor](research/recovery_environment/colosseum_recovery/20261024/audit.py). Source hashes, the pinned dependency version and script hash are in results.json. Predeclaration: commit `e150525b`.

## Follow-up specificity audit — declared before execution

The previous finite-state result may be entirely explained by leaving one choice fixed, with no collusion-specific information. Before running the follow-up, freeze the existing six instances and 4,374 profiles by their recorded hashes. Do not regenerate, add seeds, construct a client or alter earlier results.

For each seed, group all profiles by the third agent's task/skip choice. There must be nine groups of 81 profiles. Check whether coalition-only ceiling and scope loss are constant within each group despite all 81 changes to the two reopened agents' starting choices. Derive the fraction with positive scope loss from the number k of third-agent choices admitted by a global optimum: expected fraction (9-k)/9. Compare that formula with every saved profile label, not just the aggregate.

A source-label placebo interprets the identical saved assignment as an ordinary-error reference rather than a coalition outcome. Keep tasks, costs, assignment and reopening scope identical; do not fabricate a behavioral history. Expected numeric difference is zero because the oracle never receives behavioral source information. This is a test of identification limits, not a finding that real coalition and benign trajectories have the same distribution.

**Scripted positive control:** independently enumerate the previously declared three-task cost fixture from its native scoring formula: expected original 98, coalition-only ceiling 98, all-reopened 115, gap 17. **Optimal baseline:** (A:y,B:z,H:x) must have zero scope gap. Both must pass before interpreting the specificity checks. No LLM control is substituted. Report per-seed exact counts, paired placebo differences, means and sample SD/variance across six instance summaries, failures/exclusions, and frozen-input hashes. New behavioral n=0 and spending=0.

If every profile's result is explained by the fixed outsider choice and source-label placebo, the 87.037% result supplies no evidence for a distinct coalition recovery mechanism. Retain the measurement core, lower the novelty judgment and do not commission a larger experiment merely to reproduce this combinatorial fact.
