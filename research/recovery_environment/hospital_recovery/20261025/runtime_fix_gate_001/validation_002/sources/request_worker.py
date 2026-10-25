"""One fixed-destination HTTP attempt; parent owns its lifetime and accounting."""
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

import certifi

CHAT_URL = 'https://openrouter.ai/api/v1/chat/completions'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def perform(payload, key, timeout, opener=None):
    stage = 'open'
    status = None
    try:
        if opener is None:
            context = ssl.create_default_context(cafile=certifi.where())
            opener = urllib.request.build_opener(
                NoRedirect(), urllib.request.HTTPSHandler(context=context))
        request = urllib.request.Request(
            CHAT_URL, data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(),
            method='POST', headers={'Authorization': 'Bearer ' + key,
                                    'Content-Type': 'application/json'})
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.code
            stage = 'read'
            raw = response.read()
        stage = 'parse'
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            body = raw.decode('utf-8', errors='replace')
        return {'kind': 'reply', 'status_code': status, 'body': body}
    except Exception as error:
        # Only class names/numeric errno; no repr, message, headers or key.
        reason = getattr(error, 'reason', None)
        number = getattr(reason, 'errno', None) or getattr(error, 'errno', None)
        return {'kind': 'transport_error', 'stage': stage, 'http_status': status,
                'exception_type': type(error).__name__,
                'cause_type': type(reason).__name__ if isinstance(reason, BaseException) else None,
                'errno': number if isinstance(number, int) and not isinstance(number, bool) else None}


def main():
    data = json.load(sys.stdin)
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise RuntimeError('missing explicit worker credential')
    result = perform(data['payload'], key, data['timeout'])
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
