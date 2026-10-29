from flask import Blueprint, render_template, redirect, url_for, flash, request, session, abort
from routes.decorators import role_required
from database.db import db
from models import Faculty, Student, Internship, Company, TimelineEvent, ProgressReport, Evaluation, Deadline, Notification, Document, User
from routes.student import generate_timeline_events, generate_deadlines
from datetime import datetime, timezone

faculty_bp = Blueprint('faculty', __name__, url_prefix='/faculty')

@faculty_bp.route('/dashboard')
@role_required('faculty')
def dashboard():
    """
    Renders the faculty dashboard with statistics, pending placements, active placements,
    and pending evaluations.
    """
    faculty = Faculty.query.filter_by(user_id=session['user_id']).first()
    if not faculty:
        flash('Faculty record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    # Query stats dynamically from database
    total_students = Student.query.count()
    active_internships = Internship.query.filter_by(status='active').count()
    completed_internships = Internship.query.filter_by(status='completed').count()
    pending_approvals_count = Internship.query.filter_by(status='pending').count()
    pending_evaluations_count = Internship.query.filter(Internship.status.in_(['approved', 'active'])).count()
    
    # Lists for action items
    pending_approvals = Internship.query.filter_by(status='pending').all()
    pending_evaluations = Internship.query.filter(Internship.status.in_(['approved', 'active'])).all()
    
    return render_template(
        'faculty/dashboard.html', 
        faculty=faculty,
        total_students=total_students,
        active_internships=active_internships,
        completed_internships=completed_internships,
        pending_approvals_count=pending_approvals_count,
        pending_evaluations_count=pending_evaluations_count,
        pending_approvals=pending_approvals,
        pending_evaluations=pending_evaluations
    )

@faculty_bp.route('/internship/approve/<int:internship_id>', methods=['POST'])
@role_required('faculty')
def approve_internship(internship_id):
    """
    Approves a student's registered internship and generates the initial timeline tracking events.
    """
    faculty = Faculty.query.filter_by(user_id=session['user_id']).first()
    if not faculty:
        abort(403)
        
    internship = Internship.query.get_or_404(internship_id)
    if internship.status != 'pending':
        flash('This internship has already been processed.', 'warning')
        return redirect(url_for('faculty.dashboard'))
        
    try:
        internship.status = 'approved'
        generate_timeline_events(internship)
        generate_deadlines(internship)
        
        # Create approval notification for the student
        notif = Notification(
            user_id=internship.student.user_id,
            title="Internship Approved",
            message="Your internship has been approved."
        )
        db.session.add(notif)
        
        db.session.commit()
        flash(f"Internship for student {internship.student.user.name} approved successfully.", 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred during approval.', 'danger')
        
    return redirect(url_for('faculty.dashboard'))

@faculty_bp.route('/evaluation/<int:student_id>', methods=['GET', 'POST'])
@role_required('faculty')
def evaluate_internship(student_id):
    """
    Renders evaluation form for faculty and handles the scoring, validating, and transitioning
    the Faculty Evaluation timeline stage.
    """
    faculty = Faculty.query.filter_by(user_id=session['user_id']).first()
    if not faculty:
        abort(403)
        
    student = Student.query.get_or_404(student_id)
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        flash('No registered internship found for this student.', 'warning')
        return redirect(url_for('faculty.dashboard'))
    
    # Can only evaluate active or approved internships
    if internship.status not in ['approved', 'active']:
        flash('This placement is not in an evaluatable state.', 'warning')
        return redirect(url_for('faculty.dashboard'))
        
    if request.method == 'POST':
        try:
            tech_str = request.form.get('technical_skills')
            comm_str = request.form.get('communication')
            punc_str = request.form.get('punctuality')
            qual_str = request.form.get('work_quality')
            disc_str = request.form.get('discipline')
            feedback = request.form.get('feedback', '').strip()
            
            # Validation
            scores = {}
            for name, val_str in [('technical_skills', tech_str), 
                                  ('communication', comm_str), 
                                  ('punctuality', punc_str), 
                                  ('work_quality', qual_str), 
                                  ('discipline', disc_str)]:
                if val_str is None or val_str.strip() == '':
                    flash(f'Please enter a score for {name.replace("_", " ").title()}.', 'danger')
                    return render_template('faculty/evaluate.html', internship=internship)
                try:
                    val = int(val_str)
                except ValueError:
                    flash(f'Score for {name.replace("_", " ").title()} must be a number.', 'danger')
                    return render_template('faculty/evaluate.html', internship=internship)
                if val < 0 or val > 10:
                    flash(f'Score for {name.replace("_", " ").title()} must be between 0 and 10.', 'danger')
                    return render_template('faculty/evaluate.html', internship=internship)
                scores[name] = val
                
            tech = scores['technical_skills']
            comm = scores['communication']
            punc = scores['punctuality']
            qual = scores['work_quality']
            disc = scores['discipline']
            
            # Simple average score
            overall = float((tech + comm + punc + qual + disc) / 5.0)
            
            # Create/Update Evaluation record
            new_eval = Evaluation.query.filter_by(internship_id=internship.id).first()
            if not new_eval:
                new_eval = Evaluation(
                    internship_id=internship.id,
                    student_id=student.id,
                    faculty_id=faculty.id,
                    technical_skills=tech,
                    communication=comm,
                    punctuality=punc,
                    work_quality=qual,
                    discipline=disc,
                    feedback=feedback if feedback else None,
                    overall_score=overall
                )
                db.session.add(new_eval)
            else:
                new_eval.faculty_id = faculty.id
                new_eval.technical_skills = tech
                new_eval.communication = comm
                new_eval.punctuality = punc
                new_eval.work_quality = qual
                new_eval.discipline = disc
                new_eval.feedback = feedback if feedback else None
                new_eval.overall_score = overall
                new_eval.evaluated_at = datetime.now(timezone.utc)
            
            # Mark Faculty Evaluation stage as completed
            eval_event = TimelineEvent.query.filter_by(internship_id=internship.id, title='Faculty Evaluation').first()
            if eval_event:
                eval_event.status = 'completed'
                eval_event.event_date = datetime.now(timezone.utc)
                
            # Set Internship Completion stage to in_progress
            comp_event = TimelineEvent.query.filter_by(internship_id=internship.id, title='Internship Completion').first()
            if comp_event:
                comp_event.status = 'in_progress'
                comp_event.event_date = datetime.now(timezone.utc)
                
            # Mark Faculty Evaluation deadline completed
            eval_dl = Deadline.query.filter_by(internship_id=internship.id, title="Faculty Evaluation").first()
            if eval_dl:
                eval_dl.status = 'completed'
                eval_dl.completed_at = datetime.now(timezone.utc)
                
            # Create evaluation notification
            notif = Notification(
                user_id=student.user_id,
                title="Internship Evaluated",
                message=f"Your faculty evaluation has been submitted. Overall Score: {overall:.1f}/10."
            )
            db.session.add(notif)
            
            # Check if all completion conditions are satisfied
            from routes.student import check_completion_conditions
            is_satisfied, _ = check_completion_conditions(internship)
            if is_satisfied:
                internship.status = 'completed'
                if comp_event:
                    comp_event.status = 'completed'
                    comp_event.event_date = datetime.now(timezone.utc)
                    
            db.session.commit()
            
            flash(f"Evaluation for {student.user.name} submitted successfully.", 'success')
            return redirect(url_for('faculty.dashboard'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during evaluation submission.', 'danger')
            return render_template('faculty/evaluate.html', internship=internship)
            
    return render_template('faculty/evaluate.html', internship=internship)

@faculty_bp.route('/document/verify/<int:document_id>', methods=['POST'])
@role_required('faculty', 'admin')
def verify_document(document_id):
    """
    Approves/verifies a student document and generates a student notification.
    """
    doc = Document.query.get_or_404(document_id)
    doc.status = 'verified'
    doc.verified_by = session['user_id']
    
    # Create notification for student
    notif = Notification(
        user_id=doc.student.user_id,
        title="Document Verified",
        message=f"Your document {doc.document_type} has been verified."
    )
    db.session.add(notif)
    
    # Check if all completion conditions are satisfied
    internship = doc.internship
    from routes.student import check_completion_conditions
    is_satisfied, _ = check_completion_conditions(internship)
    if is_satisfied:
        internship.status = 'completed'
        comp_event = TimelineEvent.query.filter_by(internship_id=internship.id, title='Internship Completion').first()
        if comp_event:
            comp_event.status = 'completed'
            comp_event.event_date = datetime.now(timezone.utc)
            
    db.session.commit()
    
    flash(f"Document {doc.document_type} verified successfully.", 'success')
    return redirect(request.referrer or url_for('faculty.dashboard'))

@faculty_bp.route('/document/reject/<int:document_id>', methods=['POST'])
@role_required('faculty', 'admin')
def reject_document(document_id):
    """
    Rejects a student document and generates a student notification.
    """
    doc = Document.query.get_or_404(document_id)
    doc.status = 'rejected'
    
    # Create notification for student
    notif = Notification(
        user_id=doc.student.user_id,
        title="Document Rejected",
        message=f"Your document {doc.document_type} has been rejected."
    )
    db.session.add(notif)
    db.session.commit()
    
    flash(f"Document {doc.document_type} rejected.", 'danger')
    return redirect(request.referrer or url_for('faculty.dashboard'))

@faculty_bp.route('/students')
@role_required('faculty')
def list_students():
    """
    Renders the student placements list with search and filter parameters.
    """
    faculty = Faculty.query.filter_by(user_id=session['user_id']).first()
    if not faculty:
        flash('Faculty record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    # Query internships
    query = Internship.query.join(Student).join(User)
    
    if search_query:
        query = query.filter(
            (User.name.like(f"%{search_query}%")) | 
            (Student.roll_no.like(f"%{search_query}%")) |
            (Internship.role.like(f"%{search_query}%"))
        )
        
    if status_filter:
        query = query.filter(Internship.status == status_filter)
        
    internships = query.all()
    
    # Pre-calculate progress percentage for each student placement
    from routes.student import calculate_progress_percentage
    students_data = []
    for intship in internships:
        progress_val = calculate_progress_percentage(intship.id)
        students_data.append({
            'internship': intship,
            'student': intship.student,
            'progress': progress_val
        })
        
    return render_template(
        'faculty/students.html', 
        faculty=faculty, 
        students_data=students_data, 
        search_query=search_query, 
        status_filter=status_filter
    )

@faculty_bp.route('/students/<int:student_id>')
@role_required('faculty')
def student_detail(student_id):
    """
    Renders details for a specific student, including timeline, progress reports,
    submitted documents, and deadlines.
    """
    faculty = Faculty.query.filter_by(user_id=session['user_id']).first()
    if not faculty:
        flash('Faculty record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    student = Student.query.get_or_404(student_id)
    internship = Internship.query.filter_by(student_id=student.id).first()
    
    timeline_events = []
    progress_reports = []
    docs_map = {}
    deadlines_data = []
    progress_percent = 0
    doc_count = 0
    
    if internship:
        from routes.student import calculate_progress_percentage, get_deadline_status_and_days, REQUIRED_DOCUMENTS
        progress_percent = calculate_progress_percentage(internship.id)
        timeline_events = TimelineEvent.query.filter_by(internship_id=internship.id).order_by(TimelineEvent.id).all()
        progress_reports = ProgressReport.query.filter_by(internship_id=internship.id).order_by(ProgressReport.week_number).all()
        
        # Documents
        documents = Document.query.filter_by(internship_id=internship.id).all()
        docs_map = {doc.document_type: doc for doc in documents}
        doc_count = len(documents)
        
        # Deadlines
        deadlines = Deadline.query.filter_by(internship_id=internship.id).all()
        for d in deadlines:
            status_label, days_rem = get_deadline_status_and_days(d)
            deadlines_data.append({
                'id': d.id,
                'title': d.title,
                'description': d.description,
                'due_date': d.due_date,
                'status': status_label,
                'days_remaining': days_rem
            })
            
    return render_template(
        'faculty/student_detail.html',
        faculty=faculty,
        student=student,
        internship=internship,
        timeline_events=timeline_events,
        progress_reports=progress_reports,
        docs_map=docs_map,
        doc_count=doc_count,
        deadlines=deadlines_data,
        progress_percent=progress_percent,
        required_docs=REQUIRED_DOCUMENTS if internship else []
    )

@faculty_bp.route('/internship/reject/<int:internship_id>', methods=['POST'])
@role_required('faculty')
def reject_internship(internship_id):
    """
    Rejects a registered internship placement and alerts the student.
    """
    faculty = Faculty.query.filter_by(user_id=session['user_id']).first()
    if not faculty:
        abort(403)
        
    internship = Internship.query.get_or_404(internship_id)
    if internship.status != 'pending':
        flash('This internship placement has already been processed.', 'warning')
        return redirect(url_for('faculty.dashboard'))
        
    try:
        internship.status = 'rejected'
        
        # Notify the student
        notif = Notification(
            user_id=internship.student.user_id,
            title="Internship Placement Rejected",
            message=f"Your registered placement at {internship.company.company_name} for the role of {internship.role} was rejected by faculty."
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"Internship placement for student {internship.student.user.name} rejected successfully.", 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred during rejection.', 'danger')
        
    return redirect(url_for('faculty.dashboard'))

@faculty_bp.route('/progress/comment/<int:report_id>', methods=['POST'])
@role_required('faculty')
def comment_progress(report_id):
    """
    Allows faculty to post feedback/comments on a student's weekly progress log.
    """
    faculty = Faculty.query.filter_by(user_id=session['user_id']).first()
    if not faculty:
        abort(403)
        
    report = ProgressReport.query.get_or_404(report_id)
    feedback_text = request.form.get('feedback', '').strip()
    
    if not feedback_text:
        flash('Feedback text cannot be empty.', 'danger')
        return redirect(url_for('faculty.student_detail', student_id=report.student_id))
        
    try:
        report.feedback = feedback_text
        report.status = 'approved'
        
        # Create notification for student
        notif = Notification(
            user_id=report.student.user_id,
            title="Progress Report Reviewed",
            message=f"Your Week {report.week_number} progress report was reviewed by faculty: \"{feedback_text[:40]}...\""
        )
        db.session.add(notif)
        db.session.commit()
        flash('Feedback submitted successfully.', 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred while submitting feedback.', 'danger')
        
    return redirect(url_for('faculty.student_detail', student_id=report.student_id))
