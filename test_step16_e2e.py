import unittest
import os
import io
import csv
from datetime import date, datetime, timedelta, timezone
from config import Config
from app import create_app
from database.db import db
from models import User, Student, Faculty, Company, Internship, Evaluation, Document, ProgressReport, TimelineEvent, Deadline, Notification
from werkzeug.security import generate_password_hash

class TestE2EConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    TESTING = True
    SECRET_KEY = 'test-secret-key-e2e-step16'
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'scratch', 'test_e2e_uploads')

class TestStep16EndToEndLifecycle(unittest.TestCase):
    def setUp(self):
        """
        Sets up isolated environment for full lifecycle testing.
        """
        os.makedirs(TestE2EConfig.UPLOAD_FOLDER, exist_ok=True)
        self.app = create_app(TestE2EConfig)
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed initial Admin and Faculty
        self.seed_admin_and_faculty()

    def tearDown(self):
        """
        Cleans up test database and context.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def seed_admin_and_faculty(self):
        hashed = generate_password_hash('Password123!')
        
        # Admin
        self.admin_user = User(name='Placement Dean', email='admin@institution.edu', password_hash=hashed, role='admin')
        db.session.add(self.admin_user)

        # Faculty
        self.faculty_user = User(name='Dr. Alan Turing', email='advisor@institution.edu', password_hash=hashed, role='faculty')
        db.session.add(self.faculty_user)
        db.session.commit()

        self.faculty = Faculty(user_id=self.faculty_user.id, department='Computer Science', employee_id='CS-FAC-01')
        db.session.add(self.faculty)
        db.session.commit()

    def login(self, email, password='Password123!'):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_complete_internship_lifecycle_e2e(self):
        """
        Comprehensive End-to-End lifecycle test:
        1. Student registration & login
        2. Internship application submission
        3. Admin approval & timeline initialization
        4. Progress logging & faculty commenting
        5. Document submission & faculty verification
        6. Faculty evaluation grading
        7. Automatic internship completion
        8. Admin dashboard analytics & reports export
        9. Profile inspection
        """
        # =====================================================================
        # Phase 1: Student Registration & Login
        # =====================================================================
        res_reg = self.client.post('/register', data={
            'role': 'student',
            'name': 'Ada Lovelace',
            'email': 'ada@institution.edu',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'roll_no': 'CS-2026-001',
            'course': 'B.Tech CSE',
            'semester': '6',
            'phone': '555-0199'
        }, follow_redirects=True)
        self.assertEqual(res_reg.status_code, 200)
        self.assertIn(b'Registration successful', res_reg.data)

        # Student logs in
        res_login = self.login('ada@institution.edu')
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b'Welcome back, Ada Lovelace', res_login.data)

        # Access student dashboard (empty placement state)
        res_dash = self.client.get('/student/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b'Register Internship', res_dash.data)

        # =====================================================================
        # Phase 2: Internship Registration
        # =====================================================================
        start_date = date.today()
        end_date = date.today() + timedelta(days=90)

        res_int_reg = self.client.post('/student/internship', data={
            'company': 'Quantum Dynamics Inc',
            'company_address': '100 Tech Park, Cambridge',
            'company_contact': 'Grace Hopper',
            'role': 'Quantum Algorithms Intern',
            'description': 'Researching quantum algorithms and high performance architectures.',
            'start_date': str(start_date),
            'end_date': str(end_date),
            'internship_type': 'hybrid',
            'supervisor_name': 'Grace Hopper',
            'supervisor_email': 'grace@quantumdynamics.com',
            'supervisor_phone': '555-0200'
        }, follow_redirects=True)
        self.assertEqual(res_int_reg.status_code, 200)
        self.assertIn(b'Internship submitted successfully', res_int_reg.data)

        student = Student.query.filter_by(roll_no='CS-2026-001').first()
        self.assertIsNotNone(student)
        internship = Internship.query.filter_by(student_id=student.id).first()
        self.assertIsNotNone(internship)
        self.assertEqual(internship.status, 'pending')
        self.logout()

        # =====================================================================
        # Phase 3: Admin Approval & Timeline / Deadlines Generation
        # =====================================================================
        self.login('admin@institution.edu')
        res_admin_int = self.client.get('/admin/internships')
        self.assertEqual(res_admin_int.status_code, 200)
        self.assertIn(b'Quantum Dynamics Inc', res_admin_int.data)

        # Admin approves placement
        res_app = self.client.post(f'/admin/internships/approve/{internship.id}', follow_redirects=True)
        self.assertEqual(res_app.status_code, 200)
        self.assertIn(b'approved successfully', res_app.data)

        # Verify timeline events and deadlines are created
        events = TimelineEvent.query.filter_by(internship_id=internship.id).all()
        self.assertGreater(len(events), 0)
        deadlines = Deadline.query.filter_by(internship_id=internship.id).all()
        self.assertGreater(len(deadlines), 0)
        self.logout()

        # =====================================================================
        # Phase 4: Student Timeline & Progress Submission
        # =====================================================================
        self.login('ada@institution.edu')
        
        # Verify timeline view
        res_timeline = self.client.get('/student/timeline')
        self.assertEqual(res_timeline.status_code, 200)
        self.assertIn(b'Internship Timeline Journey', res_timeline.data)

        # Submit progress report for Week 1
        rep_file = (io.BytesIO(b'%PDF-1.4 Week 1 Progress Notes'), 'week1_notes.pdf')
        res_prog = self.client.post('/student/progress', data={
            'week_number': '1',
            'tasks_completed': 'Completed quantum circuit simulation framework setup and benchmarking.',
            'skills_learned': 'Qiskit, Python MPI, Superconducting qubit topologies.',
            'challenges': 'Optimizing decoherence time simulations.',
            'hours_worked': '40.0',
            'report_file': rep_file
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_prog.status_code, 200)
        self.assertIn(b'Weekly report for Week 1 submitted', res_prog.data)

        # Edit progress report
        report = ProgressReport.query.filter_by(internship_id=internship.id, week_number=1).first()
        self.assertIsNotNone(report)
        res_edit_prog = self.client.post(f'/student/progress/edit/{report.id}', data={
            'tasks_completed': 'Completed quantum circuit simulation framework setup and benchmarking (Refined).',
            'skills_learned': 'Qiskit, Python MPI, Superconducting qubit topologies.',
            'challenges': 'Optimizing decoherence time simulations.',
            'hours_worked': '42.0'
        }, follow_redirects=True)
        self.assertEqual(res_edit_prog.status_code, 200)
        self.assertIn(b'Weekly report updated successfully', res_edit_prog.data)
        self.logout()

        # Faculty reviews and comments on progress report
        self.login('advisor@institution.edu')
        res_comment = self.client.post(f'/faculty/progress/comment/{report.id}', data={
            'feedback': 'Exceptional weekly progress. Thorough analysis of qubit decoherence.'
        }, follow_redirects=True)
        self.assertEqual(res_comment.status_code, 200)
        self.assertIn(b'Feedback submitted successfully', res_comment.data)
        self.logout()

        # =====================================================================
        # Phase 5: Document Uploads & Faculty Verification
        # =====================================================================
        self.login('ada@institution.edu')
        docs_to_upload = [
            ("Offer Letter", "offer_letter.pdf", b'%PDF-1.4 Official Offer Letter'),
            ("Joining Letter", "joining_letter.pdf", b'%PDF-1.4 Official Joining Letter'),
            ("ID Proof", "id_proof.pdf", b'%PDF-1.4 Student Identity Card'),
            ("Weekly Report", "weekly_report_doc.pdf", b'%PDF-1.4 Compiled Weekly Log'),
            ("Final Report", "final_internship_report.pdf", b'%PDF-1.4 Comprehensive Final Report'),
            ("Completion Certificate", "completion_certificate.pdf", b'%PDF-1.4 Corporate Certificate')
        ]
        for doc_type, fname, content in docs_to_upload:
            upload_file = (io.BytesIO(content), fname)
            res_doc = self.client.post('/student/documents', data={
                'document_type': doc_type,
                'document_file': upload_file
            }, content_type='multipart/form-data', follow_redirects=True)
            self.assertEqual(res_doc.status_code, 200)
            self.assertIn(b'uploaded successfully', res_doc.data)
        self.logout()

        # Faculty verifies all 6 documents
        self.login('advisor@institution.edu')
        student_docs = Document.query.filter_by(internship_id=internship.id).all()
        self.assertEqual(len(student_docs), 6)
        for d in student_docs:
            res_verify = self.client.post(f'/faculty/document/verify/{d.id}', follow_redirects=True)
            self.assertEqual(res_verify.status_code, 200)

        # =====================================================================
        # Phase 6: Faculty Evaluation Submission
        # =====================================================================
        res_eval = self.client.post(f'/faculty/evaluation/{student.id}', data={
            'technical_skills': '10',
            'communication': '9',
            'punctuality': '10',
            'work_quality': '10',
            'discipline': '10',
            'feedback': 'Exemplary performance. Pioneering contributions to quantum algorithms.'
        }, follow_redirects=True)
        self.assertEqual(res_eval.status_code, 200)
        self.assertIn(b'submitted successfully', res_eval.data)

        # Verify evaluation record and score
        eval_record = Evaluation.query.filter_by(internship_id=internship.id).first()
        self.assertIsNotNone(eval_record)
        self.assertEqual(eval_record.overall_score, 9.8)

        # Refresh internship: Should be marked 'completed' because all conditions are met!
        db.session.refresh(internship)
        self.assertEqual(internship.status, 'completed')
        self.logout()

        # =====================================================================
        # Phase 7: Student Evaluation View & Profile Inspection
        # =====================================================================
        self.login('ada@institution.edu')
        res_stu_eval = self.client.get('/student/evaluation')
        self.assertEqual(res_stu_eval.status_code, 200)
        self.assertIn(b'9.8', res_stu_eval.data)
        self.assertIn(b'Exemplary performance', res_stu_eval.data)

        # View profile
        res_prof = self.client.get('/profile')
        self.assertEqual(res_prof.status_code, 200)
        self.assertIn(b'Ada Lovelace', res_prof.data)
        self.assertIn(b'CS-2026-001', res_prof.data)
        self.assertIn(b'Quantum Dynamics Inc', res_prof.data)
        self.logout()

        # =====================================================================
        # Phase 8: Admin Dashboard Analytics & Reports Export
        # =====================================================================
        self.login('admin@institution.edu')
        res_adm_dash = self.client.get('/admin/dashboard')
        self.assertEqual(res_adm_dash.status_code, 200)
        self.assertIn(b'100.0%', res_adm_dash.data) # 100% completion rate
        self.assertIn(b'Quantum Dynamics Inc', res_adm_dash.data)
        self.assertIn(b'9.8', res_adm_dash.data) # Avg eval score

        # Access Reports Console
        res_reports = self.client.get('/admin/reports')
        self.assertEqual(res_reports.status_code, 200)
        self.assertIn(b'Placement Reports & Data Export', res_reports.data)

        # Export CSV & PDF for Completion Report
        res_csv = self.client.get('/admin/reports/export/completion/csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn('Quantum Dynamics Inc', res_csv.get_data(as_text=True))
        self.assertIn('Completed', res_csv.get_data(as_text=True))

        res_pdf = self.client.get('/admin/reports/export/completion/pdf')
        self.assertEqual(res_pdf.status_code, 200)
        self.assertTrue(res_pdf.data.startswith(b'%PDF-1.'))
        self.assertGreater(len(res_pdf.data), 1500)

        # View Admin Profile
        res_adm_prof = self.client.get('/profile')
        self.assertEqual(res_adm_prof.status_code, 200)
        self.assertIn(b'Placement Dean', res_adm_prof.data)
        self.assertIn(b'admin Account', res_adm_prof.data)
        self.logout()

if __name__ == '__main__':
    unittest.main()
