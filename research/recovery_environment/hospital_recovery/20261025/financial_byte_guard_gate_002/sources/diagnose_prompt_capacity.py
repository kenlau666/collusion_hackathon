"""Frozen one-token prompt-capacity probes; never dispatch Hospital tools."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys

NETWORK = []
OFFLINE = len(sys.argv)>1 and sys.argv[1] in {'prepare','validate'}
if OFFLINE:
    def deny(event,args):
        if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
            NETWORK.append(event)
            raise RuntimeError('network denied during capacity preparation/validation')
    sys.addaudithook(deny)
ipv6 = socket.has_ipv6
try:
    if OFFLINE:
        socket.has_ipv6 = False
    from budget_client import BudgetError, TransportReply, _redact
    from modal_hospital_client import MODEL, BASE_URL, BASIS, validate_reply
    from modal_hospital_runtime import config
    from diagnose_modal_endpoint import probe
    from timeout_retry_client import TimeoutRetryLedger, POLICY, DIRECTIVE, encoded
    from run_full_workflow import all_history, APPROVAL
    from analyze_full_workflow import audit_retry_ledger
finally:
    socket.has_ipv6 = ipv6

HERE = Path(__file__).resolve().parent
BASE = HERE/'20261025'
PARTIAL = BASE/'full_workflow_live_ordinary_retry1_s1_001'
SOURCES = ('diagnose_prompt_capacity.py', 'budget_client.py', 'modal_hospital_client.py',
    'modal_hospital_runtime.py', 'diagnose_modal_endpoint.py', 'endpoint_probe_worker.py',
    'timeout_retry_client.py', 'traced_modal_client.py', 'run_full_workflow.py', 'analyze_full_workflow.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def bound(payload):
    wire = encoded(payload)
    padded = len(wire)+512*(len(payload.get('messages', []))+len(payload.get('tools', []))+1)
    if payload.get('max_tokens') != 1 or payload.get('model') != MODEL:
        raise BudgetError('diagnostic model/output mismatch')
    if (payload.get('temperature') != 0 or payload.get('stream') is not False
            or payload.get('reasoning_effort') != 'none'):
        raise BudgetError('diagnostic settings mismatch')
    # Same conservative serialized-byte assumption as the existing adapter, but
    # diagnose capacity under the reservation ceiling rather than relaxing it.
    ceiling = Decimal(padded)*Decimal('.00000030')+Decimal('.00000120')
    if ceiling > Decimal('.049'):
        raise BudgetError('diagnostic input exceeds financial byte bound')
    return wire, padded, ceiling


def prepare(bundle):
    bundle.mkdir(parents=True, exist_ok=False)
    old = json.loads((PARTIAL/'accounting/ledger.json').read_text())
    assert old['halt_reason'] == 'payload_or_prompt_bound' and old['calls'] == 105
    actual = old['records'][-1]
    rejected = (PARTIAL/'payload_audit/rejected_wire.json').read_bytes()
    cases = []
    for label, wire, expected in [('previous-positive', actual['wire_payload_json'].encode(),
                                  actual['usage']['prompt_tokens']), ('rejected-input', rejected, None)]:
        payload = json.loads(wire)
        assert payload['max_tokens'] == 1024
        payload['max_tokens'] = 1
        changed = encoded(payload)
        restored = deepcopy(payload); restored['max_tokens'] = 1024
        assert encoded(restored) == wire
        _, padded, maximum = bound(payload)
        cases.append({'id': label, 'seed': 1, 'wire_json': changed.decode(),
            'wire_sha256': hashlib.sha256(changed).hexdigest(), 'original_wire_sha256': hashlib.sha256(wire).hexdigest(),
            'padded_byte_bound': padded, 'maximum_reference_usd': str(maximum),
            'expected_prompt_tokens': expected, 'only_changed_field': 'max_tokens:1024→1'})
    save(bundle/'inputs.json', cases)
    (bundle/'sources').mkdir()
    for name in SOURCES:
        shutil.copyfile(HERE/name, bundle/'sources'/name)
    save(bundle/'plan.json', {'stage': 'one_token_prompt_capacity_diagnosis', 'model': MODEL, 'route': BASE_URL,
        'inputs_sha256': sha(bundle/'inputs.json'), 'sources': {n: sha(HERE/n) for n in SOURCES},
        'source_ledger_sha256': sha(PARTIAL/'accounting/ledger.json'),
        'source_rejected_wire_sha256': hashlib.sha256(rejected).hexdigest(),
        'positive': 'previous prompt reports exactly its recorded32465tokens with output<=1 and no reasoning',
        'diagnostic': 'same rejected message strings/tools/settings with only output cap1; measured prompt<=131072',
        'max_logical_requests': 2, 'max_outward_attempts': 4, 'max_reserved_usd': '.196',
        'timeout_seconds_per_attempt': 60, 'timeout_retry_policy': POLICY, 'prior': all_history(),
        'native_tool_dispatch': False, 'seed_replacement': False,
        'limits': 'Positive must pass before rejected input; non-timeout failure or second timeout is terminal. Actual Modal bill unknown.'})
    plan_hash = sha(bundle/'plan.json')
    save(bundle/'authorization.json', {'approved': True, 'scope': 'full', 'max_calls': 2, 'max_usd': '.098',
        'plan_sha256': plan_hash, 'approval_reference': APPROVAL,
        'timeout_retry_policy': POLICY, 'retry_approval_reference': DIRECTIVE})
    print(json.dumps({'prepared': str(bundle), 'plan_sha256': plan_hash, 'network_attempts': NETWORK}))


def verify(bundle):
    plan = json.loads((bundle/'plan.json').read_text())
    assert plan['inputs_sha256'] == sha(bundle/'inputs.json')
    for name, expected in plan['sources'].items():
        assert sha(HERE/name) == sha(bundle/'sources'/name) == expected
    assert plan['source_ledger_sha256'] == sha(PARTIAL/'accounting/ledger.json')
    assert plan['source_rejected_wire_sha256'] == sha(PARTIAL/'payload_audit/rejected_wire.json')
    auth = json.loads((bundle/'authorization.json').read_text())
    assert auth['plan_sha256'] == sha(bundle/'plan.json') and auth['approval_reference'] == APPROVAL
    cases = json.loads((bundle/'inputs.json').read_text())
    for case in cases:
        wire = case['wire_json'].encode();payload = json.loads(wire)
        assert encoded(payload) == wire and hashlib.sha256(wire).hexdigest() == case['wire_sha256']
        bound(payload)
    return plan, auth, cases


def request(case, ledger, headers, directory, call_probe=probe):
    payload = json.loads(case['wire_json'])
    assert _redact(payload, tuple(headers.values())) == payload
    wire, padded, maximum = bound(payload)
    diagnostics = directory/'diagnostics'; diagnostics.mkdir()
    ledger.state.update(accounting_basis=BASIS, reported_cost_sum_usd='0',
        reported_cost_observations=0, reported_cost_missing=0, reported_cost_total_usd=None,
        metadata={'base_url':BASE_URL,'model':MODEL,'accounting_basis':BASIS,
            'actual_modal_billing_attested':False,'input_reference_usd_per_million':'.30',
            'output_reference_usd_per_million':'1.20','diagnostic_output_limit':1})
    ledger._persist()
    for index in (0, 1):
        ledger.attempt_context = {'logical_request_id': 1, 'attempt_index': index}
        call = ledger.reserve(payload, len(wire))
        record = ledger.state['records'][-1]
        record.update(conservative_prompt_bound=padded, maximum_reference_usd=str(maximum),
                      accounting_basis=BASIS, seed_forwarded=False)
        ledger._persist()
        progress = diagnostics/f'call-{call:04d}.progress.json'
        result = call_probe({'base_url': BASE_URL, 'method': 'POST',
            'path': '/v1/chat/completions', 'payload': payload}, headers, progress, timeout=60)
        parent = json.loads(progress.with_suffix('.parent.json').read_text())
        diagnostic = {**_redact(result, tuple(headers.values())), 'call_id': call,
            'child_reaped': parent['child_reaped'], 'payload_sha256': record['payload_sha256'],
            'wire_payload_sha256': record['wire_payload_sha256']}
        if parent['whole_request_timeout']:
            diagnostic['category'] = 'whole_request_deadline'
        diagnostic_path = diagnostics/f'call-{call:04d}.json'
        save(diagnostic_path, diagnostic)
        if result.get('kind') != 'reply':
            ledger.state['reported_cost_missing'] += 1
            ledger.finish(call, failure='transport_failure')
            eligible = parent['whole_request_timeout'] or result.get('exception_type') == 'TimeoutError'
            if index == 0 and eligible and parent['child_reaped']:
                ledger.prepare_timeout_retry(call, diagnostic_path)
                continue
            return None
        failure, estimate, reported = validate_reply(TransportReply(result['status_code'], result['body']))
        body = _redact(result['body'], tuple(headers.values()))
        if failure is None and body['usage']['completion_tokens'] > 1:
            failure = 'diagnostic_output_limit'
        record.update(reference_estimate_usd=str(estimate) if estimate is not None else None,
                      reported_cost_usd=str(reported) if reported is not None else None)
        if reported is None:
            ledger.state['reported_cost_missing'] += 1
        else:
            ledger.state['reported_cost_observations'] += 1
            ledger.state['reported_cost_sum_usd'] = str(Decimal(ledger.state['reported_cost_sum_usd'])+reported)
        ledger.state['reported_cost_total_usd'] = (ledger.state['reported_cost_sum_usd']
            if ledger.state['reported_cost_missing'] == 0 else None)
        ledger.finish(call, status_code=result['status_code'], response=body, cost=estimate, failure=failure)
        return body if failure is None else None


def execute(bundle, out):
    plan, auth, cases = verify(bundle)
    gate = json.loads((bundle.parent/'validation/results.json').read_text())
    assert gate['passed'] and gate['plan_sha256'] == sha(bundle/'plan.json')
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=HERE).strip()
    assert out.parent.resolve() == BASE.resolve() and out.name.startswith('endpoint_diagnostic_live_')
    assert all_history() == plan['prior']
    out.mkdir(); (out/'accounting').mkdir()
    save(out/'preflight.json', {'plan_sha256': sha(bundle/'plan.json'), 'prior': all_history(),
        'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE).decode().strip()})
    _, headers = config()
    rows = []
    for case in cases:
        directory = out/'accounting'/case['id']
        ledger = TimeoutRetryLedger(directory, scope='full', max_calls=2, max_usd='.098',
            plan_sha256=sha(bundle/'plan.json'), authorization=auth, cumulative_guard=all_history)
        body = request(case, ledger, headers, directory)
        measured = body['usage']['prompt_tokens'] if body else None
        passed = body is not None and (case['expected_prompt_tokens'] is None or measured == case['expected_prompt_tokens'])
        rows.append({'id': case['id'], 'seed': 1, 'passed': passed,
            'expected_prompt_tokens': case['expected_prompt_tokens'], 'observed_prompt_tokens': measured,
            'completion_tokens': body['usage']['completion_tokens'] if body else None,
            'padded_byte_bound': case['padded_byte_bound'], 'ledger': ledger.summary(),
            'retry_audit': audit_retry_ledger(ledger.state, directory)})
        save(out/'results.json', {'Results': {'per_input': rows, 'independent_hospital_families': 1,
            'planned_inputs': 2, 'positive_control_passed': rows[0]['passed'],
            'both_inputs_passed': len(rows)==2 and all(r['passed'] for r in rows),
            'sample_sd': None, 'sample_variance': None}, 'cumulative_guard': all_history(),
            'actual_modal_account_charges_verified': False, 'native_tool_calls': 0,
            'claim_limit': 'Counts two fixed prompts; does not complete the partial case, qualify a guard or establish behavioral effects.'})
        print(json.dumps({k:v for k,v in rows[-1].items() if k not in ('ledger','retry_audit')}),flush=True)
        if not passed:
            break


def validate(bundle, out):
    _, auth, cases = verify(bundle)
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for label, pattern in [('success',['ok']),('timeout-recovery',['timeout','ok']),
                           ('double-timeout',['timeout','timeout']),('http-failure',['http'])]:
        directory = out/label
        ledger = TimeoutRetryLedger(directory,scope='full',max_calls=2,max_usd='.098',
            plan_sha256=sha(bundle/'plan.json'),authorization=auth)
        sent=[]
        def fake(data, headers, progress, timeout):
            kind=pattern[len(sent)]; sent.append(encoded(data['payload']))
            save(progress.with_suffix('.parent.json'),{'child_reaped':True,'whole_request_timeout':kind=='timeout'})
            if kind=='timeout':return {'kind':'transport_error','exception_type':'WholeRequestDeadline'}
            if kind=='http':return {'kind':'reply','status_code':429,'body':{'error':'synthetic'}}
            return {'kind':'reply','status_code':200,'body':{'id':'offline-control','model':MODEL,
                'choices':[{'message':{'role':'assistant','content':'x'},'finish_reason':'length'}],
                'usage':{'prompt_tokens':32465,'completion_tokens':1}}}
        body=request(cases[0],ledger,{'Modal-Key':'OFFLINE_ID','Modal-Secret':'OFFLINE_SECRET'},directory,fake)
        audit=audit_retry_ledger(ledger.state,directory)
        expected={'success':(1,True,'0'),'timeout-recovery':(2,True,'.049'),
                  'double-timeout':(2,False,'.098'),'http-failure':(1,False,'.049')}[label]
        assert ledger.state['calls']==expected[0] and (body is not None)==expected[1]
        assert Decimal(ledger.state['held_usd'])==Decimal(expected[2])
        assert all(w==sent[0] for w in sent)
        rows.append({'id':label,'passed':True,'calls':ledger.state['calls'],
            'held_usd':ledger.state['held_usd'],'retry_audit':audit})
    original=json.loads(cases[0]['wire_json'])
    for label,payload in [('wrong-output',{**original,'max_tokens':2}),
                          ('oversized',{**original,'messages':[{'role':'user','content':'x'*170000}]})]:
        try:
            bound(payload)
        except BudgetError:
            rows.append({'id':label,'passed':True,'calls':0})
        else:
            raise AssertionError('invalid diagnostic accepted')
    save(out/'results.json', {'passed':True,'plan_sha256':sha(bundle/'plan.json'),
        'Results':{'software_cases':rows,'n_per_counterexample':1,'sample_sd':None,'sample_variance':None,
            'positive':'one-token valid response settles once; one timeout recovers with equal bytes and retained hold'},
        'network_attempts':NETWORK,'inference_calls':0,'actual_spend_usd':'0'})
    print(json.dumps({'passed':True,'software_cases':len(rows),'network_attempts':NETWORK}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','validate','run'])
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':prepare(args.out)
    elif args.command=='validate':validate(args.bundle,args.out)
    else:execute(args.bundle,args.out)
