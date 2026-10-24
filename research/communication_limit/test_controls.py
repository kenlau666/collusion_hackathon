"""Offline checks of the intervention, using the real auction classes."""

import copy
import json
from pathlib import Path
import socket
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "llm-agent-collusion"))

from src.continuous_double_auction.cda_types import ExperimentParams
from src.continuous_double_auction.market.agents import LMBuyer, LMSeller
from src.continuous_double_auction.market.market import Market
from src.resources.model_wrappers import ModelWrapper


class ScriptedClient(ModelWrapper):
    def __init__(self, response):
        super().__init__(model_name="offline-fixture")
        self.response = response
        self.inputs = []

    def generate(self, messages):
        self.inputs.append(copy.deepcopy(messages))
        return json.dumps(self.response)


def fixture(prompt_limit=None, runtime_limit=None, chat=True, message="ABCDE_LONG_MESSAGE"):
    params = ExperimentParams(
        seller_valuations=[80.0, 80.0], buyer_valuations=[100.0],
        seller_models=["fixture", "fixture"], buyer_models=["fixture"], rounds=2,
        seller_comms_enabled=chat, max_message_length=500,
        seller_prompt_message_limit=prompt_limit,
        seller_runtime_message_limit=runtime_limit,
    )
    clients = [ScriptedClient({"ask": 95.0 + i, "message_to_sellers": message,
                               "new_memory": "own note"}) for i in range(2)]
    sellers = [LMSeller(id=f"seller_{i}", company=f"company_{i}", valuation=80.0,
                        expt_params=params, client=clients[i]) for i in range(2)]
    buyer = LMBuyer(id="buyer", company="buyer", valuation=100.0, expt_params=params,
                    client=ScriptedClient({"bid": 50.0}))
    return Market(sellers=sellers, buyers=[buyer]), clients


class ControlTests(unittest.TestCase):
    def test_matched_prompts_and_distinct_delivery(self):
        prompt_only, clients_p = fixture(prompt_limit=5)
        enforced, clients_c = fixture(prompt_limit=5, runtime_limit=5)
        prompt_only.run_round()
        enforced.run_round()
        self.assertEqual(clients_p[0].inputs[0], clients_c[0].inputs[0])
        self.assertIn("MUST contain 5 or fewer Unicode code points", clients_p[0].inputs[0][0]["content"])
        self.assertEqual(prompt_only.rounds[0].seller_messages["seller_0"], "ABCDE_LONG_MESSAGE")
        self.assertEqual(enforced.rounds[0].seller_messages["seller_0"], "ABCDE")
        event = enforced.rounds[0].seller_message_events["seller_0"]
        self.assertEqual(event["raw_message"], "ABCDE_LONG_MESSAGE")
        self.assertEqual(event["delivered_message"], "ABCDE")

    def test_all_peers_and_sender_receive_delivered_version(self):
        market, clients = fixture(prompt_limit=5, runtime_limit=5)
        market.run_round()
        market.run_round()
        for client in clients:
            prompt = client.inputs[1][0]["content"]
            self.assertIn("- From seller_0: ABCDE", prompt)
            self.assertIn("- From seller_1: ABCDE", prompt)
            self.assertNotIn("ABCDE_LONG_MESSAGE", prompt)

    def test_no_chat_keeps_public_action_path(self):
        market, clients = fixture(chat=False)
        market.run_round()
        market.run_round()
        prompt = clients[1].inputs[1][0]["content"]
        self.assertEqual(market.rounds[0].seller_messages, {})
        self.assertNotIn("# Messages Received from Other Sellers", prompt)
        self.assertIn("seller_0 ask $95.0", prompt)
        self.assertEqual(market.rounds[0].seller_message_events["seller_0"]["status"], "disabled")

    def test_unicode_code_points_and_zero_cap(self):
        message = "😀e\u0301xyZ"
        market, _ = fixture(runtime_limit=5, message=message)
        market.run_round()
        self.assertEqual(market.rounds[0].seller_messages["seller_0"], message[:5])
        market, _ = fixture(runtime_limit=0)
        market.run_round()
        self.assertEqual(market.rounds[0].seller_messages["seller_0"], "")

    def test_legacy_outer_cap_still_applies(self):
        market, clients = fixture(message="X" * 510)
        market.run_round()
        self.assertEqual(len(market.rounds[0].seller_messages["seller_0"]), 500)
        self.assertIn("maximum length limit of 500", clients[0].inputs[0][0]["content"])

    def test_invalid_message_type_is_not_silently_delivered(self):
        market, _ = fixture(message=["not", "a", "string"])
        with self.assertRaises(ValueError):
            market.run_round()


if __name__ == "__main__":
    def deny_network(*args, **kwargs):
        raise RuntimeError("Network disabled during offline intervention tests")

    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    unittest.main(verbosity=2)
