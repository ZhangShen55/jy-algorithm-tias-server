"""管理仅本轮创建的单 worker 实例，预热后调用闭环压测，退出时清理。"""
import argparse
import contextlib
import csv
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--backend', choices=['pytorch', 'tensorrt'], default='pytorch')
    parser.add_argument('--engine-root', default='')
    parser.add_argument('--instances', type=int, default=8)
    parser.add_argument('--concurrency', type=int, default=48)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--rate', type=float, default=0)
    parser.add_argument('--first-port', type=int, default=18981)
    parser.add_argument('--queue-size', type=int, default=0)
    parser.add_argument('--max-batches', type=int, default=1)
    parser.add_argument('--warmup-seconds', type=int, default=30)
    args = parser.parse_args()
    if args.instances < 1 or args.concurrency < 1:
        parser.error('实例数与并发必须大于零')
    root = Path(__file__).resolve().parents[2]
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    gpu = 'GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49'
    processes, handles, urls = [], [], []
    done = threading.Event()
    def sample():
        with (args.output / 'resources.csv').open('w') as out:
            writer = csv.writer(out)
            writer.writerow(['unix_time', 'gpu_query', 'process_stats'])
            while not done.is_set():
                query = subprocess.run(['nvidia-smi', f'--id={gpu}', '--query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw,clocks.sm', '--format=csv,noheader,nounits'], capture_output=True, text=True)
                proc = subprocess.run(['ps', '-o', 'pid=,pcpu=,rss=', '-p', ','.join(str(p.pid) for p in processes)], capture_output=True, text=True) if processes else None
                writer.writerow([time.time(), query.stdout.strip(), proc.stdout.strip() if proc else ''])
                out.flush()
                done.wait(1)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        for index in range(args.instances):
            port = args.first_port+index
            with socket.socket() as test:
                test.bind(('127.0.0.1', port))
            text = (root / 'config.toml').read_text()
            text = 'InferenceBackend = '+json.dumps(args.backend)+'\nEngineRoot = '+json.dumps(args.engine_root)+'\n'+text
            substitutions = {
                'GPU_ID': f'"{gpu}"\nInferenceHalf = true',
                'VbasExposeLegacySyncTasks': 'true', 'VisionOrchestratorBaseUrl': '""',
                'InstanceId': f'"perf-{port}"', 'BaseUrl': f'"http://127.0.0.1:{port}"',
                'MaxQueueSize': str(args.queue_size), 'MaxConcurrentBatches': str(args.max_batches)}
            for key, value in substitutions.items():
                text = re.sub(rf'^{key}\s*=.*$', f'{key} = {value}', text, flags=re.M)
            config = args.output / f'config-{port}.toml'
            config.write_text(text)
            env = {**os.environ, 'CONFIG_PATH': str(config), 'CUDA_VISIBLE_DEVICES': gpu}
            log = (args.output / f'instance-{port}.log').open('w')
            handles.append(log)
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(port), '--workers', '1'], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
            processes.append(process)
            url = f'http://127.0.0.1:{port}'
            deadline = time.monotonic()+180
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f'Instance exited before ready: {port}; see instance log')
                try:
                    with urllib.request.urlopen(url+'/openapi.json', timeout=2) as response:
                        if response.status == 200:
                            break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f'Instance startup timeout: {port}')
                    time.sleep(1)
            urls.append(url)
        (args.output / 'instances.json').write_text(json.dumps({'pids': [p.pid for p in processes], 'urls': urls, 'queue_size': args.queue_size, 'max_batches': args.max_batches, 'gpu_uuid': gpu, 'python': sys.executable}, indent=2))
        # 每个实例单独持续调用预热，故意不将此阶段算入正式采样。
        payload = (sorted(args.payload.glob('*.json'))[0] if args.payload.is_dir() else args.payload).read_bytes()
        for url in urls:
            deadline = time.monotonic()+args.warmup_seconds
            while time.monotonic() < deadline:
                req = urllib.request.Request(url+args.endpoint, data=payload, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=120) as response:
                    if response.status != 200:
                        raise RuntimeError(f'Warmup failed: {url}')
        subprocess.run([sys.executable, str(root/'scripts/benchmark/load.py'), '--urls', *urls,
                        '--endpoint', args.endpoint, '--payload', str(args.payload.resolve()),
                        '--output', str(args.output/'load'), '--concurrency', str(args.concurrency),
                        '--seconds', str(args.seconds), '--rate', str(args.rate)], check=True)
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        done.set()
        sampler.join(timeout=10)
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    main()
