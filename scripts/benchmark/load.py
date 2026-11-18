"""单接口闭环 HTTP 压测。实例独立部署；本程序不启动或终止服务。"""
import argparse
import asyncio
import collections
import json
from pathlib import Path
import statistics
import time


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values)-1)*q
    lo = int(position)
    hi = min(lo+1, len(values)-1)
    return values[lo] + (values[hi]-values[lo])*(position-lo)


async def run(args):
    import httpx
    files = sorted(args.payload.glob('*.json')) if args.payload.is_dir() else [args.payload]
    payloads = [json.loads(f.read_text()) for f in files]
    if not payloads or any(len(payload.get('ImageList', [])) != 1 for payload in payloads):
        raise ValueError('主实验要求每请求一图')
    args.output.mkdir(parents=True, exist_ok=False)
    stop = time.perf_counter()+args.seconds
    started = time.perf_counter()
    sequence = 0
    records = []
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    with (args.output / 'requests.jsonl').open('w') as out:
        async with httpx.AsyncClient(timeout=args.timeout, limits=limits, trust_env=False) as client:
            async def worker(worker_index, planned=None):
                nonlocal sequence
                while planned is not None or time.perf_counter() < stop:
                    number = sequence
                    sequence += 1
                    base = args.urls[worker_index % len(args.urls)].rstrip('/')
                    sent = time.perf_counter()
                    row = {'sequence': number, 'instance': base, 'sent_offset_s': sent-started}
                    try:
                        response = await client.post(base+args.endpoint, json=payloads[number % len(payloads)])
                        row['status'] = response.status_code
                        body = response.json()
                        # 200 只是传输成功；师生接口还必须有成功图片结果。
                        if args.endpoint.startswith('/ImageDetect/'):
                            data = body.get('DataList', [])
                            row['valid'] = response.status_code == 200 and len(data) == 1 and data[0].get('StatusObject', {}).get('StatusCode') == 0
                        else:
                            row['valid'] = response.status_code == 200 and bool(body.get('TaskResult'))
                        if not row['valid']:
                            row['error_response'] = body
                    except Exception as exc:
                        row.update(status=None, valid=False, error=repr(exc))
                    row['completed_offset_s'] = time.perf_counter()-started
                    row['latency_ms'] = (time.perf_counter()-sent)*1000
                    if planned is not None:
                        row['planned_offset_s'] = planned-started
                        row['latency_from_schedule_ms'] = (time.perf_counter()-planned)*1000
                    records.append(row)
                    out.write(json.dumps(row, ensure_ascii=False)+'\n')
                    if planned is not None:
                        return
            if not args.rate:
                await asyncio.gather(*(worker(i) for i in range(args.concurrency)))
            else:
                running = set()
                arrival = started
                index = 0
                while arrival < stop:
                    await asyncio.sleep(max(0, arrival-time.perf_counter()))
                    if len(running) >= args.concurrency:
                        row = {'status': None, 'valid': False, 'latency_ms': 0,
                               'error': 'load_generator_inflight_limit', 'planned_offset_s': arrival-started}
                        records.append(row)
                        out.write(json.dumps(row)+'\n')
                    else:
                        task = asyncio.create_task(worker(index, arrival))
                        running.add(task)
                        task.add_done_callback(running.discard)
                    index += 1
                    arrival = started+index/args.rate
                if running:
                    await asyncio.gather(*running)
    elapsed = time.perf_counter()-started
    successful = [r for r in records if r['valid']]
    latencies = [r['latency_ms'] for r in successful]
    # 窗口内完成吞吐与停止发请求后排空的耗时分别报告。
    completed_in_window = [r for r in successful if r['completed_offset_s'] <= args.seconds]
    summary = {'mode': 'open_loop_single_image_http' if args.rate else 'closed_loop_single_image_http', 'endpoint': args.endpoint,
               'instances': len(args.urls), 'total_concurrency': args.concurrency,
               'dispatch': 'fixed_worker_to_instance_no_retry' if not args.rate else 'round_robin_arrival_no_retry',
               'payload_count': len(payloads),
               'target_images_per_s': args.rate or None,
               'generator_limit_events': sum(r.get('error') == 'load_generator_inflight_limit' for r in records),
               'scheduled_latency_ms_p95': percentile([r['latency_from_schedule_ms'] for r in successful if 'latency_from_schedule_ms' in r], .95),
               'send_window_s': args.seconds, 'elapsed_including_drain_s': elapsed,
               'requests': len(records), 'successful': len(successful),
               'failed': len(records)-len(successful),
               'success_images_per_s_in_window': len(completed_in_window)/args.seconds,
               'success_images_per_s_including_drain': len(successful)/elapsed,
               'successful_image_latency_ms': {'p50': percentile(latencies, .5),
                    'p95': percentile(latencies, .95), 'p99': percentile(latencies, .99),
                    'mean': statistics.mean(latencies) if latencies else None},
               'status_counts': dict(collections.Counter(str(r['status']) for r in records)),
               'all_request_latency_ms_p95': percentile([r['latency_ms'] for r in records], .95),
               'warmup': 'must_be_performed_separately',
               'resource_metrics': 'must_be_collected_separately'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', nargs='+', required=True)
    parser.add_argument('--endpoint', choices=['/AE/SyncTasks2', '/ImageDetect/student/v1.0.0', '/ImageDetect/teacher/v1.0.0'], required=True)
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--concurrency', type=int, default=48)
    parser.add_argument('--seconds', type=float, default=180)
    parser.add_argument('--rate', type=float, default=0, help='大于零启用定速开放式负载，concurrency 为客户端在途上限')
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if args.concurrency < 1 or args.seconds <= 0 or args.timeout <= 0 or args.rate < 0:
        parser.error('并发、持续时间、超时必须大于零')
    asyncio.run(run(args))
