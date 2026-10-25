"""Opt-in financial byte guard; native request content and token acceptance unchanged."""
from decimal import Decimal

from budget_client import BudgetError, RESERVATION_USD
from timeout_retry_client import TimeoutRetryClient

INPUT_RATE = Decimal('.00000030')
OUTPUT_RATE = Decimal('.00000120')
OUTPUT_LIMIT = 1024
MAX_PADDED_BYTES = int((RESERVATION_USD-OUTPUT_LIMIT*OUTPUT_RATE)/INPUT_RATE)
POLICY = {'name': 'serialized_bytes_with_reservation_bound_v1',
    'max_padded_bytes': MAX_PADDED_BYTES, 'padding_per_message_tool_and_envelope': 512,
    'reservation_usd': str(RESERVATION_USD), 'input_reference_usd_per_token': str(INPUT_RATE),
    'output_reference_usd_per_token': str(OUTPUT_RATE), 'output_tokens': OUTPUT_LIMIT,
    'reported_input_limit': 131072}
TRANSPORT = 'trace-json-retry1-financial'


class FinancialByteClient(TimeoutRetryClient):
    def __init__(self, *args, **kwargs):
        ledger = kwargs.get('ledger')
        if ledger is None or ledger.authorization.get('capacity_guard_policy') != POLICY:
            raise BudgetError('explicit frozen financial byte-guard policy required')
        super().__init__(*args, **kwargs)
        ledger.state['capacity_guard_policy'] = POLICY.copy()
        ledger._persist()

    def _payload_bound(self, payload, wire):
        padded = len(wire)+512*(len(payload.get('messages', []))+len(payload.get('tools', []))+1)
        maximum = Decimal(padded)*INPUT_RATE+OUTPUT_LIMIT*OUTPUT_RATE
        if payload.get('max_tokens') != OUTPUT_LIMIT or maximum > RESERVATION_USD:
            self.ledger.halt('payload_financial_bound')
            raise BudgetError('serialized prompt bound exceeds unchanged reservation')
        return padded
