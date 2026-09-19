"""Printable question paper and answer key for an Abako competition round.

Both documents are painted with a plain :class:`~reportlab.pdfgen.canvas.Canvas`
rather than a Platypus flowable pipeline, because the one property that
matters most for a document a room full of students writes on is that a
question is never split across a column or page break. The question paper is
therefore built in two passes: every question is measured first (wrapped at
the exact column width it will be drawn at) so the whole set can be packed
into whole, unbroken blocks before a single stroke is drawn. That also means
the total page count is known up front, which is what lets the footer say
"Page N of M".

Every colour, type size and spacing value comes from ``backend/pdf_theme.py``
- the shared visual language for the whole document suite - except for the
font used for question text itself. Competition questions can contain pi, a
radical, a times/divide sign or a less-than-or-equal sign, and none of those
live in Helvetica's built-in base-14 encoding; they print as empty boxes.
DejaVu Sans covers them, and it already ships inside matplotlib, which the
report generator depends on, so no new font asset has to be bundled with the
app.
"""

import math
import os
from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from backend import pdf_theme as theme

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

BODY_FONT = "Helvetica"
BODY_FONT_BOLD = "Helvetica-Bold"

try:
    import matplotlib
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    _ttf_dir = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    pdfmetrics.registerFont(TTFont("AbakoExamBody", os.path.join(_ttf_dir, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(
        TTFont("AbakoExamBody-Bold", os.path.join(_ttf_dir, "DejaVuSans-Bold.ttf"))
    )
    BODY_FONT = "AbakoExamBody"
    BODY_FONT_BOLD = "AbakoExamBody-Bold"
except Exception:
    # If matplotlib or its bundled fonts are ever unavailable, fall back to
    # the base-14 font rather than fail exam generation outright.
    pass


def _hex(color):
    return f"#{int(color.red * 255):02x}{int(color.green * 255):02x}{int(color.blue * 255):02x}"


_MIST_HEX = _hex(theme.MIST)
_CHARCOAL_HEX = _hex(theme.CHARCOAL)

# ---------------------------------------------------------------------------
# Question paper geometry
# ---------------------------------------------------------------------------

GUTTER = 0.34 * inch
COL_WIDTH = (theme.CONTENT_W - GUTTER) / 2
NUM_GUTTER = 20  # hanging indent reserved for the question number
TEXT_WIDTH = COL_WIDTH - NUM_GUTTER

ANSWER_BOX_H = 56
TAG_GAP = 3
TEXT_TO_BOX_GAP = theme.GAP_XS + 2
BLOCK_GAP = theme.GAP_MD

STUDENT_BLOCK_H = 92
RUNNING_HEADER_H = 0.95 * inch

_question_style = ParagraphStyle(
    "examQuestion",
    fontName=BODY_FONT,
    fontSize=theme.SIZE_BODY,
    leading=theme.SIZE_BODY * theme.LEADING,
    textColor=theme.INK,
)
_tag_style = ParagraphStyle(
    "examTag",
    fontName=BODY_FONT_BOLD,
    fontSize=theme.SIZE_MICRO,
    leading=theme.SIZE_MICRO * 1.3,
    textColor=theme.SLATE,
)
def _has_inline_tag(text):
    stripped = text.strip()
    return stripped.startswith("[") and "]" in stripped[:40]


def _build_question(index, question):
    text = str(question.get("Question_Text", f"Question {index + 1}"))
    tag = None
    if not _has_inline_tag(text):
        chapter = question.get("Chapter")
        if chapter:
            tag = str(chapter)

    para = Paragraph(escape(text), _question_style)
    _, text_h = para.wrap(TEXT_WIDTH, 5000)

    tag_para = None
    tag_h = 0
    if tag:
        tag_para = Paragraph(theme.letterspace(tag), _tag_style)
        _, raw_h = tag_para.wrap(TEXT_WIDTH, 200)
        tag_h = raw_h + TAG_GAP

    height = tag_h + text_h + TEXT_TO_BOX_GAP + ANSWER_BOX_H + BLOCK_GAP
    return {
        "number": index + 1,
        "para": para,
        "text_h": text_h,
        "tag_para": tag_para,
        "tag_h": tag_h,
        "height": height,
    }


def _layout_pages(blocks, first_col_h, rest_col_h):
    """Pack whole question blocks into columns and pages.

    Each block is placed as an indivisible unit, so a question's number can
    never end up alone at the bottom of a column - if it does not fit, the
    whole block moves to the next column or page instead.
    """
    pages = [{0: [], 1: []}]
    cap = [first_col_h, first_col_h]
    col = 0

    for block in blocks:
        h = block["height"]
        if h <= cap[col] or not pages[-1][col]:
            pages[-1][col].append(block)
            cap[col] -= h
            continue
        if col == 0:
            col = 1
            if h <= cap[col] or not pages[-1][col]:
                pages[-1][col].append(block)
                cap[col] -= h
                continue
        pages.append({0: [], 1: []})
        cap = [rest_col_h, rest_col_h]
        col = 0
        pages[-1][col].append(block)
        cap[col] -= h

    return pages


def _identity_cell(label, value):
    value_text = escape(str(value)) if value else "—"
    markup = (
        f'<font face="{BODY_FONT_BOLD}" size="{theme.SIZE_MICRO}" color="{_MIST_HEX}">'
        f"{theme.letterspace(label)}</font><br/>"
        f'<font face="{BODY_FONT_BOLD}" size="{theme.SIZE_H3}" color="{_CHARCOAL_HEX}">'
        f"{value_text}</font>"
    )
    return Paragraph(markup, ParagraphStyle("idcell", leading=theme.SIZE_H3 * 1.3))


def _make_identity_table(school_info):
    data = [[
        _identity_cell("School", school_info.get("School Name", "")),
        _identity_cell("Campus", school_info.get("Campus", "")),
        _identity_cell("Grade", school_info.get("Grade", "")),
        _identity_cell("Date", school_info.get("Exam Date", "")),
    ]]
    col_widths = [
        theme.CONTENT_W * 0.40,
        theme.CONTENT_W * 0.20,
        theme.CONTENT_W * 0.15,
        theme.CONTENT_W * 0.25,
    ]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _draw_student_block(canvas, top):
    """Ruled Name / Student ID / School lines plus a single honour-code
    signature line. This appears once, on page 1, never repeated."""
    field_widths = [theme.CONTENT_W * 0.40, theme.CONTENT_W * 0.22, theme.CONTENT_W * 0.38]
    labels = ["Name", "Student ID", "School"]
    label_y = top
    line_y = top - 15

    x = theme.MARGIN_X
    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_MICRO)
    canvas.setFillColor(theme.MIST)
    for width, label in zip(field_widths, labels, strict=True):
        canvas.drawString(x, label_y, label.upper())
        theme.draw_rule(canvas, x, line_y, x + width - 16, theme.RULE_STRONG, 0.8)
        x += width

    honour_top = line_y - theme.GAP_LG
    honour_line_y = honour_top - 13
    canvas.setFont(BODY_FONT, theme.SIZE_SMALL)
    canvas.setFillColor(theme.SLATE)
    canvas.drawString(
        theme.MARGIN_X, honour_top,
        "I confirm that I have completed this exam honestly and without unauthorized assistance.",
    )
    theme.draw_rule(canvas, theme.MARGIN_X, honour_line_y, theme.MARGIN_X + 2.6 * inch,
                     theme.RULE_STRONG, 0.8)
    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_MICRO)
    canvas.setFillColor(theme.MIST)
    canvas.drawString(theme.MARGIN_X, honour_line_y - 10, "SIGNATURE")

    return honour_line_y - 10


def _draw_page1_header(canvas, school_info, identity_table, identity_h):
    top = theme.PAGE_H - 0.46 * inch
    theme.draw_wordmark(canvas, theme.MARGIN_X, top - theme.LOGO_H)

    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_H1)
    canvas.setFillColor(theme.CHARCOAL)
    canvas.drawRightString(theme.PAGE_W - theme.MARGIN_X, top - theme.LOGO_H + 8, "QUESTION PAPER")

    rule_y = top - theme.LOGO_H - 9
    theme.draw_rule(canvas, theme.MARGIN_X, rule_y, theme.PAGE_W - theme.MARGIN_X, theme.RULE_STRONG, 0.8)

    identity_top = rule_y - theme.GAP_MD
    identity_table.drawOn(canvas, theme.MARGIN_X, identity_top - identity_h)

    student_top = identity_top - identity_h - theme.GAP_LG
    return _draw_student_block(canvas, student_top) - theme.GAP_LG


def _draw_running_header(canvas, school_info, page_num, total_pages):
    top = theme.PAGE_H - 0.42 * inch
    school = str(school_info.get("School Name", ""))
    if len(school) > 46:
        school = school[:43] + "…"
    grade = school_info.get("Grade", "")

    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_H3)
    canvas.setFillColor(theme.CHARCOAL)
    canvas.drawString(theme.MARGIN_X, top, school)

    canvas.setFont(BODY_FONT, theme.SIZE_SMALL)
    canvas.setFillColor(theme.SLATE)
    grade_text = str(grade)
    sub = grade_text if grade_text.lower().startswith("grade") else f"Grade {grade_text}"
    canvas.drawString(theme.MARGIN_X, top - 13, sub if grade else "")

    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_SMALL)
    canvas.setFillColor(theme.SLATE)
    canvas.drawRightString(theme.PAGE_W - theme.MARGIN_X, top - 2,
                            f"PAGE {page_num} OF {total_pages}")

    rule_y = top - 22
    theme.draw_rule(canvas, theme.MARGIN_X, rule_y, theme.PAGE_W - theme.MARGIN_X, theme.RULE, 0.7)
    return rule_y - theme.GAP_MD


def _draw_footer(canvas, page_num, total_pages):
    y = 0.46 * inch
    theme.draw_rule(canvas, theme.MARGIN_X, y + 12, theme.PAGE_W - theme.MARGIN_X, theme.RULE, 0.6)
    canvas.setFont(BODY_FONT, theme.SIZE_MICRO)
    canvas.setFillColor(theme.MIST)
    canvas.drawString(theme.MARGIN_X, y, "Abako Math Competition")
    canvas.drawRightString(theme.PAGE_W - theme.MARGIN_X, y, f"Page {page_num} of {total_pages}")


def _draw_answer_box(canvas, x, y_top, width, height):
    canvas.saveState()
    canvas.setStrokeColor(theme.RULE_STRONG)
    canvas.setLineWidth(0.7)
    canvas.roundRect(x, y_top - height, width, height, 3, stroke=1, fill=0)

    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_MICRO)
    canvas.setFillColor(theme.MIST)
    label_y = y_top - height + 8
    canvas.drawString(x + 6, label_y, "ANSWER")
    theme.draw_rule(canvas, x + 48, label_y + 3, x + width - 8, theme.RULE, 0.6)
    canvas.restoreState()


def _draw_question_block(canvas, block, x, y_top):
    cursor = y_top
    text_x = x + NUM_GUTTER

    if block["tag_para"]:
        tag_h = block["tag_h"] - TAG_GAP
        block["tag_para"].drawOn(canvas, text_x, cursor - tag_h)
        cursor -= block["tag_h"]

    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_H3)
    canvas.setFillColor(theme.CHARCOAL)
    canvas.drawString(x, cursor - theme.SIZE_H3, f"{block['number']}.")

    block["para"].drawOn(canvas, text_x, cursor - block["text_h"])
    cursor -= block["text_h"] + TEXT_TO_BOX_GAP

    _draw_answer_box(canvas, text_x, cursor, TEXT_WIDTH, ANSWER_BOX_H)


def generate_question_paper(filename, school_info, questions):
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

    blocks = [_build_question(i, q) for i, q in enumerate(questions)]

    identity_table = _make_identity_table(school_info)
    _, identity_h = identity_table.wrap(theme.CONTENT_W, 2000)

    top = theme.PAGE_H - 0.46 * inch
    rule_y = top - theme.LOGO_H - 9
    identity_top = rule_y - theme.GAP_MD
    student_top = identity_top - identity_h - theme.GAP_LG
    col_top_page1 = student_top - STUDENT_BLOCK_H - theme.GAP_LG
    col_top_rest = theme.PAGE_H - RUNNING_HEADER_H

    first_col_h = col_top_page1 - theme.MARGIN_BOTTOM
    rest_col_h = col_top_rest - theme.MARGIN_BOTTOM

    pages = _layout_pages(blocks, first_col_h, rest_col_h)
    total_pages = len(pages)

    col_x = [theme.MARGIN_X, theme.MARGIN_X + COL_WIDTH + GUTTER]

    canvas = Canvas(filename, pagesize=(theme.PAGE_W, theme.PAGE_H))
    for page_index, page in enumerate(pages):
        if page_index == 0:
            _draw_page1_header(canvas, school_info, identity_table, identity_h)
            col_top = col_top_page1
        else:
            _draw_running_header(canvas, school_info, page_index + 1, total_pages)
            col_top = col_top_rest

        for col in (0, 1):
            y = col_top
            for block in page[col]:
                _draw_question_block(canvas, block, col_x[col], y)
                y -= block["height"]

        _draw_footer(canvas, page_index + 1, total_pages)
        canvas.showPage()

    canvas.save()


# ---------------------------------------------------------------------------
# Answer key
# ---------------------------------------------------------------------------

_KEY_HEADER_FONT_SIZE = theme.SIZE_MICRO


def _answer_key_grid(questions):
    n = len(questions)
    if n == 0:
        return 1, 0, []
    cols = max(1, min(5, math.ceil(n / 12)))
    rows = math.ceil(n / cols)
    groups = [questions[i * rows:(i + 1) * rows] for i in range(cols)]
    return cols, rows, groups


def generate_answer_key(filename, questions, school_name="", campus_name="", grade="", exam_date=""):
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

    canvas = Canvas(filename, pagesize=(theme.PAGE_W, theme.PAGE_H))

    top = theme.PAGE_H - 0.46 * inch
    theme.draw_wordmark(canvas, theme.MARGIN_X, top - theme.LOGO_H)

    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_H1)
    canvas.setFillColor(theme.CHARCOAL)
    canvas.drawRightString(theme.PAGE_W - theme.MARGIN_X, top - theme.LOGO_H + 14, "ANSWER KEY")

    canvas.setFont(BODY_FONT_BOLD, theme.SIZE_SMALL)
    canvas.setFillColor(theme.RED_DEEP)
    canvas.drawRightString(theme.PAGE_W - theme.MARGIN_X, top - theme.LOGO_H,
                            "CONFIDENTIAL — DO NOT DISTRIBUTE TO STUDENTS")

    rule_y = top - theme.LOGO_H - 9
    theme.draw_rule(canvas, theme.MARGIN_X, rule_y, theme.PAGE_W - theme.MARGIN_X, theme.RULE_STRONG, 0.8)

    school_info = {
        "School Name": school_name,
        "Campus": campus_name,
        "Grade": grade,
        "Exam Date": exam_date,
    }
    identity_table = _make_identity_table(school_info)
    identity_top = rule_y - theme.GAP_MD
    _, identity_h = identity_table.wrap(theme.CONTENT_W, 2000)
    identity_table.drawOn(canvas, theme.MARGIN_X, identity_top - identity_h)

    grid_top = identity_top - identity_h - theme.GAP_LG

    cols, rows, groups = _answer_key_grid(questions)

    table_data = [["NO.", "ANSWER"] * cols]
    for r in range(rows):
        row = []
        for group_index, group in enumerate(groups):
            if r < len(group):
                q_number = group_index * rows + r + 1
                row.append(str(q_number))
                row.append(str(group[r].get("Correct_Answer", "")))
            else:
                row.append("")
                row.append("")
        table_data.append(row)

    col_w_no = 0.34 * inch
    col_w_ans = (theme.CONTENT_W - cols * col_w_no) / cols if cols else theme.CONTENT_W
    col_widths = [col_w_no, col_w_ans] * cols

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, 0), BODY_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), _KEY_HEADER_FONT_SIZE),
        ("TEXTCOLOR", (0, 0), (-1, 0), theme.PAPER),
        ("BACKGROUND", (0, 0), (-1, 0), theme.CHARCOAL),
        ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
        ("FONTSIZE", (0, 1), (-1, -1), theme.SIZE_BODY),
        ("TEXTCOLOR", (0, 1), (-1, -1), theme.INK),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, theme.RULE_STRONG),
        ("BOX", (0, 0), (-1, -1), 0.8, theme.RULE_STRONG),
    ]
    for r in range(1, rows + 1):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), theme.PANEL))
    for group_index in range(1, cols):
        c = group_index * 2
        style_cmds.append(("LINEBEFORE", (c, 0), (c, -1), 0.8, theme.RULE_STRONG))
    for group_index in range(cols):
        c = group_index * 2
        style_cmds.append(("FONTNAME", (c, 1), (c, -1), BODY_FONT_BOLD))
        style_cmds.append(("TEXTCOLOR", (c, 1), (c, -1), theme.SLATE))

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    table_w, table_h = table.wrap(theme.CONTENT_W, grid_top - theme.MARGIN_BOTTOM)
    table.drawOn(canvas, theme.MARGIN_X + (theme.CONTENT_W - table_w) / 2, grid_top - table_h)

    footer_y = 0.46 * inch
    theme.draw_rule(canvas, theme.MARGIN_X, footer_y + 12, theme.PAGE_W - theme.MARGIN_X, theme.RULE, 0.6)
    canvas.setFont(BODY_FONT, theme.SIZE_MICRO)
    canvas.setFillColor(theme.MIST)
    canvas.drawString(theme.MARGIN_X, footer_y, "Marking aid only — keep out of student reach.")
    canvas.drawRightString(theme.PAGE_W - theme.MARGIN_X, footer_y, f"{len(questions)} Questions")

    canvas.showPage()
    canvas.save()
