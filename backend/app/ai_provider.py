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
    return OpenAI(api_key=api_key, base_url=cfg["base_url"])


# --- Промпты ----------------------------------------------------------------

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"


def _load_system_prompt() -> str:
    """
    Системный промпт хранится в docs/extraction_prompt.md между
    маркерами ```` ```\n и \n```` (первый блок SYSTEM PROMPT).
    Для простоты на этапе разработки можно временно держать промпт
    прямо здесь константой — см. EXTRACTION_SYSTEM_PROMPT_FALLBACK.
    """
    prompt_file = PROMPTS_DIR / "extraction_system_prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return EXTRACTION_SYSTEM_PROMPT_FALLBACK


EXTRACTION_SYSTEM_PROMPT_FALLBACK = (
    "Ты — ассистент инженера. Преобразуй текст задания в JSON по схеме "
    "CalculationSpec (см. docs/calculation_spec_schema.json). "
    "Отвечай ТОЛЬКО валидным JSON-объектом."
)


# --- Публичные функции -------------------------------------------------------

def extract_calculation_spec(task_text: str, use_fallback_model: bool = False) -> dict:
    """
    Отправляет текст задания в LLM и возвращает распарсенный dict,
    соответствующий CalculationSpec. Валидацию по Pydantic-схеме
    делает вызывающий код (см. main.py /extract).
    """
    cfg = PROVIDER_CONFIG[AI_PROVIDER]
    model = cfg["fallback_model"] if use_fallback_model else cfg["extract_model"]

    client = _client()
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _load_system_prompt()},
            {
                "role": "user",
                "content": (
                    "Вот полный текст задания (включая методику расчёта и "
                    "таблицу исходных данных по варианту). Преобразуй его в "
                    "CalculationSpec по описанным правилам.\n\n"
                    "=== ТЕКСТ ЗАДАНИЯ ===\n"
                    f"{task_text}\n"
                    "=== КОНЕЦ ТЕКСТА ==="
                ),
            },
        ],
    )

    content = response.choices[0].message.content
    return json.loads(content)


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
