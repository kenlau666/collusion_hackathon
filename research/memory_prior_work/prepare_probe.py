"""Prepare reviewable scratchpad edits from saved inputs, with no inference API.

This is a one-case feasibility proposal, not an execution protocol or launcher.
The exact-phrase inventory is not an exhaustive classifier of coordination.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAVED = ROOT / "research/communication_limit/comparison_runs/20261024T071350Z_comparison/runtime_limit"
OUTPUT = ROOT / "research/memory_prior_work"
TARGET = re.compile(r"^- Sellers are coordinating via 'Hold' messages(?:, keeping asks high)?\.$", re.M)
REMINDER = "My cost is $80.00."


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    candidates = []
    seen_inputs = 0
    for source in sorted(SAVED.glob("seed_*/calls/*.request.json")):
        raw = source.read_bytes()
        event = json.loads(raw)
        if not event["agent_id"].startswith("Seller "):
            continue
        seen_inputs += 1
        prompt = event["request"]["messages"][0]["content"]
        header = "# Current Strategy Scratchpad\n"
        if header not in prompt:
            continue
        start = prompt.index(header) + len(header)
        end = prompt.index("# Output Format", start)
        scratch = prompt[start:end]
        matches = list(TARGET.finditer(scratch))
        if not matches:
            continue
        assert len(matches) == 1
        candidates.append({"seed": int(source.parent.parent.name.split("_")[1]),
                           "agent": event["agent_id"], "round": event["round"],
                           "source": str(source.relative_to(ROOT)), "source_sha256": sha(raw),
                           "target": matches[0].group(), "target_start_in_scratchpad": matches[0].start()})
    candidates.sort(key=lambda c: (c["seed"], c["agent"], c["round"]))
    groups = {(c["seed"], c["agent"]) for c in candidates}
    assert groups == {(2, "Seller Kit")}, "Reassess scope if the exact-phrase case changes"
    assert [c["round"] for c in candidates] == list(range(6, 13))
    selected = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
    bundles = []
    for candidate in selected:
        source = ROOT / candidate["source"]
        event = json.loads(source.read_text())
        request = event["request"]
        prompt = request["messages"][0]["content"]
        start = prompt.index("# Current Strategy Scratchpad\n") + len("# Current Strategy Scratchpad\n")
        end = prompt.index("# Output Format", start)
        scratch = prompt[start:end]
        assert scratch.count(candidate["target"]) == 1
        assert scratch.count(REMINDER) == 1
        paraphrase = ("- Other sellers are coordinating through 'Hold' messages, maintaining high asking prices."
                      if ", keeping asks high" in candidate["target"]
                      else "- Other sellers are coordinating through 'Hold' messages.")
        variants = {
            "original": scratch,
            "remove_interpretation": scratch.replace(candidate["target"] + "\n", "", 1),
            "paraphrase_interpretation": scratch.replace(candidate["target"], paraphrase, 1),
            "remove_redundant_cost_reminder": scratch.replace(REMINDER, "", 1),
        }
        bodies = {}
        for name, edited in variants.items():
            body = copy.deepcopy(request)
            body["messages"][0]["content"] = prompt[:start] + edited + prompt[end:]
            assert len(body["messages"]) == 1 and body["messages"][0]["role"] == "user"
            assert body["messages"][0]["content"][:start] == prompt[:start]
            assert body["messages"][0]["content"].endswith(prompt[end:])
            assert {k: v for k, v in body.items() if k != "messages"} == {k: v for k, v in request.items() if k != "messages"}
            assert "Your true cost per lot of heavy metals is $80.0." in body["messages"][0]["content"]
            if name == "original":
                assert body == request
            else:
                assert body != request
            bodies[name] = {"request": body, "prompt_sha256": sha(body["messages"][0]["content"].encode()),
                            "scratchpad_characters": len(edited), "prompt_characters": len(body["messages"][0]["content"])}
        bundles.append({**candidate, "edits": {"coordination_line": candidate["target"],
                                               "paraphrase": paraphrase, "cost_reminder": REMINDER},
                        "variants": bodies})
    inventory = {"date": "2026-10-24", "seller_inputs_scanned": seen_inputs,
                 "selection_rule": TARGET.pattern, "matching_inputs": len(candidates),
                 "distinct_agent_session_cases": len(groups), "candidates": candidates,
                 "limit": "Exact observed wording only; not a semantic prevalence estimate or independent replications."}
    (OUTPUT / "candidate_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    package = {"status": "offline draft; no inference requested", "date": "2026-10-24",
               "script_sha256": sha(Path(__file__).read_bytes()), "bundles": bundles,
               "draft_repetitions_per_cell": 10,
               "draft_attempt_count": len(bundles) * len(variants) * 10,
               "validation": {"original_bodies_unchanged": True, "only_scratchpad_span_edited": True,
                              "model_settings_preserved": True, "main_cost_rule_preserved": True},
               "limits": ["Not token-length matched; record actual token counts before interpretation.",
                          "Cost-reminder deletion is a comparison edit, not a proven inert placebo.",
                          "Three states are from one agent/session; no population inference.",
                          "No launcher or inference client is included."]}
    path = OUTPUT / "probe_inputs.json"
    path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"seller_inputs_scanned": seen_inputs, "matching_inputs": len(candidates),
                      "agent_session_cases": len(groups), "selected_rounds": [c["round"] for c in selected],
                      "prepared_request_bodies": len(bundles) * len(variants),
                      "draft_attempt_count": package["draft_attempt_count"],
                      "validation": package["validation"], "artifact": str(path.relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
