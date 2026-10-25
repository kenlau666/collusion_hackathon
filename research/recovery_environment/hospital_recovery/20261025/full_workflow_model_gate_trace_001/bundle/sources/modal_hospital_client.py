"""Native chat parser, fixed Modal route, reference accounting and one-shot deadline.

No key lookup or provider construction on import. ``spent_usd`` and the generic
ledger's ``known_cost_usd`` mean reference token estimates here, NOT Modal bills.
Missing usage.cost is unknown; it is never replaced by zero or the estimate.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from branch_runtime import TogetherClient
from budget_client import BudgetError, TransportReply, _NativeResponse, _approved, _redact

BASE_URL = 'https://kenlauhong2015--ep-deepseek-v4-1-flash-server.us-west.modal.direct/v1'
MODEL = 'deepseek-ai/DeepSeek-V4.1-Flash'
WORKER = Path(__file__).with_name('modal_request_worker.py')
BASIS = 'reference_token_estimate_not_actual_modal_billing'


def persist(path, value):
    temporary = path.with_suffix('.pending')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def validate_reply(reply):
    body = reply.body
    if type(reply.status_code) is not int or not 200 <= reply.status_code < 300:
        return 'http_failure', None, None
    if not isinstance(body, dict): return 'malformed_response', None, None
    usage, choices = body.get('usage'), body.get('choices')
    if (body.get('model') != MODEL or not isinstance(body.get('id'), str) or not body['id']
        or not isinstance(choices, list) or not choices or not isinstance(choices[0], dict)
        or not isinstance(choices[0].get('message'), dict)):
        return 'model_or_response_mismatch', None, None
    if not isinstance(usage, dict): return 'missing_usage', None, None
    prompt, output = usage.get('prompt_tokens'), usage.get('completion_tokens')
    if type(prompt) is not int or not 0 <= prompt <= 131072 or type(output) is not int or not 0 <= output <= 1024:
        return 'reported_token_limit', None, None
    details = usage.get('completion_tokens_details') or {}
    message = choices[0]['message']
    if (not isinstance(details, dict) or details.get('reasoning_tokens', 0) != 0
        or message.get('reasoning_content') or message.get('reasoning') or body.get('reasoning')):
        return 'unexpected_reasoning', None, None
    reported = None
    if usage.get('cost') is not None:
        try:
            reported = Decimal(str(usage['cost']))
            if not reported.is_finite() or reported < 0: raise InvalidOperation
        except (InvalidOperation, ValueError): return 'invalid_reported_cost', None, None
        if reported > Decimal('.049'):
            return 'overreservation_reported_cost', None, reported
    estimate = Decimal(prompt) * Decimal('.00000030') + Decimal(output) * Decimal('.00000120')
    return None, estimate, reported


class ModalHospitalClient(TogetherClient):
    is_real = True

    def __init__(self, ledger, base_url, model, headers, diagnostics, worker_sha256,
                 request_timeout=60, batch_deadline_monotonic=None, max_request_timeout=60):
        approved = _approved(ledger.authorization, ledger.plan_sha256)
        if (base_url != BASE_URL or model != MODEL or ledger.scope != approved['scope']
            or ledger.max_calls > min(198, approved['max_calls'])
            or ledger.max_usd > min(Decimal('10'), Decimal(approved['max_usd']))):
            raise BudgetError('Modal route or authorization mismatch')
        allowed = {'Modal-Key', 'Modal-Secret', 'Content-Type', 'Authorization'}
        if (not isinstance(headers, dict) or not set(headers) <= allowed or headers.get('Authorization')
            or headers.get('Content-Type', 'application/json') != 'application/json'
            or any(not isinstance(headers.get(k), str) or not headers[k] or any(c in headers[k] for c in '\r\n')
                   for k in ('Modal-Key', 'Modal-Secret'))):
            raise BudgetError('explicit Modal proxy headers required')
        if (type(max_request_timeout) is not int or max_request_timeout not in (60, 180)
                or type(request_timeout) not in (int, float) or not 0 < request_timeout <= max_request_timeout):
            raise BudgetError('invalid request deadline')
        self.ledger, self.base_url, self.model = ledger, base_url, model
        self._headers = {k: headers[k] for k in ('Modal-Key', 'Modal-Secret')}
        self.request_timeout, self.batch_deadline_monotonic = request_timeout, batch_deadline_monotonic
        self.worker_sha256, self.diagnostics = worker_sha256, Path(diagnostics)
        self.diagnostics.mkdir(exist_ok=False)
        self.transport, self.session = self, SimpleNamespace(post=self._native_post)
        self._lock, self._sampling_seed = threading.Lock(), None
        ledger.state.update(accounting_basis=BASIS, reported_cost_sum_usd='0',
            reported_cost_observations=0, reported_cost_missing=0, reported_cost_total_usd=None,
            metadata={'base_url': base_url, 'model': model, 'accounting_basis': BASIS,
                'input_reference_usd_per_million': '.30', 'output_reference_usd_per_million': '1.20',
                'seed_forwarded': False, 'actual_modal_billing_attested': False})
        ledger._persist()

    @staticmethod
    def _get_retry_config(): return 0, 0.0, 0.0

    def _build_headers(self): return {}

    def sanitize_for_log(self, value): return _redact(value, tuple(self._headers.values()))

    def generate_response(self, input, params):
        if not self._lock.acquire(blocking=False): raise BudgetError('concurrent Modal call refused')
        try:
            if params.get('model') != MODEL:
                self.ledger.halt('model_mismatch'); raise BudgetError('configured Modal model required')
            self._sampling_seed = params.get('seed')
            return super().generate_response(input=input, params=params)
        finally:
            self._lock.release()

    def _native_post(self, url, *, headers, data, timeout):
        if url != BASE_URL + '/chat/completions' or headers:
            self.ledger.halt('unexpected_native_transport_fields'); raise BudgetError('unexpected native route')
        remaining = self.request_timeout
        if self.batch_deadline_monotonic is not None:
            remaining = min(remaining, self.batch_deadline_monotonic - time.monotonic())
        if remaining <= 0:
            self.ledger.halt('batch_deadline'); raise BudgetError('batch deadline before request')
        payload = json.loads(data)
        for key in ('seed', 'provider', 'reasoning'): payload.pop(key, None)
        payload.update(model=MODEL, max_tokens=1024, temperature=0, stream=False, reasoning_effort='none')
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        bound = len(encoded) + 512 * (len(payload.get('messages', [])) + len(payload.get('tools', [])) + 1)
        if len(encoded) > 128 * 1024 or bound > 131072:
            self.ledger.halt('payload_or_prompt_bound'); raise BudgetError('local payload bound exceeded')
        call = self.ledger.reserve(self.sanitize_for_log(payload), len(encoded))
        record = self.ledger.state['records'][-1]
        record.update(accounting_basis=BASIS, local_sampling_seed=self._sampling_seed,
            seed_forwarded=False, conservative_prompt_bound=bound, reported_cost_usd=None)
        self.ledger._persist()
        try:
            reply = self.transport.post(deepcopy(payload), timeout=remaining)
            failure, estimate, reported = validate_reply(reply)
            body = self.sanitize_for_log(reply.body)
            json.dumps(body, allow_nan=False)
        except Exception:
            self.ledger.state['reported_cost_missing'] += 1
            self.ledger.state['reported_cost_total_usd'] = None
            self.ledger.finish(call, failure='transport_failure')
            raise BudgetError('Modal request failed; unknown reservation retained') from None
        record.update(reference_estimate_usd=str(estimate) if estimate is not None else None,
                      reported_cost_usd=str(reported) if reported is not None else None)
        if reported is None: self.ledger.state['reported_cost_missing'] += 1
        else:
            self.ledger.state['reported_cost_observations'] += 1
            self.ledger.state['reported_cost_sum_usd'] = str(Decimal(self.ledger.state['reported_cost_sum_usd']) + reported)
        self.ledger.state['reported_cost_total_usd'] = (self.ledger.state['reported_cost_sum_usd']
            if self.ledger.state['reported_cost_missing'] == 0 else None)
        self.ledger.finish(call, status_code=reply.status_code, response=body,
                           cost=estimate if not failure else None, failure=failure)
        if failure: raise BudgetError('Modal response rejected; reservation retained')
        return _NativeResponse(body)

    def post(self, payload, *, timeout):
        started, process = time.monotonic(), None
        call = self.ledger.state['calls']
        record = {'call_id': call, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
            'kind': 'transport_error', 'stage': 'spawn', 'retry_count': 0, 'timeout_seconds': timeout}
        progress_path = (self.diagnostics / f'call-{call:04d}.progress.json').resolve()
        try:
            if hashlib.sha256(WORKER.read_bytes()).hexdigest() != self.worker_sha256:
                raise BudgetError('worker source differs from freeze')
            process = subprocess.Popen([sys.executable, str(WORKER)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env={'PATH': os.defpath,
                    'MODAL_ENDPOINT_BASE_URL': BASE_URL, 'MODAL_PROXY_TOKEN_ID': self._headers['Modal-Key'],
                    'MODAL_PROXY_TOKEN_SECRET': self._headers['Modal-Secret'],
                    'MODAL_PROGRESS_PATH': str(progress_path)})
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0: raise subprocess.TimeoutExpired(process.args, timeout)
            output, stderr = process.communicate(json.dumps({'payload': payload, 'timeout': remaining},
                ensure_ascii=False), timeout=remaining)
            record.update(child_exit_code=process.returncode, stderr_bytes=len(stderr.encode()))
            if process.returncode: raise BudgetError('worker exited')
            result = json.loads(output)
            if result.get('kind') != 'reply':
                for key in ('stage', 'exception_type', 'cause_type', 'errno', 'http_status'):
                    value = result.get(key)
                    if type(value) is int or value is None or isinstance(value, str) and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,79}', value):
                        record[key] = value
                raise BudgetError('typed worker transport failure')
            record.update(kind='reply', stage='complete', http_status=result['status_code'])
            return TransportReply(result['status_code'], result['body'])
        except subprocess.TimeoutExpired:
            record.update(category='whole_request_deadline', exception_type='TimeoutExpired')
            raise BudgetError('request deadline; charge unknown') from None
        except Exception as error:
            record.setdefault('exception_type', type(error).__name__)
            raise BudgetError('Modal transport failed; inspect safe diagnostic') from None
        finally:
            if process is not None and process.poll() is None:
                try: process.kill()
                except ProcessLookupError: pass
                try:
                    process.communicate(timeout=2); record['child_reaped'] = True
                except subprocess.TimeoutExpired:
                    record['child_reaped'] = False
            record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),
                          elapsed_monotonic_seconds=time.monotonic() - started)
            if progress_path.exists():
                try:
                    progress = json.loads(progress_path.read_text())
                    allowed_stages = {'validate', 'waiting_for_headers', 'reading_body', 'parsing', 'complete'}
                    if progress.get('stage') in allowed_stages:
                        record['worker_progress_stage'] = progress['stage']
                except (ValueError, OSError):
                    record['worker_progress_unreadable'] = True
            persist(self.diagnostics / f'call-{call:04d}.json', record)
