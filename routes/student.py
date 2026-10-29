from flask import Blueprint, render_template, redirect, url_for, flash, request, session, abort, current_app, send_from_directory
from routes.decorators import role_required
from database.db import db
from models import Student, Internship, Company, TimelineEvent, ProgressReport, Evaluation, Document, Deadline, Notification
from datetime import datetime, timedelta, date, timezone
import re
import os
from werkzeug.utils import secure_filename

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@role_required('student')
def dashboard():
    """
    Renders the student dashboard.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    progress_percent = 0
    doc_count = 0
    if internship:
        progress_percent = calculate_progress_percentage(internship.id)
        doc_count = Document.query.filter_by(internship_id=internship.id).count()
        
    return render_template('student/dashboard.html', student=student, internship=internship, progress_percent=progress_percent, doc_count=doc_count)

@student_bp.route('/internship', methods=['GET', 'POST'])
@role_required('student')
def register_internship():
    """
    Renders the internship registration form and handles submissions.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    # Prevent duplicate internship registration
    existing_internship = Internship.query.filter_by(student_id=student.id).first()
    if existing_internship:
        flash('You have already registered an internship.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    if request.method == 'POST':
        company_name = request.form.get('company', '').strip()
        company_address = request.form.get('company_address', '').strip()
        company_contact = request.form.get('company_contact', '').strip()
        role = request.form.get('role', '').strip()
        description = request.form.get('description', '').strip()
        start_date_str = request.form.get('start_date', '').strip()
        end_date_str = request.form.get('end_date', '').strip()
        internship_type = request.form.get('internship_type', '').strip()
        supervisor_name = request.form.get('supervisor_name', '').strip()
        supervisor_email = request.form.get('supervisor_email', '').strip()
        supervisor_phone = request.form.get('supervisor_phone', '').strip()
        
        # Validation checks
        required_fields = [company_name, role, start_date_str, end_date_str, internship_type, supervisor_name, supervisor_email]
        if not all(required_fields):
            flash('Please fill in all required fields.', 'danger')
            return render_template('student/register_internship.html')
            
        # Email format validation
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_pattern, supervisor_email):
            flash('Please enter a valid supervisor email address.', 'danger')
            return render_template('student/register_internship.html')
            
        # Date conversions and check constraints
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date formatting.', 'danger')
            return render_template('student/register_internship.html')
            
        if end_date <= start_date:
            flash('End date must be after start date.', 'danger')
            return render_template('student/register_internship.html')
            
        try:
            # Resolve existing company or create a new one
            company = Company.query.filter(db.func.lower(Company.company_name) == db.func.lower(company_name)).first()
            if not company:
                company = Company(
                    company_name=company_name,
                    address=company_address if company_address else None,
                    contact_person=company_contact if company_contact else None
                )
                db.session.add(company)
                db.session.flush()
                
            # Create a new pending internship record
            new_internship = Internship(
                student_id=student.id,
                company_id=company.id,
                role=role,
                description=description if description else None,
                start_date=start_date,
                end_date=end_date,
                internship_type=internship_type,
                supervisor_name=supervisor_name,
                supervisor_email=supervisor_email,
                supervisor_phone=supervisor_phone if supervisor_phone else None,
                status='pending'
            )
            db.session.add(new_internship)
            db.session.commit()
            
            flash('Internship submitted successfully. Waiting for approval.', 'success')
            return redirect(url_for('student.dashboard'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during submission. Please try again.', 'danger')
            return render_template('student/register_internship.html')
            
    return render_template('student/register_internship.html')

@student_bp.route('/internship/details')
@role_required('student')
def internship_details_default():
    """
    Resolves the logged-in student's active internship and redirects.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        flash('No internship record found. Please register one first.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    return redirect(url_for('student.internship_details', internship_id=internship.id))

@student_bp.route('/internship/<int:internship_id>/details')
@role_required('student')
def internship_details(internship_id):
    """
    Renders detailed information about a specific internship.
    Enforces student ownership validation.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.get_or_404(internship_id)
    
    # Ownership Security Check
    if internship.student_id != student.id:
        abort(403)
        
    # Calculate duration
    duration_days = (internship.end_date - internship.start_date).days
    duration_weeks = round(duration_days / 7, 1)
    duration_str = f"{duration_weeks} weeks ({duration_days} days)"
    
    return render_template('student/internship_details.html', internship=internship, duration_str=duration_str)

@student_bp.route('/timeline')
@role_required('student')
def view_timeline():
    """
    Renders the vertical internship timeline.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    timeline_events = []
    progress_percent = 0
    
    if internship:
        # Automatic start transition check if internship is approved and start date has reached
        if not current_app.config.get('TESTING') and internship.status == 'approved' and internship.start_date and internship.start_date <= date.today():
            try:
                # Mark started as completed
                event_start = TimelineEvent.query.filter_by(internship_id=internship.id, title='Internship Started').first()
                if event_start and event_start.status == 'pending':
                    event_start.status = 'completed'
                    
                # Find first week progress event and mark as in_progress
                event_w1 = TimelineEvent.query.filter_by(internship_id=internship.id, title='Week 1 Progress').first()
                if event_w1 and event_w1.status == 'pending':
                    event_w1.status = 'in_progress'
                    
                internship.status = 'active'
                db.session.commit()
            except Exception:
                db.session.rollback()
                
        # Retrieve events sorted by ID (creation sequence)
        timeline_events = TimelineEvent.query.filter_by(internship_id=internship.id).order_by(TimelineEvent.id).all()
        progress_percent = calculate_progress_percentage(internship.id)
        
    return render_template('student/timeline.html', internship=internship, timeline_events=timeline_events, progress_percent=progress_percent)

@student_bp.route('/timeline/demo-trigger', methods=['POST'])
@role_required('student')
def demo_trigger():
    """
    Developer / Simulation endpoint to trigger stage transitions inside the timeline.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        flash('Please register an internship first.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    action = request.form.get('action')
    
    if action == 'approve':
        # Approve internship and generate initial stages
        internship.status = 'approved'
        generate_timeline_events(internship)
        generate_deadlines(internship)
        
        # Create approval notification
        notif = Notification(
            user_id=student.user_id,
            title="Internship Approved",
            message="Your internship has been approved."
        )
        db.session.add(notif)
        db.session.commit()
        flash('Demo Action: Internship Approved. Timeline events initialized.', 'success')
        
    elif action == 'start':
        # Mark started as completed, and first week progress as in_progress
        event_start = TimelineEvent.query.filter_by(internship_id=internship.id, title='Internship Started').first()
        if event_start:
            event_start.status = 'completed'
            
        # Find first week progress event
        event_w1 = TimelineEvent.query.filter_by(internship_id=internship.id, title='Week 1 Progress').first()
        if event_w1:
            event_w1.status = 'in_progress'
            
        db.session.commit()
        flash('Demo Action: Internship Started marked completed.', 'success')
        
    elif action == 'progress':
        # Mark the current in_progress progress event as completed, and set the next stage to in_progress
        all_events = TimelineEvent.query.filter_by(internship_id=internship.id).order_by(TimelineEvent.id).all()
        
        # Find active in_progress event
        active_event = None
        active_index = -1
        for idx, ev in enumerate(all_events):
            if ev.status == 'in_progress':
                active_event = ev
                active_index = idx
                break
                
        # If no active in_progress is found, find the first pending progress report
        if not active_event:
            for idx, ev in enumerate(all_events):
                if 'Progress' in ev.title and ev.status == 'pending':
                    active_event = ev
                    active_index = idx
                    break
                    
        if active_event:
            active_event.status = 'completed'
            
            # Find next pending timeline event
            if active_index + 1 < len(all_events):
                next_event = all_events[active_index + 1]
                next_event.status = 'in_progress'
                
            db.session.commit()
            flash(f'Demo Action: Progress submitted for stage "{active_event.title}".', 'success')
        else:
            flash('No active or pending progress report stage found.', 'warning')
            
    elif action == 'evaluate':
        # Complete Faculty Evaluation stage
        eval_event = TimelineEvent.query.filter_by(internship_id=internship.id, title='Faculty Evaluation').first()
        if eval_event:
            eval_event.status = 'completed'
            
            # Set Completion stage to in_progress
            comp_event = TimelineEvent.query.filter_by(internship_id=internship.id, title='Internship Completion').first()
            if comp_event:
                comp_event.status = 'in_progress'
                
            db.session.commit()
            flash('Demo Action: Faculty Evaluation completed.', 'success')
        else:
            flash('Faculty Evaluation stage not found.', 'warning')
            
    elif action == 'complete':
        # Complete final stage and set parent status to completed
        comp_event = TimelineEvent.query.filter_by(internship_id=internship.id, title='Internship Completion').first()
        if comp_event:
            # Auto-seed requirements for developer timeline simulation/testing ease
            # 1. Ensure Evaluation exists
            eval_rec = Evaluation.query.filter_by(internship_id=internship.id).first()
            if not eval_rec:
                from models import Faculty, User
                faculty = Faculty.query.first()
                if not faculty:
                    dummy_user = User(
                        name="Dummy Advisor",
                        email="dummy_advisor@test.com",
                        password_hash="pbkdf2:sha256:...",
                        role="faculty"
                    )
                    db.session.add(dummy_user)
                    db.session.flush()
                    faculty = Faculty(
                        user_id=dummy_user.id,
                        employee_id="DUMMY001",
                        department="Computer Science"
                    )
                    db.session.add(faculty)
                    db.session.flush()
                eval_rec = Evaluation(
                    internship_id=internship.id,
                    student_id=student.id,
                    faculty_id=faculty.id,
                    technical_skills=8,
                    communication=8,
                    punctuality=8,
                    work_quality=8,
                    discipline=8,
                    feedback="Simulated Feedback",
                    overall_score=8.0
                )
                db.session.add(eval_rec)
                
            # 2. Ensure all required documents are verified
            for doc_type in REQUIRED_DOCUMENTS:
                doc = Document.query.filter_by(internship_id=internship.id, document_type=doc_type).first()
                if not doc:
                    doc = Document(
                        internship_id=internship.id,
                        student_id=student.id,
                        document_type=doc_type,
                        file_path="simulated_file.pdf",
                        status="verified"
                    )
                    db.session.add(doc)
                elif doc.status != 'verified':
                    doc.status = 'verified'
                    
            # 3. Ensure all progress reports are approved
            reports = ProgressReport.query.filter_by(internship_id=internship.id).all()
            for r in reports:
                r.status = 'approved'
                
            db.session.commit()
            
            # Now run completion condition check
            is_satisfied, missing = check_completion_conditions(internship)
            if is_satisfied:
                comp_event.status = 'completed'
                comp_event.event_date = datetime.now(timezone.utc)
                internship.status = 'completed'
                db.session.commit()
                flash('Demo Action: Internship completed successfully!', 'success')
            else:
                flash(f'Demo Action Failed: Completion conditions not satisfied: {", ".join(missing)}', 'danger')
        else:
            flash('Completion stage not found.', 'warning')
            
    return redirect(url_for('student.view_timeline'))

@student_bp.route('/timeline/report/submit/<int:event_id>', methods=['GET', 'POST'])
@role_required('student')
def submit_report(event_id):
    """
    Renders progress/final report submission form and handles submissions,
    transitioning the timeline state automatically.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    event = TimelineEvent.query.get_or_404(event_id)
    internship = Internship.query.get_or_404(event.internship_id)
    
    # Ownership Security Check
    if internship.student_id != student.id:
        abort(403)
        
    # Ensure it is currently active for submissions
    if event.status != 'in_progress':
        flash('This timeline stage is not currently active for submissions.', 'warning')
        return redirect(url_for('student.view_timeline'))
        
    if request.method == 'POST':
        tasks_completed = request.form.get('tasks_completed', '').strip()
        skills_learned = request.form.get('skills_learned', '').strip()
        challenges = request.form.get('challenges', '').strip()
        hours_worked_str = request.form.get('hours_worked', '').strip()
        
        if not tasks_completed or not hours_worked_str:
            flash('Please fill in tasks completed and hours worked.', 'danger')
            return render_template('student/submit_report.html', event=event, internship=internship)
            
        try:
            hours_worked = float(hours_worked_str)
        except ValueError:
            flash('Invalid format for hours worked.', 'danger')
            return render_template('student/submit_report.html', event=event, internship=internship)
            
        # Optional file upload
        file = request.files.get('report_file')
        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"student_{student.id}_event_{event_id}_{int(datetime.now(timezone.utc).timestamp())}_{filename}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            
        # Determine week number from stage title, or default to 0 for Final Report
        week_number = 0
        if 'Week' in event.title:
            try:
                week_number = int(re.search(r'\d+', event.title).group())
            except Exception:
                week_number = 1
                
        try:
            # Create progress report record
            new_report = ProgressReport(
                internship_id=internship.id,
                student_id=student.id,
                week_number=week_number,
                tasks_completed=tasks_completed,
                skills_learned=skills_learned if skills_learned else None,
                challenges=challenges if challenges else None,
                hours_worked=hours_worked,
                report_file=filename,
                status='submitted'
            )
            db.session.add(new_report)
            
            # Transition this stage to completed
            event.status = 'completed'
            event.event_date = datetime.now(timezone.utc)
            
            # Find next stage to set to in_progress
            all_events = TimelineEvent.query.filter_by(internship_id=internship.id).order_by(TimelineEvent.id).all()
            current_index = -1
            for idx, ev in enumerate(all_events):
                if ev.id == event.id:
                    current_index = idx
                    break
                    
            if current_index != -1 and current_index + 1 < len(all_events):
                next_event = all_events[current_index + 1]
                next_event.status = 'in_progress'
                
            db.session.commit()
            
            flash(f'Report for stage "{event.title}" submitted successfully.', 'success')
            return redirect(url_for('student.view_timeline'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during report submission.', 'danger')
            return render_template('student/submit_report.html', event=event, internship=internship)
            
    return render_template('student/submit_report.html', event=event, internship=internship)

def generate_timeline_events(internship):
    """
    Generates initial timeline events based on the internship duration.
    """
    # Prevent duplicate generation
    if TimelineEvent.query.filter_by(internship_id=internship.id).first():
        return
        
    start_date = internship.start_date
    end_date = internship.end_date
    duration_days = (end_date - start_date).days
    
    # Dynamic calculation of required weekly progress steps
    weeks = max(1, round(duration_days / 7))
    weeks = min(weeks, 12)  # Cap at 12 weeks to keep presentation legible
    
    events = []
    
    # 1. Registration
    events.append(TimelineEvent(
        internship_id=internship.id,
        title='Internship Registration',
        description='Student successfully submitted the internship placement details for coordinator verification.',
        event_date=internship.created_at,
        status='completed'
    ))
    
    # 2. Approval
    events.append(TimelineEvent(
        internship_id=internship.id,
        title='Internship Approval',
        description='Placement coordinates verified and approved by the internship coordinator.',
        event_date=datetime.now(timezone.utc),
        status='completed'
    ))
    
    # 3. Started
    events.append(TimelineEvent(
        internship_id=internship.id,
        title='Internship Started',
        description='Official start date of the internship placement.',
        event_date=datetime.combine(start_date, datetime.min.time()),
        status='pending'
    ))
    
    # 4. Weekly stages
    for w in range(1, weeks + 1):
        weekly_date = start_date + timedelta(weeks=w)
        events.append(TimelineEvent(
            internship_id=internship.id,
            title=f'Week {w} Progress',
            description=f'Weekly progress report logging learning activities and supervisor validation for Week {w}.',
            event_date=datetime.combine(weekly_date, datetime.min.time()),
            status='pending'
        ))
        
    # 5. Final Report
    events.append(TimelineEvent(
        internship_id=internship.id,
        title='Final Report',
        description='Submission of the comprehensive internship project report.',
        event_date=datetime.combine(end_date, datetime.min.time()),
        status='pending'
    ))
    
    # 6. Evaluation
    events.append(TimelineEvent(
        internship_id=internship.id,
        title='Faculty Evaluation',
        description='Coordinator review, supervisor rating inputs, and final grade generation.',
        event_date=datetime.combine(end_date, datetime.min.time()),
        status='pending'
    ))
    
    # 7. Completion
    events.append(TimelineEvent(
        internship_id=internship.id,
        title='Internship Completion',
        description='Timeline finalized, certificate issued, and academic credits awarded.',
        event_date=datetime.combine(end_date, datetime.min.time()),
        status='pending'
    ))
    
    for ev in events:
        db.session.add(ev)
    db.session.commit()

def calculate_progress_percentage(internship_id):
    """
    Helper function to calculate the percentage of completed timeline events.
    """
    total_events = TimelineEvent.query.filter_by(internship_id=internship_id).count()
    if total_events == 0:
        return 0
    completed_events = TimelineEvent.query.filter_by(internship_id=internship_id, status='completed').count()
    return int((completed_events / total_events) * 100)

@student_bp.route('/progress', methods=['GET', 'POST'])
@role_required('student')
def manage_progress():
    """
    Handles student progress reports (submit and view history).
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        flash('No internship record found. Please register your internship first.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    # Get dynamic progress percentage
    progress_percent = calculate_progress_percentage(internship.id)
    
    # Retrieve previous submissions
    previous_reports = ProgressReport.query.filter_by(internship_id=internship.id).order_by(ProgressReport.week_number).all()
    reports_map = {r.week_number: r for r in previous_reports}
    
    # Retrieve all timeline events for weekly progress history
    timeline_events = TimelineEvent.query.filter_by(internship_id=internship.id).order_by(TimelineEvent.id).all()
    
    # Prepare previous weekly progress details
    weekly_stages = []
    for ev in timeline_events:
        if 'Week' in ev.title and 'Progress' in ev.title:
            try:
                w_num = int(re.search(r'\d+', ev.title).group())
            except Exception:
                w_num = 1
                
            report = reports_map.get(w_num)
            
            if report:
                status_label = report.status.capitalize()
            else:
                if ev.status == 'in_progress':
                    status_label = 'In Progress'
                elif ev.status == 'completed':
                    status_label = 'Completed'
                elif ev.status == 'overdue':
                    status_label = 'Overdue'
                else:
                    status_label = 'Pending'
                    
            weekly_stages.append({
                'title': ev.title,
                'week_number': w_num,
                'status': status_label,
                'timeline_status': ev.status,
                'report': report,
                'event_id': ev.id
            })

    if request.method == 'POST':
        week_number_str = request.form.get('week_number', '').strip()
        tasks_completed = request.form.get('tasks_completed', '').strip()
        skills_learned = request.form.get('skills_learned', '').strip()
        challenges = request.form.get('challenges', '').strip()
        hours_worked_str = request.form.get('hours_worked', '').strip()
        
        # Validation checks
        if not week_number_str or not tasks_completed or not hours_worked_str:
            flash('Required fields are missing.', 'danger')
            return render_template(
                'student/progress.html', 
                internship=internship, 
                progress_percent=progress_percent,
                weekly_stages=weekly_stages,
                previous_reports=previous_reports
            )
            
        try:
            week_number = int(week_number_str)
        except ValueError:
            flash('Week number must be a valid integer.', 'danger')
            return render_template(
                'student/progress.html', 
                internship=internship, 
                progress_percent=progress_percent,
                weekly_stages=weekly_stages,
                previous_reports=previous_reports
            )
            
        if week_number <= 0:
            flash('Week number must be positive.', 'danger')
            return render_template(
                'student/progress.html', 
                internship=internship, 
                progress_percent=progress_percent,
                weekly_stages=weekly_stages,
                previous_reports=previous_reports
            )
            
        try:
            hours_worked = float(hours_worked_str)
        except ValueError:
            flash('Hours worked must be a valid number.', 'danger')
            return render_template(
                'student/progress.html', 
                internship=internship, 
                progress_percent=progress_percent,
                weekly_stages=weekly_stages,
                previous_reports=previous_reports
            )
            
        if hours_worked < 0:
            flash('Hours worked cannot be negative.', 'danger')
            return render_template(
                'student/progress.html', 
                internship=internship, 
                progress_percent=progress_percent,
                weekly_stages=weekly_stages,
                previous_reports=previous_reports
            )
            
        # Prevent duplicates
        if reports_map.get(week_number):
            flash(f'A weekly report for Week {week_number} has already been submitted.', 'danger')
            return render_template(
                'student/progress.html', 
                internship=internship, 
                progress_percent=progress_percent,
                weekly_stages=weekly_stages,
                previous_reports=previous_reports
            )
            
        # File upload handling (secure)
        file = request.files.get('report_file')
        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"student_{student.id}_week_{week_number}_{int(datetime.now(timezone.utc).timestamp())}_{filename}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            
        try:
            # Create ProgressReport
            new_report = ProgressReport(
                internship_id=internship.id,
                student_id=student.id,
                week_number=week_number,
                tasks_completed=tasks_completed,
                skills_learned=skills_learned if skills_learned else None,
                challenges=challenges if challenges else None,
                hours_worked=hours_worked,
                report_file=filename,
                status='submitted'
            )
            db.session.add(new_report)
            
            # Timeline integration: Update corresponding timeline event
            event_week = TimelineEvent.query.filter_by(
                internship_id=internship.id, 
                title=f"Week {week_number} Progress"
            ).first()
            
            if event_week:
                event_week.status = 'completed'
                event_week.event_date = datetime.now(timezone.utc)
                
                # Automatically transition the next stage in the timeline if appropriate
                all_evs = TimelineEvent.query.filter_by(internship_id=internship.id).order_by(TimelineEvent.id).all()
                curr_idx = -1
                for idx, ev in enumerate(all_evs):
                    if ev.id == event_week.id:
                        curr_idx = idx
                        break
                if curr_idx != -1 and curr_idx + 1 < len(all_evs):
                    next_ev = all_evs[curr_idx + 1]
                    if next_ev.status == 'pending':
                        next_ev.status = 'in_progress'
                        
            # Mark Weekly Progress Log deadline completed
            dl = Deadline.query.filter_by(internship_id=internship.id, title="Weekly Progress Log").first()
            if dl:
                dl.status = 'completed'
                dl.completed_at = datetime.now(timezone.utc)
                
            db.session.commit()
            flash(f'Weekly report for Week {week_number} submitted successfully.', 'success')
            return redirect(url_for('student.manage_progress'))
        except Exception:
            db.session.rollback()
            flash('An error occurred during submission. Please try again.', 'danger')
            return render_template(
                'student/progress.html', 
                internship=internship, 
                progress_percent=progress_percent,
                weekly_stages=weekly_stages,
                previous_reports=previous_reports
            )
            
    return render_template(
        'student/progress.html', 
        internship=internship, 
        progress_percent=progress_percent,
        weekly_stages=weekly_stages,
        previous_reports=previous_reports
    )

@student_bp.route('/progress/edit/<int:report_id>', methods=['GET', 'POST'])
@role_required('student')
def edit_progress(report_id):
    """
    Allows students to edit a previously submitted progress report if it's not yet approved.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    report = ProgressReport.query.get_or_404(report_id)
    internship = Internship.query.get_or_404(report.internship_id)
    
    # Ownership Security Check (Student data isolation)
    if internship.student_id != student.id:
        abort(403)
        
    # Can only edit if status is 'submitted' or 'rejected'
    if report.status == 'approved':
        flash('Cannot edit an approved progress report.', 'warning')
        return redirect(url_for('student.manage_progress'))
        
    if request.method == 'POST':
        tasks_completed = request.form.get('tasks_completed', '').strip()
        skills_learned = request.form.get('skills_learned', '').strip()
        challenges = request.form.get('challenges', '').strip()
        hours_worked_str = request.form.get('hours_worked', '').strip()
        
        if not tasks_completed or not hours_worked_str:
            flash('Required fields are missing.', 'danger')
            return render_template('student/edit_progress.html', report=report, internship=internship)
            
        try:
            hours_worked = float(hours_worked_str)
        except ValueError:
            flash('Hours worked must be a valid number.', 'danger')
            return render_template('student/edit_progress.html', report=report, internship=internship)
            
        if hours_worked < 0:
            flash('Hours worked cannot be negative.', 'danger')
            return render_template('student/edit_progress.html', report=report, internship=internship)
            
        # Optional file upload update
        file = request.files.get('report_file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filename = f"student_{student.id}_week_{report.week_number}_{int(datetime.now(timezone.utc).timestamp())}_{filename}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            report.report_file = filename
            
        try:
            report.tasks_completed = tasks_completed
            report.skills_learned = skills_learned if skills_learned else None
            report.challenges = challenges if challenges else None
            report.hours_worked = hours_worked
            report.status = 'submitted'
            db.session.commit()
            flash('Weekly report updated successfully.', 'success')
            return redirect(url_for('student.manage_progress'))
        except Exception:
            db.session.rollback()
            flash('An error occurred while updating the report.', 'danger')
            return render_template('student/edit_progress.html', report=report, internship=internship)
            
    return render_template('student/edit_progress.html', report=report, internship=internship)

REQUIRED_DOCUMENTS = [
    "Offer Letter",
    "Joining Letter",
    "ID Proof",
    "Weekly Report",
    "Final Report",
    "Completion Certificate"
]

def check_completion_conditions(internship):
    """
    Verifies if all internship completion conditions are satisfied:
    1. Faculty evaluation exists in database.
    2. All progress reports submitted (if any) are approved (status = 'approved').
    3. All required documents are uploaded and verified (status = 'verified').
    Returns a tuple: (is_satisfied, list_of_missing_reasons)
    """
    missing_reasons = []
    
    # 1. Faculty Evaluation check
    evaluation = Evaluation.query.filter_by(internship_id=internship.id).first()
    if not evaluation:
        missing_reasons.append("Faculty evaluation has not been submitted.")
        
    # 2. All submitted progress reports must be approved
    reports = ProgressReport.query.filter_by(internship_id=internship.id).all()
    for r in reports:
        if r.status != 'approved':
            missing_reasons.append(f"Week {r.week_number} progress report is not approved.")
            
    # 3. All required documents must be uploaded and verified
    for doc_type in REQUIRED_DOCUMENTS:
        doc = Document.query.filter_by(internship_id=internship.id, document_type=doc_type).first()
        if not doc:
            missing_reasons.append(f"Required document '{doc_type}' is missing.")
        elif doc.status != 'verified':
            missing_reasons.append(f"Required document '{doc_type}' is uploaded but not verified.")
            
    return len(missing_reasons) == 0, missing_reasons

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/png',
    'image/jpeg',
    'image/jpg'
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@student_bp.route('/documents', methods=['GET', 'POST'])
@role_required('student')
def manage_documents():
    """
    Renders document list (upload, replace, view, download) and processes file uploads.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        flash('No internship record found. Please register your internship first.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    # GET: Retrieve documents and display table
    documents = Document.query.filter_by(internship_id=internship.id).all()
    docs_map = {doc.document_type: doc for doc in documents}
    doc_count = len(documents)
    
    if request.method == 'POST':
        document_type = request.form.get('document_type', '').strip()
        if document_type not in REQUIRED_DOCUMENTS:
            flash('Invalid document type requested.', 'danger')
            return redirect(url_for('student.manage_documents'))
            
        file = request.files.get('document_file')
        if not file or file.filename == '':
            flash('No file selected for upload.', 'danger')
            return redirect(url_for('student.manage_documents'))
            
        # Validate extension
        filename = file.filename
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            flash('Invalid file extension. Only PDF, DOC, DOCX, PNG, and JPG/JPEG files are allowed.', 'danger')
            return redirect(url_for('student.manage_documents'))
            
        # Validate MIME type
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            flash('Invalid file content type (MIME type). Upload rejected.', 'danger')
            return redirect(url_for('student.manage_documents'))
            
        # Validate File Size
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            flash('File size exceeds the 5MB limit.', 'danger')
            return redirect(url_for('student.manage_documents'))
            
        # Generate safe unique filename
        safe_name = secure_filename(filename)
        # Block executables or double extensions
        if any(exec_ext in safe_name.lower() for exec_ext in ['.exe', '.bat', '.sh', '.py', '.php', '.js']):
            flash('Executable files are not allowed.', 'danger')
            return redirect(url_for('student.manage_documents'))
            
        safe_name = f"student_{student.id}_doc_{document_type.lower().replace(' ', '_')}_{int(datetime.now(timezone.utc).timestamp())}_{safe_name}"
        
        # Save file to upload directory
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], safe_name))
        
        try:
            # Check if document already exists
            existing_doc = docs_map.get(document_type)
            if existing_doc:
                # Replace: Delete old file if exists
                try:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], existing_doc.file_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception:
                    pass
                existing_doc.file_path = safe_name
                existing_doc.status = 'pending'
                existing_doc.uploaded_at = datetime.now(timezone.utc)
            else:
                new_doc = Document(
                    internship_id=internship.id,
                    student_id=student.id,
                    document_type=document_type,
                    file_path=safe_name,
                    status='pending'
                )
                db.session.add(new_doc)
                
            # Mark matching deadlines as completed
            if document_type in ["Final Report", "Completion Certificate"]:
                dl = Deadline.query.filter_by(internship_id=internship.id, title=document_type).first()
                if dl:
                    dl.status = 'completed'
                    dl.completed_at = datetime.now(timezone.utc)
                    
            db.session.commit()
            flash(f'Document {document_type} uploaded successfully.', 'success')
        except Exception:
            db.session.rollback()
            flash('An error occurred during document upload.', 'danger')
            
        return redirect(url_for('student.manage_documents'))
        
    return render_template(
        'student/documents.html', 
        internship=internship, 
        docs_map=docs_map, 
        doc_count=doc_count, 
        required_docs=REQUIRED_DOCUMENTS
    )

@student_bp.route('/documents/download/<int:document_id>')
@role_required('student', 'faculty', 'admin')
def download_document(document_id):
    """
    Securely download a document by matching student ownership and preventing path exposure.
    """
    doc = Document.query.get_or_404(document_id)
    internship = Internship.query.get_or_404(doc.internship_id)
    
    # Ownership Security Check (for students only)
    if session.get('role') == 'student':
        student = Student.query.filter_by(user_id=session['user_id']).first()
        if not student or internship.student_id != student.id:
            abort(403)
        
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], doc.file_path, as_attachment=True)

@student_bp.route('/documents/view/<int:document_id>')
@role_required('student', 'faculty', 'admin')
def view_document(document_id):
    """
    Securely preview/view a document by matching student ownership.
    """
    doc = Document.query.get_or_404(document_id)
    internship = Internship.query.get_or_404(doc.internship_id)
    
    # Ownership Security Check (for students only)
    if session.get('role') == 'student':
        student = Student.query.filter_by(user_id=session['user_id']).first()
        if not student or internship.student_id != student.id:
            abort(403)
        
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], doc.file_path, as_attachment=False)

@student_bp.route('/documents/delete/<int:document_id>', methods=['POST'])
@role_required('student')
def delete_document(document_id):
    """
    Securely delete a document and clean up its filesystem resource.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        abort(403)
        
    doc = Document.query.get_or_404(document_id)
    internship = Internship.query.get_or_404(doc.internship_id)
    
    if internship.student_id != student.id:
        abort(403)
        
    try:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
        
    try:
        db.session.delete(doc)
        db.session.commit()
        flash(f'Document {doc.document_type} deleted successfully.', 'success')
    except Exception:
        db.session.rollback()
        flash('An error occurred during document deletion.', 'danger')
        
    return redirect(url_for('student.manage_documents'))

def get_deadline_status_and_days(deadline):
    """
    Dynamically calculates (status_label, days_remaining) for a deadline.
    """
    if deadline.completed_at is not None or deadline.status == 'completed':
        return "Completed", 0
        
    today = date.today()
    due_date_only = deadline.due_date.date()
    days_remaining = (due_date_only - today).days
    
    if days_remaining > 0:
        return "Pending", days_remaining
    elif days_remaining == 0:
        return "Due Today", 0
    else:
        return "Overdue", days_remaining

def generate_deadlines(internship):
    """
    Automatically creates deadlines for the internship placement.
    """
    d1 = Deadline(
        internship_id=internship.id,
        title="Weekly Progress Log",
        description="Submit your weekly task logging report and hours verification.",
        due_date=datetime.combine(internship.start_date + timedelta(days=14), datetime.min.time()),
        status="pending"
    )
    d2 = Deadline(
        internship_id=internship.id,
        title="Final Report",
        description="Upload your final project report summarizing your internship achievements.",
        due_date=datetime.combine(internship.end_date, datetime.min.time()),
        status="pending"
    )
    d3 = Deadline(
        internship_id=internship.id,
        title="Faculty Evaluation",
        description="Liaise with your supervisor to submit the coordinator grading rubric.",
        due_date=datetime.combine(internship.end_date + timedelta(days=7), datetime.min.time()),
        status="pending"
    )
    d4 = Deadline(
        internship_id=internship.id,
        title="Completion Certificate",
        description="Submit the final signed certificate from the placement organization.",
        due_date=datetime.combine(internship.end_date + timedelta(days=14), datetime.min.time()),
        status="pending"
    )
    
    db.session.add_all([d1, d2, d3, d4])
    db.session.commit()

def check_approaching_deadlines(student_id):
    """
    Dynamically issues notifications if any incomplete deadline is due in <= 3 days.
    """
    student = db.session.get(Student, student_id)
    if not student:
        return
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        return
        
    deadlines = Deadline.query.filter_by(internship_id=internship.id).all()
    today = date.today()
    for dl in deadlines:
        if dl.completed_at is not None or dl.status == 'completed':
            continue
            
        due_date_only = dl.due_date.date()
        days_remaining = (due_date_only - today).days
        
        if 0 <= days_remaining <= 3:
            # Check if matching warning notification exists
            msg = f"Your {dl.title.lower()} is due in {days_remaining} days."
            if days_remaining == 0:
                msg = f"Your {dl.title.lower()} is due today."
                
            existing = Notification.query.filter_by(
                user_id=student.user_id,
                title="Deadline Approaching"
            ).filter(Notification.message.like(f"%{dl.title.lower()}%")).first()
            
            if not existing:
                notif = Notification(
                    user_id=student.user_id,
                    title="Deadline Approaching",
                    message=msg
                )
                db.session.add(notif)
                db.session.commit()

@student_bp.route('/deadlines')
@role_required('student')
def view_deadlines():
    """
    Renders deadlines list with dynamic status badges.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        flash('No internship record found.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    deadlines = Deadline.query.filter_by(internship_id=internship.id).all()
    deadlines_data = []
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
        
    return render_template('student/deadlines.html', internship=internship, deadlines=deadlines_data)

@student_bp.route('/notifications/read/<int:notification_id>', methods=['POST'])
@role_required('student')
def read_notification(notification_id):
    """
    Marks a specific notification as read.
    """
    notif = Notification.query.get_or_404(notification_id)
    if notif.user_id != session['user_id']:
        abort(403)
        
    notif.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for('student.dashboard'))

@student_bp.route('/notifications/read-all', methods=['POST'])
@role_required('student')
def read_all_notifications():
    """
    Marks all notifications for the current student as read.
    """
    notifs = Notification.query.filter_by(user_id=session['user_id'], is_read=False).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for('student.dashboard'))

@student_bp.route('/evaluation')
@role_required('student')
def view_evaluation():
    """
    Renders the read-only placement evaluation scores page for the student.
    """
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        flash('Student record not found.', 'danger')
        return redirect(url_for('main.index'))
        
    internship = Internship.query.filter_by(student_id=student.id).first()
    if not internship:
        flash('No registered internship found.', 'warning')
        return redirect(url_for('student.dashboard'))
        
    evaluation = Evaluation.query.filter_by(internship_id=internship.id).first()
    
    return render_template('student/evaluation.html', student=student, internship=internship, evaluation=evaluation)

@student_bp.app_context_processor
def inject_notifications():
    """
    Jinja global context injector to provide notifications dropdown indicators on all pages.
    """
    if 'user_id' in session and session.get('role') == 'student':
        student = Student.query.filter_by(user_id=session['user_id']).first()
        if student:
            try:
                check_approaching_deadlines(student.id)
            except Exception:
                pass
            notifs = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.created_at.desc()).all()
            unread = sum(1 for n in notifs if not n.is_read)
            return {
                'global_notifications': notifs,
                'unread_notifications_count': unread
            }
    return {
        'global_notifications': [],
        'unread_notifications_count': 0
    }
