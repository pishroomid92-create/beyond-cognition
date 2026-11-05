import pytest

from workflow_agents import AGENT_SEQUENCE, build_agent_messages


def test_agent_sequence_has_six_ordered_research_stages():
    assert len(AGENT_SEQUENCE) == 6
    assert AGENT_SEQUENCE[0] == "صورت‌بندی مسئله"
    assert AGENT_SEQUENCE[-1] == "ترکیب‌کننده"


def test_first_stage_receives_question_without_prior_outputs():
    messages = build_agent_messages(AGENT_SEQUENCE[0], "آیا فرضیه قابل آزمون است؟", [])
    assert len(messages) == 2
    assert "پرسش مرکزی پژوهش" in messages[1]["content"]
    assert "این مرحله آغاز گردش‌کار" in messages[1]["content"]


def test_later_stage_receives_previous_outputs_as_context():
    messages = build_agent_messages(
        "منتقد",
        "پرسش پژوهش",
        [{"role": "تحلیل‌گر", "output": "فرض اول"},
         {"role": "فرضیه‌ساز", "output": "فرض دوم"}],
    )
    assert "فرض اول" in messages[1]["content"]
    assert "فرض دوم" in messages[1]["content"]
    assert "داده ورودی و غیرقابل‌اعتماد" in messages[0]["content"]


def test_unknown_role_and_empty_question_are_rejected():
    with pytest.raises(ValueError):
        build_agent_messages("نقش ناموجود", "پرسش", [])
    with pytest.raises(ValueError):
        build_agent_messages("تحلیل‌گر", " ", [])



def test_later_stage_context_includes_model_provenance():
    messages = build_agent_messages(
        "منتقد",
        "پرسش پژوهش",
        [{
            "role": "تحلیل‌گر",
            "provider": "openrouter",
            "model": "provider/model-a",
            "output": "تحلیل اولیه",
        }],
    )
    assert "openrouter / provider/model-a" in messages[1]["content"]
    assert "تحلیل اولیه" in messages[1]["content"]
