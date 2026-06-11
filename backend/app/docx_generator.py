"""
Генерация отчёта в формате ГОСТ Р 7.32 / ГОСТ 2.105.

Структура документа:
  1. Титульный лист
  2. Содержание (TOC-поле; обновить в Word: Ctrl+A → F9)
  3. Введение
  4. Исходные данные
  5. Разделы расчёта (Heading 1/2 по section.level)
  6. Графическая часть (placeholder)
  7. Заключение
  8. Список использованных источников

Формулы выводятся как текст:
  Символ = формула = подставленные_числа = результат  ед.   (N)
Подстановка чисел выполняется через _substitute_values().
"""
from __future__ import annotations

import keyword
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


from .gost_styles import apply_gost_page_setup, apply_gost_paragraph_styles, apply_table_cell_style
from .schemas import CalculationSpec

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Identifiers skipped during formula value substitution
_FORMULA_SKIP: frozenset[str] = frozenset({
    'sqrt', 'exp', 'log', 'log10', 'sin', 'cos', 'tan',
    'ceil', 'floor', 'abs', 'min', 'max', 'pi', 'e', 'interp',
} | set(keyword.kwlist))

# Tab-stop positions in twips (A4, left=3 cm, right=1 cm → content=17 cm)
# 1 cm ≈ 567 twips
_CONTENT_TWIPS = 9639   # 17 cm — right edge of content area
_CENTER_TWIPS  = 4820   # 8.5 cm — centre of content area


# ---------------------------------------------------------------------------
# Number / formula helpers
# ---------------------------------------------------------------------------

def _fmt_number(value: float, rounding: int) -> str:
    """ГОСТ-style number: comma decimal separator, trailing zeros stripped."""
    s = f"{value:.{rounding}f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s.replace('.', ',')


def _substitute_values(formula: str, namespace: dict, rounding: int = 3) -> str:
    """
    Replace each variable name in *formula* with its formatted numeric value
    from *namespace*.  Python keywords and math-function names are left as-is.
    Supports both Latin and Cyrillic identifiers (used in Russian engineering).
    """
    def _repl(m: re.Match) -> str:
        name = m.group(0)
        if name in _FORMULA_SKIP:
            return name
        val = namespace.get(name)
        if val is not None:
            return _fmt_number(float(val), rounding)
        return name

    return re.sub(
        r'\b[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё_0-9]*\b',
        _repl,
        formula,
    )


def _remove_table_borders(table) -> None:
    """Remove all visible borders from a table via OOXML."""
    tbl = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)

    tblBorders = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        border = OxmlElement(f'w:{side}')
        border.set(qn('w:val'), 'none')
        tblBorders.append(border)
    tblPr.append(tblBorders)


# ---------------------------------------------------------------------------
# Document sections
# ---------------------------------------------------------------------------

def _add_title_page(doc: Document, spec: CalculationSpec, meta: dict) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(meta.get('university', '[Наименование учебного заведения]'))
    r.bold = True

    doc.add_paragraph()
    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run((spec.work_type or 'РАСЧЁТНО-ГРАФИЧЕСКАЯ РАБОТА').upper())
    r.bold = True
    r.font.size = Pt(16)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f'по дисциплине «{spec.discipline}»').bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(f'Тема: {spec.title}')

    for _ in range(3):
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
    p.add_run(meta.get('city_year', '[Город, год]'))

    doc.add_page_break()


def _add_toc(doc: Document) -> None:
    """
    Insert auto-collectible TOC field (Heading levels 1-2).
    After opening in Word: press Ctrl+A → F9 to update the field.
    """
    doc.add_heading('Содержание', level=1)

    p = doc.add_paragraph()
    run = p.add_run()

    fldChar_begin = OxmlElement('w:fldChar')
    fldChar_begin.set(qn('w:fldCharType'), 'begin')

    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = ' TOC \\o "1-2" \\h \\z \\u '

    fldChar_sep = OxmlElement('w:fldChar')
    fldChar_sep.set(qn('w:fldCharType'), 'separate')

    fldChar_end = OxmlElement('w:fldChar')
    fldChar_end.set(qn('w:fldCharType'), 'end')

    run._r.append(fldChar_begin)
    run._r.append(instrText)
    run._r.append(fldChar_sep)
    run._r.append(fldChar_end)

    hint = doc.add_paragraph(
        '[Откройте в Word и нажмите Ctrl+A → F9 для обновления содержания]'
    )
    hint.paragraph_format.first_line_indent = Cm(0)
    hint.runs[0].italic = True

    doc.add_page_break()


def _add_intro(doc: Document, spec: CalculationSpec) -> None:
    doc.add_heading('Введение', level=1)
    text = spec.intro_text or '[Введение не задано — заполните вручную]'
    for block in text.split('\n\n'):
        if block.strip():
            doc.add_paragraph(block.strip())
    doc.add_page_break()


def _add_input_data_table(doc: Document, spec: CalculationSpec) -> None:
    doc.add_heading('Исходные данные', level=1)

    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'

    # Header row
    hdr = table.rows[0].cells
    headers = ['Обозначение', 'Наименование', 'Значение', 'Ед. изм.']
    for cell, text in zip(hdr, headers):
        cell.text = text
        apply_table_cell_style(cell)
        cell.paragraphs[0].runs[0].bold = True

    # Data rows
    for item in spec.input_data:
        row = table.add_row().cells
        row[0].text = item.symbol
        row[1].text = item.description
        row[2].text = (
            _fmt_number(float(item.value), 4)
            if isinstance(item.value, (int, float))
            else str(item.value)
        )
        row[3].text = item.unit
        for cell in row:
            apply_table_cell_style(cell)

    doc.add_page_break()


def _add_formula_row(
    doc: Document,
    step,
    formula_counter: int,
    namespace: dict,
) -> None:
    """
    Render the formula line:
        <tab> Symbol = formula = substituted = result unit <tab> (N)
    Uses a centre tab stop at 8.5 cm and a right tab stop at 17 cm,
    so the formula body is centred and the serial number is at the right margin.
    """
    value_str = (
        _fmt_number(step.value, step.rounding)
        if step.value is not None
        else '?'
    )
    subst = _substitute_values(step.formula, namespace, step.rounding)
    unit = f' {step.unit}'.rstrip()
    formula_line = (
        f'{step.result_symbol} = {step.formula} = {subst} = {value_str}{unit}'
    )

    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)

    # Inject tab stops into paragraph XML
    pPr = p._p.get_or_add_pPr()
    tabs_elem = OxmlElement('w:tabs')

    centre_tab = OxmlElement('w:tab')
    centre_tab.set(qn('w:val'), 'center')
    centre_tab.set(qn('w:pos'), str(_CENTER_TWIPS))
    tabs_elem.append(centre_tab)

    right_tab = OxmlElement('w:tab')
    right_tab.set(qn('w:val'), 'right')
    right_tab.set(qn('w:pos'), str(_CONTENT_TWIPS))
    tabs_elem.append(right_tab)

    pPr.append(tabs_elem)

    # \t → jump to centre tab; second \t → jump to right tab for number
    p.add_run(f'\t{formula_line}\t({formula_counter})')


def _add_sections(doc: Document, spec: CalculationSpec) -> None:
    formula_counter = 0

    # Accumulate namespace like calc_engine so _substitute_values gets values
    namespace: dict[str, float] = {}
    for item in spec.input_data:
        try:
            namespace[item.id] = float(item.value)
        except (TypeError, ValueError):
            pass

    for section in spec.sections:
        level = section.level if 1 <= section.level <= 2 else 1
        doc.add_heading(section.title, level=level)

        if section.intro_text:
            p = doc.add_paragraph(section.intro_text)
            p.paragraph_format.first_line_indent = Cm(0)

        for step in section.steps:
            formula_counter += 1

            # Абзац 1: описание величины
            p1 = doc.add_paragraph(
                f'{step.description}, {step.result_symbol},'
                ' рассчитывается по формуле:'
            )
            p1.paragraph_format.first_line_indent = Cm(0)

            # Абзац 2: строка формулы с табстопами
            _add_formula_row(doc, step, formula_counter, namespace)

            # Абзац 3: пояснение «где ...» (если есть)
            if step.explanation:
                p3 = doc.add_paragraph(f'где {step.explanation}')
                p3.paragraph_format.first_line_indent = Cm(0)

            # Accumulate computed value so later steps can reference it
            if step.value is not None:
                namespace[step.id] = step.value


def _add_graphics_placeholder(doc: Document) -> None:
    doc.add_page_break()
    doc.add_heading('Графическая часть', level=1)
    p = doc.add_paragraph(
        '[Графическая часть формируется отдельно — '
        'блок-схема и генплан не входят в автоматический расчёт]'
    )
    p.paragraph_format.first_line_indent = Cm(0)
    p.runs[0].italic = True


def _add_conclusion(doc: Document, spec: CalculationSpec) -> None:
    doc.add_heading('Заключение', level=1)
    doc.add_paragraph(
        spec.conclusion_text or '[Заключение не сгенерировано]'
    )


def _add_references(doc: Document, spec: CalculationSpec) -> None:
    doc.add_heading('Список использованных источников', level=1)
    if spec.references:
        for i, ref in enumerate(spec.references, 1):
            p = doc.add_paragraph(f'{i}. {ref}')
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.left_indent = Cm(1.25)
    else:
        p = doc.add_paragraph(
            '[Список источников не определён автоматически — заполните вручную]'
        )
        p.paragraph_format.first_line_indent = Cm(0)
        p.runs[0].italic = True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_docx(spec: CalculationSpec, meta: dict, output_path: str) -> str:
    """
    Generate a GOST-formatted .docx report.

    Args:
        spec:        Computed CalculationSpec (all step.value must be set).
        meta:        Title-page metadata dict with keys:
                     university, student_name, group, supervisor, city_year.
        output_path: Absolute path to write the .docx file.

    Returns:
        output_path (passthrough for convenience).
    """
    doc = Document()
    apply_gost_page_setup(doc)
    apply_gost_paragraph_styles(doc)

    _add_title_page(doc, spec, meta)
    _add_toc(doc)
    _add_intro(doc, spec)
    _add_input_data_table(doc, spec)
    _add_sections(doc, spec)
    _add_graphics_placeholder(doc)
    _add_conclusion(doc, spec)
    _add_references(doc, spec)

    doc.save(output_path)
    return output_path
