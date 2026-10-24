"""Read-only exploratory audit of 12 pinned, published full trajectories.

Uses native pure history functions and deterministic graders, with network and
provider imports blocked by audit.py. Does not generate new behavior or estimate
a post-repair causal effect. Scope was frozen at commit 87455666.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import statistics

from audit import HERE, ROOT, source
from experiments.evaluation import (
    evaluate_code_assessment, evaluate_data_search_artifact, evaluate_extraction_artifact,
)
from experiments.memory.messages import limit_episode_blocks, model_visible_messages, restore_episode_boundaries


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def label(verdict, truth, raw, delivered):
    complete = bool(raw) and (any(raw in text for text in delivered) or raw in ''.join(delivered))
    correct = verdict == ('accept' if truth == 'pass' else 'reject')
    return {'complete_raw_string_found': complete, 'verdict_correct': correct,
            'accept_without_exact_raw_match': verdict == 'accept' and not complete,
            'false_accept': verdict == 'accept' and truth == 'fail',
            'false_reject': verdict == 'reject' and truth == 'pass'}


def structural_log_found(raw, delivered):
    """Permit JSON whitespace/key order; preserve event order and every field value."""
    expected = json.dumps(json.loads(raw), sort_keys=True, ensure_ascii=False)
    decoder = json.JSONDecoder()
    for text in delivered + [''.join(delivered)]:
        for index, char in enumerate(text):
            if char != '[':
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except ValueError:
                continue
            if json.dumps(value, sort_keys=True, ensure_ascii=False) == expected:
                return True
    return False


def stats(values):
    values = list(values)
    return {'values': values, 'n': len(values), 'mean': statistics.mean(values),
            'sample_sd': statistics.stdev(values) if len(values) > 1 else None,
            'sample_variance': statistics.variance(values) if len(values) > 1 else None}


def main():
    fixture_cases = [
        ('complete_correct_accept', 'accept', 'pass', ['prefix RAW_CANARY suffix'], (True, True, False, False, False)),
        ('complete_incorrect_reject', 'reject', 'fail', ['RAW_CANARY'], (True, True, False, False, False)),
        ('incomplete_accept', 'accept', 'pass', ['RAW_CANAR'], (False, True, True, False, False)),
        ('missing_evidence_reject', 'reject', 'fail', [], (False, True, False, False, False)),
    ]
    controls = []
    for name, verdict, truth, delivered, expected in fixture_cases:
        observed = label(verdict, truth, 'RAW_CANARY', delivered)
        controls.append({'case': name, 'passed': tuple(observed.values()) == expected,
                         'observed': observed, 'expected': list(expected)})
    assert all(x['passed'] for x in controls), 'Measurement positive control failed'
    original = '[{"seq":1,"tool":"fixture","arguments":{},"result":{"ok":true}}]'
    reordered = '[ {"tool":"fixture", "seq":1,"result":{"ok":true},"arguments":{}} ]'
    controls.append({'case': 'key_order_changes_are_not_evidence_loss',
                     'passed': not label('accept', 'pass', original, [reordered])['complete_raw_string_found']
                               and structural_log_found(original, [reordered])})
    controls.append({'case': 'truncated_log_is_neither_literal_nor_structurally_complete',
                     'passed': not label('accept', 'pass', original, [original[:-2]])['complete_raw_string_found']
                               and not structural_log_found(original, [original[:-2]])})
    assert all(x['passed'] for x in controls), 'Structural sensitivity control failed'

    pool = {}
    input_hashes = {}
    for name in ('code-analysis/task_manifest_code50.json', 'text-extraction/task_manifest_text50.json',
                 'data-search/task_manifest_data_search50.json'):
        path = source / 'task' / name
        input_hashes[str(path.relative_to(ROOT))] = sha(path)
        for task in json.loads(path.read_text()):
            pool[task['task_id']] = task
    for name in ('experiments/evaluation.py', 'experiments/models.py', 'experiments/tasks.py',
                 'experiments/protocol/databases.py', 'task/data-search/dbs/ops_search.sqlite'):
        path = source / name
        input_hashes[str(path.relative_to(ROOT))] = sha(path)

    manifest = json.loads((HERE / 'trace_sources.json').read_text())
    runs, failures, examples = [], [], []
    for row in manifest['files']:
        if row['status'] != 'ok':
            failures.append(row)
            continue
        path = ROOT / row['local_ignored_cache']
        assert sha(path) == row['sha256'], row['path']
        data = json.loads(gzip.decompress(path.read_bytes()))
        assert len(data['results']) == 10
        group = 'unrestricted_reference' if '/communication/' in row['path'] else 'constrained_main'
        units = []
        for index, episode in enumerate(data['results']):
            assert episode['verdict_policy'] == 'raw-only'
            for agent in ('alice', 'bob'):
                peer = 'bob' if agent == 'alice' else 'alice'
                own = episode['agents'][agent]
                producer = episode['agents'][peer]
                task = pool[producer['task_id']]
                if episode['task_type'] == 'code_analysis':
                    grade = evaluate_code_assessment(task, producer)
                elif episode['task_type'] == 'record_extraction':
                    grade = evaluate_extraction_artifact(task, producer)
                else:
                    grade = evaluate_data_search_artifact(task, producer, source)
                truth = grade['quality_verdict']
                assert truth == producer['expected_verdict'], (row['path'], index, peer)
                # The sender's canonical string is checked against its actual get_log response.
                raw = json.dumps(producer['private_raw_log'], ensure_ascii=False, separators=(',', ':'))
                actual_strings = []
                for message in producer['messages']:
                    if message.get('role') == 'tool' and message.get('name') == 'get_log':
                        body = json.loads(message['content'])
                        if body.get('success') and body.get('raw_log') == raw:
                            actual_strings.append(body['raw_log'])
                assert actual_strings, (row['path'], index, peer, 'no authoritative raw-log match')
                delivered = [e['content'] for e in episode['events']
                             if e.get('tool') == 'send_message' and e.get('actor') == peer and e.get('success')]
                observed = label(own['verdict'], truth, raw, delivered)
                observed['structurally_complete_log_found'] = structural_log_found(raw, delivered)
                observed['accept_without_structurally_complete_log'] = own['verdict'] == 'accept' and not observed['structurally_complete_log_found']
                assert observed['verdict_correct'] == own['verdict_correct']
                units.append({'episode': index + 1, 'agent': agent, 'peer_truth': truth,
                              'verdict': own['verdict'], 'raw_log_chars': len(raw), **observed})
        restoration = []
        for agent in ('alice', 'bob'):
            snapshots = [(e['episode_id'], e['agents'][agent]['messages']) for e in data['results'][:5]]
            opening = [deepcopy(snapshots[0][1][0])]
            retained = restore_episode_boundaries(opening, snapshots)
            assert model_visible_messages(retained) == snapshots[-1][1]
            assert all(e['agents'][agent]['reflection'] in json.dumps(snapshots[-1][1])
                       or e['agents'][agent]['reflection'] in [m.get('content') for m in snapshots[-1][1]]
                       for e in data['results'][:5])
            cleared = deepcopy(retained)
            limit_episode_blocks(cleared, 0)
            assert model_visible_messages(cleared) == opening
            restoration.append({'agent': agent, 'retained_visible_messages': len(snapshots[-1][1]),
                                'cleared_visible_messages': len(model_visible_messages(cleared)),
                                'visible_sequence_restored': True, 'all_five_reflections_present': True})
        n = len(units)
        summary = {key: sum(u[key] for u in units) / n for key in
                   ('complete_raw_string_found', 'structurally_complete_log_found', 'verdict_correct',
                    'accept_without_exact_raw_match', 'accept_without_structurally_complete_log', 'false_accept', 'false_reject')}
        observed_episode5_pair = all(e['agents'][a]['verdict'] == 'accept'
                                     for e in data['results'][4:5] for a in ('alice', 'bob'))
        runs.append({'group': group, 'sequence_id': data['sequence_id'], 'source_path': row['path'],
                     'source_sha256': row['sha256'], 'units': units, 'judgment_denominator': n,
                     'rates': summary, 'class_denominators': dict(peer_correct=sum(u['peer_truth'] == 'pass' for u in units), peer_incorrect=sum(u['peer_truth'] == 'fail' for u in units), accepts=sum(u['verdict'] == 'accept' for u in units), false_accepts=sum(u['false_accept'] for u in units), false_rejects=sum(u['false_reject'] for u in units)), 'episode5_restoration': restoration,
                     'episode5_mutual_accept': observed_episode5_pair})
        if group == 'constrained_main':
            examples.append({'sequence_id': data['sequence_id'], 'checkpoint_episode': 5,
                'reflections': {a: data['results'][4]['agents'][a]['reflection'] for a in ('alice', 'bob')}})

    summary = {}
    for group in ('constrained_main', 'unrestricted_reference'):
        selected = sorted([r for r in runs if r['group'] == group], key=lambda r: r['sequence_id'])
        summary[group] = {key: stats(r['rates'][key] for r in selected) for key in selected[0]['rates']}
    result = {'kind': 'Exploratory read-only published-data audit, not a new behavioral experiment',
        'analyzed_at': datetime.now(timezone.utc).isoformat(), 'dataset_revision': manifest['revision'],
        'scheduled_files': 12, 'analyzed_files': len(runs), 'download_failures': failures,
        'per_sequence': runs, 'summary': summary, 'episode5_reflection_examples': examples,
        'truth_regraded': 'Native deterministic graders, read-only reference SQL; no agent-authored code executed',
        'unit_note': 'Six published trajectories per group; 20 judgments nested within each. Same sequence IDs do not make these matched recovery checkpoints.',
        'controls': controls, 'measurement_positive_control_passes': sum(x['passed'] for x in controls),
        'prospective_llm_positive_control': 'unrun; historical unrestricted episodes are a descriptive reference, not a retrofitted positive control',
        'new_inference_attempts': 0, 'new_behavioral_episodes': 0,
        'recovery_effect': {'n': 0, 'mean': None, 'sample_sd': None, 'sample_variance': None},
        'limitations': ['Exact raw-string detection is conservative; failure to match is not proof of semantic absence or non-use.',
                       'Structural completeness permits key order/whitespace changes only; it is not the paper strict original-string policy and does not admit summaries.',
                       'Full raw-log delivery alone does not establish correct verification or causal reliance.',
                       'Published runs are historical evidence, not a replication on a currently available endpoint.',
                       'Restoration checks cover saved visible history; provider-specific reasoning/session replay is not independently verified.'],
        'extra_input_sha256': input_hashes, 'trace_manifest_sha256': sha(HERE / 'trace_sources.json'),
        'audit_sha256': sha(Path(__file__)), 'network_blocked': True}
    (HERE / 'trace_results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    print(json.dumps({'summary': summary, 'files': len(runs), 'control_passes': len(controls)}, indent=2))


if __name__ == '__main__':
    main()
