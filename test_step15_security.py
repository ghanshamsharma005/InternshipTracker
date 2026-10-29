import unittest
import os
import io
from datetime import date, datetime, timedelta, timezone
from config import Config
from app import create_app
from database.db import db
from models import User, Student, Faculty, Company, Internship, Evaluation, Document, ProgressReport, TimelineEvent, Notification
from werkzeug.security import generate_password_hash, check_password_hash

class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    TESTING = True
    SECRET_KEY = 'test-secret-key-security-step15'
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'scratch', 'test_uploads')

class TestStep15SecurityAudit(unittest.TestCase):
    def setUp(self):
        """
        Creates isolated in-memory test database and environment.
        """
        os.makedirs(TestConfig.UPLOAD_FOLDER, exist_ok=True)
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.setup_users_and_records()

    def tearDown(self):
        """
        Closes context and drops tables.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_users_and_records(self):
        hashed = generate_password_hash('StrongAuthPass123!')
        
        # 1. Admin
        self.user_admin = User(name='Admin User', email='admin@sec.com', password_hash=hashed, role='admin', is_active=True)
        
        # 2. Faculty
        self.user_faculty = User(name='Faculty User', email='faculty@sec.com', password_hash=hashed, role='faculty', is_active=True)
        
        # 3. Student 1 & Student 2
        self.user_student1 = User(name='Student One', email='student1@sec.com', password_hash=hashed, role='student', is_active=True)
        self.user_student2 = User(name='Student Two', email='student2@sec.com', password_hash=hashed, role='student', is_active=True)
        
        # 4. Deactivated Student
        self.user_deactivated = User(name='Deactivated User', email='deactivated@sec.com', password_hash=hashed, role='student', is_active=False)
        
        db.session.add_all([self.user_admin, self.user_faculty, self.user_student1, self.user_student2, self.user_deactivated])
        db.session.commit()

        self.faculty = Faculty(user_id=self.user_faculty.id, department='CS', employee_id='EMP-001')
        self.student1 = Student(user_id=self.user_student1.id, roll_no='STU-001', course='B.Tech CSE', semester=6)
        self.student2 = Student(user_id=self.user_student2.id, roll_no='STU-002', course='B.Tech ECE', semester=6)
        self.student_deact = Student(user_id=self.user_deactivated.id, roll_no='STU-DEACT', course='B.Tech CSE', semester=6)
        
        self.company = Company(company_name='SecureTech Solutions')
        db.session.add_all([self.faculty, self.student1, self.student2, self.student_deact, self.company])
        db.session.commit()

        # Internships
        self.internship1 = Internship(
            student_id=self.student1.id,
            company_id=self.company.id,
            role='Software Intern',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            status='active'
        )
        self.internship2 = Internship(
            student_id=self.student2.id,
            company_id=self.company.id,
            role='Hardware Intern',
            start_date=date(2026, 2, 1),
            end_date=date(2026, 5, 1),
            status='active'
        )
        db.session.add_all([self.internship1, self.internship2])
        db.session.commit()

        # Timeline Event for Student 2
        self.event2 = TimelineEvent(internship_id=self.internship2.id, title='Week 1 Progress', status='in_progress', event_date=datetime.now(timezone.utc))
        db.session.add(self.event2)

        # Progress Report for Student 2
        self.report2 = ProgressReport(
            internship_id=self.internship2.id,
            student_id=self.student2.id,
            week_number=1,
            tasks_completed='Tasks for student 2',
            skills_learned='Skills',
            hours_worked=40.0,
            status='submitted',
            report_file='student_2_rep_w1.pdf'
        )
        db.session.add(self.report2)

        # Document for Student 2
        self.doc2 = Document(
            internship_id=self.internship2.id,
            student_id=self.student2.id,
            document_type='Offer Letter',
            file_path='student_2_doc_offer.pdf',
            status='pending'
        )
        db.session.add(self.doc2)

        # Notification for Student 2
        self.notif2 = Notification(
            user_id=self.user_student2.id,
            title='Confidential Alert',
            message='Alert only for Student 2'
        )
        db.session.add(self.notif2)
        db.session.commit()

        # Create dummy files in uploads directory for test
        upload_folder = self.app.config['UPLOAD_FOLDER']
        with open(os.path.join(upload_folder, 'student_2_doc_offer.pdf'), 'w') as f:
            f.write('Student 2 Offer Letter Content')
        with open(os.path.join(upload_folder, 'student_2_rep_w1.pdf'), 'w') as f:
            f.write('Student 2 Progress Report Content')

    def login(self, email, password='StrongAuthPass123!'):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # =========================================================================
    # 1. Authentication & Session Security Tests
    # =========================================================================
    def test_password_hashing_and_security(self):
        """
        Verifies passwords are never stored in plaintext and use strong hashing.
        """
        user = User.query.filter_by(email='student1@sec.com').first()
        self.assertNotEqual(user.password_hash, 'StrongAuthPass123!')
        self.assertTrue(user.password_hash.startswith(('scrypt:', 'pbkdf2:')))
        self.assertTrue(check_password_hash(user.password_hash, 'StrongAuthPass123!'))
        self.assertFalse(check_password_hash(user.password_hash, 'WrongPassword!'))

    def test_session_cleared_on_logout(self):
        """
        Verifies session values are wiped when user logs out.
        """
        self.login('student1@sec.com')
        # Access protected page
        res = self.client.get('/student/dashboard')
        self.assertEqual(res.status_code, 200)

        # Logout
        self.logout()
        res_after = self.client.get('/student/dashboard')
        self.assertEqual(res_after.status_code, 302)
        self.assertIn('/login', res_after.headers['Location'])

    def test_deactivated_account_access_blocked(self):
        """
        Verifies deactivated accounts cannot log in and active sessions are terminated.
        """
        # 1. Attempt login with deactivated credentials
        res = self.login('deactivated@sec.com')
        self.assertIn(b'account has been deactivated', res.data)

        # 2. Deactivate an active student and attempt access with active session
        self.login('student1@sec.com')
        # Admin deactivates student 1
        user1 = User.query.filter_by(email='student1@sec.com').first()
        user1.is_active = False
        db.session.commit()

        res_blocked = self.client.get('/student/dashboard')
        self.assertEqual(res_blocked.status_code, 302)
        self.assertIn('/login', res_blocked.headers['Location'])

    # =========================================================================
    # 2. Authorization & Role Separation Tests
    # =========================================================================
    def test_role_separation_boundaries(self):
        """
        Tests strict role boundaries:
        - Student -> Faculty routes (403)
        - Student -> Admin routes (403)
        - Faculty -> Admin routes (403)
        """
        # Student attempting Faculty & Admin routes
        self.login('student1@sec.com')
        self.assertEqual(self.client.get('/faculty/dashboard').status_code, 403)
        self.assertEqual(self.client.get('/faculty/students').status_code, 403)
        self.assertEqual(self.client.get('/admin/dashboard').status_code, 403)
        self.assertEqual(self.client.get('/admin/reports').status_code, 403)
        self.assertEqual(self.client.get('/admin/students').status_code, 403)
        self.logout()

        # Faculty attempting Admin routes
        self.login('faculty@sec.com')
        self.assertEqual(self.client.get('/admin/dashboard').status_code, 403)
        self.assertEqual(self.client.get('/admin/reports').status_code, 403)
        self.assertEqual(self.client.get('/admin/companies').status_code, 403)
        self.logout()

    # =========================================================================
    # 3. Data Isolation (IDOR) Tests
    # =========================================================================
    def test_cross_student_data_isolation(self):
        """
        Verifies Student 1 cannot view, edit, download, or delete Student 2's data.
        """
        self.login('student1@sec.com')

        # 1. Internship details IDOR
        res_int = self.client.get(f'/student/internship/{self.internship2.id}/details')
        self.assertEqual(res_int.status_code, 403)

        # 2. Document view & download IDOR
        res_doc_view = self.client.get(f'/student/documents/view/{self.doc2.id}')
        self.assertEqual(res_doc_view.status_code, 403)

        res_doc_dl = self.client.get(f'/student/documents/download/{self.doc2.id}')
        self.assertEqual(res_doc_dl.status_code, 403)

        # 3. Document delete IDOR
        res_doc_del = self.client.post(f'/student/documents/delete/{self.doc2.id}')
        self.assertEqual(res_doc_del.status_code, 403)

        # 4. Progress report edit IDOR
        res_rep_edit = self.client.get(f'/student/progress/edit/{self.report2.id}')
        self.assertEqual(res_rep_edit.status_code, 403)

        # 5. Timeline report submit IDOR
        res_time_sub = self.client.get(f'/student/timeline/report/submit/{self.event2.id}')
        self.assertEqual(res_time_sub.status_code, 403)

        # 6. Direct /uploads/<filename> IDOR
        res_upload = self.client.get('/uploads/student_2_doc_offer.pdf')
        self.assertEqual(res_upload.status_code, 403)

        # 7. Notification read IDOR
        res_notif = self.client.post(f'/student/notifications/read/{self.notif2.id}')
        self.assertEqual(res_notif.status_code, 403)

        self.logout()

    # =========================================================================
    # 4. Form & Input Validation Tests
    # =========================================================================
    def test_registration_validation(self):
        """
        Tests registration form validation against invalid/duplicate inputs.
        """
        # Passwords mismatch
        res_mismatch = self.client.post('/register', data={
            'name': 'New Student',
            'email': 'new@test.com',
            'password': 'Password123',
            'confirm_password': 'DifferentPassword456',
            'role': 'student',
            'roll_no': 'NEW-001',
            'course': 'CSE',
            'semester': '6'
        })
        self.assertIn(b'Passwords do not match', res_mismatch.data)

        # Duplicate email
        res_dup_email = self.client.post('/register', data={
            'name': 'Duplicate Email',
            'email': 'student1@sec.com',
            'password': 'Password123',
            'confirm_password': 'Password123',
            'role': 'student',
            'roll_no': 'UNIQUE-001',
            'course': 'CSE',
            'semester': '6'
        })
        self.assertIn(b'Email already registered', res_dup_email.data)

        # Duplicate roll number
        res_dup_roll = self.client.post('/register', data={
            'name': 'Duplicate Roll',
            'email': 'uniquemail@test.com',
            'password': 'Password123',
            'confirm_password': 'Password123',
            'role': 'student',
            'roll_no': 'STU-001',
            'course': 'CSE',
            'semester': '6'
        })
        self.assertIn(b'Roll number already registered', res_dup_roll.data)

    def test_faculty_evaluation_rubric_boundaries(self):
        """
        Tests faculty evaluation form rejection of negative or >10 scores.
        """
        self.login('faculty@sec.com')

        # Score > 10
        res_high = self.client.post(f'/faculty/evaluation/{self.student1.id}', data={
            'technical_skills': '15',
            'communication': '8',
            'punctuality': '8',
            'work_quality': '8',
            'discipline': '8',
            'feedback': 'Good'
        })
        self.assertIn(b'must be between 0 and 10', res_high.data)

        # Negative score
        res_neg = self.client.post(f'/faculty/evaluation/{self.student1.id}', data={
            'technical_skills': '-2',
            'communication': '8',
            'punctuality': '8',
            'work_quality': '8',
            'discipline': '8',
            'feedback': 'Good'
        })
        self.assertIn(b'must be between 0 and 10', res_neg.data)
        self.logout()

    # =========================================================================
    # 5. File Upload Security Tests
    # =========================================================================
    def test_file_upload_security_filters(self):
        """
        Tests that executable files and disallowed MIME types are rejected.
        """
        self.login('student1@sec.com')

        # Executable file (.exe)
        exe_file = (io.BytesIO(b'MZ executable payload'), 'malware.exe')
        res_exe = self.client.post('/student/documents', data={
            'document_type': 'Offer Letter',
            'document_file': exe_file
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Invalid file extension', res_exe.data)

        # Script file (.py)
        py_file = (io.BytesIO(b'import os; os.system("calc")'), 'script.py')
        res_py = self.client.post('/student/documents', data={
            'document_type': 'Offer Letter',
            'document_file': py_file
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn(b'Invalid file extension', res_py.data)

        self.logout()

    def test_path_traversal_protection_on_uploads(self):
        """
        Tests that path traversal queries (e.g. /uploads/../../etc/passwd) are aborted.
        """
        self.login('student1@sec.com')
        res_traversal = self.client.get('/uploads/..%2F..%2Fconfig.py')
        self.assertIn(res_traversal.status_code, [400, 403, 404])
        self.logout()

    # =========================================================================
    # 6. HTTP Security Headers Tests
    # =========================================================================
    def test_security_headers_present(self):
        """
        Verifies required HTTP security headers are injected in responses.
        """
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(res.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(res.headers.get('X-XSS-Protection'), '1; mode=block')
        self.assertEqual(res.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')
        self.assertIn('default-src', res.headers.get('Content-Security-Policy', ''))

if __name__ == '__main__':
    unittest.main()
