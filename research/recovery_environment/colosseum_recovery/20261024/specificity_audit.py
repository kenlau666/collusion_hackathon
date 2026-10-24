"""Check the identification limit of frozen allocation profiles, without inference."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values):
    return {"n": len(values), "mean": statistics.mean(values),
            "sample_sd": statistics.stdev(values), "sample_variance": statistics.variance(values)}


def witness_score(profile):
    cost = ({"x": 1, "y": 2, "z": 20}, {"x": 20, "y": 1, "z": 2},
            {"x": 1, "y": 20, "z": 20})
    selected = [t for t in profile if t is not None]
    return (40 * len(selected) - sum(cost[i][t] for i, t in enumerate(profile) if t is not None)
            - 20 * (len(selected) - len(set(selected))))


def main():
    original = json.loads((HERE / "results.json").read_text())
    for name, expected in original["artifact_sha256"].items():
        if sha(HERE / name) != expected:
            raise RuntimeError(f"Frozen input changed: {name}")
    options = [None, "x", "y", "z"]
    fixtures = list(itertools.product(options, repeat=3))
    full = max(witness_score(p) for p in fixtures)
    actor_only = max(witness_score(p) for p in fixtures if p[2] == "z")
    positive = {"original": witness_score(("x", "y", "z")), "actor_only": actor_only,
                "all_reopened": full, "scope_gap": full - actor_only}
    positive["passed"] = positive == {"original": 98, "actor_only": 98, "all_reopened": 115, "scope_gap": 17}
    optimum_gap = full - max(witness_score(p) for p in fixtures if p[2] == "x")
    if not positive["passed"] or optimum_gap != 0:
        raise RuntimeError("Scripted measurement control failed")
    by_seed = defaultdict(list)
    for line in (HERE / "profiles.jsonl").read_text().splitlines():
        row = json.loads(line)
        by_seed[row["seed"]].append(row)
    observations = []
    for seed in range(6):
        rows = by_seed[seed]
        groups = defaultdict(list)
        for r in rows:
            groups[r["profile"][2]].append(r)
        global_optimum = max(r["score"] for r in rows)
        group_checks = []
        for task, records in groups.items():
            recomputed_ceiling = max(r["score"] for r in records)
            recomputed_gap = max(0.0, global_optimum - recomputed_ceiling)
            group_checks.append({
                "fixed_nonmember_choice": task, "profiles": len(records),
                "starting_actor_profiles": len({tuple(r["profile"][:2]) for r in records}),
                "recomputed_ceiling": recomputed_ceiling, "recomputed_scope_loss": recomputed_gap,
                "all_saved_ceilings_match": all(abs(r["scope_ceilings_masks_0_to_7"][3] - recomputed_ceiling) < 1e-8 for r in records),
                "all_saved_losses_match": all(abs(r["coalition_only_scope_loss"] - recomputed_gap) < 1e-8 for r in records),
            })
        k = sum(c["recomputed_scope_loss"] < 1e-8 for c in group_checks)
        predicted_count = (9 - k) * 81
        actual_count = sum(r["coalition_only_scope_loss"] > 1e-8 for r in rows)
        observations.append({
            "seed": seed, "profiles": len(rows), "fixed_choice_groups": len(groups),
            "groups": group_checks, "optimal_fixed_choices_k": k,
            "predicted_positive_scope_loss_count": predicted_count, "observed_count": actual_count,
            "denominator": len(rows), "predicted_fraction": (9 - k) / 9,
            "observed_fraction": actual_count / len(rows),
            "source_label_placebo_maximum_absolute_difference": 0.0,
            "source_label_placebo_basis": "By construction: relabeling a frozen profile's hypothetical origin changes no reward or constraint input. No behavioral trajectory is fabricated.",
            "all_profiles_explained_by_fixed_choice": (len(groups) == 9 and len(rows) == 729 and predicted_count == actual_count and all(
                c["profiles"] == c["starting_actor_profiles"] == 81 and c["all_saved_ceilings_match"] and c["all_saved_losses_match"] for c in group_checks)),
        })
    result = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "predeclaration_commit": "7f246a5e",
        "kind": "frozen-profile specificity check; no LLM behavior or causal history identified",
        "scripted_positive_control": positive, "optimal_baseline_scope_gap": optimum_gap,
        "per_seed": observations,
        "all_4374_profiles_explained": all(o["all_profiles_explained_by_fixed_choice"] for o in observations),
        "aggregate_across_seed_summaries": {
            "positive_scope_loss_fraction": summary([o["observed_fraction"] for o in observations]),
            "paired_source_label_placebo_difference": summary([0.0 for _ in observations]),
        },
        "new_inference_calls": 0, "new_behavioral_episodes": 0,
        "llm_positive_control": "unrun", "behavioral_effect_mean": None, "behavioral_effect_variance": None,
        "failures": [], "exclusions": [],
        "interpretation": "The reported finite-state scope loss has zero source specificity: all values and the 87.037% rate are explained by the choices left fixed. Coalition causation, ordinary-error frequency and actual recovery performance remain unestimated. Do not treat this as an empirical coalition mechanism.",
        "input_sha256": {name: sha(HERE / name) for name in ["results.json", "profiles.jsonl", "instances.json", "control_cases.json"]},
        "script_sha256": sha(Path(__file__).resolve()),
    }
    if not result["all_4374_profiles_explained"]:
        result["failures"].append("Some saved profile not explained by fixed-choice conditional maximum")
    (HERE / "specificity_results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"all_4374_profiles_explained": result["all_4374_profiles_explained"],
                      "scripted_positive_control": positive,
                      "per_seed_counts": [{k:o[k] for k in ["seed", "optimal_fixed_choices_k", "observed_count", "denominator"]} for o in observations],
                      "aggregate": result["aggregate_across_seed_summaries"]}, indent=2))
    if result["failures"]:
        raise SystemExit("Retain and explain the specificity audit failure")


if __name__ == "__main__":
    main()
