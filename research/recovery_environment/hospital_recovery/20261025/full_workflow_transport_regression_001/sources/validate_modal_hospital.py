"""Unpaid native qualification and accounting controls for the selected Modal route."""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch

network=[]
def deny(event,args):
    if event in {'socket.connect','socket.getaddrinfo','socket.bind','http.client.connect'}:
        network.append(event);raise RuntimeError('no network in Modal validator')
sys.addaudithook(deny)
saved_ipv6=socket.has_ipv6
try:
    socket.has_ipv6=False
    import modal_hospital_runtime as runtime
    import modal_hospital_client as adapter
    import modal_request_worker as worker
    import engagement_pilot as engagement
    from budget_client import BudgetError,BudgetLedger,TransportReply
finally:
    socket.has_ipv6=saved_ipv6

HERE=Path(__file__).resolve().parent


class FakeModal(engagement.MockTransport):
    def post(self,payload,*,timeout):
        reply=super().post(payload,timeout=timeout)
        body=deepcopy(reply.body);body['model']=runtime.MODEL
        body['usage'].pop('cost',None)
        return TransportReply(reply.status_code,body)


def make(path,transport=None):
    authorization={'approved':True,'scope':'full','max_calls':198,'max_usd':'10',
                   'plan_sha256':'b'*64,'approval_reference':'OFFLINE fake authorization only'}
    ledger=BudgetLedger(path/'accounting',scope='full',max_calls=198,max_usd='10',
                       plan_sha256='b'*64,authorization=authorization)
    client=adapter.ModalHospitalClient(ledger,runtime.EXPECTED_BASE,runtime.MODEL,
        {'Modal-Key':'offline-proxy-id','Modal-Secret':'offline-proxy-secret'},
        path/'diagnostics',runtime.sha(HERE/'modal_request_worker.py'))
    if transport is not None:client.transport=transport
    return client


async def validate(output):
    output.mkdir(parents=True,exist_ok=False);(output/'sources').mkdir()
    for name in (*runtime.SOURCES,'validate_modal_hospital.py'):
        (output/'sources'/name).write_bytes((HERE/name).read_bytes())
    checks={};result={'kind':'unpaid Modal adapter validation','checks':checks,
                      'provider_calls':0,'real_credential_lookups':0,'actual_spend_usd':'0'}
    try:
        roots,inputs=await runtime.task_inputs()
        assert len(roots)==len(inputs)==12
        checks['all12task_inputs_and_roots_equal_original']=True
        original_turn=engagement.turn
        engagement.turn=runtime.modal_turn
        try:
            transport=FakeModal();client=make(output/'success',transport)
            cases,summary=await engagement.execute(client,output/'success',roots)
            assert len(cases)==12 and summary['qualification_passed'] and len(transport.posts)==162
            old=json.loads((HERE/'20261025/engagement_gate_001/success_pipeline/accounting/ledger.json').read_text())
            for new,prior in zip(transport.posts,old['records']):
                assert new['messages']==prior['payload']['messages'] and new['tools']==prior['payload']['tools']
                assert new['model']==runtime.MODEL and not any(k in new for k in ('seed','provider','reasoning'))
                assert new['reasoning_effort']=='none' and new['max_tokens']==1024
            assert client.ledger.state['reported_cost_missing']==162
            assert client.ledger.state['reported_cost_total_usd'] is None
            assert client.ledger.state['accounting_basis']==adapter.BASIS
            checks['162same_task_payloads_and_reference_not_actual_cost']=True
            result['scripted_positive_pipeline']=summary
            transport=FakeModal('noop');client=make(output/'noop',transport)
            cases,summary=await engagement.execute(client,output/'noop',roots)
            assert len(cases)==6 and not any(r['passed'] for r in cases) and len(transport.posts)==54
            assert len(summary['unstarted_cases'])==6
            checks['6behavioral_failures_retained_noordinary']=True
            result['scripted_negative_controls']=summary
        finally:
            engagement.turn=original_turn
        first=inputs['engagement-positive-s0']
        def attempt(client):
            try:client.generate_response(first['messages'],{'model':runtime.MODEL,'tools':first['tools'],'seed':0})
            except BudgetError:return
            raise AssertionError('expected terminal failure')
        class Failure:
            is_real=False
            def __init__(self,kind):self.kind=kind;self.posts=0
            def post(self,payload,*,timeout):
                self.posts+=1
                if self.kind=='transport':raise TimeoutError('offline-proxy-secret')
                return TransportReply(402,{'error':{'message':'synthetic unavailable budget'}})
        for kind in ('transport','http402'):
            transport=Failure(kind);client=make(output/kind,transport);attempt(client)
            assert transport.posts==1 and client.ledger.state['calls']==1
            assert client.ledger.state['status']=='halted' and client.ledger.state['held_usd']=='0.049'
            assert client.ledger.state['reported_cost_total_usd'] is None
        checks['HTTP402_and_transport_stop_once_unknown_charge']=True
        excessive=TransportReply(200,{'id':'offline-high-cost','model':runtime.MODEL,
            'choices':[{'message':{'role':'assistant','content':'offline'}}],
            'usage':{'prompt_tokens':100,'completion_tokens':20,'cost':.05}})
        reason,estimate,reported=adapter.validate_reply(excessive)
        assert reason=='overreservation_reported_cost' and estimate is None and str(reported)=='0.05'
        checks['reported_cost_above_reservation_rejected_and_retained']=True
        client=make(output/'expired',Failure('transport'));client.batch_deadline_monotonic=time.monotonic()-1
        attempt(client);assert client.ledger.state['calls']==0 and client.transport.posts==0
        checks['batch_deadline_blocks_before_reservation']=True
        client=make(output/'deadline');client.request_timeout=1
        real_popen=subprocess.Popen
        def sleeping(*args,**kwargs):
            return real_popen([sys.executable,'-c','import sys,time;sys.stdin.read();time.sleep(5)'],**kwargs)
        started=time.monotonic()
        with patch.object(adapter.subprocess,'Popen',sleeping):attempt(client)
        diagnostic=json.loads((output/'deadline/diagnostics/call-0001.json').read_text())
        assert diagnostic['category']=='whole_request_deadline' and diagnostic['child_reaped']
        assert client.ledger.state['held_usd']=='0.049' and 'offline-proxy-secret' not in json.dumps(diagnostic)
        result['deadline_positive_control']={'elapsed_seconds':time.monotonic()-started,'n':1,'sample_sd':None,'sample_variance':None,'expected':'one killed/reaped child, unknown reservation held','observed_pass':True}
        checks['real_child_deadline_reaped_and_diagnostics_safe']=True
        assert worker.NoRedirect().redirect_request(None,None,302,'',{},'https://example.org') is None
        wrong=worker.perform({},'https://example.org',{'Modal-Key':'x','Modal-Secret':'y'},1)
        assert wrong['kind']=='transport_error' and wrong['stage']=='validate'
        checks['worker_refuses_other_endpoints_and_redirects']=True
        engagement.verify_bundle(runtime.ORIGINAL)
        oldhash=json.loads((HERE/'20261025/engagement_gate_001/prior_evidence_hashes.json').read_text())
        assert all(runtime.sha(HERE/path)==expected for path,expected in oldhash.items())
        assert not network
        checks['7frozen_42native_849prior_unchanged_zero_network']=True
        result.update(passed=len(checks),total=len(checks),fake_attempts=219,
                      deadline_pre_generation_refusal=1,network_attempts=network)
    except Exception as error:
        result.update(status='failed',error_type=type(error).__name__,detail=str(error))
        engagement.save(output/'results.json',result);raise
    engagement.save(output/'results.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    result=asyncio.run(validate(parser.parse_args().out))
    print(json.dumps({k:result[k] for k in ('passed','total','fake_attempts','provider_calls','actual_spend_usd')}))
