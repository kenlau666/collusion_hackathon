"""Opt-in JSON transport with phase timings; same native parser and no retries."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from budget_client import BudgetError, TransportReply
from modal_hospital_client import BASE_URL, ModalHospitalClient, persist

WORKER = Path(__file__).with_name('endpoint_probe_worker.py')


class TracedModalClient(ModalHospitalClient):
    def post(self, payload, *, timeout):
        if payload.get('stream') is not False or 'stream_options' in payload:
            raise BudgetError('traced Hospital transport requires unchanged JSON payload')
        started, child = time.monotonic(), None
        call = self.ledger.state['calls']
        progress = (self.diagnostics / f'call-{call:04d}.progress.json').resolve()
        diagnostic = {'call_id': call, 'kind': 'transport_error', 'retry_count': 0,
            'timeout_seconds': timeout, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
            'transport': 'trace-json'}
        try:
            if hashlib.sha256(WORKER.read_bytes()).hexdigest() != self.worker_sha256:
                raise BudgetError('traced worker differs from freeze')
            child = subprocess.Popen([sys.executable, str(WORKER)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env={'PATH': os.defpath, 'MODAL_PROXY_TOKEN_ID': self._headers['Modal-Key'],
                     'MODAL_PROXY_TOKEN_SECRET': self._headers['Modal-Secret'],
                     'MODAL_PROGRESS_PATH': str(progress)})
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(child.args, timeout)
            output, stderr = child.communicate(json.dumps({'base_url': BASE_URL, 'method': 'POST',
                'path': '/v1/chat/completions', 'payload': payload, 'timeout': remaining},
                ensure_ascii=False, allow_nan=False), timeout=remaining)
            diagnostic.update(child_exit_code=child.returncode, stderr_bytes=len(stderr.encode()))
            if child.returncode:
                raise BudgetError('traced worker exited')
            result = json.loads(output)
            if result.get('kind') != 'reply':
                diagnostic.update(exception_type=result.get('exception_type'), errno=result.get('errno'))
                raise BudgetError('traced request failed')
            diagnostic.update(kind='reply', http_status=result['status_code'])
            return TransportReply(result['status_code'], result['body'])
        except subprocess.TimeoutExpired:
            diagnostic.update(category='whole_request_deadline', exception_type='TimeoutExpired')
            raise BudgetError('traced deadline; reservation retained') from None
        except Exception as error:
            diagnostic.setdefault('exception_type', type(error).__name__)
            raise BudgetError('traced transport failed; inspect phases') from None
        finally:
            if child is not None and child.poll() is None:
                child.kill()
                child.communicate(timeout=2)
            diagnostic.update(child_reaped=child is not None and child.poll() is not None,
                elapsed_monotonic_seconds=time.monotonic() - started,
                finished_at_utc=datetime.now(timezone.utc).isoformat())
            if progress.exists():
                # Worker sidecars contain phases/counts, not credentials or bodies.
                phases = json.loads(progress.read_text())
                diagnostic['worker_progress_stage'] = phases['stage']
                diagnostic['phase_events'] = phases.get('events', [])
                diagnostic['body_bytes'] = phases.get('body_bytes', 0)
            persist(self.diagnostics / f'call-{call:04d}.json', diagnostic)
