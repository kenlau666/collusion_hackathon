"""Network-free integration, accounting, and outcome checks for the baseline."""

from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import socket
import tempfile
import unittest

import baseline


class FakeResponse:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class FakeTransport:
    def __init__(self, body=None):
        self.body = body
        self.requests = []

    def post(self, url, json):
        self.requests.append(copy.deepcopy(json))
        if self.body is not None:
            return FakeResponse(self.body)
        seller = "as a seller in" in json["messages"][0]["content"]
        answer = {"ask" if seller else "bid": 95.0 if seller else 96.0,
                  "new_memory": "Own private memory.", "scratch_pad_update": "Own strategy."}
        if seller:
            answer["message_to_sellers"] = "Fixture message for route verification."
        return FakeResponse({"model": baseline.MODEL+"-2025-04-14", "provider": "OpenAI",
                             "choices": [{"finish_reason": "stop", "message": {"content": __import__('json').dumps(answer)}}],
                             "usage": {"cost": 0.001, "prompt_tokens": 1000, "completion_tokens": 100}})


class BaselineTests(unittest.TestCase):
    def test_real_market_two_rounds_and_accounting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = baseline.Budget(root/"ledger.json", 1.0)
            transport = FakeTransport()
            clients = []
            def builder(agent_id, seller, seed, call_dir):
                client = baseline.AuditedClient(agent_id,seller,seed,budget,call_dir,transport)
                clients.append(client)
                return client
            summary = baseline.run_session(baseline.make_params(2,0), root/"session", builder)
            self.assertEqual(summary["num_trades"], 6)
            self.assertAlmostEqual(summary["seller_profit"], 93.0)
            self.assertAlmostEqual(summary["buyer_surplus"], 27.0)
            self.assertAlmostEqual(summary["total_welfare"], 120.0)
            self.assertEqual(summary["delivered_messages_over_500"], 0)
            self.assertEqual(len(transport.requests), 12)
            self.assertAlmostEqual(budget.state["spent_usd"], 0.012)
            self.assertAlmostEqual(budget.state["held_usd"], 0.0)
            self.assertEqual(budget.state["unknown_usd"], 0.0)
            restarted = baseline.Budget(root/"ledger.json", 1.0)
            self.assertFalse(restarted.stopped)
            metadata = json.loads((root/"session/session.json").read_text())
            self.assertEqual(metadata["status"], "complete")
            self.assertEqual(len(list((root/"session/calls").glob("*.result.json"))), 12)
            round2_sellers = [r for r in transport.requests if "Hour #2 out of" in r["messages"][0]["content"]
                              and "as a seller in" in r["messages"][0]["content"]]
            self.assertEqual(len(round2_sellers), 3)
            for request in round2_sellers:
                content = request["messages"][0]["content"]
                for seller in metadata["sellers"]:
                    self.assertIn(f"- From {seller['id']}: Fixture message for route verification.",content)
                self.assertEqual(request["provider"]["only"], ["openai"])
                self.assertFalse(request["provider"]["allow_fallbacks"])
                self.assertIn("Own private memory.", content)

    def test_concurrent_reservations_cannot_exceed_ceiling(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = baseline.Budget(Path(directory)/"ledger.json",0.02)
            def reserve():
                try:
                    budget.reserve(0.015)
                    return True
                except baseline.RunStopped:
                    return False
            with ThreadPoolExecutor(max_workers=6) as executor:
                success = list(executor.map(lambda _:reserve(),range(6)))
            self.assertEqual(sum(success),1)
            self.assertAlmostEqual(budget.state["held_usd"],0.015)
            restarted = baseline.Budget(Path(directory)/"ledger.json",0.02)
            with self.assertRaises(baseline.RunStopped):
                restarted.reserve(0.001)

    def test_missing_cost_stops_future_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            budget = baseline.Budget(root/"ledger.json",1)
            transport = FakeTransport({"usage":{}, "choices":[]})
            client = baseline.AuditedClient("Seller fixture",True,0,budget,root/"calls",transport)
            with self.assertRaises(baseline.RunStopped):
                client.generate([{"role":"user","content":"fixture"}])
            with self.assertRaises(baseline.RunStopped):
                client.generate([{"role":"user","content":"fixture"}])
            self.assertEqual(len(transport.requests),1)
            self.assertGreater(budget.state["unknown_usd"],0)

    def test_invalid_actions_and_truncation_fail_closed(self):
        for answer in ('{"ask": true}', '{"ask": null}', '{"ask": "95"}',
                       '{"ask": NaN}', '{"ask": 95, "message_to_sellers": [1]}'):
            with self.subTest(answer=answer), self.assertRaises(baseline.RunStopped):
                baseline.validate_answer(answer,True)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            budget=baseline.Budget(root/"ledger.json",1)
            transport=FakeTransport({"usage":{"cost":0.001},"choices":[{"finish_reason":"length"}]})
            client=baseline.AuditedClient("Seller fixture",True,0,budget,root/"calls",transport)
            with self.assertRaises(baseline.RunStopped):
                client.generate([{"role":"user","content":"fixture"}])
            self.assertAlmostEqual(budget.state["spent_usd"],0.001)
            result=json.loads(next((root/"calls").glob("*.result.json")).read_text())
            self.assertEqual(result["status"],"failed")


if __name__ == "__main__":
    def deny_network(*args, **kwargs):
        raise RuntimeError("Network disabled during baseline tests")
    socket.socket.connect=deny_network
    socket.create_connection=deny_network
    unittest.main(verbosity=2)
