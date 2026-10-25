"""Read-only fixed-six summary across the explicitly recorded execution correction."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent
BASE=HERE/'20261025'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def stats(values,planned=False):
    defined=[v for v in values if v is not None]
    ready=not planned or len(defined)==6
    return {'values':values,'observed_n':len(defined),'planned_denominator':6,
        'mean':statistics.mean(defined) if ready and defined else None,
        'sample_sd':statistics.stdev(defined) if ready and len(defined)>1 else None,
        'sample_variance':statistics.variance(defined) if ready and len(defined)>1 else None}


def ledger(run):
    raw=(run/'accounting/ledger.json').read_bytes()
    d=json.loads(raw)
    return d,sha(raw),max(Decimal(d['spent_usd']),Decimal(d['reported_cost_sum_usd']))+Decimal(d['held_usd'])


def main(out):
    controls=[]
    for policy,name in [('retry1','full_workflow_live_controls_retry1_001'),
                        ('financial','full_workflow_live_controls_financial_001')]:
        p=BASE/name;d=json.loads((p/'analysis.json').read_text());l,h,_=ledger(p)
        assert d['positive_control_passed'] and d['raw_ledger_sha256']==h
        controls.append({'policy':policy,'care_passes':6,'cycle_passes':6,'care_values':[8]*6,
            'cycle_credit_values':[30]*6,'sample_sd':0,'sample_variance':0,
            'analysis_sha256':sha((p/'analysis.json').read_bytes()),'calls':l['calls']})
    rows=[];sources={}
    later_guard=Decimal(0)
    for seed in range(6):
        name=('full_workflow_live_ordinary_retry1_s0_001' if seed==0 else
            'full_workflow_live_ordinary_financial_s1_suffix_001' if seed==1 else
            f'full_workflow_live_ordinary_financial_s{seed}_001')
        p=BASE/name
        row={'seed':seed,'status':'running' if p.exists() else 'unstarted','complete':False,
            'passed':None,'care_final':None,'resource_failures_final':None,'native_score_final':None,
            'care_last_observed':None,'resource_failures_last_observed':None,
            'zero_shortage_criterion_already_violated':None,
            'credit_final':None,'outward_attempts':None,'unique_logical_requests':None,
            'raw_client_invocations':None,'execution_policy':'retry1' if seed==0 else 'financial',
            'reference_usd':None,'held_usd':None,'retry_attempts':None}
        if (p/'accounting/ledger.json').exists():
            l,h,guard=ledger(p);sources[name+'/ledger']=h
            row.update(outward_attempts=l['calls'],reference_usd=l['spent_usd'],held_usd=l['held_usd'],
                retry_attempts=sum(r['attempt_index']==1 for r in l['records']))
            if seed>=2:later_guard+=guard
        if (p/'analysis.json').exists():
            result=json.loads((p/'results.json').read_text());a=json.loads((p/'analysis.json').read_text())
            assert a['reconciliation_passed']
            sources[name+'/analysis']=sha((p/'analysis.json').read_bytes())
            if seed==1:
                assert a['suffix_ledger_sha256']==h
                parent=BASE/'full_workflow_live_ordinary_retry1_s1_001'
                old,old_hash,old_guard=ledger(parent)
                assert old['calls']==105 and old['halt_reason']=='payload_or_prompt_bound'
                sources['seed1_original_partial_ledger']=old_hash
                archive=p/result['archive'];care=a['care_final'];score=a['native_score'];credit=a['credit']
                last_care=a['care_last_observed']
                complete=a['complete'];passed=a['passed'];failures=a['resource_failures']
                row.update(outward_attempts=a['combined_outward_attempts'],
                    reference_usd=a['parent_plus_suffix_reference_usd'],held_usd=str(Decimal(old['held_usd'])+Decimal(l['held_usd'])),
                    unique_logical_requests=result['metrics']['logical_generation_requests'],
                    raw_client_invocations=result['raw_client_invocations_including_local_rejection'],
                    original_partial_report_preserved=True,joined_completion=True)
                expected_archive=result['archive_sha256']
            else:
                assert a['raw_ledger_sha256']==h
                case=result['cases'][0];measured=a['cases'][0]
                assert case['spec']['seed']==measured['seed']==seed
                archive=p/case['archive'];expected_archive=case['archive_sha256']
                care=measured['care_final'];score=measured['native_score'];credit=measured['credit']
                last_care=measured['care_last_observed']
                complete=case['complete'];passed=case['passed'];failures=measured['resource_failures']
                row.update(unique_logical_requests=case['metrics']['logical_generation_requests'],
                    raw_client_invocations=case['metrics']['logical_generation_requests'])
            assert sha(archive.read_bytes())==expected_archive
            sources[name+'/archive']=expected_archive
            row.update(status='complete' if complete else 'partial',complete=complete,
                passed=passed if complete else None,care_final=care if complete else None,
                care_last_observed=last_care,resource_failures_last_observed=failures,
                zero_shortage_criterion_already_violated=failures>0,
                resource_failures_final=failures if complete else None,native_score_final=score if complete else None,
                credit_final=credit if complete else None)
        rows.append(row)
    anchor=BASE/'full_workflow_live_ordinary_financial_s2_001/preflight.json'
    initial_guard=Decimal(json.loads(anchor.read_text())['prior']['guard_usd'])
    keys=['care_final','resource_failures_final','native_score_final','credit_final']
    values={k:[r[k] for r in rows] for k in keys}
    result={'kind':'ordinary_fixed_six_execution_lineage','generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_sha256':sha(Path(__file__).read_bytes()),'provenance_sha256':sources,
        'Results':{'per_seed':rows,'planned_families':6,'complete':sum(r['complete'] for r in rows),
            'passed':sum(r['passed'] is True for r in rows),
            'families_with_observed_resource_failure':sum(r['zero_shortage_criterion_already_violated'] is True for r in rows),
            'ordinary_gate_passed':all(r['complete'] and r['passed'] for r in rows),
            'complete_only':{k:stats(v) for k,v in values.items()},
            'planned_six':{k:stats(v,True) for k,v in values.items()},
            'paired_care_minus_instructed':stats([r['care_final']-8 if r['care_final'] is not None else None for r in rows],True),
            'positive_controls':controls,'independent_unit':'six fixed families; repetitions/requests/suffix are not new independent seeds'},
        'cumulative_guard_through_ordinary_sample_usd':str(initial_guard+later_guard),
        'budget_scope':'Seed2preflight cumulative history plus fixed seeds2-5 ledgers only; excludes future unrelated stages; live all_history remains authoritative.',
        'actual_modal_account_charges_verified':False,
        'lineage_limit':'Seed0uses the old admitted policy; seed1joins an unchanged old prefix to the exact corrected suffix; seeds2-5 use the financial policy. This is descriptive, not a causal capacity-policy comparison.',
        'claim_limit':'No inherited-plan, source-exclusion, repair or LLM retrieval effect follows from baseline qualification.'}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'complete':result['Results']['complete'],'passed':result['Results']['passed'],
        'gate_passed':result['Results']['ordinary_gate_passed'],'guard_usd':str(initial_guard+later_guard)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args().out)
