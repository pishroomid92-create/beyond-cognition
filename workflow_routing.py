"""Validation helpers for per-role provider/model routing."""

def validate_stage_routes(stage_routes, required_roles, configured_providers):
    """Validate a complete role-to-provider/model map.

    Returns (normalized_routes, errors). On any error, normalized_routes is empty
    so a caller cannot accidentally execute a partially configured pipeline.
    """
    if not isinstance(stage_routes, dict):
        return {}, ["تنظیمات مسیر مدل باید یک ساختار معتبر باشد."]

    configured = set(configured_providers or [])
    normalized = {}
    errors = []

    for role in required_roles:
        route = stage_routes.get(role)
        if not isinstance(route, dict):
            errors.append(f"{role}: مسیر مدل تعریف نشده است.")
            continue

        provider = str(route.get("provider") or "").strip()
        model = str(route.get("model") or "").strip()

        if provider not in configured:
            errors.append(
                f"{role}: ارائه‌دهنده انتخاب‌شده کلید فعال در Secrets ندارد."
            )
        if not model:
            errors.append(f"{role}: شناسه مدل خالی است.")

        if provider in configured and model:
            normalized[role] = {"provider": provider, "model": model}

    if errors:
        return {}, errors
    return normalized, []
