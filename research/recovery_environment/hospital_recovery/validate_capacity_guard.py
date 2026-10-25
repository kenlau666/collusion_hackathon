"""Network-denied capacity-bound counterexamples and old-request equivalence."""
import argparse
from decimal import Decimal
import hashlib
import json
import logging
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

NETWORK = []
def deny(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
        NETWORK.append(event);raise RuntimeError('network denied in capacity-guard audit')
sys.addaudithook(deny)
ipv6=socket.has_ipv6
try:
    socket.has_ipv6=False
    import capacity_guard_client as c
    from modal_hospital_client import ModalHospitalClient, MODEL, BASE_URL, validate_reply
    from timeout_retry_client import TimeoutRetryLedger, POLICY, DIRECTIVE, encoded
    from budget_client import BudgetError, TransportReply
    from analyze_full_workflow import audit_retry_ledger
    import diagnose_prompt_capacity as diagnostic
finally:
    socket.has_ipv6=ipv6
logging.disable(logging.CRITICAL)
HERE=Path(__file__).resolve().parent
BASE=HERE/'20261025'


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    source_names=('validate_capacity_guard.py','capacity_guard_client.py','modal_hospital_client.py',
        'timeout_retry_client.py','diagnose_prompt_capacity.py')
    plan={'positive':'all316 prior native request bodies accepted identically; rejected body accepted within reservation',
        'negative':'legacy guard still rejects blocked body; financial byte boundary+1 and input token131073 rejected',
        'sources':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in source_names},
        'policy':c.POLICY,'inference_allowed':False,'paid_calls':0}
    diagnostic.save(out/'plan.json',plan)
    auth={'approved':True,'scope':'full','max_calls':198,'max_usd':'10','plan_sha256':'c'*64,
        'approval_reference':'OFFLINE capacity counterexamples only','timeout_retry_policy':POLICY,
        'retry_approval_reference':DIRECTIVE,'capacity_guard_policy':c.POLICY}
    ledger=TimeoutRetryLedger(out/'bounds',scope='full',max_calls=198,max_usd='10',
        plan_sha256='c'*64,authorization=auth)
    client=c.FinancialByteClient(ledger=ledger,base_url=BASE_URL,model=MODEL,
        headers={'Modal-Key':'OFFLINE_ID','Modal-Secret':'OFFLINE_SECRET'},diagnostics=out/'diagnostics',
        worker_sha256=hashlib.sha256((HERE/'endpoint_probe_worker.py').read_bytes()).hexdigest())
    legacy=object.__new__(ModalHospitalClient)
    legacy.ledger=SimpleNamespace(halt=lambda reason:None)
    audited=[]
    for name in ('full_workflow_live_controls_retry1_001','full_workflow_live_ordinary_retry1_s0_001',
                 'full_workflow_live_ordinary_retry1_s1_001'):
        path=BASE/name/'accounting/ledger.json';data=json.loads(path.read_text())
        for record in data['records']:
            wire=record['wire_payload_json'].encode();payload=record['payload']
            old=legacy._payload_bound(payload,wire);new=client._payload_bound(payload,wire)
            assert old==new==record['conservative_prompt_bound']
            assert record['usage']['prompt_tokens']<=new
            assert encoded(json.loads(wire))==wire
        audited.append({'path':str(path.relative_to(HERE)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'requests':len(data['records'])})
    assert sum(x['requests'] for x in audited)==316 and ledger.state['calls']==0
    blocked=(BASE/'full_workflow_live_ordinary_retry1_s1_001/payload_audit/rejected_wire.json').read_bytes()
    payload=json.loads(blocked)
    try:legacy._payload_bound(payload,blocked)
    except BudgetError:pass
    else:raise AssertionError('legacy default changed')
    assert client._payload_bound(payload,blocked)==133100
    maximum=Decimal(133100)*c.INPUT_RATE+1024*c.OUTPUT_RATE
    assert maximum==Decimal('.04115880') and maximum<Decimal('.049')
    template={'model':MODEL,'messages':[{'role':'user','content':''}],'max_tokens':1024}
    overhead=len(encoded(template))+512*2
    template['messages'][0]['content']='x'*(c.MAX_PADDED_BYTES-overhead)
    assert client._payload_bound(template,encoded(template))==c.MAX_PADDED_BYTES==159237
    template['messages'][0]['content']+='x'
    try:client._payload_bound(template,encoded(template))
    except BudgetError:pass
    else:raise AssertionError('overreservation bytes accepted')
    assert ledger.state['calls']==0 and ledger.state['halt_reason']=='payload_financial_bound'
    body={'id':'offline-token-bound','model':MODEL,'choices':[{'message':{'role':'assistant','content':'x'}}],
          'usage':{'prompt_tokens':131072,'completion_tokens':1024}}
    assert validate_reply(TransportReply(200,body))[0] is None
    body['usage']['prompt_tokens']=131073
    assert validate_reply(TransportReply(200,body))[0]=='reported_token_limit'
    # Exercise the previously mislabeled diagnostic metadata without inference.
    metadata_ledger=TimeoutRetryLedger(out/'metadata',scope='full',max_calls=198,max_usd='10',
        plan_sha256='c'*64,authorization=auth)
    case=json.loads((BASE/'payload_capacity_gate_001/bundle/inputs.json').read_text())[0]
    def fake(data,headers,progress,timeout):
        diagnostic.save(progress.with_suffix('.parent.json'),{'child_reaped':True,'whole_request_timeout':False})
        return {'kind':'reply','status_code':200,'body':{'id':'offline-metadata','model':MODEL,
            'choices':[{'message':{'role':'assistant','content':'x'}}],
            'usage':{'prompt_tokens':32465,'completion_tokens':1}}}
    assert diagnostic.request(case,metadata_ledger,{'Modal-Key':'OFFLINE_ID','Modal-Secret':'OFFLINE_SECRET'},out/'metadata',fake)
    assert metadata_ledger.state['metadata']['base_url']==BASE_URL
    assert 'openrouter.ai' not in json.dumps(metadata_ledger.state['metadata'])
    audit=audit_retry_ledger(metadata_ledger.state,out/'metadata')
    result={'Results':{'prior_payloads':audited,'prior_native_requests':316,'blocked_wire_unchanged':True,
        'old_default_still_rejects':True,'new_blocked_bound':133100,'new_blocked_maximum_reference_usd':str(maximum),
        'exact_financial_boundary_passed':True,'financial_boundary_plus_one_rejected':True,
        'reported_input_limit_unchanged':True,'metadata_initialization_fixed':True,
        'n_per_counterexample':1,'sample_sd':None,'sample_variance':None,
        'positive_control':'316 prior native wire bodies retain bounds; original blocked body fits unchanged reservation',
        'behavioral_positive_control':'unrun under new policy'},'passed':True,'network_attempts':NETWORK,
        'native_or_provider_calls':0,'actual_spend_usd':'0','metadata_software_retry_audit':audit,
        'plan_sha256':hashlib.sha256((out/'plan.json').read_bytes()).hexdigest()}
    assert not NETWORK
    diagnostic.save(out/'results.json',result)
    print(json.dumps({'passed':True,'prior_requests':316,'max_padded_bytes':c.MAX_PADDED_BYTES,'network_attempts':NETWORK}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args().out)
