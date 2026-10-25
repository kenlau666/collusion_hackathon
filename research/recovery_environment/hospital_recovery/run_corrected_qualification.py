"""Launch the unchanged corrected freeze only after a separate human run approval."""
import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE / '20261025'
BUNDLE = BASE / 'corrected_control_gate_002/bundle'
PLAN_SHA = 'f24af35934b3c8b29d7a63b56057c48a650c7bd212ca7dd6070b89b8288738fd'
AUTH = BASE / 'corrected_qualification_authorization.json'
LAUNCH = BASE / 'corrected_qualification_launch_manifest.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def check(output):
    plan, authorization, launch = read(BUNDLE / 'plan.json'), read(AUTH), read(LAUNCH)
    if (sha(BUNDLE / 'plan.json') != PLAN_SHA or authorization.get('approved') is not True
        or authorization.get('plan_sha256') != PLAN_SHA or authorization.get('scope') != 'full'
        or authorization.get('max_calls') != 198 or Decimal(authorization.get('max_usd', '0')) != 10
        or launch.get('plan_sha256') != PLAN_SHA or launch.get('authorization_sha256') != sha(AUTH)
        or launch.get('launcher_sha256') != sha(Path(__file__))):
        raise ValueError('frozen plan/run approval/launcher binding mismatch')
    for name, expected in plan['source_hashes'].items():
        if sha(HERE / name) != expected or sha(BUNDLE / 'sources' / name) != expected:
            raise ValueError('corrected research source mismatch')
    for name, expected in plan['native_sources'].items():
        if sha(Path(name)) != expected:
            raise ValueError('native source mismatch')
    for name, expected in plan['files'].items():
        if sha(BUNDLE / name) != expected:
            raise ValueError('corrected input file mismatch')
    for name, expected in plan['old_failed_run_files'].items():
        if sha(Path(name)) != expected:
            raise ValueError('old failed evidence mismatch')
    validation = Path(plan['validation_results_path'])
    if not validation.is_absolute():
        validation = HERE.parents[2] / validation
    if sha(validation) != plan['validation_results_sha256']:
        raise ValueError('offline validation evidence mismatch')

    saved_ipv6 = socket.has_ipv6
    try:
        socket.has_ipv6 = False  # suppress the documented unused import-only probe
        import corrected_control_prompts as corrected
        import modal_hospital_runtime as modal
        from branch_runtime import ScriptedChatClient
        from llm_server.clients.together_client import _convert_tools
    finally:
        socket.has_ipv6 = saved_ipv6
    modal.validate_output(output)
    if (plan['cases'] != corrected.engagement.matrix() or plan['max_calls'] != 198
        or plan['max_usd'] != '10' or plan['model'] != modal.MODEL
        or plan['endpoint'] != modal.EXPECTED_BASE or plan['contract'] != corrected.CONTRACT
        or plan['conversation_cap'] != 3 or plan['request_deadline_seconds'] != 60
        or plan['batch_deadline_seconds'] != 1800 or plan['main_study_started'] is not False):
        raise ValueError('qualification parameters mismatch')
    prior = modal.history()
    if prior != plan['prior_accounting'] or Decimal(prior['conservative_guard_usd']) + 10 > 50:
        raise ValueError('prior accounting changed or ceiling insufficient')
    roots, inputs = read(BUNDLE / 'roots.json'), read(BUNDLE / 'initial_inputs.json')
    for spec in plan['cases']:
        branch, root, steps = await corrected.make_case(spec)
        if json.loads(json.dumps(root)) != roots[spec['id']]:
            raise ValueError('corrected root reconstruction mismatch')
        client = ScriptedChatClient()
        await modal.modal_turn(branch, steps[0], client)
        request = client.requests[0]
        actual = {'messages': request['input'], 'tools': _convert_tools(request['params']['tools']),
                  'model': modal.MODEL, 'local_sampling_seed': steps[0]['sampling_seed'],
                  'api_seed_forwarded': False}
        if actual != inputs[spec['id']]:
            raise ValueError('corrected first input reconstruction mismatch')
    return plan, authorization, roots, corrected, modal


async def run(output):
    lock_path = Path(tempfile.gettempdir()) / (
        'modal-Hospital-' + hashlib.sha256(str(HERE).encode()).hexdigest()[:16] + '.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan, authorization, roots, corrected, modal = await check(output)
        # Only now may the frozen Modal-specific helper read proxy credentials.
        base, headers = modal.config()
        from modal_request_worker import NoRedirect
        import certifi
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=certifi.where())))
        with opener.open(urllib.request.Request(base + '/models', headers=headers), timeout=20) as response:
            metadata = json.load(response)
        if modal.MODEL not in [m.get('id') for m in metadata.get('data', [])]:
            raise ValueError('configured Modal model unavailable')
        from budget_client import BudgetLedger
        from modal_hospital_client import ModalHospitalClient
        output.mkdir(parents=True, exist_ok=False)
        corrected.engagement.save(output / 'preflight.json', {
            'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'plan_sha256': PLAN_SHA,
            'authorization_sha256': sha(AUTH), 'launch_manifest_sha256': sha(LAUNCH),
            'launcher_sha256': sha(Path(__file__)), 'model': modal.MODEL, 'endpoint': base,
            'authentication_header_names': list(headers), 'metadata': metadata,
            'prior_accounting': plan['prior_accounting'], 'actual_modal_charges_verified': False})
        ledger = BudgetLedger(output / 'accounting', scope='full', max_calls=198,
                              max_usd='10', plan_sha256=PLAN_SHA, authorization=authorization)
        client = ModalHospitalClient(ledger, base, modal.MODEL, headers,
            output / 'transport_diagnostics', plan['source_hashes']['modal_request_worker.py'],
            request_timeout=60, batch_deadline_monotonic=time.monotonic() + 1800)
        return await corrected.execute(client, output, roots)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'run'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'check':
        def offline(event, values):
            if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
                raise RuntimeError('network denied during input check')
            if event == 'open' and isinstance(values[0], (str, bytes)) and str(values[0]).endswith('compute.env'):
                raise RuntimeError('credential file denied during input check')
        sys.addaudithook(offline)
    try:
        if args.command == 'check':
            asyncio.run(check(args.out))
            print(json.dumps({'offline_check': 'passed', 'roots_and_initial_inputs': 12,
                              'provider_calls': 0, 'credential_lookups': 0}))
        else:
            _, result = asyncio.run(run(args.out))
            raise SystemExit(0 if result['qualification_passed'] else 2)
    except Exception as error:
        print(json.dumps({'status': 'stopped', 'error_type': type(error).__name__}))
        raise SystemExit(1)
