"""Read-only reconciliation of the new qualifier, including denied proposals."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import analyze_full_workflow as original
from analyze_actual_frontier import care, score


def main(bundle, run, out):
    original.main(bundle, run, out)
    analysis = json.loads(out.read_text())
    results = json.loads((run / 'results.json').read_text())
    counts = {}
    for brief in results['cases']:
        case = json.loads(gzip.decompress((run / brief['archive']).read_bytes()))
        assert case['study_variant'] == 'current_supply_schedule_preflight_v1'
        final = case['final']['native']
        assert sum(care(final).values()) == case['metrics']['care']
        assert score(final) == case['metrics']['native_score']
        observations = iter(o for o in case['observations'] if o['tool'] == 'schedule_patient')
        denied = 0
        for checked in case['supply_checks']:
            deficit = {resource: n - checked['stock'][resource]
                       for resource, n in checked['required'].items() if checked['stock'][resource] < n}
            assert deficit == checked['deficits']
            assert checked['decision'] == ('deny' if deficit else 'delegate_native')
            for observation in observations:
                args = observation['arguments']
                if (observation['actor'] == checked['actor'] and args.get('patient_id') == checked['patient_id']
                        and args.get('step_index') == checked['step_index']):
                    break
            else:
                raise AssertionError('preflight check has no corresponding scheduling observation')
            hospital = observation['before']['agents_map'][checked['actor']]['hospital']
            stock = observation['before']['inventory'][hospital]
            assert all(stock.get(resource, 0) == n for resource, n in checked['stock'].items())
            if deficit:
                denied += 1
                assert observation['status'] == 'denied' and observation['before'] == observation['after']
                assert observation['decision_source'] == 'current_supply_schedule_preflight_v1'
        assert len(case['supply_checks']) == brief['metrics']['supply_checks']
        assert denied == brief['metrics']['denied_supply_proposals']
        counts[brief['spec']['id']] = {'seed': brief['spec']['seed'], 'kind': brief['spec']['kind'],
            'complete': brief['complete'], 'supply_checks': len(case['supply_checks']),
            'denied_supply_proposals': denied, 'executed_shortages': sum(final['resource_failures'].values())}
    plan = json.loads((bundle / 'plan.json').read_text())
    positives = None
    if plan['stage'] == 'ordinary':
        path = run.parent / plan['qualification_run'] / 'analysis.json'
        positives = json.loads(path.read_text())
        assert positives['positive_control_passed'] and positives['supply_preflight_reconciliation_passed']
        assert positives['plan_sha256'] == plan['qualification_plan_sha256']
    analysis.update(study_variant='current_supply_schedule_preflight_v1',
        supply_preflight_reconciliation_passed=True, supply_proposals=list(counts.values()),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        positive_controls_observed=({'care_passes': 6, 'cycle_passes': 6,
            'analysis_sha256': hashlib.sha256(path.read_bytes()).hexdigest()} if positives else None),
        claim_limit='Common supply architecture qualification only. A denied proposal remains an observed model error; prevented shortage alone does not demonstrate better planning, source-removal recovery or advice/retrieval effects.')
    if positives:
        analysis['positive_control_passed'] = True
    for kind in ('care', 'cycle', 'ordinary'):
        lookup = {r['seed']: r for r in counts.values() if r['kind'] == kind}
        analysis['summaries'][kind]['denied_supply_proposals'] = original.stats(
            [lookup[s]['denied_supply_proposals'] if s in lookup and lookup[s]['complete'] else None for s in range(6)], 6)
    out.write_text(json.dumps(analysis, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'supply_preflight_reconciliation_passed': True,
                      'denied_supply_proposals': sum(r['denied_supply_proposals'] for r in counts.values())}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.bundle, args.run, args.out)
