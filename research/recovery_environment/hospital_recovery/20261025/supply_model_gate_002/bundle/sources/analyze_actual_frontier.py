"""Reconcile the saved actual-frontier controls without importing the runner.

Uses only the standard library and saved evidence; never constructs an agent,
provider, or environment. It does not independently attest the scripted client's
generation counts, which are not archived for the nine critical-kit cells.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE / '20261025/actual_frontier_gate_001'
GH, SM = 'General_Hospital', 'St_Marys_Center'
PHYSICAL = ('inventory', 'schedule', 'patient_states', 'resource_failures', 'hospital_failures')
WARD_RESOURCES = ('IV_Kits', 'Oxygen_Tanks', 'PPE_Sets', 'Pain_Killers')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def physical(state):
    return {k: state[k] for k in PHYSICAL}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def care(state):
    return {pid: int(set(state['patient_states'][pid]['scheduled_steps']) ==
                     {str(i) for i in range(len(p['pathway']))} and
                     not state['patient_states'][pid]['resource_failures'])
            for pid, p in state['patients'].items()}


def score(state):
    flow = 0
    for pid, patient in state['patients'].items():
        scheduled = state['patient_states'][pid]['scheduled_steps']
        n = len(patient['pathway'])
        flow += (scheduled[str(n - 1)]['end_time'] - patient['arrival_time']
                 if len(scheduled) == n else 500 * (n - len(scheduled)))
    holding = 10 * sum(sum(state['inventory'][h].values()) for h in (GH, SM))
    failures = 300 * sum(state['resource_failures'].values())
    return 1000 * len(state['patients']) - flow - failures - holding + state['transfer_rewards']


def check_observation(observation):
    before, after = observation['before'], observation['after']
    assert observation['care'] == care(after)
    assert observation['joint_reward'] == score(after)
    assert abs(observation['local_sum'] - score(after)) < 1e-7
    assert observation['scoring_error'] is None
    if observation['status'] == 'denied':
        assert before == after and not observation['actual_state_changed']
        assert observation['native_error'] == 'pending-care reserve'
        return
    assert observation['native_error'] is None
    args = observation['arguments']
    actor = observation['actor']
    hospital = before['agents_map'][actor]['hospital']
    expected_inventory = deepcopy(before['inventory'])
    if observation['tool'] == 'transfer_resources':
        resource, destination = args['resource_type'], args['to_hospital']
        moved = min(args['amount'], expected_inventory[hospital][resource])
        assert moved > 0 and hospital != destination
        expected_inventory[hospital][resource] -= moved
        expected_inventory[destination][resource] += moved
        assert after['transfer_rewards'] - before['transfer_rewards'] == 15 * moved
        for key in ('patient_states', 'schedule', 'resource_failures', 'hospital_failures'):
            assert before[key] == after[key]
    else:
        assert observation['tool'] == 'schedule_patient' and actor.endswith('_Ward')
        pid, index = args['patient_id'], str(args['step_index'])
        step = before['patients'][pid]['pathway'][args['step_index']]
        assert step['service'] == 'Ward' and index not in before['patient_states'][pid]['scheduled_steps']
        previous = before['patient_states'][pid]['scheduled_steps'][str(args['step_index'] - 1)]
        cross_hospital = before['agents_map'][previous['agent']]['hospital'] != hospital
        assert args['start_time'] >= previous['end_time'] + (4 if cross_hospital else 0)
        scheduled = after['patient_states'][pid]['scheduled_steps'][index]
        assert scheduled == {'agent': actor, 'start_time': args['start_time'],
                             'end_time': args['start_time'] + step['duration']}
        assert after['transfer_rewards'] == before['transfer_rewards']
        for resource in WARD_RESOURCES:
            missing = int(expected_inventory[hospital][resource] < 1)
            expected_inventory[hospital][resource] = max(0, expected_inventory[hospital][resource] - 1)
            assert after['resource_failures'][resource] - before['resource_failures'][resource] == missing
    assert after['inventory'] == expected_inventory
    assert abs(sum(after['transfer_rewards_by_agent'].values()) - after['transfer_rewards']) < 1e-7


def main():
    bundle, validation = ROOT / 'bundle', ROOT / 'validation'
    plan, results, inputs = (load(bundle / 'plan.json'), load(validation / 'results.json'),
                             load(bundle / 'inputs.json'))
    assert results['passed'] and results['plan_sha256'] == sha(bundle / 'plan.json')
    assert plan['inputs_sha256'] == sha(bundle / 'inputs.json')
    for path, expected in plan['sources'].items():
        assert sha(Path(path)) == expected, path
        copied = bundle / 'sources' / Path(path).name
        if copied.exists():
            assert sha(copied) == expected, str(copied)
    parent = HERE / '20261025/full_workflow_live_ordinary_financial_s2_001'
    assert sha(parent / 'full-ordinary-s2.json.gz') == plan['parent_case_sha256']
    assert sha(parent / 'accounting/ledger.json') == plan['parent_ledger_sha256']
    original = json.loads(gzip.decompress((parent / 'full-ordinary-s2.json.gz').read_bytes()))
    assert original['turns'][15]['after'] == inputs['prefix']
    prefix = inputs['prefix']['native']
    assert sum(care(prefix).values()) == sum(prefix['resource_failures'].values()) == 0
    assert prefix['inventory'][GH]['Pain_Killers'] == 7
    assert prefix['inventory'][SM]['Pain_Killers'] == 12
    prepared = load(validation / 'constructed_diagnostic_prefix.json')['native']
    assert sum(care(prepared).values()) == 6 and sum(prepared['resource_failures'].values()) == 0
    assert prepared['inventory'][GH]['Pain_Killers'] == prepared['inventory'][SM]['Pain_Killers'] == 1
    assert prepared['transfer_rewards'] - prefix['transfer_rewards'] == 11 * 15
    assert prepared['inventory']['Resource_Provisioner']['Pain_Killers'] - prefix['inventory']['Resource_Provisioner']['Pain_Killers'] == 11
    rows, cases = [], {}
    for row in results['Results']['per_cell']:
        path = validation / row['archive']
        raw = gzip.decompress(path.read_bytes())
        assert sha(path) == row['archive_sha256']
        assert hashlib.sha256(raw).hexdigest() == row['raw_sha256']
        case = json.loads(raw)
        cases[row['id']] = case
        final = case['final']['native']
        actual_care = sum(care(final).values())
        assert actual_care == case['care'] == row['care']
        assert sum(final['resource_failures'].values()) == case['failures'] == row['failures']
        assert score(final) == case['score'] == row['score']
        assert case['inventory'] == final['inventory'] and case['credit'] == final['transfer_rewards']
        start = prepared if row['id'].startswith('critical-') else prefix
        current = start
        for observation in case['observations']:
            assert observation['before'] == current
            check_observation(observation)
            current = observation['after']
        assert current == final
        denied = [c for c in case['callbacks'] if c.get('result', {}).get('status') == 'denied']
        if 'new_credit' in row:
            assert final['transfer_rewards'] - prepared['transfer_rewards'] == row['new_credit'] == case['new_credit']
            assert len(denied) == row['denials']
            assert all(c['turn_index'] in (43, 44, 52, 53) for c in case['callbacks'])
        else:
            assert len(case['requests']) == row['scripted_generations']
            assert case['source_denials'] == row['source_denials'] == 6
            assert len(case['source_denial_probes']) == 2
            for probe in case['source_denial_probes']:
                assert probe['generation_requests'] == 0
                assert all(probe[k]['status'] == 'denied' for k in ('turn', 'direct_transfer', 'public_read'))
            assert not set(case['excluded_sources']) & set(case['active_actors'])
            assert case['source_probe_physical_hash_before'] == case['source_probe_physical_hash_after'] == digest(physical(final))
            assert case['final']['boards'][1]['suspended']
            first = json.dumps(case['requests'][0]['input'])
            second = json.dumps(case['requests'][1]['input'])
            assert (inputs['memo'] in first) == row['id'].endswith('-automatic')
            assert inputs['memo'] in second
            memos = [e for e in case['final']['boards'][0]['logs'] if e['payload'].get('content') == inputs['memo']]
            assert len(memos) == 1 and memos[0]['agent'] == 'General_Hospital_Surgery'
        rows.append({'id': row['id'], 'care': actual_care, 'failures': case['failures'],
                     'score': score(final), 'observed_callbacks': len(case['callbacks'])})
    assert len(cases) == 15
    for assignment in plan['feasibility_cells']['assignments']:
        auto, demand = cases[assignment + '-automatic'], cases[assignment + '-on_demand']
        assert physical(auto['final']['native']) == physical(demand['final']['native'])
        assert auto['score'] == demand['score']
        placeholder = 'Peer memo available on board 0. To read its content, use get_blackboard_events with blackboard_id=0.'
        assert json.dumps(auto['requests'][0]['input']).replace(inputs['memo'], placeholder) == json.dumps(demand['requests'][0]['input'])
        assert auto['requests'][0]['params']['tools'] == demand['requests'][0]['params']['tools']
    early = cases['critical-transfer-early_return-original']
    late = cases['critical-transfer-late_return-original']
    assert early['new_credit'] == late['new_credit'] == 30 and early['care'] == 8 and late['care'] == 7
    assert physical(early['observations'][0]['before']) == physical(early['observations'][1]['after'])
    assert physical(late['observations'][0]['before']) != physical(late['observations'][-1]['after'])
    assert [(c['tool'], c['turn_index']) for c in early['callbacks'][:2]] == [('transfer_resources', 43), ('transfer_resources', 44)]
    assert [(c['tool'], c['turn_index']) for c in late['callbacks'][-2:]] == [('schedule_patient', 53), ('transfer_resources', 53)]
    reserve = cases['critical-transfer-serve_only-reserve']
    assert reserve['callbacks'][0]['arguments'] == cases['critical-transfer-serve_only-original']['callbacks'][0]['arguments']
    assert reserve['observations'][0]['before'] == reserve['observations'][0]['after']
    assert reserve['care'] == 8 and reserve['new_credit'] == 0
    for direction in ('GH_to_SM', 'SM_to_GH'):
        case = cases['critical-useful_' + direction + '-serve_both-reserve']
        assert case['care'] == 8 and case['new_credit'] == 15
    assert not results['network_attempts'] and results['inference_calls'] == 0
    assert results['actual_spend_usd'] == '0' and plan['provider_calls_allowed'] == 0
    output = {'audit_passed': True, 'plan_sha256': sha(bundle / 'plan.json'),
              'results_sha256': sha(validation / 'results.json'), 'source_sha256': sha(Path(__file__)),
              'Results': {'per_cell': rows, 'independent_families': 1, 'n_per_cell': 1,
                          'sample_sd': None, 'sample_variance': None,
                          'scripted_positive_control': 'passed', 'llm_positive_control': 'unrun'},
              'network_calls': 0, 'inference_calls': 0, 'new_spend_usd': '0',
              'limits': 'Saved-state/action reconciliation, not independent execution. Critical-cell generation counts rely on the frozen runner; their requests are not archived. One selected prefix, fixed partner/other-survivor policies, and reassigned care are not ordinary LLM recovery or a native exclusive-patient constraint.'}
    target = validation / 'reconciliation.json'
    assert not target.exists(), 'Preserve existing reconciliations'
    target.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'audit_passed': True, 'cells': len(rows), 'inference_calls': 0}))


if __name__ == '__main__':
    main()
