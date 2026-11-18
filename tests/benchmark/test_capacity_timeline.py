"""分辨客户端未发送积压、已发送在途与本地保护槽，不依赖模型。"""
import unittest

from scripts.benchmark.summarize_capacity import timeline


class CapacityTimelineTest(unittest.TestCase):
    def test_slow_sender_is_not_network_queue(self):
        records = [{'valid': True, 'planned_offset_s': i,
                    'sent_offset_s': i * 2, 'completed_offset_s': i * 2 + .1}
                   for i in range(40)]
        result = timeline(records, 30, True)
        self.assertIsNotNone(result['first_sustained_backlog_increase'])
        self.assertIsNotNone(result['first_sustained_dispatch_backlog_increase'])
        self.assertIsNone(result['first_sustained_network_inflight_increase'])
        for row in result['windows']:
            self.assertEqual(row['scheduled_unresolved_excluding_local_drops'],
                             row['scheduled_not_sent_excluding_local_drops'] + row['network_inflight'])

    def test_slow_responses_are_already_dispatched(self):
        records = [{'valid': True, 'planned_offset_s': i,
                    'sent_offset_s': i, 'completed_offset_s': i + 100}
                   for i in range(40)]
        result = timeline(records, 30, True)
        self.assertIsNone(result['first_sustained_dispatch_backlog_increase'])
        self.assertIsNotNone(result['first_sustained_network_inflight_increase'])

    def test_local_drops_do_not_become_unsent_queue(self):
        records = [{'valid': False, 'planned_offset_s': i,
                    'error': 'load_generator_inflight_limit'} for i in range(40)]
        result = timeline(records, 30, True)
        self.assertIsNone(result['first_sustained_dispatch_backlog_increase'])
        self.assertIsNone(result['first_sustained_network_inflight_increase'])
        self.assertTrue(all(x['scheduled_not_sent_excluding_local_drops'] == 0
                            for x in result['windows']))

    def test_closed_or_partial_windows_do_not_claim_growth(self):
        records = [{'valid': True, 'planned_offset_s': i,
                    'sent_offset_s': i * 2, 'completed_offset_s': i * 2 + .1}
                   for i in range(40)]
        for seconds, open_loop in [(30, False), (29, True)]:
            result = timeline(records, seconds, open_loop)
            self.assertIsNone(result['first_sustained_dispatch_backlog_increase'])
            self.assertIsNone(result['first_sustained_network_inflight_increase'])


if __name__ == '__main__':
    unittest.main()
