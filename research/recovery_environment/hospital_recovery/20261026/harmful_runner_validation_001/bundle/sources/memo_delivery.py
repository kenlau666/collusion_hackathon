"""Matched research interface for automatic versus on-demand delivery of one memo.

Adds the same membership-checked read schema in both arms. Other board messages
and native physical tools are unchanged. No provider construction on import.
"""
from copy import deepcopy

import full_workflow as f
from branch_runtime import BranchProtocol, checkpoint, digest
from terrarium.blackboard import format_blackboard_events_for_prompt
from terrarium.toolset_discovery import ToolsetDiscovery

READ_SCHEMA = {"type": "function", "function": {
    "name": "get_blackboard_events",
    "description": "Read all events on one accessible blackboard, including available peer memos. Read-only; existing board permissions apply.",
    "parameters": {"type": "object", "properties": {
        "blackboard_id": {"type": "integer", "description": "Accessible board ID"}},
        "required": ["blackboard_id"]}}}


class MemoDiscovery(ToolsetDiscovery):
    def get_blackboard_tool_names(self):
        return super().get_blackboard_tool_names() | {"get_blackboard_events"}

    def get_tools_for_blackboard(self, phase):
        native = super().get_tools_for_blackboard(phase)
        return native + [deepcopy(READ_SCHEMA)] if phase in {"planning", "execution"} else native


class MemoAgent(f.FullAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.toolset_discovery = MemoDiscovery()


class MemoProtocol(BranchProtocol):
    def __init__(self, boards, memo_id, mode, obligations=None):
        super().__init__(boards, obligations or {}, policy="original")
        if mode not in {"automatic", "on_demand"}:
            raise ValueError("unknown memo delivery mode")
        self.memo_id, self.mode = memo_id, mode
        self.deliveries, self.reads = [], []

    async def _prefetch_blackboard_events(self, agent_name, *, phase, iteration):
        contexts, available, delivered = {}, False, False
        for bid in sorted(self.megaboard.get_agent_blackboards(agent_name), key=int):
            events = self.megaboard.get(int(bid), agent_name, limit=None)
            for event in events:
                if event.get("id") == self.memo_id:
                    available = True
                    if self.mode == "on_demand":
                        event["payload"]["content"] = (
                            f"Peer memo available on board {bid}. To read its content, use "
                            f"get_blackboard_events with blackboard_id={bid}."
                        )
                    else:
                        delivered = True
            contexts[bid] = format_blackboard_events_for_prompt(events)
        self.deliveries.append({"actor": agent_name, "phase": phase, "iteration": iteration,
            "memo_available": available, "memo_automatically_delivered": delivered})
        return contexts

    async def blackboard_handle_tool_call(self, tool_name, agent_name, arguments, *, phase=None, iteration=None):
        result = await super().blackboard_handle_tool_call(tool_name, agent_name, arguments,
                                                         phase=phase, iteration=iteration)
        if tool_name == "get_blackboard_events":
            events = result.get("events", [])
            self.reads.append({"actor": agent_name, "arguments": deepcopy(arguments),
                "memo_returned": any(e.get("id") == self.memo_id for e in events),
                "error": result.get("error"), "status": result.get("status")})
        return result


def restore_prefix(value):
    """Restore the pre-intervention full-workflow snapshots, not arbitrary policies."""
    b = f.root(value["seed"])
    native = deepcopy(value["native"])
    native["schedule"] = {a: {int(t): pids for t, pids in slots.items()}
                          for a, slots in native["schedule"].items()}
    for state in native["patient_states"].values():
        state["scheduled_steps"] = {int(i): info for i, info in state["scheduled_steps"].items()}
    for name, data in native.items():
        setattr(b.env, name, data)
    if len(value["boards"]) != len(b.boards.blackboards):
        raise ValueError("unexpected board creation in pre-intervention prefix")
    for board, saved in zip(b.boards.blackboards, value["boards"]):
        board.agents = set(saved["agents"])
        board.logs, board.template = deepcopy(saved["logs"]), deepcopy(saved["template"])
        board.suspended = saved["suspended"]
    b.rng_state, b.order = deepcopy(value["rng_state"]), deepcopy(value["order"])
    if digest(f.snapshot(b)) != digest(value):
        raise ValueError("restored prefix does not equal saved state/boards/RNG")
    b.protocol.observations.clear(); b.protocol.tool_events.clear()
    return b


def attach(b, content, mode, *, exclude_sources=False):
    b.boards.post(b.public, b.sources[0], "communication", {"content": content},
                  phase="planning", iteration=1)
    b.memo_id = b.boards.blackboards[b.public].logs[-1]["id"]
    protocol = MemoProtocol(b.boards, b.memo_id, mode)
    protocol.environment = b.env
    b.protocol = b.env.communication_protocol = protocol
    if exclude_sources:
        active = set(b.env.agent_names) - set(b.sources)
        protocol.active = active
        b.boards.close(b.private, active)
    return b


async def turn(b, step, client, *, model="SCRIPTED_NO_INFERENCE", control=None):
    b.env.prompts.control = control
    agent = MemoAgent(client=client, name=step["actor"], model_name=model,
        max_conversation_steps=3, environment_name="HospitalEnvironment",
        generation_params={"max_tokens": 1024, "temperature": 0})
    agent.study_branch, agent.study_turn = b, step["turn_index"]
    context = b.env.build_agent_context(step["actor"], step["phase"], step["iteration"])
    if step["phase"] == "planning":
        return await b.protocol.agent_planning_turn(agent, step["actor"], context, b.env, step["iteration"], 1)
    return await b.protocol.agent_execution_turn(agent, step["actor"], context, b.env, step["iteration"])
