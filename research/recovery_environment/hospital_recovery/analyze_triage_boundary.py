"""Saved-state reconciliation only; no native environment or provider imports."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics

from analyze_actual_frontier import care, score


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    return {'values': values, 'n': len(values), 'mean': statistics.mean(values),
        'sample_sd': statistics.stdev(values) if len(values) > 1 else None,
        'sample_variance': statistics.variance(values) if len(values) > 1 else None}


def main(bundle, run, out):
    plan = json.loads((bundle / 'plan.json').read_text())
    inputs = json.loads((bundle / 'inputs.json').read_text())
    results = json.loads((run / 'results.json').read_text())
    assert sha(bundle / 'plan.json') == results['plan_sha256'] and results['passed']
    assert sha(bundle / 'inputs.json') == plan['inputs_sha256']
    for path, digest in plan['sources'].items():
        assert sha(Path(path)) == digest
    rows = []
    for record in results['Results']['per_seed']:
        assert sha(run / record['archive']) == record['archive_sha256']
        case = json.loads(gzip.decompress((run / record['archive']).read_bytes()))
        seed = case['seed']
        parent = inputs['triage'][seed]
        assert sha(Path(parent['parent_path'])) == parent['parent_archive_sha256']
        assert [t['turn_index'] for t in case['turns']] == list(range(12, 54))
        assert len(case['requests']) == sum(t['generations'] for t in case['turns'])
        assert case['turns'][0]['after'] == parent['prefix']
        for turn in case['turns']:
            assert turn['generations'] <= 3
            if turn['actor'] in case['source_actors']:
                assert turn['generations'] == 0 and turn['proposed_batch'] == []
        assert all(p['generation_requests'] == 0 and p['direct_transfer_denied'] and
            p['public_read_write_denied'] for p in case['closure'])
        final = case['summary']['final']['native']
        measured = sum(care(final).values())
        assert measured == record['care'] == case['summary']['care']
        assert score(final) == record['native_score'] == case['summary']['score']
        assert sum(final['resource_failures'].values()) == 0
        assert all(check['decision'] == 'delegate_native' and not check['deficits'] for check in case['supply_checks'])
        rows.append({'seed': seed, 'assignment': record['assignment'], 'care': measured,
            'native_score': score(final), 'generations': len(case['requests']),
            'source_checkpoint_complete': parent['last_turn_complete'],
            'archive_sha256': record['archive_sha256']})
    negative = json.loads(gzip.decompress((run / 'surgery-s1-negative.json.gz').read_bytes()))
    final = negative['summary']['final']['native']
    assert sum(care(final).values()) == 7 and sum(final['resource_failures'].values()) == 0
    assert score(final) == negative['summary']['score']
    groups = {name: [r for r in rows if r['assignment'] == name] for name in ('balanced', 'all_SM', 'noop')}
    assert all([r['seed'] for r in group] == list(range(6)) for group in groups.values())
    value = {'reconciliation_passed': True, 'plan_sha256': sha(bundle / 'plan.json'),
        'source_sha256': sha(Path(__file__)), 'Results': {'per_seed': rows,
            'independent_families': 6, 'sample_limit': 'same six actual states reused across19scripted cells; seed5state follows an incomplete turn',
            'summary': {name: {key: stats([r[key] for r in group]) for key in ('care', 'native_score', 'generations')} for name, group in groups.items()},
            'paired_all_SM_minus_balanced_care': stats([a['care']-b['care'] for a,b in zip(groups['all_SM'], groups['balanced'])]),
            'paired_all_SM_minus_balanced_score': stats([a['native_score']-b['native_score'] for a,b in zip(groups['all_SM'], groups['balanced'])]),
            'surgery_seed1_negative_care': 7, 'negative_n': 1, 'negative_sample_sd': None,
            'positive_control_passed': True, 'LLM_positive_control': 'unrun'},
        'new_paid_spend_usd': '0', 'model_calls': 0,
        'claim_limit': 'Candidate source-excluded software care feasible, including all-SM counterexample. Does not qualify ordinary LLM care, a completed seed5prefix, inherited-plan effects, repair or a new paid study.'}
    out.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'reconciliation_passed': True, 'scripted_cells': 19, 'model_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.bundle, args.run, args.out)
