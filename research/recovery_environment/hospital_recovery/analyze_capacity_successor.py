"""Independent saved-artifact audit and fixed22 lineage for the USD0.16 successor.

Imports only standard-library evidence helpers, never a runner, native agent,
provider, credential loader or network client. Closed deadline evidence stays
immutable and is used only to verify unchanged inputs and prior accounting.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

import analyze_deadline_pilot as clinical
import summarize_deadline_pilot as lineage

HERE = Path(__file__).resolve().parent
BASE = HERE / "20261025"
BUNDLE = BASE / "capacity_successor_gate_001/bundle"
VARIANT = "capacity_matched_advice_recovery_read_v2"
PRIOR_PLAN_SHA = "e7ceb112050fe27e083771ae3fcad04e8ce85871afe3681bc19c1ee3067bc44a"
PRIOR_LINEAGE_SHA = "a93f60d13f8e4d96de6ae1c835f67fd003b1c807eed937e02a898e16b4a2a687"
PRIOR_GUARD = Decimal("11.50530648")
PRIOR_HOLDS = Decimal(".588")
RESERVATION = Decimal(".16")
PADDED_LIMIT = 529237
FOCAL = clinical.FOCAL
INPUT_RATE, OUTPUT_RATE = Decimal(".00000030"), Decimal(".00000120")
load, sha = clinical.load, clinical.sha


def profile(plan):
    assert plan["study_variant"] == VARIANT
    policy = plan["capacity_guard_policy"]
    assert Decimal(plan["reservation_usd"]) == Decimal(policy["reservation_usd"]) == RESERVATION
    assert policy["max_padded_bytes"] == PADDED_LIMIT
    assert policy["padding_per_message_tool_and_envelope"] == 512
    assert Decimal(policy["input_reference_usd_per_token"]) == INPUT_RATE
    assert Decimal(policy["output_reference_usd_per_token"]) == OUTPUT_RATE
    assert policy["output_tokens"] == plan["max_output_tokens"] == 1024
    assert policy["reported_input_limit"] == 131072
    assert plan["conversation_cap"] == 3 and plan["max_calls_per_run"] == 198
    assert Decimal(plan["max_usd_per_run"]) == 10 and Decimal(plan["cumulative_ceiling_usd"]) == 50
    assert plan["request_deadline_seconds"] == 60
    assert PADDED_LIMIT == int((RESERVATION - 1024 * OUTPUT_RATE) / INPUT_RATE)
    return policy


def scientific_identity(bundle, plan):
    previous = plan["prior_closed_study"]
    old_plan_path, old_lineage_path = Path(previous["plan_path"]), Path(previous["lineage_path"])
    assert sha(old_plan_path) == previous["plan_sha256"] == PRIOR_PLAN_SHA
    assert sha(old_lineage_path) == previous["lineage_sha256"] == PRIOR_LINEAGE_SHA
    assert Decimal(plan["prior_reference_guard_usd"]) == PRIOR_GUARD
    assert plan["scientific_inputs_byte_equal_prior"] is True
    assert (bundle / "initial_inputs.json").read_bytes() == old_plan_path.with_name("initial_inputs.json").read_bytes()
    old_plan = load(old_plan_path)
    assert plan["cases"] == old_plan["cases"]
    assert Counter(s["stage"] for s in plan["cases"]) == {"controls": 5, "main": 11, "diagnostic": 6}
    assert len({s["id"] for s in plan["cases"]}) == 22
    for key in ("model", "route", "conversation_cap", "max_output_tokens", "timeout_retry_policy", "timeout_turn_policy"):
        assert plan[key] == old_plan[key]
    return {str(old_plan_path): sha(old_plan_path), str(old_lineage_path): sha(old_lineage_path)}


def audit_ledger(ledger, run, plan):
    """Verify actual per-attempt reservations, wire bytes, replies and retry links."""
    policy, records = profile(plan), ledger["records"]
    assert ledger["calls"] == len(records) <= 198
    assert ledger["max_calls"] == 198 and Decimal(ledger["max_usd"]) == 10
    assert Decimal(ledger["reservation_usd"]) == RESERVATION
    assert ledger["capacity_guard_policy"] == policy
    assert ledger["timeout_retry_policy"] == plan["timeout_retry_policy"]
    assert ledger["timeout_turn_policy"] == plan["timeout_turn_policy"]
    assert [r["call_id"] for r in records] == list(range(1, len(records) + 1))
    by_id = {r["call_id"]: r for r in records}
    logical, retry_ids = defaultdict(list), []
    spent, held, reported = Decimal(0), Decimal(0), Decimal(0)
    failed_no_reply, failed_with_reply, failed_reference = [], [], Decimal(0)
    reported_n, maximum_padded = 0, 0
    for record in records:
        assert Decimal(record["reservation_usd"]) == RESERVATION
        assert max(spent, reported) + held + RESERVATION <= 10
        held += RESERVATION
        wire, payload = record["wire_payload_json"].encode(), record["payload"]
        assert len(wire) == record["payload_bytes"] and hashlib.sha256(wire).hexdigest() == record["wire_payload_sha256"]
        assert json.loads(wire) == payload
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
        assert hashlib.sha256(canonical).hexdigest() == record["payload_sha256"]
        padded = len(wire) + 512 * (len(payload.get("messages", [])) + len(payload.get("tools", [])) + 1)
        assert padded == record["conservative_prompt_bound"] <= PADDED_LIMIT
        assert Decimal(padded) * INPUT_RATE + 1024 * OUTPUT_RATE <= RESERVATION
        maximum_padded = max(maximum_padded, padded)
        assert payload["model"] == plan["model"] and payload["max_tokens"] == 1024
        assert payload["temperature"] == 0 and payload["reasoning_effort"] == "none"
        assert "provider" not in payload and "seed" not in payload
        group = logical[record["logical_request_id"]]
        assert type(record["attempt_index"]) is int and record["attempt_index"] == len(group) < 2
        if group:
            first = group[0]
            assert first["status"] == "failed" and first["failure"] == "transport_failure"
            assert first["response"] is None and first.get("retried_by_call_id") == record["call_id"]
            assert record["retry_of_call_id"] == first["call_id"]
            assert first["wire_payload_json"] == record["wire_payload_json"]
            clinical.diagnostic(run, first["call_id"])
            retry_ids.append(record["call_id"])
        else:
            assert record["retry_of_call_id"] is None
        group.append(record)
        assert record["status"] in {"settled", "failed"}, "An outward attempt is unfinished"
        known = Decimal(record["known_cost_usd"]) if record.get("known_cost_usd") is not None else None
        estimate = Decimal(record["reference_estimate_usd"]) if record.get("reference_estimate_usd") is not None else None
        if record["status"] == "settled":
            assert record["response"] is not None and 200 <= record["http_status"] < 300
            body, usage = record["response"], record["usage"]
            assert body["model"] == plan["model"] and usage == body["usage"]
            assert type(usage["prompt_tokens"]) is int and 0 <= usage["prompt_tokens"] <= 131072
            assert type(usage["completion_tokens"]) is int and 0 <= usage["completion_tokens"] <= 1024
            derived = Decimal(usage["prompt_tokens"]) * INPUT_RATE + Decimal(usage["completion_tokens"]) * OUTPUT_RATE
            assert known == estimate == derived <= RESERVATION
            held -= RESERVATION
        else:
            assert record.get("failure")
            if record.get("response") is None:
                failed_no_reply.append(record["call_id"])
            else:
                failed_with_reply.append({"call_id": record["call_id"], "failure": record["failure"],
                                          "http_status": record.get("http_status")})
                if estimate is not None:
                    failed_reference += estimate
        if known is not None:
            assert known >= 0 and known == estimate
            spent += known
        if record.get("reported_cost_usd") is not None:
            value = Decimal(record["reported_cost_usd"])
            assert value >= 0
            reported += value
            reported_n += 1
    links = []
    for event in ledger["retry_events"]:
        first = by_id[event["failed_call_id"]]
        path, _ = clinical.diagnostic(run, first["call_id"])
        assert sha(path) == event["diagnostic_sha256"]
        assert event["wire_payload_sha256"] == first["wire_payload_sha256"]
        assert Decimal(event["failed_reservation_retained_usd"]) == RESERVATION
        if event["retry_call_id"] is not None:
            assert by_id[event["retry_call_id"]]["retry_of_call_id"] == first["call_id"]
            links.append(event["retry_call_id"])
    assert sorted(links) == sorted(retry_ids)
    abandoned = []
    for event in ledger["abandoned_timeout_turns"]:
        group = logical[event["logical_request_id"]]
        assert len(group) == 2 and [r["call_id"] for r in group] == event["failed_call_ids"]
        assert event["physical_state_unchanged"] and event["failed_reply_native_effects"] == 0
        assert group[0]["wire_payload_json"] == group[1]["wire_payload_json"]
        assert event["wire_payload_sha256"] == group[0]["wire_payload_sha256"]
        assert len(event["evidence"]) == 2
        for evidence, record in zip(event["evidence"], group):
            assert record["status"] == "failed" and record["response"] is None
            path, _ = clinical.diagnostic(run, record["call_id"])
            assert evidence["call_id"] == record["call_id"] and evidence["diagnostic_sha256"] == sha(path)
            assert Decimal(evidence["retained_reservation_usd"]) == RESERVATION
        abandoned.append(event["logical_request_id"])
    assert len(abandoned) == len(set(abandoned))
    assert spent == Decimal(ledger["spent_usd"]) and held == Decimal(ledger["held_usd"])
    assert reported == Decimal(ledger.get("reported_cost_sum_usd", "0"))
    assert max(spent, reported) + held <= 10
    return {"outward_attempts": len(records), "settled": sum(r["status"] == "settled" for r in records),
        "failed_attempts": sum(r["status"] == "failed" for r in records),
        "failed_without_reply_call_ids": failed_no_reply, "failed_with_preserved_reply": failed_with_reply,
        "failed_reply_reference_estimates_usd": str(failed_reference),
        "logical_requests_with_attempts": len(logical), "retry_attempts": len(retry_ids),
        "abandoned_generations": len(abandoned), "exact_retry_wire_bytes_verified": True,
        "reference_estimate_usd": str(spent), "unknown_held_usd": str(held),
        "reported_cost_observations": reported_n,
        "reported_cost_total_usd": str(reported) if reported_n == len(records) else None,
        "actual_modal_charges_verified": False, "reservation_usd": str(RESERVATION),
        "maximum_observed_padded_bytes": maximum_padded, "capacity_profile_verified": True}


def audit_wave(preflight, run):
    if preflight["mode"] != "live_model":
        return {}
    path = Path(preflight["supervisor_wave"]) / "runtime.json"
    runtime = load(path)
    assert sha(path) == preflight["supervisor_runtime_sha256"]
    assert runtime["plan_sha256"] == preflight["plan_sha256"] and runtime["mock"] is None
    assert set(preflight["selected"]) <= set(runtime["case_ids"])
    slots = len(runtime["case_ids"])
    assert 1 <= slots <= 3 and len(set(runtime["case_ids"])) == slots
    assert Decimal(runtime["reserved_run_envelopes_usd"]) == 10 * slots
    assert Decimal(runtime["baseline_guard_usd"]) + 10 * slots == Decimal(runtime["worst_case_guard_usd"]) <= 50
    snapshot = runtime["prior"]
    old_guard = sum((Decimal(v["spent_or_reference_usd"]) + Decimal(v["held_usd"])
                     for v in snapshot["old"]["ledgers"]), Decimal(0))
    assert old_guard == Decimal(snapshot["old"]["conservative_guard_usd"])
    recorded_guard = old_guard + sum((Decimal(v["guard_usd"]) for v in snapshot["new"] + snapshot["diagnostics"]), Decimal(0))
    assert recorded_guard == Decimal(snapshot["guard_usd"]) == Decimal(runtime["baseline_guard_usd"])
    assert Decimal(preflight["reservation_usd"]) == RESERVATION
    return {str(path): sha(path)}


def main(bundle, run, out):
    bundle, run, out = Path(bundle).resolve(), Path(run).resolve(), Path(out).resolve()
    assert not out.exists(), "Existing analyses are immutable; choose a fresh output path"
    plan_path, inputs_path = bundle / "plan.json", bundle / "initial_inputs.json"
    plan, inputs = load(plan_path), load(inputs_path)
    policy, prior_provenance = profile(plan), scientific_identity(bundle, plan)
    results, preflight, plan_hash = load(run / "results.json"), load(run / "preflight.json"), sha(plan_path)
    authorization = load(bundle / "authorization.json")
    assert authorization["capacity_guard_policy"] == policy
    assert Decimal(authorization["reservation_usd"]) == RESERVATION
    assert plan["initial_inputs_sha256"] == sha(inputs_path)
    assert results["plan_sha256"] == preflight["plan_sha256"] == plan_hash
    assert results["study_variant"] == preflight["study_variant"] == VARIANT
    assert results["mode"] == preflight["mode"] in {"live_model", "scripted_software"}
    for name, expected in plan["sources"].items():
        assert sha(HERE / name) == sha(bundle / "sources" / name) == expected, name
    for name, expected in plan["native_sources"].items():
        assert sha(Path(name)) == expected, name
    raw_ledger = clinical.ledger_bytes(run)
    ledger = json.loads(raw_ledger)
    assert ledger["plan_sha256"] == plan_hash
    accounting = audit_ledger(ledger, run, plan)
    fixed = {s["id"]: s for s in plan["cases"]}
    assert len(results["selected"]) == len(set(results["selected"]))
    assert set(results["selected"]) <= fixed.keys()
    ids = [v["spec"]["id"] for v in results["cases"]]
    assert ids == results["selected"][:len(ids)] and results["unstarted"] == results["selected"][len(ids):]
    ledger_path = run / "accounting/ledger.json"
    if not ledger_path.exists():
        ledger_path = ledger_path.with_suffix(".json.gz")
    provenance = {str(plan_path): plan_hash, str(inputs_path): sha(inputs_path),
        str(run / "results.json"): sha(run / "results.json"), str(ledger_path): sha(ledger_path),
        "raw_ledger": hashlib.sha256(raw_ledger).hexdigest(), **prior_provenance, **audit_wave(preflight, run)}
    for name in ("analyze_deadline_pilot.py", "analyze_actual_frontier.py", "summarize_deadline_pilot.py"):
        provenance[str(HERE / name)] = sha(HERE / name)
    rows, offset, archived_abandoned = [], 0, []
    for brief in results["cases"]:
        archive = run / brief["archive"]
        assert sha(archive) == brief["archive_sha256"]
        raw = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == brief["raw_sha256"]
        case = json.loads(raw)
        assert case["spec"] == fixed[case["spec"]["id"]]
        n = len(case["provider_call_ids"])
        assert case["provider_call_ids"] == list(range(offset + 1, offset + n + 1))
        row = clinical.audit_case(case, brief, ledger["records"][offset:offset + n], inputs[case["spec"]["id"]], plan)
        row.update(archive_sha256=brief["archive_sha256"], raw_sha256=brief["raw_sha256"])
        rows.append(row)
        archived_abandoned.extend(case["abandoned_timeout_turns"])
        offset += n
        provenance[str(archive)] = sha(archive)
    assert offset == ledger["calls"] and archived_abandoned == ledger["abandoned_timeout_turns"]
    assert results["all_passed"] == (len(ids) == len(results["selected"]) and all(v["clinical_or_control_passed"] for v in rows))
    controls = [v for v in rows if v["spec"]["stage"] == "controls"]
    expected_controls = {s["id"] for s in plan["cases"] if s["stage"] == "controls"}
    positives = {v["id"] for v in controls} == expected_controls and all(
        v["clinical_or_control_passed"] and v["all_designated_control_callbacks_exact"] for v in controls)
    output = {"reconciliation_passed": True, "capacity_reconciliation_passed": True,
        "capacity_profile": policy, "mode": results["mode"], "plan_sha256": plan_hash,
        "results_sha256": sha(run / "results.json"), "raw_ledger_sha256": hashlib.sha256(raw_ledger).hexdigest(),
        "source_sha256": sha(Path(__file__)), "Results": {"per_cell": rows,
            "independence": "One actual seed0 prefix and one separate constructed seed2 state; repeated cells are not independent seeds.",
            "sample_sd": None, "sample_variance": None,
            "positive_control": {"expected_fixed_cells": 5, "observed_cells": len(controls),
                "passed_cells": sum(v["clinical_or_control_passed"] and v["all_designated_control_callbacks_exact"] for v in controls),
                "all_control_callbacks_exact": all(v["all_designated_control_callbacks_exact"] for v in controls) if controls else None,
                "all_five_controls_passed_in_this_run": bool(positives),
                "evidence_kind": "LLM behavioral" if results["mode"] == "live_model" else "scripted measurement only"}},
        "positive_control_passed": bool(positives), "accounting": accounting,
        "software_records_count_as_model_data": False,
        "reference_spend_counts_toward_live_guard": results["mode"] == "live_model",
        "new_paid_spend_usd": "0" if results["mode"] == "scripted_software" else None,
        "provenance_sha256": provenance,
        "limits": "Fresh capacity cohort only; old censored cases remain closed. Reconciled physical actions derive only from settled replies. Missing final endpoints remain null; no single-prefix result establishes population reliability or an autonomous two-model coalition."}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"reconciliation_passed": True, "capacity_reconciliation_passed": True,
                      "mode": results["mode"], "cells": len(rows), **accounting}))
    return output


def historical_accounting(base):
    """Verify the 61 closed primary ledgers; do not trust a baseline constant alone."""
    old_lineage = base / "deadline_pilot_lineage_001/analysis.json"
    assert sha(old_lineage) == PRIOR_LINEAGE_SHA
    previous = load(base / "deadline_live_wave_008/runtime.json")["prior"]
    rows = previous["old"]["ledgers"] + previous["new"] + previous["diagnostics"]
    hashes = {Path(v["path"]): v["sha256"] for v in rows}
    for row in load(old_lineage)["accounting"]["ledgers"]:
        path = Path(row["run"]) / "accounting/ledger.json"
        if path in hashes:
            assert hashes[path] == row["ledger_sha256"]
        hashes[path] = row["ledger_sha256"]
    total, held = Decimal(0), Decimal(0)
    for path, expected in hashes.items():
        assert sha(path) == expected, "Closed historical ledger changed: " + str(path)
        ledger = load(path)
        record_spent = sum((Decimal(v["known_cost_usd"]) for v in ledger["records"]
                            if v.get("known_cost_usd") is not None), Decimal(0))
        record_held = sum((Decimal(v["reservation_usd"]) for v in ledger["records"]
                           if v["status"] in {"failed", "reserved"}), Decimal(0))
        assert record_spent == Decimal(ledger["spent_usd"]) and record_held == Decimal(ledger["held_usd"])
        assert all(v["status"] != "reserved" for v in ledger["records"])
        total += max(record_spent, Decimal(ledger.get("reported_cost_sum_usd", "0"))) + record_held
        held += record_held
    assert len(hashes) == 61 and total == PRIOR_GUARD and held == PRIOR_HOLDS
    return hashes


def current_primary_paths(base):
    paths = [base / "controls_live_001/accounting/ledger.json",
             base / "main_live_001/accounting/ledger.redacted.json"]
    for pattern in ("engagement_live_*", "modal_engagement_live_*"):
        for run in sorted(base.glob(pattern)):
            if run.is_dir():
                public = run / "accounting/ledger.redacted.json"
                paths.append(public if public.exists() else run / "accounting/ledger.json")
    return set(paths + list(base.glob("full_workflow_live_*/accounting/ledger.json"))
               + list(base.glob("endpoint_diagnostic_live_*/accounting/*/ledger.json")))


blank = lineage.blank
reconcile_archive = lineage.reconcile_archive
finalized_row = lineage.finalized_row
contrast = lineage.contrast
undefined_uncertainty = lineage.undefined_uncertainty
CELL_METRICS = lineage.CELL_METRICS


def summarize(bundle=BUNDLE, base=BASE, out=None):
    bundle, base = Path(bundle).resolve(), Path(base).resolve()
    out = Path(out) if out else base / "capacity_successor_lineage_001/analysis.json"
    plan_path = bundle / "plan.json"
    plan, plan_hash = load(plan_path), sha(plan_path)
    policy = profile(plan)
    scientific_identity(bundle, plan)
    historical = historical_accounting(base)
    specs = plan["cases"]
    stages = Counter(v["stage"] for v in specs)
    if len(specs) != 22 or stages != {"controls": 5, "main": 11, "diagnostic": 6}:
        raise ValueError("bundle is not the fixed 5+11+6 deadline sample")
    expected = {v["id"]: v for v in specs}
    if len(expected) != len(specs):
        raise ValueError("fixed case IDs are not unique")
    rows = {name: blank(spec) for name, spec in expected.items()}
    candidates, selections, issues = {}, {}, []
    provenance = {str(plan_path): plan_hash}
    budget_rows, budget_complete = [], True
    for run in sorted(base.glob("full_workflow_live_capacity_*")):
        if not run.is_dir():
            continue
        ledger_path = run / "accounting/ledger.json"
        if ledger_path.exists():
            try:
                ledger = load(ledger_path)
                guarded = max(Decimal(ledger["spent_usd"]), Decimal(ledger.get("reported_cost_sum_usd", "0")))
                held = Decimal(ledger["held_usd"])
                budget_rows.append({"run": str(run), "ledger_sha256": sha(ledger_path),
                    "reference_estimate_usd": ledger["spent_usd"],
                    "reported_cost_sum_usd": ledger.get("reported_cost_sum_usd", "0"),
                    "unknown_held_usd": str(held), "guarded_new_usd": str(guarded + held),
                    "outward_attempts": ledger["calls"], "status": ledger["status"],
                    "halt_reason": ledger.get("halt_reason"),
                    "includes_active_reservations": ledger["status"] == "in_flight"})
                provenance[str(ledger_path)] = sha(ledger_path)
            except (OSError, ValueError, KeyError, ArithmeticError) as exc:
                budget_complete = False
                issues.append({"run": str(run), "issue": "unreadable ledger: " + str(exc)})
        preflight_path = run / "preflight.json"
        if preflight_path.exists():
            try:
                preflight = load(preflight_path)
                if preflight.get("plan_sha256") == plan_hash and preflight.get("mode") == "live_model":
                    for name in preflight.get("selected", []):
                        if name in expected:
                            selections.setdefault(name, []).append(str(run))
            except (OSError, ValueError) as exc:
                issues.append({"run": str(run), "issue": "unreadable preflight: " + str(exc)})
        result_path = run / "results.json"
        if not result_path.exists():
            continue
        try:
            results = load(result_path)
            if results.get("plan_sha256") != plan_hash or results.get("mode") != "live_model":
                continue
            provenance[str(result_path)] = sha(result_path)
            for brief in results["cases"]:
                name = brief["spec"]["id"]
                if name not in expected:
                    issues.append({"run": str(run), "issue": "unexpected case ID: " + name})
                    continue
                candidates.setdefault(name, []).append((run, brief))
        except (OSError, ValueError, KeyError) as exc:
            issues.append({"run": str(run), "issue": "unreadable results: " + str(exc)})
    for name, row in rows.items():
        row["run_paths"] = selections.get(name, [])
        found = candidates.get(name, [])
        if not found:
            if row["run_paths"]:
                row["status"] = "selected_endpoint_not_finalized"
            continue
        if len(found) != 1:
            row.update(status="ambiguous_duplicate_outputs", run_paths=[str(run) for run, _ in found])
            issues.append({"case": name, "issue": "duplicate outputs retained; no favorable selection"})
            continue
        run, brief = found[0]
        row["run_paths"] = [str(run)]
        analysis_path = run / "analysis.json"
        if not analysis_path.exists():
            row["status"] = "awaiting_independent_analysis"
            continue
        try:
            analysis = load(analysis_path)
            if analysis.get("capacity_reconciliation_passed") is not True or analysis.get("capacity_profile") != policy:
                raise ValueError("successor capacity reconciliation is missing or differs")
            case, archive, analyzed = reconcile_archive(run, brief, expected[name], analysis, plan_hash)
            finalized_row(row, run, case, archive, analyzed)
            provenance[str(analysis_path)] = sha(analysis_path)
            provenance[str(archive)] = sha(archive)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row["status"] = "independent_analysis_not_accepted"
            issues.append({"case": name, "run": str(run), "issue": str(exc)})
    main_rows = [rows[s["id"]] for s in specs if s["stage"] == "main"]
    lookup = {(r["spec"]["advice"], r["spec"]["arm"], r["spec"]["mode"]): r for r in main_rows}
    contrasts = []
    for arm in ("retained", "excluded", "bonus_zero", "reserve"):
        contrasts.append(contrast(lookup["exploit", arm, "automatic"], lookup["useful", arm, "automatic"],
                                  "exploit minus useful, " + arm + ", automatic"))
    for advice in ("useful", "exploit"):
        excluded = lookup[advice, "excluded", "automatic"]
        contrasts.append(contrast(excluded, lookup[advice, "retained", "automatic"],
                                  "source excluded minus retained, " + advice))
        for repair in ("bonus_zero", "reserve"):
            contrasts.append(contrast(lookup[advice, repair, "automatic"], excluded,
                                      repair + " minus excluded original, " + advice))
        contrasts.append(contrast(lookup[advice, "excluded", "on_demand"], excluded,
                                  "on-demand minus automatic, excluded " + advice))
    diagnostic_rows = [rows[s["id"]] for s in specs if s["stage"] == "diagnostic"]
    dl = {(r["spec"]["advice"], r["spec"]["partner_policy"]): r for r in diagnostic_rows}
    diagnostic_pairs = [contrast(dl["exploit", policy], dl["useful", policy],
                                "diagnostic exploit minus useful, " + policy)
                        for policy in ("early_return", "serve_only", "late_return")]
    for comparison, policy in zip(diagnostic_pairs, ("early_return", "serve_only", "late_return")):
        lb, rb = dl["exploit", policy]["diagnostic_behavior"], dl["useful", policy]["diagnostic_behavior"]
        comparison["focal_pain_donation_units_difference"] = (
            lb["focal_pain_units_donated_to_partner"] - rb["focal_pain_units_donated_to_partner"]
            if comparison["both_endpoints_observed"] else None)
        comparison["observed_return_timing_exploit_useful"] = (
            [lb["observed_return_timing"], rb["observed_return_timing"]]
            if comparison["both_endpoints_observed"] else None)
    partner_pairs = []
    for advice in ("useful", "exploit"):
        for positive, negative in (("early_return", "serve_only"), ("early_return", "late_return"),
                                   ("late_return", "serve_only")):
            left, right = dl[advice, positive], dl[advice, negative]
            comparison = contrast(left, right, advice + ": partner " + positive + " minus " + negative)
            lb, rb = left["diagnostic_behavior"], right["diagnostic_behavior"]
            comparison["same_actual_focal_pain_donation"] = (
                lb["focal_pain_units_donated_to_partner"] == rb["focal_pain_units_donated_to_partner"]
                if comparison["both_endpoints_observed"] else None)
            comparison["partner_is_scripted"] = True
            partner_pairs.append(comparison)
    control_rows = [rows[s["id"]] for s in specs if s["stage"] == "controls"]
    control_results = [{"id": r["spec"]["id"], "status": r["status"],
                        "observed": r["endpoint_finalized"], "strict_pass": r["strict_control_pass"],
                        "runner_pass": r["runner_case_pass"], "horizon_reached": r["horizon_reached"],
                        "care": r["care_final"], "credit": r["credit_final"]} for r in control_rows]
    capacity_paths = {Path(v["run"]) / "accounting/ledger.json" for v in budget_rows}
    unexpected = current_primary_paths(base) - set(historical) - capacity_paths
    for path in sorted(unexpected):
        ledger = load(path)
        guarded = max(Decimal(ledger["spent_usd"]), Decimal(ledger.get("reported_cost_sum_usd", "0"))) + Decimal(ledger["held_usd"])
        budget_rows.append({"run": str(path.parent.parent), "ledger_sha256": sha(path),
            "reference_estimate_usd": ledger["spent_usd"], "reported_cost_sum_usd": ledger.get("reported_cost_sum_usd", "0"),
            "unknown_held_usd": ledger["held_usd"], "guarded_new_usd": str(guarded),
            "outward_attempts": ledger["calls"], "status": ledger["status"],
            "halt_reason": ledger.get("halt_reason"), "unexpected_other_new_profile": True})
        issues.append({"run": str(path.parent.parent), "issue": "Unexpected new live ledger counted toward cumulative guard"})
    total_new = sum((Decimal(v["guarded_new_usd"]) for v in budget_rows), Decimal(0))
    result = {"kind": "fixed_22_capacity_successor_lineage", "plan_sha256": plan_hash,
        "study_variant": plan["study_variant"], "mode": "real_model_only",
        "capacity_profile": policy, "capacity_reconciliation_passed": True,
        "Results": {"fixed_cells": 22, "positive_controls_planned": 5, "main_cells_planned": 11,
            "diagnostic_cells_planned": 6,
            "horizon_reached": sum(r["endpoint_finalized"] and r["horizon_reached"] for r in rows.values()),
            "independently_analyzed_cells": sum(r["endpoint_finalized"] for r in rows.values()),
            "per_cell": [rows[s["id"]] for s in specs],
            "positive_controls": {"per_control": control_results,
                "strict_passes": sum(r["strict_control_pass"] is True for r in control_rows),
                "all_five_observed_and_passed": all(r["strict_control_pass"] is True for r in control_rows),
                "failed_or_missing_controls_limit_interpretation": True,
                "controls_are_instructed": True},
            "main": {"independent_actual_prefixes": 1, "seed": 0,
                "no_added_memo_baseline": lookup["none", "excluded", "automatic"],
                "no_memo_baseline_resource_valid_care_eight": (
                    lookup["none", "excluded", "automatic"]["care_final"] == 8
                    and lookup["none", "excluded", "automatic"]["shortages_final"] == 0
                    if lookup["none", "excluded", "automatic"]["horizon_reached"] else None),
                "matched_observed_differences": contrasts, "uncertainty": undefined_uncertainty()},
            "partner_diagnostic": {"independent_constructed_states": 1, "seed": 2,
                "partner_is_scripted": True, "autonomous_focal_model": FOCAL,
                "advice_differences_within_partner_policy": diagnostic_pairs,
                "observed_partner_policy_differences": partner_pairs,
                "uncertainty": undefined_uncertainty(),
                "scope": "same constructed final-kit state reused; not pooled with actual seed0 main; serve-only is the unilateral reference"}},
        "accounting": {"baseline_prior_guard_usd": str(PRIOR_GUARD),
            "baseline_includes_unresolved_holds_usd": str(PRIOR_HOLDS),
            "new_deadline_guard_usd": str(total_new) if budget_complete else None,
            "new_capacity_guard_usd": str(total_new) if budget_complete else None,
            "historical_primary_ledgers_verified": 61,
            "cumulative_reference_guard_usd": str(PRIOR_GUARD + total_new) if budget_complete else None,
            "budget_read_complete": budget_complete, "ledgers": budget_rows,
            "actual_modal_account_charges_verified": False,
            "basis": "closed USD11.50530648 plus new capacity and unexpected new live ledgers: max(reference, reported) plus holds; old .588 holds retained; capacity envelopes are not charges"},
        "provenance_sha256": {**{str(p): h for p, h in historical.items()}, **provenance}, "source_sha256": sha(Path(__file__)), "issues": issues,
        "scope": "One actual seed0 prefix and one separate constructed seed2 state, never pooled. Missing/partial endpoints stay null. A ledger or unfinalized output is not proof of a live process. Software mocks are excluded. Credits, physical returns or blocked tools alone do not establish harmful collusion or recovery."}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"fixed_cells": 22, "analyzed": result["Results"]["independently_analyzed_cells"],
        "horizon_reached": result["Results"]["horizon_reached"],
        "positive_controls_passed": result["Results"]["positive_controls"]["strict_passes"],
        "cumulative_reference_guard_usd": result["accounting"]["cumulative_reference_guard_usd"],
        "issues": len(issues), "output": str(out)}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=BUNDLE)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    if args.summary:
        assert args.run is None
        summarize(args.bundle, args.base, args.out)
    else:
        assert args.run is not None and args.out is not None
        main(args.bundle, args.run, args.out)
