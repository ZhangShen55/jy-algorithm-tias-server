"""按图片、接口、模型和类别匹配 NMS 后框；这是基线一致性，不是真实准确率。"""
import argparse
import collections
import json
import statistics
from pathlib import Path


def iou(a, b):
    overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    area_a = max(0, a[2]-a[0])*max(0, a[3]-a[1])
    area_b = max(0, b[2]-b[0])*max(0, b[3]-b[1])
    return overlap/max(area_a+area_b-overlap, 1e-12)


def match(reference, candidate, threshold):
    # 按 IoU 从高到低贪心一对一匹配，禁止同一框重复匹配。
    pairs = sorted([(score, i, j) for i, a in enumerate(reference)
                    for j, b in enumerate(candidate) if int(a[5]) == int(b[5])
                    and (score := iou(a, b)) >= threshold], reverse=True)
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


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items() if k not in {'TimeStamp', 'UseTimeMs', 'FreeCapacity'}}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def business_counts(value, result=None):
    result = collections.Counter() if result is None else result
    if isinstance(value, dict):
        if 'ObjectType' in value and 'ObjectCount' in value:
            result[f'ObjectType:{value["ObjectType"]}'] += value['ObjectCount']
        for name in ['PersonCnt', 'FaceCnt']:
            if name in value:
                result[name] += value[name]
        for v in value.values():
            business_counts(v, result)
    elif isinstance(value, list):
        for v in value:
            business_counts(v, result)
    return result


def business_boxes(value, result=None):
    result = collections.defaultdict(list) if result is None else result
    def append(label, positions):
        for p in positions or []:
            result[label].append([p[k] for k in ['LeftTopX', 'LeftTopY', 'RightBtmX', 'RightBtmY']]+[1., 0])
    if isinstance(value, dict):
        if 'ObjectType' in value:
            append(f'ObjectType:{value["ObjectType"]}', value.get('ObjectPostList'))
        for name in ['Personlist', 'Facelist']:
            if name in value:
                append(name, [p['ROI'] for p in value[name]])
        for v in value.values():
            business_boxes(v, result)
    elif isinstance(value, list):
        for v in value:
            business_boxes(v, result)
    return result


def valid_business(row):
    body = row['response']
    if row['endpoint'] == '/AE/SyncTasks2':
        return body.get('Response', {}).get('ErrCode') == 0 and len(body.get('TaskResult', [])) == 1
    return len(body.get('DataList', [])) == 1 and body['DataList'][0].get('StatusObject', {}).get('StatusCode') == 0


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
    count_deltas = collections.defaultdict(list)
    class_stats = collections.defaultdict(collections.Counter)
    matches_all = []
    geometry_stats = collections.defaultdict(collections.Counter)
    with (args.output / 'differences.jsonl').open('w') as stream:
        for key in sorted(reference.keys() | candidate.keys()):
            a, b = reference.get(key), candidate.get(key)
            if a is None or b is None:
                counts['missing_records' if b is None else 'added_records'] += 1
                stream.write(json.dumps({'key': key, 'error': 'missing_record' if b is None else 'added_record'})+'\n')
                continue
            counts['paired_records'] += 1
            if a['status'] != 200 or b['status'] != 200 or not valid_business(a) or not valid_business(b):
                counts['failed_pairs'] += 1
                stream.write(json.dumps({'key': key, 'error': 'non_200'})+'\n')
                continue
            equal = canonical(a['response']) == canonical(b['response'])
            counts['business_equal_ignoring_timing_and_order' if equal else 'business_changed'] += 1
            ac, bc = business_counts(a['response']), business_counts(b['response'])
            ab, bb = business_boxes(a['response']), business_boxes(b['response'])
            geometry = {}
            for label in ab.keys() | bb.keys():
                matched = match(ab.get(label, []), bb.get(label, []), args.iou)
                geometry[label] = {'matched': len(matched['matched']), 'missing': len(matched['missing']),
                                   'added': len(matched['added']),
                                   'max_coordinate_delta': max((m['max_coordinate_delta'] for m in matched['matched']), default=0)}
                for field in ['matched', 'missing', 'added']:
                    geometry_stats[(key[0], label)][field] += geometry[label][field]
                geometry_stats[(key[0], label)]['max_coordinate_delta'] = max(geometry_stats[(key[0], label)]['max_coordinate_delta'], geometry[label]['max_coordinate_delta'])
            for count_key in ac.keys() | bc.keys():
                count_deltas[(key[0], count_key)].append(bc[count_key]-ac[count_key])
            stream.write(json.dumps({'key': key, 'business_equal_ignoring_timing_and_order': equal,
                                     'reference_counts': dict(ac), 'candidate_counts': dict(bc),
                                     'business_geometry': geometry})+'\n')
            am = {p['model']: p for p in a['predictions']}
            bm = {p['model']: p for p in b['predictions']}
            for model in sorted(am.keys() | bm.keys()):
                if model not in am or model not in bm:
                    counts['missing_model_pairs'] += 1
                    stream.write(json.dumps({'key': key, 'model': model, 'error': 'model_missing'})+'\n')
                    continue
                result = match(am[model]['boxes_xyxy_conf_cls'], bm[model]['boxes_xyxy_conf_cls'], args.iou)
                matches_all.extend(result['matched'])
                reference_boxes, candidate_boxes = am[model]['boxes_xyxy_conf_cls'], bm[model]['boxes_xyxy_conf_cls']
                for item in result['matched']:
                    class_stats[(key[0], model, int(reference_boxes[item['reference_index']][5]))]['matched'] += 1
                for index in result['missing']:
                    class_stats[(key[0], model, int(reference_boxes[index][5]))]['missing'] += 1
                for index in result['added']:
                    class_stats[(key[0], model, int(candidate_boxes[index][5]))]['added'] += 1
                for name in ['matched', 'missing', 'added']:
                    counts[name] += len(result[name])
                stream.write(json.dumps({'key': key, 'model': model, **result})+'\n')
    summary = {'evaluation': 'reference_consistency_not_ground_truth_accuracy',
               'algorithm': 'class_aware_greedy_descending_iou', 'iou_threshold': args.iou,
               'counts': dict(counts),
               'matched_boxes': {'mean_iou': statistics.mean(m['iou'] for m in matches_all) if matches_all else None,
                                 'max_coordinate_delta': max((m['max_coordinate_delta'] for m in matches_all), default=None),
                                 'mean_absolute_confidence_delta': statistics.mean(abs(m['confidence_delta']) for m in matches_all) if matches_all else None},
               'per_class': [{'endpoint': k[0], 'model': k[1], 'class_id': k[2], **v} for k, v in sorted(class_stats.items())],
               'business_geometry': [{'endpoint': k[0], 'key': k[1], **v} for k, v in sorted(geometry_stats.items())],
               'business_counts_relative_to_reference': [{'endpoint': k[0], 'key': k[1], 'images': len(v),
                    'equal_images': sum(d == 0 for d in v), 'mean_absolute_delta': statistics.mean(abs(d) for d in v),
                    'max_absolute_delta': max(abs(d) for d in v), 'signed_total_delta': sum(v)}
                    for k, v in sorted(count_deltas.items())],
               'business_comparison': 'strict_values_after_removing_timing_capacity_and_list_order_not_accuracy_acceptance'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
