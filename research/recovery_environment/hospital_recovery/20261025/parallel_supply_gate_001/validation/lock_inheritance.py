"""Local OS lock inheritance control; no inference or network access."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

NETWORK = []


def deny(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        NETWORK.append(event)
        raise RuntimeError('network denied in local lock fixture')


sys.addaudithook(deny)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    directory = Path(__file__).resolve().parent
    supervisor = directory.parents[2] / 'run_parallel_supply.py'
    plan = directory.parent / 'bundle/plan.json'
    probe = '''import fcntl,sys
with open(sys.argv[1],'a') as handle:
    try:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(77)
'''
    child_code = '''import os,sys,time,json
from pathlib import Path
fd=int(sys.argv[1]); root=Path(sys.argv[2]); value=os.fstat(fd)
(root/'ready.json').write_text(json.dumps({'device':value.st_dev,'inode':value.st_ino}))
while not (root/'release').exists():
    time.sleep(.01)
# No flock call: merely keeping the inherited descriptor retains the lock.
'''
    with tempfile.TemporaryDirectory(prefix='hospital-lock-inheritance-') as tmp:
        root = Path(tmp)
        lock_path = root / 'original-exclusion.lock'
        handle = lock_path.open('a')
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def blocked():
            outcome = subprocess.run([sys.executable, '-c', probe, str(lock_path)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            assert outcome.returncode in (0, 77), outcome.stderr.decode()
            return outcome.returncode == 77

        parent_excludes = blocked()
        assert parent_excludes
        identity = os.fstat(handle.fileno())
        child = subprocess.Popen([sys.executable, '-c', child_code, str(handle.fileno()), str(root)],
            pass_fds=(handle.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            until = time.monotonic() + 5
            while not (root / 'ready.json').exists() and time.monotonic() < until:
                assert child.poll() is None
                time.sleep(.01)
            ready = json.loads((root / 'ready.json').read_text())
            assert ready == {'device': identity.st_dev, 'inode': identity.st_ino}
            handle.close()
            inherited_excludes = blocked()
            assert inherited_excludes and child.poll() is None
            (root / 'release').write_text('release child normally\n')
            _, stderr = child.communicate(timeout=5)
            assert child.returncode == 0, stderr.decode()
            released = not blocked()
            assert released
        finally:
            handle.close()
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)
    assert not NETWORK
    result = {'passed': True, 'script_sha256': sha(Path(__file__).resolve()),
        'supervisor_sha256': sha(supervisor), 'orchestration_plan_sha256': sha(plan),
        'Results': {'parent_holding_lock_excludes_independent_process': parent_excludes,
            'inherited_child_retains_exclusion_after_parent_close': inherited_excludes,
            'child_normal_exit_releases_exclusion': released,
            'inherited_descriptor_same_device_inode': True},
        'positive_control': 'independent process acquires after final inherited descriptor closes',
        'positive_control_passed': released, 'n_per_condition': 1,
        'sample_sd': None, 'sample_variance': None, 'network_attempts': NETWORK,
        'inference_calls': 0, 'new_spend_usd': '0',
        'limit': 'Local flock/pass_fds behavior only; no claim about endpoint concurrency or model behavior.'}
    (directory / 'lock_inheritance.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
