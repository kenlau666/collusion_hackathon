"""Check saved API contexts, delivery, actions and cost without making model calls."""

import argparse
import ast
import json
from pathlib import Path

from baseline import economic_summary, save_json, validate_answer


def audit(session, allow_partial=False):
    session=Path(session)
    metadata=json.loads((session/"session.json").read_text())
    rounds=json.loads((session/"rounds.json").read_text())
    results=[json.loads(p.read_text()) for p in (session/"calls").glob("*.result.json")]
    seller_ids={a["id"] for a in metadata["sellers"]}
    buyer_ids={a["id"] for a in metadata["buyers"]}
    errors=[]
    def check(ok,description):
        if not ok:
            errors.append(description)
    if not allow_partial:
        check(metadata["status"]=="complete","session incomplete")
        check(len(results)==6*metadata["params"]["rounds"],"unexpected call count")
        check(len(rounds)==metadata["params"]["rounds"],"unexpected round count")
    else:
        check(len(results)>=6*len(rounds),"too few calls for completed rounds")
    context_checks=0
    for index,round_data in enumerate(rounds):
        number=round_data["round_number"]
        calls=[r for r in results if r["round"]==number]
        check({r["agent_id"] for r in calls}==seller_ids|buyer_ids,f"round {number} agent coverage")
        books=[]
        for call in calls:
            agent=call["agent_id"]
            seller=agent in seller_ids
            check(call["status"]=="success",f"{number}/{agent}: call failed")
            check(call["response"].get("provider")=="OpenAI",f"{number}/{agent}: provider")
            check(call["actual_cost_usd"] is not None,f"{number}/{agent}: missing cost")
            check(call["request"]["provider"]["only"]==["openai"],f"{number}/{agent}: provider request")
            envelope=call["request"]["messages"]
            check(len(envelope)==1 and envelope[0]["role"]=="user",f"{number}/{agent}: envelope")
            content=envelope[0]["content"]
            bid_text=content.split("## Current Status of Bid Queue\n\n",1)[1].split("\n\n## Current Status of Ask Queue",1)[0].strip()
            ask_text=content.split("## Current Status of Ask Queue\n\n",1)[1].split("\n\n## Asks/Bids",1)[0].strip()
            books.append((ast.literal_eval(bid_text),ast.literal_eval(ask_text)))
            answer=validate_answer(call["answer"],seller)
            action=answer["ask" if seller else "bid"]
            actual_actions=round_data["seller_asks" if seller else "buyer_bids"]
            if action=="null":
                check(agent not in actual_actions,f"{number}/{agent}: withdrawn action")
            else:
                check(actual_actions.get(agent)==action,f"{number}/{agent}: parsed action mismatch")
            if seller:
                event=round_data["seller_message_events"][agent]
                check(event["raw_message"]==answer.get("message_to_sellers"),f"{number}/{agent}: raw message")
                raw=event["raw_message"]
                delivered=round_data["seller_messages"].get(agent)
                check(delivered==(raw[:500] if raw else None),f"{number}/{agent}: cap transformation")
                section=content.split("# Messages Received from Other Sellers (Previous Hour)",1)[1]
                section=section.split("# Current Strategy Scratchpad",1)[0].split("# Output Format",1)[0]
                if index:
                    for sender,message in rounds[index-1]["seller_messages"].items():
                        check(f"- From {sender}: {message}" in section,f"{number}/{agent}: missing delivered message from {sender}")
                        context_checks+=1
                else:
                    check("No messages received" in section,f"{number}/{agent}: first-round message section")
        check(all(book==books[0] for book in books),f"round {number}: inconsistent starting public queues")
    computed=economic_summary(rounds,{a["id"]:a["cost"] for a in metadata["sellers"]},
                              {a["id"]:a["value"] for a in metadata["buyers"]})
    saved=json.loads((session/"summary.json").read_text())
    check(all(saved[k]==v for k,v in computed.items()),"summary differs from recomputed metrics")
    report={"passed":not errors,"errors":errors,"calls":len(results),"rounds":len(rounds),
            "complete_session":metadata["status"]=="complete",
            "partial_round_successful_calls_excluded_from_outcomes":sum(
                r["round"]>len(rounds) and r["status"]=="success" for r in results),
            "failed_calls":sum(r["status"]!="success" for r in results),
            "recipient_message_checks":context_checks,
            "total_cost_usd":sum(r["actual_cost_usd"] or 0 for r in results),
            "summary":computed,
            "claim_limit":"software/context audit, not a coordination detector"}
    save_json(session/"audit.json",report)
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session",type=Path)
    parser.add_argument("--allow-partial",action="store_true")
    args=parser.parse_args()
    report=audit(args.session,allow_partial=args.allow_partial)
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report["passed"] else 1)
