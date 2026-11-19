"""错误分层和真实CPU连接复位证据；不证明历史C256的具体TCP根因。"""
import base64
import contextlib
import errno
import hashlib
import http.server
import importlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ResetHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        self.connection.close()
        self.close_connection = True

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def reset_server():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), ResetHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class ErrorEvidenceTests(unittest.TestCase):
    def details(self, exc):
        try:
            module = importlib.import_module('scripts.benchmark.errors')
        except ModuleNotFoundError:
            self.fail('缺少有界异常链采集')
        return module.exception_details(exc)

    def test_underlying_os_error_is_retained_without_changing_the_exception(self):
        cause = ConnectionResetError(errno.ECONNRESET, 'Connection reset by peer')
        top = RuntimeError('read failed')
        top.__cause__ = cause
        result = self.details(top)
        self.assertEqual([x['type'] for x in result['error_chain']],
                         ['builtins.RuntimeError', 'builtins.ConnectionResetError'])
        self.assertEqual(result['error_chain'][1]['errno'], errno.ECONNRESET)
        self.assertTrue(result['os_errno_available'])
        self.assertEqual(result['error_chain'][1]['relation'], 'cause')
        self.assertEqual(repr(top), "RuntimeError('read failed')")
        self.assertIs(top.__cause__, cause)

    def test_cycles_and_long_chains_are_bounded(self):
        cycle = RuntimeError('cycle')
        cycle.__cause__ = cycle
        result = self.details(cycle)
        self.assertEqual(len(result['error_chain']), 1)
        self.assertTrue(result['error_chain_truncated'])
        head = RuntimeError('head')
        for _ in range(20):
            parent = RuntimeError('parent')
            parent.__cause__ = head
            head = parent
        result = self.details(head)
        self.assertEqual(len(result['error_chain']), 8)
        self.assertTrue(result['error_chain_truncated'])

    def test_suppressed_context_is_not_exposed(self):
        exc = RuntimeError('public')
        exc.__context__ = ValueError('suppressed context')
        exc.__suppress_context__ = True
        result = self.details(exc)
        self.assertEqual(len(result['error_chain']), 1)
        self.assertNotIn('suppressed context', json.dumps(result))

    def test_large_error_text_is_bounded(self):
        exc = RuntimeError('x'*10000)
        result = self.details(exc)
        self.assertLessEqual(len(result['error_chain'][0]['repr']), 1000)
        self.assertTrue(result['error_chain'][0]['repr_truncated'])
        self.assertEqual(len(exc.args[0]), 10000)

    def test_exception_argument_keeps_its_os_error(self):
        cause = ConnectionResetError(errno.ECONNRESET, 'Connection reset by peer')
        result = self.details(RuntimeError(cause))
        self.assertEqual(result['error_chain'][1]['relation'], 'argument')
        self.assertEqual(result['error_chain'][1]['errno'], errno.ECONNRESET)

    def invoke(self, audit):
        with tempfile.TemporaryDirectory() as temporary, reset_server() as url:
            root = Path(temporary)
            payload = root/'payload'
            payload.mkdir()
            raw = b'synthetic input, no photo'
            (payload/'one.json').write_text(json.dumps({'ImageList': [{'ImageID': 'synthetic',
                                                     'Data': base64.b64encode(raw).decode()}]}))
            out = root/'output'
            command = [sys.executable, str(ROOT/f'scripts/benchmark/{"audit" if audit else "load"}.py'),
                       '--urls', url, '--endpoint', '/AE/SyncTasks2', '--payload', str(payload),
                       '--output', str(out), '--concurrency', '1', '--timeout', '2']
            if audit:
                reference = root/'reference.jsonl'
                reference.write_text(json.dumps({'endpoint': '/AE/SyncTasks2', 'image_id': 'synthetic',
                    'status': 200, 'image_sha256': hashlib.sha256(raw).hexdigest(),
                    'request': {'ImageList': [{'ImageID': 'synthetic'}]},
                    'response': {'Response': {'ErrCode': 0}, 'TaskResult': [{}]}})+'\n')
                command += ['--reference', str(reference), '--repetitions', '3']
            else:
                command += ['--rate', '1', '--seconds', '.1']
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1 if audit else 0, result.stderr)
            rows = [json.loads(s) for s in (out/('responses.jsonl' if audit else 'requests.jsonl')).read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertFalse(row['valid'])
            self.assertIsNone(row['status'])
            self.assertGreaterEqual(row['latency_ms'], 0)
            chain = row.get('error_chain', [])
            self.assertTrue(any(x['type'].endswith('.BrokenResourceError') or x.get('errno') == errno.ECONNRESET
                                for x in chain), row)
            # 部分AnyIO版本raise ... from None会丢弃原errno，不能凭已知fixture补造。
            self.assertEqual(row['os_errno_available'], any('errno' in x for x in chain))
            if row['os_errno_available']:
                self.assertTrue(any(x.get('errno') == errno.ECONNRESET for x in chain), row)
            if audit:
                summary = json.loads((out/'summary.json').read_text())
                self.assertEqual(summary['unattempted_calls'], 2)

    def test_load_preserves_available_reset_layers(self):
        self.invoke(False)

    def test_audit_keeps_reset_layers_and_stops_new_dispatch(self):
        self.invoke(True)


if __name__ == '__main__':
    unittest.main()
