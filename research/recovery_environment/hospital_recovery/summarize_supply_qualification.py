"""Fixed-six descriptive lineage for the new common-supply qualifier only."""
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
BASE = HERE / '20261025'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values, *, planned):
    defined = [v for v in values if v is not None]
    complete = len(defined) == planned
    return {'values': values, 'observed_n': len(defined), 'planned_denominator': planned,
            'mean': statistics.mean(defined) if complete and defined else None,
            'sample_sd': statistics.stdev(defined) if complete and len(defined) > 1 else None,
            'sample_variance': statistics.variance(defined) if complete and len(defined) > 1 else None}


def main():
    control = BASE / 'full_workflow_live_controls_supply_001'
    positive = load(control / 'analysis.json')
    assert positive['positive_control_passed'] and positive['supply_preflight_reconciliation_passed']
    prior = Decimal(load(control / 'preflight.json')['prior']['guard_usd'])
    ledger_paths = [control / 'accounting/ledger.json']
    rows, provenance = [], {str(control / 'analysis.json'): sha(control / 'analysis.json')}
    for seed in range(6):
        run = BASE / f'full_workflow_live_ordinary_supply_s{seed}_001'
        row = {'seed': seed, 'status': 'unstarted', 'complete': False, 'passed': None,
               'care_final': None, 'care_last_observed': None, 'shortages_final': None,
               'denied_supply_proposals_final': None, 'native_score_final': None,
               'credit_final': None, 'outward_attempts': None}
        ledger = run / 'accounting/ledger.json'
        if ledger.exists():
            ledger_paths.append(ledger)
            row.update(status='endpoint_not_finalized', outward_attempts=load(ledger)['calls'])
        analysis_path = run / 'analysis.json'
        if analysis_path.exists():
            analysis = load(analysis_path)
            assert analysis['supply_preflight_reconciliation_passed']
            brief = load(run / 'results.json')['cases'][0]
            archive = run / brief['archive']
            assert sha(archive) == brief['archive_sha256']
            raw = gzip.decompress(archive.read_bytes())
            assert hashlib.sha256(raw).hexdigest() == brief['raw_sha256']
            trace = json.loads(raw)
            expected_turns = [(iteration, phase, actor) for iteration in range(1, 4)
                              for phase in ('planning', 'execution') for actor in trace['initial']['order']]
            actual_turns = [(t['iteration'], t['phase'], t['actor']) for t in trace['turns']]
            assert actual_turns == expected_turns[:len(actual_turns)]
            assert all(t['logical_generation_requests'] <= 3 for t in trace['turns'])
            if trace['complete']:
                assert len(actual_turns) == 54 and all(t['complete_turn'] for t in trace['turns'])
            case, counts = analysis['cases'][0], analysis['supply_proposals'][0]
            assert case['seed'] == seed and case['kind'] == 'ordinary'
            final = case['complete']
            row.update(status='complete' if final else 'partial', complete=final,
                passed=case['passed'] if final else None, care_final=case['care_final'],
                care_last_observed=case['care_last_observed'],
                shortages_final=case['resource_failures'] if final else None,
                denied_supply_proposals_final=counts['denied_supply_proposals'] if final else None,
                native_score_final=case['native_score'] if final else None,
                credit_final=case['credit'] if final else None)
            provenance[str(analysis_path)] = sha(analysis_path)
        rows.append(row)
    total = prior
    for path in ledger_paths:
        ledger = load(path)
        total += max(Decimal(ledger['spent_usd']), Decimal(ledger.get('reported_cost_sum_usd', '0'))) + Decimal(ledger['held_usd'])
        provenance[str(path)] = sha(path)
    metrics = ('care_final', 'shortages_final', 'denied_supply_proposals_final', 'native_score_final', 'credit_final')
    result = {'kind': 'common_supply_fixed_six_lineage',
        'Results': {'independent_unit': 'six fixed scenario families; old cohort and repeated controls not pooled',
            'per_seed': rows, 'complete': sum(r['complete'] for r in rows),
            'planned_families': 6, 'ordinary_gate_passed': all(r['complete'] and r['passed'] for r in rows),
            'planned_six': {key: stats([r[key] for r in rows], planned=6) for key in metrics},
            'complete_only': {key: stats([r[key] for r in rows if r['complete']],
                                       planned=sum(r['complete'] for r in rows)) for key in metrics},
            'paired_final_care_minus_instructed': stats(
                [r['care_final'] - 8 if r['complete'] else None for r in rows], planned=6),
            'positive_control': {'care_passes': 6, 'cycle_passes': 6, 'care_each': 8,
                'cycle_credit_each': 30, 'supply_denials_each': 0, 'shortages_each': 0,
                'sample_sd': 0, 'sample_variance': 0}},
        'cumulative_reference_guard_usd': str(total), 'actual_modal_charges_verified': False,
        'provenance_sha256': provenance, 'source_sha256': sha(Path(__file__)),
        'scope': 'New qualification only; unfinished endpoints are missing, not failures or zero care. A ledger alone is not proof of a live process. Old failed study remains unchanged. No inherited-plan, recovery or model retrieval effect follows.'}
    out = BASE / 'supply_ordinary_lineage_001'
    out.mkdir(exist_ok=True)
    (out / 'analysis.json').write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'complete': result['Results']['complete'], 'planned': 6,
        'ordinary_gate_passed': result['Results']['ordinary_gate_passed'],
        'cumulative_reference_guard_usd': str(total)}))


if __name__ == '__main__':
    main()
