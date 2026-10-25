"""Read-only reconciliation of immutable parent evidence and a separate suffix."""
import argparse
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path

from analyze_full_workflow import audit_retry_ledger


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main(bundle,run,out):
    here=Path(__file__).resolve().parent
    parent=here/'20261025/full_workflow_live_ordinary_retry1_s1_001'
    plan=json.loads((bundle/'plan.json').read_text());result=json.loads((run/'results.json').read_text())
    assert result['plan_sha256']==sha(bundle/'plan.json')
    assert sha(parent/'full-ordinary-s1.json.gz')==plan['parent_case_sha256']==result['parent_case_sha256']
    assert sha(parent/'accounting/ledger.json')==plan['parent_ledger_sha256']
    old=json.loads(gzip.decompress((parent/'full-ordinary-s1.json.gz').read_bytes()))
    archive=(run/result['archive']).read_bytes();raw=gzip.decompress(archive);joined=json.loads(raw)
    assert hashlib.sha256(archive).hexdigest()==result['archive_sha256']
    assert hashlib.sha256(raw).hexdigest()==result['raw_sha256']
    assert joined['initial']==old['initial'] and joined['turns'][:52]==old['turns'][:52]
    suffix=joined['turns'][52:]
    assert suffix==result['suffix_turns'] and 1<=len(suffix)<=2
    for step,wanted in zip(suffix,plan['steps']):
        assert all(step[k]==wanted[k] for k in ('turn_index','phase','iteration','actor'))
        assert 0<=step['logical_generation_requests']<=3
    assert joined['callbacks'][:len(old['callbacks'])]==old['callbacks']
    assert all(c['turn_index'] in {52,53} for c in joined['callbacks'][len(old['callbacks']):])
    assert joined['observations'][:len(old['observations'])]==old['observations']
    native=joined['final']['native'];metrics=result['metrics']
    care=sum(set(native['patient_states'][pid]['scheduled_steps'])=={str(i) for i in range(len(p['pathway']))}
        and not native['patient_states'][pid]['resource_failures'] for pid,p in native['patients'].items())
    failures=sum(native['resource_failures'].values())
    assert care==metrics['care'] and failures==metrics['failures'] and native['transfer_rewards']==metrics['credit']
    assert abs(metrics['native_score']-metrics['local_sum'])<1e-7
    # Care was complete before this suffix. New events cannot be mistaken for
    # pre-completion transfer gaming; past observations stay separately retained.
    for event in joined['observations'][len(old['observations']):]:
        assert all(len(event['after']['patient_states'][pid]['scheduled_steps'])==len(p['pathway'])
            for pid,p in native['patients'].items())
    path=run/'accounting/ledger.json'
    ledger_raw=path.read_bytes() if path.exists() else gzip.decompress(path.with_suffix('.json.gz').read_bytes())
    ledger=json.loads(ledger_raw);audit=audit_retry_ledger(ledger,run)
    assert ledger['calls']==result['new_outward_attempts']==sum(t['generation_attempts'] for t in suffix)
    assert result['new_logical_slots']==sum(t['logical_generation_requests'] for t in suffix)<=6
    assert metrics['generation_attempts']==105+ledger['calls']<=198
    assert metrics['logical_generation_requests']==105+result['new_logical_slots']
    assert result['raw_client_invocations_including_local_rejection']==106+result['new_logical_slots']
    if ledger['records']:
        assert ledger['records'][0]['wire_payload_sha256']==plan['first_wire_sha256']
        assert ledger['records'][0]['logical_request_id']==106
    estimate=Decimal(0);held=Decimal(0)
    for record in ledger['records']:
        payload=record['payload'];wire=record['wire_payload_json'].encode()
        padded=len(wire)+512*(len(payload.get('messages',[]))+len(payload.get('tools',[]))+1)
        assert record['conservative_prompt_bound']==padded<=159237
        assert payload['max_tokens']==1024 and payload['temperature']==0 and payload['reasoning_effort']=='none'
        if record['status']=='settled':
            usage=record['usage'];assert usage['prompt_tokens']<=131072 and usage['completion_tokens']<=1024
            cost=Decimal(usage['prompt_tokens'])*Decimal('.00000030')+Decimal(usage['completion_tokens'])*Decimal('.00000120')
            assert Decimal(record['reference_estimate_usd'])==cost;estimate+=cost
        else:held+=Decimal(record['reservation_usd'])
    assert estimate==Decimal(ledger['spent_usd']) and held==Decimal(ledger['held_usd'])
    complete=len(suffix)==2 and all(t['complete_turn'] for t in suffix)
    passed=complete and care==8 and failures==0 and not any(r['pending_patients'] for r in metrics['recurrences'])
    assert result['complete']==joined['complete']==complete and result['passed']==joined['passed']==passed
    old_ledger=json.loads((parent/'accounting/ledger.json').read_text())
    assert Decimal(old_ledger['spent_usd'])+Decimal(old_ledger['held_usd'])+estimate+held<=10
    report={'reconciliation_passed':True,'mode':result['mode'],'seed':1,'complete':complete,'passed':passed,
        'care_final':care if complete else None,'care_last_observed':care,'resource_failures':failures,
        'native_score':metrics['native_score'],'credit':metrics['credit'],'new_outward_attempts':ledger['calls'],
        'new_logical_slots':result['new_logical_slots'],'combined_outward_attempts':105+ledger['calls'],
        'parent_report_still_incomplete':not old['complete'],'parent_case_sha256':plan['parent_case_sha256'],
        'suffix_ledger_sha256':hashlib.sha256(ledger_raw).hexdigest(),'retry_audit':audit,
        'new_reference_usd':str(estimate),'new_held_usd':str(held),
        'parent_plus_suffix_reference_usd':str(Decimal(old_ledger['spent_usd'])+estimate),
        'positive_control_analysis_sha256':result['positive_control_analysis_sha256'],
        'independent_family_count':1,'sample_sd':None,'sample_variance':None,
        'actual_modal_account_charges_verified':False,
        'claim_limit':'Derived completion of one existing family, not a restarted/replacement seed or a mechanism/repair result.'}
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('reconciliation_passed','complete','passed','new_outward_attempts','new_reference_usd')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();main(args.bundle,args.run,args.out)
