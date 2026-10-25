"""Continue only two missing native turns from the preserved seed1 checkpoint."""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

import run_full_workflow as w
from memo_delivery import restore_prefix
from timeout_retry_client import TimeoutRetryLedger, encoded
from capacity_guard_client import FinancialByteClient, POLICY, TRANSPORT
from branch_runtime import ScriptedChatClient, care, digest
from budget_client import BudgetError, TransportReply
from analyze_full_workflow import audit_retry_ledger

HERE=w.HERE
BASE=w.BASE
PARENT=BASE/'full_workflow_live_ordinary_retry1_s1_001'
ORDINARY=BASE/'full_workflow_ordinary_gate_financial_001/bundle'
CONTROLS=BASE/'full_workflow_live_controls_financial_001'
SOURCES=('resume_ordinary_suffix.py','run_full_workflow.py','full_workflow.py','memo_delivery.py',
    'branch_runtime.py','capacity_guard_client.py','timeout_retry_client.py','traced_modal_client.py',
    'modal_hospital_client.py','modal_hospital_runtime.py','endpoint_probe_worker.py',
    'budget_client.py','analyze_full_workflow.py','analyze_ordinary_suffix.py')


def parent():
    raw=gzip.decompress((PARENT/'full-ordinary-s1.json.gz').read_bytes())
    old=json.loads(raw)
    ledger=json.loads((PARENT/'accounting/ledger.json').read_text())
    assert ledger['halt_reason']=='payload_or_prompt_bound' and ledger['calls']==105
    assert len(old['turns'])==53 and all(t['complete_turn'] for t in old['turns'][:52])
    blocked=old['turns'][-1]
    assert blocked['turn_index']==52 and not blocked['complete_turn']
    assert blocked['generation_attempts']==0 and blocked['logical_generation_requests']==1
    assert blocked['after']==old['turns'][-2]['after']
    assert all(c['turn_index']<52 for c in old['callbacks'])
    return old,ledger


async def first_wire(prefix,step,template):
    b=restore_prefix(prefix)
    client=ScriptedChatClient()
    await w.f.native_turn(b,step,client,model=w.MODEL)
    request=client.requests[0]
    payload=json.loads(template)
    payload.update(messages=request['input'],tools=w._convert_tools(request['params']['tools']))
    assert digest(w.f.snapshot(b))==digest(prefix)
    return encoded(payload)


async def prepare(bundle):
    ordinary_plan,_=w.verify_bundle(ORDINARY)
    old,ledger=parent();prefix=old['turns'][-2]['after']
    blocked=(PARENT/'payload_audit/rejected_wire.json').read_bytes()
    b=restore_prefix(prefix);steps=w.f.turns(b)[52:]
    assert len(steps)==2 and all(s['phase']=='execution' and s['iteration']==3 for s in steps)
    assert await first_wire(prefix,steps[0],blocked)==blocked
    bundle.mkdir(parents=True,exist_ok=False);(bundle/'sources').mkdir()
    w.save(bundle/'prefix.json',prefix)
    (bundle/'first_wire.json').write_bytes(blocked)
    for name in SOURCES:shutil.copyfile(HERE/name,bundle/'sources'/name)
    plan={'stage':'faithful_seed1_suffix','seed':1,'parent_case_sha256':w.sha(PARENT/'full-ordinary-s1.json.gz'),
        'parent_ledger_sha256':w.sha(PARENT/'accounting/ledger.json'),
        'prefix_sha256':w.sha(bundle/'prefix.json'),'prefix_digest':digest(prefix),
        'first_wire_sha256':w.sha(bundle/'first_wire.json'),'steps':steps,
        'sources':{n:w.sha(HERE/n) for n in SOURCES},'native_sources':ordinary_plan['native_sources'],
        'ordinary_plan_sha256':w.sha(ORDINARY/'plan.json'),'capacity_guard_policy':POLICY,
        'control_plan_sha256':w.sha(BASE/'full_workflow_model_gate_financial_001/bundle/plan.json'),
        'transport':TRANSPORT,'request_deadline_seconds':60,'logical_start':105,
        'blocked_slot_reused':106,'max_new_logical_requests':6,'max_outward_attempts':12,
        'max_reserved_usd':'.588','parent_paid_attempts':105,
        'parent_guard_usd':str(Decimal(ledger['spent_usd'])+Decimal(ledger['held_usd'])),
        'positive':'exact restored state and first wire; query→native transfer executes once in unchanged two-turn suffix',
        'negative':'changed first wire denied before dispatch; HTTP failure retains hold; no-op remains valid after care',
        'no_seed_restart_or_replacement':True,'native_generations_per_turn':3,
        'budget':'All historical guards plus this new ledger checked before each call; parent+suffix<=198/USD10',
        'parent_endpoint_unchanged':'original partial report stays incomplete; joined trajectory is explicitly derived'}
    w.save(bundle/'plan.json',plan)
    w.save(bundle/'authorization.json',{'approved':True,'scope':'full','max_calls':12,'max_usd':'.588',
        'plan_sha256':w.sha(bundle/'plan.json'),'approval_reference':w.APPROVAL,
        'timeout_retry_policy':w.RETRY_POLICY,'retry_approval_reference':w.RETRY_DIRECTIVE,
        'capacity_guard_policy':POLICY})
    print(json.dumps({'prepared':str(bundle),'plan_sha256':w.sha(bundle/'plan.json'),'network_attempts':w.NETWORK}))


async def verify(bundle):
    plan=json.loads((bundle/'plan.json').read_text());old,ledger=parent()
    assert w.sha(PARENT/'full-ordinary-s1.json.gz')==plan['parent_case_sha256']
    assert w.sha(PARENT/'accounting/ledger.json')==plan['parent_ledger_sha256']
    assert w.sha(bundle/'prefix.json')==plan['prefix_sha256'] and w.sha(bundle/'first_wire.json')==plan['first_wire_sha256']
    assert w.sha(ORDINARY/'plan.json')==plan['ordinary_plan_sha256']
    assert w.sha(BASE/'full_workflow_model_gate_financial_001/bundle/plan.json')==plan['control_plan_sha256']
    for name,h in plan['sources'].items():assert w.sha(HERE/name)==w.sha(bundle/'sources'/name)==h
    for name,h in plan['native_sources'].items():assert w.sha(Path(name))==h
    prefix=json.loads((bundle/'prefix.json').read_text())
    assert prefix==old['turns'][-2]['after'] and digest(prefix)==plan['prefix_digest']
    wire=(bundle/'first_wire.json').read_bytes()
    assert await first_wire(prefix,plan['steps'][0],wire)==wire
    assert plan['parent_paid_attempts']+plan['max_outward_attempts']<=198
    assert Decimal(plan['parent_guard_usd'])+Decimal(plan['max_reserved_usd'])<=10
    auth=json.loads((bundle/'authorization.json').read_text())
    assert auth['plan_sha256']==w.sha(bundle/'plan.json') and auth['capacity_guard_policy']==POLICY
    assert auth['approval_reference']==w.APPROVAL and auth['retry_approval_reference']==w.RETRY_DIRECTIVE
    return plan,auth,old,prefix


class FirstWireLedger(TimeoutRetryLedger):
    expected_first_sha256=None
    def reserve(self,payload,payload_bytes):
        if self.state['calls']==0 and hashlib.sha256(encoded(payload)).hexdigest()!=self.expected_first_sha256:
            self.halt('resumed_request_mismatch')
            raise BudgetError('continuation first request differs from preserved blocked slot')
        return super().reserve(payload,payload_bytes)


class Mock:
    is_real=False
    def __init__(self,b,mode):self.b,self.mode,self.calls=b,mode,0
    def post(self,payload,*,timeout):
        self.calls+=1
        if self.mode=='http_failure':return TransportReply(429,{'error':'offline synthetic failure'})
        batch=[]
        if self.mode=='positive' and self.calls==1:batch=[['get_job_queue',{}]]
        if self.mode=='positive' and self.calls==2:batch=[['transfer_resources',w.f.move_args(self.b.precedence[1])]]
        message={'role':'assistant','content':'scripted suffix control','tool_calls':[
            {'id':f'offline-{self.calls}-{i}','type':'function','function':{'name':n,'arguments':json.dumps(a)}}
            for i,(n,a) in enumerate(batch)]}
        return TransportReply(200,{'id':f'offline-{self.calls}','model':w.MODEL,
            'choices':[{'message':message,'finish_reason':'tool_calls' if batch else 'stop'}],
            'usage':{'prompt_tokens':2000,'completion_tokens':200}})


async def execute(bundle,out,mock=None):
    plan,auth,old,prefix=await verify(bundle)
    qualified_hash=None
    if mock is None:
        gate=json.loads((bundle.parent/'validation/results.json').read_text())
        assert gate['passed'] and gate['plan_sha256']==w.sha(bundle/'plan.json')
        controls=json.loads((CONTROLS/'results.json').read_text())
        analysis=json.loads((CONTROLS/'analysis.json').read_text())
        assert controls['transport']==TRANSPORT and controls['all_passed'] and analysis['positive_control_passed']
        assert controls['plan_sha256']==analysis['plan_sha256']==plan['control_plan_sha256']
        assert analysis['reconciliation_passed']
        assert [r['spec'] for r in controls['cases']]==w.specs('controls')
        assert analysis['raw_ledger_sha256']==w.sha(CONTROLS/'accounting/ledger.json')
        qualified_hash=w.sha(CONTROLS/'analysis.json')
        prior=w.all_history()
        assert not any(r['transport']==TRANSPORT and r['status']!='ready' for r in prior['new'])
        assert out.parent.resolve()==BASE.resolve() and out.name.startswith('full_workflow_live_')
        assert Decimal(prior['guard_usd'])+Decimal('.049')<=50
    else:
        prior=None
    out.mkdir(parents=True,exist_ok=False)
    w.save(out/'preflight.json',{'transport':TRANSPORT,'request_deadline_seconds':60,
        'plan_sha256':w.sha(bundle/'plan.json'),'prior':prior,'parent_case_sha256':plan['parent_case_sha256'],
        'qualifying_control_analysis_sha256':qualified_hash,'mode':'live_model' if mock is None else 'scripted_software'})
    _,headers=w.modal_config() if mock is None else (w.BASE_URL,{'Modal-Key':'OFFLINE_ID','Modal-Secret':'OFFLINE_SECRET'})
    ledger=FirstWireLedger(out/'accounting',scope='full',max_calls=12,max_usd='.588',
        plan_sha256=w.sha(bundle/'plan.json'),authorization=auth,cumulative_guard=w.all_history if mock is None else None)
    ledger.expected_first_sha256='0'*64 if mock=='wrong_wire' else plan['first_wire_sha256']
    client=FinancialByteClient(ledger=ledger,base_url=w.BASE_URL,model=w.MODEL,headers=headers,
        diagnostics=out/'transport_diagnostics',worker_sha256=plan['sources']['endpoint_probe_worker.py'],
        request_timeout=60,max_request_timeout=60,batch_deadline_monotonic=time.monotonic()+1800)
    # Reuse the previously undispatched logical slot, rather than grant a fourth
    # generation in its native turn. Provider records1..105 remain in the parent.
    client.logical_requests=plan['logical_start']
    b=restore_prefix(prefix)
    if mock is not None:client.transport=Mock(b,mock)
    history=[];error=None
    for step in plan['steps']:
        before_calls=ledger.state['calls'];before_logical=client.logical_requests
        complete=True
        try:
            await w.f.native_turn(b,step,client,model=w.MODEL)
            if ledger.state['status']=='halted':raise BudgetError('suffix ledger halted')
        except Exception as exc:
            complete=False;error=type(exc).__name__
        turns_used=client.logical_requests-before_logical
        assert turns_used<=3
        history.append({**step,'generation_attempts':ledger.state['calls']-before_calls,
            'logical_generation_requests':turns_used,'after':w.f.snapshot(b),'complete_turn':complete})
        if not complete:break
    observations=old['observations']+b.protocol.observations
    callbacks=old['callbacks']+b.callback_attempts
    errors=[r for r in callbacks if isinstance(r.get('result'),dict) and
        ('error' in r['result'] or r['result'].get('status') in {'denied','error'})]
    joint,local=b.env._calculate_makespan_and_flow()
    metrics={'care':sum(care(b.env).values()),'failures':sum(b.env.resource_failures.values()),
        'credit':b.env.transfer_rewards,'native_score':joint,'local_sum':sum(local.values()),
        'recurrences':w.recurrences(observations),'callback_errors':len(errors),
        'generation_attempts':105+ledger.state['calls'],'logical_generation_requests':client.logical_requests}
    complete=len(history)==2 and all(t['complete_turn'] for t in history)
    passed=complete and metrics['care']==8 and metrics['failures']==0 and not any(r['pending_patients'] for r in metrics['recurrences'])
    joined={**deepcopy(old),'complete':complete,'passed':passed,'error':error,'metrics':metrics,
        'final':w.f.snapshot(b),'turns':old['turns'][:52]+history,'callbacks':callbacks,
        'observations':observations,'tool_events':old['tool_events']+[asdict(e) for e in b.protocol.tool_events],
        'lineage':{'kind':'derived_prefix_plus_suffix','parent_case_sha256':plan['parent_case_sha256'],
            'parent_ledger_sha256':plan['parent_ledger_sha256'],'suffix_plan_sha256':w.sha(bundle/'plan.json'),
            'raw_client_invocations_including_local_rejection':106+client.logical_requests-105,
            'undispatched_slot106_reused_once':True,'parent_report_stays_unchanged':True}}
    raw=json.dumps(joined,indent=2,sort_keys=True,allow_nan=False).encode()
    archive=out/'derived-full-ordinary-s1.json.gz';archive.write_bytes(gzip.compress(raw,mtime=0))
    assert gzip.decompress(archive.read_bytes())==raw
    result={'mode':'live_model' if mock is None else 'scripted_software','stage':'ordinary_suffix',
        'plan_sha256':w.sha(bundle/'plan.json'),'complete':complete,'passed':bool(passed),'metrics':metrics,
        'suffix_turns':history,'archive':archive.name,'archive_sha256':w.sha(archive),
        'raw_sha256':hashlib.sha256(raw).hexdigest(),'parent_case_sha256':plan['parent_case_sha256'],
        'ledger':ledger.summary(),'retry_audit':audit_retry_ledger(ledger.state,out),
        'new_outward_attempts':ledger.state['calls'],'new_logical_slots':client.logical_requests-105,
        'raw_client_invocations_including_local_rejection':106+client.logical_requests-105,
        'positive_control_analysis_sha256':qualified_hash,'independent_families':1,
        'sample_sd':None,'sample_variance':None,'network_attempts':w.NETWORK,
        'claim_limit':'A continuation of the same seed1, not a replacement/new independent seed or an exposure/repair result.'}
    w.save(out/'results.json',result)
    print(json.dumps({'complete':complete,'passed':bool(passed),'new_calls':ledger.state['calls'],
        'new_logical_slots':client.logical_requests-105,'metrics':metrics}),flush=True)
    return result


async def validate(bundle,out):
    out.mkdir(parents=True,exist_ok=False)
    rows={}
    for mode in ('positive','noop','http_failure','wrong_wire'):
        rows[mode]=await execute(bundle,out/mode,mock=mode)
    assert rows['positive']['complete'] and rows['positive']['passed']
    assert rows['positive']['metrics']['care']==8 and rows['positive']['metrics']['credit']==15
    assert [t['logical_generation_requests'] for t in rows['positive']['suffix_turns']]==[2,3]
    assert rows['noop']['complete'] and rows['noop']['passed'] and rows['noop']['new_outward_attempts']==6
    assert not rows['http_failure']['complete'] and rows['http_failure']['new_outward_attempts']==1
    assert Decimal(rows['http_failure']['ledger']['held_usd'])==Decimal('.049')
    assert not rows['wrong_wire']['complete'] and rows['wrong_wire']['new_outward_attempts']==0
    assert rows['wrong_wire']['ledger']['halt_reason']=='resumed_request_mismatch'
    assert not w.NETWORK
    result={'passed':True,'plan_sha256':w.sha(bundle/'plan.json'),'Results':{
        'per_counterexample':{k:{'complete':v['complete'],'passed':v['passed'],'new_calls':v['new_outward_attempts'],
            'care':v['metrics']['care'],'credit':v['metrics']['credit']} for k,v in rows.items()},
        'positive_control':'exact first wire and native query→one transfer; care remains8/8 and max3logical slots per turn',
        'n_per_counterexample':1,'sample_sd':None,'sample_variance':None},
        'network_attempts':w.NETWORK,'inference_calls':0,'actual_spend_usd':'0','llm_suffix':'unrun'}
    w.save(out/'results.json',result)
    print(json.dumps({'passed':True,'software_cases':4,'network_attempts':w.NETWORK}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','validate','run'])
    parser.add_argument('--bundle',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':asyncio.run(prepare(args.out))
    elif args.command=='validate':asyncio.run(validate(args.bundle,args.out))
    else:
        lock_path=Path(tempfile.gettempdir())/('modal-Hospital-'+hashlib.sha256(str(HERE).encode()).hexdigest()[:16]+'.lock')
        with lock_path.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            asyncio.run(execute(args.bundle,args.out))


if __name__=='__main__':main()
