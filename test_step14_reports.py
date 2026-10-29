import unittest
import csv
import io
from datetime import date, datetime, timedelta, timezone
from app import create_app
from database.db import db
from models import User, Student, Faculty, Company, Internship, Evaluation
from werkzeug.security import generate_password_hash

class TestStep14Reports(unittest.TestCase):
    def setUp(self):
        """
        Creates isolated in-memory test database and environment.
        """
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test-secret-key-step14'
        self.client = self.app.test_client()
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.setup_users_and_data()

    def tearDown(self):
        """
        Closes context and drops tables.
        """
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_users_and_data(self):
        self.secret_hash = generate_password_hash('SecretPassword999!')
        
        # Admin User
        self.user_admin = User(name='Admin Officer', email='admin@test.com', password_hash=self.secret_hash, role='admin')
        
        # Student 1 (CSE) & Student 2 (ECE)
        self.user_s1 = User(name='Alice Wonder', email='alice@test.com', password_hash=self.secret_hash, role='student')
        self.user_s2 = User(name='Bob Builder', email='bob@test.com', password_hash=self.secret_hash, role='student')
        
        # Faculty User
        self.user_f = User(name='Dr. Evaluation Head', email='faculty@test.com', password_hash=self.secret_hash, role='faculty')
        
        db.session.add_all([self.user_admin, self.user_s1, self.user_s2, self.user_f])
        db.session.commit()
        
        self.student1 = Student(user_id=self.user_s1.id, roll_no='CSE-001', course='B.Tech CSE', semester=6, phone='555-0101')
        self.student2 = Student(user_id=self.user_s2.id, roll_no='ECE-002', course='B.Tech ECE', semester=6, phone='555-0202')
        self.faculty = Faculty(user_id=self.user_f.id, department='Computer Science', employee_id='FAC-777')
        
        self.company_tech = Company(company_name='TechCorp Global', contact_person='Jane Doe', email='hr@techcorp.com', phone='555-9999', industry='Software')
        self.company_auto = Company(company_name='AutoDynamics', contact_person='John Smith', email='careers@autodynamics.com', phone='555-8888', industry='Automotive')
        
        db.session.add_all([self.student1, self.student2, self.faculty, self.company_tech, self.company_auto])
        db.session.commit()

        # Placements
        self.internship1 = Internship(
            student_id=self.student1.id,
            company_id=self.company_tech.id,
            role='Full Stack Intern',
            start_date=date(2026, 1, 10),
            end_date=date(2026, 3, 10),
            status='completed'
        )
        self.internship2 = Internship(
            student_id=self.student2.id,
            company_id=self.company_auto.id,
            role='Embedded Systems Intern',
            start_date=date(2026, 2, 1),
            end_date=date(2026, 5, 1),
            status='active'
        )
        self.internship3 = Internship(
            student_id=self.student1.id,
            company_id=self.company_tech.id,
            role='DevOps Intern',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 1),
            status='pending'
        )
        db.session.add_all([self.internship1, self.internship2, self.internship3])
        db.session.commit()

        # Faculty Evaluation on Internship 1
        self.evaluation1 = Evaluation(
            internship_id=self.internship1.id,
            student_id=self.student1.id,
            faculty_id=self.faculty.id,
            technical_skills=9,
            communication=8,
            punctuality=10,
            work_quality=9,
            discipline=9,
            overall_score=9.0,
            feedback='Outstanding engineering excellence demonstrated.'
        )
        db.session.add(self.evaluation1)
        db.session.commit()

    def login(self, email, password='SecretPassword999!'):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_access_control_reports(self):
        """
        Tests role authorization on /admin/reports and /admin/reports/export.
        """
        # 1. Guest -> redirect to /login
        res_guest = self.client.get('/admin/reports')
        self.assertEqual(res_guest.status_code, 302)
        self.assertIn('/login', res_guest.headers['Location'])

        res_guest_export = self.client.get('/admin/reports/export/completion/csv')
        self.assertEqual(res_guest_export.status_code, 302)

        # 2. Student -> 403 Forbidden
        self.login('alice@test.com')
        res_student = self.client.get('/admin/reports')
        self.assertEqual(res_student.status_code, 403)
        res_student_export = self.client.get('/admin/reports/export/completion/csv')
        self.assertEqual(res_student_export.status_code, 403)
        self.logout()

        # 3. Faculty -> 403 Forbidden
        self.login('faculty@test.com')
        res_faculty = self.client.get('/admin/reports')
        self.assertEqual(res_faculty.status_code, 403)
        self.logout()

        # 4. Admin -> 200 OK
        self.login('admin@test.com')
        res_admin = self.client.get('/admin/reports')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'Placement Reports', res_admin.data)

    def test_reports_overview_metrics_display(self):
        """
        Verifies that the /admin/reports page displays all required database KPIs:
        Total students, Total internships, Active, Completed, Pending, Completion rate, Avg eval score.
        """
        self.login('admin@test.com')
        response = self.client.get('/admin/reports')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        # Total students = 2
        self.assertIn('TOTAL STUDENTS', html)
        self.assertIn('2', html)

        # Total internships = 3
        self.assertIn('TOTAL PLACEMENTS', html)
        self.assertIn('3', html)

        # Active = 1, Completed = 1, Pending = 1
        self.assertIn('ACTIVE', html)
        self.assertIn('COMPLETED', html)
        self.assertIn('PENDING', html)

        # Completion rate = 1/3 * 100 = 33.3%
        self.assertIn('33.3%', html)

        # Average evaluation score = 9.0
        self.assertIn('9.0', html)

    def test_preview_all_four_report_tabs(self):
        """
        Verifies that all 4 report previews render properly on /admin/reports?type=...
        """
        self.login('admin@test.com')

        # 1. Completion Report
        res1 = self.client.get('/admin/reports?type=completion')
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b'Internship Completion Report', res1.data)
        self.assertIn(b'TechCorp Global', res1.data)
        self.assertIn(b'Full Stack Intern', res1.data)

        # 2. Student Directory Report
        res2 = self.client.get('/admin/reports?type=students')
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b'Student Internship Report', res2.data)
        self.assertIn(b'Alice Wonder', res2.data)
        self.assertIn(b'CSE-001', res2.data)
        self.assertIn(b'Bob Builder', res2.data)

        # 3. Company Statistics Report
        res3 = self.client.get('/admin/reports?type=companies')
        self.assertEqual(res3.status_code, 200)
        self.assertIn(b'Company Internship Report', res3.data)
        self.assertIn(b'TechCorp Global', res3.data)
        self.assertIn(b'AutoDynamics', res3.data)

        # 4. Evaluation Summary Report
        res4 = self.client.get('/admin/reports?type=evaluations')
        self.assertEqual(res4.status_code, 200)
        self.assertIn(b'Faculty Evaluation Summary', res4.data)
        self.assertIn(b'Dr. Evaluation Head', res4.data)
        self.assertIn(b'9.0', res4.data)

    def test_export_csv_reports(self):
        """
        Tests CSV export for all 4 reports, verifying content structure,
        real database values, and strict security (no passwords leaked).
        """
        self.login('admin@test.com')

        for r_type in ['completion', 'students', 'companies', 'evaluations']:
            response = self.client.get(f'/admin/reports/export/{r_type}/csv')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'text/csv')
            self.assertIn(f'interntrack_{r_type}_report_', response.headers['Content-Disposition'])
            self.assertTrue(response.headers['Content-Disposition'].endswith('.csv"'))

            # Parse CSV
            csv_content = response.get_data(as_text=True)
            
            # Security Check: Ensure passwords/hashes are NOT leaked
            self.assertNotIn('SecretPassword', csv_content)
            self.assertNotIn('password_hash', csv_content)
            self.assertNotIn('pbkdf2', csv_content)

            reader = csv.reader(io.StringIO(csv_content.lstrip('\ufeff')))
            rows = list(reader)
            self.assertGreaterEqual(len(rows), 2) # At least header + 1 data row

        # Specific verification for completion CSV
        res_comp = self.client.get('/admin/reports/export/completion/csv')
        comp_text = res_comp.get_data(as_text=True)
        self.assertIn('TechCorp Global', comp_text)
        self.assertIn('Full Stack Intern', comp_text)
        self.assertIn('Completed', comp_text)

        # Specific verification for evaluations CSV
        res_eval = self.client.get('/admin/reports/export/evaluations/csv')
        eval_text = res_eval.get_data(as_text=True)
        self.assertIn('Dr. Evaluation Head', eval_text)
        self.assertIn('Outstanding engineering excellence demonstrated.', eval_text)
        self.assertIn('9.00/10', eval_text)

    def test_export_pdf_reports(self):
        """
        Tests PDF export for all 4 reports, verifying valid PDF magic header,
        non-empty binary payload, proper HTTP headers, and security.
        """
        self.login('admin@test.com')

        for r_type in ['completion', 'students', 'companies', 'evaluations']:
            response = self.client.get(f'/admin/reports/export/{r_type}/pdf')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'application/pdf')
            self.assertIn(f'interntrack_{r_type}_report_', response.headers['Content-Disposition'])
            self.assertTrue(response.headers['Content-Disposition'].endswith('.pdf"'))

            # Check PDF header (%PDF-1.)
            pdf_bytes = response.data
            self.assertTrue(pdf_bytes.startswith(b'%PDF-1.'))
            self.assertGreater(len(pdf_bytes), 1000)

            # Security check
            self.assertNotIn(b'SecretPassword999!', pdf_bytes)

    def test_filtered_report_export(self):
        """
        Tests that course filter and status filter narrow down the CSV and PDF report outputs.
        """
        self.login('admin@test.com')

        # Filter completion CSV by course=B.Tech CSE -> only student 1 placements
        res_cse = self.client.get('/admin/reports/export/completion/csv?course=B.Tech+CSE')
        self.assertEqual(res_cse.status_code, 200)
        cse_text = res_cse.get_data(as_text=True)
        self.assertIn('Alice Wonder', cse_text)
        self.assertNotIn('Bob Builder', cse_text)

        # Filter completion CSV by status=completed -> only 1 placement
        res_status = self.client.get('/admin/reports/export/completion/csv?status=completed')
        self.assertEqual(res_status.status_code, 200)
        status_text = res_status.get_data(as_text=True)
        self.assertIn('Full Stack Intern', status_text)
        self.assertNotIn('Embedded Systems Intern', status_text) # active
        self.assertNotIn('DevOps Intern', status_text)           # pending

if __name__ == '__main__':
    unittest.main()
