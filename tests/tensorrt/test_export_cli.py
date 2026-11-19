from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class ExportCliTests(unittest.TestCase):
    def test_missing_sources_and_existing_output_fail_before_gpu_import(self):
        script=Path(__file__).resolve().parents[2]/'scripts/export_tensorrt_models.py'
        self.assertTrue(script.exists(), 'export command not implemented')
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);output=base/'output';output.mkdir()
            for target in [output,base/'new']:
                r=subprocess.run([sys.executable,str(script),'--source-root',str(base/'missing'),
                    '--output',str(target),'--device','GPU-test'],capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0)
                self.assertNotIn('ModuleNotFoundError',r.stderr)
                self.assertFalse((target/'manifest.json').exists())
            self.assertFalse((base/'new').exists())

if __name__=='__main__':unittest.main()
