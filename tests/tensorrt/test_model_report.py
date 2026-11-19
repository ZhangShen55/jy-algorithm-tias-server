import importlib
import unittest

class ReportTests(unittest.TestCase):
    def api(self):
        try:return importlib.import_module('scripts.benchmark.model_report')
        except ModuleNotFoundError:self.fail('model comparison report not implemented')

    def test_matching_never_hides_missing_or_added_classes(self):
        api=self.api()
        a=[[0,0,10,10,0.9,0],[10,10,20,20,0.8,1]]
        b=[[0,0,10,10,0.8,0],[10,10,20,20,0.8,2]]
        row=api.compare_boxes(a,b)
        self.assertEqual(len(row['matched']),1);self.assertEqual(row['missing'],[1]);self.assertEqual(row['added'],[1])
        summary=api.summarize([dict(row,reference_boxes=a,candidate_boxes=b)])
        self.assertEqual(summary['reference_boxes'],2);self.assertEqual(summary['candidate_boxes'],2)
        self.assertEqual(summary['missing'],1);self.assertEqual(summary['added'],1)
        self.assertEqual(summary['mean_iou'],1)
        self.assertEqual(summary['count_changed_images'],0)
        self.assertEqual(summary['changed_images'],1)

    def test_illegal_numeric_or_geometry_is_rejected(self):
        api=self.api()
        for b in [[[0,0,10,10,float('nan'),0]],[[10,0,0,10,.9,0]],[[0,0,101,10,.9,0]],[[0,0,10,10,.9,1.5]]]:
            with self.assertRaises(ValueError):api.validate_boxes(b,[100,100,3],2)
        api.validate_boxes([],[100,100,3],2)

if __name__=='__main__':unittest.main()
