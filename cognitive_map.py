"""Graph representation helpers for the interactive research map."""
import json


def _dot_label(value, limit=180):
    text = str(value or "").strip().replace("\\n", " ")
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return json.dumps(text, ensure_ascii=False)


def build_research_tree_dot(session, steps, evidence_by_step):
    """Build a safe Graphviz tree from existing session, step and evidence rows."""
    lines = [
        "digraph ResearchMap {",
        'graph [rankdir="TB", bgcolor="transparent", pad="0.25", nodesep="0.35", ranksep="0.55"];',
        'node [shape="box", style="rounded,filled", fontname="Arial", fontsize="11", color="#64748b", fillcolor="#eff6ff", fontcolor="#0f172a", margin="0.16,0.10"];',
        'edge [color="#94a3b8", arrowsize="0.7"];',
        'root [shape="ellipse", fillcolor="#dbeafe", color="#2563eb", penwidth="1.6", label=' + _dot_label(session.get("title") or "پرسش پژوهش") + "];",
    ]
    ordered_steps = sorted(steps or [], key=lambda row: int(row.get("sequence_no", 0)))
    previous_node = "root"
    for index, step in enumerate(ordered_steps):
        node_id = "step_" + str(index)
        role = step.get("role") or "بدون نقش"
        status = step.get("epistemic_status") or "نامعلوم / بررسی‌نشده"
        color = "#16a34a" if status == "مستند" else "#d97706" if status == "فرضیه آزمون‌پذیر" else "#64748b"
        label = f'{step.get("sequence_no", index + 1)} · {role}\\n{status}'
        lines.append(f'{node_id} [label={_dot_label(label)}, color="{color}"];')
        lines.append(f"{previous_node} -> {node_id};")
        previous_node = node_id
        for ev_index, evidence in enumerate((evidence_by_step or {}).get(step.get("id"), [])):
            ev_node = f"evidence_{index}_{ev_index}"
            ev_label = f'شاهد: {evidence.get("evidence_type") or "بدون نوع"}\\n{evidence.get("source_title") or evidence.get("claim") or "بدون عنوان"}'
            lines.append(f'{ev_node} [shape="note", fillcolor="#fef3c7", color="#d97706", label={_dot_label(ev_label)}];')
            lines.append(f"{node_id} -> {ev_node};")
    if not ordered_steps:
        lines.append('empty [label="هنوز گرهی ثبت نشده است", style="rounded,dashed,filled", fillcolor="#f8fafc"];')
        lines.append("root -> empty;")
    lines.append("}")
    return "\\n".join(lines)
