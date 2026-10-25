"""Read-only endpoint capacity discovery: no generation or account mutations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

import certifi
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
BASE = 'https://kenlauhong2015--ep-deepseek-v4-1-flash-server.us-west.modal.direct'
MODEL = 'deepseek-ai/DeepSeek-V4.1-Flash'
CASES = [
    {'id': 'models-positive', 'method': 'GET', 'path': '/v1/models', 'payload': None},
    {'id': 'model-info', 'method': 'GET', 'path': '/get_model_info', 'payload': None},
    {'id': 'tokenizer-list', 'method': 'GET', 'path': '/v1/tokenizers', 'payload': None},
    {'id': 'gateway-tokenize', 'method': 'POST', 'path': '/v1/tokenize',
     'payload': {'model': MODEL, 'prompt': 'capacity_probe'}},
    {'id': 'native-tokenize', 'method': 'POST', 'path': '/tokenize',
     'payload': {'text': 'capacity_probe', 'add_special_tokens': False}},
]


def save(path, value):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')
    os.replace(temporary, path)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def worker(index):
    case = CASES[index]
    headers = {'Modal-Key': os.environ['MODAL_PROXY_TOKEN_ID'],
               'Modal-Secret': os.environ['MODAL_PROXY_TOKEN_SECRET']}
    assert all(v and '\r' not in v and '\n' not in v for v in headers.values())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
    data = json.dumps(case['payload']).encode() if case['payload'] is not None else None
    request = urllib.request.Request(BASE+case['path'], data=data, method=case['method'],
        headers={**headers, 'Content-Type': 'application/json'})
    try:
        try:
            response = opener.open(request, timeout=12)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(512*1024+1)
            assert len(raw) <= 512*1024
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                body = {'non_json_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            return {'http_status': response.code, 'body': body}
    except Exception as error:
        return {'transport_error': type(error).__name__}


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save(out/'plan.json', {'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': source_hash, 'cases': CASES, 'inference_calls': 0,
        'positive_control': 'GET models returns HTTP200 and the configured model ID',
        'tokenize_positive': 'HTTP200 with nonempty integer tokens or token_ids and a matching count',
        'budget': 'No generation route; five read-only API operations, 15s hard deadline each; actual hosting charges unknown',
        'limits': 'No tokenizer registration, deployments, account changes, or Hospital tool dispatch',
        'source_urls': [
            'https://github.com/sgl-project/sglang/blob/main/docs/docs/advanced_features/sgl_model_gateway.mdx',
            'https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/entrypoints/http_server.py'],
        'source_limit': 'Documentation motivates discovery paths; actual server implementation/version unknown'})
    values = dotenv_values(HERE.parents[2]/'compute.env')
    assert values.get('MODAL_ENDPOINT_BASE_URL', '').rstrip('/') == BASE+'/v1'
    assert values.get('MODAL_ENDPOINT_MODEL') == MODEL
    credentials = {k: values[k] for k in ('MODAL_PROXY_TOKEN_ID', 'MODAL_PROXY_TOKEN_SECRET')}
    rows = []
    for index, case in enumerate(CASES):
        save(out/(case['id']+'.attempt.json'), {'case': case, 'status': 'dispatching', 'inference': False})
        started = time.monotonic()
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(index)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env={'PATH': os.defpath, **credentials})
        try:
            output, error = child.communicate(timeout=15)
            result = json.loads(output) if child.returncode == 0 else {'worker_exit': child.returncode, 'stderr_bytes': len(error.encode())}
        except subprocess.TimeoutExpired:
            child.kill(); child.communicate(timeout=2)
            result = {'transport_error': 'WholeRequestDeadline'}
        finally:
            if child.poll() is None:
                child.kill(); child.communicate(timeout=2)
        encoded = json.dumps(result)
        for secret in credentials.values():
            encoded = encoded.replace(secret, '[REDACTED]')
        result = json.loads(encoded)
        row = {'case': case, 'result': result, 'child_reaped': child.poll() is not None,
               'elapsed_seconds': time.monotonic()-started}
        save(out/(case['id']+'.result.json'), row)
        rows.append(row)
        print(json.dumps({'id': case['id'], 'http_status': result.get('http_status'),
                          'transport_error': result.get('transport_error')}), flush=True)
        if index == 0:
            assert result.get('http_status') == 200 and MODEL in [m['id'] for m in result['body']['data']]
    positives = []
    for row in rows[3:]:
        body = row['result'].get('body', {})
        tokens = body.get('tokens', body.get('token_ids')) if isinstance(body, dict) else None
        positives.append(row['result'].get('http_status') == 200 and isinstance(tokens, list)
            and bool(tokens) and all(type(t) is int for t in tokens)
            and body.get('count', len(tokens)) == len(tokens))
    save(out/'results.json', {'Results': {'per_operation': rows, 'independent_hospital_seeds': 0,
        'positive_control_passed': True, 'tokenize_positive_passes': sum(positives),
        'tokenize_positive_denominator': 2, 'sample_sd': None, 'sample_variance': None},
        'inference_calls': 0, 'actual_hosting_charges_verified': False,
        'claim_limit': 'Endpoint capability discovery, not an LLM experiment or evidence of a safe replacement guard'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    parser.add_argument('--worker', type=int, choices=range(len(CASES)))
    args = parser.parse_args()
    if args.worker is not None:
        print(json.dumps(worker(args.worker)))
    else:
        assert args.out is not None
        main(args.out)
