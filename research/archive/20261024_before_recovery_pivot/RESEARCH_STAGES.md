# Research stages

Last updated: 2026-10-24 (Asia/Hong_Kong)

## Current status

**Stage 6A pilot complete; question discovery reopened with novelty and agent-community impact as the priority.**

Current objective: identify a consequential unresolved problem in harmful agent coordination before selecting another experiment or solution. The earlier communication-enforcement question is retained as a completed exploratory pilot, rather than the proposed main contribution.

Detailed question design, proposed comparisons, code observations, and open decisions are in [DIAGNOSTIC_QUESTION.md](DIAGNOSTIC_QUESTION.md).

Current preparatory study: [consolidated system map](SYSTEM_MAP.md), connecting [agent architecture](AGENT_ARCHITECTURE.md) and [context flow](AGENT_CONTEXT_FLOW.md), followed by [causal influence](CAUSAL_INFLUENCE.md).

The [novelty direction assessment](NOVEL_RESEARCH_DIRECTIONS.md) screens 16 candidates and prioritizes distributed recovery after an unsafe agreement for further overlap checking, with reciprocal-history effects on faulty-work approval as a backup. Both gaps remain unconfirmed. No architecture or task replacement has been selected.

The user proposed `llm-agent-collusion-2` if recovery is pursued. Its [environment assessment](RECOVERY_ENVIRONMENT_ASSESSMENT.md) favors Cleanup as a conditional candidate, while verifying host-authored alliance prompts and altered action mechanics that need explicit controls. No live experiment or starter-code change was made.

The [saved memory review](CONTEXT_MEMORY_REVIEW.md) and [close-prior-work assessment](MEMORY_PRIOR_WORK.md) remain supporting evidence. The [review-only memory test](MEMORY_TEST_PROTOCOL_DRAFT.md) is parked and has not been run.

## Roadmap

| Stage | Purpose | Status |
| --- | --- | --- |
| 1. Design the questions | Specify the diagnostic question, scope, outcomes, and controls. | Reopened by the user: novelty and practical agent-system impact take priority. |
| 2. Study the reasoning | Understand why prompts or code are used, their guarantees, and their tradeoffs. | Pending. |
| 3. Study related work | Compare close studies with the question and eventual diagnostic findings. | Memory review complete; recovery/verification candidate screen documented, exact overlap checks remain. |
| 4. Confirm the gap | Identify a specific unresolved issue, or revise the question if already answered. | Unconfirmed. Broad persistence, rollback, provenance and feasibility ideas have close prior work. |
| 5. Propose an approach | Select the simplest approach justified by the finding and confirmed gap. | Unselected. |
| 6. Test | Run diagnostic baselines (6A), then evaluate an approach if justified (6B). | A/B/C/D each have three complete audited sessions. [Comparison](COMPARISON_RESULTS.md) complete; no new-method evaluation or mechanism probe run. |
| 7. State results and findings | Report evidence, uncertainty, limitations, and practical implications. | Pilot report and three condition reviews complete; causal harm, generalization and novelty remain unresolved. |

The workflow can loop: question → rationale → diagnostic pilot (6A) → focused related work → gap confirmation → approach, if needed → evaluation (6B) → findings. Check obvious prior art before the pilot. A diagnostic finding can be valuable without a new method.

## Next step

Use the [direction assessment](NOVEL_RESEARCH_DIRECTIONS.md) and [Cleanup feasibility assessment](RECOVERY_ENVIRONMENT_ASSESSMENT.md) to make the recovery claim concrete: define matched mechanics, reset boundaries and the result beyond existing methods before selecting a run. Keep the memory probe parked; do not expand inference or claim novelty from the current screen. No live recovery runs or experimental task replacement are underway. Keep GPT and Modal data separate.

Keep this file short: record the roadmap, stage status, and next action. Put detailed reasoning, evidence, reading notes, and results in topic-specific documents and link them here when needed.
