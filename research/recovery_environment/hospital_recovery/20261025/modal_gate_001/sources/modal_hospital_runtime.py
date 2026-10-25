"""User-selected existing Modal endpoint; unchanged native Hospital qualification."""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import tempfile
import time
from urllib.parse import urlsplit
import urllib.request

import certifi
from dotenv import dotenv_values

import engagement_pilot as engagement
from budget_client import BudgetError,BudgetLedger,_approved
from branch_runtime import ScriptedChatClient
from llm_server.clients.together_client import _convert_tools

HERE=Path(__file__).resolve().parent
BASE=HERE/'20261025'
ORIGINAL=BASE/'engagement_gate_001/bundle'
DIRECTIVE=BASE/'modal_qualification_authorization.json'
MODEL='deepseek-ai/DeepSeek-V4.1-Flash'
EXPECTED_BASE='https://kenlauhong2015--ep-deepseek-v4-1-flash-server.us-west.modal.direct/v1'
SOURCES=('modal_hospital_client.py','modal_request_worker.py','modal_hospital_runtime.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config():
    values=dotenv_values(HERE.parents[2]/'compute.env')
    base=(values.get('MODAL_ENDPOINT_BASE_URL') or '').strip().rstrip('/')
    parsed=urlsplit(base)
    if (parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.modal.direct')
        or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path!='/v1'
        or values.get('MODAL_ENDPOINT_MODEL')!=MODEL or base!=EXPECTED_BASE):
        raise BudgetError('configured Modal endpoint/model mismatch')
    headers={}
    bearer=values.get('MODAL_ENDPOINT_API_KEY') or values.get('MODAL_PROXY_TOKEN')
    token_id,secret=values.get('MODAL_PROXY_TOKEN_ID'),values.get('MODAL_PROXY_TOKEN_SECRET')
    if bool(token_id)!=bool(secret):raise BudgetError('incomplete Modal proxy credential pair')
    if bearer:headers['Authorization']='Bearer '+bearer
    if token_id:headers.update({'Modal-Key':token_id,'Modal-Secret':secret})
    if not headers:raise BudgetError('no configured Modal authentication')
    return base,headers


def history():
    paths=[BASE/'controls_live_001/accounting/ledger.json',BASE/'main_live_001/accounting/ledger.redacted.json']
    for pattern in ('engagement_live_*','modal_engagement_live_*'):
        for directory in sorted(BASE.glob(pattern)):
            if not directory.is_dir():continue
            public=directory/'accounting/ledger.redacted.json'
            path=public if public.exists() else directory/'accounting/ledger.json'
            if not path.exists():raise BudgetError('existing run lacks its ledger')
            paths.append(path)
    rows=[]
    for path in paths:
        data=json.loads(path.read_text())
        rows.append({'path':str(path),'sha256':sha(path),'spent_or_reference_usd':data['spent_usd'],
                     'held_usd':data['held_usd'],'accounting_basis':data.get('accounting_basis','reported provider monetary cost plus unknown reservations')})
    return {'ledgers':rows,'conservative_guard_usd':str(sum((Decimal(x['spent_or_reference_usd'])+Decimal(x['held_usd']) for x in rows),Decimal(0))),
            'actual_modal_charges_verified':False}


async def modal_turn(branch,step,client):
    if branch.engagement_spec['kind']=='positive':
        branch.env.prompts.instruction=f"Actor {step['actor']}: call {step['tool']} with arguments "+json.dumps(step['arguments'],sort_keys=True)+'.'
    if isinstance(getattr(client,'transport',None),engagement.MockTransport):
        client.transport.branch,client.transport.step=branch,step
    agent=engagement.MainAgent(client=client,name=step['actor'],model_name=MODEL,
        max_conversation_steps=3,environment_name='HospitalEnvironment',
        generation_params={'seed':step['sampling_seed'],'max_tokens':1024,'temperature':0,
                           'reasoning':{'enabled':False}})
    agent.study_branch,agent.study_turn=branch,step['turn_index']
    context=branch.env.build_agent_context(step['actor'],step['phase'],step['iteration'])
    if step['phase']=='planning':
        return await branch.protocol.agent_planning_turn(agent,step['actor'],context,branch.env,step['iteration'],1)
    return await branch.protocol.agent_execution_turn(agent,step['actor'],context,branch.env,step['iteration'])


async def task_inputs():
    engagement.verify_bundle(ORIGINAL)
    roots=await engagement.verify_initial_inputs(ORIGINAL)
    old=json.loads((ORIGINAL/'initial_inputs.json').read_text())
    inputs={}
    for spec in engagement.matrix():
        branch,root,steps=await engagement.make_case(spec)
        client=ScriptedChatClient()
        await modal_turn(branch,steps[0],client)
        request=client.requests[0]
        messages,tools=request['input'],_convert_tools(request['params']['tools'])
        if (messages!=old[spec['id']]['messages'] or tools!=old[spec['id']]['tools']
            or engagement.digest(root)!=engagement.digest(roots[spec['id']])):
            raise BudgetError('Modal task input differs from old task')
        inputs[spec['id']]={'messages':messages,'tools':tools,'model':MODEL,
                            'local_sampling_seed':steps[0]['sampling_seed'],'api_seed_forwarded':False}
    return roots,inputs


def validate_output(output):
    if (output.resolve().parent!=BASE.resolve() or not re.fullmatch(r'modal_engagement_live_[0-9]{3}',output.name)
        or output.exists()):raise BudgetError('fresh tracked Modal run output required')


async def prepare(output):
    roots,inputs=await task_inputs()
    directive=json.loads(DIRECTIVE.read_text())
    if directive.get('approved') is not True or directive.get('openrouter_inference_allowed') is not False:
        raise BudgetError('explicit Modal directive required')
    prior=history()
    if Decimal(prior['conservative_guard_usd'])+10>50:raise BudgetError('cumulative guard insufficient')
    output.mkdir(parents=True,exist_ok=False);(output/'sources').mkdir()
    for name in SOURCES:shutil.copyfile(HERE/name,output/'sources'/name)
    engagement.save(output/'roots.json',roots);engagement.save(output/'initial_inputs.json',inputs)
    plan={'stage':'user_selected_modal_Hospital_qualification','approved':False,'model':MODEL,'endpoint':EXPECTED_BASE,
          'original_plan_sha256':sha(ORIGINAL/'plan.json'),'directive_sha256':sha(DIRECTIVE),
          'max_calls':198,'max_usd':'10','accounting_basis':'published Modal Shared Endpoint reference token estimate; actual charges unverified',
          'input_reference_usd_per_million':'0.30','output_reference_usd_per_million':'1.20',
          'max_reported_input_tokens':131072,'max_output_tokens':1024,'temperature':0,
          'reasoning_effort':'none','api_seed_forwarded':False,'conversation_cap':3,
          'request_deadline_seconds':60,'batch_deadline_seconds':1800,'main_study_started':False,
          'cases':engagement.matrix(),'prior_accounting':prior,
          'sources':{name:sha(HERE/name) for name in SOURCES},
          'files':{'roots.json':sha(output/'roots.json'),'initial_inputs.json':sha(output/'initial_inputs.json')}}
    engagement.save(output/'plan.json',plan)
    engagement.save(output/'authorization.json',{'approved':True,'scope':'full','max_calls':198,'max_usd':'10',
        'plan_sha256':sha(output/'plan.json'),'approval_reference':'Standing qualification authorization and explicit human answer: Use the configured Modal endpoint.',
        'directive_sha256':sha(DIRECTIVE),'accounting_basis':plan['accounting_basis']})
    return plan


async def preflight(bundle,output):
    validate_output(output)
    plan=json.loads((bundle/'plan.json').read_text())
    if (plan['model']!=MODEL or plan['endpoint']!=EXPECTED_BASE or plan['max_calls']!=198 or plan['max_usd']!='10'
        or plan['directive_sha256']!=sha(DIRECTIVE) or plan['original_plan_sha256']!=engagement.verify_bundle(ORIGINAL)
        or plan['prior_accounting']!=history() or plan['main_study_started'] is not False
        or plan['cases']!=engagement.matrix() or plan['conversation_cap']!=3
        or plan['request_deadline_seconds']!=60 or plan['batch_deadline_seconds']!=1800
        or set(plan['sources'])!=set(SOURCES) or set(plan['files'])!={'roots.json','initial_inputs.json'}
        or plan['max_reported_input_tokens']!=131072 or plan['max_output_tokens']!=1024
        or plan['temperature']!=0 or plan['reasoning_effort']!='none' or plan['api_seed_forwarded'] is not False):
        raise BudgetError('Modal plan mismatch')
    for name,expected in plan['sources'].items():
        if sha(HERE/name)!=expected or sha(bundle/'sources'/name)!=expected:raise BudgetError('Modal source mismatch')
    for name,expected in plan['files'].items():
        if sha(bundle/name)!=expected:raise BudgetError('Modal bundle mismatch')
    authorization=json.loads((bundle/'authorization.json').read_text())
    approved=_approved(authorization,sha(bundle/'plan.json'))
    if approved['scope']!='full' or approved['max_calls']!=198 or Decimal(approved['max_usd'])!=10:
        raise BudgetError('Modal qualification authorization bounds mismatch')
    roots,inputs=await task_inputs()
    if roots!=json.loads((bundle/'roots.json').read_text()) or inputs!=json.loads((bundle/'initial_inputs.json').read_text()):
        raise BudgetError('Modal roots/input reconstruction mismatch')
    # Modal metadata needs authentication; only now read Modal-specific values.
    base,headers=config()
    from request_worker import NoRedirect
    opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
    with opener.open(urllib.request.Request(base+'/models',headers=headers),timeout=20) as response:
        metadata=json.load(response)
    if MODEL not in [m.get('id') for m in metadata.get('data',[])]:raise BudgetError('configured Modal model not listed')
    return plan,authorization,roots,base,headers,metadata


async def run(bundle,output):
    lock_path=Path(tempfile.gettempdir())/('modal-Hospital-'+hashlib.sha256(str(HERE).encode()).hexdigest()[:16]+'.lock')
    with lock_path.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise BudgetError('another Modal qualification is active') from None
        plan,authorization,roots,base,headers,metadata=await preflight(bundle,output)
        from modal_hospital_client import ModalHospitalClient
        output.mkdir(parents=True,exist_ok=False)
        engagement.save(output/'preflight.json',{'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'plan_sha256':sha(bundle/'plan.json'),'model':MODEL,'endpoint':base,
            'authentication_header_names':list(headers),'metadata':metadata,
            'prior_accounting':plan['prior_accounting'],'actual_Modal_charges_verified':False})
        ledger=BudgetLedger(output/'accounting',scope='full',max_calls=198,max_usd='10',
            plan_sha256=sha(bundle/'plan.json'),authorization=authorization)
        client=ModalHospitalClient(ledger=ledger,base_url=base,model=MODEL,headers=headers,
            diagnostics=output/'transport_diagnostics',worker_sha256=plan['sources']['modal_request_worker.py'],
            request_timeout=60,batch_deadline_monotonic=time.monotonic()+1800)
        original_turn=engagement.turn
        engagement.turn=modal_turn
        try:return await engagement.execute(client,output,roots)
        finally:engagement.turn=original_turn


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='prepare':asyncio.run(prepare(args.out));raise SystemExit(0)
        _,summary=asyncio.run(run(args.bundle,args.out));raise SystemExit(0 if summary['qualification_passed'] else 2)
    except (BudgetError,OSError,ValueError):
        print(json.dumps({'status':'stopped','error_type':'Modal_runtime_or_transport_failure'}));raise SystemExit(1)
