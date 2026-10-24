"""One-shot, 18-attempt offer presentation diagnostic; no game/partner execution.

prepare and report are offline. Only run --live can make inference requests.
The actual initiator validator is extracted from source, before its invitation call.
Neither the production validator nor the starter is imported or modified.
"""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'live_runs/20261024T111809Z'
MODEL = 'deepseek-ai/DeepSeek-V4.1-Flash'
ORDER_SEED = 2026102401
LIMITS = dict(attempts=18, input_tokens=200_000, output_tokens=4608,
              reference_usd=1.0, wall_seconds=600, call_timeout_seconds=30,
              concurrency=1, retries=0)
RATES = dict(input_usd_per_million=0.30, output_usd_per_million=1.20)
B_TASK = (
    'An optional private text channel is offered and pending your decision. '
    'It is inactive only because acceptance has not happened yet. '
    'Accepting and selecting a valid other agent sends that agent an invitation; '
    'activation requires the selected partner to accept too. '
    'The channel allows private messages with that partner without changing actions, '
    'rewards, zap range or immunity. Refusing has no penalty. '
    'Return JSON {"accept":true,"partner":OTHER_AGENT_ID} or {"accept":false}.')
B_STATUS = dict(status='offered_pending_your_decision', active=False, partner=None,
                inactive_reason='acceptance_has_not_happened_yet',
                acceptance_sends_invitation=True, activation_requires_partner_acceptance=True)
C_SUFFIX = (' Control-only instruction for an interface-acceptance test: '
            'return exactly {"accept":true,"partner":%d}. '
            'Select agent %d, the designated valid other agent. Return no explanation.')


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def source_function(path, name):
    return next(n for n in ast.parse(Path(path).read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == name)


def validator_namespace():
    """Execute the actual JSON parser and initiator guard, never the invitation.

    Fail closed if the inspected source structure changes. Tests compare this slice
    against the complete production consent function with an offline call sentinel.
    """
    strict = source_function(HERE / 'harness.py', 'strict_object')
    consent = source_function(HERE / 'run_study.py', 'consent')
    guarded = next(n for n in consent.body if isinstance(n, ast.Try)).body
    assert len(guarded) == 6 and isinstance(guarded[2], ast.If)
    assert ast.unparse(guarded[3].value.func) == 'invoke'
    assert ast.unparse(guarded[3].targets[0]) == 'second'
    fn = ast.parse('def validate(first, initiator):\n    pass\n').body[0]
    fn.body = copy.deepcopy(guarded[:3]) + [ast.Return(value=ast.Name(id='answer', ctx=ast.Load()))]
    module = ast.fix_missing_locations(ast.Module(body=[strict, fn], type_ignores=[]))
    namespace = {'json': json}
    exec(compile(module, str(HERE / 'run_study.py') + ':initiator-guard', 'exec'), namespace)
    return namespace


def parse_decision(raw, complete, initiator, designated):
    namespace = validator_namespace()
    result = dict(parsed=None, decision='invalid', partner=None, partner_valid=None,
                  complete=complete, validator_acceptance=False, control_pass=False, parse_error=None)
    try:
        answer = namespace['strict_object'](raw)
        result['parsed'] = answer
        partner = answer.get('partner')
        result['partner'] = partner
        if partner is not None or answer.get('accept') is True:
            result['partner_valid'] = type(partner) is int and partner in set(range(4)) - {initiator}
        try:
            namespace['validate']({'text': raw, 'complete': complete}, initiator)
            result.update(decision='accept', validator_acceptance=True,
                          control_pass=partner == designated)
        except (ValueError, TypeError) as exc:
            # Production groups refusal with invalid acceptance. Distinguish an
            # explicit complete boolean refusal for descriptive reporting only.
            if complete and answer.get('accept') is False:
                result['decision'] = 'refuse'
            else:
                result['parse_error'] = str(exc)
    except (ValueError, TypeError) as exc:
        result['parse_error'] = str(exc)
    return result


def construct(original, condition, designated):
    body = copy.deepcopy(original)
    if condition == 'A':
        return body
    data = json.loads(body['messages'][1]['content'])
    if condition == 'B':
        data['private_channel'] = copy.deepcopy(B_STATUS)
        data['task'] = B_TASK
    elif condition == 'C':
        data['task'] += C_SUFFIX % (designated, designated)
    else:
        raise ValueError('Unknown condition')
    body['messages'][1]['content'] = json.dumps(data, ensure_ascii=False)
    return body


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=False)
    audit_path = SOURCE / 'analysis/offer_audit.json'
    audit = read(audit_path)
    cases, requests = [], []
    assert [c['seed'] for c in audit['cases']] == list(range(6))
    for case in audit['cases']:
        path = SOURCE / 'calls' / (case['call_id'] + '.json')
        assert sha(path) == case['call_sha256']
        original = read(path)
        aid = original['agent']
        designated = (aid + 1) % 4
        cases.append(dict(seed=case['seed'], initiator=aid, designated_partner=designated,
                          source_call=str(path.relative_to(ROOT)), source_sha256=sha(path)))
        for condition in 'ABC':
            name = f"requests/seed-{case['seed']}-{condition}.json"
            body = construct(original['request'], condition, designated)
            assert body['model'] == MODEL and body['max_tokens'] == 256
            save(directory / name, body)
            requests.append(dict(seed=case['seed'], condition=condition, request=name,
                                 sha256=sha(directory / name)))
    rng = random.Random(ORDER_SEED)
    permutations = list(itertools.permutations('ABC'))
    rng.shuffle(permutations)
    schedule = []
    for block in range(3):
        seeds = list(range(6))
        rng.shuffle(seeds)
        for seed in seeds:
            condition = permutations[seed][block]
            request = next(r for r in requests if r['seed'] == seed and r['condition'] == condition)
            schedule.append(dict(order=len(schedule) + 1, block=block + 1, **request))
    sources = [Path(__file__), HERE / 'test_offer_diagnostic.py', HERE / 'run_study.py',
               HERE / 'harness.py', ROOT / 'research/communication_limit/modal_endpoint.py',
               ROOT / 'AGENTS.md', ROOT / 'RESEARCH.md', ROOT / 'ARCHITECTURE.md',
               ROOT / 'RELATED_WORK.md', audit_path, SOURCE / 'formation_endpoint_preflight.json']
    hashes = {}
    for path in sources:
        relative = str(path.relative_to(ROOT))
        target = directory / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        hashes[relative] = sha(path)
    plan = dict(created_at=now(), model=MODEL, limits=LIMITS, reference_rates=RATES,
                endpoint_base_url=read(SOURCE/'formation_endpoint_preflight.json')['endpoint_base_url'],
                order_seed=ORDER_SEED, order_seed_is_not_generation_seed=True,
                cases=cases, schedule=schedule, source_sha256=hashes,
                original_audit=str(audit_path.relative_to(ROOT)),
                git_parent=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                B_task=B_TASK, B_status=B_STATUS, C_instruction_template=C_SUFFIX,
                no_partner_calls_no_game_steps=True)
    save(directory / 'plan.json', plan)
    print(json.dumps({'prepared': str(directory.relative_to(ROOT)), 'plan_sha256': sha(directory / 'plan.json'),
                      'schedule': [(s['seed'], s['condition']) for s in schedule]}))


def input_bound(body):
    # Deliberately conservative UTF-8 byte reservation plus message/protocol overhead.
    return sum(len(m['content'].encode()) + 256 for m in body['messages']) + 256


def reference_cost(inputs, outputs):
    return (inputs * RATES['input_usd_per_million'] + outputs * RATES['output_usd_per_million']) / 1_000_000


def run(directory):
    plan = read(directory / 'plan.json')
    assert plan['limits'] == LIMITS and len(plan['schedule']) == 18
    for relative, expected in plan['source_sha256'].items():
        assert sha(ROOT / relative) == expected, 'Source changed since freeze: ' + relative
    for case in plan['cases']:
        assert sha(ROOT / case['source_call']) == case['source_sha256']
    for entry in plan['schedule']:
        assert sha(directory / entry['request']) == entry['sha256']
    offline = read(directory / 'offline_validation.json')
    assert offline['passed'] and offline['inference_calls'] == 0
    assert offline['plan_sha256'] == sha(directory/'plan.json')
    # Exclusive durable launch marker prevents a second invocation or resumed batch.
    with (directory / 'execution.json').open('x') as handle:
        json.dump(dict(started_at=now(), plan_sha256=sha(directory / 'plan.json'),
                       protocol_sha256=sha(ROOT / 'RECOVERY_PROTOCOL.md'),
                       git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                       no_retry_no_resume=True), handle, indent=2)
    shutil.copyfile(ROOT / 'RECOVERY_PROTOCOL.md', directory / 'protocol_before_inference.md')
    sys.path.insert(0, str(ROOT / 'research/communication_limit'))
    from dotenv import dotenv_values
    import httpx2 as httpx
    from modal_endpoint import EndpointConfig, probe
    values = dict(dotenv_values(ROOT / 'compute.env'))
    values.update(os.environ)
    config = EndpointConfig.from_values(values)
    assert config.model == MODEL, 'No model substitution permitted'
    assert config.base_url == plan['endpoint_base_url'], 'Must use the existing endpoint'
    totals = dict(attempts=0, http_successes=0, failed_attempts=0,
                  reported_input_tokens=0, reported_output_tokens=0,
                  accounted_input_tokens=0, accounted_output_tokens=0,
                  usage_reported_calls=0, reported_cost_usd=0.0, cost_reported_calls=0,
                  verified_charges_usd=None, reference_cost_is_not_a_verified_charge=True)
    started, utc_started = time.monotonic(), time.time()
    stop_reason = None
    # Explicit transport retries=0; one sequential POST per scheduled entry.
    with httpx.Client(timeout=LIMITS['call_timeout_seconds'], follow_redirects=False,
                      transport=httpx.HTTPTransport(retries=0)) as transport:
        preflight = probe(config, transport)
        save(directory / 'endpoint_preflight.json', preflight)
        if not preflight.get('configured_model_listed'):
            raise RuntimeError('Frozen model not listed; no inference dispatched')
        for entry in plan['schedule']:
            body = read(directory / entry['request'])
            bound, cap = input_bound(body), body['max_tokens']
            pi, po = totals['accounted_input_tokens'] + bound, totals['accounted_output_tokens'] + cap
            if (totals['attempts'] >= 18 or pi > LIMITS['input_tokens'] or po > LIMITS['output_tokens']
                or reference_cost(pi, po) > LIMITS['reference_usd']
                or max(time.monotonic()-started, time.time()-utc_started) >= LIMITS['wall_seconds']):
                stop_reason = 'Predeclared spending/time gate closed'
                break
            case = plan['cases'][entry['seed']]
            event = dict(**entry, initiator=case['initiator'], designated_partner=case['designated_partner'],
                         started_at=now(), status='dispatch_pending', request_body=body,
                         input_reservation=bound, output_reservation=cap)
            path = directory / 'calls' / f"{entry['order']:02d}-seed-{entry['seed']}-{entry['condition']}.json"
            totals['attempts'] += 1
            save(path, event)  # Prepared before POST; ambiguous interrupted requests remain attempts.
            save(directory / 'usage.json', totals)
            tick = time.monotonic()
            usage = {}
            try:
                response = transport.post(config.base_url + '/chat/completions', json=body, headers=config.headers)
                event['http_status'] = response.status_code
                event['raw_http_body'] = response.text
                response_body = response.json()
                event['response'] = response_body
                usage = response_body.get('usage', {})
                if not isinstance(usage, dict):
                    usage = {}
                if response.status_code != 200 or response_body.get('error'):
                    raise RuntimeError('Endpoint error; raw response preserved')
                if response_body.get('model') != MODEL:
                    stop_reason = 'Returned model mismatch; no substitution or additional dispatch'
                    raise RuntimeError(stop_reason)
                choice = response_body['choices'][0]
                raw = choice['message']['content']
                if not isinstance(raw, str):
                    raise ValueError('Missing text response')
                event.update(raw_response=raw, finish_reason=choice.get('finish_reason'))
                event['outcome'] = parse_decision(raw, choice.get('finish_reason') == 'stop',
                                                 case['initiator'], case['designated_partner'])
                event['status'] = 'success'
                totals['http_successes'] += 1
            except Exception as exc:
                # Avoid saving exception messages that could contain credentials.
                event.update(status='failed', failure_type=type(exc).__name__)
                totals['failed_attempts'] += 1
            finally:
                counts = [usage.get(k) for k in ('prompt_tokens', 'completion_tokens')]
                valid = all(type(v) is int and v >= 0 for v in counts)
                if valid:
                    totals['usage_reported_calls'] += 1
                    totals['reported_input_tokens'] += counts[0]
                    totals['reported_output_tokens'] += counts[1]
                    totals['accounted_input_tokens'] += counts[0]
                    totals['accounted_output_tokens'] += counts[1]
                    if counts[0] > bound or counts[1] > cap:
                        stop_reason = 'Usage exceeded reservation; stop remaining dispatch'
                else:
                    totals['accounted_input_tokens'] += bound
                    totals['accounted_output_tokens'] += cap
                cost = usage.get('cost')
                if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
                    totals['reported_cost_usd'] += cost
                    totals['cost_reported_calls'] += 1
                event.update(usage=usage, usage_complete=valid, finished_at=now(), seconds=time.monotonic()-tick)
                totals['reference_cost_usd'] = reference_cost(totals['accounted_input_tokens'], totals['accounted_output_tokens'])
                save(path, event)
                save(directory / 'usage.json', totals)
                print(json.dumps({k:event[k] for k in ('order', 'seed', 'condition', 'status')} |
                                 {'outcome': event.get('outcome')}), flush=True)
            if stop_reason:
                break
    save(directory / 'completion.json', dict(finished_at=now(), stop_reason=stop_reason,
         attempts=totals['attempts'], scheduled=18, partner_calls=0, game_steps=0,
         formation_episodes=0, recovery_continuations=0, retries=0))


def stats(values):
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                sample_sd=statistics.stdev(values) if len(values)>1 else None,
                sample_variance=statistics.variance(values) if len(values)>1 else None)


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    center = (k/n + z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt((k/n)*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [0.0 if k==0 else max(0, center-half), 1.0 if k==n else min(1, center+half)]


def report(directory):
    plan, usage = read(directory / 'plan.json'), read(directory / 'usage.json')
    events = {e['order']:e for e in (read(p) for p in sorted((directory/'calls').glob('*.json')))}
    rows, by_condition = [], {}
    for entry in plan['schedule']:
        event = events.get(entry['order'], {})
        outcome = event.get('outcome', {})
        rows.append(dict(seed=entry['seed'], condition=entry['condition'], order=entry['order'],
            raw_response=event.get('raw_response'), parsed=outcome.get('parsed'),
            decision=outcome.get('decision', 'unresolved'), partner=outcome.get('partner'),
            partner_valid=outcome.get('partner_valid'), complete=outcome.get('complete', False),
            status=event.get('status','not_attempted'), failure=event.get('failure_type') or outcome.get('parse_error'),
            control_pass=event.get('status')=='success' and outcome.get('control_pass',False),
            call_file=next((str(p.relative_to(directory)) for p in (directory/'calls').glob(f"{entry['order']:02d}-*.json")), None)))
    for condition in 'ABC':
        subset = [r for r in rows if r['condition']==condition]
        valid = [r for r in subset if r['status']=='success' and r['decision'] in ('accept','refuse')]
        accepts = sum(r['decision']=='accept' for r in valid)
        passes = sum(r['control_pass'] for r in subset)
        by_condition[condition] = dict(acceptances=accepts, scheduled_denominator=6,
            attempted=sum(r['status']!='not_attempted' for r in subset), valid_decisions=len(valid),
            refusals=sum(r['decision']=='refuse' for r in valid), unresolved=6-len(valid),
            acceptance_fraction_bounds=[accepts/6, (accepts+6-len(valid))/6],
            complete_case_binary_stats=stats([int(r['decision']=='accept') for r in valid]),
            illustrative_wilson_95=wilson(accepts,len(valid)), control_passes=passes)
    pairs = []
    for seed in range(6):
        a,b = [next(r for r in rows if r['seed']==seed and r['condition']==c) for c in 'AB']
        valid = all(r['status']=='success' and r['decision'] in ('accept','refuse') for r in (a,b))
        pairs.append(dict(seed=seed, A=a['decision'], B=b['decision'],
                          B_minus_A=int(b['decision']=='accept')-int(a['decision']=='accept') if valid else None))
    paired_stats = stats([p['B_minus_A'] for p in pairs if p['B_minus_A'] is not None])
    pair_counts = {label:sum(p['A']==a and p['B']==b for p in pairs)
                   for label,a,b in [('both_accept','accept','accept'),('both_refuse','refuse','refuse'),
                                     ('A_only_accept','accept','refuse'),('B_only_accept','refuse','accept')]}
    pair_counts['unresolved'] = sum(p['B_minus_A'] is None for p in pairs)
    result = dict(rows=rows, conditions=by_condition, paired=pairs, paired_difference=paired_stats,
                  paired_counts=pair_counts,
                  usage=usage, provenance=dict(plan_sha256=sha(directory/'plan.json'),
                  source_audit=plan['original_audit'], cases=plan['cases']),
                  independent_new_episodes=0, reused_contexts=6)
    save(directory/'results.json', result)
    lines = ['# Private-channel offer diagnostic', '', '## Results:', '',
        'Six reused decision contexts from prefix seeds 0–5; one stochastic draw per condition/context. '
        'No new independent episodes. A is an exact saved-request replay; B is a presentation-package intervention; '
        'C is an instructed interface-acceptance positive control.', '',
        '| Condition | Acceptance / scheduled | Valid refusals | Unresolved | Acceptance mean; sample SD; variance (valid cases) |',
        '| --- | ---: | ---: | ---: | --- |']
    for c,s in by_condition.items():
        v=s['complete_case_binary_stats']
        lines.append(f"| {c} | {s['acceptances']}/6 | {s['refusals']} | {s['unresolved']} | {v['mean']}; {v['sample_sd']}; {v['sample_variance']} |")
    lines += ['', f"**Positive control C: {by_condition['C']['control_passes']}/6 scheduled attempts passed** the actual initiator consent validator and designated-partner criterion. "
        'Failures are retained. This checks instructed acceptance-output capability only; no partner was called.', '',
        '| Seed | A | B | B − A (acceptance) |', '| --- | --- | --- | ---: |']
    for p in pairs:
        lines.append(f"| {p['seed']} | {p['A']} | {p['B']} | {p['B_minus_A']} |")
    lines += ['', f"Paired counts: `{json.dumps(pair_counts)}`.", '',
        f"Paired descriptive statistics: `{json.dumps(paired_stats)}`. "
        'Zero empirical variance is not proof of a stable zero effect. Each changed binary result moves a six-case rate by 16.7 percentage points. '
        'There are no within-context replicates to estimate sampling variability at a fixed situation.', '']
    for c in 'AB':
        s=by_condition[c]
        lines.append(f"{c}: illustrative 95% Wilson range among valid decisions `{s['illustrative_wilson_95']}`; "
            f"unresolved-case acceptance bounds among six scheduled contexts `{s['acceptance_fraction_bounds']}`. "
            'Wilson ranges assume exchangeable Bernoulli trials and are sensitivity descriptions, not population inference from six selected, reused contexts.')
    lines += ['', '### Every case and condition', '',
        '| Seed | Condition (dispatch) | Raw response | Parsed decision | Partner (valid) | Complete | Status / failure |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for r in sorted(rows,key=lambda r:(r['seed'],r['condition'])):
        raw=json.dumps(r['raw_response'],ensure_ascii=False).replace('|','&#124;').replace('`','&#96;')
        parsed=json.dumps(r['parsed'],ensure_ascii=False).replace('|','&#124;').replace('`','&#96;')
        lines.append(f"| {r['seed']} | {r['condition']} ({r['order']}) | `{raw}` | {r['decision']}: `{parsed}` | {r['partner']} ({r['partner_valid']}) | {r['complete']} | [{r['status']}]({r['call_file']}) / {r['failure']} |")
    lines += ['', 'A missing partner on a valid refusal is not applicable (null validity), not an invalid-partner acceptance.', '',
        '### Accounting and provenance', '', f"`{json.dumps(usage,sort_keys=True)}`", '',
        'Reference rates: $0.30/million input and $1.20/million output, inherited assumptions. '
        'Missing usage is conservatively accounted at the full request reservation. Token-cost references are not verified endpoint charges; '
        'provider-reported cost, if present, is also kept separate from independently verified billing.', '',
        '[Frozen plan, source hashes, source-case links, designated partners and dispatch order](plan.json); '
        '[exact pre-inference protocol](protocol_before_inference.md); [offline checks](offline_validation.json); '
        '[execution commit](execution.json); [completion](completion.json); [full machine-readable results](results.json).', '',
        '### Interpretation and next decision', '',
        'Acceptance does not establish voluntary partner consent, channel delivery, coordination, targeting or recovery. '
        'B versus A concerns the entire presentation package, not one word/field. '
        'No motivations were requested or measured. This diagnostic changes neither production consent nor starter mechanics. '
        'The selected Cleanup recovery question remains unchanged and R0–R5 remain unrun.', '']
    if by_condition['A']['refusals']==6 and by_condition['B']['refusals']==6:
        lines += ['Both neutral conditions remained refused: clarification did not establish improved uptake in these contexts. '
            'Do not infer ethics, interface misunderstanding or low strategic value, and do not restore attack coaching. '
            'Recommended next decision: keep recovery inference paused and have the user decide whether this model/task remains a viable voluntary-formation setting. '
            'Any further diagnostic or alternative setting needs a separately specified, authorized plan.', '']
    else:
        lines += ['Recommended next decision: review the complete paired outcomes and control reliability before deciding whether voluntary formation is a viable prerequisite. '
            'This result does not authorize formation or recovery runs; any next inference requires a separate plan.', '']
    (directory/'results.md').write_text('\n'.join(lines))
    print(json.dumps({'conditions':by_condition,'paired':paired_stats,'usage':usage},indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','run','report'])
    parser.add_argument('directory',type=Path)
    parser.add_argument('--live',action='store_true')
    args=parser.parse_args()
    if args.mode=='run' and not args.live:
        parser.error('run requires --live; prepare/report never infer')
    {'prepare':prepare,'run':run,'report':report}[args.mode](args.directory.resolve())
