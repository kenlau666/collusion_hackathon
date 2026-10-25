"""Network-denied reservation regression and real local-worker retry controls.

Saved request/reply/callback data are read only. Synthetic ledgers and local
children below are software evidence, never provider usage or model outcomes.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

NETWORK = []


def deny(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        NETWORK.append(event)
        raise RuntimeError('network denied in reservation-profile audit')


sys.addaudithook(deny)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'colosseum'))
ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False
    from budget_client import BudgetError, BudgetLedger, TransportReply, _validate_reply, MODEL_ID
    from capacity_guard_client import FinancialByteClient, POLICY, SUCCESSOR_POLICY
    from modal_hospital_client import BASE_URL, MODEL, validate_reply
    from timeout_retry_client import POLICY as RETRY_POLICY, DIRECTIVE as RETRY_DIRECTIVE, encoded
    from timeout_turn_policy import ContinueTurnLedger, POLICY as TURN_POLICY, DIRECTIVE as TURN_DIRECTIVE
finally:
    socket.has_ipv6 = ipv6


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authorization(amount):
    auth = {'approved': True, 'scope': 'full', 'max_calls': 198, 'max_usd': '10',
        'plan_sha256': 'a' * 64, 'approval_reference': 'OFFLINE reservation-profile control',
        'capacity_guard_policy': POLICY if amount == '.049' else SUCCESSOR_POLICY,
        'timeout_retry_policy': RETRY_POLICY, 'retry_approval_reference': RETRY_DIRECTIVE,
        'timeout_turn_policy': TURN_POLICY, 'timeout_turn_approval': TURN_DIRECTIVE}
    if amount != '.049':
        auth['reservation_usd'] = amount
    return auth


def pair(root, name, amount='.16', *, max_calls=198, max_usd='10', cumulative=None):
    directory = root / name
    directory.mkdir()
    ledger = ContinueTurnLedger(directory / 'accounting', scope='full', max_calls=max_calls,
        max_usd=max_usd, plan_sha256='a' * 64, authorization=authorization(amount),
        reservation_usd=amount, cumulative_guard=cumulative)
    client = FinancialByteClient(ledger=ledger, base_url=BASE_URL, model=MODEL,
        headers={'Modal-Key': 'OFFLINE_TEST_ID', 'Modal-Secret': 'OFFLINE_TEST_SECRET'},
        diagnostics=directory / 'diagnostics', request_timeout=.3,
        worker_sha256=sha(HERE / 'endpoint_probe_worker.py'))
    return ledger, client


def fails(action, reason=None):
    try:
        action()
    except BudgetError:
        return
    raise AssertionError(reason or 'expected fail-closed BudgetError')


def body(cost=None, prompt=100, output=20):
    usage = {'prompt_tokens': prompt, 'completion_tokens': output}
    if cost is not None:
        usage['cost'] = cost
    return {'id': 'offline-reservation-control', 'model': MODEL,
        'choices': [{'message': {'role': 'assistant', 'content': 'software control'}}], 'usage': usage}


def local_call(client, mode='success', reported=None):
    """Run actual retry/reap code, replacing only the worker program locally."""
    real_popen, launches = subprocess.Popen, []

    def fake(*args, **kwargs):
        launches.append(1)
        if mode == 'double_timeout' or mode == 'timeout_success' and len(launches) == 1:
            code = 'import sys,time;sys.stdin.read();time.sleep(3)'
        else:
            reply = {'kind': 'reply', 'status_code': 200, 'body': body(reported)}
            code = 'import sys;sys.stdin.read();print(' + repr(json.dumps(reply)) + ')'
        return real_popen([sys.executable, '-c', code], **kwargs)

    payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'software only'}]}
    with patch('traced_modal_client.subprocess.Popen', fake):
        if mode == 'double_timeout':
            fails(lambda: client._native_post(BASE_URL + '/chat/completions',
                headers={}, data=json.dumps(payload), timeout=.3))
        else:
            client._native_post(BASE_URL + '/chat/completions',
                headers={}, data=json.dumps(payload), timeout=.3)
    return len(launches)


def audit(out):
    out.mkdir(parents=True, exist_ok=False)
    checks, evidence = [], []

    def passed(name):
        checks.append(name)

    old = BudgetLedger(out / 'default-ledger')
    assert old.reservation_usd == Decimal('.049') and old.state['reservation_usd'] == '0.049'
    call = old.reserve({}, 2)
    assert Decimal(old.state['held_usd']) == Decimal('.049')
    old.finish(call, cost=Decimal('.001'))
    assert Decimal(old.state['held_usd']) == 0
    passed('default_049_reserve_and_release_unchanged')

    fails(lambda: BudgetLedger(out / 'missing-auth', reservation_usd='.16'))
    fails(lambda: BudgetLedger(out / 'unsupported', reservation_usd='.17'))
    assert not (out / 'missing-auth').exists() and not (out / 'unsupported').exists()
    bad = authorization('.16')
    bad['reservation_usd'] = '.049'
    fails(lambda: BudgetLedger(out / 'mismatch-auth', reservation_usd='.16',
        scope='full', max_calls=198, max_usd='10', plan_sha256='a' * 64, authorization=bad))
    passed('new_profile_missing_mismatched_and_unsupported_authorization_rejected')

    ledger, client = pair(out, 'large-profile')
    assert ledger.reservation_usd == Decimal('.16')
    ledger.authorization['capacity_guard_policy'] = deepcopy(POLICY)
    fails(lambda: FinancialByteClient(ledger=ledger))
    ledger.authorization['capacity_guard_policy'] = deepcopy(SUCCESSOR_POLICY)
    passed('client_policy_bound_to_same_ledger_reservation')

    old_ledger, old_client = pair(out, 'old-profile', '.049')
    count = 0
    base = HERE / '20261025'
    for directory in sorted(base.glob('full_workflow_live_deadline_*_001')):
        path = directory / 'accounting/ledger.json'
        data = json.loads(path.read_text())
        for record in data['records']:
            wire = record['wire_payload_json'].encode()
            assert old_client._payload_bound(record['payload'], wire) == record['conservative_prompt_bound']
            assert client._payload_bound(record['payload'], wire) == record['conservative_prompt_bound']
            count += 1
    assert count == 742
    passed('all_742_prior_attempt_bodies_bounds_and_defaults_unchanged')

    # Reconstruct missing-request size from saved normalized input + final reply
    # + native callback results. Original rejected wire order was not saved.
    for directory in sorted(base.glob('full_workflow_live_deadline_deadline_exploit_*_001')):
        result = json.loads((directory / 'results.json').read_text())['cases'][0]
        archive = directory / result['archive']
        case = json.loads(gzip.decompress(archive.read_bytes()))
        path = directory / 'accounting/ledger.json'
        last = json.loads(path.read_text())['records'][-1]
        payload = json.loads(last['wire_payload_json'])
        message = last['response']['choices'][0]['message']
        payload['messages'].append(message)
        calls = message.get('tool_calls') or []
        callbacks = case['callbacks'][-len(calls):] if calls else []
        for tool, callback in zip(calls, callbacks):
            assert tool['function']['name'] == callback['tool']
            assert json.loads(tool['function']['arguments']) == callback['arguments']
            payload['messages'].append({'role': 'tool', 'tool_call_id': tool['id'],
                'name': callback['tool'], 'content': json.dumps(callback['result'])})
        wire = encoded(payload)
        padded = client._payload_bound(payload, wire)
        assert padded > POLICY['max_padded_bytes'] and padded <= SUCCESSOR_POLICY['max_padded_bytes']
        evidence.append({'case': case['spec']['id'], 'archive_sha256': sha(archive),
            'ledger_sha256': sha(path), 'reconstructed_wire_bytes': len(wire), 'padded_bytes': padded,
            'old_guard_rejects': True, 'new_guard_accepts': True,
            'limit': 'reconstructed size; original undispatched wire key order/hash unrecorded'})
    assert len(evidence) == 5
    passed('all_five_censored_size_reconstructions_fit_without_content_changes')

    template = {'model': MODEL, 'messages': [{'role': 'user', 'content': ''}], 'max_tokens': 1024}
    overhead = len(encoded(template)) + 1024
    template['messages'][0]['content'] = 'x' * (SUCCESSOR_POLICY['max_padded_bytes'] - overhead)
    assert client._payload_bound(template, encoded(template)) == 529237
    template['messages'][0]['content'] += 'x'
    fails(lambda: client._payload_bound(template, encoded(template)))
    assert ledger.state['calls'] == 0 and ledger.state['halt_reason'] == 'payload_financial_bound'
    passed('exact_529237_boundary_and_plus_one_predispatch_rejection')

    assert validate_reply(TransportReply(200, body('.10')))[0] == 'overreservation_reported_cost'
    assert validate_reply(TransportReply(200, body('.10')), reservation_usd=Decimal('.16'))[0] is None
    assert validate_reply(TransportReply(200, body('.160001')), reservation_usd=Decimal('.16'))[0] == 'overreservation_reported_cost'
    assert validate_reply(TransportReply(200, body(prompt=131073)), reservation_usd=Decimal('.16'))[0] == 'reported_token_limit'
    assert validate_reply(TransportReply(200, body(output=1025)), reservation_usd=Decimal('.16'))[0] == 'reported_token_limit'
    generic = body('.10'); generic['model'] = MODEL_ID
    assert _validate_reply(200, generic)[0] == 'overreservation_cost'
    assert _validate_reply(200, generic, reservation_usd=Decimal('.16'))[0] is None
    passed('reported_cost_uses_profile_but_input_output_limits_unchanged')

    success, success_client = pair(out, 'reported-settlement')
    assert local_call(success_client, reported='.10') == 1
    assert success.state['status'] == 'ready' and Decimal(success.state['held_usd']) == 0
    assert success.state['records'][0]['reservation_usd'] == '0.16'
    assert Decimal(success.state['reported_cost_sum_usd']) == Decimal('.10')
    passed('actual_client_uses_160_reported_cost_and_releases_full_hold')

    for name, kwargs, expected in (
        ('run-limit', {'max_usd': '.15'}, 'dollar_limit'),
        ('cumulative-limit', {'cumulative': lambda: {'guard_usd': '49.85'}}, 'cumulative_dollar_limit')):
        bounded, bounded_client = pair(out, name, **kwargs)
        fails(lambda: local_call(bounded_client))
        assert bounded.state['calls'] == 0 and bounded.state['halt_reason'] == expected
    reported, _ = pair(out, 'reported-run-limit')
    reported.state.update(spent_usd='.01', reported_cost_sum_usd='9.85')
    reported.attempt_context = {'logical_request_id': 1, 'attempt_index': 0}
    fails(lambda: reported.reserve({}, 2))
    assert reported.state['halt_reason'] == 'dollar_limit' and reported.state['calls'] == 0
    passed('run_and_cumulative_caps_include_full_160_and_reported_costs')

    limited, limited_client = pair(out, 'call-limit', max_calls=1)
    assert local_call(limited_client) == 1
    fails(lambda: local_call(limited_client))
    assert limited.state['calls'] == 1 and limited.state['halt_reason'] == 'call_limit'
    passed('outward_call_cap_unchanged')

    retry, retry_client = pair(out, 'timeout-success')
    assert local_call(retry_client, 'timeout_success') == 2
    first, second = retry.state['records']
    assert first['status'] == 'failed' and second['status'] == 'settled'
    assert first['wire_payload_json'] == second['wire_payload_json']
    assert first['reservation_usd'] == second['reservation_usd'] == '0.16'
    assert Decimal(retry.state['held_usd']) == Decimal('.16')
    assert first['retried_by_call_id'] == 2 and second['retry_of_call_id'] == 1
    diagnostic = json.loads((retry_client.diagnostics / 'call-0001.json').read_text())
    assert diagnostic['child_reaped'] and diagnostic['category'] == 'whole_request_deadline'
    passed('actual_killed_reaped_timeout_exact_retry_keeps_first_160_hold')

    doubled, doubled_client = pair(out, 'double-timeout')
    assert local_call(doubled_client, 'double_timeout') == 2
    assert Decimal(doubled.state['held_usd']) == Decimal('.32') and doubled.state['calls'] == 2
    assert all(r['status'] == 'failed' for r in doubled.state['records'])
    assert doubled.abandon_timeout_turn(diagnostics=doubled_client.diagnostics, turn={'turn_index': 1},
        physical_unchanged=True, retained_prior_callbacks=0)
    assert Decimal(doubled.state['held_usd']) == Decimal('.32')
    assert local_call(doubled_client) == 1
    assert Decimal(doubled.state['held_usd']) == Decimal('.32') and doubled.state['calls'] == 3
    passed('two_timeouts_keep_320_after_abandonment_and_next_logical_success')

    capped, capped_client = pair(out, 'retry-dollar-limit', max_usd='.31')
    fails(lambda: local_call(capped_client, 'timeout_success'))
    assert capped.state['calls'] == 1 and Decimal(capped.state['held_usd']) == Decimal('.16')
    assert capped.state['halt_reason'] == 'dollar_limit'
    passed('retry_rechecks_remaining_full_reservation_before_second_dispatch')

    assert not NETWORK
    result = {'passed': True, 'checks_passed': len(checks), 'checks': checks,
        'Results': {'legacy_reservation_usd': '.049', 'successor_reservation_usd': '.16',
            'successor_max_padded_bytes': 529237, 'prior_attempt_bodies': count,
            'blocked_size_reconstructions': evidence, 'independent_n_per_control': 1,
            'sample_sd': None, 'sample_variance': None, 'behavioral_positive_control': 'unrun'},
        'mode': 'scripted_software', 'network_attempts': NETWORK, 'provider_calls': 0,
        'new_paid_spend_usd': '0', 'synthetic_reservations_are_not_paid_usage': True,
        'source_sha256': {n: sha(HERE / n) for n in ('audit_reservation_profiles.py',
            'budget_client.py', 'timeout_retry_client.py', 'modal_hospital_client.py', 'capacity_guard_client.py')}}
    save(out / 'results.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.out)
    print(json.dumps({'passed': result['passed'], 'checks_passed': result['checks_passed'],
        'provider_calls': 0, 'network_attempts': NETWORK}))
