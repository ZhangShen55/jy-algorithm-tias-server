"""Compare complete frozen PT/TRT model cohorts; no ground-truth accuracy claims."""
import argparse
import collections
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.engine_artifacts import MODEL_SPECS, sha256
from scripts.benchmark.compare import match


def validate_boxes(boxes, shape, classes):
    height, width = shape[:2]
    for box in boxes:
        if len(box) != 6 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in box):
            raise ValueError('Nonfinite or malformed box')
        x1,y1,x2,y2,conf,cls = box
        if not (0 <= conf <= 1 and cls == int(cls) and 0 <= cls < classes
                and 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError('Illegal box geometry/confidence/class')


def compare_boxes(reference, candidate):
    return dict(match(reference,candidate,0.5), exact_equal=reference==candidate)


def quantile(values, fraction):
    if not values: return None
    values=sorted(values);at=(len(values)-1)*fraction;lower=int(at);upper=min(lower+1,len(values)-1)
    return values[lower]+(values[upper]-values[lower])*(at-lower)


def summarize(rows):
    pairs=[p for row in rows for p in row['matched']]
    ious=[p['iou'] for p in pairs];conf=[abs(p['confidence_delta']) for p in pairs]
    count_delta=[len(r['candidate_boxes'])-len(r['reference_boxes']) for r in rows]
    return {'images':len(rows),'changed_images':sum(not r['exact_equal'] for r in rows),
        'reference_boxes':sum(len(r['reference_boxes']) for r in rows),
        'candidate_boxes':sum(len(r['candidate_boxes']) for r in rows),
        'reference_positive_images':sum(bool(r['reference_boxes']) for r in rows),
        'candidate_positive_images':sum(bool(r['candidate_boxes']) for r in rows),
        'matched':len(pairs),'missing':sum(len(r['missing']) for r in rows),'added':sum(len(r['added']) for r in rows),
        'mean_iou':statistics.mean(ious) if ious else None,'median_iou':quantile(ious,.5),
        'p5_iou':quantile(ious,.05),'min_iou':min(ious,default=None),
        'mean_absolute_confidence_delta':statistics.mean(conf) if conf else None,
        'p95_absolute_confidence_delta':quantile(conf,.95),'max_absolute_confidence_delta':max(conf,default=None),
        'max_coordinate_delta':max((p['max_coordinate_delta'] for p in pairs),default=None),
        'count_changed_images':sum(x!=0 for x in count_delta),'max_absolute_count_delta':max(map(abs,count_delta),default=0)}


def load_predictions(path):
    result={}
    with Path(path).open() as stream:
        for line in stream:
            row=json.loads(line);key=(row['model'],row['mode'],row['sequence'])
            if key in result:raise ValueError(f'Duplicate output key: {key}')
            validate_boxes(row['boxes'],row['shape'],len(MODEL_SPECS[row['model']]['names']))
            if not row['runtime_fp16']:raise ValueError('Non-FP16 output record')
            result[key]=row
    return result


def build_report(run_root, output, image_root=None):
    run_root,output=Path(run_root),Path(output)
    if output.exists():raise FileExistsError(output)
    reference=load_predictions(run_root/'pytorch/predictions.jsonl')
    candidate=load_predictions(run_root/'tensorrt/predictions.jsonl')
    if set(reference)!=set(candidate) or len(reference)!=500:raise ValueError('Expected complete matching 500-call outputs')
    frozen=json.loads((run_root/'cohort/samples.json').read_text())
    for backend in ['pytorch','tensorrt']:
        provenance=json.loads((run_root/backend/'provenance.json').read_text())
        if provenance['samples_sha256']!=sha256(run_root/'cohort/samples.json'):raise ValueError('Frozen cohort SHA mismatch')
        result=json.loads((run_root/backend/'result.json').read_text())
        if result['successful']!=500 or result['failed']!=0 or result['predictions_sha256']!=sha256(run_root/backend/'predictions.jsonl'):
            raise ValueError('Output summary/SHA mismatch')
    rows=[];groups=collections.defaultdict(list)
    for key in sorted(reference):
        a,b=reference[key],candidate[key];model,mode,seq=key
        sample=frozen['models'][model][seq]
        if (a['image_id'],a['image_sha256'])!=(sample['image_id'],sample['sha256']):raise ValueError('Output cohort differs')
        for field in ['image_id','image_sha256','selection','shape','names','parameters']:
            if a[field]!=b[field]:raise ValueError(f'Unfair comparison: {field}')
        if a['weight_dtype']!='torch.float16':raise ValueError('PT weights are not HALF')
        row=dict(compare_boxes(a['boxes'],b['boxes']),model=model,mode=mode,sequence=seq,
            image_id=a['image_id'],image_sha256=a['image_sha256'],selection=a['selection'],
            reference_boxes=a['boxes'],candidate_boxes=b['boxes'])
        rows.append(row);groups[(model,mode)].append(row)
    for group,items in groups.items():
        if len(items)!=100 or {r['sequence'] for r in items}!=set(range(100)):raise ValueError(f'Incomplete group: {group}')
    expected={(m,mode) for m in MODEL_SPECS for mode in (['legacy_true','student_false'] if m=='person_count' else ['default_false'])}
    if set(groups)!=expected:raise ValueError('Missing/extra model groups')
    output.mkdir(parents=True,exist_ok=False)
    with (output/'differences.jsonl').open('x') as stream:
        for row in rows:stream.write(json.dumps(row)+'\n')
    summary={'evaluation':'relative_to_pytorch_fp16_not_ground_truth_accuracy','model_image_pairs':400,
        'formal_calls_per_backend':500,'matching':'same_class_greedy_descending_iou_ge_0.5_not_acceptance_threshold',
        'user_difference_review':'pending','sampling':'80_random_plus_up_to20_historical_difference_separate_layers',
        'source_sha256':{str(p.relative_to(run_root)):sha256(p) for p in [run_root/'cohort/samples.json',run_root/'pytorch/predictions.jsonl',run_root/'tensorrt/predictions.jsonl']},
        'analysis_source_sha256':sha256(Path(__file__)),'groups':[]}
    for (model,mode),items in groups.items():
        classes=[]
        for cls,name in enumerate(MODEL_SPECS[model]['names']):
            filtered=[]
            for row in items:
                a=[b for b in row['reference_boxes'] if b[5]==cls];b=[b for b in row['candidate_boxes'] if b[5]==cls]
                filtered.append(dict(compare_boxes(a,b),reference_boxes=a,candidate_boxes=b))
            classes.append(dict(summarize(filtered),class_id=cls,name=name))
        summary['groups'].append(dict(summarize(items),model=model,mode=mode,per_class=classes,
            layers={layer:summarize([r for r in items if r['selection']==layer]) for layer in ['random','historical_difference','random_fill']}))
    visual_index=[]
    if image_root is not None:
        import cv2
        import numpy as np
        visuals=output/'visuals';visuals.mkdir()
        selected={(r['model'],r['mode'],r['sequence']) for r in rows if r['missing'] or r['added'] or len(r['reference_boxes'])!=len(r['candidate_boxes'])}
        for model in MODEL_SPECS:
            diffs=[r for r in rows if r['model']==model and not r['exact_equal'] and (r['model'],r['mode'],r['sequence']) not in selected]
            diffs.sort(key=lambda r:(max((m['max_coordinate_delta'] for m in r['matched']),default=0),max((abs(m['confidence_delta']) for m in r['matched']),default=0)),reverse=True)
            used=set()
            for row in diffs:
                if row['image_sha256'] in used:continue
                selected.add((row['model'],row['mode'],row['sequence']));used.add(row['image_sha256'])
                if len(used)==10:break
        for model,mode,seq in sorted(selected):
            row=next(r for r in groups[(model,mode)] if r['sequence']==seq)
            path=(Path(image_root)/row['image_id']).resolve()
            if not path.is_relative_to(Path(image_root).resolve()) or sha256(path)!=row['image_sha256']:raise ValueError('Visual source SHA/path invalid')
            image=cv2.imread(str(path));panels=[]
            for label,boxes in [('PT FP16',row['reference_boxes']),('TRT FP16',row['candidate_boxes'])]:
                panel=image.copy();cv2.putText(panel,label,(20,35),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
                for x1,y1,x2,y2,confidence,cls in boxes:
                    cv2.rectangle(panel,(int(x1),int(y1)),(int(x2),int(y2)),(0,255,0),2)
                    cv2.putText(panel,f'{int(cls)} {confidence:.5f}',(int(x1),max(14,int(y1))),cv2.FONT_HERSHEY_SIMPLEX,.45,(0,0,255),1)
                panels.append(panel)
            file=visuals/f'{model}-{mode}-{seq:03}.png'
            if not cv2.imwrite(str(file),np.concatenate(panels,axis=1)):raise ValueError('Failed to write comparison image')
            visual_index.append({'model':model,'mode':mode,'image_id':row['image_id'],'file':str(file.relative_to(output)),'sha256':sha256(file)})
    (output/'visual-index.json').write_text(json.dumps(visual_index,indent=2))
    summary['visuals']=len(visual_index)
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--image-root',type=Path)
    args=parser.parse_args();summary=build_report(**vars(args))
    print(json.dumps({'formal_calls_per_backend':500,'groups':[{k:v for k,v in r.items() if k in ['model','mode','matched','missing','added','count_changed_images','mean_iou','max_coordinate_delta']} for r in summary['groups']],'visuals':summary['visuals']},indent=2))


if __name__=='__main__':main()
