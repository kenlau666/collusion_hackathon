# Context flow — Cleanup recovery study

Last updated: 2026-10-24 (Asia/Hong_Kong).

**Scope:** current study in llm-agent-collusion-2/Collusion_Cleanup. The old auction trace is [archived](research/archive/20261024_before_recovery_pivot/manifest.json). See [SYSTEM_MAP.md](SYSTEM_MAP.md), [architecture](AGENT_ARCHITECTURE.md) and [protocol](RECOVERY_PROTOCOL.md).

## Inspected routing

1. The host selects a channel participant in the step loop and requests a private message through get_tool_response. The tool-interaction call has its own system/user input.
2. The selected peer receives a separate response request containing the sender's text. This is another inference, not access to the sender's hidden neural state.
3. The starter extracts intention strings with regexes, then writes peer-derived text into action_context and recent_secret_messages.
4. The action path renders current world observations. When the local alliance flag and context are present, it adds an alliance context section and commands; the system prompt also depends on the local flag.
5. The client sends system and user messages. The response is parsed into an action; four agents' actions are applied to the environment.
6. The next model calls receive observations from the new world. The private exchange and action generation are separate calls.

Sources: games/secret_channel.py, agents/llm_agent.py, agents/prompts.py and agents/llm_client.py. Exact source hashes are in [the audit output](research/recovery_environment/offline_audit.json).

The host's private-message log is not automatically a replayed conversation. A field called recent messages does not establish that all those messages are supplied. The inspected action path mainly uses the latest action_context.

## Proposed research routing

The research adapter will deliver bounded literal peer text as data rather than regex-generated intention labels. It will remove host-authored attack coaching. These are declared common changes to the research variant, not current starter behavior.

The authority to deliver messages will come from the host registry. Context cleared in R1/R2 can be repopulated by newly permitted messages. R3/R4/R5 must block all new private deliveries; only the specified resets remove old context.

Every inference record must contain its call type, agent ID, step/phase, complete supplied envelope, backend/settings, raw response, parsed action/message, delivery result and provenance. The observer may retain logs that the agent no longer receives.

## What is private and shared

| Information | Recipient access |
| --- | --- |
| World observations | The environment supplies each agent with public grid, positions, scores and legal actions. |
| Private peer text | Delivered only to the selected pair when permitted; actual delivered content must be logged. |
| Agent-local context | Returned to that agent through context assembly; peers do not automatically read it. |
| Channel membership | Host-held metadata used for routing; the research adapter gives an accurate interface description. |
| Audit logs | Observer records; not additional model context unless explicitly supplied. |
| Model weights | May be the same service across agents; separate calls do not share their local supplied histories automatically. |

## Executed offline checks and limits

The [reproducible fixture](research/recovery_environment/audit_local.py) uses actual source methods, scripted responses and blocked network/provider-client construction. It verifies:

- Clearing recent text while retaining the flag leaves alliance system instructions.
- Local reset clears the agent's fields but leaves the external channel and world membership.
- An active channel can issue a fresh alliance-framed interaction after that reset and repopulate action_context; it does not restore the local flag.
- Disabling the channel leaves world membership. Membership changes actual zap effectiveness in the starter.
- The wrapper's requested seeds can lead to identical initial observations; actual freeze state is omitted from the observation field used by the formatter.

These are software observations, not real-model agreement, influence, harmful coordination or recovery findings. No live recovery inference has run. The proposed literal-text routing still needs its own executed verification after implementation.
