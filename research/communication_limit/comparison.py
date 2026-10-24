"""Fixed exploratory B/C/D comparison on the existing Modal endpoint.

One dispatcher interleaves sessions; --live is required for inference.
"""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import threading
import time

from dotenv import dotenv_values
import httpx2 as httpx

from audit_session import audit
from baseline import REPO, RunStopped, make_params, now, provenance, run_session, save_json
from modal_baseline import ModalClient, UsageLedger
from modal_endpoint import EndpointConfig, probe

ARMS=("prompt_limit", "runtime_limit", "no_chat")
MODEL="deepseek-ai/DeepSeek-V4.1-Flash"
SEEDS=(0,1,2)
ROUNDS=15
LIMIT=5
MAX_CALLS=810
CONCURRENCY=6
WALL_SECONDS=2700
BASELINE=Path(__file__).parent/"modal_runs/20261024T065354Z_modal_baseline"


def condition_params(arm,seed,model=MODEL,rounds=ROUNDS):
    if arm not in ARMS:
        raise ValueError("Unknown condition")
    params=make_params(rounds,seed,model)
    params.tag=f"{arm}_seed_{seed}"
    params.seller_comms_enabled=arm!="no_chat"
    params.seller_prompt_message_limit=LIMIT if arm!="no_chat" else None
    params.seller_runtime_message_limit=LIMIT if arm=="runtime_limit" else None
    return params


def schedule():
    # One randomized base order, cyclic rotations: every arm occupies each
    # within-seed position once. This does not randomize the historical A arm.
    order=list(ARMS)
    random.Random(20261024).shuffle(order)
    return [{"arm":order[(position+block)%3],"seed":seed}
            for block,seed in enumerate(SEEDS) for position in range(3)]


def validate_historical_match():
    ignored={"seller_comms_enabled","seller_prompt_message_limit",
             "seller_runtime_message_limit","tag"}
    for seed in SEEDS:
        previous=json.loads((BASELINE/f"seed_{seed}/session.json").read_text())
        if previous["status"]!="complete":
            raise RunStopped("Historical baseline incomplete")
        for arm in ARMS:
            params=condition_params(arm,seed).model_dump()
            if {k:v for k,v in params.items() if k not in ignored}!={k:v for k,v in previous["params"].items() if k not in ignored}:
                raise RunStopped("Non-treatment settings differ from historical baseline")


def compliance(session):
    metadata=json.loads((session/"session.json").read_text())
    rounds=json.loads((session/"rounds.json").read_text())
    events=[e for r in rounds for e in r["seller_message_events"].values()]
    raw=[e["raw_length"] for e in events if e["raw_length"] is not None]
    delivered=[e["delivered_length"] for e in events if e["delivered_length"] is not None]
    return {"seller_turns":len(events),"generated_message_count":len(raw),
            "delivered_message_count":len(delivered),"raw_lengths":raw,
            "delivered_lengths":delivered,"raw_over_5":sum(x>LIMIT for x in raw),
            "delivered_over_5":sum(x>LIMIT for x in delivered),
            "truncated_count":sum(e["status"]=="truncated" for e in events),
            "absent_count":sum(e["status"]=="absent" for e in events),
            "empty_count":sum(e["status"]=="empty" for e in events),
            "disabled_count":sum(e["status"]=="disabled" for e in events),
            "target_limit_applies":metadata["params"]["seller_prompt_message_limit"] is not None,
            "note":"Final-round messages have no subsequent in-session recipient."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    validate_historical_match()
    plan={"created_at":now(),"kind":"exploratory fixed B/C/D comparison",
          "model":MODEL,"limit_unicode_code_points":LIMIT,"rounds":ROUNDS,
          "seeds":list(SEEDS),"schedule":schedule(),"historical_baseline":str(BASELINE),
          "params":{arm:[condition_params(arm,s).model_dump() for s in SEEDS] for arm in ARMS},
          "calls_maximum":MAX_CALLS,"global_api_concurrency":CONCURRENCY,
          "batch_wall_cap_seconds":WALL_SECONDS,"primary_endpoint":"total buyer surplus per session",
          "sampling":{"temperature":0.7,"top_p":1.0,"max_tokens":4000,
                      "response_format":{"type":"json_object"},"reasoning_effort":"none"},
          "seed_forwarded":False,"no_retries_or_fallbacks":True,
          "billing_mode_unverified":True,"reference_is_not_verified_charge":True,
          "reference_ceiling_usd":19.60,
          "scope":"Three new conditions only; no new defense, model, or mechanism probe."}
    if not args.live:
        print(json.dumps(plan,indent=2))
        return
    values=dict(dotenv_values(REPO/"compute.env"));values.update(os.environ)
    config=EndpointConfig.from_values(values)
    if config.model!=MODEL:
        raise RunStopped("Configured model differs from completed Modal baseline")
    historical_plan=json.loads((BASELINE/"plan.json").read_text())
    if config.base_url!=historical_plan["endpoint"]:
        raise RunStopped("Configured endpoint differs from completed Modal baseline")
    directory=Path(__file__).parent/"comparison_runs"
    directory.mkdir(exist_ok=True)
    # Reuse the baseline endpoint lock as well as a separate comparison ledger.
    # Competing comparison/baseline processes fail before any request dispatch.
    with (Path(__file__).parent/"modal_runs/ledger.lock").open("a") as endpoint_lock:
        fcntl.flock(endpoint_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=UsageLedger(directory/"usage_ledger.json",max_calls=MAX_CALLS,reference_ceiling=19.60)
        if ledger.state["calls_started"]:
            raise RunStopped("Comparison already attempted; no automatic rerun or selective replacement")
        ledger.persist()
        batch=directory/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_comparison")
        batch.mkdir(exist_ok=False)
        provenance(batch)
        protocol=REPO/"research/communication_limit/docs/COMPARISON_PROTOCOL.md"
        shutil.copyfile(protocol,batch/"source/COMPARISON_PROTOCOL.md")
        saved_provenance=json.loads((batch/"provenance.json").read_text())
        saved_provenance["sha256"]["COMPARISON_PROTOCOL.md"]=hashlib.sha256(protocol.read_bytes()).hexdigest()
        save_json(batch/"provenance.json",saved_provenance)
        save_json(batch/"plan.json",plan)
        capabilities=Path(__file__).parent/"modal_models.json"
        save_json(batch/"advertised_model_capabilities.json",json.loads(capabilities.read_text()))
        prior={"modal":json.loads((Path(__file__).parent/"modal_runs/usage_ledger.json").read_text()),
               "openrouter":json.loads((Path(__file__).parent/"runs/ledger.json").read_text())}
        save_json(batch/"prior_usage.json",prior)
        results={"status":"running","started_at":now(),"sessions":[],"plan":plan}
        save_json(batch/"aggregate_summary.json",results)
        print(json.dumps({"batch":str(batch),"schedule":schedule()}),flush=True)
        deadline=time.monotonic()+WALL_SECONDS
        gate=threading.BoundedSemaphore(CONCURRENCY)
        try:
            with httpx.Client(timeout=120,follow_redirects=False) as transport:
                discovery=probe(config,transport)
                save_json(batch/"endpoint_preflight.json",discovery)
                if discovery.get("http_status")!=200 or not discovery.get("configured_model_listed"):
                    raise RunStopped("Modal authentication/model discovery failed")
                def builder(agent_id,seller,seed,call_dir):
                    return ModalClient(agent_id,seller,seed,ledger,call_dir,transport,config,deadline,gate)
                for item in schedule():
                    arm,seed=item["arm"],item["seed"]
                    session=batch/arm/f"seed_{seed}"
                    print(json.dumps({"starting_condition":arm,"seed":seed}),flush=True)
                    summary=run_session(condition_params(arm,seed),session,builder)
                    report=audit(session)
                    if not report["passed"]:
                        raise RunStopped("Saved-context/action/delivery audit failed; inspect audit.json")
                    lengths=compliance(session)
                    save_json(session/"compliance.json",lengths)
                    results["sessions"].append({**item,"path":str(session),"summary":summary,
                                                "audit_passed":True,"compliance":lengths})
                    save_json(batch/"aggregate_summary.json",results)
                    print(json.dumps({"completed_condition":arm,"seed":seed,"audit_passed":True,
                                      "summary":summary,"raw_over_5":lengths["raw_over_5"],
                                      "delivered_over_5":lengths["delivered_over_5"]}),flush=True)
            results["status"]="complete"
        except BaseException as exc:
            results.update(status="failed",error_type=type(exc).__name__,error=str(exc))
            raise
        finally:
            results.update(finished_at=now(),usage=ledger.state)
            save_json(batch/"aggregate_summary.json",results)
            print(json.dumps({"status":results["status"],"batch":str(batch),"usage":ledger.state}),flush=True)


if __name__=="__main__":
    main()
