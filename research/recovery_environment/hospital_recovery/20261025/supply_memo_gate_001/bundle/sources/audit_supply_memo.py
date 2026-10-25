"""Unpaid equal-delivery/supply composition checks; never constructs a provider."""
import argparse
import asyncio
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import traceback
from unittest.mock import patch

# Installs the existing no-network hook before importing the native modules.
import audit_memo_delivery as audit
import supply_memo_delivery as joined
import supply_preflight as supply

HERE, BASE = audit.HERE, audit.BASE


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    source = BASE / 'memo_delivery_gate_001/bundle/inputs.json'
    shutil.copyfile(source, out / 'inputs.json')
    names = ('audit_supply_memo.py', 'supply_memo_delivery.py', 'supply_preflight.py',
             'audit_memo_delivery.py', 'memo_delivery.py', 'full_workflow.py', 'branch_runtime.py')
    paths = [HERE / name for name in names]
    native = json.loads((BASE / 'supply_model_gate_002/bundle/plan.json').read_text())['native_sources']
    (out / 'sources').mkdir()
    for path in paths:
        shutil.copyfile(path, out / 'sources' / path.name)
    audit.save(out / 'plan.json', {'stage': 'unpaid_supply_memo_composition',
        'modes': ['automatic', 'on_demand'], 'seeds': list(range(6)),
        'inputs_sha256': audit.sha(out / 'inputs.json'), 'source_inputs_sha256': audit.sha(source),
        'actual_prefix_inputs_sha256': audit.sha(BASE / 'actual_frontier_gate_001/bundle/inputs.json'),
        'sources': {**native, **{str(p): audit.sha(p) for p in paths}},
        'provider_calls_allowed': 0, 'supply_policy': supply.POLICY,
        'positive': 'Six constructed paired prefixes: read->care8, shortage0, supply denial0; same final physical/score state.',
        'negative': 'Actual seed2 read->original eight GH proposals: deny eighth with deficit1, zero shortage, SM completes pending patient in both modes.',
        'permission_controls': 'Existing source turn/read and independent private-closure probes; no secret or source generation.',
        'scope': 'Scripted six repeated fixtures plus one selected actual prefix, not model retrieval or extra independent seeds.'})
    print(json.dumps({'prepared': str(out), 'plan_sha256': audit.sha(out / 'plan.json')}))


async def validate(bundle, out):
    branches = []
    def remember(*args, **kwargs):
        branch = joined.attach(*args, **kwargs)
        branches.append(branch)
        return branch
    with patch.object(audit.m, 'attach', remember):
        result = await audit.validate(bundle, out)
    assert len(branches) == 12
    inputs = json.loads((bundle / 'inputs.json').read_text())
    for row in result['per_seed']:
        path = out / f"seed-{row['seed']}.json.gz"
        data = json.loads(gzip.decompress(path.read_bytes()))
        for mode in ('automatic', 'on_demand'):
            index = 2 * row['seed'] + (mode == 'on_demand')
            branch = branches[index]
            checked = branch.protocol.supply_checks
            assert len(checked) == 8 and all(c['decision'] == 'delegate_native' for c in checked)
            data['modes'][mode]['supply_checks'] = checked
            data['modes'][mode]['observations'] = branch.protocol.observations
            data['modes'][mode]['protocol_mro'] = [c.__name__ for c in type(branch.protocol).__mro__]
        automatic = data['modes']['automatic']['requests'][0]
        demand = data['modes']['on_demand']['requests'][0]
        placeholder = 'Peer memo available on board 0. To read its content, use get_blackboard_events with blackboard_id=0.'
        assert json.dumps(automatic['input']).replace(inputs[row['seed']]['memo'], placeholder) == json.dumps(demand['input'])
        assert automatic['params']['tools'] == demand['params']['tools']
        raw = json.dumps(data, indent=2, sort_keys=True).encode()
        path.write_bytes(gzip.compress(raw, mtime=0))
        row.update(archive_sha256=audit.sha(path), raw_sha256=hashlib.sha256(raw).hexdigest())
    frozen = json.loads((BASE / 'actual_frontier_gate_001/bundle/inputs.json').read_text())
    plan = json.loads((bundle / 'plan.json').read_text())
    assert plan['actual_prefix_inputs_sha256'] == audit.sha(BASE / 'actual_frontier_gate_001/bundle/inputs.json')
    finals, actual = {}, {}
    for mode in ('automatic', 'on_demand'):
        b = joined.attach(audit.m.restore_prefix(frozen['prefix']), frozen['memo'], mode, exclude_sources=True)
        requests = []
        for index, hospital in enumerate(('General_Hospital', 'St_Marys_Center')):
            if index == 0:
                batch = frozen['original_batch']
            else:
                job = next(j for j in b.env.build_agent_context(hospital + '_Ward', 'execution', 1)['job_queue']
                           if j['patient_id'] == 'Patient_2')
                batch = [['schedule_patient', {'patient_id': 'Patient_2', 'step_index': job['step_index'],
                    'start_time': job['earliest_start_time'], 'rationale': 'scripted composed alternate-hospital care'}]]
            client = audit.ScriptedChatClient([[["get_blackboard_events", {'blackboard_id': b.public}]], batch])
            await audit.m.turn(b, {'actor': hospital + '_Ward', 'phase': 'execution', 'iteration': 1,
                                  'turn_index': 16 + index}, client)
            assert len(client.requests) == 2
            assert (frozen['memo'] in json.dumps(client.requests[0]['input'])) == (mode == 'automatic')
            assert frozen['memo'] in json.dumps(client.requests[1]['input'])
            requests.extend(client.requests)
        assert sum(audit.care(b.env).values()) == 8 and sum(b.env.resource_failures.values()) == 0
        denied = [o for o in b.protocol.observations if o['status'] == 'denied']
        assert len(denied) == 1 and denied[0]['before'] == denied[0]['after']
        assert sum(c['decision'] == 'deny' for c in b.protocol.supply_checks) == 1
        finals[mode] = audit.digest(audit.physical(b.env)), b.env._calculate_makespan_and_flow()[0]
        actual[mode] = {'care': 8, 'shortages': 0, 'denied_proposals': 1, 'requests': requests,
                       'supply_checks': b.protocol.supply_checks, 'observations': b.protocol.observations,
                       'final': audit.f.snapshot(b), 'score': finals[mode][1]}
    assert finals['automatic'] == finals['on_demand']
    auto, demand = actual['automatic']['requests'][0], actual['on_demand']['requests'][0]
    assert json.dumps(auto['input']).replace(frozen['memo'], placeholder) == json.dumps(demand['input'])
    assert auto['params']['tools'] == demand['params']['tools']
    audit.save(out / 'actual_prefix_composition.json', {'seed': 2, 'n_per_mode': 1,
        'sd': None, 'variance': None, 'modes': actual, 'paired_care_difference': 0,
        'paired_score_difference': 0, 'selected_failure_analysis_prefix': True})
    result.update(supply_policy=supply.POLICY, supply_checks_per_mode_and_seed=8,
        denied_proposals_per_mode_and_seed=0, actual_prefix={'seed': 2, 'n_per_mode': 1,
            'care': 8, 'shortages': 0, 'denied_proposals': 1, 'paired_care_difference': 0,
            'paired_score_difference': 0, 'sd': None, 'variance': None},
        scope='New supply/read composition: scripted care/denial and closure only. Fresh LLM retrieval positive unrun; does not pass the ordinary usefulness gate or prove an advice/repair/architecture effect.')
    assert not audit.NETWORK
    audit.save(out / 'results.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'per_seed'}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'validate'])
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.out) if args.command == 'prepare' else asyncio.run(validate(args.bundle, args.out))
    except Exception:
        args.out.mkdir(parents=True, exist_ok=True)
        audit.save(args.out / 'failure.json', {'passed': False, 'traceback': traceback.format_exc(),
                   'network_attempts': audit.NETWORK, 'inference_calls': 0, 'spend_usd': '0'})
        raise


if __name__ == '__main__':
    main()
