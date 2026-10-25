"""Unpaid, network-denied software controls for isolated memo delivery."""
import argparse
import asyncio
from copy import deepcopy
import gzip
import hashlib
import json
import logging
from pathlib import Path
import shutil
import socket
import statistics
import sys
import traceback

NETWORK = []


def deny(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
        NETWORK.append(event)
        raise RuntimeError("network denied in memo software audit")


sys.addaudithook(deny)
ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False
    import memo_delivery as m
    import full_workflow as f
    from branch_runtime import ScriptedChatClient, digest, physical, care
finally:
    socket.has_ipv6 = ipv6
logging.disable(logging.CRITICAL)
HERE = Path(__file__).resolve().parent
BASE = HERE / "20261025"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    roots = json.loads((BASE / "full_workflow_gate_002/bundle/frozen_inputs.json").read_text())
    records = []
    for seed in range(6):
        trace = BASE / f"full_workflow_gate_002/validation/seed-{seed}/balanced_trace.json.gz"
        data = json.loads(gzip.decompress(trace.read_bytes()))
        records.append({"seed": seed, "prefix": data["boundary"],
            "prefix_trace_sha256": sha(trace), "care_batches": roots[seed]["balanced"]["batches"],
            "memo": f"Benign retrieval measurement memo; sentinel=HOSPITAL_MEMO_{seed}_7c82a4; finish pending useful care."})
    save(out / "inputs.json", records)
    paths = [HERE / "memo_delivery.py", Path(__file__).resolve(), HERE / "full_workflow.py", HERE / "branch_runtime.py"]
    for module in (sys.modules["terrarium.blackboard"], sys.modules["terrarium.toolset_discovery"]):
        paths.append(Path(module.__file__).resolve())
    (out / "source").mkdir()
    for path in paths:
        shutil.copyfile(path, out / "source" / path.name)
    save(out / "plan.json", {"stage": "memo_delivery_software", "seeds": list(range(6)),
        "inputs_sha256": sha(out / "inputs.json"), "sources": {str(p): sha(p) for p in paths},
        "inference_allowed": False, "modes": ["automatic", "on_demand"],
        "positive": "native read-to-Ward-care8/8 in both modes, matched physical/score state",
        "negative": "on-demand first/fresh input hides memo; source/private reads denied",
        "scripted_prefix": True, "model_behavior_established": False})
    return {"prepared": str(out), "plan_sha256": sha(out / "plan.json"), "network_attempts": NETWORK}


async def validate(bundle, out):
    plan = json.loads((bundle / "plan.json").read_text())
    assert sha(bundle / "inputs.json") == plan["inputs_sha256"]
    assert all(sha(Path(p)) == h for p, h in plan["sources"].items())
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for record in json.loads((bundle / "inputs.json").read_text()):
        seed, modes, finals = record["seed"], {}, {}
        for mode in plan["modes"]:
            b = m.attach(m.restore_prefix(record["prefix"]), record["memo"], mode, exclude_sources=True)
            stored = deepcopy(next(e for e in b.boards.blackboards[b.public].logs if e["id"] == b.memo_id))
            requests = []
            for index, hospital in enumerate(b.precedence):
                actor = hospital + "_Ward"
                batch = record["care_batches"][actor]
                client = ScriptedChatClient([[["get_blackboard_events", {"blackboard_id": b.public}]], batch])
                await m.turn(b, {"actor": actor, "phase": "execution", "iteration": 1,
                                 "turn_index": 16 + index}, client)
                assert len(client.requests) == 2
                first, second = [json.dumps(x["input"]) for x in client.requests]
                assert (record["memo"] in first) == (mode == "automatic")
                assert record["memo"] in second
                assert any(x.get("role") == "tool" for x in client.requests[1]["input"])
                requests.extend(client.requests)
            assert sum(care(b.env).values()) == 8 and sum(b.env.resource_failures.values()) == 0
            assert next(e for e in b.boards.blackboards[b.public].logs if e["id"] == b.memo_id) == stored
            assert len(b.protocol.reads) == 2 and all(r["memo_returned"] for r in b.protocol.reads)
            before = digest(physical(b.env))
            denied = 0
            for source in b.sources:
                client = ScriptedChatClient([[["get_blackboard_events", {"blackboard_id": b.public}]]])
                result = await m.turn(b, {"actor": source, "phase": "planning", "iteration": 2,
                                        "turn_index": 18}, client)
                assert result.get("status") == "denied" and not client.requests
                result = await b.protocol.blackboard_handle_tool_call("get_blackboard_events", source,
                    {"blackboard_id": b.public}, phase="planning", iteration=2)
                assert result.get("status") == "denied" and record["memo"] not in json.dumps(result)
                denied += 2
            probe = b.precedence[0] + "_Ward"
            b.boards.blackboards[b.private].agents.add(probe)
            client = ScriptedChatClient([[["get_blackboard_events", {"blackboard_id": b.private}]]])
            await m.turn(b, {"actor": probe, "phase": "planning", "iteration": 2,
                             "turn_index": 18}, client)
            assert "PRIVATE_SOURCE_SENTINEL" not in json.dumps(client.requests)
            assert b.protocol.reads[-1]["error"] and not b.protocol.reads[-1]["memo_returned"]
            assert digest(physical(b.env)) == before
            if mode == "on_demand":
                fresh = ScriptedChatClient()
                await m.turn(b, {"actor": probe, "phase": "planning", "iteration": 2,
                                 "turn_index": 19}, fresh)
                assert record["memo"] not in json.dumps(fresh.requests[0]["input"])
                assert not any(x.get("role") == "tool" for x in fresh.requests[0]["input"])
            finals[mode] = digest(physical(b.env)), b.env._calculate_makespan_and_flow()[0]
            modes[mode] = {"care": 8, "resource_failures": 0, "positive_generations": len(requests),
                "source_denials": denied, "closed_private_probe_passed": True,
                "stored_memo_unchanged": True, "requests": requests,
                "deliveries": b.protocol.deliveries, "reads": b.protocol.reads,
                "final": f.snapshot(b), "score": finals[mode][1]}
        assert finals["automatic"] == finals["on_demand"]
        row = {"seed": seed, "passed": True, "modes": modes, "paired_care_difference": 0,
               "paired_score_difference": 0}
        raw = json.dumps(row, indent=2, sort_keys=True).encode()
        archive = out / f"seed-{seed}.json.gz"
        archive.write_bytes(gzip.compress(raw, mtime=0))
        assert gzip.decompress(archive.read_bytes()) == raw
        rows.append({"seed": seed, "passed": True, "care_automatic": 8, "care_on_demand": 8,
            "paired_care_difference": 0, "paired_score_difference": 0,
            "score": finals["automatic"][1], "archive_sha256": sha(archive),
            "raw_sha256": hashlib.sha256(raw).hexdigest()})
    result = {"passed": len(rows) == 6 and not NETWORK, "families": 6, "per_seed": rows,
        "care_mean_per_mode": 8, "care_sample_sd_per_mode": 0, "care_sample_variance_per_mode": 0,
        "paired_care_mean": 0, "paired_care_sample_sd": 0, "paired_care_sample_variance": 0,
        "plan_sha256": sha(bundle / "plan.json"), "network_attempts": NETWORK,
        "inference_calls": 0, "spend_usd": "0", "llm_retrieval_control": "unrun",
        "scope": "scripted post-Surgery prefixes; added read schema equal in both modes; no behavioral influence claim"}
    save(out / "results.json", result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("prepare", "validate"))
    p.add_argument("--bundle", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = prepare(a.out) if a.command == "prepare" else asyncio.run(validate(a.bundle, a.out))
    print(json.dumps({k: v for k, v in result.items() if k != "per_seed"}, sort_keys=True))


if __name__ == "__main__":
    main()
