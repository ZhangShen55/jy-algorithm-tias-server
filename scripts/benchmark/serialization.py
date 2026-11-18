"""重放已保存业务响应的 JSONResponse 编码成本；无模型、无 GPU、不是 HTTP 容量测试。"""
import argparse
import collections
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import time

try:
    from .load import percentile
    from .compare import valid_business
except ImportError:
    from load import percentile
    from compare import valid_business


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', nargs='+', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('重复次数必须大于零')
    from starlette.responses import JSONResponse
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = {}
    counts = collections.Counter()
    metrics = collections.defaultdict(list)
    sizes = collections.defaultdict(list)
    with (args.output/'samples.jsonl').open('w') as out:
        for source in args.reference:
            if str(source.resolve()) in inputs:
                raise ValueError('同一结果输入不能重复')
            inputs[str(source.resolve())] = hashlib.sha256(source.read_bytes()).hexdigest()
            warmed = set()
            seen = set()
            with source.open() as stream:
                for line in stream:
                    row = json.loads(line)
                    if row['status'] != 200 or not valid_business(row):
                        raise ValueError('不对失败业务响应生成成功路径编码指标')
                    key = (row['endpoint'], row['image_id'])
                    if key in seen:
                        raise ValueError('重复基线图片/接口')
                    seen.add(key)
                    group = (str(source.resolve()), row['endpoint'])
                    counts[group] += 1
                    if row['endpoint'] not in warmed:
                        for _ in range(16):
                            JSONResponse(row['response'])
                        warmed.add(row['endpoint'])
                    for repeat in range(args.repeats):
                        start = time.perf_counter_ns()
                        response = JSONResponse(row['response'])
                        elapsed = (time.perf_counter_ns()-start)/1e6
                        # 校验不计入编码计时，不覆盖原始响应。
                        if json.loads(response.body) != row['response']:
                            raise ValueError('JSON 编码/解码未能保留业务响应值')
                        metrics[group].append(elapsed)
                        sizes[group].append(len(response.body))
                        out.write(json.dumps({'source': str(source.resolve()), 'endpoint': row['endpoint'],
                            'image_id': row['image_id'], 'image_sha256': row['image_sha256'],
                            'repeat': repeat+1, 'elapsed_ms': elapsed, 'json_body_bytes': len(response.body)})+'\n')
    rows = []
    for group, samples in sorted(metrics.items()):
        rows.append({'source': group[0], 'endpoint': group[1], 'images': counts[group], 'samples': len(samples),
                     'encode_ms': {'p50': percentile(samples, .5), 'p95': percentile(samples, .95),
                                   'p99': percentile(samples, .99), 'mean': statistics.mean(samples)},
                     'json_body_bytes_mean': statistics.mean(sizes[group]), 'json_body_bytes_max': max(sizes[group])})
    manifest = {'scope': 'starlette_JSONResponse_construct_render_and_headers_from_saved_plain_response',
                'excluded': ['pydantic_response_validation_and_dump', 'request_parsing', 'network',
                             'gpu_inference', 'business_object_construction', 'concurrent_capacity'],
                'uses_gpu': False, 'python': platform.python_version(), 'platform': platform.platform(),
                'starlette_version': importlib.metadata.version('starlette'),
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'references_sha256': inputs, 'repeats_per_image': args.repeats, 'results': rows}
    (args.output/'summary.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({'groups': len(rows), 'samples': sum(len(v) for v in metrics.values()), 'uses_gpu': False}))


if __name__ == '__main__':
    main()
