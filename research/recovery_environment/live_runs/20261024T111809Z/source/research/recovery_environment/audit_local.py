"""Offline starter-code probes for recovery suitability; no inference clients loaded.

Run from any directory with Python 3.9+. Actual environment/agent/channel methods
are used with a scripted client. Liar's Bar findings are AST observations only.
This is a software-routing fixture, not a behavioral/collusion experiment.
"""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
STARTER = ROOT / "llm-agent-collusion-2"
CLEANUP = STARTER / "Collusion_Cleanup" / "cleanup_llm"


def forbidden(*args, **kwargs):
    raise AssertionError("Network/client construction forbidden in offline probe")


socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden

# Prevent importing the routed provider client or reading its environment files.
stub = ModuleType("agents.llm_client")
class ForbiddenClient:
    __init__ = forbidden
stub.LLMClient = ForbiddenClient
sys.modules["agents.llm_client"] = stub
sys.path.insert(0, str(CLEANUP))

from agents.llm_agent import LLMAgent
from cleanup.env import CleanupEnvironment
from cleanup.actions import Action
from games.secret_channel import CleanupSecretChannel
from agents.prompts import format_cleanup_prompt


class ScriptedClient:
    def __init__(self):
        self.requests = []

    def generate(self, **kwargs):
        self.requests.append(kwargs)
        return "We can CLEAN together."


def tree(relative_path):
    return ast.parse((STARTER / relative_path).read_text())


def run():
    logs = io.StringIO()
    with redirect_stdout(logs):
        client_a, client_b = ScriptedClient(), ScriptedClient()
        a = LLMAgent(0, "offline-fixture", client_a)
        b = LLMAgent(1, "offline-fixture", client_b)
        a.activate_secret_alliance("B")
        a.add_secret_context("fixture previous peer plan")
        a.recent_secret_messages.clear()
        a.action_context = None
        prompt_after_text_clear = a._get_enhanced_system_prompt()
        assert "UNBREAKABLE ALLIANCE" in prompt_after_text_clear

        # Start without any LLM configs, then install explicit scripted agents.
        configs = [{"type": "random", "name": n} for n in "ABCD"]
        game = CleanupSecretChannel(configs, {}, max_steps=3, seed=7)
        game.agents[0], game.agents[1] = a, b
        game.establish_secret_channel(0, 1)
        a.reset()
        assert not a.secret_alliance_active
        assert a.action_context is None and a.recent_secret_messages == []
        assert game.secret_channel.active
        assert game.env.is_alliance(0, 1)
        requests_before = len(client_a.requests)
        game.secret_communicate(0)
        resumed = client_a.requests[requests_before:]
        assert resumed and "UNBREAKABLE ALLIES" in resumed[0]["user_prompt"]
        assert a.action_context is not None
        # Do not claim this method restores the flag or proves action influence.
        assert not a.secret_alliance_active

        game.secret_channel.active = False
        assert game.env.is_alliance(0, 1)
        game.env.reset(seed=7)
        assert game.env.is_alliance(0, 1)

        zap_cases = []
        for allied in (False, True):
            env = CleanupEnvironment()
            env.reset(seed=7)
            # All agents at separate corners: right of A is empty in both cases.
            if allied:
                env.add_alliance(0, 1)
            positions = {i: [x.row, x.col] for i, x in env.agents.items()}
            env._process_zap_actions({0: Action.ZAP_RIGHT})
            frozen = {str(i): x.frozen_steps for i, x in env.agents.items()}
            zap_cases.append({"allied": allied, "positions": positions, "frozen": frozen})
        assert not any(zap_cases[0]["frozen"].values())
        assert zap_cases[1]["frozen"]["2"] == 5

        # The wrapper seeds Python before constructing an environment that seeds
        # it again from its default config. Test the actual constructed worlds.
        seeded_worlds = []
        for requested_seed in (11, 29):
            seeded_game = CleanupSecretChannel(configs, {}, max_steps=3, seed=requested_seed)
            encoded = json.dumps(seeded_game.current_obs, sort_keys=True)
            seeded_worlds.append({"requested_seed": requested_seed,
                                  "initial_observation_sha256": hashlib.sha256(encoded.encode()).hexdigest()})
        assert seeded_worlds[0]["initial_observation_sha256"] == seeded_worlds[1]["initial_observation_sha256"]

        # Metrics must use world state, not the formatter's missing-field default.
        observed_env = CleanupEnvironment()
        observed_env.reset(seed=7)
        observed_env.agents[0].frozen_steps = 5
        frozen_obs = observed_env._get_observations()[0]
        assert "frozen_steps" not in frozen_obs
        assert "Frozen steps remaining: 0" in format_cleanup_prompt(frozen_obs)

    player_tree = tree("Collusion_Liars_Bar/src/agents/player.py")
    player_cls = next(n for n in player_tree.body if isinstance(n, ast.ClassDef) and n.name == "Player")
    method_names = {n.name for n in player_cls.body if isinstance(n, ast.FunctionDef)}
    missing_helper_calls = [
        n.lineno for n in ast.walk(player_cls)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get_secret_alliance_memory"
    ]
    assert len(missing_helper_calls) == 2
    assert "get_secret_alliance_memory" not in method_names
    assert "get_secret_memory_context" in method_names

    paths = [
        "Collusion_Cleanup/cleanup_llm/agents/llm_agent.py",
        "Collusion_Cleanup/cleanup_llm/agents/prompts.py",
        "Collusion_Cleanup/cleanup_llm/games/secret_channel.py",
        "Collusion_Cleanup/cleanup_llm/games/tournament_secret_channel.py",
        "Collusion_Cleanup/cleanup_llm/cleanup/env.py",
        "Collusion_Cleanup/cleanup_llm/cleanup/config.py",
        "Collusion_Liars_Bar/src/agents/player.py",
        "Collusion_Liars_Bar/src/game/game_secret_channel.py",
        "Collusion_Liars_Bar/src/game/game_series_secret_channel.py",
    ]
    result = {
        "kind": "synthetic software-routing probe plus AST inspection",
        "inference_calls": 0,
        "provider_client_imported": False,
        "network": "socket connection operations blocked",
        "cleanup": {
            "clear_recent_text_keeps_alliance_system_instructions": True,
            "agent_reset_clears_local_alliance_fields": True,
            "agent_reset_keeps_channel_and_environment_membership": True,
            "active_channel_supplies_alliance_prompt_after_agent_reset": True,
            "scripted_peer_reply_repopulates_action_context": True,
            "secret_communicate_restores_local_alliance_flag": False,
            "disable_channel_keeps_environment_alliance": True,
            "environment_reset_keeps_alliance_pairs": True,
            "same_action_different_zap_rules": zap_cases,
            "wrapper_seed_observations": seeded_worlds,
            "missing_frozen_steps_observation_defaults_display_to_zero": True,
            "reset_agent_scripted_requests": resumed,
        },
        "liars_bar_static": {
            "undefined_helper": "get_secret_alliance_memory",
            "calls_at_lines": missing_helper_calls,
            "other_defined_helper": "get_secret_memory_context",
            "limit": "No Liar's Bar game or memory-enabled model call executed",
        },
        "source_hashes": {
            str((STARTER / p).relative_to(ROOT)): hashlib.sha256((STARTER / p).read_bytes()).hexdigest()
            for p in paths
        },
        "captured_fixture_stdout": logs.getvalue(),
        "limits": [
            "Scripted responses are not LLM behavior or collusion evidence.",
            "No recovery intervention was evaluated on live agents.",
            "No claim of full game, replay, or secret-hint-path coverage.",
        ],
    }
    output = Path(__file__).with_name("offline_audit.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"saved": str(output.relative_to(ROOT)), "inference_calls": 0,
                      "routing_probes": "passed", "source_hashes": len(paths)}, indent=2))


if __name__ == "__main__":
    run()
