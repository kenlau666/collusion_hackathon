"""Offline validation and immutable preparation bundle; no paid run command."""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import statistics
import sys

NETWORK = []
CREDENTIAL_ACCESS = []


def offline_only(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind', 'http.client.connect'}:
        NETWORK.append(event)
        raise RuntimeError('network denied during corrected-control preparation')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = str(args[0])
        if name.endswith(('compute.env', '/.env', '/.modal.toml')):
            CREDENTIAL_ACCESS.append('credential_file')
            raise RuntimeError('credential access denied during offline preparation')


sys.addaudithook(offline_only)
saved_ipv6 = socket.has_ipv6
try:
    # Suppress only urllib3's known import-time IPv6 probe; restore immediately.
    socket.has_ipv6 = False
    import corrected_control_prompts as corrected
    import engagement_pilot as engagement
    import modal_hospital_runtime as modal
    from modal_hospital_client import ModalHospitalClient
    from budget_client import BudgetLedger, TransportReply
finally:
    socket.has_ipv6 = saved_ipv6

HERE = Path(__file__).resolve().parent
BASE = HERE / '20261025'
OLD_BUNDLE = BASE / 'modal_gate_integration_001/bundle'
OLD_REFERENCE = BASE / 'modal_gate_002/success'
PAID_RUN = BASE / 'modal_engagement_live_001'
NEW_SOURCES = ('corrected_control_prompts.py', 'freeze_corrected_controls.py')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preserved_sources():
    original = read(modal.ORIGINAL / 'plan.json')
    sources = {str(HERE / Path(p).name): h for p, h in original['files'].items()
               if p.startswith('sources/')}
    sources.update(original['native_sources'])
    sources.update({str(HERE / p): h for p, h in read(OLD_BUNDLE / 'plan.json')['sources'].items()})
    if len(sources) != 52 or any(sha(Path(p)) != h for p, h in sources.items()):
        raise ValueError('frozen scientific/native/Modal source mismatch')
    return sources


class FakeModal(engagement.MockTransport):
    def __init__(self, mode='success', replies=None):
        super().__init__(mode)
        self.replies = replies

    def post(self, payload, *, timeout):
        if self.replies is not None:
            self.posts.append(deepcopy(payload))
            body = deepcopy(self.replies[len(self.posts) - 1])
            body['id'] = 'offline-replayed-' + body['id']
            return TransportReply(200, body)
        reply = super().post(payload, timeout=timeout)
        body = deepcopy(reply.body)
        body['model'] = modal.MODEL
        body.pop('provider', None)
        body['usage'].pop('cost', None)
        return TransportReply(reply.status_code, body)


def fake_client(path, transport):
    authorization = {'approved': True, 'scope': 'full', 'max_calls': 198, 'max_usd': '10',
                     'plan_sha256': 'f' * 64, 'approval_reference': 'OFFLINE fake transport only'}
    ledger = BudgetLedger(path / 'accounting', scope='full', max_calls=198, max_usd='10',
                          plan_sha256='f' * 64, authorization=authorization)
    client = ModalHospitalClient(ledger, modal.EXPECTED_BASE, modal.MODEL,
        {'Modal-Key': 'offline-proxy-id', 'Modal-Secret': 'offline-proxy-secret'},
        path / 'diagnostics', sha(HERE / 'modal_request_worker.py'))
    client.transport = transport
    return client


def visible_facts(user, corrected_prompt=False):
    prefix = user.rpartition('\n[PHASE:')[0]
    if corrected_prompt:
        prefix = prefix.replace(corrected.NEW_QUEUE + '\n' + corrected.NEW_QUEUE_RULE,
                                corrected.OLD_QUEUE + '\n' + corrected.OLD_QUEUE_RULE)
    inventory = re.findall(r'^(?:Inventory|3\. INVENTORY CHECK): \[(.*)\]$', user, re.MULTILINE)
    costs = re.findall(r'^Costs per Patient: \[(.*)\]$', user, re.MULTILINE)
    penalties = re.findall(r'Scheduling without resources costs -300, which is better than -500', user)
    assert len(inventory) == 1
    return {'status_boards_full_queue_and_cost_table': prefix, 'inventory': inventory,
            'costs': costs, 'penalty_comparison': penalties}


async def validate(output):
    output.mkdir(parents=True, exist_ok=False)
    frozen = preserved_sources()
    paid = {str(p): sha(p) for p in sorted(PAID_RUN.rglob('*')) if p.is_file()}
    sources = {p: sha(HERE / p) for p in NEW_SOURCES}
    (output / 'sources').mkdir()
    for name in NEW_SOURCES:
        shutil.copyfile(HERE / name, output / 'sources' / name)
    checks = {}
    result = {'kind': 'offline corrected-control validation', 'checks': checks,
              'new_sources': sources, 'preserved_sources': frozen, 'paid_run_files': paid,
              'provider_calls': 0, 'credential_lookups': 0, 'actual_spend_usd': '0'}
    try:
        engagement.verify_bundle(modal.ORIGINAL)
        roots = read(OLD_BUNDLE / 'roots.json')
        transport = FakeModal()
        client = fake_client(output / 'success', transport)
        cases, summary = await corrected.execute(client, output / 'success', roots)
        assert len(cases) == 12 and summary['qualification_passed'] and len(transport.posts) == 162
        checks['six_scripted_care_positives_and_six_ordinary_measurement_baselines'] = True
        old_records = read(OLD_REFERENCE / 'accounting/ledger.json')['records']
        assert len(old_records) == len(transport.posts)
        initial, positive_turns, reference = {}, {}, []
        cursor = 0
        for case in cases:
            spec = case['spec']
            prior = read(OLD_REFERENCE / (spec['id'] + '.json'))
            persisted = json.loads(json.dumps(case))
            assert persisted['root'] == roots[spec['id']] == prior['root']
            for key in ('initial', 'final', 'metrics', 'final_native_reward', 'passed',
                        'designated_physical_sequence', 'callback_attempts'):
                assert persisted[key] == prior[key], (spec['id'], key)
            rows = []
            for turn in case['turn_outcomes']:
                first = deepcopy(transport.posts[cursor])
                rows.append({'step': turn['step'], 'payload': first,
                             'trajectory': 'scripted designated-action reference, not a future LLM reply'})
                if not initial.get(spec['id']):
                    initial[spec['id']] = {'messages': first['messages'], 'tools': first['tools'],
                        'model': first['model'], 'local_sampling_seed': turn['step']['sampling_seed'],
                        'api_seed_forwarded': False}
                for _ in range(turn['generation_calls']):
                    new, old = transport.posts[cursor], old_records[cursor]['payload']
                    reference.append({'case': spec['id'], 'turn_index': turn['step']['turn_index'],
                                      'payload': deepcopy(new)})
                    assert {k: v for k, v in new.items() if k != 'messages'} == {
                        k: v for k, v in old.items() if k != 'messages'}
                    if spec['kind'] == 'ordinary':
                        assert new == old
                    else:
                        assert len(new['messages']) == len(old['messages'])
                        for nm, om in zip(new['messages'], old['messages']):
                            if nm['role'] == 'user':
                                assert om['role'] == 'user' and nm['content'] != om['content']
                                assert visible_facts(nm['content'], True) == visible_facts(om['content'])
                                assert corrected.CONTRACT in nm['content']
                                for banned in ('for every line item', 'schedule ANYWAY',
                                               'HAVE SURPLUS?', 'Do NOT wait. Do NOT hesitate.',
                                               corrected.OLD_QUEUE_RULE):
                                    assert banned not in nm['content']
                            else:
                                assert nm == om
                    cursor += 1
            if spec['kind'] == 'positive':
                assert len(rows) == 3
                positive_turns[spec['id']] = rows
        assert cursor == 162 and len(initial) == 12 and len(positive_turns) == 6
        checks['all18_positive_turn_facts_full_queue_tools_resources_and_criteria_unchanged'] = True
        checks['all126_ordinary_payloads_byte_equivalent_to_old_scripted_reference'] = True
        checks['all_positive_system_assistant_and_tool_messages_unchanged'] = True
        for name, value in (('roots.json', roots), ('initial_inputs.json', initial),
                            ('positive_turn_inputs.json', positive_turns),
                            ('scripted_reference_inputs.json', reference)):
            engagement.save(output / name, value)

        noop_transport = FakeModal('noop')
        noop_client = fake_client(output / 'noop', noop_transport)
        noops, noop_summary = await corrected.execute(noop_client, output / 'noop', roots)
        assert len(noops) == 6 and not any(r['passed'] for r in noops)
        assert len(noop_transport.posts) == 54 and len(noop_summary['unstarted_cases']) == 6
        checks['all_six_noop_failures_retained_and_ordinary_gated_off'] = True

        actual = read(PAID_RUN / 'accounting/ledger.json')['records']
        replay_transport = FakeModal(replies=[r['response'] for r in actual[7:11]])
        replay_client = fake_client(output / 'retained_seed2_replay', replay_transport)
        replay_spec = next(s for s in engagement.matrix() if s['kind'] == 'positive' and s['seed'] == 2)
        with corrected.installed():
            replay = await engagement.run_case(replay_spec, replay_client,
                output / 'retained_seed2_replay', roots[replay_spec['id']])
        assert len(replay_transport.posts) == 4 and not replay['passed']
        assert json.loads(json.dumps(replay['final'])) == read(PAID_RUN / 'engagement-positive-s2.json')['final']
        assert replay['metrics']['care_final']['complete'] == 1
        assert sum(replay['final']['resource_failures'].values()) == 1
        assert replay['designated_physical_sequence'] is False
        checks['saved_extra_action_batch_still_executes_and_fails_care_resource_sequence'] = True

        class BadNative:
            def get_user_prompt(self, *args): return 'unsupported source layout'
        prompt = corrected.CorrectedDesignatedActionPrompts(BadNative())
        for instruction, context in (('', {'phase': 'execution'}), ('designated', {'phase': 'survey'}),
                                     ('designated', {'phase': 'execution'})):
            prompt.instruction = instruction
            try:
                prompt.get_user_prompt('actor', context, {})
            except ValueError:
                pass
            else:
                raise AssertionError('unsupported prompt layout accepted')
        checks['missing_designation_and_unsupported_prompt_layouts_fail_closed'] = True
        assert engagement.make_case is corrected.ORIGINAL_MAKE_CASE
        assert all(sha(Path(p)) == h for p, h in paid.items())
        assert preserved_sources() == frozen and not NETWORK and not CREDENTIAL_ACCESS
        checks['old_34_run_files_52_sources_and_all_scientific_rules_preserved'] = True
        result.update(status='passed', passed=len(checks), total=len(checks),
            scripted_pipeline=summary, scripted_noop_controls=noop_summary,
            retained_replay={'fixture_seed': 2, 'care': 1, 'IV_failures': 1, 'passed': False,
                             'scripted_calls': 4, 'n': 1, 'sample_sd': None, 'sample_variance': None,
                             'limit': 'Saved old tool outputs replayed, not new model behavior.'},
            fake_transport_attempts=220, network_attempts=NETWORK, credential_attempts=CREDENTIAL_ACCESS,
            input_files={name: sha(output / name) for name in
                ('roots.json', 'initial_inputs.json', 'positive_turn_inputs.json', 'scripted_reference_inputs.json')})
    except Exception as error:
        result.update(status='failed', error_type=type(error).__name__, detail=str(error))
        engagement.save(output / 'results.json', result)
        raise
    engagement.save(output / 'results.json', result)
    return result


def freeze(validation, output):
    result = read(validation / 'results.json')
    if result.get('status') != 'passed' or not all(result['checks'].values()):
        raise ValueError('passing offline validation required')
    if result['new_sources'] != {p: sha(HERE / p) for p in NEW_SOURCES}:
        raise ValueError('validated correction source changed')
    if preserved_sources() != result['preserved_sources']:
        raise ValueError('frozen dependency changed')
    if any(sha(Path(p)) != h for p, h in result['paid_run_files'].items()):
        raise ValueError('old failed evidence changed')
    if any(sha(validation / p) != h for p, h in result['input_files'].items()):
        raise ValueError('validated input changed')
    prior = modal.history()
    if Decimal(prior['conservative_guard_usd']) + 10 > 50:
        raise ValueError('cumulative reference guard insufficient')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'sources').mkdir()
    research_sources = {**{Path(p).name: h for p, h in result['preserved_sources'].items()
                          if Path(p).parent == HERE}, **result['new_sources']}
    for name in research_sources:
        shutil.copyfile(HERE / name, output / 'sources' / name)
    for name in result['input_files']:
        shutil.copyfile(validation / name, output / name)
    old = read(OLD_BUNDLE / 'plan.json')
    retained_fields = ('model', 'endpoint', 'max_calls', 'max_usd', 'max_output_tokens',
        'max_reported_input_tokens', 'input_reference_usd_per_million', 'output_reference_usd_per_million',
        'temperature', 'reasoning_effort', 'api_seed_forwarded', 'conversation_cap',
        'request_deadline_seconds', 'batch_deadline_seconds', 'cases', 'accounting_basis')
    plan = {k: old[k] for k in retained_fields}
    plan.update(stage='positive_control_instruction_correction', approved=False,
        execution_authorized=False, main_study_started=False, scope='offline implementation validation and freeze only',
        contract=corrected.CONTRACT, code_entrypoint='corrected_control_prompts.execute(client, output, roots)',
        paid_run_command=None, positive_cases=6, conditional_ordinary_cases=6,
        native_turns={'positive': 3, 'ordinary': 8}, max_calls_by_group={'positive': 54, 'ordinary': 144},
        ordinary_gate='all six positive cases pass; retain all failures without replacement',
        criteria_source_sha256=sha(HERE / 'engagement_pilot.py'),
        old_plan_sha256=sha(OLD_BUNDLE / 'plan.json'), old_failed_run_files=result['paid_run_files'],
        reference_trajectory_limit='Scripted responses only; future reply-dependent contexts are not known in advance.',
        ordinary_and_main_inputs_changed=False, prior_accounting=prior, total_hospital_ceiling_usd='50',
        actual_modal_charges_verified=False, source_hashes=research_sources,
        native_sources=read(modal.ORIGINAL / 'plan.json')['native_sources'],
        files={name: sha(output / name) for name in result['input_files']},
        validation_results_path=str(validation / 'results.json'), validation_results_sha256=sha(validation / 'results.json'))
    engagement.save(output / 'plan.json', plan)
    return {'plan_sha256': sha(output / 'plan.json'), 'source_count': len(research_sources),
            'native_source_count': len(plan['native_sources']), 'execution_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('validate'); p.add_argument('--out', type=Path, required=True)
    p = commands.add_parser('freeze'); p.add_argument('--validation', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'validate':
        result = asyncio.run(validate(args.out))
        print(json.dumps({k: result[k] for k in ('status', 'passed', 'total', 'fake_transport_attempts', 'provider_calls', 'actual_spend_usd')}))
    else:
        print(json.dumps(freeze(args.validation, args.out)))
