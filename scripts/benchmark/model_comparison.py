"""Freeze per-model cohorts and collect standalone PT/TRT post-NMS predictions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.engine_artifacts import MODEL_SPECS, sha256, validate_bundle

ENDPOINTS = {'person_count': '/AE/SyncTasks2', 'face_count': '/AE/SyncTasks2',
             'student': '/ImageDetect/student/v1.0.0', 'teacher_behavior': '/ImageDetect/teacher/v1.0.0'}
ALIASES = {'person_count': 'yolo_person_model', 'face_count': 'yolo_face_model',
           'student': 'yolo_student_model', 'teacher_behavior': 'yolo_teacher_behavior_model'}


def select_samples(rows, historical_hashes, seed):
    unique = {}
    for row in sorted(rows, key=lambda r: (r['image_id'], r['sha256'])):
        unique.setdefault(row['sha256'], row)
    rows = list(unique.values())
    if len(rows) < 100:
        raise ValueError('At least 100 distinct image contents are required')
    rng = random.Random(seed)
    random_rows = rng.sample(rows, 80)
    used = {r['sha256'] for r in random_rows}
    candidates = [r for r in rows if r['sha256'] in historical_hashes and r['sha256'] not in used]
    enriched = candidates[:20]
    used.update(r['sha256'] for r in enriched)
    fill = rng.sample([r for r in rows if r['sha256'] not in used], 20 - len(enriched))
    return ([dict(r, selection='random') for r in random_rows]
            + [dict(r, selection='historical_difference') for r in enriched]
            + [dict(r, selection='random_fill') for r in fill])


def historical_predictions(path):
    data = {}
    with Path(path).open() as stream:
        for line in stream:
            row = json.loads(line)
            for model, alias in ALIASES.items():
                if row['endpoint'] != ENDPOINTS[model]: continue
                prediction = next((p for p in row['predictions'] if p['model'] == alias), None)
                if prediction is not None:
                    key = (model, row['image_id'], row['image_sha256'])
                    if key in data: raise ValueError(f'Duplicate historical record: {key}')
                    data[key] = {'boxes': prediction['boxes_xyxy_conf_cls'], 'args': prediction['predict_args']}
    return data


def freeze(dataset, pt_reference, trt_reference, output):
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    reference, candidate = historical_predictions(pt_reference), historical_predictions(trt_reference)
    rows = [json.loads(line) for line in Path(dataset).read_text().splitlines()]
    result = {'schema_version': 1, 'seed': 20261119, 'sampler': 'python_random_sample_80_then_sorted_history20_v1',
        'source_sha256': {str(p): sha256(p) for p in [dataset, pt_reference, trt_reference]},
        'models': {}, 'parameters': {}}
    for model in MODEL_SPECS:
        pool = [r for r in rows if r['image_id'].startswith('teacher_test_img/' if model == 'teacher_behavior' else 'student_test_img/') and not r.get('error')]
        history = {key[2] for key in reference.keys() & candidate.keys() if key[0] == model
                   and reference[key]['boxes'] != candidate[key]['boxes']}
        result['models'][model] = select_samples(pool, history, result['seed'])
        model_args = [value['args'] for key, value in reference.items() if key[0] == model]
        confs = {args['conf'] for args in model_args}
        if len(confs) != 1: raise ValueError(f'{model}: historical confidence is not uniform')
        result['parameters'][model] = {'conf': confs.pop(), 'iou': 0.7, 'max_det': 300,
            'rect': False, 'half': True, 'verbose': False, 'imgsz': MODEL_SPECS[model]['shape'][2:],
            'agnostic_nms': False}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'samples.json').write_text(json.dumps(result, indent=2))
    for model, selected in result['models'].items():
        (output / f'{model}.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in selected))
    (output / 'freeze-result.json').write_text(json.dumps({'samples_sha256': sha256(output/'samples.json'),
        'models': {name: len(rows) for name, rows in result['models'].items()}, 'frozen_unix': time.time()}, indent=2))
    return result


def collect(samples, backend, image_root, pt_root, engine_root, output, device):
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    cohort = json.loads(Path(samples).read_text())
    if set(cohort['models']) != set(MODEL_SPECS): raise ValueError('Incomplete cohort')
    for name, rows in cohort['models'].items():
        if len(rows) != 100 or len({r['sha256'] for r in rows}) != 100: raise ValueError(f'{name}: invalid cohort')
    manifest = validate_bundle(engine_root)
    for name, row in manifest['models'].items():
        if sha256(Path(pt_root)/f'{name}.pt') != row['source_sha256']: raise ValueError(f'{name}: PT source differs from Engine')
    os.environ['CUDA_VISIBLE_DEVICES'] = device
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    from core.inference_runtime import isolate_predictions
    if not device.startswith('GPU-') or not torch.cuda.is_available(): raise ValueError('Explicit CUDA GPU required')
    output.mkdir(parents=True, exist_ok=False)
    provenance = {'backend': backend, 'samples_sha256': sha256(samples), 'engine_manifest_sha256': sha256(Path(engine_root)/'manifest.json'),
        'source_git_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'device_uuid': device, 'torch': torch.__version__, 'cuda': torch.version.cuda,
        'parameters': cohort['parameters'], 'formal_expected': 500, 'warmup': 'one_zero_image_per_model_excluded',
        'preprocessing': 'same_fixed_imgsz_rect_false_for_both_backends', 'started_unix': time.time()}
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2))
    count = 0
    with (output/'predictions.jsonl').open('x') as stream:
        for name, spec in MODEL_SPECS.items():
            path = Path(pt_root)/f'{name}.pt' if backend == 'pytorch' else Path(engine_root)/f'{name}.engine'
            model = YOLO(str(path), task='detect')
            if backend == 'pytorch': model.to('cuda:0')
            else: isolate_predictions(model, spec['shape'])
            params = cohort['parameters'][name]
            model.predict(np.zeros((*spec['shape'][2:],3),dtype=np.uint8),device=0,**params)
            if not model.predictor.model.fp16: raise ValueError(f'{name}: runtime is not FP16')
            if backend == 'tensorrt' and not model.predictor.model.engine: raise ValueError(f'{name}: runtime is not TensorRT')
            modes = [('legacy_true', True), ('student_false', False)] if name == 'person_count' else [('default_false', False)]
            for mode, agnostic in modes:
                for sequence, row in enumerate(cohort['models'][name]):
                    path = (Path(image_root)/row['image_id']).resolve()
                    if not path.is_relative_to(Path(image_root).resolve()): raise ValueError('Image path escapes dataset root')
                    if sha256(path) != row['sha256']: raise ValueError(f'Image SHA mismatch: {row["image_id"]}')
                    raw = path.read_bytes(); image = cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
                    if image is None: raise ValueError(f'Image decode failed: {row["image_id"]}')
                    kwargs = dict(params, agnostic_nms=agnostic)
                    start = time.perf_counter()
                    result = model.predict(image,device=0,**kwargs)[0]
                    boxes = result.boxes.data.cpu().tolist()
                    elapsed = (time.perf_counter()-start)*1000
                    names = [result.names[i] for i in range(len(result.names))]
                    if names != spec['names']: raise ValueError(f'{name}: actual class mapping differs')
                    if not np.isfinite(np.asarray(boxes,dtype=np.float64)).all(): raise ValueError(f'{name}: invalid numeric output')
                    stream.write(json.dumps({'model':name,'mode':mode,'sequence':sequence,'image_id':row['image_id'],
                        'image_sha256':row['sha256'],'selection':row['selection'],'shape':list(image.shape),
                        'names':names,'boxes':boxes,'parameters':kwargs,'runtime_fp16':True,
                        'weight_dtype':str(next(model.model.parameters()).dtype) if backend=='pytorch' else None,
                        'elapsed_ms':elapsed})+'\n');stream.flush();count+=1
            del result, model
            import gc
            gc.collect()
    if count != 500: raise ValueError(f'Incomplete formal calls: {count}')
    (output/'result.json').write_text(json.dumps({'successful':count,'failed':0,'predictions_sha256':sha256(output/'predictions.jsonl'),
        'elapsed_s':time.time()-provenance['started_unix']},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    f=commands.add_parser('freeze')
    for arg in ['dataset','pt-reference','trt-reference','output']:f.add_argument('--'+arg,type=Path,required=True)
    c=commands.add_parser('collect')
    for arg in ['samples','image-root','pt-root','engine-root','output']:c.add_argument('--'+arg,type=Path,required=True)
    c.add_argument('--backend',choices=['pytorch','tensorrt'],required=True);c.add_argument('--device',required=True)
    args=vars(parser.parse_args());command=args.pop('command')
    existed_before=args['output'].exists()
    try:
        if command=='freeze': freeze(**args)
        else: collect(**args)
    except Exception:
        import traceback
        output=args['output']
        if not existed_before and output.is_dir(): (output/'controller-error.txt').write_text(traceback.format_exc())
        raise


if __name__=='__main__':main()
