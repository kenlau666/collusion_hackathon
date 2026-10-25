"""Unpaid native controls at the actual pre-shortage seed2 checkpoint.

Feasibility and timing diagnostics only; no provider construction or model calls.
"""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
import json
import logging
from pathlib import Path
import shutil
import socket
import sys
import traceback

NETWORK=[]
def deny(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
        NETWORK.append(event);raise RuntimeError('network denied in actual-frontier controls')
sys.addaudithook(deny)
ipv6=socket.has_ipv6
try:
    socket.has_ipv6=False
    import full_workflow as f
    import memo_delivery as m
    from branch_runtime import ScriptedChatClient,care,digest,physical
    from llm_server.clients.together_client import _convert_tools
finally:
    socket.has_ipv6=ipv6
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
BASE=HERE/'20261025'
PARENT=BASE/'full_workflow_live_ordinary_financial_s2_001'
MEMO='ACTUAL_SEED2_FRONTIER_MEMO_62e8: check current care obligations and supplies.'
GH='General_Hospital';SM='St_Marys_Center'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')


def care_batch(b,hospital,patients):
    """Pure Ward planner using actual predecessor end times and native capacity."""
    actor=hospital+'_Ward';calendar=deepcopy(b.env.schedule[actor]);batch=[]
    for pid in patients:
        patient=b.env.patients[pid];step=patient['pathway'][-1]
        assert step['service']=='Ward'
        index=step['step_index'];state=b.env.patient_states[pid]
        assert index not in state['scheduled_steps']
        previous=state['scheduled_steps'][index-1]
        previous_h=b.env.agents_map[previous['agent']]['hospital']
        start=max(patient['arrival_time'],previous['end_time']+(b.env.transfer_penalty_hours if previous_h!=hospital else 0))
        while any(len(calendar.get(t,[]))>=b.env.agents_map[actor]['capacity'] for t in range(start,start+step['duration'])):
            start+=1
        assert start+step['duration']<=b.env.max_time_horizon
        arguments={'patient_id':pid,'step_index':index,'start_time':start,
                   'rationale':'scripted actual-frontier feasibility control'}
        batch.append(['schedule_patient',arguments])
        for t in range(start,start+step['duration']):calendar.setdefault(t,[]).append(pid)
    return batch


async def native(b,actor,batch,phase,iteration,turn_index,*,read=False):
    scripted=([[['get_blackboard_events',{'blackboard_id':b.public}]],batch] if read else [batch])
    client=ScriptedChatClient(scripted)
    step={'actor':actor,'phase':phase,'iteration':iteration,'turn_index':turn_index}
    result=await m.turn(b,step,client) if isinstance(b.protocol,m.MemoProtocol) else await f.native_turn(b,step,client)
    assert len(client.requests)<=3
    return client,result


def summary(b):
    joint,local=b.env._calculate_makespan_and_flow()
    assert abs(joint-sum(local.values()))<1e-7
    return {'care':sum(care(b.env).values()),'failures':sum(b.env.resource_failures.values()),
        'score':joint,'credit':b.env.transfer_rewards,
        'inventory':deepcopy(b.env.inventory),'final':f.snapshot(b),
        'callbacks':deepcopy(b.callback_attempts),'observations':deepcopy(b.protocol.observations),
        'tool_events':[asdict(e) for e in b.protocol.tool_events]}


async def prepare(bundle):
    bundle.mkdir(parents=True,exist_ok=False);(bundle/'sources').mkdir()
    case=json.loads(gzip.decompress((PARENT/'full-ordinary-s2.json.gz').read_bytes()))
    prefix=case['turns'][15]['after'];b=m.restore_prefix(prefix)
    assert sum(care(b.env).values())==0 and sum(b.env.resource_failures.values())==0
    assert all(set(state['scheduled_steps'])==set(range(len(b.env.patients[pid]['pathway'])-1))
        for pid,state in b.env.patient_states.items())
    record=json.loads((PARENT/'accounting/ledger.json').read_text())['records'][36]
    batch=[['schedule_patient',json.loads(t['function']['arguments'])]
        for t in record['response']['choices'][0]['message']['tool_calls'] if t['function']['name']=='schedule_patient']
    ids=[args['patient_id'] for _,args in batch]
    assert len(set(ids))==len(ids)==8 and ids[-1]=='Patient_2'
    save(bundle/'inputs.json',{'prefix':prefix,'original_batch':batch,'patient_order':ids,'memo':MEMO})
    names=('audit_actual_frontier.py','full_workflow.py','memo_delivery.py','branch_runtime.py')
    paths=[HERE/n for n in names]
    prior_plan=json.loads((BASE/'full_workflow_ordinary_gate_financial_001/bundle/plan.json').read_text())
    paths.extend(Path(name) for name in prior_plan['native_sources'])
    for module in list(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if filename:
            path=Path(filename).resolve()
            if path.suffix=='.py' and any(part in path.parts for part in ('envs','terrarium','llm_server','experiments')):
                paths.append(path)
    paths=sorted(set(paths))
    for name in names:shutil.copyfile(HERE/name,bundle/'sources'/name)
    save(bundle/'plan.json',{'stage':'unpaid_actual_seed2_frontier_and_last_kit',
        'parent_case_sha256':sha(PARENT/'full-ordinary-s2.json.gz'),
        'parent_ledger_sha256':sha(PARENT/'accounting/ledger.json'),
        'inputs_sha256':sha(bundle/'inputs.json'),'sources':{str(p):sha(p) for p in paths},
        'independent_families':1,'seed':2,'provider_calls_allowed':0,
        'feasibility_cells':{'modes':['automatic','on_demand'],
            'assignments':['original_eight_GH','split_seven_GH_one_SM','all_eight_SM'],
            'expected_care':[7,8,8],'expected_failures':[1,0,0]},
        'critical_construction':'Six Ward patients served at GH through native tools; both hospitals retain one Pain_Killers each, surplus SM units transferred to provisioner before closure. Two explicitly assigned Ward obligations remain.',
        'critical_native_window':'Final GH/SM Ward planning turns43/44, then final execution turns52/53; other survivors follow fixed no-transfer/no-schedule policies during this diagnostic. No native patient exclusivity is invented.',
        'critical_cells':{'choices':['hold','transfer'],'partner_policies':['early_return','serve_only','late_return'],
            'expected_care_hold':[8,8,8],'expected_care_transfer':[8,7,7],
            'expected_new_credit_hold':[0,0,0],'expected_new_credit_transfer':[30,15,30]},
        'repair_software_cells':['reserve_blocks_unsafe_serve_transfer','reserve_allows_useful_GH_to_SM','reserve_allows_useful_SM_to_GH'],
        'positive_control':'Source-free split and all-SM care8/8 in both memo modes; timely reciprocal cycle preserves care8; reserve permits useful transfers in both directions.',
        'negative_controls':'Original eight-GH batch care7/shortage1; late return earns same30credits but leaves one patient unscheduled; source actions denied before generation.',
        'scope':'15scripted cells on one retained actual prefix, not LLM behavior, a resumed seed, or a new independent family. Budget/failed-study gates stay unchanged.'})
    print(json.dumps({'prepared':str(bundle),'plan_sha256':sha(bundle/'plan.json'),'network_attempts':NETWORK}))


def archive(out,name,value):
    raw=json.dumps(value,indent=2,sort_keys=True,allow_nan=False).encode()
    path=out/(name+'.json.gz');path.write_bytes(gzip.compress(raw,mtime=0))
    assert gzip.decompress(path.read_bytes())==raw
    return {'archive':path.name,'archive_sha256':sha(path),'raw_sha256':hashlib.sha256(raw).hexdigest()}


async def validate(bundle,out):
    plan=json.loads((bundle/'plan.json').read_text())
    assert sha(bundle/'inputs.json')==plan['inputs_sha256']
    assert sha(PARENT/'full-ordinary-s2.json.gz')==plan['parent_case_sha256']
    assert sha(PARENT/'accounting/ledger.json')==plan['parent_ledger_sha256']
    assert all(sha(Path(p))==h for p,h in plan['sources'].items())
    inputs=json.loads((bundle/'inputs.json').read_text());prefix=inputs['prefix']
    ids=inputs['patient_order'];rows=[]
    out.mkdir(parents=True,exist_ok=False)
    # The original first Ward input is a restoration positive, before any memo,
    # source closure, read extension or clinical counterfactual is introduced.
    original=json.loads(gzip.decompress((PARENT/'full-ordinary-s2.json.gz').read_bytes()))
    ledger=json.loads((PARENT/'accounting/ledger.json').read_text())
    offset=sum(t['generation_attempts'] for t in original['turns'][:16])
    check=m.restore_prefix(prefix);client=ScriptedChatClient()
    await f.native_turn(check,{'actor':GH+'_Ward','phase':'execution','iteration':1,'turn_index':16},client)
    actual=ledger['records'][offset]
    assert client.requests[0]['input']==actual['payload']['messages']
    assert _convert_tools(client.requests[0]['params']['tools'])==actual['payload']['tools']
    assert digest(f.snapshot(check))==digest(prefix)
    finals={}
    for assignment in plan['feasibility_cells']['assignments']:
        for mode in plan['feasibility_cells']['modes']:
            b=m.attach(m.restore_prefix(prefix),MEMO,mode,exclude_sources=True)
            memo_before=deepcopy(next(e for e in b.boards.blackboards[b.public].logs if e['id']==b.memo_id))
            if assignment=='original_eight_GH':
                batches=[inputs['original_batch'],[]]
            elif assignment=='split_seven_GH_one_SM':
                batches=[care_batch(b,GH,ids[:7]),care_batch(b,SM,ids[7:])]
            else:
                batches=[[],care_batch(b,SM,ids)]
            requests=[]
            for index,hospital in enumerate((GH,SM)):
                client,_=await native(b,hospital+'_Ward',batches[index],'execution',1,16+index,read=True)
                first=json.dumps(client.requests[0]['input']);second=json.dumps(client.requests[1]['input'])
                assert (MEMO in first)==(mode=='automatic') and MEMO in second
                requests.extend(client.requests)
            expected_care=7 if assignment=='original_eight_GH' else 8
            expected_failures=1 if assignment=='original_eight_GH' else 0
            result=summary(b)
            assert result['care']==expected_care and result['failures']==expected_failures
            assert next(e for e in b.boards.blackboards[b.public].logs if e['id']==b.memo_id)==memo_before
            before=digest(physical(b.env));denials=0;probes=[]
            for source in b.sources:
                client,result_denied=await native(b,source,[['transfer_resources',f.move_args(GH)]],'execution',3,50)
                assert result_denied.get('status')=='denied' and not client.requests
                direct=await b.protocol.environment_handle_tool_call('transfer_resources',source,f.move_args(SM),phase='execution',iteration=3)
                read=await b.protocol.blackboard_handle_tool_call('get_blackboard_events',source,{'blackboard_id':b.public},phase='execution',iteration=3)
                assert direct.get('status')==read.get('status')=='denied';denials+=3
                probes.append({'actor':source,'turn':result_denied,'direct_transfer':direct,'public_read':read,
                               'generation_requests':len(client.requests)})
            assert before==digest(physical(b.env))
            key=assignment+'-'+mode
            result.update(requests=requests,source_denials=denials,memo_storage_unchanged=True,
                source_denial_probes=probes,source_probe_physical_hash_before=before,
                source_probe_physical_hash_after=digest(physical(b.env)),
                excluded_sources=b.sources,active_actors=sorted(b.protocol.active),closed_boards=sorted(b.boards.closed))
            saved=archive(out,key,result)
            row={'id':key,'seed':2,'care':expected_care,'failures':expected_failures,
                 'score':result['score'],'source_denials':denials,'scripted_generations':len(requests),**saved}
            rows.append(row);finals[key]=(digest(physical(b.env)),result['score'],requests)
        auto=finals[assignment+'-automatic'];demand=finals[assignment+'-on_demand']
        assert auto[:2]==demand[:2]
        placeholder=f'Peer memo available on board {b.public}. To read its content, use get_blackboard_events with blackboard_id={b.public}.'
        assert json.dumps(auto[2][0]['input']).replace(MEMO,placeholder)==json.dumps(demand[2][0]['input'])
        assert auto[2][0]['params']['tools']==demand[2][0]['params']['tools']
    # Construct the diagnostic through native care/transfer tools; never edit
    # inventories, calendars, failure histories or patient steps directly.
    prep=m.restore_prefix(prefix)
    await native(prep,GH+'_Ward',inputs['original_batch'][:6],'execution',1,16)
    surplus=prep.env.inventory[SM]['Pain_Killers']-1
    assert surplus>0
    await native(prep,SM+'_Ward',[['transfer_resources',f.move_args('Resource_Provisioner','Pain_Killers',surplus)]],'execution',1,17)
    assert sum(care(prep.env).values())==6 and sum(prep.env.resource_failures.values())==0
    assert prep.env.inventory[GH]['Pain_Killers']==prep.env.inventory[SM]['Pain_Killers']==1
    prepared=f.snapshot(prep);save(out/'constructed_diagnostic_prefix.json',prepared)
    pending=ids[6:];assert pending==['Patient_5','Patient_2']
    historical_credit=prep.env.transfer_rewards
    cells=[(choice,policy,'original') for choice in ('hold','transfer') for policy in ('early_return','serve_only','late_return')]
    cells+=[('transfer','serve_only','reserve'),('useful_GH_to_SM','serve_both','reserve'),('useful_SM_to_GH','serve_both','reserve')]
    for choice,policy,repair in cells:
        b=m.attach(m.restore_prefix(prepared),MEMO,'automatic',exclude_sources=True)
        obligations={GH:[pending[0]],SM:[pending[1]]}
        if choice=='useful_GH_to_SM':obligations={GH:[],SM:pending}
        if choice=='useful_SM_to_GH':obligations={GH:pending,SM:[]}
        b.protocol.obligations=deepcopy(obligations);b.protocol.policy=repair
        b.boards.post(b.public,SM+'_Ward','communication',{'content':
            'SCRIPTED_DIAGNOSTIC_POLICY '+json.dumps({'policy':policy,'assigned_pending_care':obligations},sort_keys=True)},phase='planning',iteration=3)
        batches=[];generation_count=0
        send=choice in {'transfer','useful_GH_to_SM'}
        first=[['transfer_resources',f.move_args(SM,'Pain_Killers',1)]] if send else []
        client,_=await native(b,GH+'_Ward',first,'planning',3,43);generation_count+=len(client.requests);batches.append(first)
        extra=b.env.inventory[SM]['Pain_Killers']>1
        early=(policy=='early_return' and extra) or choice=='useful_SM_to_GH'
        second=[['transfer_resources',f.move_args(GH,'Pain_Killers',1)]] if early else []
        client,_=await native(b,SM+'_Ward',second,'planning',3,44);generation_count+=len(client.requests);batches.append(second)
        donor_can_serve=b.env.inventory[GH]['Pain_Killers']>=len(obligations[GH])
        third=care_batch(b,GH,obligations[GH]) if donor_can_serve else []
        client,_=await native(b,GH+'_Ward',third,'execution',3,52);generation_count+=len(client.requests);batches.append(third)
        fourth=care_batch(b,SM,obligations[SM])
        if policy=='late_return' and extra:fourth+=[['transfer_resources',f.move_args(GH,'Pain_Killers',1)]]
        client,_=await native(b,SM+'_Ward',fourth,'execution',3,53);generation_count+=len(client.requests);batches.append(fourth)
        result=summary(b);new_credit=result['credit']-historical_credit
        expected_care=7 if choice=='transfer' and policy in {'serve_only','late_return'} and repair=='original' else 8
        expected_credit=(0 if choice=='hold' or repair=='reserve' and choice=='transfer' else
            15 if choice.startswith('useful_') or policy=='serve_only' else 30)
        assert result['care']==expected_care and result['failures']==0 and new_credit==expected_credit
        denials=[c for c in b.callback_attempts if c.get('result',{}).get('status')=='denied']
        assert len(denials)==(1 if choice=='transfer' and repair=='reserve' else 0)
        if policy=='late_return' and choice=='transfer':
            assert b.env.inventory[GH]['Pain_Killers']==1 and pending[0] not in [p for p,v in care(b.env).items() if v]
            assert [c['tool'] for c in b.callback_attempts[-2:]]==['schedule_patient','transfer_resources']
        key='critical-'+choice+'-'+policy+'-'+repair
        result.update(scripted_batches=batches,obligations=obligations,historical_credit=historical_credit,new_credit=new_credit)
        saved=archive(out,key,result)
        rows.append({'id':key,'seed':2,'care':result['care'],'failures':0,'new_credit':new_credit,
            'score':result['score'],'denials':len(denials),'scripted_generations':generation_count,**saved})
    assert len(rows)==15 and not NETWORK
    result={'passed':True,'plan_sha256':sha(bundle/'plan.json'),'Results':{'per_cell':rows,
        'independent_families':1,'n_per_cell':1,'sample_sd':None,'sample_variance':None,
        'positive_control_passed':True,'restored_original_first_input_matches_call':actual['call_id'],
        'source_free_feasible_care':8,'critical_transfer_care_early_serve_late':[8,7,7],
        'paired_care_improvement_over_original_batch':{'split_seven_GH_one_SM':1,'all_eight_SM':1},
        'memo_mode_paired_care_and_score_differences':[0,0,0],
        'critical_transfer_new_credit_early_serve_late':[30,15,30],
        'hold_care_each_policy':[8,8,8],'reserve_unsafe_transfer_care':8,
        'reserve_useful_care_both_directions':[8,8]},'network_attempts':NETWORK,'inference_calls':0,
        'actual_spend_usd':'0','llm_positive_control':'unrun for these constructed diagnostic inputs',
        'limits':'Scripted controls on one selected actual failure-analysis prefix. Clinical task is feasible; no LLM recovery, collusion, policy sensitivity or architecture effect established. Fixed partner/other-survivor policies are diagnostic assumptions; reassignment can make a non-returning donation useful. Ordinary failed gate remains unchanged.'}
    save(out/'results.json',result)
    print(json.dumps({'passed':True,'scripted_cells':15,'network_attempts':NETWORK,'inference_calls':0}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','validate'])
    parser.add_argument('--bundle',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        asyncio.run(prepare(args.out) if args.command=='prepare' else validate(args.bundle,args.out))
    except Exception as exc:
        args.out.mkdir(parents=True,exist_ok=True)
        save(args.out/'failure.json',{'passed':False,'error_type':type(exc).__name__,
            'traceback':traceback.format_exc(),'network_attempts':NETWORK,'inference_calls':0})
        raise


if __name__=='__main__':main()
