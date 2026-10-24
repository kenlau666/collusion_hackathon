# Agent architecture — Cleanup recovery study

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Scope:** the selected Cleanup study in llm-agent-collusion-2. This replaces the old auction-oriented architecture notes. Earlier versions are [archived](research/archive/20261024_before_recovery_pivot/manifest.json).

The [Mermaid file](mermaid-diagram.mmd) is the editable diagram. Its solid paths describe inspected software responsibilities; dashed paths show proposed research additions. [RECOVERY_PROTOCOL.md](RECOVERY_PROTOCOL.md) is authoritative for the experiment design.

## Model and harness

The model receives application-constructed inputs and produces text. The surrounding harness selects messages, retains limited peer context, checks channel access, parses actions and applies them to the world. Resetting one harness object does not automatically reset another.

| Component | Inspected responsibility | Recovery implication |
| --- | --- | --- |
| Model service | Stateless calls at the application interface using system and user messages. No server-managed conversation continuation is supplied by this client. | Context cleanup changes supplied text; it is not weight editing or evidence that the provider's internal state was erased. |
| Agent-local fields | Alliance flag, partner cache, recent messages and latest action_context. | A local reset can clear these fields; there is no inspected general long-term memory manager. |
| Context builder | Combines rules, observations and selected context; the starter also adds alliance coaching. | Verify the actual first input after a reset. Stored text and delivered input are different evidence. |
| Channel registry | Tracks active status, participants and messages. | Revoking here must stop future delivery in both directions. Local text cleanup does not revoke access. |
| Private exchange scheduler | Explicit host calls for messages and replies before action generation. | These are separate model calls, not a universal model-selected tool/delegation interface. |
| Action parser | Extracts actions and applies fallback behavior; the starter prefers zaps among candidates. | Model output is not the executed action. Log both and fix parsing across conditions. |
| Environment | Positions, apples, pollution, freezes, scores and alliance-dependent privileges in the starter. | Keep physical rules identical across study arms. A new agent does not undo existing freezes or restore lost apples. |
| Tournament manager | Recreates agents/games and re-establishes selected coalition metadata. | Do not equate its cross-game restoration with learned private memory. |
| Recovery controller | **Proposed:** checkpoint, branch edits and continuation dispatcher. | Must operate between completed environment steps, with defined access/state boundaries. |
| Event recorder | **Proposed:** exact requests/delivery, per-target action events, metrics and accounting. | Needed to connect software controls, behavior and outcomes. |

## Planned common architecture changes

The research adapter will provide neutral common prompts, ordinary directional zap rules for everyone, literal peer text, strict action handling, correct observations and isolated environment randomness. These changes are common to every arm from the beginning. They are not implemented by this documentation update.

Live grants are authoritative host state; retained peer text is historical agent context. The current grant description must remain accurate after every treatment. Clearing an agent's context preserves identity, goal, current observations and the interface it is presently permitted to use.

No shared editable memory, filesystem tool ecosystem, delegated subagents, learned scratchpad or hidden thought-state transfer is assumed. A later architectural extension would be a separate declared study.

## Boundaries investigated

The six conditions vary two things: whether new private messages can be delivered, and whether one or both participants retain old peer-derived context. The main contrast is revocation alone against revocation plus two-participant context cleanup.

World consequences remain at the checkpoint. A full tested context cleanup is not a full world restart, model retraining or a permanent recovery guarantee.

## Evidence

The [source assessment](RECOVERY_ENVIRONMENT_ASSESSMENT.md) and [offline probe](research/recovery_environment/offline_audit.json) establish routing/state facts with scripted responses and blocked provider/network access. They do not demonstrate behavioral recovery in LLMs.

The possible novelty lies in a consequential, verified recovery boundary and safety/utility tradeoff, not the invention of context deletion or access revocation. [Closest work](NOVEL_RESEARCH_DIRECTIONS.md) remains a required comparison.
