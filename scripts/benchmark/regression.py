"""冻结两后端共同的快速回归子集；保留所有计数差异和非空类别代表。"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import random

try:
    from .compare import business_counts, load, valid_business
except ImportError:
    from compare import business_counts, load, valid_business


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--samples', type=int, default=64)
    parser.add_argument('--seed', type=int, default=20261118)
    parser.add_argument('--include-image-id', action='append', default=[])
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('样本数必须大于零')
    reference, candidate = load(args.reference), load(args.candidate)
    if reference.keys() != candidate.keys():
        raise ValueError('两后端基线接口/图片ID/SHA集合不同')
    if set(args.include_image_id) - {k[2] for k in reference}:
        raise ValueError('额外指定的图片ID不存在')
    mandatory = collections.defaultdict(set)
    by_endpoint = collections.defaultdict(list)
    counts = {}
    for key, row in reference.items():
        if any(r['status'] != 200 or not valid_business(r) for r in [row, candidate[key]]):
            raise ValueError('失败基线记录不能静默进入回归集')
        by_endpoint[key[0]].append(key)
        a, b = business_counts(row['response']), business_counts(candidate[key]['response'])
        counts[key] = a, b
        if any(a[k] != b[k] for k in a.keys() | b.keys()):
            mandatory[key].add('backend_business_count_difference')
        if key[2] in args.include_image_id:
            mandatory[key].add('explicit_diagnostic_case')
    selected, groups = [], []
    for endpoint, keys in sorted(by_endpoint.items()):
        keys.sort(key=lambda k: k[2])
        labels = sorted({label for key in keys for counter in counts[key]
                         for label, value in counter.items() if value > 0})
        for label in labels:
            key = next(k for k in keys if any(c[label] > 0 for c in counts[k]))
            mandatory[key].add('nonempty_output_representative:'+label)
        chosen = {k for k in keys if mandatory[k]}
        remaining = [k for k in keys if k not in chosen]
        random.Random(args.seed).shuffle(remaining)
        # 不为凑固定64而删掉必须留存的计数差异；超过目标时显式扩大。
        target = min(len(keys), max(args.samples, len(chosen)))
        chosen.update(remaining[:target-len(chosen)])
        chosen = sorted(chosen, key=lambda k: k[2])
        selected.extend(chosen)
        groups.append({'endpoint': endpoint, 'images': len(chosen), 'nonempty_output_labels': labels,
                       'selection': [{'image_id': k[2], 'image_sha256': k[1],
                                      'reasons': sorted(mandatory[k]) or ['seeded_fill']} for k in chosen]})
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in [('torch-reference.jsonl', reference), ('trt-reference.jsonl', candidate)]:
        with (args.output/name).open('w') as stream:
            for key in selected:
                stream.write(json.dumps(rows[key], ensure_ascii=False)+'\n')
    manifest = {'seed': args.seed, 'minimum_images_per_endpoint': args.samples,
                'explicit_image_ids': args.include_image_id,
                'scope': 'diagnostic_regression_not_unbiased_accuracy_evaluation',
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'source_sha256': {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in [args.reference, args.candidate]}, 'groups': groups}
    (args.output/'selection.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({group['endpoint']: group['images'] for group in groups}))


if __name__ == '__main__':
    main()
