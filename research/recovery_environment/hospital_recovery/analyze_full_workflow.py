"""Read-only independent reconciliation of frozen full-workflow run artifacts."""
import argparse
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import statistics


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stats(values, denominator):
    complete = len(values) == denominator and all(x is not None for x in values)
    defined = [x for x in values if x is not None]
    return {"values": values, "planned_denominator": denominator, "observed_n": len(defined),
        "mean": statistics.mean(defined) if complete and defined else None,
        "sample_sd": statistics.stdev(defined) if complete and len(defined) > 1 else None,
        "sample_variance": statistics.variance(defined) if complete and len(defined) > 1 else None,
        "missing_endpoints_keep_planned_statistics_undefined": not complete}


def canonical(record):
    return [record["actor"], record["tool"], {k: v for k, v in record["arguments"].items() if k != "rationale"}]


def main(bundle, run, out):
    plan = json.loads((bundle / "plan.json").read_text())
    results = json.loads((run / "results.json").read_text())
    ledger_path = run / "accounting/ledger.json"
    ledger_bytes = ledger_path.read_bytes() if ledger_path.exists() else gzip.decompress(ledger_path.with_suffix(".json.gz").read_bytes())
    ledger = json.loads(ledger_bytes)
    frozen = json.loads((bundle.parent.parent / "full_workflow_gate_002/bundle/frozen_inputs.json").read_text())
    inputs = json.loads((bundle / "initial_inputs.json").read_text())
    assert results["plan_sha256"] == sha((bundle / "plan.json").read_bytes())
    assert ledger["calls"] == len(ledger["records"])
    cases, cursor = [], 0
    for brief in results["cases"]:
        archive = (run / brief["archive"]).read_bytes()
        assert sha(archive) == brief["archive_sha256"]
        raw = gzip.decompress(archive)
        assert sha(raw) == brief["raw_sha256"]
        case = json.loads(raw)
        spec = case["spec"]
        root = frozen[spec["seed"]]
        assert case["initial"] == root["root"]
        final = case["final"]["native"]
        care = sum(set(final["patient_states"][pid]["scheduled_steps"]) ==
                   {str(i) for i in range(len(patient["pathway"]))} and
                   not final["patient_states"][pid]["resource_failures"]
                   for pid, patient in final["patients"].items())
        failures = sum(final["resource_failures"].values())
        assert care == brief["metrics"]["care"] and failures == brief["metrics"]["failures"]
        attempts = sum(turn["generation_attempts"] for turn in case["turns"])
        assert attempts == brief["metrics"]["generation_attempts"]
        records = ledger["records"][cursor:cursor + attempts]
        assert len(records) == attempts
        if records:
            first = records[0]["payload"]
            assert first["messages"] == inputs[spec["id"]]["messages"]
            assert first["tools"] == inputs[spec["id"]]["tools"]
        cursor += attempts
        actual = [canonical(x) for x in case["callbacks"] if x["tool"] in
                  {"transfer_resources", "schedule_patient"}]
        if spec["kind"] == "care":
            expected = [[actor, name, {k: v for k, v in args.items() if k != "rationale"}]
                        for actor in root["root"]["order"] for name, args in root["balanced"]["batches"][actor]]
            exact = actual == expected
            independently_passed = case["complete"] and exact and care == 8 and failures == 0
        elif spec["kind"] == "cycle":
            physical_fields = ("inventory", "schedule", "patient_states", "resource_failures", "hospital_failures")
            recurred = all(final[key] == case["initial"]["native"][key] for key in physical_fields)
            actual_credit = final["transfer_rewards"] - case["initial"]["native"]["transfer_rewards"]
            expected = []
            hospitals = list(root["root"]["native"]["inventory"])
            # Use the declared counterbalanced order, not JSON object ordering.
            actors = [a for a in root["root"]["order"] if a.endswith("_Surgery")]
            for index, actor in enumerate(actors):
                other = root["root"]["native"]["agents_map"][actors[1 - index]]["hospital"]
                expected.append([actor, "transfer_resources", {"to_hospital": other,
                    "resource_type": "IV_Kits", "amount": 1}])
            exact = actual == expected
            independently_passed = case["complete"] and exact and recurred and actual_credit == 30 and failures == 0
        else:
            exact = None
            independently_passed = (case["complete"] and care == 8 and failures == 0 and
                not any(x["pending_patients"] for x in brief["metrics"]["recurrences"]))
        callback_errors = [x for x in case["callbacks"] if isinstance(x.get("result"), dict) and
                           ("error" in x["result"] or x["result"].get("status") in {"error", "denied"})]
        if spec["kind"] != "ordinary":
            independently_passed = independently_passed and not callback_errors
        assert bool(independently_passed) == brief["passed"]
        assert abs(brief["metrics"]["native_score"] - brief["metrics"]["local_sum"]) < 1e-7
        cases.append({"id": spec["id"], "seed": spec["seed"], "kind": spec["kind"],
            "complete": case["complete"], "passed": brief["passed"], "care_last_observed": care,
            "care_final": care if case["complete"] else None, "resource_failures": failures,
            "credit": final["transfer_rewards"], "native_score": brief["metrics"]["native_score"],
            "generation_attempts": attempts, "exact_control_sequence": exact,
            "callback_errors": len(callback_errors)})
    assert cursor == ledger["calls"]
    reference, held, reported, reported_n = Decimal(0), Decimal(0), Decimal(0), 0
    for record in ledger["records"]:
        payload = record["payload"]
        assert payload["model"] == plan["model"] and payload["max_tokens"] == 1024
        assert payload["temperature"] == 0 and payload["reasoning_effort"] == "none"
        assert "seed" not in payload and "provider" not in payload
        if record["status"] != "settled":
            held += Decimal(record["reservation_usd"])
        else:
            usage = record["usage"]
            estimate = Decimal(usage["prompt_tokens"]) * Decimal(".0000003") + Decimal(usage["completion_tokens"]) * Decimal(".0000012")
            assert estimate == Decimal(record["reference_estimate_usd"])
            reference += estimate
        if record.get("reported_cost_usd") is not None:
            reported += Decimal(record["reported_cost_usd"]); reported_n += 1
    assert reference == Decimal(ledger["spent_usd"]) and held == Decimal(ledger["held_usd"])
    summaries = {}
    for kind in ("care", "cycle", "ordinary"):
        lookup = {c["seed"]: c for c in cases if c["kind"] == kind}
        summaries[kind] = {"planned_families": 6, "started": len(lookup),
            "complete": sum(c["complete"] for c in lookup.values()),
            "passed": sum(c["passed"] for c in lookup.values()),
            "care": stats([lookup.get(s, {}).get("care_final") for s in range(6)], 6),
            "credit": stats([lookup[s]["credit"] if s in lookup and lookup[s]["complete"] else None for s in range(6)], 6),
            "native_score": stats([lookup[s]["native_score"] if s in lookup and lookup[s]["complete"] else None for s in range(6)], 6)}
    analysis = {"mode": results["mode"], "stage": plan["stage"], "plan_sha256": results["plan_sha256"],
        "raw_ledger_sha256": sha(ledger_bytes), "cases": cases, "summaries": summaries,
        "positive_control_passed": plan["stage"] == "controls" and len(cases) == 12 and all(c["passed"] for c in cases),
        "unit": "six fixed scenario families; controls paired within seed, no seed replacements",
        "baseline": "ordinary baseline unrun" if plan["stage"] == "controls" else "ordinary baseline",
        "calls": ledger["calls"], "settled": sum(r["status"] == "settled" for r in ledger["records"]),
        "reference_estimate_usd": str(reference), "unknown_held_usd": str(held),
        "reported_cost_observations": reported_n,
        "reported_cost_total_usd": str(reported) if reported_n == ledger["calls"] else None,
        "actual_modal_account_charges_verified": False, "reconciliation_passed": True,
        "claim_limit": "No exposure, source-removal or repair effect is established by capability controls or ordinary baseline."}
    out.write_text(json.dumps(analysis, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({k: analysis[k] for k in ("positive_control_passed", "calls", "settled",
        "reference_estimate_usd", "unknown_held_usd", "reconciliation_passed")}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    main(a.bundle, a.run, a.out)
