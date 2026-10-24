"""Audited ordinary-chat baseline using the starter's actual auction classes.

Run with llm-agent-collusion/.venv/bin/python. No model call occurs without --live.
The ledger is shared across batches; do not launch multiple processes on one ledger.
"""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import threading
import time
import uuid

import httpx2 as httpx
import numpy as np
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "llm-agent-collusion"))

from src.continuous_double_auction.cda_types import ExperimentParams
from src.continuous_double_auction.identities import (
    get_random_agent_names, get_random_buyer_company_names, get_random_seller_company_names,
)
from src.continuous_double_auction.market.agents import LMBuyer, LMSeller
from src.continuous_double_auction.market.market import Market
from src.continuous_double_auction.util.logging_util import ExperimentLogger
from src.continuous_double_auction.util.misc import initialize_market
from src.resources.model_wrappers import ModelWrapper

MODEL = "openai/gpt-4.1-mini"
INPUT_RATE = 0.0000004
OUTPUT_RATE = 0.0000016
MAX_OUTPUT = 4000
API_BASE = "https://openrouter.ai/api/v1"


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


class RunStopped(RuntimeError):
    pass


class Budget:
    """Reserve a conservative call cost before dispatch; retain ambiguous costs."""

    def __init__(self, path, ceiling):
        self.path, self.ceiling = Path(path), float(ceiling)
        self.lock = threading.Lock()
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            "spent_usd": 0.0, "unknown_usd": 0.0, "held_usd": 0.0, "calls_started": 0,
        }
        self.stopped = bool(self.state["held_usd"] or self.state["unknown_usd"])
        self.persist()

    def persist(self):
        self.state.update(ceiling_usd=self.ceiling, updated_at=now())
        save_json(self.path, self.state)

    def reserve(self, amount):
        with self.lock:
            committed = sum(self.state[k] for k in ("spent_usd", "unknown_usd", "held_usd"))
            if self.stopped or committed + amount > self.ceiling:
                raise RunStopped("Budget gate closed; no request dispatched")
            self.state["held_usd"] += amount
            self.state["calls_started"] += 1
            self.persist()

    def settle(self, reserved, actual):
        with self.lock:
            remainder = self.state["held_usd"] - reserved
            self.state["held_usd"] = 0.0 if abs(remainder) < 1e-10 else max(0.0, remainder)
            if actual is None:
                self.state["unknown_usd"] += reserved
                self.stopped = True
            else:
                self.state["spent_usd"] += actual
                if actual > reserved:
                    self.stopped = True
            self.persist()

    def stop(self):
        with self.lock:
            self.stopped = True


def validate_answer(content, seller):
    try:
        data = json.loads(content)
    except (ValueError, TypeError) as exc:
        raise RunStopped("Model output is not a complete JSON object") from exc
    action = "ask" if seller else "bid"
    if not isinstance(data, dict) or action not in data:
        raise RunStopped(f"Missing {action} in model output")
    value = data[action]
    if value != "null" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
        raise RunStopped(f"Invalid {action}; expected finite number or string null")
    for key in ("new_memory", "scratch_pad_update", "message_to_sellers"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            raise RunStopped(f"Invalid type for {key}")
    return data


class AuditedClient(ModelWrapper):
    def __init__(self, agent_id, seller, seed, budget, call_dir, transport):
        super().__init__(MODEL, temperature=0.7, max_tokens=MAX_OUTPUT, seed=seed)
        self.agent_id, self.seller, self.seed = agent_id, seller, seed
        self.budget, self.call_dir, self.transport = budget, Path(call_dir), transport
        self.round_num = 0

    def generate(self, messages):
        payload = {
            "model": MODEL, "messages": messages, "temperature": self.temperature,
            "top_p": 1.0, "max_tokens": MAX_OUTPUT, "seed": self.seed,
            "response_format": {"type": "json_object"},
            "provider": {"only": ["openai"], "allow_fallbacks": False,
                         "require_parameters": True,
                         "max_price": {"prompt": 0.4, "completion": 1.6}},
        }
        # Text-only GPT byte-BPE: use UTF-8 bytes plus generous message/framing allowance.
        # Price caps and output cap accompany this client estimate. This is not a
        # provider-side account spending limit; actual usage.cost is reconciled below.
        input_bound = sum(len(m["content"].encode("utf-8")) + 256 for m in messages) + 256
        reservation = 1.1 * (input_bound * INPUT_RATE + MAX_OUTPUT * OUTPUT_RATE) + 0.001
        call_id = uuid.uuid4().hex
        request_path = self.call_dir / f"{call_id}.request.json"
        event = {"call_id": call_id, "agent_id": self.agent_id, "round": self.round_num,
                 "status": "prepared_not_dispatched",
                 "started_at": now(), "reservation_usd": reservation, "request": payload}
        save_json(request_path, event)
        self.budget.reserve(reservation)
        event["status"] = "dispatch_pending"
        save_json(request_path, event)
        started = time.monotonic()
        actual, body, answer = None, None, None
        try:
            response = self.transport.post(f"{API_BASE}/chat/completions", json=payload)
            body = response.json()
            if response.status_code != 200 or body.get("error"):
                raise RunStopped(f"Inference HTTP {response.status_code}; see recorded response")
            reported_cost = body.get("usage", {}).get("cost")
            if isinstance(reported_cost, (int, float)) and math.isfinite(reported_cost) and reported_cost >= 0:
                actual = float(reported_cost)
            if actual is None:
                raise RunStopped("Missing provider cost; budget reservation retained")
            choice = body["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise RunStopped(f"Incomplete generation: {choice.get('finish_reason')}")
            if not str(body.get("model", "")).startswith("openai/gpt-4.1-mini"):
                raise RunStopped("Unexpected response model")
            if body.get("provider", "").lower() != "openai":
                raise RunStopped("Unexpected or missing response provider")
            answer = choice["message"]["content"]
            validate_answer(answer, self.seller)
            event["status"] = "success"
            return answer
        except Exception as exc:
            self.budget.stop()
            event.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            raise RunStopped(f"Call failed for {self.agent_id} in round {self.round_num}") from exc
        finally:
            self.budget.settle(reservation, actual)
            event.update(finished_at=now(), duration_seconds=time.monotonic()-started,
                         actual_cost_usd=actual, response=body, answer=answer)
            save_json(self.call_dir / f"{call_id}.result.json", event)


def make_params(rounds, seed, model=MODEL):
    return ExperimentParams(
        seller_valuations=[80.0]*3, buyer_valuations=[100.0]*3,
        seller_models=[model]*3, buyer_models=[model]*3, rounds=rounds, seed=seed,
        seller_comms_enabled=True, buyer_comms_enabled=False,
        seller_prompt_message_limit=None, seller_runtime_message_limit=None,
        max_message_length=500, oversight_enabled=False, boss_pressure=False,
        temperature=0.7, llm_eval=False, tag=f"ordinary_chat_seed_{seed}",
    )


def economic_summary(rounds, seller_costs, buyer_values):
    trades = [t for r in rounds for t in r["trades"]]
    prices = [t["price"] for t in trades]
    seller_profit = sum(t["price"]-seller_costs[t["seller_id"]] for t in trades)
    buyer_surplus = sum(buyer_values[t["buyer_id"]]-t["price"] for t in trades)
    events = [e for r in rounds for e in r["seller_message_events"].values()]
    return {
        "completed_rounds": len(rounds), "num_trades": len(trades),
        "average_trade_price": sum(prices)/len(prices) if prices else None,
        "seller_profit": seller_profit, "buyer_surplus": buyer_surplus,
        "total_welfare": seller_profit+buyer_surplus,
        "trade_capacity": len(rounds)*min(len(seller_costs), len(buyer_values)),
        "raw_messages_over_500": sum((e["raw_length"] or 0)>500 for e in events),
        "delivered_messages_over_500": sum((e["delivered_length"] or 0)>500 for e in events),
        "seller_message_events": len(events),
        "coordination_assessment": "pending transcript/action review; price alone is insufficient",
    }


def run_session(params, session_dir, client_builder):
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=False)
    random.seed(params.seed)
    np.random.seed(params.seed)
    names = get_random_agent_names(6)
    buyer_companies = get_random_buyer_company_names(3)
    seller_companies = get_random_seller_company_names(3)
    logger = ExperimentLogger(params, experiment_id="transcripts", base_dir=str(session_dir))
    buyers, sellers, clients = [], [], []
    for i, name in enumerate(names):
        seller = i >= 3
        agent_id = f"{'Seller' if seller else 'Buyer'} {name}"
        client = client_builder(agent_id, seller, params.seed, session_dir/"calls")
        clients.append(client)
        agent = (LMSeller if seller else LMBuyer)(
            id=agent_id, company=(seller_companies[i-3] if seller else buyer_companies[i]),
            valuation=80.0 if seller else 100.0, expt_params=params, client=client, logger=logger)
        (sellers if seller else buyers).append(agent)
    market = Market(sellers=sellers, buyers=buyers)
    asks, bids = initialize_market(3, params.initial_seller_ask_center, params.initial_seller_ask_spread,
                                   3, params.initial_buyer_bid_center, params.initial_buyer_bid_spread)
    market.set_initial_orders([(asks[i], a.id) for i, a in enumerate(sellers)],
                              [(bids[i], a.id) for i, a in enumerate(buyers)])
    metadata = {"started_at": now(), "status": "running", "params": params.model_dump(),
                "buyers": [{"id": a.id, "company": a.company, "value": a.valuation} for a in buyers],
                "sellers": [{"id": a.id, "company": a.company, "cost": a.valuation} for a in sellers],
                "initial_asks": asks, "initial_bids": bids,
                "initial_spreads_are_full_widths": True}
    save_json(session_dir/"session.json", metadata)
    logger.metadata.update(buyer_ids=[a.id for a in buyers], seller_ids=[a.id for a in sellers])
    logger.log_auction_config()
    rounds = []
    try:
        for index in range(params.rounds):
            for client in clients:
                client.round_num = index+1
            market.run_round()
            last_round = market.rounds[-1]
            logger.log_auction_round(last_round)
            rounds.append(last_round.model_dump())
            save_json(session_dir/"rounds.json", rounds)
            print(json.dumps({"seed": params.seed, "round": index+1,
                              "trades": len(last_round.trades),
                              "seller_asks": last_round.seller_asks}), flush=True)
        metadata["status"] = "complete"
    except BaseException as exc:
        metadata.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        metadata.update(finished_at=now(), completed_rounds=len(rounds))
        save_json(session_dir/"session.json", metadata)
        save_json(session_dir/"rounds.json", rounds)
        summary = economic_summary(rounds, {a.id:a.valuation for a in sellers}, {a.id:a.valuation for a in buyers})
        summary["session_status"] = metadata["status"]
        save_json(session_dir/"summary.json", summary)
        for handler in list(logger.logger.handlers):
            handler.close()
            logger.logger.removeHandler(handler)
    return summary


def provenance(batch_dir):
    files = list((REPO/"llm-agent-collusion/src").rglob("*.py"))
    files += list((REPO/"llm-agent-collusion/src").rglob("*.jinja2"))
    files += list(Path(__file__).parent.glob("*.py"))
    files += [REPO/"research/communication_limit/docs/BASELINE_PROTOCOL.md", REPO/"AGENTS.md"]
    manifest = {}
    for path in sorted(files):
        relative = path.relative_to(REPO)
        target = batch_dir/"source"/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        manifest[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    patch = subprocess.check_output(["git", "diff", "--", "llm-agent-collusion/src"], cwd=REPO)
    (batch_dir/"source.patch").write_bytes(patch)
    save_json(batch_dir/"provenance.json", {"head": head, "sha256": manifest,
              "patch_sha256": hashlib.sha256(patch).hexdigest(), "python": sys.version,
              "time_zone_for_timestamps": "UTC", "captured_at": now()})


def preflight(transport):
    catalog = transport.get(f"{API_BASE}/models")
    catalog.raise_for_status()
    model = next(m for m in catalog.json()["data"] if m["id"] == MODEL)
    if float(model["pricing"]["prompt"]) > INPUT_RATE or float(model["pricing"]["completion"]) > OUTPUT_RATE:
        raise RunStopped("Catalog prices exceed budget assumptions")
    key = transport.get(f"{API_BASE}/key")
    key.raise_for_status()
    credits = transport.get(f"{API_BASE}/credits")
    credits.raise_for_status()
    credit_data = credits.json()["data"]
    remaining = credit_data["total_credits"] - credit_data["total_usage"]
    if remaining <= 0:
        raise RunStopped("OpenRouter account has no funded credit; no inference dispatched")
    return {"checked_at": now(), "model": model, "authentication_status": key.status_code,
            "account_has_positive_credit": True,
            "secret_and_exact_account_balance_excluded": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--rounds", type=int, default=15)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--budget-usd", type=float, default=20.0)
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent/"runs")
    args = parser.parse_args()
    if args.rounds < 1 or not 0 < args.budget_usd <= 120 or len(set(args.seeds)) != len(args.seeds):
        parser.error("Require positive rounds, unique seeds, and budget in (0, 120]")
    if not args.live:
        print(json.dumps({"mode": "plan_only", "calls": 6*args.rounds*len(args.seeds),
                          "params": [make_params(args.rounds,s).model_dump() for s in args.seeds]}, indent=2))
        return
    load_dotenv(REPO/"compute.env", override=False)
    if not os.environ.get("OPENROUTER_API_KEY"):
        parser.error("OPENROUTER_API_KEY is not configured")
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/"ledger.lock").open("a") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        budget = Budget(args.output/"ledger.json", args.budget_usd)
        batch = args.output/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+args.label)
        batch.mkdir(exist_ok=False)
        provenance(batch)
        save_json(batch/"plan.json", {"stage": "exploratory ordinary-chat baseline", "created_at": now(),
                  "params": [make_params(args.rounds,s).model_dump() for s in args.seeds],
                  "max_output_tokens": MAX_OUTPUT, "budget_ceiling_usd": args.budget_usd,
                  "no_automatic_retries_or_fallbacks": True})
        with httpx.Client(headers={"Authorization": "Bearer "+os.environ["OPENROUTER_API_KEY"]},
                          timeout=120.0) as transport:
            save_json(batch/"provider_preflight.json", preflight(transport))
            def builder(agent_id, seller, seed, call_dir):
                return AuditedClient(agent_id,seller,seed,budget,call_dir,transport)
            for seed in args.seeds:
                run_session(make_params(args.rounds,seed), batch/f"seed_{seed}", builder)
        print(json.dumps({"batch": str(batch), "budget": budget.state}), flush=True)


if __name__ == "__main__":
    main()
