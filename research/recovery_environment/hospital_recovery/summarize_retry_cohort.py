"""Read-only six-family summary; unfinished endpoints never become zeroes."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
BASE = HERE / '20261025'
CONTROL = BASE / 'full_workflow_live_controls_retry1_001'
BUNDLE = BASE / 'full_workflow_ordinary_gate_retry1_002/bundle'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values, require_six=False):
    defined = [x for x in values if x is not None]
    allowed = not require_six or len(defined) == 6
    return {'values': values, 'observed_n': len(defined), 'planned_denominator': 6,
        'mean': statistics.mean(defined) if allowed and defined else None,
        'sample_sd': statistics.stdev(defined) if allowed and len(defined)>1 else None,
        'sample_variance': statistics.variance(defined) if allowed and len(defined)>1 else None,
        'scope': 'planned-six endpoints' if require_six else 'observed complete endpoints only'}


def summarize(out):
    control = json.loads((CONTROL/'analysis.json').read_text())
    control_ledger = json.loads((CONTROL/'accounting/ledger.json').read_text())
    assert control['positive_control_passed'] and control['raw_ledger_sha256'] == sha(CONTROL/'accounting/ledger.json')
    frozen = sha(BUNDLE/'plan.json')
    rows, provenance = [], {'source': sha(Path(__file__).resolve()),
        'ordinary_plan': frozen, 'control_analysis': sha(CONTROL/'analysis.json')}
    complete_guard = (Decimal(json.loads((CONTROL/'preflight.json').read_text())['prior']['guard_usd']) +
        max(Decimal(control_ledger['spent_usd']), Decimal(control_ledger['reported_cost_sum_usd'])) +
        Decimal(control_ledger['held_usd']))
    for seed in range(6):
        run = BASE/f'full_workflow_live_ordinary_retry1_s{seed}_001'
        row = {'seed':seed,'status':'in_progress' if run.exists() else 'unstarted',
            'complete':False,'passed':None,'care_final':None,'resource_failures_final':None,
            'credit_final':None,'native_score_final':None,'outward_attempts':None,
            'logical_requests':None,'failed_attempts':None,'retry_attempts':None,
            'recovered_logical_requests':None,'held_usd':None,'reference_usd':None}
        if (run/'results.json').exists():
            result = json.loads((run/'results.json').read_text())
            analysis = json.loads((run/'analysis.json').read_text())
            ledger = json.loads((run/'accounting/ledger.json').read_text())
            assert result['plan_sha256'] == analysis['plan_sha256'] == frozen
            assert analysis['reconciliation_passed'] and analysis['raw_ledger_sha256'] == sha(run/'accounting/ledger.json')
            case, measured = result['cases'][0], analysis['cases'][0]
            assert case['spec']['seed'] == measured['seed'] == seed
            assert sha(run/case['archive']) == case['archive_sha256']
            assert ledger['calls'] <= 198 and Decimal(ledger['spent_usd']) + Decimal(ledger['held_usd']) <= 10
            row.update(status='complete' if case['complete'] else 'partial', complete=case['complete'],
                passed=case['passed'], care_last_observed=measured['care_last_observed'],
                care_final=measured['care_final'],
                resource_failures_final=measured['resource_failures'] if case['complete'] else None,
                credit_final=measured['credit'] if case['complete'] else None,
                native_score_final=measured['native_score'] if case['complete'] else None,
                outward_attempts=ledger['calls'], logical_requests=analysis['retry_audit']['logical_requests_with_outward_attempts'],
                failed_attempts=analysis['retry_audit']['failed_attempts'],
                retry_attempts=analysis['retry_audit']['outward_retry_attempts'],
                recovered_logical_requests=analysis['retry_audit']['recovered_logical_requests'],
                held_usd=ledger['held_usd'], reference_usd=ledger['spent_usd'])
            complete_guard += max(Decimal(ledger['spent_usd']), Decimal(ledger['reported_cost_sum_usd'])) + Decimal(ledger['held_usd'])
            provenance[f'seed{seed}_analysis'] = sha(run/'analysis.json')
            provenance[f'seed{seed}_ledger'] = sha(run/'accounting/ledger.json')
        rows.append(row)
    values = {key:[r[key] for r in rows] for key in ('care_final','resource_failures_final','credit_final','native_score_final')}
    paired = [r['care_final']-8 if r['care_final'] is not None else None for r in rows]
    result = {'kind':'derived_retry_enabled_ordinary_cohort_summary',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),'provenance_sha256':provenance,
        'unit':'six fixed scenario families, seeds0-5; repeats/requests are not new independent scenarios',
        'Results':{'per_seed':rows,'complete':sum(r['complete'] for r in rows),
            'passed':sum(r['passed'] is True for r in rows),'planned_denominator':6,
            'ordinary_gate_passed':all(r['complete'] and r['passed'] for r in rows),
            'planned_six':{k:stats(v,True) for k,v in values.items()},
            'complete_only':{k:stats(v) for k,v in values.items()},
            'paired_care_minus_instructed_control':stats(paired,True),
            'paired_difference_limit':'descriptive capability/ordinary comparison; different instructions and horizons, not a causal repair effect',
            'positive_control':{'passed':True,'care_passes':6,'cycle_passes':6,
                'care_values':[8]*6,'cycle_credit_values':[30]*6,'sample_sd':0,'sample_variance':0,
                'limit':'prescribed competence; software timeout positives and natural live recoveries reported separately'}},
        'guard_through_finished_cohort_cases_usd':str(complete_guard),
        'budget_limit':'excludes any still-running case from this derived snapshot; live ledger guard remains authoritative',
        'actual_modal_account_charges_verified':False,
        'claim_limit':'No exposure, source exclusion, repair or retrieval effect follows from this ordinary baseline.'}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'complete':result['Results']['complete'],'passed':result['Results']['passed'],
        'planned':6,'ordinary_gate_passed':result['Results']['ordinary_gate_passed']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    summarize(parser.parse_args().out)
