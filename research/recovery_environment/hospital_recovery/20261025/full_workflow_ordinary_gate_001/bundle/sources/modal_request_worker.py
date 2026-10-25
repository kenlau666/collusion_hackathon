"""One whitelisted Modal HTTP attempt; the parent supervises and reaps it."""
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

import certifi

BASE_URL = 'https://kenlauhong2015--ep-deepseek-v4-1-flash-server.us-west.modal.direct/v1'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def perform(payload, base_url, headers, timeout, opener=None):
    stage, status = 'validate', None
    try:
        if base_url != BASE_URL:
            raise ValueError('endpoint outside configured whitelist')
        if set(headers) != {'Modal-Key', 'Modal-Secret'} or any(
                not isinstance(v, str) or not v or '\r' in v or '\n' in v for v in headers.values()):
            raise ValueError('invalid proxy credentials')
        if opener is None:
            context = ssl.create_default_context(cafile=certifi.where())
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=context))
        request = urllib.request.Request(base_url + '/chat/completions',
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(), method='POST',
            headers={**headers, 'Content-Type': 'application/json'})
        stage = 'open'
        try:
            response = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status, stage = response.code, 'read'
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError('response body exceeds local bound')
        stage = 'parse'
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            body = raw.decode('utf-8', errors='replace')
        return {'kind': 'reply', 'status_code': status, 'body': body}
    except Exception as error:
        reason = getattr(error, 'reason', None)
        number = getattr(reason, 'errno', None) or getattr(error, 'errno', None)
        return {'kind': 'transport_error', 'stage': stage, 'http_status': status,
            'exception_type': type(error).__name__,
            'cause_type': type(reason).__name__ if isinstance(reason, BaseException) else None,
            'errno': number if type(number) is int else None}


def main():
    data = json.load(sys.stdin)
    result = perform(data['payload'], os.environ.get('MODAL_ENDPOINT_BASE_URL'),
        {'Modal-Key': os.environ.get('MODAL_PROXY_TOKEN_ID'),
         'Modal-Secret': os.environ.get('MODAL_PROXY_TOKEN_SECRET')}, data['timeout'])
    sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
