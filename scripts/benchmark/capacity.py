"""顺序执行单 GPU、分接口容量实验；中断后通过 journal 恢复，不自动采用配置。"""
import argparse
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--payload-root', required=True, type=Path)
    parser.add_argument('--backend', choices=['pytorch', 'tensorrt'], required=True)
    parser.add_argument('--engine-root', default='')
    parser.add_argument('--explore-seconds', type=int, default=180)
    parser.add_argument('--confirm-seconds', type=int, default=300)
    parser.add_argument('--stability-seconds', type=int, default=1800)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    results = []
    def case(label, name, endpoint, instances, concurrency, batches, seconds, rate=0):
        folder = args.output/label
        cached = folder/'case-result.json'
        if cached.exists():
            return json.loads(cached.read_text())
        if folder.exists():
            raise RuntimeError(f'Incomplete case needs inspection before resume: {folder}')
        # 防止意外与其他 GPU 工作重叠；不终止不属于本轮的进程。
        gpu = subprocess.check_output(['nvidia-smi', '--id=GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True)
        if int(gpu.strip()) > 100:
            raise RuntimeError('GPU is not idle; do not overlap experiments')
        available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        # 保留主机余量；限制属于实验边界，不通过 OOM 杀死其他服务寻找 CPU 内存上限。
        if available < (8+instances*1.5)*(1 << 30):
            return {'label': label, 'usable': False, 'cause': 'host_memory_budget', 'instances': instances, 'concurrency': concurrency}
        cmd = [sys.executable, str(root/'scripts/benchmark/instances.py'), '--output', str(folder),
               '--payload', str((args.payload_root/name).resolve()), '--endpoint', endpoint,
               '--instances', str(instances), '--concurrency', str(concurrency), '--max-batches', str(batches),
               '--seconds', str(seconds), '--warmup-seconds', '30', '--backend', args.backend,
               '--engine-root', args.engine_root, '--rate', str(rate)]
        with (args.output/f'{label}.log').open('w') as log:
            code = subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT).returncode
        result = {'label': label, 'instances': instances, 'concurrency': concurrency, 'max_batches': batches,
                  'seconds': seconds, 'rate': rate, 'returncode': code, 'usable': False}
        summary = folder/'load/summary.json'
        if summary.exists():
            result['summary'] = json.loads(summary.read_text())
            result['usable'] = code == 0 and result['summary']['failed'] == 0 and result['summary']['successful'] > 0
        if not result['usable']:
            oom = False
            for f in folder.glob('instance-*.log'):
                with f.open(errors='replace') as stream:
                    if any('out of memory' in line.lower() for line in stream):
                        oom = True
            result['cause'] = 'cuda_oom' if oom else ('http_or_business_failure' if summary.exists() else 'startup_or_tool_error')
        if folder.exists():
            cached.write_text(json.dumps(result, indent=2))
        with (args.output/'journal.jsonl').open('a') as journal:
            journal.write(json.dumps(result)+'\n')
        print(json.dumps(result), flush=True)
        time.sleep(2)
        if code and result.get('cause') != 'cuda_oom':
            raise RuntimeError(f'Unexpected case failure: inspect {label}')
        return result

    endpoints = [('sync', '/AE/SyncTasks2'), ('student', '/ImageDetect/student/v1.0.0'), ('teacher', '/ImageDetect/teacher/v1.0.0')]
    for name, endpoint in endpoints:
        candidates = []
        instance_plateaus = 0
        best_tps = 0
        for instances in [1, 2, 4, 6, 8, 12, 16]:
            if args.backend == 'pytorch' and name == 'student' and instances >= 8:
                break  # 已有 8 实例预热 OOM 证据，保留原日志，避免无意义重复。
            instance_best = 0
            previous = None
            base_failed = False
            for factor in [1, 2, 4, 6]:
                row = case(f'{name}-explore-i{instances}-c{instances*factor}-b{factor}', name, endpoint,
                           instances, instances*factor, factor, args.explore_seconds)
                if not row['usable']:
                    if factor == 1:
                        base_failed = True
                    break
                candidates.append(row)
                current = row['summary']['success_images_per_s_in_window']
                instance_best = max(instance_best, current)
                if previous and current < previous['summary']['success_images_per_s_in_window']*1.05 and row['summary']['successful_image_latency_ms']['p95'] > previous['summary']['successful_image_latency_ms']['p95']*1.2:
                    break
                previous = row
            if base_failed:
                break
            instance_plateaus = instance_plateaus+1 if best_tps and instance_best < best_tps*1.05 else 0
            best_tps = max(best_tps, instance_best)
            if instance_plateaus >= 2:
                break
        if not candidates:
            raise RuntimeError(f'No zero-failure candidate: {name}')
        best = max(candidates, key=lambda r:r['summary']['success_images_per_s_in_window'])
        neighbors = [r for r in candidates if r['label'] != best['label']]
        neighbor = min(neighbors, key=lambda r:abs(math.log(r['instances']/best['instances']))+abs(math.log(r['concurrency']/best['concurrency']))) if neighbors else None
        confirmed = []
        for candidate in [best]+([neighbor] if neighbor else []):
            trials = [case(f'{name}-confirm-{candidate["label"]}-r{repeat}', name, endpoint,
                           candidate['instances'], candidate['concurrency'], candidate['max_batches'], args.confirm_seconds)
                      for repeat in range(1,4)]
            if all(r['usable'] for r in trials):
                confirmed.append((statistics.median(r['summary']['success_images_per_s_in_window'] for r in trials), candidate))
        if not confirmed:
            raise RuntimeError(f'No repeatably zero-failure candidate: {name}')
        throughput, candidate = max(confirmed, key=lambda item:item[0])
        stable = case(f'{name}-stability', name, endpoint, candidate['instances'], candidate['concurrency'], candidate['max_batches'], args.stability_seconds)
        for fraction in [.8, 1., 1.1]:
            case(f'{name}-open-{fraction}', name, endpoint, candidate['instances'], candidate['concurrency']*4,
                 candidate['max_batches'], args.explore_seconds, rate=throughput*fraction)
        results.append({'endpoint': endpoint, 'candidate': candidate, 'median_confirmed_images_per_s': throughput,
                        'stability_zero_failures': stable['usable'], 'production_slo': 'not_specified',
                        'adoption': 'requires_user_review', 'search_scope': 'adaptive_tested_grid_not_absolute_hardware_limit'})
        (args.output/'capacity-results.json').write_text(json.dumps(results, indent=2))
    print('Capacity experiments finished; adoption and accuracy acceptance remain separate.', flush=True)


if __name__ == '__main__':
    main()
