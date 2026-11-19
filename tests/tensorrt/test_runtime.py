import importlib
import os
from pathlib import Path
import unittest

class RuntimeTests(unittest.TestCase):
    def api(self):
        try: return importlib.import_module('core.inference_runtime')
        except ModuleNotFoundError: self.fail('TensorRT runtime API is not implemented')

    def test_visible_uuid_mapping_is_preserved_and_conflicts_rejected(self):
        api=self.api(); env={'CUDA_VISIBLE_DEVICES':'GPU-test'}
        api.configure_device(1,env)
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'GPU-test')
        with self.assertRaises(ValueError): api.configure_device('GPU-other',env)
        with self.assertRaises(ValueError): api.configure_device('cpu',env)
        with self.assertRaises(ValueError): api.configure_device(0,{'CUDA_VISIBLE_DEVICES':''})
        env={};api.configure_device('GPU-test',env);self.assertEqual(env['CUDA_VISIBLE_DEVICES'],'GPU-test')

    def test_defaults_are_project_anchored(self):
        api=self.api()
        self.assertEqual(api.resolve_engine_root(''),Path(api.__file__).resolve().parents[1]/'model')
        self.assertEqual(api.resolve_engine_root('private/model'),Path(api.__file__).resolve().parents[1]/'private/model')

    def test_predict_isolation_resets_nms_and_keeps_explicit_override(self):
        api=self.api()
        class Model:
            def __init__(self):self.calls=[]
            def predict(self,*args,**kwargs):self.calls.append(kwargs);return kwargs
        model=Model();api.isolate_predictions(model,[1,3,1088,1920])
        model.predict('image',agnostic_nms=True,conf=0.1)
        result=model.predict('image',conf=0.2)
        self.assertFalse(result['agnostic_nms'])
        self.assertTrue(model.calls[0]['agnostic_nms'])
        self.assertEqual(result['imgsz'],(1088,1920));self.assertTrue(result['half'])
        self.assertEqual(result['conf'],0.2)
        with self.assertRaises(ValueError): model.predict('image',stream=True)

if __name__=='__main__':unittest.main()
