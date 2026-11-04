"""Model/provider registry for Beyond Cognition.

API keys are read only from Streamlit Secrets at runtime.
"""

PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "secret_name": "GEMINI_API_KEY",
        "protocol": "gemini",
    },
    "groq": {
        "label": "Groq",
        "secret_name": "GROQ_API_KEY",
        "protocol": "openai_compatible",
    },
    "openrouter": {
        "label": "OpenRouter",
        "secret_name": "OPENROUTER_API_KEY",
        "protocol": "openai_compatible",
    },
}


def configured_providers(secrets):
    """Return provider IDs whose API keys are present in server-side secrets."""
    configured = []
    for provider_id, config in PROVIDERS.items():
        value = secrets.get(config["secret_name"], "")
        if isinstance(value, str) and value.strip():
            configured.append(provider_id)
    return configured
