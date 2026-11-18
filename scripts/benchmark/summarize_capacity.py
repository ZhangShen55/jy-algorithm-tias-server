"""离线归集已完成容量轮：不启动服务、不使用 GPU、不覆盖原始证据。"""
import argparse
from bisect import bisect_right
import collections
import csv
import hashlib
import json
from pathlib import Path
import statistics


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def describe(values):
    values = [v for v in values if v is not None]
    return {'samples': len(values), 'mean': statistics.mean(values) if values else None,
            'max': max(values) if values else None}


def timeline(records, seconds, open_loop, window=10):
    sent = sorted(r['sent_offset_s'] for r in records if 'sent_offset_s' in r)
    completed = sorted(r['completed_offset_s'] for r in records if 'completed_offset_s' in r)
    planned = sorted(r.get('planned_offset_s', r.get('sent_offset_s', 0)) for r in records)
    dropped = sorted(r['planned_offset_s'] for r in records
                     if r.get('error') == 'load_generator_inflight_limit')
    failures = [r.get('completed_offset_s', r.get('planned_offset_s'))
                for r in records if not r['valid']]
    bins = []
    # 只用完整窗口判断持续积压；最后不足10秒单独报告，不用于三窗口判定。
    times = list(range(0, int(seconds) + 1, window))
    if not times or times[-1] != seconds:
        times.append(seconds)
    for t in times:
        n_sent, n_done = bisect_right(sent, t), bisect_right(completed, t)
        n_planned, n_dropped = bisect_right(planned, t), bisect_right(dropped, t)
        bins.append({'elapsed_s': t, 'sent': n_sent, 'completed': n_done,
                     'scheduled': n_planned, 'generator_dropped': n_dropped,
                     'network_inflight': n_sent - n_done,
                     'scheduled_unresolved_excluding_local_drops': n_planned - n_done - n_dropped})
    wall = None
    if open_loop:
        for i in range(3, len(bins)):
            group = bins[i-3:i+1]
            if all(group[j+1]['elapsed_s'] - group[j]['elapsed_s'] == window and
                   group[j+1]['scheduled_unresolved_excluding_local_drops'] >
                   group[j]['scheduled_unresolved_excluding_local_drops'] for j in range(3)):
                wall = {'interval_start_s': group[0]['elapsed_s'],
                        'detected_at_s': group[-1]['elapsed_s'],
                        'backlogs': [g['scheduled_unresolved_excluding_local_drops'] for g in group]}
                break
    return {'window_s': window, 'windows': bins,
            'first_failure_s': min((t for t in failures if t is not None), default=None),
            'first_sustained_backlog_increase': wall,
            'backlog_rule': 'three_consecutive_full_10s_increases_open_loop_only',
            'interpretation': 'operational_congestion_signal_not_production_slo_or_hardware_limit',
            'local_generator_drops': len(dropped),
            'send_lag_ms': describe([(r['sent_offset_s']-r['planned_offset_s'])*1000
                                     for r in records if 'sent_offset_s' in r and 'planned_offset_s' in r])}


def resources(path, start, seconds):
    gpu = collections.defaultdict(list)
    roles = collections.defaultdict(lambda: collections.defaultdict(list))
    by_pid = collections.defaultdict(lambda: collections.defaultdict(list))
    samples = 0
    with path.open() as stream:
        for row in csv.DictReader(stream):
            if not start <= float(row['unix_time']) <= start + seconds:
                continue
            samples += 1
            fields = row['gpu_query'].split(',')
            for name, field in zip(['memory_mib', 'utilization_percent', 'temperature_c', 'power_w', 'sm_clock_mhz'], fields):
                try:
                    gpu[name].append(float(field.strip()))
                except ValueError:
                    pass
            totals = collections.defaultdict(lambda: collections.defaultdict(float))
            for process in json.loads(row['process_stats_json']):
                pid, role = str(process['pid']), process['role']
                for key in ['cpu_percent_one_core_100', 'rss_kib']:
                    value = process.get(key)
                    if value is not None:
                        totals[role][key] += value
                        by_pid[pid][key].append(value)
            for role, metrics in totals.items():
                for key, value in metrics.items():
                    roles[role][key].append(value)
    return {'window_samples': samples,
            'gpu': {k: describe(v) for k, v in gpu.items()},
            'roles': {role: {k: describe(v) for k, v in values.items()} for role, values in roles.items()},
            'per_pid': {pid: {k: describe(v) for k, v in values.items()} for pid, values in by_pid.items()},
            'cpu_units': 'one_core_100_percent; server_role_is_sum_of_processes',
            'scope': 'formal_send_window_excludes_startup_warmup_and_drain'}


def summarize(root, output):
    output.mkdir(parents=True, exist_ok=False)
    cases, incomplete = [], []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        result_path = folder/'case-result.json'
        if not result_path.exists():
            incomplete.append(folder.name)
            continue
        result = json.loads(result_path.read_text())
        item = {'case': result, 'evidence': {str(result_path.relative_to(root)): fingerprint(result_path)}}
        summary_path, requests_path = folder/'load/summary.json', folder/'load/requests.jsonl'
        if summary_path.exists() and requests_path.exists():
            summary = json.loads(summary_path.read_text())
            if summary != result.get('summary'):
                raise ValueError(f'轮次结果与负载摘要不符：{folder}')
            records = [json.loads(line) for line in requests_path.open()]
            successful = sum(bool(r['valid']) for r in records)
            if (len(records), successful, len(records)-successful) != (summary['requests'], summary['successful'], summary['failed']):
                raise ValueError(f'请求完整性与摘要不符：{folder}')
            item['request_integrity'] = 'counts_match_saved_summary'
            item['timeline'] = timeline(records, summary['send_window_s'], summary['mode'].startswith('open_loop'))
            resource_path = folder/'resources.csv'
            if resource_path.exists():
                item['resources'] = resources(resource_path, summary['started_unix_time'], summary['send_window_s'])
                item['evidence'][str(resource_path.relative_to(root))] = fingerprint(resource_path)
            for path in [summary_path, requests_path]:
                item['evidence'][str(path.relative_to(root))] = fingerprint(path)
        cases.append(item)
    report = {'run_root': str(root.resolve()), 'completed_cases': cases,
              'incomplete_cases_excluded': incomplete,
              'adoption': 'requires_user_review', 'ground_truth_accuracy': 'not_evaluated',
              'production_slo': 'not_specified',
              'latency_units': 'client_wall_clock_per_single_image_request_ms_not_server_compute_time'}
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    with (output/'cases.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['case', 'usable', 'instances', 'total_concurrency', 'max_batches',
                         'successes', 'failures', 'images_per_s', 'p50_ms', 'p95_ms', 'p99_ms', 'mean_ms',
                         'first_failure_s', 'congestion_interval_start_s', 'generator_drops'])
        for item in cases:
            case = item['case']; summary = case.get('summary', {})
            latency = summary.get('successful_image_latency_ms', {})
            trace = item.get('timeline', {}); wall = trace.get('first_sustained_backlog_increase') or {}
            writer.writerow([case['label'], case['usable'], case['instances'], case['concurrency'], case.get('max_batches'),
                             summary.get('successful'), summary.get('failed'), summary.get('success_images_per_s_in_window'),
                             *[latency.get(k) for k in ['p50', 'p95', 'p99', 'mean']],
                             trace.get('first_failure_s'), wall.get('interval_start_s'), trace.get('local_generator_drops')])
    return {'completed': len(cases), 'incomplete_excluded': incomplete, 'output': str(output)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.run_root, args.output), ensure_ascii=False))
