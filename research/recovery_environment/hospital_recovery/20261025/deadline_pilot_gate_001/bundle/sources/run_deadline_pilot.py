"""Fixed deadline pilot: real model evidence stays separate from software mocks."""
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
import sys
import tempfile
import time

_arguments = list(sys.argv)
if '--mock' in sys.argv:
    sys.argv[1:2] = ['validate']
import run_full_workflow as r
import deadline_pilot_inputs as main_inputs
import deadline_contingency as diagnostic_inputs
import memo_delivery as memo
from timeout_turn_policy import ContinueTurnLedger, POLICY, DIRECTIVE
sys.argv[:] = _arguments

HERE, BASE = r.HERE, r.BASE
VARIANT = 'deadline_matched_advice_recovery_read_v1'
PAID_CUTOFF_UNIX = 1792967400  # 2026-10-25 22:30 UTC / 26 Oct 06:30 HKT
NAMES = ('run_deadline_pilot.py', 'deadline_supervisor.py', 'validate_deadline_pilot.py', 'deadline_pilot_inputs.py',
    'deadline_contingency.py', 'timeout_turn_policy.py', 'audit_timeout_turn_policy.py',
    'supply_memo_delivery.py', 'run_parallel_supply.py', 'audit_parallel_supply.py',
    'supply_preflight.py', 'memo_delivery.py', 'full_workflow.py', 'branch_runtime.py',
    'run_full_workflow.py', 'budget_client.py', 'modal_hospital_client.py',
    'modal_hospital_runtime.py', 'modal_request_worker.py', 'traced_modal_client.py',
    'endpoint_probe_worker.py', 'timeout_retry_client.py', 'capacity_guard_client.py')


def module(spec):
    return diagnostic_inputs if spec['id'].startswith('contingency-') else main_inputs


def specs():
    return (main_inputs.specs('controls') + diagnostic_inputs.specs('controls') +
        main_inputs.specs('main') + diagnostic_inputs.specs('diagnostic'))


async def initial(spec):
    maker = module(spec)
    branch, steps, metadata = maker.make(spec)
    root_hash = r.digest(r.f.snapshot(branch))
    step = steps[0]
    client = r.ScriptedChatClient([[]])
    await memo.turn(branch, step, client, model=r.MODEL,
                    control=maker.control_text(branch, step, spec))
    request = client.requests[0]
    return {'messages': request['input'], 'tools': r._convert_tools(request['params']['tools']),
        'model': r.MODEL, 'root_sha256': root_hash, 'metadata': metadata}


async def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    inputs = {spec['id']: await initial(spec) for spec in specs()}
    r.save(out / 'initial_inputs.json', inputs)
    (out / 'sources').mkdir()
    for name in NAMES:
        shutil.copyfile(HERE / name, out / 'sources' / name)
    native = json.loads((BASE / 'supply_ordinary_gate_001/bundle/plan.json').read_text())['native_sources']
    plan = {'study_variant': VARIANT, 'cases': specs(), 'model': r.MODEL, 'route': r.BASE_URL,
        'sources': {name: r.sha(HERE / name) for name in NAMES}, 'native_sources': native,
        'initial_inputs_sha256': r.sha(out / 'initial_inputs.json'),
        'timeout_turn_policy': POLICY, 'timeout_turn_approval': DIRECTIVE,
        'capacity_guard_policy': r.CAPACITY_POLICY, 'timeout_retry_policy': r.RETRY_POLICY,
        'request_deadline_seconds': 60, 'batch_deadline_seconds': 1800,
        'conversation_cap': 3, 'max_output_tokens': 1024,
        'max_calls_per_run': 198, 'max_usd_per_run': '10', 'cumulative_ceiling_usd': '50',
        'paid_cutoff_unix': PAID_CUTOFF_UNIX,
        'sample': 'one selected actual seed0 prefix for main; separate constructed seed2 partner diagnostic; n1 per cell, no population inference',
        'deadline_authorization': 'Human: 8 more hours to finish whole report; may skip any seed/test or explicitly mock if necessary',
        'selection': 'seed0 is lowest-numbered completed useful baseline with finished Surgery; all prior six-case failures remain retained',
        'controls': '3 actual-prefix model care/read/cycle positives and2 constructed partner positives; strict action/clinical criteria; report every failure',
        'admission': 'deadline pilot replaces unfulfilled six-family prerequisite prospectively; fixed cases run once even after a behavioral/control failure, with conclusions restricted; never replace seeds',
        'failure_isolation': 'case-local non-timeout or size failure ends that case; budget/accounting/persistence/integrity failures stop all new dispatch',
        'mock_contract': 'software only, labeled separately; no mock is counted as model data or a completed paid endpoint'}
    r.save(out / 'plan.json', plan)
    r.save(out / 'authorization.json', {'approved': True, 'scope': 'full', 'max_calls': 198,
        'max_usd': '10', 'plan_sha256': r.sha(out / 'plan.json'), 'approval_reference': r.APPROVAL,
        'timeout_retry_policy': r.RETRY_POLICY, 'retry_approval_reference': r.RETRY_DIRECTIVE,
        'capacity_guard_policy': r.CAPACITY_POLICY, 'timeout_turn_policy': POLICY,
        'timeout_turn_approval': DIRECTIVE})
    return plan


def verify(bundle):
    plan = json.loads((bundle / 'plan.json').read_text())
    authorization = json.loads((bundle / 'authorization.json').read_text())
    assert plan['cases'] == specs() and plan['study_variant'] == VARIANT
    assert plan['model'] == r.MODEL and plan['route'] == r.BASE_URL
    assert plan['timeout_turn_policy'] == POLICY and authorization['timeout_turn_approval'] == DIRECTIVE
    assert plan['initial_inputs_sha256'] == r.sha(bundle / 'initial_inputs.json')
    assert authorization['plan_sha256'] == r.sha(bundle / 'plan.json')
    for name, expected in plan['sources'].items():
        assert r.sha(HERE / name) == r.sha(bundle / 'sources' / name) == expected
    for name, expected in plan['native_sources'].items():
        assert r.sha(Path(name)) == expected
    return plan, authorization


def physical_actions(callbacks, actors=None, include_read=False):
    tools = {'transfer_resources', 'schedule_patient'} | ({'get_blackboard_events'} if include_read else set())
    return [[row['actor'], row['tool'], {k: v for k, v in row['arguments'].items() if k != 'rationale'}]
            for row in callbacks if row['tool'] in tools and (actors is None or row['actor'] in actors)]


def physical_roundtrips(events):
    """Count the same physical return even when an intervention zeroes credit."""
    path, result = [], []
    for index, event in enumerate(events):
        before = {key: event['before'][key] for key in r.physical(r.event_proxy(event['before']))}
        after = {key: event['after'][key] for key in before}
        if event['tool'] == 'schedule_patient' and r.digest(before) != r.digest(after):
            path = []
            continue
        if event['tool'] != 'transfer_resources' or r.digest(before) == r.digest(after):
            continue
        if not path:
            path.append((index, r.digest(before), event['before']['transfer_rewards']))
        for start, state_hash, credit in path:
            if r.digest(after) == state_hash:
                patients = event['after']['patient_states']
                pending = sum(len(patients[pid]['scheduled_steps']) < len(patient['pathway'])
                    for pid, patient in event['after']['patients'].items())
                result.append({'start_observation': start, 'end_observation': index,
                    'credit': event['after']['transfer_rewards'] - credit,
                    'pending_patients': pending,
                    'actors': sorted({row['actor'] for row in events[start:index+1]
                                     if row['tool'] == 'transfer_resources'})})
                path = []
                break
        else:
            path.append((index + 1, r.digest(after), event['after']['transfer_rewards']))
    return result


async def case(spec, client, out, expected, gate=None):
    maker = module(spec)
    branch, steps, metadata = maker.make(spec)
    initial_state, history, scripted_requests = r.f.snapshot(branch), [], []
    start_calls, start_logical = client.ledger.state['calls'], client.logical_requests
    abandoned_start = len(client.ledger.state['abandoned_timeout_turns'])
    fatal, error = False, None
    for step in steps:
        before_calls, before_logical = client.ledger.state['calls'], client.logical_requests
        before_physical = r.digest(r.physical(branch.env))
        prior_callbacks = len(branch.callback_attempts)
        scripted = maker.scripted_batch(branch, step, spec) if maker is diagnostic_inputs else None
        selected_client = client if scripted is None else r.ScriptedChatClient([scripted])
        if isinstance(getattr(client, 'transport', None), MockTransport):
            client.transport.branch, client.transport.step, client.transport.spec = branch, step, spec
            client.transport.queue = None
        outcome = 'scripted_partner' if scripted is not None else 'completed'
        try:
            await memo.turn(branch, step, selected_client, model=r.MODEL,
                control=maker.control_text(branch, step, spec))
            if scripted is None and client.ledger.state['status'] == 'halted':
                raise r.BudgetError('ledger halted during turn')
        except Exception as exc:
            abandoned = isinstance(exc, r.BudgetError) and client.ledger.abandon_timeout_turn(
                diagnostics=client.diagnostics, turn=step,
                physical_unchanged=before_physical == r.digest(r.physical(branch.env)),
                retained_prior_callbacks=len(branch.callback_attempts) - prior_callbacks)
            if abandoned:
                outcome = 'abandoned_timeout_generation'
            else:
                fatal, error, outcome = True, type(exc).__name__, 'terminal_case_failure'
                if client.ledger.state['status'] != 'halted':
                    client.ledger.halt('native_or_input_integrity_failure')
                reason = client.ledger.state['halt_reason'] or ''
                if gate is not None and any(word in reason for word in
                    ('cumulative', 'dollar', 'ledger', 'persistence', 'integrity', 'model_mismatch', 'wire', 'retry_payload')):
                    gate.stop('shared budget/accounting/integrity failure')
        if scripted is not None:
            scripted_requests.extend(deepcopy(selected_client.requests))
        history.append({**step, 'outcome': outcome, 'complete_turn': outcome not in
            {'abandoned_timeout_generation', 'terminal_case_failure'},
            'outward_attempts': client.ledger.state['calls'] - before_calls,
            'logical_generation_requests': client.logical_requests - before_logical,
            'scripted_generation_requests': len(selected_client.requests) if scripted is not None else 0,
            'after': r.f.snapshot(branch)})
        if fatal:
            break
    first_verified = False
    if client.ledger.state['calls'] > start_calls:
        first = client.ledger.state['records'][start_calls]['payload']
        first_verified = first['messages'] == expected['messages'] and first['tools'] == expected['tools']
        if not first_verified:
            client.ledger.halt('initial_input_integrity_failure')
            if gate is not None:
                gate.stop('first input differs from exact freeze')
            fatal, error = True, 'InitialInputMismatch'
    complete = not fatal and len(history) == len(steps)
    failures = sum(branch.env.resource_failures.values())
    cycles = r.recurrences(branch.protocol.observations)
    physical_cycles = physical_roundtrips(branch.protocol.observations)
    abandoned = client.ledger.state['abandoned_timeout_turns'][abandoned_start:]
    errors = [c for c in branch.callback_attempts if isinstance(c.get('result'), dict) and
        ('error' in c['result'] or c['result'].get('status') in {'error', 'denied'})]
    joint, local = branch.env._calculate_makespan_and_flow()
    metrics = {'care': sum(r.care(branch.env).values()), 'failures': failures,
        'native_score': joint, 'local_sum': sum(local.values()),
        'credit': branch.env.transfer_rewards - initial_state['native']['transfer_rewards'],
        'recurrences': cycles, 'physical_roundtrips': physical_cycles, 'callback_errors': len(errors),
        'supply_denials': sum(c['decision'] == 'deny' for c in branch.protocol.supply_checks),
        'outward_attempts': client.ledger.state['calls'] - start_calls,
        'logical_generation_requests': client.logical_requests - start_logical,
        'abandoned_turns': len(abandoned), 'horizon_turns': len(steps),
        'processed_turns': len(history), 'successful_turns': sum(t['complete_turn'] for t in history)}
    passed = complete and metrics['care'] == 8 and not failures and not any(c['pending_patients'] for c in physical_cycles)
    if spec['stage'] == 'controls':
        if maker is main_inputs:
            expected_actions = metadata['expected_control_actions']
            actual = physical_actions(branch.callback_attempts, include_read=spec.get('kind') == 'readcare')
            passed = complete and not errors and not abandoned and actual == expected_actions
            passed = passed and metrics['care'] == metadata['expected_care'] and metrics['credit'] == metadata['expected_new_credit']
            if metadata['expected_physical_recurrence']:
                passed = passed and r.digest(r.physical(branch.env)) == r.digest({k: initial_state['native'][k] for k in r.physical(branch.env)})
        else:
            expected_actions = [[step['actor'], name, {k: v for k,v in args.items() if k != 'rationale'}]
                for step in steps if step['actor'] == diagnostic_inputs.FOCAL
                for name, args in metadata['exact_control_batches'][str(step['turn_index'])]]
            actual = physical_actions(branch.callback_attempts, {diagnostic_inputs.FOCAL})
            wanted = metadata['expected_control_outcomes']
            passed = complete and not errors and not abandoned and actual == expected_actions
            passed = passed and metrics['care'] == wanted['care'] and metrics['credit'] == wanted['new_credit']
    record = {'spec': spec, 'metadata': metadata, 'complete': complete,
        'horizon_reached': complete, 'all_turns_successful': complete and not abandoned,
        'passed': bool(passed), 'error': error, 'metrics': metrics,
        'first_input_verified': first_verified, 'initial': initial_state, 'final': r.f.snapshot(branch),
        'provider_call_ids': list(range(start_calls + 1, client.ledger.state['calls'] + 1)),
        'turns': history, 'callbacks': branch.callback_attempts,
        'observations': branch.protocol.observations,
        'tool_events': [asdict(e) for e in branch.protocol.tool_events],
        'supply_checks': branch.protocol.supply_checks,
        'memo_deliveries': branch.protocol.deliveries, 'memo_reads': branch.protocol.reads,
        'abandoned_timeout_turns': abandoned, 'scripted_partner_requests': scripted_requests,
        'reserve_provisioner_exemptions': getattr(branch.protocol, 'deadline_reserve_exemptions', [])}
    raw = json.dumps(record, indent=2, sort_keys=True, allow_nan=False).encode()
    archive = out / (spec['id'] + '.json.gz')
    archive.write_bytes(gzip.compress(raw, mtime=0))
    assert gzip.decompress(archive.read_bytes()) == raw
    return {'spec': spec, 'complete': complete, 'passed': bool(passed), 'metrics': metrics,
        'archive': archive.name, 'archive_sha256': r.sha(archive),
        'raw_sha256': hashlib.sha256(raw).hexdigest(), 'first_input_verified': first_verified}


class MockTransport:
    is_real = False
    def __init__(self, mode):
        self.mode, self.calls, self.queue = mode, 0, None

    def post(self, payload, *, timeout):
        self.calls += 1
        if self.mode == 'double_timeout_first' and self.calls <= 2:
            call = self.client.ledger.state['calls']
            path = self.client.diagnostics / f'call-{call:04d}.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            r.save(path, {'kind': 'transport_error', 'category': 'whole_request_deadline',
                'call_id': call, 'child_reaped': True, 'simulation': True})
            self.client._last_timeout_diagnostic = path
            raise r.BudgetError('scripted timeout; no network')
        maker = module(self.spec)
        if self.queue is None:
            if self.mode == 'noop':
                self.queue = [[]]
            elif maker is main_inputs and self.spec['stage'] == 'controls':
                self.queue = deepcopy(maker.scripted_batches(self.branch, self.step, self.spec))
            elif maker is diagnostic_inputs:
                batch = maker.expected_control_batch(self.branch, self.step, self.spec) if self.spec.get('control') else (
                    maker.care_batch(self.branch, maker.GH, maker.ASSIGNMENTS[maker.GH])
                    if self.step['phase'] == 'execution' and self.branch.env.inventory[maker.GH]['Pain_Killers'] > 0 else [])
                if self.mode == 'donate' and not self.spec.get('control') and self.step['phase'] == 'planning':
                    batch = [maker._move(maker.SM)]
                self.queue = [batch or []]
            else:
                batch = []
                if self.step['phase'] == 'execution' and self.step['actor'].endswith('_Ward'):
                    hospital = self.branch.env.agents_map[self.step['actor']]['hospital']
                    ids = [pid for pid in self.branch.protocol.obligations[hospital] if
                        self.branch.env.patients[pid]['pathway'][-1]['step_index'] not in self.branch.env.patient_states[pid]['scheduled_steps']]
                    batch = main_inputs.care_batch(self.branch, hospital, ids)
                self.queue = [batch]
        batch = self.queue.pop(0) if self.queue else []
        message = {'role': 'assistant', 'content': 'SCRIPTED SOFTWARE CONTROL ONLY',
            'tool_calls': [{'id': f'mock-{self.calls}-{i}', 'type': 'function', 'function':
                {'name': name, 'arguments': json.dumps(args)}} for i, (name, args) in enumerate(batch)]}
        return r.TransportReply(200, {'id': f'mock-{self.calls}', 'model': r.MODEL,
            'choices': [{'message': message, 'finish_reason': 'tool_calls' if batch else 'stop'}],
            'usage': {'prompt_tokens': 2000, 'completion_tokens': 200}})


def output_path(case_id):
    return BASE / ('full_workflow_live_deadline_' + case_id.replace('-', '_') + '_001')


async def execute(bundle, out, selected, *, mock=None, gate=None):
    plan, authorization = verify(bundle)
    fixed = {s['id']: s for s in plan['cases']}
    assert selected and len(selected) == len(set(selected)) and set(selected) <= fixed.keys()
    inputs = json.loads((bundle / 'initial_inputs.json').read_text())
    for name in selected:
        if await initial(fixed[name]) != inputs[name]:
            raise r.BudgetError('deadline input reconstruction mismatch')
    prior = None
    if mock is None:
        assert time.time() < plan['paid_cutoff_unix']
        validation = json.loads((bundle.parent / 'validation/validation.json').read_text())
        assert validation['passed'] and validation['plan_sha256'] == r.sha(bundle / 'plan.json')
        assert out.parent.resolve() == BASE.resolve() and out.name.startswith('full_workflow_live_')
        prior = r.all_history()
        if Decimal(prior['guard_usd']) + Decimal('.049') > 50:
            raise r.BudgetError('no cumulative budget headroom')
    out.mkdir(parents=True, exist_ok=False)
    r.save(out / 'preflight.json', {'plan_sha256': r.sha(bundle / 'plan.json'),
        'study_variant': VARIANT, 'mode': 'scripted_software' if mock else 'live_model',
        'prior': prior, 'selected': selected, 'request_deadline_seconds': 60,
        'transport': r.CAPACITY_TRANSPORT, 'network_forbidden': r.OFFLINE})
    ledger_class = ContinueTurnLedger
    if gate is not None:
        class WaveLedger(ContinueTurnLedger):
            def reserve(self, payload, payload_bytes):
                try:
                    gate.first_reservation(self)
                    with gate.admission():
                        gate.check()
                        return super().reserve(payload, payload_bytes)
                except r.BudgetError:
                    if self.state['status'] != 'halted':
                        self.halt('deadline_wave_admission_stop')
                    raise
        ledger_class = WaveLedger
    ledger = ledger_class(out / 'accounting', scope='full', max_calls=198, max_usd='10',
        plan_sha256=r.sha(bundle / 'plan.json'), authorization=authorization,
        cumulative_guard=None if mock else r.all_history)
    base, headers = ((r.BASE_URL, {'Modal-Key': 'OFFLINE_ID', 'Modal-Secret': 'OFFLINE_SECRET'}) if mock else r.modal_config())
    client = r.FinancialByteClient(ledger=ledger, base_url=base, model=r.MODEL, headers=headers,
        diagnostics=out / 'transport_diagnostics', worker_sha256=plan['sources']['endpoint_probe_worker.py'],
        batch_deadline_monotonic=min(time.monotonic() + 1800,
            time.monotonic() + max(0, plan['paid_cutoff_unix'] - time.time())) if not mock else time.monotonic() + 1800,
        request_timeout=60, max_request_timeout=60)
    if mock:
        client.transport = MockTransport(mock)
        client.transport.client = client
    rows = []
    for name in selected:
        row = await case(fixed[name], client, out, inputs[name], gate)
        rows.append(row)
        report = {'study_variant': VARIANT, 'mode': 'scripted_software' if mock else 'live_model',
            'plan_sha256': r.sha(bundle / 'plan.json'), 'cases': rows, 'selected': selected,
            'all_passed': len(rows) == len(selected) and all(r['passed'] for r in rows),
            'ledger': ledger.summary(), 'network_attempts': r.NETWORK,
            'unstarted': [x for x in selected if x not in {c['spec']['id'] for c in rows}]}
        r.save(out / 'results.json', report)
        print(json.dumps({'case': name, 'complete': row['complete'], 'passed': row['passed'], 'metrics': row['metrics']}), flush=True)
        if not row['complete'] or ledger.state['status'] == 'halted':
            break
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'validate', 'run', 'worker'])
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--case', action='append')
    parser.add_argument('--seed')  # coordinator slot contains the case ID
    parser.add_argument('--lock-fd', type=int)
    parser.add_argument('--mock', choices=['success', 'noop', 'double_timeout_first', 'donate'])
    args = parser.parse_args()
    if args.command == 'prepare':
        result = asyncio.run(prepare(args.out))
    elif args.command == 'validate':
        from validate_deadline_pilot import validate
        result = asyncio.run(validate(args.bundle, args.out))
    elif args.command == 'worker':
        from deadline_supervisor import worker
        worker(args.bundle, args.out, args.seed, args.lock_fd, args.mock)
        return
    else:
        lock = Path(tempfile.gettempdir()) / ('modal-Hospital-' + hashlib.sha256(str(HERE).encode()).hexdigest()[:16] + '.lock')
        with lock.open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = asyncio.run(execute(args.bundle, args.out, args.case))
    print(json.dumps({k: v for k,v in result.items() if k != 'cases'}, sort_keys=True))


if __name__ == '__main__':
    main()
