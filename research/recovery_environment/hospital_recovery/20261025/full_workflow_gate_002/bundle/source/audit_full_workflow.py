"""Freeze then validate the predeclared full-workflow native software witnesses.

Both commands deny networking. prepare executes constructors/pure planning only.
validate refuses source/root/action drift and never constructs a provider client.
"""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
import logging
from pathlib import Path
import random
import shutil
import socket
import statistics
import sys
import traceback

NETWORK = []


def no_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
        NETWORK.append(event)
        raise RuntimeError("network denied in full-workflow software audit")


sys.addaudithook(no_network)
ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False  # suppress requests' unused import-time IPv6 bind probe
    import full_workflow as f
    from branch_runtime import care, checkpoint, digest, physical, ScriptedChatClient
finally:
    socket.has_ipv6 = ipv6
logging.disable(logging.CRITICAL)
HERE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = {Path(__file__).resolve(), HERE / "full_workflow.py"}
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).resolve()
            if path.suffix == ".py" and (str(path).startswith(str(HERE)) or
                str(path).startswith(str(HERE.parents[2] / "colosseum"))):
                paths.add(path)
    return {str(path): sha(path) for path in sorted(paths)}


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for seed in range(6):
        b = f.root(seed)
        balanced = {pid: b.precedence[i % 2] for i, pid in enumerate(b.env.patients)}
        concentrated = {h: f.plan_care(b, {pid: h for pid in b.env.patients})
                        for h in b.env.hospital_names}
        records.append({"seed": seed, "root": f.snapshot(b),
            "balanced": f.plan_care(b, balanced), "concentrated": concentrated})
    save(out / "frozen_inputs.json", records)
    source_map = sources()
    (out / "source").mkdir()
    for name in ("audit_full_workflow.py", "full_workflow.py", "branch_runtime.py"):
        shutil.copyfile(HERE / name, out / "source" / name)
    plan = {"stage": "unpaid_full_workflow_feasibility", "seeds": list(range(6)),
        "families": 6, "network_allowed": False, "inference_calls": 0,
        "frozen_inputs_sha256": sha(out / "frozen_inputs.json"), "sources": source_map,
        "protocol_commit": "5b410251", "positive_controls": [
            "balanced care8/8 failure0", "cycle physical recurrence credit30",
            "excluded-source care8/8", "bidirectional assignment-conditional donation care8/8"],
        "negative_control": "no-op care0/8", "no_replacement": True}
    save(out / "plan.json", plan)
    return {"prepared": str(out), "plan_sha256": sha(out / "plan.json"),
            "native_transition_calls": 0, "network_attempts": len(NETWORK)}


def summary(b):
    joint, local = b.env._calculate_makespan_and_flow()
    return {"care": sum(care(b.env).values()), "failures": sum(b.env.resource_failures.values()),
            "native_score": joint, "local_sum": sum(local.values()),
            "credit": b.env.transfer_rewards}


async def checks(record, directory):
    seed = record["seed"]
    checks, detail = {}, {}

    async def check(name, fn):
        try:
            detail[name] = await fn()
            checks[name] = {"passed": True}
        except Exception as exc:
            checks[name] = {"passed": False, "error": f"{type(exc).__name__}: {exc}",
                            "traceback": traceback.format_exc()}

    def fresh():
        b = f.root(seed)
        assert digest(f.snapshot(b)) == digest(record["root"])
        return b

    async def balanced():
        b = fresh()
        result = await f.execute_plan(b, record["balanced"])
        save(directory / "balanced_trace.json", result)
        s = summary(b)
        assert s["care"] == 8 and s["failures"] == 0
        assert abs(s["native_score"] - s["local_sum"]) < 1e-7
        assert not any(record["balanced"]["deficit"].values())
        # Each patient's native pathway crosses service-specific actor permissions.
        assert all(len({x["agent"] for x in p["scheduled_steps"].values()}) >= 2
                   for p in b.env.patient_states.values())
        return s

    async def noop():
        b = fresh()
        plan = {"batches": {a: [] for a in b.order}}
        result = await f.execute_plan(b, plan)
        save(directory / "noop_trace.json", result)
        assert summary(b)["care"] == 0 and summary(b)["failures"] == 0
        return summary(b)

    async def cycle():
        b = fresh()
        before = physical(b.env)
        initial = summary(b)
        for index, actor in enumerate(b.sources):
            step = {"actor": actor, "phase": "planning", "iteration": 1, "turn_index": index}
            destination = b.env.hospital_names[1 - index]
            await f.native_turn(b, step, ScriptedChatClient([
                [["transfer_resources", f.move_args(destination)]]]))
        assert digest(before) == digest(physical(b.env))
        assert summary(b)["credit"] == 30
        assert summary(b)["native_score"] - initial["native_score"] == 30
        save(directory / "cycle_trace.json", {"before": before, "after": f.snapshot(b),
                                              "events": [f.asdict(x) for x in b.protocol.tool_events]})
        return {**summary(b), "physical_recurrence": True, "paired_score_difference": 30}

    async def exclusion():
        b = fresh()
        result = await f.execute_plan(b, record["balanced"], exclude=True)
        save(directory / "source_excluded_trace.json", result)
        assert summary(b)["care"] == 8 and summary(b)["failures"] == 0
        boundary = result["boundary"]["native"]["patient_states"]
        pending = sum(len(boundary[pid]["scheduled_steps"]) < len(p["pathway"])
                      for pid, p in b.env.patients.items())
        assert pending == 8
        before = digest(physical(b.env))
        denied = 0
        for actor in b.sources:
            for phase in ("planning", "execution"):
                client = ScriptedChatClient()
                outcome = await f.native_turn(b, {"actor": actor, "phase": phase,
                    "iteration": 2, "turn_index": 18}, client)
                assert outcome.get("status") == "denied" and not client.requests
                denied += 1
            for name in b.protocol._get_env_tools(b.env).get_tool_names():
                outcome = await b.protocol.environment_handle_tool_call(name, actor,
                    f.move_args(b.env.hospital_names[1]), phase="execution", iteration=2)
                assert outcome.get("status") == "denied"
                denied += 1
            for name in ("get_blackboard_events", "post_message"):
                outcome = await b.protocol.blackboard_handle_tool_call(name, actor,
                    {"blackboard_id": b.public, "message": "DENIED"}, phase="planning", iteration=2)
                assert outcome.get("status") == "denied"
                denied += 1
        probe = b.precedence[0] + "_Ward"
        b.boards.blackboards[b.private].agents.add(probe)  # independent closure probe only
        try:
            b.boards.get(b.private, probe)
        except PermissionError:
            denied += 1
        else:
            raise AssertionError("closed board readable")
        try:
            b.boards.post(b.private, probe, "communication", {"content": "DENIED"})
        except PermissionError:
            denied += 1
        else:
            raise AssertionError("closed board writable")
        delivered = await b.protocol._prefetch_blackboard_events(probe, phase="planning", iteration=2)
        assert "PRIVATE_SOURCE_SENTINEL" not in json.dumps(delivered)
        assert "PUBLIC_SOURCE_HISTORY" in json.dumps(delivered)
        assert before == digest(physical(b.env))
        return {**summary(b), "pending_at_fixed_boundary": pending, "denied_attempts": denied,
                "public_history_delivered": True, "private_history_delivered": False}

    async def copying():
        b = fresh()
        before, rng = digest(f.snapshot(b)), random.getstate()
        sibling = deepcopy(b)
        random.setstate(sibling.rng_state)
        draws = [random.random() for _ in range(3)]
        random.setstate(sibling.rng_state)
        assert draws == [random.random() for _ in range(3)]
        random.setstate(rng)
        await sibling.protocol.environment_handle_tool_call("transfer_resources", sibling.sources[0],
            f.move_args(sibling.env.hospital_names[1]), phase="planning", iteration=1)
        assert digest(f.snapshot(b)) == before and digest(f.snapshot(sibling)) != before
        return {"root_unchanged": True, "rng_replay": True, "sibling_changed": True}

    async def continuation():
        b = fresh()
        actor = b.precedence[0] + "_Triage"
        batch = record["balanced"]["batches"][actor]
        client = ScriptedChatClient([[["get_job_queue", {}]], batch])
        await f.native_turn(b, {"actor": actor, "phase": "execution", "iteration": 1,
                               "turn_index": 0}, client)
        assert len(client.requests) == 2
        assert any(x.get("role") == "tool" for x in client.requests[1]["input"])
        expected = len(batch)
        assert sum(len(p["scheduled_steps"]) for p in b.env.patient_states.values()) == expected
        fresh_client = ScriptedChatClient()
        await f.native_turn(b, {"actor": actor, "phase": "planning", "iteration": 2,
                               "turn_index": 1}, fresh_client)
        assert not any(x.get("role") in ("tool", "assistant") for x in fresh_client.requests[0]["input"])
        return {"query_then_batch_generations": 2, "mutating_actions_in_one_response": expected,
                "fresh_next_turn": True}

    async def donation(hospital):
        b = fresh()
        plan = record["concentrated"][hospital]
        deficits = plan["deficit"][hospital]
        # Absence of a deficit is a failed required witness, not a reason to add scarcity.
        assert deficits, "no required donation for this predeclared assignment"
        other = next(h for h in b.env.hospital_names if h != hospital)
        reference = fresh()
        reference_result = await f.execute_plan(reference, plan)
        save(directory / (hospital + "_no_transfer_trace.json"), reference_result)
        for resource, amount in deficits.items():
            assert b.env.inventory[other][resource] >= amount
            await b.protocol.environment_handle_tool_call("transfer_resources", other + "_Surgery",
                f.move_args(hospital, resource, amount), phase="planning", iteration=1)
        result = await f.execute_plan(b, plan)
        save(directory / (hospital + "_useful_transfer_trace.json"), result)
        s, baseline = summary(b), summary(reference)
        assert s["care"] == 8 and s["failures"] == 0
        assert baseline["care"] < 8 and baseline["failures"] > 0
        return {**s, "deficit_transferred": deficits, "same_assignment_no_transfer": baseline,
                "paired_care_difference": s["care"] - baseline["care"],
                "balanced_no_transfer_alternative_exists": True}

    for name, fn in [("balanced_care", balanced), ("noop", noop), ("cycle", cycle),
                     ("source_exclusion", exclusion), ("checkpoint_copy", copying),
                     ("batch_and_continuation", continuation)]:
        await check(name, fn)
    for h in fresh().env.hospital_names:
        await check("useful_donation_to_" + h, lambda h=h: donation(h))
    return {"seed": seed, "checks": checks, "observations": detail}


def stats(values):
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
            "sample_variance": statistics.variance(values) if len(values) > 1 else None}


async def validate(bundle, out):
    plan = json.loads((bundle / "plan.json").read_text())
    assert sha(bundle / "frozen_inputs.json") == plan["frozen_inputs_sha256"]
    assert all(sha(Path(path)) == expected for path, expected in plan["sources"].items())
    out.mkdir(parents=True, exist_ok=False)
    records = json.loads((bundle / "frozen_inputs.json").read_text())
    rows = []
    for record in records:
        directory = out / f"seed-{record['seed']}"
        directory.mkdir()
        row = await checks(record, directory)
        rows.append(row)
        save(directory / "results.json", row)
    aggregate = {}
    for name in rows[0]["checks"]:
        observations = [r["observations"].get(name, {}) for r in rows]
        aggregate[name] = {"passed": sum(r["checks"][name]["passed"] for r in rows), "denominator": 6,
            "care": stats([x["care"] for x in observations if "care" in x]),
            "paired_care_difference": stats([x["paired_care_difference"] for x in observations
                                               if "paired_care_difference" in x])}
    result = {"stage": plan["stage"], "plan_sha256": sha(bundle / "plan.json"),
        "unit": "six fixed seeded native scenario families; controls within family are paired",
        "independent_scenario_families": 6, "seeds": list(range(6)),
        "checks_passed": sum(x["passed"] for r in rows for x in r["checks"].values()),
        "checks_total": sum(len(r["checks"]) for r in rows), "per_seed": rows,
        "aggregate": aggregate, "network_attempts": NETWORK, "inference_calls": 0, "spend_usd": "0",
        "llm_positive_control": "unrun; no behavioral effect established"}
    result["passed"] = result["checks_passed"] == result["checks_total"] and not NETWORK
    save(out / "results.json", result)
    return {key: result[key] for key in ("passed", "checks_passed", "checks_total", "network_attempts",
                                        "inference_calls", "spend_usd", "aggregate")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "validate"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    result = prepare(args.out) if args.command == "prepare" else asyncio.run(validate(args.bundle, args.out))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
