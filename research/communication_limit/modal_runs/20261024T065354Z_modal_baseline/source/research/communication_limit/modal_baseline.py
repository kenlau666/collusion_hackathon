"""Bounded baseline on the existing Modal endpoint; no deployment or credential logging."""

import argparse
from datetime import datetime,timezone
import fcntl
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid

from dotenv import dotenv_values
import httpx2 as httpx

from baseline import ModelWrapper,RunStopped,make_params,now,provenance,run_session,save_json,validate_answer
from modal_endpoint import EndpointConfig,probe

INPUT_REFERENCE_RATE=0.30/1_000_000
OUTPUT_REFERENCE_RATE=1.20/1_000_000
MAX_OUTPUT=4000
INFERENCE_GATE=threading.BoundedSemaphore(2)


class UsageLedger:
    """Limits requests and reference token estimates; actual billing mode is unverified."""
    def __init__(self,path,max_calls=288,reference_ceiling=19.94):
        self.path=Path(path)
        self.lock=threading.Lock()
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {
            "calls_started":0,"calls_completed":0,"calls_failed":0,"prompt_tokens":0,
            "completion_tokens":0,"reference_estimate_usd":0.0,"reference_reserved_usd":0.0,
            "reported_cost_usd":0.0,"calls_without_reported_cost":0,
            "billing_mode":"unverified; user authorized use of available credit",
            "reference_rates_usd_per_million":{"input":0.30,"output":1.20},
            "reference_is_not_verified_charge":True}
        self.max_calls,self.ceiling=max_calls,reference_ceiling
        self.stopped=bool(self.state["reference_reserved_usd"])

    def persist(self):
        self.state.update(updated_at=now(),max_calls=self.max_calls,reference_ceiling_usd=self.ceiling)
        save_json(self.path,self.state)

    def reserve(self,amount):
        with self.lock:
            if self.stopped or self.state["calls_started"]>=self.max_calls or self.state["reference_estimate_usd"]+self.state["reference_reserved_usd"]+amount>self.ceiling:
                raise RunStopped("Modal request/reference-cost gate closed")
            self.state["calls_started"]+=1
            self.state["reference_reserved_usd"]+=amount
            self.persist()

    def settle(self,reservation,usage,failed):
        with self.lock:
            remaining=self.state["reference_reserved_usd"]-reservation
            self.state["reference_reserved_usd"]=0.0 if abs(remaining)<1e-10 else max(remaining,0)
            if failed:
                self.state["calls_failed"]+=1
                self.stopped=True
            else:
                self.state["calls_completed"]+=1
            prompt=usage.get("prompt_tokens")
            completion=usage.get("completion_tokens")
            if isinstance(prompt,int) and isinstance(completion,int) and min(prompt,completion)>=0:
                self.state["prompt_tokens"]+=prompt
                self.state["completion_tokens"]+=completion
                estimate=prompt*INPUT_REFERENCE_RATE+completion*OUTPUT_REFERENCE_RATE
                self.state["reference_estimate_usd"]+=estimate
                if estimate>reservation:
                    self.stopped=True
            else:
                self.state["reference_estimate_usd"]+=reservation
                self.stopped=True
            cost=usage.get("cost")
            if isinstance(cost,(float,int)) and not isinstance(cost,bool) and math.isfinite(cost) and cost>=0:
                self.state["reported_cost_usd"]+=cost
            else:
                self.state["calls_without_reported_cost"]+=1
            self.persist()


class ModalClient(ModelWrapper):
    def __init__(self,agent_id,seller,seed,ledger,call_dir,transport,config,deadline,gate=None):
        super().__init__(config.model,temperature=0.7,max_tokens=MAX_OUTPUT)
        self.agent_id,self.seller,self.seed=agent_id,seller,seed
        self.ledger,self.call_dir,self.transport,self.config=ledger,Path(call_dir),transport,config
        self.deadline,self.round_num=deadline,0
        self.gate=gate or INFERENCE_GATE

    def generate(self,messages):
        if time.monotonic()>self.deadline:
            raise RunStopped("Modal batch wall-clock gate closed")
        payload={"model":self.model_name,"messages":messages,"temperature":0.7,"top_p":1.0,
                 "max_tokens":MAX_OUTPUT,"response_format":{"type":"json_object"},
                 "reasoning_effort":"none"}
        # Seed is deliberately absent: the endpoint does not advertise that parameter.
        input_bound=sum(len(m["content"].encode("utf-8"))+256 for m in messages)+256
        reserved=1.1*(input_bound*INPUT_REFERENCE_RATE+MAX_OUTPUT*OUTPUT_REFERENCE_RATE)+0.001
        event={"call_id":uuid.uuid4().hex,"agent_id":self.agent_id,"round":self.round_num,
               "backend":"modal","endpoint_base_url":self.config.base_url,
               "seed_forwarded":False,"request":payload,"started_at":now(),
               "reference_reservation_usd":reserved,"status":"prepared_not_dispatched"}
        path=self.call_dir/(event["call_id"]+".request.json")
        save_json(path,event)
        self.ledger.reserve(reserved)
        event["status"]="dispatch_pending"
        save_json(path,event)
        body,answer,usage=None,None,{}
        failed=True
        started=time.monotonic()
        try:
            with self.gate:
                response=self.transport.post(self.config.base_url+"/chat/completions",json=payload,
                    headers={**self.config.headers,"Modal-Routing-Affinity-Key":f"{self.call_dir.parent.name}-{self.agent_id}"})
            body=response.json()
            if isinstance(body.get("usage"),dict):
                usage=body["usage"]
            if response.status_code!=200 or body.get("error"):
                raise RunStopped(f"Modal inference HTTP {response.status_code}; inspect saved response")
            if body.get("model")!=self.model_name:
                raise RunStopped("Modal returned a different model ID")
            choice=body["choices"][0]
            if choice.get("finish_reason")!="stop":
                raise RunStopped(f"Incomplete generation: {choice.get('finish_reason')}")
            answer=choice["message"]["content"]
            validate_answer(answer,self.seller)
            failed=False
            event["status"]="success"
            return answer
        except Exception as exc:
            event.update(status="failed",error_type=type(exc).__name__,error=str(exc))
            raise RunStopped(f"Modal call failed for {self.agent_id}, round {self.round_num}") from exc
        finally:
            self.ledger.settle(reserved,usage,failed)
            event.update(response=body,answer=answer,finished_at=now(),duration_seconds=time.monotonic()-started,
                         actual_cost_usd=usage.get("cost"),
                         reference_token_estimate_usd=(usage["prompt_tokens"]*INPUT_REFERENCE_RATE+usage["completion_tokens"]*OUTPUT_REFERENCE_RATE)
                         if isinstance(usage.get("prompt_tokens"),int) and isinstance(usage.get("completion_tokens"),int) else None)
            save_json(self.call_dir/(event["call_id"]+".result.json"),event)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--rounds",type=int,default=3)
    parser.add_argument("--seeds",type=int,nargs="+",default=[999])
    parser.add_argument("--label",default="modal_smoke")
    parser.add_argument("--concurrency",type=int,default=2)
    args=parser.parse_args()
    if args.rounds<1 or len(set(args.seeds))!=len(args.seeds) or not 1<=args.concurrency<=6:
        parser.error("Require positive rounds, distinct seeds, and concurrency from 1 to 6")
    root=Path(__file__).resolve().parents[2]
    values=dict(dotenv_values(root/"compute.env"));values.update(os.environ)
    config=EndpointConfig.from_values(values)
    if not config.model:
        parser.error("Discover and configure the exact MODAL_ENDPOINT_MODEL first")
    if not args.live:
        print(json.dumps({"mode":"plan_only","model":config.model,"calls":6*args.rounds*len(args.seeds),
                          "reasoning_effort":"none","seed_forwarded":False},indent=2))
        return
    output=Path(__file__).parent/"modal_runs";output.mkdir(exist_ok=True)
    with (output/"ledger.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ledger=UsageLedger(output/"usage_ledger.json")
        batch=output/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+args.label)
        batch.mkdir(exist_ok=False)
        provenance(batch)
        models_path=Path(__file__).parent/"modal_models.json"
        if models_path.exists():
            save_json(batch/"advertised_model_capabilities.json",json.loads(models_path.read_text()))
        save_json(batch/"plan.json",{"model":config.model,"endpoint":config.base_url,
            "params":[make_params(args.rounds,s,config.model).model_dump() for s in args.seeds],
            "seed_forwarded":False,"reasoning_effort":"none","max_output_tokens":MAX_OUTPUT,
            "request_cap_total":288,"batch_time_cap_seconds":1800,
            "api_concurrency":args.concurrency,
            "billing_mode_unverified":True,"user_authorized_credit_use":True,
            "reference_rates_are_not_verified_charges":True})
        deadline=time.monotonic()+1800
        gate=threading.BoundedSemaphore(args.concurrency)
        with httpx.Client(timeout=120,follow_redirects=False) as transport:
            discovery=probe(config,transport)
            save_json(batch/"endpoint_preflight.json",discovery)
            if discovery.get("http_status")!=200 or not discovery.get("configured_model_listed"):
                raise RunStopped("Modal authentication/model discovery check failed")
            def builder(agent_id,seller,seed,call_dir):
                return ModalClient(agent_id,seller,seed,ledger,call_dir,transport,config,deadline,gate)
            for seed in args.seeds:
                run_session(make_params(args.rounds,seed,config.model),batch/f"seed_{seed}",builder)
        print(json.dumps({"batch":str(batch),"usage":ledger.state}),flush=True)


if __name__=="__main__":
    main()
