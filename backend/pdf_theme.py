"""Shared visual language for every PDF the suite produces.

Everything printable in Abako - the question paper, the answer key, the
individual report card and the school summary - pulls its colours, type scale,
spacing and page furniture from here, so the whole pack looks like one set of
documents instead of four unrelated ones.

The palette is taken from the Abako wordmark: charcoal #363434 and red #EB3238.
Red is a signal colour, not a decoration - it marks the one number that matters
on a page and nothing else. Gold appears only on the certificate.

Only the PDF base-14 fonts are used (Helvetica for the report body, Times for
the certificate), so nothing here depends on a font file being installed or
shipped in the PyInstaller bundle.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

INK = colors.HexColor("#1A1A1C")       # body text
CHARCOAL = colors.HexColor("#363434")  # brand charcoal, headings and rules
SLATE = colors.HexColor("#5C6068")     # secondary text, labels
MIST = colors.HexColor("#8A9099")      # tertiary text, footers

RED = colors.HexColor("#EB3238")       # brand red, signal only
RED_DEEP = colors.HexColor("#B3252A")  # red that still reads as text on white
GOLD = colors.HexColor("#A8842C")      # certificate rules and seal
GOLD_PALE = colors.HexColor("#F1E7CC")

RULE = colors.HexColor("#D8DADF")      # hairlines
RULE_STRONG = colors.HexColor("#B4B8BF")
PANEL = colors.HexColor("#F4F5F7")     # light fill behind stat blocks
PANEL_DEEP = colors.HexColor("#E9EBEF")
PAPER = colors.white

# Performance semantics, reused by charts and tables alike.
CORRECT = colors.HexColor("#2F7D63")
INCORRECT = colors.HexColor("#EB3238")
UNATTEMPTED = colors.HexColor("#B9BDC6")

# Matplotlib needs plain hex strings.
CHART_CORRECT = "#2F7D63"
CHART_INCORRECT = "#EB3238"
CHART_UNATTEMPTED = "#B9BDC6"
CHART_GRID = "#D8DADF"
CHART_TEXT = "#5C6068"
CHART_INK = "#1A1A1C"

# --------------------------------------------------------------------------
# Type
# --------------------------------------------------------------------------

SANS = "Helvetica"
SANS_BOLD = "Helvetica-Bold"
SANS_OBLIQUE = "Helvetica-Oblique"
SERIF = "Times-Roman"
SERIF_BOLD = "Times-Bold"
SERIF_ITALIC = "Times-Italic"

# One scale, used everywhere. Sizes are points.
SIZE_DISPLAY = 34
SIZE_H1 = 19
SIZE_H2 = 13
SIZE_H3 = 10.5
SIZE_BODY = 9.5
SIZE_SMALL = 8
SIZE_MICRO = 7

LEADING = 1.38  # multiply a size by this for its leading

# --------------------------------------------------------------------------
# Page geometry
# --------------------------------------------------------------------------

PAGE_W, PAGE_H = letter
MARGIN_X = 0.62 * inch
MARGIN_TOP = 1.05 * inch
MARGIN_BOTTOM = 0.72 * inch
CONTENT_W = PAGE_W - 2 * MARGIN_X

LOGO_W = 108
LOGO_H = 35

# Vertical rhythm. Use these instead of ad-hoc Spacer values.
GAP_XS = 4
GAP_SM = 8
GAP_MD = 14
GAP_LG = 22
GAP_XL = 34


def styles():
    """Return the shared paragraph styles, keyed by role."""
    def _s(name, **kw):
        kw.setdefault("fontName", SANS)
        kw.setdefault("fontSize", SIZE_BODY)
        kw.setdefault("leading", round(kw["fontSize"] * LEADING, 1))
        kw.setdefault("textColor", INK)
        return ParagraphStyle(name, **kw)

    return {
        # Big centred number or name, e.g. the score on the report card.
        "display": _s("display", fontName=SANS_BOLD, fontSize=SIZE_DISPLAY,
                      leading=SIZE_DISPLAY * 1.05, alignment=TA_CENTER,
                      textColor=CHARCOAL),
        # Page title.
        "h1": _s("h1", fontName=SANS_BOLD, fontSize=SIZE_H1, textColor=CHARCOAL,
                 spaceAfter=GAP_XS),
        # Section heading.
        "h2": _s("h2", fontName=SANS_BOLD, fontSize=SIZE_H2, textColor=CHARCOAL,
                 spaceBefore=GAP_MD, spaceAfter=GAP_SM),
        # Sub-heading inside a section.
        "h3": _s("h3", fontName=SANS_BOLD, fontSize=SIZE_H3, textColor=CHARCOAL,
                 spaceAfter=GAP_XS),
        # All-caps label above a value.
        "eyebrow": _s("eyebrow", fontName=SANS_BOLD, fontSize=SIZE_MICRO,
                      textColor=MIST, spaceAfter=2),
        "body": _s("body"),
        "body_center": _s("body_center", alignment=TA_CENTER),
        "muted": _s("muted", fontSize=SIZE_SMALL, textColor=SLATE),
        "muted_center": _s("muted_center", fontSize=SIZE_SMALL, textColor=SLATE,
                           alignment=TA_CENTER),
        "small_right": _s("small_right", fontSize=SIZE_SMALL, textColor=SLATE,
                          alignment=TA_RIGHT),
        "footnote": _s("footnote", fontSize=SIZE_MICRO, textColor=MIST),
        # Table cells.
        "cell": _s("cell", fontSize=SIZE_SMALL, leading=SIZE_SMALL * 1.3),
        "cell_head": _s("cell_head", fontName=SANS_BOLD, fontSize=SIZE_MICRO,
                        leading=SIZE_MICRO * 1.3, textColor=PAPER),
        # Certificate.
        "cert_title": _s("cert_title", fontName=SERIF_BOLD, fontSize=26,
                         leading=30, alignment=TA_CENTER, textColor=CHARCOAL),
        "cert_name": _s("cert_name", fontName=SERIF_BOLD, fontSize=24,
                        leading=28, alignment=TA_CENTER, textColor=CHARCOAL),
        "cert_body": _s("cert_body", fontName=SERIF, fontSize=11.5, leading=17,
                        alignment=TA_CENTER, textColor=INK),
        "cert_eyebrow": _s("cert_eyebrow", fontName=SERIF, fontSize=SIZE_SMALL,
                           alignment=TA_CENTER, textColor=SLATE),
        # Question paper.
        "question": _s("question", fontSize=SIZE_BODY, leading=SIZE_BODY * 1.45,
                       alignment=TA_LEFT, spaceAfter=GAP_SM),
    }


def letterspace(text):
    """Space out `text` with hair spaces.

    Small all-caps eyebrow labels look cramped without a little tracking, and
    ReportLab's inline markup has no letter-spacing attribute.
    """
    return "&#8202;".join(text.upper())


def draw_wordmark(canvas, x, y, width=LOGO_W, height=LOGO_H, logo_path=None):
    """Draw the Abako wordmark, or a typographic fallback if the file is gone."""
    import os

    if logo_path is None:
        logo_path = os.path.join("resources", "abako_logo.png")
    if os.path.exists(logo_path):
        canvas.drawImage(logo_path, x, y, width=width, height=height,
                         preserveAspectRatio=True, anchor="sw", mask="auto")
    else:
        canvas.saveState()
        canvas.setFont(SANS_BOLD, 15)
        canvas.setFillColor(CHARCOAL)
        canvas.drawString(x, y + height / 2 - 5, "ABAKO")
        canvas.restoreState()


def draw_rule(canvas, x1, y, x2, color=RULE, width=0.6):
    canvas.saveState()
    canvas.setStrokeColor(color)
    canvas.setLineWidth(width)
    canvas.line(x1, y, x2, y)
    canvas.restoreState()


def draw_page_furniture(canvas, doc, title, context_line, footer_note=None,
                        show_page_number=True):
    """Standard header and footer for a content page.

    Header: wordmark left, document title right, hairline under both.
    Footer: context line left, page number right.
    """
    canvas.saveState()

    top = PAGE_H - 0.46 * inch
    draw_wordmark(canvas, MARGIN_X, top - LOGO_H)

    canvas.setFont(SANS_BOLD, SIZE_SMALL)
    canvas.setFillColor(SLATE)
    canvas.drawRightString(PAGE_W - MARGIN_X, top - 12, title.upper())

    rule_y = top - LOGO_H - 9
    draw_rule(canvas, MARGIN_X, rule_y, PAGE_W - MARGIN_X, RULE_STRONG, 0.8)

    canvas.setFont(SANS, SIZE_MICRO)
    canvas.setFillColor(MIST)
    if context_line:
        canvas.drawString(MARGIN_X, 0.46 * inch, context_line)
    if show_page_number:
        canvas.drawRightString(PAGE_W - MARGIN_X, 0.46 * inch,
                               f"Page {canvas.getPageNumber()}")
    if footer_note:
        canvas.drawCentredString(PAGE_W / 2, 0.46 * inch, footer_note)

    canvas.restoreState()


def apply_chart_style(ax, fig):
    """Strip a matplotlib axes down to the house style: no box, soft y-grid."""
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(CHART_GRID)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.yaxis.grid(True, color=CHART_GRID, linewidth=0.6, zorder=0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(colors=CHART_TEXT, labelsize=7.5, length=0)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(CHART_TEXT)
