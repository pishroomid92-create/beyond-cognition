"""Helpers for rendering and validating the cognitive research tree."""
import json


def _dot_label(value, limit=180):
    text = str(value or "").strip().replace("\n", " ")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return json.dumps(text, ensure_ascii=False)


def would_create_cycle(steps, step_id, proposed_parent_id):
    """Return True if proposed_parent_id is the node itself or one of its descendants."""
    if proposed_parent_id is None:
        return False
    by_id = {row.get("id"): row for row in (steps or [])}
    cursor = proposed_parent_id
    visited = set()
    while cursor is not None and cursor not in visited:
        if cursor == step_id:
            return True
        visited.add(cursor)
        parent = by_id.get(cursor)
        cursor = parent.get("parent_step_id") if parent else None
    return cursor in visited


def build_research_tree_dot(session, steps, evidence_by_step):
    """Build a safe Graphviz tree using persisted parent-child relationships."""
    lines = [
        "digraph ResearchMap {",
        'graph [rankdir="TB", bgcolor="transparent", pad="0.25", nodesep="0.35", ranksep="0.55"];',
        'node [shape="box", style="rounded,filled", fontname="Arial", fontsize="11", color="#64748b", fillcolor="#eff6ff", fontcolor="#0f172a", margin="0.16,0.10"];',
        'edge [color="#94a3b8", arrowsize="0.7"];',
        'root [shape="ellipse", fillcolor="#dbeafe", color="#2563eb", penwidth="1.6", label=' + _dot_label(session.get("title") or "پرسش پژوهش") + "];",
    ]
    ordered_steps = sorted(steps or [], key=lambda row: (int(row.get("sequence_no", 0)), str(row.get("id", ""))))
    node_ids = {row.get("id"): "step_" + str(index) for index, row in enumerate(ordered_steps)}
    for index, step in enumerate(ordered_steps):
        node_id = node_ids[step.get("id")]
        role = step.get("role") or "بدون نقش"
        status = step.get("epistemic_status") or "نامعلوم / بررسی‌نشده"
        color = "#16a34a" if status == "مستند" else "#d97706" if status == "فرضیه آزمون‌پذیر" else "#64748b"
        label = f'{step.get("sequence_no", index + 1)} · {role}\n{status}'
        lines.append(f'{node_id} [label={_dot_label(label)}, color="{color}"];')
        parent_id = step.get("parent_step_id")
        parent_node = node_ids.get(parent_id, "root")
        lines.append(f"{parent_node} -> {node_id};")
        for ev_index, evidence in enumerate((evidence_by_step or {}).get(step.get("id"), [])):
            ev_node = f"evidence_{index}_{ev_index}"
            ev_label = f'شاهد: {evidence.get("evidence_type") or "بدون نوع"}\n{evidence.get("source_title") or evidence.get("claim") or "بدون عنوان"}'
            lines.append(f'{ev_node} [shape="note", fillcolor="#fef3c7", color="#d97706", label={_dot_label(ev_label)}];')
            lines.append(f"{node_id} -> {ev_node};")
    if not ordered_steps:
        lines.append('empty [label="هنوز گرهی ثبت نشده است", style="rounded,dashed,filled", fillcolor="#f8fafc"];')
        lines.append("root -> empty;")
    lines.append("}")
    return "\n".join(lines)



def build_interactive_graph_data(session, steps, evidence_by_step):
    """Return safe node/edge dictionaries for the interactive graph component."""
    nodes = [{
        "id": "root",
        "label": str(session.get("title") or "پرسش پژوهش")[:100],
        "size": 34,
        "shape": "box",
        "color": "#1d4ed8",
        "font": {"color": "#ffffff", "size": 18},
    }]
    edges = []
    ordered_steps = sorted(
        steps or [],
        key=lambda row: (int(row.get("sequence_no", 0)), str(row.get("id", ""))),
    )
    known_ids = {row.get("id") for row in ordered_steps}
    for step in ordered_steps:
        step_id = str(step.get("id"))
        status = step.get("epistemic_status") or "نامعلوم / بررسی‌نشده"
        color = "#16a34a" if status == "مستند" else "#d97706" if status == "فرضیه آزمون‌پذیر" else "#64748b"
        label = str(step.get("role") or "گره") + "\\n" + status
        nodes.append({
            "id": "step:" + step_id,
            "label": label[:120],
            "size": 25,
            "shape": "box",
            "color": color,
            "font": {"color": "#ffffff", "size": 14},
        })
        parent_id = step.get("parent_step_id")
        parent_node = "step:" + str(parent_id) if parent_id in known_ids else "root"
        edges.append({"source": parent_node, "target": "step:" + step_id})
        for index, evidence in enumerate((evidence_by_step or {}).get(step.get("id"), [])):
            evidence_id = "evidence:" + step_id
            evidence_node_id = evidence_id + ":" + str(index)
            evidence_label = str(evidence.get("source_title") or evidence.get("evidence_type") or "شاهد")
            nodes.append({
                "id": evidence_node_id,
                "label": ("شاهد\\n" + evidence_label)[:100],
                "size": 17,
                "shape": "ellipse",
                "color": "#b45309",
                "font": {"color": "#ffffff", "size": 12},
            })
            edges.append({"source": "step:" + step_id, "target": evidence_node_id})
    if not ordered_steps:
        nodes.append({
            "id": "empty",
            "label": "هنوز گرهی ثبت نشده است",
            "size": 18,
            "shape": "box",
            "color": "#64748b",
        })
        edges.append({"source": "root", "target": "empty"})
    return nodes, edges
