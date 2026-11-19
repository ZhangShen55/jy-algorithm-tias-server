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
