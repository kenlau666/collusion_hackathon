"""Offline audit of the frozen inputs, completed calls and derived offer results."""
import json
from pathlib import Path
import sys

import offer_diagnostic as d
from test_offer_diagnostic import full_production_guard


def verify(directory):
    plan = d.read(directory/'plan.json')
    calls = sorted((directory/'calls').glob('*.json'))
    assert len(calls) == len(plan['schedule']) == 18
    execution = d.read(directory/'execution.json')
    assert execution['plan_sha256'] == d.sha(directory/'plan.json')
    assert execution['protocol_sha256'] == d.sha(directory/'protocol_before_inference.md')
    assert d.read(directory/'offline_validation.json')['passed']
    assert d.read(directory/'offline_validation.json')['plan_sha256'] == execution['plan_sha256']
    for relative, expected in plan['source_sha256'].items():
        assert d.sha(directory/'source'/relative) == expected
        # Authoritative prose may now report results; scientific code may not drift.
        if relative.endswith('.py'):
            assert d.sha(d.ROOT/relative) == expected
    audit = d.read(d.SOURCE/'analysis/offer_audit.json')
    for case, old in zip(plan['cases'], audit['cases']):
        assert case['source_sha256'] == old['call_sha256'] == d.sha(d.ROOT/case['source_call'])
    acceptance = {c:0 for c in 'ABC'}
    tokens = [0,0]
    raw_pairs = {seed:{} for seed in range(6)}
    control_passes = 0
    hashes = {}
    for path, scheduled in zip(calls,plan['schedule']):
        call = d.read(path)
        assert all(call[k] == scheduled[k] for k in ('order','block','seed','condition','sha256'))
        assert call['request_body'] == d.read(directory/scheduled['request'])
        assert d.sha(directory/scheduled['request']) == scheduled['sha256']
        assert call['status'] == 'success' and call['http_status'] == 200
        assert json.loads(call['raw_http_body']) == call['response']
        response = call['response']
        assert response['model'] == plan['model']
        choice = response['choices'][0]
        assert choice['finish_reason'] == 'stop'
        assert choice['message']['content'] == call['raw_response']
        answer = json.loads(choice['message']['content'])
        complete = choice['finish_reason'] == 'stop'
        case = plan['cases'][call['seed']]
        accepted = full_production_guard({'text':call['raw_response'],'complete':complete},case['initiator'])
        assert accepted == call['outcome']['validator_acceptance']
        acceptance[call['condition']] += int(accepted)
        if call['condition']=='C':
            passed = accepted and answer['partner'] == case['designated_partner']
            assert passed == call['outcome']['control_pass']
            control_passes += passed
        elif call['condition'] in 'AB':
            raw_pairs[call['seed']][call['condition']] = int(accepted)
        for i,k in enumerate(('prompt_tokens','completion_tokens')):
            tokens[i] += response['usage'][k]
        hashes[str(path.relative_to(directory))] = d.sha(path)
    results = d.read(directory/'results.json')
    for c in 'ABC':
        assert acceptance[c] == results['conditions'][c]['acceptances']
        assert results['conditions'][c]['scheduled_denominator'] == 6
    assert control_passes == results['conditions']['C']['control_passes']
    for pair in results['paired']:
        raw = raw_pairs[pair['seed']]
        assert raw['B'] - raw['A'] == pair['B_minus_A']
    usage = d.read(directory/'usage.json')
    assert usage['attempts'] == usage['http_successes'] == 18 and usage['failed_attempts']==0
    assert tokens == [usage['reported_input_tokens'],usage['reported_output_tokens']]
    assert abs(d.reference_cost(*tokens)-usage['reference_cost_usd']) < 1e-12
    completion = d.read(directory/'completion.json')
    for key in ('partner_calls','game_steps','formation_episodes','recovery_continuations','retries'):
        assert completion[key] == 0
    verification = dict(passed=True,verified_at=d.now(),inference_calls=0,
        method='Independent provider-body accounting and complete production consent AST with offline invitation sentinel',
        source_cases=6,call_records=18,acceptance_counts=acceptance,control_passes=control_passes,
        input_tokens=tokens[0],output_tokens=tokens[1],call_sha256=hashes,
        verifier_source_sha256=d.sha(Path(__file__)),plan_sha256=d.sha(directory/'plan.json'))
    d.save(directory/'post_run_verification.json',verification)
    print(json.dumps({k:v for k,v in verification.items() if k!='call_sha256'},indent=2))


if __name__=='__main__':
    verify(Path(sys.argv[1]).resolve())
