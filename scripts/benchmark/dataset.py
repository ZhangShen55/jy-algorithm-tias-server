"""生成与目录位置无关的图像清单，保留所有失败记录。"""
import argparse
import collections
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import cv2
    import numpy as np
    args.output.mkdir(parents=True, exist_ok=False)
    counts = collections.Counter()
    seen = {}
    errors = duplicates = 0
    manifest = args.output / 'dataset.jsonl'
    with manifest.open('w') as out:
        for image in sorted(args.root.rglob('*.jpg')):
            raw = image.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            relative = image.relative_to(args.root).as_posix()
            decoded = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            duplicate = seen.get(checksum)
            record = {'image_id': relative, 'sha256': checksum, 'bytes': len(raw),
                      'source_group': image.parent.relative_to(args.root).as_posix(),
                      'shape': list(decoded.shape) if decoded is not None else None,
                      'exact_duplicate_of': duplicate,
                      'error': 'decode_failed' if decoded is None else None}
            seen.setdefault(checksum, relative)
            errors += decoded is None
            duplicates += duplicate is not None
            counts[relative.split('/')[0]] += 1
            out.write(json.dumps(record, ensure_ascii=False) + '\n')
    summary = {'groups': dict(counts), 'decode_errors': errors, 'exact_duplicates': duplicates,
               'dataset_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
               'near_duplicate_review': 'pending', 'annotation_status': 'none_user_confirmed'}
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
