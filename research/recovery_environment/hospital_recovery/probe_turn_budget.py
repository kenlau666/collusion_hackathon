"""Offline native continuation witness, predeclared at874db9bb.

No provider construction, keys, paid inference, source edits or run resumption.
Every attempt uses a fresh output directory and retains its full scripted trace.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
import socket
import statistics
import sys
import traceback

NETWORK = []


def deny_network(event, args):
    if event in {'socket.connect','socket.getaddrinfo','socket.bind'}:
        NETWORK.append({'event':event, 'stack':traceback.format_stack(limit=8)})
        raise RuntimeError('Network forbidden in unpaid continuation probe')


sys.addaudithook(deny_network)
_original_ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False
    from branch_runtime import (ScriptedChatClient, care, checkpoint, digest, schedule_args, transfer_args)
    from main_inputs import make_case, matrix, root_for, turns_for
    from main_pilot import MainAgent, canonical_recorded, file_hash, reward_endpoint, verify_bundle
finally:
    socket.has_ipv6 = _original_ipv6
logging.disable(logging.CRITICAL)

HERE = Path(__file__).resolve().parent
CONDITIONS = (('query_then_act_cap1',1,'query_then_act'),
              ('query_then_act_cap3',3,'query_then_act'),
              ('always_query_cap3',3,'always_query'),
              ('query_and_action_cap1',1,'batch'))


def save(path, value):
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,sort_keys=True,allow_nan=False)
        handle.write('\n')


def stats(values):
    return {'values':values,'n':len(values),'mean':statistics.mean(values),
            'sample_sd':statistics.stdev(values) if len(values)>1 else None,
            'sample_variance':statistics.variance(values) if len(values)>1 else None,
            'range':[min(values),max(values)]}


class ContextContingentScript(ScriptedChatClient):
    """The follow-up action is permitted only by a query result in current input.

    Its feasible action selection is hand-coded from the constructed case; this
    is not an LLM planner and not a test of behavioral care/exploit adoption.
    """
    def __init__(self, branch, mode):
        super().__init__()
        self.branch, self.mode, self.actor = branch, mode, None
        self.decisions = []

    def physical_action(self):
        b = self.branch
        hospital = b.env.agents_map[self.actor]['hospital']
        other = next(h for h in b.env.hospital_names if h != hospital)
        stock = b.env.inventory[hospital]['IV_Kits']
        if (stock > b.protocol.reserve(hospital,'IV_Kits') and
            b.env.inventory[other]['IV_Kits'] < b.protocol.reserve(other,'IV_Kits')):
            return ('transfer_resources',transfer_args(other))
        if not canonical_recorded(b,hospital) and stock >= 1:
            return ('schedule_patient',schedule_args(b.env,hospital,b.obligations[hospital][0]))
        return None

    def generate_response(self, input, params):
        has_query_result = any(m.get('role')=='tool' and m.get('name')=='get_job_queue' for m in input)
        batch = []
        if self.mode == 'always_query' or self.mode == 'batch' or not has_query_result:
            batch.append(('get_job_queue',{}))
        if self.mode == 'batch' or (self.mode == 'query_then_act' and has_query_result):
            action = self.physical_action()
            if action: batch.append(action)
        self.decisions.append({'actor':self.actor,'has_current_query_result':has_query_result,
                               'selected_tools':[name for name,_ in batch]})
        self.batches.append(batch)
        return super().generate_response(input,params)


async def case(seed, condition, cap, mode, frozen_roots, output):
    spec = next(s for s in matrix() if s['id']==f'main-s{seed}-neutral-original')
    b = await make_case(spec)
    initial_root = root_for(b,spec)
    if digest(initial_root) != digest(frozen_roots[spec['id']]):
        raise ValueError('Initial native root differs from frozen main input')
    initial = checkpoint(b.env)
    initial_score = reward_endpoint(b)
    # Use only the first declared hospital ordering, twice, for4execution turns.
    actors = [s['actor'] for s in turns_for(b,spec)[:2]]*2
    client = ContextContingentScript(b,mode)
    outcomes, errors = [], []
    for index, name in enumerate(actors):
        client.actor = name
        agent = MainAgent(client=client,name=name,model_name='SCRIPTED_NO_INFERENCE',
                          max_conversation_steps=cap,environment_name='HospitalEnvironment',
                          generation_params={'seed':100*seed+index})
        agent.study_branch, agent.study_turn = b,index
        before = len(client.requests)
        try:
            result = await b.protocol.agent_execution_turn(agent,name,
                b.env.build_agent_context(name,'execution',index//2+1),b.env,index//2+1)
        except Exception as exc:
            errors.append({'turn_index':index,'error_type':type(exc).__name__,'detail':str(exc)})
            result = {'error_type':type(exc).__name__}
        outcomes.append({'actor':name,'turn_index':index,'scripted_generations':len(client.requests)-before,
                         'first_scripted_request_index':before if len(client.requests)>before else None,
                         'outcome':result,'care':care(b.env),'checkpoint':checkpoint(b.env)})
    final, final_score = checkpoint(b.env),reward_endpoint(b)
    callbacks = b.callback_attempts
    summary = {'seed':seed,'condition':condition,'cap':cap,'scripted_generations':len(client.requests),
        'care_complete':sum(care(b.env).values()),'patients':2,
        'new_transfer_credit':final['transfer_rewards']-initial['transfer_rewards'],
        'transfer_attempts':sum(c['tool']=='transfer_resources' for c in callbacks),
        'schedule_attempts':sum(c['tool']=='schedule_patient' for c in callbacks),
        'query_attempts':sum(c['tool']=='get_job_queue' for c in callbacks),
        'resource_failures':sum(final['resource_failures'].values()),
        'initial_joint_reward':initial_score['joint_reward'],'final_joint_reward':final_score['joint_reward'],
        'native_reward_error':final_score['error'],'errors':errors,
        'first_generation_current_query_result_flags':[d['has_current_query_result']
            for d in [client.decisions[o['first_scripted_request_index']] for o in outcomes
                      if o['first_scripted_request_index'] is not None]],
        'physical_action_has_current_query_result_flags':[d['has_current_query_result'] for d in client.decisions
            if any(t in {'transfer_resources','schedule_patient'} for t in d['selected_tools'])]}
    summary['native_returned_errors'] = [o['turn_index'] for o in outcomes
        if o['outcome'].get('error') or any(str(o['outcome'].get(k,'')).startswith('[ERROR]')
            for k in ('response','full_content'))]
    summary['callback_errors'] = [i for i,c in enumerate(callbacks) if isinstance(c.get('result'),dict)
        and (c['result'].get('error') or c['result'].get('status') in {'error','denied'})]
    expected_generations = {'query_then_act_cap1':4,'query_then_act_cap3':9,
                            'always_query_cap3':12,'query_and_action_cap1':4}[condition]
    expected_queries = 12 if condition=='always_query_cap3' else 4
    active = condition in {'query_then_act_cap3','query_and_action_cap1'}
    summary['passed'] = (not errors and not summary['native_returned_errors']
        and not summary['callback_errors'] and final_score['error'] is None
        and len(outcomes)==4 and len(summary['first_generation_current_query_result_flags'])==4
        and summary['scripted_generations']==expected_generations and summary['query_attempts']==expected_queries
        and len(summary['physical_action_has_current_query_result_flags'])==(3 if active else 0)
        and summary['care_complete']==(2 if active else 0)
        and summary['new_transfer_credit']==(15 if active else 0)
        and summary['transfer_attempts']==(1 if active else 0)
        and summary['schedule_attempts']==(2 if active else 0)
        and summary['resource_failures']==0
        and not any(summary['first_generation_current_query_result_flags'])
        and (mode!='query_then_act' or all(summary['physical_action_has_current_query_result_flags'])))
    save(output/f'{condition}-s{seed}.json',{'summary':summary,'root':initial_root,'initial':initial,
         'final':final,'initial_native_reward':initial_score,'final_native_reward':final_score,
         'scripted_requests':client.requests,'scripted_decisions':client.decisions,'turns':outcomes,
         'callbacks':callbacks,'observations':b.protocol.observations})
    return summary


async def run(output, bundle):
    output.mkdir(parents=True,exist_ok=False)
    source = output/'source'; source.mkdir()
    shutil.copyfile(__file__,source/Path(__file__).name)
    before_plan = verify_bundle(bundle)
    roots = json.loads((bundle/'roots.json').read_text())
    previous = HERE/'20261025/main_live_001'
    protected = {p:file_hash(p) for p in previous.rglob('*') if p.is_file()}
    rows = []
    try:
        for seed in range(6):
            for name,cap,mode in CONDITIONS:
                rows.append(await case(seed,name,cap,mode,roots,output))
    except Exception as exc:
        save(output/'failed.json',{'error_type':type(exc).__name__,'detail':str(exc),
                                  'completed':rows,'network_attempts':NETWORK})
        raise
    groups = {}
    for name,_,_ in CONDITIONS:
        group = [r for r in rows if r['condition']==name]
        groups[name] = {'pass_count':sum(r['passed'] for r in group),'scenario_families':6,
            'endpoints':{key:stats([r[key] for r in group]) for key in
                ('care_complete','scripted_generations','new_transfer_credit','initial_joint_reward',
                 'final_joint_reward','resource_failures','query_attempts')}}
    comparisons = {}
    for name in ('query_then_act_cap3','always_query_cap3','query_and_action_cap1'):
        for metric in ('care_complete','final_joint_reward'):
            comparisons[f'{name}-baseline/{metric}'] = stats([
                next(r[metric] for r in rows if r['condition']==name and r['seed']==seed)
                -next(r[metric] for r in rows if r['condition']=='query_then_act_cap1' and r['seed']==seed)
                for seed in range(6)])
    integrity = before_plan==verify_bundle(bundle) and all(file_hash(p)==value for p,value in protected.items())
    result = {'kind':'scripted native software continuation probe, not LLM behavior',
        'predeclaration_commit':'874db9bb','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'network_attempts':NETWORK,'real_inference_calls':0,'paid_spend_usd':0,
        'scripted_generations':sum(r['scripted_generations'] for r in rows),'declared_scripted_ceiling':192,
        'scenario_families':6,'cases':rows,'groups':groups,'paired_differences':comparisons,
        'plan_sha256':before_plan,'frozen_source_and_prior_run_hashes_unchanged':integrity,
        'passed':all(r['passed'] for r in rows) and integrity and not NETWORK
                 and sum(r['scripted_generations'] for r in rows)<=192,
        'source_sha256':file_hash(Path(__file__)),
        'limits':'Scripted outcomes are imposed by action selection. Higher cap permits continuation but does not prove LLM task engagement. No novelty/readiness increase, paid restart or revised main study is authorized.'}
    save(output/'results.json',result)
    print(json.dumps({'passed':result['passed'],'cases':len(rows),
        'scripted_generations':result['scripted_generations'],'network_attempts':NETWORK,'real_inference_calls':0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    args = parser.parse_args()
    asyncio.run(run(args.out,args.bundle))


if __name__=='__main__':
    main()
