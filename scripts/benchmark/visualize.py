"""生成私有差异图，原图不修改，不将课堂照片写入 Git。"""
import argparse
import hashlib
import json
from pathlib import Path
try:
    from .compare import load
except ImportError:
    from compare import load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--differences', required=True, type=Path)
    parser.add_argument('--image-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--limit', type=int, default=32)
    args = parser.parse_args()
    import cv2
    import numpy as np
    reference, candidate = load(args.reference), load(args.candidate)
    selected = []
    for line in args.differences.open():
        row = json.loads(line)
        if 'model' not in row or 'matched' not in row:
            continue
        delta = max((m['max_coordinate_delta'] for m in row['matched']), default=0)
        priority = (len(row['missing'])+len(row['added']))*1000+delta
        if priority:
            selected.append((priority, row))
    args.output.mkdir(parents=True, exist_ok=False)
    index = []
    seen = set()
    for priority, row in sorted(selected, key=lambda p:p[0], reverse=True):
        key = tuple(row['key'])
        if key[1] in seen:
            continue
        seen.add(key[1])
        original = cv2.imread(str(args.image_root/key[2]))
        if original is None:
            raise ValueError(f'Cannot read: {key[2]}')
        panels = []
        for label, record, unmatched in [('PyTorch FP16', reference[key], row['missing']), ('TensorRT FP16', candidate[key], row['added'])]:
            prediction = next(p for p in record['predictions'] if p['model']==row['model'])
            canvas = original.copy()
            for i, box in enumerate(prediction['boxes_xyxy_conf_cls']):
                color = (0,0,255) if i in unmatched else (0,180,0)
                x1,y1,x2,y2 = map(int,box[:4])
                cv2.rectangle(canvas,(x1,y1),(x2,y2),color,3 if i in unmatched else 1)
                if i in unmatched:
                    name = prediction['names'].get(str(int(box[5])), str(int(box[5])))
                    cv2.putText(canvas,f'{name} {box[4]:.5f}',(max(0,x1),max(18,y1-4)),cv2.FONT_HERSHEY_SIMPLEX,.55,color,2)
            banner = np.zeros((55,canvas.shape[1],3),dtype=np.uint8)
            cv2.putText(banner,f'{label} | {row["model"]} | boxes={len(prediction["boxes_xyxy_conf_cls"])}',(10,24),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1)
            cv2.putText(banner,'RED: unmatched  GREEN: matched | '+key[2][-95:],(10,46),cv2.FONT_HERSHEY_SIMPLEX,.45,(220,220,220),1)
            panels.append(np.vstack([banner,canvas]))
        filename = f'{len(index):02d}-{hashlib.sha256(str(key).encode()).hexdigest()[:12]}.jpg'
        if not cv2.imwrite(str(args.output/filename),np.hstack(panels)):
            raise RuntimeError('Visualization write failed')
        index.append({'file': filename,'key': key,'model': row['model'],'priority': priority,
                      'missing': len(row['missing']),'added': len(row['added'])})
        if len(index)>=args.limit:
            break
    (args.output/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
    print(json.dumps({'visualizations':len(index),'output':str(args.output)}))


if __name__ == '__main__':
    main()
