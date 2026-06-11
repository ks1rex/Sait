"""
Генерация отчёта в формате, близком к ГОСТ-оформлению (по образцу
прикреплённой курсовой: титульный лист, содержание, разделы с
формулами вида "Описание: Result = formula = 12 / 3 = 4 ед.",
заключение, список источников).

MVP-версия: формулы выводятся как обычный текст
("Q = Q_сут / 24 = 40000 / 24 = 1666,667 м3/ч"), без вставки
изображений/OMML. Это уже даёт читаемый и редактируемый docx.
Следующий шаг развития — рендер формул через LaTeX -> PNG
(matplotlib.mathtext) и вставка как Picture, для более "академического"
вида.
"""
from __future__ import annotations

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from .schemas import CalculationSpec


def _fmt_number(value: float, rounding: int) -> str:
    """Форматирует число в стиле ГОСТ: запятая вместо точки."""
    s = f"{value:.{rounding}f}"
    # убираем незначащие хвостовые нули, но оставляем хотя бы 0 знаков
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _add_title_page(doc: Document, spec: CalculationSpec, meta: dict):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta.get("university", "[Наименование учебного заведения]"))
    run.bold = True

    doc.add_paragraph()
    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(spec.work_type.upper() or "РАСЧЁТНО-ГРАФИЧЕСКАЯ РАБОТА")
    run.bold = True
    run.font.size = Pt(16)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f"по дисциплине «{spec.discipline}»").bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f"Тема: {spec.title}")

    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.add_run(f"Выполнил: {meta.get('student_name', '[ФИО студента]')}\n")
    p.add_run(f"Группа: {meta.get('group', '[группа]')}\n")
    p.add_run(f"Проверил: {meta.get('supervisor', '[ФИО преподавателя]')}")

    doc.add_paragraph()
    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(meta.get("city_year", "[Город, год]"))

    doc.add_page_break()


def _add_input_data_table(doc: Document, spec: CalculationSpec):
    doc.add_heading("Исходные данные", level=1)

    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Обозначение"
    hdr[1].text = "Наименование"
    hdr[2].text = "Значение"
    hdr[3].text = "Ед. изм."

    for item in spec.input_data:
        row = table.add_row().cells
        row[0].text = item.symbol
        if isinstance(item.value, (int, float)):
            row[2].text = _fmt_number(float(item.value), 4)
        else:
            row[2].text = str(item.value)
        row[1].text = item.description
        row[3].text = item.unit

    doc.add_page_break()


def _add_sections(doc: Document, spec: CalculationSpec):
    formula_counter = 0

    for s_idx, section in enumerate(spec.sections, start=1):
        doc.add_heading(section.title, level=1)
        if section.intro_text:
            doc.add_paragraph(section.intro_text)

        for step in section.steps:
            formula_counter += 1

            p = doc.add_paragraph()
            p.add_run(f"{step.description}, {step.result_symbol}, "
                      f"определяется по формуле:")

            value_str = (
                _fmt_number(step.value, step.rounding)
                if step.value is not None
                else "?"
            )

            formula_p = doc.add_paragraph()
            formula_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            formula_p.add_run(
                f"{step.result_symbol} = {step.formula} = {value_str} {step.unit}    ({formula_counter})"
            )

            if step.explanation:
                doc.add_paragraph(step.explanation)


def _add_conclusion(doc: Document, spec: CalculationSpec):
    doc.add_heading("Заключение", level=1)
    doc.add_paragraph(spec.conclusion_text or "[Заключение не сгенерировано]")


def generate_docx(spec: CalculationSpec, meta: dict, output_path: str) -> str:
    """
    meta: словарь с данными для титульного листа
    {university, student_name, group, supervisor, city_year}.
    Возвращает путь к сохранённому файлу.
    """
    doc = Document()

    _add_title_page(doc, spec, meta)
    _add_input_data_table(doc, spec)
    _add_sections(doc, spec)
    _add_conclusion(doc, spec)

    doc.save(output_path)
    return output_path
