"""管理仅本轮创建的单 worker 实例，预热后调用闭环压测，退出时清理。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
from pathlib import Path
import re
import socket
import signal
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
    parser.add_argument('--seed', type=int, default=20261118)
    parser.add_argument('--rate', type=float, default=0)
    parser.add_argument('--first-port', type=int, default=18981)
    parser.add_argument('--queue-size', type=int, default=0)
    parser.add_argument('--max-batches', type=int, default=1)
    parser.add_argument('--warmup-seconds', type=int, default=30)
    parser.add_argument('--audit-reference', type=Path, help='独立业务一致性模式；不用作容量测量')
    parser.add_argument('--audit-repetitions', type=int, default=1)
    parser.add_argument('--trace-http', action='store_true', help='独立诊断时间线，勿混作普通容量成绩')
    parser.add_argument('--load-processes', type=int, choices=[1, 2], help='显式启用统一起点的单/双发生器诊断')
    args = parser.parse_args()
    if args.instances < 1 or args.concurrency < 1 or args.max_batches < 1 or args.queue_size < 0:
        parser.error('实例数与并发必须大于零')
    if args.audit_repetitions < 1 or (args.audit_reference and args.rate):
        parser.error('一致性重复必须大于零，且不能混入定速容量实验')
    if args.trace_http and not args.audit_reference:
        parser.error('HTTP时间线只用于带audit-reference的独立诊断，不混入普通容量实验')
    if args.load_processes is not None and (args.audit_reference or args.instances % args.load_processes or
            args.concurrency % args.load_processes or args.concurrency < args.load_processes):
        parser.error('协调发生器要求实例/总并发均匀分片，且不与audit-reference混用')
    if args.audit_reference:
        try:
            from .audit import workload
        except ImportError:
            from audit import workload
        workload(args.audit_reference, args.payload, args.endpoint)
    root = Path(__file__).resolve().parents[2]
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    def event(name, **details):
        with (args.output/'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': name, 'unix_time': time.time(), 'elapsed_s': time.perf_counter()-started, **details})+'\n')
    event('run_start', instances=args.instances, concurrency=args.concurrency, max_batches=args.max_batches,
          backend=args.backend, trace_http=args.trace_http,
          load_processes=args.load_processes,
          audit_reference=str(args.audit_reference.resolve()) if args.audit_reference else None)
    gpu = 'GPU-8c6b7efd-2b4f-04f3-db71-b50d2482fc49'
    processes, handles, urls = [], [], []
    load_process = None
    done = threading.Event()
    def sample():
        with (args.output / 'resources.csv').open('w') as out:
            writer = csv.writer(out)
            writer.writerow(['unix_time', 'gpu_query', 'process_stats_json', 'gpu_process_memory_csv'])
            previous = {}
            while not done.is_set():
                iteration_started = time.monotonic()
                query = subprocess.run(['nvidia-smi', f'--id={gpu}', '--query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw,clocks.sm', '--format=csv,noheader,nounits'], capture_output=True, text=True)
                now = time.monotonic()
                stats = []
                sampled = [(p.pid, 'server') for p in list(processes)]
                if load_process is not None:
                    sampled.append((load_process.pid, 'load_coordinator' if args.load_processes else 'load_generator'))
                    if args.load_processes:
                        try:
                            workers = json.loads((args.output/'load/workers.json').read_text())
                            for worker in workers:
                                fields = Path(f'/proc/{worker["pid"]}/stat').read_text().rsplit(')', 1)[1].split()
                                if int(fields[1]) == load_process.pid:
                                    sampled.append((worker['pid'], 'load_generator'))
                        except (FileNotFoundError, ProcessLookupError, json.JSONDecodeError):
                            pass
                for pid, role in sampled:
                    try:
                        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
                        ticks = int(fields[11])+int(fields[12])
                        old = previous.get(pid)
                        cpu = (ticks-old[1])/os.sysconf('SC_CLK_TCK')/(now-old[0])*100 if old else None
                        previous[pid] = (now, ticks)
                        stats.append({'pid': pid, 'role': role, 'cpu_percent_one_core_100': cpu,
                                      'rss_kib': int(fields[21])*os.sysconf('SC_PAGE_SIZE')/1024})
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                gpu_processes = subprocess.run(['nvidia-smi', f'--id={gpu}', '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'], capture_output=True, text=True)
                writer.writerow([time.time(), query.stdout.strip(), json.dumps(stats), gpu_processes.stdout.strip()])
                out.flush()
                done.wait(max(0, 1-(time.monotonic()-iteration_started)))
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    payload_files = sorted(args.payload.glob('*.json')) if args.payload.is_dir() else [args.payload]
    if len(payload_files) > 16:
        payload_files = [payload_files[round(i*(len(payload_files)-1)/15)] for i in range(16)]
    payloads = [p.read_bytes() for p in payload_files]
    if not payloads:
        raise ValueError('No warmup payloads')
    def post_warmup(url, payload):
        req = urllib.request.Request(url+args.endpoint, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as response:
            body = json.load(response)
            if response.status != 200:
                raise RuntimeError(f'Warmup failed: {url}')
            if args.endpoint.startswith('/ImageDetect/'):
                if not body.get('DataList') or any(r.get('StatusObject', {}).get('StatusCode') != 0 for r in body['DataList']):
                    raise RuntimeError(f'Warmup business error: {url}')
            elif body.get('Response', {}).get('ErrCode') != 0 or len(body.get('TaskResult', [])) != 1:
                raise RuntimeError(f'Warmup empty result: {url}')
    try:
        for index in range(args.instances):
            port = args.first_port+index
            with socket.socket() as test:
                test.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
            # 显式移除继承值，默认容量组不得意外启用诊断。
            env.pop('VBAS_BENCHMARK_TRACE_FILE', None)
            if args.trace_http:
                env['VBAS_BENCHMARK_TRACE_FILE'] = str(args.output/f'timing-{port}.jsonl')
            log = (args.output / f'instance-{port}.log').open('w')
            handles.append(log)
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'scripts.benchmark.server:app', '--host', '127.0.0.1', '--port', str(port), '--workers', '1'], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
            processes.append(process)
            event('instance_spawned', port=port, pid=process.pid)
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
            event('instance_ready', port=port)
            post_warmup(url, payloads[0])
            event('instance_prefilled', port=port)
        (args.output / 'instances.json').write_text(json.dumps({'pids': [p.pid for p in processes], 'urls': urls, 'queue_size': args.queue_size, 'max_batches': args.max_batches, 'gpu_uuid': gpu, 'python': sys.executable}, indent=2))
        # 错峰完成首次模型初始化后，并行预热全部实例及样本，避免串行预热使前面的实例冷却。
        def warm(url):
            deadline = time.monotonic()+args.warmup_seconds
            index = 0
            while time.monotonic() < deadline or index < len(payloads):
                post_warmup(url, payloads[index % len(payloads)])
                index += 1
        event('warmup_start')
        with ThreadPoolExecutor(max_workers=args.instances) as pool:
            list(pool.map(warm, urls))
        event('warmup_complete')
        startup_stats = {}
        for url in urls:
            with urllib.request.urlopen(url+'/_benchmark/memory') as response:
                startup_stats[url] = json.load(response)
            with urllib.request.urlopen(urllib.request.Request(url+'/_benchmark/reset_peak', data=b'', method='POST')) as response:
                response.read()
        (args.output/'startup-memory.json').write_text(json.dumps(startup_stats, indent=2))
        event('load_start')
        command = [sys.executable, str(root/'scripts/benchmark/load.py'), '--urls', *urls,
                        '--endpoint', args.endpoint, '--payload', str(args.payload.resolve()),
                        '--output', str(args.output/'load'), '--concurrency', str(args.concurrency),
                        '--seconds', str(args.seconds), '--rate', str(args.rate), '--seed', str(args.seed)]
        if args.load_processes is not None:
            command[1] = str(root/'scripts/benchmark/coordinated_load.py')
            command += ['--processes', str(args.load_processes)]
        if args.audit_reference:
            command = [sys.executable, str(root/'scripts/benchmark/audit.py'), '--urls', *urls,
                       '--endpoint', args.endpoint, '--payload', str(args.payload.resolve()),
                       '--output', str(args.output/'load'), '--concurrency', str(args.concurrency),
                       '--seed', str(args.seed), '--reference', str(args.audit_reference.resolve()),
                       '--repetitions', str(args.audit_repetitions)]
        load_process = subprocess.Popen(command, start_new_session=args.load_processes is not None)
        code = load_process.wait()
        if code:
            raise RuntimeError(f'Load generator exited: {code}')
        event('load_complete')
        steady_stats = {}
        for url in urls:
            with urllib.request.urlopen(url+'/_benchmark/memory') as response:
                steady_stats[url] = json.load(response)
        (args.output/'inference-memory.json').write_text(json.dumps(steady_stats, indent=2))
    except BaseException as exc:
        event('run_failed', error=repr(exc))
        raise
    finally:
        if load_process is not None and args.load_processes is not None:
            # 新建会话只包含本轮协调器和其子进程；即使父进程意外退出也清理同组发生器。
            try:
                os.killpg(load_process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if load_process is not None and load_process.poll() is None:
            if args.load_processes is None:
                load_process.terminate()
            try:
                load_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if args.load_processes is not None:
                    try:
                        os.killpg(load_process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                load_process.kill()
                load_process.wait()
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
        event('cleanup_complete', exit_codes=[p.returncode for p in processes])


if __name__ == '__main__':
    main()
