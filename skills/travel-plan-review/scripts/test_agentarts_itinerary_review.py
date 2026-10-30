"""AgentArts adapter tests using the synthetic itinerary fixture."""
import json
import unittest

from validate_itinerary import main
from test_validate_itinerary import fixture


class AgentArtsAdapterTests(unittest.TestCase):
    AS_OF = '2026-11-05T12:00:00+08:00'

    def test_plan_review(self):
        output = main({'plan_json': json.dumps(fixture(), ensure_ascii=False), 'as_of': self.AS_OF})
        self.assertEqual(output['status'], 'pass')
        self.assertEqual(json.loads(output['report_json'])['status'], 'pass')

    def test_candidate_review(self):
        plan = fixture()
        output = main({
            'plan_json': json.dumps(plan),
            'candidate_json': json.dumps(plan),
            'as_of': self.AS_OF
        })
        self.assertEqual(output['status'], 'pass')
        self.assertEqual(json.loads(output['report_json'])['recheck_result']['status'], 'pass')

    def test_invalid_json(self):
        output = main({'plan_json': '{'})
        self.assertEqual(output['status'], 'invalid')

    def test_runtime_flags_departure_already_past(self):
        output = main({'plan_json': json.dumps(fixture()), 'as_of': '2026-11-06T13:35:00+08:00'})
        report = json.loads(output['report_json'])
        self.assertEqual(output['status'], 'fail')
        self.assertTrue(any(check['rule'] == 'past_start' for check in report['issues']))


if __name__ == '__main__':
    unittest.main()
