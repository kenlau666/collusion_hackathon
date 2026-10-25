"""Network-denied timeout-retry controls through real native tool dispatch."""
import argparse
import asyncio
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket
import shutil
import subprocess
import sys
from unittest.mock import patch

NETWORK = []
def deny(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        NETWORK.append(event)
        raise RuntimeError('network denied in timeout retry controls')
sys.addaudithook(deny)
ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False
    import full_workflow as f
    from budget_client import BudgetError
    from modal_hospital_client import BASE_URL, MODEL
    from timeout_retry_client import TimeoutRetryClient, TimeoutRetryLedger, POLICY, DIRECTIVE, encoded
finally:
    socket.has_ipv6 = ipv6

HERE = Path(__file__).resolve().parent
MODES = ('success_no_timeout', 'timeout_then_success', 'socket_timeout_then_success', 'two_timeouts',
         'http_failure', 'malformed', 'blocked_retry_budget', 'call_limit', 'dollar_limit', 'mutation', 'wire_order_mutation')


async def main(out):
    out.mkdir(parents=True, exist_ok=False)
    plan = {'cases': list(MODES), 'policy': POLICY, 'request_deadline_seconds_test': .2,
        'positive_control': 'timeout then valid reply executes one native transfer, not two',
        'limits': 'one retry only; identical payload; every failed hold retained; no non-timeout retry',
        'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                    (Path(__file__).resolve(), HERE/'timeout_retry_client.py', HERE/'traced_modal_client.py')}}
    (out/'plan.json').write_text(json.dumps(plan, indent=2, sort_keys=True)+'\n')
    (out/'sources').mkdir()
    for name in plan['sources']:
        shutil.copyfile(HERE/name, out/'sources'/name)
    plan_hash = hashlib.sha256((out/'plan.json').read_bytes()).hexdigest()
    auth = {'approved': True, 'scope': 'full', 'max_calls': 198, 'max_usd': '10',
        'plan_sha256': plan_hash, 'approval_reference': DIRECTIVE,
        'timeout_retry_policy': POLICY, 'retry_approval_reference': DIRECTIVE}
    reports = []
    real_popen = subprocess.Popen
    for mode in MODES:
        directory = out/mode
        guard_calls = []
        def guard():
            guard_calls.append(1)
            return {'guard_usd': '49.96' if mode == 'blocked_retry_budget' and len(guard_calls)>1 else '0'}
        class MutationLedger(TimeoutRetryLedger):
            def reserve(self, payload, payload_bytes):
                if self.attempt_context.get('attempt_index') == 1:
                    payload = deepcopy(payload)
                    if mode == 'wire_order_mutation':
                        payload = dict(reversed(list(payload.items())))
                    else:
                        payload['temperature'] = .1
                return super().reserve(payload, payload_bytes)
        cls = MutationLedger if mode in ('mutation','wire_order_mutation') else TimeoutRetryLedger
        ledger = cls(directory/'accounting', scope='full', max_calls=1 if mode=='call_limit' else 198,
            max_usd='.049' if mode=='dollar_limit' else '10', authorization=auth,
            plan_sha256=plan_hash, cumulative_guard=guard)
        client = TimeoutRetryClient(ledger=ledger, base_url=BASE_URL, model=MODEL,
            headers={'Modal-Key':'OFFLINE_TEST_ID','Modal-Secret':'OFFLINE_TEST_SECRET'},
            diagnostics=directory/'diagnostics', request_timeout=.2,
            worker_sha256=hashlib.sha256((HERE/'endpoint_probe_worker.py').read_bytes()).hexdigest())
        branch = f.root(0)
        actor = branch.precedence[0]+'_Surgery'
        source = branch.env.agents_map[actor]['hospital']
        destination = next(h for h in branch.env.hospital_names if h != source)
        args = f.move_args(destination)
        before = deepcopy(branch.env.inventory)
        launches = []
        def fake(*launch_args, **kwargs):
            launches.append(1)
            attempt = len(launches)
            pause = mode in ('two_timeouts','blocked_retry_budget','call_limit','dollar_limit','mutation','wire_order_mutation') or mode=='timeout_then_success' and attempt==1
            if pause:
                code = ("import sys,time,os,json;from pathlib import Path;sys.stdin.read();"
                    "Path(os.environ['MODAL_PROGRESS_PATH']).write_text(json.dumps({'stage':'request_sent_waiting_headers','events':[],'body_bytes':0}));time.sleep(4)")
            elif mode=='socket_timeout_then_success' and attempt==1:
                code = "import sys,json;sys.stdin.read();print(json.dumps({'kind':'transport_error','exception_type':'TimeoutError','errno':None}))"
            elif mode=='malformed':
                code = "import sys;sys.stdin.read();print('not JSON')"
            else:
                message = {'role':'assistant','content':'offline native transfer control',
                    'tool_calls':[{'id':'control-call','type':'function','function':{
                        'name':'transfer_resources','arguments':json.dumps(args)}}]}
                response = {'kind':'reply','status_code':429 if mode=='http_failure' else 200,
                    'body':{'id':'offline-reply','model':MODEL,'choices':[{'message':message,'finish_reason':'tool_calls'}],
                            'usage':{'prompt_tokens':100,'completion_tokens':20}}}
                code = 'import sys;sys.stdin.read();print('+repr(json.dumps(response))+')'
            return real_popen([sys.executable,'-c',code], **kwargs)
        with patch('traced_modal_client.subprocess.Popen', fake):
            try:
                await f.native_turn(branch, {'actor':actor,'phase':'planning','iteration':1,'turn_index':0}, client, model=MODEL)
            except BudgetError:
                assert mode not in ('success_no_timeout','timeout_then_success','socket_timeout_then_success')
        positive = mode in ('success_no_timeout','timeout_then_success','socket_timeout_then_success')
        callbacks = [x for x in branch.callback_attempts if x['tool']=='transfer_resources']
        if positive:
            assert len(callbacks)==1 and client.logical_requests==1 and len(launches)==(1 if mode=='success_no_timeout' else 2)
            assert branch.env.inventory[source]['IV_Kits']==before[source]['IV_Kits']-1
            assert branch.env.inventory[destination]['IV_Kits']==before[destination]['IV_Kits']+1
            assert branch.env.transfer_rewards==15 and ledger.state['status']=='ready'
            assert [r['status'] for r in ledger.state['records']]==(['settled'] if mode=='success_no_timeout' else ['failed','settled'])
            if mode!='success_no_timeout':
                assert ledger.state['records'][0]['payload']==ledger.state['records'][1]['payload']
                assert ledger.state['records'][0]['payload_sha256']==ledger.state['records'][1]['payload_sha256']
                assert ledger.state['records'][0]['wire_payload_json']==ledger.state['records'][1]['wire_payload_json']
                assert ledger.state['records'][0]['wire_payload_sha256']==ledger.state['records'][1]['wire_payload_sha256']
                assert ledger.state['records'][1]['retry_of_call_id']==1
        else:
            assert not callbacks and branch.env.inventory==before and ledger.state['status']=='halted'
            assert len(launches)==(2 if mode=='two_timeouts' else 1)
        expected_calls = 2 if mode in ('timeout_then_success','socket_timeout_then_success','two_timeouts') else 1
        assert ledger.state['calls']==expected_calls
        assert Decimal(ledger.state['held_usd'])==Decimal('.049')*(0 if mode=='success_no_timeout' else (2 if mode=='two_timeouts' else 1))
        assert client.logical_requests==1
        if mode in ('mutation','wire_order_mutation'): assert ledger.state['halt_reason']=='retry_payload_or_link_mismatch'
        if mode=='blocked_retry_budget': assert ledger.state['halt_reason']=='cumulative_dollar_limit'
        if mode=='call_limit': assert ledger.state['halt_reason']=='call_limit'
        if mode=='dollar_limit': assert ledger.state['halt_reason']=='dollar_limit'
        reports.append({'mode':mode,'passed':True,'outward_attempts':ledger.state['calls'],
            'logical_generations':client.logical_requests,'native_transfers':len(callbacks),
            'held_simulated_usd':ledger.state['held_usd'],'ledger_status':ledger.state['status']})
    assert not NETWORK
    result={'passed':True,'plan_sha256':plan_hash,'cases':reports,'network_attempts':NETWORK,
        'positive_controls':'whole-request and socket timeout then exact retry produce one native transfer each',
        'sample_sd':None,'sample_variance':None,'n_per_counterexample':1,
        'inference_calls':0,'real_spend_usd':'0','llm_behavior_established':False}
    (out/'results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    asyncio.run(main(parser.parse_args().out))
