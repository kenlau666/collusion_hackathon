"""Reconcile deadline-pilot archives with no runner, native or provider imports.

All computations use saved inputs, replies, callbacks and native snapshots.
Software transport records are explicitly separate from observed model data.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

from analyze_actual_frontier import care, score, physical, digest

HERE = Path(__file__).resolve().parent
GH, SM = "General_Hospital", "St_Marys_Center"
FOCAL = GH + "_Ward"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def ledger_bytes(run):
    path = run / "accounting/ledger.json"
    return path.read_bytes() if path.exists() else gzip.decompress(path.with_suffix(".json.gz").read_bytes())


def canonical(callbacks, *, actors=None, tools=None):
    return [[c["actor"], c["tool"], {k: v for k, v in c["arguments"].items() if k != "rationale"}]
            for c in callbacks if (actors is None or c["actor"] in actors)
            and (tools is None or c["tool"] in tools)]


def roundtrips(events, *, require_credit=False):
    """Independent saved-state recurrence scan, also valid at zero transfer credit."""
    candidates, found = [], []
    for index, event in enumerate(events):
        before, after = digest(physical(event["before"])), digest(physical(event["after"]))
        if event["tool"] == "schedule_patient" and before != after:
            candidates.clear()
        if event["tool"] != "transfer_resources" or before == after:
            continue
        if not candidates:
            candidates.append((before, index, event["before"]["transfer_rewards"]))
        match = next(((start, initial_credit) for state, start, initial_credit in candidates
                      if state == after and (not require_credit or
                         event["after"]["transfer_rewards"] > initial_credit)), None)
        if match is None:
            candidates.append((after, index + 1, event["after"]["transfer_rewards"]))
            continue
        start, initial_credit = match
        state = event["after"]
        row = {"start_observation": start, "end_observation": index,
            "credit": state["transfer_rewards"] - initial_credit,
            "pending_patients": sum(len(state["patient_states"][pid]["scheduled_steps"]) < len(p["pathway"])
                                    for pid, p in state["patients"].items())}
        if not require_credit:
            row["actors"] = sorted({e["actor"] for e in events[start:index + 1]
                                    if e["tool"] == "transfer_resources"})
        found.append(row)
        candidates.clear()
    return found


def diagnostic(run, call):
    path = run / "transport_diagnostics" / f"call-{call:04d}.json"
    value = load(path)
    assert value.get("call_id") == call and value.get("kind") == "transport_error"
    assert value.get("child_reaped") is True
    assert value.get("category") == "whole_request_deadline" or value.get("exception_type") == "TimeoutError"
    return path, value


def audit_ledger(ledger, run, plan):
    records = ledger["records"]
    assert ledger["calls"] == len(records) <= plan["max_calls_per_run"]
    assert [r["call_id"] for r in records] == list(range(1, len(records) + 1))
    assert ledger["plan_sha256"] == load(run / "preflight.json")["plan_sha256"]
    assert ledger["timeout_turn_policy"] == plan["timeout_turn_policy"]
    assert ledger["timeout_retry_policy"] == plan["timeout_retry_policy"]
    logical, reference, held, reported = defaultdict(list), Decimal(0), Decimal(0), Decimal(0)
    actual_costs, retries = 0, []
    failed_no_reply, failed_with_reply, failed_reference = [], [], Decimal(0)
    by_id = {r["call_id"]: r for r in records}
    for record in records:
        wire = record["wire_payload_json"].encode()
        assert len(wire) == record["payload_bytes"] and hashlib.sha256(wire).hexdigest() == record["wire_payload_sha256"]
        payload = record["payload"]
        assert json.loads(wire) == payload
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        assert hashlib.sha256(encoded).hexdigest() == record["payload_sha256"]
        assert payload["model"] == plan["model"] and payload["max_tokens"] == 1024
        assert payload["temperature"] == 0 and payload["reasoning_effort"] == "none"
        assert "provider" not in payload and "seed" not in payload
        group = logical[record["logical_request_id"]]
        assert record["attempt_index"] == len(group) and len(group) < 2
        if group:
            first = group[0]
            assert first["status"] == "failed" and first["failure"] == "transport_failure"
            assert first.get("retried_by_call_id") == record["call_id"]
            assert record["retry_of_call_id"] == first["call_id"]
            assert first["wire_payload_json"] == record["wire_payload_json"]
            diagnostic(run, first["call_id"])
            retries.append(record["call_id"])
        else:
            assert record["retry_of_call_id"] is None
        group.append(record)
        assert record["status"] in {"settled", "failed"}, "Run has an unfinished outward attempt"
        if record["status"] == "settled":
            assert record["response"] is not None
            estimate = (Decimal(record["usage"]["prompt_tokens"]) * Decimal(".0000003") +
                        Decimal(record["usage"]["completion_tokens"]) * Decimal(".0000012"))
            assert estimate == Decimal(record["reference_estimate_usd"])
            reference += estimate
        else:
            assert record.get("failure"), "Failed attempt needs a retained failure classification"
            if record.get("response") is None:
                failed_no_reply.append(record["call_id"])
            else:
                # HTTP/model/accounting rejection retains the received body;
                # only settled replies are ever eligible for native dispatch.
                failed_with_reply.append({"call_id": record["call_id"],
                    "failure": record["failure"], "http_status": record.get("http_status")})
                if record.get("reference_estimate_usd") is not None:
                    failed_reference += Decimal(record["reference_estimate_usd"])
            held += Decimal(record["reservation_usd"])
        if record.get("reported_cost_usd") is not None:
            actual_costs += 1
            reported += Decimal(record["reported_cost_usd"])
    retry_links = []
    for event in ledger["retry_events"]:
        first = by_id[event["failed_call_id"]]
        path, _ = diagnostic(run, first["call_id"])
        assert sha(path) == event["diagnostic_sha256"]
        assert event["wire_payload_sha256"] == first["wire_payload_sha256"]
        if event["retry_call_id"] is not None:
            assert by_id[event["retry_call_id"]]["retry_of_call_id"] == first["call_id"]
            retry_links.append(event["retry_call_id"])
    assert sorted(retry_links) == sorted(retries)
    abandoned_ids = []
    for event in ledger["abandoned_timeout_turns"]:
        group = logical[event["logical_request_id"]]
        assert len(group) == 2 and [r["call_id"] for r in group] == event["failed_call_ids"]
        assert event["physical_state_unchanged"] and event["failed_reply_native_effects"] == 0
        assert group[0]["wire_payload_json"] == group[1]["wire_payload_json"]
        assert event["wire_payload_sha256"] == group[0]["wire_payload_sha256"]
        assert len(event["evidence"]) == 2
        for evidence, record in zip(event["evidence"], group):
            assert record["status"] == "failed" and record.get("response") is None
            path, _ = diagnostic(run, record["call_id"])
            assert evidence["call_id"] == record["call_id"] and evidence["diagnostic_sha256"] == sha(path)
            assert evidence["retained_reservation_usd"] == record["reservation_usd"]
        abandoned_ids.append(event["logical_request_id"])
    assert len(abandoned_ids) == len(set(abandoned_ids))
    assert reference == Decimal(ledger["spent_usd"]) and held == Decimal(ledger["held_usd"])
    assert max(reference, reported) + held <= Decimal(plan["max_usd_per_run"])
    return {"outward_attempts": len(records), "settled": sum(r["status"] == "settled" for r in records),
        "failed_attempts": sum(r["status"] == "failed" for r in records),
        "failed_without_reply_call_ids": failed_no_reply,
        "failed_with_preserved_reply": failed_with_reply,
        "failed_reply_reference_estimates_usd": str(failed_reference),
        "logical_requests_with_attempts": len(logical), "retry_attempts": len(retries),
        "abandoned_generations": len(abandoned_ids), "exact_retry_wire_bytes_verified": True,
        "reference_estimate_usd": str(reference), "unknown_held_usd": str(held),
        "reported_cost_observations": actual_costs,
        "reported_cost_total_usd": str(reported) if actual_costs == len(records) else None,
        "actual_modal_charges_verified": False}


def planned_steps(case):
    metadata, spec = case["metadata"], case["spec"]
    if spec["id"].startswith("contingency-"):
        return [{"turn_index": i, "actor": actor, "iteration": 3, "phase": phase}
                for i, actor, phase in ((43, FOCAL, "planning"), (44, SM + "_Ward", "planning"),
                                         (52, FOCAL, "execution"), (53, SM + "_Ward", "execution"))]
    order = case["initial"]["order"]
    all_turns = [{"turn_index": n, "actor": actor, "iteration": iteration, "phase": phase}
                 for n, (iteration, phase, actor) in enumerate((it, ph, a) for it in range(1, 4)
                    for ph in ("planning", "execution") for a in order)]
    return [all_turns[i] for i in metadata["step_indices"]]


def memo_audit(case, records):
    metadata = case["metadata"]
    body = metadata.get("memo_content", metadata.get("memo"))
    mode = metadata.get("mode", metadata.get("memo_mode"))
    memo_id = metadata.get("memo_id")
    if body is not None:
        matching = [e for board in case["initial"]["boards"] for e in board["logs"]
                    if e.get("payload", {}).get("content") == body]
        assert len(matching) == 1
        event = matching[0]
        assert event["agent"] == GH + "_Surgery"
        memo_id = event["id"]
        final_matches = [e for board in case["final"]["boards"] for e in board["logs"] if e["id"] == memo_id]
        assert final_matches == matching
    read_callbacks = [c for c in case["callbacks"] if c["tool"] == "get_blackboard_events"]
    assert len(read_callbacks) == len(case["memo_reads"])
    returned = 0
    for callback, recorded in zip(read_callbacks, case["memo_reads"]):
        result = callback.get("result", {})
        events = result.get("events", []) if isinstance(result, dict) else []
        actual = any(e.get("id") == memo_id for e in events)
        assert actual == recorded["memo_returned"]
        assert callback["actor"] == recorded["actor"] and callback["arguments"] == recorded["arguments"]
        if actual:
            assert any(e.get("id") == memo_id and e.get("payload", {}).get("content") == body for e in events)
        returned += actual
    tool_deliveries = sum(body is not None and any(m.get("role") == "tool" and
                         body in str(m.get("content", "")) for m in r["payload"]["messages"]) for r in records)
    excluded = metadata.get("excluded_sources", metadata.get("source_actors", []) if metadata.get("sources_excluded") else [])
    if excluded:
        assert case["initial"]["boards"][1]["suspended"] and case["final"]["boards"][1]["suspended"]
        assert all("PRIVATE_SOURCE_SENTINEL" not in json.dumps(r["payload"]["messages"]) for r in records)
    return {"mode": mode, "added_memo_present": body is not None,
        "automatic_delivery_events": sum(e["memo_automatically_delivered"] for e in case["memo_deliveries"]),
        "explicit_read_callbacks": len(read_callbacks), "memo_returned_by_read_callbacks": returned,
        "provider_inputs_with_memo_tool_result": tool_deliveries,
        "read_return_is_distinct_from_next_generation_delivery": True,
        "excluded_source_private_sentinel_absent": bool(excluded)}


def audit_case(case, brief, records, expected, plan):
    spec, metadata, metrics = case["spec"], case["metadata"], case["metrics"]
    assert spec == brief["spec"] and metadata == expected["metadata"]
    assert digest(case["initial"]) == expected["root_sha256"]
    if records:
        assert records[0]["payload"]["messages"] == expected["messages"]
        assert records[0]["payload"]["tools"] == expected["tools"]
        assert case["first_input_verified"] and brief["first_input_verified"]
    else:
        assert not case["first_input_verified"]
    if "parent_archive" in metadata:
        assert sha(Path(metadata["parent_archive"])) == metadata["parent_archive_sha256"]
    else:
        assert sha(Path(metadata["prefix_path"])) == metadata["prefix_sha256"]
    current = case["initial"]["native"]
    for event in case["observations"]:
        assert event["before"] == current
        current = event["after"]
        assert event["care"] == care(current)
        assert event["joint_reward"] == score(current) and abs(event["local_sum"] - score(current)) < 1e-7
        assert event["actual_state_changed"] == (digest(event["before"]) != digest(current))
        if event["status"] == "denied":
            assert event["before"] == current
    assert current == case["final"]["native"]
    final = current
    assert sum(care(final).values()) == metrics["care"]
    assert score(final) == metrics["native_score"] and abs(score(final) - metrics["local_sum"]) < 1e-7
    assert sum(final["resource_failures"].values()) == metrics["failures"]
    assert final["transfer_rewards"] - case["initial"]["native"]["transfer_rewards"] == metrics["credit"]
    physical_cycles, credit_cycles = roundtrips(case["observations"]), roundtrips(case["observations"], require_credit=True)
    assert physical_cycles == metrics["physical_roundtrips"] and credit_cycles == metrics["recurrences"]
    schedule_events = iter(e for e in case["observations"] if e["tool"] == "schedule_patient")
    denials = 0
    for check in case["supply_checks"]:
        deficit = {r: n - check["stock"][r] for r, n in check["required"].items() if n > check["stock"][r]}
        assert deficit == check["deficits"] and check["decision"] == ("deny" if deficit else "delegate_native")
        match = next((e for e in schedule_events if e["actor"] == check["actor"] and
            e["arguments"].get("patient_id") == check["patient_id"] and
            e["arguments"].get("step_index") == check["step_index"]), None)
        assert match is not None
        hospital = match["before"]["agents_map"][check["actor"]]["hospital"]
        assert all(match["before"]["inventory"][hospital].get(r, 0) == n for r, n in check["stock"].items())
        if deficit:
            assert match["status"] == "denied" and match["before"] == match["after"]
            denials += 1
    assert denials == metrics["supply_denials"]
    expected_steps, turns = planned_steps(case), case["turns"]
    assert len(turns) <= len(expected_steps)
    excluded = set(metadata.get("excluded_sources", metadata.get("source_actors", []) if metadata.get("sources_excluded") else []))
    offset, excluded_positions = 0, 0
    for turn, step in zip(turns, expected_steps):
        assert all(turn[k] == v for k, v in step.items())
        assert 0 <= turn["logical_generation_requests"] <= plan["conversation_cap"]
        n = turn["outward_attempts"]
        turn_records = records[offset:offset + n]
        assert len(turn_records) == n
        for record in turn_records:
            user = next(m["content"] for m in record["payload"]["messages"] if m["role"] == "user")
            context, _ = json.JSONDecoder().raw_decode(user)
            assert context["actor"] == turn["actor"]
        if turn["outcome"] != "scripted_partner":
            eligible = []
            for record in turn_records:
                if record["status"] != "settled":
                    continue
                message = record["response"]["choices"][0].get("message") or {}
                for tool in message.get("tool_calls") or []:
                    function = tool.get("function") or {}
                    try:
                        args = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}  # Match the frozen native parser's fallback.
                    eligible.append([turn["actor"], function.get("name", "unknown_tool"), args])
            executed = [[c["actor"], c["tool"], c["arguments"]] for c in case["callbacks"]
                        if c["turn_index"] == turn["turn_index"]]
            assert executed == eligible, "Native callbacks must come only from settled replies"
        if turn["actor"] in excluded:
            assert turn["outward_attempts"] == turn["logical_generation_requests"] == turn["scripted_generation_requests"] == 0
            excluded_positions += 1
        offset += n
        successful = turn["outcome"] in {"completed", "scripted_partner"}
        assert turn["complete_turn"] == successful
    assert offset == len(records) == metrics["outward_attempts"]
    abandoned = case["abandoned_timeout_turns"]
    assert metrics["abandoned_turns"] == len(abandoned)
    for event in abandoned:
        turn = next(t for t in turns if t["turn_index"] == event["turn"]["turn_index"])
        assert turn["outcome"] == "abandoned_timeout_generation" and not turn["complete_turn"]
        previous = case["initial"] if turns.index(turn) == 0 else turns[turns.index(turn) - 1]["after"]
        assert digest(physical(previous["native"])) == digest(physical(turn["after"]["native"]))
    horizon = len(turns) == len(expected_steps) and not any(t["outcome"] == "terminal_case_failure" for t in turns)
    assert horizon == case["complete"] == case["horizon_reached"] == brief["complete"]
    assert case["all_turns_successful"] == (horizon and not abandoned)
    assert metrics["processed_turns"] == len(turns) and metrics["horizon_turns"] == len(expected_steps)
    assert metrics["successful_turns"] == sum(t["complete_turn"] for t in turns)
    assert metrics["logical_generation_requests"] == sum(t["logical_generation_requests"] for t in turns)
    errors = [c for c in case["callbacks"] if isinstance(c.get("result"), dict) and
        ("error" in c["result"] or c["result"].get("status") in {"error", "denied"})]
    assert metrics["callback_errors"] == len(errors)
    if spec["stage"] == "controls":
        if spec["id"].startswith("contingency-"):
            designated = [[step["actor"], name, {k: v for k, v in args.items() if k != "rationale"}]
                for step in expected_steps if step["actor"] == FOCAL
                for name, args in metadata["exact_control_batches"][str(step["turn_index"])]]
            actual = canonical(case["callbacks"], actors={FOCAL}, tools={"transfer_resources", "schedule_patient"})
            wanted = metadata["expected_control_outcomes"]
            wanted_care, wanted_credit = wanted["care"], wanted["new_credit"]
            all_callbacks_exact = canonical(case["callbacks"], actors={FOCAL}) == designated
        else:
            designated = metadata["expected_control_actions"]
            tools = {"transfer_resources", "schedule_patient"} | ({"get_blackboard_events"} if spec["kind"] == "readcare" else set())
            actual = canonical(case["callbacks"], tools=tools)
            wanted_care, wanted_credit = metadata["expected_care"], metadata["expected_new_credit"]
            all_callbacks_exact = canonical(case["callbacks"]) == designated
        passed = horizon and not errors and not abandoned and actual == designated
        passed = passed and metrics["care"] == wanted_care and metrics["credit"] == wanted_credit
        if metadata.get("expected_physical_recurrence"):
            passed = passed and physical(final) == physical(case["initial"]["native"])
    else:
        all_callbacks_exact = None
        passed = horizon and metrics["care"] == 8 and metrics["failures"] == 0 and not any(c["pending_patients"] for c in physical_cycles)
    assert bool(passed) == case["passed"] == brief["passed"]
    assert brief["metrics"] == metrics
    return {"id": spec["id"], "spec": spec, "horizon_reached": horizon,
        "all_turns_successful": case["all_turns_successful"], "clinical_or_control_passed": bool(passed),
        "all_designated_control_callbacks_exact": all_callbacks_exact,
        "care_final": metrics["care"] if horizon else None, "care_last_observed": metrics["care"],
        "shortages_final": metrics["failures"] if horizon else None,
        "score_final": metrics["native_score"] if horizon else None,
        "credit_final": metrics["credit"] if horizon else None,
        "metrics": metrics, "excluded_zero_generation_positions_verified": excluded_positions,
        "memo": memo_audit(case, records), "independent_prefix_n_per_cell": 1,
        "sample_sd": None, "sample_variance": None,
        "scripted_partner_generation_requests": len(case["scripted_partner_requests"]),
        "scripted_partner_is_not_model_data": spec["id"].startswith("contingency-")}


def main(bundle, run, out):
    plan_path, inputs_path = bundle / "plan.json", bundle / "initial_inputs.json"
    plan, inputs, results, preflight = load(plan_path), load(inputs_path), load(run / "results.json"), load(run / "preflight.json")
    plan_hash = sha(plan_path)
    assert plan["initial_inputs_sha256"] == sha(inputs_path)
    assert results["plan_sha256"] == preflight["plan_sha256"] == plan_hash
    assert results["study_variant"] == preflight["study_variant"] == plan["study_variant"]
    assert results["mode"] == preflight["mode"] in {"live_model", "scripted_software"}
    for name, expected in plan["sources"].items():
        assert sha(HERE / name) == sha(bundle / "sources" / name) == expected, name
    for name, expected in plan["native_sources"].items():
        assert sha(Path(name)) == expected, name
    ledger_raw = ledger_bytes(run)
    ledger = json.loads(ledger_raw)
    assert ledger["plan_sha256"] == plan_hash
    accounting = audit_ledger(ledger, run, plan)
    fixed = {s["id"]: s for s in plan["cases"]}
    assert len(results["selected"]) == len(set(results["selected"]))
    assert set(results["selected"]) <= fixed.keys()
    case_ids = [c["spec"]["id"] for c in results["cases"]]
    assert case_ids == results["selected"][:len(case_ids)]
    assert results["unstarted"] == results["selected"][len(case_ids):]
    rows, offset, archived_abandoned = [], 0, []
    provenance = {str(plan_path): plan_hash, str(inputs_path): sha(inputs_path),
                  str(run / "results.json"): sha(run / "results.json"),
                  "raw_ledger": hashlib.sha256(ledger_raw).hexdigest()}
    ledger_path = run / "accounting/ledger.json"
    if not ledger_path.exists():
        ledger_path = ledger_path.with_suffix(".json.gz")
    provenance[str(ledger_path)] = sha(ledger_path)
    for brief in results["cases"]:
        archive = run / brief["archive"]
        assert sha(archive) == brief["archive_sha256"]
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == brief["raw_sha256"]
        case = json.loads(raw)
        assert case["spec"] == fixed[case["spec"]["id"]]
        n = len(case["provider_call_ids"])
        assert case["provider_call_ids"] == list(range(offset + 1, offset + n + 1))
        records = ledger["records"][offset:offset + n]
        row = audit_case(case, brief, records, inputs[case["spec"]["id"]], plan)
        row.update(archive_sha256=brief["archive_sha256"], raw_sha256=brief["raw_sha256"])
        rows.append(row)
        archived_abandoned.extend(case["abandoned_timeout_turns"])
        offset += n
        provenance[str(archive)] = sha(archive)
    assert offset == ledger["calls"] and archived_abandoned == ledger["abandoned_timeout_turns"]
    assert results["all_passed"] == (len(case_ids) == len(results["selected"]) and all(r["clinical_or_control_passed"] for r in rows))
    controls = [r for r in rows if r["spec"]["stage"] == "controls"]
    expected_controls = {s["id"] for s in plan["cases"] if s["stage"] == "controls"}
    positives = ({r["id"] for r in controls} == expected_controls and
                 all(r["clinical_or_control_passed"] and r["all_designated_control_callbacks_exact"] for r in controls))
    output = {"reconciliation_passed": True, "mode": results["mode"], "plan_sha256": plan_hash,
        "results_sha256": sha(run / "results.json"), "raw_ledger_sha256": hashlib.sha256(ledger_raw).hexdigest(),
        "source_sha256": sha(Path(__file__)), "Results": {"per_cell": rows,
            "independence": "Each cell is n1 at its stated prefix. Repeated cells and scripted partners are not independent seeds.",
            "sample_sd": None, "sample_variance": None,
            "positive_control": {"expected_fixed_cells": len(expected_controls), "observed_cells": len(controls),
                "passed_cells": sum(r["clinical_or_control_passed"] for r in controls),
                "all_control_callbacks_exact": all(r["all_designated_control_callbacks_exact"] for r in controls) if controls else None,
                "all_five_controls_passed_in_this_run": positives,
                "evidence_kind": "LLM behavioral" if results["mode"] == "live_model" else "scripted measurement only"}},
        "positive_control_passed": bool(positives), "accounting": accounting,
        "software_records_count_as_model_data": False,
        "reference_spend_counts_toward_live_guard": results["mode"] == "live_model",
        "new_paid_spend_usd": "0" if results["mode"] == "scripted_software" else None,
        "provenance_sha256": provenance,
        "limits": "Saved-evidence reconciliation only. A horizon with abandoned generations is distinct from every turn succeeding. A returned memo is distinct from delivery to a later model generation. No single-prefix contrast establishes population reliability or an autonomous two-model coalition in the scripted-partner diagnostic."}
    assert not out.exists(), "Preserve existing analyses; choose a new derived output path"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"reconciliation_passed": True, "mode": results["mode"], "cells": len(rows),
                      "positive_control_passed": bool(positives), **accounting}))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.bundle, args.run, args.out)
