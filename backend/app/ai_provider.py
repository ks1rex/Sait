"""
Слой абстракции над LLM-провайдером.

По умолчанию используется DeepSeek (OpenAI-совместимый эндпоинт).
Переключение провайдера — через переменные окружения, без изменения
остального кода.

ВАЖНО: перед использованием в продакшене свериться с актуальной
документацией DeepSeek (https://api-docs.deepseek.com) — в частности:
  - точные имена моделей (deepseek-v4-flash / deepseek-v4-pro,
    старые алиасы deepseek-chat/deepseek-reasoner отключаются 2026-07-24);
  - параметр включения thinking-режима (может называться иначе, чем
    `reasoning` ниже — заглушка, проверить в доках);
  - поддержку response_format={"type": "json_object"}.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import NamedTuple

import httpx
from openai import OpenAI

# --- Конфигурация провайдера ---------------------------------------------

AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")  # deepseek | anthropic | openai

PROVIDER_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "extract_model": "deepseek-v4-flash",
        "fallback_model": "deepseek-v4-pro",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "extract_model": "gpt-4.1-mini",
        "fallback_model": "gpt-5",
    },
    # DeepSeek также отдаёт Anthropic-совместимый эндпоинт:
    # https://api.deepseek.com/anthropic — при желании можно завести
    # отдельный клиент через anthropic SDK по тому же принципу.
}


def _client() -> OpenAI:
    cfg = PROVIDER_CONFIG[AI_PROVIDER]
    api_key = os.environ[cfg["api_key_env"]]
    # Pass trust_env=False httpx client to bypass system SOCKS proxy
    http = httpx.Client(trust_env=False)
    return OpenAI(api_key=api_key, base_url=cfg["base_url"], http_client=http)


# --- Промпты ----------------------------------------------------------------

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"


def _load_system_prompt() -> str:
    prompt_file = PROMPTS_DIR / "extraction_system_prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return EXTRACTION_SYSTEM_PROMPT_FALLBACK


EXTRACTION_SYSTEM_PROMPT_FALLBACK = (
    "Ты — ассистент инженера. Преобразуй текст задания в JSON по схеме "
    "CalculationSpec (см. docs/calculation_spec_schema.json). "
    "Отвечай ТОЛЬКО валидным JSON-объектом."
)


# --- Возвращаемый тип -------------------------------------------------------

class ExtractionResult(NamedTuple):
    spec_dict: dict
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


class VariantExtractionResult(NamedTuple):
    overrides: dict  # {id: numeric value}
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


# --- Публичные функции -------------------------------------------------------

def extract_calculation_spec(
    task_text: str,
    methodology_text: str | None = None,
    extra_inputs_text: str | None = None,
    use_fallback_model: bool = False,
) -> ExtractionResult:
    """
    Отправляет текст(ы) источников в LLM и возвращает ExtractionResult.
    Поле spec_dict — распарсенный dict, соответствующий CalculationSpec.
    Валидацию по Pydantic-схеме делает вызывающий код (main.py /extract).

    Args:
        task_text: текст задания (обязательный).
        methodology_text: текст методички (опционально).
        extra_inputs_text: отдельные исходные данные по варианту (опционально).
        use_fallback_model: переключиться на резервную модель.

    Raises:
        ValueError: если модель вернула невалидный JSON.
        openai.APIError: при сетевых или API-ошибках.
    """
    cfg = PROVIDER_CONFIG[AI_PROVIDER]
    model = cfg["fallback_model"] if use_fallback_model else cfg["extract_model"]

    # Build user message with clearly labelled source blocks
    parts: list[str] = ["=== ЗАДАНИЕ ===", task_text, "=== КОНЕЦ ЗАДАНИЯ ==="]

    if methodology_text and methodology_text.strip():
        parts += ["", "=== МЕТОДИЧКА ===", methodology_text, "=== КОНЕЦ МЕТОДИЧКИ ==="]

    if extra_inputs_text and extra_inputs_text.strip():
        parts += [
            "",
            "=== ИСХОДНЫЕ ДАННЫЕ (ОТДЕЛЬНО) ===",
            extra_inputs_text,
            "=== КОНЕЦ ИСХОДНЫХ ДАННЫХ ===",
        ]

    user_content = (
        "Преобразуй приведённые ниже материалы в CalculationSpec "
        "по правилам из системного промпта.\n\n" + "\n".join(parts)
    )

    client = _client()
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _load_system_prompt()},
            {"role": "user", "content": user_content},
        ],
    )

    content = response.choices[0].message.content or ""

    # Guard against markdown wrapping despite json_object response_format
    if "```" in content:
        for part in content.split("```"):
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                content = stripped
                break

    try:
        spec_dict = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Модель вернула невалидный JSON: {e}\n"
            f"Начало ответа: {content[:300]}"
        )

    usage = response.usage
    return ExtractionResult(
        spec_dict=spec_dict,
        provider=AI_PROVIDER,
        model=model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
    )


_VARIANT_SYSTEM_PROMPT = (
    "Ты — ассистент инженера. Тебе дан список расчётных параметров и текст "
    "варианта студента (содержит таблицу «Исходные данные»). "
    "Найди числовые значения параметров в тексте варианта. "
    "Верни JSON-объект {id: значение}, где id — идентификатор из списка, "
    "значение — число (int или float). "
    "Включай ТОЛЬКО параметры, значение которых явно указано в тексте. "
    "Если параметр не найден — не включай его. "
    "Отвечай ТОЛЬКО JSON-объектом, без пояснений и markdown-разметки."
)


def extract_variant_inputs(
    input_data_schema: list[dict],
    variant_text: str,
) -> VariantExtractionResult:
    """
    Lightweight AI call: extract input_data overrides from a student variant PDF.

    Args:
        input_data_schema: list of {id, symbol, description, unit} from the template
        variant_text: extracted text from the variant PDF

    Returns:
        VariantExtractionResult with overrides {id: numeric value}

    Raises:
        ValueError: if model returns invalid JSON
        openai.APIError: on network/API errors
    """
    cfg = PROVIDER_CONFIG[AI_PROVIDER]
    model = cfg["extract_model"]

    schema_lines = "\n".join(
        f"  {item['id']}: {item.get('symbol', '')} — "
        f"{item.get('description', '')} [{item.get('unit', '')}]"
        for item in input_data_schema
    )
    user_content = (
        f"Список параметров шаблона:\n{schema_lines}\n\n"
        f"=== ТЕКСТ ВАРИАНТА ===\n{variant_text}\n=== КОНЕЦ ТЕКСТА ===\n\n"
        "Верни JSON {id: значение} только для параметров, "
        "явно указанных в тексте варианта."
    )

    client = _client()
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _VARIANT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    content = response.choices[0].message.content or ""
    if "```" in content:
        for part in content.split("```"):
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                content = stripped
                break

    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Модель вернула невалидный JSON при извлечении варианта: {exc}\n"
            f"{content[:300]}"
        )

    overrides: dict = {}
    for k, v in raw.items():
        if isinstance(v, (int, float)):
            overrides[k] = v
        elif isinstance(v, str):
            try:
                overrides[k] = float(v.replace(",", "."))
            except ValueError:
                pass

    usage = response.usage
    return VariantExtractionResult(
        overrides=overrides,
        provider=AI_PROVIDER,
        model=model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
    )


class MinimalEditResult(NamedTuple):
    markdown: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


_MINIMAL_EDIT_SYSTEM_PROMPT = (
    "Ты — технический редактор инженерных расчётных работ. "
    "Ты получаешь образец готовой работы в формате Markdown и новое задание (новый вариант). "
    "Твоя единственная задача — переписать образец, сделав МИНИМАЛЬНО НЕОБХОДИМЫЕ изменения "
    "для соответствия новому заданию. "
    "Отвечай ТОЛЬКО Markdown-текстом переработанного документа, без пояснений, "
    "без markdown-блоков с кодом (не оборачивай в ```markdown ... ```), "
    "без вводных фраз вроде 'Вот переработанный документ:'."
)


def minimal_edit_rewrite(
    template_markdown: str,
    task_text: str,
) -> MinimalEditResult:
    """
    Call DeepSeek to rewrite template_markdown with minimal edits
    to match the new task/variant described in task_text.

    Uses the fallback (more capable) model and a large token budget
    because the full document rewrite is a long, complex output.
    """
    cfg = PROVIDER_CONFIG[AI_PROVIDER]
    model = cfg["fallback_model"]

    user_content = (
        "Вот образец готовой работы в Markdown "
        "(структура, формулировки, формулы, числа из СТАРОГО варианта):\n\n"
        f"{template_markdown}\n\n"
        "---\n\n"
        "Вот новое задание (новый вариант/условие):\n\n"
        f"{task_text}\n\n"
        "---\n\n"
        "Перепиши образец, внеся МИНИМАЛЬНО НЕОБХОДИМЫЕ изменения, чтобы "
        "результат соответствовал новому заданию: обнови исходные данные, "
        "пересчитай числовые результаты по тем же формулам с новыми "
        "входными значениями, при необходимости скорректируй текстовые "
        "формулировки (например, если изменилось количество секций/типов "
        "оборудования — добавь/убери соответствующие пункты по аналогии "
        "со стилем образца). ВСЁ остальное — структуру, заголовки, "
        "формулировки, порядок разделов, стиль изложения — оставь БЕЗ "
        "ИЗМЕНЕНИЙ. Заключение и введение перепиши с учётом новых данных, "
        "сохранив структуру и стиль образца.\n\n"
        "Верни результат тем же Markdown-форматом (# для Заголовок 1, "
        "## для Заголовок 2, markdown-таблицы)."
    )

    client = _client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _MINIMAL_EDIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=32000,
    )

    content = response.choices[0].message.content or ""
    # Strip accidental markdown code-block wrapper
    if content.startswith("```"):
        inner = content.split("```", 2)
        if len(inner) >= 3:
            content = inner[2] if inner[1].strip().lower() == "markdown" else inner[1]
            content = content.strip()

    usage = response.usage
    return MinimalEditResult(
        markdown=content,
        provider=AI_PROVIDER,
        model=model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
    )


def generate_conclusion(spec_dict: dict, computed_results: dict) -> str:
    """
    Генерирует текст заключения на основе conclusion_instructions
    и посчитанных результатов. computed_results — плоский словарь
    {step_id: значение}.
    """
    cfg = PROVIDER_CONFIG[AI_PROVIDER]
    client = _client()

    instructions = spec_dict.get("conclusion_instructions", "")
    response = client.chat.completions.create(
        model=cfg["extract_model"],
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты помогаешь студенту написать раздел 'Заключение' для "
                    "технической работы по ГОСТ. Пиши официальным "
                    "техническим стилем на русском языке, 1-2 абзаца, без "
                    "markdown-разметки."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Название работы: {spec_dict.get('title')}\n\n"
                    f"Что нужно отразить в заключении:\n{instructions}\n\n"
                    f"Посчитанные результаты (id: значение):\n"
                    f"{json.dumps(computed_results, ensure_ascii=False, indent=2)}"
                ),
            },
        ],
    )
    return response.choices[0].message.content
