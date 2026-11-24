"""Налаштування DeepSeek і виклик структурованої відповіді."""

from __future__ import annotations

import os
from pathlib import Path

from langchain_openai import ChatOpenAI

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"


def load_env_file() -> None:
    """Підхоплює .env, не перезаписуючи вже задані змінні оточення."""
    path = Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def get_settings() -> dict[str, str]:
    """Читає ключ, модель і базову адресу чату."""
    load_env_file()
    base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    return {
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": base_url,
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
    }


def build_llm(temperature: float = 0) -> ChatOpenAI:
    """OpenAI-сумісний клієнт DeepSeek.

    Thinking у deepseek-flash увімкнений за замовчуванням і відхиляє
    примусовий tool_choice, без якого не працює structured output.
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings["model"],
        api_key=settings["api_key"] or "missing",
        base_url=settings["base_url"],
        temperature=temperature,
        extra_body={"thinking": {"type": "disabled"}},
    )


def llm_model_name(llm: object) -> str:
    return str(
        getattr(llm, "model_name", None)
        or getattr(llm, "model", None)
        or get_settings()["model"]
    )


def invoke_structured(llm: object, schema: type, messages: list):
    """Спершу function calling. Якщо провайдер його відхиляє, пробує json schema."""
    errors: list[str] = []
    for kwargs in ({"method": "function_calling"}, {}):
        try:
            structured = llm.with_structured_output(schema, **kwargs)
            return structured.invoke(messages)
        except Exception as exc:  # noqa: BLE001 — другий метод лише після відмови першого
            label = kwargs.get("method", "json_schema")
            errors.append(f"{label}: {exc}")
    raise RuntimeError("Не вдалося зібрати структуровану відповідь. " + " | ".join(errors))
