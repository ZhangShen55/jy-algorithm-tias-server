"""独立的并发业务结果采集；不用于吞吐评分，不将差异自动认定为精度通过。"""
import argparse
import asyncio
import base64
import collections
import hashlib
import json
from pathlib import Path
import random
import statistics
import time
from urllib.parse import quote

try:
    from .compare import business_boxes, business_counts, canonical, match, valid_business
    from .load import percentile
except ImportError:
    from compare import business_boxes, business_counts, canonical, match, valid_business
    from load import percentile


def workload(reference, payload_root, endpoint):
    references = {}
    with reference.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['endpoint'] != endpoint:
                continue
            if row['image_id'] in references or row['status'] != 200 or not valid_business(row):
                raise ValueError('基线有重复或无效记录')
            for prediction in row.get('predictions', []):
                legacy_half = ('runtime_fp16' not in prediction
                               and prediction.get('weight_dtype') == 'torch.float16'
                               and prediction.get('predict_args', {}).get('half') is True)
                if prediction.get('runtime_fp16') is not True and not legacy_half:
                    raise ValueError('有模型元数据时必须使用已验证FP16基线')
                if (endpoint == '/ImageDetect/student/v1.0.0' and prediction['model'] == 'yolo_person_model'
                        and prediction.get('predict_args', {}).get('agnostic_nms') is not False):
                    raise ValueError('学生基线必须使用独立NMS=False修正版')
            references[row['image_id']] = row
    items, seen = [], set()
    for path in sorted(payload_root.glob('*.json')):
        payload = json.loads(path.read_text())
        if len(payload.get('ImageList', [])) != 1:
            raise ValueError('并发一致性主验证要求一请求一图')
        image = payload['ImageList'][0]
        image_id = image.get('ImageId', image.get('ImageID'))
        row = references[image_id]
        encoded = image.get('Data', image.get('StoragePath'))
        if image_id in seen or hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest() != row['image_sha256']:
            raise ValueError(f'输入重复或与基线图片哈希不符：{image_id}')
        stripped = {k: v for k, v in payload.items() if k != 'ImageList'}
        stripped['ImageList'] = [{k: v for k, v in image.items() if k not in {'Data', 'StoragePath'}}]
        expected_request = row['request']
        if 'ImageList' not in expected_request:
            # 89da431/6ffb689历史采集省略了整个ImageList；源代码只含ID和图像字节。
            # 图像字节已按SHA验证，恢复已记录的image_id，仍拒绝额外的逐图参数。
            id_key = 'ImageID' if endpoint == '/AE/SyncTasks2' else 'ImageId'
            expected_request = {**expected_request, 'ImageList': [{id_key: image_id}]}
        if stripped != expected_request:
            raise ValueError(f'请求参数与基线不符：{image_id}')
        seen.add(image_id)
        items.append((image_id, payload, row))
    if not items or seen != references.keys():
        raise ValueError('请求池与所选接口基线覆盖不一致')
    return items


def difference(expected, actual):
    counts_a, counts_b = business_counts(expected), business_counts(actual)
    boxes_a, boxes_b = business_boxes(expected), business_boxes(actual)
    geometry = {}
    for label in sorted(boxes_a.keys() | boxes_b.keys()):
        result = match(boxes_a.get(label, []), boxes_b.get(label, []), .5)
        geometry[label] = {'matched': len(result['matched']), 'missing': len(result['missing']),
                           'added': len(result['added']),
                           'max_coordinate_delta': max((m['max_coordinate_delta'] for m in result['matched']), default=0)}
    return {'strict_equal_ignoring_timing_capacity_order': canonical(expected) == canonical(actual),
            'count_deltas': {k: counts_b[k]-counts_a[k] for k in sorted(counts_a.keys() | counts_b.keys())
                             if counts_b[k] != counts_a[k]},
            'business_geometry': geometry}


async def run(args):
    import httpx
    items = workload(args.reference, args.payload, args.endpoint)
    random.Random(args.seed).shuffle(items)
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    sequence = 0
    total = len(items)*args.repetitions
    abort = asyncio.Event()
    started = time.perf_counter()
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    with (args.output/'responses.jsonl').open('w') as out:
        async with httpx.AsyncClient(timeout=args.timeout, limits=limits, trust_env=False) as client:
            async def worker(index):
                nonlocal sequence
                while sequence < total and not abort.is_set():
                    number = sequence
                    sequence += 1
                    image_id, payload, expected = items[number % len(items)]
                    url = args.urls[index % len(args.urls)].rstrip('/')
                    row = {'sequence': number, 'repeat': number//len(items)+1, 'endpoint': args.endpoint,
                           'image_id': image_id, 'image_sha256': expected['image_sha256'], 'instance': url,
                           'valid': False, 'status': None}
                    sent = time.perf_counter()
                    row['sent_offset_s'] = sent-started
                    try:
                        response = await client.post(url+args.endpoint, json=payload,
                            headers={'X-Benchmark-Sequence': str(number), 'X-Benchmark-Image-Id': quote(image_id, safe='/')})
                        received = time.perf_counter()
                        row.update(completed_offset_s=received-started, latency_ms=(received-sent)*1000)
                        row.update(status=response.status_code, response=response.json())
                        row['valid'] = response.status_code == 200 and valid_business(row)
                        if row['valid']:
                            row['comparison'] = difference(expected['response'], row['response'])
                    except Exception as exc:
                        row.update(valid=False, error=repr(exc))
                        if 'latency_ms' not in row:
                            row.update(completed_offset_s=time.perf_counter()-started,
                                       latency_ms=(time.perf_counter()-sent)*1000)
                    if not row['valid']:
                        abort.set()
                    records.append(row)
                    out.write(json.dumps(row, ensure_ascii=False)+'\n')
                    out.flush()
            await asyncio.gather(*(worker(i) for i in range(args.concurrency)))
    valid = [r for r in records if r['valid']]
    latencies = [r['latency_ms'] for r in valid]
    summary = {'mode': 'concurrent_business_consistency_not_capacity_measurement',
               'endpoint': args.endpoint, 'reference': str(args.reference.resolve()),
               'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
               'images': len(items), 'repetitions': args.repetitions, 'seed': args.seed,
               'reference_image_metadata_reconstructed_images': sum('ImageList' not in r['request'] for _, _, r in items),
               'instances': len(args.urls), 'total_concurrency': args.concurrency,
               'expected_calls': total, 'completed_calls': len(records), 'unattempted_calls': total-sequence,
               'http_or_business_failures': len(records)-len(valid),
               'strict_equal_calls': sum(r['comparison']['strict_equal_ignoring_timing_capacity_order'] for r in valid),
               'count_changed_calls': sum(bool(r['comparison']['count_deltas']) for r in valid),
               'calls_per_instance': dict(collections.Counter(r['instance'] for r in records)),
               'client_http_body_latency_ms': {'samples': len(latencies), 'p50': percentile(latencies, .5),
                    'p95': percentile(latencies, .95), 'p99': percentile(latencies, .99),
                    'mean': statistics.mean(latencies) if latencies else None},
               'latency_scope': 'client_post_to_full_body_received_excludes_response_comparison_and_file_write',
               'elapsed_s': time.perf_counter()-started,
               'scope': 'final_business_response_only_not_raw_model_boxes_or_ground_truth_accuracy',
               'acceptance': 'full_differences_preserved_for_review_no_automatic_accuracy_acceptance'}
    (args.output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False))
    if len(valid) != total:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--urls', nargs='+', required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--concurrency', type=int, required=True)
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--seed', type=int, default=20261118)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if args.concurrency < 1 or args.repetitions < 1 or args.timeout <= 0:
        parser.error('并发、重复和超时必须大于零')
    asyncio.run(run(args))
