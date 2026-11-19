import importlib
import unittest

class SamplingTests(unittest.TestCase):
    def api(self):
        try:return importlib.import_module('scripts.benchmark.model_comparison')
        except ModuleNotFoundError:self.fail('model comparison sampler not implemented')

    def test_sample_is_content_unique_repeatable_and_labels_enrichment(self):
        api=self.api()
        rows=[{'image_id':f'{i:04}.jpg','sha256':f'{i:064x}'} for i in range(140)]
        rows.append(dict(rows[0],image_id='duplicate.jpg'))
        first=api.select_samples(rows,{f'{i:064x}' for i in range(140)},20261119)
        second=api.select_samples(list(reversed(rows)),{f'{i:064x}' for i in range(140)},20261119)
        self.assertEqual(first,second);self.assertEqual(len(first),100)
        self.assertEqual(len({r['sha256'] for r in first}),100)
        self.assertEqual(sum(r['selection']=='random' for r in first),80)
        self.assertEqual(sum(r['selection']=='historical_difference' for r in first),20)

    def test_insufficient_distinct_inputs_is_an_error_and_missing_history_is_filled(self):
        api=self.api()
        with self.assertRaises(ValueError):api.select_samples([{'image_id':'x','sha256':'same'}]*140,set(),20261119)
        rows=[{'image_id':str(i),'sha256':str(i)} for i in range(100)]
        selected=api.select_samples(rows,set(),20261119)
        self.assertEqual(len(selected),100)
        self.assertEqual(sum(r['selection']=='random_fill' for r in selected),20)

if __name__=='__main__':unittest.main()
