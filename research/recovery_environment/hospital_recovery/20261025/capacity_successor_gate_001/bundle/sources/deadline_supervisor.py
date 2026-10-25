"""Isolated fixed-case deadline waves with inherited global budget exclusion."""
import argparse
import asyncio
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import run_deadline_pilot as runner
from run_parallel_supply import WaveGate, envelope

r = runner.r


def read(path):
    return json.loads(path.read_text())


def worker(bundle, wave, case_id, lock_fd, mock):
    runtime = read(wave / 'runtime.json')
    assert case_id in runtime['case_ids']
    stat = os.fstat(lock_fd)
    assert [stat.st_dev, stat.st_ino] == runtime['lock_identity']
    gate = WaveGate(wave, case_id)
    output = wave / ('mock-' + case_id) if mock else runner.output_path(case_id)
    with (wave / ('slot-' + case_id + '.lock')).open('a') as slot:
        fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            gate.check()
            result = asyncio.run(runner.execute(bundle, output, [case_id], mock=mock, gate=gate))
            r.save(wave / ('finished-' + case_id + '.json'), {'case_id': case_id,
                'output': str(output), 'complete': all(c['complete'] for c in result['cases']),
                'passed': result['all_passed'], 'results_sha256': r.sha(output / 'results.json')})
        except BaseException as exc:
            # Unexpected worker exceptions may leave reservations unresolved.
            gate.stop('worker/preflight exception: ' + type(exc).__name__)
            r.save(wave / ('failed-' + case_id + '.json'), {'case_id': case_id,
                'error_type': type(exc).__name__})
            raise


def supervise(bundle, out, cases, mock=None):
    plan, auth = runner.verify(bundle)
    fixed = {s['id'] for s in plan['cases']}
    assert 1 <= len(cases) <= 3 and len(set(cases)) == len(cases) and set(cases) <= fixed
    if not mock:
        gate = read(bundle.parent / 'validation/validation.json')
        assert gate['passed'] and gate['plan_sha256'] == r.sha(bundle / 'plan.json')
        assert time.time() < plan['paid_cutoff_unix']
    lock_path = Path(tempfile.gettempdir()) / ('modal-Hospital-' + hashlib.sha256(str(runner.HERE).encode()).hexdigest()[:16] + '.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prior = {'guard_usd': '0'} if mock else r.all_history()
        worst = envelope(prior['guard_usd'], len(cases))
        if not mock:
            assert all(not runner.output_path(case_id).exists() for case_id in cases)
        out.mkdir(parents=True, exist_ok=False)
        stat = os.fstat(lock.fileno())
        r.save(out / 'runtime.json', {'coordinator_pid': os.getpid(),
            'lock_identity': [stat.st_dev, stat.st_ino], 'case_ids': cases,
            'plan_sha256': r.sha(bundle / 'plan.json'), 'mock': mock, 'prior': prior,
            'baseline_guard_usd': prior['guard_usd'], 'reserved_run_envelopes_usd': str(10*len(cases)),
            'worst_case_guard_usd': str(worst), 'envelope_is_capacity_not_charge': True})
        admission = WaveGate(out, None)
        processes, logs = {}, []
        started = time.monotonic()
        try:
            r.save(out / 'heartbeat.json', {'unix': time.time()})
            for case_id in cases:
                log = (out / (case_id + '.log')).open('w'); logs.append(log)
                command = [sys.executable, str(runner.HERE / 'run_deadline_pilot.py'), 'worker',
                    '--bundle', str(bundle), '--out', str(out), '--seed', case_id,
                    '--lock-fd', str(lock.fileno())]
                if mock:
                    command += ['--mock', mock]
                processes[case_id] = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                    pass_fds=(lock.fileno(),))
            previous = None
            while True:
                r.save(out / 'heartbeat.json', {'unix': time.time()})
                codes = {name: process.poll() for name, process in processes.items()}
                if any(code is not None and code != 0 for code in codes.values()):
                    admission.stop('unexpected worker failure')
                if not (out / 'release.json').exists() and not (out / 'stop.json').exists():
                    if all((out / ('ready-' + name + '.json')).exists() for name in cases):
                        ready = [read(out / ('ready-' + name + '.json')) for name in cases]
                        assert all(row['calls'] == 0 and row['status'] == 'ready' for row in ready)
                        r.save(out / 'release.json', {'all_ready': ready, 'unix': time.time()})
                    elif time.monotonic() - started > 120:
                        admission.stop('startup barrier deadline')
                if codes != previous:
                    r.save(out / 'status.json', {'exit_codes': codes, 'unix': time.time()}); previous = codes
                if all(code is not None for code in codes.values()):
                    break
                time.sleep(.2)
        except BaseException:
            admission.stop('coordinator interrupted')
            raise  # children retain lock and fail closed, without forced kills
        finally:
            for log in logs:
                log.close()
        report = {'plan_sha256': r.sha(bundle / 'plan.json'), 'mock': mock,
            'exit_codes': codes, 'shared_stop': read(out / 'stop.json') if (out / 'stop.json').exists() else None,
            'finished': [read(out / ('finished-' + name + '.json')) for name in cases
                if (out / ('finished-' + name + '.json')).exists()],
            'unresolved_worker_outputs': [name for name in cases if not (out / ('finished-' + name + '.json')).exists()]}
        r.save(out / 'results.json', report)
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--case', action='append', required=True)
    args = parser.parse_args()
    print(json.dumps(supervise(args.bundle, args.out, args.case), sort_keys=True))
