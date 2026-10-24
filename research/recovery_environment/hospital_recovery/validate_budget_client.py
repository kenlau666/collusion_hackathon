"""Predeclared offline checks for budget_client; never a model positive control.

Run only after the parent records the named checks in a predeclaration commit.
All replies are injected. Native chat parsing is exercised without credentials,
provider construction or real POSTs. Temporary ledgers are discarded afterwards.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch

import budget_client
from budget_client import (
    BASE_URL, CHAT_URL, CONTEXT_LIMIT, ENDPOINT_OUTPUT_LIMIT, MAX_PAYLOAD_BYTES,
    MODEL_ID, NATIVE_REQUEST_UPPER_BOUND_USD, PROVIDER_SLUG, REQUEST_OUTPUT_LIMIT,
    RESERVATION_USD, SCOPE_LIMITS, BudgetError, BudgetLedger, BudgetedChatClient,
    LiveOpenRouterTransport, TransportReply,
)
from llm_server.clients.together_client import TogetherClient

PLAN = "a" * 64


def response(cost="0.001", **changes):
    result = {"id": "mock-generation-1", "model": MODEL_ID,
        "choices": [{"message": {"role": "assistant", "content": "mock answer"}}],
        "usage": {"cost": cost, "prompt_tokens": 50, "completion_tokens": 10,
                  "total_tokens": 60, "completion_tokens_details": {"reasoning_tokens": 0}}}
    result.update(changes)
    return result


class FakeTransport:
    is_real = False

    def __init__(self, replies=(), callback=None):
        self.replies, self.callback, self.posts = list(replies), callback, []

    def post(self, payload, *, timeout):
        self.posts.append({"payload": deepcopy(payload), "timeout": timeout})
        if self.callback:
            return self.callback(payload)
        return self.replies.pop(0) if self.replies else TransportReply(200, response())


def must_fail(callback):
    try:
        callback()
    except BudgetError as error:
        return str(error)
    raise AssertionError("expected BudgetError")


def make(root, label, *, replies=(), callback=None, scope="controls", **kwargs):
    ledger = BudgetLedger(root / label, scope=scope, plan_sha256=PLAN, **kwargs)
    transport = FakeTransport(replies, callback)
    return BudgetedChatClient(ledger=ledger, transport=transport), ledger, transport


def invoke(client, **params):
    return client.generate_response(client.init_context("system", "user"), {"model": MODEL_ID, **params})


def state(ledger):
    return json.loads(ledger.path.read_text())


def retained(ledger, transport):
    assert len(transport.posts) == 1
    saved = state(ledger)
    assert saved["calls"] == 1 and saved["status"] == "halted"
    assert Decimal(saved["held_usd"]) == RESERVATION_USD
    must_fail(lambda: invoke(transport.client if hasattr(transport, "client") else
                            BudgetedChatClient(ledger=ledger, transport=transport)))
    assert len(transport.posts) == 1


def check_native(root):
    client, ledger, _ = make(root, "native")
    assert BudgetedChatClient.init_context is TogetherClient.init_context
    assert BudgetedChatClient.process_tool_calls is TogetherClient.process_tool_calls
    assert BudgetedChatClient.get_usage is TogetherClient.get_usage
    assert not hasattr(client, "api_key")
    assert client.base_url == BASE_URL
    assert client._get_retry_config() == (0, 0.0, 0.0)
    usage = client.get_usage(response(), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    assert usage == {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}


def check_pinned(root):
    client, _, transport = make(root, "pinned")
    tools = [{"type": "function", "function": {"name": "transfer_resources",
        "description": "native tool", "parameters": {"type": "object"}, "discarded": 1}}]
    context = client.init_context("same system", "same user")
    data, text = client.generate_response(context, {"model": MODEL_ID, "tools": tools,
        "reasoning": {"enabled": True}, "temperature": 1, "seed": 7,
        "max_completion_tokens": REQUEST_OUTPUT_LIMIT})
    payload = transport.posts[0]["payload"]
    assert payload["messages"] == context
    assert payload["model"] == MODEL_ID and payload["seed"] == 7
    assert payload["max_tokens"] == 1024 and payload["temperature"] == 0 and payload["stream"] is False
    assert payload["reasoning"] == {"enabled": False}
    assert payload["provider"] == {"only": [PROVIDER_SLUG], "order": [PROVIDER_SLUG],
        "allow_fallbacks": False, "require_parameters": True,
        "max_price": {"prompt": 0.26, "completion": 0.38, "request": 0}}
    assert "discarded" not in payload["tools"][0]["function"]
    assert "headers" not in transport.posts[0] and "Authorization" not in json.dumps(payload)
    assert text == "mock answer" and data["id"] == "mock-generation-1"


def check_durable(root):
    ledger = BudgetLedger(root / "durable", plan_sha256=PLAN)
    def callback(payload):
        saved = state(ledger)
        assert saved["status"] == "in_flight" and saved["calls"] == 1
        assert Decimal(saved["held_usd"]) == RESERVATION_USD
        assert saved["records"][0]["status"] == "reserved"
        assert saved["records"][0]["payload"] == payload
        return TransportReply(200, response())
    client = BudgetedChatClient(ledger=ledger, transport=FakeTransport(callback=callback))
    invoke(client)


def check_reconciliation(root):
    client, ledger, transport = make(root, "reconcile", replies=[TransportReply(200,response("0.002")),
                                                              TransportReply(200,response("0.003"))])
    invoke(client)
    invoke(client)
    saved = state(ledger)
    assert saved["calls"] == 2 and Decimal(saved["spent_usd"]) == Decimal("0.005")
    assert Decimal(saved["held_usd"]) == 0 and saved["status"] == "ready"
    assert all(r["status"] == "settled" for r in saved["records"])


def check_call_limit(root):
    client, ledger, transport = make(root, "call_limit", max_calls=1)
    invoke(client)
    must_fail(lambda: invoke(client))
    assert len(transport.posts) == 1 and state(ledger)["halt_reason"] == "call_limit"


def check_dollar_limit(root):
    client, ledger, transport = make(root, "dollar_limit", max_usd="0.048")
    must_fail(lambda: invoke(client))
    assert not transport.posts and state(ledger)["calls"] == 0
    assert state(ledger)["halt_reason"] == "dollar_limit"


def check_scope_caps(root):
    for scope, (calls, dollars) in SCOPE_LIMITS.items():
        ledger = BudgetLedger(root / ("scope_" + scope), scope=scope, plan_sha256=PLAN)
        assert ledger.max_calls == calls and ledger.max_usd == dollars
        must_fail(lambda: BudgetLedger(root / ("excess_calls_" + scope),scope=scope,max_calls=calls+1))
        must_fail(lambda: BudgetLedger(root / ("excess_dollars_" + scope),scope=scope,max_usd=dollars+1))
    assert NATIVE_REQUEST_UPPER_BOUND_USD < RESERVATION_USD
    assert SCOPE_LIMITS["controls"][0] * RESERVATION_USD <= SCOPE_LIMITS["controls"][1]
    assert SCOPE_LIMITS["full"][0] * RESERVATION_USD <= SCOPE_LIMITS["full"][1]


def check_resume(root):
    ledger = BudgetLedger(root / "resume", plan_sha256=PLAN)
    before = ledger.path.read_bytes()
    must_fail(lambda: BudgetLedger(root / "resume", plan_sha256=PLAN))
    assert ledger.path.read_bytes() == before


def check_http_failure(root):
    client, ledger, transport = make(root, "http_failure", replies=[TransportReply(429,{"error":"rate limited"})])
    must_fail(lambda: invoke(client))
    retained(ledger, transport)
    assert state(ledger)["records"][0]["http_status"] == 429


def check_exception_secret(root):
    secret = "sk-or-v1-OFFLINE_CANARY_NOT_A_CREDENTIAL"
    def callback(payload):
        raise RuntimeError("transport might echo Authorization: Bearer " + secret)
    client, ledger, transport = make(root, "exception_secret", callback=callback)
    error = must_fail(lambda: invoke(client))
    retained(ledger, transport)
    assert secret not in error and secret not in ledger.path.read_text()


def check_missing_cost(root):
    reply = response()
    del reply["usage"]["cost"]
    client, ledger, transport = make(root, "missing_cost", replies=[TransportReply(200,reply)])
    must_fail(lambda: invoke(client))
    retained(ledger, transport)
    assert state(ledger)["halt_reason"] == "missing_cost"


def check_invalid_cost(root):
    for i, value in enumerate([True, None, {}, -1, "NaN", "Infinity", "not money"]):
        client, ledger, transport = make(root, f"invalid_cost_{i}", replies=[TransportReply(200,response(value))])
        must_fail(lambda: invoke(client))
        retained(ledger, transport)
        assert state(ledger)["halt_reason"] == "invalid_cost"


def check_overreservation(root):
    client, ledger, transport = make(root, "overreservation", replies=[TransportReply(200,response("0.05"))])
    must_fail(lambda: invoke(client))
    retained(ledger, transport)
    assert Decimal(state(ledger)["spent_usd"]) == Decimal("0.05")
    assert state(ledger)["halt_reason"] == "overreservation_cost"


def check_input_tokens(root):
    reply = response()
    reply["usage"]["prompt_tokens"] = CONTEXT_LIMIT + 1
    client, ledger, transport = make(root, "input_tokens", replies=[TransportReply(200,reply)])
    must_fail(lambda: invoke(client))
    retained(ledger, transport)
    assert state(ledger)["halt_reason"] == "reported_input_token_limit"


def check_output_tokens(root):
    reply = response()
    reply["usage"]["completion_tokens"] = REQUEST_OUTPUT_LIMIT + 1
    client, ledger, transport = make(root, "output_tokens", replies=[TransportReply(200,reply)])
    must_fail(lambda: invoke(client))
    retained(ledger, transport)
    assert state(ledger)["halt_reason"] == "reported_output_token_limit"
    client2, ledger2, transport2 = make(root, "requested_output")
    must_fail(lambda: invoke(client2, max_completion_tokens=REQUEST_OUTPUT_LIMIT + 1))
    assert not transport2.posts and state(ledger2)["calls"] == 0
    assert state(ledger2)["halt_reason"] == "requested_output_limit"


def check_bytes(root):
    client, ledger, transport = make(root, "bytes")
    # Deliberately bytes, not a local tokenizer-derived prompt-token assertion.
    context = client.init_context("system", "x" * MAX_PAYLOAD_BYTES)
    must_fail(lambda: client.generate_response(context, {"model": MODEL_ID}))
    assert not transport.posts and state(ledger)["calls"] == 0
    assert state(ledger)["halt_reason"] == "payload_byte_limit"
    client2, ledger2, transport2 = make(root, "bytes_unicode_fits")
    context2 = client2.init_context("system", "界" * (MAX_PAYLOAD_BYTES // 4))
    client2.generate_response(context2, {"model": MODEL_ID})
    encoded = json.dumps(transport2.posts[0]["payload"],ensure_ascii=False,allow_nan=False).encode("utf-8")
    assert len(encoded) <= MAX_PAYLOAD_BYTES
    assert state(ledger2)["records"][0]["payload_bytes"] == len(encoded)
    client3, ledger3, transport3 = make(root, "bytes_unicode_exceeds")
    context3 = client3.init_context("system", "界" * (MAX_PAYLOAD_BYTES // 2))
    must_fail(lambda: client3.generate_response(context3, {"model": MODEL_ID}))
    assert not transport3.posts and state(ledger3)["calls"] == 0


def check_retry_environment(root):
    before = dict(os.environ)
    client, _, _ = make(root, "retry_environment")
    invoke(client)
    assert client._get_retry_config() == (0, 0.0, 0.0) and dict(os.environ) == before


def check_native_parser(root):
    reply = response()
    reply["choices"][0]["message"]["tool_calls"] = [{"id":"native-call","type":"function",
        "function":{"name":"transfer_resources","arguments":json.dumps({"amount":1})}}]
    client, _, _ = make(root, "parser", replies=[TransportReply(200,reply)])
    data, _ = invoke(client)
    calls = []
    async def callback(name, arguments):
        calls.append((name,arguments))
        return {"status":"ok"}
    count, context, steps = asyncio.run(client.process_tool_calls(data, [], callback))
    assert count == 1 and calls == [("transfer_resources",{"amount":1})]
    assert context[-1]["role"] == "tool" and context[-1]["tool_call_id"] == "native-call"
    assert steps == ['transfer_resources -- {"amount": 1}']


def approval(**updates):
    result = {"approved":True,"scope":"controls","max_calls":30,"max_usd":"1.50",
              "plan_sha256":PLAN,"approval_reference":"OFFLINE_TEST_ONLY_NOT_PERMISSION"}
    result.update(updates)
    return result


def check_live_approval(root):
    for auth in ({}, approval(approved=False), approval(plan_sha256="b"*64), approval(max_calls=31),
                 approval(max_usd="1.51"), approval(approval_reference="")):
        # No approved live object is constructed: the globally blocked opener
        # would immediately fail if validation were performed too late.
        must_fail(lambda: LiveOpenRouterTransport(authorization=auth,api_key="OFFLINE_NOT_A_KEY",
                                                  expected_plan_sha256=PLAN))
    # Pure TLS configuration is mocked: no live transport, opener, SSL context
    # or HTTP handler is constructed, and no certificate validation is disabled.
    context = SimpleNamespace(check_hostname=True,verify_mode="CERT_REQUIRED")
    handler = object()
    with patch.object(budget_client.certifi,"where",return_value="MOCK_CA_BUNDLE") as ca_bundle, \
         patch.object(budget_client.ssl,"create_default_context",return_value=context) as make_context, \
         patch.object(budget_client.urllib.request,"HTTPSHandler",return_value=handler) as make_handler:
        assert budget_client._verified_https_handler() is handler
        ca_bundle.assert_called_once_with()
        make_context.assert_called_once_with(cafile="MOCK_CA_BUNDLE")
        make_handler.assert_called_once_with(context=context)
        assert context.check_hostname is True and context.verify_mode == "CERT_REQUIRED"


def check_authorization_match(root):
    # Allocate an uninitialized sentinel solely to exercise client checks;
    # no live transport constructor or HTTP machinery is run.
    live = object.__new__(LiveOpenRouterTransport)
    live.authorization_summary = {"approved":True,"scope":"controls","max_calls":30,
        "max_usd":"1.50","plan_sha256":"b"*64,"approval_reference_sha256":"x"}
    ledger = BudgetLedger(root / "auth_match",plan_sha256=PLAN,authorization=approval())
    must_fail(lambda: BudgetedChatClient(ledger=ledger,transport=live))


def check_concurrent(root):
    entered, release = threading.Event(), threading.Event()
    def callback(payload):
        entered.set()
        assert release.wait(5)
        return TransportReply(200,response())
    client, ledger, transport = make(root,"concurrent",callback=callback)
    errors = []
    def worker():
        try:
            invoke(client)
        except Exception as error:
            errors.append(type(error).__name__)
    worker_thread = threading.Thread(target=worker)
    worker_thread.start()
    try:
        assert entered.wait(5)
        must_fail(lambda: invoke(client))
        assert len(transport.posts) == 1
    finally:
        release.set()
        worker_thread.join(5)
    assert not worker_thread.is_alive() and not errors and state(ledger)["calls"] == 1


def check_artifacts(root):
    client, ledger, _ = make(root,"artifacts")
    invoke(client)
    record = state(ledger)["records"][0]
    assert record["payload"]["model"] == MODEL_ID
    assert record["response_id"] == "mock-generation-1"
    assert record["response"]["usage"] == record["usage"]
    assert "headers" not in record and "Authorization" not in ledger.path.read_text()
    assert state(ledger)["plan_sha256"] == PLAN
    secret = "OFFLINE_CREDENTIAL_ECHO_CANARY"
    reply = response()
    reply["choices"][0]["message"]["content"] = secret
    client2, ledger2, transport2 = make(root,"artifacts_echo",replies=[TransportReply(200,reply)])
    # Exercise the live class's pure redactor using an uninitialized sentinel,
    # never its constructor or networking method.
    sentinel = object.__new__(LiveOpenRouterTransport)
    sentinel._api_key = secret
    transport2.sanitize_for_log = sentinel.sanitize_for_log
    returned, text = invoke(client2)
    assert secret not in json.dumps(returned) and secret not in text
    assert secret not in ledger2.path.read_text()


def check_malformed(root):
    for i, body in enumerate(["not JSON",response(choices=[]),response(id=None),response(choices=[{}])]):
        client, ledger, transport = make(root,f"malformed_{i}",replies=[TransportReply(200,body)])
        must_fail(lambda: invoke(client))
        retained(ledger,transport)
        assert state(ledger)["halt_reason"] == "malformed_response"
    client, ledger, transport = make(root,"mismatched_model")
    must_fail(lambda: client.generate_response([], {"model":"ANOTHER_MODEL"}))
    assert not transport.posts and state(ledger)["calls"] == 0
    client, ledger, transport = make(root,"returned_model",replies=[
        TransportReply(200,response(model="ANOTHER_MODEL"))])
    must_fail(lambda: invoke(client))
    retained(ledger,transport)
    assert state(ledger)["halt_reason"] == "returned_model_mismatch"


def check_seed(root):
    client, _, transport = make(root,"seeds")
    invoke(client,seed=11)
    invoke(client,seed=12)
    assert [p["payload"]["seed"] for p in transport.posts] == [11,12]


CHECKS = [
    ("1_native_methods_and_no_provider_constructor",check_native),
    ("2_pinned_request_tools_seed_and_no_headers",check_pinned),
    ("3_durable_reservation_precedes_transport",check_durable),
    ("4_valid_cost_reconciliation",check_reconciliation),
    ("5_call_limit",check_call_limit),
    ("6_dollar_limit",check_dollar_limit),
    ("7_scope_caps",check_scope_caps),
    ("8_refused_ledger_resume",check_resume),
    ("9_http_failure_retains_and_halts",check_http_failure),
    ("10_transport_exception_secret_redacted",check_exception_secret),
    ("11_missing_cost_retains_and_halts",check_missing_cost),
    ("12_invalid_cost_values",check_invalid_cost),
    ("13_overreservation_cost_retains_and_halts",check_overreservation),
    ("14_input_token_context_bound",check_input_tokens),
    ("15_output_endpoint_bound",check_output_tokens),
    ("16_payload_byte_guard_before_spend",check_bytes),
    ("17_no_global_retry_env_mutation",check_retry_environment),
    ("18_actual_native_tool_parser",check_native_parser),
    ("19_live_authorization_required_before_transport",check_live_approval),
    ("20_live_authorization_matches_ledger",check_authorization_match),
    ("21_concurrent_calls_refused",check_concurrent),
    ("22_persisted_payload_response_id_usage_without_headers",check_artifacts),
    ("23_malformed_response_retains_and_halts",check_malformed),
    ("24_each_request_seed_override",check_seed),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--predeclaration-commit",required=True)
    args = parser.parse_args()
    checks, network_attempts, constructors = [], [], []
    def forbidden_network(event, arguments):
        if event in {"socket.connect","socket.getaddrinfo","http.client.connect"}:
            network_attempts.append(event)
            raise RuntimeError("offline validator blocks networking")
    sys.addaudithook(forbidden_network)
    def forbidden_constructor(*args, **kwargs):
        constructors.append("provider_or_http_constructor")
        raise RuntimeError("offline validator blocks provider construction")
    with tempfile.TemporaryDirectory(prefix="hospital_budget_offline_") as temporary:
        root = Path(temporary)
        with patch("requests.Session",forbidden_constructor), \
             patch("urllib.request.build_opener",forbidden_constructor), \
             patch.object(TogetherClient,"__init__",forbidden_constructor):
            for name, callback in CHECKS:
                try:
                    callback(root)
                except Exception as error:
                    checks.append({"name":name,"passed":False,"error_type":type(error).__name__})
                else:
                    checks.append({"name":name,"passed":True})
    result = {"kind":"offline injected transport checks; not LLM behavior",
        "predeclaration_commit":args.predeclaration_commit,
        "checks":checks,"checks_passed":sum(c["passed"] for c in checks),"checks_total":len(checks),
        "network_attempts":network_attempts,"provider_constructions":constructors,
        "inference_attempts":0,"behavioral_episodes":0,"llm_positive_control":"unrun",
        "scripted_positive_control":{"name":"3_durable_reservation_precedes_transport",
            "passed":next(c["passed"] for c in checks if c["name"].startswith("3_"))},
        "source_sha256":{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                          for name in ("budget_client.py","validate_budget_client.py")}}
    text = json.dumps(result,indent=2,sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf-8") as handle:
            handle.write(text+"\n")
    print(text)
    return 0 if result["checks_passed"]==len(checks) and not network_attempts and not constructors else 1


if __name__ == "__main__":
    raise SystemExit(main())
