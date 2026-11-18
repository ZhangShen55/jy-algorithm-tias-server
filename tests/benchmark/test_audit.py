"""无模型/无网络的审计工具回归；不替代实际 GPU 并发验证。"""
import asyncio
import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts.benchmark.audit import difference, run, workload


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pool = self.root/'pool'
        self.pool.mkdir()
        self.endpoint = '/ImageDetect/student/v1.0.0'
        self.responses = {}
        references = []
        for image_id in ['a', 'b']:
            # 只核对字节哈希，不执行图像解码或推理。
            raw = image_id.encode()
            response = {'TimeStamp': 1, 'DataList': [{'ImageId': image_id,
                        'StatusObject': {'StatusCode': 0}, 'Objects': [{'ObjectType': 100,
                        'ObjectCount': 1, 'ObjectPostList': [{'LeftTopX': 0, 'LeftTopY': 0,
                        'RightBtmX': 10, 'RightBtmY': 10}]}]}]}
            self.responses[image_id] = response
            references.append({'endpoint': self.endpoint, 'image_id': image_id, 'status': 200,
                               'image_sha256': hashlib.sha256(raw).hexdigest(),
                               'request': {'ImageList': [{'ImageId': image_id}]}, 'response': response})
            (self.pool/f'{image_id}.json').write_text(json.dumps({'ImageList': [
                {'ImageId': image_id, 'StoragePath': base64.b64encode(raw).decode()}]}))
        self.reference = self.root/'reference.jsonl'
        self.reference.write_text(''.join(json.dumps(r)+'\n' for r in references))

    def test_values_and_geometry_are_not_hidden_by_timing_filter(self):
        expected = self.responses['a']
        actual = copy.deepcopy(expected)
        actual['TimeStamp'] = 2
        self.assertTrue(difference(expected, actual)['strict_equal_ignoring_timing_capacity_order'])
        obj = actual['DataList'][0]['Objects'][0]
        obj['ObjectCount'] = 2
        obj['ObjectPostList'][0]['RightBtmX'] = 11
        result = difference(expected, actual)
        self.assertFalse(result['strict_equal_ignoring_timing_capacity_order'])
        self.assertEqual(result['count_deltas'], {'ObjectType:100': 1})
        self.assertEqual(result['business_geometry']['ObjectType:100']['max_coordinate_delta'], 1)

    def test_image_bytes_and_coverage_must_match_reference(self):
        self.assertEqual(len(workload(self.reference, self.pool, self.endpoint)), 2)
        (self.pool/'b.json').unlink()
        with self.assertRaises(ValueError):
            workload(self.reference, self.pool, self.endpoint)
        path = self.pool/'a.json'
        body = json.loads(path.read_text())
        body['ImageList'][0]['StoragePath'] = base64.b64encode(b'changed').decode()
        path.write_text(json.dumps(body))
        with self.assertRaises(ValueError):
            workload(self.reference, self.pool, self.endpoint)

    def invoke(self, fail):
        responses = self.responses
        class Client:
            active = peak = 0
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def post(self, url, json):
                Client.active += 1
                Client.peak = max(Client.peak, Client.active)
                await asyncio.sleep(0)
                Client.active -= 1
                body = copy.deepcopy(responses[json['ImageList'][0]['ImageId']])
                body['TimeStamp'] = 999
                return types.SimpleNamespace(status_code=500 if fail else 200, json=lambda: body)
        args = types.SimpleNamespace(reference=self.reference, payload=self.pool,
                    endpoint=self.endpoint, output=self.root/'output', urls=['http://a', 'http://b'],
                    concurrency=2, repetitions=3, seed=1, timeout=60)
        fake = types.SimpleNamespace(AsyncClient=Client, Limits=lambda **kwargs: None)
        with patch.dict('sys.modules', {'httpx': fake}), contextlib.redirect_stdout(io.StringIO()):
            if fail:
                with self.assertRaises(SystemExit) as caught:
                    asyncio.run(run(args))
                self.assertEqual(caught.exception.code, 1)
            else:
                asyncio.run(run(args))
        return json.loads((args.output/'summary.json').read_text()), Client.peak

    def test_concurrent_capture_covers_every_image_and_repeat(self):
        result, peak = self.invoke(False)
        self.assertEqual(peak, 2)
        self.assertEqual(result['completed_calls'], 6)
        self.assertEqual(result['strict_equal_calls'], 6)
        self.assertEqual(result['http_or_business_failures'], 0)
        self.assertEqual(result['unattempted_calls'], 0)
        self.assertEqual(set(result['calls_per_instance']), {'http://a', 'http://b'})

    def test_http_failure_stops_new_work_and_preserves_incomplete_status(self):
        result, _ = self.invoke(True)
        self.assertGreater(result['http_or_business_failures'], 0)
        self.assertGreater(result['unattempted_calls'], 0)
        self.assertEqual(result['strict_equal_calls'], 0)


if __name__ == '__main__':
    unittest.main()
