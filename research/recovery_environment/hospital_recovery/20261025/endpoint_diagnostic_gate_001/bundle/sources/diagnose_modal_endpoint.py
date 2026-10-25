"""Fixed endpoint-only diagnostics; never executes or resumes Hospital actions."""
import argparse
from copy import deepcopy
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

import endpoint_probe_worker as worker
from budget_client import BudgetError, BudgetLedger, TransportReply, _redact
from modal_hospital_client import MODEL, validate_reply
from modal_hospital_runtime import config
from run_full_workflow import all_history

HERE = Path(__file__).resolve().parent
BASE = HERE / '20261025'
SOURCES = ('diagnose_modal_endpoint.py', 'endpoint_probe_worker.py', 'budget_client.py',
           'modal_hospital_client.py', 'modal_hospital_runtime.py', 'run_full_workflow.py')
DIRECTIVE = ('Human requested endpoint-only timeout diagnosis on 2026-10-25 so the experiment can continue; '
             'standing paid authorization USD50 cumulative Hospital ceiling, no further approval required.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def matrix():
    first = [('positive', False), ('failed60', False), ('failed180', True),
             ('positive', True), ('failed60', True), ('failed180', False)]
    return [{'id': f'r{r}-{name}-' + ('sse' if stream else 'json'),
             'fixture': name, 'stream': stream, 'repeat_index': r}
            for r, order in enumerate((first, first[3:] + first[:3]))
            for name, stream in order]


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    roots, prior = {}, all_history()
    retrospection = {}
    for name, folder in [('failed60', 'full_workflow_live_ordinary_s0_001'),
                         ('failed180', 'full_workflow_live_ordinary_180_s0_001')]:
        path = BASE / folder / 'accounting/ledger.json'
        ledger = json.loads(path.read_text())
        assert ledger['status'] == 'halted' and ledger['records'][-1]['status'] == 'failed'
        roots[name] = deepcopy(ledger['records'][-1]['payload'])
        retrospect = []
        for record in ledger['records']:
            diagnostic = json.loads((BASE / folder / 'transport_diagnostics' /
                                     f"call-{record['call_id']:04d}.json").read_text())
            retrospect.append({'call': record['call_id'], 'status': record['status'],
                'payload_bytes': record['payload_bytes'],
                'roles': [m['role'] for m in record['payload']['messages']],
                'elapsed_seconds': diagnostic['elapsed_monotonic_seconds'],
                'finish_reason': ((record.get('response') or {}).get('choices') or [{}])[0].get('finish_reason')})
        retrospection[name] = {'source': str(path.relative_to(HERE)), 'sha256': sha(path),
            'records': retrospect, 'largest_success_bytes': max(r['payload_bytes'] for r in retrospect if r['status'] == 'settled')}
    roots['positive'] = {'model': MODEL, 'messages': [{'role': 'user',
        'content': 'Reply with exactly ENDPOINT_OK and no other text.'}],
        'max_tokens': 1024, 'temperature': 0, 'reasoning_effort': 'none', 'stream': False}
    payloads = {}
    for name, root in roots.items():
        for stream in (False, True):
            payload = deepcopy(root)
            payload['stream'] = stream
            if stream:
                payload['stream_options'] = {'include_usage': True}
            payloads[name + ('-sse' if stream else '-json')] = payload
    save(out / 'payloads.json', payloads)
    save(out / 'retrospective.json', retrospection)
    for name in SOURCES:
        (out / 'sources').mkdir(exist_ok=True)
        shutil.copyfile(HERE / name, out / 'sources' / name)
    plan = {'stage': 'endpoint_only_transport_diagnostic', 'cases': matrix(),
        'model': MODEL, 'base_url': worker.BASE_URL, 'max_calls': 12, 'max_usd': '.588',
        'reservation_per_call_usd': '.049', 'prior_guard': prior,
        'request_deadline_seconds': 60, 'batch_deadline_seconds': 900,
        'fixed_schedule_continues_after_independent_failed_probe': True,
        'no_hospital_actions_or_cohort_resume': True,
        'positive_control': 'each short JSON/SSE probe returns exactly ENDPOINT_OK with valid model/usage; 2 repeats per format',
        'negative_controls': 'offline incomplete stream and connection failure reject; sleeping child killed/reaped with hold',
        'claim_limits': 'two saved inputs from seed0, not independent Hospital seeds; two transport repeats per cell; no service-wide reliability guarantee',
        'sources': {name: sha(HERE / name) for name in SOURCES},
        'files': {name: sha(out / name) for name in ('payloads.json', 'retrospective.json')}}
    if Decimal(prior['guard_usd']) + Decimal('.588') > 50:
        raise BudgetError('cumulative ceiling insufficient')
    save(out / 'plan.json', plan)
    save(out / 'authorization.json', {'approved': True, 'scope': 'full', 'max_calls': 12,
        'max_usd': '.588', 'plan_sha256': sha(out / 'plan.json'), 'approval_reference': DIRECTIVE})
    return {'plan_sha256': sha(out / 'plan.json'), 'maximum_additional_guard_usd': '.588'}


def verify(bundle):
    plan = json.loads((bundle / 'plan.json').read_text())
    assert plan['cases'] == matrix() and plan['max_calls'] == 12 and plan['max_usd'] == '.588'
    assert plan['request_deadline_seconds'] == 60 and plan['model'] == MODEL
    for name, value in plan['sources'].items():
        assert sha(HERE / name) == value == sha(bundle / 'sources' / name)
    for name, value in plan['files'].items():
        assert sha(bundle / name) == value
    for fixture in json.loads((bundle / 'retrospective.json').read_text()).values():
        assert sha(HERE / fixture['source']) == fixture['sha256']
    return plan


def probe(data, headers, progress, timeout=60, launcher=subprocess.Popen):
    started = time.monotonic()
    child = launcher([sys.executable, str(HERE / 'endpoint_probe_worker.py')],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={'PATH': os.defpath, 'MODAL_PROXY_TOKEN_ID': headers['Modal-Key'],
             'MODAL_PROXY_TOKEN_SECRET': headers['Modal-Secret'], 'MODAL_PROGRESS_PATH': str(progress.resolve())})
    timed_out = False
    try:
        output, error = child.communicate(json.dumps({**data, 'timeout': timeout}), timeout=timeout)
        if child.returncode:
            return {'kind': 'transport_error', 'exception_type': 'WorkerExit', 'stderr_bytes': len(error.encode())}
        return json.loads(output)
    except subprocess.TimeoutExpired:
        timed_out = True
        child.kill()
        child.communicate(timeout=2)
        return {'kind': 'transport_error', 'exception_type': 'WholeRequestDeadline', 'child_reaped': True}
    finally:
        if child.poll() is None:
            child.kill(); child.communicate(timeout=2)
        summary = {'elapsed_seconds': time.monotonic() - started,
                   'whole_request_timeout': timed_out, 'child_reaped': child.poll() is not None}
        save(progress.with_suffix('.parent.json'), summary)


def validate(bundle, out):
    import io
    import socket
    from types import SimpleNamespace
    network = []
    def deny(event, args):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
            network.append(event); raise RuntimeError('network denied')
    sys.addaudithook(deny)
    verify(bundle)
    out.mkdir(parents=True, exist_ok=False)
    frames = [{'id': 'test', 'model': MODEL, 'choices': [{'index': 0, 'delta': {
        'role': 'assistant', 'content': 'ENDPOINT_', 'tool_calls': [{'index': 0, 'id': 'call_1',
        'type': 'function', 'function': {'name': 'test', 'arguments': '{"x":'}}]}}]},
        {'id': 'test', 'model': MODEL, 'choices': [{'index': 0, 'delta': {'content': 'OK',
        'tool_calls': [{'index': 0, 'function': {'arguments': '1}'}}]}, 'finish_reason': 'tool_calls'}]},
        {'id': 'test', 'model': MODEL, 'choices': [], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}]
    body = worker.assemble(frames, True)
    assert body['choices'][0]['message']['content'] == 'ENDPOINT_OK'
    assert body['choices'][0]['message']['tool_calls'][0]['function']['arguments'] == '{"x":1}'
    assert validate_reply(TransportReply(200, body))[0] is None
    try:
        worker.assemble(frames, False)
    except ValueError:
        pass
    else:
        raise AssertionError('unterminated stream accepted')
    # Exercise the actual phase instrumentation and SSE reader with fake sockets.
    class FakeSocket:
        def settimeout(self, value): pass
        def connect(self, address): pass
        def close(self): pass
    stream = b''.join(b'data: ' + json.dumps(frame).encode() + b'\n\n' for frame in frames) + b'data: [DONE]\n\n'
    class FakeResponse(io.BytesIO):
        status = 200
        def getheaders(self): return [('Content-Type', 'text/event-stream')]
    class FakeConnection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return FakeResponse(stream)
        def close(self): pass
    data = {'base_url': worker.BASE_URL, 'method': 'POST', 'path': '/v1/chat/completions',
            'payload': {'stream': True}, 'timeout': 1}
    fake_headers = {'Modal-Key': 'OFFLINE_TEST_ID', 'Modal-Secret': 'OFFLINE_TEST_SECRET'}
    with patch.object(worker.socket, 'getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]), \
         patch.object(worker.socket, 'socket', return_value=FakeSocket()), \
         patch.object(worker.ssl, 'create_default_context', return_value=SimpleNamespace(wrap_socket=lambda sock, **kwargs: sock)), \
         patch.object(worker.http.client, 'HTTPSConnection', FakeConnection):
        trace = worker.Trace(out / 'scripted-sse.progress.json')
        reply = worker.perform(data, fake_headers, trace)
        assert reply['body'] == body and reply['sse_done'] and trace.value['stage'] == 'complete'
        assert [e['stage'] for e in trace.value['events']][:7] == [
            'dns_start', 'dns_done', 'tcp_connect_start', 'tcp_connected', 'tls_start', 'tls_ready', 'sending_request']
    with patch.object(worker.socket, 'getaddrinfo', side_effect=OSError(101, 'scripted offline DNS failure')):
        trace = worker.Trace(out / 'scripted-dns-error.progress.json')
        reply = worker.perform(data, fake_headers, trace)
        assert reply['kind'] == 'transport_error' and trace.value['failure_phase'] == 'dns_start'
    def sleeping(*args, **kwargs):
        return subprocess.Popen([sys.executable, '-c', 'import sys,time;sys.stdin.read();time.sleep(5)'], **kwargs)
    test = probe({'base_url': worker.BASE_URL, 'method': 'GET', 'path': '/v1/models'},
        {'Modal-Key': 'OFFLINE_TEST_ID', 'Modal-Secret': 'OFFLINE_TEST_SECRET'}, out / 'sleep.progress.json', .2, sleeping)
    assert test.get('child_reaped') and test['exception_type'] == 'WholeRequestDeadline'
    auth = json.loads((bundle / 'authorization.json').read_text())
    ledger = BudgetLedger(out / 'accounting', scope='full', max_calls=1, max_usd='.049',
        authorization=auth, plan_sha256=sha(bundle / 'plan.json'))
    call = ledger.reserve({'offline': True}, 1)
    ledger.finish(call, failure='simulated_timeout')
    assert ledger.state['status'] == 'halted' and Decimal(ledger.state['held_usd']) == Decimal('.049')
    try:
        ledger.reserve({}, 1)
    except BudgetError:
        pass
    else:
        raise AssertionError('halted probe ledger resumed')
    assert Decimal('49.96') + Decimal('.049') > 50
    assert not network
    result = {'passed': True, 'plan_sha256': sha(bundle / 'plan.json'),
        'positive': 'complete SSE content/tool/usage assembly passes native validator',
        'negative': 'missing DONE rejected; hard deadline kills/reaps; failed ledger retains hold and cannot resume',
        'network_attempts': network, 'inference_calls': 0, 'real_spend_usd': '0'}
    save(out / 'results.json', result)
    return result


def stats(values):
    return {'n': len(values), 'values': values, 'mean': statistics.mean(values) if values else None,
        'sample_sd': statistics.stdev(values) if len(values) > 1 else None,
        'sample_variance': statistics.variance(values) if len(values) > 1 else None}


def run(bundle, out):
    plan = verify(bundle)
    gate = json.loads((bundle.parent / 'validation/results.json').read_text())
    assert gate['passed'] and gate['plan_sha256'] == sha(bundle / 'plan.json')
    assert not out.exists() and out.resolve().parent == BASE.resolve()
    assert out.name.startswith('endpoint_diagnostic_live_')
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=HERE).strip()
    assert all_history() == plan['prior_guard']
    out.mkdir()
    base, headers = config()
    secrets = tuple(headers.values())
    save(out / 'preflight.json', {'plan_sha256': sha(bundle / 'plan.json'),
        'request_deadline_seconds': 60, 'prior_guard': all_history(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE).decode().strip()})
    meta = []
    for i, path in enumerate(('/v1/models', '/health', '/openapi.json')):
        result = probe({'base_url': base, 'method': 'GET', 'path': path}, headers,
            out / f'metadata-{i}.progress.json', timeout=15)
        save(out / f'metadata-{i}.json', _redact(result, secrets))
        meta.append(result)
    models = meta[0]
    assert models.get('status_code') == 200 and MODEL in [m['id'] for m in models['body'].get('data', [])]
    payloads = json.loads((bundle / 'payloads.json').read_text())
    authorization = json.loads((bundle / 'authorization.json').read_text())
    reports, started = [], time.monotonic()
    for spec in plan['cases']:
        if time.monotonic() - started + 60 > plan['batch_deadline_seconds']:
            break
        if Decimal(all_history()['guard_usd']) + Decimal('.049') > 50:
            raise BudgetError('cumulative ceiling before diagnostic')
        key = spec['fixture'] + ('-sse' if spec['stream'] else '-json')
        payload = payloads[key]
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        bound = len(encoded) + 512 * (len(payload.get('messages', [])) + len(payload.get('tools', [])) + 1)
        assert len(encoded) <= 128 * 1024 and bound <= 131072
        ledger = BudgetLedger(out / 'accounting' / spec['id'], scope='full', max_calls=1,
            max_usd='.049', plan_sha256=sha(bundle / 'plan.json'), authorization=authorization)
        ledger.state.update(metadata={'model': MODEL, 'base_url': base, 'accounting_basis': 'reference_token_estimate_not_actual_modal_billing'})
        ledger._persist()
        call = ledger.reserve(payload, len(encoded))
        progress = out / (spec['id'] + '.progress.json')
        result = _redact(probe({'base_url': base, 'method': 'POST', 'path': '/v1/chat/completions',
            'payload': payload}, headers, progress), secrets)
        save(out / (spec['id'] + '.reply.json'), result)
        failure, estimate, reported = 'transport_failure', None, None
        if result.get('kind') == 'reply':
            failure, estimate, reported = validate_reply(TransportReply(result['status_code'], result['body']))
        ledger.state['records'][-1].update(reported_cost_usd=str(reported) if reported is not None else None)
        if reported is not None:
            ledger.state['reported_cost_sum_usd'] = str(reported)
        ledger.finish(call, status_code=result.get('status_code'), response=result.get('body'),
            cost=estimate if not failure else None, failure=failure)
        timing = json.loads(progress.with_suffix('.parent.json').read_text())
        trace = json.loads(progress.read_text()) if progress.exists() else {}
        message = ((result.get('body') or {}).get('choices') or [{}])[0].get('message', {}) if isinstance(result.get('body'), dict) else {}
        passed = failure is None and (spec['fixture'] != 'positive' or message.get('content', '').strip() == 'ENDPOINT_OK')
        report = {**spec, 'transport_pass': failure is None, 'positive_control_pass': passed if spec['fixture'] == 'positive' else None,
            'elapsed_seconds': timing['elapsed_seconds'], 'stage': trace.get('stage'),
            'failure_phase': trace.get('failure_phase'),
            'phase_elapsed_seconds': {e['stage']: e['elapsed_seconds'] for e in trace.get('events', [])},
            'http_status': result.get('status_code'), 'body_bytes': trace.get('body_bytes', 0),
            'sse_frames': trace.get('frames', 0), 'failure': failure,
            'reference_usd': str(estimate) if estimate is not None and not failure else None,
            'held_usd': ledger.state['held_usd']}
        reports.append(report)
        save(out / 'results.json', {'plan_sha256': sha(bundle / 'plan.json'), 'cases': reports,
            'planned_cases': plan['cases'], 'guarded_cumulative_usd': all_history()['guard_usd'],
            'actual_modal_charges_verified': False, 'hospital_cases_resumed': 0})
        print(json.dumps(report), flush=True)
    groups = {}
    for key in payloads:
        selected = [r for r in reports if r['fixture'] + ('-sse' if r['stream'] else '-json') == key]
        groups[key] = {'transport_passes': sum(r['transport_pass'] for r in selected),
            'planned_denominator': 2, 'elapsed_all_attempts': stats([r['elapsed_seconds'] for r in selected]),
            'successful_elapsed': stats([r['elapsed_seconds'] for r in selected if r['transport_pass']])}
    final = json.loads((out / 'results.json').read_text())
    final.update(groups=groups, positive_control_passes=sum(r['positive_control_pass'] is True for r in reports),
        positive_control_denominator=4, unstarted=plan['cases'][len(reports):])
    save(out / 'results.json', final)
    return {'diagnostic_attempts': len(reports), 'positive_control_passes': final['positive_control_passes'],
            'guarded_cumulative_usd': final['guarded_cumulative_usd']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'validate', 'run'))
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.out)
    elif args.command == 'validate':
        result = validate(args.bundle, args.out)
    else:
        lock = Path(tempfile.gettempdir()) / ('modal-Hospital-' + hashlib.sha256(str(HERE).encode()).hexdigest()[:16] + '.lock')
        with lock.open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = run(args.bundle, args.out)
    print(json.dumps(result, sort_keys=True))
