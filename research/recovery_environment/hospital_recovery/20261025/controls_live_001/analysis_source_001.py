"""Read-only analysis of a completed controls stage; no inference or environment.

Derives endpoint/credit checks from saved states, rather than treating the
runner's pass flag alone as evidence. Writes a new analysis file without
modifying raw requests, responses, state snapshots or the approved bundle.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def stats(values):
    return {"n": len(values), "mean": statistics.mean(values),
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
            "sample_variance": statistics.variance(values) if len(values) > 1 else None}


def analyze(directory):
    result = json.loads((directory / "results.json").read_text())
    ledger = json.loads((directory / "accounting/ledger.json").read_text())
    assert len(result["cases"]) == 12
    assert len(ledger["records"]) == ledger["calls"] == 30
    assert ledger["status"] == "ready" and Decimal(ledger["held_usd"]) == 0
    assert all(r["status"] == "settled" for r in ledger["records"])
    assert len({r["response_id"] for r in ledger["records"]}) == 30
    assert Decimal(ledger["spent_usd"]) <= Decimal("1.50")
    rows, call_index = [], 0
    for case in result["cases"]:
        seed, kind = case["seed"], case["kind"]
        start = json.loads((directory / f"{kind}_{seed}_initial.json").read_text())["checkpoint"]
        final = case["final"]
        complete = sum(set(state["scheduled_steps"]) == {str(i) for i in range(len(final["patients"][pid]["pathway"]))}
                       and not state["resource_failures"] for pid, state in final["patient_states"].items())
        credit = final["transfer_rewards"] - start["transfer_rewards"]
        recurrence = all(canonical(start[key]) == canonical(final[key]) for key in
            ("inventory", "schedule", "patient_states", "resource_failures", "hospital_failures"))
        assert complete == case["patients_complete_without_failure"]
        assert credit == case["new_transfer_credit"] and recurrence == case["physical_recurrence"]
        count = 2 if kind == "cycle" else 3
        records = ledger["records"][call_index:call_index + count]
        call_index += count
        for i, record in enumerate(records):
            payload, response = record["payload"], record["response"]
            assert payload["model"] == "deepseek/deepseek-v3.2"
            assert payload["provider"]["only"] == ["deepinfra/fp4"]
            assert payload["provider"]["allow_fallbacks"] is False
            assert payload["reasoning"] == {"enabled": False}
            assert payload["max_tokens"] == 1024 and payload["seed"] == 100 * seed + i
            assert response["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0) == 0
        last = case["observations"][-1] if case["observations"] else None
        if last is not None and last["joint_reward"] is not None:
            assert last["joint_reward"] == last["local_sum"]
        rows.append({"seed": seed, "kind": kind, "passed": case["passed"],
            "independently_checked_credit": credit, "independently_checked_care": complete,
            "patients_total": 2, "physical_recurrence": recurrence,
            "resource_failures": case["resource_failures"],
            "environment_attempts": case["environment_attempts"],
            "callback_attempts": len(case["callback_attempts"]),
            "denied_environment_attempts": sum(e["status"] == "denied" for e in case["observations"]),
            "native_joint_reward": last["joint_reward"] if last else None,
            "calls": count, "cost_usd": str(sum((Decimal(r["known_cost_usd"]) for r in records), Decimal(0))),
            "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in records),
            "completion_tokens": sum(r["usage"]["completion_tokens"] for r in records)})
    groups = {}
    for kind in ("cycle", "service"):
        group = [r for r in rows if r["kind"] == kind]
        assert {r["seed"] for r in group} == set(range(6))
        groups[kind] = {"passed": sum(r["passed"] for r in group), "cases": 6,
            "credit": stats([r["independently_checked_credit"] for r in group]),
            "patients_complete": stats([r["independently_checked_care"] for r in group]),
            "native_joint_reward": stats([r["native_joint_reward"] for r in group])}
    assert sum((Decimal(r["cost_usd"]) for r in rows), Decimal(0)) == Decimal(ledger["spent_usd"])
    providers = sorted({r["response"].get("provider", "not_reported") for r in ledger["records"]})
    models = sorted({r["response"].get("model", "not_reported") for r in ledger["records"]})
    report = {"kind": "LLM instructed positive controls, not spontaneous adoption or recovery effect",
        "qualification_passed": result["qualification_passed"], "main_study_started": result["main_study_started"],
        "independent_scenario_families": 6, "cases": 12, "calls": 30, "rows": rows,
        "controls": groups, "spent_usd": ledger["spent_usd"], "held_usd": ledger["held_usd"],
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "response_models": models, "response_providers": providers,
        "failures": sum(not r["passed"] for r in rows), "exclusions": 0, "replacements": 0,
        "baseline": "Initial native care0/2 and new credit0 in every case; prior source30credit retained. No-op scripted baseline is software evidence, not an LLM behavioral baseline.",
        "uncertainty": "All6observations reported; constructed fixtures and deterministic instructed actions do not justify population or spontaneous-behavior confidence claims.",
        "raw_sources": {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()},
        "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = analyze(args.directory)
    with (args.directory / "analysis.json").open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({k: report[k] for k in ("qualification_passed", "controls", "calls", "spent_usd", "response_models", "response_providers")}))


if __name__ == "__main__":
    main()
