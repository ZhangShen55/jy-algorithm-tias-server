from pathlib import Path
import tempfile
import unittest
from core.model_protection import ModelPathResolver, ModelProtectionConfig, generate_key, encrypt_model_file
from scripts.protect_vbas_models import protect_models

class ProtectionTests(unittest.TestCase):
    def test_missing_engine_preflight_leaves_no_partial_ciphertext(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'src';source.mkdir();(source/'person_count.engine').write_bytes(b'engine')
            with self.assertRaises(FileNotFoundError):
                protect_models(source, root/'enc', generate_key(), ['person_count.engine','face_count.engine'])
            self.assertFalse((root/'enc/person_count.engine.enc').exists())

    def test_workers_have_separate_paths_and_cleanup_does_not_cross_delete(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);enc=root/'enc';enc.mkdir();key=generate_key();keyfile=root/'key';keyfile.write_text(key)
            plain=root/'model.engine';plain.write_bytes(b'engine')
            encrypt_model_file(plain,enc/'model.engine.enc',key)
            config=ModelProtectionConfig(True,enc,root/'tmp',keyfile,True)
            first,second=ModelPathResolver(config),ModelPathResolver(config)
            a=first.prepare_model_path(plain);b=second.prepare_model_path(plain)
            self.assertNotEqual(a,b,'workers must not share a decrypted path')
            self.assertEqual(a.parent.stat().st_mode & 0o777,0o700)
            first.cleanup();self.assertFalse(a.exists());self.assertTrue(b.exists())
            self.assertEqual(b.read_bytes(),plain.read_bytes());second.cleanup()
            self.assertTrue(keyfile.exists());self.assertTrue(plain.exists())

if __name__=='__main__':unittest.main()

class RuntimeFailureCleanupTests(unittest.TestCase):
    def test_failed_release_validation_removes_decrypted_files_even_if_keep_after_success(self):
        from types import SimpleNamespace
        from core.inference_runtime import load_models
        from core.engine_artifacts import MODEL_SPECS
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);enc=root/'enc';enc.mkdir();key=generate_key();keyfile=root/'key';keyfile.write_text(key)
            for name in MODEL_SPECS:
                plain=root/f'{name}.engine';plain.write_bytes(b'not-a-valid-engine')
                encrypt_model_file(plain,enc/f'{name}.engine.enc',key)
            resolver=ModelPathResolver(ModelProtectionConfig(True,enc,root/'tmp',keyfile,False))
            config=SimpleNamespace(InferenceBackend='tensorrt',InferenceHalf=True,EngineRoot=str(root))
            with self.assertRaises(ValueError):load_models(config,resolver)
            self.assertFalse(list((root/'tmp').rglob('*.engine')),'failure must always clean decrypted files')
