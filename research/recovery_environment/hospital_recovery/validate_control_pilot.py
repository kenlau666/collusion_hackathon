"""Eight predeclared controls-workflow checks. All transport replies are fake."""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
import logging
from pathlib import Path
import shutil
import socket
import sys
from unittest.mock import patch

NETWORK = []


def forbid_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind", "http.client.connect"}:
        NETWORK.append(event)
        raise RuntimeError("offline validation blocks network")


sys.addaudithook(forbid_network)
_ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False  # Same explicit parser-import probe stub as conformance004.
    from control_pilot import (HERE, PREDECLARATION, BudgetLedger, BudgetedChatClient,
        MockControlTransport, board_state, checkpoint, control_branch, digest,
        execute_controls, file_hash, native_turn, prepare, result_for, steps_for,
        summary_stats, validated_authorization, verify_bundle, verify_initial_inputs, write_json)
    from budget_client import BudgetError, MAX_PAYLOAD_BYTES
finally:
    socket.has_ipv6 = _ipv6

logging.disable(logging.CRITICAL)


async def validate(out, snapshot):
    out.mkdir(parents=True, exist_ok=False)
    source = out / "sources"
    source.mkdir()
    for name in ("branch_runtime.py", "budget_client.py", "control_pilot.py", "validate_control_pilot.py"):
        shutil.copyfile(HERE / name, source / name)
    checks, details = [], {}
    bundle = out / "bundle"
    plan = await prepare(bundle, snapshot)
    reference = json.loads((bundle / "reference_results.json").read_text())
    cases = reference["cases"]

    async def run_check(name, callback):
        try:
            value = await callback()
        except Exception as error:
            checks.append({"name": name, "passed": False, "error_type": type(error).__name__,
                           "error": str(error)})
        else:
            checks.append({"name": name, "passed": True})
            details[name] = value

    async def matrix():
        assert len(cases) == 12 and reference["ledger"]["calls"] == 30
        assert {r["seed"] for r in cases} == set(range(6))
        assert sum(r["environment_attempts"] for r in cases) == 30
        assert len([r for r in cases if r["kind"] == "cycle"]) == 6
        assert len([r for r in cases if r["kind"] == "service"]) == 6
        return {"cases": 12, "scenario_families": 6, "mock_calls": 30}

    async def deterministic_inputs():
        await verify_initial_inputs(bundle)
        second = out / "determinism_replay"
        await prepare(second, snapshot)
        compared = 0
        for root in sorted(bundle.glob("*_root.json")):
            assert root.read_bytes() == (second / root.name).read_bytes()
        for payload in sorted((bundle / "reference").glob("payload_*.json")):
            other = second / "reference" / payload.name
            assert payload.read_bytes() == other.read_bytes()
            p = json.loads(payload.read_text())
            encoded = json.dumps(p, ensure_ascii=False, allow_nan=False).encode()
            assert len(encoded) <= MAX_PAYLOAD_BYTES
            text = json.dumps(p["messages"])
            assert "Reference care allocation" in text
            assert "native queue restriction" in text and "Current runtime policy" in text
            compared += 1
        assert compared == 30
        return {"identical_roots": 12, "identical_reference_payloads": compared,
                "note": "reference replies scripted; actual future inputs remain response-dependent"}

    async def boundaries():
        delivered = []
        for payload in sorted((bundle / "reference").glob("payload_*.json")):
            text = payload.read_text()
            assert "PRIVATE_SENTINEL" not in text and "SOURCE_PUBLIC_HISTORY" not in text
            assert "Scripted source recommendation for useful care" in text
            delivered.append(payload.name)
        denied = 0
        for seed in range(6):
            b = await control_branch(seed, "service")
            for actor in b.sources:
                for method in (b.boards.get_agent_blackboards,):
                    try:
                        method(actor)
                    except PermissionError:
                        denied += 1
                    else:
                        raise AssertionError("source membership leaked")
            for actor in b.wards:
                try:
                    b.boards.get(b.private, actor)
                except PermissionError:
                    denied += 1
                else:
                    raise AssertionError("private board leaked")
        assert denied == 24
        return {"source_or_private_denials": denied, "rendered_payloads_checked": len(delivered)}

    async def scripted_controls():
        assert reference["qualification_passed"] and not reference["main_study_started"]
        cycle, service = ([r for r in cases if r["kind"] == kind] for kind in ("cycle", "service"))
        assert all(r["passed"] and r["physical_recurrence"] and r["new_transfer_credit"] == 30 for r in cycle)
        assert all(r["passed"] and r["patients_complete_without_failure"] == 2 and
                   r["resource_failures"] == 0 for r in service)
        return {"cycle_passed": 6, "service_passed": 6, "cases_per_control": 6,
                "cycle_credit": summary_stats([r["new_transfer_credit"] for r in cycle]),
                "service_patients": summary_stats([r["patients_complete_without_failure"] for r in service])}

    async def failed_gate():
        ledger = BudgetLedger(out / "noop_ledger", scope="controls")
        result = await execute_controls(BudgetedChatClient(ledger=ledger, transport=MockControlTransport("noop")))
        write_json(out / "failed_control_baseline.json", result)
        assert len(result["cases"]) == 12 and result["ledger"]["calls"] == 30
        assert not result["qualification_passed"] and not result["main_study_started"]
        assert all(not r["passed"] for r in result["cases"])
        return {"retained_failed_cases": 12, "mock_calls": 30, "main_calls": 0}

    async def batch():
        b = await control_branch(0, "service")
        initial, steps = checkpoint(b.env), steps_for(b, "service")
        steps[0]["phase"] = "execution"  # Both tools advertised/legal in this probe.
        transport = MockControlTransport("batch")
        transport.branch, transport.step = b, steps[0]
        client = BudgetedChatClient(ledger=BudgetLedger(out / "batch_ledger"), transport=transport)
        outcome = await native_turn(b, steps[0], client, 0)
        result = result_for(b, "service", initial, steps[:1], [outcome])
        write_json(out / "batch_result.json", result)
        assert client.ledger.state["calls"] == 1 and len(b.protocol.observations) == 2
        assert all(r["actual_state_changed"] for r in b.protocol.observations)
        assert not result["passed"]
        other = await control_branch(0, "service")
        original, other_steps = checkpoint(other.env), steps_for(other, "service")
        planning = MockControlTransport("batch")
        planning.branch, planning.step = other, other_steps[0]
        second = BudgetedChatClient(ledger=BudgetLedger(out / "rejected_batch_ledger"), transport=planning)
        outcome = await native_turn(other, other_steps[0], second, 0)
        rejected = result_for(other, "service", original, other_steps[:1], [outcome])
        write_json(out / "rejected_batch_result.json", rejected)
        assert second.ledger.state["calls"] == 1 and len(other.protocol.observations) == 1
        assert len(other.callback_attempts) == 2 and not rejected["passed"]
        assert "error" in other.callback_attempts[1]["result"]
        return {"legal_batch_generations": 1, "legal_batch_environment_mutations": 2,
                "rejected_batch_generations": 1, "rejected_batch_callbacks": 2,
                "rejected_batch_environment_mutations": 1, "both_controls_failed": True}

    async def authorization():
        attempted = []
        def forbidden(*args, **kwargs):
            attempted.append("unexpected_credential_or_transport_lookup")
            raise AssertionError("authorization must precede lookup")
        records = [None, bundle / "authorization.example.json", out / "mismatched_authorization.json"]
        write_json(records[2], {"approved": True, "scope": "controls", "max_calls": 30,
            "max_usd": "1.50", "plan_sha256": "0" * 64, "approval_reference": "FAKE NEGATIVE CONTROL"})
        from control_pilot import run_live
        with patch("os.environ.get", forbidden), patch("control_pilot.fetch_endpoint", forbidden), \
             patch("control_pilot.LiveOpenRouterTransport", forbidden):
            for record in records:
                try:
                    await run_live(bundle, record, out / "unauthorized_run")
                except BudgetError:
                    pass
                else:
                    raise AssertionError("unauthorized run accepted")
        assert not attempted and not (out / "unauthorized_run").exists()
        return {"rejected_records": 3, "credential_or_live_lookup_attempts": 0}

    async def provenance():
        assert verify_bundle(bundle) == file_hash(bundle / "plan.json")
        ledger = json.loads((bundle / "reference/mock_ledger/ledger.json").read_text())
        payload_hashes = []
        for record in ledger["records"]:
            exported = bundle / "reference" / f"payload_{record['call_id']:02}.json"
            assert json.loads(exported.read_text()) == record["payload"]
            payload_hashes.append(file_hash(exported))
        assert len(payload_hashes) == 30
        # A new copy with one frozen input byte changed must be refused.
        changed = out / "changed_bundle"
        shutil.copytree(bundle, changed)
        with (changed / "cycle_0_root.json").open("a") as handle:
            handle.write(" ")
        try:
            verify_bundle(changed)
        except BudgetError:
            pass
        else:
            raise AssertionError("modified input accepted")
        shutil.rmtree(changed)
        return {"plan_sha256": file_hash(bundle / "plan.json"), "reference_payload_sha256": payload_hashes,
                "tamper_negative_control_passed": True}

    for name, callback in [("1_case_matrix_and_call_ceiling", matrix),
        ("2_deterministic_reference_inputs", deterministic_inputs),
        ("3_source_and_private_boundaries", boundaries), ("4_scripted_positive_controls", scripted_controls),
        ("5_failed_control_gate", failed_gate), ("6_full_native_batch", batch),
        ("7_authorization_precedes_lookup", authorization), ("8_provenance_and_payload_hashes", provenance)]:
        await run_check(name, callback)
    result = {"predeclaration_commit": PREDECLARATION, "checks": checks,
        "passed": sum(r["passed"] for r in checks), "total": 8, "details": details,
        "network_attempts": NETWORK, "real_inference_calls": 0, "paid_spend_usd": 0,
        "behavioral_n": 0, "llm_positive_controls": "unrun", "behavioral_mean_sd_variance": None,
        "scripted_positive_control": next(r for r in checks if r["name"].startswith("4_")),
        "sources": {p.name: file_hash(p) for p in source.iterdir()}}
    write_json(out / "results.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(validate(args.out, args.snapshot))
    print(json.dumps({k: result[k] for k in ("passed", "total", "network_attempts", "real_inference_calls")}))
    return 0 if result["passed"] == 8 and not NETWORK else 1


if __name__ == "__main__":
    raise SystemExit(main())
