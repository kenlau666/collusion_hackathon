"""Unpaid positive/negative tests of traced worker -> native parser -> ledger."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

NETWORK = []
def deny(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo'}:
        NETWORK.append(event)
        raise RuntimeError('network denied in traced bridge validation')
sys.addaudithook(deny)
ipv6 = socket.has_ipv6
try:
    socket.has_ipv6 = False
    from budget_client import BudgetLedger, BudgetError
    from modal_hospital_client import BASE_URL, MODEL
    from traced_modal_client import TracedModalClient
finally:
    socket.has_ipv6 = ipv6

HERE = Path(__file__).resolve().parent


def main(bundle, out):
    out.mkdir(parents=True, exist_ok=False)
    auth = json.loads((bundle / 'authorization.json').read_text())
    plan = json.loads((bundle / 'plan.json').read_text())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    first = json.loads((bundle / 'initial_inputs.json').read_text())['full-care-s0']
    real_popen = subprocess.Popen
    reports = []
    for mode in ('positive', 'malformed'):
        ledger = BudgetLedger(out / mode / 'accounting', scope='full', max_calls=1,
            max_usd='.049', plan_sha256=sha(bundle / 'plan.json'), authorization=auth)
        client = TracedModalClient(ledger=ledger, base_url=BASE_URL, model=MODEL,
            headers={'Modal-Key': 'OFFLINE_ID', 'Modal-Secret': 'OFFLINE_SECRET'},
            diagnostics=out / mode / 'diagnostics', worker_sha256=plan['sources']['endpoint_probe_worker.py'])
        def fake(*args, **kwargs):
            code = ("import json,sys,os;from pathlib import Path;d=json.load(sys.stdin);"
                "b={'id':'offline','model':d['payload']['model'],'choices':[{'message':{'role':'assistant',"
                "'content':'BRIDGE_OK','tool_calls':[{'id':'q','type':'function','function':{'name':'get_job_queue','arguments':'{}'}}]},"
                "'finish_reason':'tool_calls'}],'usage':{'prompt_tokens':100,'completion_tokens':20}};"
                "Path(os.environ['MODAL_PROGRESS_PATH']).write_text(json.dumps({'stage':'complete','events':[],'body_bytes':1}));"
                "print(json.dumps({'kind':'reply','status_code':200,'body':b}))")
            if mode == 'malformed':
                code = "import sys;sys.stdin.read();print('not JSON')"
            return real_popen([sys.executable, '-c', code], **kwargs)
        with patch('traced_modal_client.subprocess.Popen', fake):
            try:
                response, text = client.generate_response(first['messages'], {'model': MODEL, 'tools': first['tools']})
            except BudgetError:
                assert mode == 'malformed'
            else:
                assert mode == 'positive' and text == 'BRIDGE_OK'
                assert response['choices'][0]['message']['tool_calls'][0]['function']['name'] == 'get_job_queue'
        payload = ledger.state['records'][0]['payload']
        assert payload['messages'] == first['messages'] and payload['tools'] == first['tools']
        assert payload['stream'] is False and 'stream_options' not in payload
        assert ledger.state['calls'] == 1
        if mode == 'positive':
            assert ledger.state['status'] == 'ready' and ledger.state['held_usd'] == '0.000'
        else:
            assert ledger.state['status'] == 'halted' and ledger.state['held_usd'] == '0.049'
        reports.append({'mode': mode, 'passed': True, 'calls': 1, 'ledger_status': ledger.state['status']})
    assert not NETWORK
    result = {'passed': True, 'cases': reports, 'network_attempts': NETWORK, 'inference_calls': 0,
        'source_hashes': {p.name: sha(p) for p in (Path(__file__).resolve(), HERE / 'traced_modal_client.py')},
        'plan_sha256': sha(bundle / 'plan.json'), 'exact_first_payload': True,
        'sample_sd': None, 'sample_variance': None, 'n': 1,
        'limit': 'single scripted positive/malformed counterexamples; no LLM competence or reliability estimate'}
    (out / 'results.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    main(args.bundle, args.out)
