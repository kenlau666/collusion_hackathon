"""Explicitly authorized one-time timeout recovery, with every attempt retained.

Only new opt-in ledgers may enter retry_pending. Historical ledgers stay closed.
No incomplete model response reaches the native tool parser or environment.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from budget_client import BudgetError, BudgetLedger
from traced_modal_client import TracedModalClient

POLICY = {'max_retries_per_request': 1, 'trigger': 'local_request_or_socket_timeout',
          'same_payload_required': True, 'non_timeout_retries': 0}
DIRECTIVE = ('Human instruction 2026-10-25: yes, add one logged retry for the exact same request '
             'on timeout and continue the experiment. preserve all failed attempts and costs, '
             'and stay within the $50 budget')


def encoded(payload):
    return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def verified_timeout(diagnostic, call):
    return (diagnostic.get('call_id') == call and diagnostic.get('kind') == 'transport_error'
        and diagnostic.get('child_reaped') is True
        and (diagnostic.get('category') == 'whole_request_deadline'
             or diagnostic.get('exception_type') == 'TimeoutError'))


class TimeoutRetryLedger(BudgetLedger):
    """Durable failed attempt + narrowly authorized exact-payload retry transition."""
    def __init__(self, *args, cumulative_guard=None, **kwargs):
        authorization = kwargs.get('authorization') or {}
        if (authorization.get('timeout_retry_policy') != POLICY
                or authorization.get('retry_approval_reference') != DIRECTIVE):
            raise BudgetError('explicit exact-request timeout retry authorization required')
        super().__init__(*args, **kwargs)
        self.cumulative_guard = cumulative_guard
        self.attempt_context = {}
        self.state.update(timeout_retry_policy=deepcopy(POLICY), retry_events=[], pending_retry=None)
        self._persist()

    def reserve(self, payload, payload_bytes):
        with self._lock:
            digest = fingerprint(payload)
            wire = encoded(payload)
            wire_digest = hashlib.sha256(wire).hexdigest()
            pending = self.state.get('pending_retry')
            if self.state['status'] == 'retry_pending':
                if (not pending or pending['payload_sha256'] != digest
                        or pending['wire_payload_sha256'] != wire_digest
                        or payload_bytes != pending['payload_bytes']
                        or payload != self.state['records'][-1]['payload']
                        or self.attempt_context.get('attempt_index') != 1
                        or self.attempt_context.get('logical_request_id') != pending['logical_request_id']):
                    self.halt('retry_payload_or_link_mismatch')
                    raise BudgetError('timeout retry differs from the original request')
            elif pending or self.attempt_context.get('attempt_index') != 0:
                self.halt('invalid_retry_state')
                raise BudgetError('retry reservation without authorized timeout')
            if self.cumulative_guard is not None:
                if Decimal(self.cumulative_guard()['guard_usd']) + Decimal('.049') > 50:
                    self.halt('cumulative_dollar_limit')
                    raise BudgetError('cumulative ceiling before provider attempt')
            if self.state['status'] == 'retry_pending':
                # Only the next exact request may consume this explicit transition.
                # A process crash still cannot reopen this ledger's directory.
                self.state['status'] = 'ready'
                self._persist()
            call = super().reserve(payload, payload_bytes)
            record = self.state['records'][-1]
            record.update(deepcopy(self.attempt_context), payload_sha256=digest,
                wire_payload_sha256=wire_digest, wire_payload_json=wire.decode(),
                retry_of_call_id=pending['failed_call_id'] if pending else None)
            if pending:
                self.state['records'][-2]['retried_by_call_id'] = call
                self.state['retry_events'][-1]['retry_call_id'] = call
                self.state['pending_retry'] = None
            self._persist()
            return call

    def prepare_timeout_retry(self, call, diagnostic_path):
        with self._lock:
            record = self.state['records'][-1]
            path = Path(diagnostic_path)
            diagnostic = json.loads(path.read_text())
            if (self.state['status'] != 'halted' or self.state['halt_reason'] != 'transport_failure'
                    or record['call_id'] != call or record['status'] != 'failed'
                    or record.get('attempt_index') != 0 or record.get('retry_of_call_id') is not None
                    or not verified_timeout(diagnostic, call)):
                raise BudgetError('failed attempt is not eligible for a timeout retry')
            event = {'failed_call_id': call, 'retry_call_id': None,
                'logical_request_id': record['logical_request_id'],
                'payload_sha256': fingerprint(record['payload']), 'payload_bytes': record['payload_bytes'],
                'wire_payload_sha256': record['wire_payload_sha256'],
                'reason': 'one_authorized_timeout_retry',
                'diagnostic_path': str(path), 'diagnostic_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'failed_reservation_retained_usd': record['reservation_usd'],
                'scheduled_at_utc': datetime.now(timezone.utc).isoformat()}
            self.state['retry_events'].append(event)
            self.state.update(status='retry_pending', halt_reason=None, pending_retry=deepcopy(event))
            self._persist()


class TimeoutRetryClient(TracedModalClient):
    def __init__(self, *args, **kwargs):
        if not isinstance(kwargs.get('ledger'), TimeoutRetryLedger):
            raise BudgetError('timeout retry needs its opt-in ledger')
        super().__init__(*args, **kwargs)
        self.logical_requests = 0
        self._last_timeout_diagnostic = None

    def post(self, payload, *, timeout):
        # Verify the actual worker body against the durably logged wire bytes.
        record = self.ledger.state['records'][-1]
        if hashlib.sha256(encoded(payload)).hexdigest() != record['wire_payload_sha256']:
            raise BudgetError('actual provider request differs from logged request bytes')
        try:
            return super().post(payload, timeout=timeout)
        except BudgetError:
            call = self.ledger.state['calls']
            path = self.diagnostics / f'call-{call:04d}.json'
            if path.exists() and verified_timeout(json.loads(path.read_text()), call):
                self._last_timeout_diagnostic = path
            raise

    def _native_post(self, url, *, headers, data, timeout):
        self.logical_requests += 1
        logical = self.logical_requests
        original_data = data
        for index in (0, 1):
            self.ledger.attempt_context = {'logical_request_id': logical, 'attempt_index': index}
            self._last_timeout_diagnostic = None
            try:
                # The native serialized request and normalization inputs are unchanged.
                return super()._native_post(url, headers=headers, data=original_data, timeout=timeout)
            except BudgetError:
                if index != 0 or self._last_timeout_diagnostic is None:
                    raise
                self.ledger.prepare_timeout_retry(self.ledger.state['calls'], self._last_timeout_diagnostic)
