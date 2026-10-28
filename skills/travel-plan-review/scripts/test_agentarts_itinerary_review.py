"""AgentArts adapter tests using the synthetic itinerary fixture."""
import json
import unittest

from validate_itinerary import main
from test_validate_itinerary import fixture


class AgentArtsAdapterTests(unittest.TestCase):
    def test_plan_review(self):
        output = main({'plan_json': json.dumps(fixture(), ensure_ascii=False)})
        self.assertEqual(output['status'], 'pass')
        self.assertEqual(json.loads(output['report_json'])['status'], 'pass')

    def test_candidate_review(self):
        plan = fixture()
        output = main({
            'plan_json': json.dumps(plan),
            'candidate_json': json.dumps(plan)
        })
        self.assertEqual(output['status'], 'pass')
        self.assertEqual(json.loads(output['report_json'])['recheck_result']['status'], 'pass')

    def test_invalid_json(self):
        output = main({'plan_json': '{'})
        self.assertEqual(output['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()
