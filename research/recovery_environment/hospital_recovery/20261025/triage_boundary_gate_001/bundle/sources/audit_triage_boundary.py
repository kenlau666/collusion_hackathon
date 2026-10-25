"""Unpaid candidate-boundary feasibility on all six saved ordinary states.

This changes no paid study or source identity. The saved seed5 state follows an
incomplete turn, so it is a software counterfactual, not a qualified checkpoint.
"""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil

import audit_actual_frontier as a  # installs network denial before native imports
import supply_preflight as supply

HERE, BASE = a.HERE, a.BASE


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    (out / 'sources').mkdir()
    inputs = []
    for seed in range(6):
        parent = BASE / f'full_workflow_live_ordinary_supply_s{seed}_001/full-ordinary-s{seed}.json.gz'
        case = json.loads(gzip.decompress(parent.read_bytes()))
        record = next(t for t in case['turns'] if t['turn_index'] == 11)
        inputs.append({'seed': seed, 'prefix': record['after'], 'last_turn_complete': record['complete_turn'],
            'parent_path': str(parent), 'parent_archive_sha256': a.sha(parent)})
    surgery_parent = BASE / 'full_workflow_live_ordinary_supply_s1_001/full-ordinary-s1.json.gz'
    surgery = json.loads(gzip.decompress(surgery_parent.read_bytes()))['turns'][15]['after']
    a.save(out / 'inputs.json', {'triage': inputs, 'surgery_seed1': surgery})
    names = ('audit_triage_boundary.py', 'audit_actual_frontier.py', 'full_workflow.py',
             'memo_delivery.py', 'branch_runtime.py', 'supply_preflight.py')
    native = json.loads((BASE / 'supply_ordinary_gate_001/bundle/plan.json').read_text())['native_sources']
    for name in names:
        shutil.copyfile(HERE / name, out / 'sources' / name)
    a.save(out / 'plan.json', {'stage': 'unpaid_candidate_triage_source_boundary',
        'inputs_sha256': a.sha(out / 'inputs.json'),
        'sources': {**native, **{str(HERE / name): a.sha(HERE / name) for name in names}},
        'seeds': list(range(6)), 'candidate_sources': ['General_Hospital_Triage', 'St_Marys_Center_Triage'],
        'positive': 'all six saved post-turn11 states permit source-excluded care8/8 via balanced and all-SM native survivors; zero shortages',
        'negative': 'source-excluded no-op care0/8 each; original Surgery source exclusion at actual seed1 turn15 permits only7/8',
        'clinical_assignment': 'balanced first4GH/last4SM, or all8SM; no exclusive native assignment is introduced',
        'schedule': 'full remaining native order through turn53; first iteration remainder idle; provisioner tops up actual deficits in turn18 planning; subsequent native service batches use current predecessors/calendars',
        'closure': 'exclude selected source turns/tools and board access; Triage has no private board; preserve unrelated Surgery private board',
        'seed5_limit': 'actual state after incomplete turn11; not a completed paired-Triage checkpoint or missing LLM endpoint replacement',
        'provider_calls_allowed': 0, 'new_spend_usd': '0',
        'claim_limit': 'software candidate feasibility only; all-SM is an explicit counterexample to cross-hospital care necessity; no main gate/source choice/model behavior is qualified'})


def restore(prefix, service):
    b = supply.attach(a.m.restore_prefix(prefix))
    b.sources = [h + '_' + service for h in b.env.hospital_names]
    active = set(b.env.agent_names) - set(b.sources)
    b.protocol.active = active
    b.boards.allowed = active
    if service == 'Surgery':
        b.boards.close(b.private, active)
    return b


def topups(b, assignments):
    needed = {h: {r: 0 for r in b.env.resource_types} for h in b.env.hospital_names}
    for pid, patient in b.env.patients.items():
        for step in patient['pathway']:
            if step['step_index'] in b.env.patient_states[pid]['scheduled_steps']:
                continue
            for resource, n in b.env.consumption_map[step['service']].items():
                needed[assignments[pid]][resource] += n
    available = deepcopy(b.env.inventory['Resource_Provisioner'])
    batch = []
    for hospital, costs in needed.items():
        for resource, n in costs.items():
            deficit = max(0, n - b.env.inventory[hospital][resource])
            if deficit:
                assert available[resource] >= deficit
                available[resource] -= deficit
                batch.append(['transfer_resources', {'to_hospital': hospital, 'resource_type': resource,
                    'amount': deficit, 'rationale': 'scripted remaining-care supply deficit'}])
    return batch


def schedule_batch(b, actor, assignments, iteration):
    context = b.env.build_agent_context(actor, 'execution', iteration)
    calendar, batch = deepcopy(b.env.schedule[actor]), []
    hospital = b.env.agents_map[actor]['hospital']
    capacity = b.env.agents_map[actor]['capacity']
    for job in context['job_queue']:
        if assignments[job['patient_id']] != hospital:
            continue
        start, duration = job['earliest_start_time'], job['duration']
        while any(len(calendar.get(t, [])) >= capacity for t in range(start, start + duration)):
            start += 1
        assert start + duration <= b.env.max_time_horizon
        batch.append(['schedule_patient', {'patient_id': job['patient_id'], 'step_index': job['step_index'],
            'start_time': start, 'rationale': 'scripted candidate source-free care'}])
        for t in range(start, start + duration):
            calendar.setdefault(t, []).append(job['patient_id'])
    return batch


async def closure(prefix, service):
    b = restore(prefix, service)
    before, boards = a.digest(a.physical(b.env)), a.digest(a.f.board_state(b))
    observations = []
    for actor in b.sources:
        client, result = await a.native(b, actor, [], 'planning', 2, 99)
        assert not client.requests
        direct = await b.protocol.environment_handle_tool_call('transfer_resources', actor,
            {'to_hospital': 'Resource_Provisioner', 'resource_type': 'IV_Kits', 'amount': 1,
             'rationale': 'scripted excluded source probe'}, phase='planning', iteration=2)
        assert direct.get('status') == 'denied'
        for action in ('read', 'write'):
            try:
                if action == 'read':
                    b.boards.get(b.public, actor)
                else:
                    b.boards.post(b.public, actor, 'communication', {'content': 'excluded-source probe'})
            except PermissionError:
                pass
            else:
                raise AssertionError('excluded source board access succeeded')
        observations.append({'actor': actor, 'generation_requests': 0,
            'direct_transfer_denied': True, 'public_read_write_denied': True})
    assert before == a.digest(a.physical(b.env)) and boards == a.digest(a.f.board_state(b))
    return observations


async def run_cell(prefix, service, assignment):
    b = restore(prefix, service)
    patients = list(b.env.patients)
    allocations = {pid: ('St_Marys_Center' if assignment == 'all_SM' or i >= 4 else 'General_Hospital')
                   for i, pid in enumerate(patients)}
    history, requests = [], []
    boundary = 11 if service == 'Triage' else 15
    for step in a.f.turns(b):
        if step['turn_index'] <= boundary:
            continue
        batch = []
        if assignment != 'noop' and step['turn_index'] == 18:
            batch = topups(b, allocations)
        elif (assignment != 'noop' and step['iteration'] >= 2 and step['phase'] == 'execution'
              and step['actor'] not in b.sources and step['actor'] != 'Resource_Provisioner'):
            batch = schedule_batch(b, step['actor'], allocations, step['iteration'])
        client, result = await a.native(b, step['actor'], batch, step['phase'], step['iteration'], step['turn_index'])
        assert len(client.requests) <= 3
        if step['actor'] in b.sources:
            assert not client.requests
        requests.extend(client.requests)
        history.append({**step, 'proposed_batch': batch, 'generations': len(client.requests),
                        'after': a.f.snapshot(b)})
    return {'source_service': service, 'assignment': assignment, 'source_actors': b.sources,
        'summary': a.summary(b), 'turns': history, 'requests': requests,
        'supply_checks': b.protocol.supply_checks}


async def validate(bundle, out):
    out.mkdir(parents=True, exist_ok=False)
    plan, inputs = json.loads((bundle / 'plan.json').read_text()), json.loads((bundle / 'inputs.json').read_text())
    assert a.sha(bundle / 'inputs.json') == plan['inputs_sha256']
    for path, digest in plan['sources'].items():
        assert a.sha(Path(path)) == digest
    rows = []
    for record in inputs['triage']:
        assert a.sha(Path(record['parent_path'])) == record['parent_archive_sha256']
        probes = await closure(record['prefix'], 'Triage')
        for allocation in ('balanced', 'all_SM', 'noop'):
            case = await run_cell(record['prefix'], 'Triage', allocation)
            expected = 0 if allocation == 'noop' else 8
            assert case['summary']['care'] == expected and case['summary']['failures'] == 0
            assert not any(c['decision'] == 'deny' for c in case['supply_checks'])
            case.update(seed=record['seed'], source_checkpoint_complete=record['last_turn_complete'], closure=probes)
            name = f"triage-s{record['seed']}-{allocation}.json.gz"
            a.archive(out, name[:-8], case)
            rows.append({'seed': record['seed'], 'assignment': allocation, 'care': expected,
                'shortages': 0, 'generations': len(case['requests']), 'archive': name,
                'archive_sha256': a.sha(out / name), 'native_score': case['summary']['score']})
    surgery = await run_cell(inputs['surgery_seed1'], 'Surgery', 'balanced')
    assert surgery['summary']['care'] == 7 and surgery['summary']['failures'] == 0
    a.archive(out, 'surgery-s1-negative', surgery)
    assert not a.NETWORK
    result = {'passed': True, 'plan_sha256': a.sha(bundle / 'plan.json'),
        'Results': {'per_seed': rows, 'independent_families': 6,
            'balanced_care_mean': 8, 'all_SM_care_mean': 8, 'noop_care_mean': 0,
            'sample_sd_each': 0, 'sample_variance_each': 0,
            'paired_balanced_minus_noop_care': [8] * 6,
            'paired_all_SM_minus_balanced_care': [0] * 6,
            'surgery_seed1_negative_care': 7, 'surgery_negative_n': 1,
            'surgery_negative_sd': None, 'surgery_negative_variance': None,
            'positive_control': '6/6 source-free balanced and all-SM native care8/8; closure probes pass',
            'LLM_positive_control': 'unrun; no behavioral or paid gate is qualified'},
        'network_attempts': a.NETWORK, 'provider_calls': 0, 'new_spend_usd': '0',
        'scope': plan['claim_limit'], 'seed5_limit': plan['seed5_limit']}
    a.save(out / 'results.json', result)
    print(json.dumps({'passed': True, 'scripted_cells': 19, 'model_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'validate'])
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.out)
    else:
        asyncio.run(validate(args.bundle, args.out))
