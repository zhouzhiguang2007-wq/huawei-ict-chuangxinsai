"""Tests for Module D: guided questionnaire store.

Tests cover:
  - questionnaire.py: get_step, list_all, get_by_dimension, list_dimensions,
    upsert, bulk_upsert, next_step
  - seed_knowledge.py: GUIDED_QUESTIONS_DATA populates all 12 steps
  - tools.py: questionnaire_get_step, questionnaire_list, questionnaire_next,
    questionnaire_dimensions actions
"""

import pytest

from travel_shared.db import init_db
from travel_shared.questionnaire import QuestionnaireStore
from travel_shared.seed_knowledge import seed_all, GUIDED_QUESTIONS_DATA
from travel_shared.tools import TravelTools


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test_quest.sqlite3")
    init_db(db_path)
    return db_path


@pytest.fixture
def seeded_db(tmp_path):
    db_path = str(tmp_path / "test_seeded_quest.sqlite3")
    init_db(db_path)
    seed_all(db_path)
    return db_path


# ===== QuestionnaireStore tests =====

class TestQuestionnaireStore:

    def test_upsert_and_get_step(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "destination", "你想去哪？", "choice",
                  [{"label": "贵阳", "description": "避暑"}],
                  triggers_skill="travel-requirement-analysis")
        result = qs.get_step(1)
        assert result["found"] is True
        assert result["dimension"] == "destination"
        assert result["question"] == "你想去哪？"
        assert result["question_type"] == "choice"
        assert result["options"][0]["label"] == "贵阳"
        assert result["triggers_skill"] == "travel-requirement-analysis"

    def test_get_step_not_found(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        result = qs.get_step(999)
        assert result["found"] is False

    def test_list_all(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s1")
        qs.upsert(2, "b", "q2", "fill", triggers_skill="s2")
        result = qs.list_all()
        assert result["count"] == 2
        assert result["steps"][0]["step"] == 1
        assert result["steps"][1]["step"] == 2

    def test_get_by_dimension(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "budget", "预算多少？", "choice", triggers_skill="s")
        qs.upsert(2, "destination", "去哪？", "choice", triggers_skill="s")
        result = qs.get_by_dimension("budget")
        assert result["count"] == 1
        assert result["steps"][0]["dimension"] == "budget"

    def test_list_dimensions(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s")
        qs.upsert(2, "b", "q2", "choice", triggers_skill="s")
        result = qs.list_dimensions()
        assert "a" in result["dimensions"]
        assert "b" in result["dimensions"]

    def test_bulk_upsert(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        entries = [
            {"step": 1, "dimension": "a", "question": "q1", "question_type": "choice",
             "options": [{"label": "x"}], "triggers_skill": "s1"},
            {"step": 2, "dimension": "b", "question": "q2", "question_type": "fill",
             "triggers_skill": "s2"},
        ]
        result = qs.bulk_upsert(entries)
        assert result["count"] == 2
        assert qs.get_step(1)["found"] is True
        assert qs.get_step(2)["found"] is True

    def test_next_step(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s1")
        qs.upsert(2, "b", "q2", "choice", triggers_skill="s2")
        qs.upsert(3, "c", "q3", "choice", triggers_skill="s3")
        result = qs.next_step(1)
        assert result["found"] is True
        assert result["step"] == 2

    def test_next_step_none(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "a", "q1", "choice", triggers_skill="s1")
        result = qs.next_step(1)
        assert result["found"] is False

    def test_upsert_overwrites(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "a", "old question", "choice", triggers_skill="s")
        qs.upsert(1, "a", "new question", "fill", triggers_skill="s")
        result = qs.get_step(1)
        assert result["question"] == "new question"
        assert result["question_type"] == "fill"

    def test_allow_custom_default_true(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "a", "q", "choice", triggers_skill="s")
        result = qs.get_step(1)
        assert result["allow_custom"] is True

    def test_is_optional_default_false(self, tmp_db):
        qs = QuestionnaireStore(tmp_db)
        qs.upsert(1, "a", "q", "choice", triggers_skill="s")
        result = qs.get_step(1)
        assert result["is_optional"] is False


# ===== Seed data tests =====

class TestSeedQuestionnaire:

    def test_seed_populates_12_steps(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.list_all()
        assert result["count"] == 12

    def test_seed_step_1_destination(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.get_step(1)
        assert result["found"] is True
        assert result["dimension"] == "destination"
        assert result["question_type"] == "choice"
        assert len(result["options"]) >= 10
        assert result["triggers_skill"] == "travel-requirement-analysis"

    def test_seed_step_2_departure_fill(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.get_step(2)
        assert result["found"] is True
        assert result["dimension"] == "departure_location"
        assert result["question_type"] == "fill"

    def test_seed_step_5_budget_choice(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.get_step(5)
        assert result["found"] is True
        assert result["dimension"] == "budget"
        assert result["question_type"] == "choice"
        assert any("经济型" in o["label"] for o in result["options"])

    def test_seed_step_9_photo_optional(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.get_step(9)
        assert result["found"] is True
        assert result["dimension"] == "photo_needs"
        assert result["triggers_skill"] == "x-xiake"
        assert result["is_optional"] is True

    def test_seed_step_12_contingency(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.get_step(12)
        assert result["found"] is True
        assert result["dimension"] == "contingency_awareness"
        assert result["triggers_skill"] == "travel-replanner"

    def test_seed_covers_all_skills(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.list_all()
        all_skills = set()
        for step in result["steps"]:
            all_skills.add(step["triggers_skill"])
        expected = {"travel-requirement-analysis", "multi-platform-travel-planner",
                    "travel-accommodation-advisor", "x-xiake",
                    "travel-plan-review", "travel-handbook-builder",
                    "travel-replanner"}
        assert expected.issubset(all_skills)

    def test_seed_dimensions_in_order(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.list_dimensions()
        dims = result["dimensions"]
        assert dims[0] == "destination"
        assert dims[1] == "departure_location"
        assert dims[-1] == "contingency_awareness"

    def test_seed_next_step_chaining(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        for step_num in range(1, 12):
            result = qs.next_step(step_num)
            assert result["found"] is True
            assert result["step"] == step_num + 1

    def test_seed_next_step_after_last(self, seeded_db):
        qs = QuestionnaireStore(seeded_db)
        result = qs.next_step(12)
        assert result["found"] is False

    def test_seed_idempotent(self, tmp_path):
        db_path = str(tmp_path / "test_idempotent_quest.sqlite3")
        init_db(db_path)
        seed_all(db_path)
        seed_all(db_path)
        qs = QuestionnaireStore(db_path)
        assert qs.list_all()["count"] == 12


# ===== tools.py integration tests =====

class TestToolsQuestionnaireIntegration:

    def test_questionnaire_get_step_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "questionnaire_get_step", "step": 1},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["found"] is True
        assert result["data"]["dimension"] == "destination"

    def test_questionnaire_list_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "questionnaire_list"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["count"] == 12

    def test_questionnaire_next_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "questionnaire_next", "current_step": 5},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["found"] is True
        assert result["data"]["step"] == 6

    def test_questionnaire_dimensions_action(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "questionnaire_dimensions"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert len(result["data"]["dimensions"]) == 12

    def test_questionnaire_get_step_invalid_step(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "questionnaire_get_step", "step": 0},
            user_id="test_user",
        )
        assert result["status"] == "invalid"

    def test_questionnaire_next_invalid_step(self, seeded_db):
        tools = TravelTools(internal_db_path=seeded_db)
        result = tools.handle(
            {"action": "questionnaire_next", "current_step": -1},
            user_id="test_user",
        )
        assert result["status"] == "invalid"

    def test_seed_action_includes_questionnaire(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
        result = tools.handle(
            {"action": "seed"},
            user_id="test_user",
        )
        assert result["status"] == "ok"
        assert result["data"]["guided_questions"]["count"] == 12

    def test_preference_actions_still_work(self, tmp_db):
        tools = TravelTools(internal_db_path=tmp_db)
        result = tools.handle(
            {"action": "get"},
            user_id="test_user",
        )
        assert result["status"] == "ok"