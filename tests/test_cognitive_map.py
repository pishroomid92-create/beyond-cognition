from cognitive_map import build_research_tree_dot


def test_builds_session_step_and_evidence_tree():
    session = {"title": "پرسش آزمایشی"}
    steps = [
        {"id": "s1", "sequence_no": 1, "role": "تحلیل‌گر", "epistemic_status": "نامعلوم / بررسی‌نشده"},
        {"id": "s2", "sequence_no": 2, "parent_step_id": "s1", "role": "منتقد", "epistemic_status": "مستند"},
    ]
    evidence = {"s1": [{"evidence_type": "منبع علمی", "source_title": "منبع اول", "claim": "ادعا"}]}
    dot = build_research_tree_dot(session, steps, evidence)
    assert "پرسش آزمایشی" in dot
    assert "تحلیل‌گر" in dot
    assert "منتقد" in dot
    assert "منبع اول" in dot
    assert "root -> step_0" in dot
    assert "step_0 -> step_1" in dot
    assert "step_0 -> evidence_0_0" in dot


def test_empty_map_has_placeholder_node():
    dot = build_research_tree_dot({"title": "خالی"}, [], {})
    assert "هنوز گرهی ثبت نشده است" in dot
    assert "root -> empty" in dot


def test_labels_are_truncated_and_quoted():
    long_text = 'عنوان "ویژه" ' + ("الف" * 240)
    dot = build_research_tree_dot({"title": long_text}, [], {})
    assert "\\\"ویژه\\\"" in dot
    assert "…" in dot



def test_branching_tree_uses_explicit_parent_relationships():
    steps = [
        {"id": "root-a", "sequence_no": 1, "parent_step_id": None, "role": "تحلیل‌گر"},
        {"id": "child-a", "sequence_no": 2, "parent_step_id": "root-a", "role": "فرضیه‌ساز"},
        {"id": "child-b", "sequence_no": 3, "parent_step_id": "root-a", "role": "منتقد"},
        {"id": "root-b", "sequence_no": 4, "parent_step_id": None, "role": "یادداشت"},
    ]
    dot = build_research_tree_dot({"title": "درخت"}, steps, {})
    assert "root -> step_0" in dot
    assert "step_0 -> step_1" in dot
    assert "step_0 -> step_2" in dot
    assert "root -> step_3" in dot


def test_parent_change_rejects_self_and_descendant_cycles():
    from cognitive_map import would_create_cycle

    steps = [
        {"id": "a", "parent_step_id": None},
        {"id": "b", "parent_step_id": "a"},
        {"id": "c", "parent_step_id": "b"},
    ]
    assert would_create_cycle(steps, "a", "a")
    assert would_create_cycle(steps, "a", "b")
    assert would_create_cycle(steps, "a", "c")
    assert not would_create_cycle(steps, "c", "a")
    assert not would_create_cycle(steps, "b", None)
