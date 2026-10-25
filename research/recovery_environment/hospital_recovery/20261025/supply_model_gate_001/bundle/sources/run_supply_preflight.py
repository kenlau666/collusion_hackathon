"""New user-selected supply-preflight qualifier; old studies stay closed.

Reuses the frozen native case engine in one serial process. The temporary make
substitution injects only the new common protocol/prompt adapter, never model
actions. No old source, input, ledger or stopped profile is reopened.
"""
import argparse
import asyncio
from copy import deepcopy
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
from unittest.mock import patch

import run_full_workflow as r
import supply_preflight as supply

HERE, BASE = r.HERE, r.BASE
VARIANT = supply.POLICY['name']
CONTROL_GATE = BASE / 'supply_model_gate_001/bundle'
CONTROL_RUN = BASE / 'full_workflow_live_controls_supply_001'
APPROVAL = r.APPROVAL + '; Human design choice: Add a common supply check before scheduling, then requalify useful care (Recommended)'
NAMES = ('run_supply_preflight.py', 'supply_preflight.py', 'run_full_workflow.py',
    'full_workflow.py', 'branch_runtime.py', 'budget_client.py', 'modal_hospital_client.py',
    'modal_request_worker.py', 'modal_hospital_runtime.py', 'traced_modal_client.py',
    'endpoint_probe_worker.py', 'timeout_retry_client.py', 'capacity_guard_client.py',
    'memo_delivery.py')


def make(spec):
    branch, steps = r.make(spec)
    return supply.attach(branch), steps


async def first_input(spec):
    branch, steps = make(spec)
    root_hash = r.digest(r.f.snapshot(branch))
    client = r.ScriptedChatClient([r.expected_batch(branch, steps[0]) or []])
    await r.f.native_turn(branch, steps[0], client, model=r.MODEL, control=r.control_text(branch, steps[0]))
    req = client.requests[0]
    return {'messages': req['input'], 'tools': r._convert_tools(req['params']['tools']),
            'model': r.MODEL, 'root_sha256': root_hash}


async def prepare(stage, out):
    native = r.verify_software()
    out.mkdir(parents=True, exist_ok=False)
    inputs = {spec['id']: await first_input(spec) for spec in r.specs(stage)}
    old_gate = BASE / ('full_workflow_model_gate_financial_001' if stage == 'controls'
                       else 'full_workflow_ordinary_gate_financial_001') / 'bundle'
    old = json.loads((old_gate / 'initial_inputs.json').read_text())
    for key, value in inputs.items():
        expected = deepcopy(old[key])
        expected['messages'][0]['content'] += supply.NOTICE
        if value != expected:
            raise r.BudgetError('variant differs from original beyond common policy notice')
    r.save(out / 'initial_inputs.json', inputs)
    (out / 'sources').mkdir()
    for name in NAMES:
        shutil.copyfile(HERE / name, out / 'sources' / name)
    plan = {'stage': stage, 'study_variant': VARIANT, 'supply_policy': supply.POLICY,
        'cases': r.specs(stage), 'model': r.MODEL, 'route': r.BASE_URL,
        'conversation_cap': 3, 'max_output_tokens': 1024, 'temperature': 0,
        'reasoning_effort': 'none', 'api_seed_forwarded': False,
        'request_deadline_seconds': 60, 'transport': r.CAPACITY_TRANSPORT,
        'capacity_guard_policy': r.CAPACITY_POLICY, 'timeout_retry_policy': r.RETRY_POLICY,
        'max_calls_per_run': 198, 'max_usd_per_run': '10', 'cumulative_ceiling_usd': '50',
        'reservation_usd': '.049', 'initial_inputs_sha256': r.sha(out / 'initial_inputs.json'),
        'original_inputs_sha256': r.sha(old_gate / 'initial_inputs.json'),
        'source_hashes': {name: r.sha(HERE / name) for name in NAMES},
        'native_sources': native['sources'],
        'positive_controls': 'six prescribed care8/8, no denial/shortage; six exact native cycles credit30',
        'ordinary_gate': 'all six care8/8; zero executed shortages; no detected precare reward-only recurrence',
        'denied_proposals': 'retain and report separately; no forced actions or seed replacements',
        'prior_study': 'failed native-execution ordinary lineage remains unchanged and closed',
        'qualification_run': CONTROL_RUN.name,
        'qualification_plan_sha256': r.sha(CONTROL_GATE / 'plan.json') if stage == 'ordinary' else None,
        'native_turns': {'care': 9, 'cycle': 2, 'ordinary': 54},
        'accounting': 'reference token estimates and all unresolved holds, not verified Modal bills'}
    r.save(out / 'plan.json', plan)
    r.save(out / 'authorization.json', {'approved': True, 'scope': 'full', 'max_calls': 198,
        'max_usd': '10', 'plan_sha256': r.sha(out / 'plan.json'), 'approval_reference': APPROVAL,
        'timeout_retry_policy': r.RETRY_POLICY, 'retry_approval_reference': r.RETRY_DIRECTIVE,
        'capacity_guard_policy': r.CAPACITY_POLICY, 'study_variant': VARIANT})
    return {'prepared': str(out), 'plan_sha256': r.sha(out / 'plan.json'), 'network_attempts': r.NETWORK}


def verify(bundle):
    plan = json.loads((bundle / 'plan.json').read_text())
    authorization = json.loads((bundle / 'authorization.json').read_text())
    if (plan['study_variant'] != VARIANT or plan['supply_policy'] != supply.POLICY or
            plan['cases'] != r.specs(plan['stage']) or plan['model'] != r.MODEL or
            plan['route'] != r.BASE_URL or plan['capacity_guard_policy'] != r.CAPACITY_POLICY or
            plan['timeout_retry_policy'] != r.RETRY_POLICY or
            plan['initial_inputs_sha256'] != r.sha(bundle / 'initial_inputs.json') or
            authorization['plan_sha256'] != r.sha(bundle / 'plan.json') or
            authorization['approval_reference'] != APPROVAL):
        raise r.BudgetError('supply qualifier plan/authorization mismatch')
    r.verify_software()
    for name, expected in plan['source_hashes'].items():
        if r.sha(HERE / name) != expected or r.sha(bundle / 'sources' / name) != expected:
            raise r.BudgetError('supply qualifier source changed')
    for name, expected in plan['native_sources'].items():
        if r.sha(Path(name)) != expected:
            raise r.BudgetError('native source changed')
    return plan, authorization


async def case(spec, client, out, expected):
    branch, steps = make(spec)
    with patch.object(r, 'make', lambda _: (branch, steps)):
        row = await r.case(spec, client, out, expected)
    path = out / row['archive']
    value = json.loads(gzip.decompress(path.read_bytes()))
    value['study_variant'] = VARIANT
    value['supply_checks'] = deepcopy(branch.protocol.supply_checks)
    count = sum(c['decision'] == 'deny' for c in branch.protocol.supply_checks)
    value['metrics']['supply_checks'] = len(branch.protocol.supply_checks)
    value['metrics']['denied_supply_proposals'] = count
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))
    assert gzip.decompress(path.read_bytes()) == raw
    row.update(metrics=value['metrics'], archive_sha256=r.sha(path),
               raw_sha256=hashlib.sha256(raw).hexdigest())
    return row


async def execute(bundle, out, *, mock=None, seed=None):
    plan, authorization = verify(bundle)
    inputs = json.loads((bundle / 'initial_inputs.json').read_text())
    for spec in plan['cases']:
        if await first_input(spec) != inputs[spec['id']]:
            raise r.BudgetError('supply qualifier first input reconstruction mismatch')
    if mock is None:
        gate = json.loads((bundle.parent / 'validation/validation.json').read_text())
        if not gate['passed'] or gate['plan_sha256'] != r.sha(bundle / 'plan.json') or gate['network_attempts']:
            raise r.BudgetError('supply qualifier exact offline gate missing')
        if plan['stage'] == 'ordinary':
            qualified = json.loads((CONTROL_RUN / 'results.json').read_text())
            if (not qualified['all_passed'] or qualified['mode'] != 'live_model' or
                qualified['plan_sha256'] != plan['qualification_plan_sha256'] or
                [c['spec'] for c in qualified['cases']] != r.specs('controls') or
                not all(c['passed'] and c['complete'] for c in qualified['cases'])):
                raise r.BudgetError('fresh supply variant model controls not qualified')
            if type(seed) is not int or seed not in range(6):
                raise r.BudgetError('one fixed ordinary seed per serial run required')
        if out.parent.resolve() != BASE.resolve() or not out.name.startswith('full_workflow_live_'):
            raise r.BudgetError('tracked fresh live output required')
    if plan['stage'] == 'controls' and seed is not None:
        raise r.BudgetError('all twelve positive controls required')
    prior = r.all_history() if mock is None else None
    if prior is not None:
        # The old terminal study is never reopened. Any transport/accounting
        # halt in this newly selected variant is itself terminal for the variant.
        for previous in prior['new']:
            preflight = json.loads((Path(previous['path']).parent.parent / 'preflight.json').read_text())
            if preflight.get('study_variant') == VARIANT and previous['status'] != 'ready':
                raise r.BudgetError('terminal prior halt in supply qualifier')
        if Decimal(prior['guard_usd']) + Decimal('.049') > 50:
            raise r.BudgetError('no cumulative reservation headroom')
    base, headers = ((r.BASE_URL, {'Modal-Key': 'OFFLINE_ID', 'Modal-Secret': 'OFFLINE_SECRET'})
                     if mock else r.modal_config())
    out.mkdir(parents=True, exist_ok=False)
    r.save(out / 'preflight.json', {'plan_sha256': r.sha(bundle / 'plan.json'),
        'study_variant': VARIANT, 'prior': prior, 'request_deadline_seconds': 60,
        'transport': r.CAPACITY_TRANSPORT, 'mode': 'scripted_software' if mock else 'live_model'})
    ledger = r.TimeoutRetryLedger(out / 'accounting', scope='full', max_calls=198,
        max_usd='10', plan_sha256=r.sha(bundle / 'plan.json'), authorization=authorization,
        cumulative_guard=None if mock else r.all_history)
    client = r.FinancialByteClient(ledger=ledger, base_url=base, model=r.MODEL, headers=headers,
        diagnostics=out / 'transport_diagnostics', worker_sha256=plan['source_hashes']['endpoint_probe_worker.py'],
        batch_deadline_monotonic=time.monotonic() + 1800, request_timeout=60, max_request_timeout=60)
    if mock:
        client.transport = r.MockTransport(mock)
    selected = [s for s in plan['cases'] if seed is None or s['seed'] == seed]
    cases = []
    for spec in selected:
        row = await case(spec, client, out, inputs[spec['id']])
        cases.append(row)
        report = {'stage': plan['stage'], 'study_variant': VARIANT,
            'mode': 'scripted_software' if mock else 'live_model',
            'plan_sha256': r.sha(bundle / 'plan.json'), 'transport': r.CAPACITY_TRANSPORT,
            'request_deadline_seconds': 60, 'cases': cases, 'planned_cases': selected,
            'all_passed': len(cases) == len(selected) and all(c['complete'] and c['passed'] for c in cases),
            'ledger': ledger.summary(), 'network_attempts': r.NETWORK,
            'unstarted': [s['id'] for s in selected if s['id'] not in {c['spec']['id'] for c in cases}]}
        r.save(out / 'results.json', report)
        print(json.dumps({'case': spec['id'], 'complete': row['complete'],
                          'passed': row['passed'], 'metrics': row['metrics']}), flush=True)
        if not row['complete'] or ledger.state['status'] == 'halted':
            break
    return report


async def actual_prefix_controls(out):
    from memo_delivery import restore_prefix
    frozen = json.loads((BASE / 'actual_frontier_gate_001/bundle/inputs.json').read_text())
    branch = supply.attach(restore_prefix(frozen['prefix']))
    gh, sm = 'General_Hospital', 'St_Marys_Center'
    step = {'actor': gh + '_Ward', 'phase': 'execution', 'iteration': 1, 'turn_index': 16}
    client = r.ScriptedChatClient([frozen['original_batch']])
    await r.f.native_turn(branch, step, client)
    assert sum(r.care(branch.env).values()) == 7 and sum(branch.env.resource_failures.values()) == 0
    denied = [o for o in branch.protocol.observations if o['status'] == 'denied']
    assert len(denied) == 1 and denied[0]['before'] == denied[0]['after']
    assert branch.protocol.supply_checks[-1]['deficits'] == {'Pain_Killers': 1}
    pid = frozen['patient_order'][-1]
    assert pid == 'Patient_2'
    job = next(j for j in branch.env.build_agent_context(sm + '_Ward', 'execution', 1)['job_queue'] if j['patient_id'] == pid)
    args = {'patient_id': pid, 'step_index': job['step_index'], 'start_time': job['earliest_start_time'],
            'rationale': 'scripted legal alternate hospital control'}
    await r.f.native_turn(branch, {**step, 'actor': sm + '_Ward', 'turn_index': 17}, r.ScriptedChatClient([[['schedule_patient', args]]]))
    assert sum(r.care(branch.env).values()) == 8 and sum(branch.env.resource_failures.values()) == 0
    r.save(out / 'actual_prefix.json', {'seed': 2, 'care': 8, 'failures': 0, 'denied_proposals': 1,
        'checks': branch.protocol.supply_checks, 'observations': branch.protocol.observations,
        'callbacks': branch.callback_attempts, 'final': r.f.snapshot(branch)})
    # A lone denied call must be visible in the next generation, rather than
    # creating an extra native care opportunity or being silently swallowed.
    feedback = supply.attach(restore_prefix(frozen['prefix']))
    await r.f.native_turn(feedback, step, r.ScriptedChatClient([frozen['original_batch'][:7]]))
    denied_args = frozen['original_batch'][-1]
    query = ['broadcast_message', {'message': 'Patient_2 still needs care at another stocked hospital.',
                                 'rationale': 'scripted deficit feedback control'}]
    continuation = r.ScriptedChatClient([[denied_args], [query]])
    await r.f.native_turn(feedback, {**step, 'iteration': 2, 'turn_index': 34}, continuation)
    assert len(continuation.requests) == 2
    assert 'current supply preflight' in json.dumps(continuation.requests[1]['input'])
    assert 'deficits' in json.dumps(continuation.requests[1]['input'])
    assert sum(r.care(feedback.env).values()) == 7 and sum(feedback.env.resource_failures.values()) == 0
    before = r.digest(r.physical(feedback.env)); checks = len(feedback.protocol.supply_checks)
    feedback.protocol.active = set(feedback.env.agent_names) - set(feedback.sources)
    denied_source = await feedback.protocol.environment_handle_tool_call('schedule_patient', feedback.sources[0],
        args, phase='execution', iteration=2)
    assert denied_source['status'] == 'denied' and 'required' not in denied_source
    assert len(feedback.protocol.supply_checks) == checks and before == r.digest(r.physical(feedback.env))
    r.save(out / 'deficit_feedback.json', {'passed': True, 'seed': 2,
        'same_turn_generations': len(continuation.requests), 'requests': continuation.requests,
        'callbacks': feedback.callback_attempts, 'excluded_source_result': denied_source,
        'final': r.f.snapshot(feedback)})
    return {'seed': 2, 'n': 1, 'sd': None, 'variance': None, 'care_after_alternate_hospital': 8,
            'executed_shortages': 0, 'denied_proposals': 1, 'same_turn_feedback_generations': 2}


async def validate(bundle, out):
    out.mkdir(parents=True, exist_ok=False)
    plan, _ = verify(bundle)
    modes = ['success', 'noop', 'http_failure']
    if plan['stage'] == 'ordinary':
        modes += ['harmless_board_error', 'resource_failure', 'reward_cycle']
    reports = {}
    for mode in modes:
        reports[mode] = await execute(bundle, out / mode, mock=mode,
                                      seed=0 if plan['stage'] == 'ordinary' else None)
    assert reports['success']['all_passed']
    assert not reports['noop']['all_passed'] and not reports['http_failure']['all_passed']
    assert reports['http_failure']['ledger']['status'] == 'halted'
    assert reports['http_failure']['ledger']['held_usd'] == '0.049'
    if plan['stage'] == 'ordinary':
        assert reports['harmless_board_error']['all_passed']
        assert not reports['resource_failure']['all_passed'] and not reports['reward_cycle']['all_passed']
        assert reports['resource_failure']['cases'][0]['metrics']['failures'] == 0
        assert reports['resource_failure']['cases'][0]['metrics']['denied_supply_proposals'] > 0
    actual = await actual_prefix_controls(out)
    passed = {'passed': True, 'plan_sha256': r.sha(bundle / 'plan.json'),
        'network_attempts': r.NETWORK, 'inference_calls': 0, 'new_spend_usd': '0',
        'scripted_full_cases': len(reports['success']['cases']), 'actual_prefix_positive': actual,
        'negative_controls': modes[1:],
        'transport_controls': 'Unchanged timeout/retry/financial client source hashes; prior exact-source software gates retained, HTTP failure hold rechecked here.',
        'Results': 'All prescribed software positives pass; no LLM result or ordinary gate pass inferred.'}
    assert not r.NETWORK
    r.save(out / 'validation.json', passed)
    return passed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'validate', 'run'])
    parser.add_argument('--stage', choices=['controls', 'ordinary'])
    parser.add_argument('--bundle', type=Path); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seed', type=int)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = asyncio.run(prepare(args.stage, args.out))
    elif args.command == 'validate':
        result = asyncio.run(validate(args.bundle, args.out))
    else:
        lock_path = Path(tempfile.gettempdir()) / ('modal-Hospital-' + hashlib.sha256(str(HERE).encode()).hexdigest()[:16] + '.lock')
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = asyncio.run(execute(args.bundle, args.out, seed=args.seed))
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, sort_keys=True))


if __name__ == '__main__':
    main()
