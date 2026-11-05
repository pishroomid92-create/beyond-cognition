from workflow_routing import validate_stage_routes

ROLES = ["صورت‌بندی", "تحلیل‌گر", "فرضیه‌ساز"]


def valid_routes():
    return {
        role: {"provider": "openrouter", "model": "openrouter/free"}
        for role in ROLES
    }


def test_valid_role_routes_are_normalized():
    routes, errors = validate_stage_routes(
        valid_routes(), ROLES, ["openrouter", "groq"]
    )
    assert errors == []
    assert list(routes) == ROLES
    assert routes["تحلیل‌گر"] == {
        "provider": "openrouter",
        "model": "openrouter/free",
    }


def test_missing_role_route_blocks_entire_pipeline():
    config = valid_routes()
    config.pop("فرضیه‌ساز")
    routes, errors = validate_stage_routes(config, ROLES, ["openrouter"])
    assert routes == {}
    assert any("فرضیه‌ساز" in error for error in errors)


def test_unconfigured_provider_is_rejected():
    config = valid_routes()
    config["تحلیل‌گر"]["provider"] = "gemini"
    routes, errors = validate_stage_routes(config, ROLES, ["openrouter"])
    assert routes == {}
    assert any("تحلیل‌گر" in error for error in errors)


def test_blank_model_is_rejected():
    config = valid_routes()
    config["فرضیه‌ساز"]["model"] = " "
    routes, errors = validate_stage_routes(config, ROLES, ["openrouter"])
    assert routes == {}
    assert any("شناسه مدل خالی" in error for error in errors)


def test_invalid_route_object_is_rejected():
    config = valid_routes()
    config["تحلیل‌گر"] = None
    routes, errors = validate_stage_routes(config, ROLES, ["openrouter"])
    assert routes == {}
    assert any("تحلیل‌گر" in error for error in errors)


def test_extra_roles_are_ignored():
    config = valid_routes()
    config["یادداشت اضافی"] = {"provider": "openrouter", "model": "ignored"}
    routes, errors = validate_stage_routes(config, ROLES, ["openrouter"])
    assert errors == []
    assert list(routes) == ROLES
