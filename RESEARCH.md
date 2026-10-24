# Recovery beyond the coalition in Colosseum

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Selected repository-based approach:** use the bundled `colosseum/` Jira allocation environment to ask: **after a coalition is stopped, can repairing only its members restore the cooperative outcome, or must decisions made by other agents also be reopened?** The user authorized changing the approach and required using bundled projects. The unsuccessful Cleanup configuration remains stopped; the external SALT-NLP proposal is parked.

The proposed contribution is an empirical boundary of actor-targeted recovery, not a new memory mechanism or rollback algorithm. We will distinguish loss that is unavoidable under a fixed repair scope from loss caused by poor replanning. Removing a private channel or replacing an agent does not itself revise the committed task assignments in this implementation.

**Current status:** design selected; predeclared deterministic feasibility screen completed, 10/10 software checks passed. No LLM formation result, behavioral recovery effect or passing LLM positive control is yet available for this approach. No new inference budget is authorized. The previous approach's scores do not transfer. All-8 has not been achieved.

## What changes

Replace the memory-deletion question with a question about **which agents' decisions must be revisable**. At the same completed allocation, compare no reopening, reopening only the two coalition members' assignments, and reopening all assignments. All future behavioral branches stop the coalition instructions/channel in the same way; only the reopening scope varies. A research adapter would be needed because the native tool forbids an already-assigned agent from revising its choice.

First compute the best score reachable under each scope with the native grader. An omniscient oracle is a measurement bound, not a deployable defense. If even the best possible coalition-only revision cannot reach the cooperative optimum, no better prompt to those members can close that gap while other assignments remain fixed. This is an allocation boundary, not proof of a memory-mediated convention or collusion.

Later behavioral evidence must show that the relevant nonmember choices were caused by coalition behavior rather than ordinary error. Include matched all-cooperative and unilateral-misalignment references, retain failed formation seeds, and report valid unique task completion and outsider rewards alongside joint reward. If the same phenomenon is entirely ordinary error propagation already explained by prior work, report that and do not claim a new collusion mechanism.

## Skill and candidate decisions

Applied [Orchestra Research Idea Brainstorming v1.0.0 at commit 773a52944ba4747a18bd4ae9ade53fff041adcbc](https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/773a52944ba4747a18bd4ae9ade53fff041adcbc/21-research-ideation/brainstorming-research-ideas/SKILL.md). Problem-first: an operator stops the culprit actors but needs the whole task to recover. Failure-analysis: separate committed state from model input and feasible recovery from model competence. Simplicity: use existing finite tasks, rewards and an exact bound before building a defense.

| Repository-based candidate | Decision |
| --- | --- |
| Repeat Cleanup offers | Reject: failed feasibility; user stopped this configuration. |
| Add long-term memory to Cleanup | Reject: manufactures the mechanism and overlaps memory ablations. |
| Delete Colosseum's private blackboard | Reject as contribution: ordinary channel intervention, with public spillover left uncontrolled. |
| Clear all public messages | Reject as contribution: source/dependency cleanup is established. |
| Correct recipients' false beliefs | Park: strong overlap with misinformation propagation and repair literature. |
| Clear only private reflections | Reject: native Colosseum turns do not establish this retained state. |
| Replace the market participant/model | Reject as contribution: bundled llm-cartel already branches these replacements. |
| Market defection/punishment audit | Park: historical auction direction and close new enforcement-audit work. |
| Change coalition rewards | Park: changes the threat and already has close ablations. |
| Label secret language versus harmful action | Reject as contribution: Colosseum already establishes this distinction. |
| Separate unilateral harm from coalition effects | Required behavioral baseline; factorial comparison itself is established. |
| **Measure recovery limits by whose decisions can reopen** | **Selected conditional empirical question:** native committed state supplies a real intervention boundary; novelty remains provisional. |

[Architecture and code limits](ARCHITECTURE.md), [protocol and controls](RECOVERY_PROTOCOL.md), [closest overlaps](RELATED_WORK.md). The external screen and its 8,8,8,6,8,6 judgments are preserved [at 8fb1665d](https://github.com/kenlau666/collusion_hackathon/blob/8fb1665d/RESEARCH.md); they are not ratings for this approach. The retired Cleanup audit is preserved [at 4580fdf3](https://github.com/kenlau666/collusion_hackathon/blob/4580fdf3/RESEARCH.md).

## Current ratings and next gate

These are judgments against the same six dimensions, not measurements or guarantees. No extra rewrite can establish behavioral sensitivity or an important new result.

| Dimension | /10 | Basis and limit |
| --- | ---: | --- |
| Operator problem | 8 | Remediating culprit actors versus restoring the whole allocation is a concrete recovery-scope decision. |
| Architecture audit and evidence discipline | 8 | Native commit/input/reward paths, exact solver and finite software checks audited; full client and live branching remain unverified. |
| Conditional causal design | 7 | Same-checkpoint scope contrast and reachable bounds are clear; induced nonmember decisions, matched references, native replay and the final inference schedule remain unresolved. |
| Behavioral readiness | 4 | Native software works and six draft competence cases are oracle-checkable; no LLM control or eligible coalition trajectory exists for this approach. |
| Useful-cooperation construct | 8 | Unique tasks, outsider rewards, duplicate penalties, decision changes and honest-only collateral-disruption baselines are explicit; behavioral preservation is unestimated. |
| Demonstrated novelty | 6 | Actor-targeted versus task-level recovery is a candidate empirical distinction; selective rollback, propagated-state repair and paired recovery are established. The software witness is insufficient to establish a new collusion finding. |

**The all-8 target is not met.** The approach now has a concrete repository-native question and an executable unpaid measurement core, not a claimed new defense. The next informative step is a bounded behavioral qualification/formation study with benign and unilateral references, then matched recovery only if qualifying states occur. Freeze the exact model, native requests, client/state compatibility and a complete spending schedule before execution; do not reuse old budgets. No paid inference is currently authorized. The six-instance enumeration does not justify expanding it or pretending the remaining scores are 8.

If behavioral qualification fails or the harm is explained by ordinary single-agent errors, stop the collusion-specific claim. If a close prior study already tests the same actor-targeted recovery boundary, abandon the novelty claim instead of renaming it. The precise overlapping literature and unresolved lead are in [RELATED_WORK.md](RELATED_WORK.md).

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
