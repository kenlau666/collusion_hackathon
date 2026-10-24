"""Network-blocked integration for the Modal adapter and estimated-cost labels."""

import json
from pathlib import Path
import socket
import tempfile
import time
import unittest

from audit_session import audit
from baseline import make_params,run_session
from modal_baseline import ModalClient,UsageLedger
from modal_endpoint import EndpointConfig


class ModalTests(unittest.TestCase):
    def test_full_auction_route_and_cost_uncertainty(self):
        class Response:
            status_code=200
            def __init__(self,body):
                self.body=body
            def json(self):
                return self.body
        class Transport:
            def post(self,url,json,headers):
                self.last_request=json
                seller="as a seller in" in json["messages"][0]["content"]
                answer={"ask" if seller else "bid":95.0 if seller else 96.0,"new_memory":"private note"}
                if seller:
                    answer["message_to_sellers"]="Fixture delivery."
                return Response({"model":"fixture-modal-model","choices":[{"finish_reason":"stop",
                    "message":{"content":__import__('json').dumps(answer)}}],
                    "usage":{"prompt_tokens":1000,"completion_tokens":100}})
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=EndpointConfig.from_values({"MODAL_ENDPOINT_BASE_URL":"https://fixture.modal.direct/v1",
                "MODAL_ENDPOINT_MODEL":"fixture-modal-model","MODAL_ENDPOINT_API_KEY":"fixture-private"})
            ledger=UsageLedger(root/"usage.json")
            transport=Transport()
            def builder(agent_id,seller,seed,call_dir):
                return ModalClient(agent_id,seller,seed,ledger,call_dir,transport,config,time.monotonic()+60)
            summary=run_session(make_params(2,0,config.model),root/"session",builder)
            self.assertEqual(summary["num_trades"],6)
            self.assertAlmostEqual(summary["buyer_surplus"],27)
            audited=audit(root/"session")
            self.assertTrue(audited["passed"],audited["errors"])
            self.assertIsNone(audited["total_cost_usd"])
            self.assertAlmostEqual(audited["reference_token_estimate_usd"],0.00504)
            self.assertEqual(ledger.state["calls_without_reported_cost"],12)
            self.assertNotIn("seed",transport.last_request)
            self.assertNotIn("provider",transport.last_request)
            for p in (root/"session/calls").glob("*.json"):
                self.assertNotIn("fixture-private",p.read_text())

    def test_request_limit_and_restart_with_pending_reservation(self):
        from baseline import RunStopped
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"usage.json"
            ledger=UsageLedger(path,max_calls=1)
            ledger.reserve(0.01)
            with self.assertRaises(RunStopped):
                ledger.reserve(0.01)
            restarted=UsageLedger(path,max_calls=2)
            with self.assertRaises(RunStopped):
                restarted.reserve(0.01)


if __name__=="__main__":
    def deny_network(*args,**kwargs):
        raise RuntimeError("Network blocked during Modal adapter tests")
    socket.socket.connect=deny_network
    socket.create_connection=deny_network
    unittest.main(verbosity=2)
