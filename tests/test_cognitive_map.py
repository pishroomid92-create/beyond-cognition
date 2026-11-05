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


def test_interactive_graph_data_contains_branching_nodes_and_evidence():
    from cognitive_map import build_interactive_graph_data

    session = {"title": "پژوهش تعاملی"}
    steps = [
        {"id": "a", "sequence_no": 1, "parent_step_id": None, "role": "تحلیل‌گر"},
        {"id": "b", "sequence_no": 2, "parent_step_id": "a", "role": "منتقد"},
        {"id": "c", "sequence_no": 3, "parent_step_id": "a", "role": "فرضیه‌ساز"},
    ]
    evidence = {"b": [{"source_title": "سند آزمایشی", "evidence_type": "سند رسمی"}]}
    nodes, edges = build_interactive_graph_data(session, steps, evidence)
    node_ids = {node["id"] for node in nodes}
    edge_pairs = {(edge["source"], edge["target"]) for edge in edges}
    assert "root" in node_ids
    assert "step:a" in node_ids and "step:b" in node_ids and "step:c" in node_ids
    assert any(node["id"].startswith("evidence:b:") for node in nodes)
    assert ("step:a", "step:b") in edge_pairs
    assert ("step:a", "step:c") in edge_pairs


def test_interactive_graph_empty_state_is_renderable():
    from cognitive_map import build_interactive_graph_data

    nodes, edges = build_interactive_graph_data({"title": "خالی"}, [], {})
    assert {node["id"] for node in nodes} == {"root", "empty"}
    assert edges == [{"source": "root", "target": "empty"}]
