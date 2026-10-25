"""Reconcile a real saved planning prefix with its actually delivered next input.

Read-only/no inference. This validates restoration beyond constructed witnesses;
it does not turn an interrupted episode into a completed behavioral result.
"""
import asyncio
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import socket
import sys

NETWORK = []


def deny(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
        NETWORK.append(event)
        raise RuntimeError("network denied during saved-prefix verification")


sys.addaudithook(deny)
ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False
    import memo_delivery as m
    import full_workflow as f
    from branch_runtime import ScriptedChatClient, digest
    from llm_server.clients.together_client import _convert_tools
finally:
    socket.has_ipv6 = ipv6

HERE = Path(__file__).resolve().parent
RUN = HERE / "20261025/full_workflow_live_ordinary_s0_001"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def main():
    path = RUN / "full-ordinary-s0.json.gz"
    case = json.loads(gzip.decompress(path.read_bytes()))
    ledger_path = RUN / "accounting/ledger.json"
    ledger = json.loads(ledger_path.read_text())
    assert all(t["complete_turn"] for t in case["turns"][:9])
    prefix = deepcopy(case["turns"][8]["after"])
    frozen = digest(prefix)
    b = m.restore_prefix(prefix)
    step = f.turns(b)[9]
    assert step["phase"] == "execution" and step["actor"] == "Resource_Provisioner"
    client = ScriptedChatClient()
    await f.native_turn(b, step, client, model=ledger["records"][0]["payload"]["model"])
    offset = sum(t["generation_attempts"] for t in case["turns"][:9])
    delivered = ledger["records"][offset]["payload"]
    request = client.requests[0]
    assert request["input"] == delivered["messages"]
    assert _convert_tools(request["params"]["tools"]) == delivered["tools"]
    sibling = m.restore_prefix(prefix)
    sibling.env.inventory[sibling.env.hospital_names[0]]["IV_Kits"] -= 1
    assert digest(prefix) == frozen and digest(f.snapshot(sibling)) != frozen
    assert not NETWORK
    out = HERE / "20261025/memo_delivery_gate_001/validation/live_prefix_verification.json"
    result = {"passed": True, "actual_model_prefixes": 1, "seed": 0,
        "boundary": "after native turn8 first planning, before turn9 first execution",
        "stored_case_sha256": sha(path), "ledger_sha256": sha(ledger_path),
        "restored_snapshot_sha256": frozen, "matching_next_actual_call_id": offset + 1,
        "same_messages": True, "same_tool_schemas": True, "sibling_no_alias": True,
        "network_attempts": NETWORK, "inference_calls": 0, "spend_usd": "0",
        "sample_sd": None, "sample_variance": None,
        "positive_control": "restored prefix produces the byte-equal message strings/schemas of the retained next request",
        "negative_control": "sibling inventory perturbation changes sibling only",
        "limit": "one pre-intervention prefix of an interrupted episode; no behavioral endpoint or arbitrary-policy restore claim",
        "sources": {p.name: sha(p) for p in (Path(__file__).resolve(), HERE / "memo_delivery.py", HERE / "full_workflow.py")}}
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
