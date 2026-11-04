"""Small, dependency-free adapters for supported text-generation APIs.

The module never reads secrets itself. Callers must pass a server-side API key
from Streamlit Secrets and must never expose that key to the browser or logs.
"""

import json
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from model_registry import PROVIDERS


class ModelProviderError(RuntimeError):
    """Safe, user-displayable model-provider error."""


@dataclass(frozen=True)
class ModelResponse:
    text: str
    provider: str
    model: str
    usage: dict
    latency_ms: int
    request_id: str = ""


def _normalize_messages(messages):
    if not isinstance(messages, list) or not messages:
        raise ModelProviderError("حداقل یک پیام برای مدل لازم است.")

    normalized = []
    for item in messages:
        if not isinstance(item, dict):
            raise ModelProviderError("ساختار پیام مدل معتبر نیست.")
        role = item.get("role")
        content = item.get("content")
        if role not in ("system", "user", "assistant"):
            raise ModelProviderError("نقش پیام پشتیبانی نمی‌شود.")
        if not isinstance(content, str) or not content.strip():
            raise ModelProviderError("متن پیام نمی‌تواند خالی باشد.")
        normalized.append({"role": role, "content": content.strip()})

    if not any(item["role"] == "user" for item in normalized):
        raise ModelProviderError("حداقل یک پیام کاربر باید وجود داشته باشد.")
    return normalized


def _build_gemini_payload(messages, temperature, max_output_tokens):
    system_text = "\n\n".join(
        item["content"] for item in messages if item["role"] == "system"
    )
    contents = []
    for item in messages:
        if item["role"] == "system":
            continue
        role = "model" if item["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": item["content"]}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    return payload


def _build_request(provider, model, messages, api_key, temperature, max_output_tokens):
    if provider not in PROVIDERS:
        raise ModelProviderError("ارائه‌دهنده انتخاب‌شده پشتیبانی نمی‌شود.")
    if not isinstance(model, str) or not model.strip():
        raise ModelProviderError("شناسه مدل الزامی است.")
    if not isinstance(api_key, str) or not api_key.strip():
        raise ModelProviderError("کلید API این ارائه‌دهنده در Secrets تنظیم نشده است.")
    if not 0 <= float(temperature) <= 2:
        raise ModelProviderError("دمای مدل باید بین ۰ و ۲ باشد.")
    if not 64 <= int(max_output_tokens) <= 8192:
        raise ModelProviderError("حداکثر خروجی باید بین ۶۴ و ۸۱۹۲ توکن باشد.")

    normalized = _normalize_messages(messages)
    config = PROVIDERS[provider]

    headers = {"Content-Type": "application/json"}
    if config["protocol"] == "openai_compatible":
        base_urls = {
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
        }
        endpoint = base_urls[provider] + "/chat/completions"
        headers["Authorization"] = "Bearer " + api_key.strip()
        payload = {
            "model": model.strip(),
            "messages": normalized,
            "temperature": float(temperature),
            "max_tokens": int(max_output_tokens),
        }
    else:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + quote(model.strip(), safe="")
            + ":generateContent"
        )
        headers["x-goog-api-key"] = api_key.strip()
        payload = _build_gemini_payload(
            normalized, float(temperature), int(max_output_tokens)
        )

    return endpoint, headers, payload


def _extract_error_message(body, api_key):
    try:
        data = json.loads(body)
        error = data.get("error", data) if isinstance(data, dict) else data
        if isinstance(error, dict):
            message = error.get("message") or error.get("status") or "درخواست رد شد."
        else:
            message = str(error)
    except (TypeError, ValueError):
        message = "پاسخ خطای ارائه‌دهنده قابل خواندن نبود."
    message = str(message).replace(api_key, "[کلید پنهان شد]")
    return message[:700]


def _parse_response(provider, data):
    if provider in ("groq", "openrouter"):
        choices = data.get("choices") or []
        if not choices:
            raise ModelProviderError("ارائه‌دهنده پاسخ متنی برنگرداند.")
        message = (choices[0].get("message") or {})
        content = message.get("content")
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            content = "\n".join(text_parts)
        if not isinstance(content, str) or not content.strip():
            raise ModelProviderError("پاسخ مدل خالی یا غیرمتنی بود.")
        return content.strip(), data.get("usage") or {}

    candidates = data.get("candidates") or []
    text_parts = []
    if candidates:
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text_parts = [
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
    output = "\n".join(part for part in text_parts if part).strip()
    if not output:
        feedback = data.get("promptFeedback") or {}
        reason = feedback.get("blockReason")
        detail = "؛ علت: " + str(reason) if reason else ""
        raise ModelProviderError("Gemini پاسخ متنی تولید نکرد." + detail)

    usage_meta = data.get("usageMetadata") or {}
    usage = {
        "prompt_tokens": usage_meta.get("promptTokenCount"),
        "completion_tokens": usage_meta.get("candidatesTokenCount"),
        "total_tokens": usage_meta.get("totalTokenCount"),
    }
    return output, usage


def generate_model_response(
    provider,
    model,
    messages,
    api_key,
    temperature=0.3,
    max_output_tokens=2048,
    timeout_seconds=60,
):
    """Call one provider and return a normalized text response."""
    if not 5 <= int(timeout_seconds) <= 180:
        raise ModelProviderError("مهلت درخواست باید بین ۵ تا ۱۸۰ ثانیه باشد.")

    endpoint, headers, payload = _build_request(
        provider, model, messages, api_key, temperature, max_output_tokens
    )
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    started = time.monotonic()
    try:
        with urlopen(request, timeout=int(timeout_seconds)) as response:
            raw = response.read()
            request_id = (
                response.headers.get("x-request-id", "")
                or response.headers.get("request-id", "")
            )
    except HTTPError as exc:
        body = exc.read(4000).decode("utf-8", errors="replace")
        detail = _extract_error_message(body, api_key)
        raise ModelProviderError(
            f"خطای سرویس {PROVIDERS[provider]['label']} (HTTP {exc.code}): {detail}"
        ) from None
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        detail = str(reason or "ارتباط شبکه برقرار نشد.").replace(api_key, "[کلید پنهان شد]")
        raise ModelProviderError(
            f"ارتباط با {PROVIDERS[provider]['label']} ناموفق بود: {detail[:300]}"
        ) from None

    latency_ms = int((time.monotonic() - started) * 1000)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ModelProviderError("پاسخ ارائه‌دهنده JSON معتبر نبود.") from None

    output, usage = _parse_response(provider, data)
    return ModelResponse(
        text=output,
        provider=provider,
        model=str(data.get("model") or model),
        usage=usage,
        latency_ms=latency_ms,
        request_id=request_id,
    )
