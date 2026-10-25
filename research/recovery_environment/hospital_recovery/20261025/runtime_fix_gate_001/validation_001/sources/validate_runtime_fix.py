"""Network-denied validation of transport corrections, with retained failures."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
from unittest.mock import patch

network_attempts=[]


def deny_network(event, args):
    if event in {'socket.connect','socket.getaddrinfo','socket.bind','http.client.connect'}:
        network_attempts.append(event)
        raise RuntimeError('network prohibited in correction validator')


sys.addaudithook(deny_network)
original_ipv6=socket.has_ipv6
try:
    socket.has_ipv6=False
    import engagement_pilot as engagement
    from budget_client import BudgetError, BudgetLedger, BudgetedChatClient
    import deadline_transport as transport_module
    from deadline_transport import DeadlineTransport
    import qualification_runtime as runtime
    import request_worker
finally:
    socket.has_ipv6=original_ipv6

HERE=Path(__file__).resolve().parent
KEY='offline-placeholder-credential'


def read(path):
    return json.loads(path.read_text())


class ScriptedDeadline(DeadlineTransport,engagement.MockTransport):
    is_real=False


class FakeProcess:
    def __init__(self,transport,*,reply=None):
        self.transport,self.reply=transport,reply
        self.returncode=None

    def communicate(self,data=None,timeout=None):
        if self.reply is None:
            payload=json.loads(data)['payload']
            native=engagement.MockTransport.post(self.transport,payload,timeout=timeout)
            result={'kind':'reply','status_code':native.status_code,'body':native.body}
        else:
            result=self.reply
        self.returncode=0
        return json.dumps(result),''

    def poll(self):
        return self.returncode


def client_at(path,mode='success',limit=198):
    auth={'approved':True,'scope':'full','max_calls':limit,'max_usd':'10',
          'plan_sha256':'a'*64,'approval_reference':'OFFLINE injected validation only'}
    ledger=BudgetLedger(path/'accounting',scope='full',max_calls=limit,max_usd='10',
                        plan_sha256='a'*64,authorization=auth)
    transport=ScriptedDeadline(authorization=auth,api_key=KEY,expected_plan_sha256='a'*64,
        worker_sha256=runtime.sha(transport_module.WORKER),ledger=ledger,diagnostics=path/'diagnostics')
    engagement.MockTransport.__init__(transport,mode)
    return BudgetedChatClient(ledger=ledger,transport=transport),transport


async def validate(output):
    output.mkdir(parents=True,exist_ok=False)
    (output/'sources').mkdir()
    for name in (*runtime.SOURCES,'validate_runtime_fix.py'):
        (output/'sources'/name).write_bytes((HERE/name).read_bytes())
    checks={}
    data={'kind':'unpaid correction gate','checks':checks,'provider_calls':0,
          'credential_lookups':0,'actual_spend_usd':'0'}
    try:
        engagement.verify_bundle(runtime.ORIGINAL)
        roots=await engagement.verify_initial_inputs(runtime.ORIGINAL)
        client,transport=client_at(output/'success')
        with patch.object(transport_module.subprocess,'Popen',lambda *a,**k:FakeProcess(transport)):
            cases,summary=await engagement.execute(client,output/'success',roots)
        assert summary['qualification_passed'] and len(cases)==12 and client.ledger.state['calls']==162
        old=read(HERE/'20261025/engagement_gate_001/success_pipeline/accounting/ledger.json')
        assert [r['payload'] for r in client.ledger.state['records']]==[r['payload'] for r in old['records']]
        assert len(list((output/'success/diagnostics').glob('*.json')))==162
        checks['unchanged162payloads_6plus6positive_pipeline']=True
        data['scripted_success']=summary

        client,transport=client_at(output/'noop','noop')
        with patch.object(transport_module.subprocess,'Popen',lambda *a,**k:FakeProcess(transport)):
            cases,summary=await engagement.execute(client,output/'noop',roots)
        assert len(cases)==6 and not any(r['passed'] for r in cases) and client.ledger.state['calls']==54
        assert all(x['spec']['kind']=='positive' for x in cases) and len(summary['unstarted_cases'])==6
        checks['all6behavioral_failures_retained_noordinary']=True
        data['scripted_noop']=summary

        class OpenError:
            def open(self,*a,**k):
                raise urllib.error.URLError(TimeoutError(KEY))
        typed=request_worker.perform({},KEY,1,opener=OpenError())
        assert typed['stage']=='open' and typed['exception_type']=='URLError' and typed['cause_type']=='TimeoutError'
        assert KEY not in json.dumps(typed)
        class ReadError:
            code=200
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self):raise ConnectionResetError(104,KEY)
        class ReadOpener:
            def open(self,*a,**k):return ReadError()
        read_failure=request_worker.perform({},KEY,1,opener=ReadOpener())
        assert read_failure['stage']=='read' and read_failure['exception_type']=='ConnectionResetError'
        assert read_failure['errno']==104 and read_failure['http_status']==200 and KEY not in json.dumps(read_failure)
        checks['typed_open_read_exceptions_preserved_without_message']=True
        data['worker_exception_controls']=[typed,read_failure]

        first=read(runtime.ORIGINAL/'initial_inputs.json')['engagement-positive-s0']
        def generate(client):
            params={'model':engagement.MODEL_ID,'tools':deepcopy(first['tools']),'seed':0,'max_tokens':1024}
            try:
                client.generate_response(deepcopy(first['messages']),params)
            except BudgetError:
                return
            raise AssertionError('expected global transport stop')

        for name,reply in [('typed_error',typed),('http429',{'kind':'reply','status_code':429,'body':{'error':'synthetic overload'}})]:
            client,transport=client_at(output/name)
            with patch.object(transport_module.subprocess,'Popen',lambda *a,**k:FakeProcess(transport,reply=reply)):
                generate(client)
            state=client.ledger.state
            assert state['calls']==1 and state['status']=='halted' and state['held_usd']=='0.049'
            diagnostic=read(output/name/'diagnostics/call-0001.json')
            assert KEY not in json.dumps(diagnostic)
            if name=='typed_error':assert diagnostic['exception_type']=='URLError'
            else:assert diagnostic['http_status']==429 and state['records'][0]['http_status']==429
        checks['typed_failure_and_HTTP429_stop_once_hold_unknown']=True

        real_popen=subprocess.Popen
        durations=[]
        for trial in range(3):
            client,transport=client_at(output/f'deadline-{trial}')
            client.request_timeout=1
            def sleeping_child(*a,**kwargs):
                return real_popen([sys.executable,'-c','import sys,time;sys.stdin.read();time.sleep(5)'],**kwargs)
            started=time.monotonic()
            with patch.object(transport_module.subprocess,'Popen',sleeping_child):
                generate(client)
            durations.append(time.monotonic()-started)
            diagnostic=read(output/f'deadline-{trial}'/'diagnostics/call-0001.json')
            assert diagnostic['category']=='whole_request_deadline' and diagnostic['child_reaped']
            assert diagnostic['child_exit_code']!=0 and client.ledger.state['calls']==1
            assert client.ledger.state['held_usd']=='0.049' and client.ledger.state['status']=='halted'
        checks['3real_child_deadlines_killed_reaped_no_retry']=True
        data['deadline_control']={'repeat_indices':list(range(3)),'elapsed_seconds':durations,
            'mean':statistics.mean(durations),'sample_sd':statistics.stdev(durations),
            'sample_variance':statistics.variance(durations),'test_timeout_seconds':1,
            'production_timeout_seconds':60,'positive_control':'successful full scripted pipeline',
            'limit':'Active host scheduling only; no deadline can execute while host is suspended.'}
        assert request_worker.NoRedirect().redirect_request(None,None,302,'',{},'https://example.org') is None
        checks['worker_no_redirects']=True
        oldhash=read(HERE/'20261025/engagement_gate_001/prior_evidence_hashes.json')
        assert all(runtime.sha(HERE/path)==expected for path,expected in oldhash.items())
        engagement.verify_bundle(runtime.ORIGINAL)
        checks['frozen7_42_and849prior_files_unchanged']=True
        assert not network_attempts
        checks['zero_network_provider_or_real_credential_access']=True
        data.update(passed=len(checks),total=len(checks),fake_outward_attempts=221,
                    network_attempts=network_attempts,prior_artifact_count=len(oldhash))
    except Exception as error:
        data.update(status='failed',error_type=type(error).__name__,detail=str(error))
        engagement.save(output/'results.json',data)
        raise
    engagement.save(output/'results.json',data)
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    result=asyncio.run(validate(parser.parse_args().out))
    print(json.dumps({k:result[k] for k in ('passed','total','fake_outward_attempts','provider_calls','actual_spend_usd')}))
