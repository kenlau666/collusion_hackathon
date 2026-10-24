"""Network-blocked request accounting and full session routing tests."""
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest

from harness import Session, world_step
from run_study import Client, EndpointConfig, LIMITS, MODEL, Stopped, play


def forbidden(*args, **kwargs):
    raise AssertionError('No network allowed in runner tests')


socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden


class Response:
    status_code = 200
    def __init__(self, body):
        self.body = body
    def json(self):
        return self.body


class Transport:
    def __init__(self, missing_usage=False, wrong_model=False, incomplete=False):
        self.requests = []
        self.missing_usage, self.wrong_model = missing_usage, wrong_model
        self.incomplete = incomplete
    def post(self, url, json, headers):
        self.requests.append(json)
        data = __import__('json').loads(json['messages'][1]['content'])
        task = data['task']
        if 'Choose one legal action' in task:
            answer = '{"action":"STAY","explanation":"fixture"}'
        elif 'optional private text channel' in task:
            answer = '{"accept":true,"partner":1}'
        else:
            answer = 'fixture private message'
        body = {'model': 'wrong' if self.wrong_model else MODEL,
                'choices': [{'finish_reason': 'length' if self.incomplete else 'stop', 'message': {'content': answer}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 10}}
        if self.missing_usage:
            body.pop('usage')
        return Response(body)


def client(directory, transport):
    config = EndpointConfig('https://fixture.invalid/v1', MODEL, 'fixture', {'Authorization': 'PRIVATE_HEADER_SENTINEL'})
    return Client(directory, config, transport, time.monotonic() + 60)


class RunnerTests(unittest.TestCase):
    def test_revocation_blocks_all_new_peer_calls_and_reset_removes_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for arm in ('R3', 'R5'):
                session = Session(0)
                session.channel = {'active': True, 'pair': [0, 1]}
                session.deliver(0, 1, 'OLD_PEER_SENTINEL', 'fixture')
                session.deliver(1, 0, 'OLD_PEER_SENTINEL', 'fixture')
                session.intervene(arm, 0)
                transport = Transport()
                api = client(root / arm, transport)
                play(api, session, 2, arm, root / arm / 'episode')
                self.assertEqual(api.state['calls_completed'], 8)
                self.assertEqual(len(session.messages), 2)
                self.assertEqual(any('OLD_PEER_SENTINEL' in json.dumps(p) for p in transport.requests), arm == 'R3')
                self.assertNotIn('PRIVATE_HEADER_SENTINEL', ''.join(p.read_text() for p in (root / arm).rglob('*.json')))

    def test_open_channel_repopulates_cleared_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = Session(0)
            session.channel = {'active': True, 'pair': [0, 1]}
            session.intervene('R2', 0)
            api = client(root, Transport())
            play(api, session, 1, 'open', root / 'episode')
            self.assertEqual(api.state['calls_completed'], 8)
            self.assertEqual(len(session.messages), 4)
            self.assertTrue(all(session.context[i]['latest_peer'] is not None for i in (0, 1)))

    def test_missing_usage_and_model_substitution_stop_following_calls(self):
        for options in ({'missing_usage': True}, {'wrong_model': True}):
            with tempfile.TemporaryDirectory() as directory:
                transport = Transport(**options)
                api = client(directory, transport)
                messages = Session(0).envelope(0, 'Choose one legal action')
                meta = {'kind': 'action', 'episode': 'failure', 'agent': 0, 'step': 1}
                with self.assertRaises(Stopped):
                    api.call(messages, meta, True)
                with self.assertRaises(Stopped):
                    api.call(messages, meta, True)
                self.assertEqual(len(transport.requests), 1)
                self.assertEqual(api.state['calls_failed'], 1)
                self.assertEqual(api.state['reserved_input_tokens'], 0)

    def test_call_cap_closes_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = Transport()
            api = client(directory, transport)
            api.state['calls_started'] = LIMITS['calls']
            with self.assertRaises(Stopped):
                api.call(Session(0).envelope(0, 'fixture'),
                         {'kind': 'action', 'episode': 'gate', 'agent': 0, 'step': 1}, True)
            self.assertEqual(transport.requests, [])

    def test_utc_wall_deadline_closes_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = Transport()
            api = client(directory, transport)
            api.utc_deadline = time.time() - 1
            with self.assertRaises(Stopped):
                api.call(Session(0).envelope(0, 'fixture'),
                         {'kind': 'action', 'episode': 'utc_gate', 'agent': 0, 'step': 1}, True)
            self.assertEqual(transport.requests, [])

    def test_restored_episode_metrics_exclude_its_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = Session(0)
            for _ in range(2):
                world_step(original, dict.fromkeys(range(4), 'STAY'))
            restored = Session.restore(json.loads(json.dumps(original.snapshot())))
            api = client(root, Transport())
            play(api, restored, 3, 'continuation', root / 'episode')
            metrics = json.loads((root / 'episode/metrics.json').read_text())
            self.assertEqual(metrics['steps'], 1)
            self.assertEqual(len(restored.records), 3)

    def test_incomplete_messages_are_not_delivered_and_actions_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = Session(0)
            session.channel = {'active': True, 'pair': [0, 1]}
            api = client(root, Transport(incomplete=True))
            play(api, session, 1, 'incomplete', root / 'episode')
            self.assertEqual(api.state['calls_completed'], 6)
            self.assertEqual(len(session.messages), 2)
            self.assertTrue(all(not m['delivered'] for m in session.messages))
            self.assertTrue(all(v['error'] for v in session.records[0]['parsing'].values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
