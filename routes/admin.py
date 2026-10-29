from flask import Blueprint, render_template, redirect, url_for, flash, request, session, abort, Response, current_app
from routes.decorators import role_required
from database.db import db
from models import User, Student, Faculty, Company, Internship, TimelineEvent, Document, Deadline, Notification, ProgressReport, Evaluation
from routes.student import generate_timeline_events, generate_deadlines
from services.report_service import ReportService
from datetime import datetime, date, timezone
from werkzeug.security import generate_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    """
    Renders the admin dashboard with real database statistics and Chart.js analytics.
    """
    from collections import defaultdict

    course_filter = request.args.get('course', '').strip()
    
    # Available courses for filter dropdown
    available_courses = [
        c[0] for c in db.session.query(Student.course)
        .distinct()
        .filter(Student.course.isnot(None), Student.course != '')
        .order_by(Student.course)
        .all()
    ]
    
    # Base queries depending on course filter
    if course_filter:
        internships_q = Internship.query.join(Student, Internship.student_id == Student.id).filter(Student.course == course_filter)
        students_q = Student.query.filter(Student.course == course_filter)
    else:
        internships_q = Internship.query
        students_q = Student.query

    # Primary counts
    total_students = students_q.count()
    total_internships = internships_q.count()
    pending_approvals = internships_q.filter(Internship.status == 'pending').count()
    approved_internships = internships_q.filter(Internship.status == 'approved').count()
    active_internships = internships_q.filter(Internship.status == 'active').count()
    completed_internships = internships_q.filter(Internship.status == 'completed').count()
    rejected_internships = internships_q.filter(Internship.status == 'rejected').count()
    not_completed_internships = total_internships - completed_internships

    completion_rate = 0.0
    if total_internships > 0:
        completion_rate = round((completed_internships / total_internships) * 100, 1)

    # 1. Status Chart Data
    status_labels = ['Pending', 'Approved', 'Active', 'Completed', 'Rejected']
    status_data = [
        pending_approvals,
        approved_internships,
        active_internships,
        completed_internships,
        rejected_internships
    ]

    # 2. Company Chart Data
    if course_filter:
        company_query = (
            db.session.query(
                db.func.coalesce(Company.company_name, 'Unassigned').label('name'),
                db.func.count(Internship.id).label('count')
            )
            .outerjoin(Company, Internship.company_id == Company.id)
            .join(Student, Internship.student_id == Student.id)
            .filter(Student.course == course_filter)
            .group_by(Company.company_name)
            .order_by(db.func.count(Internship.id).desc())
            .all()
        )
    else:
        company_query = (
            db.session.query(
                db.func.coalesce(Company.company_name, 'Unassigned').label('name'),
                db.func.count(Internship.id).label('count')
            )
            .outerjoin(Company, Internship.company_id == Company.id)
            .group_by(Company.company_name)
            .order_by(db.func.count(Internship.id).desc())
            .all()
        )

    company_labels = [row[0] for row in company_query]
    company_data = [row[1] for row in company_query]

    # Most popular companies (top 3)
    most_popular_companies = [
        {"name": row[0], "count": row[1]}
        for row in company_query
        if row[0] != 'Unassigned' and row[1] > 0
    ][:3]

    # 3. Monthly Registration Trends
    internship_dates = internships_q.with_entities(Internship.created_at).all()
    monthly_counts = defaultdict(int)
    for (dt,) in internship_dates:
        if dt:
            month_key = dt.strftime('%Y-%m')
            monthly_counts[month_key] += 1

    if monthly_counts:
        sorted_months = sorted(monthly_counts.keys())
        monthly_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in sorted_months]
        monthly_data = [monthly_counts[m] for m in sorted_months]
    else:
        monthly_labels = []
        monthly_data = []

    # 4. Completion Rate Chart Data
    completion_labels = ['Completed', 'Not Completed']
    completion_data = [completed_internships, not_completed_internships]

    # Additional Useful Metric: Average Internship Duration (in days and weeks)
    date_pairs = internships_q.with_entities(Internship.start_date, Internship.end_date).filter(
        Internship.start_date.isnot(None),
        Internship.end_date.isnot(None)
    ).all()
    durations = [(end - start).days for start, end in date_pairs if end and start and (end - start).days >= 0]
    if durations:
        avg_duration_days = round(sum(durations) / len(durations), 1)
        avg_duration_weeks = round(avg_duration_days / 7, 1)
    else:
        avg_duration_days = 0.0
        avg_duration_weeks = 0.0

    # Additional Useful Metric: Average Evaluation Score
    eval_query = db.session.query(db.func.avg(Evaluation.overall_score))
    if course_filter:
        eval_query = eval_query.join(Student, Evaluation.student_id == Student.id).filter(Student.course == course_filter)
    avg_eval_val = eval_query.scalar()
    avg_evaluation_score = round(float(avg_eval_val), 2) if avg_eval_val is not None else None

    # Consolidated chart data for clean JSON serialization
    chart_payload = {
        'status': {
            'labels': status_labels,
            'data': status_data
        },
        'company': {
            'labels': company_labels,
            'data': company_data
        },
        'monthly': {
            'labels': monthly_labels,
            'data': monthly_data
        },
        'completion': {
            'labels': completion_labels,
            'data': completion_data
        }
    }

    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        total_internships=total_internships,
        active_internships=active_internships,
        completed_internships=completed_internships,
        pending_approvals=pending_approvals,
        approved_internships=approved_internships,
        rejected_internships=rejected_internships,
        not_completed_internships=not_completed_internships,
        completion_rate=completion_rate,
        avg_duration_days=avg_duration_days,
        avg_duration_weeks=avg_duration_weeks,
        avg_evaluation_score=avg_evaluation_score,
        most_popular_companies=most_popular_companies,
        available_courses=available_courses,
        selected_course=course_filter,
        chart_data=chart_payload
    )

@admin_bp.route('/students')
@role_required('admin')
def list_students():
    """
    Lists students with search and filter capabilities.
    """
    search_query = request.args.get('search', '').strip()
    course_filter = request.args.get('course', '').strip()
    semester_filter = request.args.get('semester', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    query = Student.query.join(User)
    
    if search_query:
        query = query.filter(
            (User.name.like(f"%{search_query}%")) |
            (Student.roll_no.like(f"%{search_query}%")) |
            (Student.course.like(f"%{search_query}%"))
        )
        
    if course_filter:
        query = query.filter(Student.course == course_filter)
        
    if semester_filter:
        try:
            query = query.filter(Student.semester == int(semester_filter))
        except ValueError:
            pass
            
    if status_filter:
        is_active_val = True if status_filter == 'active' else False
        query = query.filter(User.is_active == is_active_val)
        
    students = query.all()
    
    # Extract unique courses for filtering dropdown
    all_courses = [c[0] for c in db.session.query(Student.course).distinct().all() if c[0]]
    
    return render_template(
        'admin/students.html',
        students=students,
        search_query=search_query,
        course_filter=course_filter,
        semester_filter=semester_filter,
        status_filter=status_filter,
        all_courses=all_courses
    )

@admin_bp.route('/students/add', methods=['GET', 'POST'])
@role_required('admin')
def add_student():
    """
    Allows admin to register a new student.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        roll_no = request.form.get('roll_no', '').strip()
        course = request.form.get('course', '').strip()
        semester_str = request.form.get('semester', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not all([name, email, password, roll_no, course, semester_str]):
            flash('All student fields are required.', 'danger')
            return render_template('admin/student_form.html', student=None, action='Add')
            
        try:
            semester = int(semester_str)
        except ValueError:
            flash('Semester must be an integer.', 'danger')
            return render_template('admin/student_form.html', student=None, action='Add')
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('admin/student_form.html', student=None, action='Add')
            
        if Student.query.filter_by(roll_no=roll_no).first():
            flash('Roll number already registered.', 'danger')
            return render_template('admin/student_form.html', student=None, action='Add')
            
        try:
            new_user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role='student',
                is_active=True
            )
            db.session.add(new_user)
            db.session.flush()
            
            new_student = Student(
                user_id=new_user.id,
                roll_no=roll_no,
                course=course,
                semester=semester,
                phone=phone if phone else None
            )
            db.session.add(new_student)
            db.session.commit()
            
            flash(f'Student {name} registered successfully.', 'success')
            return redirect(url_for('admin.list_students'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error("Admin registration of student failed for email=%s, roll_no=%s: %s: %s", email, roll_no, type(e).__name__, e, exc_info=True)
            flash('An error occurred during registration.', 'danger')
            
    return render_template('admin/student_form.html', student=None, action='Add')

@admin_bp.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
@role_required('admin')
def edit_student(student_id):
    """
    Allows admin to edit an existing student.
    """
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        roll_no = request.form.get('roll_no', '').strip()
        course = request.form.get('course', '').strip()
        semester_str = request.form.get('semester', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not all([name, email, roll_no, course, semester_str]):
            flash('All student fields are required.', 'danger')
            return render_template('admin/student_form.html', student=student, action='Edit')
            
        try:
            semester = int(semester_str)
        except ValueError:
            flash('Semester must be an integer.', 'danger')
            return render_template('admin/student_form.html', student=student, action='Edit')
            
        # Email uniqueness
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != student.user_id:
            flash('Email already registered by another user.', 'danger')
            return render_template('admin/student_form.html', student=student, action='Edit')
            
        # Roll uniqueness
        existing_student = Student.query.filter_by(roll_no=roll_no).first()
        if existing_student and existing_student.id != student.id:
            flash('Roll number already registered by another student.', 'danger')
            return render_template('admin/student_form.html', student=student, action='Edit')
            
        try:
            student.user.name = name
            student.user.email = email
            student.roll_no = roll_no
            student.course = course
            student.semester = semester
            student.phone = phone if phone else None
            
            db.session.commit()
            flash(f'Student {name} updated successfully.', 'success')
            return redirect(url_for('admin.list_students'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while updating the student.', 'danger')
            
    return render_template('admin/student_form.html', student=student, action='Edit')

@admin_bp.route('/students/toggle-status/<int:student_id>', methods=['POST'])
@role_required('admin')
def toggle_student_status(student_id):
    """
    Activates or deactivates a student's login privileges.
    """
    student = Student.query.get_or_404(student_id)
    student.user.is_active = not student.user.is_active
    db.session.commit()
    
    status_str = "activated" if student.user.is_active else "deactivated"
    flash(f"Student account for {student.user.name} has been {status_str}.", 'success')
    return redirect(url_for('admin.list_students'))

@admin_bp.route('/students/delete/<int:student_id>', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    """
    Deletes a student user account, cascade-clearing associated student/internships data.
    """
    student = Student.query.get_or_404(student_id)
    user = student.user
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"Student {user.name} and all related records deleted.", 'success')
    except Exception:
        db.session.rollback()
        flash("An error occurred during deletion.", 'danger')
        
    return redirect(url_for('admin.list_students'))

@admin_bp.route('/internships')
@role_required('admin')
def list_internships():
    """
    Lists internships with comprehensive filters.
    """
    search_query = request.args.get('search', '').strip()
    company_filter = request.args.get('company_id', '').strip()
    status_filter = request.args.get('status', '').strip()
    course_filter = request.args.get('course', '').strip()
    start_date_filter = request.args.get('start_date', '').strip()
    end_date_filter = request.args.get('end_date', '').strip()
    
    query = Internship.query.join(Student).join(User)
    
    if search_query:
        query = query.join(Company, Internship.company_id == Company.id, isouter=True).filter(
            (User.name.like(f"%{search_query}%")) |
            (Company.company_name.like(f"%{search_query}%")) |
            (Internship.role.like(f"%{search_query}%"))
        )
        
    if company_filter:
        try:
            query = query.filter(Internship.company_id == int(company_filter))
        except ValueError:
            pass
            
    if status_filter:
        query = query.filter(Internship.status == status_filter)
        
    if course_filter:
        query = query.filter(Student.course == course_filter)
        
    if start_date_filter:
        try:
            start_date_val = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
            query = query.filter(Internship.start_date >= start_date_val)
        except ValueError:
            pass
            
    if end_date_filter:
        try:
            end_date_val = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
            query = query.filter(Internship.end_date <= end_date_val)
        except ValueError:
            pass
            
    internships = query.all()
    
    # Data for filtering panels
    companies = Company.query.order_by(Company.company_name).all()
    all_courses = [c[0] for c in db.session.query(Student.course).distinct().all() if c[0]]
    
    return render_template(
        'admin/internships.html',
        internships=internships,
        companies=companies,
        all_courses=all_courses,
        search_query=search_query,
        company_filter=company_filter,
        status_filter=status_filter,
        course_filter=course_filter,
        start_date_filter=start_date_filter,
        end_date_filter=end_date_filter
    )

@admin_bp.route('/internships/detail/<int:internship_id>')
@role_required('admin')
def internship_detail(internship_id):
    """
    Renders detailed timeline progress, progress reports, and documents for an internship.
    """
    internship = Internship.query.get_or_404(internship_id)
    student = internship.student
    
    timeline_events = TimelineEvent.query.filter_by(internship_id=internship.id).order_by(TimelineEvent.id).all()
    progress_reports = ProgressReport.query.filter_by(internship_id=internship.id).order_by(ProgressReport.week_number).all()
    documents = Document.query.filter_by(internship_id=internship.id).all()
    evaluation = Evaluation.query.filter_by(internship_id=internship.id).first()
    
    # Calculate progress %
    from routes.student import calculate_progress_percentage
    progress_percent = calculate_progress_percentage(internship.id)
    
    return render_template(
        'admin/internship_detail.html',
        internship=internship,
        student=student,
        timeline_events=timeline_events,
        progress_reports=progress_reports,
        documents=documents,
        evaluation=evaluation,
        progress_percent=progress_percent
    )

@admin_bp.route('/internships/edit/<int:internship_id>', methods=['GET', 'POST'])
@role_required('admin')
def edit_internship(internship_id):
    """
    Allows admin to edit internship details.
    """
    internship = Internship.query.get_or_404(internship_id)
    
    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        description = request.form.get('description', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        internship_type = request.form.get('internship_type', '').strip()
        supervisor_name = request.form.get('supervisor_name', '').strip()
        supervisor_email = request.form.get('supervisor_email', '').strip()
        supervisor_phone = request.form.get('supervisor_phone', '').strip()
        company_id_str = request.form.get('company_id', '').strip()
        
        if not all([role, start_date_str, end_date_str, internship_type, supervisor_name, supervisor_email]):
            flash('Please fill in all required fields.', 'danger')
            return render_template('admin/internship_form.html', internship=internship, companies=Company.query.all())
            
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date formatting.', 'danger')
            return render_template('admin/internship_form.html', internship=internship, companies=Company.query.all())
            
        if end_date <= start_date:
            flash('End date must be after start date.', 'danger')
            return render_template('admin/internship_form.html', internship=internship, companies=Company.query.all())
            
        try:
            internship.role = role
            internship.description = description if description else None
            internship.start_date = start_date
            internship.end_date = end_date
            internship.internship_type = internship_type
            internship.supervisor_name = supervisor_name
            internship.supervisor_email = supervisor_email
            internship.supervisor_phone = supervisor_phone if supervisor_phone else None
            
            if company_id_str:
                internship.company_id = int(company_id_str)
            else:
                internship.company_id = None
                
            db.session.commit()
            flash('Internship record updated successfully.', 'success')
            return redirect(url_for('admin.list_internships'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during update.', 'danger')
            
    companies = Company.query.order_by(Company.company_name).all()
    return render_template('admin/internship_form.html', internship=internship, companies=companies)

@admin_bp.route('/internships/approve/<int:internship_id>', methods=['POST'])
@role_required('admin')
def approve_internship(internship_id):
    """
    Approves a student's internship, initializing timeline/deadlines, and notifies the student.
    """
    internship = Internship.query.get_or_404(internship_id)
    if internship.status != 'pending':
        flash('This internship has already been processed.', 'warning')
        return redirect(url_for('admin.list_internships'))
        
    try:
        internship.status = 'approved'
        generate_timeline_events(internship)
        generate_deadlines(internship)
        
        # Create approval notification
        notif = Notification(
            user_id=internship.student.user_id,
            title="Internship Approved by Admin",
            message=f"Your placement at {internship.company.company_name} was approved by the placement cell."
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"Internship for student {internship.student.user.name} approved successfully.", 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred during approval.', 'danger')
        
    return redirect(request.referrer or url_for('admin.list_internships'))

@admin_bp.route('/internships/reject/<int:internship_id>', methods=['POST'])
@role_required('admin')
def reject_internship(internship_id):
    """
    Rejects a registered internship placement and alerts the student.
    """
    internship = Internship.query.get_or_404(internship_id)
    if internship.status != 'pending':
        flash('This internship placement has already been processed.', 'warning')
        return redirect(url_for('admin.list_internships'))
        
    try:
        internship.status = 'rejected'
        
        # Notify the student
        notif = Notification(
            user_id=internship.student.user_id,
            title="Internship Placement Rejected",
            message=f"Your registered placement at {internship.company.company_name} for the role of {internship.role} was rejected by admin."
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"Internship placement for student {internship.student.user.name} rejected.", 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred during rejection.', 'danger')
        
    return redirect(request.referrer or url_for('admin.list_internships'))

@admin_bp.route('/companies')
@role_required('admin')
def list_companies():
    """
    Lists registered companies with search and internship counts.
    """
    search_query = request.args.get('search', '').strip()
    
    query = Company.query
    if search_query:
        query = query.filter(Company.company_name.like(f"%{search_query}%"))
        
    companies = query.order_by(Company.company_name).all()
    
    # Pre-compute internship counts
    company_data = []
    for comp in companies:
        count = Internship.query.filter_by(company_id=comp.id).count()
        company_data.append({
            'company': comp,
            'internship_count': count
        })
        
    return render_template(
        'admin/companies.html',
        company_data=company_data,
        search_query=search_query
    )

@admin_bp.route('/companies/add', methods=['GET', 'POST'])
@role_required('admin')
def add_company():
    """
    Allows admin to register a new company.
    """
    if request.method == 'POST':
        name = request.form.get('company_name', '').strip()
        address = request.form.get('address', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        
        if not name:
            flash('Company name is required.', 'danger')
            return render_template('admin/company_form.html', company=None, action='Add')
            
        try:
            new_comp = Company(
                company_name=name,
                address=address if address else None,
                contact_person=contact_person if contact_person else None
            )
            db.session.add(new_comp)
            db.session.commit()
            
            flash(f'Company {name} registered successfully.', 'success')
            return redirect(url_for('admin.list_companies'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while creating the company.', 'danger')
            
    return render_template('admin/company_form.html', company=None, action='Add')

@admin_bp.route('/companies/edit/<int:company_id>', methods=['GET', 'POST'])
@role_required('admin')
def edit_company(company_id):
    """
    Allows admin to edit company details.
    """
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        name = request.form.get('company_name', '').strip()
        address = request.form.get('address', '').strip()
        contact_person = request.form.get('contact_person', '').strip()
        
        if not name:
            flash('Company name is required.', 'danger')
            return render_template('admin/company_form.html', company=company, action='Edit')
            
        try:
            company.company_name = name
            company.address = address if address else None
            company.contact_person = contact_person if contact_person else None
            
            db.session.commit()
            flash(f'Company {name} updated successfully.', 'success')
            return redirect(url_for('admin.list_companies'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during update.', 'danger')
            
    return render_template('admin/company_form.html', company=company, action='Edit')

@admin_bp.route('/companies/delete/<int:company_id>', methods=['POST'])
@role_required('admin')
def delete_company(company_id):
    """
    Deletes a company from database. Placements will clear company_id to NULL.
    """
    company = Company.query.get_or_404(company_id)
    name = company.company_name
    
    try:
        db.session.delete(company)
        db.session.commit()
        flash(f"Company {name} deleted successfully.", 'success')
    except Exception:
        db.session.rollback()
        flash("An error occurred during deletion.", 'danger')
        
    return redirect(url_for('admin.list_companies'))


@admin_bp.route('/reports')
@role_required('admin')
def reports():
    """
    Renders the professional reports management page with real database metrics,
    interactive previews of 4 core reports, and CSV/PDF export actions.
    """
    report_type = request.args.get('type', 'completion').strip().lower()
    if report_type not in ['completion', 'students', 'companies', 'evaluations']:
        report_type = 'completion'
        
    course_filter = request.args.get('course', '').strip()
    status_filter = request.args.get('status', '').strip()

    # Available academic courses for filter
    available_courses = [
        c[0] for c in db.session.query(Student.course)
        .distinct()
        .filter(Student.course.isnot(None), Student.course != '')
        .order_by(Student.course)
        .all()
    ]

    # Global KPI Metrics
    metrics = ReportService.get_dashboard_metrics(course_filter=course_filter if course_filter else None)

    # Active Report Data
    if report_type == 'completion':
        report_data = ReportService.get_completion_report_data(course_filter, status_filter)
    elif report_type == 'students':
        report_data = ReportService.get_student_report_data(course_filter)
    elif report_type == 'companies':
        report_data = ReportService.get_company_report_data()
    elif report_type == 'evaluations':
        report_data = ReportService.get_evaluation_report_data(course_filter)
    else:
        report_data = []

    return render_template(
        'admin/reports.html',
        report_type=report_type,
        report_data=report_data,
        metrics=metrics,
        available_courses=available_courses,
        selected_course=course_filter,
        selected_status=status_filter
    )


@admin_bp.route('/reports/export/<report_type>/<export_format>')
@role_required('admin')
def export_report(report_type, export_format):
    """
    Exports the requested report (completion, students, companies, evaluations)
    in CSV or PDF format using real database records.
    """
    report_type = report_type.lower().strip()
    export_format = export_format.lower().strip()

    if report_type not in ['completion', 'students', 'companies', 'evaluations']:
        abort(404)

    if export_format not in ['csv', 'pdf']:
        abort(400)

    course_filter = request.args.get('course', '').strip()
    status_filter = request.args.get('status', '').strip()

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"interntrack_{report_type}_report_{timestamp}.{export_format}"

    if export_format == 'csv':
        file_bytes = ReportService.generate_csv(report_type, course_filter, status_filter)
        return Response(
            file_bytes,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    elif export_format == 'pdf':
        file_bytes = ReportService.generate_pdf(report_type, course_filter, status_filter)
        return Response(
            file_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

