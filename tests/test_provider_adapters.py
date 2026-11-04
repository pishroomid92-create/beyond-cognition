import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

import provider_adapters
from model_registry import configured_providers


def test_provider_registry_only_returns_keys_present_in_secrets():
    assert configured_providers({
        "GROQ_API_KEY": "  test-key  ",
        "OPENROUTER_API_KEY": "",
    }) == ["groq"]


def test_openai_compatible_request_uses_server_key_header():
    endpoint, headers, payload = provider_adapters._build_request(
        "groq",
        "sample-model",
        [{"role": "user", "content": "test prompt"}],
        "secret-key",
        0.4,
        512,
    )
    assert endpoint == "https://api.groq.com/openai/v1/chat/completions"
    assert headers["Authorization"] == "Bearer secret-key"
    assert payload["model"] == "sample-model"
    assert payload["max_tokens"] == 512


def test_gemini_request_maps_roles_and_system_instruction():
    endpoint, headers, payload = provider_adapters._build_request(
        "gemini",
        "sample-model",
        [
            {"role": "system", "content": "Be rigorous."},
            {"role": "user", "content": "Question?"},
            {"role": "assistant", "content": "Prior answer."},
        ],
        "secret-key",
        0.2,
        1024,
    )
    assert endpoint.endswith("/models/sample-model:generateContent")
    assert headers["x-goog-api-key"] == "secret-key"
    assert payload["systemInstruction"]["parts"][0]["text"] == "Be rigorous."
    assert payload["contents"][1]["role"] == "model"


def test_generate_model_response_parses_openai_compatible_result(monkeypatch):
    class FakeResponse:
        headers = {"x-request-id": "request-123"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "model": "sample-model",
                "choices": [{"message": {"content": "A grounded answer."}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }).encode()

    def fake_urlopen(request, timeout):
        assert timeout == 60
        assert request.get_header("Authorization") == "Bearer secret-key"
        return FakeResponse()

    monkeypatch.setattr(provider_adapters, "urlopen", fake_urlopen)
    result = provider_adapters.generate_model_response(
        "groq", "sample-model", [{"role": "user", "content": "test"}],
        "secret-key",
    )
    assert result.text == "A grounded answer."
    assert result.usage["total_tokens"] == 15
    assert result.request_id == "request-123"


def test_http_error_redacts_api_key(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url, 401, "Unauthorized", {},
            BytesIO(b'{"error":{"message":"invalid secret-key"}}'),
        )

    monkeypatch.setattr(provider_adapters, "urlopen", fake_urlopen)
    with pytest.raises(provider_adapters.ModelProviderError) as error:
        provider_adapters.generate_model_response(
            "groq", "sample-model", [{"role": "user", "content": "test"}],
            "secret-key",
        )
    assert "secret-key" not in str(error.value)
    assert "[کلید پنهان شد]" in str(error.value)


def test_invalid_message_and_provider_are_rejected():
    with pytest.raises(provider_adapters.ModelProviderError):
        provider_adapters.generate_model_response(
            "unknown", "model", [{"role": "user", "content": "test"}], "key"
        )
    with pytest.raises(provider_adapters.ModelProviderError):
        provider_adapters.generate_model_response(
            "groq", "model", [{"role": "assistant", "content": "no user"}], "key"
        )
