"""Summarize complete audited sessions; no inference or hypothesis tests."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from jinja2 import Environment

from baseline import REPO, now, save_json
from comparison import ARMS, BASELINE, SEEDS, compliance

LABELS={"ordinary_chat":"Ordinary chat\n(historical)","prompt_limit":"Prompt\nlimit",
        "runtime_limit":"Prompt + code\nlimit","no_chat":"No seller\nchat"}
ORDER=("ordinary_chat",)+ARMS
METRICS=("buyer_surplus","num_trades","seller_profit","total_welfare","average_trade_price")


def first_inputs(session):
    result={}
    for path in (session/"calls").glob("*.result.json"):
        event=json.loads(path.read_text())
        if event["round"]==1:
            result[event["agent_id"]]=event["request"]
    return result


def describe(values):
    available=[value for value in values if value is not None]
    return {"values":values,"n":len(available),
            "mean":statistics.mean(available) if available else None,
            "sample_sd":statistics.stdev(available) if len(available)>1 else None}


def message_section(content):
    return content.split("# Messages Received from Other Sellers (Previous Hour)",1)[1].split(
        "# Current Strategy Scratchpad",1)[0].split("# Output Format",1)[0]


def exact_section_matches(content,previous,template,params):
    # Retain every whitespace code point. The runtime audit normalizes outer
    # section whitespace, so this supplementary audit strengthens that check.
    rendered=template.render(seller_comms_enabled=True,seller_messages=previous,
        seller_prompt_message_limit=params.get("seller_prompt_message_limit"),
        max_message_length=params["max_message_length"],
        scratch_pad="placeholder" if "# Current Strategy Scratchpad" in content else None)
    return message_section(content)==message_section(rendered)


def audit_exact_sections(session,template_path):
    metadata=json.loads((session/"session.json").read_text())
    rounds=json.loads((session/"rounds.json").read_text())
    params=metadata["params"]
    sellers={s["id"] for s in metadata["sellers"]}
    template=Environment().from_string(template_path.read_text())
    count=0
    for path in (session/"calls").glob("*.result.json"):
        event=json.loads(path.read_text())
        if event["agent_id"] not in sellers:
            continue
        content=event["request"]["messages"][0]["content"]
        if params["seller_comms_enabled"]:
            previous=rounds[event["round"]-2]["seller_messages"] if event["round"]>1 else {}
            if not exact_section_matches(content,previous,template,params):
                raise ValueError(f"Whitespace-exact section mismatch: {session.name}/{event['agent_id']}/{event['round']}")
        elif "# Messages Received from Other Sellers (Previous Hour)" in content:
            raise ValueError("No-chat input contains chat section")
        count+=1
    return {"passed":True,"seller_inputs_checked":count,
            "chat_sections_checked":count if params["seller_comms_enabled"] else 0,
            "whitespace_normalized":False}


def analyze(batch):
    provenance=json.loads((batch/"provenance.json").read_text())
    snapshot_matches=all(hashlib.sha256((batch/"source"/relative).read_bytes()).hexdigest()==digest
                         for relative,digest in provenance["sha256"].items())
    if not snapshot_matches:
        raise ValueError("Frozen inference snapshot hash mismatch")
    aggregate=json.loads((batch/"aggregate_summary.json").read_text())
    if aggregate["status"]!="complete" or len(aggregate["sessions"])!=9:
        raise ValueError("All nine comparison sessions must complete before final analysis")
    sessions={}
    for arm in ORDER:
        root=BASELINE if arm=="ordinary_chat" else batch/arm
        sessions[arm]=[]
        for seed in SEEDS:
            session=root/f"seed_{seed}"
            metadata=json.loads((session/"session.json").read_text())
            audit=json.loads((session/"audit.json").read_text())
            if metadata["status"]!="complete" or not audit["passed"]:
                raise ValueError("Analysis requires complete audited sessions")
            summary=json.loads((session/"summary.json").read_text())
            rounds=json.loads((session/"rounds.json").read_text())
            template_root=BASELINE if arm=="ordinary_chat" else batch
            template_path=template_root/"source/llm-agent-collusion/src/continuous_double_auction/prompt_templates/seller_prompt_base.jinja2"
            exact_audit=audit_exact_sections(session,template_path)
            sessions[arm].append({"seed":seed,"path":str(session),"summary":summary,
                "compliance":compliance(session),"audit":audit,"whitespace_exact_context_audit":exact_audit,
                "first_trade_round":next((r["round_number"] for r in rounds if r["trades"]),None)})
    initial_matches={}
    first_input_matches={}
    for seed in SEEDS:
        reference=json.loads((BASELINE/f"seed_{seed}/session.json").read_text())
        fields=("buyers","sellers","initial_asks","initial_bids")
        initial_matches[str(seed)]={}
        for arm in ARMS:
            other=json.loads((batch/arm/f"seed_{seed}/session.json").read_text())
            initial_matches[str(seed)][arm]=all(other[key]==reference[key] for key in fields)
        first_input_matches[str(seed)]=first_inputs(batch/"prompt_limit"/f"seed_{seed}")==first_inputs(batch/"runtime_limit"/f"seed_{seed}")
    if not all(all(x.values()) for x in initial_matches.values()) or not all(first_input_matches.values()):
        raise ValueError("Matched initial conditions or B/C first-round inputs differ")
    descriptions={arm:{metric:describe([s["summary"][metric] for s in sessions[arm]]) for metric in METRICS}
                  for arm in ORDER}
    compliance_totals={}
    for arm in ORDER:
        compliance_totals[arm]={key:sum(s["compliance"][key] for s in sessions[arm]) for key in
            ("seller_turns","generated_message_count","delivered_message_count","raw_over_5",
             "delivered_over_5","truncated_count","absent_count","empty_count","disabled_count")}
    contrasts={}
    for left,right in (("runtime_limit","prompt_limit"),("no_chat","runtime_limit")):
        contrasts[f"{left}_minus_{right}"]={metric:describe([
            sessions[left][i]["summary"][metric]-sessions[right][i]["summary"][metric]
            if sessions[left][i]["summary"][metric] is not None and sessions[right][i]["summary"][metric] is not None else None
            for i in range(3)]) for metric in METRICS}
    report={"created_at":now(),"model":"deepseek-ai/DeepSeek-V4.1-Flash",
            "sessions":sessions,"descriptive_statistics":descriptions,
            "compliance_totals":compliance_totals,"contrasts":contrasts,
            "initial_population_orders_match_A":initial_matches,
            "actual_B_C_first_round_requests_identical":first_input_matches,
            "comparison_usage":aggregate["usage"],
            "claim_limit":"Exploratory n=3 sessions/arm; no significance/equivalence or causal-collusion claim; A historical; local seeds match initialization, not API randomness."}
    save_json(batch/"comparison_analysis.json",report)
    figure,axes=plt.subplots(1,3,figsize=(13.8,4.8),layout="constrained")
    colors=("#64748b","#2563eb","#0d9488","#d97706")
    for axis,metric,title in zip(axes,("buyer_surplus","num_trades","seller_profit"),
                                ("Buyer surplus","Completed trades","Seller profit")):
        for index,arm in enumerate(ORDER):
            values=descriptions[arm][metric]["values"]
            for seed,value in enumerate(values):
                axis.scatter(index+(seed-1)*0.13,value,color=colors[index],s=58,
                             marker=("o","^","s")[seed],zorder=3,edgecolor="white",linewidth=0.6)
            axis.hlines(descriptions[arm][metric]["mean"],index-0.25,index+0.25,color=colors[index],linewidth=2.6,zorder=2)
        axis.set_xticks(range(4),[LABELS[a] for a in ORDER],fontsize=9)
        axis.set_title(title,fontsize=12,fontweight="bold")
        minimum=min(value for arm in ORDER for value in descriptions[arm][metric]["values"] if value is not None)
        axis.set_ylim(bottom=min(0,minimum*1.1))
        axis.set_ylabel("Trades per session" if metric=="num_trades" else "Simulation dollars per session")
        axis.spines[["top","right"]].set_visible(False)
        axis.grid(axis="y",alpha=0.18)
        if metric=="num_trades":
            axis.set_ylim(0,47)
            axis.axhline(45,color="#94a3b8",linestyle=":",linewidth=1)
    figure.suptitle("Communication restrictions: exploratory market outcomes\n"
                    "DeepSeek-V4.1-Flash · 3 sessions per condition · 15 rounds · points = sessions, bars = means",
                    fontsize=13,fontweight="bold")
    figure.savefig(batch/"comparison_overview.png",dpi=180,facecolor="white")
    figure.savefig(batch/"comparison_overview.svg",facecolor="white")
    plt.close(figure)
    sources=batch/"analysis_source"
    sources.mkdir(exist_ok=True)
    hashes={}
    paths=[Path(__file__),Path(__file__).with_name("audit_session.py"),REPO/"COMPARISON_PROTOCOL.md"]
    paths+=list((Path(__file__).parent/"conditions").glob("*_results.md"))
    if (REPO/"COMPARISON_RESULTS.md").exists():
        paths.append(REPO/"COMPARISON_RESULTS.md")
    for source in paths:
        target=sources/source.name
        shutil.copyfile(source,target)
        hashes[str(source.relative_to(REPO))]=hashlib.sha256(source.read_bytes()).hexdigest()
    save_json(batch/"analysis_manifest.json",{"created_at":now(),"sha256":hashes,
              "inference_snapshot_not_modified":snapshot_matches})
    print(json.dumps({"descriptive_statistics":descriptions,"compliance_totals":compliance_totals,
                      "first_inputs_equal":first_input_matches,"contrasts":contrasts},indent=2))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch",type=Path)
    analyze(parser.parse_args().batch)
