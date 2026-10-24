# Recovery beyond the coalition in Colosseum

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Selected repository-based approach:** use the bundled `colosseum/` Jira allocation environment to ask: **after a coalition is stopped, can repairing only its members restore the cooperative outcome, or must decisions made by other agents also be reopened?** The user authorized changing the approach and required using bundled projects. The unsuccessful Cleanup configuration remains stopped; the external SALT-NLP proposal is parked.

The proposed contribution is an empirical boundary of actor-targeted recovery, not a new memory mechanism or rollback algorithm. We will distinguish loss that is unavoidable under a fixed repair scope from loss caused by poor replanning. Removing a private channel or replacing an agent does not itself revise the committed task assignments in this implementation.

**Current status:** design selected; deterministic feasibility screen predeclared in [RECOVERY_PROTOCOL.md](RECOVERY_PROTOCOL.md). No feasibility result, LLM formation result, recovery effect or passing behavioral positive control is yet available for this approach. No new inference budget is authorized. The previous approach's scores do not transfer. All-8 has not been achieved.

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

## Results:

New model calls: **0**. New behavioral episodes: **0**. Behavioral positive control: **unrun**. Recovery effect: **n=0; mean, sample SD and variance undefined**. The deterministic screen and its scripted positive control have not yet executed. Historical Cleanup and external audits are preserved and are not controls for this system.
