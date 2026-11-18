"""HTTP时间线核心逻辑的无模型回归。"""
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import quote

from scripts.benchmark.timing import HTTPTiming, span, timed


class TimingTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'trace.jsonl'

    def tracer(self, app):
        value = HTTPTiming(app, self.path)
        self.addCleanup(value.close)
        return value

    async def invoke(self, app, image='a', path='/AE/SyncTasks2'):
        sent = []
        async def receive():
            return {'type': 'http.request', 'body': b'abc'}
        async def send(message):
            sent.append(message)
        await app({'type': 'http', 'path': path, 'headers': [
            (b'x-benchmark-sequence', b'7'), (b'x-benchmark-image-id', quote(image, safe='/').encode())]}, receive, send)
        return sent

    async def test_wire_preserved_and_thread_context_propagates(self):
        @timed_function
        def task():
            return 42
        async def app(scope, receive, send):
            await receive()
            self.assertEqual(await asyncio.to_thread(task), 42)
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'{}'})
        tracer = self.tracer(app)
        self.assertEqual((await self.invoke(tracer))[-1]['body'], b'{}')
        row = json.loads(self.path.read_text())
        self.assertEqual((row['image_id'], row['client_sequence'], row['status']), ('a', '7', 200))
        self.assertEqual((row['input_body_bytes'], row['response_body_bytes']), (3, 2))
        child = next(s for s in row['spans'] if s['name'] == 'threaded')
        self.assertNotEqual(child['thread_id'], threading.get_ident())

    async def test_concurrent_requests_do_not_share_identity_or_spans(self):
        async def app(scope, receive, send):
            with span('business-'+dict(scope['headers'])[b'x-benchmark-image-id'].decode()):
                await asyncio.sleep(0)
            await send({'type': 'http.response.start', 'status': 200})
            await send({'type': 'http.response.body', 'body': b'{}'})
        tracer = self.tracer(app)
        await asyncio.gather(self.invoke(tracer, 'a'), self.invoke(tracer, 'b'))
        rows = [json.loads(line) for line in self.path.read_text().splitlines()]
        self.assertEqual(len({r['request_id'] for r in rows}), 2)
        for row in rows:
            self.assertEqual([s['name'] for s in row['spans'] if s['name'].startswith('business-')], ['business-'+row['image_id']])

    async def test_exception_is_preserved_and_untracked_route_is_skipped(self):
        async def app(scope, receive, send):
            raise ValueError('test')
        tracer = self.tracer(app)
        with self.assertRaises(ValueError):
            await self.invoke(tracer, path='/openapi.json')
        self.assertEqual(self.path.read_text(), '')
        with self.assertRaises(ValueError):
            await self.invoke(tracer)
        self.assertEqual(json.loads(self.path.read_text())['error_type'], 'ValueError')

    async def test_existing_evidence_is_not_overwritten(self):
        self.path.write_text('original')
        with self.assertRaises(FileExistsError):
            HTTPTiming(None, self.path)
        self.assertEqual(self.path.read_text(), 'original')

    async def test_unicode_image_identifier_round_trips(self):
        async def app(scope, receive, send):
            await send({'type': 'http.response.start', 'status': 200})
            await send({'type': 'http.response.body', 'body': b'{}'})
        await self.invoke(self.tracer(app), image='学生/a%.jpg')
        self.assertEqual(json.loads(self.path.read_text())['image_id'], '学生/a%.jpg')


def timed_function(function):
    return timed(function, 'threaded')


if __name__ == '__main__':
    unittest.main()
