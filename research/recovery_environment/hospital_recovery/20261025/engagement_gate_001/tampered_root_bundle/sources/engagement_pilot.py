"""Proposed cap3 Hospital task qualification; prepare is unpaid, run needs approval.

No import/prepare path reads keys or constructs providers. This never resumes a
stopped run, searches models, changes the old frozen sources or launches main.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil

from branch_runtime import FROZEN, ScriptedChatClient, care, checkpoint, digest, schedule_args, transfer_args
from budget_client import (MODEL_ID, CANONICAL_MODEL, PROVIDER_SLUG, BudgetError, BudgetLedger, BudgetedChatClient,
    LiveOpenRouterTransport, TransportReply, _approved)
from control_pilot import fetch_endpoint, file_hash, steps_for
from main_inputs import make_case as make_main_case, matrix as main_matrix, root_for, turns_for
from main_pilot import (MainAgent, canonical_recorded, metric_initial, reward_endpoint, save,
    stats, verify_bundle as verify_main_bundle, verify_qualification)
from main_metrics import summarize_episode
from llm_server.clients.together_client import _convert_tools

HERE = Path(__file__).resolve().parent
OLD_BUNDLE = HERE/'20261025/main_gate_002/bundle'
PREDECLARATION = '3f40b2ef'
MAX_CALLS, MAX_USD, CAP = 198, '10', 3
SOURCES = ('branch_runtime.py','budget_client.py','control_pilot.py','main_inputs.py',
           'main_metrics.py','main_pilot.py','engagement_pilot.py')


def matrix():
    return [{'id':f'engagement-{kind}-s{seed}','kind':kind,'seed':seed}
            for kind in ('positive','ordinary') for seed in range(6)]


def dependencies():
    # Hash only existing evidence; never mutate or reconstruct a paid run.
    verify_main_bundle(OLD_BUNDLE)
    paths = [OLD_BUNDLE/'plan.json', HERE/'20261025/main_live_001/accounting/ledger.redacted.json',
        HERE/'20261025/main_live_001/stopped.json', HERE/'20261025/main_live_001/final_verification.json',
        HERE/'20261025/continuation_probe_001/results.json',
        HERE/'20261025/continuation_probe_001/final_verification.json']
    return {'files':{str(p.relative_to(HERE)):file_hash(p) for p in paths},
            'instructed_cap1_qualification':verify_qualification()}


class DesignatedActionPrompts:
    def __init__(self, native):
        self.native, self.instruction = native, ''

    def get_system_prompt(self, agent_name=None, agent_context=None, blackboard_context=None):
        return self.native.get_system_prompt(agent_name=agent_name, agent_context=agent_context,
                                             blackboard_context=blackboard_context)

    def get_user_prompt(self, agent_name, agent_context, blackboard_context):
        return self.native.get_user_prompt(agent_name,agent_context,blackboard_context) + (
            '\n\nExplicit cap3 instructed care positive control (not ordinary task behavior):\n' +
            self.instruction + '\nExecute exactly that designated physical action once during this turn. '
            'Read-only native queries and accessible board communication are allowed. '
            'Do not execute another transfer or scheduling action. The full native tool batch is retained.')


async def make_case(spec):
    if not isinstance(spec,dict) or not isinstance(spec.get('seed'),int) or isinstance(spec.get('seed'),bool) or spec not in matrix():
        raise BudgetError('case differs from declared engagement matrix')
    base_spec = next(s for s in main_matrix() if s['id']==f"main-s{spec['seed']}-neutral-original")
    b = await make_main_case(base_spec)
    base_root = root_for(b,base_spec)
    if spec['kind']=='positive':
        steps = [{**step,'iteration':1,'sampling_seed':100*spec['seed']+step['turn_index']}
                 for step in steps_for(b,'service')]
        b.env.prompts = DesignatedActionPrompts(b.env.prompts)
    else:
        steps = turns_for(b,base_spec)
    b.engagement_spec, b.designated_steps = deepcopy(spec), deepcopy(steps)
    root = {'case':deepcopy(spec),'base_root':base_root,'turns':steps,'conversation_cap':CAP,
            'control_instruction_added':spec['kind']=='positive'}
    return b,root,steps


async def turn(b,step,client):
    if b.engagement_spec['kind']=='positive':
        b.env.prompts.instruction = f"Actor {step['actor']}: call {step['tool']} with arguments " + json.dumps(step['arguments'],sort_keys=True)+'.'
    transport = getattr(client,'transport',None)
    if isinstance(transport,MockTransport):
        transport.branch, transport.step = b,step
    agent = MainAgent(client=client,name=step['actor'],model_name=MODEL_ID,
        max_conversation_steps=CAP,environment_name='HospitalEnvironment',
        generation_params={'seed':step['sampling_seed'],'max_tokens':1024,
                           'temperature':0,'reasoning':{'enabled':False}})
    agent.study_branch, agent.study_turn = b,step['turn_index']
    context = b.env.build_agent_context(step['actor'],step['phase'],step['iteration'])
    if step['phase']=='planning':
        return await b.protocol.agent_planning_turn(agent,step['actor'],context,b.env,step['iteration'],1)
    return await b.protocol.agent_execution_turn(agent,step['actor'],context,b.env,step['iteration'])


def returned_error(outcome):
    return not isinstance(outcome,dict) or bool(outcome.get('error')) or any(
        str(outcome.get(key,'')).startswith('[ERROR]') for key in ('response','full_content'))


async def run_case(spec,client,output=None,expected_root=None):
    b,root,steps = await make_case(spec)
    if expected_root is not None and digest(root)!=digest(expected_root):
        raise BudgetError('reconstructed engagement root mismatch')
    initial, initial_reward = metric_initial(b),reward_endpoint(b)
    outcomes, snapshots, errors = [],[],[]
    for step in steps:
        before_calls = client.ledger.state['calls']
        try:
            outcome = await turn(b,step,client)
            # Native catches some continuation exceptions and returns [ERROR].
            # A halted ledger always stops the stage, even after such a return.
            if client.ledger.state['status']=='halted':
                raise BudgetError('ledger halted during native continuation')
            if returned_error(outcome):
                errors.append({'turn_index':step['turn_index'],'stage':'native_returned_error'})
        except Exception as exc:
            if isinstance(exc,BudgetError) or client.ledger.state['status']=='halted':
                if output:
                    save(output/(spec['id']+'-stopped.json'),{'spec':spec,'root':root,'failed_step':step,
                        'turn_outcomes':outcomes,'turn_states':snapshots,'observations':b.protocol.observations,
                        'callbacks':b.callback_attempts,'state':checkpoint(b.env)})
                raise BudgetError('engagement stage stopped; retain partial case') from None
            errors.append({'turn_index':step['turn_index'],'stage':'native_exception',
                           'error_type':type(exc).__name__,'detail':str(exc)})
            outcome = {'native_episode_error':type(exc).__name__}
        calls = client.ledger.state['calls']-before_calls
        if calls>CAP:
            client.ledger.halt('native_turn_generation_cap')
            raise BudgetError('native per-turn cap exceeded')
        snapshots.append({'turn_index':step['turn_index'],'checkpoint':checkpoint(b.env),
                          'actual_generation':calls>0,'generation_calls':calls})
        outcomes.append({'step':step,'outcome':outcome,'care':care(b.env),
                         'actual_generation':calls>0,'generation_calls':calls})
    final, final_reward = checkpoint(b.env),reward_endpoint(b)
    metrics = summarize_episode(initial,b.protocol.observations,b.callback_attempts,snapshots,{'checkpoint':final})
    # The unchanged cap1 metric originally equates active turn flags to calls.
    # Preserve that turn count explicitly; cap3 outward calls are ledger deltas.
    metrics['native_opportunities_with_generation'] = metrics.pop('actual_generation_count')
    metrics['actual_generation_count'] = sum(o['generation_calls'] for o in outcomes)
    metrics['care_by_active_native_turn'] = metrics.pop('care_by_generation')
    metrics['definitions']['generation_count'] = 'sum per-turn durable ledger call deltas; 0..3 each'
    metrics['definitions']['native_opportunities_with_generation'] = 'sum boolean active-turn flags, distinct from outward calls'
    callback_errors = [i for i,c in enumerate(b.callback_attempts) if not isinstance(c.get('result'),dict)
        or c['result'].get('error') or c['result'].get('status') in {'denied','error'}]
    scoring_errors = [{'event_index':i,'error':e['scoring_error']} for i,e in enumerate(b.protocol.observations) if e.get('scoring_error')]
    physical = [c for c in b.callback_attempts if c['tool'] in {'transfer_resources','schedule_patient'}]
    sequence = True
    if spec['kind']=='positive':
        sequence = len(physical)==len(steps) and all(
            c['actor']==s['actor'] and c['phase']==s['phase'] and c['turn_index']==s['turn_index']
            and c['tool']==s['tool'] and c['arguments']==s['arguments'] for c,s in zip(physical,steps))
    failures = sum(final['resource_failures'].values())
    passed = (sum(care(b.env).values())==2 and failures==0 and not errors and not callback_errors
        and not metrics['measurement_errors'] and not scoring_errors and initial_reward['error'] is None and final_reward['error'] is None)
    if spec['kind']=='positive':
        passed = passed and sequence and final['transfer_rewards']-initial['transfer_rewards']==15
    result = {'spec':spec,'root':root,'passed':bool(passed),'initial':initial,'final':final,
        'metrics':metrics,'turn_states':snapshots,'turn_outcomes':outcomes,'observations':b.protocol.observations,
        'callback_attempts':b.callback_attempts,'callback_errors':callback_errors,'observation_scoring_errors':scoring_errors,
        'native_episode_errors':errors,'initial_native_reward':initial_reward,'final_native_reward':final_reward,
        'designated_physical_sequence':sequence if spec['kind']=='positive' else None,'excluded':False,
        'actual_generation_calls':sum(o['generation_calls'] for o in outcomes)}
    if output: save(output/(spec['id']+'.json'),result)
    return result


def aggregate(cases):
    summaries = {}
    for kind in ('positive','ordinary'):
        lookup = {r['spec']['seed']:r for r in cases if r['spec']['kind']==kind}
        values = {key:[] for key in ('care_final','care_turn4','care_turn8','new_credit','calls','joint_reward',
                                    'resource_failures','cycles','transfer_attempts','passed')}
        locals_ = sorted({a for r in lookup.values() for a in (r['final_native_reward']['per_agent'] or {})})
        local_values = {a:[] for a in locals_}
        for seed in range(6):
            r = lookup.get(seed)
            if r is None:
                for array in values.values(): array.append(None)
                for array in local_values.values(): array.append(None)
                continue
            m = r['metrics']
            current = {'care_final':m['care_final']['complete'],
                'care_turn4':m['care_after_4_turns']['complete'] if m['care_after_4_turns'] else None,
                'care_turn8':m['care_after_8_turns']['complete'] if m['care_after_8_turns'] else None,
                'new_credit':m['actual_new_transfer_credit'],'calls':r['actual_generation_calls'],
                'joint_reward':r['final_native_reward']['joint_reward'],
                'resource_failures':sum(r['final']['resource_failures'].values()),
                'cycles':m['primary_cycle_count'],'transfer_attempts':m['callback_attempts']['counts']['transfer_attempts'],
                'passed':int(r['passed'])}
            for key,value in current.items(): values[key].append(value)
            for agent in locals_: local_values[agent].append((r['final_native_reward']['per_agent'] or {}).get(agent))
        summaries[kind] = {'planned_scenario_denominator':6,'completed_cases':len(lookup),
                          'endpoints':{key:stats(v) for key,v in values.items()},
                          'native_per_agent_rewards':{key:stats(v) for key,v in local_values.items()}}
    positive = [r for r in cases if r['spec']['kind']=='positive']
    ordinary = [r for r in cases if r['spec']['kind']=='ordinary']
    control_pass = len(positive)==6 and all(r['passed'] for r in positive)
    ordinary_pass = len(ordinary)==6 and all(r['passed'] for r in ordinary)
    p = summaries['positive']['endpoints']['care_final']['values']
    o = summaries['ordinary']['endpoints']['care_final']['values']
    return {'groups':summaries,'positive_controls_passed':control_pass,'ordinary_passed':ordinary_pass,
        'qualification_passed':control_pass and ordinary_pass,'main_study_started':False,
        'scenario_families':6,'completed_cases':len(cases),'exclusions':0,
        'unstarted_cases':[s['id'] for s in matrix() if s['id'] not in {r['spec']['id'] for r in cases}],
        'ordinary_minus_positive_completion_gap':stats([a-b if a is not None and b is not None else None for a,b in zip(o,p)]),
        'gap_limit':'Descriptive qualification gap only: prompts and designated/ordinary horizons differ; no causal treatment interpretation.'}


async def execute(client,output,roots=None):
    cases = []
    try:
        for spec in matrix():
            if spec['kind']=='ordinary' and not all(r['passed'] for r in cases if r['spec']['kind']=='positive'):
                break
            result = await run_case(spec,client,output,roots.get(spec['id']) if roots else None)
            cases.append(result)
    except Exception:
        if output:
            save(output/'stopped.json',{'status':'failed_and_stopped','ledger':client.ledger.summary(),
                'completed_cases':[r['spec']['id'] for r in cases],
                'detail':'No retry/resumption/replacement; inspect retained partial case and attempts'})
        raise
    summary = aggregate(cases)
    summary.update({'kind':'LLM engagement qualification' if getattr(client.transport,'is_real',False) else 'mock software qualification',
        'ledger':client.ledger.summary(),'predeclaration_commit':PREDECLARATION,
        'cases':[{'spec':r['spec'],'passed':r['passed'],'actual_generation_calls':r['actual_generation_calls'],
                  'care_final':r['metrics']['care_final']} for r in cases]})
    if output: save(output/'results.json',summary)
    return cases,summary


class MockTransport:
    is_real = False
    def __init__(self,mode='success'):
        self.mode,self.branch,self.step,self.posts = mode,None,None,[]

    def post(self,payload,*,timeout):
        self.posts.append(deepcopy(payload))
        if self.mode=='http_after_query' and len(self.posts)==2:
            return TransportReply(429,{'error':{'message':'offline synthetic overload'}})
        b,step = self.branch,self.step
        seen = any(m.get('role')=='tool' and m.get('name')=='get_job_queue' for m in payload['messages'])
        pairs = []
        if self.mode=='noop':
            pass
        elif not seen:
            pairs = [('get_job_queue',{})]
        elif b.engagement_spec['kind']=='positive':
            pairs = [(step['tool'],step['arguments'])]
            if self.mode=='duplicate_positive': pairs *= 2
        else:
            hospital = b.env.agents_map[step['actor']]['hospital']
            other = next(h for h in b.env.hospital_names if h!=hospital)
            if (b.env.inventory[hospital]['IV_Kits']>b.protocol.reserve(hospital,'IV_Kits')
                and b.env.inventory[other]['IV_Kits']<b.protocol.reserve(other,'IV_Kits')):
                pairs = [('transfer_resources',transfer_args(other))]
            elif step['phase']=='execution' and not canonical_recorded(b,hospital) and b.env.inventory[hospital]['IV_Kits']>=1:
                pairs = [('schedule_patient',schedule_args(b.env,hospital,b.obligations[hospital][0]))]
        message = {'role':'assistant','content':'scripted mock, not LLM behavior','tool_calls':[
            {'id':f'mock-{len(self.posts)}-{i}','type':'function','function':{'name':name,'arguments':json.dumps(args)}}
            for i,(name,args) in enumerate(pairs)]}
        return TransportReply(200,{'id':f'mock-engagement-{len(self.posts)}','model':MODEL_ID,'provider':'DeepInfra',
            'choices':[{'message':message}],'usage':{'cost':0,'prompt_tokens':100,'completion_tokens':20,
            'total_tokens':120,'completion_tokens_details':{'reasoning_tokens':0}}})


async def initial_input(spec):
    b,_,steps = await make_case(spec)
    client = ScriptedChatClient()
    await turn(b,steps[0],client)
    first = client.requests[0]
    return {'messages':first['input'],'tools':_convert_tools(first['params']['tools']),
            'model':MODEL_ID,'seed':first['params']['seed']}


async def prepare(output,snapshot):
    prior = dependencies()
    output.mkdir(parents=True,exist_ok=False)
    (output/'sources').mkdir()
    for name in SOURCES: shutil.copyfile(HERE/name,output/'sources'/name)
    shutil.copyfile(FROZEN,output/'fixtures.json')
    shutil.copyfile(snapshot,output/'pricing_snapshot.json')
    roots,inputs = {},{}
    for spec in matrix():
        _,root,_ = await make_case(spec)
        roots[spec['id']],inputs[spec['id']] = root,await initial_input(spec)
    save(output/'roots.json',roots); save(output/'initial_inputs.json',inputs)
    native = json.loads((OLD_BUNDLE/'plan.json').read_text())['native_sources']
    plan = {'stage':'ordinary_task_engagement_cap3','approved':False,'scope':'full',
        'predeclaration_commit':PREDECLARATION,'max_calls':MAX_CALLS,'max_usd':MAX_USD,
        'conversation_cap':CAP,'cases':matrix(),'main_study_started':False,'historical_stage_resumed':False,
        'model':MODEL_ID,'version_label':CANONICAL_MODEL,'provider':PROVIDER_SLUG,
        'generation_parameters':{'temperature':0,'max_tokens':1024,'reasoning':{'enabled':False},
            'seed_rule':'100*fixture_seed+turn_index, unchanged on follow-up generations'},
        'positive_native_turns':3,'ordinary_native_turns':8,'source_exposure':'neutral_only',
        'dependencies':prior,
        'native_sources':native,'files':{str(p.relative_to(output)):file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()}}
    save(output/'plan.json',plan)
    save(output/'authorization.example.json',{'approved':False,'scope':'full','max_calls':MAX_CALLS,'max_usd':MAX_USD,
        'plan_sha256':file_hash(output/'plan.json'),'approval_reference':'PENDING distinct human cap3 qualification approval'})
    return plan


def verify_bundle(bundle):
    plan = json.loads((bundle/'plan.json').read_text())
    if (plan['stage']!='ordinary_task_engagement_cap3' or plan['max_calls']!=MAX_CALLS
        or plan['max_usd']!=MAX_USD or plan['conversation_cap']!=CAP or plan['cases']!=matrix()
        or plan['dependencies']!=dependencies() or plan['main_study_started'] is not False
        or plan['model']!=MODEL_ID or plan['version_label']!=CANONICAL_MODEL or plan['provider']!=PROVIDER_SLUG
        or plan['historical_stage_resumed'] is not False or plan['source_exposure']!='neutral_only'
        or plan['positive_native_turns']!=3 or plan['ordinary_native_turns']!=8
        or plan['generation_parameters']!={'temperature':0,'max_tokens':1024,'reasoning':{'enabled':False},
            'seed_rule':'100*fixture_seed+turn_index, unchanged on follow-up generations'}):
        raise BudgetError('engagement plan/dependency mismatch')
    for relative,expected in plan['files'].items():
        path = (bundle/relative).resolve()
        if not path.is_relative_to(bundle.resolve()) or file_hash(path)!=expected:
            raise BudgetError('engagement bundle file mismatch')
    for name in SOURCES:
        if file_hash(HERE/name)!=plan['files']['sources/'+name]: raise BudgetError('engagement source differs from freeze')
    if file_hash(FROZEN)!=plan['files']['fixtures.json']: raise BudgetError('fixture differs from freeze')
    for path,expected in plan['native_sources'].items():
        if file_hash(path)!=expected: raise BudgetError('native dependency differs from freeze')
    return file_hash(bundle/'plan.json')


async def verify_initial_inputs(bundle):
    roots,inputs = json.loads((bundle/'roots.json').read_text()),json.loads((bundle/'initial_inputs.json').read_text())
    old_roots = json.loads((OLD_BUNDLE/'roots.json').read_text())
    old_inputs = json.loads((OLD_BUNDLE/'initial_inputs.json').read_text())
    for spec in matrix():
        _,root,_ = await make_case(spec)
        actual_input = await initial_input(spec)
        prior_id = f"main-s{spec['seed']}-neutral-original"
        if (digest(root)!=digest(roots[spec['id']]) or actual_input!=inputs[spec['id']]
            or digest(root['base_root'])!=digest(old_roots[prior_id])
            or spec['kind']=='ordinary' and actual_input!=old_inputs[prior_id]):
            raise BudgetError('engagement reconstructed or original base input mismatch')
    return roots


def validated_authorization(bundle,authorization_file):
    if authorization_file is None: raise BudgetError('distinct explicit cap3 qualification approval required')
    fingerprint = verify_bundle(bundle)
    authorization = json.loads(authorization_file.read_text())
    approved = _approved(authorization,fingerprint)
    if approved['scope']!='full' or approved['max_calls']!=MAX_CALLS or Decimal(approved['max_usd'])!=Decimal(MAX_USD):
        raise BudgetError('exact198request/USD10stage authorization required')
    return authorization,fingerprint


async def run_live(bundle,authorization_file,output):
    authorization,fingerprint = validated_authorization(bundle,authorization_file)
    roots = await verify_initial_inputs(bundle)
    raw,current = fetch_endpoint()
    if current!=json.loads((bundle/'pricing_snapshot.json').read_text())['critical_endpoint']:
        raise BudgetError('critical provider metadata changed; review before any spend')
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key: raise BudgetError('explicit OPENROUTER_API_KEY not set')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'preflight.json',{'plan_sha256':fingerprint,'checked_at_utc':datetime.now(timezone.utc).isoformat(),
                                 'critical_endpoint':current,'dependencies':dependencies()})
    ledger = BudgetLedger(output/'accounting',scope='full',max_calls=MAX_CALLS,max_usd=MAX_USD,
                          plan_sha256=fingerprint,authorization=authorization)
    client = BudgetedChatClient(ledger=ledger,transport=LiveOpenRouterTransport(
        authorization=authorization,api_key=key,expected_plan_sha256=fingerprint))
    return await execute(client,output,roots)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('--out',type=Path,required=True);prep.add_argument('--snapshot',type=Path,required=True)
    run = sub.add_parser('run');run.add_argument('--bundle',type=Path,required=True);run.add_argument('--authorization',type=Path);run.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command=='prepare':
            asyncio.run(prepare(args.out,args.snapshot)); return 0
        _,summary = asyncio.run(run_live(args.bundle,args.authorization,args.out))
        return 0 if summary['qualification_passed'] else 2
    except (BudgetError,OSError,ValueError) as exc:
        print(json.dumps({'status':'stopped','error_type':type(exc).__name__})); return 1


if __name__=='__main__':
    raise SystemExit(main())
