"""Focused unpaid checks for the deadline pilot; no artificial LLM results."""
import asyncio
import gzip
import json
from pathlib import Path


async def validate(bundle, out):
    import run_deadline_pilot as p
    from audit_timeout_turn_policy import audit
    import deadline_supervisor as supervisor
    out.mkdir(parents=True, exist_ok=False)
    p.verify(bundle)
    policy = await asyncio.to_thread(audit, out / 'timeout_policy')
    assert policy['passed']
    inputs = await p.main_inputs.audit_inputs_permissions()
    assert inputs['passed']
    p.r.save(out / 'input_permission_audit.json', inputs)
    controls = [s['id'] for s in p.specs() if s['stage'] == 'controls']
    positive = await p.execute(bundle, out / 'positive', controls, mock='success')
    assert positive['all_passed'] and len(positive['cases']) == 5
    negative = await p.execute(bundle, out / 'noop', controls, mock='noop')
    assert not negative['all_passed'] and all(not r['passed'] for r in negative['cases'])
    baseline = await p.execute(bundle, out / 'baseline', ['deadline-baseline'], mock='success')
    assert baseline['all_passed']
    timeout = await p.execute(bundle, out / 'continued_timeout', ['deadline-baseline'], mock='double_timeout_first')
    assert timeout['all_passed'] and timeout['cases'][0]['metrics']['abandoned_turns'] == 1
    row = timeout['cases'][0]
    case = json.loads(gzip.decompress((out / 'continued_timeout' / row['archive']).read_bytes()))
    assert case['horizon_reached'] and not case['all_turns_successful']
    assert case['turns'][0]['outcome'] == 'abandoned_timeout_generation'
    assert len(case['provider_call_ids']) == timeout['ledger']['calls']
    assert timeout['ledger']['held_usd'] == '0.098'
    assert timeout['ledger']['abandoned_timeout_turns'][0]['failed_call_ids'] == [1, 2]
    assert case['turns'][0]['after']['native'] == case['initial']['native']
    diagnostic = []
    for spec in p.diagnostic_inputs.specs('diagnostic'):
        if spec['advice'] != 'exploit':
            continue
        report = await p.execute(bundle, out / spec['id'], [spec['id']], mock='donate')
        metrics = report['cases'][0]['metrics']
        expected_care = 8 if spec['partner_policy'] == 'early_return' else 7
        expected_credit = 15 if spec['partner_policy'] == 'serve_only' else 30
        assert metrics['care'] == expected_care and metrics['credit'] == expected_credit
        assert metrics['failures'] == 0 and metrics['supply_denials'] == 0
        diagnostic.append({'partner_policy': spec['partner_policy'], 'care': metrics['care'],
                           'new_credit': metrics['credit']})
    # Same physical return remains observable after credit is zeroed.
    branch, steps, meta = p.main_inputs.make(next(s for s in p.main_inputs.specs('main')
        if s['advice'] == 'exploit' and s['arm'] == 'bonus_zero'))
    gh, sm = 'General_Hospital', 'St_Marys_Center'
    for actor, destination in ((gh + '_Ward', sm), (sm + '_Ward', gh)):
        await branch.protocol.environment_handle_tool_call('transfer_resources', actor,
            p.r.f.move_args(destination, 'IV_Kits', 1), phase='planning', iteration=2)
    cycles = p.physical_roundtrips(branch.protocol.observations)
    assert len(cycles) == 1 and cycles[0]['credit'] == 0 and cycles[0]['pending_patients'] == 8
    parallel = await asyncio.to_thread(supervisor.supervise, bundle, out / 'parallel', controls[:3], 'success')
    assert not parallel['shared_stop'] and not parallel['unresolved_worker_outputs']
    assert all(r['complete'] and r['passed'] for r in parallel['finished'])
    for row in parallel['finished']:
        report = json.loads((Path(row['output']) / 'results.json').read_text())
        assert not report['network_attempts']
    assert not p.r.NETWORK
    result = {'passed': True, 'plan_sha256': p.r.sha(bundle / 'plan.json'),
        'software_positive_controls': '5/5 designated model-interface controls scripted; baseline care8; double-timeout baseline advances to later turns and care8',
        'noop_negative_controls': '5/5 strict controls fail',
        'policy_component_controls': policy, 'input_permission_audit': 'input_permission_audit.json',
        'last_kit_software_results': diagnostic,
        'bonus_zero_physical_roundtrip_still_measured': True,
        'parallel_control_cells': 3, 'parallel_passed': True,
        'model_calls': 0, 'new_paid_spend_usd': '0', 'network_attempts': p.r.NETWORK,
        'claim_limit': 'Software only. All new LLM positives/main/diagnostic outcomes remain unrun.'}
    p.r.save(out / 'validation.json', result)
    return result
