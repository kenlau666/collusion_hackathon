"""One bounded HTTP diagnostic against the configured endpoint; no redirects.

The parent supplies credentials in its private environment and kills/reaps this
process at the whole-request deadline. Progress contains phases/counts only.
"""
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit

import certifi

BASE_URL = 'https://kenlauhong2015--ep-deepseek-v4-1-flash-server.us-west.modal.direct/v1'
LIMIT = 4 * 1024 * 1024


class Trace:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.start = time.monotonic()
        self.value = {'stage': 'validate', 'events': [], 'body_bytes': 0, 'frames': 0}

    def mark(self, stage, **values):
        self.value.update(stage=stage, **values)
        self.value['events'].append({'stage': stage, 'elapsed_seconds': time.monotonic() - self.start})
        self.save()

    def save(self):
        if self.path:
            temporary = self.path.with_suffix('.pending')
            temporary.write_text(json.dumps(self.value, allow_nan=False) + '\n')
            os.replace(temporary, self.path)


def assemble(frames, done):
    """Reconstruct OpenAI-compatible streamed deltas without dropping tool data."""
    if not done:
        raise ValueError('missing stream terminator')
    message = {'role': 'assistant', 'content': ''}
    tools, usage, response_id, model, finish = {}, None, None, None, None
    for frame in frames:
        if frame.get('id'):
            if response_id is not None and response_id != frame['id']:
                raise ValueError('mixed stream ids')
            response_id = frame['id']
        if frame.get('model'):
            if model is not None and model != frame['model']:
                raise ValueError('mixed stream models')
            model = frame['model']
        if frame.get('usage') is not None:
            usage = frame['usage']
        for choice in frame.get('choices', []):
            if choice.get('index', 0) != 0:
                raise ValueError('unexpected multiple choices')
            delta = choice.get('delta') or {}
            for field in ('content', 'reasoning_content', 'reasoning'):
                if delta.get(field) is not None:
                    message[field] = message.get(field, '') + delta[field]
            for fragment in delta.get('tool_calls') or []:
                index = fragment['index']
                target = tools.setdefault(index, {'id': '', 'type': 'function',
                    'function': {'name': '', 'arguments': ''}})
                if fragment.get('id'):
                    target['id'] += fragment['id']
                if fragment.get('type'):
                    target['type'] = fragment['type']
                for field in ('name', 'arguments'):
                    target['function'][field] += (fragment.get('function') or {}).get(field) or ''
            if choice.get('finish_reason') is not None:
                finish = choice['finish_reason']
    if not response_id or not model or finish is None or usage is None:
        raise ValueError('incomplete stream metadata')
    if tools:
        message['tool_calls'] = [tools[i] for i in sorted(tools)]
    return {'id': response_id, 'model': model, 'choices': [{'index': 0,
        'message': message, 'finish_reason': finish}], 'usage': usage}


def perform(data, headers, trace):
    conn = sock = None
    try:
        method, path, payload = data['method'], data['path'], data.get('payload')
        if data['base_url'] != BASE_URL or method not in {'GET', 'POST'}:
            raise ValueError('unapproved route')
        if method == 'GET' and path not in {'/v1/models', '/health', '/openapi.json'}:
            raise ValueError('unapproved metadata path')
        if method == 'POST' and path != '/v1/chat/completions':
            raise ValueError('unapproved inference path')
        if set(headers) != {'Modal-Key', 'Modal-Secret'} or any(
            not isinstance(v, str) or not v or '\r' in v or '\n' in v for v in headers.values()):
            raise ValueError('invalid credential headers')
        host = urlsplit(BASE_URL).hostname
        context = ssl.create_default_context(cafile=certifi.where())
        trace.mark('dns_start')
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        trace.mark('dns_done', address_families=sorted({int(a[0]) for a in addresses}))
        last = None
        for family, kind, protocol, _, address in addresses:
            sock = socket.socket(family, kind, protocol)
            sock.settimeout(data['timeout'])
            try:
                trace.mark('tcp_connect_start')
                sock.connect(address)
                trace.mark('tcp_connected')
                break
            except OSError as error:
                last = error
                sock.close()
        else:
            raise last or OSError('no resolved addresses')
        trace.mark('tls_start')
        sock = context.wrap_socket(sock, server_hostname=host)
        trace.mark('tls_ready')
        conn = http.client.HTTPSConnection(host, timeout=data['timeout'], context=context)
        conn.sock = sock
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode() if payload is not None else None
        trace.mark('sending_request')
        conn.request(method, path, body=body,
            headers={**headers, 'Content-Type': 'application/json', 'Connection': 'close'})
        trace.mark('request_sent_waiting_headers')
        response = conn.getresponse()
        safe_headers = {k.lower(): v for k, v in response.getheaders()
            if k.lower() in {'content-type', 'content-length', 'transfer-encoding', 'server',
                             'x-request-id', 'modal-function-call-id'}}
        trace.mark('headers_received', http_status=response.status, response_headers=safe_headers)
        is_stream = bool(payload and payload.get('stream') and response.status == 200)
        raw, frames, done = bytearray(), [], False
        if is_stream:
            while True:
                line = response.readline(LIMIT + 1)
                if not line:
                    break
                raw.extend(line)
                if len(raw) > LIMIT:
                    raise ValueError('body exceeds bound')
                if trace.value['body_bytes'] == 0:
                    trace.mark('first_body_bytes')
                trace.value['body_bytes'] = len(raw)
                if line.startswith(b'data:'):
                    item = line[5:].strip()
                    if item == b'[DONE]':
                        done = True
                        trace.mark('stream_done')
                        break
                    if item:
                        frame = json.loads(item)
                        frames.append(frame)
                        trace.value['frames'] = len(frames)
                        if len(frames) == 1:
                            trace.mark('first_sse_frame')
                        if not trace.value.get('output_delta_seen') and any(
                            any((choice.get('delta') or {}).get(field)
                                for field in ('content', 'reasoning_content', 'reasoning', 'tool_calls'))
                            for choice in frame.get('choices', [])):
                            trace.mark('first_output_delta', output_delta_seen=True)
                trace.save()
            parsed = assemble(frames, done)
        else:
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                if not raw:
                    trace.mark('first_body_bytes')
                raw.extend(chunk)
                if len(raw) > LIMIT:
                    raise ValueError('body exceeds bound')
                trace.value['body_bytes'] = len(raw)
                trace.save()
            try:
                parsed = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                parsed = raw.decode('utf-8', errors='replace')
        trace.mark('complete')
        return {'kind': 'reply', 'status_code': response.status, 'body': parsed,
                'sse_frames': frames, 'sse_done': done, 'raw_body_text': raw.decode('utf-8', errors='replace')}
    except Exception as error:
        trace.mark('error', failure_phase=trace.value['stage'], exception_type=type(error).__name__)
        return {'kind': 'transport_error', 'exception_type': type(error).__name__,
                'errno': error.errno if isinstance(error, OSError) else None}
    finally:
        if conn:
            conn.close()
        elif sock:
            sock.close()


if __name__ == '__main__':
    data = json.load(sys.stdin)
    trace = Trace(os.environ.get('MODAL_PROGRESS_PATH'))
    result = perform(data, {'Modal-Key': os.environ.get('MODAL_PROXY_TOKEN_ID'),
        'Modal-Secret': os.environ.get('MODAL_PROXY_TOKEN_SECRET')}, trace)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
