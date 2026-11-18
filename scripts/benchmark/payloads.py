"""由已保存基线重建本轮全图请求池，逐图校验内容，不写入 Git。"""
import argparse
import base64
import collections
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--image-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    counters = collections.Counter()
    manifests = collections.defaultdict(list)
    names = {'/AE/SyncTasks2': 'sync', '/ImageDetect/student/v1.0.0': 'student', '/ImageDetect/teacher/v1.0.0': 'teacher'}
    for line in args.reference.open():
        row = json.loads(line)
        if row['status'] != 200:
            raise ValueError('Reference has unsuccessful HTTP records')
        name = names[row['endpoint']]
        raw = (args.image_root/row['image_id']).read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum != row['image_sha256']:
            raise ValueError(f'Image changed since baseline: {row["image_id"]}')
        body = row['request']
        if name == 'sync':
            items = body.get('ImageList', [{'ImageID': row['image_id']}])
            items[0]['Data'] = base64.b64encode(raw).decode()
        else:
            items = body.get('ImageList', [{'ImageId': row['image_id']}])
            items[0]['StoragePath'] = base64.b64encode(raw).decode()
        body['ImageList'] = items
        folder = args.output/name
        folder.mkdir(exist_ok=True)
        filename = f'{counters[name]:05d}.json'
        encoded = json.dumps(body, ensure_ascii=False).encode()
        (folder/filename).write_bytes(encoded)
        manifests[name].append({'payload': filename, 'image_id': row['image_id'], 'image_sha256': checksum,
                                'payload_sha256': hashlib.sha256(encoded).hexdigest()})
        counters[name] += 1
    for name, records in manifests.items():
        (args.output/f'{name}-manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(json.dumps(dict(counters)))


if __name__ == '__main__':
    main()
