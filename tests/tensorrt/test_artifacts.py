import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'model'
        self.root.mkdir()

    def api(self):
        try:
            return importlib.import_module('core.engine_artifacts')
        except ModuleNotFoundError:
            self.fail('Engine artifact validation API is not implemented')

    def bundle(self):
        api = self.api()
        manifest = {'schema_version': 1, 'release_id': 'test-r1', 'environment': {
            'os': 'Linux', 'machine': 'x86_64', 'tensorrt': '10.13.3.9',
            'cuda': '13.0', 'driver': '580.126.09', 'torch': '2.12.1+cu130',
            'ultralytics': '8.3.156', 'gpu_name': 'NVIDIA GeForce RTX 3090',
            'compute_capability': [8, 6], 'gpu_uuid': 'GPU-test', 'code_commit': 'a'*40}, 'models': {}}
        for name, spec in api.MODEL_SPECS.items():
            metadata = {'names': dict(enumerate(spec['names'])), 'task': 'detect'}
            header = json.dumps(metadata).encode()
            data = len(header).to_bytes(4, 'little') + header + b'nonempty-test-plan'
            (self.root / f'{name}.engine').write_bytes(data)
            manifest['models'][name] = {'file': f'{name}.engine', 'engine_sha256': hashlib.sha256(data).hexdigest(),
                'source_sha256': 'a'*64, 'onnx_sha256': 'b'*64, 'shape': spec['shape'],
                'names': spec['names'], 'precision': 'fp16', 'tf32_enabled': False,
                'io_tensors': [{'name': 'images', 'dtype': 'float16', 'shape': spec['shape'], 'mode': 'INPUT'},
                    {'name': 'output0', 'dtype': 'float16', 'shape': [1, 4+len(spec['names']), 10], 'mode': 'OUTPUT'}]}
        self.save(manifest)
        return manifest

    def save(self, value):
        (self.root / 'manifest.json').write_text(json.dumps(value))

    def test_valid_bundle_without_gpu_imports(self):
        self.bundle()
        self.assertEqual(set(self.api().validate_bundle(self.root)['models']), set(self.api().MODEL_SPECS))

    def test_missing_engine_and_model_fail(self):
        m = self.bundle()
        (self.root / 'face_count.engine').unlink()
        with self.assertRaisesRegex(ValueError, 'face_count'):
            self.api().validate_bundle(self.root)
        del m['models']['face_count']; self.save(m)
        with self.assertRaises(ValueError): self.api().validate_bundle(self.root)

    def test_hash_tampering_fails(self):
        self.bundle()
        with (self.root / 'student.engine').open('ab') as f: f.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'student.*SHA'): self.api().validate_bundle(self.root)

    def test_invalid_shape_names_precision_and_paths_fail(self):
        m = self.bundle()
        for field, value in [('shape', [1, 3, 640, 640]), ('names', ['wrong']),
                              ('precision', 'fp32'), ('tf32_enabled', True), ('file', '../outside.engine')]:
            with self.subTest(field=field):
                bad = copy.deepcopy(m); bad['models']['student'][field] = value; self.save(bad)
                with self.assertRaises(ValueError): self.api().validate_bundle(self.root)
        self.save(m)
        self.api().validate_bundle(self.root)

    def test_invalid_header_or_wrong_metadata_fails_even_with_valid_hash(self):
        m = self.bundle()
        for data in [b'\xff'*20, b'\x02\x00\x00\x00{}',
                     (22).to_bytes(4,'little')+b'{"names":{"0":"bad"}}'+b'plan']:
            (self.root / 'face_count.engine').write_bytes(data)
            m['models']['face_count']['engine_sha256'] = hashlib.sha256(data).hexdigest(); self.save(m)
            with self.assertRaises(ValueError): self.api().validate_bundle(self.root)

    def test_missing_environment_and_fp32_io_fail(self):
        m = self.bundle(); bad = copy.deepcopy(m); del bad['environment']['tensorrt']; self.save(bad)
        with self.assertRaises(ValueError): self.api().validate_bundle(self.root)
        bad = copy.deepcopy(m); bad['models']['face_count']['io_tensors'][0]['dtype'] = 'float32'; self.save(bad)
        with self.assertRaises(ValueError): self.api().validate_bundle(self.root)

    def test_copy_is_verified_and_refuses_existing_output(self):
        self.bundle(); dest = self.root.parent / 'copy'
        self.api().copy_bundle(self.root, dest)
        self.assertEqual((self.root/'student.engine').read_bytes(), (dest/'student.engine').read_bytes())
        with self.assertRaises(FileExistsError): self.api().copy_bundle(self.root, dest)
        self.assertTrue((self.root/'student.engine').exists())


if __name__ == '__main__': unittest.main()

class LegacyImportTests(unittest.TestCase):
    setUp = ArtifactTests.setUp
    api = ArtifactTests.api
    bundle = ArtifactTests.bundle
    save = ArtifactTests.save
    def test_legacy_import_checks_source_and_preserves_engines(self):
        m=self.bundle(); api=self.api()
        self.assertTrue(hasattr(api,'prepare_legacy_bundle'),'legacy release import not implemented')
        legacy=self.root.parent/'legacy';sources=self.root.parent/'sources';sources.mkdir()
        for name,row in m['models'].items():
            child=legacy/name;child.mkdir(parents=True)
            (sources/f'{name}.pt').write_bytes(b'original-weight')
            (child/f'{name}.onnx').write_bytes(b'original-graph')
            (child/f'{name}.engine').write_bytes((self.root/f'{name}.engine').read_bytes())
            old={'source_sha256':api.sha256(sources/f'{name}.pt'), 'engine_sha256':row['engine_sha256'],
                 'shape':row['shape'],'precision_requested':'fp16','tf32_enabled':False,
                 'io_tensors':[dict(t,dtype='DataType.HALF') for t in row['io_tensors']]}
            (child/'build-manifest.json').write_text(json.dumps(old))
        output=self.root.parent/'release'
        api.prepare_legacy_bundle(legacy,sources,output,m['environment'])
        self.assertEqual((output/'student.engine').read_bytes(),(self.root/'student.engine').read_bytes())
        (sources/'student.pt').write_bytes(b'wrong-weight')
        with self.assertRaises(ValueError):api.prepare_legacy_bundle(legacy,sources,self.root.parent/'invalid',m['environment'])
        self.assertFalse((self.root.parent/'invalid/manifest.json').exists())
