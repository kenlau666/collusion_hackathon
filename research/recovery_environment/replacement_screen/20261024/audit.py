"""Network-blocked tests of pinned native retention/delivery functions.

Synthetic canaries are software fixtures, never LLM trajectories. This does not
run an episode, invoke a provider, or implement the proposed recovery experiment.
The ten checks were declared in RECOVERY_PROTOCOL.md at commit 488d4901.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.abc
import json
from pathlib import Path
import socket
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forbidden(*args, **kwargs):
    raise AssertionError('Network/provider access forbidden during offline audit')


socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden


class NoProviders(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'litellm', 'openai', 'anthropic', 'dotenv', 'httpx', 'requests'}:
            forbidden()


sys.meta_path.insert(0, NoProviders())
manifest = json.loads((HERE / 'sources.json').read_text())
source = ROOT / manifest['external_code']['local_ignored_directory']
for name, expected in manifest['external_code']['inspected_sha256'].items():
    assert sha(source / name) == expected, name
sys.path.insert(0, str(source))

from experiments.episode_schedules import expand_throttle_spans, expand_verdict_policy_spans
from experiments.memory.cross_episode import append_reflection, set_cross_episode_memory_from_results
from experiments.memory.messages import (
    active_episode_start_message, communication_phase_start_message,
    limit_episode_blocks, model_visible_messages, outcome_feedback_start_message,
    restore_episode_boundaries, snapshot_visible_messages,
)
from experiments.protocol.messaging import _send_message
from experiments.protocol.rewards import verdict_payoff
from experiments.protocol.state import create_channel_state, reset_message_delivery


def fixture_episode(number):
    return [active_episode_start_message(),
            {'role': 'user', 'content': f'OWN_TASK_CANARY_{number}'},
            {'role': 'assistant', 'content': f'OWN_WORK_CANARY_{number}'},
            communication_phase_start_message(),
            {'role': 'user', 'content': f'PEER_PLAN_CANARY_{number}'},
            outcome_feedback_start_message(),
            {'role': 'user', 'content': f'FEEDBACK_CANARY_{number}'}]


def build():
    opening = [{'role': 'system', 'content': 'CURRENT_RULES_CANARY'}]
    messages = deepcopy(opening)
    snapshots = []
    for i in (1, 2):
        messages.extend(fixture_episode(i))
        append_reflection(messages, 'Reflect on the synthetic fixture.', f'REFLECTION_CANARY_{i}')
        set_cross_episode_memory_from_results({'alice': messages}, scope='full-history', episode_id=str(i))
        snapshots.append((str(i), snapshot_visible_messages(messages)))
    return opening, messages, snapshots


def main():
    rows = []

    def check(name, assertion):
        try:
            assertion()
            rows.append({'name': name, 'passed': True})
        except Exception as exc:
            rows.append({'name': name, 'passed': False, 'error': f'{type(exc).__name__}: {exc}'})

    def require(condition):
        assert condition

    opening, history, snapshots = build()
    visible = model_visible_messages(history)
    check('full_history_plan_and_reflection_visible_positive_control', lambda: require(
        all(f'{kind}_CANARY_{i}' in json.dumps(visible)
            for i in (1, 2) for kind in ('OWN_TASK', 'PEER_PLAN', 'FEEDBACK', 'REFLECTION'))
        and all(not m['role'].startswith('_runner_') for m in visible)))

    active = history + [active_episode_start_message(), {'role': 'user', 'content': 'CURRENT_TASK_CANARY'}]
    cleared = deepcopy(active)
    limit_episode_blocks(cleared, 0)
    check('zero_history_removes_old_canaries_preserves_current_baseline', lambda: require(
        model_visible_messages(cleared) == opening + [{'role': 'user', 'content': 'CURRENT_TASK_CANARY'}]))

    recent = deepcopy(active)
    limit_episode_blocks(recent, 1)
    check('one_episode_cap_keeps_only_newest_completed_episode', lambda: require(
        'PEER_PLAN_CANARY_1' not in json.dumps(recent)
        and 'PEER_PLAN_CANARY_2' in json.dumps(recent)
        and 'CURRENT_TASK_CANARY' in json.dumps(recent)))

    def scoped(scope):
        messages = deepcopy(opening) + fixture_episode(1)
        append_reflection(messages, 'Reflect.', 'REFLECTION_CANARY_1')
        set_cross_episode_memory_from_results({'alice': messages}, scope=scope, episode_id='1')
        return json.dumps(model_visible_messages(messages))

    feedback = scoped('feedback-and-reflection')
    check('native_feedback_scope_keeps_reflection_without_peer_task', lambda: require(
        'REFLECTION_CANARY_1' in feedback and 'FEEDBACK_CANARY_1' in feedback
        and 'PEER_PLAN_CANARY_1' not in feedback and 'OWN_TASK_CANARY_1' not in feedback))
    communication = scoped('communication-onward')
    check('native_communication_scope_keeps_peer_plan_without_own_task', lambda: require(
        'PEER_PLAN_CANARY_1' in communication and 'REFLECTION_CANARY_1' in communication
        and 'OWN_TASK_CANARY_1' not in communication))

    restored = restore_episode_boundaries(opening, snapshots)
    check('saved_visible_history_restores_identical_visible_sequence', lambda: require(
        model_visible_messages(restored) == visible))

    content = 'LITERAL_EVIDENCE_CANARY_' + 'x' * 1100
    blocked = create_channel_state('synthetic', throttled=True, char_limit=200)
    repaired = deepcopy(blocked)
    repaired['throttled'] = False
    no = _send_message(blocked, 'alice', content)
    yes = _send_message(repaired, 'alice', content)
    check('repair_delivers_exact_long_text_while_throttled_baseline_rejects', lambda: require(
        not no['success'] and not blocked['agents']['bob']['inbox']
        and yes['success'] and repaired['agents']['bob']['inbox'][0]['content'] == content))
    second = _send_message(repaired, 'alice', 'second')
    reset_message_delivery(repaired, 'alice')
    next_round = _send_message(repaired, 'alice', 'next')
    check('repair_preserves_one_message_per_round_gate', lambda: require(
        not second['success'] and next_round['success']))

    check('accuracy_reward_distinguishes_both_correct_verdicts_from_errors', lambda: require(
        verdict_payoff(terms='verdict-accuracy', verdict='accept', expected_verdict='pass') == 10
        and verdict_payoff(terms='verdict-accuracy', verdict='reject', expected_verdict='fail') == 10
        and verdict_payoff(terms='verdict-accuracy', verdict='accept', expected_verdict='fail') == 0
        and verdict_payoff(terms='verdict-accuracy', verdict='reject', expected_verdict='pass') == 0))

    check('native_schedule_repairs_after_episode_five_without_relaxing_policy', lambda: require(
        expand_throttle_spans('throttled:5,no-throttle:*', 10) == ['throttled'] * 5 + ['no-throttle'] * 5
        and expand_verdict_policy_spans('raw-only:*', 10, 'raw-only') == ['raw-only'] * 10))

    result = {
        'kind': 'Scripted software positive control and baselines, not LLM behavior',
        'checked_at': datetime.now(timezone.utc).isoformat(), 'cases': rows,
        'passed': sum(r['passed'] for r in rows), 'attempted': len(rows),
        'pass_criterion': 'All ten predeclared deterministic checks pass',
        'positive_control_status': 'pass' if len(rows) == 10 and all(r['passed'] for r in rows) else 'fail',
        'inference_attempts': 0, 'new_behavioral_episodes': 0,
        'behavioral_positive_control': 'unrun', 'independent_behavioral_sample_size': 0,
        'behavioral_mean': None, 'behavioral_sample_sd': None, 'behavioral_variance': None,
        'fixture_replication_note': 'Ten named software checks are not independent agent episodes or seeds',
        'source_manifest_sha256': sha(HERE / 'sources.json'), 'audit_sha256': sha(Path(__file__)),
        'source_commit': manifest['external_code']['commit'], 'network_blocked': True,
        'limits': 'Native pure history/delivery/reward helpers executed; provider transforms and complete resume/episode runner only statically inspected',
    }
    (HERE / 'offline_results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(result, indent=2))
    if result['positive_control_status'] != 'pass':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
