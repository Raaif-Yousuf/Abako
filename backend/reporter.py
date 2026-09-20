"""Student-facing PDF output: the individual report card / certificate combo
and the school summary.

Every colour, type size, spacing value and piece of page furniture comes from
``backend.pdf_theme`` so this document pack reads as one system with the
question paper and answer key. Nothing here invents data - stat tiles, the
score track and the remarks paragraph only ever restate numbers already
present on the student or cohort dict.
"""

import datetime
import io
import math
import os
import re
import textwrap
from xml.sax.saxutils import escape as _esc

import matplotlib

matplotlib.use("Agg")  # must happen before pyplot is imported anywhere below
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Flowable, Paragraph, Table, TableStyle

from backend import pdf_theme as theme

MAX_SCORE = 60


# --------------------------------------------------------------------------
# Small shared helpers
# --------------------------------------------------------------------------

def _ensure_dir(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def _flow(c, flowable, x, y_top, avail_w, gap_after=0):
    """Wrap a Platypus flowable (Paragraph or Table) and draw it hanging down
    from ``y_top``. Returns the new cursor position below it."""
    _, h = flowable.wrap(avail_w, y_top)
    flowable.drawOn(c, x, y_top - h)
    return y_top - h - gap_after


def _truncate(c, text, font, size, max_w):
    if c.stringWidth(text, font, size) <= max_w:
        return text
    ell = "…"
    while text and c.stringWidth(text + ell, font, size) > max_w:
        text = text[:-1]
    return (text + ell) if text else ell


def _median(values):
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def _wrap_label(text, width=12):
    wrapped = textwrap.wrap(str(text), width=width, break_long_words=False,
                            break_on_hyphens=False)
    return "\n".join(wrapped) or str(text)


def _ordinal(n):
    """13 -> '13th', 22 -> '22nd'. Percentiles are fractional, so round to
    the nearest whole number first - "93.3th" is not a word."""
    i = int(round(n))
    if 10 <= abs(i) % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(abs(i) % 10, "th")
    return f"{i}{suffix}"


def _name_style(name, base_style):
    """Shrink the name style for long names so it wraps to at most two lines
    instead of three or four - a name is a headline, not a paragraph."""
    n = len(name)
    if n <= 26:
        size = 22
    elif n <= 42:
        size = 18
    else:
        size = 15
    return base_style.clone("_name_fit", fontSize=size, leading=round(size * 1.15, 1))


def _draw_demo_footer(c):
    """A clear, unmissable footer line - so demo numbers can never be
    mistaken for a real result. Used on every page."""
    c.saveState()
    c.setFont(theme.SANS_BOLD, theme.SIZE_MICRO)
    c.setFillColor(theme.MIST)
    c.drawCentredString(theme.PAGE_W / 2, theme.MARGIN_BOTTOM * 0.42,
                        "DEMO DATA - FOR PREVIEW ONLY, NOT AN OFFICIAL RESULT")
    c.restoreState()


def _draw_demo_diagonal(c):
    """A light diagonal watermark, reserved for the certificate - it has the
    open white space to carry it without burying a data table under it."""
    c.saveState()
    c.translate(theme.PAGE_W / 2, theme.PAGE_H / 2)
    c.rotate(36)
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.06))
    c.setFont(theme.SANS_BOLD, 118)
    c.drawCentredString(0, -40, "DEMO")
    c.restoreState()


def _place_chart(c, buf, x, y_top, width, max_h):
    """Draw a chart PNG at its true aspect ratio, capped to max_h, centred in
    the given width."""
    reader = ImageReader(buf)
    iw, ih = reader.getSize()
    w, h = width, width * ih / iw
    if h > max_h:
        h = max_h
        w = h * iw / ih
    cx = x + (width - w) / 2
    c.drawImage(reader, cx, y_top - h, width=w, height=h, mask="auto")
    return y_top - h


# --------------------------------------------------------------------------
# A tiny proportional bar used inside table cells
# --------------------------------------------------------------------------

class _ScoreBar(Flowable):
    """A rounded track with a proportional fill and a trailing percentage,
    used in the Score column of the topic-breakdown table."""

    def __init__(self, pct, width=90, height=9):
        super().__init__()
        self.pct = max(0.0, min(100.0, float(pct)))
        self.width = width
        self.height = height

    def wrap(self, *_args):
        return self.width, self.height

    def draw(self):
        c = self.canv
        bar_w = self.width - 30
        weak = self.pct < 33
        c.saveState()
        c.setFillColor(theme.PANEL_DEEP)
        c.roundRect(0, 0, bar_w, self.height, self.height / 2, fill=1, stroke=0)
        fill_w = bar_w * self.pct / 100.0
        if fill_w > 0:
            if self.pct >= 66:
                color = theme.SCORE_STRONG
            elif self.pct >= 33:
                color = theme.SCORE_MID
            else:
                color = theme.SCORE_WEAK
            c.setFillColor(color)
            c.roundRect(0, 0, max(fill_w, self.height), self.height,
                       self.height / 2, fill=1, stroke=0)
        # A weak score gets brand red *and* bold weight - a topic that needs
        # attention should stand out by more than hue alone.
        c.setFont(theme.SANS_BOLD, theme.SIZE_SMALL)
        c.setFillColor(theme.SCORE_WEAK if weak else theme.SLATE)
        c.drawRightString(self.width, self.height / 2 - 3, f"{self.pct:.0f}%")
        c.restoreState()


# --------------------------------------------------------------------------
# Chart
# --------------------------------------------------------------------------

def _make_topic_chart(topic_breakdown, all_topics):
    """A stacked correct/incorrect/unattempted bar chart, house style, dpi
    >= 200, closed cleanly so repeated calls never leak figures."""
    labels = list(all_topics)
    correct, incorrect, unattempted = [], [], []
    for t in labels:
        st = topic_breakdown.get(t, {})
        correct.append(st.get("correct", 0))
        incorrect.append(st.get("incorrect", 0))
        unattempted.append(st.get("unattempted", 0))

    crowded = len(labels) > 7
    fig, ax = plt.subplots(figsize=(7.3, 2.95 if crowded else 2.55))
    x = list(range(len(labels)))
    # Correct/incorrect/unattempted read apart by more than hue alone - a
    # solid black fill, a red diagonal hatch and a grey dot hatch - so the
    # three states still separate in greyscale print or for a colour-blind
    # reader.
    ax.bar(x, correct, color=theme.CHART_CORRECT, label="Correct", width=0.62,
          zorder=3, hatch=theme.HATCH_CORRECT, edgecolor="white", linewidth=0.4)
    ax.bar(x, incorrect, bottom=correct, color=theme.CHART_INCORRECT,
          label="Incorrect", width=0.62, zorder=3, hatch=theme.HATCH_INCORRECT,
          edgecolor="white", linewidth=0.4)
    bottom2 = [cc + ii for cc, ii in zip(correct, incorrect, strict=True)]
    ax.bar(x, unattempted, bottom=bottom2, color=theme.CHART_UNATTEMPTED,
          label="Unattempted", width=0.62, zorder=3, hatch=theme.HATCH_UNATTEMPTED,
          edgecolor="white", linewidth=0.4)

    ax.set_xticks(x)
    if crowded:
        # Many categories: a short, diagonal, single-line label reads better
        # than a wrapped one (which collides with its neighbours) - the full
        # name is already in the table above, so the chart can abbreviate.
        short = [t if len(t) <= 22 else t[:21].rstrip() + "…" for t in labels]
        ax.set_xticklabels(short, fontsize=7, rotation=38, ha="right",
                          rotation_mode="anchor")
    else:
        ax.set_xticklabels([_wrap_label(t) for t in labels], fontsize=7.2)
    ax.set_ylabel("Questions", fontsize=7.5, color=theme.CHART_TEXT)
    theme.apply_chart_style(ax, fig)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=3,
             frameon=False, fontsize=7.5, labelcolor=theme.CHART_TEXT,
             handlelength=1.0, columnspacing=1.2)
    if crowded:
        # A fixed bottom margin (rather than tight_layout) keeps the figure
        # at its declared size regardless of how far the diagonal labels
        # descend, so the plotted bars keep their share of the image.
        fig.subplots_adjust(left=0.07, right=0.99, top=0.80, bottom=0.38)
    else:
        fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=220, facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


# --------------------------------------------------------------------------
# Report card (page 1)
# --------------------------------------------------------------------------

_META_FRACTIONS = (0.13, 0.34, 0.13, 0.14, 0.26)


def _draw_meta_row(c, x, y_top, width, items):
    """Eyebrow label above value, laid out in columns sized for what they
    typically hold (School gets the most room, Student ID the least)."""
    fractions = _META_FRACTIONS if len(items) == len(_META_FRACTIONS) else \
        [1 / len(items)] * len(items)
    eyebrow_h = theme.SIZE_MICRO * theme.LEADING
    value_h = theme.SIZE_H3 * theme.LEADING
    block_h = eyebrow_h + value_h + 2
    c.saveState()
    cx = x
    for (label, value), frac in zip(items, fractions, strict=True):
        col_w = width * frac
        c.setFont(theme.SANS_BOLD, theme.SIZE_MICRO)
        c.setFillColor(theme.MIST)
        c.drawString(cx, y_top - eyebrow_h + 2, label.upper())
        c.setFont(theme.SANS_BOLD, theme.SIZE_H3)
        c.setFillColor(theme.CHARCOAL)
        text = _truncate(c, str(value), theme.SANS_BOLD, theme.SIZE_H3, col_w - 10)
        c.drawString(cx, y_top - block_h + 4, text)
        cx += col_w
    c.restoreState()
    return y_top - block_h


def _draw_stat_row(c, x, y_top, width, tiles, tile_h=62):
    n = len(tiles)
    gap = theme.GAP_SM
    tile_w = (width - gap * (n - 1)) / n
    for i, (label, value, color) in enumerate(tiles):
        tx = x + i * (tile_w + gap)
        theme.draw_stat_tile(c, tx, y_top - tile_h, tile_w, tile_h, label, value,
                             value_color=color, value_size=20)
    return y_top - tile_h


def _draw_score_track(c, x, y_top, width, student_score, class_avg, percentile,
                      max_score=MAX_SCORE, track_h=40):
    y_bottom = y_top - track_h
    line_y = y_bottom + track_h / 2 - 2

    def clamp_x(px):
        return max(x + 34, min(px, x + width - 34))

    def marker_x(score):
        return x + width * max(0, min(score, max_score)) / max_score

    c.saveState()
    c.setStrokeColor(theme.RULE_STRONG)
    c.setLineWidth(2)
    c.line(x, line_y, x + width, line_y)
    for pct in (0, 25, 50, 75, 100):
        tx = x + width * pct / 100
        c.setStrokeColor(theme.RULE)
        c.setLineWidth(0.8)
        c.line(tx, line_y - 3, tx, line_y + 3)

    # The class average is a reference tick, drawn first and taller than the
    # student's dot so it stays visible even when the two nearly coincide.
    avg_x = marker_x(class_avg)
    c.setStrokeColor(theme.SLATE)
    c.setLineWidth(1.6)
    c.line(avg_x, line_y - 7, avg_x, line_y + 7)
    c.setFont(theme.SANS, theme.SIZE_MICRO)
    c.setFillColor(theme.SLATE)
    c.drawCentredString(clamp_x(avg_x), line_y - 18, f"Class average · {class_avg:g}")

    stu_x = marker_x(student_score)
    c.setFillColor(theme.RED_DEEP)
    c.circle(stu_x, line_y, 4.5, fill=1, stroke=0)
    c.setFont(theme.SANS_BOLD, theme.SIZE_SMALL)
    c.setFillColor(theme.RED_DEEP)
    c.drawCentredString(clamp_x(stu_x), line_y + 13,
                       f"{student_score:g} · {_ordinal(percentile)} percentile")
    c.restoreState()
    return y_bottom


def _topic_table_style(n_rows, emphasize_col=None):
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), theme.CHARCOAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 1.0, theme.CHARCOAL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [theme.PAPER, theme.PANEL]),
    ]
    for r in range(1, n_rows - 1):
        cmds.append(("LINEBELOW", (0, r), (-1, r), 0.5, theme.RULE))
    if emphasize_col is not None:
        # The Score column is the headline number in this table - a brand
        # red header cell (not another grey) draws the eye to it, the same
        # way theme.RED_DEEP marks the one number that matters elsewhere.
        cmds.append(("BACKGROUND", (emphasize_col, 0), (emphasize_col, 0), theme.RED_DEEP))
    return TableStyle(cmds)


def _build_topic_table(all_topics, topic_breakdown, width):
    styles = theme.styles()
    cell, cell_r = styles["cell"], styles["cell"].clone("_cell_r", alignment=TA_RIGHT)
    head, head_r = styles["cell_head"], styles["cell_head"].clone("_head_r", alignment=TA_RIGHT)

    col_w = [width * 0.34, width * 0.15, width * 0.15, width * 0.16, width * 0.20]
    bar_w = col_w[4] - 16

    header_row = [
        Paragraph(theme.letterspace("Topic"), head),
        Paragraph(theme.letterspace("Correct"), head_r),
        Paragraph(theme.letterspace("Incorrect"), head_r),
        Paragraph(theme.letterspace("Unattempted"), head_r),
        Paragraph(theme.letterspace("Score"), head_r),
    ]
    data = [header_row]
    for t in all_topics:
        st = topic_breakdown.get(t)
        if st:
            data.append([
                Paragraph(_esc(str(t)), cell),
                Paragraph(str(st["correct"]), cell_r),
                Paragraph(str(st["incorrect"]), cell_r),
                Paragraph(str(st["unattempted"]), cell_r),
                _ScoreBar(st["percentage"], width=bar_w),
            ])
        else:
            data.append([
                Paragraph(_esc(str(t)), cell),
                Paragraph("—", cell_r), Paragraph("—", cell_r),
                Paragraph("—", cell_r), Paragraph("—", cell_r),
            ])

    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(_topic_table_style(len(data), emphasize_col=4))
    return tbl


def _derive_student_remarks(student, class_avg, topic_breakdown, all_topics):
    """Rule-based sentences describing this student's result. Every clause
    is a direct restatement of a field already on the student dict."""
    name = str(student.get("name", "The student")).split()[0] or "The student"
    final = student.get("final_score", 0)
    diff = round(final - class_avg, 1)
    sentences = []
    if diff > 0:
        sentences.append(f"{name} scored {abs(diff):g} point{'s' if abs(diff) != 1 else ''} "
                        f"above the class average of {class_avg:g}.")
    elif diff < 0:
        sentences.append(f"{name} scored {abs(diff):g} point{'s' if abs(diff) != 1 else ''} "
                        f"below the class average of {class_avg:g}.")
    else:
        sentences.append(f"{name} scored exactly at the class average of {class_avg:g}.")

    scored = [(t, topic_breakdown[t]) for t in all_topics
             if t in topic_breakdown and topic_breakdown[t].get("total", 0) > 0]
    if scored:
        best = max(scored, key=lambda kv: kv[1]["percentage"])
        worst = min(scored, key=lambda kv: kv[1]["percentage"])
        if best[0] == worst[0] or len(scored) == 1:
            sentences.append(f"Performance was steady, centred on {best[0]} at {best[1]['percentage']:g}%.")
        else:
            sentences.append(f"The strongest topic was {best[0]} at {best[1]['percentage']:g}%, "
                            f"while {worst[0]} is the area to revisit, at {worst[1]['percentage']:g}%.")
        total_q = sum(s["total"] for _, s in scored)
        attempted = sum(s["correct"] + s["incorrect"] for _, s in scored)
        if total_q:
            rate = round(attempted / total_q * 100)
            sentences.append(f"{name} attempted {rate}% of the questions across {len(scored)} topics.")
    return " ".join(sentences)


def _draw_report_card(c, student, school_info, all_topics, class_avg, demo=False):
    c.setFillColor(theme.PAPER)
    c.rect(0, 0, theme.PAGE_W, theme.PAGE_H, fill=1, stroke=0)

    context = " · ".join(str(school_info.get(k, "—")) for k in
                        ("School Name", "Campus", "Grade") if school_info.get(k))
    theme.draw_page_furniture(c, None, title="Individual Performance Report",
                              context_line=context)
    if demo:
        _draw_demo_footer(c)

    x0 = theme.MARGIN_X
    width = theme.CONTENT_W
    cursor = theme.PAGE_H - theme.MARGIN_TOP

    styles = theme.styles()
    name_text = str(student.get("name", ""))
    name_style = _name_style(name_text, styles["name"])
    name_par = Paragraph(_esc(name_text), name_style)
    cursor = _flow(c, name_par, x0, cursor, width * 0.7, gap_after=theme.GAP_SM)

    meta_items = [
        ("Student ID", student.get("student_id", "—")),
        ("School", school_info.get("School Name", "—")),
        ("Campus", school_info.get("Campus", "—")),
        ("Grade", school_info.get("Grade", "—")),
        ("Exam Date", school_info.get("Exam Date", "—")),
    ]
    cursor = _draw_meta_row(c, x0, cursor, width, meta_items)
    cursor -= theme.GAP_MD

    final_score = student.get("final_score", 0)
    percentile = student.get("percentile", 0)
    rank = student.get("rank")
    rank_display = str(rank) if rank and rank <= 10 else "—"
    tiles = [
        ("Final Score", f"{final_score:g} / {MAX_SCORE}", theme.RED_DEEP),
        ("Percentile", _ordinal(percentile), None),
        ("Rank", rank_display, None),
        ("Class Average", f"{class_avg:g} / {MAX_SCORE}", None),
    ]
    cursor = _draw_stat_row(c, x0, cursor, width, tiles)
    cursor -= theme.GAP_MD

    cursor = _draw_score_track(c, x0, cursor, width, final_score, class_avg, percentile)
    cursor -= theme.GAP_MD

    theme.draw_rule(c, x0, cursor, x0 + width)
    cursor -= theme.GAP_SM
    c.setFont(theme.SANS_BOLD, theme.SIZE_H3)
    c.setFillColor(theme.CHARCOAL)
    c.drawString(x0, cursor - theme.SIZE_H3, "Topic Breakdown")
    cursor -= theme.SIZE_H3 + theme.GAP_SM

    topic_breakdown = student.get("topic_breakdown", {})
    table = _build_topic_table(all_topics, topic_breakdown, width)
    cursor = _flow(c, table, x0, cursor, width, gap_after=theme.GAP_MD)

    c.setFont(theme.SANS_BOLD, theme.SIZE_H3)
    c.setFillColor(theme.CHARCOAL)
    c.drawString(x0, cursor - theme.SIZE_H3, "Topic Performance")
    cursor -= theme.SIZE_H3 + theme.GAP_SM

    chart_buf = _make_topic_chart(topic_breakdown, all_topics)
    remaining = cursor - theme.MARGIN_BOTTOM - 46  # leave room for remarks
    cursor = _place_chart(c, chart_buf, x0, cursor, width, max_h=min(200, max(90, remaining)))
    cursor -= theme.GAP_MD

    remarks = _derive_student_remarks(student, class_avg, topic_breakdown, all_topics)
    _flow(c, Paragraph(_esc(remarks), styles["muted"]), x0, cursor, width)


# --------------------------------------------------------------------------
# Certificate (page 2)
# --------------------------------------------------------------------------

def _draw_seal(c, cx, cy, r):
    """A vector seal - concentric rings, a rosette of ticks, and lettering
    that all scale with r, so a bigger seal reads as one solid medallion
    rather than a small logo lost inside an oversized ring."""
    year = datetime.date.today().year
    c.saveState()
    for i, rr in enumerate((r, r * 0.82, r * 0.66)):
        c.setStrokeColor(theme.GOLD)
        c.setLineWidth(1.4 if i == 0 else 0.7)
        c.circle(cx, cy, rr, fill=0, stroke=1)
    n = 30
    for i in range(n):
        ang = 2 * math.pi * i / n
        x1 = cx + math.cos(ang) * r * 0.66
        y1 = cy + math.sin(ang) * r * 0.66
        x2 = cx + math.cos(ang) * r * 0.57
        y2 = cy + math.sin(ang) * r * 0.57
        c.setStrokeColor(theme.GOLD)
        c.setLineWidth(0.7)
        c.line(x1, y1, x2, y2)
    c.setFillColor(theme.GOLD)
    c.setFont(theme.SERIF_BOLD, r * 0.26)
    c.drawCentredString(cx, cy + r * 0.07, "ABAKO")
    c.setFont(theme.SERIF, r * 0.19)
    c.drawCentredString(cx, cy - r * 0.24, str(year))
    c.restoreState()


def _draw_signature(c, cx, y, role):
    w = 1.9 * inch
    c.saveState()
    c.setStrokeColor(theme.SLATE)
    c.setLineWidth(0.7)
    c.line(cx - w / 2, y, cx + w / 2, y)
    c.setFont(theme.SANS, theme.SIZE_SMALL)
    c.setFillColor(theme.SLATE)
    c.drawCentredString(cx, y - 13, role)
    c.restoreState()


def _draw_certificate(c, student, school_info, demo=False):
    c.setFillColor(theme.PAPER)
    c.rect(0, 0, theme.PAGE_W, theme.PAGE_H, fill=1, stroke=0)

    outer = 0.55 * inch
    inner = outer + 9
    c.saveState()
    c.setStrokeColor(theme.GOLD)
    c.setLineWidth(1.4)
    c.rect(outer, outer, theme.PAGE_W - 2 * outer, theme.PAGE_H - 2 * outer, fill=0, stroke=1)
    c.setLineWidth(0.6)
    c.rect(inner, inner, theme.PAGE_W - 2 * inner, theme.PAGE_H - 2 * inner, fill=0, stroke=1)
    c.restoreState()

    if demo:
        _draw_demo_diagonal(c)
        _draw_demo_footer(c)

    styles = theme.styles()
    cx = theme.PAGE_W / 2
    text_w = theme.PAGE_W - 2 * inner

    percentile = student.get("percentile", 0)
    rank = student.get("rank") or 999
    achievement = percentile >= 90 or rank <= 10
    title_text = "Certificate of Achievement" if achievement else "Certificate of Participation"
    exam_date = school_info.get("Exam Date", "—")
    school = school_info.get("School Name", "—")
    grade = school_info.get("Grade", "—")
    verb = "outstanding performance in" if achievement else "participation in"
    body_text = (f"For {verb} the Abako National Math Competition, representing "
               f"{_esc(str(school))}, {_esc(str(grade))}, on {_esc(str(exam_date))}.")

    title_par = Paragraph(title_text, styles["cert_title"])
    # A tracked small-caps kicker line, sized to support the name below
    # rather than read as a stray sentence under the title above it.
    kicker_par = Paragraph(theme.letterspace("this certificate is proudly presented to"),
                          styles["cert_eyebrow"])
    name_par = Paragraph(_esc(str(student.get("name", ""))), styles["cert_name"])
    body_par = Paragraph(body_text, styles["cert_body"])

    _, title_h = title_par.wrap(text_w, theme.PAGE_H)
    _, kicker_h = kicker_par.wrap(text_w, theme.PAGE_H)
    _, name_h = name_par.wrap(text_w, theme.PAGE_H)
    _, body_h = body_par.wrap(5.2 * inch, theme.PAGE_H)

    competition_h = (theme.SIZE_SMALL + 1) * theme.LEADING
    seal_r = 0.9 * inch
    seal_gap = 0.32 * inch
    sig_gap = 0.4 * inch
    sig_text_h = 17

    # The seal is a centrepiece, not an afterthought, and sits close under
    # the citation instead of floating in a void; the signatures sit a
    # matching distance below it. The whole block is then centred as a unit
    # within the bordered frame, instead of hanging from a fixed top offset
    # and leaving the lower frame empty.
    content_h = (
        theme.LOGO_H + theme.GAP_LG + competition_h + theme.GAP_XL
        + title_h + theme.GAP_MD
        + kicker_h + theme.GAP_MD
        + name_h + 6
        + theme.GAP_LG
        + body_h
        + seal_gap + seal_r * 2
        + sig_gap + sig_text_h
    )
    frame_top = theme.PAGE_H - inner
    frame_bottom = inner
    content_top = frame_bottom + (frame_top - frame_bottom + content_h) / 2
    # A very short certificate should still look anchored under the border,
    # not simply floating dead-centre with an oversized top margin.
    content_top = min(content_top, frame_top - 0.6 * inch)

    y = content_top
    theme.draw_wordmark(c, cx - theme.LOGO_W / 2, y - theme.LOGO_H)
    y -= theme.LOGO_H + theme.GAP_LG

    c.setFont(theme.SERIF, theme.SIZE_SMALL + 1)
    c.setFillColor(theme.SLATE)
    c.drawCentredString(cx, y, "ABAKO NATIONAL MATH COMPETITION")
    y -= theme.GAP_XL

    y = _flow(c, title_par, inner, y, text_w, gap_after=theme.GAP_MD)
    y = _flow(c, kicker_par, inner, y, text_w, gap_after=theme.GAP_MD)
    y = _flow(c, name_par, inner, y, text_w, gap_after=6)

    c.setStrokeColor(theme.GOLD)
    c.setLineWidth(0.8)
    rule_w = 2.3 * inch
    c.line(cx - rule_w / 2, y, cx + rule_w / 2, y)
    y -= theme.GAP_LG

    y = _flow(c, body_par, cx - 2.6 * inch, y, 5.2 * inch, gap_after=0)

    seal_cy = y - seal_gap - seal_r
    _draw_seal(c, cx, seal_cy, seal_r)

    sig_y = seal_cy - seal_r - sig_gap
    _draw_signature(c, inner + 1.5 * inch, sig_y, "Competition Director")
    _draw_signature(c, theme.PAGE_W - inner - 1.5 * inch, sig_y, "Head of Mathematics")


# --------------------------------------------------------------------------
# School report
# --------------------------------------------------------------------------

def _aggregate_topic_breakdown(students):
    agg = {}
    for s in students:
        for topic, st in s.get("topic_breakdown", {}).items():
            a = agg.setdefault(topic, {"correct": 0, "incorrect": 0, "unattempted": 0, "total": 0})
            a["correct"] += st.get("correct", 0)
            a["incorrect"] += st.get("incorrect", 0)
            a["unattempted"] += st.get("unattempted", 0)
            a["total"] += st.get("total", 0)
    for a in agg.values():
        a["percentage"] = round(a["correct"] / a["total"] * 100, 1) if a["total"] else 0.0
    return agg


def _build_school_table(top_students):
    styles = theme.styles()
    cell, cell_r = styles["cell"], styles["cell"].clone("_scell_r", alignment=TA_RIGHT)
    head, head_r = styles["cell_head"], styles["cell_head"].clone("_shead_r", alignment=TA_RIGHT)

    fractions = [0.12, 0.46, 0.24, 0.18]
    col_w = [theme.CONTENT_W * f for f in fractions]
    header_row = [
        Paragraph(theme.letterspace("Rank"), head_r),
        Paragraph(theme.letterspace("Student"), head),
        Paragraph(theme.letterspace("Student ID"), head),
        Paragraph(theme.letterspace("Score"), head_r),
    ]
    data = [header_row]
    for s in top_students:
        data.append([
            Paragraph(str(s.get("rank", "—")), cell_r),
            Paragraph(_esc(str(s.get("name", "—"))), cell),
            Paragraph(_esc(str(s.get("student_id", "—"))), cell),
            Paragraph(f"{s.get('final_score', 0):g} / {MAX_SCORE}", cell_r),
        ])
    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(_topic_table_style(len(data)))
    return tbl


def _derive_school_summary(students, class_avg, agg, all_topics):
    n = len(students)
    sentence = (f"{n} student{'s' if n != 1 else ''} sat the exam with a class "
              f"average of {class_avg:g} / {MAX_SCORE}.")
    scored = [(t, agg[t]) for t in all_topics if t in agg and agg[t].get("total", 0) > 0]
    if scored:
        best = max(scored, key=lambda kv: kv[1]["percentage"])
        worst = min(scored, key=lambda kv: kv[1]["percentage"])
        if best[0] != worst[0]:
            sentence += (f" As a cohort, {best[0]} was the strongest topic at "
                       f"{best[1]['percentage']:g}%, and {worst[0]} the one to "
                       f"revisit, at {worst[1]['percentage']:g}%.")
    return sentence


def generate_school_report(students, school_info, all_topics, output_path, demo=False):
    _ensure_dir(output_path)
    c = pdfcanvas.Canvas(output_path, pagesize=(theme.PAGE_W, theme.PAGE_H))
    c.setFillColor(theme.PAPER)
    c.rect(0, 0, theme.PAGE_W, theme.PAGE_H, fill=1, stroke=0)

    context = " · ".join(str(school_info.get(k, "—")) for k in
                        ("School Name", "Campus", "Grade") if school_info.get(k))
    theme.draw_page_furniture(c, None, title="School Summary Report", context_line=context)
    if demo:
        _draw_demo_footer(c)

    x0 = theme.MARGIN_X
    width = theme.CONTENT_W
    cursor = theme.PAGE_H - theme.MARGIN_TOP
    styles = theme.styles()

    # An identity block, the same shape as the one on the report card - the
    # school report should name the school on its face, not only in the
    # running footer.
    school_name = str(school_info.get("School Name", "—"))
    name_style = _name_style(school_name, styles["name"])
    cursor = _flow(c, Paragraph(_esc(school_name), name_style), x0, cursor,
                  width * 0.7, gap_after=theme.GAP_SM)

    meta_items = [
        ("Campus", school_info.get("Campus", "—")),
        ("Grade", school_info.get("Grade", "—")),
        ("Exam Date", school_info.get("Exam Date", "—")),
        ("Students", str(len(students))),
    ]
    cursor = _draw_meta_row(c, x0, cursor, width, meta_items)
    cursor -= theme.GAP_MD

    if not students:
        c.setFont(theme.SANS, theme.SIZE_BODY)
        c.setFillColor(theme.SLATE)
        c.drawString(x0, cursor - 18, "No students to report.")
        c.showPage()
        c.save()
        return

    scores = [s.get("final_score", 0) for s in students]
    class_avg = round(sum(scores) / len(scores), 1)
    tiles = [
        ("Students", str(len(students)), None),
        ("Class Average", f"{class_avg:g} / {MAX_SCORE}", None),
        ("Top Score", f"{max(scores):g} / {MAX_SCORE}", theme.RED_DEEP),
        ("Median Score", f"{_median(scores):g} / {MAX_SCORE}", None),
    ]
    cursor = _draw_stat_row(c, x0, cursor, width, tiles)
    cursor -= theme.GAP_LG

    c.setFont(theme.SANS_BOLD, theme.SIZE_H3)
    c.setFillColor(theme.CHARCOAL)
    c.drawString(x0, cursor - theme.SIZE_H3, "Top 10 Performers")
    cursor -= theme.SIZE_H3 + theme.GAP_SM

    top10 = sorted(students, key=lambda s: s.get("rank", 10**9))[:10]
    cursor = _flow(c, _build_school_table(top10), x0, cursor, width, gap_after=theme.GAP_LG)

    c.setFont(theme.SANS_BOLD, theme.SIZE_H3)
    c.setFillColor(theme.CHARCOAL)
    c.drawString(x0, cursor - theme.SIZE_H3, "Aggregate Topic Performance")
    cursor -= theme.SIZE_H3 + theme.GAP_SM

    agg = _aggregate_topic_breakdown(students)
    chart_buf = _make_topic_chart(agg, all_topics)
    remaining = cursor - theme.MARGIN_BOTTOM - 30
    cursor = _place_chart(c, chart_buf, x0, cursor, width, max_h=min(230, max(90, remaining)))
    cursor -= theme.GAP_MD

    summary = _derive_school_summary(students, class_avg, agg, all_topics)
    _flow(c, Paragraph(_esc(summary), styles["muted"]), x0, cursor, width)

    c.showPage()
    c.save()


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------

def generate_individual_report(student, school_info, all_topics, class_avg, output_path, demo=False):
    _ensure_dir(output_path)
    c = pdfcanvas.Canvas(output_path, pagesize=(theme.PAGE_W, theme.PAGE_H))
    _draw_report_card(c, student, school_info, all_topics, class_avg, demo=demo)
    c.showPage()
    _draw_certificate(c, student, school_info, demo=demo)
    c.showPage()
    c.save()


def generate_all_reports(grader_result, school_info, all_topics_from_bank=None, base_dir=None, demo=False):
    if base_dir:
        sub_dir = base_dir
    else:
        competition_date = school_info.get("Exam Date", "Unknown_Date").replace("/", "-").replace("\\", "-")
        sub_dir = os.path.join("output", competition_date, "Reports")

    indiv_dir = os.path.join(sub_dir, "Individual_Reports")
    os.makedirs(sub_dir, exist_ok=True)
    os.makedirs(indiv_dir, exist_ok=True)

    students = grader_result.get("students", [])
    if not students:
        return

    tested_topics = grader_result.get("tested_topics", [])
    if all_topics_from_bank is None:
        all_topics_from_bank = tested_topics
    else:
        all_topics_from_bank = list(set(all_topics_from_bank + tested_topics))

    class_avg = round(sum(s["final_score"] for s in students) / len(students), 1)

    for s in students:
        safe_name = re.sub(r"[^\w\-]", "", s["name"].replace(" ", "_"))
        out_path = os.path.join(indiv_dir, f"{safe_name}.pdf")
        generate_individual_report(s, school_info, all_topics_from_bank, class_avg, out_path, demo=demo)

    school_out = os.path.join(sub_dir, "School_Report.pdf")
    generate_school_report(students, school_info, all_topics_from_bank, school_out, demo=demo)
