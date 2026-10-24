"""Read saved episodes for an architecture review; no agent/environment imports.

Run from any directory. Only results.json beside this file is written. Historical
files are hash-checked against the prior construct audit before and after reading.
This is a descriptive reanalysis, not new episodes or a recovery experiment.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import statistics

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = ROOT / 'research/recovery_environment'


def forbidden(*args, **kwargs):
    raise AssertionError('Network forbidden in saved-evidence review')


socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values):
    values = list(values)
    return dict(values=values, n=len(values), mean=statistics.mean(values),
                sample_sd=statistics.stdev(values), sample_variance=statistics.variance(values))


def main():
    historical = read(BASE / 'construct_audits/20261024T124951Z/audit.json')['historical_sha256']
    for path, expected in historical.items():
        assert sha(ROOT / path) == expected, path
    source_hashes = {}

    def evidence(path):
        source_hashes[str(path.relative_to(ROOT))] = sha(path)
        return read(path)

    groups = {}
    for group in ('prefixes', 'references', 'controls'):
        rows = []
        for seed in range(6):
            directory = BASE / 'live_runs/20261024T111809Z' / group / f'seed_{seed}'
            state = evidence(directory / 'checkpoint.json')
            status = evidence(directory / 'status.json')
            records = state['records']
            actions = Counter(a for r in records for a in r['actions'].values())
            events = [e for r in records for e in r['events']]
            rows.append(dict(seed=seed, status=status['status'], steps=len(records),
                actions=dict(actions), apple_rewards=sum(sum(r['rewards'].values()) for r in records),
                all_agent_hit_events=sum(e['kind'] == 'hit' for e in events),
                effective_cleaning_units=sum(e['units_removed'] for e in events if e['kind'] == 'cleaning'),
                clean_action_count=actions['CLEAN'],
                post_step_pollution_at_or_above_cutoff=sum(r['pollution'] >= 6 for r in records),
                checkpoint_peer_record_count=sum(v['latest_peer'] is not None for v in state['context'].values())))
        complete = [r for r in rows if r['status'] == 'complete']
        groups[group] = dict(attempted_seeds=list(range(6)), per_seed=rows,
            completed_summary={key: stats(r[key] for r in complete) for key in
                ('apple_rewards', 'all_agent_hit_events', 'effective_cleaning_units', 'clean_action_count',
                 'post_step_pollution_at_or_above_cutoff')})

    pc_s = evidence(BASE / 'offline_runs/20261024T095635Z/results.json')
    pc_l = evidence(BASE / 'live_runs/20261024T095809Z/control_review.json')
    offers = evidence(BASE / 'offer_diagnostics/20261024T123500Z/results.json')
    literature = evidence(BASE / 'construct_audits/20261024T124951Z/literature_manifest.json')
    sources = []
    for item in literature['sources']:
        if item['name'] not in ('FLP', 'SafeFlow', 'Emergent Collusion', 'Voluntary Collusion'):
            continue
        cached = ROOT / item['local_ignored_cache']
        if cached.exists():
            assert sha(cached) == item['sha256']
        sources.append(dict(name=item['name'], version=item['version'], url=item['url'],
                            sha256=item['sha256'], existing_cache_hash_verified=True if cached.exists() else None))
    for path in ('harness.py', 'run_study.py', 'validate_harness.py', 'test_runner.py'):
        source_hashes[str((BASE / path).relative_to(ROOT))] = sha(BASE / path)
    starter = ROOT / 'llm-agent-collusion-2/Collusion_Cleanup/cleanup_llm'
    for path in ('agents/llm_agent.py', 'agents/llm_client.py', 'agents/prompts.py',
                 'games/secret_channel.py', 'games/tournament_secret_channel.py',
                 'cleanup/env.py', 'cleanup/config.py'):
        source_hashes[str((starter / path).relative_to(ROOT))] = sha(starter / path)
    for path, expected in historical.items():
        assert sha(ROOT / path) == expected, path
    result = dict(kind='Descriptive reanalysis of saved evidence; not a new behavioral experiment',
        reviewed_at=datetime.now(timezone.utc).isoformat(), inference_attempts=0,
        new_behavioral_episodes=0, new_game_steps=0, network_blocked=True,
        independent_units='Six historical seed/episode blocks per group; calls/actions/hits are nested, not replicates',
        comparisons='Different horizons and trajectories; no cross-group recovery treatment effect estimated',
        groups=groups, historical_controls=dict(
            PC_S_passes=pc_s['positive_control_passes'], PC_S_attempts=pc_s['attempted'],
            PC_L_passes=pc_l['passed'], PC_L_attempts=pc_l['attempted'],
            PC_L_completed=pc_l['complete'], PC_L_failed=pc_l['failed'],
            note='Historical controls retained; software tests do not establish behavioral sensitivity or message reliance'),
        offer_results_source=str((BASE / 'offer_diagnostics/20261024T123500Z/results.json').relative_to(ROOT)),
        offer_counts={key: dict(acceptances=value['acceptances'], attempted=value['attempted'],
                               control_passes=value['control_passes']) for key, value in offers['conditions'].items()},
        primary_sources=sources, research_skill=literature['skill'],
        recovery_effect=dict(independent_blocks=0, mean=None, sample_sd=None, sample_variance=None),
        historical_files_unchanged=len(historical), input_and_code_sha256=source_hashes,
        analyzer_sha256=sha(Path(__file__)))
    assert pc_s['positive_control_passes'] == 6 and pc_l['passed'] == 2
    assert len(offers['rows']) == 18
    (HERE / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(groups={k: v['completed_summary'] for k, v in groups.items()},
                          historical_files_unchanged=len(historical)), indent=2))


if __name__ == '__main__':
    main()
