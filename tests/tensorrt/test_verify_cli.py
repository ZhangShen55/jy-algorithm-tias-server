from pathlib import Path
import subprocess
import sys
import unittest

class VerifyCliTests(unittest.TestCase):
    def test_static_missing_bundle_fails_without_gpu_import(self):
        script=Path(__file__).resolve().parents[2]/'scripts/verify_tensorrt_models.py'
        self.assertTrue(script.exists(), 'verification command not implemented')
        r=subprocess.run([sys.executable,str(script),'--root','/nonexistent/vbas-release'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('manifest',r.stderr)
        self.assertNotIn('ModuleNotFoundError',r.stderr)

if __name__=='__main__':unittest.main()
