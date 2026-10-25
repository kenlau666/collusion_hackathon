"""Bounded three-process orchestration; the qualified clinical engine is unchanged.

One supervisor holds the original exclusion lock; children inherit it. A startup
barrier keeps every ledger ready until all frozen preflights have completed.
USD10 envelopes make the worst-case cumulative bound independent of read races.
"""
import argparse
import asyncio
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

# Mock children must inherit the original no-network import/validation policy.
_arguments = list(sys.argv)
if '--mock' in sys.argv:
    sys.argv[1:2] = ['validate']
import run_supply_preflight as supply
sys.argv[:] = _arguments
r = supply.r
HERE, BASE = supply.HERE, supply.BASE
ORDINARY = BASE / 'supply_ordinary_gate_001/bundle'
SEEDS = (3, 4, 5)
FILES = ('run_parallel_supply.py', 'audit_parallel_supply.py')
APPROVAL = 'Human request: can we have multiple agent to run the seed?'


def read(path):
    return json.loads(Path(path).read_text())


def envelope(baseline, slots=3):
    if type(slots) is not int or not 1 <= slots <= 3:
        raise r.BudgetError('one to three independent slots required')
    worst = Decimal(str(baseline)) + Decimal(10) * slots
    if worst > 50:
        raise r.BudgetError('full USD10 envelopes exceed cumulative USD50')
    return worst


class WaveGate:
    def __init__(self, wave, seed):
        self.wave, self.seed = Path(wave), seed
        self.once = False
        self._thread_lock = threading.RLock()
        self._depth = 0

    @contextmanager
    def admission(self):
        with self._thread_lock:
            if self._depth:
                self._depth += 1
                try:
                    yield
                finally:
                    self._depth -= 1
                return
            with (self.wave / 'admission.lock').open('a') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                self._depth = 1
                try:
                    yield
                finally:
                    self._depth = 0
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def stop(self, reason):
        with self.admission():
            if not (self.wave / 'stop.json').exists():
                r.save(self.wave / 'stop.json', {'seed': self.seed, 'reason': reason,
                    'observed_at_unix': time.time(),
                    'policy': 'deny new reservations; allow already reserved requests to finish/archive'})

    def check(self):
        if (self.wave / 'stop.json').exists():
            raise r.BudgetError('parallel wave terminal stop')
        runtime = read(self.wave / 'runtime.json')
        if runtime.get('test_only'):
            return
        parent = runtime['coordinator_pid']
        heartbeat = read(self.wave / 'heartbeat.json')
        if os.getppid() != parent or time.time() - heartbeat['unix'] > 10:
            self.stop('coordinator unavailable; inherited exclusion lock retained')
            raise r.BudgetError('coordinator unavailable')

    def first_reservation(self, ledger):
        if self.once:
            return
        assert ledger.state['calls'] == 0 and ledger.state['status'] == 'ready'
        r.save(self.wave / f'ready-{self.seed}.json', {'seed': self.seed,
            'ledger': str(ledger.path), 'status': 'ready', 'calls': 0,
            'plan_sha256': ledger.plan_sha256})
        until = time.monotonic() + 120
        while not (self.wave / 'release.json').exists():
            self.check()
            if time.monotonic() >= until:
                self.stop('startup barrier deadline')
                raise r.BudgetError('parallel startup barrier deadline')
            time.sleep(.1)
        self.check()
        self.once = True


def coordinated_classes(gate):
    class CoordinatedLedger(r.TimeoutRetryLedger):
        def reserve(self, payload, payload_bytes):
            try:
                gate.first_reservation(self)
                with gate.admission():
                    gate.check()
                    return super().reserve(payload, payload_bytes)
            except r.BudgetError:
                if self.state['status'] != 'halted':
                    self.halt('parallel_peer_terminal_stop')
                raise

    class CoordinatedClient(r.FinancialByteClient):
        def _native_post(self, *args, **kwargs):
            try:
                return super()._native_post(*args, **kwargs)
            except Exception:
                # This is outside the unchanged timeout retry loop. A first
                # timeout followed by success never publishes a cohort stop.
                gate.stop('terminal request after original retry policy')
                raise
    return CoordinatedLedger, CoordinatedClient


def prepare(out):
    supply.verify(ORDINARY)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'sources').mkdir()
    for name in FILES:
        shutil.copyfile(HERE / name, out / 'sources' / name)
    plan = {'schema': 1, 'seeds': list(SEEDS), 'ordinary_bundle': str(ORDINARY),
        'ordinary_plan_sha256': r.sha(ORDINARY / 'plan.json'),
        'initial_inputs_sha256': r.sha(ORDINARY / 'initial_inputs.json'),
        'sources': {name: r.sha(HERE / name) for name in FILES},
        'authorization': APPROVAL, 'max_parallel_processes': 3,
        'max_calls_per_run': 198, 'max_usd_per_run': '10', 'cumulative_ceiling_usd': '50',
        'admission': 'original global exclusion lock; 3 full USD10 envelopes; exact-source startup barrier',
        'stop': 'shared stop after terminal execution failure; pre-reserved requests finish and archive',
        'task_changes': 'none; no seed replacement, new prompt, cap, model, deadline or retry',
        'positive_control': 'three simultaneous scripted native ordinary cases: care8/8 and 54 turns each; exact independent serial match',
        'transport_limit': 'serial model controls are not a concurrency/throughput guarantee'}
    r.save(out / 'plan.json', plan)
    return plan


def verify(bundle):
    plan = read(bundle / 'plan.json')
    assert plan['seeds'] == list(SEEDS) and plan['authorization'] == APPROVAL
    assert plan['ordinary_plan_sha256'] == r.sha(ORDINARY / 'plan.json')
    assert plan['initial_inputs_sha256'] == r.sha(ORDINARY / 'initial_inputs.json')
    for name, expected in plan['sources'].items():
        assert r.sha(HERE / name) == expected == r.sha(bundle / 'sources' / name)
    supply.verify(ORDINARY)
    return plan


def case_path(seed):
    return BASE / f'full_workflow_live_ordinary_supply_s{seed}_001'


def worker(bundle, wave, seed, lock_fd, mock):
    plan = verify(bundle)
    assert seed in plan['seeds']
    runtime = read(wave / 'runtime.json')
    lock_stat = os.fstat(lock_fd)
    assert [lock_stat.st_dev, lock_stat.st_ino] == runtime['lock_identity']
    gate = WaveGate(wave, seed)
    output = wave / f'mock-s{seed}' if mock else case_path(seed)
    with (wave / f'seed-{seed}.lock').open('a') as slot:
        fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger_class, client_class = coordinated_classes(gate)
        try:
            gate.check()
            with patch.object(r, 'TimeoutRetryLedger', ledger_class), patch.object(r, 'FinancialByteClient', client_class):
                result = asyncio.run(supply.execute(ORDINARY, output, seed=seed, mock=mock))
            if not all(c['complete'] for c in result['cases']):
                gate.stop('incomplete case; retain all partial evidence')
            r.save(output / 'orchestration.json', {'wave': str(wave), 'seed': seed,
                'orchestration_plan_sha256': r.sha(bundle / 'plan.json'),
                'clinical_plan_sha256': result['plan_sha256'], 'sources': plan['sources'],
                'case_complete': all(c['complete'] for c in result['cases']),
                'provider_concurrency_limit': 3})
            r.save(wave / f'finished-{seed}.json', {'seed': seed, 'output': str(output),
                'complete': all(c['complete'] for c in result['cases']), 'passed': result['all_passed'],
                'results_sha256': r.sha(output / 'results.json')})
        except BaseException as exc:
            gate.stop('worker exception: ' + type(exc).__name__)
            r.save(wave / f'failed-{seed}.json', {'seed': seed, 'error_type': type(exc).__name__})
            raise


def supervise(bundle, out, mock=None):
    plan = verify(bundle)
    if not mock:
        validation = read(bundle.parent / 'validation/validation.json')
        assert validation['passed'] and validation['plan_sha256'] == r.sha(bundle / 'plan.json')
    lock_path = Path(tempfile.gettempdir()) / ('modal-Hospital-' + hashlib.sha256(str(HERE).encode()).hexdigest()[:16] + '.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prior = r.all_history() if not mock else {'guard_usd': '0', 'new': []}
        worst = envelope(prior['guard_usd'])
        if not mock:
            # Independent paid runs remain fixed, and every earlier execution
            # must be terminal/ready before the parallel wave starts.
            for row in prior['new']:
                preflight = read(Path(row['path']).parent.parent / 'preflight.json')
                if preflight.get('study_variant') == supply.VARIANT and row['status'] != 'ready':
                    raise r.BudgetError('active or halted prior supply run')
            for seed in SEEDS:
                if case_path(seed).exists():
                    raise r.BudgetError('fixed seed output already exists; no repeat')
        out.mkdir(parents=True, exist_ok=False)
        stat = os.fstat(lock.fileno())
        r.save(out / 'runtime.json', {'coordinator_pid': os.getpid(),
            'lock_identity': [stat.st_dev, stat.st_ino], 'seeds': list(SEEDS),
            'plan_sha256': r.sha(bundle / 'plan.json'), 'mock': mock,
            'baseline_guard_usd': prior['guard_usd'], 'prior': prior,
            'reserved_run_envelopes_usd': '30', 'worst_case_guard_usd': str(worst),
            'envelope_is_capacity_not_charge': True})
        gate = WaveGate(out, None)
        processes, logs = {}, []
        started = time.monotonic()
        try:
            r.save(out / 'heartbeat.json', {'unix': time.time()})
            for seed in SEEDS:
                log = (out / f'seed-{seed}.log').open('w')
                logs.append(log)
                command = [sys.executable, str(Path(__file__).resolve()), 'worker',
                    '--bundle', str(bundle), '--out', str(out), '--seed', str(seed),
                    '--lock-fd', str(lock.fileno())]
                if mock:
                    command += ['--mock', mock]
                processes[seed] = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                    pass_fds=(lock.fileno(),))
            previous = None
            while True:
                r.save(out / 'heartbeat.json', {'unix': time.time()})
                codes = {str(seed): process.poll() for seed, process in processes.items()}
                if any(code is not None and code != 0 for code in codes.values()):
                    gate.stop('worker exited unsuccessfully')
                if not (out / 'release.json').exists() and not (out / 'stop.json').exists():
                    if all((out / f'ready-{seed}.json').exists() for seed in SEEDS):
                        ready = [read(out / f'ready-{seed}.json') for seed in SEEDS]
                        assert all(row['calls'] == 0 and row['status'] == 'ready' for row in ready)
                        r.save(out / 'release.json', {'all_ready': ready, 'unix': time.time()})
                    elif time.monotonic() - started > 120:
                        gate.stop('not all frozen preflights reached startup barrier')
                if codes != previous:
                    r.save(out / 'status.json', {'exit_codes': codes, 'unix': time.time()})
                    previous = codes
                if all(code is not None for code in codes.values()):
                    break
                time.sleep(.2)
        except BaseException:
            gate.stop('coordinator interrupted')
            # Do not kill request workers or discard native history. Children
            # retain the exclusion FD and fail closed before any next reserve.
            raise
        finally:
            for log in logs:
                log.close()
        report = {'plan_sha256': r.sha(bundle / 'plan.json'), 'mock': mock,
            'exit_codes': codes, 'shared_stop': read(out / 'stop.json') if (out / 'stop.json').exists() else None,
            'finished': [read(out / f'finished-{seed}.json') for seed in SEEDS if (out / f'finished-{seed}.json').exists()],
            'new_paid_spend_usd': '0' if mock else 'see individual immutable ledgers; actual bills unverified'}
        r.save(out / 'results.json', report)
        return report


def validate(bundle, out):
    from audit_parallel_supply import audit
    out.mkdir(parents=True, exist_ok=False)
    unit = audit(out / 'coordination')
    parallel = supervise(bundle, out / 'parallel', mock='success')
    assert not parallel['shared_stop'] and all(row['complete'] and row['passed'] for row in parallel['finished'])
    rows = []
    for seed in SEEDS:
        directory = out / f'serial-s{seed}'
        serial = asyncio.run(supply.execute(ORDINARY, directory, seed=seed, mock='success'))
        paired = read(out / 'parallel' / f'mock-s{seed}' / 'results.json')
        a, b = serial['cases'][0], paired['cases'][0]
        first = json.loads(__import__('gzip').decompress((directory / a['archive']).read_bytes()))
        second = json.loads(__import__('gzip').decompress((out / 'parallel' / f'mock-s{seed}' / b['archive']).read_bytes()))
        assert a['metrics'] == b['metrics'] and first == second
        assert a['complete'] and b['complete'] and len(first['turns']) == 54
        assert a['metrics']['care'] == 8 and a['metrics']['failures'] == 0
        rows.append({'seed': seed, 'care': 8, 'turns': 54, 'exact_serial_parallel_archive_equal': True})
    assert not r.NETWORK
    result = {'passed': True, 'plan_sha256': r.sha(bundle / 'plan.json'),
        'software_positive_control': rows, 'coordination_controls': unit,
        'network_attempts': r.NETWORK, 'model_calls': 0, 'new_paid_spend_usd': '0',
        'claim_limit': 'scripted execution equivalence only; endpoint concurrency success not established'}
    r.save(out / 'validation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'validate', 'run', 'worker'])
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--lock-fd', type=int)
    parser.add_argument('--mock', choices=['success'])
    args = parser.parse_args()
    if args.command == 'prepare':
        value = prepare(args.out)
    elif args.command == 'validate':
        value = validate(args.bundle, args.out)
    elif args.command == 'run':
        if args.mock:
            raise r.BudgetError('mock option belongs to offline validation only')
        value = supervise(args.bundle, args.out)
    else:
        worker(args.bundle, args.out, args.seed, args.lock_fd, args.mock)
        return
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    main()
