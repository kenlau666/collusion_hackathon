"""Read-only orchestration/stop reconciliation, separate from clinical analysis."""
import argparse
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def stamp(value):
    return datetime.fromisoformat(value).timestamp()


def main(bundle, wave, out):
    plan = read(bundle / 'plan.json')
    runtime, report, dispatch = (read(wave / p) for p in ('runtime.json', 'results.json', 'dispatch.json'))
    assert plan['seeds'] == [3, 4, 5] and runtime['seeds'] == plan['seeds']
    assert runtime['plan_sha256'] == report['plan_sha256'] == dispatch['orchestration_plan_sha256'] == sha(bundle / 'plan.json')
    assert dispatch['runtime_sha256'] == sha(wave / 'runtime.json')
    assert dispatch['startup_release_sha256'] == sha(wave / 'release.json')
    assert Decimal(runtime['baseline_guard_usd']) + Decimal(runtime['reserved_run_envelopes_usd']) == Decimal(runtime['worst_case_guard_usd']) <= 50
    for name, expected in plan['sources'].items():
        assert sha(bundle / 'sources' / name) == expected
    release = read(wave / 'release.json')
    assert [r['seed'] for r in release['all_ready']] == [3, 4, 5]
    assert all(r['status'] == 'ready' and r['calls'] == 0 for r in release['all_ready'])
    stop = read(wave / 'stop.json') if (wave / 'stop.json').exists() else None
    assert report['shared_stop'] == stop
    rows, provenance = [], {}
    for item in report['finished']:
        seed, run = item['seed'], Path(item['output'])
        results, ledger, analysis, orchestration = (read(run / p) for p in
            ('results.json', 'accounting/ledger.json', 'analysis.json', 'orchestration.json'))
        assert sha(run / 'results.json') == item['results_sha256']
        assert analysis['positive_control_passed'] and analysis['supply_preflight_reconciliation_passed']
        assert analysis['reconciliation_passed']
        assert orchestration['orchestration_plan_sha256'] == sha(bundle / 'plan.json')
        assert results['plan_sha256'] == ledger['plan_sha256'] == plan['ordinary_plan_sha256']
        assert len(results['cases']) == 1
        brief = results['cases'][0]
        assert brief['spec']['seed'] == seed and brief['complete'] == item['complete']
        raw = gzip.decompress((run / brief['archive']).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == brief['raw_sha256']
        assert sha(run / brief['archive']) == brief['archive_sha256']
        case = json.loads(raw)
        assert len(ledger['records']) == ledger['calls'] <= 198
        assert max(Decimal(ledger['spent_usd']), Decimal(ledger.get('reported_cost_sum_usd', '0'))) + Decimal(ledger['held_usd']) <= 10
        assert all(stamp(record['reserved_at_utc']) >= release['unix'] for record in ledger['records'])
        if stop:
            assert all(stamp(record['reserved_at_utc']) <= stop['observed_at_unix'] for record in ledger['records'])
        settled_later = sum(record['status'] == 'settled' and stop is not None and
            stamp(record['finished_at_utc']) > stop['observed_at_unix'] for record in ledger['records'])
        for event in ledger['retry_events']:
            first = ledger['records'][event['failed_call_id'] - 1]
            second = ledger['records'][event['retry_call_id'] - 1]
            assert first['status'] == 'failed' and first['attempt_index'] == 0 and second['attempt_index'] == 1
            assert first['wire_payload_json'] == second['wire_payload_json']
            assert first['logical_request_id'] == second['logical_request_id']
            for record in (first, second):
                diagnostic = read(run / 'transport_diagnostics' / f"call-{record['call_id']:04d}.json")
                assert diagnostic['child_reaped'] and diagnostic['category'] == 'whole_request_deadline'
                assert record['response'] is None
        rows.append({'seed': seed, 'complete': brief['complete'],
            'care_final': brief['metrics']['care'] if brief['complete'] else None,
            'care_last_observed': brief['metrics']['care'],
            'completed_turns': sum(t['complete_turn'] for t in case['turns']),
            'outward_attempts': ledger['calls'], 'logical_invocations': brief['metrics']['logical_generation_requests'],
            'settled': sum(r['status'] == 'settled' for r in ledger['records']),
            'failed': sum(r['status'] == 'failed' for r in ledger['records']),
            'retries': len(ledger['retry_events']), 'halt_reason': ledger['halt_reason'],
            'reference_usd': ledger['spent_usd'], 'held_usd': ledger['held_usd'],
            'settled_after_shared_stop': settled_later, 'post_stop_reservations': 0})
        for path in (run / 'analysis.json', run / 'accounting/ledger.json', run / brief['archive']):
            provenance[str(path)] = sha(path)
    assert [r['seed'] for r in rows] == [3, 4, 5]
    reference = sum((Decimal(row['reference_usd']) for row in rows), Decimal(0))
    held = sum((Decimal(row['held_usd']) for row in rows), Decimal(0))
    value = {'orchestration_reconciliation_passed': True,
        'orchestration_plan_sha256': sha(bundle / 'plan.json'),
        'source_sha256': sha(Path(__file__)), 'provenance_sha256': provenance,
        'Results': {'per_seed': rows, 'independent_families': 3, 'planned_families': 3,
            'completed_episodes': sum(row['complete'] for row in rows),
            'outward_attempts': sum(row['outward_attempts'] for row in rows),
            'logical_invocations': sum(row['logical_invocations'] for row in rows),
            'settled': sum(row['settled'] for row in rows), 'failed': sum(row['failed'] for row in rows),
            'reference_usd': str(reference), 'held_usd': str(held),
            'final_care_mean': None, 'final_care_sample_sd': None, 'final_care_sample_variance': None,
            'positive_controls': {'same_source_llm_care': '6/6 pass', 'same_source_llm_cycle': '6/6 pass',
                'concurrent_software_vs_serial': '3/3 exact native archives; 440 equal wire bodies',
                'endpoint_throughput_control': 'unrun; serial model competence is not throughput qualification'}},
        'cumulative_guard_usd': str(Decimal(runtime['baseline_guard_usd']) + reference + held),
        'actual_modal_charges_verified': False,
        'claim_limit': 'Partial clinical states have different horizons; final endpoints and effects are undefined. Two timeouts do not identify provider cause or a causal concurrency effect. No retry/replacement or new model call occurs in this analysis.'}
    out.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({k: value[k] for k in ('orchestration_reconciliation_passed', 'cumulative_guard_usd')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--wave', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.bundle, args.wave, args.out)
