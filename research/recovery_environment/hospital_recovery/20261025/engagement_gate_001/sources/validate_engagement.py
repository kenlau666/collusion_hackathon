"""Eight predeclared unpaid checks of the proposed cap-three engagement gate.

This command uses only injected fake transports. It does not authorize, resume,
or retry any paid experiment. Run only after the parent confirms the protocol
commit; every invocation requires a fresh output directory and retains failures.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import logging
from pathlib import Path
import shutil
import socket
import statistics
import sys
import traceback
from unittest.mock import patch


NETWORK = []


def forbid_network(event, arguments):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind", "http.client.connect"}:
        NETWORK.append({"event": event, "stack": traceback.format_stack(limit=8)})
        raise RuntimeError("Network denied in unpaid engagement validation")


sys.addaudithook(forbid_network)
_native_ipv6 = socket.has_ipv6
IMPORT_FAILURE = None
try:
    # requests/urllib3 imports contain an unused IPv6 bind probe. Suppress only
    # that import-time probe; the audit hook is enforced before and afterwards.
    socket.has_ipv6 = False
    import engagement_pilot as engagement
    from branch_runtime import (PHYSICAL_FIELDS, ScriptedChatClient, actor, checkpoint,
                                digest, tool, transfer_args)
    from budget_client import (MODEL_ID, BudgetError, BudgetLedger, BudgetedChatClient,
                               TransportReply)
except Exception as exc:
    IMPORT_FAILURE = {"error_type": type(exc).__name__, "error": str(exc),
                      "traceback": traceback.format_exc()}
finally:
    socket.has_ipv6 = _native_ipv6

logging.disable(logging.CRITICAL)

HERE = Path(__file__).resolve().parent
OLD_BUNDLE = HERE / "20261025/main_gate_002/bundle"
OLD_MAIN_AUTHORIZATION = HERE / "20261025/main_authorization.json"
SOURCE_NAMES = ("branch_runtime.py", "budget_client.py", "control_pilot.py",
                "main_inputs.py", "main_metrics.py", "main_pilot.py",
                "engagement_pilot.py", "validate_engagement.py")
PHYSICAL_TOOLS = {"transfer_resources", "schedule_patient"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def stats(values):
    return {"values": values, "scenario_denominator": len(values),
            "mean": statistics.mean(values) if values else None,
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
            "sample_variance": statistics.variance(values) if len(values) > 1 else None}


def prior_manifest(output):
    """Hash old evidence without copying or displaying private ledger contents."""
    output = output.resolve()
    return {str(p.relative_to(HERE)): sha(p)
            for directory in (HERE / "20261024", HERE / "20261025")
            for p in sorted(directory.rglob("*"))
            if p.is_file() and not p.resolve().is_relative_to(output)}


def fake_client(directory, mode="success", *, max_calls=198, max_usd="10", transport=None):
    ledger = BudgetLedger(directory / "accounting", scope="full",
                          max_calls=max_calls, max_usd=max_usd)
    return BudgetedChatClient(ledger=ledger, transport=(
        transport if transport is not None else engagement.MockTransport(mode=mode)))


def response_tools(record):
    choices = (record.get("response") or {}).get("choices", [])
    if not choices:
        return []
    calls = choices[0].get("message", {}).get("tool_calls", [])
    return [c.get("function", {}).get("name") for c in calls if isinstance(c, dict)]


def query_result_present(record):
    return any(message.get("role") == "tool" and message.get("name") == "get_job_queue"
               for message in record["payload"]["messages"])


def care_from_checkpoint(state):
    by_patient = {}
    for patient_id, patient in state["patients"].items():
        progress = state["patient_states"][patient_id]
        actual = {str(index) for index in progress["scheduled_steps"]}
        expected = {str(index) for index in range(len(patient["pathway"]))}
        by_patient[str(patient_id)] = int(actual == expected and not progress["resource_failures"])
    return {"by_patient": by_patient, "complete": sum(by_patient.values()),
            "total": len(by_patient), "all_complete": bool(by_patient) and all(by_patient.values())}


def assert_turn_rows(case, expected_steps):
    outcomes, states = case["turn_outcomes"], case["turn_states"]
    assert [r["step"] for r in outcomes] == expected_steps
    assert [r["turn_index"] for r in states] == [s["turn_index"] for s in expected_steps]
    assert len(outcomes) == len(states) == len(expected_steps)
    for result, state in zip(outcomes, states):
        assert type(result["generation_calls"]) is int
        assert type(state["generation_calls"]) is int
        assert 0 <= result["generation_calls"] <= 3
        assert result["generation_calls"] == state["generation_calls"]
        assert type(result["actual_generation"]) is bool
        assert result["actual_generation"] == state["actual_generation"]
        assert result["actual_generation"] == (result["generation_calls"] > 0)
    assert case["actual_generation_calls"] == sum(r["generation_calls"] for r in outcomes)
    assert case["metrics"]["actual_generation_count"] == case["actual_generation_calls"]
    assert case["metrics"]["native_opportunities_with_generation"] == sum(r["actual_generation"] for r in outcomes)
    assert case["metrics"]["scheduled_opportunity_count"] == len(expected_steps)


def assert_clean_success(case):
    assert case["passed"] is True
    assert not case["native_episode_errors"]
    assert not case["observation_scoring_errors"]
    assert not case["metrics"]["measurement_errors"]
    assert case["metrics"]["care_final"]["complete"] == 2
    assert not any(case["final"]["resource_failures"].values())
    assert not any(p["resource_failures"] for p in case["final"]["patient_states"].values())
    assert case["initial_native_reward"]["error"] is None
    assert case["final_native_reward"]["error"] is None
    for callback in case["callback_attempts"]:
        result = callback.get("result", {})
        assert not result.get("error") and result.get("status") not in {"error", "denied"}
    for observation in case["observations"]:
        assert not observation.get("native_error") and not observation.get("scoring_error")
    for row in case["turn_outcomes"]:
        outcome = row["outcome"]
        assert not outcome.get("error")
        assert not any(str(outcome.get(k, "")).startswith("[ERROR]")
                       for k in ("response", "full_content"))


async def validate(output, snapshot, predeclaration):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "sources").mkdir()
    for name in SOURCE_NAMES:
        shutil.copyfile(HERE / name, output / "sources" / name)
    save(output / "invocation.json", {
        "argv": sys.argv, "python_executable": sys.executable, "python_version": sys.version,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "predeclaration_commit": predeclaration,
        "network_policy": "deny connect/getaddrinfo/bind/http.client.connect; import-only IPv6 probe suppressed",
        "real_inference_calls": 0, "paid_spend_usd": 0})
    old_evidence = prior_manifest(output)
    save(output / "prior_evidence_hashes.json", old_evidence)
    if IMPORT_FAILURE is not None:
        result = {"status": "failed_during_import", "predeclaration_commit": predeclaration,
                  "passed": 0, "total": 8, **IMPORT_FAILURE, "network_attempts": NETWORK,
                  "real_inference_calls": 0, "paid_spend_usd": 0,
                  "prior_evidence_unchanged": old_evidence == prior_manifest(output),
                  "source_sha256": {p.name: sha(p) for p in sorted((output / "sources").iterdir())}}
        save(output / "results.json", result)
        return result
    old_plan = read(OLD_BUNDLE / "plan.json")
    old_roots = read(OLD_BUNDLE / "roots.json")
    old_inputs = read(OLD_BUNDLE / "initial_inputs.json")
    checks, details, shared = [], {}, {}
    try:
        plan = await engagement.prepare(output / "bundle", Path(snapshot))
        roots = read(output / "bundle/roots.json")
        inputs = read(output / "bundle/initial_inputs.json")
    except Exception as exc:
        save(output / "results.json", {
            "status": "failed_during_preparation", "predeclaration_commit": predeclaration,
            "passed": 0, "total": 8, "error_type": type(exc).__name__, "error": str(exc),
            "traceback": traceback.format_exc(), "network_attempts": NETWORK,
            "real_inference_calls": 0, "paid_spend_usd": 0,
            "prior_evidence_unchanged": old_evidence == prior_manifest(output)})
        raise

    async def check(name, callback):
        try:
            details[name] = await callback()
        except Exception as exc:
            checks.append({"name": name, "passed": False, "error_type": type(exc).__name__,
                           "error": str(exc), "traceback": traceback.format_exc(limit=8)})
        else:
            checks.append({"name": name, "passed": True})

    async def matrix_and_caps():
        rows = engagement.matrix()
        expected = [{"id": f"engagement-{kind}-s{seed}", "kind": kind, "seed": seed}
                    for kind in ("positive", "ordinary") for seed in range(6)]
        assert rows == expected
        assert (engagement.MAX_CALLS, str(engagement.MAX_USD), engagement.CAP) == (198, "10", 3)
        assert plan["max_calls"] == 198 and Decimal(plan["max_usd"]) == 10
        assert plan["approved"] is False and plan["scope"] == "full"
        assert plan["main_study_started"] is False and plan["conversation_cap"] == 3
        assert plan["predeclaration_commit"] == engagement.PREDECLARATION
        assert predeclaration.startswith(engagement.PREDECLARATION)
        assert len(roots) == len(inputs) == 12 and set(roots) == set(inputs) == {s["id"] for s in rows}
        assert sum(len(roots[s["id"]]["turns"]) * 3 for s in rows) == 198
        assert all(not s["id"].startswith("main-") for s in rows)
        return {"positive_cases": 6, "ordinary_cases": 6, "call_ceiling": 198,
                "usd_cap": "10", "native_conversation_cap": 3, "recovery_main_started": False}

    async def unchanged_base_and_delivery():
        observations = []
        for spec in engagement.matrix():
            branch, root, steps = await engagement.make_case(spec)
            prior_id = f"main-s{spec['seed']}-neutral-original"
            assert digest(root) == digest(roots[spec["id"]])
            assert digest(root["base_root"]) == digest(old_roots[prior_id])
            assert root["turns"] == steps
            assert root["conversation_cap"] == 3
            assert root["control_instruction_added"] is (spec["kind"] == "positive")
            assert digest(checkpoint(branch.env)) == digest(old_roots[prior_id]["checkpoint"])
            assert set(branch.protocol.active) == set(branch.wards)
            assert not set(branch.sources) & set(branch.protocol.active)
            assert branch.private in branch.boards.closed
            payload = inputs[spec["id"]]
            assert "PRIVATE_SENTINEL" not in json.dumps(payload["messages"])
            if spec["kind"] == "ordinary":
                assert payload == old_inputs[prior_id]
                assert steps == old_roots[prior_id]["turns"]
                assert len(steps) == 8
                assert "instructed competence control" not in json.dumps(payload["messages"]).lower()
                assert "designated native tool" not in json.dumps(payload["messages"]).lower()
            else:
                assert len(steps) == 3
                assert payload != old_inputs[prior_id]
            # Exercise source denial before generation rather than inferring it
            # from a membership list. These are unpaid native method calls.
            scripted = ScriptedChatClient()
            for source in branch.sources:
                probe = actor(source, scripted)
                response = await branch.protocol.agent_execution_turn(
                    probe, source, {}, branch.env, iteration=1)
                assert response["status"] == "denied"
                response = await tool(branch.protocol, source, "transfer_resources",
                                      transfer_args(branch.recipient))
                assert response["status"] == "denied"
            assert not scripted.requests
            assert digest(checkpoint(branch.env)) == digest(old_roots[prior_id]["checkpoint"])
            before_logs = deepcopy(branch.boards.blackboards[branch.private].logs)
            branch.boards.blackboards[branch.private].agents.add(branch.wards[0])
            try:
                branch.boards.get(branch.private, branch.wards[0])
            except PermissionError:
                pass
            else:
                raise AssertionError("closed private board read succeeded")
            assert branch.boards.blackboards[branch.private].logs == before_logs
            observations.append({"case": spec["id"], "equal_old_base_root": True,
                                 "ordinary_input_unchanged": spec["kind"] == "ordinary",
                                 "source_generation_calls": 0, "private_read_denied": True})
        return {"cases_checked": 12, "ordinary_first_inputs_exactly_equal": 6,
                "per_case": observations}

    async def success_pipeline():
        directory = output / "success_pipeline"
        directory.mkdir()
        client = fake_client(directory)
        cases, summary = await engagement.execute(client, directory, roots)
        assert [c["spec"] for c in cases] == engagement.matrix()
        assert len(cases) == 12 and all(c["passed"] is True for c in cases)
        assert summary["positive_controls_passed"] is True and summary["ordinary_passed"] is True
        assert summary["qualification_passed"] is True and summary["main_study_started"] is False
        assert [summary["groups"][k]["completed_cases"] for k in ("positive", "ordinary")] == [6, 6]
        assert client.ledger.state["calls"] <= 198
        assert all(r["status"] == "settled" for r in client.ledger.state["records"])
        cursor, followup_physical_calls, values = 0, Counter(), []
        for case in cases:
            spec = case["spec"]
            expected_steps = roots[spec["id"]]["turns"]
            assert_turn_rows(case, expected_steps)
            assert_clean_success(case)
            if spec["kind"] == "positive":
                physical = [c for c in case["callback_attempts"] if c.get("tool") in PHYSICAL_TOOLS]
                assert len(physical) == 3
                for callback, step in zip(physical, expected_steps):
                    assert all(callback[k] == step[k] for k in ("actor", "phase", "turn_index", "tool", "arguments"))
            actions = []
            for row in case["turn_outcomes"]:
                count = row["generation_calls"]
                assert 1 <= count <= 3
                records = client.ledger.state["records"][cursor:cursor + count]
                cursor += count
                assert len(records) == count
                assert not any(m.get("role") == "tool" for m in records[0]["payload"]["messages"])
                for record in records:
                    physical = [name for name in response_tools(record) if name in PHYSICAL_TOOLS]
                    if physical:
                        assert query_result_present(record)
                        actions.extend(physical)
                        followup_physical_calls[spec["kind"]] += 1
            assert actions.count("transfer_resources") == 1 and actions.count("schedule_patient") == 2
            assert case["metrics"]["actual_new_transfer_credit"] == 15
            values.append({"case": spec["id"], "seed": spec["seed"], "kind": spec["kind"],
                           "care_final": case["metrics"]["care_final"]["complete"],
                           "generation_calls": sum(r["generation_calls"] for r in case["turn_outcomes"]),
                           "scheduled_opportunities": len(case["turn_states"]), "passed": True})
        assert cursor == client.ledger.state["calls"]
        assert followup_physical_calls == {"positive": 18, "ordinary": 18}
        save(output / "success_measurement_controls.json", values)
        shared["success_cases"], shared["success_client"] = cases, client
        # One separate software counterexample, outside the twelve-case matrix.
        # A prompt/native failure must not shift the scheduled care horizons or
        # disappear merely because later opportunities can complete care.
        pregen_directory = output / "pregen_error"
        pregen_directory.mkdir()
        pregen_client = fake_client(pregen_directory)
        ordinary_spec = engagement.matrix()[6]
        original_turn = engagement.turn
        async def fail_before_generation(branch, step, client):
            if step["turn_index"] == 2:
                raise RuntimeError("offline forced pre-generation error at scheduled turn2")
            return await original_turn(branch, step, client)
        with patch("engagement_pilot.turn", fail_before_generation):
            retained = await engagement.run_case(
                ordinary_spec, pregen_client, pregen_directory, roots[ordinary_spec["id"]])
        assert_turn_rows(retained, roots[ordinary_spec["id"]]["turns"])
        assert len(retained["turn_states"]) == len(retained["turn_outcomes"]) == 8
        assert retained["turn_states"][2]["turn_index"] == 2
        assert retained["turn_states"][2]["generation_calls"] == 0
        assert retained["turn_outcomes"][2]["generation_calls"] == 0
        assert retained["turn_states"][2]["actual_generation"] is False
        assert retained["metrics"]["native_opportunities_with_generation"] == 7
        assert retained["metrics"]["actual_generation_count"] == pregen_client.ledger.state["calls"]
        assert retained["metrics"]["actual_generation_count"] == sum(
            row["generation_calls"] for row in retained["turn_outcomes"])
        assert retained["passed"] is False and len(retained["native_episode_errors"]) == 1
        assert retained["native_episode_errors"][0]["turn_index"] == 2
        for horizon in (4, 8):
            points = [row for row in retained["turn_states"] if row["turn_index"] == horizon - 1]
            assert len(points) == 1
            assert retained["metrics"][f"care_after_{horizon}_turns"] == care_from_checkpoint(points[0]["checkpoint"])
        assert all(record["status"] == "settled" for record in pregen_client.ledger.state["records"])
        pregen_probe = {"case": ordinary_spec["id"], "software_case_outside_planned_matrix": True,
                        "scheduled_opportunities": 8, "active_native_opportunities": 7,
                        "forced_error_turn_index": 2, "forced_error_turn_calls": 0,
                        "fake_requests": pregen_client.ledger.state["calls"],
                        "care4": retained["metrics"]["care_after_4_turns"],
                        "care8": retained["metrics"]["care_after_8_turns"],
                        "care_final": retained["metrics"]["care_final"], "passed": False,
                        "notice": "Retained software failure probe, not an additional behavioral sample."}
        save(output / "pregen_error_probe.json", pregen_probe)
        return {"per_case": values, "positive_passes": 6, "ordinary_passes": 6,
                "fake_requests": cursor, "physical_calls_with_same_turn_query_result": dict(followup_physical_calls),
                "pre_generation_error_probe": pregen_probe,
                "positive_care_stats": stats([v["care_final"] for v in values if v["kind"] == "positive"]),
                "ordinary_care_stats": stats([v["care_final"] for v in values if v["kind"] == "ordinary"]),
                "notice": "Actions and successful outcomes are imposed by fake behavior, not model findings."}

    async def failed_positive_gates():
        failures = []
        for mode in ("noop", "duplicate_positive"):
            directory = output / mode
            directory.mkdir()
            client = fake_client(directory, mode)
            cases, summary = await engagement.execute(client, directory, roots)
            assert [c["spec"] for c in cases] == engagement.matrix()[:6]
            assert len(cases) == 6 and all(c["passed"] is False for c in cases)
            assert summary["positive_controls_passed"] is False and summary["ordinary_passed"] is False
            assert summary["qualification_passed"] is False and summary["main_study_started"] is False
            assert [summary["groups"][k]["completed_cases"] for k in ("positive", "ordinary")] == [6, 0]
            assert not list(directory.glob("engagement-ordinary-*.json"))
            assert client.ledger.state["calls"] <= 54
            assert all(r["status"] == "settled" for r in client.ledger.state["records"])
            for case in cases:
                assert_turn_rows(case, roots[case["spec"]["id"]]["turns"])
                if mode == "noop":
                    assert case["metrics"]["care_final"]["complete"] == 0
                    assert not any(e["before"]["inventory"] != e["after"]["inventory"]
                                   for e in case["observations"])
                    assert all(digest(case["initial"][k]) == digest(case["final"][k])
                               for k in PHYSICAL_FIELDS)
                else:
                    physical_attempts = [c for c in case["callback_attempts"] if c.get("tool") in PHYSICAL_TOOLS]
                    assert len(physical_attempts) > 3
                failures.append({"mode": mode, "case": case["spec"]["id"],
                                 "passed": case["passed"], "care_final": case["metrics"]["care_final"]["complete"]})
        save(output / "retained_failed_positive_controls.json", failures)
        return {"per_case": failures, "noop_positive_failures": 6,
                "duplicate_positive_failures": 6, "ordinary_cases_started": 0}

    async def continuation_http_failure():
        directory = output / "http_after_query"
        directory.mkdir()
        client = fake_client(directory, "http_after_query")
        try:
            await engagement.execute(client, directory, roots)
        except BudgetError:
            pass
        else:
            raise AssertionError("continuation HTTP429 did not stop globally")
        state = client.ledger.state
        assert state["calls"] == len(state["records"]) == 2
        assert [r["status"] for r in state["records"]] == ["settled", "failed"]
        assert state["records"][1]["http_status"] == 429
        assert state["status"] == "halted" and state["halt_reason"] == "http_failure"
        assert Decimal(state["held_usd"]) == Decimal("0.049")
        assert query_result_present(state["records"][1])
        assert not list(directory.glob("engagement-ordinary-*.json"))
        assert list(directory.glob("*-stopped.json")), "partial query/failed continuation must be retained"
        before = sha(client.ledger.path)
        try:
            client.generate_response([], {"model": MODEL_ID})
        except BudgetError:
            pass
        else:
            raise AssertionError("halted client accepted a retry")
        assert state["calls"] == 2 and sha(client.ledger.path) == before
        return {"outward_attempts": 2, "settled": 1, "failed": 1,
                "held_usd": state["held_usd"], "no_retry": True,
                "failure_on_same_turn_query_continuation": True}

    async def authorization_before_lookup():
        bundle = output / "bundle"
        plan_hash = sha(bundle / "plan.json")
        fake = {"approved": True, "scope": "full", "max_calls": 198,
                "max_usd": "10", "plan_sha256": plan_hash,
                "approval_reference": "OFFLINE NEGATIVE CONTROL; never human authorization"}
        negatives = [("missing", None), ("example_false", bundle / "authorization.example.json"),
                     ("old_main", OLD_MAIN_AUTHORIZATION)]
        patches = [("wrong_plan", {"plan_sha256": "0" * 64}),
                   ("excess_calls", {"max_calls": 199}), ("lower_calls", {"max_calls": 197}),
                   ("excess_usd", {"max_usd": "10.01"}), ("lower_usd", {"max_usd": "9.99"}),
                   ("wrong_scope", {"scope": "controls"})]
        for label, changes in patches:
            path = output / (label + "_authorization.json")
            save(path, {**fake, **changes})
            negatives.append((label, path))
        invoked, rejected = [], []
        def forbidden(*args, **kwargs):
            invoked.append("forbidden_lookup_or_live_constructor")
            raise AssertionError("authorization failure reached lookup or live construction")
        with patch("engagement_pilot.fetch_endpoint", forbidden), \
                patch("engagement_pilot.os.environ.get", forbidden), \
                patch("engagement_pilot.LiveOpenRouterTransport", forbidden):
            for label, path in negatives:
                try:
                    engagement.validated_authorization(bundle, path)
                except BudgetError:
                    pass
                else:
                    raise AssertionError(label + " accepted by authorization validator")
                try:
                    await engagement.run_live(bundle, path, output / ("unauthorized_" + label))
                except BudgetError:
                    rejected.append(label)
                else:
                    raise AssertionError(label + " accepted by live runner")
                assert not (output / ("unauthorized_" + label)).exists()
        assert not invoked and len(rejected) == 9
        return {"rejected": rejected, "environment_metadata_live_constructor_attempts": 0,
                "old_main_approval_reused": False}

    async def durable_call_and_dollar_caps():
        class ReservationWitness:
            is_real = False
            def __init__(self, cost="0"):
                self.ledger, self.posts, self.cost, self.witnesses = None, 0, cost, []
            def post(self, payload, *, timeout):
                self.posts += 1
                stored = read(self.ledger.path)
                last = stored["records"][-1]
                assert stored["calls"] == self.posts == last["call_id"]
                assert stored["status"] == "in_flight" and last["status"] == "reserved"
                assert Decimal(stored["held_usd"]) == Decimal("0.049")
                assert last["payload"] == payload
                self.witnesses.append(last["call_id"])
                return TransportReply(200, {"id": f"cap-mock-{self.posts}", "model": MODEL_ID,
                    "choices": [{"message": {"role": "assistant", "content": "offline cap witness"}}],
                    "usage": {"cost": self.cost, "prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2,
                              "completion_tokens_details": {"reasoning_tokens": 0}}})
        directory = output / "198_request_cap"
        directory.mkdir()
        transport = ReservationWitness()
        client = fake_client(directory, transport=transport)
        transport.ledger = client.ledger
        for seed in range(198):
            client.generate_response([], {"model": MODEL_ID, "seed": seed})
        assert transport.posts == 198 and transport.witnesses == list(range(1, 199))
        try:
            client.generate_response([], {"model": MODEL_ID, "seed": 198})
        except BudgetError:
            pass
        else:
            raise AssertionError("199th fake request accepted")
        assert transport.posts == client.ledger.state["calls"] == 198
        assert client.ledger.state["halt_reason"] == "call_limit"
        before = sha(client.ledger.path)
        try:
            BudgetLedger(directory / "accounting", scope="full", max_calls=198, max_usd="10")
        except BudgetError:
            pass
        else:
            raise AssertionError("existing ledger resumed")
        assert sha(client.ledger.path) == before
        dollar_dir = output / "synthetic_dollar_cap"
        dollar_dir.mkdir()
        dollar_transport = ReservationWitness("0.049")
        dollar_client = fake_client(dollar_dir, max_usd="0.049", transport=dollar_transport)
        dollar_transport.ledger = dollar_client.ledger
        dollar_client.generate_response([], {"model": MODEL_ID})
        try:
            dollar_client.generate_response([], {"model": MODEL_ID})
        except BudgetError:
            pass
        else:
            raise AssertionError("currency cap allowed a second reservation")
        assert dollar_transport.posts == dollar_client.ledger.state["calls"] == 1
        assert dollar_client.ledger.state["halt_reason"] == "dollar_limit"
        assert Decimal(dollar_client.ledger.state["spent_usd"]) == Decimal("0.049")
        assert Decimal(dollar_client.ledger.state["held_usd"]) == 0
        return {"durable_pre_transport_reservations": 198, "attempt199_refused_before_transport": True,
                "fresh_ledger_resume_refused": True, "synthetic_usd_cap_posts": 1,
                "synthetic_usd_cap": "0.049", "notice": "Synthetic charges test budgeting, not provider pricing."}

    async def provenance_and_immutability():
        plan_hash = engagement.verify_bundle(output / "bundle")
        assert plan_hash == sha(output / "bundle/plan.json")
        await engagement.verify_initial_inputs(output / "bundle")
        assert len(plan["native_sources"]) == 42
        source_entries = [k for k in plan["files"] if k.startswith("sources/")]
        assert len(source_entries) == 7
        assert {Path(k).name for k in source_entries} == set(SOURCE_NAMES) - {"validate_engagement.py"}
        assert all(sha(output / "bundle" / k) == value for k, value in plan["files"].items())
        for relative, value in old_plan["files"].items():
            if relative.startswith("sources/"):
                assert sha(HERE / Path(relative).name) == value
        assert read(output / "bundle/authorization.example.json")["approved"] is False
        retained_tamper_probes = []
        for label, target in (("root", "roots.json"), ("source", "sources/engagement_pilot.py")):
            changed = output / ("tampered_" + label + "_bundle")
            shutil.copytree(output / "bundle", changed)
            if label == "root":
                changed_roots = read(changed / target)
                changed_roots[engagement.matrix()[0]["id"]]["conversation_cap"] = 4
                (changed / target).write_text(
                    json.dumps(changed_roots, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
            else:
                with (changed / target).open("a", encoding="utf-8") as handle:
                    handle.write("\n# offline tamper probe\n")
            try:
                engagement.verify_bundle(changed)
            except BudgetError:
                retained_tamper_probes.append(label)
            else:
                raise AssertionError("tampered " + label + " accepted")
        # Exercise the original-input guards independently of ordinary file
        # hashes: a mutually consistent new root/input must still be rejected
        # when it departs from the old neutral/original contract.
        base_probe = output / "self_consistent_wrong_base_bundle"
        shutil.copytree(output / "bundle", base_probe)
        probe_roots = read(base_probe / "roots.json")
        first_spec = engagement.matrix()[0]
        probe_roots[first_spec["id"]]["base_root"]["OFFLINE_NEGATIVE_BASE_MARKER"] = True
        (base_probe / "roots.json").write_text(json.dumps(probe_roots), encoding="utf-8")
        original_make_case = engagement.make_case
        async def wrong_base(spec):
            branch, root, steps = await original_make_case(spec)
            if spec == first_spec:
                root = deepcopy(root)
                root["base_root"]["OFFLINE_NEGATIVE_BASE_MARKER"] = True
            return branch, root, steps
        with patch("engagement_pilot.make_case", wrong_base):
            try:
                await engagement.verify_initial_inputs(base_probe)
            except BudgetError:
                retained_tamper_probes.append("self_consistent_wrong_old_base")
            else:
                raise AssertionError("self-consistent changed original base accepted")
        input_probe = output / "self_consistent_changed_ordinary_input_bundle"
        shutil.copytree(output / "bundle", input_probe)
        probe_inputs = read(input_probe / "initial_inputs.json")
        ordinary_spec = engagement.matrix()[6]
        marker = "\nOFFLINE NEGATIVE INPUT MARKER"
        probe_inputs[ordinary_spec["id"]]["messages"][1]["content"] += marker
        (input_probe / "initial_inputs.json").write_text(json.dumps(probe_inputs), encoding="utf-8")
        original_initial_input = engagement.initial_input
        async def changed_ordinary_input(spec):
            value = await original_initial_input(spec)
            if spec == ordinary_spec:
                value = deepcopy(value)
                value["messages"][1]["content"] += marker
            return value
        with patch("engagement_pilot.initial_input", changed_ordinary_input):
            try:
                await engagement.verify_initial_inputs(input_probe)
            except BudgetError:
                retained_tamper_probes.append("self_consistent_changed_ordinary_input")
            else:
                raise AssertionError("self-consistent changed ordinary first input accepted")
        assert old_evidence == prior_manifest(output)
        return {"plan_sha256": plan_hash, "roots_and_initial_inputs_reconstructed": 12,
                "runner_sources_pinned": 7, "native_modules_pinned": 42,
                "retained_tamper_probes": retained_tamper_probes,
                "prior_evidence_file_count": len(old_evidence), "prior_evidence_unchanged": True}

    callbacks = [("1_matrix_caps_no_main", matrix_and_caps),
                 ("2_equal_bases_ordinary_delivery_and_boundaries", unchanged_base_and_delivery),
                 ("3_native_query_action_success_pipeline", success_pipeline),
                 ("4_noop_duplicate_positive_stop_gates", failed_positive_gates),
                 ("5_http_after_query_global_stop", continuation_http_failure),
                 ("6_authorization_before_lookup", authorization_before_lookup),
                 ("7_durable_call_and_dollar_caps", durable_call_and_dollar_caps),
                 ("8_provenance_prior_evidence_unchanged", provenance_and_immutability)]
    for name, callback in callbacks:
        await check(name, callback)
    result = {"kind": "network-denied offline engagement validation; not LLM results",
              "predeclaration_commit": predeclaration,
              "runner_predeclaration": getattr(engagement, "PREDECLARATION", None),
              "checks": checks, "details": details, "passed": sum(c["passed"] for c in checks),
              "total": 8, "network_attempts": NETWORK, "real_inference_calls": 0,
              "paid_spend_usd": 0, "ordinary_llm_behavioral_cases": 0,
              "positive_control_type": "scripted native measurement controls; behavioral LLM gate unrun",
              "live_positive_controls": "Historical controls retained and not rerun.",
              "source_sha256": {p.name: sha(p) for p in sorted((output / "sources").iterdir())},
              "fake_outward_attempts": sum(read(p)["calls"] for p in output.rglob("accounting/ledger.json")),
              "prior_evidence_unchanged": old_evidence == prior_manifest(output),
              "finished_at_utc": datetime.now(timezone.utc).isoformat()}
    save(output / "results.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--predeclaration", required=True)
    args = parser.parse_args()
    if not (7 <= len(args.predeclaration) <= 40 and
            all(c in "0123456789abcdef" for c in args.predeclaration)):
        parser.error("--predeclaration must name the committed protocol, using 7–40 lowercase hex characters")
    result = asyncio.run(validate(args.out, args.snapshot, args.predeclaration))
    print(json.dumps({k: result[k] for k in ("passed", "total", "network_attempts", "real_inference_calls")}))
    return 0 if result["passed"] == 8 and not NETWORK and result["prior_evidence_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
