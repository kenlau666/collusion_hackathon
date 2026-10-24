# Research stages — recovery in Cleanup

Last updated: 2026-10-24 (Asia/Hong_Kong).

## Current direction

**Selected:** recovery from harmful coordination in Cleanup, within llm-agent-collusion-2.

**Question:** After revoking a private coordination channel, does clearing participants' retained context further reduce harm, and what does that cost useful cooperation?

The [current project document](DIAGNOSTIC_QUESTION.md) replaces the old enforcement plan and explains the pivot. The [protocol](RECOVERY_PROTOCOL.md) specifies six recovery conditions, measurements, selection, accounting and interpretation limits. The [editable architecture diagram](mermaid-diagram.mmd) and [system map](SYSTEM_MAP.md) distinguish existing software from planned changes.

## Status

| Stage | Status |
| --- | --- |
| 1. Define the question | Recovery direction selected; bounded test and primary contrast proposed. |
| 2. Study the system and rationale | Cleanup code traced; offline routing, privilege, seed and observation probes passed. |
| 3. Review closest work | Relevant persistence/recovery methods identified; exact novelty comparison still required. |
| 4. Confirm the gap | Unconfirmed. Setting selection is not a novelty claim. |
| 5. Specify the approach | Neutral, equal-rules variant and six recovery arms designed; no new defense selected. |
| 6. Implement and test | Research adapter pending; no live recovery inference run. |
| 7. Report findings | Software observations documented; behavioral recovery, harm reduction and generalization unestablished. |

## Documents

- [Current question and pivot rationale](DIAGNOSTIC_QUESTION.md).
- [Experiment protocol and measurements](RECOVERY_PROTOCOL.md).
- [Repository assessment and verified software observations](RECOVERY_ENVIRONMENT_ASSESSMENT.md).
- [Architecture](AGENT_ARCHITECTURE.md), [context flow](AGENT_CONTEXT_FLOW.md), [controls](SYSTEM_MAP.md), [causal interpretation](CAUSAL_INFLUENCE.md).
- [Closest prior work and novelty gate](NOVEL_RESEARCH_DIRECTIONS.md).

## Next action

Implement and validate the research adapter and complete the novelty overlap check. Freeze the request configuration, sample schedule and spending/time gates before dispatching a live feasibility study.

The earlier auction experiment is completed pilot evidence in [COMPARISON_RESULTS.md](COMPARISON_RESULTS.md). Its planning versions are [archived](research/archive/20261024_before_recovery_pivot/manifest.json). The earlier memory probe is parked. The requested diagram deliverable is Mermaid source; the PNG is not being changed.
