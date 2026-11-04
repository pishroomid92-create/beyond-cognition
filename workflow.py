"""Pure workflow progress helpers for Beyond Cognition."""

def summarize_workflow(steps, required_roles):
    """Summarize completion, duplicates, and role ordering without DB dependencies."""
    required = list(required_roles)
    seen = []
    for step in steps:
        role = step.get("role")
        if role in required:
            seen.append(role)

    completed = set(seen)
    duplicates = sorted({role for role in seen if seen.count(role) > 1},
                        key=required.index)
    missing = [role for role in required if role not in completed]

    order_indexes = [required.index(role) for role in seen]
    out_of_order = []
    highest_index = -1
    for role, index in zip(seen, order_indexes):
        if index < highest_index and role not in out_of_order:
            out_of_order.append(role)
        highest_index = max(highest_index, index)

    return {
        "completed_count": len(completed),
        "missing_roles": missing,
        "duplicate_roles": duplicates,
        "out_of_order": out_of_order,
        "next_role": missing[0] if missing else None,
    }
