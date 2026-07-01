"""
Извлечение текста из загруженного PDF задания.

MVP: просто вытаскиваем весь текст постранично через PyMuPDF.
Таблицы при этом превращаются в обычный текст — DeepSeek неплохо
справляется с разбором таблиц из текста, если они не сильно
"расползлись" по столбцам. Если на практике окажется, что таблицы
с исходными данными извлекаются плохо — следующий шаг: попробовать
fitz Page.find_tables() и сериализовать таблицы отдельно (markdown-таблицы)
перед остальным текстом.
"""
from __future__ import annotations

import fitz  # PyMuPDF


def extract_text_and_tables(file_path: str) -> str:
    """
    Более аккуратное извлечение: текст + таблицы (как markdown) отдельно
    для каждой страницы. TODO: реализовать и сравнить качество извлечения
    DeepSeek на эталонном PDF (расчёт очистных сооружений).
    """
    doc = fitz.open(file_path)
    chunks = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        chunks.append(f"--- Страница {page_num} ---\n{text}")

        try:
            tables = page.find_tables()
            for i, table in enumerate(tables):
                rows = table.extract()
                md_lines = []
                for row in rows:
                    md_lines.append(
                        "| " + " | ".join(str(c) if c is not None else "" for c in row) + " |"
                    )
                chunks.append(
                    f"[Таблица {page_num}.{i+1}]\n" + "\n".join(md_lines)
                )
        except Exception:
            # find_tables может быть недоступен в старых версиях PyMuPDF —
            # тогда просто полагаемся на обычный текст.
            pass

    doc.close()
    return "\n\n".join(chunks)
