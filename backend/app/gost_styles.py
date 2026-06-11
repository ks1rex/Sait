"""
GOST document styles and page setup.

Public API:
    apply_gost_page_setup(doc)       — page margins per GOST
    apply_gost_paragraph_styles(doc) — Normal, Heading 1, Heading 2 styles
    apply_table_cell_style(cell)     — single table cell
    apply_gost_styles(doc)           — calls all three on the whole document
    remove_toc_section(doc)          — removes Содержание heading + TOC field paragraphs
"""
from __future__ import annotations

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

# ---------------------------------------------------------------------------
# Shared constants (importable by other modules)
# ---------------------------------------------------------------------------

GOST_FONT = 'Times New Roman'
GOST_BODY_PT = Pt(14)
GOST_TABLE_PT = Pt(12)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _set_font_all_scripts(style, font_name: str) -> None:
    """
    Set w:ascii, w:hAnsi, w:eastAsia and w:cs on a style's rPr → rFonts.
    python-docx's font.name only sets ascii+hAnsi; eastAsia/cs are required
    for correct Cyrillic rendering in all viewers.
    """
    style.font.name = font_name

    rPr = style.element.find(qn('w:rPr'))
    if rPr is None:
        rPr = OxmlElement('w:rPr')
        style.element.append(rPr)

    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)

    for attr in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
        rFonts.set(qn(attr), font_name)


def _setup_heading_style(style) -> None:
    _set_font_all_scripts(style, GOST_FONT)
    style.font.size = GOST_BODY_PT
    style.font.bold = True
    style.font.italic = False
    style.font.color.rgb = RGBColor(0, 0, 0)

    pf = style.paragraph_format
    pf.left_indent = Cm(1.25)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.line_spacing = 1.5
    pf.space_before = Pt(14)
    pf.space_after = Pt(14)
    pf.page_break_before = False


def _setup_normal_style(doc: Document) -> None:
    style = doc.styles['Normal']
    _set_font_all_scripts(style, GOST_FONT)
    style.font.size = GOST_BODY_PT

    pf = style.paragraph_format
    pf.first_line_indent = Cm(1.25)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_gost_page_setup(doc: Document) -> None:
    """ГОСТ margins: left 30 mm, right 10 mm, top/bottom 20 mm."""
    for section in doc.sections:
        section.left_margin = Cm(3)
        section.right_margin = Cm(1)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)


def apply_gost_paragraph_styles(doc: Document) -> None:
    """Configure Normal, Heading 1 and Heading 2 styles to GOST spec."""
    _setup_normal_style(doc)
    _setup_heading_style(doc.styles['Heading 1'])
    _setup_heading_style(doc.styles['Heading 2'])


def apply_table_cell_style(cell) -> None:
    """
    GOST table-cell style: centred, no first-line indent, 8 pt spacing,
    Times New Roman 12 pt.
    """
    for p in cell.paragraphs:
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(8)
        pf.space_after = Pt(8)
        for run in p.runs:
            run.font.name = GOST_FONT
            run.font.size = GOST_TABLE_PT


def apply_gost_styles(doc: Document) -> None:
    """
    Apply all GOST styles to the document:
    page margins, paragraph styles, and table cell styles for every cell.
    """
    apply_gost_page_setup(doc)
    apply_gost_paragraph_styles(doc)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                apply_table_cell_style(cell)


def remove_toc_section(doc: Document) -> None:
    """
    Remove the 'Содержание' heading paragraph and any TOC field paragraphs
    (paragraphs containing w:instrText with 'TOC') from the document body.
    Also removes immediately adjacent page-break or hint paragraphs.
    """
    body = doc.element.body
    children = list(body)

    to_remove: set[int] = set()

    # Pass 1 — mark paragraphs that contain a TOC field instruction
    for elem in children:
        if elem.tag != qn('w:p'):
            continue
        for instr in elem.findall('.//' + qn('w:instrText')):
            if 'TOC' in (instr.text or ''):
                to_remove.add(id(elem))
                break

    # Pass 2 — mark the 'Содержание' heading that immediately precedes a TOC paragraph
    for i, elem in enumerate(children):
        if id(elem) not in to_remove or i == 0:
            continue
        prev = children[i - 1]
        if prev.tag != qn('w:p'):
            continue
        text = ''.join(
            t.text or '' for t in prev.findall('.//' + qn('w:t'))
        ).strip().lower()
        if text in ('содержание', 'оглавление', 'contents', 'table of contents'):
            to_remove.add(id(prev))

    # Pass 3 — mark page-break or hint paragraphs immediately after a removed paragraph
    changed = True
    while changed:
        changed = False
        for i, elem in enumerate(children):
            if id(elem) not in to_remove or i + 1 >= len(children):
                continue
            nxt = children[i + 1]
            if nxt.tag != qn('w:p') or id(nxt) in to_remove:
                continue
            text = ''.join(t.text or '' for t in nxt.findall('.//' + qn('w:t'))).strip()
            has_page_break = any(
                br.get(qn('w:type')) == 'page'
                for br in nxt.findall('.//' + qn('w:br'))
            )
            if has_page_break or text.startswith('['):
                to_remove.add(id(nxt))
                changed = True

    for elem in children:
        if id(elem) in to_remove:
            body.remove(elem)
