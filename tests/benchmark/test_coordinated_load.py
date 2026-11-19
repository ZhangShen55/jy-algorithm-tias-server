"""协调丢失/错误窗口、错误分片和遗留进程必须被真实CPU HTTP检查捕获。"""
import contextlib
import http.server
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'scripts/benchmark/coordinated_load.py'


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        time.sleep(self.server.reply_delay)
        status = self.server.reply_status
        body = json.dumps({'Response': {'ErrCode': 0}, 'TaskResult': [{}]}).encode()
        self.send_response(status)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def servers(status=200, delay=0):
    running = []
    try:
        for _ in range(2):
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.reply_status = status
            server.reply_delay = delay
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            running.append((server, thread))
        yield [f'http://127.0.0.1:{s.server_port}' for s, _ in running]
    finally:
        for server, thread in running:
            server.shutdown()
            server.server_close()
            thread.join()


class CoordinatedLoadTests(unittest.TestCase):
    def command(self, directory, urls, processes=2, seconds=.65, rate=8):
        payload = directory/'payloads'
        if not payload.exists():
            payload.mkdir()
            for i in range(8):
                (payload/f'{i}.json').write_text(json.dumps({'ImageList': [{'ImageID': str(i)}]}))
        output = directory/f'load-{processes}'
        return [sys.executable, str(SCRIPT), '--urls', *urls, '--endpoint', '/AE/SyncTasks2',
                '--payload', str(payload), '--output', str(output), '--processes', str(processes),
                '--concurrency', '4', '--seconds', str(seconds), '--rate', str(rate),
                '--seed', '20261118', '--ready-timeout', '5', '--timeout', '2'], output

    def test_open_loop_has_one_global_schedule_and_matching_images(self):
        # 如果两个进程各自从0编号/同相发送或窗口独立，本检查失败。
        with tempfile.TemporaryDirectory() as temporary, servers() as urls:
            root = Path(temporary)
            maps = []
            for count in (1, 2):
                command, output = self.command(root, urls, count)
                result = subprocess.run(command, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = [json.loads(s) for s in (output/'requests.jsonl').read_text().splitlines()]
                rows.sort(key=lambda r: r['sequence'])
                self.assertEqual([r['sequence'] for r in rows], [0, 1, 2, 3, 4, 5])
                for row, planned in zip(rows, [0, .125, .25, .375, .5, .625]):
                    self.assertAlmostEqual(row['planned_offset_s'], planned, places=6)
                    self.assertGreaterEqual(row['sent_offset_s'], planned-1e-6)
                maps.append([r['image_id'] for r in rows])
                summary = json.loads((output/'summary.json').read_text())
                self.assertEqual((summary['requests'], summary['successful'], summary['failed']), (6, 6, 0))
                self.assertEqual(summary['total_concurrency'], 4)
                self.assertEqual(summary['send_window_s'], .65)
                self.assertTrue(summary['mode'].startswith('open_loop'), '离线时间线必须识别开放式模式')
                latencies = sorted(row['latency_ms'] for row in rows)
                self.assertAlmostEqual(summary['successful_image_latency_ms']['p95'],
                                       latencies[4]*.25+latencies[5]*.75)
                self.assertEqual(len({json.loads((output/f'shard-{i}/summary.json').read_text())['started_unix_time'] for i in range(count)}), 1)
            self.assertEqual(maps[0], maps[1])

    def test_http_rejections_remain_in_pooled_results(self):
        with tempfile.TemporaryDirectory() as temporary, servers(429) as urls:
            command, output = self.command(Path(temporary), urls)
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((output/'summary.json').read_text())
            self.assertEqual((summary['requests'], summary['successful'], summary['failed']), (6, 0, 6))
            self.assertEqual(summary['status_counts'], {'429': 6})

    def test_generator_protection_keeps_every_global_slot_without_fake_http(self):
        with tempfile.TemporaryDirectory() as temporary, servers(delay=.15) as urls:
            command, output = self.command(Path(temporary), urls, rate=40)
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(s) for s in (output/'requests.jsonl').read_text().splitlines()]
            self.assertEqual(sorted(r['sequence'] for r in rows), list(range(26)))
            dropped = [r for r in rows if r.get('error') == 'load_generator_inflight_limit']
            self.assertGreater(len(dropped), 0)
            self.assertTrue(all('sent_offset_s' not in r and r['status'] is None for r in dropped))
            summary = json.loads((output/'summary.json').read_text())
            self.assertEqual(summary['generator_limit_events'], len(dropped))
            self.assertEqual(summary['failed'], len(dropped))
            self.assertEqual(summary['requests'], 26)

    def test_uneven_partition_is_rejected_before_workers_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            command, output = self.command(Path(temporary), ['http://127.0.0.1:1'])
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('均匀分片', result.stderr)
            self.assertFalse((output/'workers.json').exists())

    def test_termination_reaps_owned_workers(self):
        with tempfile.TemporaryDirectory() as temporary, servers() as urls:
            command, output = self.command(Path(temporary), urls, seconds=30, rate=8)
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                deadline = time.monotonic()+8
                while not (output/'control/start.json').exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue((output/'control/start.json').exists(), '协调起点未发布')
                workers = json.loads((output/'workers.json').read_text())
                process.send_signal(signal.SIGTERM)
                process.communicate(timeout=8)
                self.assertNotEqual(process.returncode, 0)
                for worker in workers:
                    with self.assertRaises(ProcessLookupError):
                        os.kill(worker['pid'], 0)
                self.assertFalse((output/'summary.json').exists())

    def test_closed_loop_and_original_default_both_collect_requests(self):
        with tempfile.TemporaryDirectory() as temporary, servers() as urls:
            root = Path(temporary)
            command, output = self.command(root, urls, seconds=.2, rate=0)
            result = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((output/'summary.json').read_text())
            self.assertGreater(summary['successful'], 0)
            self.assertEqual(summary['failed'], 0)
            rows = [json.loads(s) for s in (output/'requests.jsonl').read_text().splitlines()]
            self.assertEqual(len({r['sequence'] for r in rows}), len(rows))
            # 普通load仍可独立执行，无新屏障文件/分片参数，也不生成协调元数据。
            ordinary = root/'ordinary'
            legacy = [sys.executable, str(ROOT/'scripts/benchmark/load.py'), '--urls', *urls,
                      '--endpoint', '/AE/SyncTasks2', '--payload', str(root/'payloads'),
                      '--output', str(ordinary), '--concurrency', '2', '--seconds', '.2']
            result = subprocess.run(legacy, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((ordinary/'summary.json').read_text())
            self.assertGreater(summary['successful'], 0)
            self.assertNotIn('coordinated_shard', summary)

    def test_startup_failure_preserves_evidence_and_reaps_workers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command, output = self.command(root, ['http://127.0.0.1:1', 'http://127.0.0.1:2'])
            (root/'payloads/0.json').write_text('invalid JSON')
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((output/'coordination-error.json').exists())
            self.assertFalse((output/'summary.json').exists())
            for worker in json.loads((output/'workers.json').read_text()):
                with self.assertRaises(ProcessLookupError):
                    os.kill(worker['pid'], 0)

    def test_manager_rejects_audit_and_uneven_partitions_before_gpu_work(self):
        manager = str(ROOT/'scripts/benchmark/instances.py')
        base = [sys.executable, manager, '--output', '/does-not-exist', '--payload', '/does-not-exist',
                '--endpoint', '/AE/SyncTasks2', '--load-processes', '2']
        for extra in (['--instances', '3'], ['--audit-reference', '/does-not-exist']):
            result = subprocess.run(base+extra, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('协调', result.stderr)


if __name__ == '__main__':
    unittest.main()
