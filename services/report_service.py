import csv
import io
from datetime import datetime, timezone
from database.db import db
from models import User, Student, Faculty, Company, Internship, Evaluation
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print total page numbers: 'Page X of Y'
    along with an enterprise confidentiality footer.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor('#64748b'))
        
        # Draw footer line
        self.setStrokeColor(colors.HexColor('#e2e8f0'))
        self.setLineWidth(0.5)
        self.line(30, 30, self._pagesize[0] - 30, 30)
        
        # Left notice
        self.drawString(30, 18, "InternTrack - Placement & Internship Analytics System (Confidential)")
        
        # Right page number
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(self._pagesize[0] - 30, 18, page_text)
        self.restoreState()


class ReportService:
    @staticmethod
    def get_dashboard_metrics(course_filter=None):
        """
        Retrieves global metrics required for the reports overview.
        """
        if course_filter:
            students_q = Student.query.filter_by(course=course_filter)
            internships_q = Internship.query.join(Student, Internship.student_id == Student.id).filter(Student.course == course_filter)
            eval_q = db.session.query(db.func.avg(Evaluation.overall_score)).join(Student, Evaluation.student_id == Student.id).filter(Student.course == course_filter)
        else:
            students_q = Student.query
            internships_q = Internship.query
            eval_q = db.session.query(db.func.avg(Evaluation.overall_score))

        total_students = students_q.count()
        total_internships = internships_q.count()
        active_internships = internships_q.filter(Internship.status == 'active').count()
        completed_internships = internships_q.filter(Internship.status == 'completed').count()
        pending_internships = internships_q.filter(Internship.status == 'pending').count()
        approved_internships = internships_q.filter(Internship.status == 'approved').count()
        rejected_internships = internships_q.filter(Internship.status == 'rejected').count()

        completion_rate = 0.0
        if total_internships > 0:
            completion_rate = round((completed_internships / total_internships) * 100, 1)

        avg_eval_val = eval_q.scalar()
        avg_eval_score = round(float(avg_eval_val), 2) if avg_eval_val is not None else 0.0

        return {
            'total_students': total_students,
            'total_internships': total_internships,
            'active_internships': active_internships,
            'completed_internships': completed_internships,
            'pending_internships': pending_internships,
            'approved_internships': approved_internships,
            'rejected_internships': rejected_internships,
            'completion_rate': completion_rate,
            'avg_eval_score': avg_eval_score
        }

    # =========================================================================
    # 1. Internship Completion Report
    # =========================================================================
    @staticmethod
    def get_completion_report_data(course_filter=None, status_filter=None):
        q = Internship.query
        if course_filter:
            q = q.join(Student, Internship.student_id == Student.id).filter(Student.course == course_filter)
        if status_filter:
            q = q.filter(Internship.status == status_filter)
        internships = q.order_by(Internship.id.desc()).all()

        rows = []
        for i in internships:
            duration_str = "N/A"
            if i.start_date and i.end_date:
                days = (i.end_date - i.start_date).days
                if days >= 0:
                    duration_str = f"{days} days"

            rows.append({
                'id': i.id,
                'student_name': i.student.user.name if i.student and i.student.user else "Unknown",
                'roll_no': i.student.roll_no if i.student else "N/A",
                'course': i.student.course if i.student else "N/A",
                'company': i.company.company_name if i.company else "Unassigned",
                'role': i.role or "N/A",
                'start_date': str(i.start_date) if i.start_date else "N/A",
                'end_date': str(i.end_date) if i.end_date else "N/A",
                'duration': duration_str,
                'status': (i.status or 'pending').capitalize(),
                'is_completed': "Completed" if i.status == 'completed' else ("Active / In Progress" if i.status == 'active' else (i.status or 'pending').capitalize())
            })
        return rows

    # =========================================================================
    # 2. Student Internship Report
    # =========================================================================
    @staticmethod
    def get_student_report_data(course_filter=None):
        q = Student.query
        if course_filter:
            q = q.filter(Student.course == course_filter)
        students = q.order_by(Student.roll_no).all()

        rows = []
        for s in students:
            internships = s.internships if hasattr(s, 'internships') else []
            latest_internship = internships[-1] if len(internships) > 0 else None
            
            rows.append({
                'roll_no': s.roll_no,
                'student_name': s.user.name if s.user else "Unknown",
                'course': s.course,
                'semester': s.semester,
                'email': s.user.email if s.user else "N/A",
                'phone': s.phone or "N/A",
                'internship_count': len(internships),
                'latest_company': latest_internship.company.company_name if (latest_internship and latest_internship.company) else ("Self Placed" if latest_internship else "None"),
                'latest_role': latest_internship.role if latest_internship else "None",
                'latest_status': (latest_internship.status.capitalize() if latest_internship and latest_internship.status else "Not Registered")
            })
        return rows

    # =========================================================================
    # 3. Company Internship Report
    # =========================================================================
    @staticmethod
    def get_company_report_data():
        companies = Company.query.order_by(Company.company_name).all()
        rows = []
        for c in companies:
            internships = c.internships if hasattr(c, 'internships') else []
            active_count = sum(1 for i in internships if i.status == 'active')
            completed_count = sum(1 for i in internships if i.status == 'completed')
            
            rows.append({
                'id': c.id,
                'company_name': c.company_name,
                'contact_person': c.contact_person or "N/A",
                'email': c.email or "N/A",
                'phone': c.phone or "N/A",
                'industry': c.industry or "Technology",
                'total_placements': len(internships),
                'active_placements': active_count,
                'completed_placements': completed_count
            })
        return rows

    # =========================================================================
    # 4. Evaluation Summary Report
    # =========================================================================
    @staticmethod
    def get_evaluation_report_data(course_filter=None):
        q = Evaluation.query
        if course_filter:
            q = q.join(Student, Evaluation.student_id == Student.id).filter(Student.course == course_filter)
        evaluations = q.order_by(Evaluation.evaluated_at.desc()).all()

        rows = []
        for e in evaluations:
            rows.append({
                'id': e.id,
                'student_name': e.student.user.name if (e.student and e.student.user) else "Unknown",
                'roll_no': e.student.roll_no if e.student else "N/A",
                'course': e.student.course if e.student else "N/A",
                'faculty_name': e.faculty.user.name if (e.faculty and e.faculty.user) else "Faculty Advisor",
                'company': e.internship.company.company_name if (e.internship and e.internship.company) else "Enterprise",
                'role': e.internship.role if e.internship else "Intern",
                'technical_skills': f"{e.technical_skills}/10",
                'communication': f"{e.communication}/10",
                'punctuality': f"{e.punctuality}/10",
                'work_quality': f"{e.work_quality}/10",
                'discipline': f"{e.discipline}/10",
                'overall_score': f"{e.overall_score:.2f}/10",
                'evaluated_date': e.evaluated_at.strftime('%Y-%m-%d') if e.evaluated_at else "N/A",
                'feedback': e.feedback or "No feedback recorded"
            })
        return rows

    # =========================================================================
    # CSV Generator
    # =========================================================================
    @staticmethod
    def generate_csv(report_type, course_filter=None, status_filter=None):
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        if report_type == 'completion':
            headers = ['Internship ID', 'Student Name', 'Roll Number', 'Course', 'Company', 'Role', 'Start Date', 'End Date', 'Duration', 'Status', 'Completion Stage']
            writer.writerow(headers)
            data = ReportService.get_completion_report_data(course_filter, status_filter)
            for r in data:
                writer.writerow([
                    r['id'], r['student_name'], r['roll_no'], r['course'], r['company'],
                    r['role'], r['start_date'], r['end_date'], r['duration'], r['status'], r['is_completed']
                ])

        elif report_type == 'students':
            headers = ['Roll Number', 'Student Name', 'Course', 'Semester', 'Email', 'Phone', 'Total Placements', 'Current Company', 'Role', 'Status']
            writer.writerow(headers)
            data = ReportService.get_student_report_data(course_filter)
            for r in data:
                writer.writerow([
                    r['roll_no'], r['student_name'], r['course'], r['semester'], r['email'],
                    r['phone'], r['internship_count'], r['latest_company'], r['latest_role'], r['latest_status']
                ])

        elif report_type == 'companies':
            headers = ['Company ID', 'Company Name', 'Contact Person', 'Email', 'Phone', 'Industry', 'Total Placements', 'Active Placements', 'Completed Placements']
            writer.writerow(headers)
            data = ReportService.get_company_report_data()
            for r in data:
                writer.writerow([
                    r['id'], r['company_name'], r['contact_person'], r['email'], r['phone'],
                    r['industry'], r['total_placements'], r['active_placements'], r['completed_placements']
                ])

        elif report_type == 'evaluations':
            headers = ['Evaluation ID', 'Student Name', 'Roll Number', 'Course', 'Faculty Evaluator', 'Company', 'Role', 'Technical', 'Communication', 'Punctuality', 'Work Quality', 'Discipline', 'Overall Score', 'Date', 'Feedback']
            writer.writerow(headers)
            data = ReportService.get_evaluation_report_data(course_filter)
            for r in data:
                writer.writerow([
                    r['id'], r['student_name'], r['roll_no'], r['course'], r['faculty_name'],
                    r['company'], r['role'], r['technical_skills'], r['communication'], r['punctuality'],
                    r['work_quality'], r['discipline'], r['overall_score'], r['evaluated_date'], r['feedback']
                ])
        else:
            writer.writerow(['Error', 'Unknown report type'])

        # Return UTF-8 encoded bytes with BOM for Excel compatibility
        csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
        return csv_bytes

    # =========================================================================
    # PDF Generator (ReportLab)
    # =========================================================================
    @staticmethod
    def generate_pdf(report_type, course_filter=None, status_filter=None):
        buf = io.BytesIO()
        
        # Use landscape for wide data tables
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            leftMargin=25,
            rightMargin=25,
            topMargin=25,
            bottomMargin=40
        )
        
        styles = getSampleStyleSheet()
        
        # Custom Typography Styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#0F172A')
        )
        
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#64748B')
        )
        
        meta_style = ParagraphStyle(
            'ReportMeta',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#475569')
        )

        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white
        )

        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#1E293B')
        )
        
        cell_bold_style = ParagraphStyle(
            'TableCellBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#0F172A')
        )

        cell_muted_style = ParagraphStyle(
            'TableCellMuted',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor('#64748B')
        )

        story = []

        # Titles and report configurations
        timestamp_str = datetime.now(timezone.utc).strftime('%B %d, %Y - %H:%M UTC')
        report_names = {
            'completion': ('Internship Completion & Fulfillment Report', 'Comprehensive audit of placement durations, lifecycle statuses, and student milestones.'),
            'students': ('Student Placement Registry & Roster Report', 'Comprehensive directory of enrolled students, contact info, and active placement assignments.'),
            'companies': ('Corporate Partner Engagement & Volume Report', 'Corporate affiliate listings, point-of-contact information, and student intake analytics.'),
            'evaluations': ('Faculty Evaluation & Performance Summary Report', 'Academic rubric appraisals, individual competency scores, and faculty feedback remarks.')
        }

        title_text, subtitle_text = report_names.get(report_type, ('System Report', 'Generated placement report.'))

        # 1. Header Banner Table
        header_data = [
            [
                Paragraph(f"<b>InternTrack</b> &bull; Placement Administration", meta_style),
                Paragraph(f"Generated: <b>{timestamp_str}</b>", ParagraphStyle('RightMeta', parent=meta_style, alignment=2))
            ],
            [
                Paragraph(title_text, title_style),
                Paragraph(f"Scope: <b>{course_filter or 'All Courses'}</b>", ParagraphStyle('RightScope', parent=meta_style, alignment=2))
            ],
            [
                Paragraph(subtitle_text, subtitle_style),
                Paragraph("Status: <b>Verified Database Record</b>", ParagraphStyle('RightVer', parent=meta_style, alignment=2))
            ]
        ]
        header_table = Table(header_data, colWidths=[520, 260])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceAfter=12))

        # 2. Build Report Specific Tables and Data
        if report_type == 'completion':
            data_rows = ReportService.get_completion_report_data(course_filter, status_filter)
            total_count = len(data_rows)
            completed_count = sum(1 for r in data_rows if r['status'] == 'Completed')
            comp_rate = round((completed_count / total_count * 100), 1) if total_count > 0 else 0.0

            # KPI Summary Bar
            kpi_data = [[
                Paragraph(f"Total Placements: <b>{total_count}</b>", cell_style),
                Paragraph(f"Completed: <b>{completed_count}</b>", cell_style),
                Paragraph(f"In Progress / Active: <b>{sum(1 for r in data_rows if r['status'] == 'Active')}</b>", cell_style),
                Paragraph(f"Pending Approval: <b>{sum(1 for r in data_rows if r['status'] == 'Pending')}</b>", cell_style),
                Paragraph(f"Completion Rate: <b>{comp_rate}%</b>", cell_bold_style),
            ]]
            kpi_table = Table(kpi_data, colWidths=[150, 140, 170, 160, 160])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('PADDING', (0,0), (-1,-1), 6),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 12))

            # Main Table
            table_headers = ['ID', 'Student Name', 'Roll No', 'Course', 'Company', 'Role', 'Dates (Start / End)', 'Duration', 'Status']
            col_widths = [35, 120, 65, 80, 130, 120, 115, 60, 65]
            
            table_content = [[Paragraph(h, table_header_style) for h in table_headers]]
            for r in data_rows:
                table_content.append([
                    Paragraph(f"#{r['id']}", cell_muted_style),
                    Paragraph(r['student_name'], cell_bold_style),
                    Paragraph(r['roll_no'], cell_style),
                    Paragraph(r['course'], cell_style),
                    Paragraph(r['company'], cell_style),
                    Paragraph(r['role'], cell_style),
                    Paragraph(f"{r['start_date']} &rarr; {r['end_date']}", cell_muted_style),
                    Paragraph(r['duration'], cell_style),
                    Paragraph(r['status'], cell_bold_style if r['status'] == 'Completed' else cell_style),
                ])

        elif report_type == 'students':
            data_rows = ReportService.get_student_report_data(course_filter)
            total_students = len(data_rows)
            placed_students = sum(1 for r in data_rows if r['internship_count'] > 0)
            
            kpi_data = [[
                Paragraph(f"Total Enrolled Students: <b>{total_students}</b>", cell_style),
                Paragraph(f"Registered in Placements: <b>{placed_students}</b>", cell_style),
                Paragraph(f"Placement Participation: <b>{round(placed_students / total_students * 100, 1) if total_students > 0 else 0}%</b>", cell_bold_style),
            ]]
            kpi_table = Table(kpi_data, colWidths=[260, 260, 260])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 12))

            table_headers = ['Roll No', 'Student Name', 'Course', 'Sem', 'Email', 'Phone', 'Placements', 'Assigned Enterprise', 'Role', 'Status']
            col_widths = [65, 115, 80, 35, 130, 80, 55, 105, 75, 50]
            
            table_content = [[Paragraph(h, table_header_style) for h in table_headers]]
            for r in data_rows:
                table_content.append([
                    Paragraph(r['roll_no'], cell_bold_style),
                    Paragraph(r['student_name'], cell_style),
                    Paragraph(r['course'], cell_style),
                    Paragraph(str(r['semester']), cell_style),
                    Paragraph(r['email'], cell_muted_style),
                    Paragraph(r['phone'], cell_muted_style),
                    Paragraph(str(r['internship_count']), cell_style),
                    Paragraph(r['latest_company'], cell_style),
                    Paragraph(r['latest_role'], cell_style),
                    Paragraph(r['latest_status'], cell_bold_style if r['latest_status'] == 'Completed' else cell_style),
                ])

        elif report_type == 'companies':
            data_rows = ReportService.get_company_report_data()
            total_companies = len(data_rows)
            total_hosted = sum(r['total_placements'] for r in data_rows)

            kpi_data = [[
                Paragraph(f"Corporate Partners: <b>{total_companies}</b>", cell_style),
                Paragraph(f"Total Internships Hosted: <b>{total_hosted}</b>", cell_style),
                Paragraph(f"Active Placements: <b>{sum(r['active_placements'] for r in data_rows)}</b>", cell_style),
                Paragraph(f"Completed Placements: <b>{sum(r['completed_placements'] for r in data_rows)}</b>", cell_bold_style),
            ]]
            kpi_table = Table(kpi_data, colWidths=[195, 195, 195, 195])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 12))

            table_headers = ['ID', 'Company Name', 'Contact Person', 'Email', 'Phone', 'Industry', 'Total Hosted', 'Active', 'Completed']
            col_widths = [35, 160, 110, 130, 85, 95, 65, 50, 50]
            
            table_content = [[Paragraph(h, table_header_style) for h in table_headers]]
            for r in data_rows:
                table_content.append([
                    Paragraph(f"#{r['id']}", cell_muted_style),
                    Paragraph(r['company_name'], cell_bold_style),
                    Paragraph(r['contact_person'], cell_style),
                    Paragraph(r['email'], cell_muted_style),
                    Paragraph(r['phone'], cell_muted_style),
                    Paragraph(r['industry'], cell_style),
                    Paragraph(str(r['total_placements']), cell_bold_style),
                    Paragraph(str(r['active_placements']), cell_style),
                    Paragraph(str(r['completed_placements']), cell_style),
                ])

        elif report_type == 'evaluations':
            data_rows = ReportService.get_evaluation_report_data(course_filter)
            total_evals = len(data_rows)
            scores = [float(r['overall_score'].replace('/10', '')) for r in data_rows if '/10' in r['overall_score']]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

            kpi_data = [[
                Paragraph(f"Evaluations Recorded: <b>{total_evals}</b>", cell_style),
                Paragraph(f"Average Evaluation Score: <b>{avg_score} / 10</b>", cell_bold_style),
                Paragraph(f"Score Range: <b>{min(scores) if scores else 0.0} - {max(scores) if scores else 0.0}</b>", cell_style),
            ]]
            kpi_table = Table(kpi_data, colWidths=[260, 260, 260])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 12))

            table_headers = ['ID', 'Student Name', 'Roll No', 'Faculty Evaluator', 'Company / Role', 'Tech', 'Comm', 'Punct', 'Qual', 'Disc', 'Overall', 'Date']
            col_widths = [30, 115, 60, 110, 130, 38, 38, 38, 38, 38, 55, 60]
            
            table_content = [[Paragraph(h, table_header_style) for h in table_headers]]
            for r in data_rows:
                table_content.append([
                    Paragraph(f"#{r['id']}", cell_muted_style),
                    Paragraph(r['student_name'], cell_bold_style),
                    Paragraph(r['roll_no'], cell_style),
                    Paragraph(r['faculty_name'], cell_style),
                    Paragraph(f"{r['company']}<br/><font color='#64748b'>{r['role']}</font>", cell_muted_style),
                    Paragraph(r['technical_skills'], cell_style),
                    Paragraph(r['communication'], cell_style),
                    Paragraph(r['punctuality'], cell_style),
                    Paragraph(r['work_quality'], cell_style),
                    Paragraph(r['discipline'], cell_style),
                    Paragraph(f"<b>{r['overall_score']}</b>", cell_bold_style),
                    Paragraph(r['evaluated_date'], cell_muted_style),
                ])
        else:
            table_content = [[Paragraph("Error", table_header_style)], [Paragraph("Invalid report type", cell_style)]]
            col_widths = [780]

        # Style the main table
        report_table = Table(table_content, colWidths=col_widths, repeatRows=1)
        report_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8FAFC')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(report_table)

        doc.build(story, canvasmaker=NumberedCanvas)
        return buf.getvalue()
