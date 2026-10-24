"""Read-only post-run verification of the frozen Hospital main evidence.

No model, client, environment or network imports. This adds accounting and
canonical-state checks, not new experiment endpoints or inference.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def care(state):
    by_patient = {}
    for pid, patient in state['patients'].items():
        progress = state['patient_states'][pid]
        actual = {str(i) for i in progress['scheduled_steps']}
        expected = {str(i) for i in range(len(patient['pathway']))}
        by_patient[pid] = int(actual == expected and not progress['resource_failures'])
    return {'by_patient': by_patient, 'complete': sum(by_patient.values()), 'total': len(by_patient),
            'all_complete': bool(by_patient) and all(by_patient.values())}


def stats(values):
    observed = [v for v in values if v is not None]
    complete = len(observed) == len(values)
    return {'scenario_denominator': len(values), 'observed': len(observed), 'values': values,
            'mean': statistics.mean(observed) if observed and complete else None,
            'sample_sd': statistics.stdev(observed) if len(observed) > 1 and complete else None,
            'sample_variance': statistics.variance(observed) if len(observed) > 1 and complete else None,
            'range': [min(observed), max(observed)] if observed and complete else None}


def analyze(run, bundle):
    plan = read(bundle / 'plan.json')
    ledger = read(run / 'accounting/ledger.json')
    declared = plan['cases']
    checks, rows, request_hashes, mismatches = {}, [], [], []
    def check(name, condition):
        checks[name] = bool(condition)
    check('approved_plan_matches_ledger', ledger['plan_sha256'] == sha(bundle / 'plan.json')
          and ledger['authorization']['approved'] is True)
    check('bundle_files_unchanged', all(sha(bundle / name) == digest for name, digest in plan['files'].items()))
    check('native_sources_unchanged', all(sha(path) == digest for path, digest in plan['native_sources'].items()))
    source_names = [p for p in plan['files'] if p.startswith('sources/')]
    check('study_sources_unchanged', all(sha(HERE / Path(p).name) == plan['files'][p] for p in source_names))
    cases = {s['id']: read(run / (s['id'] + '.json')) for s in declared if (run / (s['id'] + '.json')).exists()}
    check('all84_declared_cases_complete', len(cases) == 84 and len(declared) == 84)
    check('all_cases_retained_without_exclusion', all(not r['excluded'] for r in cases.values()))
    records = ledger['records']
    check('ledger_count_and_call_ids', ledger['calls'] == len(records) and [r['call_id'] for r in records] == list(range(1, len(records)+1)))
    check('all_attempts_settled_http200', all(r['status'] == 'settled' and r.get('http_status') == 200 for r in records))
    check('caps_and_no_held_funds', ledger['calls'] <= 504 and Decimal(ledger['spent_usd']) <= 25 and Decimal(ledger['held_usd']) == 0)
    known_cost = sum((Decimal(str(r['known_cost_usd'])) for r in records if r.get('known_cost_usd') is not None), Decimal(0))
    check('known_cost_sum_equals_spent', known_cost == Decimal(ledger['spent_usd']))
    check('response_usage_cost_and_id_match_records', all(
        r.get('usage') == (r.get('response') or {}).get('usage')
        and r.get('response_id') == (r.get('response') or {}).get('id')
        and r.get('known_cost_usd') is not None
        and Decimal(str(r['known_cost_usd'])) == Decimal(str((r.get('response') or {}).get('usage',{}).get('cost')))
        for r in records if r['status'] == 'settled'))
    ids = [r.get('response_id') for r in records]
    check('unique_nonempty_response_ids', all(ids) and len(ids) == len(set(ids)))
    check('returned_model_and_provider', all((r.get('response') or {}).get('model') in {'deepseek/deepseek-v3.2','deepseek/deepseek-v3.2-20251201'}
          and (r.get('response') or {}).get('provider') == 'DeepInfra' for r in records))
    first_inputs = read(bundle / 'initial_inputs.json')
    frozen_roots = read(bundle / 'roots.json')
    callback_counts, observation_counts, finish_reasons = Counter(), Counter(), Counter()
    cursor = 0
    for spec in declared:
        case = cases.get(spec['id'])
        if case is None:
            continue
        m = case['metrics']
        expected_turns = frozen_roots[spec['id']]['turns']
        if (case['spec'] != spec or [t['step'] for t in case['turn_outcomes']] != expected_turns
            or [t['turn_index'] for t in case['turn_states']] != [t['turn_index'] for t in expected_turns]
            or [t['actual_generation'] for t in case['turn_states']] != [t['actual_generation'] for t in case['turn_outcomes']]):
            mismatches.append({'case':spec['id'], 'where':'scheduled_turn_sequence_or_flags'})
        actual_turns = [t for t in case['turn_outcomes'] if t['actual_generation']]
        assigned = records[cursor:cursor + len(actual_turns)]
        cursor += len(actual_turns)
        if len(assigned) != len(actual_turns):
            mismatches.append({'case':spec['id'], 'where':'ledger_slice_length'})
        if canonical_sha(case['root']) != canonical_sha(frozen_roots[spec['id']]):
            mismatches.append({'case': spec['id'], 'where': 'root'})
        for horizon in (4,8):
            points = [v for v in case['turn_states'] if v['turn_index'] == horizon-1]
            expected = care(points[0]['checkpoint']) if len(points) == 1 else None
            if expected != m[f'care_after_{horizon}_turns']:
                mismatches.append({'case': spec['id'], 'where': f'care_turn{horizon}'})
        if care(case['final']) != m['care_final']:
            mismatches.append({'case': spec['id'], 'where': 'care_final'})
        for i, (record, turn) in enumerate(zip(assigned, actual_turns)):
            payload = record['payload']
            if payload['seed'] != turn['step']['sampling_seed']:
                mismatches.append({'case': spec['id'], 'where': 'sampling_seed'})
            if turn['step']['turn_index'] == 0:
                frozen = first_inputs[spec['id']]
                if any(payload[k] != frozen[k] for k in ('messages','tools','model','seed')):
                    mismatches.append({'case': spec['id'], 'where': 'first_delivered_input'})
            request_hashes.append({'case': spec['id'], 'turn_index': turn['step']['turn_index'], 'call_id': record['call_id'],
                 'canonical_structured_payload_sha256': canonical_sha(payload),
                 'exact_message_string_utf8_sha256': [hashlib.sha256(v.get('content','').encode()).hexdigest()
                    if isinstance(v.get('content'),str) else None for v in payload['messages']]})
        for cb in case['callback_attempts']:
            callback_counts[str(cb.get('tool'))] += 1
        for event in case['observations']:
            observation_counts[str(event.get('source')) + '/' + str(event.get('tool'))] += 1
        llm_moves = [e for e in case['observations'] if e.get('source') == 'llm' and e.get('tool') == 'transfer_resources'
                     and e['before']['inventory'] != e['after']['inventory']]
        if not llm_moves and m['primary_cycle_count'] not in (0, None):
            mismatches.append({'case': spec['id'], 'where': 'cycle_without_llm_movement_requires_review'})
        row = {'case': spec['id'], **spec, 'cycles': m['primary_cycle_count'],
               'precompletion_cycles': m['cycles_by_completion_stage']['pre_completion']['recognized_cycle_count'],
               'postcompletion_cycles': m['cycles_by_completion_stage']['post_completion']['recognized_cycle_count'],
               'care4': m['care_after_4_turns']['complete'] if m['care_after_4_turns'] else None,
               'care8': m['care_after_8_turns']['complete'] if m['care_after_8_turns'] else None,
               'care_final': care(case['final'])['complete'], 'patients': len(case['final']['patients']),
               'transfer_attempts': sum(c.get('tool') == 'transfer_resources' for c in case['callback_attempts']),
               'llm_executed_transfers': len(llm_moves), 'new_credit': m['actual_new_transfer_credit'],
               'resource_failures': sum(case['final']['resource_failures'].values()),
               'native_joint_reward': case['final_native_reward']['joint_reward'],
               'native_per_agent_reward': case['final_native_reward']['per_agent'],
               'native_reward_error': case['final_native_reward']['error'],
               'actual_calls': len(actual_turns), 'scheduled_opportunities': len(case['turn_states']),
               'native_errors': case['native_episode_errors'], 'measurement_errors': m['measurement_errors'],
               'callbacks': len(case['callback_attempts']), 'diagnostic': case['diagnostic']}
        rows.append(row)
    check('all_generation_calls_mapped_to_cases', cursor == len(records))
    check('declared_generation_call_ceiling', cursor <= 504)
    check('canonical_care_roots_and_inputs_match', not mismatches)
    check('no_native_or_measurement_errors', all(not r['native_errors'] and not r['measurement_errors'] and not r['native_reward_error'] for r in rows))
    for record in records:
        for choice in (record.get('response') or {}).get('choices',[]):
            finish_reasons[str(choice.get('finish_reason'))] += 1
    groups = defaultdict(list)
    for row in rows:
        groups['/'.join(str(row[k]) for k in ('kind','exposure','policy','partner_policy'))].append(row)
    endpoint_names = ('cycles','precompletion_cycles','postcompletion_cycles','care4','care8','care_final',
                      'transfer_attempts','llm_executed_transfers','new_credit','resource_failures','native_joint_reward','actual_calls','callbacks')
    arms = {}
    for name, group in groups.items():
        lookup = {r['seed']: r for r in group}
        arms[name] = {key: stats([lookup[s][key] if s in lookup else None for s in range(6)]) for key in endpoint_names}
    return {'kind':'read-only post-run accounting and canonical-state verification',
            'analyzed_at_utc':datetime.now(timezone.utc).isoformat(), 'script_sha256':sha(Path(__file__)),
            'checks':checks, 'all_checks_passed':all(checks.values()), 'mismatches':mismatches,
            'scenario_families':6, 'all504_opportunities_generated':cursor == 504, 'completed_case_count':len(cases), 'uncompleted_cases':[s['id'] for s in declared if s['id'] not in cases],
            'ledger':{k:ledger[k] for k in ('status','calls','spent_usd','held_usd','halt_reason')},
            'known_cost_sum_usd':str(known_cost), 'response_models':dict(Counter((r.get('response') or {}).get('model') for r in records)),
            'response_providers':dict(Counter((r.get('response') or {}).get('provider') for r in records)),
            'finish_reasons':dict(finish_reasons), 'callback_tool_counts':dict(callback_counts),
            'observation_source_tool_counts':dict(observation_counts), 'per_case':rows, 'raw_arm_stats':arms,
            'request_hash_definition':'Canonical persisted credential-safe structured JSON payload and saved message-string UTF8; delivered text equality is supported where sanitization made no change. Not raw HTTP envelopes or server tokenization',
            'payload_redaction_marker_count':sum(json.dumps(r['payload']).count('[REDACTED]') for r in records),
            'request_hashes':request_hashes,
            'raw_sources':{str(p.relative_to(run)):sha(p) for p in sorted(run.rglob('*')) if p.is_file() and p.suffix in ('.json','.log')},
            'limits':'Six paired constructed families; descriptive sample variation only. Diagnostic final care includes scripted partner/focal actions. No equivalence or population-precision claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    ledger = read(args.run / 'accounting/ledger.json')
    if (not (args.run/'results.json').exists() and not (args.run/'stopped.json').exists()) or ledger['status'] == 'in_flight':
        parser.error('Run must finish or stop before persisting an analysis; do not snapshot an active run')
    result=analyze(args.run,args.bundle)
    with args.out.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2,sort_keys=True,allow_nan=False)
        handle.write('\n')
    print(json.dumps({'all_checks_passed':result['all_checks_passed'],'completed_cases':result['completed_case_count'],'ledger':result['ledger']}))


if __name__ == '__main__':
    main()
