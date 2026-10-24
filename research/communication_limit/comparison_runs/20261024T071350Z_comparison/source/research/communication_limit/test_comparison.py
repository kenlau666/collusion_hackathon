"""Network-blocked checks of all three arms, matched prompts and delivery audits."""

import json
from pathlib import Path
import socket
import tempfile
import time
import unittest

from jinja2 import Environment

from audit_session import audit
from baseline import REPO, run_session
from comparison import ARMS, BASELINE, compliance, condition_params, schedule, validate_historical_match
from modal_baseline import ModalClient, UsageLedger
from modal_endpoint import EndpointConfig


class Response:
    status_code=200
    def __init__(self,body):
        self.body=body
    def json(self):
        return self.body


class Transport:
    def post(self,url,json,headers):
        seller="as a seller in" in json["messages"][0]["content"]
        answer={"ask" if seller else "bid":95.0 if seller else 96.0,"new_memory":"own note"}
        # Deliberately unsolicited in D to verify disabled delivery.
        if seller:
            answer["message_to_sellers"]="😀e\u0301XY_LONG_PRIVATE_SENTINEL"
        return Response({"model":"fixture","choices":[{"finish_reason":"stop",
            "message":{"content":__import__('json').dumps(answer)}}],
            "usage":{"prompt_tokens":1000,"completion_tokens":100}})


class ComparisonTests(unittest.TestCase):
    def test_schedule_is_balanced_and_settings_match_baseline(self):
        items=schedule()
        self.assertEqual(len(items),9)
        self.assertEqual(len({(x["arm"],x["seed"]) for x in items}),9)
        for position in range(3):
            self.assertEqual({items[block*3+position]["arm"] for block in range(3)},set(ARMS))
        validate_historical_match()

    def test_no_chat_notice_leaves_chat_enabled_rendering_unchanged(self):
        relative=Path("llm-agent-collusion/src/continuous_double_auction/prompt_templates/seller_prompt_base.jinja2")
        old=Environment().from_string((BASELINE/"source"/relative).read_text())
        current=Environment().from_string((REPO/relative).read_text())
        for limit in (None,5):
            for messages in ({},{"Seller A":"ABCDE","Seller B":"95"}):
                data={"seller_id":"Seller A","company":"Fixture","valuation":80,
                      "round_number":2,"num_rounds":15,"memory":"own note",
                      "seller_comms_enabled":True,"seller_messages":messages,
                      "seller_prompt_message_limit":limit,"max_message_length":500}
                self.assertEqual(old.render(data),current.render(data))

    def test_all_arms_end_to_end_and_audit_detects_undelivered_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=EndpointConfig.from_values({"MODAL_ENDPOINT_BASE_URL":"https://fixture.modal.direct/v1",
                "MODAL_ENDPOINT_MODEL":"fixture","MODAL_ENDPOINT_API_KEY":"private-test-credential"})
            ledger=UsageLedger(root/"usage.json",max_calls=36)
            transport=Transport()
            def builder(agent_id,seller,seed,call_dir):
                return ModalClient(agent_id,seller,seed,ledger,call_dir,transport,config,time.monotonic()+60)
            first_inputs={}
            for arm in ARMS:
                session=root/arm
                run_session(condition_params(arm,0,"fixture",rounds=2),session,builder)
                report=audit(session)
                self.assertTrue(report["passed"],report["errors"])
                lengths=compliance(session)
                self.assertEqual(lengths["raw_over_5"],6)
                self.assertEqual(lengths["delivered_over_5"],6 if arm=="prompt_limit" else 0)
                self.assertEqual(lengths["disabled_count"],6 if arm=="no_chat" else 0)
                first_inputs[arm]={}
                for path in (session/"calls").glob("*.result.json"):
                    event=json.loads(path.read_text())
                    if event["round"]==1:
                        first_inputs[arm][event["agent_id"]]=event["request"]
                    self.assertNotIn("private-test-credential",path.read_text())
            self.assertEqual(first_inputs["prompt_limit"],first_inputs["runtime_limit"])
            session=root/"runtime_limit"
            target=next(path for path in (session/"calls").glob("*.result.json")
                        if (lambda e:e["round"]==2 and e["agent_id"].startswith("Seller"))(json.loads(path.read_text())))
            event=json.loads(target.read_text())
            event["request"]["messages"][0]["content"]=event["request"]["messages"][0]["content"].replace(
                "# Messages Received from Other Sellers (Previous Hour)",
                "# Messages Received from Other Sellers (Previous Hour)\nUNDELIVERED_PRIVATE_SENTINEL")
            target.write_text(json.dumps(event))
            report=audit(session)
            self.assertFalse(report["passed"])
            self.assertTrue(any("exact delivered message section" in e for e in report["errors"]))
            self.assertEqual(ledger.state["calls_completed"],36)


if __name__=="__main__":
    def deny_network(*args,**kwargs):
        raise RuntimeError("Network blocked during comparison tests")
    socket.socket.connect=deny_network
    socket.create_connection=deny_network
    unittest.main(verbosity=2)
