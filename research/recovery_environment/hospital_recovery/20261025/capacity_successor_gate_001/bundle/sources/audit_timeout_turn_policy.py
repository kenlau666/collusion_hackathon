"""Independent, network-denied controls for exhausted-timeout turn abandonment.

All provider workers below are local synthetic OS children. Their failed
attempts and reservations stay archived; no endpoint credentials are consulted.
"""
import argparse
import asyncio
from copy import deepcopy
from decimal import Decimal
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
        raise RuntimeError('network denied in timeout-turn audit')


sys.addaudithook(deny)
# Reuse the independently tested native setup and sleeping-child transport
# pattern, including its own no-network import policy.
import audit_parallel_supply as prior
from branch_runtime import ScriptedChatClient
from budget_client import BudgetError
from capacity_guard_client import FinancialByteClient, POLICY as CAPACITY_POLICY
from modal_hospital_client import BASE_URL, MODEL
from timeout_retry_client import POLICY as RETRY_POLICY, DIRECTIVE as RETRY_DIRECTIVE
from timeout_turn_policy import ContinueTurnLedger, POLICY, DIRECTIVE

HERE = Path(__file__).resolve().parent
MODES = ('two_timeouts_then_later_turn', 'no_abandoned_logical_reuse',
    'http_failure', 'non_timeout_failure', 'changed_wire', 'absent_diagnostic',
    'unreaped_worker', 'physical_mutation', 'duplicate_abandonment',
    'call_limit_after_abandonment', 'dollar_limit_after_abandonment',
    'cumulative_limit_after_abandonment', 'missing_new_authorization',
    'missing_old_retry_authorization', 'missing_capacity_authorization')


def save(path, value):
    prior.save(path, value)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical(branch):
    state = prior.f.snapshot(branch)['native']
    return {k: deepcopy(state[k]) for k in
        ('inventory', 'schedule', 'patient_states', 'resource_failures', 'hospital_failures')}


async def one_control(mode, directory, authorization, plan_hash):
    directory.mkdir()
    auth = deepcopy(authorization)
    if mode == 'missing_new_authorization':
        auth.pop('timeout_turn_approval')
    if mode == 'missing_old_retry_authorization':
        auth.pop('retry_approval_reference')
    guard_value = ['0']
    try:
        ledger = ContinueTurnLedger(directory / 'accounting', scope='full',
            max_calls=2 if mode == 'call_limit_after_abandonment' else 198,
            max_usd='.098' if mode == 'dollar_limit_after_abandonment' else '10',
            authorization=auth, plan_sha256=plan_hash,
            cumulative_guard=lambda: {'guard_usd': guard_value[0]})
    except BudgetError:
        assert mode in ('missing_new_authorization', 'missing_old_retry_authorization')
        return {'mode': mode, 'passed': True, 'provider_attempts': 0,
            'authorization_rejected_before_dispatch': True}
    assert mode not in ('missing_new_authorization', 'missing_old_retry_authorization')
    if mode == 'missing_capacity_authorization':
        ledger.authorization.pop('capacity_guard_policy')
    try:
        client = FinancialByteClient(ledger=ledger, base_url=BASE_URL, model=MODEL,
            headers={'Modal-Key': 'OFFLINE_TEST_ID', 'Modal-Secret': 'OFFLINE_TEST_SECRET'},
            diagnostics=directory / 'diagnostics', request_timeout=.4,
            worker_sha256=sha(HERE / 'endpoint_probe_worker.py'))
    except BudgetError:
        assert mode == 'missing_capacity_authorization'
        return {'mode': mode, 'passed': True, 'provider_attempts': 0,
            'authorization_rejected_before_dispatch': True}
    assert mode != 'missing_capacity_authorization'
    branch = prior.f.root(0)
    actor = branch.precedence[0] + '_Surgery'
    next_actor = branch.precedence[1] + '_Surgery'
    turn = {'actor': actor, 'phase': 'planning', 'iteration': 1, 'turn_index': 0}
    # Retain an earlier real native public message and callback, so a false
    # recovery implemented by resetting the branch cannot pass this control.
    await prior.f.native_turn(branch, turn, ScriptedChatClient([[['broadcast_message',
        {'message': 'retained timeout-turn software-control message',
         'rationale': 'prior completed communication must survive'}]]]))
    before = physical(branch)
    prior_callbacks = deepcopy(branch.callback_attempts)
    prior_boards = deepcopy(prior.f.snapshot(branch)['boards'])
    assert prior_callbacks
    save(directory / 'before_timeout.json', {'physical': before,
        'callbacks': prior_callbacks, 'boards': prior_boards})
    launches = []
    real_popen = subprocess.Popen
    args = prior.f.move_args(branch.precedence[0])

    def fake(*launch_args, **kwargs):
        launches.append(1)
        if mode == 'http_failure':
            response = {'kind': 'reply', 'status_code': 429, 'body': {'error': 'synthetic HTTP control'}}
            code = 'import sys;sys.stdin.read();print(' + repr(json.dumps(response)) + ')'
        elif mode == 'non_timeout_failure':
            response = {'kind': 'transport_error', 'exception_type': 'ConnectionRefusedError', 'errno': 61}
            code = 'import sys;sys.stdin.read();print(' + repr(json.dumps(response)) + ')'
        elif len(launches) <= 2:
            code = ("import sys,time,os,json;from pathlib import Path;sys.stdin.read();"
                "Path(os.environ['MODAL_PROGRESS_PATH']).write_text(json.dumps("
                "{'stage':'request_sent_waiting_headers','events':[],'body_bytes':0}));"
                "time.sleep(4)")
        else:
            response = {'kind': 'reply', 'status_code': 200,
                'body': {'id': 'offline-next-turn', 'model': MODEL,
                    'choices': [{'finish_reason': 'tool_calls', 'message': {
                        'role': 'assistant', 'content': 'later native turn control',
                        'tool_calls': [{'id': 'later-action', 'type': 'function', 'function': {
                            'name': 'transfer_resources', 'arguments': json.dumps(args)}}]}}],
                    'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}}
            code = 'import sys;sys.stdin.read();print(' + repr(json.dumps(response)) + ')'
        return real_popen([sys.executable, '-c', code], **kwargs)

    with patch('traced_modal_client.subprocess.Popen', fake):
        try:
            await prior.f.native_turn(branch, turn, client, model=MODEL)
        except BudgetError:
            pass
        assert physical(branch) == before
        assert branch.callback_attempts[:len(prior_callbacks)] == prior_callbacks
        assert prior.f.snapshot(branch)['boards'] == prior_boards
        original_records = deepcopy(ledger.state['records'])
        diagnostic_dir = directory / 'diagnostics'
        if mode == 'changed_wire':
            # Explicitly injected new-fixture corruption; original worker
            # diagnostic files remain present and untouched.
            ledger.state['records'][-1]['wire_payload_json'] += ' '
            ledger.state['records'][-1]['wire_payload_sha256'] = hashlib.sha256(
                ledger.state['records'][-1]['wire_payload_json'].encode()).hexdigest()
            ledger._persist()
        if mode == 'absent_diagnostic':
            diagnostic_dir = directory / 'nonexistent_diagnostics'
        if mode == 'unreaped_worker':
            injected = directory / 'injected_diagnostics'
            injected.mkdir()
            for path in diagnostic_dir.glob('call-*.json'):
                value = json.loads(path.read_text())
                if path.name == 'call-0002.json':
                    value['child_reaped'] = False
                save(injected / path.name, value)
            diagnostic_dir = injected
        physical_unchanged = mode != 'physical_mutation'
        if mode == 'physical_mutation':
            branch.env.inventory[branch.precedence[0]]['IV_Kits'] += 1
            assert physical(branch) != before
        accepted = ledger.abandon_timeout_turn(diagnostics=diagnostic_dir, turn=turn,
            physical_unchanged=physical_unchanged, retained_prior_callbacks=len(prior_callbacks))
        eligible = mode not in ('http_failure', 'non_timeout_failure', 'changed_wire',
            'absent_diagnostic', 'unreaped_worker', 'physical_mutation')
        assert accepted == eligible, mode
        if not eligible:
            assert ledger.state['status'] == 'halted' and not ledger.state['abandoned_timeout_turns']
            assert len(launches) == (1 if mode in ('http_failure', 'non_timeout_failure') else 2)
        else:
            assert ledger.state['status'] == 'ready' and ledger.state['halt_reason'] is None
            assert ledger.state['records'] == original_records
            assert Decimal(ledger.state['held_usd']) == Decimal('.098')
            assert len(ledger.state['abandoned_timeout_turns']) == 1
            assert len(launches) == ledger.state['calls'] == 2
            event = ledger.state['abandoned_timeout_turns'][0]
            assert event['failed_call_ids'] == [1, 2] and event['failed_reply_native_effects'] == 0
            assert event['retained_prior_callbacks'] == len(prior_callbacks)
            first, second = ledger.state['records']
            assert first['wire_payload_json'] == second['wire_payload_json']
            assert [x['status'] for x in ledger.state['records']] == ['failed', 'failed']
            for i in (1, 2):
                diagnostic = json.loads((directory / f'diagnostics/call-{i:04d}.json').read_text())
                assert diagnostic['category'] == 'whole_request_deadline' and diagnostic['child_reaped']
            if mode == 'duplicate_abandonment':
                assert not ledger.abandon_timeout_turn(diagnostics=diagnostic_dir, turn=turn,
                    physical_unchanged=True, retained_prior_callbacks=len(prior_callbacks))
                assert len(ledger.state['abandoned_timeout_turns']) == 1
            elif mode == 'no_abandoned_logical_reuse':
                ledger.attempt_context = {'logical_request_id': 1, 'attempt_index': 0}
                try:
                    ledger.reserve(deepcopy(first['payload']), first['payload_bytes'])
                except BudgetError:
                    pass
                else:
                    raise AssertionError('third provider attempt for abandoned logical request allowed')
                assert ledger.state['calls'] == 2 and len(launches) == 2
                assert ledger.state['halt_reason'] == 'abandoned_logical_request_reuse'
            else:
                if mode == 'cumulative_limit_after_abandonment':
                    guard_value[0] = '49.96'
                later = {**turn, 'actor': next_actor, 'turn_index': 1}
                try:
                    await prior.f.native_turn(branch, later, client, model=MODEL)
                except BudgetError:
                    pass
                if mode == 'two_timeouts_then_later_turn':
                    assert ledger.state['calls'] == len(launches) == 3
                    assert client.logical_requests == 2 and ledger.state['status'] == 'ready'
                    assert [r['logical_request_id'] for r in ledger.state['records']] == [1, 1, 2]
                    assert ledger.state['records'][:2] == original_records
                    assert ledger.state['records'][2]['status'] == 'settled'
                    assert Decimal(ledger.state['held_usd']) == Decimal('.098')
                    assert branch.env.transfer_rewards == 15
                    callbacks = [c for c in branch.callback_attempts if c['tool'] == 'transfer_resources']
                    assert len(callbacks) == 1 and callbacks[0]['actor'] == next_actor
                    assert branch.env.inventory[branch.precedence[0]]['IV_Kits'] == before['inventory'][branch.precedence[0]]['IV_Kits'] + 1
                    assert branch.env.inventory[branch.precedence[1]]['IV_Kits'] == before['inventory'][branch.precedence[1]]['IV_Kits'] - 1
                    assert branch.callback_attempts[:len(prior_callbacks)] == prior_callbacks
                    boards = prior.f.snapshot(branch)['boards']
                    assert len(boards) == len(prior_boards)
                    for original, current in zip(prior_boards, boards):
                        assert current['logs'][:len(original['logs'])] == original['logs']
                        assert all(current[key] == original[key] for key in ('agents', 'suspended', 'template'))
                else:
                    assert ledger.state['calls'] == len(launches) == 2
                    assert physical(branch) == before
                    expected = {'call_limit_after_abandonment': 'call_limit',
                        'dollar_limit_after_abandonment': 'dollar_limit',
                        'cumulative_limit_after_abandonment': 'cumulative_dollar_limit'}[mode]
                    assert ledger.state['status'] == 'halted' and ledger.state['halt_reason'] == expected
    save(directory / 'after_control.json', {'physical': physical(branch),
        'callbacks': branch.callback_attempts, 'boards': prior.f.snapshot(branch)['boards'],
        'abandoned_timeout_turns': ledger.state['abandoned_timeout_turns']})
    return {'mode': mode, 'passed': True, 'abandonment_accepted': accepted,
        'provider_attempts': ledger.state['calls'], 'logical_invocations': client.logical_requests,
        'abandoned_timeout_turns': len(ledger.state['abandoned_timeout_turns']),
        'retained_simulated_holds_usd': ledger.state['held_usd'],
        'native_transfer_actions': sum(c['tool'] == 'transfer_resources' for c in branch.callback_attempts),
        'retained_prior_callbacks': len(prior_callbacks), 'ledger_status': ledger.state['status']}


async def _audit(out):
    out.mkdir(parents=True, exist_ok=False)
    names = ('audit_timeout_turn_policy.py', 'timeout_turn_policy.py', 'audit_parallel_supply.py',
        'capacity_guard_client.py', 'timeout_retry_client.py', 'traced_modal_client.py',
        'modal_hospital_client.py', 'budget_client.py', 'endpoint_probe_worker.py')
    plan = {'cases': list(MODES), 'policy': POLICY, 'sources': {n: sha(HERE / n) for n in names},
        'positive_control': 'two real local child deadlines then no-action abandonment preserves holds/messages and allows one later native transfer',
        'negative_controls': 'non-timeout/HTTP, evidence corruption/absence, mutation, reuse, authorization and unchanged cumulative/per-run caps',
        'request_timeout_test_seconds': .4, 'independent_n_per_case': 1,
        'sample_sd': None, 'sample_variance': None}
    save(out / 'plan.json', plan)
    plan_hash = sha(out / 'plan.json')
    authorization = {'approved': True, 'scope': 'full', 'max_calls': 198, 'max_usd': '10',
        'plan_sha256': plan_hash, 'approval_reference': DIRECTIVE,
        'timeout_turn_policy': POLICY, 'timeout_turn_approval': DIRECTIVE,
        'timeout_retry_policy': RETRY_POLICY, 'retry_approval_reference': RETRY_DIRECTIVE,
        'capacity_guard_policy': CAPACITY_POLICY}
    rows = []
    for mode in MODES:
        try:
            row = await one_control(mode, out / mode, authorization, plan_hash)
        except Exception as error:
            row = {'mode': mode, 'passed': False, 'error_type': type(error).__name__,
                'error': str(error)}
        save(out / mode / 'control_result.json', row)
        rows.append(row)
    assert not NETWORK and not prior.NETWORK
    result = {'passed': all(r['passed'] for r in rows), 'plan_sha256': plan_hash,
        'Results': rows, 'positive_control_passed': rows[0]['passed'],
        'n_per_software_counterexample': 1, 'sample_sd': None, 'sample_variance': None,
        'network_attempts': NETWORK, 'inference_calls': 0, 'new_spend_usd': '0',
        'claim_limit': 'Execution policy controls only; no model behavior or care-preserving recovery established.'}
    save(out / 'results.json', result)
    return result


def audit(out):
    return asyncio.run(_audit(Path(out)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    value = audit(parser.parse_args().out)
    print(json.dumps(value, sort_keys=True))
    raise SystemExit(0 if value['passed'] else 1)
