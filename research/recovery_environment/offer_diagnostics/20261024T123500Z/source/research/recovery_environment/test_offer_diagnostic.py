"""Offline contract tests. Network connections are forbidden during this suite."""
import ast
import copy
import json
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import patch

import offer_diagnostic as d


class InvitationReached(BaseException):
    pass


def full_production_guard(first, initiator):
    """Run unchanged consent AST; intercept before any partner request is made."""
    namespace = d.validator_namespace()
    count = 0

    def invoke(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            return first
        raise InvitationReached

    namespace.update(invoke=invoke, save=lambda *args: None)
    fn = d.source_function(d.HERE/'run_study.py','consent')
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual-consent-offline','exec'),namespace)
    try:
        namespace['consent'](None,types.SimpleNamespace(channel={'active':False}),initiator,'offline',Path('.'))
    except InvitationReached:
        return True
    return False


class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocker=patch.object(socket.socket,'connect',side_effect=AssertionError('Offline network forbidden'))
        cls.blocker.start()
        cls.audit=d.read(d.SOURCE/'analysis/offer_audit.json')

    @classmethod
    def tearDownClass(cls):
        cls.blocker.stop()

    def test_actual_validator_contract_and_slice(self):
        fixtures = [
            ('{"accept":true,"partner":1}',True,True,'accept'),
            ('{"accept":false}',True,False,'refuse'),
            ('{"accept":true,"partner":0}',True,False,'invalid'),
            ('{"accept":true,"partner":4}',True,False,'invalid'),
            ('{"accept":true,"partner":"1"}',True,False,'invalid'),
            ('{"accept":true,"partner":true}',True,False,'invalid'),
            ('{"accept":true}',True,False,'invalid'),
            ('{"accept":1,"partner":1}',True,False,'invalid'),
            ('{"accept":true,"partner":1}',False,False,'invalid'),
            ('{"accept":false}',False,False,'invalid'),
            ('{"accept":true,"partner":1',True,False,'invalid'),
            ('{"accept":false,"accept":true,"partner":1}',True,False,'invalid'),
            ('[]',True,False,'invalid'),
            ('```json\n{"accept":true,"partner":1}\n```',True,False,'invalid'),
        ]
        for raw,complete,accepted,decision in fixtures:
            with self.subTest(raw=raw,complete=complete):
                result=d.parse_decision(raw,complete,0,1)
                self.assertEqual(full_production_guard({'text':raw,'complete':complete},0),accepted)
                self.assertEqual(result['validator_acceptance'],accepted)
                self.assertEqual(result['decision'],decision)
        # Valid acceptance of another partner must fail this designated-partner control.
        result=d.parse_decision('{"accept":true,"partner":2}',True,0,1)
        self.assertTrue(result['validator_acceptance'])
        self.assertFalse(result['control_pass'])

    def test_exact_replay_and_presentation_only_changes_all_cases(self):
        for case in self.audit['cases']:
            path=d.SOURCE/'calls'/(case['call_id']+'.json')
            self.assertEqual(d.sha(path),case['call_sha256'])
            saved=d.read(path)
            original=saved['request']
            data=json.loads(original['messages'][1]['content'])
            self.assertEqual(data['observation']['you'],saved['agent'])
            designated=(saved['agent']+1)%4
            self.assertIn(str(designated),data['observation']['agents'])
            self.assertNotEqual(designated,saved['agent'])
            self.assertEqual(d.construct(original,'A',designated),original)
            for condition in 'BC':
                constructed=d.construct(original,condition,designated)
                self.assertEqual({k:v for k,v in constructed.items() if k!='messages'},
                                 {k:v for k,v in original.items() if k!='messages'})
                self.assertEqual(constructed['messages'][0],original['messages'][0])
                changed=json.loads(constructed['messages'][1]['content'])
                self.assertEqual(changed['observation'],data['observation'])
                self.assertEqual(changed['retained_peer_text'],data['retained_peer_text'])
                for key in data:
                    if key not in (('task','private_channel') if condition=='B' else ('task',)):
                        self.assertEqual(changed[key],data[key])
            self.assertTrue(d.parse_decision(json.dumps({'accept':True,'partner':designated}),
                                            True,saved['agent'],designated)['control_pass'])

    def test_frozen_schedule_requests_bounds_and_sources(self):
        directory=Path(__import__('os').environ['OFFER_DIAGNOSTIC_DIRECTORY'])
        plan=d.read(directory/'plan.json')
        self.assertEqual(len(plan['schedule']),18)
        self.assertEqual({(r['seed'],r['condition']) for r in plan['schedule']},
                         {(s,c) for s in range(6) for c in 'ABC'})
        for block in range(1,4):
            block_rows=[r for r in plan['schedule'] if r['block']==block]
            self.assertEqual({r['seed'] for r in block_rows},set(range(6)))
            self.assertEqual([sum(r['condition']==c for r in block_rows) for c in 'ABC'],[2,2,2])
        for seed in range(6):
            self.assertEqual({r['condition'] for r in plan['schedule'] if r['seed']==seed},set('ABC'))
        total_input=0
        for row in plan['schedule']:
            path=directory/row['request']
            self.assertEqual(d.sha(path),row['sha256'])
            case=plan['cases'][row['seed']]
            original=d.read(d.ROOT/case['source_call'])['request']
            self.assertEqual(d.read(path),d.construct(original,row['condition'],case['designated_partner']))
            total_input+=d.input_bound(d.read(path))
        self.assertLessEqual(total_input,d.LIMITS['input_tokens'])
        self.assertLess(d.reference_cost(total_input,18*256),d.LIMITS['reference_usd'])
        for path,expected in plan['source_sha256'].items():
            self.assertEqual(d.sha(d.ROOT/path),expected)
        print(json.dumps({'worst_case_reserved_input_tokens':total_input,'output_tokens':4608,
                          'reference_usd':d.reference_cost(total_input,4608)}))

    def test_no_world_or_partner_execution_in_dispatcher(self):
        tree=ast.parse(Path(d.__file__).read_text())
        calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)]
        self.assertEqual(calls.count('transport.post'),1)
        for forbidden in ('consent','Session','world_step','play','invoke'):
            self.assertNotIn(forbidden,calls)
        self.assertEqual(d.wilson(0,6)[0],0)
        self.assertAlmostEqual(d.wilson(0,6)[1],0.3903342879021653)

    def test_report_keeps_failures_in_denominator(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            (directory/'calls').mkdir()
            schedule=[dict(order=i*3+j+1,seed=i,condition=c) for i in range(6) for j,c in enumerate('ABC')]
            d.save(directory/'plan.json',dict(schedule=schedule,cases=[],original_audit='offline'))
            d.save(directory/'usage.json',dict(attempts=18))
            for row in schedule:
                event=dict(row,status='failed',failure_type='ReadTimeout')
                if row['order'] != 3:
                    raw='{"accept":true,"partner":1}' if row['condition']=='C' else '{"accept":false}'
                    event.update(status='success',raw_response=raw,outcome=d.parse_decision(raw,True,0,1))
                d.save(directory/'calls'/f"{row['order']:02d}-fixture.json",event)
            d.report(directory)
            result=d.read(directory/'results.json')
            self.assertEqual(result['conditions']['C']['control_passes'],5)
            self.assertEqual(result['conditions']['C']['scheduled_denominator'],6)
            self.assertEqual(result['conditions']['C']['unresolved'],1)
            self.assertEqual(result['conditions']['A']['refusals'],6)


if __name__=='__main__':
    import os
    directory=Path(os.environ['OFFER_DIAGNOSTIC_DIRECTORY'])
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(OfflineTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    d.save(directory/'offline_validation.json',dict(passed=result.wasSuccessful(),tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),inference_calls=0,
        plan_sha256=d.sha(directory/'plan.json'),tested_at=d.now(),
        includes='actual production-consent contract, replay invariants, interleaving, bounds, reporting failures'))
    raise SystemExit(0 if result.wasSuccessful() else 1)
