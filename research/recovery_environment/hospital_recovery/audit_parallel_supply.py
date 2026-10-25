"""Network-denied controls for the separate parallel supply supervisor.

These are deterministic execution counterexamples, not model experiments. Real
short-lived OS children exercise the unchanged timeout/reaping/retry machinery;
their replies are fabricated locally and no endpoint credentials are accessed.
"""
import argparse
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

NETWORK = []


def deny(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        NETWORK.append(event)
        raise RuntimeError('network denied in parallel supply controls')


sys.addaudithook(deny)
_ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False
    import full_workflow as f
    import run_parallel_supply as parallel
    from budget_client import BudgetError
    from capacity_guard_client import POLICY as CAPACITY_POLICY
    from modal_hospital_client import BASE_URL, MODEL
    from timeout_retry_client import POLICY, DIRECTIVE
finally:
    socket.has_ipv6 = _ipv6

HERE = Path(__file__).resolve().parent


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecordingGate:
    """Isolate factory hooks while preserving a durable stop artifact."""
    def __init__(self, directory, mode):
        self.directory, self.mode = directory, mode
        self.directory.mkdir(parents=True)
        self.mutex = threading.RLock()
        self.ledger = None
        self.first_entries = []
        self.admissions = 0

    @contextmanager
    def admission(self):
        with self.mutex:
            self.admissions += 1
            yield

    def stop(self, reason):
        path = self.directory / 'stop.json'
        if not path.exists():
            save(path, {'reason': str(reason)})

    def check(self):
        if (self.mode == 'stop_before_retry' and self.ledger is not None and
                self.ledger.attempt_context.get('attempt_index') == 1):
            self.stop('synthetic_peer_terminal_halt')
        if (self.directory / 'stop.json').exists():
            raise BudgetError('durable synthetic wave stop')

    def first_reservation(self, ledger):
        self.ledger = ledger
        self.first_entries.append(ledger.attempt_context.copy())
        if self.mode == 'stop_before_initial':
            self.stop('synthetic_peer_terminal_halt')


async def inherited_client_controls(out, auth, plan_hash):
    modes = ('success_no_timeout', 'timeout_then_success', 'two_timeouts',
             'http_failure', 'stop_before_initial', 'stop_before_retry',
             'call_limit', 'dollar_limit', 'already_reserved_success', 'payload_guard')
    reports = []
    real_popen = subprocess.Popen
    for mode in modes:
        directory = out / mode
        directory.mkdir()
        gate = RecordingGate(directory / 'wave', mode)
        ledger_type, client_type = parallel.coordinated_classes(gate)
        ledger = ledger_type(directory / 'accounting', scope='full',
            max_calls=1 if mode == 'call_limit' else 198,
            max_usd='.049' if mode == 'dollar_limit' else '10',
            authorization=auth, plan_sha256=plan_hash,
            cumulative_guard=lambda: {'guard_usd': '0'})
        client = client_type(ledger=ledger, base_url=BASE_URL, model=MODEL,
            headers={'Modal-Key': 'OFFLINE_TEST_ID', 'Modal-Secret': 'OFFLINE_TEST_SECRET'},
            diagnostics=directory / 'diagnostics', request_timeout=.4,
            worker_sha256=digest(HERE / 'endpoint_probe_worker.py'))
        branch = f.root(0)
        actor = branch.precedence[0] + '_Surgery'
        source = branch.env.agents_map[actor]['hospital']
        destination = next(h for h in branch.env.hospital_names if h != source)
        args = f.move_args(destination)
        before = deepcopy(branch.env.inventory)
        launches = []

        def fake(*launch_args, **kwargs):
            launches.append(1)
            pause = (mode in ('two_timeouts', 'stop_before_retry', 'call_limit', 'dollar_limit')
                     or mode == 'timeout_then_success' and len(launches) == 1)
            if pause:
                code = ("import sys,time,os,json;from pathlib import Path;sys.stdin.read();"
                    "Path(os.environ['MODAL_PROGRESS_PATH']).write_text(json.dumps("
                    "{'stage':'request_sent_waiting_headers','events':[],'body_bytes':0}));"
                    "time.sleep(4)")
            else:
                message = {'role': 'assistant', 'content': 'offline native transfer control',
                    'tool_calls': [{'id': 'control-call', 'type': 'function', 'function': {
                        'name': 'transfer_resources', 'arguments': json.dumps(args)}}]}
                response = {'kind': 'reply', 'status_code': 429 if mode == 'http_failure' else 200,
                    'body': {'id': 'offline-reply', 'model': MODEL,
                        'choices': [{'message': message, 'finish_reason': 'tool_calls'}],
                        'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}}
                code = 'import sys;sys.stdin.read();print(' + repr(json.dumps(response)) + ')'
                if mode == 'already_reserved_success':
                    gate.stop('synthetic_peer_halt_after_local_reservation')
            return real_popen([sys.executable, '-c', code], **kwargs)

        if mode == 'payload_guard':
            original_bound = client._payload_bound

            def over_bound(payload, wire):
                changed = deepcopy(payload)
                changed['messages'] = [{'role': 'user', 'content': 'x' * 170000}]
                return original_bound(changed, b'x' * 170000)

            client._payload_bound = over_bound
        with patch('traced_modal_client.subprocess.Popen', fake):
            try:
                await f.native_turn(branch,
                    {'actor': actor, 'phase': 'planning', 'iteration': 1, 'turn_index': 0},
                    client, model=MODEL)
            except BudgetError:
                pass  # The native continuation may propagate or record this failure.
        callbacks = [x for x in branch.callback_attempts if x['tool'] == 'transfer_resources']
        positive = mode in ('success_no_timeout', 'timeout_then_success', 'already_reserved_success')
        expected_calls = (2 if mode in ('timeout_then_success', 'two_timeouts') else
                          0 if mode in ('stop_before_initial', 'payload_guard') else 1)
        expected_held = (2 if mode == 'two_timeouts' else 0 if mode in
            ('success_no_timeout', 'already_reserved_success', 'stop_before_initial', 'payload_guard') else 1)
        assert ledger.state['calls'] == len(launches) == expected_calls, mode
        assert Decimal(ledger.state['held_usd']) == Decimal('.049') * expected_held, mode
        assert client.logical_requests == 1, mode
        if positive:
            assert len(callbacks) == 1 and branch.env.transfer_rewards == 15, mode
            assert branch.env.inventory[source]['IV_Kits'] == before[source]['IV_Kits'] - 1, mode
            assert branch.env.inventory[destination]['IV_Kits'] == before[destination]['IV_Kits'] + 1, mode
        else:
            assert not callbacks and branch.env.inventory == before, mode
        stopped = (directory / 'wave/stop.json').exists()
        assert stopped == (mode not in ('success_no_timeout', 'timeout_then_success')), mode
        if mode == 'timeout_then_success':
            first, retry = ledger.state['records']
            assert first['status'] == 'failed' and retry['status'] == 'settled'
            assert first['wire_payload_json'] == retry['wire_payload_json']
            assert first['wire_payload_sha256'] == retry['wire_payload_sha256']
            assert retry['retry_of_call_id'] == first['call_id']
            assert ledger.state['status'] == 'ready'
        if mode in ('timeout_then_success', 'two_timeouts', 'stop_before_retry', 'call_limit', 'dollar_limit'):
            diagnostic = json.loads((directory / 'diagnostics/call-0001.json').read_text())
            assert diagnostic['category'] == 'whole_request_deadline' and diagnostic['child_reaped']
        if mode == 'stop_before_retry':
            assert len(ledger.state['retry_events']) == 1
            assert ledger.state['retry_events'][0]['retry_call_id'] is None
        reports.append({'mode': mode, 'passed': True, 'outward_attempts': ledger.state['calls'],
            'logical_generations': client.logical_requests, 'native_transfers': len(callbacks),
            'held_simulated_usd': ledger.state['held_usd'], 'durable_stop': stopped,
            'recording_gate_only': True})
        save(directory / 'control_result.json', reports[-1])
    return reports


def wave_gate_controls(out, auth, plan_hash):
    reports = []
    wave = out / 'actual_gate_stop'
    wave.mkdir()
    save(wave / 'runtime.json', {'test_only': True})
    save(wave / 'release.json', {})
    gate = parallel.WaveGate(wave, 3)
    with gate.admission():
        with gate.admission():
            gate.check()
    gate.stop('first durable reason')
    original = (wave / 'stop.json').read_bytes()
    gate.stop('later reason must not overwrite')
    assert (wave / 'stop.json').read_bytes() == original
    ledger_type, _ = parallel.coordinated_classes(gate)
    ledger = ledger_type(wave / 'accounting', scope='full', max_calls=198, max_usd='10',
        authorization=auth, plan_sha256=plan_hash, cumulative_guard=lambda: {'guard_usd': '0'})
    ledger.attempt_context = {'logical_request_id': 1, 'attempt_index': 0}
    try:
        ledger.reserve({'test': 'must never dispatch'}, 31)
    except BudgetError:
        pass
    else:
        raise AssertionError('real gate admitted after durable stop')
    assert ledger.state['calls'] == 0 and ledger.state['held_usd'] == '0'
    assert ledger.state['status'] == 'halted'
    reports.append({'mode': 'real_wave_reentrant_stop_and_reservation', 'passed': True})

    for mode in ('dead_coordinator', 'stale_heartbeat'):
        wave = out / mode
        wave.mkdir()
        save(wave / 'runtime.json', {'coordinator_pid': -1 if mode == 'dead_coordinator' else os.getppid()})
        save(wave / 'heartbeat.json', {'unix': time.time() - (11 if mode == 'stale_heartbeat' else 0)})
        gate = parallel.WaveGate(wave, 3)
        try:
            gate.check()
        except BudgetError:
            pass
        else:
            raise AssertionError(mode + ' admitted')
        assert (wave / 'stop.json').exists()
        reports.append({'mode': mode, 'passed': True})

    wave = out / 'first_reservation_barrier'
    wave.mkdir()
    save(wave / 'runtime.json', {'test_only': True})
    gate = parallel.WaveGate(wave, 4)
    dummy = SimpleNamespace(state={'calls': 0, 'status': 'ready'},
        path=wave / 'dummy-ledger.json', plan_sha256=plan_hash)
    errors = []

    def blocked():
        try:
            gate.first_reservation(dummy)
        except BaseException as error:
            errors.append(type(error).__name__)

    thread = threading.Thread(target=blocked, daemon=True)
    thread.start()
    until = time.monotonic() + 5
    while not (wave / 'ready-4.json').exists() and time.monotonic() < until:
        time.sleep(.01)
    assert (wave / 'ready-4.json').exists() and thread.is_alive()
    marker = json.loads((wave / 'ready-4.json').read_text())
    assert marker['calls'] == 0 and marker['status'] == 'ready'
    save(wave / 'release.json', {'test_release': True})
    thread.join(3)
    assert not thread.is_alive() and not errors and gate.once
    reports.append({'mode': 'real_wave_startup_barrier', 'passed': True})

    wave = out / 'multiprocess_mutex'
    wave.mkdir()
    save(wave / 'runtime.json', {'test_only': True})
    (wave / 'counter.txt').write_text('0')
    code = '''import sys,socket,time
from pathlib import Path
def deny(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo'}:
        raise RuntimeError('network denied in mutex child')
sys.addaudithook(deny)
socket.has_ipv6=False
sys.path.insert(0,sys.argv[1])
from run_parallel_supply import WaveGate
wave=Path(sys.argv[2]); gate=WaveGate(wave,int(sys.argv[3]))
for _ in range(12):
    with gate.admission():
        with gate.admission():
            value=int((wave/'counter.txt').read_text())
            time.sleep(.005)
            (wave/'counter.txt').write_text(str(value+1))
'''
    children = [subprocess.Popen([sys.executable, '-c', code, str(HERE), str(wave), str(seed)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for seed in (3, 4, 5)]
    for child in children:
        _, stderr = child.communicate(timeout=30)
        assert child.returncode == 0, 'mutex child error: ' + stderr[-500:]
    assert int((wave / 'counter.txt').read_text()) == 36
    reports.append({'mode': 'real_three_process_admission_mutex', 'passed': True,
        'processes': 3, 'serialized_updates': 36})
    return reports


async def _audit(out):
    out.mkdir(parents=True, exist_ok=False)
    sources = ('audit_parallel_supply.py', 'run_parallel_supply.py', 'run_supply_preflight.py',
               'timeout_retry_client.py', 'capacity_guard_client.py', 'traced_modal_client.py',
               'modal_hospital_client.py', 'budget_client.py', 'endpoint_probe_worker.py')
    plan = {'sources': {name: digest(HERE / name) for name in sources},
        'positive_control': 'OS-child timeout then byte-identical retry executes exactly one native transfer without stopping peers',
        'limits': 'synthetic execution controls only; no endpoint/network/credentials/inference',
        'n_per_counterexample': 1, 'sample_sd': None, 'sample_variance': None}
    save(out / 'plan.json', plan)
    plan_hash = digest(out / 'plan.json')
    auth = {'approved': True, 'scope': 'full', 'max_calls': 198, 'max_usd': '10',
        'plan_sha256': plan_hash, 'approval_reference': DIRECTIVE,
        'timeout_retry_policy': POLICY, 'retry_approval_reference': DIRECTIVE,
        'capacity_guard_policy': CAPACITY_POLICY}
    assert parallel.envelope(Decimal('20'), slots=3) == Decimal('50')
    assert parallel.envelope(Decimal('6.5'), slots=3) == Decimal('36.5')
    try:
        parallel.envelope(Decimal('20.00000001'), slots=3)
    except BudgetError:
        pass
    else:
        raise AssertionError('over-ceiling wave accepted')
    reports = [{'mode': 'static_envelope_boundaries', 'passed': True}]
    reports.extend(await inherited_client_controls(out, auth, plan_hash))
    save(out / 'completed_inherited_controls.json', reports)
    reports.extend(wave_gate_controls(out, auth, plan_hash))
    assert not NETWORK
    result = {'passed': True, 'plan_sha256': plan_hash, 'cases': reports,
        'network_attempts': NETWORK, 'inference_calls': 0, 'real_spend_usd': '0',
        'positive_control_passed': True, 'llm_behavior_established': False,
        'independent_n_per_counterexample': 1, 'sample_sd': None, 'sample_variance': None,
        'Results': 'Inherited exact-timeout retry and terminal admission counterexamples pass; these are software controls, not model samples.'}
    save(out / 'results.json', result)
    return result


def audit(out):
    return asyncio.run(_audit(Path(out)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    print(json.dumps(audit(parser.parse_args().out), sort_keys=True))
