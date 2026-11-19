"""单/双发生器独立诊断：统一起点、分片端口，合并原始请求而非分位数。"""
import argparse
import asyncio
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time


async def wait_for_start(args):
    """在load的输入和HTTP客户端初始化后才宣布ready。"""
    control = args.coordination_dir
    pending = control/f'ready-{args.shard_index}.pending'
    with pending.open('x') as stream:
        json.dump({'pid': os.getpid(), 'shard': args.shard_index}, stream)
    pending.rename(control/f'ready-{args.shard_index}.json')
    deadline = time.monotonic()+args.ready_timeout
    start_file = control/'start.json'
    while not start_file.exists():
        if time.monotonic() > deadline:
            raise TimeoutError('协调起点未发布')
        await asyncio.sleep(.01)
    start = json.loads(start_file.read_text())
    if start['shard_count'] != args.shard_count:
        raise ValueError('协调分片数量不一致')
    await asyncio.sleep(max(0, start['perf_counter']-time.perf_counter()))
    return start['perf_counter'], start['unix_time']


def merge(args, control):
    try:
        from .load import percentile
    except ImportError:
        from load import percentile
    records, summaries, sources = [], [], {}
    seen = set()
    for shard in range(args.processes):
        directory = args.output/f'shard-{shard}'
        summary = json.loads((directory/'summary.json').read_text())
        rows = [json.loads(line) for line in (directory/'requests.jsonl').read_text().splitlines()]
        valid = [r for r in rows if r['valid']]
        if (len(rows), len(valid), len(rows)-len(valid)) != (summary['requests'], summary['successful'], summary['failed']):
            raise ValueError('分片原始计数与摘要不一致')
        if summary['started_unix_time'] != control['unix_time'] or summary['send_window_s'] != args.seconds:
            raise ValueError('不能合并不同正式窗口')
        if summary.get('coordinated_shard') != {'index': shard, 'count': args.processes}:
            raise ValueError('分片身份不一致')
        if summary['total_concurrency'] != args.concurrency//args.processes or summary['instances'] != len(args.urls)//args.processes:
            raise ValueError('分片实例或并发不一致')
        if summary['payload_seed'] != args.seed or summary['target_images_per_s'] != (args.rate/args.processes or None):
            raise ValueError('分片输入种子或速率不一致')
        for row in rows:
            number = row['sequence']
            if number in seen or number % args.processes != shard:
                raise ValueError('重复或归属错误的全局序号')
            seen.add(number)
            if args.rate and not math.isclose(row['planned_offset_s'], number/args.rate, abs_tol=1e-7):
                raise ValueError('全局计划相位不一致')
            records.append({**row, 'shard_index': shard})
        summaries.append(summary)
        for name in ('requests.jsonl', 'summary.json'):
            path = directory/name
            sources[str(path.relative_to(args.output))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.rate:
        expected = set(range(math.ceil(args.rate*args.seconds)))
        if seen != expected:
            raise ValueError('计划槽覆盖不完整')
    successful = [r for r in records if r['valid']]
    latencies = [r['latency_ms'] for r in successful]
    elapsed = max(s['elapsed_including_drain_s'] for s in summaries)
    result = {
        'mode': 'open_loop_single_image_http' if args.rate else 'closed_loop_single_image_http',
        'endpoint': args.endpoint, 'instances': len(args.urls), 'total_concurrency': args.concurrency,
        'load_processes': args.processes, 'payload_count': summaries[0]['payload_count'], 'payload_seed': args.seed,
        'target_images_per_s': args.rate or None, 'started_unix_time': control['unix_time'],
        'send_window_s': args.seconds, 'elapsed_including_drain_s': elapsed,
        'requests': len(records), 'successful': len(successful), 'failed': len(records)-len(successful),
        'generator_limit_events': sum(r.get('error') == 'load_generator_inflight_limit' for r in records),
        'success_images_per_s_in_window': sum(r['completed_offset_s'] <= args.seconds for r in successful)/args.seconds,
        'success_images_per_s_including_drain': len(successful)/elapsed,
        'successful_image_latency_ms': {'p50': percentile(latencies, .5), 'p95': percentile(latencies, .95),
                                      'p99': percentile(latencies, .99), 'mean': statistics.mean(latencies) if latencies else None},
        'scheduled_latency_ms_p95': percentile([r['latency_from_schedule_ms'] for r in successful if 'latency_from_schedule_ms' in r], .95),
        'all_request_latency_ms_p95': percentile([r['latency_ms'] for r in records], .95),
        'status_counts': dict(collections.Counter(str(r['status']) for r in records)),
        'dispatch': 'disjoint_instance_shards_interleaved_global_sequences_no_retry',
        'source_sha256': sources, 'warmup': 'must_be_performed_separately',
        'resource_metrics': 'must_be_collected_separately',
    }
    with (args.output/'requests.jsonl').open('x') as stream:
        for row in sorted(records, key=lambda r: (r.get('completed_offset_s', r.get('planned_offset_s', 0)), r['sequence'])):
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
    with (args.output/'summary.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    return result


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    control_dir = args.output/'control'
    control_dir.mkdir()
    workers, logs = [], []
    load_script = Path(__file__).with_name('load.py')
    manifest = {'python': sys.executable, 'urls': args.urls, 'processes': args.processes,
                'concurrency': args.concurrency, 'rate': args.rate, 'seconds': args.seconds,
                'seed': args.seed, 'timeout': args.timeout,
                'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (load_script, Path(__file__))}}
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2))
    try:
        width = len(args.urls)//args.processes
        for shard in range(args.processes):
            log = (args.output/f'shard-{shard}.log').open('x')
            logs.append(log)
            command = [sys.executable, str(load_script), '--urls', *args.urls[shard*width:(shard+1)*width],
                       '--endpoint', args.endpoint, '--payload', str(args.payload), '--output', str(args.output/f'shard-{shard}'),
                       '--concurrency', str(args.concurrency//args.processes), '--seconds', str(args.seconds),
                       '--rate', str(args.rate/args.processes), '--seed', str(args.seed), '--timeout', str(args.timeout),
                       '--coordination-dir', str(control_dir), '--shard-index', str(shard), '--shard-count', str(args.processes),
                       '--ready-timeout', str(args.ready_timeout+5)]
            workers.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT))
        worker_list = args.output/'workers.pending'
        worker_list.write_text(json.dumps([{'shard': i, 'pid': p.pid} for i, p in enumerate(workers)]))
        worker_list.rename(args.output/'workers.json')
        deadline = time.monotonic()+args.ready_timeout
        while not all((control_dir/f'ready-{i}.json').exists() for i in range(args.processes)):
            if any(p.poll() is not None for p in workers):
                raise RuntimeError('发生器在ready前退出；查看shard日志')
            if time.monotonic() > deadline:
                raise TimeoutError('发生器ready超时')
            time.sleep(.01)
        for i, process in enumerate(workers):
            if json.loads((control_dir/f'ready-{i}.json').read_text())['pid'] != process.pid:
                raise ValueError('ready进程身份错误')
        now = time.perf_counter()
        control = {'perf_counter': now+.5, 'unix_time': time.time()+.5, 'shard_count': args.processes}
        temporary = control_dir/'start.pending'
        temporary.write_text(json.dumps(control))
        temporary.rename(control_dir/'start.json')
        # 开放式可能追赶迟发计划，给定窗口、超时之外再留有界协调余量。
        deadline = control['perf_counter']+args.seconds+args.timeout+60
        while any(p.poll() is None for p in workers):
            if any(p.returncode not in (None, 0) for p in workers):
                raise RuntimeError('发生器非零退出；保留分片证据')
            if time.perf_counter() > deadline:
                raise TimeoutError('发生器排空超过有界等待')
            time.sleep(.02)
        if any(p.returncode != 0 for p in workers):
            raise RuntimeError('发生器失败')
        return merge(args, control)
    except BaseException as exc:
        (args.output/'coordination-error.json').write_text(json.dumps({'error': repr(exc), 'unix_time': time.time()}))
        raise
    finally:
        for process in workers:
            if process.poll() is None:
                process.terminate()
        for process in workers:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--urls', nargs='+', required=True)
    parser.add_argument('--endpoint', choices=['/AE/SyncTasks2', '/ImageDetect/student/v1.0.0', '/ImageDetect/teacher/v1.0.0'], required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--processes', type=int, choices=[1, 2], required=True)
    parser.add_argument('--concurrency', type=int, required=True)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--rate', type=float, default=0)
    parser.add_argument('--seed', type=int, default=20261118)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--ready-timeout', type=float, default=60)
    args = parser.parse_args()
    args.urls = [url.rstrip('/') for url in args.urls]
    if (len(set(args.urls)) != len(args.urls) or len(args.urls) % args.processes or
            args.concurrency < args.processes or args.concurrency % args.processes):
        parser.error('端口必须唯一，实例与总并发必须可均匀分片')
    if not all(math.isfinite(v) for v in (args.seconds, args.rate, args.timeout, args.ready_timeout)) or min(args.seconds, args.timeout, args.ready_timeout) <= 0 or args.rate < 0:
        parser.error('无效时长、速率或超时')
    args.payload, args.output = args.payload.resolve(), args.output.resolve()
    def terminate(signum, frame):
        raise KeyboardInterrupt(f'coordinator signal {signum}')
    signal.signal(signal.SIGTERM, terminate)
    print(json.dumps(run(args)))


if __name__ == '__main__':
    main()
