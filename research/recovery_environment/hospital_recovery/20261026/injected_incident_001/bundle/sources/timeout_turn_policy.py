"""Prospective human-selected abandonment of one exhausted timeout generation.

Only fresh ledgers can opt in. Failed records/holds remain; no third attempt,
rollback, fabricated reply or execution of partial output is permitted.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from budget_client import BudgetError
from timeout_retry_client import TimeoutRetryLedger, verified_timeout

DIRECTIVE = 'Human design choice 2026-10-26: Record the failed turn as no action and continue later scheduled turns (Recommended)'
POLICY = {'name': 'exhausted_timeout_generation_abandon_v1', 'max_attempts_per_generation': 2,
    'eligible_error': 'both exact attempts have typed timeout and reaped worker',
    'next_action': 'advance to next scheduled native turn; do not retry abandoned generation',
    'prior_completed_tool_effects': 'retain, including communication; never rollback',
    'clinical_gate': 'unchanged care8/8, no executed shortage or precare reward-only recurrence',
    'instructed_controls': 'any abandoned turn fails the strict designated-sequence control'}


class ContinueTurnLedger(TimeoutRetryLedger):
    def __init__(self, *args, **kwargs):
        auth = kwargs.get('authorization') or {}
        if auth.get('timeout_turn_policy') != POLICY or auth.get('timeout_turn_approval') != DIRECTIVE:
            raise BudgetError('explicit prospective timeout-turn policy required')
        super().__init__(*args, **kwargs)
        self.state.update(timeout_turn_policy=deepcopy(POLICY), abandoned_timeout_turns=[])
        self._persist()

    def reserve(self, payload, payload_bytes):
        with self._lock:
            logical = self.attempt_context.get('logical_request_id')
            if any(event['logical_request_id'] == logical for event in self.state['abandoned_timeout_turns']):
                self.halt('abandoned_logical_request_reuse')
                raise BudgetError('abandoned generation cannot be attempted again')
            return super().reserve(payload, payload_bytes)

    def abandon_timeout_turn(self, *, diagnostics, turn, physical_unchanged,
                            retained_prior_callbacks):
        """Return False on any ineligible failure; never rehabilitate that error."""
        with self._lock:
            if (self.state['status'] != 'halted' or self.state['halt_reason'] != 'transport_failure'
                    or self.state.get('pending_retry') is not None or not physical_unchanged
                    or len(self.state['records']) < 2):
                return False
            first, second = self.state['records'][-2:]
            logical = first.get('logical_request_id')
            if (first['status'] != 'failed' or second['status'] != 'failed'
                    or first.get('attempt_index') != 0 or second.get('attempt_index') != 1
                    or first.get('retried_by_call_id') != second['call_id']
                    or second.get('retry_of_call_id') != first['call_id']
                    or second.get('logical_request_id') != logical
                    or first.get('wire_payload_json') != second.get('wire_payload_json')
                    or not self.state['retry_events']
                    or self.state['retry_events'][-1].get('retry_call_id') != second['call_id']
                    or any(e['logical_request_id'] == logical for e in self.state['abandoned_timeout_turns'])):
                return False
            evidence = []
            for record in (first, second):
                path = Path(diagnostics) / f"call-{record['call_id']:04d}.json"
                if not path.exists():
                    return False
                diagnostic = json.loads(path.read_text())
                wire = record.get('wire_payload_json', '').encode()
                if (not verified_timeout(diagnostic, record['call_id'])
                        or hashlib.sha256(wire).hexdigest() != record.get('wire_payload_sha256')
                        or record.get('response') is not None):
                    return False
                evidence.append({'call_id': record['call_id'], 'diagnostic_path': str(path),
                    'diagnostic_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'retained_reservation_usd': record['reservation_usd']})
            self.state['abandoned_timeout_turns'].append({'turn': deepcopy(turn),
                'logical_request_id': logical, 'failed_call_ids': [first['call_id'], second['call_id']],
                'wire_payload_sha256': first['wire_payload_sha256'], 'evidence': evidence,
                'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
                'failed_reply_native_effects': 0, 'physical_state_unchanged': True,
                'retained_prior_callbacks': retained_prior_callbacks,
                'outcome': 'failed generation has no action; next scheduled turn remains eligible'})
            self.state.update(status='ready', halt_reason=None)
            self._persist()
            return True
