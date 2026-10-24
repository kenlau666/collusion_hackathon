"""Trace real auction context assembly with scripted responses and no inference.

Run from llm-agent-collusion/ using its existing Python environment:
    .venv/bin/python ../research/context_flow/offline_trace.py

Writes a synthetic plumbing trace next to this script. This is not evidence of
model behavior, collusion, or intervention effectiveness.
"""

import copy
import json
from pathlib import Path
import socket
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "llm-agent-collusion"))


def deny_network(*args, **kwargs):
    raise RuntimeError("Network access is disabled in this offline walkthrough")


socket.socket.connect = deny_network
socket.create_connection = deny_network

from src.continuous_double_auction.cda_types import ExperimentParams
from src.continuous_double_auction.market.agents import LMBuyer, LMSeller
from src.continuous_double_auction.market.market import Market
from src.resources.model_wrappers import ModelWrapper


class ScriptedClient(ModelWrapper):
    def __init__(self, response):
        super().__init__(model_name="offline-scripted-fixture")
        self.response = copy.deepcopy(response)
        self.inputs = []

    def generate(self, messages):
        self.inputs.append(copy.deepcopy(messages))
        return json.dumps(self.response)


def walkthrough(chat_enabled):
    params = ExperimentParams(
        seller_valuations=[60.0, 60.0],
        buyer_valuations=[80.0],
        seller_models=["offline-fixture", "offline-fixture"],
        buyer_models=["offline-fixture"],
        rounds=2,
        seller_comms_enabled=chat_enabled,
        max_message_length=5,
    )
    raw_a = {
        "reflection": "A_PRIVATE_REFLECTION_MARKER",
        "plan_for_this_hour": "A_PRIVATE_PLAN_MARKER",
        "ask": 95.0,
        "new_memory": "A_PRIVATE_MEMORY_MARKER",
        "plan_for_message": "A_PRIVATE_MESSAGE_PLAN_MARKER",
        "message_to_sellers": "ABCDE_LONG_A_MESSAGE",
        "scratch_pad_update": "A_PRIVATE_SCRATCHPAD_MARKER",
    }
    raw_b = {
        "ask": 96.0,
        "new_memory": "B_OWN_MEMORY_MARKER",
        "message_to_sellers": "XYZ12_LONG_B_MESSAGE",
        "scratch_pad_update": "B_OWN_SCRATCHPAD_MARKER",
    }
    client_a, client_b = ScriptedClient(raw_a), ScriptedClient(raw_b)
    client_buyer = ScriptedClient({"bid": 50.0})
    seller_a = LMSeller(
        id="seller_a", company="Fixture A", valuation=60.0,
        expt_params=params, client=client_a,
    )
    seller_b = LMSeller(
        id="seller_b", company="Fixture B", valuation=60.0,
        expt_params=params, client=client_b,
    )
    buyer = LMBuyer(
        id="buyer_fixture", company="Fixture buyer", valuation=80.0,
        expt_params=params, client=client_buyer,
    )
    market = Market(sellers=[seller_a, seller_b], buyers=[buyer])
    market.run_round()
    market.run_round()
    prompt_b1 = client_b.inputs[0][0]["content"]
    prompt_b2 = client_b.inputs[1][0]["content"]
    private_markers = [v for k, v in raw_a.items() if k not in {"ask", "message_to_sellers"}]
    checks = {
        "no_peer_message_in_b_first_round": "- From seller_a:" not in prompt_b1,
        "a_public_ask_in_b_second_round_history": "seller_a ask $95.0" in prompt_b2,
        "a_private_fields_not_forwarded_to_b": all(v not in prompt_b2 for v in private_markers),
        "b_own_memory_retained": "B_OWN_MEMORY_MARKER" in prompt_b2,
        "b_own_scratchpad_retained": "B_OWN_SCRATCHPAD_MARKER" in prompt_b2,
        "b_receives_one_user_message": len(client_b.inputs[1]) == 1 and client_b.inputs[1][0]["role"] == "user",
    }
    if chat_enabled:
        checks.update({
            "delivery_truncates_a_message": market.rounds[0].seller_messages["seller_a"] == "ABCDE",
            "b_sees_a_delivered_message": "- From seller_a: ABCDE" in prompt_b2,
            "b_does_not_see_a_untruncated_message": raw_a["message_to_sellers"] not in prompt_b2,
            "b_also_sees_its_own_delivered_message": "- From seller_b: XYZ12" in prompt_b2,
        })
    else:
        checks.update({
            "no_seller_message_is_delivered": market.rounds[0].seller_messages == {},
            "no_seller_message_section_in_b_context": "# Messages Received from Other Sellers" not in prompt_b2,
        })
    if not all(checks.values()):
        raise AssertionError({key: value for key, value in checks.items() if not value})
    return {
        "synthetic_fixture_only": True,
        "chat_enabled": chat_enabled,
        "general_delivery_cap": 5,
        "gag_order_active": market.is_gag_order_active,
        "scripted_a_response": raw_a,
        "first_round_delivered_messages": market.rounds[0].seller_messages,
        "b_first_round_model_input": client_b.inputs[0],
        "b_second_round_model_input": client_b.inputs[1],
        "checks": checks,
    }


if __name__ == "__main__":
    cases = [walkthrough(True), walkthrough(False)]
    trace = {
        "purpose": "Offline context-plumbing walkthrough; no LLM inference or collusion measurement",
        "starter_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
        ).strip(),
        "network_connections_blocked": True,
        "cases": cases,
    }
    output = Path(__file__).with_name("offline_trace.json")
    output.write_text(json.dumps(trace, indent=2) + "\n")
    print(f"Saved synthetic context trace: {output}")
    for case in cases:
        print(f"chat_enabled={case['chat_enabled']}: {sum(case['checks'].values())}/{len(case['checks'])} checks passed")
