"""Research-only Hospital branch adapters; no provider construction or run CLI.

This module uses native Terrarium classes. ScriptedChatClient replaces generation
only; TogetherClient's actual context, usage and batch parser methods are retained.
It does not qualify any LLM or provide a production security boundary.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "colosseum"))

from experiments.common.local_protocol import LocalCommunicationProtocol
from envs.dcops.hospital.hospital_env import HospitalEnvironment
from llm_server.clients.together_client import TogetherClient
from terrarium.agents.base import BaseAgent
from terrarium.blackboard import Megaboard

FROZEN = Path(__file__).parent / "20261024/fixtures.json"
PHYSICAL_FIELDS = ("inventory", "schedule", "patient_states", "resource_failures", "hospital_failures")


def digest(value):
    # JSON round-trip normalizes int dictionary keys in native versus saved state.
    value = json.loads(json.dumps(value))
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def physical(env):
    return {key: deepcopy(getattr(env, key)) for key in PHYSICAL_FIELDS}


def checkpoint(env):
    return {**physical(env), **{key: deepcopy(getattr(env, key)) for key in
            ("patients", "agents_map", "transfer_rewards", "transfer_rewards_by_agent")}}


def care(env):
    return {pid: int(len(env.patient_states[pid]["scheduled_steps"]) == len(p["pathway"])
                     and not env.patient_states[pid]["resource_failures"])
            for pid, p in env.patients.items()}


def score(env):
    return env._calculate_makespan_and_flow()[0]


def restore(seed):
    record = next(r for r in json.loads(FROZEN.read_text()) if r["seed"] == seed)
    cfg = {"environment": {"num_hospitals": 2, "num_patients": 2},
           "simulation": {"seed": seed, "run_timestamp": "20261024_branch_conformance"}}
    env = HospitalEnvironment(SimpleNamespace(), cfg, None)
    saved = deepcopy(record["constructed_frontier"])
    saved["schedule"] = {a: {int(t): ps for t, ps in slots.items()}
                         for a, slots in saved["schedule"].items()}
    for p in saved["patient_states"].values():
        p["scheduled_steps"] = {int(k): v for k, v in p["scheduled_steps"].items()}
    for key, value in saved.items():
        setattr(env, key, value)
    assert digest(checkpoint(env)) == digest(record["constructed_frontier"])
    return env, record


class GuardedBoards(Megaboard):
    """Read/write closure at native agent-access methods; host is trusted."""
    def __init__(self):
        super().__init__()
        self.allowed = None
        self.closed = set()

    def authorize(self, actor, board_id=None):
        if self.allowed is not None and actor not in self.allowed:
            raise PermissionError("actor excluded")
        if board_id is not None and int(board_id) in self.closed:
            raise PermissionError("board closed")

    def get(self, blackboard_id, agent, limit=None):
        self.authorize(agent, blackboard_id)
        return deepcopy(super().get(int(blackboard_id), agent, limit))

    def post(self, blackboard_id, agent, kind, payload=None, phase=None, iteration=None):
        self.authorize(agent, blackboard_id)
        return super().post(int(blackboard_id), agent, kind, payload, phase, iteration)

    def get_agent_blackboards(self, agent_name):
        self.authorize(agent_name)
        return [b for b in super().get_agent_blackboards(agent_name) if int(b) not in self.closed]

    def get_blackboard_by_string_id(self, blackboard_id):
        try:
            board_id = int(blackboard_id)
        except (ValueError, TypeError):
            return None
        if board_id in self.closed:
            return None
        return super().get_blackboard_by_string_id(blackboard_id)

    def close(self, board_id, allowed):
        self.closed.add(int(board_id))
        self.blackboards[int(board_id)].suspended = True
        self.allowed = set(allowed)


class BranchPrompts:
    def __init__(self, native, policy):
        self.native, self.policy = native, policy

    def get_system_prompt(self):
        text = self.native.get_system_prompt()
        return text.replace("+15", "+0") if self.policy == "bonus_zero" else text

    def get_user_prompt(self, agent_name, agent_context, blackboard_context):
        text = self.native.get_user_prompt(agent_name, agent_context, blackboard_context)
        if self.policy == "bonus_zero":
            text = text.replace("for a reward", "for redistribution")
        return text


class BranchProtocol(LocalCommunicationProtocol):
    def __init__(self, boards, obligations, policy="original"):
        super().__init__(config={}, megaboard=boards)
        self.active = None
        self.obligations = obligations
        self.policy = policy
        self.observations = []

    def reserve(self, hospital, resource):
        env = self.environment
        total = 0
        for pid in self.obligations[hospital]:
            step = env.patients[pid]["pathway"][-1]
            if step["step_index"] not in env.patient_states[pid]["scheduled_steps"]:
                total += env.consumption_map[step["service"]].get(resource, 0)
        return total

    def _denied(self, actor):
        return self.active is not None and actor not in self.active

    def _record_denial(self, tool, actor, arguments, phase, iteration, reason):
        result = {"status": "denied", "error": reason}
        self._record_tool_event(tool_name=tool, agent_name=actor, arguments=arguments,
                                result=result, phase=phase, iteration=iteration)
        return result

    async def environment_handle_tool_call(self, tool_name, agent_name, arguments,
                                           *, phase=None, iteration=None):
        env = self.environment
        before = checkpoint(env)
        reason = "actor excluded" if self._denied(agent_name) else None
        if reason is None and self.policy == "reserve" and tool_name == "transfer_resources":
            h = env.agents_map[agent_name]["hospital"]
            resource = arguments.get("resource_type")
            stock = env.inventory[h].get(resource, 0)
            requested = arguments.get("amount", 0)
            actual = min(requested, stock)
            if actual > 0 and stock - actual < self.reserve(h, resource):
                reason = "pending-care reserve"
        if reason:
            result = self._record_denial(tool_name, agent_name, arguments, phase, iteration, reason)
        else:
            # Native tools, state application, logging and secret-board scrubbing.
            result = await super().environment_handle_tool_call(
                tool_name, agent_name, arguments, phase=phase, iteration=iteration)
            if self.policy == "bonus_zero":
                env.transfer_rewards = before["transfer_rewards"]
                env.transfer_rewards_by_agent = deepcopy(before["transfer_rewards_by_agent"])
        after = checkpoint(env)
        joint, local = env._calculate_makespan_and_flow()
        self.observations.append({"actor": agent_name, "tool": tool_name, "arguments": deepcopy(arguments),
            "phase": phase, "status": result.get("status", "native"),
            "before": before, "after": after, "joint_reward": joint,
            "local_sum": sum(local.values()), "care": care(env)})
        return result

    async def blackboard_handle_tool_call(self, tool_name, agent_name, arguments,
                                          *, phase=None, iteration=None):
        if self._denied(agent_name):
            return self._record_denial(tool_name, agent_name, arguments, phase, iteration, "actor excluded")
        return await super().blackboard_handle_tool_call(
            tool_name, agent_name, arguments, phase=phase, iteration=iteration)

    async def agent_planning_turn(self, agent, agent_name, *args, **kwargs):
        if self._denied(agent_name):
            return {"status": "denied", "error": "actor excluded before generation"}
        return await super().agent_planning_turn(agent, agent_name, *args, **kwargs)

    async def agent_execution_turn(self, agent, agent_name, *args, **kwargs):
        if self._denied(agent_name):
            return {"status": "denied", "error": "actor excluded before generation"}
        return await super().agent_execution_turn(agent, agent_name, *args, **kwargs)

    async def agent_survey_turn(self, agent, agent_name, *args, **kwargs):
        if self._denied(agent_name):
            return {"status": "denied", "error": "actor excluded before generation"}
        return await super().agent_survey_turn(agent, agent_name, *args, **kwargs)


class ScriptedChatClient(TogetherClient):
    """No super constructor: no dotenv, credentials, session or HTTP client."""
    def __init__(self, batches=()):
        self.batches = list(batches)
        self.requests = []

    def generate_response(self, input, params):
        i = len(self.requests)
        self.requests.append({"input": deepcopy(input), "params": deepcopy(params)})
        batch = self.batches[i] if i < len(self.batches) else []
        text = "TRANSIENT_ASSISTANT_ONLY_MARKER"
        message = {"role": "assistant", "content": text, "tool_calls": [
            {"id": f"script-{i}-{j}", "type": "function", "function":
             {"name": tool, "arguments": json.dumps(arguments)}}
            for j, (tool, arguments) in enumerate(batch)]}
        return {"choices": [{"message": message}], "usage": {}}, text


def actor(name, client):
    return BaseAgent(client=client, name=name, model_name="SCRIPTED_NO_INFERENCE",
                     max_conversation_steps=1, environment_name="HospitalEnvironment")


def transfer_args(destination, amount=1):
    return {"to_hospital": destination, "resource_type": "IV_Kits", "amount": amount,
            "rationale": "scripted conformance control"}


def schedule_args(env, hospital, pid=None):
    if pid is None:
        pid = list(env.patients)[env.hospital_names.index(hospital)]
    name = hospital + "_Ward"
    job = next(j for j in env.build_agent_context(name, "execution", 1)["job_queue"]
               if j["patient_id"] == pid)
    return {"patient_id": pid, "step_index": job["step_index"],
            "start_time": job["earliest_start_time"], "rationale": "scripted care control"}


async def tool(protocol, actor_name, name, arguments, phase="execution"):
    return await protocol.environment_handle_tool_call(name, actor_name, arguments, phase=phase, iteration=1)


async def make_branch(seed, policy="original"):
    env, record = restore(seed)
    donor, recipient = list(record["supply_edit"]["after"])
    sources = [donor + "_Surgery", recipient + "_Surgery"]
    wards = [donor + "_Ward", recipient + "_Ward"]
    obligations = {h: [pid] for h, pid in zip(env.hospital_names, env.patients)}
    boards = GuardedBoards()
    public = boards.add_blackboard(list(env.agents_map))
    private = boards.add_blackboard(sources, {"secret_channel": True})
    boards.post(public, sources[0], "communication", {"content": "SOURCE_PUBLIC_HISTORY"})
    boards.post(private, sources[0], "communication", {"content": "PRIVATE_SENTINEL"})
    protocol = BranchProtocol(boards, obligations)
    protocol.environment = env
    env.communication_protocol = protocol
    await tool(protocol, sources[0], "transfer_resources", transfer_args(recipient))
    await tool(protocol, sources[1], "transfer_resources", transfer_args(donor))
    protocol.active = set(wards)
    protocol.policy = policy
    boards.close(private, wards)
    env.prompts = BranchPrompts(env.prompts, policy)
    protocol.observations.clear()
    protocol.tool_events.clear()
    return SimpleNamespace(env=env, protocol=protocol, boards=boards, donor=donor, recipient=recipient,
                           sources=sources, wards=wards, public=public, private=private,
                           obligations=obligations, frozen_record=record)
