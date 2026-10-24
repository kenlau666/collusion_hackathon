"""Audit saved A/B/C/D memory restoration offline; never imports inference clients.

Reads immutable experiment artifacts and writes a separate analysis artifact.
Checks routing, not whether generated descriptions or strategies are true.
"""
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPARISON = ROOT / "research/communication_limit/comparison_runs/20261024T071350Z_comparison"
BASELINE = ROOT / "research/communication_limit/modal_runs/20261024T065354Z_modal_baseline"
OUTPUT = ROOT / "research/communication_limit/context_review/context_memory_audit.json"
BATCHES = {"A": BASELINE, "B": COMPARISON / "prompt_limit",
           "C": COMPARISON / "runtime_limit", "D": COMPARISON / "no_chat"}


def relative(path):
    return str(path.relative_to(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(prompt, start, end):
    if start not in prompt:
        return None
    return prompt.split(start, 1)[1].split(end, 1)[0]


def main():
    errors, records, examples = [], [], []
    counts = defaultdict(int)
    sizes = defaultdict(list)
    selected = {("A", 0, "Seller Max", 1),
                ("B", 2, "Seller Kit", 14), ("B", 2, "Seller Mia", 14),
                ("C", 2, "Seller Kit", 5), ("C", 2, "Seller Kit", 6),
                ("C", 2, "Seller Mia", 13), ("C", 2, "Seller Mia", 14),
                ("C", 2, "Seller Mia", 15), ("C", 2, "Seller Lena", 13),
                ("C", 2, "Seller Lena", 14), ("C", 2, "Buyer Ana", 3),
                ("C", 2, "Buyer Ana", 4), ("D", 0, "Seller Max", 4),
                ("D", 0, "Seller Max", 5)}
    for arm, batch in BATCHES.items():
        for seed in range(3):
            session = batch / f"seed_{seed}"
            groups = defaultdict(list)
            rounds = {r["round_number"]: r for r in json.loads((session / "rounds.json").read_text())}
            for path in sorted((session / "calls").glob("*.result.json")):
                event = json.loads(path.read_text())
                groups[event["agent_id"]].append((event["round"], path, event))
            if len(groups) != 6:
                errors.append(f"{arm}/{seed}: expected six agents")
            for agent_id, events in sorted(groups.items()):
                events.sort(key=lambda entry: entry[0])
                if [entry[0] for entry in events] != list(range(1, 16)):
                    errors.append(f"{arm}/{seed}/{agent_id}: unexpected rounds")
                memories, scratch = {}, ""
                role = "seller" if agent_id.startswith("Seller ") else "buyer"
                for round_no, path, event in events:
                    label = f"{arm}/{seed}/{agent_id}/{round_no}"
                    request_path = path.with_name(path.name.replace(".result.json", ".request.json"))
                    saved_request = json.loads(request_path.read_text())
                    if saved_request["request"] != event["request"]:
                        errors.append(label + ": request/result body mismatch")
                    request = event["request"]
                    messages = request["messages"]
                    envelope_ok = len(messages) == 1 and messages[0]["role"] == "user"
                    if not envelope_ok or "tools" in request:
                        errors.append(label + ": unexpected input envelope/tool interface")
                    prompt = messages[0]["content"]
                    result = json.loads(event["answer"])
                    memory = section(prompt, "# Your Memory\n", "# Market Status")
                    expected = "\n".join(f"Hour {hour}: {text}" for hour, text in sorted(memories.items())) or "No memories yet."
                    memory_ok = memory == expected + "\n\n"
                    if not memory_ok:
                        errors.append(label + ": accumulated own-memory mismatch")
                    scratch_input = section(prompt, "# Current Strategy Scratchpad\n", "# Output Format")
                    scratch_ok = scratch_input == scratch + "\n\n\n" if scratch else scratch_input is None
                    if not scratch_ok:
                        errors.append(label + ": prior own-scratchpad mismatch")
                    chat = section(prompt, "# Messages Received from Other Sellers (Previous Hour)\n",
                                   "# Current Strategy Scratchpad" if scratch_input is not None else "# Output Format")
                    if (role == "buyer" or arm == "D") and chat is not None:
                        errors.append(label + ": unexpected seller-chat section")
                    if role == "seller" and arm == "D" and "Seller-to-seller messaging is unavailable." not in prompt:
                        errors.append(label + ": missing no-chat notice")
                    counts[f"{arm}_{role}_inputs"] += 1
                    counts["single_user_inputs"] += int(envelope_ok)
                    counts["memory_checks_passed"] += int(memory_ok)
                    counts["scratchpad_checks_passed"] += int(scratch_ok)
                    counts["empty_initial_states"] += int(round_no == 1 and not memories and not scratch and memory_ok and scratch_ok)
                    counts["memory_transition_checks_passed"] += int(round_no > 1 and memory_ok)
                    counts["scratchpad_transition_checks_passed"] += int(round_no > 1 and scratch_ok)
                    for name, value in (("memory", expected), ("scratchpad", scratch), ("prompt", prompt)):
                        sizes[(arm, role, round_no, name)].append(len(value))
                    records.append({"arm": arm, "seed": seed, "agent": agent_id, "round": round_no,
                                    "result": relative(path), "result_sha256": digest(path),
                                    "request": relative(request_path), "request_sha256": digest(request_path),
                                    "memory_entries": len(memories), "memory_characters": len(expected),
                                    "scratchpad_characters": len(scratch), "prompt_characters": len(prompt),
                                    "memory_ok": memory_ok, "scratchpad_ok": scratch_ok})
                    if (arm, seed, agent_id, round_no) in selected:
                        event_message = rounds[round_no].get("seller_message_events", {}).get(agent_id)
                        examples.append({"arm": arm, "seed": seed, "agent": agent_id, "round": round_no,
                                         "result": relative(path), "input_memory": expected,
                                         "input_scratchpad": scratch, "input_seller_messages_section": chat,
                                         "generated": result, "seller_message_event": event_message,
                                         "settled_round_trades": rounds[round_no]["trades"]})
                    if result.get("new_memory"):
                        memories[round_no] = result["new_memory"]
                    if result.get("scratch_pad_update"):
                        scratch = result["scratch_pad_update"]
    size_summary = [{"arm": arm, "role": role, "round": round_no, "section": name,
                     "n": len(values), "mean_characters": statistics.mean(values),
                     "min_characters": min(values), "max_characters": max(values)}
                    for (arm, role, round_no, name), values in sorted(sizes.items()) if round_no in (1, 15)]
    report = {"date": "2026-10-24", "time_zone": "Asia/Hong_Kong", "passed": not errors,
              "method": "Offline comparison of saved requests against each agent's preceding generated memory and scratchpad; no inference.",
              "limits": ["Routing correctness is not factual correctness or causal influence.",
                         "Selected examples are exploratory and are not a blinded intent classifier.",
                         "Character sizes count Unicode code points, not tokens.",
                         "No cross-agent secrecy guarantee is inferred from restoration checks."],
              "counts": dict(sorted(counts.items())), "errors": errors, "size_summary": size_summary,
              "script_sha256": digest(Path(__file__)), "records": records, "selected_examples": examples}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"artifact": relative(OUTPUT), "passed": not errors,
                      "counts": report["counts"], "errors": errors,
                      "size_summary": size_summary}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
