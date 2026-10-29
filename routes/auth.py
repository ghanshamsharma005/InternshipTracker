import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from database.db import db
from models import User, Student, Faculty

auth_bp = Blueprint('auth', __name__)

def _sanitize_error_message(msg: str) -> str:
    """
    Sanitizes database error messages to prevent credential leakage.
    Masks passwords in database connection strings and parameters.
    """
    if not isinstance(msg, str):
        msg = str(msg)
    # Mask passwords in connection strings like postgresql://user:password@host:port/db
    msg = re.sub(r'(://[^:]+:)([^@]+)(@)', r'\1***\3', msg)
    # Mask password key-value parameters
    msg = re.sub(r'(password[\'\"]?\s*[:=]\s*[\'\"]?)[^\'\"]+', r'\1***', msg, flags=re.IGNORECASE)
    return msg

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles Student and Faculty registrations, mapping them to correct database profiles.
    """
    if 'user_id' in session:
        return redirect_to_dashboard(session.get('role'))
        
    if request.method == 'POST':
        role = request.form.get('role', 'student').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Base validation
        if not all([name, email, password, confirm_password]):
            flash('All base fields are required.', 'danger')
            return render_template('register.html', form_data=request.form)
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', form_data=request.form)
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please sign in or use a different email.', 'danger')
            return render_template('register.html', form_data=request.form)
            
        # Role-specific fields and validation
        if role == 'faculty':
            employee_id = request.form.get('employee_id', '').strip()
            department = request.form.get('department', '').strip()
            
            if not all([employee_id, department]):
                flash('Please fill in all Faculty fields.', 'danger')
                return render_template('register.html', form_data=request.form)
                
            if Faculty.query.filter_by(employee_id=employee_id).first():
                flash('Employee ID already registered.', 'danger')
                return render_template('register.html', form_data=request.form)
        else:
            roll_no = request.form.get('roll_no', '').strip()
            course = request.form.get('course', '').strip()
            semester = request.form.get('semester', '').strip()
            phone = request.form.get('phone', '').strip()
            
            if not all([roll_no, course, semester]):
                flash('Please fill in all Student fields.', 'danger')
                return render_template('register.html', form_data=request.form)
                
            try:
                semester = int(semester)
            except ValueError:
                flash('Semester must be a valid number.', 'danger')
                return render_template('register.html', form_data=request.form)
                
            if Student.query.filter_by(roll_no=roll_no).first():
                flash('Roll number already registered.', 'danger')
                return render_template('register.html', form_data=request.form)
                
        try:
            # Create user
            new_user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role=role
            )
            db.session.add(new_user)
            db.session.flush()
            
            if role == 'faculty':
                new_faculty = Faculty(
                    user_id=new_user.id,
                    employee_id=employee_id,
                    department=department
                )
                db.session.add(new_faculty)
            else:
                new_student = Student(
                    user_id=new_user.id,
                    roll_no=roll_no,
                    course=course,
                    semester=semester,
                    phone=phone if phone else None
                )
                db.session.add(new_student)
                
            db.session.commit()
            flash('Registration successful! Please log in with your credentials.', 'success')
            return redirect(url_for('auth.login'))
        except IntegrityError as e:
            db.session.rollback()
            current_app.logger.warning(
                "Registration failed due to database unique constraint / integrity violation [role=%s, email=%s]: %s",
                role, email, _sanitize_error_message(str(e))
            )
            flash('A user or record with these details already exists. Please verify your email, roll number, or employee ID.', 'danger')
            return render_template('register.html', form_data=request.form)
        except OperationalError as e:
            db.session.rollback()
            err_str = str(e).lower()
            if 'readonly' in err_str or 'attempt to write a readonly database' in err_str or 'unable to open database file' in err_str:
                current_app.logger.error(
                    "Registration failed: SQLite database write permission error. "
                    "The serverless filesystem is read-only (standard behavior on Vercel). "
                    "To fix this, connect a hosted PostgreSQL database by configuring the DATABASE_URL environment variable in your Vercel project settings. "
                    "Exception details: %s",
                    _sanitize_error_message(str(e)),
                    exc_info=True
                )
            else:
                current_app.logger.error(
                    "Registration failed due to database operational/connection error [role=%s, email=%s]: %s",
                    role, email, _sanitize_error_message(str(e)),
                    exc_info=True
                )
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html', form_data=request.form)
        except ProgrammingError as e:
            db.session.rollback()
            current_app.logger.error(
                "Registration failed due to missing database table or schema error [role=%s, email=%s]. "
                "Ensure database tables have been created (e.g., db.create_all() or migrations). Exception details: %s",
                role, email, _sanitize_error_message(str(e)),
                exc_info=True
            )
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html', form_data=request.form)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                "Registration failed with unexpected exception [role=%s, email=%s]: %s: %s",
                role, email, type(e).__name__, _sanitize_error_message(str(e)),
                exc_info=True
            )
            flash('An error occurred during registration. Please try again.', 'danger')
            return render_template('register.html', form_data=request.form)
            
    return render_template('register.html', form_data={})

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Validates user credentials and logs them in, storing attributes inside session keys.
    """
    if 'user_id' in session:
        return redirect_to_dashboard(session.get('role'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html', email=email)
            
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if not getattr(user, 'is_active', True):
                flash('Your account has been deactivated. Please contact admin.', 'danger')
                return render_template('login.html', email=email)
                
            session['user_id'] = user.id
            session['role'] = user.role
            session['user_name'] = user.name
            
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect_to_dashboard(user.role)
        else:
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', email=email)
            
    return render_template('login.html', email='')

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Wipes the session values and redirects to the index route.
    """
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))

from routes.decorators import login_required
from models import Internship

@auth_bp.route('/profile')
@login_required
def profile():
    """
    Renders the authenticated user's profile with role-specific details.
    """
    user = db.session.get(User, session['user_id'])
    if not user:
        flash('User account not found.', 'danger')
        return redirect(url_for('auth.login'))
        
    student = None
    faculty = None
    internship = None
    
    if user.role == 'student':
        student = Student.query.filter_by(user_id=user.id).first()
        if student:
            internship = Internship.query.filter_by(student_id=student.id).first()
    elif user.role == 'faculty':
        faculty = Faculty.query.filter_by(user_id=user.id).first()
        
    return render_template('profile.html', user=user, student=student, faculty=faculty, internship=internship)

import io
from datetime import datetime, timezone
from flask import Response, send_file
from models import UserProfileImage

@auth_bp.route('/user/image/<int:user_id>')
def get_user_image(user_id):
    """
    Streams raw binary image bytes (BLOB) directly from the database for the given user.
    Falls back to a clean default SVG avatar if no custom image is stored.
    """
    img = UserProfileImage.query.filter_by(user_id=user_id).first()
    if img and img.image_data:
        return send_file(
            io.BytesIO(img.image_data),
            mimetype=img.mimetype,
            as_attachment=False,
            download_name=img.filename
        )
    
    # Return SVG avatar placeholder if no image stored
    svg_placeholder = """<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="background:#0f172a;border-radius:50%;">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
        <circle cx="12" cy="7" r="4"></circle>
    </svg>"""
    return Response(svg_placeholder, mimetype='image/svg+xml')

@auth_bp.route('/profile/upload-image', methods=['POST'])
@login_required
def upload_profile_image():
    """
    Reads an uploaded image file as raw binary bytes and persists it directly
    into the SQLite database via a LargeBinary (BLOB) column.
    """
    if 'profile_image' not in request.files:
        flash('No file selected.', 'warning')
        return redirect(url_for('auth.profile'))
        
    file = request.files['profile_image']
    if not file or file.filename == '':
        flash('No file selected.', 'warning')
        return redirect(url_for('auth.profile'))
        
    allowed_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_exts:
        flash('Allowed image types are PNG, JPG, JPEG, GIF, and WEBP.', 'danger')
        return redirect(url_for('auth.profile'))
        
    image_bytes = file.read()
    if len(image_bytes) > 2 * 1024 * 1024:  # 2MB max for database BLOB storage
        flash('Image file size must be less than 2MB for database storage.', 'danger')
        return redirect(url_for('auth.profile'))

    mimetype = file.mimetype or f'image/{ext}'
    user_id = session['user_id']

    try:
        existing = UserProfileImage.query.filter_by(user_id=user_id).first()
        if existing:
            existing.filename = file.filename
            existing.mimetype = mimetype
            existing.image_data = image_bytes
            existing.uploaded_at = datetime.now(timezone.utc)
        else:
            new_img = UserProfileImage(
                user_id=user_id,
                filename=file.filename,
                mimetype=mimetype,
                image_data=image_bytes  # Directly storing raw bytes into SQLite BLOB
            )
            db.session.add(new_img)
            
        db.session.commit()
        flash('Profile image stored successfully in the database (BLOB)!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            "Failed to store profile image in database [user_id=%s]: %s: %s",
            user_id, type(e).__name__, _sanitize_error_message(str(e)),
            exc_info=True
        )
        flash('Failed to store image in database.', 'danger')
        
    return redirect(url_for('auth.profile'))

@auth_bp.route('/profile/delete-image', methods=['POST'])
@login_required
def delete_profile_image():
    """
    Removes the user's stored image BLOB from the database.
    """
    img = UserProfileImage.query.filter_by(user_id=session['user_id']).first()
    if img:
        try:
            db.session.delete(img)
            db.session.commit()
            flash('Profile image removed from database.', 'info')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                "Failed to remove profile image from database [user_id=%s]: %s: %s",
                session.get('user_id'), type(e).__name__, _sanitize_error_message(str(e)),
                exc_info=True
            )
            flash('Failed to remove image from database.', 'danger')
    return redirect(url_for('auth.profile'))

def redirect_to_dashboard(role):
    """
    Helpers to redirect a user based on their specific authorization group.
    """
    if role == 'student':
        return redirect(url_for('student.dashboard'))
    elif role == 'faculty':
        return redirect(url_for('faculty.dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('main.index'))


