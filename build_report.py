"""Сборка Отчет_ЛР4.docx из Отчет_ЛР4.md.

Поддерживаются заголовки, абзацы, списки, таблицы, блоки кода,
полужирный текст, встроенный код и картинки.
"""

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "Отчет_ЛР4.md"
DST = ROOT / "Отчет_ЛР4.docx"

FONT = "Times New Roman"
MONO = "Consolas"


def set_run_font(run, name=FONT, size=None, bold=None, italic=None, color=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = RGBColor(*color)


def add_inline(paragraph, text, size=12):
    """Разбирает **жирный** и `код` на отдельные run-ы."""
    tokens = re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)
    for token in tokens:
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size=size, bold=True)
        elif token.startswith("`") and token.endswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, name=MONO, size=size - 1.5)
            run.font.color.rgb = RGBColor(0x8B, 0x1A, 0x1A)
        else:
            run = paragraph.add_run(token)
            set_run_font(run, size=size)


def shade(cell, fill="EDEDED"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def add_page_number(paragraph):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)
    set_run_font(run, size=10)


def setup(doc):
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    pf = normal.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    pf.space_after = Pt(4)
    pf.first_line_indent = Cm(1.25)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for name, size in (("Heading 1", 15), ("Heading 2", 13), ("Heading 3", 12)):
        st = doc.styles[name]
        st.font.name = FONT
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.paragraph_format.first_line_indent = Cm(0)
        st.paragraph_format.space_before = Pt(12)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.keep_with_next = True

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("Лабораторная работа № 4 — Гестурный пульт · стр. ")
    set_run_font(run, size=10)
    add_page_number(footer)


def add_code(doc, block):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F4F4F4")
    after = ("w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
             "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE",
             "w:autoSpaceDN", "w:bidi", "w:adjustRightInd", "w:snapToGrid",
             "w:spacing", "w:ind", "w:contextualSpacing", "w:mirrorIndents",
             "w:suppressOverlap", "w:jc", "w:textDirection", "w:textAlignment",
             "w:textboxTightWrap", "w:outlineLvl", "w:divId", "w:cnfStyle",
             "w:rPr", "w:sectPr", "w:pPrChange")
    for tag in after:
        el = pPr.find(qn(tag))
        if el is not None:
            el.addprevious(shd)
            break
    else:
        pPr.append(shd)
    for i, line in enumerate(block):
        if i:
            p.add_run().add_break()
        run = p.add_run(line.rstrip())
        set_run_font(run, name=MONO, size=9.5)


def _cell_left(cell):
    for p in cell.paragraphs:
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    ncols = len(header)
    table = doc.add_table(rows=1, cols=ncols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    # компактные внутренние отступы: длинные имена файлов влезают в колонку
    cell_mar = OxmlElement("w:tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), "20" if side in ("top", "bottom") else "60")
        el.set(qn("w:type"), "dxa")
        cell_mar.append(el)
    tblPr = table._tbl.tblPr
    tblLook = tblPr.find(qn("w:tblLook"))
    if tblLook is not None:
        tblLook.addprevious(cell_mar)
    else:
        tblPr.append(cell_mar)

    # фиксированные доли ширины: текст в узких колонках не расползается
    if ncols == 2:
        fractions = (34, 66)
    elif ncols == 3:
        second_wide = any("`" in row[1] and len(row[1]) > 10
                          for row in rows[1:] if len(row) > 1)
        fractions = (24, 26, 50) if second_wide else (26, 18, 56)
    elif ncols == 4:
        first_long = max(len(row[0]) for row in rows if row) > 8
        fractions = (17, 18, 15, 50) if first_long else (8, 22, 28, 42)
    elif ncols == 5:
        fractions = (6, 18, 24, 22, 30)
    else:
        fractions = None
    widths = []
    if fractions:
        total = 16.4
        widths = [Cm(total * frac / 100) for frac in fractions]
        for j, width in enumerate(widths):
            table.columns[j].width = width

    # шапка повторяется на следующей странице
    trPr = table.rows[0]._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:tblHeader"))
    trPr.append(OxmlElement("w:cantSplit"))

    for j, text in enumerate(header):
        cell = table.rows[0].cells[j]
        if widths:
            cell.width = widths[j]
        cell.text = ""
        p = cell.paragraphs[0]
        add_inline(p, text, size=9.5)
        for run in p.runs:
            run.bold = True
        shade(cell)
        _cell_left(cell)

    for row in body:
        cells = table.add_row().cells
        trPr = table.rows[-1]._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        for j, text in enumerate(row[:ncols]):
            cells[j].text = ""
            if widths:
                cells[j].width = widths[j]
            add_inline(cells[j].paragraphs[0], text, size=9.5)
            _cell_left(cells[j])

    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.line_spacing = Pt(5)
    spacer.paragraph_format.first_line_indent = Cm(0)


def add_image(doc, alt, path):
    full = ROOT / path
    if not full.exists():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    run = p.add_run()
    run.add_picture(str(full), width=Cm(15))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.first_line_indent = Cm(0)
    cap.paragraph_format.space_after = Pt(8)
    run = cap.add_run(alt)
    set_run_font(run, size=10, italic=True)


def parse_table(lines, start):
    rows = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        raw = lines[i].strip().strip("|")
        cells = [c.strip() for c in raw.split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            rows.append(cells)
        i += 1
    return rows, i


def build():
    md = SRC.read_text(encoding="utf-8").splitlines()
    doc = Document()
    setup(doc)

    i = 0
    paragraph = None  # накопитель обычного текста
    first_heading = True
    in_meta = False

    def flush():
        nonlocal paragraph
        if paragraph is not None:
            # длинные куски кода не дают растягивать пробелы по ширине
            long_code = any(
                run.font.name == MONO and len(run.text) >= 12
                for run in paragraph.runs)
            if long_code:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph = None

    while i < len(md):
        line = md[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            block = []
            i += 1
            while i < len(md) and not md[i].strip().startswith("```"):
                block.append(md[i])
                i += 1
            i += 1
            add_code(doc, block)
            continue

        if stripped.startswith("#"):
            flush()
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip().replace("`", "").replace("**", "")
            if first_heading:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.first_line_indent = Cm(0)
                p.paragraph_format.space_after = Pt(10)
                run = p.add_run(text)
                set_run_font(run, size=18, bold=True)
                first_heading = False
                in_meta = True
            else:
                in_meta = False
                p = doc.add_paragraph(style=f"Heading {min(level - 1, 3)}")
                p.paragraph_format.first_line_indent = Cm(0)
                run = p.add_run(text)
                set_run_font(run, size={2: 15, 3: 13, 4: 12}.get(level, 12), bold=True)
            i += 1
            continue

        m = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
        if m:
            flush()
            add_image(doc, m.group(1), m.group(2))
            i += 1
            continue

        if stripped.startswith("|"):
            flush()
            rows, i = parse_table(md, i)
            if rows:
                add_table(doc, rows)
            continue

        if stripped.startswith(("- ", "* ")):
            flush()
            p = doc.add_paragraph()
            p.paragraph_format.first_line_indent = Cm(-0.4)
            p.paragraph_format.left_indent = Cm(0.8)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run("•  ")
            set_run_font(run, size=12)
            add_inline(p, stripped[2:])
            paragraph = p
            i += 1
            continue

        numbered = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if numbered and paragraph is None:
            p = doc.add_paragraph()
            p.paragraph_format.first_line_indent = Cm(-0.4)
            p.paragraph_format.left_indent = Cm(0.8)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(f"{numbered.group(1)}.  ")
            set_run_font(run, size=12)
            add_inline(p, numbered.group(2))
            paragraph = p
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue

        if paragraph is None:
            paragraph = doc.add_paragraph()
            if in_meta:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                paragraph.paragraph_format.first_line_indent = Cm(0)
                paragraph.paragraph_format.space_after = Pt(2)
        elif paragraph.runs:
            paragraph.add_run().add_break()
        add_inline(paragraph, stripped)
        i += 1

    flush()
    doc.core_properties.title = "Лабораторная работа № 4. Гестурный пульт"
    doc.core_properties.subject = "Трек A — управление"
    doc.save(DST)
    print("Сохранено:", DST)


if __name__ == "__main__":
    build()
