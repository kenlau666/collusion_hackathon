"""Fixed-route one-shot transport with a killable request and safe diagnostics."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from budget_client import BudgetError, TransportReply, _approved, _redact

WORKER = Path(__file__).with_name('request_worker.py')


def persist(path, value):
    temporary = path.with_suffix('.pending')
    with temporary.open('w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def safe_class(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,79}', value) else None


class DeadlineTransport:
    is_real = True

    def __init__(self, *, authorization, api_key, expected_plan_sha256,
                 worker_sha256, ledger, diagnostics):
        self.authorization_summary = _approved(authorization, expected_plan_sha256)
        if not isinstance(api_key, str) or not api_key.strip() or any(c in api_key for c in '\r\n'):
            raise BudgetError('invalid explicit credential')
        self._key = api_key
        self.worker_sha256, self.ledger = worker_sha256, ledger
        self.diagnostics = Path(diagnostics)
        self.diagnostics.mkdir(exist_ok=False)

    def sanitize_for_log(self, value):
        return _redact(value, (self._key,))

    def post(self, payload, *, timeout):
        started = time.monotonic()
        call_id = self.ledger.state['calls']
        record = {'call_id': call_id, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                  'timeout_seconds': timeout, 'retry_count': 0, 'http_status': None,
                  'stage': 'spawn', 'kind': 'transport_error'}
        process = None
        try:
            if hashlib.sha256(WORKER.read_bytes()).hexdigest() != self.worker_sha256:
                raise BudgetError('worker source differs from freeze')
            # No key in argv/stdin, no credentials loaded by the worker import.
            process = subprocess.Popen(
                [sys.executable, str(WORKER)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env={'PATH': os.defpath, 'OPENROUTER_API_KEY': self._key})
            record['stage'] = 'worker_open_read_parse'
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout)
            output, error_output = process.communicate(
                json.dumps({'payload': payload, 'timeout': remaining}, ensure_ascii=False),
                timeout=remaining)
            record.update(child_exit_code=process.returncode, stderr_bytes=len(error_output.encode()))
            if process.returncode != 0:
                record['category'] = 'worker_exit'
                raise BudgetError('request worker failed')
            result = json.loads(output)
            if result.get('kind') == 'transport_error':
                record.update(kind='transport_error', category='worker_transport_exception',
                              stage=result.get('stage') if result.get('stage') in {'open','read','parse'} else 'worker',
                              exception_type=safe_class(result.get('exception_type')),
                              cause_type=safe_class(result.get('cause_type')))
                number = result.get('errno')
                record['errno'] = number if isinstance(number,int) and not isinstance(number,bool) else None
                record['http_status'] = result.get('http_status') if isinstance(result.get('http_status'),int) else None
                raise BudgetError('typed request transport failure')
            if result.get('kind') != 'reply' or not isinstance(result.get('status_code'), int):
                raise BudgetError('malformed worker envelope')
            record.update(kind='reply', category='http_response', stage='complete',
                          http_status=result['status_code'])
            return TransportReply(result['status_code'], result['body'])
        except subprocess.TimeoutExpired:
            record.update(category='whole_request_deadline', exception_type='TimeoutExpired')
            if process is not None:
                process.kill()
                try:
                    process.communicate(timeout=2)
                    record['child_exit_code'] = process.returncode
                    record['child_reaped'] = True
                except subprocess.TimeoutExpired:
                    record['child_reaped'] = False
            raise BudgetError('request deadline; outcome and charge unknown') from None
        except Exception as error:
            record.setdefault('category', 'parent_transport_exception')
            record.setdefault('exception_type', safe_class(type(error).__name__))
            raise BudgetError('request transport failed; inspect safe diagnostic') from None
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                try:
                    process.communicate(timeout=2)
                    record['child_reaped'] = True
                except subprocess.TimeoutExpired:
                    record['child_reaped'] = False
            record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),
                          elapsed_monotonic_seconds=time.monotonic()-started)
            persist(self.diagnostics/f'call-{call_id:04d}.json', record)
