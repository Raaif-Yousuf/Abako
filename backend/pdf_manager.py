import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, SimpleDocTemplate, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

_LOGO_W = 180
_LOGO_H = 50

def _draw_header_footer(canvas, doc, school_info):
    canvas.saveState()
    page_w = letter[0]
    logo_x = (page_w - _LOGO_W) / 2
    logo_y = letter[1] - 0.4*inch - _LOGO_H  # 0.4 inch clearance above logo

    logo_path = os.path.join('resources', 'abako_logo.png')
    if os.path.exists(logo_path):
        canvas.drawImage(logo_path, logo_x, logo_y, width=_LOGO_W, height=_LOGO_H, preserveAspectRatio=True)
    else:
        canvas.setFont('Helvetica-Bold', 14)
        canvas.drawCentredString(page_w / 2, logo_y + _LOGO_H / 2, "LOGO")

    canvas.setFont('Helvetica', 9)
    info_parts = [
        f"School: {school_info.get('School Name', 'Mock School')}",
        f"Campus: {school_info.get('Campus', 'Main')}",
        f"Grade: {school_info.get('Grade', '10')}",
        f"Date: {school_info.get('Exam Date', '2026-05-05')}"
    ]
    canvas.drawCentredString(page_w / 2, logo_y - 14, " | ".join(info_parts))

    canvas.setFont('Helvetica-Oblique', 10)
    footer_text = "I hereby confirm I have adhered to the honor code: _________________________"
    canvas.drawCentredString(letter[0]/2.0, 0.5*inch, footer_text)

    canvas.restoreState()

def generate_question_paper(filename, school_info, questions):
    os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)

    doc = BaseDocTemplate(filename, pagesize=letter, topMargin=2.0*inch, bottomMargin=1.0*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)

    def on_page(canvas, doc):
        _draw_header_footer(canvas, doc, school_info)

    col_width = (letter[0] - 1.5*inch) / 2
    frame1 = Frame(0.5*inch, 1.0*inch, col_width, letter[1] - 3.0*inch, id='col1')
    frame2 = Frame(0.5*inch + col_width + 0.5*inch, 1.0*inch, col_width, letter[1] - 3.0*inch, id='col2')

    template = PageTemplate(id='TwoCol', frames=[frame1, frame2], onPage=on_page)
    doc.addPageTemplates([template])

    styles = getSampleStyleSheet()
    styleN = ParagraphStyle(
        'NormalQuestion',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        spaceAfter=12
    )

    story = []
    for i, q in enumerate(questions):
        q_text = q.get('Question_Text', f'Question {i+1}')
        text = f"<b>{i+1}.</b> {q_text}<br/><br/>Answer: ___________________________"
        story.append(Paragraph(text, styleN))

    doc.build(story)

def generate_answer_key(filename, questions, school_name='', campus_name='', grade='', exam_date=''):
    os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)

    doc = SimpleDocTemplate(filename, pagesize=letter, topMargin=1*inch, bottomMargin=1*inch)
    styles = getSampleStyleSheet()

    story = []

    logo_path = os.path.join('resources', 'abako_logo.png')
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=_LOGO_W, height=_LOGO_H)
        logo_img.hAlign = 'CENTER'
        story.append(logo_img)
    story.append(Spacer(1, 8))

    header_style = ParagraphStyle('AKHeader', parent=styles['Normal'], alignment=1, fontSize=10, spaceAfter=6)
    header_text = f"School: {school_name} | Campus: {campus_name} | Grade: {grade} | Date: {exam_date}"
    story.append(Paragraph(header_text, header_style))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("<b>Answer Key</b>", styles['Title']))
    story.append(Spacer(1, 0.2*inch))

    styleN = ParagraphStyle('AKNormal', parent=styles['Normal'], fontName='Helvetica', fontSize=12)
    for i, q in enumerate(questions):
        ans = q.get('Correct_Answer', '')
        story.append(Paragraph(f"{i+1}. {ans}", styleN))

    doc.build(story)
