import os
import re
import io
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def create_bar_chart(topic_breakdown, all_topics):
    labels = []
    corrects = []
    incorrects = []
    unattempted = []

    for t in all_topics:
        labels.append(t)
        if t in topic_breakdown:
            stats = topic_breakdown[t]
            corrects.append(stats["correct"])
            incorrects.append(stats["incorrect"])
            unattempted.append(stats["unattempted"])
        else:
            corrects.append(0)
            incorrects.append(0)
            unattempted.append(0)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, corrects, label='Correct', color='green')
    ax.bar(labels, incorrects, bottom=corrects, label='Incorrect', color='red')

    bottom_u = [c + i for c, i in zip(corrects, incorrects)]
    ax.bar(labels, unattempted, bottom=bottom_u, label='Unattempted', color='gray')

    ax.set_ylabel('Questions')
    ax.set_title('Topic Performance')
    ax.legend()
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

def generate_individual_report(student, school_info, all_topics, class_avg, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    logo_path = os.path.join('resources', 'abako_logo.png')
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=180, height=50)
        logo_img.hAlign = 'CENTER'
        story.append(logo_img)

    story.append(Paragraph("<b>Individual Performance Report</b>", styles['Title']))
    story.append(Spacer(1, 20))

    info_text = (
        f"<b>Name:</b> {student['name']} <br/>"
        f"<b>Student ID:</b> {student['student_id']} <br/>"
        f"<b>Exam Date:</b> {school_info.get('Exam Date', 'N/A')} <br/>"
        f"<b>School:</b> {school_info.get('School Name', 'N/A')} | "
        f"<b>Campus:</b> {school_info.get('Campus', 'N/A')} | "
        f"<b>Grade:</b> {school_info.get('Grade', 'N/A')}"
    )
    story.append(Paragraph(info_text, styles['Normal']))
    story.append(Spacer(1, 30))

    story.append(Paragraph(f"<b>Final Score:</b> {student['final_score']} / 60", styles['Heading2']))
    story.append(Paragraph(f"<b>Percentile:</b> {student['percentile']}th", styles['Heading2']))

    rank_display = str(student['rank']) if student['rank'] <= 10 else "N/A"
    story.append(Paragraph(f"<b>Rank:</b> {rank_display}", styles['Heading2']))
    story.append(Paragraph(f"<b>Class Average:</b> {class_avg}", styles['Heading2']))

    story.append(PageBreak())

    story.append(Paragraph("<b>Analytics &amp; Insights</b>", styles['Title']))
    story.append(Spacer(1, 20))

    story.append(Paragraph(f"<b>Time Performance / Velocity Index:</b> {student['velocity_index']}", styles['Heading3']))
    story.append(Spacer(1, 20))

    chart_buf = create_bar_chart(student['topic_breakdown'], all_topics)
    story.append(Image(chart_buf, width=400, height=260))
    story.append(Spacer(1, 20))

    table_data = [["Topic", "Score (%)", "Correct", "Wrong", "Unattempted"]]
    for t in all_topics:
        if t in student['topic_breakdown']:
            st = student['topic_breakdown'][t]
            table_data.append([t, f"{st['percentage']}%", st['correct'], st['incorrect'], st['unattempted']])
        else:
            table_data.append([t, "N/A", "N/A", "N/A", "N/A"])

    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ])
    tbl = Table(table_data)
    tbl.setStyle(t_style)
    story.append(tbl)

    doc.build(story)

def generate_school_report(students, school_info, all_topics, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    logo_path = os.path.join('resources', 'abako_logo.png')
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=180, height=50)
        logo_img.hAlign = 'CENTER'
        story.append(logo_img)

    story.append(Paragraph("<b>School Summary Report</b>", styles['Title']))
    story.append(Spacer(1, 20))

    class_avg = round(sum(s['final_score'] for s in students) / len(students), 1) if students else 0
    story.append(Paragraph(f"<b>Class Average:</b> {class_avg} / 60", styles['Heading2']))
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Top 10 Performers</b>", styles['Heading3']))
    top_10 = sorted(students, key=lambda x: x['rank'])[:10]

    t_data = [["Rank", "Name", "Student ID", "Score"]]
    for s in top_10:
        t_data.append([s['rank'], s['name'], s['student_id'], s['final_score']])

    tbl = Table(t_data)
    tbl.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)
    ]))
    story.append(tbl)
    story.append(Spacer(1, 20))

    agg_stats = {}
    for s in students:
        for topic, st in s['topic_breakdown'].items():
            if topic not in agg_stats:
                agg_stats[topic] = {"correct": 0, "incorrect": 0, "unattempted": 0}
            agg_stats[topic]["correct"] += st["correct"]
            agg_stats[topic]["incorrect"] += st["incorrect"]
            agg_stats[topic]["unattempted"] += st["unattempted"]

    story.append(Paragraph("<b>Aggregate Topic Performance</b>", styles['Heading3']))
    chart_buf = create_bar_chart(agg_stats, all_topics)
    story.append(Image(chart_buf, width=400, height=260))

    doc.build(story)

def generate_all_reports(grader_result, school_info, all_topics_from_bank=None, base_dir=None):
    school = school_info.get("School Name", "Unknown").replace(' ', '_')
    campus = school_info.get("Campus", "Unknown").replace(' ', '_')
    grade = school_info.get("Grade", "Unknown").replace(' ', '_')

    if base_dir:
        folder_name = f"{school}_{campus}_{grade}"
        sub_dir = os.path.join(base_dir, folder_name)
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

    class_avg = round(sum(s['final_score'] for s in students) / len(students), 1)

    for s in students:
        safe_name = re.sub(r'[^\w\-]', '', s['name'].replace(' ', '_'))
        out_path = os.path.join(indiv_dir, f"{safe_name}.pdf")
        generate_individual_report(s, school_info, all_topics_from_bank, class_avg, out_path)

    school_out = os.path.join(sub_dir, "School_Report.pdf")
    generate_school_report(students, school_info, all_topics_from_bank, school_out)
