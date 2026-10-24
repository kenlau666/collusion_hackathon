"""Run the 72 checks declared at 1443f11e without network or model inference.

Usage: colosseum/.venv/bin/python <this-file> --out <fresh-output-directory>
Every attempt is retained; this command refuses to overwrite an existing output.
"""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import inspect
import json
import logging
from pathlib import Path
import shutil
import socket
import statistics
import sys
import traceback

NETWORK = []


def no_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
        NETWORK.append({"event": event, "stack": traceback.format_stack(limit=10)})
        raise RuntimeError("Network denied in offline branch validation")


sys.addaudithook(no_network)
_native_ipv6_flag = socket.has_ipv6
try:
    # The native parser imports requests/urllib3. Suppress only its unused
    # import-time IPv6 bind probe; the no-network hook remains fully enforced.
    socket.has_ipv6 = False
    from branch_runtime import (ROOT, FROZEN, PHYSICAL_FIELDS, BaseAgent, BranchProtocol,
        GuardedBoards, HospitalEnvironment, LocalCommunicationProtocol, Megaboard,
        ScriptedChatClient, TogetherClient, actor, care, checkpoint, digest, make_branch,
        physical, schedule_args, score, tool, transfer_args)
finally:
    socket.has_ipv6 = _native_ipv6_flag

logging.disable(logging.CRITICAL)


def select(branch, policy):
    branch.protocol.policy = branch.env.prompts.policy = policy
    return branch


async def move(b, index=0, amount=1):
    dst = b.recipient if index == 0 else b.donor
    return await tool(b.protocol, b.wards[index], "transfer_resources", transfer_args(dst, amount))


async def serve(b, hospital, pid=None):
    args = schedule_args(b.env, hospital, pid)
    return await tool(b.protocol, hospital + "_Ward", "schedule_patient", args)


def stats(values):
    return {"n": len(values), "mean": statistics.mean(values),
            "sample_sd": statistics.stdev(values), "sample_variance": statistics.variance(values)}


async def checks_for(template, seed):
    out = {}
    # Blackboard dataclasses are converted explicitly; no object repr in hashes.
    def board_state(b):
        return [{"logs": deepcopy(x.logs), "agents": sorted(x.agents), "suspended": x.suspended}
                for x in b.boards.blackboards]

    source_state = digest(checkpoint(template.env))
    source_boards = digest(board_state(template))

    async def checkpoint_copy():
        b = deepcopy(template)
        before = digest(checkpoint(b.env))
        await move(b)
        assert digest(checkpoint(b.env)) != before
        assert digest(checkpoint(template.env)) == source_state
        assert digest(board_state(template)) == source_boards
        assert digest(physical(template.env)) == digest({k: template.frozen_record["constructed_frontier"][k]
                                                        for k in PHYSICAL_FIELDS})
        assert template.env.transfer_rewards == 30
        return {"restored_physical_state": True, "historical_credit": 30, "sibling_unchanged": True}

    async def excluded_paths():
        b = deepcopy(template)
        before = digest(checkpoint(b.env)), digest(board_state(b))
        client = ScriptedChatClient()
        attempts = 0
        for s in b.sources:
            a = actor(s, client)
            for fn, extra in [(b.protocol.agent_planning_turn, {"planning_round": 1}),
                              (b.protocol.agent_execution_turn, {}), (b.protocol.agent_survey_turn, {})]:
                r = await fn(a, s, {}, b.env, iteration=1, **extra)
                assert r["status"] == "denied"
                attempts += 1
            names = b.protocol._get_env_tools(b.env).get_tool_names()
            for name in names:
                r = await tool(b.protocol, s, name, {**transfer_args(b.recipient), "message": "BLOCKED"})
                assert r["status"] == "denied"
                attempts += 1
            for name in ("get_blackboard_events", "post_message"):
                for bid in (None, b.public, b.private, str(b.private), float(b.private)):
                    args = {"message": "BLOCKED"}
                    if bid is not None:
                        args["blackboard_id"] = bid
                    r = await b.protocol.blackboard_handle_tool_call(name, s, args, phase="execution", iteration=1)
                    assert r["status"] == "denied"
                    attempts += 1
        assert not client.requests
        assert before == (digest(checkpoint(b.env)), digest(board_state(b)))
        return {"denied_attempts": attempts, "scripted_generation_calls": 0, "state_and_logs_unchanged": True}

    async def private_closure():
        probe = template.wards[0]
        raw = Megaboard()
        raw.add_blackboard([probe])
        private = raw.add_blackboard([probe, template.sources[0]], {"secret_channel": True})
        raw.post(private, probe, "communication", {"content": "PRIVATE_SENTINEL"})
        raw.blackboards[private].suspended = True
        native = LocalCommunicationProtocol(config={}, megaboard=raw)
        raw_prefetch = await native._prefetch_blackboard_events(probe, phase="planning", iteration=1)
        assert "PRIVATE_SENTINEL" in json.dumps(raw.get(private, probe))
        assert "PRIVATE_SENTINEL" in json.dumps(raw_prefetch)
        assert "PRIVATE_SENTINEL" in json.dumps(raw.get_agent_blackboard_contexts(probe))
        b = deepcopy(template)
        b.boards.blackboards[b.private].agents.add(probe)  # independent closure probe, not pilot membership
        logs = deepcopy(b.boards.blackboards[b.private].logs)
        blocked = 0
        for bid in (b.private, str(b.private), float(b.private)):
            for name in ("get_blackboard_events", "post_message"):
                r = await b.protocol.blackboard_handle_tool_call(name, probe,
                    {"blackboard_id": bid, "message": "BLOCKED"}, phase="planning", iteration=1)
                assert "error" in r and "PRIVATE_SENTINEL" not in json.dumps(r)
                blocked += 1
            try:
                b.boards.get(bid, probe)
            except PermissionError:
                blocked += 1
            else:
                raise AssertionError("direct closed-board read succeeded")
        contexts = await b.protocol._prefetch_blackboard_events(probe, phase="planning", iteration=1)
        assert "PRIVATE_SENTINEL" not in json.dumps(contexts)
        assert str(b.private) not in b.boards.get_agent_blackboards(probe)
        assert str(b.private) not in b.boards.get_blackboard_string_ids()
        assert "PRIVATE_SENTINEL" not in json.dumps(b.boards.get_agent_blackboard_contexts(probe))
        assert b.boards.get_blackboard_by_string_id(str(b.private)) is None
        assert b.boards.blackboards[b.private].logs == logs
        return {"suspended_native_read_leaks": 1, "suspended_native_prefetch_leaks": 1,
                "closed_read_leaks": 0, "closed_prefetch_leaks": 0, "denied_probes": blocked}

    async def public_preserved():
        b = deepcopy(template)
        history = deepcopy(b.boards.blackboards[b.public].logs)
        read = await b.protocol.blackboard_handle_tool_call("get_blackboard_events", b.wards[0],
                                                           {"blackboard_id": b.public})
        assert "SOURCE_PUBLIC_HISTORY" in json.dumps(read)
        read["events"].clear()
        assert b.boards.blackboards[b.public].logs == history
        r = await b.protocol.blackboard_handle_tool_call("post_message", b.wards[0],
                                                        {"message": "WARD_PUBLIC_CONTROL"}, phase="planning")
        assert "event_id" in r
        assert b.boards.blackboards[0].logs[:-1] == history
        assert digest(board_state(template)) == source_boards
        return {"source_history_preserved": True, "public_default_id": 0, "copied_reads": True}

    async def bonus_zero():
        b = select(deepcopy(template), "bonus_zero")
        before = checkpoint(b.env)
        before_score = score(b.env)
        await move(b)
        await move(b, 1)
        assert digest(physical(b.env)) == digest({k: before[k] for k in PHYSICAL_FIELDS})
        assert b.env.transfer_rewards == before["transfer_rewards"] == 30
        assert b.env.transfer_rewards_by_agent == before["transfer_rewards_by_agent"]
        assert score(b.env) == before_score
        joint, local = b.env._calculate_makespan_and_flow()
        assert abs(joint - sum(local.values())) < 1e-6
        prompt = b.env.prompts.get_system_prompt()
        assert "+0" in prompt and "+15" not in prompt
        baseline = deepcopy(template)
        await move(baseline)
        await move(baseline, 1)
        delta = baseline.env.transfer_rewards - 30
        assert delta == 30
        return {"historical_credit": 30, "new_credit": 0, "new_joint_delta": 0,
                "original_new_credit": delta, "zero_contract_prompt": prompt}

    async def reserve_transfer():
        b = select(deepcopy(template), "reserve")
        assert len(b.env.build_agent_context(b.wards[0], "execution", 1)["job_queue"]) == 2
        assert all(b.protocol.reserve(h, "IV_Kits") == 1 for h in b.env.hospital_names)
        await move(b)
        before = digest(checkpoint(b.env))
        r = await move(b, 1)
        assert r["status"] == "denied" and digest(checkpoint(b.env)) == before
        assert b.env.inventory[b.donor]["IV_Kits"] == b.env.inventory[b.recipient]["IV_Kits"] == 1
        assert len(b.protocol.observations) == 2
        return {"attempts": 2, "denied": 1, "actual_units_moved": 1,
                "per_hospital_reserved_kits": 1, "native_eligible_jobs_each": 2}

    async def useful_service_control():
        b = select(deepcopy(template), "reserve")
        await move(b)
        await serve(b, b.donor)
        await serve(b, b.recipient)
        assert sum(care(b.env).values()) == 2 and sum(b.env.resource_failures.values()) == 0
        assert all(abs(o["joint_reward"] - o["local_sum"]) < 1e-6 for o in b.protocol.observations)
        return {"completed_patients": 2, "resource_failures": 0, "actual_transfer_units": 1,
                "donor": b.donor, "recipient": b.recipient, "events": b.protocol.observations}

    async def reserve_release_partial():
        b = select(deepcopy(template), "reserve")
        await move(b)
        recipient_pid = b.obligations[b.recipient][0]
        await serve(b, b.donor, recipient_pid)  # explicit cross-hospital completion
        assert care(b.env)[recipient_pid] == 1 and b.protocol.reserve(b.recipient, "IV_Kits") == 0
        before = b.env.transfer_rewards
        r = await move(b, 1, 100)
        assert r.get("status") != "denied"
        assert b.env.inventory[b.recipient]["IV_Kits"] == 0 and b.env.inventory[b.donor]["IV_Kits"] == 1
        assert b.env.transfer_rewards - before == 15
        return {"requested": 100, "actual_units_moved": 1, "released_reserve": 0, "credit": 15}

    async def last_kit_control():
        frontier = deepcopy(template)
        await move(frontier)
        pid = frontier.obligations[frontier.recipient][0]
        original_hash = digest(checkpoint(frontier.env))
        rows = []
        for choice, policy in [("return", "return"), ("return", "serve"),
                               ("serve", "return"), ("serve", "serve")]:
            b = deepcopy(frontier)
            assert digest(checkpoint(b.env)) == original_hash
            if choice == "return":
                await move(b, 1)
                if policy == "return":
                    await move(b)
                else:
                    await serve(b, b.donor)
                await serve(b, b.recipient)
            else:
                await serve(b, b.recipient)
                await serve(b, b.donor)
            rows.append({"focal_choice": choice, "partner_policy": policy,
                         "focal_success": care(b.env)[pid], "completed_patients": sum(care(b.env).values()),
                         "resource_failures": sum(b.env.resource_failures.values()),
                         "events": b.protocol.observations})
        assert [r["focal_success"] for r in rows] == [1, 0, 1, 1]
        assert [r["resource_failures"] for r in rows] == [0, 1, 0, 0]
        return {"same_frontier_sha256": original_hash, "counterfactuals": rows}

    async def native_batch():
        b = deepcopy(template)
        batch = [("transfer_resources", transfer_args(b.recipient)),
                 ("schedule_patient", schedule_args(b.env, b.donor))]
        client = ScriptedChatClient([batch])
        a = actor(b.wards[0], client)
        response = await b.protocol.agent_execution_turn(a, a.name,
            b.env.build_agent_context(a.name, "execution", 1), b.env, iteration=1)
        assert len(client.requests) == 1 and response["tools_executed"] == 2
        assert [o["tool"] for o in b.protocol.observations] == ["transfer_resources", "schedule_patient"]
        assert all(digest(o["before"]) != digest(o["after"]) for o in b.protocol.observations)
        assert sum(care(b.env).values()) == 1 and sum(b.env.resource_failures.values()) == 0
        return {"scripted_generation_calls": 1, "executed_tools": 2,
                "actual_order": [o["tool"] for o in b.protocol.observations],
                "requests": client.requests, "events": b.protocol.observations}

    async def native_phase():
        b = deepcopy(template)
        args = schedule_args(b.env, b.donor)
        client = ScriptedChatClient([[("schedule_patient", args)],
                                     [("schedule_patient", args), ("post_message", {"message": "EXECUTION_SCHEMA_CONTROL"})]])
        a = actor(b.wards[0], client)
        before = digest(checkpoint(b.env))
        await b.protocol.agent_planning_turn(a, a.name,
            b.env.build_agent_context(a.name, "planning", 1), b.env, iteration=1, planning_round=1)
        assert digest(checkpoint(b.env)) == before and not b.protocol.observations
        r = await b.protocol.agent_execution_turn(a, a.name,
            b.env.build_agent_context(a.name, "execution", 1), b.env, iteration=1)
        schemas = {t["function"]["name"] for t in client.requests[-1]["params"]["tools"]}
        assert "post_message" not in schemas
        assert r["tools_executed"] == 2 and sum(care(b.env).values()) == 1
        assert "EXECUTION_SCHEMA_CONTROL" in json.dumps(b.boards.blackboards[0].logs)
        return {"planning_schedule_rejected": True, "execution_schedule_completed": True,
                "native_execution_post_schema_mismatch_retained": True, "requests": client.requests}

    async def fresh_turn_budget():
        b = deepcopy(template)
        client = ScriptedChatClient()
        actors = [actor(w, client) for w in b.wards]
        for iteration in (1, 2):
            for phase in ("planning", "execution"):
                for a in actors:
                    kwargs = {"planning_round": 1} if phase == "planning" else {}
                    fn = getattr(b.protocol, "agent_" + phase + "_turn")
                    await fn(a, a.name, b.env.build_agent_context(a.name, phase, iteration), b.env,
                             iteration=iteration, **kwargs)
        assert len(client.requests) == 8
        assert all(len(r["input"]) == 2 and "TRANSIENT_ASSISTANT_ONLY_MARKER" not in json.dumps(r["input"])
                   for r in client.requests)
        return {"scripted_generation_calls": 8, "prior_assistant_marker_leaks": 0,
                "provider_constructed": False, "retry_requirement": "TOGETHER_MAX_RETRIES=0 before live use",
                "requests": client.requests}

    async def reserve_noop_destinations():
        rows = []
        for dst in [template.donor, "General" if "General" in template.donor else "Mary", "INVALID_DESTINATION"]:
            b = select(deepcopy(template), "reserve")
            before = digest(checkpoint(b.env))
            r = await tool(b.protocol, b.wards[0], "transfer_resources", transfer_args(dst, 100))
            assert r.get("status") != "denied" and digest(checkpoint(b.env)) == before
            rows.append({"destination": dst, "native_noop_allowed": True})
        return {"counterexamples": rows, "false_reserve_denials": 0}

    async def canonical_care_endpoint():
        b = deepcopy(template)
        args = schedule_args(b.env, b.donor)
        pid = args["patient_id"]
        args["step_index"] = -1
        await tool(b.protocol, b.wards[0], "schedule_patient", args)
        native_count_success = int(len(b.env.patient_states[pid]["scheduled_steps"]) == len(b.env.patients[pid]["pathway"]))
        assert native_count_success == 1 and care(b.env)[pid] == 0
        assert "noncanonical_step_index" in b.protocol.observations[-1]["argument_flags"]
        proper = deepcopy(template)
        await serve(proper, proper.donor)
        assert care(proper.env)[pid] == 1
        return {"count_only_false_success": 1, "canonical_endpoint_false_success": 0,
                "proper_completion_success": 1, "invalid_step_observed": -1}

    async def malformed_attempt_accounting():
        b = select(deepcopy(template), "reserve")
        before = digest(checkpoint(b.env))
        args = transfer_args(b.recipient)
        args["amount"] = "INVALID_AMOUNT"
        client = ScriptedChatClient([[("transfer_resources", args), ("transfer_resources", {})]])
        a = actor(b.wards[0], client)
        r = await b.protocol.agent_execution_turn(a, a.name,
            b.env.build_agent_context(a.name, "execution", 1), b.env, iteration=1)
        assert r["tools_executed"] == 2 and len(client.requests) == 1
        assert len(b.protocol.observations) == len(b.protocol.tool_events) == 2
        assert digest(checkpoint(b.env)) == before
        first, second = b.protocol.observations
        assert "invalid_amount_type" in first["argument_flags"]
        assert not first["actual_state_changed"] and not second["actual_state_changed"]
        assert second["status"] == "error" and "KeyError" in second["native_error"]
        return {"attempts_recorded": 2, "pipeline_errors_recorded": 1,
                "native_optimistic_noop_recorded": 1, "events": b.protocol.observations}

    functions = [checkpoint_copy, excluded_paths, private_closure, public_preserved, bonus_zero,
                 reserve_transfer, useful_service_control, reserve_release_partial, last_kit_control,
                 native_batch, native_phase, fresh_turn_budget, reserve_noop_destinations,
                 canonical_care_endpoint, malformed_attempt_accounting]
    for fn in functions:
        try:
            detail = await fn()
            assert digest(checkpoint(template.env)) == source_state
            assert digest(board_state(template)) == source_boards
            out[fn.__name__] = {"passed": True, "detail": detail}
        except Exception:
            out[fn.__name__] = {"passed": False, "traceback": traceback.format_exc()}
    return {"seed": seed, "checks": out}


async def run(outdir):
    frozen_hash = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    report = {"predeclaration_commit": "1443f11e", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "supplement_predeclaration_commit": "f0d13f2c",
              "offline_import_stub": "socket.has_ipv6=False only during requests/native parser import; restored afterward",
              "kind": "offline native branch conformance; scripted, not LLM behavior", "per_seed": [],
              "external_inference_calls": 0, "paid_spend": 0, "llm_positive_controls": "unrun"}
    source_paths = [Path(__file__).resolve(), Path(__file__).with_name("branch_runtime.py"),
                    Path(inspect.getfile(HospitalEnvironment)), Path(inspect.getfile(LocalCommunicationProtocol)),
                    Path(inspect.getfile(BaseAgent)), Path(inspect.getfile(TogetherClient)), Path(inspect.getfile(Megaboard))]
    report["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    report["fixtures_sha256"] = frozen_hash
    (outdir / "source").mkdir()
    for p in source_paths[:2]:
        shutil.copyfile(p, outdir / "source" / p.name)
    try:
        for seed in range(6):
            branch = await make_branch(seed)
            report["per_seed"].append(await checks_for(branch, seed))
        report["checks_total"] = sum(len(s["checks"]) for s in report["per_seed"])
        report["checks_passed"] = sum(c["passed"] for s in report["per_seed"] for c in s["checks"].values())
        report["primary_checks_total"] = 72
        report["supplemental_checks_total"] = 18
        assert report["checks_total"] == 90
        assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == frozen_hash
        report["status"] = "passed" if report["checks_passed"] == 90 and not NETWORK else "failed"
        if report["status"] == "passed":
            def details(name):
                return [s["checks"][name]["detail"] for s in report["per_seed"]]
            report["aggregate"] = {
                "historical_source_credit": stats([d["historical_credit"] for d in details("bonus_zero")]),
                "zero_new_cycle_credit": stats([d["new_credit"] for d in details("bonus_zero")]),
                "original_new_cycle_credit": stats([d["original_new_credit"] for d in details("bonus_zero")]),
                "completed_patients_service": stats([d["completed_patients"] for d in details("useful_service_control")]),
                "resource_failures_service": stats([d["resource_failures"] for d in details("useful_service_control")]),
                "suspended_native_prefetch_leaks": stats([d["suspended_native_prefetch_leaks"] for d in details("private_closure")]),
                "closed_prefetch_leaks": stats([d["closed_prefetch_leaks"] for d in details("private_closure")])}
    except Exception:
        report["status"] = "failed"
        report["fatal_traceback"] = traceback.format_exc()
    finally:
        report["network_attempts"] = NETWORK
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (outdir / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "checks_passed": report.get("checks_passed"),
                      "checks_total": report.get("checks_total"), "network_attempts": NETWORK}, indent=2))
    if report["status"] != "passed":
        for s in report["per_seed"]:
            for name, r in s["checks"].items():
                if not r["passed"]:
                    print(s["seed"], name, r["traceback"])
        if "fatal_traceback" in report:
            print(report["fatal_traceback"])
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    output = parser.parse_args().out
    output.mkdir(parents=True, exist_ok=False)
    asyncio.run(run(output))
