"""按图片、接口、模型和类别匹配 NMS 后框；这是基线一致性，不是真实准确率。"""
import argparse
import collections
import json
from pathlib import Path


def iou(a, b):
    overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    area_a = max(0, a[2]-a[0])*max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0])*max(0, b[3]-b[1])
    return overlap/max(area_a+area_b-overlap, 1e-12)


def match(reference, candidate, threshold):
    # 按 IoU 从高到低贪心一对一匹配，禁止同一框重复匹配。
    pairs = sorted([(iou(a, b), i, j) for i, a in enumerate(reference)
                    for j, b in enumerate(candidate) if int(a[5]) == int(b[5])], reverse=True)
    used_a, used_b, matches = set(), set(), []
    for score, i, j in pairs:
        if score >= threshold and i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            matches.append({'reference_index': i, 'candidate_index': j, 'iou': score,
                            'confidence_delta': candidate[j][4]-reference[i][4],
                            'max_coordinate_delta': max(abs(candidate[j][k]-reference[i][k]) for k in range(4))})
    return {'matched': matches, 'missing': [i for i in range(len(reference)) if i not in used_a],
            'added': [j for j in range(len(candidate)) if j not in used_b]}


def load(path):
    result = {}
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            key = (row['endpoint'], row['image_sha256'], row['image_id'])
            if key in result:
                raise ValueError(f'Duplicate record: {key}')
            result[key] = row
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--iou', type=float, default=0.5)
    args = parser.parse_args()
    if not 0 <= args.iou <= 1:
        parser.error('IoU must be in [0,1]')
    reference, candidate = load(args.reference), load(args.candidate)
    args.output.mkdir(parents=True, exist_ok=False)
    counts = collections.Counter()
    with (args.output / 'differences.jsonl').open('w') as stream:
        for key in sorted(reference.keys() | candidate.keys()):
            a, b = reference.get(key), candidate.get(key)
            if a is None or b is None:
                counts['missing_records' if b is None else 'added_records'] += 1
                stream.write(json.dumps({'key': key, 'error': 'missing_record' if b is None else 'added_record'})+'\n')
                continue
            counts['paired_records'] += 1
            if a['status'] != 200 or b['status'] != 200:
                counts['failed_pairs'] += 1
                stream.write(json.dumps({'key': key, 'error': 'non_200'})+'\n')
                continue
            am = {p['model']: p for p in a['predictions']}
            bm = {p['model']: p for p in b['predictions']}
            for model in sorted(am.keys() | bm.keys()):
                if model not in am or model not in bm:
                    counts['missing_model_pairs'] += 1
                    stream.write(json.dumps({'key': key, 'model': model, 'error': 'model_missing'})+'\n')
                    continue
                result = match(am[model]['boxes_xyxy_conf_cls'], bm[model]['boxes_xyxy_conf_cls'], args.iou)
                for name in ['matched', 'missing', 'added']:
                    counts[name] += len(result[name])
                stream.write(json.dumps({'key': key, 'model': model, **result})+'\n')
    summary = {'evaluation': 'reference_consistency_not_ground_truth_accuracy',
               'algorithm': 'class_aware_greedy_descending_iou', 'iou_threshold': args.iou,
               'counts': dict(counts), 'business_response_comparison': 'pending'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
