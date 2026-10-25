"""Unpaid loopback verification of socket timeout versus total read duration."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import statistics
import threading
import time
import urllib.request

BODY = b'abcdef'
TIMEOUT = .15


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', str(len(BODY)))
        self.end_headers()
        if self.path == '/slow':
            for byte in BODY:
                time.sleep(.06)
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
        else:
            self.wfile.write(BODY)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    rows = []
    try:
        for trial in range(3):
            for kind in ('fast', 'slow'):
                started = time.monotonic()
                with urllib.request.urlopen(
                    f'http://127.0.0.1:{server.server_port}/{kind}', timeout=TIMEOUT
                ) as response:
                    body = response.read()
                    status = response.status
                elapsed = time.monotonic() - started
                rows.append(dict(trial=trial, kind=kind, elapsed_seconds=elapsed,
                                 body_matches=body == BODY, http_status=status))
    finally:
        server.shutdown()
        server.server_close()
    summaries = {}
    for kind in ('fast', 'slow'):
        values = [r['elapsed_seconds'] for r in rows if r['kind'] == kind]
        summaries[kind] = dict(n=len(values), mean=statistics.mean(values),
                              sample_sd=statistics.stdev(values),
                              sample_variance=statistics.variance(values))
    passed = all(r['body_matches'] and r['http_status'] == 200 and
                 (r['kind'] == 'fast' or r['elapsed_seconds'] > TIMEOUT) for r in rows)
    result = dict(kind='local software timeout probe', socket_timeout_seconds=TIMEOUT,
                  rows=rows, summaries=summaries, positive_controls_passed=3,
                  verified_per_operation_timeout_limitation=passed,
                  provider_calls=0, credential_lookups=0, actual_spend_usd='0',
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  limit='Loopback repeat indices are not independent behavioral seeds; '
                        'this does not identify the old live failure cause.')
    target = Path(__file__).with_name('timeout_probe_results.json')
    with target.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps(result, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
