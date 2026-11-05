"""Tests for Module D: guided questionnaire store.

Pure unittest style (no pytest dependency) so CI's
`python -m unittest discover -s tests` collects and runs them on
Python 3.9 / 3.13 without extra packages.

Tests cover:
  - questionnaire.py: get_step, list_all, get_by_dimension, list_dimensions,
    upsert, bulk_upsert, next_step
  - seed_knowledge.py: GUIDED_QUESTIONS_DATA populates all 12 steps
  - tools.py: questionnaire_get_step, questionnaire_list, questionnaire_next,
    questionnaire_dimensions actions
"""

import tempfile
import unittest
from pathlib import Path

from travel_shared.db import init_db
from travel_shared.questionnaire import QuestionnaireStore
from travel_shared.seed_knowledge import seed_all
from travel_shared.tools import TravelTools


class QuestionnaireTestCase(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.tmp_db = str(Path(self._tmpdir) / "test_quest.sqlite3")
        init_db(self.tmp_db)
        self.seeded_db = str(Path(self._tmpdir) / "test_seeded_quest.sqlite3")
        init_db(self.seeded_db)
        seed_all(self.seeded_db)


# ===== QuestionnaireStore tests =====

class TestQuestionnaireStore(QuestionnaireTestCase):

    def test_upsert_and_get_step(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "destination", "你想去哪？", "choice",
                  [{"label": "贵阳", "description": "避暑"}],
                  triggers_skill="travel-requirement-analysis")
        result = qs.get_step(1)
        self.assertTrue(result["found"])
        self.assertEqual(result["dimension"], "destination")
        self.assertEqual(result["question"], "你想去哪？")
        self.assertEqual(result["question_type"], "choice")
        self.assertEqual(result["options"][0]["label"], "贵阳")
        self.assertEqual(result["triggers_skill"], "travel-requirement-analysis")

    def test_get_step_not_found(self):
        qs = QuestionnaireStore(self.tmp_db)
        result = qs.get_step(999)
        self.assertFalse(result["found"])

    def test_list_all(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s1")
        qs.upsert(2, "b", "q2", "fill", triggers_skill="s2")
        result = qs.list_all()
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["steps"][0]["step"], 1)
        self.assertEqual(result["steps"][1]["step"], 2)

    def test_get_by_dimension(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "budget", "预算多少？", "choice", triggers_skill="s")
        qs.upsert(2, "destination", "去哪？", "choice", triggers_skill="s")
        result = qs.get_by_dimension("budget")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["steps"][0]["dimension"], "budget")

    def test_list_dimensions(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s")
        qs.upsert(2, "b", "q2", "choice", triggers_skill="s")
        result = qs.list_dimensions()
        self.assertIn("a", result["dimensions"])
        self.assertIn("b", result["dimensions"])

    def test_bulk_upsert(self):
        qs = QuestionnaireStore(self.tmp_db)
        entries = [
            {"step": 1, "dimension": "a", "question": "q1", "question_type": "choice",
             "options": [{"label": "x"}], "triggers_skill": "s1"},
            {"step": 2, "dimension": "b", "question": "q2", "question_type": "fill",
             "triggers_skill": "s2"},
        ]
        result = qs.bulk_upsert(entries)
        self.assertEqual(result["count"], 2)
        self.assertTrue(qs.get_step(1)["found"])
        self.assertTrue(qs.get_step(2)["found"])

    def test_next_step(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s1")
        qs.upsert(2, "b", "q2", "choice", triggers_skill="s2")
        qs.upsert(3, "c", "q3", "choice", triggers_skill="s3")
        result = qs.next_step(1)
        self.assertTrue(result["found"])
        self.assertEqual(result["step"], 2)

    def test_next_step_none(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s1")
        result = qs.next_step(1)
        self.assertFalse(result["found"])

    def test_upsert_overwrites(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "a", "old question", "choice", triggers_skill="s")
        qs.upsert(1, "a", "new question", "fill", triggers_skill="s")
        result = qs.get_step(1)
        self.assertEqual(result["question"], "new question")
        self.assertEqual(result["question_type"], "fill")

    def test_allow_custom_default_true(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "a", "q", "choice", triggers_skill="s")
        result = qs.get_step(1)
        self.assertTrue(result["allow_custom"])

    def test_is_optional_default_false(self):
        qs = QuestionnaireStore(self.tmp_db)
        qs.upsert(1, "a", "q", "choice", triggers_skill="s")
        result = qs.get_step(1)
        self.assertFalse(result["is_optional"])


# ===== Seed data tests =====

class TestSeedQuestionnaire(QuestionnaireTestCase):

    def test_seed_populates_12_steps(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.list_all()
        self.assertEqual(result["count"], 12)

    def test_seed_step_1_destination(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.get_step(1)
        self.assertTrue(result["found"])
        self.assertEqual(result["dimension"], "destination")
        self.assertEqual(result["question_type"], "choice")
        self.assertGreaterEqual(len(result["options"]), 10)
        self.assertEqual(result["triggers_skill"], "travel-requirement-analysis")

    def test_seed_step_2_departure_fill(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.get_step(2)
        self.assertTrue(result["found"])
        self.assertEqual(result["dimension"], "departure_location")
        self.assertEqual(result["question_type"], "fill")

    def test_seed_step_5_budget_choice(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.get_step(5)
        self.assertTrue(result["found"])
        self.assertEqual(result["dimension"], "budget")
        self.assertEqual(result["question_type"], "choice")
        self.assertTrue(any("经济型" in o["label"] for o in result["options"]))

    def test_seed_step_9_photo_optional(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.get_step(9)
        self.assertTrue(result["found"])
        self.assertEqual(result["dimension"], "photo_needs")
        self.assertEqual(result["triggers_skill"], "x-xiake")
        self.assertTrue(result["is_optional"])

    def test_seed_step_12_contingency(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.get_step(12)
        self.assertTrue(result["found"])
        self.assertEqual(result["dimension"], "contingency_awareness")
        self.assertEqual(result["triggers_skill"], "travel-replanner")

    def test_seed_covers_all_skills(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.list_all()
        all_skills = set()
        for step in result["steps"]:
            all_skills.add(step["triggers_skill"])
        expected = {"travel-requirement-analysis", "multi-platform-travel-planner",
                    "travel-accommodation-advisor", "x-xiake",
                    "travel-plan-review", "travel-handbook-builder",
                    "travel-replanner"}
        self.assertTrue(expected.issubset(all_skills))

    def test_seed_dimensions_in_order(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.list_dimensions()
        dims = result["dimensions"]
        self.assertEqual(dims[0], "destination")
        self.assertEqual(dims[1], "departure_location")
        self.assertEqual(dims[-1], "contingency_awareness")

    def test_seed_next_step_chaining(self):
        qs = QuestionnaireStore(self.seeded_db)
        for step_num in range(1, 12):
            result = qs.next_step(step_num)
            self.assertTrue(result["found"])
            self.assertEqual(result["step"], step_num + 1)

    def test_seed_next_step_after_last(self):
        qs = QuestionnaireStore(self.seeded_db)
        result = qs.next_step(12)
        self.assertFalse(result["found"])

    def test_seed_idempotent(self):
        seed_all(self.seeded_db)
        seed_all(self.seeded_db)
        qs = QuestionnaireStore(self.seeded_db)
        self.assertEqual(qs.list_all()["count"], 12)


# ===== tools.py integration tests =====

class TestToolsQuestionnaireIntegration(QuestionnaireTestCase):

    def test_questionnaire_get_step_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "questionnaire_get_step", "step": 1},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"]["found"])
        self.assertEqual(result["data"]["dimension"], "destination")

    def test_questionnaire_list_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "questionnaire_list"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["count"], 12)

    def test_questionnaire_next_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "questionnaire_next", "current_step": 5},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["data"]["found"])
        self.assertEqual(result["data"]["step"], 6)

    def test_questionnaire_dimensions_action(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "questionnaire_dimensions"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["data"]["dimensions"]), 12)

    def test_questionnaire_get_step_invalid_step(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "questionnaire_get_step", "step": 0},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "invalid")

    def test_questionnaire_next_invalid_step(self):
        tools = TravelTools(internal_db_path=self.seeded_db)
        result = tools.handle(
            {"action": "questionnaire_next", "current_step": -1},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "invalid")

    def test_seed_action_includes_questionnaire(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        result = tools.handle(
            {"action": "seed"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["data"]["guided_questions"]["count"], 12)

    def test_preference_actions_still_work(self):
        tools = TravelTools(internal_db_path=self.tmp_db)
        result = tools.handle(
            {"action": "get"},
            user_id="test_user",
        )
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()