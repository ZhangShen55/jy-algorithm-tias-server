"""仅从已核验的聚合证据制图；不读取照片、不运行模型、不改变原记录。"""
from pathlib import Path
import csv
import hashlib
import json
import os
import subprocess
import sys
import textwrap

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
os.environ['MPLCONFIGDIR'] = str(OUT/'mpl-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SOURCES = {
    'pytorch': (ROOT/'capacity-analysis-20261119-torch-dispatch-components/summary.json',
                '91bb5eff1afdc3e622bf34c2e71fa83b7a108abca4a561b0f2256bc4395ac72d', 69),
    'tensorrt': (ROOT/'capacity-analysis-20261119-trt-formal-complete/summary.json',
                 '10693fbcc95f0e9c0f2345262baf5c61e7d46f59f5b98578d261338a737ce9a5', 74),
}
data, fingerprints = {}, {}
for backend, (path, expected, count) in SOURCES.items():
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, path
    document = json.loads(raw)
    assert len(document['completed_cases']) == count and not document['incomplete_cases_excluded']
    data[backend] = document['completed_cases']
    fingerprints[str(path)] = expected
supplement = {}
for backend, short in [('pytorch', 'pt'), ('tensorrt', 'trt')]:
    path = ROOT/f'sync-c256-checkpoint-20261119/evidence/capacity-analysis-20261119-{short}-sync-c256/summary.json'
    expected = {'pt': 'fc3a69e4b64def24885a895a9c423c87b2d126b82186becb7c11cd20b914819c',
                'trt': 'a6d5e31beeaed9975925893436d4d234b9f26b2c46445b4df884e45c098d1593'}[short]
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    supplement[backend] = json.loads(raw)['completed_cases'][0]
    fingerprints[str(path)] = expected

plt.rcParams.update({'font.size': 10, 'axes.titlesize': 12, 'axes.labelsize': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none', 'savefig.dpi': 180})
names = {'sync': 'Person count', 'student': 'Student behavior', 'teacher': 'Teacher behavior'}
display = {'pytorch': 'PyTorch FP16', 'tensorrt': 'TensorRT FP16'}
instances = [1, 2, 4, 6, 8, 12]
colors = {i: plt.get_cmap('tab10')(n) for n, i in enumerate(instances)}
artifacts = []


def save(fig, name, footer):
    fig.text(.025, .012, textwrap.fill(footer, 155), va='bottom', fontsize=9, color='#444444')
    for suffix in ['png', 'svg']:
        p = OUT/f'{name}.{suffix}'
        assert not p.exists()
        fig.savefig(p, facecolor='white')
        if suffix == 'svg':
            import xml.etree.ElementTree as ET
            import re
            raw_svg = p.read_text()
            normalized = '\n'.join(line.rstrip() for line in raw_svg.splitlines())+'\n'
            before, after = ET.fromstring(raw_svg), ET.fromstring(normalized)
            for original, cleaned in zip(before.iter(), after.iter(), strict=True):
                assert original.tag == cleaned.tag and original.text == cleaned.text
                assert original.attrib.keys() == cleaned.attrib.keys()
                for key in original.attrib:
                    assert re.sub(r'\s+', ' ', original.attrib[key]).strip() == re.sub(r'\s+', ' ', cleaned.attrib[key]).strip()
            p.write_text(normalized)
        artifacts.append(p)
    plt.close(fig)


exploration = {b: [x for x in rows if '-explore-' in x['case']['label'] and '-confirm-' not in x['case']['label']]
               for b, rows in data.items()}
assert sum(map(len, exploration.values())) == 83
assert all(x['case']['summary']['failed'] == 0 for rows in exploration.values() for x in rows)

for measure, ylabel, title, filename in [
        ('throughput', 'Successful images / second', 'Measured capacity search', 'search-throughput'),
        ('latency', 'Client P95 latency (ms)', 'Latency across the measured search grid', 'search-latency-p95')]:
    fig, axes = plt.subplots(3, 2, figsize=(13, 10.5), sharex='row', sharey='row')
    fig.suptitle(title+' | one RTX 3090', y=.995, fontsize=16)
    fig.legend([Line2D([], [], color=colors[i], marker='o', label=f'I={i}') for i in instances],
               [f'I={i}' for i in instances], loc='upper center', bbox_to_anchor=(.5, .964), ncol=6, frameon=False)
    for row, endpoint in enumerate(names):
        largest_c = max(x['case']['concurrency'] for rows in exploration.values() for x in rows
                        if x['case']['label'].startswith(endpoint+'-'))
        ticks = [n for n in [1, 2, 4, 8, 16, 32] if n <= largest_c]
        if largest_c > 32:
            ticks.append(largest_c)
        relevant = [x for rows in exploration.values() for x in rows if x['case']['label'].startswith(endpoint+'-')]
        upper = max(x['case']['summary']['success_images_per_s_in_window'] if measure == 'throughput'
                    else x['case']['summary']['successful_image_latency_ms']['p95'] for x in relevant)
        for column, backend in enumerate(data):
            ax = axes[row, column]
            ax.set_xlim(.85, largest_c*1.15)
            for i in instances:
                points = sorted([x for x in exploration[backend] if x['case']['label'].startswith(endpoint+'-')
                                 and x['case']['instances'] == i], key=lambda x: x['case']['concurrency'])
                if not points:
                    continue
                ax.plot([x['case']['concurrency'] for x in points],
                        [x['case']['summary']['success_images_per_s_in_window'] if measure == 'throughput'
                         else x['case']['summary']['successful_image_latency_ms']['p95'] for x in points],
                        marker='o', color=colors[i], linewidth=1.6, markersize=4)
            ax.set_title(display[backend]+' / '+names[endpoint])
            ax.set_xscale('log', base=2)
            ax.set_xticks(ticks, labels=list(map(str, ticks)))
            ax.minorticks_off()
            ax.set_ylim(0, max(1, upper*1.12))
            ax.set_xlabel('Total HTTP concurrency C (log scale)')
            ax.grid(alpha=.22)
            if column == 0:
                ax.set_ylabel(ylabel)
    assert sum(len(line.get_xdata()) for ax in axes.flat for line in ax.lines) == 83
    for ax in axes.flat:
        for line in ax.lines:
            assert all(ax.get_ylim()[0] <= y <= ax.get_ylim()[1] for y in line.get_ydata())
            assert all(ax.get_xlim()[0] <= x <= ax.get_xlim()[1] for x in line.get_xdata())
    fig.tight_layout(rect=(.01, .065, .995, .96), h_pad=2.2)
    save(fig, filename, '83 exploration cases, 180-second formal windows. Adaptive tested grid only; no production SLO. '
         'Teacher generator limits remain unresolved; I16 teacher was not launched due to host-memory guard. '
         'These individual search points do not replace repeated, same-configuration backend comparisons.')


fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True, sharey='row')
fig.suptitle('Teacher open-loop dispatch backlog | original single generator', y=.995, fontsize=15)
for row, fraction in enumerate(['0.8', '1.0', '1.1']):
    both = [next(x for x in data[b] if x['case']['label'] == 'teacher-open-'+fraction) for b in data]
    upper = max(w[key] for item in both for w in item['timeline']['windows']
                for key in ['scheduled_not_sent_excluding_local_drops', 'network_inflight'])
    for column, backend in enumerate(data):
        item = next(x for x in data[backend] if x['case']['label'] == 'teacher-open-'+fraction)
        ax = axes[row, column]
        windows = item['timeline']['windows']
        for key, label, color in [('scheduled_not_sent_excluding_local_drops', 'Scheduled but not sent', '#2366af'),
                                  ('network_inflight', 'Sent but not completed', '#df7a17')]:
            ax.plot([x['elapsed_s'] for x in windows], [x[key] for x in windows], label=label, color=color, marker='.', linewidth=1.8)
        ax.set_title(f"{display[backend]} / {int(float(fraction)*100)}% / target {item['case']['rate']:.3f} images/s")
        ax.set_ylim(0, max(1, upper*1.12))
        ax.set_xticks([0, 30, 60, 90, 120, 150, 180])
        ax.set_xlabel('Seconds after each formal run starts')
        ax.set_ylabel('Requests / planned slots')
        ax.grid(alpha=.22)
        if row == 0 and column == 0:
            ax.legend(loc='upper left', frameon=False, fontsize=9)
fig.tight_layout(rect=(.01, .065, .995, .95), h_pad=2)
save(fig, 'teacher-open-backlog', 'Unsent schedule backlog is separated from network in-flight requests; neither is a direct measurement of server queue depth. '
     'All teacher HTTP calls eventually succeeded, while delayed sending at high target rates prevents a faithful arrival-capacity claim. '
     'Panels share a vertical scale within each row; resource details and pending single/dual-generator checks are in the reports.')


fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
fig.suptitle('Bounded C256 diagnostic | fixed 110% arrival targets', y=.99, fontsize=15)
for ax, backend in zip(axes, data):
    item = supplement[backend]
    windows, timeline = item['timeline']['windows'], item['timeline']
    protection = timeline['first_generator_protection_s']
    case = item['case']
    ax.plot([x['elapsed_s'] for x in windows], [x['network_inflight'] for x in windows], label='Network in flight (instantaneous)', color='#2366af', marker='.')
    ax.plot([x['elapsed_s'] for x in windows], [x['generator_dropped'] for x in windows], label='Local unsent slots (cumulative)', color='#df7a17', marker='.')
    ax.axhline(256, color='#777777', linestyle=':', linewidth=1, label='Generator bound: 256')
    ax.axvspan(protection, 180, color='#df7a17', alpha=.08)
    ax.axvline(protection, color='#df7a17', linestyle='--', linewidth=1, label='First local protection')
    attribution = ROOT/f'sync-c256-checkpoint-20261119/evidence/capacity-analysis-20261119-{"pt" if backend == "pytorch" else "trt"}-sync-c256/attribution.json'
    errors = json.loads(attribution.read_text())['read_error_rows']
    ax.axvline(min(x['completed_offset_s'] for x in errors), color='#b72e35', linestyle='--', linewidth=1, label='First ReadError completion')
    ax.set_title(f"{display[backend]} / target {case['rate']:.3f} images/s\nReadError: {len(errors)}; local unsent: {timeline['local_generator_drops']}")
    ax.set_xlim(0, 180)
    ax.set_ylim(0, 290)
    ax.set_xticks([0, 30, 60, 90, 120, 150, 180])
    ax.set_xlabel('Seconds from formal start')
    ax.grid(alpha=.22)
axes[0].set_ylabel('Requests / planned slots')
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .12), ncol=3, frameon=False, fontsize=9)
fig.tight_layout(rect=(.01, .25, .995, .89))
save(fig, 'sync-c256-backlog', 'Both backends showed increasing in-flight counts before local protection. Shaded intervals have censored input. '
     'ReadError has no recorded HTTP status or underlying TCP cause; these failed high-rate points are not recommendations. No further C increase is planned.')

csv_path = OUT/'case-metrics.csv'
with csv_path.open('x') as stream:
    fields = ['backend', 'case', 'I', 'C', 'b', 'window_s', 'success', 'failed_slots', 'window_images_s', 'p50_ms', 'p95_ms', 'p99_ms', 'mean_ms', 'gpu_mean_percent', 'generator_cpu_one_core_mean_percent']
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for backend, items in data.items():
        for item in items+[supplement[backend]]:
            case, summary, resource = item['case'], item['case']['summary'], item['resources']
            latency = summary['successful_image_latency_ms']
            writer.writerow(dict(zip(fields, [backend, case['label'], case['instances'], case['concurrency'], case['max_batches'],
                summary['send_window_s'], summary['successful'], summary['failed'], summary['success_images_per_s_in_window'],
                latency['p50'], latency['p95'], latency['p99'], latency['mean'], resource['gpu']['utilization_percent']['mean'],
                resource['roles']['load_generator']['cpu_percent_one_core_100']['mean']])))
artifacts += [csv_path, OUT/'plot.py']
requirements = OUT/'requirements.txt'
requirements.write_text(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True))
artifacts.append(requirements)
manifest = {'scope': 'original_143_cases_and_two_C256_supplements; paired/audit/trace/dual-generator results pending',
            'original_cases': 143, 'exploration_cases_plotted': 83, 'c256_cases': 2,
            'python': sys.version, 'matplotlib': matplotlib.__version__, 'source_sha256': fingerprints,
            'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in artifacts}}
(OUT/'manifest.json').open('x').write(json.dumps(manifest, indent=2))
print(json.dumps({'plots': 4, 'data_rows': 145, 'output': str(OUT)}))
